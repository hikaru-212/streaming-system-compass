from decimal import Decimal
from uuid import UUID

import pytest

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.compass.runtime.write_side_outcome_mapping import (
    map_postgres_write_side_result_to_semantic_outcome,
    map_write_side_admission_status_to_semantic_outcome,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
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
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000301")


def make_order_event(
    *,
    event_id: str = "event-001",
    request_id: str = "request-001",
    order_id: str = "order-001",
    sequence: int = 1,
    event_type: EventType = EventType.CREATED,
    amount: Decimal = Decimal("100.00"),
    occurred_at_ms: int = 1,
    prev_event_id: str | None = None,
    prev_version: int = 0,
    prev_status: OrderStatus = OrderStatus.INIT,
) -> OrderEvent:
    return OrderEvent(
        event_id=event_id,
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=event_type,
        amount=amount,
        occurred_at_ms=occurred_at_ms,
        proof=Proof(
            prev_event_id=prev_event_id,
            prev_version=prev_version,
            prev_status=prev_status,
        ),
    )


def make_request_signature(
    *,
    request_id: str = "request-001",
    command_type: CommandType = CommandType.CREATE,
    order_id: str = "order-001",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=command_type,
        order_id=order_id,
        amount=amount,
    )


def make_idempotency_decision(
    *,
    verdict: IdempotencyVerdict = IdempotencyVerdict.MISS,
    reason: str = "No prior request with this request_id",
    record: IdempotencyRecord | None = None,
) -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=verdict,
        reason=reason,
        record=record,
    )


def make_idempotency_record(
    *,
    signature: RequestSignature | None = None,
    accepted_event: OrderEvent | None = None,
) -> IdempotencyRecord:
    return IdempotencyRecord(
        signature=signature or make_request_signature(),
        accepted_event=accepted_event or make_order_event(),
    )


def make_validation_decision(
    *,
    action: EnforcementAction = EnforcementAction.BLOCK,
    verdict: ValidationVerdict = ValidationVerdict.FAILED,
    reason: str = (
        "Predecessor mismatch: prev_event_id does not match "
        "actual previous event"
    ),
    candidate_event_id: str = "candidate-event-001",
) -> ValidationDecision:
    return ValidationDecision(
        action=action,
        validation_result=ValidationResult(
            verdict=verdict,
            reason=reason,
            candidate_event_id=candidate_event_id,
            validator_name="FullProofValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={"order_id": "order-001"},
        ),
    )


def test_write_side_admission_status_maps_with_layer_1_boundary() -> None:
    outcome = map_write_side_admission_status_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        technical_status="COMPASS_VALIDATION_BLOCKED",
        reason="Candidate event was blocked by Compass Layer 1 validation.",
        context={"order_id": "order-001"},
        evidence={"source": "unit-test"},
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.BLOCK_REQUIRED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
    )
    assert outcome.context == {"order_id": "order-001"}
    assert outcome.evidence == {
        "source": "unit-test",
        "technical_status": "COMPASS_VALIDATION_BLOCKED",
    }


def test_write_side_admission_status_rejects_contradictory_technical_status_evidence() -> None:
    with pytest.raises(
        ValueError,
        match="evidence technical_status must match mapped technical_status",
    ):
        map_write_side_admission_status_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            technical_status="COMPASS_VALIDATION_BLOCKED",
            reason="Candidate event was blocked by Compass Layer 1 validation.",
            evidence={"technical_status": "WRITE_SIDE_ACCEPTED"},
        )


