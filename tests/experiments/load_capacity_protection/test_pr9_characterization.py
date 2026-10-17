"""Deterministic production-path witnesses; no live PostgreSQL or real sleeps."""

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Lock
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.pr9_characterization import (
    ProductionLane, refused_only, request_problems, verify_durable,
)
from experiments.load_capacity_protection.pr9_model import DurableEvidence
from experiments.load_capacity_protection.pr9_postgres_runtime import read_durable, require_fresh
from src.pipeline.postgres_writer_request import WriterRetryEventKind as Retry
from src.pipeline.transactional import postgres_write_side_measurement_instrumentation as instrumentation
from src.pipeline.transactional.postgres_write_side import PostgresTransactionalWriteSide, PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_config import ValidationPlacement
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSidePhaseMeasurementState as State
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityObserver, WriterCapacityRefused
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from src.storage.errors import StaleWriteError
from tests.unit.pipeline.test_postgres_writer_request import (
    POLICY, occupied, _signature, _accepted_result, _replay_result, _conflict_result, _positive_result,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_characterization import (
    _FakeConnection, _ManualClock, _Probe, _Scenario,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_instrumentation import _install_preview_boundaries


class Clock:
    def __init__(self):
        self.now = 10_000_000_000
        self.lock = Lock()

    def read(self):
        with self.lock:
            self.now += 1
            return self.now

    def wait(self, seconds):
        with self.lock:
            self.now += round(seconds * 1e9) + 1


def connection():
    return SimpleNamespace(closed=False, autocommit=False,
                           info=SimpleNamespace(transaction_status=TransactionStatus.IDLE))


def accepted_durable(signature, event):
    return DurableEvidence((event,), 1, 1, IdempotencyVerdict.REPLAY, signature, event, None)


def absent():
    return DurableEvidence((), 0, 0, IdempotencyVerdict.MISS, None, None, None)


def invoke(monkeypatch, *, policy=POLICY, result=None, error=None, hold=False, release=True, observer_clock=None):
    clock, conn, gate = Clock(), connection(), BoundedWriterAdmission(1)
    observer = WriterCapacityObserver(clock_ns=observer_clock or clock.read)
    lane = ProductionLane(0, conn)
    value = result or _accepted_result(_signature())
    calls = []
    def body(writer, **kwargs):
        calls.append(RequestSignature(**{k: kwargs[k] for k in ("request_id", "command_type", "order_id", "amount")}))
        if error is not None:
            raise error
        return value
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    if hold:
        with occupied(gate) as free:
            def wait(delay):
                assert conn.info.transaction_status is TransactionStatus.IDLE
                assert not calls
                if release:
                    free()
                    assert gate.run(lambda: "permit free") == "permit free"
                clock.wait(delay)
            request = lane.invoke(0, _signature(), clock.read(), gate=gate, observer=observer,
                                  policy=policy, clock_ns=clock.read, wait=wait)
    else:
        request = lane.invoke(0, _signature(), clock.read(), gate=gate, observer=observer,
                              policy=policy, clock_ns=clock.read, wait=clock.wait)
    return request, calls


def test_real_owner_disabled_vs_enabled_observation_and_budget(monkeypatch):
    disabled, calls = invoke(monkeypatch, policy=None, hold=True)
    assert not calls and refused_only(disabled)
    assert sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in disabled.retry) == 1
    assert not disabled.waits and not disabled.measurements
    assert next(e for e in disabled.retry if e.kind is Retry.CAPACITY_REFUSED).pre_body_refusal is None
    assert request_problems(disabled, None) == ()
    enabled, calls = invoke(monkeypatch, hold=True)
    assert calls == [_signature()]
    assert [e.attempt_number for e in enabled.retry if e.kind is Retry.ATTEMPT_DISPATCHED] == [1, 2]
    assert enabled.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert request_problems(enabled, POLICY) == ()
    wait, = enabled.waits
    assert wait.connection_before == wait.connection_after == enabled.connection_id
    assert wait.thread_before == wait.thread_after == enabled.thread_id
    assert wait.transaction_before == wait.transaction_after == "IDLE"
    assert wait.open_before and wait.open_after
    assert wait.ended_ns > wait.started_ns


def test_exhaustion_has_no_body_or_effect_and_no_attempt_beyond_budget(monkeypatch):
    request, calls = invoke(monkeypatch, hold=True, release=False)
    assert not calls and refused_only(request)
    assert request.exception_class == "WriterCapacityRetryExhausted"
    assert sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in request.retry) == POLICY.max_attempts
    assert len(request.waits) == POLICY.max_attempts - 1
    assert request_problems(replace(request, durable=absent()), POLICY) == ()
    assert verify_durable(request, replace(absent(), request_event_count=1))


