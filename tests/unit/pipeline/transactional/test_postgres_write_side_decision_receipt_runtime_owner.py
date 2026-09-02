from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier, Event, Lock
from typing import cast
from uuid import UUID

import pytest

from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_runtime_owner as runtime_owner,
    postgres_write_side_invocation_owner as invocation_module,
)
from src.compass.runtime.decision_receipt import DecisionReceipt
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
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
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideCurrentResponseEvaluation,
    PostgresWriteSideInvocationLifecycleError,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptConflictCategory,
    DecisionReceiptConflictError,
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
    PersistedDecisionReceipt,
)
from src.storage.errors import StorageInfrastructureError
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_decision_receipt_transaction_owner import (
    DecisionReceiptConnectionDisposition,
    DecisionReceiptRollbackDisposition,
    DecisionReceiptTransactionDurability,
    DecisionReceiptTransactionFailureCategory,
    PostgresDecisionReceiptTransactionOwner,
    PostgresDecisionReceiptTransactionResult,
)


RECEIPT_ID_A1 = UUID("00000000-0000-0000-0000-000000000b01")
RECEIPT_ID_A2 = UUID("00000000-0000-0000-0000-000000000b02")
RECEIPT_OUTCOME_ID_A1 = UUID("00000000-0000-0000-0000-000000000b11")
RECEIPT_OUTCOME_ID_A2 = UUID("00000000-0000-0000-0000-000000000b12")
STAGE4C_OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000b21")
MATERIALIZED_AT = datetime(2026, 8, 29, tzinfo=timezone.utc)
PROVENANCE = DecisionReceiptMaterializationProvenance.LIVE_RESULT
WAIT_SECONDS = 5.0

PostgresWriteSideDecisionReceiptCompletedInvocation = (
    runtime_owner.PostgresWriteSideDecisionReceiptCompletedInvocation
)
PostgresWriteSideDecisionReceiptPersistenceEligibility = (
    runtime_owner.PostgresWriteSideDecisionReceiptPersistenceEligibility
)
PostgresWriteSideDecisionReceiptRuntimeDelivery = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeDelivery
)
PostgresWriteSideDecisionReceiptRuntimeLifecycleError = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeLifecycleError
)
PostgresWriteSideDecisionReceiptRuntimeOwner = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeOwner
)
PostgresWriteSideDecisionReceiptRuntimeStatus = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeStatus
)
evaluate_postgres_write_side_decision_receipt_persistence_eligibility = (
    runtime_owner
    .evaluate_postgres_write_side_decision_receipt_persistence_eligibility
)


PersistenceResultFactory = Callable[
    [DecisionReceipt],
    PostgresDecisionReceiptTransactionResult,
]


