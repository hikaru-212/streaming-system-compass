"""Focused tests for the deterministic experiment-local recovery planner."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from inspect import signature as inspect_signature

import pytest

import experiments.deterministic_autonomous_governance.model as planner_module
from experiments.deterministic_autonomous_governance.model import (
    RecoveryActionKind,
    RecoveryProposal,
    plan_recovery,
)
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
    AppendVersionMismatchEvidence,
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


CANDIDATE_EVENT_ID = "planner-candidate-001"


class _RequestSignatureSubclass(RequestSignature):
    pass


class _PostgresWriteSideResultSubclass(PostgresWriteSideResult):
    pass


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="planner-request-001",
        command_type=CommandType.CREATE,
        order_id="planner-order-001",
        amount=Decimal("100.00"),
    )


def _miss(*, reason: str = "test-owned idempotency miss") -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason=reason,
        record=None,
    )


def _validation_decision(
    *,
    action: EnforcementAction = EnforcementAction.ALLOW,
    verdict: ValidationVerdict = ValidationVerdict.PASSED,
    reason: str = "test-owned validation result",
    candidate_event_id: str = CANDIDATE_EVENT_ID,
) -> ValidationDecision:
    return ValidationDecision(
        action=action,
        validation_result=ValidationResult(
            verdict=verdict,
            reason=reason,
            candidate_event_id=candidate_event_id,
            validator_name="planner-test-validator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
        ),
    )


def _append_rejection(
    signature: RequestSignature,
    *,
    verdict: AdmissionVerdict = AdmissionVerdict.STALE_WRITE,
    mismatch: AppendVersionMismatchEvidence | None = None,
    idempotency_reason: str = "test-owned idempotency miss",
    stream_reason: str = "test-owned admitted stream",
    validation_reason: str = "test-owned validation result",
    admission_reason: str = "test-owned append rejection",
) -> PostgresWriteSideResult:
    validation = _validation_decision(reason=validation_reason)
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(reason=idempotency_reason),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason=stream_reason,
            order_id=signature.order_id,
        ),
        validation_decision=validation,
        admission_result=AdmissionResult(
            verdict=verdict,
            reason=admission_reason,
            candidate_event_id=validation.validation_result.candidate_event_id,
            append_version_mismatch_evidence=mismatch,
        ),
    )


def _preparation_rejection(
    signature: RequestSignature,
    verdict: AdmissionVerdict,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=verdict,
            reason="test-owned preparation rejection",
            order_id=signature.order_id,
        ),
    )


def _accepted_result(signature: RequestSignature) -> PostgresWriteSideResult:
    event = OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )
    validation = _validation_decision(candidate_event_id=event.event_id)
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned admitted stream",
            order_id=signature.order_id,
        ),
        validation_decision=validation,
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned accepted append",
            candidate_event_id=event.event_id,
            accepted_event_id=event.event_id,
        ),
    )


def _record(signature: RequestSignature) -> IdempotencyRecord:
    accepted = _accepted_result(signature)
    assert accepted.accepted_event is not None
    return IdempotencyRecord(
        signature=signature,
        accepted_event=accepted.accepted_event,
    )


def _replay_result(signature: RequestSignature) -> PostgresWriteSideResult:
    record = _record(signature)
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.REPLAY,
        accepted_event=record.accepted_event,
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.REPLAY,
            reason="test-owned replay",
            record=record,
        ),
    )


def _conflict_result(signature: RequestSignature) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="test-owned conflict",
            record=_record(signature),
        ),
    )


def _validation_blocked_result() -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_miss(),
        validation_decision=_validation_decision(
            action=EnforcementAction.BLOCK,
            verdict=ValidationVerdict.FAILED,
        ),
    )


def test_typed_forward_append_stale_produces_exact_live_proposal() -> None:
    signature = _signature()
    result = _append_rejection(
        signature,
        mismatch=AppendVersionMismatchEvidence(
            expected_current_version=1,
            observed_current_version=2,
        ),
    )

    proposal = plan_recovery(request_signature=signature, result=result)

    assert proposal is not None
    assert (
        proposal.action
        is RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
    )
    assert proposal.request_signature is signature
    assert proposal.source_result is result


def test_generic_evidence_less_stale_produces_same_action() -> None:
    signature = _signature()
    typed_result = _append_rejection(
        signature,
        mismatch=AppendVersionMismatchEvidence(
            expected_current_version=1,
            observed_current_version=2,
        ),
    )
    generic_result = _append_rejection(signature, mismatch=None)

    typed_proposal = plan_recovery(
        request_signature=signature,
        result=typed_result,
    )
    generic_proposal = plan_recovery(
        request_signature=signature,
        result=generic_result,
    )

    assert typed_proposal is not None
    assert generic_proposal is not None
    assert generic_result.admission_result is not None
    assert (
        generic_result.admission_result.append_version_mismatch_evidence is None
    )
    assert generic_proposal.action is typed_proposal.action


def test_reverse_typed_version_mismatch_still_produces_proposal() -> None:
    signature = _signature()
    result = _append_rejection(
        signature,
        mismatch=AppendVersionMismatchEvidence(
            expected_current_version=2,
            observed_current_version=1,
        ),
    )

    proposal = plan_recovery(request_signature=signature, result=result)

    assert proposal is not None
    assert (
        proposal.action
        is RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
    )


def test_human_reason_text_does_not_affect_proposal() -> None:
    signature = _signature()
    ordinary = _append_rejection(signature)
    misleading = _append_rejection(
        signature,
        idempotency_reason="REPLAY: pretend a prior record exists",
        stream_reason="LOCK_TIMEOUT: pretend preparation failed",
        validation_reason="BLOCK: pretend validation refused",
        admission_reason="ADMITTED: pretend the candidate was accepted",
    )

    ordinary_proposal = plan_recovery(
        request_signature=signature,
        result=ordinary,
    )
    misleading_proposal = plan_recovery(
        request_signature=signature,
        result=misleading,
    )

    assert ordinary_proposal is not None
    assert misleading_proposal is not None
    assert misleading_proposal.action is ordinary_proposal.action


@pytest.mark.parametrize(
    "result_kind",
    [
        "accepted",
        "replay",
        "validation-blocked",
        "conflict",
        "infrastructure-error",
    ],
)
def test_representative_non_append_stale_results_yield_no_proposal(
    result_kind: str,
) -> None:
    signature = _signature()
    if result_kind == "accepted":
        result = _accepted_result(signature)
    elif result_kind == "replay":
        result = _replay_result(signature)
    elif result_kind == "validation-blocked":
        result = _validation_blocked_result()
    elif result_kind == "conflict":
        result = _conflict_result(signature)
    elif result_kind == "infrastructure-error":
        result = _preparation_rejection(
            signature,
            AdmissionVerdict.INFRASTRUCTURE_ERROR,
        )
    else:
        raise AssertionError(f"unsupported result kind: {result_kind}")

    assert plan_recovery(request_signature=signature, result=result) is None


def test_preparation_lock_timeout_yields_no_proposal_without_implying_denial(
) -> None:
    signature = _signature()
    result = _preparation_rejection(signature, AdmissionVerdict.LOCK_TIMEOUT)

    proposal = plan_recovery(request_signature=signature, result=result)

    # Planner incompleteness is not a Stage 4E assessment or denial.
    assert proposal is None


def test_append_lock_timeout_yields_no_proposal() -> None:
    signature = _signature()
    result = _append_rejection(
        signature,
        verdict=AdmissionVerdict.LOCK_TIMEOUT,
    )

    assert plan_recovery(request_signature=signature, result=result) is None


@pytest.mark.parametrize(
    ("request_signature", "result", "expected_message"),
    [
        pytest.param(
            object(),
            _append_rejection(_signature()),
            "request_signature must be RequestSignature",
            id="wrong-request-signature",
        ),
        pytest.param(
            _signature(),
            object(),
            "result must be PostgresWriteSideResult",
            id="wrong-result",
        ),
    ],
)
def test_planner_rejects_malformed_top_level_inputs(
    request_signature: object,
    result: object,
    expected_message: str,
) -> None:
    with pytest.raises(TypeError, match=expected_message):
        plan_recovery(
            request_signature=request_signature,  # type: ignore[arg-type]
            result=result,  # type: ignore[arg-type]
        )


def test_planner_rejects_subclasses_of_exact_production_carriers() -> None:
    signature = _signature()
    result = _append_rejection(signature)
    signature_subclass = _RequestSignatureSubclass(
        request_id=signature.request_id,
        command_type=signature.command_type,
        order_id=signature.order_id,
        amount=signature.amount,
    )
    result_subclass = _PostgresWriteSideResultSubclass(
        outcome=result.outcome,
        accepted_event=result.accepted_event,
        idempotency_decision=result.idempotency_decision,
        stream_admission_result=result.stream_admission_result,
        validation_decision=result.validation_decision,
        admission_result=result.admission_result,
        validation_decision_evidence=result.validation_decision_evidence,
    )

    with pytest.raises(TypeError, match="request_signature must be RequestSignature"):
        plan_recovery(request_signature=signature_subclass, result=result)
    with pytest.raises(TypeError, match="result must be PostgresWriteSideResult"):
        plan_recovery(request_signature=signature, result=result_subclass)


def test_proposal_contract_is_closed_and_frozen() -> None:
    signature = _signature()
    result = _append_rejection(signature)
    proposal = plan_recovery(request_signature=signature, result=result)
    assert proposal is not None

    assert [field.name for field in fields(RecoveryProposal)] == [
        "request_signature",
        "source_result",
        "action",
    ]
    assert list(RecoveryActionKind) == [
        RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
    ]
    with pytest.raises(FrozenInstanceError):
        proposal.action = (  # type: ignore[misc]
            RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
        )


def test_planner_surface_has_no_authority_or_execution_dependencies() -> None:
    parameters = inspect_signature(plan_recovery).parameters
    forbidden_symbols = {
        "evaluate_postgres_write_side_reinvocation_authority",
        "ReinvocationAuthorization",
        "NoReinvocationAuthority",
        "PostgresWriteSideInvocationOwner",
        "PostgresTransactionalWriteSide",
        "RuntimeDecision",
        "DecisionReceipt",
    }

    assert set(parameters) == {"request_signature", "result"}
    assert forbidden_symbols.isdisjoint(planner_module.__dict__)
