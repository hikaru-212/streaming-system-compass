"""Reviewed Stage 4E PostgreSQL write-side re-invocation authority profiles."""

from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

from src.compass.runtime.reinvocation_authority import (
    NoReinvocationAuthority,
    ReinvocationAuthorization,
)
from src.compass.transition.runtime import ValidationDecisionWithRuleEvidence
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationResult,
)
from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent
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


PostgresWriteSideReinvocationAuthorityEvaluation: TypeAlias = (
    ReinvocationAuthorization | NoReinvocationAuthority
)


def evaluate_postgres_write_side_reinvocation_authority(
    *,
    request_signature: RequestSignature,
    result: PostgresWriteSideResult,
) -> PostgresWriteSideReinvocationAuthorityEvaluation:
    """Evaluate the reviewed Stage 4E PostgreSQL write-side profiles.

    Args:
        request_signature: Complete identity retained by the trusted caller for
            the completed invocation.
        result: Exact completed PostgreSQL write-side producer result.

    Returns:
        Immutable authority for one additional invocation of the complete
        request when and only when ``result`` has either the accepted
        preparation ``LOCK_TIMEOUT`` shape or the accepted append-version-
        advance shape. Every other well-typed result returns immutable typed
        no-authority. Human-readable producer reasons are never read.

    Raises:
        TypeError: If either top-level input or a required typed source field
            has the wrong Python structural type.

    The evaluator does not consume authority, retain a writer, execute an
    invocation, select a strategy, evaluate Stage 4C, or depend on semantic,
    receipt, trace, measurement, rule, lifecycle, or persistence evidence.
    """

    _validate_request_signature_types(request_signature)
    _validate_result_types(result)

    if _is_eligible_preparation_lock_timeout(
        request_signature=request_signature,
        result=result,
    ):
        return ReinvocationAuthorization._from_evaluation(
            request_signature=request_signature,
        )

    if _is_eligible_append_version_mismatch(
        request_signature=request_signature,
        result=result,
    ):
        return ReinvocationAuthorization._from_evaluation(
            request_signature=request_signature,
        )

    return NoReinvocationAuthority._from_evaluation(
        request_signature=request_signature,
        explanation=(
            "The completed PostgreSQL write-side result is outside the accepted "
            "preparation LOCK_TIMEOUT and append version-advance profiles; no "
            "Stage 4E authority was issued."
        ),
    )


def _validate_request_signature_types(
    request_signature: RequestSignature,
) -> None:
    """Reject structurally invalid request identity before policy evaluation."""

    if not isinstance(request_signature, RequestSignature):
        raise TypeError("request_signature must be RequestSignature")
    if not isinstance(request_signature.request_id, str):
        raise TypeError("request_signature.request_id must be str")
    if not isinstance(request_signature.command_type, CommandType):
        raise TypeError("request_signature.command_type must be CommandType")
    if not isinstance(request_signature.order_id, str):
        raise TypeError("request_signature.order_id must be str")
    if not isinstance(request_signature.amount, Decimal):
        raise TypeError("request_signature.amount must be Decimal")


