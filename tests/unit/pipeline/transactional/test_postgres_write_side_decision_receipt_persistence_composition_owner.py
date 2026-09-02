from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from decimal import Decimal
from inspect import signature
from threading import Barrier, Event, Lock
from typing import TypeAlias
from uuid import UUID

import pytest
from psycopg import Connection

from src.compass.runtime.decision_receipt import DecisionReceipt
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_materialization_owner as materialization,
    postgres_write_side_decision_receipt_persistence_composition_owner as composition,
)
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
    PersistedDecisionReceipt,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
)
from src.storage.postgres_decision_receipt_transaction_owner import (
    DecisionReceiptConnectionDisposition,
    DecisionReceiptRollbackDisposition,
    DecisionReceiptTransactionDurability,
    DecisionReceiptTransactionFailureCategory,
    PostgresDecisionReceiptTransactionOwner,
    PostgresDecisionReceiptTransactionResult,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000a01")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000a02")
MATERIALIZED_AT = datetime(2026, 8, 27, tzinfo=timezone.utc)
PROVENANCE = DecisionReceiptMaterializationProvenance.LIVE_RESULT
WAIT_SECONDS = 5.0

CompositionDelivery: TypeAlias = (
    composition.PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery
)
CompositionOwner: TypeAlias = (
    composition.PostgresWriteSideDecisionReceiptPersistenceCompositionOwner
)
MaterializationStatus = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationStatus
)
PersistenceResultFactory: TypeAlias = Callable[
    [DecisionReceipt],
    PostgresDecisionReceiptTransactionResult,
]


class _CountingMaterializationOwner(
    materialization.PostgresWriteSideDecisionReceiptMaterializationOwner
):
    """Use the real PR1 lifecycle while exposing compose-call evidence."""

    def __init__(self, completed_result: PostgresWriteSideResult) -> None:
        super().__init__(
            completed_result=completed_result,
            receipt_id_factory=lambda: RECEIPT_ID,
            outcome_id_factory=lambda: OUTCOME_ID,
        )
        self.calls = 0
        self.deliveries: list[
            materialization
            .PostgresWriteSideDecisionReceiptMaterializationDelivery
        ] = []
        self._calls_lock = Lock()

    def materialize(
        self,
    ) -> (
        materialization
        .PostgresWriteSideDecisionReceiptMaterializationDelivery
    ):
        with self._calls_lock:
            self.calls += 1
        delivery = super().materialize()
        self.deliveries.append(delivery)
        return delivery


class _CapturingReceiptTransactionOwner(
    PostgresDecisionReceiptTransactionOwner
):
    """Capture exact receipt custody and return existing result contracts."""

    def __init__(
        self,
        result_factory: PersistenceResultFactory,
        *,
        persistence_entered: Event | None = None,
        release_persistence: Event | None = None,
    ) -> None:
        def unused_connection_factory() -> Connection[object]:
            raise AssertionError("overridden persist must not acquire connection")

        super().__init__(
            unused_connection_factory,
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
                raise AssertionError("test did not release receipt persistence")
        result = self._result_factory(receipt)
        self.results.append(result)
        return result


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="persistence-composition test miss",
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
            reason="persistence-composition test validation",
            candidate_event_id=candidate_event_id,
            validator_name="PersistenceCompositionTestValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        ),
    )


def _accepted_result() -> PostgresWriteSideResult:
    event = OrderAggregate("persistence-composition-order").create(
        "persistence-composition-request",
        Decimal("100.00"),
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="persistence-composition stream admitted",
            order_id=event.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=event.event_id,
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="persistence-composition append admitted",
            candidate_event_id=event.event_id,
            accepted_event_id=event.event_id,
        ),
    )


def _validation_blocked_result() -> PostgresWriteSideResult:
    candidate = OrderAggregate(
        "persistence-composition-blocked-order"
    ).create(
        "persistence-composition-blocked-request",
        Decimal("100.00"),
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="persistence-composition stream admitted",
            order_id=candidate.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=candidate.event_id,
            action=EnforcementAction.BLOCK,
            verdict=ValidationVerdict.FAILED,
        ),
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


