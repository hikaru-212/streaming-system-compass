from dataclasses import FrozenInstanceError, fields
from uuid import UUID

import pytest

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)

OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_semantic_outcome(**overrides: object) -> SemanticOutcome:
    values: dict[str, object] = {
        "outcome_id": OUTCOME_ID,
        "ok": False,
        "boundary": SemanticBoundary.SNAPSHOT_TRUST,
        "category": SemanticOutcomeCategory.DRIFT,
        "semantic_code": SemanticOutcomeCode.DRIFT_DETECTED,
        "severity": SemanticSeverity.ERROR,
        "risk_level": SemanticRiskLevel.HIGH,
        "reversibility": SemanticReversibility.REBUILDABLE,
        "reason": "Snapshot-assisted reconstruction diverged from authority.",
        "context": {"order_id": "order-001"},
        "evidence": {"technical_status": "SNAPSHOT_ASSISTED_DRIFT"},
    }
    values.update(overrides)
    return SemanticOutcome(**values)  # type: ignore[arg-type]


def test_semantic_outcome_preserves_required_fields() -> None:
    outcome = make_semantic_outcome()

    assert outcome.outcome_id == OUTCOME_ID
    assert outcome.ok is False
    assert outcome.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert outcome.category == SemanticOutcomeCategory.DRIFT
    assert outcome.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert outcome.severity == SemanticSeverity.ERROR
    assert outcome.risk_level == SemanticRiskLevel.HIGH
    assert outcome.reversibility == SemanticReversibility.REBUILDABLE
    assert (
        outcome.reason
        == "Snapshot-assisted reconstruction diverged from authority."
    )
    assert outcome.context == {"order_id": "order-001"}
    assert outcome.evidence == {
        "technical_status": "SNAPSHOT_ASSISTED_DRIFT"
    }


def test_semantic_outcome_defaults_context_and_evidence_to_empty_mappings() -> None:
    outcome = SemanticOutcome(
        outcome_id=OUTCOME_ID,
        ok=True,
        boundary=SemanticBoundary.LAYER_2_READ_SIDE,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
        reason="Runtime evidence is semantically valid.",
    )

    assert outcome.context == {}
    assert outcome.evidence == {}


def test_semantic_outcome_defensively_copies_and_deep_freezes_mappings() -> None:
    context = {"tags": ["read-side", "snapshot"]}
    evidence = {
        "technical_status": "TAIL_REPLAY_FAILED",
        "failed_sequences": [1, 2, 3],
        "details": {"tail_source": "projection_event_source"},
    }

    outcome = make_semantic_outcome(context=context, evidence=evidence)

    context["tags"].append("mutated")
    evidence["failed_sequences"].append(4)
    evidence["details"]["tail_source"] = "mutated"

    assert outcome.context["tags"] == ("read-side", "snapshot")
    assert outcome.evidence["failed_sequences"] == (1, 2, 3)
    assert (
        outcome.evidence["details"]["tail_source"]
        == "projection_event_source"
    )

    with pytest.raises(AttributeError):
        outcome.evidence["failed_sequences"].append(4)

    with pytest.raises(TypeError):
        outcome.evidence["details"]["tail_source"] = "mutated"


@pytest.mark.parametrize("field_name", ["context", "evidence"])
def test_semantic_outcome_context_and_evidence_are_read_only(
    field_name: str,
) -> None:
    outcome = make_semantic_outcome()
    mapping = getattr(outcome, field_name)

    with pytest.raises(TypeError):
        mapping["new_key"] = "new-value"


def test_semantic_outcome_is_frozen() -> None:
    outcome = make_semantic_outcome()

    with pytest.raises(FrozenInstanceError):
        outcome.reason = "changed"  # type: ignore[misc]


def test_semantic_outcome_rejects_non_uuid_outcome_id() -> None:
    with pytest.raises(TypeError, match="outcome_id must be UUID"):
        make_semantic_outcome(outcome_id="outcome-001")