class _SequencedWriteSide(PostgresTransactionalWriteSide):
    """Return deterministic normal results through the real invocation API."""

    def __init__(self, results: list[PostgresWriteSideResult]) -> None:
        self._results = results
        self._calls_lock = Lock()
        self.calls: list[tuple[CommandType, str, str, Decimal]] = []

    def create_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._record_and_return(
            command_type=CommandType.CREATE,
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )

    def pay_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._record_and_return(
            command_type=CommandType.PAY,
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )

    def _record_and_return(
        self,
        *,
        command_type: CommandType,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        with self._calls_lock:
            self.calls.append(
                (command_type, request_id, order_id, amount)
            )
            call_index = len(self.calls) - 1
        if call_index >= len(self._results):
            raise AssertionError("unexpected public-writer entry")
        return self._results[call_index]


class _CapturingReceiptTransactionOwner(
    PostgresDecisionReceiptTransactionOwner
):
    """Capture persistence calls and return one existing result contract."""

    def __init__(
        self,
        result_factory: PersistenceResultFactory,
        *,
        persistence_entered: Event | None = None,
        release_persistence: Event | None = None,
    ) -> None:
        super().__init__(
            lambda: (_ for _ in ()).throw(
                AssertionError(
                    "overridden persist must not acquire connection"
                )
            ),
            idle_in_transaction_session_timeout_ms=1,
        )
        self._result_factory = result_factory
        self._persistence_entered = persistence_entered
        self._release_persistence = release_persistence
        self.calls: list[
            tuple[
                DecisionReceipt,
                DecisionReceiptMaterializationProvenance,
            ]
        ] = []
        self.results: list[PostgresDecisionReceiptTransactionResult] = []

    def persist(
        self,
        receipt: DecisionReceipt,
        *,
        materialization_provenance: (
            DecisionReceiptMaterializationProvenance
        ),
    ) -> PostgresDecisionReceiptTransactionResult:
        self.calls.append((receipt, materialization_provenance))
        if self._persistence_entered is not None:
            self._persistence_entered.set()
        if self._release_persistence is not None:
            if not self._release_persistence.wait(WAIT_SECONDS):
                raise AssertionError("test did not release persistence")
        result = self._result_factory(receipt)
        self.results.append(result)
        return result


class _IdentitySequence:
    """Supply deterministic owner-local identities without attempt identity."""

    def __init__(self, identities: list[UUID]) -> None:
        self._identities = identities
        self.calls = 0

    def __call__(self) -> UUID:
        if self.calls >= len(self._identities):
            raise AssertionError("unexpected identity allocation")
        identity = self._identities[self.calls]
        self.calls += 1
        return identity


class _InfrastructureFailingEventStore:
    """Raise one real storage exception through PostgreSQL gate translation."""

    def __init__(self, diagnostic_sentinel: str) -> None:
        self._diagnostic_sentinel = diagnostic_sentinel

    def append(self, *_args: object, **_kwargs: object) -> None:
        raise StorageInfrastructureError(self._diagnostic_sentinel)


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="decision-receipt-pr3-request",
        command_type=CommandType.CREATE,
        order_id="decision-receipt-pr3-order",
        amount=Decimal("100.00"),
    )


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="No prior request with this request_id",
        record=None,
    )


def _validation_decision(
    *,
    candidate_event_id: str,
    action: EnforcementAction,
    verdict: ValidationVerdict,
) -> ValidationDecision:
    return ValidationDecision(
        action=action,
        validation_result=ValidationResult(
            verdict=verdict,
            reason=(
                "Event passed full proof transition validation"
                if action is EnforcementAction.ALLOW
                else "Proof mismatch: prev_version does not match history"
            ),
            candidate_event_id=candidate_event_id,
            validator_name="FullProofValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        ),
    )


def _accepted_result(
    signature: RequestSignature | None = None,
) -> PostgresWriteSideResult:
    signature = signature or _signature()
    event = OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id=signature.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=event.event_id,
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Event admitted by PostgreSQL optimistic admission gate",
            candidate_event_id=event.event_id,
            accepted_event_id=event.event_id,
        ),
    )


def _validation_blocked_result() -> PostgresWriteSideResult:
    signature = _signature()
    candidate = OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id=signature.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=candidate.event_id,
            action=EnforcementAction.BLOCK,
            verdict=ValidationVerdict.FAILED,
        ),
    )


def _replay_result() -> PostgresWriteSideResult:
    signature = _signature()
    accepted = _accepted_result(signature)
    assert accepted.accepted_event is not None
    record = IdempotencyRecord(
        signature=signature,
        accepted_event=accepted.accepted_event,
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.REPLAY,
        accepted_event=record.accepted_event,
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.REPLAY,
            reason="Semantically identical retry detected",
            record=record,
        ),
    )


def _conflict_result() -> PostgresWriteSideResult:
    replay = _replay_result()
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=replay.idempotency_decision.record,
        ),
    )


def _preparation_lock_timeout_result() -> PostgresWriteSideResult:
    signature = _signature()
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason=(
                "Stream lock was not available for PostgreSQL pessimistic "
                f"admission gate: order_id={signature.order_id}"
            ),
            order_id=signature.order_id,
        ),
    )


def _translated_infrastructure_failure_result(
    diagnostic_sentinel: str,
) -> PostgresWriteSideResult:
    signature = _signature()
    candidate = OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )
    gate = PostgresOptimisticAdmissionGate(
        cast(object, _InfrastructureFailingEventStore(diagnostic_sentinel))
    )
    admission_result = gate.append_if_admitted(
        candidate,
        expected_current_version=0,
    )
    assert admission_result.verdict is AdmissionVerdict.INFRASTRUCTURE_ERROR
    assert diagnostic_sentinel in admission_result.reason
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id=signature.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=candidate.event_id,
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
        ),
        admission_result=admission_result,
    )


