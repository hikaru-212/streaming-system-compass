from dataclasses import FrozenInstanceError, fields
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlagState,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.json_types import (
    MAX_JSON_DEPTH,
    ensure_json_object,
    ensure_json_value,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000201")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000101")
CANDIDATE_EVENT_ID = UUID("00000000-0000-0000-0000-000000000301")
ACCEPTED_EVENT_ID = UUID("00000000-0000-0000-0000-000000000302")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000401")
FLAG_FIELD_NAMES = (
    "fallback_required",
    "rebuild_required",
    "operator_review_required",
    "retry_candidate",
)


def make_decision_receipt(**overrides: object) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": RECEIPT_ID,
        "outcome_id": OUTCOME_ID,
        "ok": False,
        "boundary": SemanticBoundary.SNAPSHOT_TRUST,
        "category": SemanticOutcomeCategory.DRIFT,
        "semantic_code": SemanticOutcomeCode.DRIFT_DETECTED,
        "severity": SemanticSeverity.ERROR,
        "risk_level": SemanticRiskLevel.HIGH,
        "reversibility": SemanticReversibility.REBUILDABLE,
        "reason": "Snapshot-assisted reconstruction diverged from authority.",
        "evidence_source": DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
        "subject": DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id="order-001",
        ),
        "correlation": DecisionReceiptCorrelation(
            order_id="order-001",
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
        ),
        "actor": DecisionReceiptActor(
            actor_id="projection-worker",
            actor_role="runtime",
            runtime_role="compass_projection_worker",
        ),
        "cost_summary": DecisionReceiptCostSummary(
            elapsed_ms=12,
            replay_elapsed_ms=8,
        ),
        "flags": DecisionReceiptFlags(
            rebuild_required=DecisionReceiptFlagState.TRUE
        ),
        "evidence_summary": {
            "technical_status": "SNAPSHOT_ASSISTED_DRIFT",
            "snapshot_state": {"status": "PAID", "paid_amount": "100.00"},
            "authority_state": {"status": "CREATED", "paid_amount": "0.00"},
            "tail_event_count": 2,
        },
        "metadata": {"source": "unit-test"},
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def test_decision_receipt_preserves_required_semantic_summary() -> None:
    receipt = make_decision_receipt()

    assert receipt.receipt_id == RECEIPT_ID
    assert receipt.outcome_id == OUTCOME_ID
    assert receipt.ok is False
    assert receipt.boundary == SemanticBoundary.SNAPSHOT_TRUST
    assert receipt.category == SemanticOutcomeCategory.DRIFT
    assert receipt.semantic_code == SemanticOutcomeCode.DRIFT_DETECTED
    assert receipt.severity == SemanticSeverity.ERROR
    assert receipt.risk_level == SemanticRiskLevel.HIGH
    assert receipt.reversibility == SemanticReversibility.REBUILDABLE
    assert (
        receipt.reason
        == "Snapshot-assisted reconstruction diverged from authority."
    )
    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH
    )


def test_decision_receipt_preserves_subject_correlation_actor_cost_and_flags() -> None:
    receipt = make_decision_receipt()

    assert receipt.subject == DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.ORDER,
        subject_id="order-001",
    )
    assert receipt.correlation == DecisionReceiptCorrelation(
        order_id="order-001",
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
    )
    assert receipt.actor == DecisionReceiptActor(
        actor_id="projection-worker",
        actor_role="runtime",
        runtime_role="compass_projection_worker",
    )
    assert receipt.cost_summary == DecisionReceiptCostSummary(
        elapsed_ms=12,
        replay_elapsed_ms=8,
    )
    assert receipt.flags == DecisionReceiptFlags(
        rebuild_required=DecisionReceiptFlagState.TRUE
    )