def _validate_result_types(result: PostgresWriteSideResult) -> None:
    """Reject malformed producer structure without converting it to refusal."""

    if not isinstance(result, PostgresWriteSideResult):
        raise TypeError("result must be PostgresWriteSideResult")
    if not isinstance(result.outcome, PostgresWriteSideOutcome):
        raise TypeError("result.outcome must be PostgresWriteSideOutcome")
    if result.accepted_event is not None and not isinstance(
        result.accepted_event,
        OrderEvent,
    ):
        raise TypeError("result.accepted_event must be OrderEvent or None")

    idempotency_decision = result.idempotency_decision
    if not isinstance(idempotency_decision, IdempotencyDecision):
        raise TypeError(
            "result.idempotency_decision must be IdempotencyDecision"
        )
    if not isinstance(idempotency_decision.verdict, IdempotencyVerdict):
        raise TypeError(
            "result.idempotency_decision.verdict must be IdempotencyVerdict"
        )
    if idempotency_decision.record is not None and not isinstance(
        idempotency_decision.record,
        IdempotencyRecord,
    ):
        raise TypeError(
            "result.idempotency_decision.record must be IdempotencyRecord or None"
        )

    stream_admission_result = result.stream_admission_result
    if stream_admission_result is not None:
        if not isinstance(stream_admission_result, StreamAdmissionResult):
            raise TypeError(
                "result.stream_admission_result must be "
                "StreamAdmissionResult or None"
            )
        if not isinstance(stream_admission_result.verdict, AdmissionVerdict):
            raise TypeError(
                "result.stream_admission_result.verdict must be AdmissionVerdict"
            )
        if not isinstance(stream_admission_result.order_id, str):
            raise TypeError(
                "result.stream_admission_result.order_id must be str"
            )

    validation_decision = result.validation_decision
    if validation_decision is not None:
        if not isinstance(validation_decision, ValidationDecision):
            raise TypeError(
                "result.validation_decision must be ValidationDecision or None"
            )
        if not isinstance(validation_decision.action, EnforcementAction):
            raise TypeError(
                "result.validation_decision.action must be EnforcementAction"
            )
        if not isinstance(
            validation_decision.validation_result,
            ValidationResult,
        ):
            raise TypeError(
                "result.validation_decision.validation_result must be "
                "ValidationResult"
            )
        if not isinstance(
            validation_decision.validation_result.candidate_event_id,
            str,
        ):
            raise TypeError(
                "result.validation_decision.validation_result."
                "candidate_event_id must be str"
            )
    if result.validation_decision_evidence is not None and not isinstance(
        result.validation_decision_evidence,
        ValidationDecisionWithRuleEvidence,
    ):
        raise TypeError(
            "result.validation_decision_evidence must be "
            "ValidationDecisionWithRuleEvidence or None"
        )

    admission_result = result.admission_result
    if admission_result is not None:
        if not isinstance(admission_result, AdmissionResult):
            raise TypeError(
                "result.admission_result must be AdmissionResult or None"
            )
        if not isinstance(admission_result.verdict, AdmissionVerdict):
            raise TypeError(
                "result.admission_result.verdict must be AdmissionVerdict"
            )
        if not isinstance(admission_result.candidate_event_id, str):
            raise TypeError(
                "result.admission_result.candidate_event_id must be str"
            )
        if admission_result.accepted_event_id is not None and not isinstance(
            admission_result.accepted_event_id,
            str,
        ):
            raise TypeError(
                "result.admission_result.accepted_event_id must be str or None"
            )
        mismatch = admission_result.append_version_mismatch_evidence
        if mismatch is not None:
            if not isinstance(mismatch, AppendVersionMismatchEvidence):
                raise TypeError(
                    "result.admission_result."
                    "append_version_mismatch_evidence must be "
                    "AppendVersionMismatchEvidence or None"
                )
            if type(mismatch.expected_current_version) is not int:
                raise TypeError(
                    "append version mismatch expected_current_version must be int"
                )
            if type(mismatch.observed_current_version) is not int:
                raise TypeError(
                    "append version mismatch observed_current_version must be int"
                )


def _is_eligible_preparation_lock_timeout(
    *,
    request_signature: RequestSignature,
    result: PostgresWriteSideResult,
) -> bool:
    """Match only the accepted validation-not-reached preparation profile."""

    stream_admission_result = result.stream_admission_result
    idempotency_decision = result.idempotency_decision

    return (
        result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        and result.accepted_event is None
        and idempotency_decision.verdict is IdempotencyVerdict.MISS
        and idempotency_decision.record is None
        and stream_admission_result is not None
        and stream_admission_result.verdict is AdmissionVerdict.LOCK_TIMEOUT
        and stream_admission_result.order_id == request_signature.order_id
        and result.validation_decision is None
        and result.validation_decision_evidence is None
        and result.admission_result is None
    )


def _is_eligible_append_version_mismatch(
    *,
    request_signature: RequestSignature,
    result: PostgresWriteSideResult,
) -> bool:
    """Match only the reviewed append-version-advance source profile.

    This predicate authorizes one fresh full invocation so current
    authoritative state can be observed. It does not authorize candidate or
    validation reuse, append retry, acceptance, replay, or any other business
    outcome.
    """

    idempotency_decision = result.idempotency_decision
    stream_admission_result = result.stream_admission_result
    validation_decision = result.validation_decision
    admission_result = result.admission_result

    if validation_decision is None or admission_result is None:
        return False

    mismatch = admission_result.append_version_mismatch_evidence

    return (
        result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        and result.accepted_event is None
        and idempotency_decision.verdict is IdempotencyVerdict.MISS
        and idempotency_decision.record is None
        and stream_admission_result is not None
        and stream_admission_result.verdict is AdmissionVerdict.ADMITTED
        and stream_admission_result.order_id == request_signature.order_id
        and validation_decision.action is EnforcementAction.ALLOW
        and admission_result.verdict is AdmissionVerdict.STALE_WRITE
        and admission_result.accepted_event_id is None
        and isinstance(mismatch, AppendVersionMismatchEvidence)
        and mismatch.observed_current_version
        > mismatch.expected_current_version
        and admission_result.candidate_event_id
        == validation_decision.validation_result.candidate_event_id
    )


__all__ = (
    "PostgresWriteSideReinvocationAuthorityEvaluation",
    "evaluate_postgres_write_side_reinvocation_authority",
)
