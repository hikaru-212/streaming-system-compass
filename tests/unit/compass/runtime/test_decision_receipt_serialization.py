from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from enum import Enum
from inspect import Parameter, signature
from uuid import UUID

import pytest

import src.compass.runtime.decision_receipt_serialization as serialization_module
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
from src.compass.runtime.decision_receipt_serialization import (
    DECISION_RECEIPT_SERIALIZATION_VERSION,
    deserialize_decision_receipt,
    serialize_decision_receipt,
)
from src.compass.runtime.read_side_decision_receipt_mapping import (
    map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
    map_projection_snapshot_replay_validation_result_to_decision_receipt,
    map_replay_validation_result_to_decision_receipt,
)
from src.compass.runtime.write_side_decision_receipt_mapping import (
    map_postgres_write_side_result_to_decision_receipt,
)
from src.compass.runtime.json_types import MAX_JSON_DEPTH
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.replay_validator import (
    ReplayValidationResult,
    ReplayValidationStatus,
)
from tests.unit.compass.runtime.test_read_side_decision_receipt_mapping import (
    CREATED_STATE,
    ORDER_ID,
    PAID_STATE,
)
from tests.unit.compass.runtime.test_write_side_decision_receipt_mapping import (
    make_accepted_result,
    make_validation_blocked_result,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000601")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000602")
CANDIDATE_EVENT_ID = UUID("00000000-0000-0000-0000-000000000603")
ACCEPTED_EVENT_ID = UUID("00000000-0000-0000-0000-000000000604")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000605")
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

