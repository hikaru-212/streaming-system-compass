from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

import src.compass.runtime.write_side_rule_feedback as feedback_module
from src.compass.runtime.semantic_outcome import (
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
)
from src.compass.runtime.write_side_outcome_mapping import (
    map_postgres_write_side_result_to_semantic_outcome,
)
from src.compass.runtime.write_side_rule_feedback import (
    PostgresWriteSideSemanticRuleFeedback,
    map_postgres_write_side_result_to_semantic_rule_feedback,
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
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
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


OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000701")


class _AlwaysAllowPolicy(ValidationPolicy):
    """Allow a failed FullProof result only for synthetic mapper robustness."""

    def decide(self, result: ValidationResult) -> EnforcementAction:
        return EnforcementAction.ALLOW


def _candidate(
    event_id: str,
    *,
    violates_sequence_rule: bool,
) -> OrderEvent:
    candidate = OrderAggregate("order-rule-feedback").create(
        request_id=f"request-{event_id}",
        total_amount=Decimal("100.00"),
    )
    return replace(
        candidate,
        event_id=event_id,
        sequence=2 if violates_sequence_rule else 1,
    )


def _context() -> ValidationContext:
    return ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=OrderStatus.INIT,
    )


def _full_proof_rule_carrier(
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
    carrier = runtime.decide_with_rule_evidence(candidate, _context())
    assert carrier.observed_violation is not None
    return candidate, carrier


def _off_carrier(
    event_id: str,
) -> tuple[OrderEvent, ValidationDecisionWithRuleEvidence]:
    candidate = _candidate(event_id, violates_sequence_rule=False)
    runtime = ValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=FullProofValidator(),
            off_validator=NoOpValidator(),
        ),
        policy=ValidationPolicy(),
        mode=ValidationMode.OFF,
    )
    return candidate, runtime.decide_with_rule_evidence(candidate, _context())


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


def _non_validation_result(
    outcome: PostgresWriteSideOutcome,
    *,
    event: OrderEvent,
    carrier: ValidationDecisionWithRuleEvidence | None,
) -> PostgresWriteSideResult:
    validation_decision = None if carrier is None else carrier.decision

    if outcome is PostgresWriteSideOutcome.ACCEPTED:
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=event,
            idempotency_decision=_miss(),
            validation_decision=validation_decision,
            validation_decision_evidence=carrier,
        )

    if outcome is PostgresWriteSideOutcome.REPLAY:
        record = _record(event)
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=event,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="test-owned idempotent replay",
                record=record,
            ),
            validation_decision=validation_decision,
            validation_decision_evidence=carrier,
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
            validation_decision=validation_decision,
            validation_decision_evidence=carrier,
        )

    if outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED:
        return PostgresWriteSideResult(
            outcome=outcome,
            accepted_event=None,
            idempotency_decision=_miss(),
            stream_admission_result=StreamAdmissionResult(
                verdict=AdmissionVerdict.LOCK_TIMEOUT,
                reason="test-owned admission rejection",
                order_id=event.order_id,
            ),
            validation_decision=validation_decision,
            validation_decision_evidence=carrier,
        )

    raise AssertionError(f"unsupported non-validation outcome: {outcome}")


NON_VALIDATION_OUTCOMES = (
    pytest.param(
        PostgresWriteSideOutcome.ACCEPTED,
        "WRITE_SIDE_ACCEPTED",
        id="accepted",
    ),
    pytest.param(
        PostgresWriteSideOutcome.REPLAY,
        "IDEMPOTENT_REPLAY",
        id="replay",
    ),
    pytest.param(
        PostgresWriteSideOutcome.CONFLICT,
        "IDEMPOTENCY_CONFLICT",
        id="conflict",
    ),
    pytest.param(
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        "LOCK_TIMEOUT",
        id="admission-rejected",
    ),
)


