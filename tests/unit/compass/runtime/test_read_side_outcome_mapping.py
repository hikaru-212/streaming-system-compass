from decimal import Decimal
from uuid import UUID
from uuid import uuid4

import pytest

from src.compass.runtime.read_side_outcome_mapping import (
    map_projection_snapshot_assisted_resolution_result_to_semantic_outcome,
    map_projection_snapshot_replay_validation_result_to_semantic_outcome,
    map_replay_validation_result_to_semantic_outcome,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.replay_validator import (
    ReplayValidationResult,
    ReplayValidationStatus,
)

OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000201")


def make_order_state(
    *,
    order_id: str = "order-001",
    status: OrderStatus = OrderStatus.CREATED,
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    version: int = 1,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        version=version,
    )


def test_replay_validation_match_maps_to_semantically_valid() -> None:
    state = make_order_state()
    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.MATCH,
        expected_state=state,
        persisted_state=state,
        reason="Persisted projection state matches replay-derived state",
    )

    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.VALID
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.severity == SemanticSeverity.INFO
    assert outcome.risk_level == SemanticRiskLevel.LOW
    assert outcome.reversibility == SemanticReversibility.REVERSIBLE
    assert outcome.context["order_id"] == "order-001"
    assert outcome.evidence["technical_status"] == "MATCH"
    assert outcome.evidence["result_type"] == "ReplayValidationResult"
    assert outcome.evidence["expected_state_present"] is True
    assert outcome.evidence["persisted_state_present"] is True


def test_replay_validation_missing_projection_maps_to_rebuild_required() -> None:
    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.MISSING_PROJECTION,
        expected_state=make_order_state(),
        persisted_state=None,
        reason="Accepted history exists but projection state is missing",
    )

    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.REBUILD_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.REQUIRES_REBUILD
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE
    assert outcome.evidence["technical_status"] == "MISSING_PROJECTION"
    assert outcome.evidence["expected_state_present"] is True
    assert outcome.evidence["persisted_state_present"] is False


def test_replay_validation_drift_maps_to_drift_detected() -> None:
    expected_state = make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    persisted_state = make_order_state()

    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.DRIFT,
        expected_state=expected_state,
        persisted_state=persisted_state,
        reason="Persisted projection state differs from replay-derived state",
    )

    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.DRIFT
    assert outcome.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.evidence["technical_status"] == "DRIFT"


def test_replay_validation_no_accepted_history_for_order_maps_to_runtime_unresolved() -> None:
    # DurableReplayValidator is scoped by order_id.
    # The current production enum is named NO_ACCEPTED_HISTORY, but in this
    # validator contract it means "no accepted history exists for this order",
    # not necessarily that the global accepted-history log is empty.
    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
        expected_state=None,
        persisted_state=None,
        reason="No accepted history exists for order",
    )

    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.UNRESOLVED
    assert outcome.semantic_code == SemanticOutcomeCode.RUNTIME_UNRESOLVED
    assert outcome.risk_level == SemanticRiskLevel.UNKNOWN
    assert outcome.evidence["technical_status"] == "NO_ACCEPTED_HISTORY"
    assert outcome.evidence["expected_state_present"] is False
    assert outcome.evidence["persisted_state_present"] is False


def test_snapshot_replay_match_maps_to_semantically_valid_snapshot_trust() -> None:
    snapshot_id = uuid4()
    state = make_order_state()

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MATCH,
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=state,
        authority_state=state,
        reason="Snapshot-assisted replay matches accepted-history replay.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.VALID
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.context["order_id"] == "order-001"
    assert outcome.context["snapshot_id"] == snapshot_id
    assert outcome.context["source_global_position"] == 10
    assert outcome.evidence["technical_status"] == "MATCH"
    assert (
        outcome.evidence["result_type"]
        == "ProjectionSnapshotReplayValidationResult"
    )
    assert outcome.evidence["snapshot_assisted_state_present"] is True
    assert outcome.evidence["authority_state_present"] is True


def test_snapshot_replay_missing_snapshot_maps_to_fast_path_unavailable() -> None:
    # ProjectionSnapshotReplayValidator performs full authority replay before
    # checking the snapshot-assisted path. Therefore, missing snapshot means the
    # snapshot-assisted state is unavailable, not that authority state is absent.
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
        order_id="order-001",
        snapshot_id=None,
        source_global_position=None,
        snapshot_assisted_state=None,
        authority_state=make_order_state(),
        reason=(
            "No projection snapshot exists for order; "
            "authority state was reconstructed from accepted history."
        ),
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.FALLBACK_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.FAST_PATH_UNAVAILABLE
    assert outcome.evidence["technical_status"] == "MISSING_SNAPSHOT"
    assert outcome.evidence["snapshot_assisted_state_present"] is False
    assert outcome.evidence["authority_state_present"] is True