OUTER_KEYS = {"receipt_serialization_version", "receipt"}
RECEIPT_KEYS = {
    "receipt_id",
    "outcome_id",
    "ok",
    "boundary",
    "category",
    "semantic_code",
    "severity",
    "risk_level",
    "reversibility",
    "reason",
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
NESTED_KEYS = {
    "subject": {"subject_type", "subject_id"},
    "correlation": {
        "order_id",
        "request_id",
        "candidate_event_id",
        "accepted_event_id",
        "snapshot_id",
        "source_global_position",
        "identity_source",
    },
    "actor": {"actor_id", "actor_role", "runtime_role"},
    "cost_summary": {
        "elapsed_ms",
        "validation_elapsed_ms",
        "replay_elapsed_ms",
        "transaction_elapsed_ms",
        "lock_wait_ms",
    },
    "flags": {
        "fallback_required",
        "rebuild_required",
        "operator_review_required",
        "retry_candidate",
    },
    "admission_evidence": {"disposition"},
}


def make_minimal_receipt(**overrides: object) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": RECEIPT_ID,
        "outcome_id": OUTCOME_ID,
        "ok": True,
        "boundary": SemanticBoundary.RUNTIME_GOVERNANCE,
        "category": SemanticOutcomeCategory.VALID,
        "semantic_code": SemanticOutcomeCode.SEMANTICALLY_VALID,
        "severity": SemanticSeverity.INFO,
        "risk_level": SemanticRiskLevel.LOW,
        "reversibility": SemanticReversibility.REVERSIBLE,
        "reason": "Runtime evidence is semantically valid.",
        "evidence_source": DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def make_full_write_side_receipt(**overrides: object) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": RECEIPT_ID,
        "outcome_id": OUTCOME_ID,
        "ok": True,
        "boundary": SemanticBoundary.LAYER_1_WRITE_SIDE,
        "category": SemanticOutcomeCategory.VALID,
        "semantic_code": SemanticOutcomeCode.SEMANTICALLY_VALID,
        "severity": SemanticSeverity.INFO,
        "risk_level": SemanticRiskLevel.LOW,
        "reversibility": SemanticReversibility.REVERSIBLE,
        "reason": "Candidate event was admitted to accepted history.",
        "evidence_source": DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        "subject": DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(CANDIDATE_EVENT_ID),
        ),
        "correlation": DecisionReceiptCorrelation(
            order_id="order-001",
            request_id="request-001",
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=CANDIDATE_EVENT_ID,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        "actor": DecisionReceiptActor(
            actor_id="writer-001",
            actor_role="service",
            runtime_role="write-side",
        ),
        "cost_summary": DecisionReceiptCostSummary(
            elapsed_ms=12,
            validation_elapsed_ms=2,
            replay_elapsed_ms=0,
            transaction_elapsed_ms=8,
            lock_wait_ms=1,
        ),
        "flags": DecisionReceiptFlags(
            fallback_required=DecisionReceiptFlagState.FALSE,
            rebuild_required=DecisionReceiptFlagState.NOT_EVALUATED,
            operator_review_required=DecisionReceiptFlagState.TRUE,
            retry_candidate=DecisionReceiptFlagState.FALSE,
        ),
        "admission_evidence": DecisionReceiptAdmissionEvidence(
            disposition=(
                EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
            )
        ),
        "evidence_summary": {
            "technical_status": "SUCCESS",
            "checks": [True, False, None],
            "nested": {"count": 2, "ratio": 0.5},
        },
        "metadata": {
            "labels": ["write-side", {"source": "unit-test"}],
            "attempt": 1,
        },
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def serialized_body(receipt: DecisionReceipt | None = None) -> dict[str, object]:
    payload = serialize_decision_receipt(receipt or make_minimal_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    return body


def mutable_payload(receipt: DecisionReceipt | None = None) -> dict[str, object]:
    return deepcopy(
        serialize_decision_receipt(receipt or make_minimal_receipt())
    )


def round_trip(receipt: DecisionReceipt) -> None:
    assert deserialize_decision_receipt(
        serialize_decision_receipt(receipt)
    ) == receipt


def valid_correlation_for(
    disposition: EventAdmissionDisposition,
) -> DecisionReceiptCorrelation:
    if disposition == EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY:
        return DecisionReceiptCorrelation(
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=CANDIDATE_EVENT_ID,
        )
    if disposition in {
        EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT,
        EventAdmissionDisposition.IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY,
    }:
        return DecisionReceiptCorrelation(
            candidate_event_id=CANDIDATE_EVENT_ID,
            accepted_event_id=ACCEPTED_EVENT_ID,
        )
    if disposition in {
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE,
        EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED,
    }:
        return DecisionReceiptCorrelation(candidate_event_id=CANDIDATE_EVENT_ID)
    return DecisionReceiptCorrelation()


def mapper_produced_receipts() -> list[DecisionReceipt]:
    """Build the narrow PR4/PR5 composition matrix from public mappers."""

    snapshot_id = UUID("00000000-0000-0000-0000-000000000606")
    return [
        map_postgres_write_side_result_to_decision_receipt(
            receipt_id=UUID(int=610),
            outcome_id=UUID(int=710),
            result=make_accepted_result(),
        ),
        map_postgres_write_side_result_to_decision_receipt(
            receipt_id=UUID(int=611),
            outcome_id=UUID(int=711),
            result=make_validation_blocked_result(with_stream=True),
        ),
        map_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=612),
            outcome_id=UUID(int=712),
            result=ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.MATCH,
                expected_state=CREATED_STATE,
                persisted_state=CREATED_STATE,
                reason="Projection matches accepted-history replay.",
            ),
        ),
        map_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=613),
            outcome_id=UUID(int=713),
            result=ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
                expected_state=None,
                persisted_state=CREATED_STATE,
                reason="No accepted history exists for order.",
            ),
        ),
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=614),
            outcome_id=UUID(int=714),
            result=ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MATCH,
                order_id=ORDER_ID,
                snapshot_id=snapshot_id,
                source_global_position=10,
                snapshot_assisted_state=PAID_STATE,
                authority_state=PAID_STATE,
                reason="Snapshot-assisted replay matches authority.",
            ),
        ),
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=615),
            outcome_id=UUID(int=715),
            result=ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .NO_ACCEPTED_HISTORY_FOR_ORDER
                ),
                order_id=ORDER_ID,
                snapshot_id=snapshot_id,
                source_global_position=0,
                snapshot_assisted_state=None,
                authority_state=None,
                reason="No accepted history exists for order.",
            ),
        ),
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=UUID(int=616),
            outcome_id=UUID(int=716),
            result=ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                resolved_state=PAID_STATE,
                snapshot_id=snapshot_id,
                source_global_position=10,
                reason="Projection resolved from snapshot and tail.",
            ),
        ),
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=UUID(int=617),
            outcome_id=UUID(int=717),
            result=ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .TAIL_REPLAY_FAILED
                ),
                resolved_state=None,
                snapshot_id=snapshot_id,
                source_global_position=10,
                reason="Snapshot-assisted tail replay failed.",
            ),
        ),
    ]


