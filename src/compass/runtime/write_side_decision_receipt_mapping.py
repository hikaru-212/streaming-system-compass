from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.decision_receipt_mapping import (
    map_semantic_outcome_to_decision_receipt,
)
from src.compass.runtime.write_side_outcome_mapping import (
    map_postgres_write_side_result_to_semantic_outcome,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.events import OrderEvent
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

__all__ = ["map_postgres_write_side_result_to_decision_receipt"]


@dataclass(frozen=True)
class _SelectedIdentity:
    order_id: str | None
    request_id: str | None
    candidate_event_id: UUID | None
    accepted_event_id: UUID | None


def map_postgres_write_side_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: PostgresWriteSideResult,
) -> DecisionReceipt:
    """
    Construct a DecisionReceipt from one concrete PostgresWriteSideResult.

    This producer-specific wrapper owns the PostgreSQL write-side lifecycle
    interpretation around two stable adapters:

    - Stage 4A maps the typed result into its existing SemanticOutcome.
    - Stage 4B PR3 preserves that semantic tuple in DecisionReceipt.

    PR4 validates the result shape and selects subject, correlation, primary
    identity provenance, admission fate, and compact summary evidence directly
    from the typed result. Candidate identity does not imply accepted-history
    authority, and candidate construction does not imply that append admission
    was reached.

    Producer event IDs are strings while receipt correlation requires UUID.
    Every selected event ID is parsed explicitly; malformed or contradictory
    identity fails closed instead of being dropped, replaced, moved to
    metadata, or downgraded to unknown provenance.

    Admission fate comes from the concrete write-side lifecycle phase and
    verdict. This adapter preserves typed producer evidence but does not own
    governance flag evaluation. All four DecisionReceipt flags remain
    NOT_EVALUATED for later authorized evaluators.

    This wrapper does not accept SemanticOutcome overrides, copy
    SemanticOutcome context or evidence, mutate write-side state, execute a
    runtime action, choose policy or strategy, evaluate or authorize retry,
    serialize, or persist a receipt.
    """

    _validate_result_shape(result)

    outcome = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=outcome_id,
        result=result,
    )
    identity = _select_identity(result)
    subject = _subject_for_result(result=result, identity=identity)
    correlation = DecisionReceiptCorrelation(
        order_id=identity.order_id,
        request_id=identity.request_id,
        candidate_event_id=identity.candidate_event_id,
        accepted_event_id=identity.accepted_event_id,
        identity_source=_identity_source_for_result(
            result=result,
            identity=identity,
        ),
    )

    return map_semantic_outcome_to_decision_receipt(
        receipt_id=receipt_id,
        outcome=outcome,
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=subject,
        correlation=correlation,
        flags=DecisionReceiptFlags(),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=_admission_disposition_for_result(result)
        ),
        evidence_summary=_evidence_summary_for_result(result),
    )


def _validate_result_shape(result: PostgresWriteSideResult) -> None:
    """
    Validate the supported PostgresWriteSideResult receipt-mapping shapes.

    Supported shapes include the current PostgreSQL producer lifecycle and
    explicitly supported typed-result compositions accepted by this adapter.
    """

    _require_instance(result, PostgresWriteSideResult, "result")
    _require_instance(
        result.outcome,
        PostgresWriteSideOutcome,
        "result.outcome",
    )
    _validate_idempotency_decision(result.idempotency_decision)

    if result.accepted_event is not None:
        _require_instance(
            result.accepted_event,
            OrderEvent,
            "result.accepted_event",
        )
    if result.stream_admission_result is not None:
        _validate_stream_admission_result(result.stream_admission_result)
    if result.validation_decision is not None:
        _validate_validation_decision(result.validation_decision)
    if result.admission_result is not None:
        _validate_admission_result(result.admission_result)

    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        _validate_accepted_result(result)
        return

    if result.outcome == PostgresWriteSideOutcome.REPLAY:
        _validate_replay_or_conflict_result(
            result=result,
            expected_verdict=IdempotencyVerdict.REPLAY,
        )
        return

    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        _validate_replay_or_conflict_result(
            result=result,
            expected_verdict=IdempotencyVerdict.CONFLICT,
        )
        if result.accepted_event is not None:
            raise ValueError("CONFLICT result must not carry accepted_event")
        return

    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        _validate_validation_blocked_result(result)
        return

    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        _validate_admission_rejected_result(result)
        return

    raise ValueError(f"Unsupported write-side outcome: {result.outcome}")


