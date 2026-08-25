"""First Stage 4C PostgreSQL write-side RuntimeDecision profile."""

from __future__ import annotations

from types import MappingProxyType

from src.compass.runtime.runtime_decision import (
    RuntimeDecision,
    RuntimeDecisionResponse,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
)
from src.compass.runtime.write_side_rule_feedback import (
    PostgresWriteSideSemanticRuleFeedback,
)


class PostgresWriteSideRuntimeDecisionRefused(ValueError):
    """Report that the first reviewed profile cannot issue authority.

    Refusal is distinct from every positive ``RuntimeDecision`` response. It
    therefore cannot be interpreted as use, block, escalation, or retry
    authority.
    """


class PostgresWriteSideRuntimeDecisionEvaluation:
    """Deliver one generic decision with its exact profile-specific source.

    Instances are returned only by
    ``evaluate_postgres_write_side_runtime_decision``. The two properties retain
    the exact ``RuntimeDecision`` and source-controlled
    ``PostgresWriteSideSemanticRuleFeedback`` object references. This carrier is
    specific to the first PostgreSQL/Order profile; it is not a universal
    evidence envelope, persistence format, retry contract, or execution plan.
    """

    __slots__ = ("_decision", "_source_feedback")

    def __init__(self) -> None:
        """Reject direct construction outside the profile evaluator."""

        raise TypeError(
            "PostgresWriteSideRuntimeDecisionEvaluation must be produced by "
            "evaluate_postgres_write_side_runtime_decision"
        )

    def __setattr__(self, name: str, value: object) -> None:
        """Keep the delivery's exact source references read-only."""

        raise AttributeError(
            "PostgresWriteSideRuntimeDecisionEvaluation attributes are read-only"
        )

    @classmethod
    def _from_evaluation(
        cls,
        *,
        decision: RuntimeDecision,
        source_feedback: PostgresWriteSideSemanticRuleFeedback,
    ) -> "PostgresWriteSideRuntimeDecisionEvaluation":
        """Build one coherent evaluator-owned delivery without copying."""

        if not isinstance(decision, RuntimeDecision):
            raise TypeError("decision must be RuntimeDecision")
        if not isinstance(
            source_feedback,
            PostgresWriteSideSemanticRuleFeedback,
        ):
            raise TypeError(
                "source_feedback must be "
                "PostgresWriteSideSemanticRuleFeedback"
            )
        if decision.semantic_outcome is not source_feedback.semantic_outcome:
            raise ValueError(
                "decision must retain the exact source SemanticOutcome"
            )

        instance = object.__new__(cls)
        object.__setattr__(instance, "_decision", decision)
        object.__setattr__(instance, "_source_feedback", source_feedback)
        return instance

    @property
    def decision(self) -> RuntimeDecision:
        """Return the generic current-response authority."""

        return self._decision

    @property
    def source_feedback(self) -> PostgresWriteSideSemanticRuleFeedback:
        """Return the exact source-controlled profile input."""

        return self._source_feedback


_SUPPORTED_RESPONSES = MappingProxyType({
    (
        SemanticBoundary.LAYER_1_WRITE_SIDE,
        SemanticOutcomeCategory.VALID,
        SemanticOutcomeCode.SEMANTICALLY_VALID,
    ): RuntimeDecisionResponse.USE_CURRENT_RESULT,
    (
        SemanticBoundary.LAYER_1_WRITE_SIDE,
        SemanticOutcomeCategory.RETRY_CLASSIFIED,
        SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED,
    ): RuntimeDecisionResponse.RETURN_PRIOR_ACCEPTED_RESULT,
    (
        SemanticBoundary.LAYER_1_WRITE_SIDE,
        SemanticOutcomeCategory.BLOCK_REQUIRED,
        SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED,
    ): RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION,
    (
        SemanticBoundary.LAYER_1_WRITE_SIDE,
        SemanticOutcomeCategory.ESCALATION_REQUIRED,
        SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW,
    ): RuntimeDecisionResponse.REQUIRE_ESCALATION,
})


