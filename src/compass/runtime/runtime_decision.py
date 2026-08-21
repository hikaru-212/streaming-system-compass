"""Generic authority for responding to one completed semantic outcome."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.compass.runtime.semantic_outcome import SemanticOutcome


class RuntimeDecisionResponse(str, Enum):
    """Closed generic vocabulary for the current runtime response."""

    USE_CURRENT_RESULT = "USE_CURRENT_RESULT"
    RETURN_PRIOR_ACCEPTED_RESULT = "RETURN_PRIOR_ACCEPTED_RESULT"
    BLOCK_CURRENT_CONTINUATION = "BLOCK_CURRENT_CONTINUATION"
    REQUIRE_ESCALATION = "REQUIRE_ESCALATION"


@dataclass(frozen=True, init=False)
class RuntimeDecision:
    """Represent reviewed authority for the current completed outcome.

    Args:
        response: Generic current-response meaning selected by an evaluator.
        semantic_outcome: Exact semantic observation consumed by the evaluator.
        explanation: Non-empty human-readable review context. The explanation
            is not authoritative and must never be parsed to recover policy.

    Instances are produced through evaluator-controlled construction. This
    limits accidental free construction in normal use; it is not a Python
    object-security or authenticity boundary.

    The contract neither selects a strategy nor authorizes another attempt or
    executes the response. It has no Order/PostgreSQL fields, decision or policy
    identity, persistence responsibility, or generic evidence/metadata bag.
    """

    response: RuntimeDecisionResponse
    semantic_outcome: SemanticOutcome
    explanation: str

    def __init__(self) -> None:
        """Reject direct construction outside a reviewed evaluator."""

        raise TypeError(
            "RuntimeDecision must be produced by a reviewed runtime evaluator"
        )

    @classmethod
    def _from_evaluation(
        cls,
        *,
        response: RuntimeDecisionResponse,
        semantic_outcome: SemanticOutcome,
        explanation: str,
    ) -> "RuntimeDecision":
        """Construct validated authority from one evaluator invocation."""

        if not isinstance(response, RuntimeDecisionResponse):
            raise TypeError("response must be RuntimeDecisionResponse")
        if not isinstance(semantic_outcome, SemanticOutcome):
            raise TypeError("semantic_outcome must be SemanticOutcome")
        if not isinstance(explanation, str):
            raise TypeError("explanation must be str")
        if not explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        instance = object.__new__(cls)
        object.__setattr__(instance, "response", response)
        object.__setattr__(instance, "semantic_outcome", semantic_outcome)
        object.__setattr__(instance, "explanation", explanation)
        return instance


__all__ = ("RuntimeDecision", "RuntimeDecisionResponse")
