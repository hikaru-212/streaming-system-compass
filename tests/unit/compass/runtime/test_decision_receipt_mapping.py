from dataclasses import fields
from decimal import Decimal
from uuid import UUID

import pytest

from src.compass.runtime import map_semantic_outcome_to_decision_receipt
from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000101")
RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000201")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000301")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000401")


def make_semantic_outcome(**overrides: object) -> SemanticOutcome:
    values: dict[str, object] = {
        "outcome_id": OUTCOME_ID,
        "ok": False,
        "boundary": SemanticBoundary.SNAPSHOT_TRUST,
        "category": SemanticOutcomeCategory.DRIFT,
        "semantic_code": SemanticOutcomeCode.DRIFT_DETECTED,
        "severity": SemanticSeverity.ERROR,
        "risk_level": SemanticRiskLevel.HIGH,
        "reversibility": SemanticReversibility.REBUILDABLE,
        "reason": "Snapshot-assisted reconstruction diverged from authority.",
    }
    values.update(overrides)
    return SemanticOutcome(**values)  # type: ignore[arg-type]


def map_outcome(
    outcome: SemanticOutcome | None = None,
    **overrides: object,
) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": RECEIPT_ID,
        "outcome": outcome or make_semantic_outcome(),
        "evidence_source": DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    }
    values.update(overrides)
    return map_semantic_outcome_to_decision_receipt(  # type: ignore[arg-type]
        **values
    )


def test_mapper_preserves_exact_semantic_tuple() -> None:
    outcome = make_semantic_outcome()

    receipt = map_outcome(outcome)

    assert receipt.outcome_id == outcome.outcome_id
    assert receipt.ok == outcome.ok
    assert receipt.boundary == outcome.boundary
    assert receipt.category == outcome.category
    assert receipt.semantic_code == outcome.semantic_code
    assert receipt.severity == outcome.severity
    assert receipt.risk_level == outcome.risk_level
    assert receipt.reversibility == outcome.reversibility
    assert receipt.reason == outcome.reason


def test_mapper_uses_caller_supplied_receipt_id() -> None:
    receipt_id = UUID("00000000-0000-0000-0000-000000000202")

    receipt = map_outcome(receipt_id=receipt_id)

    assert receipt.receipt_id == receipt_id


def test_mapper_preserves_explicit_evidence_source_without_inference() -> None:
    outcome = make_semantic_outcome(
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        category=SemanticOutcomeCategory.REBUILD_REQUIRED,
        semantic_code=SemanticOutcomeCode.REQUIRES_REBUILD,
    )

    receipt = map_outcome(
        outcome,
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
    )

    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION
    )


def test_mapper_uses_current_supporting_contract_defaults() -> None:
    receipt = map_outcome()

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


def test_mapper_preserves_explicit_supporting_contracts() -> None:
    subject = DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
        subject_id=str(EVENT_ID),
    )
    correlation = DecisionReceiptCorrelation(
        order_id="order-001",
        request_id="request-001",
        candidate_event_id=EVENT_ID,
        accepted_event_id=EVENT_ID,
        identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
    )
    actor = DecisionReceiptActor(
        actor_id="writer-001",
        actor_role="runtime",
        runtime_role="compass_app_writer",
    )
    cost_summary = DecisionReceiptCostSummary(
        elapsed_ms=12,
        transaction_elapsed_ms=8,
    )
    flags = DecisionReceiptFlags(operator_review_required=True)
    admission_evidence = DecisionReceiptAdmissionEvidence(
        disposition=EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
    )
    evidence_summary = {
        "technical_status": "WRITE_SIDE_ACCEPTED",
        "counts": {"accepted": 1},
    }
    metadata = {"producer": "unit-test"}

    receipt = map_outcome(
        evidence_source=DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        subject=subject,
        correlation=correlation,
        actor=actor,
        cost_summary=cost_summary,
        flags=flags,
        admission_evidence=admission_evidence,
        evidence_summary=evidence_summary,
        metadata=metadata,
    )

    assert receipt.subject == subject
    assert receipt.correlation == correlation
    assert receipt.actor == actor
    assert receipt.cost_summary == cost_summary
    assert receipt.flags == flags
    assert receipt.admission_evidence == admission_evidence
    assert receipt.evidence_summary == evidence_summary
    assert receipt.metadata == metadata


def test_mapper_does_not_copy_or_inspect_outcome_context() -> None:
    outcome = make_semantic_outcome(
        context={
            "order_id": "order-001",
            "snapshot_id": SNAPSHOT_ID,
            "amount": Decimal("10.00"),
            "rich_value": object(),
        }
    )

    receipt = map_outcome(outcome)

    assert receipt.evidence_summary == {}
    assert receipt.metadata == {}


def test_mapper_does_not_copy_or_inspect_outcome_evidence() -> None:
    outcome = make_semantic_outcome(
        evidence={
            "technical_status": "SNAPSHOT_ASSISTED_DRIFT",
            "result_type": "ProjectionSnapshotReplayValidationResult",
            "rich_value": object(),
        }
    )

    receipt = map_outcome(outcome)

    assert receipt.evidence_summary == {}
    assert receipt.metadata == {}


