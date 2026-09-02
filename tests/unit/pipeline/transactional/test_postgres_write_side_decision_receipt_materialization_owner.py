from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from decimal import Decimal
from threading import Barrier
from typing import cast
from uuid import UUID

import pytest

from src.compass.runtime.decision_receipt import EventAdmissionDisposition
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_materialization_owner as owner_module,
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
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000901")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000902")

FailureCategory = (
    owner_module.PostgresWriteSideDecisionReceiptMaterializationFailureCategory
)
Owner = owner_module.PostgresWriteSideDecisionReceiptMaterializationOwner
Status = owner_module.PostgresWriteSideDecisionReceiptMaterializationStatus


class _CountingIdentityFactory:
    """Return one deterministic UUID while exposing bounded call evidence."""

    def __init__(self, identity: UUID) -> None:
        self.identity = identity
        self.calls = 0

    def __call__(self) -> UUID:
        self.calls += 1
        return self.identity


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="materialization-owner test miss",
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
            reason="materialization-owner test validation",
            candidate_event_id=candidate_event_id,
            validator_name="MaterializationOwnerTestValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        ),
    )


def _accepted_result() -> PostgresWriteSideResult:
    event = OrderAggregate("materialization-owner-order").create(
        "materialization-owner-request",
        Decimal("100.00"),
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="materialization-owner test stream admitted",
            order_id=event.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=event.event_id,
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="materialization-owner test append admitted",
            candidate_event_id=event.event_id,
            accepted_event_id=event.event_id,
        ),
    )


def _validation_blocked_result() -> PostgresWriteSideResult:
    candidate = OrderAggregate("materialization-owner-blocked-order").create(
        "materialization-owner-blocked-request",
        Decimal("100.00"),
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="materialization-owner test stream admitted",
            order_id=candidate.order_id,
        ),
        validation_decision=_validation_decision(
            candidate_event_id=candidate.event_id,
            action=EnforcementAction.BLOCK,
            verdict=ValidationVerdict.FAILED,
        ),
    )


def _owner(
    completed_result: PostgresWriteSideResult,
    *,
    receipt_id_factory: _CountingIdentityFactory | None = None,
    outcome_id_factory: _CountingIdentityFactory | None = None,
) -> Owner:
    return Owner(
        completed_result=completed_result,
        receipt_id_factory=(
            receipt_id_factory
            if receipt_id_factory is not None
            else _CountingIdentityFactory(RECEIPT_ID)
        ),
        outcome_id_factory=(
            outcome_id_factory
            if outcome_id_factory is not None
            else _CountingIdentityFactory(OUTCOME_ID)
        ),
    )


def test_accepted_result_materializes_with_exact_business_result_and_local_ids(
) -> None:
    result = _accepted_result()
    owner = _owner(result)

    delivery = owner.materialize()

    assert delivery.business_result is result
    assert delivery.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert delivery.status is Status.MATERIALIZED
    assert delivery.receipt is not None
    assert delivery.receipt.receipt_id == RECEIPT_ID
    assert delivery.receipt.outcome_id == OUTCOME_ID
    assert delivery.failure_category is None


def test_validation_blocked_result_materializes_without_becoming_accepted(
) -> None:
    result = _validation_blocked_result()
    owner = _owner(result)

    delivery = owner.materialize()

    assert delivery.business_result is result
    assert delivery.business_result.outcome is (
        PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )
    assert delivery.business_result.accepted_event is None
    assert delivery.status is Status.MATERIALIZED
    assert delivery.receipt is not None
    assert delivery.receipt.correlation.accepted_event_id is None
    assert delivery.receipt.admission_evidence is not None
    assert delivery.receipt.admission_evidence.disposition is (
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED
    )


def test_materialize_twice_allocates_maps_and_delivers_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _accepted_result()
    receipt_ids = _CountingIdentityFactory(RECEIPT_ID)
    outcome_ids = _CountingIdentityFactory(OUTCOME_ID)
    mapper_calls: list[tuple[UUID, UUID, PostgresWriteSideResult]] = []
    authoritative_mapper = (
        owner_module.map_postgres_write_side_result_to_decision_receipt
    )

    def observed_mapper(
        *,
        receipt_id: UUID,
        outcome_id: UUID,
        result: PostgresWriteSideResult,
    ):
        mapper_calls.append((receipt_id, outcome_id, result))
        return authoritative_mapper(
            receipt_id=receipt_id,
            outcome_id=outcome_id,
            result=result,
        )

    monkeypatch.setattr(
        owner_module,
        "map_postgres_write_side_result_to_decision_receipt",
        observed_mapper,
    )
    owner = _owner(
        result,
        receipt_id_factory=receipt_ids,
        outcome_id_factory=outcome_ids,
    )

    first = owner.materialize()
    second = owner.materialize()

    assert second is first
    assert first.receipt is second.receipt
    assert receipt_ids.calls == 1
    assert outcome_ids.calls == 1
    assert mapper_calls == [(RECEIPT_ID, OUTCOME_ID, result)]