def test_snapshot_replay_invalid_boundary_maps_to_derived_state_untrusted() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .INVALID_SNAPSHOT_BOUNDARY
        ),
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=None,
        authority_state=make_order_state(),
        reason="Snapshot source boundary is invalid.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNTRUSTED
    assert outcome.semantic_code == SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE
    assert outcome.evidence["snapshot_assisted_state_present"] is False
    assert outcome.evidence["authority_state_present"] is True


def test_snapshot_replay_tail_source_contract_violation_maps_to_unresolved() -> None:
    snapshot_id = uuid4()

    snapshot_boundary_state = make_order_state(
        status=OrderStatus.CREATED,
        paid_amount=Decimal("0.00"),
        version=1,
    )
    authority_state = make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )

    # ProjectionSnapshotReplayValidator is the full replay validator:
    # - authority_state can exist because accepted history is replayed through
    #   the authority path.
    # - snapshot_assisted_state can exist because the snapshot was loaded and
    #   hydrated successfully.
    #
    # In this case, snapshot_assisted_state represents the snapshot boundary
    # state before tail replay could complete.
    #
    # The tail source contract violation means the validator could not safely
    # load or advance through the tail events required to move the snapshot
    # boundary state toward the authority state.
    #
    # Therefore, even though snapshot_assisted_state differs from authority_state,
    # this is not drift evidence. It is runtime unresolved evidence because the
    # snapshot-assisted path did not complete.
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=snapshot_boundary_state,
        authority_state=authority_state,
        reason="Tail event source returned non-advancing global_position.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNRESOLVED
    assert outcome.semantic_code == SemanticOutcomeCode.RUNTIME_UNRESOLVED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert (
        outcome.evidence["technical_status"]
        == "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    )
    assert outcome.evidence["snapshot_assisted_state_present"] is True
    assert outcome.evidence["authority_state_present"] is True
    assert outcome.semantic_code != SemanticOutcomeCode.DRIFT_DETECTED


def test_snapshot_replay_drift_maps_to_snapshot_assisted_drift_detected() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT,
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=make_order_state(),
        authority_state=make_order_state(
            status=OrderStatus.PAID,
            paid_amount=Decimal("100.00"),
            version=2,
        ),
        reason="Snapshot-assisted replay differs from accepted-history replay.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.DRIFT
    assert outcome.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert (
        outcome.evidence["technical_status"]
        == "SNAPSHOT_ASSISTED_DRIFT"
    )
    assert outcome.evidence["snapshot_assisted_state_present"] is True
    assert outcome.evidence["authority_state_present"] is True


def test_snapshot_replay_no_accepted_history_for_order_maps_to_unresolved() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .NO_ACCEPTED_HISTORY_FOR_ORDER
        ),
        order_id="order-001",
        snapshot_id=None,
        source_global_position=None,
        snapshot_assisted_state=None,
        authority_state=None,
        reason="No accepted history exists for order.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNRESOLVED
    assert outcome.semantic_code == SemanticOutcomeCode.RUNTIME_UNRESOLVED
    assert (
        outcome.evidence["technical_status"]
        == "NO_ACCEPTED_HISTORY_FOR_ORDER"
    )
    assert outcome.evidence["snapshot_assisted_state_present"] is False
    assert outcome.evidence["authority_state_present"] is False


def test_snapshot_assisted_resolution_success_maps_to_semantically_valid() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .RESOLVED_FROM_SNAPSHOT
        ),
        resolved_state=make_order_state(),
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Projection state resolved from snapshot and tail replay.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.VALID
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.context["snapshot_id"] == snapshot_id
    assert outcome.evidence["technical_status"] == "RESOLVED_FROM_SNAPSHOT"
    assert (
        outcome.evidence["result_type"]
        == "ProjectionSnapshotAssistedResolutionResult"
    )
    assert outcome.evidence["resolved_state_present"] is True


def test_snapshot_assisted_resolution_missing_snapshot_maps_to_fast_path_unavailable() -> None:
    requested_snapshot_id = uuid4()

    # The resolver does not perform authority replay.
    #
    # The production resolver parameter is named trusted_snapshot_id. In this
    # branch, result.snapshot_id records the requested id that failed to load
    # from the snapshot store. It is not a loaded snapshot artifact id.
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        resolved_state=None,
        snapshot_id=requested_snapshot_id,
        source_global_position=None,
        reason="Projection snapshot was not found.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.FALLBACK_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.FAST_PATH_UNAVAILABLE
    assert outcome.context["snapshot_id"] == requested_snapshot_id
    assert outcome.evidence["technical_status"] == "MISSING_SNAPSHOT"
    assert outcome.evidence["resolved_state_present"] is False