def test_decision_receipt_defaults_to_empty_supporting_contracts() -> None:
    receipt = DecisionReceipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        ok=True,
        boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
        reason="Runtime evidence is semantically valid.",
        evidence_source=DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    )

    assert receipt.subject == DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.UNKNOWN
    )
    assert receipt.correlation == DecisionReceiptCorrelation()
    assert receipt.actor == DecisionReceiptActor()
    assert receipt.cost_summary == DecisionReceiptCostSummary()
    assert receipt.flags == DecisionReceiptFlags()
    assert receipt.admission_evidence is None
    assert receipt.evidence_summary == {}
    assert receipt.metadata == {}


def test_decision_receipt_evidence_summary_and_metadata_are_frozen() -> None:
    evidence_summary = {
        "technical_status": "SNAPSHOT_ASSISTED_DRIFT",
        "nested": {"values": [1, 2, 3]},
    }
    metadata = {"tags": ["stage-4b", "receipt"]}

    receipt = make_decision_receipt(
        evidence_summary=evidence_summary,
        metadata=metadata,
    )

    evidence_summary["nested"]["values"].append(4)
    metadata["tags"].append("mutated")

    assert receipt.evidence_summary["nested"]["values"] == (1, 2, 3)
    assert receipt.metadata["tags"] == ("stage-4b", "receipt")

    with pytest.raises(TypeError):
        receipt.evidence_summary["new_key"] = "new-value"  # type: ignore[index]

    with pytest.raises(TypeError):
        receipt.metadata["new_key"] = "new-value"  # type: ignore[index]

    with pytest.raises(TypeError):
        receipt.evidence_summary["nested"]["new_key"] = "value"  # type: ignore[index]


def test_decision_receipt_is_frozen() -> None:
    receipt = make_decision_receipt()

    with pytest.raises(FrozenInstanceError):
        receipt.reason = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        ("receipt_id", "receipt-001", "receipt_id must be UUID"),
        ("outcome_id", "outcome-001", "outcome_id must be UUID"),
        ("ok", "false", "ok must be bool"),
        ("boundary", "SNAPSHOT_TRUST", "boundary must be SemanticBoundary"),
        ("category", "DRIFT", "category must be SemanticOutcomeCategory"),
        (
            "semantic_code",
            "DRIFT_DETECTED",
            "semantic_code must be SemanticOutcomeCode",
        ),
        ("severity", "ERROR", "severity must be SemanticSeverity"),
        ("risk_level", "HIGH", "risk_level must be SemanticRiskLevel"),
        (
            "reversibility",
            "REBUILDABLE",
            "reversibility must be SemanticReversibility",
        ),
        (
            "evidence_source",
            "SNAPSHOT_ASSISTED_PATH",
            "evidence_source must be DecisionReceiptEvidenceSource",
        ),
        (
            "subject",
            "order-001",
            "subject must be DecisionReceiptSubject",
        ),
        (
            "correlation",
            {"order_id": "order-001"},
            "correlation must be DecisionReceiptCorrelation",
        ),
        (
            "actor",
            {"actor_id": "worker"},
            "actor must be DecisionReceiptActor",
        ),
        (
            "cost_summary",
            {"elapsed_ms": 1},
            "cost_summary must be DecisionReceiptCostSummary",
        ),
        (
            "flags",
            {"rebuild_required": True},
            "flags must be DecisionReceiptFlags",
        ),
        (
            "admission_evidence",
            {"disposition": "ADMITTED_TO_ACCEPTED_HISTORY"},
            "admission_evidence must be DecisionReceiptAdmissionEvidence",
        ),
    ],
)
def test_decision_receipt_rejects_invalid_field_types(
    field_name: str,
    bad_value: object,
    expected_message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=expected_message):
        make_decision_receipt(**{field_name: bad_value})


