"""Characterize fresh invocation after real PostgreSQL append STALE_WRITE.

The schedules use the production write side, validation runtime, optimistic
admission gate, event store, and idempotency store. The only scheduling seam is
an invocation-local wrapper that pauses immediately before delegating to the
real optimistic append.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from queue import Empty, Queue
from threading import Event, Thread

import pytest
from psycopg.pq import TransactionStatus

from src.compass.transition.runtime import (
    ValidationDecisionWithRuleEvidence,
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationMode,
    ValidationVerdict,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    AppendVersionMismatchEvidence,
    ConcurrencyGate,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.storage.idempotency_store import (
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")

AMOUNT = Decimal("100.00")
WAIT_SECONDS = 5.0


@dataclass(frozen=True)
class _ValidationObservation:
    """Retain object identity from one real validation invocation."""

    candidate_event: OrderEvent
    context: ValidationContext
    delivery: ValidationDecisionWithRuleEvidence


class _RecordingValidationRuntime:
    """Record calls while delegating truth and policy to ValidationRuntime."""

    def __init__(self) -> None:
        self._delegate = ValidationRuntime(
            dispatcher=ValidationDispatcher(
                strict_validator=FullProofValidator(),
                off_validator=NoOpValidator(),
            ),
            policy=ValidationPolicy(),
            mode=ValidationMode.STRICT,
        )
        self.observations: list[_ValidationObservation] = []

    def decide_with_rule_evidence(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> ValidationDecisionWithRuleEvidence:
        delivery = self._delegate.decide_with_rule_evidence(
            candidate_event,
            context,
        )
        self.observations.append(
            _ValidationObservation(
                candidate_event=candidate_event,
                context=context,
                delivery=delivery,
            )
        )
        return delivery


class _BeforeAppendOptimisticGate:
    """Observe, optionally pause, then perform the real optimistic append."""

    def __init__(
        self,
        delegate: PostgresOptimisticAdmissionGate,
        *,
        append_candidates: list[OrderEvent],
        expected_versions: list[int],
        reached: Event | None,
        release: Event | None,
    ) -> None:
        self._delegate = delegate
        self._append_candidates = append_candidates
        self._expected_versions = expected_versions
        self._reached = reached
        self._release = release
        self._append_called = False

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return self._delegate.prepare_stream(order_id)

    def append_if_admitted(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        self._append_candidates.append(candidate_event)
        self._expected_versions.append(expected_current_version)

        if not self._append_called:
            self._append_called = True
            if self._reached is not None:
                assert self._release is not None
                self._reached.set()
                if not self._release.wait(WAIT_SECONDS):
                    raise AssertionError("stale writer was not released")

        return self._delegate.append_if_admitted(
            candidate_event,
            expected_current_version,
        )


class _ObservedOptimisticGateFactory:
    """Build wrappers around the UOW's real production optimistic gate."""

    def __init__(
        self,
        *,
        reached: Event | None = None,
        release: Event | None = None,
    ) -> None:
        self._reached = reached
        self._release = release
        self.call_count = 0
        self.append_candidates: list[OrderEvent] = []
        self.expected_versions: list[int] = []

    def __call__(self, uow) -> ConcurrencyGate:
        self.call_count += 1
        return _BeforeAppendOptimisticGate(
            PostgresOptimisticAdmissionGate(uow.event_store),
            append_candidates=self.append_candidates,
            expected_versions=self.expected_versions,
            reached=self._reached,
            release=self._release,
        )


def _writer(
    connection,
    validation_runtime: _RecordingValidationRuntime,
    *,
    gate_factory: _ObservedOptimisticGateFactory | None = None,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=gate_factory,
        config=PostgresWriteSideConfig(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
        ),
    )


def _invoke_signature(
    writer: PostgresTransactionalWriteSide,
    signature: RequestSignature,
) -> PostgresWriteSideResult:
    if signature.command_type is CommandType.CREATE:
        return writer.create_order(
            request_id=signature.request_id,
            order_id=signature.order_id,
            amount=signature.amount,
        )
    if signature.command_type is CommandType.PAY:
        return writer.pay_order(
            request_id=signature.request_id,
            order_id=signature.order_id,
            amount=signature.amount,
        )
    raise AssertionError(f"unsupported command: {signature.command_type!r}")