def _composition(
    business_result: PostgresWriteSideResult,
    result_factory: PersistenceResultFactory,
    *,
    persistence_entered: Event | None = None,
    release_persistence: Event | None = None,
) -> tuple[
    CompositionOwner,
    _CountingMaterializationOwner,
    _CapturingReceiptTransactionOwner,
]:
    materialization_owner = _CountingMaterializationOwner(business_result)
    receipt_transaction_owner = _CapturingReceiptTransactionOwner(
        result_factory,
        persistence_entered=persistence_entered,
        release_persistence=release_persistence,
    )
    owner = CompositionOwner(
        materialization_owner=materialization_owner,
        receipt_transaction_owner=receipt_transaction_owner,
    )
    return owner, materialization_owner, receipt_transaction_owner


def test_accepted_committed_retains_exact_business_materialization_and_persistence(
) -> None:
    business_result = _accepted_result()
    owner, materialization_owner, receipt_owner = _composition(
        business_result,
        _committed_result,
    )

    delivery = owner.compose()

    assert delivery.business_result is business_result
    assert delivery.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert delivery.materialization_delivery is (
        materialization_owner.deliveries[0]
    )
    assert delivery.materialization_delivery.status is (
        MaterializationStatus.MATERIALIZED
    )
    receipt = delivery.materialization_delivery.receipt
    assert receipt is not None
    assert receipt_owner.calls == [(receipt, PROVENANCE)]
    assert receipt_owner.calls[0][0] is receipt
    assert delivery.persistence_reached is True
    assert delivery.persistence_result is receipt_owner.results[0]
    assert delivery.persistence_result.durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )


def test_validation_blocked_can_commit_receipt_without_becoming_accepted(
) -> None:
    business_result = _validation_blocked_result()
    owner, _materialization_owner, receipt_owner = _composition(
        business_result,
        _committed_result,
    )

    delivery = owner.compose()

    assert delivery.business_result is business_result
    assert delivery.business_result.outcome is (
        PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )
    assert delivery.business_result.accepted_event is None
    assert delivery.materialization_delivery.receipt is not None
    assert receipt_owner.calls[0][0] is (
        delivery.materialization_delivery.receipt
    )
    assert delivery.persistence_result is receipt_owner.results[0]
    assert delivery.persistence_result.durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )


def test_materialization_failure_is_explicitly_persistence_not_reached(
) -> None:
    business_result = _invalid_accepted_result()
    owner, materialization_owner, receipt_owner = _composition(
        business_result,
        _committed_result,
    )

    delivery = owner.compose()

    assert delivery.business_result is business_result
    assert delivery.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert delivery.materialization_delivery is (
        materialization_owner.deliveries[0]
    )
    assert delivery.materialization_delivery.status is (
        MaterializationStatus.MATERIALIZATION_FAILED
    )
    assert delivery.materialization_delivery.receipt is None
    assert delivery.persistence_reached is False
    assert delivery.persistence_result is None
    assert receipt_owner.calls == []
    assert receipt_owner.results == []


def test_accepted_not_committed_preserves_business_and_transaction_evidence(
) -> None:
    business_result = _accepted_result()
    owner, _materialization_owner, receipt_owner = _composition(
        business_result,
        _not_committed_result,
    )

    delivery = owner.compose()

    assert delivery.business_result is business_result
    assert delivery.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert delivery.persistence_result is receipt_owner.results[0]
    assert delivery.persistence_result.durability is (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )


def test_accepted_unknown_is_cached_without_retry_or_business_rewrite(
) -> None:
    business_result = _accepted_result()
    owner, materialization_owner, receipt_owner = _composition(
        business_result,
        _unknown_result,
    )

    first = owner.compose()
    second = owner.compose()

    assert second is first
    assert first.business_result is business_result
    assert first.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert first.persistence_result is receipt_owner.results[0]
    assert first.persistence_result.durability is (
        DecisionReceiptTransactionDurability.UNKNOWN
    )
    assert materialization_owner.calls == 1
    assert len(receipt_owner.calls) == 1
    assert len(receipt_owner.results) == 1