@pytest.mark.parametrize("reason", ["", "   "])
def test_decision_receipt_rejects_blank_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        make_decision_receipt(reason=reason)


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_non_mapping_json_objects(
    field_name: str,
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be a mapping"):
        make_decision_receipt(**{field_name: ["not", "a", "mapping"]})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_non_json_safe_objects(field_name: str) -> None:
    with pytest.raises(TypeError, match=f"{field_name}.bad must be JSON-safe"):
        make_decision_receipt(**{field_name: {"bad": object()}})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_non_finite_float_values(
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field_name}.bad must be a finite JSON number",
    ):
        make_decision_receipt(**{field_name: {"bad": float("nan")}})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_non_string_json_keys(field_name: str) -> None:
    with pytest.raises(TypeError, match=f"{field_name} keys must be strings"):
        make_decision_receipt(**{field_name: {1: "bad-key"}})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_empty_json_keys(field_name: str) -> None:
    with pytest.raises(
        ValueError,
        match=f"{field_name} keys must be non-empty strings",
    ):
        make_decision_receipt(**{field_name: {"": "bad-key"}})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_decision_receipt_rejects_values_deeper_than_max_json_depth(
    field_name: str,
) -> None:
    nested: dict[str, object] = {"leaf": "value"}

    for _ in range(MAX_JSON_DEPTH + 1):
        nested = {"nested": nested}

    with pytest.raises(
        ValueError,
        match=f"{field_name}.*exceeds maximum JSON depth of {MAX_JSON_DEPTH}",
    ):
        make_decision_receipt(**{field_name: nested})


def test_json_object_rejects_circular_reference_through_depth_limit() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(
        ValueError,
        match=f"payload.*exceeds maximum JSON depth of {MAX_JSON_DEPTH}",
    ):
        ensure_json_object(payload, field_name="payload")


def test_ensure_json_object_accepts_and_freezes_json_safe_values() -> None:
    payload = {
        "string": "value",
        "int": 1,
        "float": 1.5,
        "bool": True,
        "none": None,
        "list": [1, "two", False],
        "tuple": ("a", "b"),
        "mapping": {"nested": "value"},
    }

    frozen = ensure_json_object(payload, field_name="payload")

    assert frozen == {
        "string": "value",
        "int": 1,
        "float": 1.5,
        "bool": True,
        "none": None,
        "list": (1, "two", False),
        "tuple": ("a", "b"),
        "mapping": {"nested": "value"},
    }

    with pytest.raises(TypeError):
        frozen["new_key"] = "new-value"  # type: ignore[index]

    with pytest.raises(TypeError):
        frozen["mapping"]["nested"] = "mutated"  # type: ignore[index]


@pytest.mark.parametrize(
    ("value", "expected_message"),
    [
        (Decimal("1.00"), "value must be JSON-safe"),
        (datetime(2026, 1, 1), "value must be JSON-safe"),
        (UUID("00000000-0000-0000-0000-000000000999"), "value must be JSON-safe"),
        ({1, 2, 3}, "value must be JSON-safe"),
        (lambda: None, "value must be JSON-safe"),
        (float("inf"), "value must be a finite JSON number"),
    ],
)
def test_ensure_json_value_rejects_non_json_safe_values(
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=expected_message):
        ensure_json_value(value)


def test_decision_receipt_subject_rejects_invalid_values() -> None:
    with pytest.raises(
        TypeError,
        match="subject_type must be DecisionReceiptSubjectType",
    ):
        DecisionReceiptSubject(subject_type="ORDER")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="subject_id must be a non-empty string"):
        DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id="",
        )


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        ("order_id", "", "order_id must be a non-empty string"),
        ("request_id", "   ", "request_id must be a non-empty string"),
        (
            "candidate_event_id",
            "candidate-event",
            "candidate_event_id must be UUID or None",
        ),
        (
            "accepted_event_id",
            "accepted-event",
            "accepted_event_id must be UUID or None",
        ),
        ("snapshot_id", "snapshot", "snapshot_id must be UUID or None"),
        (
            "source_global_position",
            "1",
            "source_global_position must be int or None",
        ),
        (
            "identity_source",
            "ACCEPTED_HISTORY",
            "identity_source must be DecisionReceiptIdentitySource",
        ),
    ],
)
def test_decision_receipt_correlation_rejects_invalid_values(
    field_name: str,
    bad_value: object,
    expected_message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=expected_message):
        DecisionReceiptCorrelation(**{field_name: bad_value})


