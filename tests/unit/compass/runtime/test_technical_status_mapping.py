from enum import Enum
from uuid import UUID

import pytest

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.compass.runtime.technical_status_mapping import (
    map_runtime_technical_status,
    supported_runtime_technical_statuses,
)

OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000101")


class ExampleTechnicalStatus(str, Enum):
    MATCH = "MATCH"
    TAIL_REPLAY_FAILED = "TAIL_REPLAY_FAILED"


class NumericTechnicalStatus(Enum):
    MATCH = 1
    TAIL_REPLAY_FAILED = 2


def map_status(
    technical_status: str | Enum,
    *,
    boundary: SemanticBoundary = SemanticBoundary.RUNTIME_GOVERNANCE,
):
    return map_runtime_technical_status(
        outcome_id=OUTCOME_ID,
        technical_status=technical_status,
        boundary=boundary,
        reason="Runtime technical status was mapped to semantic meaning.",
        context={"order_id": "order-001"},
        evidence={"source": "unit-test"},
    )


@pytest.mark.parametrize(
    ("technical_status", "expected_ok"),
    [
        ("MATCH", True),
        ("RESOLVED_FROM_SNAPSHOT", True),
    ],
)
def test_valid_runtime_statuses_map_to_semantically_valid(
    technical_status: str,
    expected_ok: bool,
) -> None:
    outcome = map_status(technical_status)

    assert outcome.ok is expected_ok
    assert outcome.category == SemanticOutcomeCategory.VALID
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.severity == SemanticSeverity.INFO
    assert outcome.risk_level == SemanticRiskLevel.LOW
    assert outcome.reversibility == SemanticReversibility.REVERSIBLE
    assert outcome.evidence["technical_status"] == technical_status


