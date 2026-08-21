from dataclasses import FrozenInstanceError, fields
from uuid import UUID

import pytest

import src.compass.runtime.runtime_decision as runtime_decision_module
from src.compass.runtime.runtime_decision import (
    RuntimeDecision,
    RuntimeDecisionResponse,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


def _semantic_outcome() -> SemanticOutcome:
    return SemanticOutcome(
        outcome_id=UUID("00000000-0000-0000-0000-000000000801"),
        ok=True,
        boundary=SemanticBoundary.LAYER_1_WRITE_SIDE,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
        reason="The completed write-side result is semantically valid.",
    )


def _decision(
    *,
    response: RuntimeDecisionResponse = (
        RuntimeDecisionResponse.USE_CURRENT_RESULT
    ),
    semantic_outcome: SemanticOutcome | None = None,
    explanation: str = "Use the already-completed current result.",
) -> RuntimeDecision:
    return RuntimeDecision._from_evaluation(
        response=response,
        semantic_outcome=semantic_outcome or _semantic_outcome(),
        explanation=explanation,
    )


def test_runtime_decision_response_vocabulary_is_closed_and_subject_explicit() -> None:
    assert {response.value for response in RuntimeDecisionResponse} == {
        "USE_CURRENT_RESULT",
        "RETURN_PRIOR_ACCEPTED_RESULT",
        "BLOCK_CURRENT_CONTINUATION",
        "REQUIRE_ESCALATION",
    }
    assert not {"ALLOW", "BLOCK", "REPLAY"}.intersection(
        response.value for response in RuntimeDecisionResponse
    )


def test_runtime_decision_retains_exact_semantic_outcome_and_explanation() -> None:
    semantic_outcome = _semantic_outcome()

    decision = _decision(
        semantic_outcome=semantic_outcome,
        explanation="Reviewable but non-authoritative explanation.",
    )

    assert decision.response is RuntimeDecisionResponse.USE_CURRENT_RESULT
    assert decision.semantic_outcome is semantic_outcome
    assert decision.explanation == (
        "Reviewable but non-authoritative explanation."
    )


def test_runtime_decision_is_frozen() -> None:
    decision = _decision()

    with pytest.raises(FrozenInstanceError):
        decision.explanation = "changed"  # type: ignore[misc]


def test_runtime_decision_rejects_direct_construction() -> None:
    with pytest.raises(TypeError, match="must be produced by a reviewed"):
        RuntimeDecision()


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        (
            "response",
            "USE_CURRENT_RESULT",
            "response must be RuntimeDecisionResponse",
        ),
        (
            "semantic_outcome",
            object(),
            "semantic_outcome must be SemanticOutcome",
        ),
        ("explanation", 1, "explanation must be str"),
    ],
)
def test_runtime_decision_rejects_wrong_structural_types(
    field_name: str,
    bad_value: object,
    expected_message: str,
) -> None:
    values: dict[str, object] = {
        "response": RuntimeDecisionResponse.USE_CURRENT_RESULT,
        "semantic_outcome": _semantic_outcome(),
        "explanation": "Use the already-completed current result.",
    }
    values[field_name] = bad_value

    with pytest.raises(TypeError, match=expected_message):
        RuntimeDecision._from_evaluation(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("explanation", ["", "   "])
def test_runtime_decision_rejects_blank_explanation(explanation: str) -> None:
    with pytest.raises(
        ValueError,
        match="explanation must be a non-empty string",
    ):
        _decision(explanation=explanation)


def test_runtime_decision_has_only_current_response_responsibilities() -> None:
    assert {field.name for field in fields(RuntimeDecision)} == {
        "response",
        "semantic_outcome",
        "explanation",
    }

    forbidden_fields = {
        "outcome_id",
        "boundary",
        "category",
        "semantic_code",
        "reason_code",
        "order_rule_id",
        "decision_id",
        "policy_id",
        "policy_version",
        "retry_allowed",
        "attempt_count",
        "strategy",
        "execution_instruction",
        "persistence_status",
        "metadata",
        "evidence",
    }
    assert forbidden_fields.isdisjoint(
        field.name for field in fields(RuntimeDecision)
    )


def test_generic_module_has_no_profile_specific_runtime_dependencies() -> None:
    assert "PostgresWriteSideResult" not in runtime_decision_module.__dict__
    assert (
        "PostgresWriteSideSemanticRuleFeedback"
        not in runtime_decision_module.__dict__
    )
    assert "OrderRuleViolationEvidence" not in runtime_decision_module.__dict__

