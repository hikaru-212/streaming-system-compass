from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from inspect import Parameter, signature
from uuid import UUID

import pytest

import src.compass.runtime.write_side_decision_receipt_mapping as mapping_module
from src.compass.runtime.decision_receipt import (
    DecisionReceiptActor,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlagState,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.write_side_decision_receipt_mapping import (
    map_postgres_write_side_result_to_decision_receipt,
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
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
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


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000401")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000402")
CANDIDATE_ID = "00000000-0000-0000-0000-000000000403"
PRIOR_ACCEPTED_ID = "00000000-0000-0000-0000-000000000404"
OTHER_ID = "00000000-0000-0000-0000-000000000405"

COMMON_EVIDENCE_KEYS = frozenset(
    {
        "technical_status",
        "write_side_outcome",
        "idempotency_verdict",
        "lifecycle_phase",
    }
)
STREAM_EVIDENCE_KEYS = frozenset({"stream_admission_verdict"})
VALIDATION_EVIDENCE_KEYS = frozenset(
    {
        "validation_action",
        "validation_verdict",
        "validation_mode",
    }
)
APPEND_EVIDENCE_KEYS = frozenset({"append_admission_verdict"})


def make_event(
    *,
    event_id: str = CANDIDATE_ID,
    order_id: str = "order-001",
    request_id: str = "request-001",
) -> OrderEvent:
    return OrderEvent(
        event_id=event_id,
        request_id=request_id,
        order_id=order_id,
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        occurred_at_ms=1,
        proof=Proof(
            prev_event_id=None,
            prev_version=0,
            prev_status=OrderStatus.INIT,
        ),
    )


def make_record(
    *,
    accepted_event: OrderEvent | None = None,
    signature_order_id: str = "order-001",
    signature_request_id: str = "request-001",
) -> IdempotencyRecord:
    return IdempotencyRecord(
        signature=RequestSignature(
            request_id=signature_request_id,
            command_type=CommandType.CREATE,
            order_id=signature_order_id,
            amount=Decimal("100.00"),
        ),
        accepted_event=accepted_event
        or make_event(event_id=PRIOR_ACCEPTED_ID),
    )


def make_idempotency(
    verdict: IdempotencyVerdict = IdempotencyVerdict.MISS,
    *,
    record: IdempotencyRecord | None = None,
) -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=verdict,
        reason=f"idempotency {verdict.value}",
        record=record,
    )


def make_validation(
    *,
    candidate_event_id: str = CANDIDATE_ID,
    action: EnforcementAction = EnforcementAction.ALLOW,
    verdict: ValidationVerdict = ValidationVerdict.PASSED,
    metadata: dict[str, object] | None = None,
) -> ValidationDecision:
    return ValidationDecision(
        action=action,
        validation_result=ValidationResult(
            verdict=verdict,
            reason=f"validation {verdict.value}",
            candidate_event_id=candidate_event_id,
            validator_name="FullProofValidator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=1.0,
            io_time_ms=0.0,
            total_time_ms=1.0,
            metadata=metadata or {},
        ),
    )


def make_stream(
    verdict: AdmissionVerdict = AdmissionVerdict.ADMITTED,
    *,
    order_id: str = "order-001",
) -> StreamAdmissionResult:
    return StreamAdmissionResult(
        verdict=verdict,
        reason=f"stream {verdict.value}",
        order_id=order_id,
    )


def make_append(
    verdict: AdmissionVerdict = AdmissionVerdict.ADMITTED,
    *,
    candidate_event_id: str = CANDIDATE_ID,
    accepted_event_id: str | None = CANDIDATE_ID,
) -> AdmissionResult:
    return AdmissionResult(
        verdict=verdict,
        reason=f"append {verdict.value}",
        candidate_event_id=candidate_event_id,
        accepted_event_id=accepted_event_id,
    )


def make_accepted_result() -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=make_event(),
        idempotency_decision=make_idempotency(),
        stream_admission_result=make_stream(),
        validation_decision=make_validation(),
        admission_result=make_append(),
    )