def _invalid_accepted_result() -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=None,
        idempotency_decision=_miss(),
    )


def _statement_result(
    receipt: DecisionReceipt,
    *,
    status: DecisionReceiptInsertStatus = DecisionReceiptInsertStatus.INSERTED,
) -> DecisionReceiptInsertResult:
    return DecisionReceiptInsertResult(
        status=status,
        record=PersistedDecisionReceipt(
            receipt=receipt,
            receipt_serialization_version=1,
            materialization_provenance=PROVENANCE,
            materialized_at=MATERIALIZED_AT,
        ),
    )


def _committed_result(
    receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    return PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.COMMITTED,
        rollback_disposition=DecisionReceiptRollbackDisposition.NOT_REQUIRED,
        statement_result=_statement_result(receipt),
        connection_disposition=DecisionReceiptConnectionDisposition.CLOSED,
    )


def _already_present_result(
    receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    return PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.COMMITTED,
        rollback_disposition=DecisionReceiptRollbackDisposition.NOT_REQUIRED,
        statement_result=_statement_result(
            receipt,
            status=DecisionReceiptInsertStatus.ALREADY_PRESENT,
        ),
        connection_disposition=DecisionReceiptConnectionDisposition.CLOSED,
    )


def _not_committed_result(
    _receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    return PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
        rollback_disposition=DecisionReceiptRollbackDisposition.NOT_REQUIRED,
        failure_category=(
            DecisionReceiptTransactionFailureCategory
            .CONNECTION_ACQUISITION_FAILED
        ),
    )


def _unknown_result(
    receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    return PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.UNKNOWN,
        rollback_disposition=DecisionReceiptRollbackDisposition.NOT_POSSIBLE,
        statement_result=_statement_result(receipt),
        failure_category=(
            DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
        ),
        connection_disposition=DecisionReceiptConnectionDisposition.DISCARDED,
    )


def _conflict_persistence_result(
    receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    conflict = DecisionReceiptConflictError(
        category=(
            DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
        ),
        receipt_id=receipt.receipt_id,
    )
    return PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
        rollback_disposition=DecisionReceiptRollbackDisposition.CONFIRMED,
        failure_category=DecisionReceiptTransactionFailureCategory.CONFLICT,
        conflict_error=conflict,
        connection_disposition=DecisionReceiptConnectionDisposition.CLOSED,
    )


def _raise_unexpected(
    _receipt: DecisionReceipt,
) -> PostgresDecisionReceiptTransactionResult:
    raise RuntimeError("raw unexpected persistence diagnostic sentinel")


def _runtime_owner(
    results: list[PostgresWriteSideResult],
    result_factory: PersistenceResultFactory = _committed_result,
    *,
    receipt_ids: Callable[[], UUID] = lambda: RECEIPT_ID_A1,
    receipt_outcome_ids: Callable[[], UUID] = (
        lambda: RECEIPT_OUTCOME_ID_A1
    ),
    persistence_entered: Event | None = None,
    release_persistence: Event | None = None,
) -> tuple[
    PostgresWriteSideDecisionReceiptRuntimeOwner,
    _SequencedWriteSide,
    _CapturingReceiptTransactionOwner,
]:
    writer = _SequencedWriteSide(results)
    transaction_owner = _CapturingReceiptTransactionOwner(
        result_factory,
        persistence_entered=persistence_entered,
        release_persistence=release_persistence,
    )
    owner = PostgresWriteSideDecisionReceiptRuntimeOwner(
        request_signature=_signature(),
        writer=writer,
        receipt_transaction_owner=transaction_owner,
        receipt_id_factory=receipt_ids,
        receipt_outcome_id_factory=receipt_outcome_ids,
    )
    return owner, writer, transaction_owner


def _exact_persistence_result(
    delivery: PostgresWriteSideDecisionReceiptRuntimeDelivery,
) -> PostgresDecisionReceiptTransactionResult:
    persistence_delivery = delivery.persistence_delivery
    assert persistence_delivery is not None
    result = persistence_delivery.persistence_result
    assert result is not None
    return result