def test_snapshot_assisted_resolution_invalid_precondition_maps_to_untrusted() -> None:
    # The resolver requires an explicit snapshot id. Without one, it must not
    # select a snapshot by itself, because snapshot selection belongs outside this
    # resolver.
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_PRECONDITION
        ),
        resolved_state=None,
        snapshot_id=None,
        source_global_position=None,
        reason="trusted_snapshot_id is required.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNTRUSTED
    assert outcome.semantic_code == SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED
    assert (
        outcome.evidence["technical_status"]
        == "INVALID_SNAPSHOT_PRECONDITION"
    )


def test_snapshot_assisted_resolution_invalid_compatibility_maps_to_untrusted() -> None:
    snapshot_id = uuid4()

    # A snapshot artifact exists, but it cannot be consumed by this resolver
    # because its boundary, version, or state contract is incompatible.
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_COMPATIBILITY
        ),
        resolved_state=None,
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Snapshot is incompatible with current resolver.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNTRUSTED
    assert outcome.semantic_code == SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED
    assert (
        outcome.evidence["technical_status"]
        == "INVALID_SNAPSHOT_COMPATIBILITY"
    )


def test_snapshot_assisted_resolution_tail_source_contract_violation_maps_to_unresolved() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        resolved_state=None,
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Tail event source returned non-advancing global_position.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNRESOLVED
    assert outcome.semantic_code == SemanticOutcomeCode.RUNTIME_UNRESOLVED
    assert (
        outcome.evidence["technical_status"]
        == "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    )
    assert outcome.evidence["resolved_state_present"] is False


def test_snapshot_assisted_resolution_tail_replay_failed_maps_to_fast_path_unavailable() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
        resolved_state=None,
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Snapshot-assisted tail replay failed.",
    )

    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.FALLBACK_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.FAST_PATH_UNAVAILABLE
    assert outcome.semantic_code != SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.evidence["technical_status"] == "TAIL_REPLAY_FAILED"
    assert outcome.evidence["resolved_state_present"] is False


def test_read_side_mapping_preserves_caller_context_and_evidence() -> None:
    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.MATCH,
        expected_state=make_order_state(),
        persisted_state=make_order_state(),
        reason="Persisted projection state matches replay-derived state",
    )

    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
        context={"worker_name": "projection-worker-001"},
        evidence={"validator": "DurableReplayValidator"},
    )

    assert outcome.context == {
        "order_id": "order-001",
        "worker_name": "projection-worker-001",
    }
    assert outcome.evidence == {
        "result_type": "ReplayValidationResult",
        "expected_state_present": True,
        "persisted_state_present": True,
        "validator": "DurableReplayValidator",
        "technical_status": "MATCH",
    }


def test_read_side_mapping_rejects_contradictory_technical_status_evidence() -> None:
    result = ReplayValidationResult(
        order_id="order-001",
        status=ReplayValidationStatus.MATCH,
        expected_state=make_order_state(),
        persisted_state=make_order_state(),
        reason="Persisted projection state matches replay-derived state",
    )

    with pytest.raises(
        ValueError,
        match="evidence technical_status must match mapped technical_status",
    ):
        map_replay_validation_result_to_semantic_outcome(
            outcome_id=OUTCOME_ID,
            result=result,
            evidence={"technical_status": "DRIFT"},
        )


def test_read_side_mapping_uses_fallback_reason_when_result_reason_is_blank() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MATCH,
        order_id="order-001",
        snapshot_id=uuid4(),
        source_global_position=10,
        snapshot_assisted_state=make_order_state(),
        authority_state=make_order_state(),
        reason="",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert outcome.reason == (
        "Missing explicit reason from "
        "ProjectionSnapshotReplayValidationResult."
    )


def test_read_side_mapping_does_not_add_decision_strategy_or_retry_fields() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
        order_id="order-001",
        snapshot_id=None,
        source_global_position=None,
        snapshot_assisted_state=None,
        authority_state=make_order_state(),
        reason="No projection snapshot exists for order.",
    )

    outcome = map_projection_snapshot_replay_validation_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert not hasattr(outcome, "runtime_action")
    assert not hasattr(outcome, "decision")
    assert not hasattr(outcome, "strategy")
    assert not hasattr(outcome, "retry_allowed")
    assert not hasattr(outcome, "recovery_action")