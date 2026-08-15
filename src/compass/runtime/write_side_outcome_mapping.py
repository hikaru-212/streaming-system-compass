from __future__ import annotations

from enum import Enum
from typing import Any, Mapping
from uuid import UUID

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
)
from src.compass.runtime.technical_status_mapping import (
    map_runtime_technical_status,
)
from src.compass.transition.types import ValidationDecision
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)


_PROTECTED_CONTEXT_KEYS = frozenset(
    {
        "write_side_outcome",
        "order_id",
        "request_id",
        "candidate_event_id",
        "accepted_event_id",
    }
)


def map_write_side_admission_status_to_semantic_outcome(
    *,
    outcome_id: UUID,
    technical_status: str | Enum,
    reason: str,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Map write-side admission technical evidence to SemanticOutcome.

    This adapter pins the observation boundary to Layer 1 write-side admission.

    It does not:
    - append accepted history
    - persist rejected candidates
    - persist DecisionReceipt
    - choose retry behavior
    - select execution strategy
    - mutate write-side state
    """

    return map_runtime_technical_status(
        outcome_id=outcome_id,
        technical_status=technical_status,
        boundary=SemanticBoundary.LAYER_1_WRITE_SIDE,
        reason=_require_reason(reason, "write-side admission status"),
        context=dict(context or {}),
        evidence=dict(evidence or {}),
    )


def map_postgres_write_side_result_to_semantic_outcome(
    *,
    outcome_id: UUID,
    result: PostgresWriteSideResult,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Map PostgreSQL write-side orchestration result to SemanticOutcome.

    This adapter connects the Stage 3.5B / 3.5E write-side transactional
    result boundary to the Stage 4A semantic outcome contract.

    It records the write-side observation boundary.

    It does not infer read-side root cause, persist rejected candidates, execute
    recovery, govern retry, or change accepted-history admission behavior.
    """

    _validate_postgres_write_side_result_shape(result)

    technical_status = _technical_status_for_postgres_write_side_result(result)

    return map_write_side_admission_status_to_semantic_outcome(
        outcome_id=outcome_id,
        technical_status=technical_status,
        reason=_reason_for_postgres_write_side_result(
            result=result,
            technical_status=technical_status,
        ),
        context=_merge_context(
            _context_from_postgres_write_side_result(result),
            context,
        ),
        evidence=_merge_mappings(
            _evidence_from_postgres_write_side_result(result),
            evidence,
        ),
    )


def _technical_status_for_postgres_write_side_result(
    result: PostgresWriteSideResult,
) -> str:
    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        return "WRITE_SIDE_ACCEPTED"

    if result.outcome == PostgresWriteSideOutcome.REPLAY:
        return "IDEMPOTENT_REPLAY"

    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        return "IDEMPOTENCY_CONFLICT"

    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return "COMPASS_VALIDATION_BLOCKED"

    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        admission_result = _admission_rejection_source(result)
        return _technical_status_for_admission_verdict(
            admission_result.verdict,
        )

    raise ValueError(f"Unsupported write-side outcome: {result.outcome}")


def _technical_status_for_admission_verdict(
    verdict: AdmissionVerdict,
) -> str:
    if verdict == AdmissionVerdict.STALE_WRITE:
        return "CONCURRENT_STATE_STALENESS"

    if verdict == AdmissionVerdict.LOCK_TIMEOUT:
        return "LOCK_TIMEOUT"

    if verdict == AdmissionVerdict.INFRASTRUCTURE_ERROR:
        return "WRITE_SIDE_INFRASTRUCTURE_ERROR"

    raise ValueError(
        "ADMISSION_REJECTED result cannot be mapped from admitted verdict"
    )


def _reason_for_postgres_write_side_result(
    *,
    result: PostgresWriteSideResult,
    technical_status: str,
) -> str:
    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        return "Write-side candidate event was admitted into accepted history."

    if result.outcome in {
        PostgresWriteSideOutcome.REPLAY,
        PostgresWriteSideOutcome.CONFLICT,
    }:
        return _require_reason(
            result.idempotency_decision.reason,
            f"{result.outcome.value} idempotency decision",
        )

    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        assert result.validation_decision is not None
        return _require_reason(
            result.validation_decision.validation_result.reason,
            "ValidationDecision",
        )

    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        admission_result = _admission_rejection_source(result)
        return _require_reason(
            admission_result.reason,
            f"{technical_status} admission result",
        )

    return f"Write-side result mapped as {technical_status}."


def _validate_postgres_write_side_result_shape(
    result: PostgresWriteSideResult,
) -> None:
    if (
        result.outcome == PostgresWriteSideOutcome.ACCEPTED
        and result.accepted_event is None
    ):
        raise ValueError("ACCEPTED write-side result requires accepted_event")

    if (
        result.outcome == PostgresWriteSideOutcome.REPLAY
        and _accepted_event_from_result(result) is None
    ):
        raise ValueError(
            "REPLAY write-side result requires prior accepted_event "
            "from idempotency record"
        )

    if (
        result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED
        and result.validation_decision is None
    ):
        raise ValueError(
            "VALIDATION_BLOCKED write-side result requires validation_decision"
        )

    if (
        result.admission_result is not None
        and result.admission_result.verdict != AdmissionVerdict.ADMITTED
        and result.admission_result.accepted_event_id is not None
    ):
        raise ValueError(
            "rejected append-time admission result must not carry "
            "accepted_event_id"
        )

    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        _admission_rejection_source(result)


def _admission_rejection_source(
    result: PostgresWriteSideResult,
) -> AdmissionResult | StreamAdmissionResult:
    if result.admission_result is not None:
        if result.admission_result.verdict == AdmissionVerdict.ADMITTED:
            raise ValueError(
                "ADMISSION_REJECTED result cannot use admitted "
                "append-time admission result"
            )
        return result.admission_result

    if result.stream_admission_result is not None:
        if result.stream_admission_result.verdict == AdmissionVerdict.ADMITTED:
            raise ValueError(
                "ADMISSION_REJECTED result cannot use admitted "
                "stream admission result"
            )
        return result.stream_admission_result

    raise ValueError(
        "ADMISSION_REJECTED write-side result requires stream_admission_result "
        "or admission_result"
    )


def _context_from_postgres_write_side_result(
    result: PostgresWriteSideResult,
) -> dict[str, Any]:
    accepted_event = _accepted_event_from_result(result)

    return {
        "write_side_outcome": _enum_value(result.outcome),
        "order_id": _order_id_from_result(result, accepted_event),
        "request_id": _request_id_from_result(result, accepted_event),
        "candidate_event_id": _candidate_event_id_from_result(result),
        "accepted_event_id": _accepted_event_id_from_result(accepted_event),
    }


def _evidence_from_postgres_write_side_result(
    result: PostgresWriteSideResult,
) -> dict[str, Any]:
    validation_decision = result.validation_decision

    return {
        "result_type": "PostgresWriteSideResult",
        "write_side_outcome": _enum_value(result.outcome),
        "accepted_event_present": result.accepted_event is not None,
        "idempotency_verdict": _enum_value(result.idempotency_decision.verdict),
        "idempotency_reason": result.idempotency_decision.reason,
        "stream_admission_result_present": (
            result.stream_admission_result is not None
        ),
        "stream_admission_verdict": _enum_value(
            result.stream_admission_result.verdict
            if result.stream_admission_result is not None
            else None
        ),
        "stream_admission_reason": (
            result.stream_admission_result.reason
            if result.stream_admission_result is not None
            else None
        ),
        "validation_decision_present": validation_decision is not None,
        "validation_action": _validation_action(validation_decision),
        "validation_verdict": _validation_verdict(validation_decision),
        "validation_reason": _validation_reason(validation_decision),
        "validation_mode": _validation_mode(validation_decision),
        "validator_name": _validator_name(validation_decision),
        "append_admission_result_present": result.admission_result is not None,
        "append_admission_verdict": _enum_value(
            result.admission_result.verdict
            if result.admission_result is not None
            else None
        ),
        "append_admission_reason": (
            result.admission_result.reason
            if result.admission_result is not None
            else None
        ),
    }


def _accepted_event_from_result(result: PostgresWriteSideResult):
    if result.accepted_event is not None:
        return result.accepted_event

    record = result.idempotency_decision.record
    if record is not None:
        return record.accepted_event

    return None


def _order_id_from_result(
    result: PostgresWriteSideResult,
    accepted_event,
) -> str | None:
    order_ids = {
        order_id
        for order_id in (
            accepted_event.order_id if accepted_event is not None else None,
            (
                result.stream_admission_result.order_id
                if result.stream_admission_result is not None
                else None
            ),
            (
                result.idempotency_decision.record.signature.order_id
                if result.idempotency_decision.record is not None
                else None
            ),
        )
        if order_id is not None
    }

    if len(order_ids) > 1:
        raise ValueError(
            "Contradictory order_id evidence detected in write-side result"
        )

    if accepted_event is not None:
        return accepted_event.order_id

    if result.stream_admission_result is not None:
        return result.stream_admission_result.order_id

    record = result.idempotency_decision.record
    if record is not None:
        return record.signature.order_id

    return None


def _request_id_from_result(
    result: PostgresWriteSideResult,
    accepted_event,
) -> str | None:
    request_ids = {
        request_id
        for request_id in (
            accepted_event.request_id if accepted_event is not None else None,
            (
                result.idempotency_decision.record.signature.request_id
                if result.idempotency_decision.record is not None
                else None
            ),
        )
        if request_id is not None
    }

    if len(request_ids) > 1:
        raise ValueError(
            "Contradictory request_id evidence detected in write-side result"
        )

    if accepted_event is not None:
        return accepted_event.request_id

    record = result.idempotency_decision.record
    if record is not None:
        return record.signature.request_id

    return None


def _candidate_event_id_from_result(
    result: PostgresWriteSideResult,
) -> str | None:
    if result.admission_result is not None:
        return result.admission_result.candidate_event_id

    if result.validation_decision is not None:
        return result.validation_decision.validation_result.candidate_event_id

    return None


def _accepted_event_id_from_result(
    accepted_event,
) -> str | None:
    # accepted_event_id must only refer to an event that is already part of
    # accepted history.
    #
    # It may come from:
    # - the newly appended accepted_event for ACCEPTED outcomes
    # - the previously accepted event referenced by an idempotency record for
    #   REPLAY outcomes
    #
    # It must not be derived from admission_result for rejected candidates.
    # Before append admission succeeds, the event is still only a candidate.
    if accepted_event is not None:
        return accepted_event.event_id

    return None


def _validation_action(
    validation_decision: ValidationDecision | None,
) -> str | None:
    if validation_decision is None:
        return None
    return _enum_value(validation_decision.action)


def _validation_verdict(
    validation_decision: ValidationDecision | None,
) -> str | None:
    if validation_decision is None:
        return None
    return _enum_value(validation_decision.validation_result.verdict)


def _validation_reason(
    validation_decision: ValidationDecision | None,
) -> str | None:
    if validation_decision is None:
        return None
    return validation_decision.validation_result.reason


def _validation_mode(
    validation_decision: ValidationDecision | None,
) -> str | None:
    if validation_decision is None:
        return None
    return _enum_value(validation_decision.validation_result.validation_mode)


def _validator_name(
    validation_decision: ValidationDecision | None,
) -> str | None:
    if validation_decision is None:
        return None
    return validation_decision.validation_result.validator_name


def _enum_value(value: Enum | None) -> str | None:
    if value is None:
        return None
    return str(value.value)


def _require_reason(reason: str | None, source: str) -> str:
    if reason is None or not reason.strip():
        return f"Missing explicit reason from {source}."
    return reason


def _merge_context(
    base: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base)

    for key, value in dict(override or {}).items():
        if (
            key in _PROTECTED_CONTEXT_KEYS
            and key in merged
            and merged[key] is not None
            and value != merged[key]
        ):
            raise ValueError(
                f"context {key} must not contradict mapped write-side context"
            )
        merged[key] = value

    return merged


def _merge_mappings(
    base: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(base)
    merged.update(dict(override or {}))
    return merged