def test_postgres_write_side_accepted_maps_to_semantically_valid() -> None:
    accepted_event = make_order_event()

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id="order-001",
        ),
        validation_decision=make_validation_decision(
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
            reason="Event passed full proof transition validation",
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Event admitted by PostgreSQL optimistic admission gate",
            candidate_event_id=accepted_event.event_id,
            accepted_event_id=accepted_event.event_id,
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.VALID
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.severity == SemanticSeverity.INFO
    assert outcome.risk_level == SemanticRiskLevel.LOW
    assert outcome.reason == (
        "Write-side candidate event was admitted into accepted history."
    )
    assert outcome.context["write_side_outcome"] == "ACCEPTED"
    assert outcome.context["order_id"] == "order-001"
    assert outcome.context["request_id"] == "request-001"
    assert outcome.context["accepted_event_id"] == "event-001"
    assert outcome.evidence["technical_status"] == "WRITE_SIDE_ACCEPTED"
    assert outcome.evidence["result_type"] == "PostgresWriteSideResult"
    assert outcome.evidence["accepted_event_present"] is True
    assert outcome.evidence["idempotency_verdict"] == "miss"
    assert outcome.evidence["validation_action"] == "allow"
    assert outcome.evidence["validation_verdict"] == "passed"
    assert outcome.evidence["append_admission_verdict"] == "ADMITTED"


def test_postgres_write_side_replay_maps_to_idempotent_replay_allowed() -> None:
    previously_accepted_event = make_order_event()
    record = make_idempotency_record(
        accepted_event=previously_accepted_event,
    )

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.REPLAY,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(
            verdict=IdempotencyVerdict.REPLAY,
            reason="Semantically identical retry detected",
            record=record,
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.RETRY_CLASSIFIED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED
    )
    assert outcome.reason == "Semantically identical retry detected"
    assert outcome.context["write_side_outcome"] == "REPLAY"
    assert outcome.context["order_id"] == "order-001"
    assert outcome.context["request_id"] == "request-001"
    assert outcome.context["accepted_event_id"] == "event-001"
    assert outcome.evidence["technical_status"] == "IDEMPOTENT_REPLAY"
    assert outcome.evidence["accepted_event_present"] is False
    assert outcome.evidence["idempotency_verdict"] == "replay"


def test_postgres_write_side_conflict_maps_to_semantic_conflict_detected() -> None:
    previously_accepted_event = make_order_event()
    record = make_idempotency_record(
        accepted_event=previously_accepted_event,
    )

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=record,
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.BLOCK_REQUIRED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
    )
    assert outcome.reason == "Same request_id reused with different payload"
    assert outcome.context["write_side_outcome"] == "CONFLICT"
    assert outcome.context["request_id"] == "request-001"

    # The accepted_event_id comes from the prior idempotency record, not from
    # the current rejected candidate.
    assert outcome.context["accepted_event_id"] == "event-001"

    assert outcome.evidence["technical_status"] == "IDEMPOTENCY_CONFLICT"
    assert outcome.evidence["accepted_event_present"] is False
    assert outcome.evidence["idempotency_verdict"] == "conflict"


def test_postgres_write_side_validation_blocked_maps_to_compass_validation_blocked() -> None:
    validation_decision = make_validation_decision()

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id="order-001",
        ),
        validation_decision=validation_decision,
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.BLOCK_REQUIRED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
    )
    assert outcome.reason == (
        "Predecessor mismatch: prev_event_id does not match "
        "actual previous event"
    )
    assert outcome.context["write_side_outcome"] == "VALIDATION_BLOCKED"
    assert outcome.context["candidate_event_id"] == "candidate-event-001"
    assert outcome.evidence["technical_status"] == "COMPASS_VALIDATION_BLOCKED"
    assert outcome.evidence["validation_decision_present"] is True
    assert outcome.evidence["validation_action"] == "block"
    assert outcome.evidence["validation_verdict"] == "failed"
    assert outcome.evidence["validator_name"] == "FullProofValidator"


def test_postgres_write_side_stream_lock_timeout_maps_to_concurrency_uncertain() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason="Stream lock was not available.",
            order_id="order-001",
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    assert outcome.semantic_code == SemanticOutcomeCode.CONCURRENCY_UNCERTAIN
    assert outcome.reason == "Stream lock was not available."
    assert outcome.context["write_side_outcome"] == "ADMISSION_REJECTED"
    assert outcome.context["order_id"] == "order-001"
    assert outcome.evidence["technical_status"] == "LOCK_TIMEOUT"
    assert outcome.evidence["stream_admission_verdict"] == "LOCK_TIMEOUT"
    assert outcome.evidence["append_admission_result_present"] is False


def test_postgres_write_side_append_stale_write_maps_to_concurrent_state_staleness() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id="order-001",
        ),
        validation_decision=make_validation_decision(
            action=EnforcementAction.ALLOW,
            verdict=ValidationVerdict.PASSED,
            reason="Event passed full proof transition validation",
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="Stale write rejected by PostgreSQL optimistic admission gate",
            candidate_event_id="candidate-event-001",
            accepted_event_id=None,
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    assert outcome.semantic_code == SemanticOutcomeCode.CONCURRENCY_UNCERTAIN
    assert outcome.reason == (
        "Stale write rejected by PostgreSQL optimistic admission gate"
    )
    assert outcome.context["candidate_event_id"] == "candidate-event-001"
    assert (
        outcome.evidence["technical_status"]
        == "CONCURRENT_STATE_STALENESS"
    )
    assert outcome.evidence["append_admission_verdict"] == "STALE_WRITE"


def test_postgres_write_side_append_lock_timeout_maps_to_concurrency_uncertain() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Stream admitted.",
            order_id="order-001",
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason="Lock was not available during append.",
            candidate_event_id="candidate-event-001",
            accepted_event_id=None,
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    assert outcome.semantic_code == SemanticOutcomeCode.CONCURRENCY_UNCERTAIN
    assert outcome.evidence["technical_status"] == "LOCK_TIMEOUT"
    assert outcome.evidence["append_admission_verdict"] == "LOCK_TIMEOUT"


def test_postgres_write_side_infrastructure_error_maps_to_operator_review() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
            reason="PostgreSQL pessimistic admission gate requires transaction scope.",
            order_id="order-001",
        ),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_1_WRITE_SIDE
    assert outcome.category == SemanticOutcomeCategory.ESCALATION_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reason == (
        "PostgreSQL pessimistic admission gate requires transaction scope."
    )
    assert (
        outcome.evidence["technical_status"]
        == "WRITE_SIDE_INFRASTRUCTURE_ERROR"
    )
    assert outcome.evidence["stream_admission_verdict"] == "INFRASTRUCTURE_ERROR"


