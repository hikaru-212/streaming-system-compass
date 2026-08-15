"""Compose terminal write-side semantics with exact Order rule refinement."""

from __future__ import annotations

from uuid import UUID

from src.compass.runtime.semantic_outcome import SemanticOutcome
from src.compass.runtime.write_side_outcome_mapping import (
    map_postgres_write_side_result_to_semantic_outcome,
)
from src.core.order.rule_violation_evidence import OrderRuleViolationEvidence
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)


class PostgresWriteSideSemanticRuleFeedback:
    """Carry one Stage 4A outcome with terminal Order-rule refinement.

    Instances are produced only by the PostgreSQL write-side rule-feedback
    mapper. The mapper derives both views from one ``PostgresWriteSideResult``:
    the existing Stage 4A mapper produces ``semantic_outcome``, while an exact
    source rule observation becomes ``rule_refinement`` only when validation
    block is the terminal write-side outcome. Successful construction for a
    ``VALIDATION_BLOCKED`` result requires exact Order rule evidence. A
    ``None`` refinement therefore means refinement is not applicable to the
    terminal outcome; it never silently represents missing required validation
    refinement.

    This is a source-controlled in-process composition boundary. It does not
    establish authenticity, durable or cross-process provenance, retry
    authority, complete violation coverage, or live Agent transport.
    """

    __slots__ = ("_semantic_outcome", "_rule_refinement")

    def __init__(self) -> None:
        """Reject direct construction outside the source-specific mapper."""

        raise TypeError(
            "PostgresWriteSideSemanticRuleFeedback must be produced by "
            "map_postgres_write_side_result_to_semantic_rule_feedback"
        )

    def __setattr__(self, name: str, value: object) -> None:
        """Keep the composition's source references read-only."""

        raise AttributeError(
            "PostgresWriteSideSemanticRuleFeedback attributes are read-only"
        )

    @classmethod
    def _from_source(
        cls,
        *,
        semantic_outcome: SemanticOutcome,
        result: PostgresWriteSideResult,
    ) -> "PostgresWriteSideSemanticRuleFeedback":
        """Build one coherent terminal view from the exact mapped source."""

        if not isinstance(semantic_outcome, SemanticOutcome):
            raise TypeError("semantic_outcome must be SemanticOutcome")
        if not isinstance(result, PostgresWriteSideResult):
            raise TypeError("result must be PostgresWriteSideResult")

        if result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED:
            rule_refinement = result.observed_rule_violation

            if rule_refinement is None:
                raise ValueError(
                    "VALIDATION_BLOCKED requires Order rule evidence "
                    "for semantic rule refinement"
                )
        else:
            rule_refinement = None
        instance = object.__new__(cls)
        object.__setattr__(instance, "_semantic_outcome", semantic_outcome)
        object.__setattr__(instance, "_rule_refinement", rule_refinement)
        return instance

    @property
    def semantic_outcome(self) -> SemanticOutcome:
        """Return the exact object produced by the Stage 4A mapper call."""

        return self._semantic_outcome

    @property
    def rule_refinement(self) -> OrderRuleViolationEvidence | None:
        """Return exact validation-block refinement, or None when inapplicable."""

        return self._rule_refinement


def map_postgres_write_side_result_to_semantic_rule_feedback(
    *,
    outcome_id: UUID,
    result: PostgresWriteSideResult,
) -> PostgresWriteSideSemanticRuleFeedback:
    """Compose one PostgreSQL result into semantic rule feedback.

    Args:
        outcome_id: Identity for the existing Stage 4A semantic interpretation.
        result: The single PostgreSQL write-side result source.

    Returns:
        A read-only composition retaining the exact ``SemanticOutcome`` from one
        Stage 4A mapper call. When and only when ``result.outcome`` is
        ``VALIDATION_BLOCKED``, it also retains the exact source
        ``OrderRuleViolationEvidence``. For every other terminal outcome,
        ``rule_refinement`` is ``None`` because Order-rule refinement is not
        applicable.

    Raises:
        ValueError: If a ``VALIDATION_BLOCKED`` result lacks the exact Order
            rule evidence required to complete semantic rule refinement.

    Existing Stage 4A mapping validation and failures propagate unchanged. A
    legacy evidence-less validation block remains valid input to that coarse
    mapper but cannot successfully complete this refined composition.
    Preserved validation observations on later non-validation terminal outcomes
    are deliberately not promoted into terminal semantic refinement. This
    mapper does not parse text or metadata, rerun validation, infer from
    ``SemanticOutcomeCode``, authorize retry, or deliver feedback to an Agent.
    """

    semantic_outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=outcome_id,
        result=result,
    )
    return PostgresWriteSideSemanticRuleFeedback._from_source(
        semantic_outcome=semantic_outcome,
        result=result,
    )


__all__ = (
    "PostgresWriteSideSemanticRuleFeedback",
    "map_postgres_write_side_result_to_semantic_rule_feedback",
)