@pytest.mark.parametrize("factory", [_replay_result, _conflict_result, _positive_result,
                                      lambda s: replace(_positive_result(s), outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED)])
def test_normal_nonaccepted_is_terminal_in_actual_adapter(monkeypatch, factory):
    request, calls = invoke(monkeypatch, result=factory(_signature()))
    assert calls == [_signature()]
    assert not request.waits and request.exception_class is None
    assert request.retry[-1].kind is Retry.TERMINAL_RESULT


@pytest.mark.parametrize("error", [ValueError("native"), WriterCapacityRefused("inside admitted body")])
@pytest.mark.parametrize("hold", [False, True])
def test_native_or_body_refusal_is_never_retried(monkeypatch, error, hold):
    request, calls = invoke(monkeypatch, error=error, hold=hold)
    assert calls == [_signature()] and len(request.waits) == int(hold)
    assert not refused_only(request)
    assert request.measurements == ()
    assert request.retry[-1].kind is Retry.TERMINAL_FAILURE
    assert sum(e.eligible is True for e in request.retry) == int(hold)
    assert "unexpected_writer_failure" in request_problems(request, POLICY)


def test_durable_exact_effect_and_linkage_with_duplicate_and_unknown_rejection(monkeypatch):
    request, _ = invoke(monkeypatch)
    event = request.result.accepted_event
    evidence = accepted_durable(request.signature, event)
    assert verify_durable(request, evidence) == ()
    for bad in (replace(evidence, accepted_events=(event, event)),
                replace(evidence, identity_idempotency_count=2),
                replace(evidence, idempotency_signature=replace(request.signature, order_id="other")),
                replace(evidence, idempotency_event=replace(event, event_id="other")),
                replace(evidence, request_event_count=None),
                replace(evidence, failure="ReadFailure")):
        assert verify_durable(request, bad)


def test_failed_instrumentation_invalidates_evidence_without_changing_acceptance(monkeypatch):
    def bad_clock():
        raise WriterCapacityRefused()
    request, calls = invoke(monkeypatch, observer_clock=bad_clock)
    assert calls == [_signature()] and request.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert request.capacity == () and request.observation_failures
    assert "capacity_observation_incomplete" in request_problems(request, POLICY)
    from experiments.load_capacity_protection.pr9_characterization import summarize
    from experiments.load_capacity_protection.pr9_model import COMPOSITION, CellEvidence, schedule
    from tests.experiments.load_capacity_protection.test_pr9_runner import SOURCE, plan
    cell = CellEvidence(plan(), schedule(plan())[1], SOURCE, SOURCE, COMPOSITION, (), (request,), ())
    assert summarize(cell)["protected_writer_overlap"] is None
    assert not summarize(cell)["valid"]


@pytest.mark.parametrize("case", ["accepted", "stale", "ambiguous_commit"])
def test_actual_measured_algorithm_keeps_uow_inactive_during_wait_and_collects_phases(monkeypatch, case):
    _install_preview_boundaries(monkeypatch)
    clock = Clock()
    monkeypatch.setattr(instrumentation.time, "perf_counter_ns", clock.read)
    miss = IdempotencyVerdict.MISS
    conn = _FakeConnection(_Scenario(ValidationPlacement.PRE_TRANSACTION, (miss, miss),
                                    commit_raises=case == "ambiguous_commit"), _Probe(_ManualClock()))
    if case == "stale":
        def stale(*args, **kwargs):
            raise StaleWriteError("test stale")
        monkeypatch.setattr(PostgresEventStore, "append", stale)
    conn.closed = False
    conn.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
    lane, gate, observer = ProductionLane(0, conn), BoundedWriterAdmission(1), WriterCapacityObserver(clock_ns=clock.read)
    with occupied(gate) as free:
        def wait(delay):
            assert not conn.inside_uow and conn.commit_calls == conn.rollback_calls == 0
            assert conn.idempotency_check_index == 0
            free()
            gate.run(lambda: None)
            clock.wait(delay)
        request = lane.invoke(0, _signature(), clock.read(), gate=gate, observer=observer,
                              policy=POLICY, clock_ns=clock.read, wait=wait)
    assert sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in request.retry) == 2
    assert len(request.waits) == 1 and not conn.inside_uow
    if case == "ambiguous_commit":
        assert request.result is None and request.exception_class == "_CommitFailure"
        assert request.measurements == ()
        assert request.retry[-1].kind is Retry.TERMINAL_FAILURE
        return
    if case == "stale":
        assert request.result.append_verdict.value == "STALE_WRITE"
        assert request.retry[-1].kind is Retry.TERMINAL_RESULT
        assert conn.commit_calls == 0
        return
    assert request.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert conn.committed and not conn.inside_uow
    measurement = request.measurements[0].measurement
    for name in ("business_uow", "append_admission_call", "commit_finalization"):
        assert getattr(measurement, name).state is State.MEASURED
        assert getattr(measurement, name).elapsed_ns > 0
    assert request_problems(request, POLICY) == ()
    incomplete = replace(measurement, append_admission_call=replace(measurement.append_admission_call,
                                                                  state=State.NOT_COLLECTED, elapsed_ns=None))
    request = replace(request, measurements=(replace(request.measurements[0], measurement=incomplete),))
    assert "measurement_incomplete" in request_problems(request, POLICY)
    assert request.measurements[0].measurement.append_admission_call.elapsed_ns is None