def test_postgres_write_side_mapping_preserves_caller_context_and_evidence() -> None:
    accepted_event = make_order_event()

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
        context={"actor_role": "compass_app_writer"},
        evidence={"adapter": "write-side"},
    )

    assert outcome.context["write_side_outcome"] == "ACCEPTED"
    assert outcome.context["actor_role"] == "compass_app_writer"
    assert outcome.evidence["result_type"] == "PostgresWriteSideResult"
    assert outcome.evidence["adapter"] == "write-side"
    assert outcome.evidence["technical_status"] == "WRITE_SIDE_ACCEPTED"


def test_postgres_write_side_mapping_allows_matching_context_identity() -> None:
    accepted_event = make_order_event(order_id="order-001")

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
        context={"order_id": "order-001"},
    )

    assert outcome.context["order_id"] == "order-001"


def test_postgres_write_side_mapping_rejects_conflicting_context_identity() -> None:
    accepted_event = make_order_event(order_id="order-001")

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
    )

    with pytest.raises(
        ValueError,
        match="context order_id must not contradict mapped write-side context",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
            context={"order_id": "evil-order"},
        )


def test_postgres_write_side_mapping_rejects_contradictory_order_id_lineage() -> None:
    accepted_event = make_order_event(order_id="order-001")
    record = make_idempotency_record(
        signature=make_request_signature(order_id="evil-order"),
        accepted_event=accepted_event,
    )

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=record,
        ),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason="Stream lock was not available.",
            order_id="order-001",
        ),
    )

    with pytest.raises(
        ValueError,
        match="Contradictory order_id evidence detected in write-side result",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_postgres_write_side_mapping_rejects_contradictory_request_id_lineage() -> None:
    accepted_event = make_order_event(request_id="request-001")
    record = make_idempotency_record(
        signature=make_request_signature(request_id="evil-request"),
        accepted_event=accepted_event,
    )

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=record,
        ),
    )

    with pytest.raises(
        ValueError,
        match="Contradictory request_id evidence detected in write-side result",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
        

def test_postgres_write_side_mapping_rejects_contradictory_technical_status_evidence() -> None:
    accepted_event = make_order_event()

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
    )

    with pytest.raises(
        ValueError,
        match="evidence technical_status must match mapped technical_status",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
            evidence={"technical_status": "IDEMPOTENCY_CONFLICT"},
        )


def test_postgres_write_side_mapping_rejects_rejected_admission_result_with_accepted_event_id() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Stream admitted.",
            order_id="order-001",
        ),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="Stale write rejected by PostgreSQL optimistic admission gate",
            candidate_event_id="candidate-event-001",
            accepted_event_id="candidate-event-001",
        ),
    )

    with pytest.raises(
        ValueError,
        match="rejected append-time admission result must not carry accepted_event_id",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
        

def test_postgres_write_side_mapping_does_not_add_decision_strategy_or_retry_fields() -> None:
    accepted_event = make_order_event()

    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=accepted_event,
        idempotency_decision=make_idempotency_decision(),
    )

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert not hasattr(outcome, "runtime_action")
    assert not hasattr(outcome, "decision")
    assert not hasattr(outcome, "strategy")
    assert not hasattr(outcome, "retry_allowed")
    assert not hasattr(outcome, "recovery_action")


def test_postgres_write_side_mapping_rejects_inconsistent_accepted_result_shape() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
    )

    with pytest.raises(
        ValueError,
        match="ACCEPTED write-side result requires accepted_event",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_postgres_write_side_mapping_rejects_validation_blocked_without_validation_decision() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
    )

    with pytest.raises(
        ValueError,
        match="VALIDATION_BLOCKED write-side result requires validation_decision",
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_postgres_write_side_mapping_rejects_admission_rejected_without_admission_evidence() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "ADMISSION_REJECTED write-side result requires "
            "stream_admission_result or admission_result"
        ),
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_postgres_write_side_mapping_rejects_admission_rejected_with_admitted_append_result() -> None:
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency_decision(),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Event admitted.",
            candidate_event_id="candidate-event-001",
            accepted_event_id=None,
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "ADMISSION_REJECTED result cannot use admitted "
            "append-time admission result"
        ),
    ):
        map_postgres_write_side_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )