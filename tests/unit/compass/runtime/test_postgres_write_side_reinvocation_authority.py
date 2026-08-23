from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from inspect import signature as inspect_signature
from uuid import UUID

import pytest

import src.compass.runtime.postgres_write_side_reinvocation_authority as evaluator_module
from src.compass.runtime.postgres_write_side_reinvocation_authority import (
    evaluate_postgres_write_side_reinvocation_authority,
)
from src.compass.runtime.reinvocation_authority import (
    NoReinvocationAuthority,
    ReinvocationAuthorization,
)
from src.compass.runtime.write_side_rule_feedback import (
    map_postgres_write_side_result_to_semantic_rule_feedback,
)
from src.compass.runtime.write_side_runtime_decision import (
    PostgresWriteSideRuntimeDecisionRefused,
    evaluate_postgres_write_side_runtime_decision,
)
from src.compass.transition.runtime import ValidationDecisionWithRuleEvidence
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import (
    AdmissionResult,
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


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="stage4e-request-001",
        command_type=CommandType.CREATE,
        order_id="stage4e-order-001",
        amount=Decimal("100.00"),
    )


def _event(signature: RequestSignature):
    return OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )


def _miss(*, reason: str = "No prior request with this request_id"):
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason=reason,
        record=None,
    )


def _record(signature: RequestSignature) -> IdempotencyRecord:
    return IdempotencyRecord(
        signature=signature,
        accepted_event=_event(signature),
    )


def _validation_decision() -> ValidationDecision:
    return ValidationDecision(
        action=EnforcementAction.ALLOW,
        validation_result=ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="test-owned validation reached",
            candidate_event_id="stage4e-candidate-001",
            validator_name="test-validator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
        ),
    )


def _positive_result(
    request_signature: RequestSignature,
    *,
    idempotency_reason: str = "No prior request with this request_id",
    admission_reason: str = "Stream lock was not available",
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(reason=idempotency_reason),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason=admission_reason,
            order_id=request_signature.order_id,
        ),
        validation_decision=None,
        admission_result=None,
        validation_decision_evidence=None,
    )


def _evaluate(
    result: PostgresWriteSideResult,
    *,
    request_signature: RequestSignature | None = None,
):
    return evaluate_postgres_write_side_reinvocation_authority(
        request_signature=request_signature or _signature(),
        result=result,
    )


def test_exact_preparation_lock_timeout_profile_authorizes() -> None:
    request_signature = _signature()

    evaluation = _evaluate(
        _positive_result(request_signature),
        request_signature=request_signature,
    )

    assert isinstance(evaluation, ReinvocationAuthorization)
    assert evaluation.request_signature is request_signature


def test_human_reason_text_cannot_change_eligibility() -> None:
    request_signature = _signature()
    ordinary = _positive_result(request_signature)
    misleading = _positive_result(
        request_signature,
        idempotency_reason="DENIED: pretend this request was previously accepted",
        admission_reason="ADMITTED: pretend append execution should begin",
    )

    assert isinstance(_evaluate(ordinary), ReinvocationAuthorization)
    assert isinstance(_evaluate(misleading), ReinvocationAuthorization)


