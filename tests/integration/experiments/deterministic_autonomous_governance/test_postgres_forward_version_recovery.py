"""Compose deterministic recovery over a real PostgreSQL version advance."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from queue import Empty, Queue
from threading import Event, Thread

import pytest
from psycopg.pq import TransactionStatus

from experiments.deterministic_autonomous_governance.executor import (
    ControlledExecutor,
)
from experiments.deterministic_autonomous_governance.model import (
    RecoveryActionKind,
    plan_recovery,
)
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
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
from src.core.order.enums import CommandType
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
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideInvocationLifecycleError,
    PostgresWriteSideInvocationOwner,
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
    """Retain candidate and delivery identity from real strict validation."""

    candidate_event: OrderEvent
    delivery: ValidationDecisionWithRuleEvidence


class _RecordingStrictValidationRuntime:
    """Record invocations while delegating to the real strict runtime."""

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
                delivery=delivery,
            )
        )
        return delivery


class _BeforeAppendOptimisticGate:
    """Pause once immediately before delegating to the real append."""

    def __init__(
        self,
        delegate: PostgresOptimisticAdmissionGate,
        *,
        append_candidates: list[OrderEvent],
        expected_versions: list[int],
        reached: Event,
        release: Event,
    ) -> None:
        self._delegate = delegate
        self._append_candidates = append_candidates
        self._expected_versions = expected_versions
        self._reached = reached
        self._release = release
        self._append_paused = False

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return self._delegate.prepare_stream(order_id)

    def append_if_admitted(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        self._append_candidates.append(candidate_event)
        self._expected_versions.append(expected_current_version)

        if not self._append_paused:
            self._append_paused = True
            self._reached.set()
            if not self._release.wait(WAIT_SECONDS):
                raise AssertionError("A1 append was not released")

        return self._delegate.append_if_admitted(
            candidate_event,
            expected_current_version,
        )


class _ObservedOptimisticGateFactory:
    """Wrap each real UOW gate while retaining append-entry observations."""

    def __init__(self, *, reached: Event, release: Event) -> None:
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
    validation_runtime: _RecordingStrictValidationRuntime,
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
    assert signature.command_type is CommandType.CREATE
    return writer.create_order(
        request_id=signature.request_id,
        order_id=signature.order_id,
        amount=signature.amount,
    )


def _start_initial(
    owner: PostgresWriteSideInvocationOwner,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def run() -> None:
        try:
            outcome.put(owner.invoke_initial())
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
    assert finished.wait(WAIT_SECONDS), "owner invocation did not finish"
    thread.join(timeout=WAIT_SECONDS)
    assert not thread.is_alive(), "owner invocation thread remained alive"
    try:
        observed = outcome.get_nowait()
    except Empty as error:
        raise AssertionError("owner invocation produced no outcome") from error
    if isinstance(observed, BaseException):
        raise observed
    assert type(observed) is PostgresWriteSideResult
    return observed


def _assert_observer_idle(connection) -> None:
    connection.rollback()
    assert connection.info.transaction_status is TransactionStatus.IDLE


def test_real_forward_conflict_composes_to_one_fresh_replay(
    db_connection,
    db_connection_factory,
) -> None:
    """Drive real A1 conflict through proposal, authority, and one owner A2."""

    signature = RequestSignature(
        request_id="autonomous-governance-forward-request",
        command_type=CommandType.CREATE,
        order_id="autonomous-governance-forward-order",
        amount=AMOUNT,
    )
    before_append = Event()
    release_append = Event()
    a_connection = db_connection_factory()
    b_connection = db_connection_factory()
    a_validation = _RecordingStrictValidationRuntime()
    b_validation = _RecordingStrictValidationRuntime()
    a_gate_factory = _ObservedOptimisticGateFactory(
        reached=before_append,
        release=release_append,
    )
    retained_writer = _writer(
        a_connection,
        a_validation,
        gate_factory=a_gate_factory,
    )
    owner = PostgresWriteSideInvocationOwner(
        request_signature=signature,
        writer=retained_writer,
    )
    b_writer = _writer(b_connection, b_validation)
    a1_thread, a1_finished, a1_outcome = _start_initial(owner)

    try:
        assert before_append.wait(WAIT_SECONDS), "A1 never reached real append"
        assert not a1_finished.is_set()
        assert a_connection.info.transaction_status is TransactionStatus.INTRANS
        assert a_connection.info.backend_pid != b_connection.info.backend_pid
        assert a_gate_factory.call_count == 1
        assert a_gate_factory.expected_versions == [0]
        assert len(a_validation.observations) == 1

        preliminary_state = PostgresIdempotencyStore(db_connection).check(
            signature
        )
        assert preliminary_state.verdict is IdempotencyVerdict.MISS
        assert preliminary_state.record is None
        _assert_observer_idle(db_connection)

        b_result = _invoke_signature(b_writer, signature)
        assert type(b_result) is PostgresWriteSideResult
        assert b_result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert b_result.accepted_event is not None
        assert b_connection.info.transaction_status is TransactionStatus.IDLE
        assert len(b_validation.observations) == 1
        assert (
            b_result.accepted_event
            is b_validation.observations[0].candidate_event
        )
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
        _assert_observer_idle(db_connection)

        release_append.set()
        a1_result = _await_result(a1_thread, a1_finished, a1_outcome)
        assert a_connection.info.transaction_status is TransactionStatus.IDLE
        assert a1_result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        assert a1_result.accepted_event is None
        assert (
            a1_result.idempotency_decision.verdict
            is IdempotencyVerdict.MISS
        )
        assert a1_result.idempotency_decision.record is None
        assert a1_result.stream_admission_result is not None
        assert (
            a1_result.stream_admission_result.verdict
            is AdmissionVerdict.ADMITTED
        )

        assert len(a_validation.observations) == 1
        a1_validation = a_validation.observations[0]
        assert a1_validation.delivery.decision.action is EnforcementAction.ALLOW
        assert (
            a1_validation.delivery.decision.validation_result.verdict
            is ValidationVerdict.PASSED
        )
        assert a1_result.validation_decision is a1_validation.delivery.decision
        assert a1_result.validation_decision_evidence is a1_validation.delivery
        assert a_gate_factory.call_count == 1
        assert a_gate_factory.append_candidates == [
            a1_validation.candidate_event
        ]
        assert a_gate_factory.expected_versions == [0]

        assert a1_result.admission_result is not None
        assert a1_result.admission_result.verdict is AdmissionVerdict.STALE_WRITE
        assert a1_result.admission_result.accepted_event_id is None
        assert (
            a1_result.admission_result.candidate_event_id
            == a1_validation.candidate_event.event_id
        )
        assert (
            a1_result.admission_result.append_version_mismatch_evidence
            == AppendVersionMismatchEvidence(
                expected_current_version=0,
                observed_current_version=1,
            )
        )

        durable_history = PostgresEventStore(db_connection).load(
            signature.order_id
        )
        assert durable_history == [b_result.accepted_event]
        assert all(
            event.event_id != a1_validation.candidate_event.event_id
            for event in durable_history
        )
        durable_idempotency = PostgresIdempotencyStore(db_connection).check(
            signature
        )
        assert durable_idempotency.verdict is IdempotencyVerdict.REPLAY
        assert durable_idempotency.record is not None
        assert durable_idempotency.record.signature == signature
        assert (
            durable_idempotency.record.accepted_event
            == b_result.accepted_event
        )
        _assert_observer_idle(db_connection)

        proposal = plan_recovery(
            request_signature=signature,
            result=a1_result,
        )
        assert proposal is not None
        assert (
            proposal.action
            is RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
        )
        assert proposal.request_signature is signature
        assert proposal.source_result is a1_result

        assessment = owner.evaluate_reinvocation_authority()
        assert type(assessment) is ReinvocationAuthorization
        assert assessment.request_signature is signature
        assert assessment.request_signature == signature

        executor = ControlledExecutor(
            owner=owner,
            expected_signature=signature,
            retained_a1_result=a1_result,
            reinvocation_assessment=assessment,
        )
        a2_result = executor.execute(proposal)

        assert type(a2_result) is PostgresWriteSideResult
        assert a2_result.outcome is PostgresWriteSideOutcome.REPLAY
        assert a2_result.accepted_event == b_result.accepted_event
        assert (
            a2_result.idempotency_decision.verdict
            is IdempotencyVerdict.REPLAY
        )
        assert a2_result.idempotency_decision.record is not None
        assert a2_result.idempotency_decision.record.signature == signature
        assert (
            a2_result.idempotency_decision.record.accepted_event
            == b_result.accepted_event
        )
        assert a2_result.stream_admission_result is None
        assert a2_result.validation_decision is None
        assert a2_result.validation_decision_evidence is None
        assert a2_result.admission_result is None

        # A2 ended at preliminary REPLAY: no A1 work was resumed or reused.
        assert len(a_validation.observations) == 1
        assert a_gate_factory.call_count == 1
        assert a_gate_factory.append_candidates == [
            a1_validation.candidate_event
        ]
        assert a_gate_factory.expected_versions == [0]

        with pytest.raises(
            PostgresWriteSideInvocationLifecycleError,
            match="authority has already been spent",
        ):
            executor.execute(proposal)

        assert len(a_validation.observations) == 1
        assert a_gate_factory.call_count == 1
        assert len(a_gate_factory.append_candidates) == 1
        final_history = PostgresEventStore(db_connection).load(
            signature.order_id
        )
        assert final_history == [b_result.accepted_event]
        final_idempotency = PostgresIdempotencyStore(db_connection).check(
            signature
        )
        assert final_idempotency.verdict is IdempotencyVerdict.REPLAY
        assert final_idempotency.record is not None
        assert final_idempotency.record.signature == signature
        assert (
            final_idempotency.record.accepted_event
            == b_result.accepted_event
        )
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
        _assert_observer_idle(db_connection)
    finally:
        release_append.set()
        if a1_thread.is_alive():
            a1_finished.wait(WAIT_SECONDS)
            a1_thread.join(timeout=WAIT_SECONDS)
        a_connection.rollback()
        a_connection.close()
        b_connection.rollback()
        b_connection.close()