def test_decision_receipt_correlation_rejects_negative_global_position() -> None:
    with pytest.raises(
        ValueError,
        match="source_global_position must be non-negative",
    ):
        DecisionReceiptCorrelation(source_global_position=-1)


@pytest.mark.parametrize("bad_value", [True, False])
def test_decision_receipt_correlation_rejects_bool_global_position(
    bad_value: bool,
) -> None:
    with pytest.raises(
        TypeError,
        match="source_global_position must be int or None",
    ):
        DecisionReceiptCorrelation(source_global_position=bad_value)


def test_decision_receipt_correlation_can_mark_candidate_event_identity() -> None:
    correlation = DecisionReceiptCorrelation(
        order_id="order-001",
        request_id="request-001",
        candidate_event_id=CANDIDATE_EVENT_ID,
        identity_source=DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY,
    )

    assert correlation.order_id == "order-001"
    assert correlation.request_id == "request-001"
    assert correlation.candidate_event_id == CANDIDATE_EVENT_ID
    assert correlation.accepted_event_id is None
    assert (
        correlation.identity_source
        == DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY
    )


def test_decision_receipt_correlation_can_mark_write_side_correlation() -> None:
    correlation = DecisionReceiptCorrelation(
        order_id="order-001",
        request_id="request-001",
        identity_source=DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION,
    )

    assert correlation.order_id == "order-001"
    assert correlation.request_id == "request-001"
    assert (
        correlation.identity_source
        == DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
    )


def test_decision_receipt_correlation_can_mark_accepted_history_identity() -> None:
    correlation = DecisionReceiptCorrelation(
        order_id="order-001",
        request_id="request-001",
        accepted_event_id=ACCEPTED_EVENT_ID,
        identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
    )

    assert correlation.order_id == "order-001"
    assert correlation.request_id == "request-001"
    assert correlation.candidate_event_id is None
    assert correlation.accepted_event_id == ACCEPTED_EVENT_ID
    assert correlation.identity_source == DecisionReceiptIdentitySource.ACCEPTED_HISTORY



def test_admission_evidence_rejects_raw_disposition_string() -> None:
    with pytest.raises(TypeError, match="disposition must be EventAdmissionDisposition"):
        DecisionReceiptAdmissionEvidence(
            disposition="ADMITTED_TO_ACCEPTED_HISTORY"  # type: ignore[arg-type]
        )


def test_admitted_event_preserves_identity_in_accepted_history() -> None:
    receipt = make_decision_receipt(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(CANDIDATE_EVENT_ID),
        ),
        correlation=DecisionReceiptCorrelation(
            order_id="order-001",
            request_id="request-001",
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=CANDIDATE_EVENT_ID,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
        ),
    )
    assert receipt.correlation.accepted_event_id == CANDIDATE_EVENT_ID


def test_admitted_event_rejects_changed_accepted_event_identity() -> None:
    with pytest.raises(ValueError, match="candidate_event_id and accepted_event_id must match"):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=CANDIDATE_EVENT_ID,
                accepted_event_id=ACCEPTED_EVENT_ID,
                identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
            ),
        )


@pytest.mark.parametrize(
    ("candidate_event_id", "accepted_event_id", "expected_message"),
    [
        (
            None,
            ACCEPTED_EVENT_ID,
            "candidate_event_id is required when an event is admitted",
        ),
        (
            CANDIDATE_EVENT_ID,
            None,
            "accepted_event_id is required when an event is admitted",
        ),
    ],
)
def test_admitted_event_still_requires_both_event_identities(
    candidate_event_id: UUID | None,
    accepted_event_id: UUID | None,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=candidate_event_id,
                accepted_event_id=accepted_event_id,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
            ),
        )


def test_idempotent_replay_can_reference_existing_accepted_event() -> None:
    receipt = make_decision_receipt(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(ACCEPTED_EVENT_ID),
        ),
        correlation=DecisionReceiptCorrelation(
            order_id="order-001",
            request_id="request-001",
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=ACCEPTED_EVENT_ID,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
        ),
    )
    assert receipt.correlation.accepted_event_id == ACCEPTED_EVENT_ID