def make_replay_result(
    *,
    candidate_event_id: str | None = None,
) -> PostgresWriteSideResult:
    record = make_record()
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.REPLAY,
        accepted_event=record.accepted_event,
        idempotency_decision=make_idempotency(
            IdempotencyVerdict.REPLAY,
            record=record,
        ),
        validation_decision=(
            make_validation(candidate_event_id=candidate_event_id)
            if candidate_event_id is not None
            else None
        ),
    )


def make_conflict_result(
    *,
    candidate_event_id: str | None = None,
    record: IdempotencyRecord | None = None,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.CONFLICT,
        accepted_event=None,
        idempotency_decision=make_idempotency(
            IdempotencyVerdict.CONFLICT,
            record=record or make_record(),
        ),
        validation_decision=(
            make_validation(candidate_event_id=candidate_event_id)
            if candidate_event_id is not None
            else None
        ),
    )


def make_validation_blocked_result(
    *,
    with_stream: bool,
    candidate_event_id: str = CANDIDATE_ID,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=make_idempotency(),
        stream_admission_result=make_stream() if with_stream else None,
        validation_decision=make_validation(
            candidate_event_id=candidate_event_id,
            action=EnforcementAction.BLOCK,
            verdict=ValidationVerdict.FAILED,
        ),
    )


def make_stream_rejection_result(
    verdict: AdmissionVerdict,
    *,
    candidate_event_id: str | None,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency(),
        stream_admission_result=make_stream(verdict),
        validation_decision=(
            make_validation(candidate_event_id=candidate_event_id)
            if candidate_event_id is not None
            else None
        ),
        admission_result=None,
    )


def make_append_rejection_result(
    verdict: AdmissionVerdict,
    *,
    candidate_event_id: str = CANDIDATE_ID,
    append_candidate_event_id: str | None = None,
    accepted_event_id: str | None = None,
) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=make_idempotency(),
        stream_admission_result=make_stream(),
        validation_decision=make_validation(
            candidate_event_id=candidate_event_id
        ),
        admission_result=make_append(
            verdict,
            candidate_event_id=(
                append_candidate_event_id or candidate_event_id
            ),
            accepted_event_id=accepted_event_id,
        ),
    )


def map_result(result: PostgresWriteSideResult):
    return map_postgres_write_side_result_to_decision_receipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )


def assert_all_flags_not_evaluated(receipt) -> None:
    assert receipt.flags.fallback_required == DecisionReceiptFlagState.NOT_EVALUATED
    assert receipt.flags.rebuild_required == DecisionReceiptFlagState.NOT_EVALUATED
    assert (
        receipt.flags.operator_review_required
        == DecisionReceiptFlagState.NOT_EVALUATED
    )
    assert receipt.flags.retry_candidate == DecisionReceiptFlagState.NOT_EVALUATED


def test_accepted_preserves_semantic_tuple_and_admission_identity() -> None:
    result = make_accepted_result()
    semantic = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    receipt = map_result(result)

    assert receipt.receipt_id == RECEIPT_ID
    assert receipt.outcome_id == OUTCOME_ID
    assert (
        receipt.ok,
        receipt.boundary,
        receipt.category,
        receipt.semantic_code,
        receipt.severity,
        receipt.risk_level,
        receipt.reversibility,
        receipt.reason,
    ) == (
        semantic.ok,
        semantic.boundary,
        semantic.category,
        semantic.semantic_code,
        semantic.severity,
        semantic.risk_level,
        semantic.reversibility,
        semantic.reason,
    )
    assert receipt.evidence_source == DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION
    assert receipt.subject.subject_type == DecisionReceiptSubjectType.ACCEPTED_EVENT
    assert receipt.subject.subject_id == CANDIDATE_ID
    assert receipt.correlation.candidate_event_id == UUID(CANDIDATE_ID)
    assert receipt.correlation.accepted_event_id == UUID(CANDIDATE_ID)
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.ACCEPTED_HISTORY
    )
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
    )
    assert_all_flags_not_evaluated(receipt)


