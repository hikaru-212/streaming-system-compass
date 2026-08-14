"""Producer-specific rule evidence for ``FullProofValidator`` results.

This Compass-layer record pairs the existing primary ``ValidationResult`` with
bounded sibling evidence naming one observed stable Order rule violation. It
does not rank violations, collect all failures, select runtime action, or
authorize retry or repair.
"""

from dataclasses import dataclass

from src.core.order.correctness_contract import OrderCorrectnessRuleId
from src.core.order.rule_violation_evidence import OrderRuleViolationEvidence

from .types import ValidationResult, ValidationVerdict


FULL_PROOF_SUPPORTED_RULE_IDS: frozenset[OrderCorrectnessRuleId] = frozenset(
    (
        (
            OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED
        ),
        OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
        (
            OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS
        ),
    )
)


@dataclass(frozen=True)
class FullProofValidationEvidence:
    """Pair one FullProof validation result with optional sibling rule evidence.

    Args:
        validation_result: Existing primary FullProof semantic result.
        observed_violation: One stable violation observed before the validator
            terminated, or ``None`` when validation passed.

    Structural coherence is producer-specific: PASSED has no violation, FAILED
    has exactly one violation from the six explicitly supported rule IDs, and
    both records identify the same candidate. The observed violation is not a
    complete set, priority ranking, policy decision, or repair instruction.

    Raises:
        TypeError: If either field has the wrong record type.
        ValueError: If verdict, evidence presence, supported rule identity, or
            candidate correlation is incoherent.
    """

    validation_result: ValidationResult
    observed_violation: OrderRuleViolationEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.validation_result, ValidationResult):
            raise TypeError("validation_result must be ValidationResult")
        if self.observed_violation is not None and not isinstance(
            self.observed_violation,
            OrderRuleViolationEvidence,
        ):
            raise TypeError(
                "observed_violation must be OrderRuleViolationEvidence or None"
            )

        _require_non_empty_string(
            self.validation_result.candidate_event_id,
            "validation_result.candidate_event_id",
        )

        if self.validation_result.verdict is ValidationVerdict.PASSED:
            if self.observed_violation is not None:
                raise ValueError(
                    "PASSED validation must not include observed_violation"
                )
            return

        if self.validation_result.verdict is not ValidationVerdict.FAILED:
            raise ValueError(
                "FullProofValidationEvidence supports only PASSED or FAILED"
            )
        if self.observed_violation is None:
            raise ValueError(
                "FAILED validation must include observed_violation"
            )
        if (
            self.observed_violation.rule_id
            not in FULL_PROOF_SUPPORTED_RULE_IDS
        ):
            raise ValueError(
                "observed_violation rule_id is not supported by "
                "FullProofValidator evidence"
            )
        if (
            self.observed_violation.candidate_event_id
            != self.validation_result.candidate_event_id
        ):
            raise ValueError(
                "observed_violation and validation_result must identify the "
                "same candidate event"
            )


def _require_non_empty_string(value: object, field_name: str) -> None:
    """Reject non-string and whitespace-only identity values."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


__all__ = (
    "FULL_PROOF_SUPPORTED_RULE_IDS",
    "FullProofValidationEvidence",
)
