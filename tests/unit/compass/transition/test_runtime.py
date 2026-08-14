from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum

import pytest

from src.compass.transition.runtime import (
    ValidationDecisionWithRuleEvidence,
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.rule_evaluation_evidence import (
    FullProofValidationEvidence,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.correctness_contract import OrderCorrectnessRuleId
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


@dataclass
class DummyValidator:
    result: ValidationResult

    def validate(self, candidate_event, context):
        return self.result


class _ForeignEventType(Enum):
    OBSERVED = "OBSERVED"


class _RecordingFullProofValidator(FullProofValidator):
    def __init__(self) -> None:
        self.evidence_calls = 0
        self.legacy_calls = 0
        self.produced: list[FullProofValidationEvidence] = []

    def validate(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("legacy validate must not run on the evidence path")

    def validate_with_rule_evidence(
        self,
        candidate_event,
        context,
    ) -> FullProofValidationEvidence:
        self.evidence_calls += 1
        evidence = super().validate_with_rule_evidence(candidate_event, context)
        self.produced.append(evidence)
        return evidence


class _RecordingNoOpValidator(NoOpValidator):
    def __init__(self) -> None:
        self.calls = 0
        self.produced: list[ValidationResult] = []

    def validate(self, candidate_event, context) -> ValidationResult:
        self.calls += 1
        result = super().validate(candidate_event, context)
        self.produced.append(result)
        return result


class _RecordingPolicy(ValidationPolicy):
    def __init__(self) -> None:
        self.received: list[ValidationResult] = []

    def decide(self, result: ValidationResult) -> EnforcementAction:
        self.received.append(result)
        return super().decide(result)


class _RaisingPolicy(ValidationPolicy):
    def __init__(self) -> None:
        self.received: list[ValidationResult] = []

    def decide(self, result: ValidationResult) -> EnforcementAction:
        self.received.append(result)
        raise RuntimeError("policy failed")


class _RaisingFullProofValidator(FullProofValidator):
    def __init__(self) -> None:
        self.evidence_calls = 0
        self.legacy_calls = 0

    def validate(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("legacy validate must not run on the evidence path")

    def validate_with_rule_evidence(self, candidate_event, context):
        self.evidence_calls += 1
        raise RuntimeError("validator failed")


class _MisleadingFullProofValidator(_RecordingFullProofValidator):
    def validate_with_rule_evidence(
        self,
        candidate_event,
        context,
    ) -> FullProofValidationEvidence:
        evidence = super().validate_with_rule_evidence(candidate_event, context)
        evidence.validation_result.reason = (
            "metadata claims a different transition rule"
        )
        evidence.validation_result.metadata = {
            "rule_id": (
                OrderCorrectnessRuleId
                .TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS.value
            )
        }
        return evidence


def _event(
    *,
    event_id: str,
    sequence: int,
    event_type: object,
    prev_status: OrderStatus,
    prev_version: int,
    prev_event_id: str | None,
) -> OrderEvent:
    return OrderEvent(
        event_id=event_id,
        request_id=f"request-{event_id}",
        order_id="order-runtime-evidence",
        sequence=sequence,
        event_type=event_type,  # type: ignore[arg-type]
        amount=Decimal("10.00"),
        occurred_at_ms=0,
        proof=Proof(
            prev_status=prev_status,
            prev_version=prev_version,
            prev_event_id=prev_event_id,
        ),
    )


def _valid_created_candidate() -> OrderEvent:
    return _event(
        event_id="candidate-runtime",
        sequence=1,
        event_type=EventType.CREATED,
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )


def _accepted_created_event() -> OrderEvent:
    return _event(
        event_id="accepted-created",
        sequence=1,
        event_type=EventType.CREATED,
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )


def _valid_paid_candidate() -> OrderEvent:
    return _event(
        event_id="candidate-runtime-paid",
        sequence=2,
        event_type=EventType.PAID,
        prev_status=OrderStatus.CREATED,
        prev_version=1,
        prev_event_id="accepted-created",
    )


def _init_context() -> ValidationContext:
    return ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=OrderStatus.INIT,
    )


def _created_context() -> ValidationContext:
    accepted = _accepted_created_event()
    return ValidationContext(
        actual_prev_event=accepted,
        actual_prev_version=1,
        actual_prev_status=OrderStatus.CREATED,
    )


def _runtime(
    *,
    strict_validator,
    off_validator,
    policy: ValidationPolicy,
    mode: ValidationMode,
) -> ValidationRuntime:
    return ValidationRuntime(
        dispatcher=ValidationDispatcher(strict_validator, off_validator),
        policy=policy,
        mode=mode,
    )


FULL_PROOF_FAILURE_CASES = (
    pytest.param(
        replace(_valid_created_candidate(), sequence=2),
        _init_context(),
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
        id="sequence",
    ),
    pytest.param(
        replace(
            _valid_paid_candidate(),
            proof=replace(
                _valid_paid_candidate().proof,
                prev_event_id="another-accepted-event",
            ),
        ),
        _created_context(),
        (
            OrderCorrectnessRuleId
            .TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED
        ),
        id="previous-event-id",
    ),
    pytest.param(
        replace(
            _valid_paid_candidate(),
            proof=replace(_valid_paid_candidate().proof, prev_version=99),
        ),
        _created_context(),
        (
            OrderCorrectnessRuleId
            .TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED
        ),
        id="previous-version",
    ),
    pytest.param(
        replace(
            _valid_paid_candidate(),
            proof=replace(
                _valid_paid_candidate().proof,
                prev_status=OrderStatus.INIT,
            ),
        ),
        _created_context(),
        (
            OrderCorrectnessRuleId
            .TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED
        ),
        id="previous-status",
    ),
    pytest.param(
        replace(
            _valid_created_candidate(),
            event_type=_ForeignEventType.OBSERVED,  # type: ignore[arg-type]
        ),
        _init_context(),
        OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
        id="unsupported-event-type",
    ),
    pytest.param(
        _event(
            event_id="candidate-illegal-paid",
            sequence=1,
            event_type=EventType.PAID,
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
        _init_context(),
        (
            OrderCorrectnessRuleId
            .TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS
        ),
        id="illegal-event-type-from-status",
    ),
)


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


def test_evidence_carrier_rejects_direct_construction() -> None:
    with pytest.raises(TypeError, match="must be produced by ValidationRuntime"):
        ValidationDecisionWithRuleEvidence()


def test_full_proof_pass_preserves_one_invocation_and_exact_result() -> None:
    validator = _RecordingFullProofValidator()
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    carrier = runtime.decide_with_rule_evidence(
        _valid_created_candidate(),
        _init_context(),
    )
    producer_evidence = validator.produced[0]

    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == [producer_evidence.validation_result]
    assert policy.received[0] is producer_evidence.validation_result
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert (
        carrier.decision.validation_result
        is producer_evidence.validation_result
    )
    assert carrier.observed_violation is None


@pytest.mark.parametrize(
    ("candidate", "context", "expected_rule_id"),
    FULL_PROOF_FAILURE_CASES,
)
def test_each_full_proof_failure_preserves_exact_typed_violation(
    candidate: OrderEvent,
    context: ValidationContext,
    expected_rule_id: OrderCorrectnessRuleId,
) -> None:
    validator = _RecordingFullProofValidator()
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    carrier = runtime.decide_with_rule_evidence(candidate, context)
    producer_evidence = validator.produced[0]

    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert len(policy.received) == 1
    assert policy.received[0] is producer_evidence.validation_result
    assert carrier.decision.action is EnforcementAction.BLOCK
    assert (
        carrier.decision.validation_result
        is producer_evidence.validation_result
    )
    assert carrier.observed_violation is producer_evidence.observed_violation
    assert carrier.observed_violation is not None
    assert carrier.observed_violation.rule_id is expected_rule_id


def test_off_mode_preserves_skipped_result_without_rule_evidence() -> None:
    off_validator = _RecordingNoOpValidator()
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=FullProofValidator(),
        off_validator=off_validator,
        policy=policy,
        mode=ValidationMode.OFF,
    )

    carrier = runtime.decide_with_rule_evidence(
        _valid_created_candidate(),
        _init_context(),
    )

    assert off_validator.calls == 1
    assert policy.received == [off_validator.produced[0]]
    assert policy.received[0] is off_validator.produced[0]
    assert carrier.decision.validation_result is off_validator.produced[0]
    assert carrier.decision.validation_result.verdict is ValidationVerdict.SKIPPED
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert carrier.observed_violation is None


@pytest.mark.parametrize(
    ("verdict", "expected_action"),
    (
        (ValidationVerdict.PASSED, EnforcementAction.ALLOW),
        (ValidationVerdict.FAILED, EnforcementAction.BLOCK),
        (ValidationVerdict.SKIPPED, EnforcementAction.ALLOW),
    ),
)
def test_legacy_only_validator_preserves_existing_decision_without_evidence(
    verdict: ValidationVerdict,
    expected_action: EnforcementAction,
) -> None:
    validation_result = ValidationResult(
        verdict=verdict,
        reason="legacy result",
        candidate_event_id="candidate-runtime",
        validator_name="DummyValidator",
        validation_mode=ValidationMode.STRICT,
        logic_validation_time_ms=0.0,
        io_time_ms=0.0,
        total_time_ms=0.0,
        metadata={},
    )
    validator = DummyValidator(validation_result)
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    carrier = runtime.decide_with_rule_evidence(
        _valid_created_candidate(),
        _init_context(),
    )

    assert policy.received == [validation_result]
    assert policy.received[0] is validation_result
    assert carrier.decision.action is expected_action
    assert carrier.decision.validation_result is validation_result
    assert carrier.observed_violation is None


def test_validator_exception_propagates_without_legacy_fallback() -> None:
    validator = _RaisingFullProofValidator()
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    with pytest.raises(RuntimeError, match="validator failed"):
        runtime.decide_with_rule_evidence(
            _valid_created_candidate(),
            _init_context(),
        )

    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == []


def test_policy_exception_propagates_after_one_full_proof_invocation() -> None:
    validator = _RecordingFullProofValidator()
    policy = _RaisingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    with pytest.raises(RuntimeError, match="policy failed"):
        runtime.decide_with_rule_evidence(
            _valid_created_candidate(),
            _init_context(),
        )

    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == [validator.produced[0].validation_result]
    assert policy.received[0] is validator.produced[0].validation_result


@pytest.mark.parametrize(
    ("first_fails", "second_fails"),
    (
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ),
    ids=("failure-failure", "failure-success", "success-failure", "success-success"),
)
def test_evidence_is_invocation_local_across_all_two_call_sequences(
    first_fails: bool,
    second_fails: bool,
) -> None:
    validator = _RecordingFullProofValidator()
    policy = _RecordingPolicy()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=policy,
        mode=ValidationMode.STRICT,
    )
    passing_candidate = _valid_created_candidate()
    failing_candidate = replace(passing_candidate, sequence=2)

    carriers = tuple(
        runtime.decide_with_rule_evidence(
            failing_candidate if fails else passing_candidate,
            _init_context(),
        )
        for fails in (first_fails, second_fails)
    )

    assert validator.evidence_calls == 2
    assert validator.legacy_calls == 0
    assert len(policy.received) == 2
    assert tuple(
        carrier.observed_violation is not None for carrier in carriers
    ) == (first_fails, second_fails)
    for index, carrier in enumerate(carriers):
        producer_evidence = validator.produced[index]
        assert carrier.decision.validation_result is producer_evidence.validation_result
        assert carrier.observed_violation is producer_evidence.observed_violation
    if first_fails and second_fails:
        assert carriers[0].observed_violation is not carriers[1].observed_violation


def test_reason_and_metadata_cannot_select_runtime_rule_evidence() -> None:
    candidate = replace(_valid_created_candidate(), sequence=2)
    validator = _MisleadingFullProofValidator()
    runtime = _runtime(
        strict_validator=validator,
        off_validator=NoOpValidator(),
        policy=_RecordingPolicy(),
        mode=ValidationMode.STRICT,
    )

    carrier = runtime.decide_with_rule_evidence(candidate, _init_context())

    assert carrier.observed_violation is not None
    assert carrier.observed_violation.rule_id is (
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
    )