@pytest.mark.parametrize(
    "result",
    [
        make_accepted_result(),
        make_replay_result(),
        make_conflict_result(),
        make_validation_blocked_result(with_stream=True),
        make_stream_rejection_result(
            AdmissionVerdict.LOCK_TIMEOUT,
            candidate_event_id=None,
        ),
        make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
        make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT),
        make_append_rejection_result(AdmissionVerdict.INFRASTRUCTURE_ERROR),
    ],
)
def test_representative_write_side_results_preserve_exact_stage_4a_semantic_tuple(
    result: PostgresWriteSideResult,
) -> None:
    semantic = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )
    receipt = map_result(result)

    assert (
        receipt.ok,
        receipt.boundary,
        receipt.category,
        receipt.semantic_code,
        receipt.severity,
        receipt.risk_level,
        receipt.reversibility,
        receipt.reason,
    ) == (
        semantic.ok,
        semantic.boundary,
        semantic.category,
        semantic.semantic_code,
        semantic.severity,
        semantic.risk_level,
        semantic.reversibility,
        semantic.reason,
    )


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(make_accepted_result(), id="accepted"),
        pytest.param(make_replay_result(), id="replay"),
        pytest.param(make_conflict_result(), id="conflict"),
        pytest.param(
            make_validation_blocked_result(with_stream=False),
            id="validation-blocked",
        ),

        # IN_TRANSACTION-style stream rejection:
        # stream preparation rejects before candidate construction.
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.STALE_WRITE,
                candidate_event_id=None,
            ),
            id="stream-stale-write-before-candidate",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=None,
            ),
            id="stream-lock-timeout-before-candidate",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR,
                candidate_event_id=None,
            ),
            id="stream-infrastructure-error-before-candidate",
        ),

        # PRE_TRANSACTION-style stream rejection:
        # candidate construction and validation precede stream preparation.
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.STALE_WRITE,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="stream-stale-write-after-candidate",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="stream-lock-timeout-after-candidate",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="stream-infrastructure-error-after-candidate",
        ),

        pytest.param(
            make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
            id="append-stale-write",
        ),
        pytest.param(
            make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT),
            id="append-lock-timeout",
        ),
        pytest.param(
            make_append_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR
            ),
            id="append-infrastructure-error",
        ),
    ],
)
def test_write_side_receipt_preserves_stage_4a_technical_status(
    result: PostgresWriteSideResult,
) -> None:
    semantic = map_postgres_write_side_result_to_semantic_outcome(
        outcome_id=OUTCOME_ID,
        result=result,
    )

    receipt = map_result(result)

    assert (
        receipt.evidence_summary["technical_status"]
        == semantic.evidence["technical_status"]
    )


@pytest.mark.parametrize(
    ("candidate_event_id", "expected_candidate"),
    [(None, None), (CANDIDATE_ID, UUID(CANDIDATE_ID))],
)
def test_replay_preserves_prior_accepted_event_without_retry_inference(
    candidate_event_id: str | None,
    expected_candidate: UUID | None,
) -> None:
    receipt = map_result(
        make_replay_result(candidate_event_id=candidate_event_id)
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.ACCEPTED_EVENT
    assert receipt.subject.subject_id == PRIOR_ACCEPTED_ID
    assert receipt.correlation.candidate_event_id == expected_candidate
    assert receipt.correlation.accepted_event_id == UUID(PRIOR_ACCEPTED_ID)
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.ACCEPTED_HISTORY
    )
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    )
    assert_all_flags_not_evaluated(receipt)


@pytest.mark.parametrize(
    ("candidate_event_id", "expected_candidate"),
    [(None, None), (CANDIDATE_ID, UUID(CANDIDATE_ID))],
)
def test_conflict_preserves_prior_history_as_conflict_evidence(
    candidate_event_id: str | None,
    expected_candidate: UUID | None,
) -> None:
    receipt = map_result(
        make_conflict_result(candidate_event_id=candidate_event_id)
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.REQUEST
    assert receipt.subject.subject_id == "request-001"
    assert receipt.correlation.candidate_event_id == expected_candidate
    assert receipt.correlation.accepted_event_id == UUID(PRIOR_ACCEPTED_ID)
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
    )
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
    )
    assert (
        receipt.admission_evidence.disposition
        != EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    )


