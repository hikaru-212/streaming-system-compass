from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

import src.compass.runtime.write_side_rule_feedback as feedback_module
import src.compass.runtime.write_side_runtime_decision as evaluator_module
from src.compass.runtime.runtime_decision import RuntimeDecisionResponse
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
)
from src.compass.runtime.write_side_rule_feedback import (
    PostgresWriteSideSemanticRuleFeedback,
    map_postgres_write_side_result_to_semantic_rule_feedback,
)
from src.compass.runtime.write_side_runtime_decision import (
    PostgresWriteSideRuntimeDecisionEvaluation,
    PostgresWriteSideRuntimeDecisionRefused,
    evaluate_postgres_write_side_runtime_decision,
)
from src.compass.transition.runtime import (
    ValidationDecisionWithRuleEvidence,
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationMode,
    ValidationResult,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.aggregate import OrderAggregate
from src.core.order.correctness_contract import OrderCorrectnessRuleId
from src.core.order.enums import CommandType, OrderStatus
from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import (
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000802")


class _AlwaysAllowPolicy(ValidationPolicy):
    """Expose a non-terminal failed observation for conservative testing."""

    def decide(self, result: ValidationResult) -> EnforcementAction:
        return EnforcementAction.ALLOW


def _candidate(
    event_id: str,
    *,
    violates_sequence_rule: bool = False,
) -> OrderEvent:
    candidate = OrderAggregate("order-runtime-decision").create(
        request_id=f"request-{event_id}",
        total_amount=Decimal("100.00"),
    )
    return replace(
        candidate,
        event_id=event_id,
        sequence=2 if violates_sequence_rule else 1,
    )


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="test-owned idempotency miss",
    )


def _record(event: OrderEvent) -> IdempotencyRecord:
    return IdempotencyRecord(
        signature=RequestSignature(
            request_id=event.request_id,
            command_type=CommandType.CREATE,
            order_id=event.order_id,
            amount=event.amount,
        ),
        accepted_event=event,
    )


def _full_proof_carrier(
    event_id: str,
    *,
    allow_failure: bool,
) -> tuple[OrderEvent, ValidationDecisionWithRuleEvidence]:
    candidate = _candidate(event_id, violates_sequence_rule=True)
    runtime = ValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=FullProofValidator(),
            off_validator=NoOpValidator(),
        ),
        policy=_AlwaysAllowPolicy() if allow_failure else ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )
    carrier = runtime.decide_with_rule_evidence(
        candidate,
        ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        ),
    )
    assert carrier.observed_violation is not None
    return candidate, carrier


def _result(outcome: PostgresWriteSideOutcome) -> PostgresWriteSideResult:
    event = _candidate(f"candidate-{outcome.value.lower()}")
    if outcome is PostgresWriteSideOutcome.ACCEPTED:
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=event,
            idempotency_decision=_miss(),
        )
    if outcome is PostgresWriteSideOutcome.REPLAY:
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=event,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="test-owned idempotent replay",
                record=_record(event),
            ),
        )
    if outcome is PostgresWriteSideOutcome.CONFLICT:
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=None,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.CONFLICT,
                reason="test-owned idempotency conflict",
                record=_record(event),
            ),
        )
    raise AssertionError(f"unsupported result helper outcome: {outcome}")


def _admission_rejected_result(
    verdict: AdmissionVerdict,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=verdict,
            reason=f"test-owned {verdict.value.lower()} condition",
            order_id="order-runtime-decision",
        ),
    )


def _feedback(result: PostgresWriteSideResult):
    return map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )


@pytest.mark.parametrize(
    ("result", "expected_category", "expected_code", "expected_response"),
    [
        pytest.param(
            _result(PostgresWriteSideOutcome.ACCEPTED),
            SemanticOutcomeCategory.VALID,
            SemanticOutcomeCode.SEMANTICALLY_VALID,
            RuntimeDecisionResponse.USE_CURRENT_RESULT,
            id="use-current-result",
        ),
        pytest.param(
            _result(PostgresWriteSideOutcome.REPLAY),
            SemanticOutcomeCategory.RETRY_CLASSIFIED,
            SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED,
            RuntimeDecisionResponse.RETURN_PRIOR_ACCEPTED_RESULT,
            id="return-prior-accepted-result",
        ),
        pytest.param(
            _result(PostgresWriteSideOutcome.CONFLICT),
            SemanticOutcomeCategory.BLOCK_REQUIRED,
            SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED,
            RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION,
            id="block-current-continuation",
        ),
        pytest.param(
            _admission_rejected_result(AdmissionVerdict.INFRASTRUCTURE_ERROR),
            SemanticOutcomeCategory.ESCALATION_REQUIRED,
            SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW,
            RuntimeDecisionResponse.REQUIRE_ESCALATION,
            id="require-escalation",
        ),
    ],
)
def test_evaluator_maps_exact_four_reviewed_semantic_tuples(
    result: PostgresWriteSideResult,
    expected_category: SemanticOutcomeCategory,
    expected_code: SemanticOutcomeCode,
    expected_response: RuntimeDecisionResponse,
) -> None:
    feedback = _feedback(result)

    evaluation = evaluate_postgres_write_side_runtime_decision(feedback)

    assert feedback.semantic_outcome.boundary is (
        SemanticBoundary.LAYER_1_WRITE_SIDE
    )
    assert feedback.semantic_outcome.category is expected_category
    assert feedback.semantic_outcome.semantic_code is expected_code
    assert evaluation.decision.response is expected_response
    assert evaluation.source_feedback is feedback
    assert evaluation.decision.semantic_outcome is feedback.semantic_outcome