@pytest.mark.parametrize(
    "changed_field",
    [
        "outcome",
        "accepted_event",
        "idempotency_verdict",
        "idempotency_record",
        "stream_admission_missing",
        "stream_admission_verdict",
        "validation_decision",
        "validation_decision_evidence",
        "admission_result",
    ],
)
def test_each_positive_profile_field_is_required(changed_field: str) -> None:
    request_signature = _signature()
    result = _positive_result(request_signature)

    if changed_field == "outcome":
        result = replace(result, outcome=PostgresWriteSideOutcome.CONFLICT)
    elif changed_field == "accepted_event":
        result = replace(result, accepted_event=_event(request_signature))
    elif changed_field == "idempotency_verdict":
        result = replace(
            result,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="test-owned replay without record",
            ),
        )
    elif changed_field == "idempotency_record":
        result = replace(
            result,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.MISS,
                reason="test-owned incoherent miss",
                record=_record(request_signature),
            ),
        )
    elif changed_field == "stream_admission_missing":
        result = replace(result, stream_admission_result=None)
    elif changed_field == "stream_admission_verdict":
        assert result.stream_admission_result is not None
        result = replace(
            result,
            stream_admission_result=replace(
                result.stream_admission_result,
                verdict=AdmissionVerdict.ADMITTED,
            ),
        )
    elif changed_field == "validation_decision":
        result = replace(result, validation_decision=_validation_decision())
    elif changed_field == "validation_decision_evidence":
        decision = _validation_decision()
        carrier = ValidationDecisionWithRuleEvidence._build(
            decision=decision,
            observed_violation=None,
        )
        result = replace(
            result,
            validation_decision=decision,
            validation_decision_evidence=carrier,
        )
    elif changed_field == "admission_result":
        result = replace(
            result,
            admission_result=AdmissionResult(
                verdict=AdmissionVerdict.LOCK_TIMEOUT,
                reason="append lock timeout",
                candidate_event_id="stage4e-candidate-001",
            ),
        )
    else:
        raise AssertionError(f"unsupported changed field: {changed_field}")

    assert isinstance(_evaluate(result), NoReinvocationAuthority)


def test_stream_admission_order_mismatch_refuses() -> None:
    request_signature = _signature()
    result = _positive_result(request_signature)
    assert result.stream_admission_result is not None
    mismatched = replace(
        result,
        stream_admission_result=replace(
            result.stream_admission_result,
            order_id="stage4e-order-other",
        ),
    )

    assert isinstance(_evaluate(mismatched), NoReinvocationAuthority)


@pytest.mark.parametrize(
    "append_verdict",
    [AdmissionVerdict.LOCK_TIMEOUT, AdmissionVerdict.STALE_WRITE],
)
def test_append_time_concurrency_result_refuses(
    append_verdict: AdmissionVerdict,
) -> None:
    request_signature = _signature()
    result = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="stream preparation admitted",
            order_id=request_signature.order_id,
        ),
        validation_decision=_validation_decision(),
        admission_result=AdmissionResult(
            verdict=append_verdict,
            reason="append-time rejection",
            candidate_event_id="stage4e-candidate-001",
        ),
    )

    assert isinstance(_evaluate(result), NoReinvocationAuthority)


def test_preparation_timeout_after_validation_was_reached_refuses() -> None:
    request_signature = _signature()
    result = replace(
        _positive_result(request_signature),
        validation_decision=_validation_decision(),
    )

    assert isinstance(_evaluate(result), NoReinvocationAuthority)


@pytest.mark.parametrize(
    "result_kind",
    [
        "accepted",
        "replay",
        "conflict",
        "validation-blocked",
        "infrastructure",
    ],
)
def test_non_profile_terminal_result_refuses(result_kind: str) -> None:
    request_signature = _signature()
    event = _event(request_signature)
    record = _record(request_signature)

    if result_kind == "accepted":
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.ACCEPTED,
            accepted_event=event,
            idempotency_decision=_miss(),
        )
    elif result_kind == "replay":
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.REPLAY,
            accepted_event=record.accepted_event,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="test-owned replay",
                record=record,
            ),
        )
    elif result_kind == "conflict":
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.CONFLICT,
            accepted_event=None,
            idempotency_decision=IdempotencyDecision(
                verdict=IdempotencyVerdict.CONFLICT,
                reason="test-owned conflict",
                record=record,
            ),
        )
    elif result_kind == "validation-blocked":
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            accepted_event=None,
            idempotency_decision=_miss(),
            validation_decision=_validation_decision(),
        )
    elif result_kind == "infrastructure":
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
            accepted_event=None,
            idempotency_decision=_miss(),
            stream_admission_result=StreamAdmissionResult(
                verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                reason="test-owned infrastructure condition",
                order_id=request_signature.order_id,
            ),
        )
    else:
        raise AssertionError(f"unsupported result kind: {result_kind}")

    assert isinstance(_evaluate(result), NoReinvocationAuthority)