def _validate_accepted_result(result: PostgresWriteSideResult) -> None:
    _require_idempotency_state(
        result.idempotency_decision,
        expected_verdict=IdempotencyVerdict.MISS,
        expected_record=False,
        outcome_name="ACCEPTED",
    )
    if result.accepted_event is None:
        raise ValueError("ACCEPTED result requires accepted_event")
    if result.stream_admission_result is None:
        raise ValueError("ACCEPTED result requires stream_admission_result")
    if not result.stream_admission_result.admitted:
        raise ValueError("ACCEPTED result requires admitted stream evidence")
    if result.validation_decision is None:
        raise ValueError("ACCEPTED result requires validation_decision")
    if result.validation_decision.action != EnforcementAction.ALLOW:
        raise ValueError("ACCEPTED result requires an allowing validation decision")
    if result.admission_result is None:
        raise ValueError("ACCEPTED result requires admitted append evidence")
    if not result.admission_result.admitted:
        raise ValueError("ACCEPTED result requires admitted append evidence")
    if result.admission_result.accepted_event_id is None:
        raise ValueError(
            "ACCEPTED result requires append accepted_event_id evidence"
        )


def _validate_replay_or_conflict_result(
    *,
    result: PostgresWriteSideResult,
    expected_verdict: IdempotencyVerdict,
) -> None:
    outcome_name = result.outcome.value
    _require_idempotency_state(
        result.idempotency_decision,
        expected_verdict=expected_verdict,
        expected_record=True,
        outcome_name=outcome_name,
    )
    if result.stream_admission_result is not None:
        raise ValueError(
            f"{outcome_name} result must not carry stream admission evidence"
        )
    if result.admission_result is not None:
        raise ValueError(
            f"{outcome_name} result must not carry append admission evidence"
        )
    if (
        result.validation_decision is not None
        and result.validation_decision.action != EnforcementAction.ALLOW
    ):
        raise ValueError(
            f"{outcome_name} post-validation result requires an allowing "
            "validation decision"
        )


def _validate_validation_blocked_result(
    result: PostgresWriteSideResult,
) -> None:
    _require_idempotency_state(
        result.idempotency_decision,
        expected_verdict=IdempotencyVerdict.MISS,
        expected_record=False,
        outcome_name="VALIDATION_BLOCKED",
    )
    if result.accepted_event is not None:
        raise ValueError(
            "VALIDATION_BLOCKED result must not carry accepted_event"
        )
    if result.validation_decision is None:
        raise ValueError(
            "VALIDATION_BLOCKED result requires validation_decision"
        )
    if result.validation_decision.action != EnforcementAction.BLOCK:
        raise ValueError(
            "VALIDATION_BLOCKED result requires a blocking validation decision"
        )
    if result.admission_result is not None:
        raise ValueError(
            "VALIDATION_BLOCKED result must not carry append admission evidence"
        )
    if (
        result.stream_admission_result is not None
        and not result.stream_admission_result.admitted
    ):
        raise ValueError(
            "VALIDATION_BLOCKED result cannot carry rejected stream evidence"
        )


def _validate_admission_rejected_result(
    result: PostgresWriteSideResult,
) -> None:
    _require_idempotency_state(
        result.idempotency_decision,
        expected_verdict=IdempotencyVerdict.MISS,
        expected_record=False,
        outcome_name="ADMISSION_REJECTED",
    )
    if result.accepted_event is not None:
        raise ValueError("ADMISSION_REJECTED result must not carry accepted_event")
    if result.stream_admission_result is None:
        raise ValueError(
            "ADMISSION_REJECTED result requires stream admission evidence"
        )

    append_result = result.admission_result
    if append_result is None:
        if result.stream_admission_result.admitted:
            raise ValueError(
                "stream-owned ADMISSION_REJECTED result requires a rejected "
                "stream verdict"
            )
        if (
            result.validation_decision is not None
            and result.validation_decision.action != EnforcementAction.ALLOW
        ):
            raise ValueError(
                "post-validation stream rejection requires an allowing "
                "validation decision"
            )
        return

    if not result.stream_admission_result.admitted:
        raise ValueError(
            "append-owned ADMISSION_REJECTED result requires admitted stream "
            "evidence"
        )
    if append_result.admitted:
        raise ValueError(
            "ADMISSION_REJECTED result cannot carry admitted append evidence"
        )
    if append_result.accepted_event_id is not None:
        raise ValueError(
            "rejected append result must not carry accepted_event_id"
        )
    if result.validation_decision is None:
        raise ValueError(
            "append-owned ADMISSION_REJECTED result requires validation_decision"
        )
    if result.validation_decision.action != EnforcementAction.ALLOW:
        raise ValueError(
            "append-owned ADMISSION_REJECTED result requires an allowing "
            "validation decision"
        )


