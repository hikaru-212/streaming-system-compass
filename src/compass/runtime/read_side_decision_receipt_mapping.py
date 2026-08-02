from __future__ import annotations

from uuid import UUID

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptCorrelation,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
)
from src.compass.runtime.decision_receipt_mapping import (
    map_semantic_outcome_to_decision_receipt,
)
from src.compass.runtime.read_side_outcome_mapping import (
    map_projection_snapshot_assisted_resolution_result_to_semantic_outcome,
    map_projection_snapshot_replay_validation_result_to_semantic_outcome,
    map_replay_validation_result_to_semantic_outcome,
)
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.replay_validator import (
    ReplayValidationResult,
    ReplayValidationStatus,
)

__all__ = [
    "map_projection_snapshot_assisted_resolution_result_to_decision_receipt",
    "map_projection_snapshot_replay_validation_result_to_decision_receipt",
    "map_replay_validation_result_to_decision_receipt",
]


def map_replay_validation_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ReplayValidationResult,
) -> DecisionReceipt:
    """
    Map one durable read-side replay result into a DecisionReceipt.

    ReplayValidationResult owns READ_SIDE_PATH evidence about the projection
    keyed by its observed order_id. The wrapper validates status/state
    consistency before constructing the existing Stage 4A SemanticOutcome,
    derives correlation only from the typed read-side observation, and
    reconstructs compact evidence directly from the result.

    Contradictory result shapes raise ValueError before receipt construction.
    This mapper does not copy SemanticOutcome mappings, infer event identity,
    execute rebuild, generalize flags, authorize retry, or persist the receipt.
    """

    _validate_replay_result_shape(result)
    outcome = map_replay_validation_result_to_semantic_outcome(
        outcome_id=outcome_id,
        result=result,
    )

    return map_semantic_outcome_to_decision_receipt(
        receipt_id=receipt_id,
        outcome=outcome,
        evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
        subject=_replay_subject(result),
        correlation=DecisionReceiptCorrelation(
            order_id=result.order_id,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
        ),
        flags=DecisionReceiptFlags(),
        evidence_summary={
            "technical_status": result.status.value,
            "expected_state_present": result.expected_state is not None,
            "persisted_state_present": result.persisted_state is not None,
        },
    )


def map_projection_snapshot_replay_validation_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ProjectionSnapshotReplayValidationResult,
) -> DecisionReceipt:
    """
    Map one snapshot-trust validation result into a DecisionReceipt.

    ProjectionSnapshotReplayValidationResult owns SNAPSHOT_TRUST_PATH evidence.
    Loaded snapshot identity and source_global_position are preserved only as
    SNAPSHOT_LINEAGE; an absent artifact remains a READ_SIDE_OBSERVATION. The
    subject follows the producer status without attributing a tail-source
    failure or state disagreement to an unproved snapshot root cause.

    Contiguous order-local tail validation remains producer-owned. The result
    does not expose source_event_sequence, and this mapper does not reconstruct
    or infer it from snapshot lineage.

    The wrapper rejects contradictory status, state, or lineage shapes before
    calling the Stage 4A adapter. It does not inspect SemanticOutcome mappings,
    infer accepted-history identity, derive recovery flags, authorize retry,
    serialize, or persist the receipt.
    """

    _validate_snapshot_replay_result_shape(result)
    outcome = (
        map_projection_snapshot_replay_validation_result_to_semantic_outcome(
            outcome_id=outcome_id,
            result=result,
        )
    )
    snapshot_artifact_present = result.snapshot_id is not None

    return map_semantic_outcome_to_decision_receipt(
        receipt_id=receipt_id,
        outcome=outcome,
        evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
        subject=_snapshot_replay_subject(result),
        correlation=DecisionReceiptCorrelation(
            order_id=result.order_id,
            snapshot_id=result.snapshot_id,
            source_global_position=result.source_global_position,
            identity_source=(
                DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
                if snapshot_artifact_present
                else DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION
            ),
        ),
        flags=DecisionReceiptFlags(),
        evidence_summary={
            "technical_status": result.status.value,
            "snapshot_artifact_present": snapshot_artifact_present,
            "snapshot_assisted_state_present": (
                result.snapshot_assisted_state is not None
            ),
            "authority_state_present": result.authority_state is not None,
        },
    )