@pytest.mark.parametrize(
    ("with_stream", "expected_order_id"),
    [(True, "order-001"), (False, None)],
)
def test_validation_blocked_uses_candidate_without_inventing_correlation(
    with_stream: bool,
    expected_order_id: str | None,
) -> None:
    receipt = map_result(
        make_validation_blocked_result(with_stream=with_stream)
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.CANDIDATE_EVENT
    assert receipt.subject.subject_id == CANDIDATE_ID
    assert receipt.correlation.order_id == expected_order_id
    assert receipt.correlation.request_id is None
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY
    )
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED
    )


@pytest.mark.parametrize(
    "verdict",
    [
        AdmissionVerdict.STALE_WRITE,
        AdmissionVerdict.LOCK_TIMEOUT,
        AdmissionVerdict.INFRASTRUCTURE_ERROR,
    ],
)
def test_stream_rejection_before_candidate_uses_order_subject(
    verdict: AdmissionVerdict,
) -> None:
    # STALE_WRITE is a synthetic typed-domain stream fixture, not a claim
    # about current PostgreSQL optimistic stream-preparation behavior.
    receipt = map_result(
        make_stream_rejection_result(
            verdict,
            candidate_event_id=None,
        )
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.ORDER
    assert receipt.subject.subject_id == "order-001"
    assert receipt.correlation.candidate_event_id is None
    assert receipt.correlation.accepted_event_id is None
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
    )
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
    )
    assert_all_flags_not_evaluated(receipt)


@pytest.mark.parametrize(
    "verdict",
    [
        AdmissionVerdict.STALE_WRITE,
        AdmissionVerdict.LOCK_TIMEOUT,
        AdmissionVerdict.INFRASTRUCTURE_ERROR,
    ],
)
def test_non_default_post_validation_stream_rejections_map_to_append_admission_not_reached(
    verdict: AdmissionVerdict,
) -> None:
    # These are synthetic typed-domain contract fixtures. Current PostgreSQL
    # optimistic stream preparation does not produce STALE_WRITE.
    receipt = map_result(
        make_stream_rejection_result(
            verdict,
            candidate_event_id=CANDIDATE_ID,
        )
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.CANDIDATE_EVENT
    assert receipt.correlation.candidate_event_id == UUID(CANDIDATE_ID)
    assert receipt.correlation.accepted_event_id is None
    assert (
        receipt.admission_evidence.disposition
        == EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
    )
    assert (
        receipt.admission_evidence.disposition
        != EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE
    )
    assert_all_flags_not_evaluated(receipt)


@pytest.mark.parametrize(
    ("verdict", "disposition"),
    [
        (
            AdmissionVerdict.STALE_WRITE,
            EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        ),
        (
            AdmissionVerdict.LOCK_TIMEOUT,
            EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE,
        ),
        (
            AdmissionVerdict.INFRASTRUCTURE_ERROR,
            EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE,
        ),
    ],
)
def test_append_rejection_maps_fate_and_leaves_flags_not_evaluated(
    verdict: AdmissionVerdict,
    disposition: EventAdmissionDisposition,
) -> None:
    receipt = map_result(make_append_rejection_result(verdict))

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.CANDIDATE_EVENT
    assert receipt.correlation.candidate_event_id == UUID(CANDIDATE_ID)
    assert receipt.correlation.accepted_event_id is None
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY
    )
    assert receipt.admission_evidence.disposition == disposition
    assert_all_flags_not_evaluated(receipt)
    assert (
        receipt.admission_evidence.disposition
        != EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED
    )