def _validate_idempotency_decision(
    decision: IdempotencyDecision,
) -> None:
    _require_instance(decision, IdempotencyDecision, "idempotency_decision")
    _require_instance(
        decision.verdict,
        IdempotencyVerdict,
        "idempotency_decision.verdict",
    )
    if decision.record is not None:
        _require_instance(
            decision.record,
            IdempotencyRecord,
            "idempotency_decision.record",
        )
        _require_instance(
            decision.record.signature,
            RequestSignature,
            "idempotency_decision.record.signature",
        )
        _require_instance(
            decision.record.accepted_event,
            OrderEvent,
            "idempotency_decision.record.accepted_event",
        )


def _validate_validation_decision(decision: ValidationDecision) -> None:
    _require_instance(decision, ValidationDecision, "validation_decision")
    _require_instance(
        decision.action,
        EnforcementAction,
        "validation_decision.action",
    )
    _require_instance(
        decision.validation_result,
        ValidationResult,
        "validation_decision.validation_result",
    )
    _require_instance(
        decision.validation_result.verdict,
        ValidationVerdict,
        "validation_decision.validation_result.verdict",
    )
    _require_instance(
        decision.validation_result.validation_mode,
        ValidationMode,
        "validation_decision.validation_result.validation_mode",
    )


def _validate_stream_admission_result(
    result: StreamAdmissionResult,
) -> None:
    _require_instance(result, StreamAdmissionResult, "stream_admission_result")
    _require_instance(
        result.verdict,
        AdmissionVerdict,
        "stream_admission_result.verdict",
    )


def _validate_admission_result(result: AdmissionResult) -> None:
    _require_instance(result, AdmissionResult, "admission_result")
    _require_instance(
        result.verdict,
        AdmissionVerdict,
        "admission_result.verdict",
    )


def _require_idempotency_state(
    decision: IdempotencyDecision,
    *,
    expected_verdict: IdempotencyVerdict,
    expected_record: bool,
    outcome_name: str,
) -> None:
    if decision.verdict != expected_verdict:
        raise ValueError(
            f"{outcome_name} result requires idempotency verdict "
            f"{expected_verdict.value}"
        )
    if expected_record and decision.record is None:
        raise ValueError(
            f"{outcome_name} result requires an accepted idempotency record"
        )
    if not expected_record and decision.record is not None:
        raise ValueError(
            f"{outcome_name} result must not carry an idempotency record"
        )


def _select_identity(result: PostgresWriteSideResult) -> _SelectedIdentity:
    """Select only typed producer identities and reject contradictions."""

    record = result.idempotency_decision.record
    accepted_events: list[tuple[str, OrderEvent]] = []
    if result.accepted_event is not None:
        accepted_events.append(("returned accepted event", result.accepted_event))
    if record is not None:
        accepted_events.append(
            ("idempotency record accepted event", record.accepted_event)
        )

    order_sources: list[tuple[str, str]] = []
    request_sources: list[tuple[str, str]] = []
    accepted_id_sources: list[tuple[str, str]] = []

    for source_name, event in accepted_events:
        order_sources.append((f"{source_name} order_id", event.order_id))
        request_sources.append((f"{source_name} request_id", event.request_id))
        accepted_id_sources.append((f"{source_name} event_id", event.event_id))

    if record is not None:
        order_sources.append(
            ("idempotency record signature order_id", record.signature.order_id)
        )
        request_sources.append(
            (
                "idempotency record signature request_id",
                record.signature.request_id,
            )
        )

    if result.stream_admission_result is not None:
        order_sources.append(
            (
                "stream admission order_id",
                result.stream_admission_result.order_id,
            )
        )

    candidate_sources: list[tuple[str, str]] = []
    if result.validation_decision is not None:
        candidate_sources.append(
            (
                "validation candidate_event_id",
                result.validation_decision.validation_result.candidate_event_id,
            )
        )
    if result.admission_result is not None:
        candidate_sources.append(
            (
                "append candidate_event_id",
                result.admission_result.candidate_event_id,
            )
        )

    selected = _SelectedIdentity(
        order_id=_select_consistent_string(order_sources, "order_id"),
        request_id=_select_consistent_string(request_sources, "request_id"),
        candidate_event_id=_select_consistent_uuid(
            candidate_sources,
            "candidate_event_id",
        ),
        accepted_event_id=_select_consistent_uuid(
            accepted_id_sources,
            "accepted_event_id",
        ),
    )

    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        _validate_accepted_identity(result=result, identity=selected)

    return selected