def map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ProjectionSnapshotAssistedResolutionResult,
) -> DecisionReceipt:
    """
    Map one snapshot-assisted resolution result into a DecisionReceipt.

    ProjectionSnapshotAssistedResolutionResult owns SNAPSHOT_ASSISTED_PATH
    evidence. A missing snapshot carries the requested snapshot reference as a
    READ_SIDE_OBSERVATION, while compatibility and later branches carry loaded
    SNAPSHOT_LINEAGE. Runtime subjects preserve observed tail failures without
    claiming that the snapshot is their root cause.

    Contiguous order-local tail validation remains producer-owned. The result
    does not expose source_event_sequence, and this mapper does not reconstruct
    or infer it from snapshot lineage.

    Status/state/lineage contradictions raise ValueError before the existing
    Stage 4A adapter runs. This mapper does not prove accepted-history
    authority, inspect SemanticOutcome mappings, infer recovery or retry
    policy, serialize, or persist the receipt.
    """

    _validate_snapshot_assisted_result_shape(result)
    outcome = (
        map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
            outcome_id=outcome_id,
            result=result,
        )
    )
    snapshot_artifact_present = _assisted_snapshot_artifact_present(
        result.status
    )

    return map_semantic_outcome_to_decision_receipt(
        receipt_id=receipt_id,
        outcome=outcome,
        evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
        subject=_snapshot_assisted_subject(result),
        correlation=DecisionReceiptCorrelation(
            order_id=result.order_id,
            snapshot_id=result.snapshot_id,
            source_global_position=result.source_global_position,
            identity_source=(
                DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
                if snapshot_artifact_present
                else DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION
            ),
        ),
        flags=DecisionReceiptFlags(),
        evidence_summary={
            "technical_status": result.status.value,
            "snapshot_artifact_present": snapshot_artifact_present,
            "resolved_state_present": result.resolved_state is not None,
        },
    )


def _validate_replay_result_shape(result: ReplayValidationResult) -> None:
    """Reject replay status/state combinations production cannot produce."""

    _validate_order_id(result.order_id, "ReplayValidationResult")
    status = result.status

    if not isinstance(status, ReplayValidationStatus):
        raise ValueError(
            "ReplayValidationResult.status must be ReplayValidationStatus"
        )

    _validate_present_order_state(
        state=result.expected_state,
        result_order_id=result.order_id,
        result_type="ReplayValidationResult",
        field_name="expected_state",
    )
    _validate_present_order_state(
        state=result.persisted_state,
        result_order_id=result.order_id,
        result_type="ReplayValidationResult",
        field_name="persisted_state",
    )

    expected_present = result.expected_state is not None
    persisted_present = result.persisted_state is not None

    if status == ReplayValidationStatus.MATCH:
        if not expected_present or not persisted_present:
            raise ValueError(
                "ReplayValidationResult MATCH requires expected_state and "
                "persisted_state"
            )
        if result.expected_state != result.persisted_state:
            raise ValueError(
                "ReplayValidationResult MATCH requires equal states"
            )
        return

    if status == ReplayValidationStatus.MISSING_PROJECTION:
        if not expected_present:
            raise ValueError(
                "ReplayValidationResult MISSING_PROJECTION requires "
                "accepted-history replay state"
            )

        if persisted_present:
            raise ValueError(
                "ReplayValidationResult MISSING_PROJECTION requires "
                "persisted projection to be absent"
            )
        return

    if status == ReplayValidationStatus.DRIFT:
        if not expected_present or not persisted_present:
            raise ValueError(
                "ReplayValidationResult DRIFT requires expected_state and "
                "persisted_state"
            )
        if result.expected_state == result.persisted_state:
            raise ValueError(
                "ReplayValidationResult DRIFT requires unequal states"
            )
        return

    if status == ReplayValidationStatus.NO_ACCEPTED_HISTORY:
        if expected_present:
            raise ValueError(
                "ReplayValidationResult NO_ACCEPTED_HISTORY requires absent "
                "expected_state"
            )
        return

    raise ValueError(f"Unsupported ReplayValidationResult status: {status}")