def test_public_api_is_exact_and_signatures_are_pinned() -> None:
    assert DECISION_RECEIPT_SERIALIZATION_VERSION == 1
    assert serialization_module.__all__ == [
        "DECISION_RECEIPT_SERIALIZATION_VERSION",
        "serialize_decision_receipt",
        "deserialize_decision_receipt",
    ]

    serialize_signature = signature(serialize_decision_receipt)
    assert list(serialize_signature.parameters) == ["receipt"]
    assert (
        serialize_signature.parameters["receipt"].kind
        is Parameter.POSITIONAL_OR_KEYWORD
    )
    assert serialize_signature.parameters["receipt"].default is Parameter.empty
    assert (
        serialize_signature.parameters["receipt"].annotation
        == "DecisionReceipt"
    )
    assert serialize_signature.return_annotation == "dict[str, JsonValue]"

    deserialize_signature = signature(deserialize_decision_receipt)
    assert list(deserialize_signature.parameters) == ["payload"]
    assert (
        deserialize_signature.parameters["payload"].kind
        is Parameter.POSITIONAL_OR_KEYWORD
    )
    assert deserialize_signature.parameters["payload"].default is Parameter.empty
    assert (
        deserialize_signature.parameters["payload"].annotation
        == "Mapping[str, object]"
    )
    assert deserialize_signature.return_annotation == "DecisionReceipt"


@pytest.mark.parametrize(
    ("contract_type", "expected_fields"),
    [
        (DecisionReceipt, RECEIPT_KEYS),
        (DecisionReceiptSubject, NESTED_KEYS["subject"]),
        (DecisionReceiptCorrelation, NESTED_KEYS["correlation"]),
        (DecisionReceiptActor, NESTED_KEYS["actor"]),
        (DecisionReceiptCostSummary, NESTED_KEYS["cost_summary"]),
        (DecisionReceiptFlags, NESTED_KEYS["flags"]),
        (
            DecisionReceiptAdmissionEvidence,
            NESTED_KEYS["admission_evidence"],
        ),
    ],
)
def test_contract_field_ownership_is_pinned(
    contract_type: type[object],
    expected_fields: set[str],
) -> None:
    assert {field.name for field in fields(contract_type)} == expected_fields


def test_serialized_shape_and_nested_keys_are_exact() -> None:
    payload = serialize_decision_receipt(make_full_write_side_receipt())

    assert set(payload) == OUTER_KEYS
    assert payload["receipt_serialization_version"] == 1
    body = payload["receipt"]
    assert isinstance(body, dict)
    assert set(body) == RECEIPT_KEYS
    assert "is_valid" not in body

    for field_name, expected_keys in NESTED_KEYS.items():
        nested = body[field_name]
        assert isinstance(nested, dict)
        assert set(nested) == expected_keys