def _validate_accepted_identity(
    *,
    result: PostgresWriteSideResult,
    identity: _SelectedIdentity,
) -> None:
    """Prove that one admitted candidate became the returned accepted event."""

    if result.admission_result is None:
        raise ValueError("ACCEPTED result requires admitted append evidence")

    append_accepted_event_id = _parse_uuid(
        result.admission_result.accepted_event_id,
        "admission_result.accepted_event_id",
    )
    if identity.candidate_event_id is None:
        raise ValueError("ACCEPTED result requires candidate_event_id")
    if identity.accepted_event_id is None:
        raise ValueError("ACCEPTED result requires accepted_event_id")
    if (
        identity.candidate_event_id != identity.accepted_event_id
        or append_accepted_event_id != identity.accepted_event_id
    ):
        raise ValueError(
            "ACCEPTED candidate and accepted event identities must match"
        )


def _select_consistent_string(
    sources: list[tuple[str, str]],
    field_name: str,
) -> str | None:
    if not sources:
        return None

    values: set[str] = set()
    for source_name, value in sources:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{source_name} must be a non-empty string")
        values.add(value)

    if len(values) != 1:
        raise ValueError(f"Contradictory {field_name} evidence")
    return sources[0][1]


def _select_consistent_uuid(
    sources: list[tuple[str, str]],
    field_name: str,
) -> UUID | None:
    if not sources:
        return None

    parsed = [
        (source_name, _parse_uuid(value, source_name))
        for source_name, value in sources
    ]
    if len({value for _, value in parsed}) != 1:
        raise ValueError(f"Contradictory {field_name} evidence")
    return parsed[0][1]


def _parse_uuid(value: object, field_name: str) -> UUID:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty UUID string")
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID string") from exc


def _subject_for_result(
    *,
    result: PostgresWriteSideResult,
    identity: _SelectedIdentity,
) -> DecisionReceiptSubject:
    if result.outcome in {
        PostgresWriteSideOutcome.ACCEPTED,
        PostgresWriteSideOutcome.REPLAY,
    }:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(_require_selected_uuid(
                identity.accepted_event_id,
                "accepted_event_id",
            )),
        )

    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.REQUEST,
            subject_id=_require_selected_string(
                identity.request_id,
                "request_id",
            ),
        )

    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return _candidate_subject(identity)

    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        if identity.candidate_event_id is not None:
            return _candidate_subject(identity)
        return DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id=_require_selected_string(identity.order_id, "order_id"),
        )

    raise ValueError(f"Unsupported write-side outcome: {result.outcome}")


def _candidate_subject(
    identity: _SelectedIdentity,
) -> DecisionReceiptSubject:
    candidate_event_id = _require_selected_uuid(
        identity.candidate_event_id,
        "candidate_event_id",
    )
    return DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.CANDIDATE_EVENT,
        subject_id=str(candidate_event_id),
    )


def _identity_source_for_result(
    *,
    result: PostgresWriteSideResult,
    identity: _SelectedIdentity,
) -> DecisionReceiptIdentitySource:
    if result.outcome in {
        PostgresWriteSideOutcome.ACCEPTED,
        PostgresWriteSideOutcome.REPLAY,
    }:
        return DecisionReceiptIdentitySource.ACCEPTED_HISTORY
    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        return DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY
    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        if identity.candidate_event_id is None:
            return DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
        return DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY
    raise ValueError(f"Unsupported write-side outcome: {result.outcome}")