def test_repeated_compose_materializes_persists_and_delivers_once() -> None:
    owner, materialization_owner, receipt_owner = _composition(
        _accepted_result(),
        _committed_result,
    )

    first = owner.compose()
    second = owner.compose()

    assert second is first
    assert materialization_owner.calls == 1
    assert len(materialization_owner.deliveries) == 1
    assert len(receipt_owner.calls) == 1
    assert len(receipt_owner.results) == 1


def test_concurrent_compose_materializes_persists_and_delivers_once() -> None:
    participant_count = 2
    callers_ready = Barrier(participant_count)
    persistence_entered = Event()
    release_persistence = Event()
    owner, materialization_owner, receipt_owner = _composition(
        _accepted_result(),
        _committed_result,
        persistence_entered=persistence_entered,
        release_persistence=release_persistence,
    )

    def compose_after_barrier() -> CompositionDelivery:
        callers_ready.wait(timeout=WAIT_SECONDS)
        return owner.compose()

    with ThreadPoolExecutor(max_workers=participant_count) as executor:
        futures = [
            executor.submit(compose_after_barrier)
            for _ in range(participant_count)
        ]
        try:
            assert persistence_entered.wait(WAIT_SECONDS)
        finally:
            release_persistence.set()
        deliveries = [
            future.result(timeout=WAIT_SECONDS) for future in futures
        ]

    assert deliveries[1] is deliveries[0]
    assert materialization_owner.calls == 1
    assert len(materialization_owner.deliveries) == 1
    assert len(receipt_owner.calls) == 1
    assert len(receipt_owner.results) == 1


def test_already_present_is_carried_unchanged_without_second_attempt() -> None:
    owner, materialization_owner, receipt_owner = _composition(
        _accepted_result(),
        _already_present_result,
    )

    first = owner.compose()
    second = owner.compose()

    assert second is first
    assert first.persistence_result is receipt_owner.results[0]
    assert first.persistence_result.statement_result is not None
    assert first.persistence_result.statement_result.status is (
        DecisionReceiptInsertStatus.ALREADY_PRESENT
    )
    assert materialization_owner.calls == 1
    assert len(receipt_owner.calls) == 1


def test_compound_delivery_rejects_incoherent_stage_combinations() -> None:
    failed_owner = _CountingMaterializationOwner(_invalid_accepted_result())
    failed_delivery = failed_owner.materialize()
    successful_delivery = _CountingMaterializationOwner(
        _accepted_result()
    ).materialize()
    receipt = successful_delivery.receipt
    assert receipt is not None
    persistence_result = _committed_result(receipt)

    with pytest.raises(
        ValueError,
        match="failed materialization cannot carry persistence_result",
    ):
        CompositionDelivery(
            business_result=failed_delivery.business_result,
            materialization_delivery=failed_delivery,
            persistence_reached=False,
            persistence_result=persistence_result,
        )

    with pytest.raises(
        ValueError,
        match="materialized delivery must reach receipt persistence",
    ):
        CompositionDelivery(
            business_result=successful_delivery.business_result,
            materialization_delivery=successful_delivery,
            persistence_reached=False,
            persistence_result=None,
        )


def test_compound_delivery_is_frozen_and_has_only_separate_evidence_fields(
) -> None:
    owner, _materialization_owner, _receipt_owner = _composition(
        _accepted_result(),
        _committed_result,
    )
    delivery = owner.compose()

    assert [item.name for item in fields(delivery)] == [
        "business_result",
        "materialization_delivery",
        "persistence_reached",
        "persistence_result",
    ]
    with pytest.raises(FrozenInstanceError):
        delivery.persistence_result = None  # type: ignore[misc]


def test_owner_has_no_production_stage4c_or_stage4e_dependency() -> None:
    owner, _materialization_owner, _receipt_owner = _composition(
        _accepted_result(),
        _committed_result,
    )

    delivery = owner.compose()

    assert delivery.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert list(signature(CompositionOwner).parameters) == [
        "materialization_owner",
        "receipt_transaction_owner",
    ]
    assert list(signature(CompositionOwner.compose).parameters) == ["self"]
    for forbidden_name in (
        "PostgresWriteSideInvocationOwner",
        "PostgresTransactionalWriteSide",
        "RuntimeDecision",
        "ReinvocationAuthorization",
        "SemanticOutcome",
        "Stage4C",
        "Stage4E",
    ):
        assert forbidden_name not in composition.__dict__