@pytest.mark.parametrize(
    "receipt",
    [
        make_minimal_receipt(),
        make_full_write_side_receipt(),
        make_minimal_receipt(
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
            subject=DecisionReceiptSubject(
                subject_type=DecisionReceiptSubjectType.ORDER,
                subject_id="order-002",
            ),
            correlation=DecisionReceiptCorrelation(
                order_id="order-002",
                identity_source=(
                    DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION
                ),
            ),
            admission_evidence=None,
        ),
        make_minimal_receipt(
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject=DecisionReceiptSubject(
                subject_type=DecisionReceiptSubjectType.SNAPSHOT,
                subject_id=str(SNAPSHOT_ID),
            ),
            correlation=DecisionReceiptCorrelation(
                order_id="order-003",
                snapshot_id=SNAPSHOT_ID,
                source_global_position=101,
                identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            ),
        ),
        make_minimal_receipt(
            flags=DecisionReceiptFlags(
                fallback_required=DecisionReceiptFlagState.TRUE,
                rebuild_required=DecisionReceiptFlagState.FALSE,
                operator_review_required=(
                    DecisionReceiptFlagState.NOT_EVALUATED
                ),
                retry_candidate=DecisionReceiptFlagState.TRUE,
            )
        ),
        make_minimal_receipt(
            evidence_summary={
                "nested": {"values": [1, True, None, {"ratio": 1.25}]}
            },
            metadata={"tags": ["one", "two"], "empty": {}},
        ),
        make_minimal_receipt(evidence_summary={}, metadata={}),
    ],
)
def test_representative_receipts_round_trip(receipt: DecisionReceipt) -> None:
    round_trip(receipt)


MAPPER_COMPOSITION_EXPECTATIONS = {
    UUID(int=610): (
        DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        DecisionReceiptSubjectType.ACCEPTED_EVENT,
        DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        None,
        {"write_side_outcome": "ACCEPTED"},
    ),
    UUID(int=611): (
        DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        DecisionReceiptSubjectType.CANDIDATE_EVENT,
        DecisionReceiptIdentitySource.CANDIDATE_EVENT_IDENTITY,
        None,
        {"write_side_outcome": "VALIDATION_BLOCKED"},
    ),
    UUID(int=612): (
        DecisionReceiptEvidenceSource.READ_SIDE_PATH,
        DecisionReceiptSubjectType.PROJECTION,
        DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
        None,
        {"expected_state_present": True, "persisted_state_present": True},
    ),
    UUID(int=613): (
        DecisionReceiptEvidenceSource.READ_SIDE_PATH,
        DecisionReceiptSubjectType.ORDER,
        DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
        None,
        {"expected_state_present": False, "persisted_state_present": True},
    ),
    UUID(int=614): (
        DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
        DecisionReceiptSubjectType.SNAPSHOT,
        DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
        10,
        {
            "snapshot_artifact_present": True,
            "snapshot_assisted_state_present": True,
            "authority_state_present": True,
        },
    ),
    UUID(int=615): (
        DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
        DecisionReceiptSubjectType.ORDER,
        DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
        0,
        {
            "snapshot_artifact_present": True,
            "snapshot_assisted_state_present": False,
            "authority_state_present": False,
        },
    ),
    UUID(int=616): (
        DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
        DecisionReceiptSubjectType.PROJECTION,
        DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
        10,
        {"snapshot_artifact_present": True, "resolved_state_present": True},
    ),
    UUID(int=617): (
        DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
        DecisionReceiptSubjectType.RUNTIME,
        DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
        10,
        {"snapshot_artifact_present": True, "resolved_state_present": False},
    ),
}