def test_control_verifier_uses_both_raw_counts_and_preserves_unavailability(monkeypatch):
    request = _signature()
    event = _accepted_result(request).accepted_event
    commands = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args): commands.append((sql, args))
        def fetchone(self): return (1,)
    control = SimpleNamespace(rollback=lambda: None, cursor=Cursor)
    monkeypatch.setattr(PostgresEventStore, "load", lambda *a: [event])
    monkeypatch.setattr(PostgresIdempotencyStore, "check", lambda *a: SimpleNamespace(
        verdict=IdempotencyVerdict.REPLAY, record=SimpleNamespace(signature=request, accepted_event=event)))
    assert read_durable(control, request) == accepted_durable(request, event)
    assert "request_id = %s OR order_id = %s" in commands[-1][0]
    require_fresh(absent())
    with pytest.raises(ValueError):
        require_fresh(read_durable(control, request))
    monkeypatch.setattr(PostgresEventStore, "load", lambda *a: (_ for _ in ()).throw(ValueError()))
    unknown = read_durable(control, request)
    assert unknown.failure == "ValueError" and unknown.request_event_count is None
    with pytest.raises(ValueError):
        require_fresh(unknown)


def test_two_waiting_callers_retain_distinct_connections_and_budgets(monkeypatch):
    from experiments.load_capacity_protection.pr9_characterization import summarize
    from experiments.load_capacity_protection.pr9_model import COMPOSITION, CellEvidence, schedule
    from tests.experiments.load_capacity_protection.test_pr9_runner import SOURCE, plan
    gate, clock, waiting = BoundedWriterAdmission(1), Clock(), Barrier(2)
    lanes = [ProductionLane(i, connection()) for i in range(2)]
    # Keep the gate occupied for every attempt, so waiting callers can overlap
    # deterministically without injecting any test retry loop.
    def wait(delay):
        waiting.wait(5)
        clock.wait(delay)
    with occupied(gate), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(lane.invoke, i, replace(_signature(), request_id=f"r{i}"), clock.read(),
                               gate=gate, observer=WriterCapacityObserver(clock_ns=clock.read), policy=POLICY,
                               clock_ns=clock.read, wait=wait) for i, lane in enumerate(lanes)]
        requests = tuple(f.result(5) for f in futures)
    assert all(r.exception_class == "WriterCapacityRetryExhausted" for r in requests)
    assert all(sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in r.retry) == 3 for r in requests)
    assert len({r.connection_id for r in requests}) == 2
    cell = CellEvidence(plan(), schedule(plan())[1], SOURCE, SOURCE, COMPOSITION, (), requests, ())
    assert summarize(cell)["waiting_logical_peak"] == 2
    assert summarize(cell)["waiting_retained_connections_peak"] == 2
    assert all(request_problems(r, POLICY) == () for r in requests)


@pytest.mark.parametrize("changes", [{"transaction_after": "INTRANS"}, {"open_after": False},
                                    {"connection_after": -1}, {"thread_after": -1}, {"ended_ns": None}])
def test_wait_witness_detects_idle_or_retention_failure_without_changing_result(monkeypatch, changes):
    request, _ = invoke(monkeypatch, hold=True)
    changed = replace(request, waits=(replace(request.waits[0], **changes),))
    assert "wait_resource_or_release_witness" in request_problems(changed, POLICY)
    assert changed.result is request.result
