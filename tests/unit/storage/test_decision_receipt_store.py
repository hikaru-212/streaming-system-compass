from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from inspect import getdoc, signature
from uuid import UUID

import pytest

import src.storage.decision_receipt_store as contract_module
import src.storage.postgres_decision_receipt_store as postgres_module
from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptEvidenceSource,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptConflictCategory,
    DecisionReceiptConflictError,
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
    PersistedDecisionReceipt,
)
from src.storage.postgres_decision_receipt_store import (
    PostgresDecisionReceiptStore,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000801")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000802")
ACCEPTED_EVENT_ID = UUID("00000000-0000-0000-0000-000000000803")


def make_receipt() -> DecisionReceipt:
    return DecisionReceipt(
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


def make_record() -> PersistedDecisionReceipt:
    return PersistedDecisionReceipt(
        receipt=make_receipt(),
        receipt_serialization_version=1,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
        materialized_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def test_materialization_provenance_values_are_exact() -> None:
    assert {
        item.name: item.value for item in DecisionReceiptMaterializationProvenance
    } == {
        "LIVE_RESULT": "LIVE_RESULT",
        "ACCEPTED_HISTORY_RECONCILIATION": (
            "ACCEPTED_HISTORY_RECONCILIATION"
        ),
    }


def test_insert_status_values_are_exact_and_exclude_persisted() -> None:
    assert {item.name: item.value for item in DecisionReceiptInsertStatus} == {
        "INSERTED": "INSERTED",
        "ALREADY_PRESENT": "ALREADY_PRESENT",
    }
    assert "PERSISTED" not in DecisionReceiptInsertStatus.__members__


def test_conflict_category_values_are_exact() -> None:
    assert {item.name: item.value for item in DecisionReceiptConflictCategory} == {
        "RECEIPT_ID_CONTENT_CONFLICT": "RECEIPT_ID_CONTENT_CONFLICT",
        "ACCEPTED_PRODUCER_IDENTITY_CONFLICT": (
            "ACCEPTED_PRODUCER_IDENTITY_CONFLICT"
        ),
    }


def test_persisted_decision_receipt_field_ownership_is_exact() -> None:
    assert [item.name for item in fields(PersistedDecisionReceipt)] == [
        "receipt",
        "receipt_serialization_version",
        "materialization_provenance",
        "materialized_at",
    ]


def test_insert_result_field_ownership_is_exact() -> None:
    assert [item.name for item in fields(DecisionReceiptInsertResult)] == [
        "status",
        "record",
    ]


def test_persistence_records_and_results_are_immutable() -> None:
    record = make_record()
    result = DecisionReceiptInsertResult(
        status=DecisionReceiptInsertStatus.INSERTED,
        record=record,
    )

    with pytest.raises(FrozenInstanceError):
        record.receipt_serialization_version = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = (  # type: ignore[misc]
            DecisionReceiptInsertStatus.ALREADY_PRESENT
        )


def test_persisted_record_requires_timezone_aware_materialized_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PersistedDecisionReceipt(
            receipt=make_receipt(),
            receipt_serialization_version=1,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
            materialized_at=datetime(2026, 8, 1),
        )


@pytest.mark.parametrize("version", [False, 0, 2])
def test_persisted_record_requires_exact_integer_version_one(
    version: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        PersistedDecisionReceipt(
            receipt=make_receipt(),
            receipt_serialization_version=version,  # type: ignore[arg-type]
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
            materialized_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )


def test_contract_module_public_surface_is_exact() -> None:
    assert contract_module.__all__ == [
        "DecisionReceiptMaterializationProvenance",
        "DecisionReceiptInsertStatus",
        "PersistedDecisionReceipt",
        "DecisionReceiptInsertResult",
        "DecisionReceiptConflictCategory",
        "DecisionReceiptConflictError",
    ]


def test_postgres_store_module_public_surface_is_exact() -> None:
    assert postgres_module.__all__ == ["PostgresDecisionReceiptStore"]


def test_postgres_store_rejects_non_connection() -> None:
    with pytest.raises(TypeError, match="connection must be psycopg.Connection"):
        PostgresDecisionReceiptStore(object())  # type: ignore[arg-type]


def test_store_public_api_signatures_are_exact() -> None:
    assert list(signature(PostgresDecisionReceiptStore).parameters) == [
        "connection"
    ]
    assert list(signature(PostgresDecisionReceiptStore.insert).parameters) == [
        "self",
        "receipt",
        "materialization_provenance",
    ]
    assert (
        signature(PostgresDecisionReceiptStore.insert)
        .parameters["materialization_provenance"]
        .kind.name
        == "KEYWORD_ONLY"
    )
    assert list(
        signature(PostgresDecisionReceiptStore.load_by_receipt_id).parameters
    ) == ["self", "receipt_id"]
    assert list(
        signature(
            PostgresDecisionReceiptStore
            .load_admitted_write_side_materialization_by_accepted_event_id
        ).parameters
    ) == ["self", "accepted_event_id"]


@pytest.mark.parametrize(
    "public_object",
    [
        DecisionReceiptMaterializationProvenance,
        DecisionReceiptInsertStatus,
        PersistedDecisionReceipt,
        DecisionReceiptInsertResult,
        DecisionReceiptConflictCategory,
        DecisionReceiptConflictError,
        PostgresDecisionReceiptStore,
        PostgresDecisionReceiptStore.__init__,
        PostgresDecisionReceiptStore.insert,
        PostgresDecisionReceiptStore.load_by_receipt_id,
        (
            PostgresDecisionReceiptStore
            .load_admitted_write_side_materialization_by_accepted_event_id
        ),
    ],
)
def test_public_contracts_have_complete_docstrings(public_object: object) -> None:
    docstring = getdoc(public_object)
    assert docstring is not None
    assert len(docstring.split()) >= 8


def test_conflict_error_exposes_only_safe_conflict_attributes() -> None:
    error = DecisionReceiptConflictError(
        category=(
            DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
        ),
        receipt_id=RECEIPT_ID,
        accepted_event_id=ACCEPTED_EVENT_ID,
    )

    assert error.category is (
        DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
    )
    assert error.receipt_id == RECEIPT_ID
    assert error.accepted_event_id == ACCEPTED_EVENT_ID
    assert str(error) == (
        "DecisionReceipt conflict: ACCEPTED_PRODUCER_IDENTITY_CONFLICT"
    )
    for forbidden_attribute in (
        "sql",
        "constraint_name",
        "database_error",
        "connection",
        "payload",
        "metadata",
    ):
        assert not hasattr(error, forbidden_attribute)


def test_accepted_producer_conflict_requires_accepted_event_id() -> None:
    with pytest.raises(ValueError, match="accepted_event_id is required"):
        DecisionReceiptConflictError(
            category=(
                DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
            ),
            receipt_id=RECEIPT_ID,
        )