@pytest.mark.parametrize(
    "receipt",
    mapper_produced_receipts(),
    ids=[
        "write-accepted",
        "write-validation-blocked",
        "replay-match",
        "replay-no-history-with-persisted-state",
        "snapshot-match-with-lineage",
        "snapshot-no-history-with-lineage-zero-position",
        "assisted-resolved",
        "assisted-tail-replay-failed",
    ],
)
def test_pr4_pr5_mapper_produced_receipts_round_trip(
    receipt: DecisionReceipt,
) -> None:
    restored = deserialize_decision_receipt(serialize_decision_receipt(receipt))
    expected = MAPPER_COMPOSITION_EXPECTATIONS[receipt.receipt_id]
    source, subject_type, identity_source, source_position, summary = expected

    assert restored == receipt
    assert restored.evidence_source is source
    assert restored.subject.subject_type is subject_type
    assert restored.correlation.identity_source is identity_source
    assert restored.correlation.source_global_position == source_position
    for key, value in summary.items():
        observed = restored.evidence_summary[key]
        assert type(observed) is type(value)
        assert observed == value

    assert restored.flags == DecisionReceiptFlags()
    assert all(
        state is DecisionReceiptFlagState.NOT_EVALUATED
        for state in (
            restored.flags.fallback_required,
            restored.flags.rebuild_required,
            restored.flags.operator_review_required,
            restored.flags.retry_candidate,
        )
    )
    assert DecisionReceiptFlagState.FALSE is not (
        DecisionReceiptFlagState.NOT_EVALUATED
    )
    if source is not DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION:
        assert restored.admission_evidence is None


def test_optional_values_are_present_as_null() -> None:
    body = serialized_body()

    assert body["admission_evidence"] is None
    assert body["subject"] == {"subject_type": "UNKNOWN", "subject_id": None}
    assert body["correlation"] == {
        "order_id": None,
        "request_id": None,
        "candidate_event_id": None,
        "accepted_event_id": None,
        "snapshot_id": None,
        "source_global_position": None,
        "identity_source": "UNKNOWN",
    }
    assert body["actor"] == {
        "actor_id": None,
        "actor_role": None,
        "runtime_role": None,
    }
    assert body["cost_summary"] == {
        "elapsed_ms": None,
        "validation_elapsed_ms": None,
        "replay_elapsed_ms": None,
        "transaction_elapsed_ms": None,
        "lock_wait_ms": None,
    }


def test_uuid_and_enum_representations_are_portable_strings() -> None:
    body = serialized_body(make_full_write_side_receipt())

    assert body["receipt_id"] == str(RECEIPT_ID)
    assert body["outcome_id"] == str(OUTCOME_ID)
    assert body["boundary"] == SemanticBoundary.LAYER_1_WRITE_SIDE.value
    correlation = body["correlation"]
    assert isinstance(correlation, dict)
    assert correlation["candidate_event_id"] == str(CANDIDATE_EVENT_ID)
    assert correlation["identity_source"] == "ACCEPTED_HISTORY"
    admission = body["admission_evidence"]
    assert isinstance(admission, dict)
    assert admission["disposition"] == "ADMITTED_TO_ACCEPTED_HISTORY"


ENUM_FIELDS: tuple[tuple[str, type[Enum]], ...] = (
    ("boundary", SemanticBoundary),
    ("category", SemanticOutcomeCategory),
    ("semantic_code", SemanticOutcomeCode),
    ("severity", SemanticSeverity),
    ("risk_level", SemanticRiskLevel),
    ("reversibility", SemanticReversibility),
    ("evidence_source", DecisionReceiptEvidenceSource),
)


@pytest.mark.parametrize(("field_name", "enum_type"), ENUM_FIELDS)
def test_every_top_level_enum_member_round_trips(
    field_name: str,
    enum_type: type[Enum],
) -> None:
    for member in enum_type:
        round_trip(replace(make_minimal_receipt(), **{field_name: member}))


@pytest.mark.parametrize("subject_type", list(DecisionReceiptSubjectType))
def test_every_subject_type_round_trips(
    subject_type: DecisionReceiptSubjectType,
) -> None:
    round_trip(
        replace(
            make_minimal_receipt(),
            subject=DecisionReceiptSubject(subject_type=subject_type),
        )
    )


@pytest.mark.parametrize("identity_source", list(DecisionReceiptIdentitySource))
def test_every_identity_source_round_trips(
    identity_source: DecisionReceiptIdentitySource,
) -> None:
    round_trip(
        replace(
            make_minimal_receipt(),
            correlation=DecisionReceiptCorrelation(
                identity_source=identity_source
            ),
        )
    )