def test_supported_explanations_preserve_current_response_boundaries() -> None:
    current = evaluate_postgres_write_side_runtime_decision(
        _feedback(_result(PostgresWriteSideOutcome.ACCEPTED))
    ).decision
    replay = evaluate_postgres_write_side_runtime_decision(
        _feedback(_result(PostgresWriteSideOutcome.REPLAY))
    ).decision
    block = evaluate_postgres_write_side_runtime_decision(
        _feedback(_result(PostgresWriteSideOutcome.CONFLICT))
    ).decision
    escalation = evaluate_postgres_write_side_runtime_decision(
        _feedback(
            _admission_rejected_result(AdmissionVerdict.INFRASTRUCTURE_ERROR)
        )
    ).decision

    assert "already-completed current result" in current.explanation
    assert "does not authorize candidate append admission" in current.explanation
    assert "prior accepted result" in replay.explanation
    assert "does not authorize another attempt or retry" in replay.explanation
    assert "Current downstream continuation is blocked" in block.explanation
    assert "authorizes no repair" in block.explanation
    assert "requires escalation" in escalation.explanation
    assert "does not execute an operator workflow" in escalation.explanation


def test_concurrency_uncertain_is_typed_refusal_not_positive_block() -> None:
    feedback = _feedback(
        _admission_rejected_result(AdmissionVerdict.LOCK_TIMEOUT)
    )

    with pytest.raises(PostgresWriteSideRuntimeDecisionRefused) as caught:
        evaluate_postgres_write_side_runtime_decision(feedback)

    assert feedback.semantic_outcome.category is (
        SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    )
    assert "no authoritative RuntimeDecision" in str(caught.value)
    assert "REFUSAL" not in {response.value for response in RuntimeDecisionResponse}


@pytest.mark.parametrize(
    ("boundary", "category", "semantic_code"),
    [
        pytest.param(
            SemanticBoundary.LAYER_2_READ_SIDE,
            SemanticOutcomeCategory.VALID,
            SemanticOutcomeCode.SEMANTICALLY_VALID,
            id="unsupported-boundary",
        ),
        pytest.param(
            SemanticBoundary.LAYER_1_WRITE_SIDE,
            SemanticOutcomeCategory.VALID,
            SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW,
            id="unsupported-category-code-combination",
        ),
        pytest.param(
            SemanticBoundary.LAYER_1_WRITE_SIDE,
            SemanticOutcomeCategory.FALLBACK_REQUIRED,
            SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            id="coherent-tuple-outside-first-profile",
        ),
    ],
)
def test_evaluator_refuses_every_tuple_outside_first_profile(
    monkeypatch: pytest.MonkeyPatch,
    boundary: SemanticBoundary,
    category: SemanticOutcomeCategory,
    semantic_code: SemanticOutcomeCode,
) -> None:
    result = _result(PostgresWriteSideOutcome.ACCEPTED)
    source_outcome = feedback_module.map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )
    unsupported_outcome = replace(
        source_outcome,
        boundary=boundary,
        category=category,
        semantic_code=semantic_code,
    )
    monkeypatch.setattr(
        feedback_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        lambda **_: unsupported_outcome,
    )
    feedback = _feedback(result)

    with pytest.raises(PostgresWriteSideRuntimeDecisionRefused):
        evaluate_postgres_write_side_runtime_decision(feedback)


def test_evaluator_rejects_wrong_input_type() -> None:
    with pytest.raises(
        TypeError,
        match="feedback must be PostgresWriteSideSemanticRuleFeedback",
    ):
        evaluate_postgres_write_side_runtime_decision(
            object(),  # type: ignore[arg-type]
        )