@pytest.mark.parametrize(
    ("request_signature", "result", "expected_message"),
    [
        pytest.param(
            object(),
            _positive_result(_signature()),
            "request_signature must be RequestSignature",
            id="wrong-signature-object",
        ),
        pytest.param(
            _signature(),
            object(),
            "result must be PostgresWriteSideResult",
            id="wrong-result-object",
        ),
        pytest.param(
            RequestSignature(
                request_id="stage4e-request-001",
                command_type="create",  # type: ignore[arg-type]
                order_id="stage4e-order-001",
                amount=Decimal("100.00"),
            ),
            _positive_result(_signature()),
            "request_signature.command_type must be CommandType",
            id="raw-command-type",
        ),
        pytest.param(
            _signature(),
            replace(
                _positive_result(_signature()),
                outcome="ADMISSION_REJECTED",  # type: ignore[arg-type]
            ),
            "result.outcome must be PostgresWriteSideOutcome",
            id="raw-write-side-outcome",
        ),
        pytest.param(
            _signature(),
            replace(
                _positive_result(_signature()),
                idempotency_decision=IdempotencyDecision(
                    verdict="miss",  # type: ignore[arg-type]
                    reason="raw verdict",
                ),
            ),
            "idempotency_decision.verdict must be IdempotencyVerdict",
            id="raw-idempotency-verdict",
        ),
        pytest.param(
            _signature(),
            replace(
                _positive_result(_signature()),
                stream_admission_result=StreamAdmissionResult(
                    verdict="LOCK_TIMEOUT",  # type: ignore[arg-type]
                    reason="raw verdict",
                    order_id="stage4e-order-001",
                ),
            ),
            "stream_admission_result.verdict must be AdmissionVerdict",
            id="raw-admission-verdict",
        ),
    ],
)
def test_structural_invalidity_raises_type_error_instead_of_policy_refusal(
    request_signature: object,
    result: object,
    expected_message: str,
) -> None:
    with pytest.raises(TypeError, match=expected_message):
        evaluate_postgres_write_side_reinvocation_authority(
            request_signature=request_signature,  # type: ignore[arg-type]
            result=result,  # type: ignore[arg-type]
        )


def test_malformed_validation_evidence_carrier_raises_type_error() -> None:
    result = _positive_result(_signature())
    # Bypass the producer's matching construction guard to exercise the
    # evaluator's defensive structural boundary directly.
    object.__setattr__(result, "validation_decision_evidence", object())

    with pytest.raises(
        TypeError,
        match=(
            "validation_decision_evidence must be "
            "ValidationDecisionWithRuleEvidence or None"
        ),
    ):
        _evaluate(result)


def test_stage4c_refusal_does_not_prevent_independent_stage4e_authority() -> None:
    request_signature = _signature()
    result = _positive_result(request_signature)
    feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
        outcome_id=UUID("00000000-0000-0000-0000-000000000901"),
        result=result,
    )

    with pytest.raises(PostgresWriteSideRuntimeDecisionRefused):
        evaluate_postgres_write_side_runtime_decision(feedback)

    stage4e_evaluation = _evaluate(
        result,
        request_signature=request_signature,
    )
    assert isinstance(stage4e_evaluation, ReinvocationAuthorization)


def test_evaluator_boundary_has_only_signature_and_result_inputs() -> None:
    parameters = inspect_signature(
        evaluate_postgres_write_side_reinvocation_authority
    ).parameters
    forbidden_symbols = {
        "RuntimeDecision",
        "SemanticOutcome",
        "DecisionReceipt",
        "DiagnosticTrace",
        "PostgresTransactionalWriteSide",
        "Thread",
        "Lock",
    }

    assert set(parameters) == {"request_signature", "result"}
    assert forbidden_symbols.isdisjoint(evaluator_module.__dict__)