def test_a1_normal_completion_creates_one_private_retained_owner_graph(
) -> None:
    result = _accepted_result()
    owner, writer, transaction_owner = _runtime_owner([result])

    completion = owner.invoke_initial()

    assert completion.business_result is result
    assert owner.initial_completion is completion
    assert owner.initial_completion is completion
    assert completion.__dict__["_materialization_owner"] is (
        completion.__dict__["_persistence_owner"].__dict__[
            "_materialization_owner"
        ]
    )
    assert transaction_owner.calls == []
    assert len(writer.calls) == 1
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has already started",
    ):
        owner.invoke_initial()
    assert len(writer.calls) == 1


def test_validation_blocked_repeated_access_cannot_create_duplicate_receipts(
) -> None:
    result = _validation_blocked_result()
    owner, _writer, transaction_owner = _runtime_owner([result])
    completion = owner.invoke_initial()

    first = completion.compose_receipt()
    second = completion.compose_receipt()

    assert second is first
    assert first.business_result is result
    assert result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert first.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_COMPLETED
    )
    persistence_delivery = first.persistence_delivery
    assert persistence_delivery is not None
    receipt = persistence_delivery.materialization_delivery.receipt
    assert receipt is not None
    assert transaction_owner.calls == [(receipt, PROVENANCE)]
    assert _exact_persistence_result(first) is transaction_owner.results[0]


def test_concurrent_receipt_access_uses_one_graph_and_one_persistence_call(
) -> None:
    caller_count = 2
    callers_ready = Barrier(caller_count)
    persistence_entered = Event()
    release_persistence = Event()
    owner, _writer, transaction_owner = _runtime_owner(
        [_accepted_result()],
        persistence_entered=persistence_entered,
        release_persistence=release_persistence,
    )
    completion = owner.invoke_initial()

    def compose_after_barrier(
    ) -> PostgresWriteSideDecisionReceiptRuntimeDelivery:
        callers_ready.wait(timeout=WAIT_SECONDS)
        return completion.compose_receipt()

    with ThreadPoolExecutor(max_workers=caller_count) as executor:
        futures = [
            executor.submit(compose_after_barrier)
            for _ in range(caller_count)
        ]
        try:
            assert persistence_entered.wait(WAIT_SECONDS)
        finally:
            release_persistence.set()
        deliveries = [
            future.result(timeout=WAIT_SECONDS) for future in futures
        ]

    assert deliveries[1] is deliveries[0]
    assert len(transaction_owner.calls) == 1


def test_a2_has_distinct_handle_and_a1_survives_current_response_clearing(
) -> None:
    a1_result = _preparation_lock_timeout_result()
    a2_result = _accepted_result()
    receipt_ids = _IdentitySequence([RECEIPT_ID_A1, RECEIPT_ID_A2])
    receipt_outcome_ids = _IdentitySequence(
        [RECEIPT_OUTCOME_ID_A1, RECEIPT_OUTCOME_ID_A2]
    )
    owner, writer, _transaction_owner = _runtime_owner(
        [a1_result, a2_result],
        receipt_ids=receipt_ids,
        receipt_outcome_ids=receipt_outcome_ids,
    )

    a1 = owner.invoke_initial()
    a1_receipt = a1.compose_receipt()
    authority = owner.evaluate_reinvocation_authority()
    a2 = owner.invoke_authorized_reinvocation()

    assert isinstance(authority, ReinvocationAuthorization)
    assert a2 is owner.authorized_reinvocation_completion
    assert a2 is not a1
    assert a2.business_result is a2_result
    assert owner.initial_completion is a1
    assert a1.compose_receipt() is a1_receipt
    assert (
        a2.__dict__["_materialization_owner"]
        is not a1.__dict__["_materialization_owner"]
    )
    assert a2.__dict__["_persistence_owner"] is not (
        a1.__dict__["_persistence_owner"]
    )
    assert len(writer.calls) == 2
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="authority has already been spent",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 2