def _validate_snapshot_replay_result_shape(
    result: ProjectionSnapshotReplayValidationResult,
) -> None:
    """Reject snapshot-trust status, state, and lineage contradictions."""

    _validate_order_id(
        result.order_id,
        "ProjectionSnapshotReplayValidationResult",
    )
    status = result.status

    if not isinstance(status, ProjectionSnapshotReplayValidationStatus):
        raise ValueError(
            "ProjectionSnapshotReplayValidationResult.status must be "
            "ProjectionSnapshotReplayValidationStatus"
        )

    _validate_present_order_state(
        state=result.snapshot_assisted_state,
        result_order_id=result.order_id,
        result_type="ProjectionSnapshotReplayValidationResult",
        field_name="snapshot_assisted_state",
    )
    _validate_present_order_state(
        state=result.authority_state,
        result_order_id=result.order_id,
        result_type="ProjectionSnapshotReplayValidationResult",
        field_name="authority_state",
    )

    lineage_present = _validate_paired_snapshot_lineage(
        snapshot_id=result.snapshot_id,
        source_global_position=result.source_global_position,
        result_type="ProjectionSnapshotReplayValidationResult",
    )
    if status in {
        ProjectionSnapshotReplayValidationStatus.MATCH,
        ProjectionSnapshotReplayValidationStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION,
        ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT,
    }:
        _require_positive_snapshot_position(
            source_global_position=result.source_global_position,
            result_type="ProjectionSnapshotReplayValidationResult",
            status=status.value,
        )
    snapshot_state_present = result.snapshot_assisted_state is not None
    authority_state_present = result.authority_state is not None

    if status == ProjectionSnapshotReplayValidationStatus.MATCH:
        _require_loaded_snapshot_lineage(lineage_present, status.value)
        if not snapshot_state_present or not authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult MATCH requires "
                "snapshot_assisted_state and authority_state"
            )
        if result.snapshot_assisted_state != result.authority_state:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult MATCH requires "
                "equal states"
            )
        return

    if status == ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT:
        if lineage_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult MISSING_SNAPSHOT "
                "requires absent snapshot lineage"
            )
        if snapshot_state_present or not authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult MISSING_SNAPSHOT "
                "requires absent snapshot_assisted_state and present "
                "authority_state"
            )
        return

    if (
        status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    ):
        _require_loaded_snapshot_lineage(lineage_present, status.value)
        if snapshot_state_present or not authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult "
                "INVALID_SNAPSHOT_BOUNDARY requires absent "
                "snapshot_assisted_state and present authority_state"
            )
        return

    if (
        status
        == ProjectionSnapshotReplayValidationStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    ):
        _require_loaded_snapshot_lineage(lineage_present, status.value)
        if not snapshot_state_present or not authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult "
                "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION requires "
                "snapshot_assisted_state and authority_state"
            )
        return

    if (
        status
        == ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
    ):
        _require_loaded_snapshot_lineage(lineage_present, status.value)
        if not snapshot_state_present or not authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult "
                "SNAPSHOT_ASSISTED_DRIFT requires snapshot_assisted_state "
                "and authority_state"
            )
        return

    if (
        status
        == ProjectionSnapshotReplayValidationStatus
        .NO_ACCEPTED_HISTORY_FOR_ORDER
    ):
        if snapshot_state_present or authority_state_present:
            raise ValueError(
                "ProjectionSnapshotReplayValidationResult "
                "NO_ACCEPTED_HISTORY_FOR_ORDER requires absent comparison "
                "states"
            )
        return

    raise ValueError(
        "Unsupported ProjectionSnapshotReplayValidationResult status: "
        f"{status}"
    )


def _validate_snapshot_assisted_result_shape(
    result: ProjectionSnapshotAssistedResolutionResult,
) -> None:
    """Reject assisted-resolution status, state, and lineage contradictions."""

    _validate_order_id(
        result.order_id,
        "ProjectionSnapshotAssistedResolutionResult",
    )
    status = result.status

    if not isinstance(status, ProjectionSnapshotAssistedResolutionStatus):
        raise ValueError(
            "ProjectionSnapshotAssistedResolutionResult.status must be "
            "ProjectionSnapshotAssistedResolutionStatus"
        )

    _validate_present_order_state(
        state=result.resolved_state,
        result_order_id=result.order_id,
        result_type="ProjectionSnapshotAssistedResolutionResult",
        field_name="resolved_state",
    )

    snapshot_id_present = result.snapshot_id is not None
    position_present = result.source_global_position is not None
    resolved_state_present = result.resolved_state is not None

    if (
        status
        == ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_PRECONDITION
    ):
        if snapshot_id_present or position_present or resolved_state_present:
            raise ValueError(
                "ProjectionSnapshotAssistedResolutionResult "
                "INVALID_SNAPSHOT_PRECONDITION requires absent snapshot "
                "reference, lineage, and resolved_state"
            )
        return

    if status == ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT:
        if not snapshot_id_present or position_present or resolved_state_present:
            raise ValueError(
                "ProjectionSnapshotAssistedResolutionResult MISSING_SNAPSHOT "
                "requires requested snapshot_id, absent "
                "source_global_position, and absent resolved_state"
            )
        return

    if not snapshot_id_present or not position_present:
        raise ValueError(
            "ProjectionSnapshotAssistedResolutionResult "
            f"{status.value} requires loaded snapshot lineage"
        )

    if status in {
        ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT,
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION,
        ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
    }:
        _require_positive_snapshot_position(
            source_global_position=result.source_global_position,
            result_type="ProjectionSnapshotAssistedResolutionResult",
            status=status.value,
        )

    if (
        status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    ):
        if not resolved_state_present:
            raise ValueError(
                "ProjectionSnapshotAssistedResolutionResult "
                "RESOLVED_FROM_SNAPSHOT requires resolved_state"
            )
        return

    if status in {
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_COMPATIBILITY,
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION,
        ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
    }:
        if resolved_state_present:
            raise ValueError(
                "ProjectionSnapshotAssistedResolutionResult "
                f"{status.value} requires absent resolved_state"
            )
        return

    raise ValueError(
        "Unsupported ProjectionSnapshotAssistedResolutionResult status: "
        f"{status}"
    )