def _start_invocation(
    writer: PostgresTransactionalWriteSide,
    signature: RequestSignature,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def run() -> None:
        try:
            outcome.put(_invoke_signature(writer, signature))
        except BaseException as error:
            outcome.put(error)
        finally:
            finished.set()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread, finished, outcome


def _await_result(
    thread: Thread,
    finished: Event,
    outcome: Queue[object],
) -> PostgresWriteSideResult:
    assert finished.wait(WAIT_SECONDS), "writer invocation did not finish"
    thread.join(timeout=WAIT_SECONDS)
    assert not thread.is_alive(), "writer thread remained alive"
    try:
        observed = outcome.get_nowait()
    except Empty as error:
        raise AssertionError(
            "writer invocation produced no outcome"
        ) from error
    if isinstance(observed, BaseException):
        raise observed
    assert type(observed) is PostgresWriteSideResult
    return observed


def _assert_a1_append_stale(
    *,
    result: PostgresWriteSideResult,
    validation_runtime: _RecordingValidationRuntime,
    gate_factory: _ObservedOptimisticGateFactory,
    expected_store_version: int,
    expected_old_version: int,
) -> OrderEvent:
    assert type(result) is PostgresWriteSideResult
    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.idempotency_decision.record is None
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED

    assert len(validation_runtime.observations) == 1
    validation = validation_runtime.observations[0]
    assert validation.delivery.decision.action is EnforcementAction.ALLOW
    assert (
        validation.delivery.decision.validation_result.verdict
        is ValidationVerdict.PASSED
    )
    assert result.validation_decision is validation.delivery.decision
    assert result.validation_decision_evidence is validation.delivery

    assert gate_factory.call_count == 1
    assert gate_factory.append_candidates == [validation.candidate_event]
    assert gate_factory.append_candidates[0] is validation.candidate_event
    assert gate_factory.expected_versions == [expected_old_version]

    assert result.admission_result is not None
    assert result.admission_result.verdict is AdmissionVerdict.STALE_WRITE
    assert result.admission_result.accepted_event_id is None
    assert (
        result.admission_result.candidate_event_id
        == validation.candidate_event.event_id
    )
    assert result.admission_result.append_version_mismatch_evidence == (
        AppendVersionMismatchEvidence(
            expected_current_version=expected_old_version,
            observed_current_version=expected_store_version,
        )
    )
    return validation.candidate_event


def _assert_observer_idle(connection) -> None:
    connection.rollback()
    assert connection.info.transaction_status is TransactionStatus.IDLE


def test_same_request_winner_then_fresh_invocation_observes_real_replay(
    db_connection,
    db_connection_factory,
) -> None:
    """A2 begins only after A1's real stale result and rollback complete."""

    signature = RequestSignature(
        request_id="stage4e-append-stale-same-request",
        command_type=CommandType.CREATE,
        order_id="stage4e-append-stale-same-order",
        amount=AMOUNT,
    )
    before_append = Event()
    release_append = Event()
    a1_connection = db_connection_factory()
    b_connection = db_connection_factory()
    a1_validation = _RecordingValidationRuntime()
    b_validation = _RecordingValidationRuntime()
    a1_gate_factory = _ObservedOptimisticGateFactory(
        reached=before_append,
        release=release_append,
    )
    a1_writer = _writer(
        a1_connection,
        a1_validation,
        gate_factory=a1_gate_factory,
    )
    b_writer = _writer(b_connection, b_validation)
    a1_thread, a1_finished, a1_outcome = _start_invocation(
        a1_writer,
        signature,
    )

    try:
        assert before_append.wait(WAIT_SECONDS), "A1 never reached real append"
        assert not a1_finished.is_set()
        assert (
            a1_connection.info.transaction_status
            is TransactionStatus.INTRANS
        )
        assert a1_gate_factory.expected_versions == [0]
        assert len(a1_validation.observations) == 1

        pre_winner_idempotency = PostgresIdempotencyStore(db_connection).check(
            signature
        )
        assert pre_winner_idempotency.verdict is IdempotencyVerdict.MISS
        assert pre_winner_idempotency.record is None
        _assert_observer_idle(db_connection)

        b_result = _invoke_signature(b_writer, signature)
        assert type(b_result) is PostgresWriteSideResult
        assert b_result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert b_result.accepted_event is not None
        assert b_connection.info.transaction_status is TransactionStatus.IDLE
        assert a1_connection.info.backend_pid != b_connection.info.backend_pid
        assert len(b_validation.observations) == 1
        assert (
            b_result.accepted_event
            is b_validation.observations[0].candidate_event
        )
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
        _assert_observer_idle(db_connection)

        release_append.set()
        a1_result = _await_result(
            a1_thread,
            a1_finished,
            a1_outcome,
        )
        assert a1_connection.info.transaction_status is TransactionStatus.IDLE
        a1_candidate = _assert_a1_append_stale(
            result=a1_result,
            validation_runtime=a1_validation,
            gate_factory=a1_gate_factory,
            expected_store_version=1,
            expected_old_version=0,
        )

        durable_history = PostgresEventStore(db_connection).load(
            signature.order_id
        )
        assert durable_history == [b_result.accepted_event]
        assert all(
            event.event_id != a1_candidate.event_id
            for event in durable_history
        )
        durable_idempotency = PostgresIdempotencyStore(db_connection).check(
            signature
        )
        assert durable_idempotency.verdict is IdempotencyVerdict.REPLAY
        assert durable_idempotency.record is not None
        assert (
            durable_idempotency.record.accepted_event
            == b_result.accepted_event
        )
        _assert_observer_idle(db_connection)

        # A2 is a new public writer call with fresh runtime and gate instances.
        a2_validation = _RecordingValidationRuntime()
        a2_gate_factory = _ObservedOptimisticGateFactory()
        a2_writer = _writer(
            db_connection,
            a2_validation,
            gate_factory=a2_gate_factory,
        )
        assert a1_finished.is_set()
        a2_result = _invoke_signature(a2_writer, signature)

        assert type(a2_result) is PostgresWriteSideResult
        assert a2_result.outcome is PostgresWriteSideOutcome.REPLAY
        assert a2_result.accepted_event == b_result.accepted_event
        assert (
            a2_result.idempotency_decision.verdict
            is IdempotencyVerdict.REPLAY
        )
        assert a2_result.idempotency_decision.record is not None
        assert a2_result.idempotency_decision.record.signature == signature
        assert a2_result.stream_admission_result is None
        assert a2_result.validation_decision is None
        assert a2_result.validation_decision_evidence is None
        assert a2_result.admission_result is None
        assert a2_validation.observations == []
        assert a2_gate_factory.call_count == 0
        assert a2_gate_factory.append_candidates == []
        assert db_connection.info.transaction_status is TransactionStatus.IDLE
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
    finally:
        release_append.set()
        if a1_thread.is_alive():
            a1_finished.wait(WAIT_SECONDS)
            a1_thread.join(timeout=WAIT_SECONDS)
        a1_connection.rollback()
        a1_connection.close()
        b_connection.rollback()
        b_connection.close()


def test_competing_pay_invalidates_work_and_fresh_invocation_reloads(
    db_connection,
    db_connection_factory,
) -> None:
    """Follow PAID domain state instead of retrying A1's candidate."""

    order_id = "stage4e-append-stale-paid-order"
    seed_signature = RequestSignature(
        request_id="stage4e-append-stale-seed-create",
        command_type=CommandType.CREATE,
        order_id=order_id,
        amount=AMOUNT,
    )
    a_signature = RequestSignature(
        request_id="stage4e-append-stale-original-pay",
        command_type=CommandType.PAY,
        order_id=order_id,
        amount=AMOUNT,
    )
    b_signature = RequestSignature(
        request_id="stage4e-append-stale-competing-pay",
        command_type=CommandType.PAY,
        order_id=order_id,
        amount=AMOUNT,
    )

    seed_validation = _RecordingValidationRuntime()
    seed_result = _invoke_signature(
        _writer(db_connection, seed_validation),
        seed_signature,
    )
    assert seed_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert seed_result.accepted_event is not None
    assert seed_result.accepted_event.event_type is EventType.CREATED
    assert db_connection.info.transaction_status is TransactionStatus.IDLE

    before_append = Event()
    release_append = Event()
    a1_connection = db_connection_factory()
    b_connection = db_connection_factory()
    a1_validation = _RecordingValidationRuntime()
    b_validation = _RecordingValidationRuntime()
    a1_gate_factory = _ObservedOptimisticGateFactory(
        reached=before_append,
        release=release_append,
    )
    a1_writer = _writer(
        a1_connection,
        a1_validation,
        gate_factory=a1_gate_factory,
    )
    b_writer = _writer(b_connection, b_validation)
    a1_thread, a1_finished, a1_outcome = _start_invocation(
        a1_writer,
        a_signature,
    )

    try:
        assert before_append.wait(WAIT_SECONDS), "A1 never reached real append"
        assert not a1_finished.is_set()
        assert (
            a1_connection.info.transaction_status
            is TransactionStatus.INTRANS
        )
        assert len(a1_validation.observations) == 1
        a1_validation_observation = a1_validation.observations[0]
        assert a1_validation_observation.context.actual_prev_version == 1
        assert (
            a1_validation_observation.context.actual_prev_status
            is OrderStatus.CREATED
        )
        assert a1_gate_factory.expected_versions == [1]

        b_result = _invoke_signature(b_writer, b_signature)
        assert type(b_result) is PostgresWriteSideResult
        assert b_result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert b_result.accepted_event is not None
        assert b_result.accepted_event.event_type is EventType.PAID
        assert b_result.accepted_event.sequence == 2
        assert b_connection.info.transaction_status is TransactionStatus.IDLE
        assert a1_connection.info.backend_pid != b_connection.info.backend_pid
        assert len(b_validation.observations) == 1
        assert (
            b_result.accepted_event
            is b_validation.observations[0].candidate_event
        )
        assert (
            b_result.accepted_event
            is not a1_validation_observation.candidate_event
        )

        release_append.set()
        a1_result = _await_result(
            a1_thread,
            a1_finished,
            a1_outcome,
        )
        assert a1_connection.info.transaction_status is TransactionStatus.IDLE
        a1_candidate = _assert_a1_append_stale(
            result=a1_result,
            validation_runtime=a1_validation,
            gate_factory=a1_gate_factory,
            expected_store_version=2,
            expected_old_version=1,
        )

        authoritative_history = PostgresEventStore(db_connection).load(
            order_id
        )
        assert authoritative_history == [
            seed_result.accepted_event,
            b_result.accepted_event,
        ]
        assert [event.event_type for event in authoritative_history] == [
            EventType.CREATED,
            EventType.PAID,
        ]
        assert all(
            event.event_id != a1_candidate.event_id
            for event in authoritative_history
        )
        assert (
            PostgresIdempotencyStore(db_connection)
            .check(a_signature)
            .verdict
            is IdempotencyVerdict.MISS
        )
        assert (
            PostgresIdempotencyStore(db_connection)
            .check(b_signature)
            .verdict
            is IdempotencyVerdict.REPLAY
        )
        _assert_observer_idle(db_connection)

        # A2 is fresh: it re-enters the public PAY method with no A1 artifacts.
        a2_validation = _RecordingValidationRuntime()
        a2_gate_factory = _ObservedOptimisticGateFactory()
        a2_writer = _writer(
            db_connection,
            a2_validation,
            gate_factory=a2_gate_factory,
        )
        assert a1_finished.is_set()
        with pytest.raises(ValueError, match="^Order is already paid$"):
            _invoke_signature(a2_writer, a_signature)

        assert db_connection.info.transaction_status is TransactionStatus.IDLE
        assert a2_validation.observations == []
        assert a2_gate_factory.call_count == 0
        assert a2_gate_factory.append_candidates == []
        assert (
            a1_validation_observation.delivery
            is a1_result.validation_decision_evidence
        )
        assert count_rows(db_connection, "order_events") == 2
        assert count_rows(db_connection, "idempotency_records") == 2
    finally:
        release_append.set()
        if a1_thread.is_alive():
            a1_finished.wait(WAIT_SECONDS)
            a1_thread.join(timeout=WAIT_SECONDS)
        a1_connection.rollback()
        a1_connection.close()
        b_connection.rollback()
        b_connection.close()