def test_stage4e_remains_required_before_a2_and_no_a3_is_created() -> None:
    owner, writer, _transaction_owner = _runtime_owner(
        [_preparation_lock_timeout_result(), _accepted_result()]
    )
    owner.invoke_initial()

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="authority has not been explicitly evaluated",
    ):
        owner.invoke_authorized_reinvocation()

    owner.evaluate_reinvocation_authority()
    owner.invoke_authorized_reinvocation()

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="authority has already been spent",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 2


def test_receipt_composes_before_lazy_stage4c_with_independent_outcome_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invocation_module,
        "uuid4",
        lambda: STAGE4C_OUTCOME_ID,
    )
    result = _accepted_result()
    owner, _writer, _transaction_owner = _runtime_owner([result])
    completion = owner.invoke_initial()

    receipt_delivery = completion.compose_receipt()
    persistence_delivery = receipt_delivery.persistence_delivery
    assert persistence_delivery is not None
    receipt = persistence_delivery.materialization_delivery.receipt
    assert receipt is not None
    assert receipt.outcome_id is RECEIPT_OUTCOME_ID_A1

    current_response = owner.evaluate_current_response()

    assert isinstance(
        current_response,
        PostgresWriteSideCurrentResponseEvaluation,
    )
    stage4c_outcome = (
        current_response.evaluation.source_feedback.semantic_outcome
    )
    assert stage4c_outcome.outcome_id is STAGE4C_OUTCOME_ID
    assert stage4c_outcome.outcome_id != receipt.outcome_id


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            _accepted_result(),
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_ACCEPTED,
        ),
        (
            _replay_result(),
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_IDEMPOTENT_REPLAY,
        ),
        (
            _conflict_result(),
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_IDEMPOTENCY_CONFLICT,
        ),
        (
            _validation_blocked_result(),
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_VALIDATION_BLOCKED,
        ),
        (
            _preparation_lock_timeout_result(),
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_PREPARATION_LOCK_TIMEOUT,
        ),
    ],
)
def test_reviewed_positive_eligibility_profiles(
    result: PostgresWriteSideResult,
    expected: PostgresWriteSideDecisionReceiptPersistenceEligibility,
) -> None:
    assert (
        evaluate_postgres_write_side_decision_receipt_persistence_eligibility(
            result
        )
        is expected
    )


def test_real_translated_technical_failure_is_ineligible_and_not_persisted(
) -> None:
    diagnostic_sentinel = "raw-driver-diagnostic-must-not-be-durable"
    result = _translated_infrastructure_failure_result(
        diagnostic_sentinel
    )
    owner, _writer, transaction_owner = _runtime_owner([result])

    completion = owner.invoke_initial()
    first = completion.compose_receipt()
    second = completion.compose_receipt()

    assert second is first
    assert completion.business_result is result
    assert diagnostic_sentinel in result.admission_result.reason
    assert completion.persistence_eligibility is (
        PostgresWriteSideDecisionReceiptPersistenceEligibility.INELIGIBLE
    )
    assert first.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_INELIGIBLE
    )
    assert first.persistence_delivery is None
    assert transaction_owner.calls == []
    assert transaction_owner.results == []
    assert completion.__dict__["_persistence_owner"] is None
    assert (
        completion.__dict__["_materialization_owner"].__dict__[
            "_cached_delivery"
        ]
        is None
    )


def test_unknown_unreviewed_profile_fails_closed() -> None:
    future_result = PostgresWriteSideResult(
        outcome=cast(PostgresWriteSideOutcome, "FUTURE_PROFILE"),
        accepted_event=None,
        idempotency_decision=_miss(),
    )

    assert (
        evaluate_postgres_write_side_decision_receipt_persistence_eligibility(
            future_result
        )
        is PostgresWriteSideDecisionReceiptPersistenceEligibility.INELIGIBLE
    )