def _replay_subject(
    result: ReplayValidationResult,
) -> DecisionReceiptSubject:
    """Select the projection or order observation owned by replay validation."""

    if result.status == ReplayValidationStatus.NO_ACCEPTED_HISTORY:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id=result.order_id,
        )

    return DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.PROJECTION,
        subject_id=result.order_id,
    )


def _snapshot_replay_subject(
    result: ProjectionSnapshotReplayValidationResult,
) -> DecisionReceiptSubject:
    """Select a subject without converting observed failure into root cause."""

    status = result.status

    if status == ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.SNAPSHOT
        )

    if status in {
        ProjectionSnapshotReplayValidationStatus.MATCH,
        ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY,
    }:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(result.snapshot_id),
        )

    if (
        status
        == ProjectionSnapshotReplayValidationStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    ):
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.RUNTIME
        )

    if (
        status
        == ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
    ):
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=result.order_id,
        )

    if (
        status
        == ProjectionSnapshotReplayValidationStatus
        .NO_ACCEPTED_HISTORY_FOR_ORDER
    ):
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id=result.order_id,
        )

    raise ValueError(
        "Unsupported ProjectionSnapshotReplayValidationResult subject status: "
        f"{status}"
    )


def _snapshot_assisted_subject(
    result: ProjectionSnapshotAssistedResolutionResult,
) -> DecisionReceiptSubject:
    """Select an assisted-path subject without overstating snapshot causality."""

    status = result.status

    if (
        status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    ):
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=result.order_id,
        )

    if status in {
        ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_COMPATIBILITY,
    }:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(result.snapshot_id),
        )

    if status in {
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_PRECONDITION,
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION,
        ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
    }:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.RUNTIME
        )

    raise ValueError(
        "Unsupported ProjectionSnapshotAssistedResolutionResult subject "
        f"status: {status}"
    )


def _assisted_snapshot_artifact_present(
    status: ProjectionSnapshotAssistedResolutionStatus,
) -> bool:
    """Distinguish a requested missing ID from actually loaded lineage."""

    return status not in {
        ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_PRECONDITION,
    }


def _validate_order_id(order_id: str, result_type: str) -> None:
    """Apply receipt admission; generic results can still be built blank."""

    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError(f"{result_type}.order_id must be a non-empty string")


def _validate_present_order_state(
    *,
    state: object | None,
    result_order_id: str,
    result_type: str,
    field_name: str,
) -> None:
    """Require present receipt evidence to be state for the observed order."""

    if state is None:
        return

    qualified_field = f"{result_type}.{field_name}"
    if not isinstance(state, OrderState):
        raise ValueError(
            f"{qualified_field} must be OrderState when present"
        )

    if state.order_id != result_order_id:
        raise ValueError(
            f"{qualified_field} order_id mismatch: "
            f"state.order_id={state.order_id!r}, "
            f"{result_type}.order_id={result_order_id!r}"
        )


def _validate_paired_snapshot_lineage(
    *,
    snapshot_id: UUID | None,
    source_global_position: int | None,
    result_type: str,
) -> bool:
    snapshot_id_present = snapshot_id is not None
    position_present = source_global_position is not None

    if snapshot_id_present != position_present:
        raise ValueError(
            f"{result_type} requires snapshot_id and "
            "source_global_position to be both present or both absent"
        )

    return snapshot_id_present


def _require_loaded_snapshot_lineage(
    lineage_present: bool,
    status: str,
) -> None:
    if not lineage_present:
        raise ValueError(
            "ProjectionSnapshotReplayValidationResult "
            f"{status} requires loaded snapshot lineage"
        )


def _require_positive_snapshot_position(
    *,
    source_global_position: int | None,
    result_type: str,
    status: str,
) -> None:
    """Reject zero after producer boundary or compatibility validation."""

    if (
        type(source_global_position) is int
        and source_global_position == 0
    ):
        raise ValueError(
            f"{result_type} {status} requires "
            "source_global_position > 0"
        )