def test_supported_write_side_results_do_not_map_to_commit_outcome_unresolved() -> None:
    results = [
        make_accepted_result(),
        make_replay_result(),
        make_conflict_result(),
        make_validation_blocked_result(with_stream=True),
        make_stream_rejection_result(
            AdmissionVerdict.LOCK_TIMEOUT,
            candidate_event_id=None,
        ),
        make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
        make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT),
        make_append_rejection_result(AdmissionVerdict.INFRASTRUCTURE_ERROR),
    ]

    assert all(
        map_result(result).admission_evidence.disposition
        != EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED
        for result in results
    )


@pytest.mark.parametrize(
    "result",
    [
        make_accepted_result(),
        make_replay_result(),
        make_replay_result(candidate_event_id=CANDIDATE_ID),
        make_conflict_result(),
        make_conflict_result(candidate_event_id=CANDIDATE_ID),
        make_validation_blocked_result(with_stream=True),
        make_validation_blocked_result(with_stream=False),
        make_stream_rejection_result(
            AdmissionVerdict.LOCK_TIMEOUT,
            candidate_event_id=None,
        ),
        make_stream_rejection_result(
            AdmissionVerdict.INFRASTRUCTURE_ERROR,
            candidate_event_id=CANDIDATE_ID,
        ),
        make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
        make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT),
        make_append_rejection_result(AdmissionVerdict.INFRASTRUCTURE_ERROR),
    ],
)
def test_every_supported_write_side_receipt_uses_write_side_admission_evidence(
    result: PostgresWriteSideResult,
) -> None:
    receipt = map_result(result)

    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION
    )
    assert receipt.flags.fallback_required == DecisionReceiptFlagState.NOT_EVALUATED
    assert receipt.flags.rebuild_required == DecisionReceiptFlagState.NOT_EVALUATED


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(
            make_accepted_result(),
            id="accepted",
        ),
        pytest.param(
            make_replay_result(),
            id="pre-candidate-replay",
        ),
        pytest.param(
            make_replay_result(candidate_event_id=CANDIDATE_ID),
            id="post-validation-replay",
        ),
        pytest.param(
            make_conflict_result(),
            id="pre-candidate-conflict",
        ),
        pytest.param(
            make_conflict_result(candidate_event_id=CANDIDATE_ID),
            id="post-validation-conflict",
        ),
        pytest.param(
            make_validation_blocked_result(with_stream=False),
            id="pre-transaction-validation-blocked",
        ),
        pytest.param(
            make_validation_blocked_result(with_stream=True),
            id="in-transaction-validation-blocked",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.STALE_WRITE,
                candidate_event_id=None,
            ),
            id="pre-candidate-stream-stale-write",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=None,
            ),
            id="pre-candidate-stream-lock-timeout",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR,
                candidate_event_id=None,
            ),
            id="pre-candidate-stream-infrastructure-error",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.STALE_WRITE,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="post-validation-stream-stale-write",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="post-validation-stream-lock-timeout",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR,
                candidate_event_id=CANDIDATE_ID,
            ),
            id="post-validation-stream-infrastructure-error",
        ),
        pytest.param(
            make_append_rejection_result(
                AdmissionVerdict.STALE_WRITE,
            ),
            id="append-stale-write",
        ),
        pytest.param(
            make_append_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
            ),
            id="append-lock-timeout",
        ),
        pytest.param(
            make_append_rejection_result(
                AdmissionVerdict.INFRASTRUCTURE_ERROR,
            ),
            id="append-infrastructure-error",
        ),
    ],
)
def test_every_supported_result_shape_leaves_flags_not_evaluated(
    result: PostgresWriteSideResult,
) -> None:
    receipt = map_result(result)

    assert_all_flags_not_evaluated(receipt)