@pytest.mark.parametrize(
    ("result_factory", "expected_durability"),
    [
        (
            _committed_result,
            DecisionReceiptTransactionDurability.COMMITTED,
        ),
        (
            _not_committed_result,
            DecisionReceiptTransactionDurability.NOT_COMMITTED,
        ),
        (
            _unknown_result,
            DecisionReceiptTransactionDurability.UNKNOWN,
        ),
    ],
)
def test_accepted_business_truth_survives_exact_persistence_durability(
    result_factory: PersistenceResultFactory,
    expected_durability: DecisionReceiptTransactionDurability,
) -> None:
    result = _accepted_result()
    owner, _writer, transaction_owner = _runtime_owner(
        [result],
        result_factory,
    )

    completion = owner.invoke_initial()
    delivery = completion.compose_receipt()
    repeated_delivery = completion.compose_receipt()

    assert repeated_delivery is delivery
    assert delivery.business_result is result
    assert delivery.business_result.outcome is (
        PostgresWriteSideOutcome.ACCEPTED
    )
    assert delivery.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_COMPLETED
    )
    exact_result = _exact_persistence_result(delivery)
    assert exact_result is transaction_owner.results[0]
    assert exact_result.durability is expected_durability
    assert len(transaction_owner.calls) == 1


@pytest.mark.parametrize(
    "result_factory",
    [_already_present_result, _conflict_persistence_result],
)
def test_existing_already_present_and_typed_conflict_evidence_is_unchanged(
    result_factory: PersistenceResultFactory,
) -> None:
    owner, _writer, transaction_owner = _runtime_owner(
        [_accepted_result()],
        result_factory,
    )

    first = owner.invoke_initial().compose_receipt()
    exact_result = _exact_persistence_result(first)

    assert exact_result is transaction_owner.results[0]
    assert (
        exact_result.statement_result is not None
        or exact_result.conflict_error is not None
    )


def test_unexpected_persistence_exception_is_terminal_without_pr2_reentry(
) -> None:
    result = _accepted_result()
    owner, _writer, transaction_owner = _runtime_owner(
        [result],
        _raise_unexpected,
    )
    completion = owner.invoke_initial()

    first = completion.compose_receipt()
    second = completion.compose_receipt()

    assert second is first
    assert first.business_result is result
    assert first.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus
        .UNEXPECTED_COMPOSITION_EXCEPTION
    )
    assert first.persistence_delivery is None
    assert len(transaction_owner.calls) == 1
    assert transaction_owner.results == []
    assert "diagnostic" not in repr(first)


def test_materialization_failure_is_distinct_and_never_reaches_persistence(
) -> None:
    result = _invalid_accepted_result()
    owner, _writer, transaction_owner = _runtime_owner([result])

    delivery = owner.invoke_initial().compose_receipt()

    assert delivery.business_result is result
    assert delivery.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.MATERIALIZATION_FAILED
    )
    persistence_delivery = delivery.persistence_delivery
    assert persistence_delivery is not None
    assert persistence_delivery.persistence_reached is False
    assert persistence_delivery.persistence_result is None
    assert transaction_owner.calls == []


def test_completed_handle_and_delivery_are_frozen_and_bounded() -> None:
    owner, _writer, _transaction_owner = _runtime_owner(
        [_accepted_result()]
    )
    completion = owner.invoke_initial()
    delivery = completion.compose_receipt()

    with pytest.raises(FrozenInstanceError):
        completion.business_result = _accepted_result()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        delivery.persistence_delivery = None  # type: ignore[misc]
    assert [item.name for item in fields(delivery)] == [
        "business_result",
        "persistence_eligibility",
        "status",
        "persistence_delivery",
    ]
    assert "attempt" not in " ".join(owner.__dict__).lower()
    assert not any(
        isinstance(value, list) for value in owner.__dict__.values()
    )
    assert set(owner.__dict__) >= {
        "_initial_completion",
        "_authorized_reinvocation_completion",
    }


def test_completion_accessors_refuse_before_normal_completion() -> None:
    owner, _writer, _transaction_owner = _runtime_owner(
        [_accepted_result()]
    )

    with pytest.raises(
        PostgresWriteSideDecisionReceiptRuntimeLifecycleError,
        match="initial invocation has not completed normally",
    ):
        _ = owner.initial_completion
    with pytest.raises(
        PostgresWriteSideDecisionReceiptRuntimeLifecycleError,
        match="authorized re-invocation has not completed normally",
    ):
        _ = owner.authorized_reinvocation_completion


def test_completed_handle_cannot_be_constructed_from_a_raw_result() -> None:
    with pytest.raises(
        TypeError,
        match="must be produced by",
    ):
        PostgresWriteSideDecisionReceiptCompletedInvocation(
            business_result=_accepted_result()
        )