def test_early_idempotent_replay_does_not_require_candidate_event() -> None:
    receipt = make_decision_receipt(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(ACCEPTED_EVENT_ID),
        ),
        correlation=DecisionReceiptCorrelation(
            order_id="order-001",
            request_id="request-001",
            candidate_event_id=None,
            accepted_event_id=ACCEPTED_EVENT_ID,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
        ),
    )

    assert receipt.correlation.candidate_event_id is None
    assert receipt.correlation.accepted_event_id == ACCEPTED_EVENT_ID
    assert receipt.admission_evidence == DecisionReceiptAdmissionEvidence(
        disposition=EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    )


def test_idempotent_replay_requires_existing_accepted_event() -> None:
    with pytest.raises(
        ValueError,
        match="accepted_event_id is required for an idempotent replay match",
    ):
        make_decision_receipt(
            evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
            subject=DecisionReceiptSubject(
                subject_type=DecisionReceiptSubjectType.REQUEST,
                subject_id="request-001",
            ),
            correlation=DecisionReceiptCorrelation(
                order_id="order-001",
                request_id="request-001",
                candidate_event_id=None,
                accepted_event_id=None,
                identity_source=(
                    DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION
                ),
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=(
                    EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
                )
            ),
        )


def test_early_idempotency_conflict_preserves_prior_accepted_event() -> None:
    receipt = make_decision_receipt(
        correlation=DecisionReceiptCorrelation(
            request_id="request-001",
            candidate_event_id=None,
            accepted_event_id=ACCEPTED_EVENT_ID,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=(
                EventAdmissionDisposition
                .IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
            )
        ),
    )

    assert receipt.correlation.candidate_event_id is None
    assert receipt.correlation.accepted_event_id == ACCEPTED_EVENT_ID


def test_post_validation_idempotency_conflict_preserves_distinct_identities() -> None:
    receipt = make_decision_receipt(
        correlation=DecisionReceiptCorrelation(
            request_id="request-001",
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=ACCEPTED_EVENT_ID,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=(
                EventAdmissionDisposition
                .IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
            )
        ),
    )

    assert receipt.correlation.candidate_event_id == CANDIDATE_EVENT_ID
    assert receipt.correlation.accepted_event_id == ACCEPTED_EVENT_ID
    assert CANDIDATE_EVENT_ID != ACCEPTED_EVENT_ID


def test_idempotency_conflict_requires_prior_accepted_event() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "accepted_event_id is required for an idempotency conflict "
            "with accepted history"
        ),
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=CANDIDATE_EVENT_ID,
                accepted_event_id=None,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=(
                    EventAdmissionDisposition
                    .IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
                )
            ),
        )


def test_idempotency_conflict_disposition_is_distinct_from_replay() -> None:
    conflict = EventAdmissionDisposition.IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY

    assert conflict != EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    assert conflict.value == "IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY"


@pytest.mark.parametrize(
    "disposition",
    [
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED,
    ],
)
def test_non_accepted_candidate_requires_candidate_without_accepted_event(
    disposition: EventAdmissionDisposition,
) -> None:
    receipt = make_decision_receipt(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.CANDIDATE_EVENT,
            subject_id=str(CANDIDATE_EVENT_ID),
        ),
        correlation=DecisionReceiptCorrelation(
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=None,
            identity_source=DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(disposition=disposition),
    )
    assert receipt.correlation.accepted_event_id is None


@pytest.mark.parametrize(
    "disposition",
    [
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED,
    ],
)
def test_existing_candidate_only_dispositions_still_require_candidate(
    disposition: EventAdmissionDisposition,
) -> None:
    with pytest.raises(
        ValueError,
        match="candidate_event_id is required after a candidate event exists",
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=None,
                accepted_event_id=None,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=disposition
            ),
        )


@pytest.mark.parametrize(
    "disposition",
    [
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED,
    ],
)
def test_existing_candidate_only_dispositions_still_reject_accepted_event(
    disposition: EventAdmissionDisposition,
) -> None:
    with pytest.raises(
        ValueError,
        match="accepted_event_id must be None without authoritative",
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=CANDIDATE_EVENT_ID,
                accepted_event_id=ACCEPTED_EVENT_ID,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=disposition
            ),
        )


