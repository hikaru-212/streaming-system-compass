"""Real direct-caller/capacity integration with deterministic waiting and fake I/O."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg import OperationalError
from psycopg.pq import TransactionStatus

from src.bootstrap.build_postgres_writer_request import build_postgres_writer_request
from src.compass.transition.types import EnforcementAction
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType
from src.pipeline.postgres_writer_request import (
    WriterCapacityRetryExhausted,
    WriterRetryCancelled,
    WriterRetryEventKind as Kind,
    WriterRetryExpired,
)
from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
)
from src.pipeline.transactional.postgres_write_side_config import ValidationPlacement
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused
from src.pipeline.writer_retry_policy import WriterRetryPolicy
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.errors import StaleWriteError
from src.storage.postgres_event_store import PostgresEventStore
from tests.unit.pipeline.transactional.test_postgres_write_side_invocation_owner import (
    _accepted_result, _conflict_result, _positive_result, _replay_result, _signature,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_characterization import (
    _FakeConnection, _ManualClock, _Probe, _Scenario,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_instrumentation import (
    _build_preview_writer, _install_preview_boundaries,
)


GUARD = 5  # Deadlock guards only; Events establish causal ordering, never sleeps.
POLICY = WriterRetryPolicy(3, (0.25, 0.5))


class Clock:
    def __init__(self):
        self.now = 10.0
        self.waits = []

    def read(self):
        return self.now

    def wait(self, delay):
        self.waits.append(delay)
        self.now += delay


def connection():
    return SimpleNamespace(info=SimpleNamespace(transaction_status=TransactionStatus.IDLE))


def build(gate, clock, *, signature=None, policy=POLICY, conn=None, **kwargs):
    return build_postgres_writer_request(
        request_signature=signature or _signature(),
        business_connection=conn or connection(),
        validation_runtime=Mock(),
        capacity_admission=gate,
        retry_policy=policy,
        clock=clock.read,
        wait=kwargs.pop("wait", clock.wait),
        **kwargs,
    )


def events(owner, kind):
    return [event for event in owner.observations if event.kind is kind]


@contextmanager
def occupied(gate):
    entered, release = Event(), Event()

    def holder():
        def body():
            entered.set()
            assert release.wait(GUARD)
        gate.run(body)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(holder)
        try:
            assert entered.wait(GUARD)

            def free():
                release.set()
                future.result(GUARD)

            yield free
        finally:
            release.set()
            future.result(GUARD)


@pytest.mark.parametrize("explicit_none", [False, True])
def test_absent_or_disabled_policy_preserves_one_refusal_and_never_reads_clock(
    monkeypatch, explicit_none,
):
    gate = BoundedWriterAdmission(1)
    forbidden = Mock(side_effect=AssertionError("disabled path must not wait/check state"))
    body = Mock(side_effect=AssertionError("refused body must not run"))
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    kwargs = {"retry_policy": None} if explicit_none else {}
    owner = build_postgres_writer_request(
        request_signature=_signature(), business_connection=object(),
        validation_runtime=Mock(), capacity_admission=gate,
        wait=forbidden, clock=forbidden, **kwargs,
    )
    with occupied(gate):
        with pytest.raises(WriterCapacityRefused) as raised:
            owner.invoke()
    assert type(raised.value) is WriterCapacityRefused
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 1
    assert events(owner, Kind.CAPACITY_REFUSED)[0].pre_body_refusal is None
    assert events(owner, Kind.ELIGIBILITY_DECIDED)[0].eligible is False
    assert not events(owner, Kind.RETRY_SCHEDULED)
    assert not events(owner, Kind.BUDGET_EXHAUSTED)
    body.assert_not_called()
    forbidden.assert_not_called()


@pytest.mark.parametrize("command", [CommandType.CREATE, CommandType.PAY])
def test_actual_caller_retries_same_signature_serially_after_release(monkeypatch, command):
    gate, clock, conn = BoundedWriterAdmission(1), Clock(), connection()
    signature = _signature(command_type=command)
    result = _accepted_result(signature)
    calls, body_entries = [], []
    original = getattr(PostgresTransactionalWriteSide, f"{command.value.lower()}_order")

    def public(writer, **kwargs):
        calls.append((RequestSignature(command_type=command, **kwargs), clock.now))
        return original(writer, **kwargs)

    def body(writer, **kwargs):
        body_entries.append(kwargs)
        with pytest.raises(WriterCapacityRefused):
            gate.run(lambda: pytest.fail("writer must own the permit"))
        return result

    monkeypatch.setattr(PostgresTransactionalWriteSide, f"{command.value.lower()}_order", public)
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    with occupied(gate) as free:
        def wait(delay):
            assert not body_entries
            assert conn.info.transaction_status is TransactionStatus.IDLE
            assert owner._lock.acquire(blocking=False)
            owner._lock.release()
            free()
            assert gate.run(lambda: "other caller progresses") == "other caller progresses"
            # A concurrent caller cannot restart this logical request or budget.
            with ThreadPoolExecutor(max_workers=1) as pool:
                repeated = pool.submit(owner.invoke)
                with pytest.raises(RuntimeError, match="already started"):
                    repeated.result(GUARD)
            clock.wait(delay)

        owner = build(gate, clock, signature=signature, conn=conn, wait=wait)
        assert owner.invoke() is result

    assert owner._signature is signature
    assert calls == [(signature, 10.0), (signature, 10.25)]
    assert len(body_entries) == 1
    assert clock.waits == [0.25]
    assert [e.attempt_number for e in events(owner, Kind.ATTEMPT_DISPATCHED)] == [1, 2]
    assert [e.kind for e in owner.observations] == [
        Kind.LOGICAL_STARTED, Kind.ATTEMPT_DISPATCHED, Kind.CAPACITY_REFUSED,
        Kind.ELIGIBILITY_DECIDED, Kind.RETRY_SCHEDULED, Kind.RETRY_READY,
        Kind.ATTEMPT_DISPATCHED, Kind.TERMINAL_RESULT,
    ]
    assert events(owner, Kind.CAPACITY_REFUSED)[0].pre_body_refusal is True
    assert events(owner, Kind.ELIGIBILITY_DECIDED)[0].eligible is True
    assert len({e.logical_invocation_id for e in owner.observations}) == 1
    assert {e.request_id for e in owner.observations} == {signature.request_id}
    assert events(owner, Kind.TERMINAL_RESULT)[0].outcome is PostgresWriteSideOutcome.ACCEPTED
    with pytest.raises(RuntimeError, match="already started"):
        owner.invoke()


@pytest.mark.parametrize("placement", list(ValidationPlacement))
@pytest.mark.parametrize("command", [CommandType.CREATE, CommandType.PAY])
def test_real_writer_algorithm_uow_and_advisory_path_not_reached_during_backoff(
    monkeypatch, placement, command,
):
    _install_preview_boundaries(monkeypatch)
    miss = IdempotencyVerdict.MISS
    scenario = _Scenario(placement, (miss, miss), pessimistic=True)
    conn = _FakeConnection(scenario, _Probe(_ManualClock()))
    conn.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
    signature = _signature(command_type=command)
    if command is CommandType.PAY:
        conn.history = [OrderAggregate(signature.order_id).create("earlier-create", signature.amount)]
    preview = _build_preview_writer(conn)
    gate, clock = BoundedWriterAdmission(1), Clock()
    with occupied(gate) as free:
        def wait(delay):
            assert not conn.inside_uow
            assert not conn.probe.events
            assert conn.idempotency_check_index == 0
            assert conn.commit_calls == conn.rollback_calls == 0
            free()
            gate.run(lambda: None)
            clock.wait(delay)

        owner = build_postgres_writer_request(
            request_signature=signature, business_connection=conn,
            validation_runtime=preview._validation_runtime,
            admission_gate_factory=preview._admission_gate_factory,
            write_side_config=preview._config, capacity_admission=gate,
            retry_policy=POLICY, wait=wait, clock=clock.read,
        )
        result = owner.invoke()
    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert conn.committed and conn.commit_calls == 1 and not conn.inside_uow
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 2
    assert clock.waits == [0.25]


@pytest.mark.parametrize("case", ["replay", "stale", "lock", "validation"])
def test_real_writer_terminal_paths_after_refusal_are_not_retried(monkeypatch, case):
    _install_preview_boundaries(monkeypatch)
    pre, inside = ValidationPlacement.PRE_TRANSACTION, ValidationPlacement.IN_TRANSACTION
    miss, replay = IdempotencyVerdict.MISS, IdempotencyVerdict.REPLAY
    scenarios = {
        "replay": _Scenario(pre, (replay,)),
        "stale": _Scenario(pre, (miss, miss)),
        "lock": _Scenario(inside, (miss,), preparation_admitted=False),
        "validation": _Scenario(pre, (miss,), validation_action=EnforcementAction.BLOCK),
    }
    conn = _FakeConnection(scenarios[case], _Probe(_ManualClock()))
    conn.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
    preview = _build_preview_writer(conn)
    if case == "stale":
        monkeypatch.setattr(PostgresEventStore, "append", Mock(side_effect=StaleWriteError("test stale")))
    gate, clock = BoundedWriterAdmission(1), Clock()
    with occupied(gate) as free:
        def wait(delay):
            assert not conn.inside_uow and not conn.probe.events
            free()
            clock.wait(delay)

        owner = build_postgres_writer_request(
            request_signature=_signature(), business_connection=conn,
            validation_runtime=preview._validation_runtime,
            admission_gate_factory=preview._admission_gate_factory,
            write_side_config=preview._config, capacity_admission=gate,
            retry_policy=POLICY, wait=wait, clock=clock.read,
        )
        result = owner.invoke()
    if case == "stale":
        assert result.admission_result.verdict is AdmissionVerdict.STALE_WRITE
    elif case == "lock":
        assert result.stream_admission_result.verdict is AdmissionVerdict.LOCK_TIMEOUT
    elif case == "validation":
        assert result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
        assert result.validation_decision.action is EnforcementAction.BLOCK
    else:
        assert result.outcome is PostgresWriteSideOutcome.REPLAY
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 2
    assert clock.waits == [0.25]
    assert not conn.committed and not conn.inside_uow


@pytest.mark.parametrize("case", ["accepted", "replay", "conflict", "stale", "lock", "validation"])
@pytest.mark.parametrize("policy", [None, POLICY])
def test_every_normal_result_is_terminal_and_identical(monkeypatch, case, policy):
    signature = _signature()
    lock = _positive_result(signature)
    outcomes = {
        "accepted": _accepted_result(signature), "replay": _replay_result(signature),
        "conflict": _conflict_result(signature), "lock": lock,
        "stale": replace(lock, stream_admission_result=replace(
            lock.stream_admission_result, verdict=AdmissionVerdict.STALE_WRITE,
        )),
        "validation": replace(lock, outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                              stream_admission_result=None),
    }
    body = Mock(return_value=outcomes[case])
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    clock = Clock()
    owner = build(BoundedWriterAdmission(1), clock, policy=policy)
    assert owner.invoke() is outcomes[case]
    body.assert_called_once()
    assert not clock.waits
    assert len(events(owner, Kind.TERMINAL_RESULT)) == 1
    assert not events(owner, Kind.ELIGIBILITY_DECIDED)


@pytest.mark.parametrize("error", [
    OperationalError("test native failure"), ValueError("test validation exception"),
    RuntimeError("test instrumentation failure"), WriterCapacityRefused("inside body"),
    WriterRetryCancelled("body error, not caller cancellation"),
    WriterRetryExpired("body error, not dispatch expiry"),
    WriterCapacityRetryExhausted(3, WriterCapacityRefused("body error")),
    KeyboardInterrupt(),
])
def test_body_failures_preserve_identity_release_capacity_and_never_retry(monkeypatch, error):
    gate, clock = BoundedWriterAdmission(1), Clock()
    body = Mock(side_effect=error)
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    owner = build(gate, clock)
    with pytest.raises(type(error)) as raised:
        owner.invoke()
    assert raised.value is error
    body.assert_called_once()
    assert not clock.waits
    assert gate.run(lambda: "released") == "released"
    if isinstance(error, WriterCapacityRefused):
        assert events(owner, Kind.CAPACITY_REFUSED)[0].pre_body_refusal is False
        assert events(owner, Kind.ELIGIBILITY_DECIDED)[0].eligible is False
    assert events(owner, Kind.TERMINAL_FAILURE)
    assert not events(owner, Kind.BUDGET_EXHAUSTED)
    assert not events(owner, Kind.CANCELLED)
    assert not events(owner, Kind.EXPIRED)


@pytest.mark.parametrize("error", [OperationalError("test native"), WriterCapacityRefused("test body")])
def test_previous_refusal_does_not_make_later_body_failure_eligible(monkeypatch, error):
    gate, clock = BoundedWriterAdmission(1), Clock()
    body = Mock(side_effect=error)
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    with occupied(gate) as free:
        def wait(delay):
            free()
            clock.wait(delay)

        owner = build(gate, clock, wait=wait)
        with pytest.raises(type(error)) as raised:
            owner.invoke()
    assert raised.value is error
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 2
    assert clock.waits == [0.25]
    if isinstance(error, WriterCapacityRefused):
        assert [e.eligible for e in events(owner, Kind.ELIGIBILITY_DECIDED)] == [True, False]
    assert not events(owner, Kind.BUDGET_EXHAUSTED)
    body.assert_called_once()


@pytest.mark.parametrize("maximum, delays", [(1, ()), (3, (0.25, 0.5))])
def test_exhaustion_is_capacity_specific_finite_and_preserves_last_refusal(maximum, delays):
    gate, clock = BoundedWriterAdmission(1), Clock()
    owner = build(gate, clock, policy=WriterRetryPolicy(maximum, delays))
    with occupied(gate):
        with pytest.raises(WriterCapacityRetryExhausted) as raised:
            owner.invoke()
    error = raised.value
    assert error.attempts_spent == maximum
    assert type(error.final_refusal) is WriterCapacityRefused
    assert error.__cause__ is error.final_refusal
    assert not isinstance(error, WriterCapacityRefused)
    assert clock.waits == list(delays)
    assert [e.attempt_number for e in events(owner, Kind.ATTEMPT_DISPATCHED)] == list(range(1, maximum + 1))
    assert len(events(owner, Kind.BUDGET_EXHAUSTED)) == 1
    assert not events(owner, Kind.TERMINAL_RESULT)
    with pytest.raises(RuntimeError, match="already started"):
        owner.invoke()


def test_distinct_requests_sharing_gate_and_policy_have_independent_budgets():
    gate, clock = BoundedWriterAdmission(1), Clock()
    owners = [build(gate, clock, signature=replace(_signature(), request_id=f"request-{i}"))
              for i in range(2)]
    with occupied(gate):
        for owner in owners:
            with pytest.raises(WriterCapacityRetryExhausted):
                owner.invoke()
    assert [len(events(o, Kind.ATTEMPT_DISPATCHED)) for o in owners] == [3, 3]
    assert len({o.observations[0].logical_invocation_id for o in owners}) == 2
    assert clock.waits == [0.25, 0.5, 0.25, 0.5]


@pytest.mark.parametrize("status", [TransactionStatus.INTRANS, TransactionStatus.INERROR,
                                   TransactionStatus.ACTIVE, TransactionStatus.UNKNOWN])
def test_preexisting_transaction_or_unknown_state_rejected_before_execution(monkeypatch, status):
    body = Mock()
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    conn, clock = connection(), Clock()
    conn.info.transaction_status = status
    owner = build(BoundedWriterAdmission(1), clock, conn=conn)
    with pytest.raises(RuntimeError, match="idle business connection"):
        owner.invoke()
    body.assert_not_called()
    assert not events(owner, Kind.ATTEMPT_DISPATCHED)
    assert not clock.waits


def test_waiter_cannot_leave_transaction_active_for_next_dispatch():
    gate, clock, conn = BoundedWriterAdmission(1), Clock(), connection()

    def wait(delay):
        clock.wait(delay)
        conn.info.transaction_status = TransactionStatus.INTRANS

    owner = build(gate, clock, conn=conn, wait=wait)
    with occupied(gate):
        with pytest.raises(RuntimeError, match="idle business connection"):
            owner.invoke()
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 1


def test_early_wait_return_cannot_dispatch_before_monotonic_eligibility():
    gate, clock = BoundedWriterAdmission(1), Clock()
    policy = WriterRetryPolicy(2, (0.25,))

    def early_wait(delay):
        clock.wait(min(delay, 0.125))

    owner = build(gate, clock, policy=policy, wait=early_wait)
    with occupied(gate):
        with pytest.raises(WriterCapacityRetryExhausted):
            owner.invoke()
    assert clock.waits == [0.125, 0.125]
    assert [e.observed_at for e in events(owner, Kind.ATTEMPT_DISPATCHED)] == [10.0, 10.25]


@pytest.mark.parametrize("mode", ["exception", "no_progress", "backward"])
def test_broken_waiter_is_terminal_without_dispatch_or_budget_refund(mode):
    gate, clock = BoundedWriterAdmission(1), Clock()
    error = RuntimeError("test waiter failure")

    def wait(delay):
        if mode == "exception":
            raise error
        if mode == "backward":
            clock.now -= 1.0

    owner = build(gate, clock, wait=wait)
    with occupied(gate):
        with pytest.raises((RuntimeError, ValueError)) as raised:
            owner.invoke()
    if mode == "exception":
        assert raised.value is error
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 1
    assert events(owner, Kind.TERMINAL_FAILURE)


@pytest.mark.parametrize("before", [True, False])
def test_cancellation_does_not_spend_an_unexecuted_attempt(before):
    gate, clock, cancel = BoundedWriterAdmission(1), Clock(), Event()
    if before:
        cancel.set()

    def wait(delay):
        clock.wait(delay)
        cancel.set()

    owner = build(gate, clock, wait=wait, cancelled=cancel.is_set)
    with occupied(gate):
        with pytest.raises(WriterRetryCancelled):
            owner.invoke()
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == (0 if before else 1)
    assert events(owner, Kind.CANCELLED)


def test_expiry_limits_wait_and_does_not_dispatch_an_extra_attempt():
    gate, clock = BoundedWriterAdmission(1), Clock()
    owner = build(gate, clock, expires_at=10.125)
    with occupied(gate):
        with pytest.raises(WriterRetryExpired):
            owner.invoke()
    assert clock.waits == [0.125]
    assert len(events(owner, Kind.ATTEMPT_DISPATCHED)) == 1
    assert events(owner, Kind.EXPIRED)


@pytest.mark.parametrize("kwargs", [
    {"retry_policy": object()}, {"capacity_admission": None},
    {"wait": None}, {"clock": None}, {"cancelled": True},
    {"expires_at": float("inf")}, {"expires_at": True},
    {"request_signature": object()},
])
def test_invalid_composition_is_rejected_before_writer_construction(monkeypatch, kwargs):
    constructor = Mock(side_effect=AssertionError("invalid configuration reached writer"))
    monkeypatch.setattr("src.pipeline.postgres_writer_request.PostgresTransactionalWriteSide", constructor)
    options = dict(request_signature=_signature(), business_connection=connection(),
                   validation_runtime=Mock(), capacity_admission=BoundedWriterAdmission(1),
                   retry_policy=POLICY)
    options.update(kwargs)
    with pytest.raises((TypeError, ValueError)):
        build_postgres_writer_request(**options)
    constructor.assert_not_called()


def test_unreviewed_capacity_adapter_cannot_supply_eligible_refusal():
    class InstrumentedAdmission(BoundedWriterAdmission):
        def run(self, operation):
            raise WriterCapacityRefused("instrumentation, not saturation")

    with pytest.raises(TypeError, match="concrete BoundedWriterAdmission"):
        build(InstrumentedAdmission(1), Clock())


def test_direct_retry_owner_cannot_be_used_as_stage4e_writer():
    from src.pipeline.transactional.postgres_write_side_invocation_owner import (
        PostgresWriteSideInvocationOwner,
    )

    owner = build(BoundedWriterAdmission(1), Clock())
    with pytest.raises(TypeError, match="writer must be PostgresTransactionalWriteSide"):
        PostgresWriteSideInvocationOwner(request_signature=_signature(), writer=owner)
    assert not hasattr(owner, "invoke_authorized_reinvocation")
    assert not hasattr(owner, "evaluate_reinvocation_authority")


def test_independent_available_caller_can_complete_while_another_waits(monkeypatch):
    # This witnesses lack of aggregate rate/queue pacing: a waiting request owns
    # only its own budget; another request can immediately use released capacity.
    gate, clock = BoundedWriterAdmission(1), Clock()
    result = _accepted_result(_signature())
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", Mock(return_value=result))
    other = build(gate, clock, signature=replace(_signature(), request_id="other"))
    with occupied(gate) as free:
        def wait(delay):
            free()
            assert other.invoke() is result
            assert len(events(other, Kind.ATTEMPT_DISPATCHED)) == 1
            clock.wait(delay)

        owner = build(gate, clock, wait=wait)
        assert owner.invoke() is result
    assert not events(other, Kind.RETRY_SCHEDULED)