def test_mapper_accepts_and_freezes_explicit_json_safe_evidence() -> None:
    evidence_summary = {
        "technical_status": "MATCH",
        "nested": {"values": [1, "two", False]},
    }
    metadata = {"tags": ["stage-4b", "pr3"]}

    receipt = map_outcome(
        evidence_summary=evidence_summary,
        metadata=metadata,
    )

    evidence_summary["nested"]["values"].append("mutated")
    metadata["tags"].append("mutated")

    assert receipt.evidence_summary["nested"]["values"] == (1, "two", False)
    assert receipt.metadata["tags"] == ("stage-4b", "pr3")

    with pytest.raises(TypeError):
        receipt.evidence_summary["new_key"] = "value"  # type: ignore[index]

    with pytest.raises(TypeError):
        receipt.metadata["new_key"] = "value"  # type: ignore[index]


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_mapper_routes_explicit_evidence_through_json_validation(
    field_name: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"{field_name}.bad must be JSON-safe",
    ):
        map_outcome(**{field_name: {"bad": object()}})


@pytest.mark.parametrize(
    ("category", "semantic_code"),
    [
        (
            SemanticOutcomeCategory.FALLBACK_REQUIRED,
            SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
        ),
        (
            SemanticOutcomeCategory.REBUILD_REQUIRED,
            SemanticOutcomeCode.REQUIRES_REBUILD,
        ),
        (
            SemanticOutcomeCategory.ESCALATION_REQUIRED,
            SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW,
        ),
        (
            SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
            SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
        ),
        (
            SemanticOutcomeCategory.RETRY_CLASSIFIED,
            SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED,
        ),
    ],
)
def test_mapper_does_not_infer_flags(
    category: SemanticOutcomeCategory,
    semantic_code: SemanticOutcomeCode,
) -> None:
    outcome = make_semantic_outcome(
        category=category,
        semantic_code=semantic_code,
    )

    receipt = map_outcome(outcome)

    assert receipt.flags == DecisionReceiptFlags()


def test_mapper_does_not_infer_write_side_admission_contracts() -> None:
    outcome = make_semantic_outcome(
        boundary=SemanticBoundary.LAYER_1_WRITE_SIDE,
        context={
            "write_side_outcome": "ACCEPTED",
            "order_id": "order-001",
            "candidate_event_id": str(EVENT_ID),
            "accepted_event_id": str(EVENT_ID),
        },
    )

    receipt = map_outcome(outcome)

    assert receipt.subject == DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.UNKNOWN
    )
    assert receipt.correlation == DecisionReceiptCorrelation()
    assert receipt.admission_evidence is None


def test_mapper_does_not_infer_snapshot_contracts_or_evidence_source() -> None:
    outcome = make_semantic_outcome(
        boundary=SemanticBoundary.SNAPSHOT_TRUST,
        context={
            "order_id": "order-001",
            "snapshot_id": SNAPSHOT_ID,
            "source_global_position": 10,
        },
    )

    receipt = map_outcome(
        outcome,
        evidence_source=DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    )

    assert receipt.subject == DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.UNKNOWN
    )
    assert receipt.correlation == DecisionReceiptCorrelation()
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.UNKNOWN
    )
    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION
    )


def test_mapper_adds_no_policy_strategy_retry_trace_or_persistence_contract() -> None:
    receipt = map_outcome()
    field_names = {field.name for field in fields(receipt)}

    assert field_names.isdisjoint(
        {
            "runtime_action",
            "decision",
            "strategy",
            "retry_allowed",
            "diagnostic_trace",
            "persisted",
            "created_at",
            "store",
            "transaction",
            "serializer",
        }
    )


def test_mapper_ignores_receipt_like_keys_in_outcome_payloads() -> None:
    outcome = make_semantic_outcome(
        context={
            "flags": {"rebuild_required": True},
            "actor": {"actor_id": "context-actor"},
            "evidence_source": "WRITE_SIDE_ADMISSION",
        },
        evidence={
            "subject": {"subject_type": "ORDER"},
            "admission_evidence": {
                "disposition": "ADMITTED_TO_ACCEPTED_HISTORY"
            },
        },
    )

    receipt = map_outcome(outcome)

    assert receipt.flags == DecisionReceiptFlags()
    assert receipt.actor == DecisionReceiptActor()
    assert receipt.subject == DecisionReceiptSubject(
        subject_type=DecisionReceiptSubjectType.UNKNOWN
    )
    assert receipt.admission_evidence is None
    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION
    )


def test_semantic_outcome_fields_have_explicit_generic_mapper_ownership() -> None:
    outcome_fields = {field.name for field in fields(SemanticOutcome)}

    copied_from_outcome = {
        "outcome_id",
        "ok",
        "boundary",
        "category",
        "semantic_code",
        "severity",
        "risk_level",
        "reversibility",
        "reason",
    }
    intentionally_ignored = {
        "context",
        "evidence",
    }

    assert outcome_fields == copied_from_outcome | intentionally_ignored
    assert copied_from_outcome.isdisjoint(intentionally_ignored)


def test_decision_receipt_fields_have_explicit_generic_mapper_ownership() -> None:
    receipt_fields = {field.name for field in fields(DecisionReceipt)}

    copied_from_outcome = {
        "outcome_id",
        "ok",
        "boundary",
        "category",
        "semantic_code",
        "severity",
        "risk_level",
        "reversibility",
        "reason",
    }
    caller_owned = {
        "receipt_id",
        "evidence_source",
        "subject",
        "correlation",
        "actor",
        "cost_summary",
        "flags",
        "admission_evidence",
        "evidence_summary",
        "metadata",
    }

    assert receipt_fields == copied_from_outcome | caller_owned
    assert copied_from_outcome.isdisjoint(caller_owned)