def evaluate_postgres_write_side_runtime_decision(
    feedback: PostgresWriteSideSemanticRuleFeedback,
) -> PostgresWriteSideRuntimeDecisionEvaluation:
    """Evaluate the first reviewed Layer-1 PostgreSQL/Order profile.

    Args:
        feedback: Existing source-controlled composition of the terminal
            ``SemanticOutcome`` and any terminally applicable exact Order-rule
            refinement.

    Returns:
        A read-only profile delivery containing one generic ``RuntimeDecision``
        and the exact input feedback. The evaluator reads only typed outcome and
        refinement fields. It does not parse reason, context, evidence,
        metadata, or other human text.

    Raises:
        TypeError: If ``feedback`` has the wrong Python structural type.
        PostgresWriteSideRuntimeDecisionRefused: If the semantic tuple is
            outside the four reviewed first-profile cases, including
            concurrency uncertainty, or if exact rule refinement is incoherent
            with the selected response family.

    The decision governs response to an already-completed current condition.
    It does not authorize append admission, another attempt, retry, repair,
    strategy selection, operator workflow execution, or any other action
    execution.
    """

    if not isinstance(feedback, PostgresWriteSideSemanticRuleFeedback):
        raise TypeError(
            "feedback must be PostgresWriteSideSemanticRuleFeedback"
        )

    semantic_outcome = feedback.semantic_outcome
    semantic_key = (
        semantic_outcome.boundary,
        semantic_outcome.category,
        semantic_outcome.semantic_code,
    )
    response = _SUPPORTED_RESPONSES.get(semantic_key)
    if response is None:
        raise PostgresWriteSideRuntimeDecisionRefused(
            "no authoritative RuntimeDecision exists for semantic tuple "
            f"{semantic_outcome.boundary.value}/"
            f"{semantic_outcome.category.value}/"
            f"{semantic_outcome.semantic_code.value}"
        )

    rule_refinement = feedback.rule_refinement
    if (
        rule_refinement is not None
        and response is not RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION
    ):
        raise PostgresWriteSideRuntimeDecisionRefused(
            "terminal Order-rule refinement is only coherent with the "
            "reviewed block-current-continuation response family"
        )

    explanation = _explain_response(
        response=response,
        feedback=feedback,
    )
    decision = RuntimeDecision._from_evaluation(
        response=response,
        semantic_outcome=semantic_outcome,
        explanation=explanation,
    )
    return PostgresWriteSideRuntimeDecisionEvaluation._from_evaluation(
        decision=decision,
        source_feedback=feedback,
    )


def _explain_response(
    *,
    response: RuntimeDecisionResponse,
    feedback: PostgresWriteSideSemanticRuleFeedback,
) -> str:
    """Build non-authoritative review text from already-selected typed fields."""

    if response is RuntimeDecisionResponse.USE_CURRENT_RESULT:
        return (
            "The caller may use or return the already-completed current result; "
            "this decision does not authorize candidate append admission."
        )
    if response is RuntimeDecisionResponse.RETURN_PRIOR_ACCEPTED_RESULT:
        return (
            "The caller may return the prior accepted result; this decision "
            "does not authorize another attempt or retry."
        )
    if response is RuntimeDecisionResponse.REQUIRE_ESCALATION:
        return (
            "The current condition requires escalation; this decision does not "
            "execute an operator workflow."
        )

    if response is RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION:
        rule_refinement = feedback.rule_refinement
        if rule_refinement is None:
            return (
                "Current downstream continuation is blocked by a semantic "
                "conflict; this decision authorizes no repair, regeneration, "
                "reload, retry, or another attempt."
            )
        return (
            "Current downstream continuation is blocked by a semantic conflict "
            f"refined by terminal Order rule {rule_refinement.rule_id.value}; "
            "this decision authorizes no repair, regeneration, reload, retry, "
            "or another attempt."
        )

    raise AssertionError(f"unsupported RuntimeDecisionResponse: {response}")


__all__ = (
    "PostgresWriteSideRuntimeDecisionEvaluation",
    "PostgresWriteSideRuntimeDecisionRefused",
    "evaluate_postgres_write_side_runtime_decision",
)