def _admission_disposition_for_result(
    result: PostgresWriteSideResult,
) -> EventAdmissionDisposition:
    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        return EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
    if result.outcome == PostgresWriteSideOutcome.REPLAY:
        return EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        return (
            EventAdmissionDisposition.IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
        )
    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED
    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        if result.admission_result is None:
            return EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
        if result.admission_result.verdict == AdmissionVerdict.STALE_WRITE:
            return EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT
        if result.admission_result.verdict in {
            AdmissionVerdict.LOCK_TIMEOUT,
            AdmissionVerdict.INFRASTRUCTURE_ERROR,
        }:
            return EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE
    raise ValueError("Unsupported write-side admission disposition")


def _owned_rejection_verdict(
    result: PostgresWriteSideResult,
) -> AdmissionVerdict | None:
    """Return the verdict from the lifecycle phase that rejected the attempt."""

    if result.outcome != PostgresWriteSideOutcome.ADMISSION_REJECTED:
        return None
    if result.admission_result is not None:
        return result.admission_result.verdict
    if result.stream_admission_result is None:
        raise ValueError(
            "ADMISSION_REJECTED result requires stream admission evidence"
        )
    return result.stream_admission_result.verdict


def _technical_status_for_result(result: PostgresWriteSideResult) -> str:
    """Mirror the current Stage 4A status selection without reading its payload."""

    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        return "WRITE_SIDE_ACCEPTED"
    if result.outcome == PostgresWriteSideOutcome.REPLAY:
        return "IDEMPOTENT_REPLAY"
    if result.outcome == PostgresWriteSideOutcome.CONFLICT:
        return "IDEMPOTENCY_CONFLICT"
    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return "COMPASS_VALIDATION_BLOCKED"
    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        verdict = _owned_rejection_verdict(result)
        if verdict == AdmissionVerdict.STALE_WRITE:
            return "CONCURRENT_STATE_STALENESS"
        if verdict == AdmissionVerdict.LOCK_TIMEOUT:
            return "LOCK_TIMEOUT"
        if verdict == AdmissionVerdict.INFRASTRUCTURE_ERROR:
            return "WRITE_SIDE_INFRASTRUCTURE_ERROR"
    raise ValueError("Unsupported write-side technical status")


def _lifecycle_phase_for_result(result: PostgresWriteSideResult) -> str:
    if result.outcome == PostgresWriteSideOutcome.ACCEPTED:
        return "ACCEPTED_HISTORY"
    if result.outcome in {
        PostgresWriteSideOutcome.REPLAY,
        PostgresWriteSideOutcome.CONFLICT,
    }:
        return "IDEMPOTENCY_CHECK"
    if result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return "VALIDATION"
    if result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED:
        if result.admission_result is None:
            return "STREAM_PREPARATION"
        return "APPEND_ADMISSION"
    raise ValueError(f"Unsupported write-side outcome: {result.outcome}")


def _evidence_summary_for_result(
    result: PostgresWriteSideResult,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "technical_status": _technical_status_for_result(result),
        "write_side_outcome": result.outcome.value,
        "idempotency_verdict": result.idempotency_decision.verdict.value,
        "lifecycle_phase": _lifecycle_phase_for_result(result),
    }

    if result.stream_admission_result is not None:
        summary["stream_admission_verdict"] = (
            result.stream_admission_result.verdict.value
        )
    if result.validation_decision is not None:
        validation_result = result.validation_decision.validation_result
        summary["validation_action"] = result.validation_decision.action.value
        summary["validation_verdict"] = validation_result.verdict.value
        summary["validation_mode"] = validation_result.validation_mode.value
    if result.admission_result is not None:
        summary["append_admission_verdict"] = (
            result.admission_result.verdict.value
        )

    return summary


def _require_selected_uuid(value: UUID | None, field_name: str) -> UUID:
    if value is None:
        raise ValueError(f"{field_name} is required for receipt mapping")
    return value


def _require_selected_string(value: str | None, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required for receipt mapping")
    return value


def _require_instance(
    value: object,
    expected_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be {expected_type.__name__}")
