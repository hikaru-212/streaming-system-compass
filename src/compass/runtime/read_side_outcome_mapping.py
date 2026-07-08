from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
)
from src.compass.runtime.technical_status_mapping import (
    map_runtime_technical_status,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
)
from src.pipeline.projection.replay_validator import ReplayValidationResult


def map_replay_validation_result_to_semantic_outcome(
    *,
    outcome_id: UUID,
    result: ReplayValidationResult,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Map durable projection replay validation evidence to SemanticOutcome.

    This adapter connects the Stage 3.5C durable replay validation result to the
    Stage 4A semantic outcome contract.

    It does not:
    - execute rebuild
    - mutate projection state
    - advance checkpoint progress
    - persist a receipt
    - decide runtime policy
    """

    return map_runtime_technical_status(
        outcome_id=outcome_id,
        technical_status=result.status,
        boundary=SemanticBoundary.LAYER_2_READ_SIDE,
        reason=_require_reason(result.reason, "ReplayValidationResult"),
        context=_merge_mappings(
            {
                "order_id": result.order_id,
            },
            context,
        ),
        evidence=_merge_mappings(
            {
                "result_type": "ReplayValidationResult",
                "expected_state_present": result.expected_state is not None,
                "persisted_state_present": result.persisted_state is not None,
            },
            evidence,
        ),
    )


def map_projection_snapshot_replay_validation_result_to_semantic_outcome(
    *,
    outcome_id: UUID,
    result: ProjectionSnapshotReplayValidationResult,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Map projection snapshot-assisted replay validation evidence to SemanticOutcome.

    This adapter connects the Stage 3.5D snapshot-assisted replay validator to
    the Stage 4A semantic outcome contract.

    It does not:
    - trust snapshots by itself
    - execute fallback
    - rebuild snapshots
    - quarantine snapshots
    - persist a receipt
    - decide runtime policy
    """

    return map_runtime_technical_status(
        outcome_id=outcome_id,
        technical_status=result.status,
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        reason=_require_reason(
            result.reason,
            "ProjectionSnapshotReplayValidationResult"
        ),
        context=_merge_mappings(
            {
                "order_id": result.order_id,
                "snapshot_id": result.snapshot_id,
                "source_global_position": result.source_global_position,
            },
            context,
        ),
        evidence=_merge_mappings(
            {
                "result_type": "ProjectionSnapshotReplayValidationResult",
                "snapshot_assisted_state_present": (
                    result.snapshot_assisted_state is not None
                ),
                "authority_state_present": result.authority_state is not None,
            },
            evidence,
        ),
    )


def map_projection_snapshot_assisted_resolution_result_to_semantic_outcome(
    *,
    outcome_id: UUID,
    result: ProjectionSnapshotAssistedResolutionResult,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Map projection snapshot-assisted resolution evidence to SemanticOutcome.

    This adapter connects the snapshot-assisted resolver result to the Stage 4A
    semantic outcome contract.

    The resolver consumes snapshot trust evidence supplied by the caller. This
    adapter does not prove that the snapshot matches accepted history.

    It does not:
    - execute fallback
    - prove snapshot authority equivalence
    - persist a receipt
    - decide runtime policy
    - choose strategy
    """

    return map_runtime_technical_status(
        outcome_id=outcome_id,
        technical_status=result.status,
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        reason=_require_reason(
            result.reason,
            "ProjectionSnapshotAssistedResolutionResult"
        ),
        context=_merge_mappings(
            {
                "order_id": result.order_id,
                "snapshot_id": result.snapshot_id,
                "source_global_position": result.source_global_position,
            },
            context,
        ),
        evidence=_merge_mappings(
            {
                "result_type": "ProjectionSnapshotAssistedResolutionResult",
                "resolved_state_present": result.resolved_state is not None,
            },
            evidence,
        ),
    )


def _require_reason(reason: str | None, result_type: str) -> str:
    if reason is None or not reason.strip():
        return f"Missing explicit reason from {result_type}."
    return reason


def _merge_mappings(
    base: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base)
    merged.update(dict(override or {}))
    return merged