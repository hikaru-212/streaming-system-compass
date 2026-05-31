from src.core.order.events import OrderEvent

from .types import (
    TransitionValidator,
    ValidationDecision,
    ValidationMode,
    ValidationVerdict,
    ValidationResult,
    ValidationContext,
    EnforcementAction,
)



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