@pytest.mark.parametrize("flag_state", list(DecisionReceiptFlagState))
def test_every_flag_state_round_trips(
    flag_state: DecisionReceiptFlagState,
) -> None:
    round_trip(
        replace(
            make_minimal_receipt(),
            flags=DecisionReceiptFlags(
                fallback_required=flag_state,
                rebuild_required=flag_state,
                operator_review_required=flag_state,
                retry_candidate=flag_state,
            ),
        )
    )


@pytest.mark.parametrize("disposition", list(EventAdmissionDisposition))
def test_every_admission_disposition_round_trips(
    disposition: EventAdmissionDisposition,
) -> None:
    receipt = replace(
        make_minimal_receipt(),
        correlation=valid_correlation_for(disposition),
        admission_evidence=DecisionReceiptAdmissionEvidence(
            disposition=disposition
        ),
    )
    round_trip(receipt)


def test_serialized_json_objects_and_lists_are_detached_and_mutable() -> None:
    receipt = make_full_write_side_receipt()
    payload = serialize_decision_receipt(receipt)
    body = payload["receipt"]
    assert isinstance(body, dict)
    evidence = body["evidence_summary"]
    metadata = body["metadata"]
    assert isinstance(evidence, dict)
    assert isinstance(metadata, dict)
    checks = evidence["checks"]
    labels = metadata["labels"]
    assert isinstance(checks, list)
    assert isinstance(labels, list)

    checks.append("mutated")
    labels[1]["source"] = "changed"  # type: ignore[index]
    evidence["new"] = {"value": 1}

    assert receipt.evidence_summary["checks"] == (True, False, None)
    assert receipt.metadata["labels"][1]["source"] == "unit-test"  # type: ignore[index]
    assert "new" not in receipt.evidence_summary