def test_append_technical_failure_requires_candidate_without_accepted_event() -> None:
    receipt = make_decision_receipt(
        correlation=DecisionReceiptCorrelation(
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=None,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE
        ),
    )

    assert receipt.correlation.candidate_event_id == CANDIDATE_EVENT_ID
    assert receipt.correlation.accepted_event_id is None


def test_append_technical_failure_rejects_missing_candidate() -> None:
    with pytest.raises(
        ValueError,
        match="candidate_event_id is required after a candidate event exists",
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE
            ),
        )


def test_append_technical_failure_rejects_accepted_event() -> None:
    with pytest.raises(
        ValueError,
        match="accepted_event_id must be None without authoritative",
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=CANDIDATE_EVENT_ID,
                accepted_event_id=ACCEPTED_EVENT_ID,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE
            ),
        )


def test_append_admission_not_reached_without_candidate_is_valid() -> None:
    receipt = make_decision_receipt(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.REQUEST,
            subject_id="request-001",
        ),
        correlation=DecisionReceiptCorrelation(
            request_id="request-001",
            identity_source=DecisionReceiptIdentitySource.WRITE_SIDE_CORRELATION,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
        ),
    )
    assert receipt.correlation.candidate_event_id is None
    assert receipt.correlation.accepted_event_id is None


def test_append_admission_not_reached_with_candidate_is_valid() -> None:
    receipt = make_decision_receipt(
        correlation=DecisionReceiptCorrelation(
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=None,
        ),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
        ),
    )

    assert receipt.correlation.candidate_event_id == CANDIDATE_EVENT_ID
    assert receipt.correlation.accepted_event_id is None


@pytest.mark.parametrize("candidate_event_id", [None, CANDIDATE_EVENT_ID])
def test_append_admission_not_reached_rejects_accepted_event(
    candidate_event_id: UUID | None,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "accepted_event_id must be None when append admission was not "
            "reached"
        ),
    ):
        make_decision_receipt(
            correlation=DecisionReceiptCorrelation(
                candidate_event_id=candidate_event_id,
                accepted_event_id=ACCEPTED_EVENT_ID,
            ),
            admission_evidence=DecisionReceiptAdmissionEvidence(
                disposition=(
                    EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED
                )
            ),
        )


def test_event_admission_disposition_enum_member_set_is_stable() -> None:
    assert {item.value for item in EventAdmissionDisposition} == {
        "ADMITTED_TO_ACCEPTED_HISTORY",
        "MATCHED_EXISTING_ACCEPTED_EVENT",
        "IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY",
        "SEMANTIC_ADMISSION_REJECTED",
        "APPEND_CONCURRENCY_CONFLICT",
        "APPEND_TECHNICAL_FAILURE",
        "COMMIT_OUTCOME_UNRESOLVED",
        "APPEND_ADMISSION_NOT_REACHED",
        "UNKNOWN",
    }