def test_concurrent_materialize_allocates_maps_and_delivers_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _accepted_result()
    receipt_ids = _CountingIdentityFactory(RECEIPT_ID)
    outcome_ids = _CountingIdentityFactory(OUTCOME_ID)
    mapper_calls: list[tuple[UUID, UUID, PostgresWriteSideResult]] = []
    authoritative_mapper = (
        owner_module.map_postgres_write_side_result_to_decision_receipt
    )
    participant_count = 2
    wait_seconds = 5.0
    barrier = Barrier(participant_count)

    def observed_mapper(
        *,
        receipt_id: UUID,
        outcome_id: UUID,
        result: PostgresWriteSideResult,
    ):
        mapper_calls.append((receipt_id, outcome_id, result))
        return authoritative_mapper(
            receipt_id=receipt_id,
            outcome_id=outcome_id,
            result=result,
        )

    monkeypatch.setattr(
        owner_module,
        "map_postgres_write_side_result_to_decision_receipt",
        observed_mapper,
    )
    owner = _owner(
        result,
        receipt_id_factory=receipt_ids,
        outcome_id_factory=outcome_ids,
    )

    def materialize_after_barrier():
        barrier.wait(timeout=wait_seconds)
        return owner.materialize()

    with ThreadPoolExecutor(max_workers=participant_count) as executor:
        futures = [
            executor.submit(materialize_after_barrier)
            for _ in range(participant_count)
        ]
        deliveries = [
            future.result(timeout=wait_seconds) for future in futures
        ]

    assert deliveries[1] is deliveries[0]
    assert deliveries[0].receipt is not None
    assert deliveries[1].receipt is deliveries[0].receipt
    assert receipt_ids.calls == 1
    assert outcome_ids.calls == 1
    assert mapper_calls == [(RECEIPT_ID, OUTCOME_ID, result)]


@pytest.mark.parametrize(
    ("invalid_result", "expected_failure"),
    [
        (
            PostgresWriteSideResult(
                outcome=cast(PostgresWriteSideOutcome, "ACCEPTED"),
                accepted_event=None,
                idempotency_decision=_miss(),
            ),
            FailureCategory.TYPE_ERROR,
        ),
        (
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ACCEPTED,
                accepted_event=None,
                idempotency_decision=_miss(),
            ),
            FailureCategory.VALUE_ERROR,
        ),
    ],
    ids=("mapper-type-error", "mapper-value-error"),
)
def test_recognized_mapping_failure_is_bounded_and_cached(
    monkeypatch: pytest.MonkeyPatch,
    invalid_result: PostgresWriteSideResult,
    expected_failure: FailureCategory,
) -> None:
    receipt_ids = _CountingIdentityFactory(RECEIPT_ID)
    outcome_ids = _CountingIdentityFactory(OUTCOME_ID)
    mapper_calls = 0
    authoritative_mapper = (
        owner_module.map_postgres_write_side_result_to_decision_receipt
    )

    def observed_mapper(
        *,
        receipt_id: UUID,
        outcome_id: UUID,
        result: PostgresWriteSideResult,
    ):
        nonlocal mapper_calls
        mapper_calls += 1
        return authoritative_mapper(
            receipt_id=receipt_id,
            outcome_id=outcome_id,
            result=result,
        )

    monkeypatch.setattr(
        owner_module,
        "map_postgres_write_side_result_to_decision_receipt",
        observed_mapper,
    )
    owner = _owner(
        invalid_result,
        receipt_id_factory=receipt_ids,
        outcome_id_factory=outcome_ids,
    )

    first = owner.materialize()
    second = owner.materialize()

    assert second is first
    assert first.business_result is invalid_result
    assert first.status is Status.MATERIALIZATION_FAILED
    assert first.receipt is None
    assert first.failure_category is expected_failure
    assert receipt_ids.calls == 1
    assert outcome_ids.calls == 1
    assert mapper_calls == 1


def test_unexpected_mapper_exception_propagates_without_becoming_failure_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _accepted_result()
    sentinel = RuntimeError("test-owned unexpected mapper failure")

    def raise_unexpected(**_kwargs: object):
        raise sentinel

    monkeypatch.setattr(
        owner_module,
        "map_postgres_write_side_result_to_decision_receipt",
        raise_unexpected,
    )
    owner = _owner(result)

    with pytest.raises(RuntimeError) as raised:
        owner.materialize()

    assert raised.value is sentinel


def test_delivery_is_frozen() -> None:
    delivery = _owner(_accepted_result()).materialize()

    with pytest.raises(FrozenInstanceError):
        delivery.receipt = None  # type: ignore[misc]


def test_owner_has_no_stage4c_stage4e_or_persistence_dependency() -> None:
    result = _accepted_result()
    owner = _owner(result)

    delivery = owner.materialize()

    assert delivery.business_result is result
    assert delivery.receipt is not None
    assert delivery.receipt.outcome_id == OUTCOME_ID
    assert "PostgresWriteSideInvocationOwner" not in owner_module.__dict__
    assert "RuntimeDecision" not in owner_module.__dict__
    assert "ReinvocationAuthorization" not in owner_module.__dict__
    assert "PostgresDecisionReceiptTransactionOwner" not in owner_module.__dict__