@pytest.mark.parametrize("reason", ["", "   "])
def test_semantic_outcome_rejects_blank_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        make_semantic_outcome(reason=reason)


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        ("boundary", "SNAPSHOT_TRUST", "boundary must be SemanticBoundary"),
        ("category", "DRIFT", "category must be SemanticOutcomeCategory"),
        (
            "semantic_code",
            "DRIFT_DETECTED",
            "semantic_code must be SemanticOutcomeCode",
        ),
        ("severity", "ERROR", "severity must be SemanticSeverity"),
        ("risk_level", "HIGH", "risk_level must be SemanticRiskLevel"),
        (
            "reversibility",
            "REBUILDABLE",
            "reversibility must be SemanticReversibility",
        ),
    ],
)
def test_semantic_outcome_rejects_raw_strings_for_enum_fields(
    field_name: str,
    bad_value: str,
    expected_message: str,
) -> None:
    with pytest.raises(TypeError, match=expected_message):
        make_semantic_outcome(**{field_name: bad_value})


@pytest.mark.parametrize("field_name", ["context", "evidence"])
def test_semantic_outcome_rejects_non_mapping_context_or_evidence(
    field_name: str,
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be a mapping"):
        make_semantic_outcome(**{field_name: ["not", "a", "mapping"]})


def test_semantic_outcome_codes_keep_fast_path_failure_distinct_from_drift() -> None:
    fast_path_unavailable = make_semantic_outcome(
        outcome_id=UUID("00000000-0000-0000-0000-000000000002"),
        ok=False,
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
        semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
        reason="Snapshot fast path is unavailable for this request.",
        evidence={"technical_status": "TAIL_REPLAY_FAILED"},
    )

    drift_detected = make_semantic_outcome(
        outcome_id=UUID("00000000-0000-0000-0000-000000000003"),
        ok=False,
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        category=SemanticOutcomeCategory.DRIFT,
        semantic_code=SemanticOutcomeCode.DRIFT_DETECTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
        reason="Snapshot-assisted reconstruction diverged from authority.",
        evidence={"technical_status": "SNAPSHOT_ASSISTED_DRIFT"},
    )

    assert fast_path_unavailable.semantic_code != drift_detected.semantic_code
    assert fast_path_unavailable.category != drift_detected.category
    assert fast_path_unavailable.evidence == {
        "technical_status": "TAIL_REPLAY_FAILED"
    }
    assert drift_detected.evidence == {
        "technical_status": "SNAPSHOT_ASSISTED_DRIFT"
    }


def test_semantic_outcome_contract_does_not_include_decision_strategy_or_retry_fields() -> None:
    field_names = {field.name for field in fields(SemanticOutcome)}

    assert "runtime_action" not in field_names
    assert "decision" not in field_names
    assert "strategy" not in field_names
    assert "retry_allowed" not in field_names
    assert "recovery_action" not in field_names


def test_semantic_outcome_enum_member_sets_are_stable() -> None:
    assert {item.value for item in SemanticOutcomeCategory} == {
        "VALID",
        "UNRESOLVED",
        "UNTRUSTED",
        "DRIFT",
        "FALLBACK_REQUIRED",
        "REBUILD_REQUIRED",
        "BLOCK_REQUIRED",
        "ESCALATION_REQUIRED",
        "CONCURRENCY_UNCERTAIN",
        "RETRY_CLASSIFIED",
        "INTENT_INCONSISTENT",
    }

    assert {item.value for item in SemanticOutcomeCode} == {
        "SEMANTICALLY_VALID",
        "RUNTIME_UNRESOLVED",
        "DERIVED_STATE_UNTRUSTED",
        "DRIFT_DETECTED",
        "FAST_PATH_UNAVAILABLE",
        "REQUIRES_AUTHORITY_FALLBACK",
        "REQUIRES_REBUILD",
        "REQUIRES_OPERATOR_REVIEW",
        "REJECT_DOWNSTREAM_USAGE",
        "CONCURRENCY_UNCERTAIN",
        "IDEMPOTENT_REPLAY_ALLOWED",
        "SEMANTIC_CONFLICT_DETECTED",
        "INTENT_DRIFT_DETECTED",
    }

    assert {item.value for item in SemanticBoundary} == {
        "LAYER_1_WRITE_SIDE",
        "LAYER_2_READ_SIDE",
        "SNAPSHOT_TRUST",
        "IDEMPOTENCY",
        "CONCURRENCY_ADMISSION",
        "RUNTIME_GOVERNANCE",
    }

    assert {item.value for item in SemanticSeverity} == {
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }

    assert {item.value for item in SemanticRiskLevel} == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "UNKNOWN",
    }

    assert {item.value for item in SemanticReversibility} == {
        "REVERSIBLE",
        "REBUILDABLE",
        "COMPENSABLE",
        "IRREVERSIBLE",
        "UNKNOWN",
    }