@pytest.mark.parametrize(
    "result",
    [
        replace(
            make_accepted_result(),
            accepted_event=make_event(event_id="not-a-uuid"),
        ),
        replace(
            make_accepted_result(),
            accepted_event=make_event(event_id="   "),
        ),
        make_replay_result(),
        make_validation_blocked_result(
            with_stream=False,
            candidate_event_id="not-a-uuid",
        ),
        make_append_rejection_result(
            AdmissionVerdict.STALE_WRITE,
            append_candidate_event_id="not-a-uuid",
        ),
    ],
)
def test_malformed_authority_bearing_event_ids_fail_closed(
    result: PostgresWriteSideResult,
) -> None:
    if result.outcome == PostgresWriteSideOutcome.REPLAY:
        malformed_record = make_record(
            accepted_event=make_event(event_id="not-a-uuid")
        )
        result = PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.REPLAY,
            accepted_event=malformed_record.accepted_event,
            idempotency_decision=make_idempotency(
                IdempotencyVerdict.REPLAY,
                record=malformed_record,
            ),
        )

    with pytest.raises(ValueError, match="UUID string|Contradictory"):
        map_result(result)


def test_accepted_identity_contradiction_fails_closed() -> None:
    result = replace(
        make_accepted_result(),
        admission_result=make_append(accepted_event_id=OTHER_ID),
    )

    with pytest.raises(
        ValueError,
        match="candidate and accepted event identities must match",
    ):
        map_result(result)


def test_validation_and_append_candidate_contradiction_fails_closed() -> None:
    result = make_append_rejection_result(
        AdmissionVerdict.STALE_WRITE,
        append_candidate_event_id=OTHER_ID,
    )

    with pytest.raises(ValueError, match="Contradictory candidate_event_id"):
        map_result(result)


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            make_record(signature_order_id="different-order"),
            "Contradictory order_id",
        ),
        (
            make_record(signature_request_id="different-request"),
            "Contradictory request_id",
        ),
    ],
)
def test_record_signature_and_accepted_event_contradictions_fail_closed(
    record: IdempotencyRecord,
    message: str,
) -> None:
    result = make_conflict_result(record=record)

    with pytest.raises(ValueError, match=message):
        map_result(result)