def test_validation_blocked_preserves_exact_terminal_rule_refinement() -> None:
    _, carrier = _full_proof_rule_carrier(
        "candidate-validation-blocked",
        allow_failure=False,
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert feedback.semantic_outcome.category is (
        SemanticOutcomeCategory.BLOCK_REQUIRED
    )
    assert feedback.semantic_outcome.semantic_code is (
        SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
    )
    assert feedback.semantic_outcome.evidence["technical_status"] == (
        "COMPASS_VALIDATION_BLOCKED"
    )
    assert feedback.rule_refinement is result.observed_rule_violation
    assert feedback.rule_refinement is carrier.observed_violation
    assert feedback.rule_refinement is not None
    assert feedback.rule_refinement.rule_id is (
        OrderCorrectnessRuleId
        .TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
    )


def test_evidenceless_validation_block_keeps_stage4a_but_rejects_pr7() -> None:
    decision = ValidationDecision(
        action=EnforcementAction.BLOCK,
        validation_result=ValidationResult(
            verdict=ValidationVerdict.FAILED,
            reason="legacy validator blocked candidate",
            candidate_event_id="candidate-legacy-blocked",
            validator_name="LegacyValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
            metadata={},
        ),
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=decision,
    )

    semantic_outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert semantic_outcome.category is (
        SemanticOutcomeCategory.BLOCK_REQUIRED
    )
    assert semantic_outcome.evidence["technical_status"] == (
        "COMPASS_VALIDATION_BLOCKED"
    )

    with pytest.raises(
        ValueError,
        match=(
            "VALIDATION_BLOCKED requires Order rule evidence for semantic rule "
            "refinement"
        ),
    ):
        map_postgres_write_side_result_to_semantic_rule_feedback(
            outcome_id=OUTCOME_ID,
            result=result,
        )


@pytest.mark.parametrize(("outcome", "technical_status"), NON_VALIDATION_OUTCOMES)
def test_non_validation_terminal_without_observation_remains_unrefined(
    outcome: PostgresWriteSideOutcome,
    technical_status: str,
) -> None:
    event = _candidate(
        f"candidate-no-observation-{outcome.value}",
        violates_sequence_rule=False,
    )
    result = _non_validation_result(outcome, event=event, carrier=None)
    expected = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert feedback.semantic_outcome == expected
    assert feedback.semantic_outcome.evidence["technical_status"] == (
        technical_status
    )
    if outcome is PostgresWriteSideOutcome.CONFLICT:
        assert feedback.semantic_outcome.semantic_code is (
            SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
        )
    assert feedback.rule_refinement is None


@pytest.mark.parametrize(("outcome", "technical_status"), NON_VALIDATION_OUTCOMES)
def test_synthetic_non_validation_terminal_suppresses_preserved_observation(
    outcome: PostgresWriteSideOutcome,
    technical_status: str,
) -> None:
    """Exercise a structurally valid state unreachable under current policy.

    Current FullProof plus ValidationPolicy maps a typed violation to BLOCK and
    therefore terminates as VALIDATION_BLOCKED. A custom allowing policy makes
    this non-validation terminal plus violation structurally constructible for
    conservative mapper robustness only; it is not normal production topology.
    """

    event, carrier = _full_proof_rule_carrier(
        f"candidate-synthetic-{outcome.value}",
        allow_failure=True,
    )
    result = _non_validation_result(outcome, event=event, carrier=carrier)
    assert result.observed_rule_violation is carrier.observed_violation
    assert result.observed_rule_violation is not None

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert feedback.semantic_outcome.evidence["technical_status"] == (
        technical_status
    )
    if outcome is PostgresWriteSideOutcome.CONFLICT:
        assert feedback.semantic_outcome.semantic_code is (
            SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED
        )
    assert feedback.rule_refinement is None


def test_off_skipped_accepted_result_has_no_rule_refinement() -> None:
    event, carrier = _off_carrier("candidate-off")
    result = _non_validation_result(
        PostgresWriteSideOutcome.ACCEPTED,
        event=event,
        carrier=carrier,
    )

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert carrier.decision.validation_result.verdict is ValidationVerdict.SKIPPED
    assert feedback.semantic_outcome.ok is True
    assert feedback.rule_refinement is None


def test_feedback_rejects_direct_construction_and_is_read_only() -> None:
    with pytest.raises(TypeError, match="must be produced"):
        PostgresWriteSideSemanticRuleFeedback()

    _, carrier = _full_proof_rule_carrier(
        "candidate-read-only",
        allow_failure=False,
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )
    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    with pytest.raises(AttributeError, match="read-only"):
        feedback.rule_refinement = None  # type: ignore[misc]


def test_mapper_calls_stage4a_once_and_retains_exact_semantic_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, carrier = _full_proof_rule_carrier(
        "candidate-stage4a-identity",
        allow_failure=False,
    )
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )
    semantic_outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )
    calls: list[tuple[UUID, PostgresWriteSideResult]] = []

    def map_once(
        *,
        outcome_id: UUID,
        result: PostgresWriteSideResult,
    ) -> SemanticOutcome:
        calls.append((outcome_id, result))
        return semantic_outcome

    monkeypatch.setattr(
        feedback_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        map_once,
    )

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert len(calls) == 1
    assert calls[0][0] is OUTCOME_ID
    assert calls[0][1] is result
    assert feedback.semantic_outcome is semantic_outcome
    assert feedback.rule_refinement is result.observed_rule_violation


def test_stage4a_mapper_exception_propagates_without_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _candidate(
        "candidate-stage4a-failure",
        violates_sequence_rule=False,
    )
    result = _non_validation_result(
        PostgresWriteSideOutcome.ACCEPTED,
        event=event,
        carrier=None,
    )
    failure = RuntimeError("Stage 4A mapper failed")
    calls = 0

    def raise_failure(*, outcome_id: UUID, result: PostgresWriteSideResult):
        nonlocal calls
        calls += 1
        raise failure

    monkeypatch.setattr(
        feedback_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        raise_failure,
    )

    with pytest.raises(RuntimeError, match="Stage 4A mapper failed") as caught:
        map_postgres_write_side_result_to_semantic_rule_feedback(
            outcome_id=OUTCOME_ID,
            result=result,
        )

    assert calls == 1
    assert caught.value is failure


def test_reason_and_metadata_cannot_change_terminal_rule_refinement() -> None:
    _, carrier = _full_proof_rule_carrier(
        "candidate-misleading-text",
        allow_failure=False,
    )
    carrier.decision.validation_result.reason = (
        "metadata claims an unrelated terminal and rule"
    )
    carrier.decision.validation_result.metadata = {
        "write_side_outcome": PostgresWriteSideOutcome.CONFLICT.value,
        "rule_id": (
            OrderCorrectnessRuleId
            .TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS.value
        ),
    }
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )

    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert feedback.rule_refinement is result.observed_rule_violation
    assert feedback.rule_refinement is not None
    assert feedback.rule_refinement.rule_id is (
        OrderCorrectnessRuleId
        .TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
    )