def test_profile_delivery_rejects_direct_construction_and_is_read_only() -> None:
    with pytest.raises(TypeError, match="must be produced by"):
        PostgresWriteSideRuntimeDecisionEvaluation()

    evaluation = evaluate_postgres_write_side_runtime_decision(
        _feedback(_result(PostgresWriteSideOutcome.ACCEPTED))
    )
    with pytest.raises(AttributeError, match="read-only"):
        evaluation.source_feedback = object()  # type: ignore[misc]


def test_profile_delivery_rejects_a_different_source_outcome() -> None:
    source_feedback = _feedback(_result(PostgresWriteSideOutcome.ACCEPTED))
    other_feedback = _feedback(_result(PostgresWriteSideOutcome.REPLAY))
    decision = evaluate_postgres_write_side_runtime_decision(
        source_feedback
    ).decision

    assert decision.semantic_outcome is source_feedback.semantic_outcome
    assert decision.semantic_outcome is not other_feedback.semantic_outcome

    with pytest.raises(
        ValueError,
        match="decision must retain the exact source SemanticOutcome",
    ):
        PostgresWriteSideRuntimeDecisionEvaluation._from_evaluation(
            decision=decision,
            source_feedback=other_feedback,
        )


def test_terminal_full_proof_refinement_remains_exact_and_in_block_family() -> None:
    _, carrier = _full_proof_carrier(
        "candidate-terminal-rule",
        allow_failure=False,
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )
    feedback = _feedback(result)

    evaluation = evaluate_postgres_write_side_runtime_decision(feedback)

    assert feedback.rule_refinement is carrier.observed_violation
    assert evaluation.source_feedback.rule_refinement is carrier.observed_violation
    assert evaluation.decision.response is (
        RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION
    )
    assert carrier.observed_violation is not None
    assert carrier.observed_violation.rule_id is (
        OrderCorrectnessRuleId
        .TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
    )
    assert carrier.observed_violation.rule_id.value in (
        evaluation.decision.explanation
    )


def test_text_and_generic_mappings_do_not_fabricate_rule_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _result(PostgresWriteSideOutcome.CONFLICT)
    source_outcome = feedback_module.map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )
    misleading_rule = (
        OrderCorrectnessRuleId
        .TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS.value
    )
    misleading_outcome = replace(
        source_outcome,
        reason=f"pretend terminal rule {misleading_rule}",
        context={"order_rule_id": misleading_rule},
        evidence={"rule_id": misleading_rule},
    )
    monkeypatch.setattr(
        feedback_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        lambda **_: misleading_outcome,
    )
    feedback = _feedback(result)

    evaluation = evaluate_postgres_write_side_runtime_decision(feedback)

    assert feedback.rule_refinement is None
    assert evaluation.decision.response is (
        RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION
    )
    assert misleading_rule not in evaluation.decision.explanation


def test_non_terminal_validation_observation_is_not_promoted() -> None:
    event, carrier = _full_proof_carrier(
        "candidate-earlier-observation",
        allow_failure=True,
    )
    assert carrier.observed_violation is not None
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )
    feedback = _feedback(result)

    evaluation = evaluate_postgres_write_side_runtime_decision(feedback)

    assert feedback.rule_refinement is None
    assert evaluation.decision.response is (
        RuntimeDecisionResponse.USE_CURRENT_RESULT
    )


def test_incoherent_refinement_cannot_escape_block_response_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, carrier = _full_proof_carrier(
        "candidate-incoherent-refinement",
        allow_failure=False,
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )
    source_outcome = feedback_module.map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )
    incoherent_outcome = replace(
        source_outcome,
        ok=True,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
    )
    monkeypatch.setattr(
        feedback_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        lambda **_: incoherent_outcome,
    )
    feedback = _feedback(result)
    assert feedback.rule_refinement is carrier.observed_violation

    with pytest.raises(
        PostgresWriteSideRuntimeDecisionRefused,
        match="only coherent with the reviewed block",
    ):
        evaluate_postgres_write_side_runtime_decision(feedback)


def test_evaluator_has_no_writer_validation_policy_or_execution_dependencies() -> None:
    forbidden_symbols = {
        "PostgresTransactionalWriteSide",
        "ValidationDecision",
        "ValidationPolicy",
        "EnforcementAction",
        "RetryAuthorization",
        "DecisionReceipt",
    }
    assert forbidden_symbols.isdisjoint(evaluator_module.__dict__)
    assert "OrderRuleViolationEvidence" not in evaluator_module.__dict__
    assert "PostgresWriteSideResult" not in evaluator_module.__dict__