def test_rejected_append_cannot_carry_accepted_identity() -> None:
    result = make_append_rejection_result(
        AdmissionVerdict.LOCK_TIMEOUT,
        accepted_event_id=OTHER_ID,
    )

    with pytest.raises(
        ValueError,
        match="must not carry accepted_event_id",
    ):
        map_result(result)


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            replace(make_accepted_result(), accepted_event=None),
            "requires accepted_event",
        ),
        (
            replace(make_accepted_result(), admission_result=None),
            "requires admitted append evidence",
        ),
        (
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.REPLAY,
                accepted_event=None,
                idempotency_decision=make_idempotency(
                    IdempotencyVerdict.REPLAY
                ),
            ),
            "requires an accepted idempotency record",
        ),
        (
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.CONFLICT,
                accepted_event=None,
                idempotency_decision=make_idempotency(
                    IdempotencyVerdict.CONFLICT
                ),
            ),
            "requires an accepted idempotency record",
        ),
        (
            replace(
                make_validation_blocked_result(with_stream=False),
                validation_decision=None,
            ),
            "requires validation_decision",
        ),
        (
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                accepted_event=None,
                idempotency_decision=make_idempotency(),
            ),
            "requires stream admission evidence",
        ),
        (
            replace(
                make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
                stream_admission_result=make_stream(
                    AdmissionVerdict.LOCK_TIMEOUT
                ),
            ),
            "requires admitted stream evidence",
        ),
        (
            replace(
                make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
                admission_result=make_append(),
            ),
            "cannot carry admitted append evidence",
        ),
    ],
)
def test_impossible_lifecycle_shapes_are_rejected(
    result: PostgresWriteSideResult,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        map_result(result)


def test_outcome_and_idempotency_verdict_must_match() -> None:
    result = replace(
        make_accepted_result(),
        idempotency_decision=make_idempotency(
            IdempotencyVerdict.REPLAY,
            record=make_record(),
        ),
    )

    with pytest.raises(ValueError, match="requires idempotency verdict miss"):
        map_result(result)


def test_invalid_outcome_type_is_rejected() -> None:
    result = PostgresWriteSideResult(
        outcome="ACCEPTED",  # type: ignore[arg-type]
        accepted_event=None,
        idempotency_decision=make_idempotency(),
    )

    with pytest.raises(TypeError, match="result.outcome"):
        map_result(result)


def test_evidence_summary_is_compact_typed_vocabulary_and_cost_is_not_derived() -> None:
    result = make_append_rejection_result(
        AdmissionVerdict.INFRASTRUCTURE_ERROR
    )
    result.validation_decision.validation_result.metadata.update(
        {
            "order_id": "metadata-order",
            "request_payload": {"amount": "999.00"},
            "poison": "must-not-copy",
        }
    )

    receipt = map_result(result)

    assert dict(receipt.evidence_summary) == {
        "technical_status": "WRITE_SIDE_INFRASTRUCTURE_ERROR",
        "write_side_outcome": "ADMISSION_REJECTED",
        "idempotency_verdict": "miss",
        "lifecycle_phase": "APPEND_ADMISSION",
        "stream_admission_verdict": "ADMITTED",
        "validation_action": "allow",
        "validation_verdict": "passed",
        "validation_mode": "strict",
        "append_admission_verdict": "INFRASTRUCTURE_ERROR",
    }
    assert set(receipt.evidence_summary) <= {
        "technical_status",
        "write_side_outcome",
        "idempotency_verdict",
        "lifecycle_phase",
        "stream_admission_verdict",
        "validation_action",
        "validation_verdict",
        "validation_mode",
        "append_admission_verdict",
    }
    assert receipt.metadata == {}
    assert receipt.actor == DecisionReceiptActor()
    assert receipt.cost_summary == DecisionReceiptCostSummary()
    assert "PostgresWriteSideResult" not in repr(receipt.evidence_summary)
    assert "OrderEvent" not in repr(receipt.evidence_summary)
    assert "poison" not in receipt.evidence_summary


@pytest.mark.parametrize(
    ("result", "technical_status", "lifecycle_phase"),
    [
        (
            make_accepted_result(),
            "WRITE_SIDE_ACCEPTED",
            "ACCEPTED_HISTORY",
        ),
        (
            make_replay_result(),
            "IDEMPOTENT_REPLAY",
            "IDEMPOTENCY_CHECK",
        ),
        (
            make_conflict_result(),
            "IDEMPOTENCY_CONFLICT",
            "IDEMPOTENCY_CHECK",
        ),
        (
            make_validation_blocked_result(with_stream=False),
            "COMPASS_VALIDATION_BLOCKED",
            "VALIDATION",
        ),
        (
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=None,
            ),
            "LOCK_TIMEOUT",
            "STREAM_PREPARATION",
        ),
        (
            make_append_rejection_result(AdmissionVerdict.STALE_WRITE),
            "CONCURRENT_STATE_STALENESS",
            "APPEND_ADMISSION",
        ),
    ],
)
def test_common_evidence_summary_values_follow_typed_lifecycle(
    result: PostgresWriteSideResult,
    technical_status: str,
    lifecycle_phase: str,
) -> None:
    summary = map_result(result).evidence_summary

    assert summary["technical_status"] == technical_status
    assert summary["write_side_outcome"] == result.outcome.value
    assert (
        summary["idempotency_verdict"]
        == result.idempotency_decision.verdict.value
    )
    assert summary["lifecycle_phase"] == lifecycle_phase