def test_missing_snapshot_maps_to_fast_path_unavailable() -> None:
    outcome = map_status(
        "MISSING_SNAPSHOT",
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.FALLBACK_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.FAST_PATH_UNAVAILABLE
    assert outcome.severity == SemanticSeverity.WARNING
    assert outcome.risk_level == SemanticRiskLevel.MEDIUM
    assert outcome.reversibility == SemanticReversibility.REVERSIBLE


def test_missing_projection_maps_to_rebuild_required() -> None:
    outcome = map_status(
        "MISSING_PROJECTION",
        boundary=SemanticBoundary.LAYER_2_READ_SIDE,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.REBUILD_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.REQUIRES_REBUILD
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE


@pytest.mark.parametrize(
    "technical_status",
    [
        "NO_ACCEPTED_HISTORY",
        "NO_ACCEPTED_HISTORY_FOR_ORDER",
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION",
    ],
)
def test_unresolved_runtime_statuses_map_to_runtime_unresolved(
    technical_status: str,
) -> None:
    outcome = map_status(technical_status)

    assert outcome.ok is False
    assert outcome.category == SemanticOutcomeCategory.UNRESOLVED
    assert outcome.semantic_code == SemanticOutcomeCode.RUNTIME_UNRESOLVED
    assert outcome.evidence["technical_status"] == technical_status


@pytest.mark.parametrize(
    "technical_status",
    [
        "INVALID_SNAPSHOT_BOUNDARY",
        "INVALID_SNAPSHOT_PRECONDITION",
        "INVALID_SNAPSHOT_COMPATIBILITY",
    ],
)
def test_invalid_snapshot_statuses_map_to_derived_state_untrusted(
    technical_status: str,
) -> None:
    outcome = map_status(
        technical_status,
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.UNTRUSTED
    assert outcome.semantic_code == SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE


def test_tail_replay_failed_maps_to_fast_path_unavailable_not_drift() -> None:
    outcome = map_status(
        "TAIL_REPLAY_FAILED",
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.FALLBACK_REQUIRED
    assert outcome.semantic_code == SemanticOutcomeCode.FAST_PATH_UNAVAILABLE
    assert outcome.semantic_code != SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.reversibility == SemanticReversibility.REVERSIBLE


def test_generic_drift_status_maps_to_read_side_drift_detected() -> None:
    outcome = map_status(
        "DRIFT",
        boundary=SemanticBoundary.LAYER_2_READ_SIDE,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.LAYER_2_READ_SIDE
    assert outcome.category == SemanticOutcomeCategory.DRIFT
    assert outcome.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE


def test_snapshot_assisted_drift_status_maps_to_snapshot_trust_drift_detected() -> None:
    outcome = map_status(
        "SNAPSHOT_ASSISTED_DRIFT",
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.DRIFT
    assert outcome.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE


@pytest.mark.parametrize(
    "technical_status",
    [
        "OCC_CONFLICT_AFTER_VALIDATION",
        "LOCK_TIMEOUT",
    ],
)
def test_concurrency_statuses_map_to_concurrency_uncertain(
    technical_status: str,
) -> None:
    outcome = map_status(
        technical_status,
        boundary=SemanticBoundary.CONCURRENCY_ADMISSION,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.CONCURRENCY_ADMISSION
    assert outcome.category == SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    assert outcome.semantic_code == SemanticOutcomeCode.CONCURRENCY_UNCERTAIN
    assert outcome.severity == SemanticSeverity.WARNING
    assert outcome.risk_level == SemanticRiskLevel.MEDIUM
    assert outcome.reversibility == SemanticReversibility.REVERSIBLE


def test_idempotent_replay_maps_to_idempotent_replay_allowed() -> None:
    outcome = map_status(
        "IDEMPOTENT_REPLAY",
        boundary=SemanticBoundary.IDEMPOTENCY,
    )

    assert outcome.ok is True
    assert outcome.boundary == SemanticBoundary.IDEMPOTENCY
    assert outcome.category == SemanticOutcomeCategory.RETRY_CLASSIFIED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED
    )
    assert outcome.severity == SemanticSeverity.INFO
    assert outcome.risk_level == SemanticRiskLevel.LOW


def test_idempotency_conflict_maps_to_semantic_conflict_detected() -> None:
    outcome = map_status(
        "IDEMPOTENCY_CONFLICT",
        boundary=SemanticBoundary.IDEMPOTENCY,
    )

    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.IDEMPOTENCY
    assert outcome.category == SemanticOutcomeCategory.BLOCK_REQUIRED
    assert (
        outcome.semantic_code
        == SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
    )
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH


def test_mapper_accepts_enum_technical_status_values() -> None:
    outcome = map_status(ExampleTechnicalStatus.MATCH)

    assert outcome.ok is True
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.evidence["technical_status"] == "MATCH"


def test_mapper_accepts_enum_technical_status_names_when_values_are_not_strings() -> None:
    outcome = map_status(NumericTechnicalStatus.MATCH)

    assert outcome.ok is True
    assert outcome.semantic_code == SemanticOutcomeCode.SEMANTICALLY_VALID
    assert outcome.evidence["technical_status"] == "MATCH"


def test_mapper_preserves_context_and_evidence() -> None:
    outcome = map_runtime_technical_status(
        outcome_id=OUTCOME_ID,
        technical_status="MATCH",
        boundary=SemanticBoundary.LAYER_2_READ_SIDE,
        reason="Projection state matches accepted-history replay.",
        context={
            "order_id": "order-001",
            "source_global_position": 10,
        },
        evidence={
            "validator": "DurableReplayValidator",
            "accepted_event_count": 2,
        },
    )

    assert outcome.context == {
        "order_id": "order-001",
        "source_global_position": 10,
    }
    assert outcome.evidence == {
        "validator": "DurableReplayValidator",
        "accepted_event_count": 2,
        "technical_status": "MATCH",
    }


def test_mapper_uses_empty_context_and_injects_technical_status_evidence() -> None:
    outcome = map_runtime_technical_status(
        outcome_id=OUTCOME_ID,
        technical_status="MATCH",
        boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
        reason="Runtime status matched.",
    )

    assert outcome.context == {}
    assert outcome.evidence == {"technical_status": "MATCH"}


def test_mapper_rejects_evidence_with_conflicting_technical_status() -> None:
    with pytest.raises(
        ValueError,
        match="evidence technical_status must match mapped technical_status",
    ):
        map_runtime_technical_status(
            outcome_id=OUTCOME_ID,
            technical_status="MATCH",
            boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
            reason="Runtime status matched.",
            evidence={"technical_status": "TAIL_REPLAY_FAILED"},
        )


def test_mapper_rejects_unsupported_technical_status() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported runtime technical status: UNKNOWN_STATUS",
    ):
        map_status("UNKNOWN_STATUS")


@pytest.mark.parametrize("technical_status", ["", "   "])
def test_mapper_rejects_blank_technical_status(technical_status: str) -> None:
    with pytest.raises(
        ValueError,
        match="technical_status must be a non-empty string",
    ):
        map_status(technical_status)


def test_mapper_rejects_non_string_non_enum_technical_status() -> None:
    with pytest.raises(
        TypeError,
        match="technical_status must be a string or Enum value",
    ):
        map_status(123)  # type: ignore[arg-type]


def test_mapper_rejects_blank_reason_through_semantic_outcome_contract() -> None:
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        map_runtime_technical_status(
            outcome_id=OUTCOME_ID,
            technical_status="MATCH",
            boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
            reason="",
        )


def test_runtime_technical_status_mappings_are_stable() -> None:
    expected_mappings = {
        "MATCH": (
            True,
            SemanticOutcomeCategory.VALID,
            SemanticOutcomeCode.SEMANTICALLY_VALID,
            SemanticSeverity.INFO,
            SemanticRiskLevel.LOW,
            SemanticReversibility.REVERSIBLE,
        ),
        "RESOLVED_FROM_SNAPSHOT": (
            True,
            SemanticOutcomeCategory.VALID,
            SemanticOutcomeCode.SEMANTICALLY_VALID,
            SemanticSeverity.INFO,
            SemanticRiskLevel.LOW,
            SemanticReversibility.REVERSIBLE,
        ),
        "MISSING_SNAPSHOT": (
            False,
            SemanticOutcomeCategory.FALLBACK_REQUIRED,
            SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.MEDIUM,
            SemanticReversibility.REVERSIBLE,
        ),
        "MISSING_PROJECTION": (
            False,
            SemanticOutcomeCategory.REBUILD_REQUIRED,
            SemanticOutcomeCode.REQUIRES_REBUILD,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.MEDIUM,
            SemanticReversibility.REBUILDABLE,
        ),
        "NO_ACCEPTED_HISTORY": (
            False,
            SemanticOutcomeCategory.UNRESOLVED,
            SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.UNKNOWN,
            SemanticReversibility.UNKNOWN,
        ),
        "NO_ACCEPTED_HISTORY_FOR_ORDER": (
            False,
            SemanticOutcomeCategory.UNRESOLVED,
            SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.UNKNOWN,
            SemanticReversibility.UNKNOWN,
        ),
        "INVALID_SNAPSHOT_BOUNDARY": (
            False,
            SemanticOutcomeCategory.UNTRUSTED,
            SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.REBUILDABLE,
        ),
        "INVALID_SNAPSHOT_PRECONDITION": (
            False,
            SemanticOutcomeCategory.UNTRUSTED,
            SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.REBUILDABLE,
        ),
        "INVALID_SNAPSHOT_COMPATIBILITY": (
            False,
            SemanticOutcomeCategory.UNTRUSTED,
            SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.REBUILDABLE,
        ),
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION": (
            False,
            SemanticOutcomeCategory.UNRESOLVED,
            SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.UNKNOWN,
        ),
        "TAIL_REPLAY_FAILED": (
            False,
            SemanticOutcomeCategory.FALLBACK_REQUIRED,
            SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.MEDIUM,
            SemanticReversibility.REVERSIBLE,
        ),
        "DRIFT": (
            False,
            SemanticOutcomeCategory.DRIFT,
            SemanticOutcomeCode.DRIFT_DETECTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.REBUILDABLE,
        ),
        "SNAPSHOT_ASSISTED_DRIFT": (
            False,
            SemanticOutcomeCategory.DRIFT,
            SemanticOutcomeCode.DRIFT_DETECTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.REBUILDABLE,
        ),
        "OCC_CONFLICT_AFTER_VALIDATION": (
            False,
            SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
            SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.MEDIUM,
            SemanticReversibility.REVERSIBLE,
        ),
        "LOCK_TIMEOUT": (
            False,
            SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
            SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
            SemanticSeverity.WARNING,
            SemanticRiskLevel.MEDIUM,
            SemanticReversibility.REVERSIBLE,
        ),
        "IDEMPOTENT_REPLAY": (
            True,
            SemanticOutcomeCategory.RETRY_CLASSIFIED,
            SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED,
            SemanticSeverity.INFO,
            SemanticRiskLevel.LOW,
            SemanticReversibility.REVERSIBLE,
        ),
        "IDEMPOTENCY_CONFLICT": (
            False,
            SemanticOutcomeCategory.BLOCK_REQUIRED,
            SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED,
            SemanticSeverity.ERROR,
            SemanticRiskLevel.HIGH,
            SemanticReversibility.UNKNOWN,
        ),
    }

    assert supported_runtime_technical_statuses() == frozenset(
        expected_mappings
    )

    for technical_status, expected in expected_mappings.items():
        outcome = map_runtime_technical_status(
            outcome_id=OUTCOME_ID,
            technical_status=technical_status,
            boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
            reason="Runtime technical status was mapped to semantic meaning.",
        )

        assert (
            outcome.ok,
            outcome.category,
            outcome.semantic_code,
            outcome.severity,
            outcome.risk_level,
            outcome.reversibility,
        ) == expected
        assert outcome.evidence["technical_status"] == technical_status


def test_supported_runtime_technical_statuses_are_stable() -> None:
    assert supported_runtime_technical_statuses() == frozenset(
        {
            "MATCH",
            "RESOLVED_FROM_SNAPSHOT",
            "MISSING_SNAPSHOT",
            "MISSING_PROJECTION",
            "NO_ACCEPTED_HISTORY",
            "NO_ACCEPTED_HISTORY_FOR_ORDER",
            "INVALID_SNAPSHOT_BOUNDARY",
            "INVALID_SNAPSHOT_PRECONDITION",
            "INVALID_SNAPSHOT_COMPATIBILITY",
            "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION",
            "TAIL_REPLAY_FAILED",
            "DRIFT",
            "SNAPSHOT_ASSISTED_DRIFT",
            "OCC_CONFLICT_AFTER_VALIDATION",
            "LOCK_TIMEOUT",
            "IDEMPOTENT_REPLAY",
            "IDEMPOTENCY_CONFLICT",
        }
    )


def test_mapping_does_not_add_decision_strategy_or_retry_fields() -> None:
    outcome = map_status("TAIL_REPLAY_FAILED")

    assert not hasattr(outcome, "runtime_action")
    assert not hasattr(outcome, "decision")
    assert not hasattr(outcome, "strategy")
    assert not hasattr(outcome, "retry_allowed")
    assert not hasattr(outcome, "recovery_action")