@pytest.mark.parametrize(
    ("operation", "match"),
    [
        (lambda value: value.pop("receipt"), "missing keys: receipt"),
        (
            lambda value: value.__setitem__("unknown", None),
            "unknown keys: unknown",
        ),
    ],
)
def test_outer_keys_are_strict(operation: object, match: str) -> None:
    payload = mutable_payload()
    operation(payload)  # type: ignore[operator]

    with pytest.raises(ValueError, match=match):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    ("operation", "match"),
    [
        (lambda body: body.pop("reason"), "missing keys: reason"),
        (
            lambda body: body.__setitem__("is_valid", True),
            "unknown keys: is_valid",
        ),
    ],
)
def test_receipt_keys_are_strict(operation: object, match: str) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    operation(body)  # type: ignore[operator]

    with pytest.raises(ValueError, match=match):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    "nested_field",
    ["subject", "correlation", "actor", "cost_summary", "flags"],
)
@pytest.mark.parametrize("change", ["missing", "unknown"])
def test_nested_keys_are_strict(nested_field: str, change: str) -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    nested = body[nested_field]
    assert isinstance(nested, dict)
    if change == "missing":
        nested.pop(next(iter(NESTED_KEYS[nested_field])))
    else:
        nested["unknown"] = None

    with pytest.raises(ValueError, match=f"{change} keys"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize("change", ["missing", "unknown"])
def test_admission_evidence_keys_are_strict(change: str) -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    admission = body["admission_evidence"]
    assert isinstance(admission, dict)
    if change == "missing":
        admission.pop("disposition")
    else:
        admission["unknown"] = None

    with pytest.raises(ValueError, match=f"{change} keys"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    "version",
    [False, "1", 0, 2],
)
def test_invalid_serialization_versions_are_rejected(version: object) -> None:
    payload = mutable_payload()
    payload["receipt_serialization_version"] = version

    with pytest.raises((TypeError, ValueError)):
        deserialize_decision_receipt(payload)


def test_missing_version_is_rejected() -> None:
    payload = mutable_payload()
    payload.pop("receipt_serialization_version")

    with pytest.raises(ValueError, match="missing keys"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    ("field_path", "bad_value"),
    [
        (("receipt_id",), "not-a-uuid"),
        (("outcome_id",), UUID(int=1)),
        (("correlation", "candidate_event_id"), "not-a-uuid"),
        (("correlation", "snapshot_id"), SNAPSHOT_ID),
    ],
)
def test_malformed_or_native_uuid_values_are_rejected(
    field_path: tuple[str, ...],
    bad_value: object,
) -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    target = body
    for component in field_path[:-1]:
        child = target[component]
        assert isinstance(child, dict)
        target = child
    target[field_path[-1]] = bad_value

    with pytest.raises((TypeError, ValueError)):
        deserialize_decision_receipt(payload)


ENUM_PAYLOAD_PATHS: tuple[tuple[tuple[str, ...], Enum], ...] = (
    (("boundary",), SemanticBoundary.LAYER_1_WRITE_SIDE),
    (("category",), SemanticOutcomeCategory.VALID),
    (("semantic_code",), SemanticOutcomeCode.SEMANTICALLY_VALID),
    (("severity",), SemanticSeverity.INFO),
    (("risk_level",), SemanticRiskLevel.LOW),
    (("reversibility",), SemanticReversibility.REVERSIBLE),
    (
        ("evidence_source",),
        DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
    ),
    (("subject", "subject_type"), DecisionReceiptSubjectType.ACCEPTED_EVENT),
    (
        ("correlation", "identity_source"),
        DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
    ),
    (("flags", "fallback_required"), DecisionReceiptFlagState.FALSE),
    (
        ("admission_evidence", "disposition"),
        EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY,
    ),
)


@pytest.mark.parametrize(("field_path", "enum_member"), ENUM_PAYLOAD_PATHS)
@pytest.mark.parametrize("bad_kind", ["unknown", "enum-instance"])
def test_unknown_or_native_enum_values_are_rejected(
    field_path: tuple[str, ...],
    enum_member: Enum,
    bad_kind: str,
) -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    target = body
    for component in field_path[:-1]:
        child = target[component]
        assert isinstance(child, dict)
        target = child
    target[field_path[-1]] = (
        "NOT_A_CURRENT_ENUM_VALUE" if bad_kind == "unknown" else enum_member
    )

    with pytest.raises((TypeError, ValueError)):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize("value", [INT64_MIN, 0, INT64_MAX])
def test_signed_64_bit_values_round_trip_in_flexible_json(value: int) -> None:
    receipt = make_minimal_receipt(
        evidence_summary={"value": value},
        metadata={"nested": [value, True]},
    )

    round_trip(receipt)


def test_signed_64_bit_maximum_round_trips_in_typed_integer_fields() -> None:
    receipt = make_minimal_receipt(
        correlation=DecisionReceiptCorrelation(source_global_position=INT64_MAX),
        cost_summary=DecisionReceiptCostSummary(
            elapsed_ms=0,
            validation_elapsed_ms=INT64_MAX,
        ),
    )

    round_trip(receipt)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        (
            "correlation",
            DecisionReceiptCorrelation(source_global_position=INT64_MAX + 1),
        ),
        (
            "cost_summary",
            DecisionReceiptCostSummary(elapsed_ms=INT64_MAX + 1),
        ),
    ],
)
def test_serialization_rejects_out_of_range_typed_integers(
    field_name: str,
    field_value: object,
) -> None:
    receipt = make_minimal_receipt(**{field_name: field_value})

    with pytest.raises(ValueError, match="signed 64-bit"):
        serialize_decision_receipt(receipt)