@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        ("actor_id", "", "actor_id must be a non-empty string"),
        ("actor_role", "   ", "actor_role must be a non-empty string"),
        ("runtime_role", "", "runtime_role must be a non-empty string"),
    ],
)
def test_decision_receipt_actor_rejects_blank_values(
    field_name: str,
    bad_value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        DecisionReceiptActor(**{field_name: bad_value})


@pytest.mark.parametrize(
    "field_name",
    [
        "elapsed_ms",
        "validation_elapsed_ms",
        "replay_elapsed_ms",
        "transaction_elapsed_ms",
        "lock_wait_ms",
    ],
)
def test_decision_receipt_cost_summary_rejects_non_int_values(
    field_name: str,
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be int or None"):
        DecisionReceiptCostSummary(**{field_name: "1"})


@pytest.mark.parametrize(
    "field_name",
    [
        "elapsed_ms",
        "validation_elapsed_ms",
        "replay_elapsed_ms",
        "transaction_elapsed_ms",
        "lock_wait_ms",
    ],
)
@pytest.mark.parametrize("bad_value", [True, False])
def test_decision_receipt_cost_summary_rejects_bool_values(
    field_name: str,
    bad_value: bool,
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be int or None"):
        DecisionReceiptCostSummary(**{field_name: bad_value})


@pytest.mark.parametrize(
    "field_name",
    [
        "elapsed_ms",
        "validation_elapsed_ms",
        "replay_elapsed_ms",
        "transaction_elapsed_ms",
        "lock_wait_ms",
    ],
)
def test_decision_receipt_cost_summary_rejects_negative_values(
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be non-negative"):
        DecisionReceiptCostSummary(**{field_name: -1})


def test_decision_receipt_cost_summary_does_not_include_generic_extra_field() -> None:
    field_names = {field.name for field in fields(DecisionReceiptCostSummary)}

    assert "extra" not in field_names
    assert "extension_summary" not in field_names
    assert "future_cost_evidence" not in field_names


def test_decision_receipt_flag_state_member_set_is_stable() -> None:
    assert {item.value for item in DecisionReceiptFlagState} == {
        "TRUE",
        "FALSE",
        "NOT_EVALUATED",
    }


def test_decision_receipt_flags_default_every_field_to_not_evaluated() -> None:
    flags = DecisionReceiptFlags()

    assert all(
        getattr(flags, field_name) == DecisionReceiptFlagState.NOT_EVALUATED
        for field_name in FLAG_FIELD_NAMES
    )


@pytest.mark.parametrize("field_name", FLAG_FIELD_NAMES)
@pytest.mark.parametrize(
    "state",
    [
        DecisionReceiptFlagState.TRUE,
        DecisionReceiptFlagState.FALSE,
        DecisionReceiptFlagState.NOT_EVALUATED,
    ],
)
def test_decision_receipt_flags_accept_explicit_states(
    field_name: str,
    state: DecisionReceiptFlagState,
) -> None:
    flags = DecisionReceiptFlags(**{field_name: state})

    assert getattr(flags, field_name) == state


@pytest.mark.parametrize("field_name", FLAG_FIELD_NAMES)
@pytest.mark.parametrize(
    "bad_value",
    [
        True,
        False,
        None,
        "TRUE",
        "FALSE",
        "NOT_EVALUATED",
        0,
        1,
        DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    ],
)
def test_decision_receipt_flags_reject_non_flag_states(
    field_name: str,
    bad_value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field_name} must be DecisionReceiptFlagState",
    ):
        DecisionReceiptFlags(**{field_name: bad_value})


def test_decision_receipt_flags_are_frozen() -> None:
    flags = DecisionReceiptFlags()

    with pytest.raises(FrozenInstanceError):
        flags.fallback_required = (  # type: ignore[misc]
            DecisionReceiptFlagState.TRUE
        )


def test_decision_receipt_preserves_mixed_explicit_flag_states() -> None:
    # These mixed states are synthetic contract data used to prove that each
    # flag is stored independently. They do not define an approved
    # producer-specific or business-semantic mapping.
    flags = DecisionReceiptFlags(
        fallback_required=DecisionReceiptFlagState.TRUE,
        rebuild_required=DecisionReceiptFlagState.FALSE,
        operator_review_required=DecisionReceiptFlagState.NOT_EVALUATED,
        retry_candidate=DecisionReceiptFlagState.TRUE,
    )

    receipt = make_decision_receipt(flags=flags)

    assert receipt.flags == flags
    assert receipt.flags.fallback_required == DecisionReceiptFlagState.TRUE
    assert receipt.flags.rebuild_required == DecisionReceiptFlagState.FALSE
    assert (
        receipt.flags.operator_review_required
        == DecisionReceiptFlagState.NOT_EVALUATED
    )
    assert receipt.flags.retry_candidate == DecisionReceiptFlagState.TRUE


def test_decision_receipt_flags_are_evidence_not_runtime_actions() -> None:
    receipt = make_decision_receipt(
        flags=DecisionReceiptFlags(
            fallback_required=DecisionReceiptFlagState.TRUE,
            rebuild_required=DecisionReceiptFlagState.TRUE,
            operator_review_required=DecisionReceiptFlagState.TRUE,
            retry_candidate=DecisionReceiptFlagState.TRUE,
        )
    )

    field_names = {field.name for field in fields(DecisionReceipt)}

    assert not hasattr(receipt, "requires_fallback")
    assert not hasattr(receipt, "requires_rebuild")
    assert not hasattr(receipt, "requires_operator_review")
    assert "runtime_action" not in field_names
    assert "decision" not in field_names
    assert "strategy" not in field_names
    assert "retry_allowed" not in field_names
    assert "recovery_action" not in field_names
    assert "persisted" not in field_names
    assert "diagnostic_trace" not in field_names


def test_decision_receipt_is_valid_property_reflects_semantic_summary() -> None:
    valid_receipt = make_decision_receipt(
        ok=True,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
        flags=DecisionReceiptFlags(),
    )

    assert valid_receipt.is_valid is True
    assert make_decision_receipt().is_valid is False


def test_decision_receipt_enum_member_sets_are_stable() -> None:
    assert {item.value for item in DecisionReceiptEvidenceSource} == {
        "WRITE_SIDE_ADMISSION",
        "READ_SIDE_PATH",
        "SNAPSHOT_TRUST_PATH",
        "SNAPSHOT_ASSISTED_PATH",
        "RUNTIME_OBSERVATION",
        "UNKNOWN",
    }
    assert {item.value for item in DecisionReceiptSubjectType} == {
        "ORDER",
        "REQUEST",
        "CANDIDATE_EVENT",
        "ACCEPTED_EVENT",
        "SNAPSHOT",
        "PROJECTION",
        "RUNTIME",
        "UNKNOWN",
    }
    assert {item.value for item in DecisionReceiptIdentitySource} == {
        "ACCEPTED_HISTORY",
        "CANDIDATE_EVENT_IDENTITY",
        "WRITE_SIDE_CORRELATION",
        "READ_SIDE_OBSERVATION",
        "SNAPSHOT_LINEAGE",
        "CALLER_CONTEXT",
        "UNKNOWN",
    }


def test_decision_receipt_evidence_source_names_paths_not_statuses_or_operations() -> None:
    evidence_sources = {item.value for item in DecisionReceiptEvidenceSource}

    assert "RUNTIME_TECHNICAL_STATUS" not in evidence_sources
    assert "READ_SIDE_REPLAY" not in evidence_sources
    assert "SNAPSHOT_REPLAY" not in evidence_sources
    assert "SNAPSHOT_ASSISTED_RESOLUTION" not in evidence_sources

    assert "WRITE_SIDE_ADMISSION" in evidence_sources
    assert "READ_SIDE_PATH" in evidence_sources
    assert "SNAPSHOT_TRUST_PATH" in evidence_sources
    assert "SNAPSHOT_ASSISTED_PATH" in evidence_sources
    assert "RUNTIME_OBSERVATION" in evidence_sources
    

def test_decision_receipt_contract_does_not_include_mapping_or_persistence_fields() -> None:
    field_names = {field.name for field in fields(DecisionReceipt)}

    assert "technical_status" not in field_names
    assert "write_side_result" not in field_names
    assert "read_side_result" not in field_names
    assert "snapshot_result" not in field_names
    assert "postgres_row_id" not in field_names
    assert "created_at" not in field_names
    assert "created_by" not in field_names


def test_decision_receipt_identity_source_names_identity_provenance_not_process_phase() -> None:
    identity_sources = {item.value for item in DecisionReceiptIdentitySource}

    assert "PRE_ADMISSION_CANDIDATE" not in identity_sources
    assert "WRITE_SIDE_ORCHESTRATION" not in identity_sources

    assert "CANDIDATE_EVENT_IDENTITY" in identity_sources
    assert "WRITE_SIDE_CORRELATION" in identity_sources
