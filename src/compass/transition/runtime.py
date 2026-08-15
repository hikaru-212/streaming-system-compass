from src.core.order.events import OrderEvent
from src.core.order.rule_violation_evidence import OrderRuleViolationEvidence

from .rule_evaluation_evidence import FullProofValidationEvidence
from .types import (
    TransitionValidator,
    ValidationDecision,
    ValidationMode,
    ValidationVerdict,
    ValidationResult,
    ValidationContext,
    EnforcementAction,
)
from .validators import FullProofValidator


class ValidationDecisionWithRuleEvidence:
    """Carry one runtime decision with optional observed rule evidence.

    Instances are produced only by ``ValidationRuntime`` construction paths.
    FullProof construction consumes one producer bundle and retains its exact
    ``ValidationResult`` and optional ``OrderRuleViolationEvidence`` objects.
    Other validators produce the existing policy decision with no rule evidence.

    This carrier preserves a supported in-process object relationship. It is not
    an authenticity, persistence, serialization, admission, retry, or
    cross-process provenance mechanism, and its optional violation is not a
    complete violation set.
    """

    __slots__ = ("_decision", "_observed_violation")

    def __init__(self) -> None:
        """Reject direct construction outside the runtime-owned factories."""

        raise TypeError(
            "ValidationDecisionWithRuleEvidence must be produced by "
            "ValidationRuntime"
        )

    def __setattr__(self, name: str, value: object) -> None:
        """Keep the carrier's own references immutable after construction."""

        raise AttributeError(
            "ValidationDecisionWithRuleEvidence attributes are read-only"
        )

    @classmethod
    def _from_full_proof(
        cls,
        *,
        action: EnforcementAction,
        evidence: FullProofValidationEvidence,
    ) -> "ValidationDecisionWithRuleEvidence":
        """Construct from one coherent FullProof producer invocation."""

        if not isinstance(evidence, FullProofValidationEvidence):
            raise TypeError("evidence must be FullProofValidationEvidence")

        decision = ValidationDecision(
            action=action,
            validation_result=evidence.validation_result,
        )
        return cls._build(
            decision=decision,
            observed_violation=evidence.observed_violation,
        )

    @classmethod
    def _without_rule_evidence(
        cls,
        *,
        action: EnforcementAction,
        validation_result: ValidationResult,
    ) -> "ValidationDecisionWithRuleEvidence":
        """Construct the compatibility path for a non-FullProof validator."""

        if not isinstance(validation_result, ValidationResult):
            raise TypeError("validation_result must be ValidationResult")

        decision = ValidationDecision(
            action=action,
            validation_result=validation_result,
        )
        return cls._build(decision=decision, observed_violation=None)

    @classmethod
    def _build(
        cls,
        *,
        decision: ValidationDecision,
        observed_violation: OrderRuleViolationEvidence | None,
    ) -> "ValidationDecisionWithRuleEvidence":
        """Assign already-coherent runtime-owned references without copying."""

        instance = object.__new__(cls)
        object.__setattr__(instance, "_decision", decision)
        object.__setattr__(instance, "_observed_violation", observed_violation)
        return instance

    @property
    def decision(self) -> ValidationDecision:
        """Return the existing policy-owned decision object."""

        return self._decision

    @property
    def observed_violation(self) -> OrderRuleViolationEvidence | None:
        """Return the exact producer violation, or ``None`` when unavailable."""

        return self._observed_violation



class ValidationDispatcher:
    """
    Selects which validator path should handle the candidate event.

    Current minimal rule set:
    - STRICT -> full proof validator
    - OFF -> no-op validator
    """

    def __init__(self, strict_validator: TransitionValidator, off_validator: TransitionValidator):
        self.strict_validator = strict_validator
        self.off_validator = off_validator

    def select(self, candidate_event: OrderEvent, mode: ValidationMode) -> TransitionValidator:
        if mode == ValidationMode.OFF:
            return self.off_validator
        return self.strict_validator
    

class ValidationPolicy:
    """
     Maps semantic truth outcome into runtime action.

     Important separation:
     - validator decides truth
     - policy decides response
    """

    def decide(self, result: ValidationResult) -> EnforcementAction:
        if result.verdict == ValidationVerdict.FAILED:
            return EnforcementAction.BLOCK
        return EnforcementAction.ALLOW
    

class ValidationRuntime:
    """
    Orchestrates validator selection and policy decision.

    Boundary:
    - Validator decides semantic truth.
    - Policy maps semantic truth into runtime action.
    - Runtime returns the final ValidationDecision consumed by Registry.
    """

    def __init__(
        self,
        dispatcher: ValidationDispatcher,
        policy: ValidationPolicy,
        mode: ValidationMode = ValidationMode.STRICT,
    ):
        self.dispatcher = dispatcher
        self.policy = policy
        self.mode = mode

    def decide(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> ValidationDecision:
        validator = self.dispatcher.select(candidate_event, self.mode)
        validation_result = validator.validate(candidate_event, context)
        action = self.policy.decide(validation_result)

        return ValidationDecision(
            action=action,
            validation_result=validation_result,
        )

    def decide_with_rule_evidence(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> ValidationDecisionWithRuleEvidence:
        """Decide once while preserving source-legitimate rule evidence.

        Args:
            candidate_event: Candidate evaluated against accepted-history facts.
            context: Accepted-history-derived validation context.

        Returns:
            The existing policy decision paired with the exact observed FullProof
            violation when the selected producer supports the accepted PR4
            boundary. NoOp and other legacy validators carry no rule evidence.

        The selected validator and policy are each invoked exactly once. This
        method does not parse textual fields, rerun validation, infer evidence,
        authorize retry, or change the legacy ``decide`` path.
        """

        validator = self.dispatcher.select(candidate_event, self.mode)
        if isinstance(validator, FullProofValidator):
            full_proof_evidence = validator.validate_with_rule_evidence(
                candidate_event,
                context,
            )
            action = self.policy.decide(full_proof_evidence.validation_result)
            return ValidationDecisionWithRuleEvidence._from_full_proof(
                action=action,
                evidence=full_proof_evidence,
            )

        validation_result = validator.validate(candidate_event, context)
        action = self.policy.decide(validation_result)
        return ValidationDecisionWithRuleEvidence._without_rule_evidence(
            action=action,
            validation_result=validation_result,
        )