@pytest.mark.parametrize("value", [INT64_MIN - 1, INT64_MAX + 1])
@pytest.mark.parametrize(
    ("nested_field", "integer_field"),
    [
        ("correlation", "source_global_position"),
        ("cost_summary", "elapsed_ms"),
    ],
)
def test_deserialization_rejects_out_of_range_typed_integers(
    value: int,
    nested_field: str,
    integer_field: str,
) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    nested = body[nested_field]
    assert isinstance(nested, dict)
    nested[integer_field] = value

    with pytest.raises(ValueError, match="signed 64-bit"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize("value", [INT64_MIN - 1, INT64_MAX + 1])
@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_serialization_rejects_out_of_range_nested_integers(
    value: int,
    field_name: str,
) -> None:
    receipt = make_minimal_receipt(**{field_name: {"nested": [value]}})

    with pytest.raises(ValueError, match="signed 64-bit"):
        serialize_decision_receipt(receipt)


@pytest.mark.parametrize("value", [INT64_MIN - 1, INT64_MAX + 1])
@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_deserialization_rejects_out_of_range_nested_integers(
    value: int,
    field_name: str,
) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    body[field_name] = {"nested": [value]}

    with pytest.raises(ValueError, match="signed 64-bit"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    ("nested_field", "integer_field"),
    [
        ("correlation", "source_global_position"),
        ("cost_summary", "elapsed_ms"),
    ],
)
def test_bool_is_rejected_in_typed_integer_locations(
    nested_field: str,
    integer_field: str,
) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    nested = body[nested_field]
    assert isinstance(nested, dict)
    nested[integer_field] = True

    with pytest.raises(TypeError, match="not bool"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_json_numbers_are_rejected(bad_value: float) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    body["evidence_summary"] = {"number": bad_value}

    with pytest.raises(ValueError, match="finite JSON number"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    "bad_mapping",
    [
        {1: "non-string-key"},
        {"object": object()},
    ],
)
def test_invalid_flexible_json_values_are_rejected(
    bad_mapping: dict[object, object],
) -> None:
    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    body["metadata"] = bad_mapping

    with pytest.raises(TypeError):
        deserialize_decision_receipt(payload)


def test_excessively_nested_flexible_json_is_rejected() -> None:
    nested: object = "leaf"
    for _ in range(MAX_JSON_DEPTH + 2):
        nested = {"next": nested}

    payload = mutable_payload()
    body = payload["receipt"]
    assert isinstance(body, dict)
    body["evidence_summary"] = {"root": nested}

    with pytest.raises(ValueError, match="maximum JSON depth"):
        deserialize_decision_receipt(payload)


def test_invalid_admission_correlation_is_rejected_on_deserialization() -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    correlation = body["correlation"]
    assert isinstance(correlation, dict)
    correlation["candidate_event_id"] = None

    with pytest.raises(ValueError, match="candidate_event_id is required"):
        deserialize_decision_receipt(payload)


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        (("ok",), 1),
        (("reason",), 1),
        (("subject", "subject_id"), 1),
        (("admission_evidence",), "ADMITTED_TO_ACCEPTED_HISTORY"),
    ],
)
def test_incorrect_scalar_and_nested_types_are_not_coerced(
    path: tuple[str, ...],
    bad_value: object,
) -> None:
    payload = mutable_payload(make_full_write_side_receipt())
    body = payload["receipt"]
    assert isinstance(body, dict)
    target = body
    for component in path[:-1]:
        child = target[component]
        assert isinstance(child, dict)
        target = child
    target[path[-1]] = bad_value

    with pytest.raises(TypeError):
        deserialize_decision_receipt(payload)


def test_non_mapping_outer_and_receipt_body_are_rejected() -> None:
    with pytest.raises(TypeError, match="payload must be a mapping"):
        deserialize_decision_receipt([])  # type: ignore[arg-type]

    payload = mutable_payload()
    payload["receipt"] = []
    with pytest.raises(TypeError, match="payload.receipt must be a mapping"):
        deserialize_decision_receipt(payload)


def test_serializer_rejects_non_receipt_input() -> None:
    with pytest.raises(TypeError, match="receipt must be DecisionReceipt"):
        serialize_decision_receipt(object())  # type: ignore[arg-type]
