from dataclasses import dataclass

from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import OrderStatus


@dataclass
class DummyValidator:
    result: ValidationResult

    def validate(self, candidate_event, context):
        return self.result


class TestValidationDispatcher:
    def test_select_returns_off_validator_when_mode_is_off(self):
        strict_validator = object()
        off_validator = object()
        dispatcher = ValidationDispatcher(strict_validator, off_validator)

        selected = dispatcher.select(candidate_event=None, mode=ValidationMode.OFF)

        assert selected is off_validator

    def test_select_returns_strict_validator_when_mode_is_strict(self):
        strict_validator = object()
        off_validator = object()
        dispatcher = ValidationDispatcher(strict_validator, off_validator)

        selected = dispatcher.select(candidate_event=None, mode=ValidationMode.STRICT)

        assert selected is strict_validator


class TestValidationPolicy:
    def test_decide_failed_maps_to_block(self):
        policy = ValidationPolicy()
        result = ValidationResult(
            verdict=ValidationVerdict.FAILED,
            reason="bad",
            candidate_event_id="e1",
            validator_name="Dummy",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        )

        action = policy.decide(result)

        assert action == EnforcementAction.BLOCK

    def test_decide_passed_maps_to_allow(self):
        policy = ValidationPolicy()
        result = ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="ok",
            candidate_event_id="e1",
            validator_name="Dummy",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        )

        action = policy.decide(result)

        assert action == EnforcementAction.ALLOW

    def test_decide_skipped_maps_to_allow(self):
        policy = ValidationPolicy()
        result = ValidationResult(
            verdict=ValidationVerdict.SKIPPED,
            reason="skip",
            candidate_event_id="e1",
            validator_name="Dummy",
            validation_mode=ValidationMode.OFF,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
            metadata={},
        )

        action = policy.decide(result)

        assert action == EnforcementAction.ALLOW


class TestValidationRuntime:
    def test_decide_returns_validation_decision_for_passed_result(self, created_event):
        validation_result = ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="ok",
            candidate_event_id=created_event.event_id,
            validator_name="DummyValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        )
        strict_validator = DummyValidator(validation_result)
        off_validator = DummyValidator(validation_result)

        dispatcher = ValidationDispatcher(strict_validator, off_validator)
        policy = ValidationPolicy()
        runtime = ValidationRuntime(
            dispatcher=dispatcher,
            policy=policy,
            mode=ValidationMode.STRICT,
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        decision = runtime.decide(created_event, context)

        assert isinstance(decision, ValidationDecision)
        assert decision.action == EnforcementAction.ALLOW
        assert decision.validation_result == validation_result

    def test_decide_returns_block_when_validator_fails(self, created_event):
        validation_result = ValidationResult(
            verdict=ValidationVerdict.FAILED,
            reason="bad",
            candidate_event_id=created_event.event_id,
            validator_name="DummyValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata={},
        )
        strict_validator = DummyValidator(validation_result)
        off_validator = DummyValidator(validation_result)

        dispatcher = ValidationDispatcher(strict_validator, off_validator)
        policy = ValidationPolicy()
        runtime = ValidationRuntime(
            dispatcher=dispatcher,
            policy=policy,
            mode=ValidationMode.STRICT,
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        decision = runtime.decide(created_event, context)

        assert decision.action == EnforcementAction.BLOCK
        assert decision.validation_result.reason == "bad"