@pytest.mark.parametrize(
    ("result", "expected_keys"),
    [
        pytest.param(
            make_accepted_result(),
            (
                COMMON_EVIDENCE_KEYS
                | STREAM_EVIDENCE_KEYS
                | VALIDATION_EVIDENCE_KEYS
                | APPEND_EVIDENCE_KEYS
            ),
            id="accepted",
        ),
        pytest.param(
            make_replay_result(),
            COMMON_EVIDENCE_KEYS,
            id="early-replay",
        ),
        pytest.param(
            make_replay_result(candidate_event_id=CANDIDATE_ID),
            COMMON_EVIDENCE_KEYS | VALIDATION_EVIDENCE_KEYS,
            id="post-validation-replay",
        ),
        pytest.param(
            make_conflict_result(),
            COMMON_EVIDENCE_KEYS,
            id="early-conflict",
        ),
        pytest.param(
            make_conflict_result(candidate_event_id=CANDIDATE_ID),
            COMMON_EVIDENCE_KEYS | VALIDATION_EVIDENCE_KEYS,
            id="post-validation-conflict",
        ),
        pytest.param(
            make_validation_blocked_result(with_stream=False),
            COMMON_EVIDENCE_KEYS | VALIDATION_EVIDENCE_KEYS,
            id="pre-transaction-validation-blocked",
        ),
        pytest.param(
            make_validation_blocked_result(with_stream=True),
            (
                COMMON_EVIDENCE_KEYS
                | STREAM_EVIDENCE_KEYS
                | VALIDATION_EVIDENCE_KEYS
            ),
            id="in-transaction-validation-blocked",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=None,
            ),
            COMMON_EVIDENCE_KEYS | STREAM_EVIDENCE_KEYS,
            id="pre-candidate-stream-rejection",
        ),
        pytest.param(
            make_stream_rejection_result(
                AdmissionVerdict.LOCK_TIMEOUT,
                candidate_event_id=CANDIDATE_ID,
            ),
            (
                COMMON_EVIDENCE_KEYS
                | STREAM_EVIDENCE_KEYS
                | VALIDATION_EVIDENCE_KEYS
            ),
            id="post-validation-stream-rejection",
        ),
        pytest.param(
            make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT),
            (
                COMMON_EVIDENCE_KEYS
                | STREAM_EVIDENCE_KEYS
                | VALIDATION_EVIDENCE_KEYS
                | APPEND_EVIDENCE_KEYS
            ),
            id="append-rejection",
        ),
    ],
)
def test_evidence_summary_has_exact_keys_for_lifecycle_shape(
    result: PostgresWriteSideResult,
    expected_keys: frozenset[str],
) -> None:
    assert set(map_result(result).evidence_summary) == expected_keys


def test_public_wrapper_signature_is_exact_and_keyword_only() -> None:
    parameters = signature(
        map_postgres_write_side_result_to_decision_receipt
    ).parameters

    assert tuple(parameters) == ("receipt_id", "outcome_id", "result")
    assert all(
        parameter.kind == Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert set(parameters).isdisjoint(
        {
            "metadata",
            "context",
            "evidence",
            "actor",
            "cost",
            "cost_summary",
            "policy",
            "strategy",
            "retry",
            "serialization",
            "persistence",
        }
    )


def test_semantic_context_and_evidence_are_not_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = make_accepted_result()
    original_adapter = (
        mapping_module.map_postgres_write_side_result_to_semantic_outcome
    )

    def adapter_with_poison(*, outcome_id, result):
        semantic = original_adapter(outcome_id=outcome_id, result=result)
        return replace(
            semantic,
            context={"poison_context": "must-not-copy"},
            evidence={"poison_evidence": "must-not-copy"},
        )

    monkeypatch.setattr(
        mapping_module,
        "map_postgres_write_side_result_to_semantic_outcome",
        adapter_with_poison,
    )

    receipt = map_result(result)

    assert "poison_context" not in receipt.evidence_summary
    assert "poison_evidence" not in receipt.evidence_summary
    assert receipt.metadata == {}


def test_wrapper_has_no_side_effect_or_expanded_public_surface() -> None:
    result = make_append_rejection_result(AdmissionVerdict.LOCK_TIMEOUT)
    original = deepcopy(result)

    receipt = map_result(result)

    assert result == original
    assert_all_flags_not_evaluated(receipt)
    assert mapping_module.__all__ == [
        "map_postgres_write_side_result_to_decision_receipt"
    ]
    assert not any(
        name in mapping_module.__dict__
        for name in (
            "execute_retry",
            "authorize_retry",
            "serialize_receipt",
            "persist_receipt",
            "select_policy",
            "select_strategy",
        )
    )
