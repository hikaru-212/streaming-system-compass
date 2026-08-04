from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from psycopg import Connection
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

from src.compass.runtime.decision_receipt import (
    DecisionReceiptEvidenceSource,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubjectType,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


REQUIRED_COLUMNS = {
    "receipt_id": ("uuid", "NO"),
    "receipt_serialization_version": ("integer", "NO"),
    "outcome_id": ("uuid", "NO"),
    "ok": ("boolean", "NO"),
    "boundary": ("text", "NO"),
    "category": ("text", "NO"),
    "semantic_code": ("text", "NO"),
    "severity": ("text", "NO"),
    "risk_level": ("text", "NO"),
    "reversibility": ("text", "NO"),
    "reason": ("text", "NO"),
    "evidence_source": ("text", "NO"),
    "subject_type": ("text", "NO"),
    "subject_id": ("text", "YES"),
    "order_id": ("text", "YES"),
    "request_id": ("text", "YES"),
    "candidate_event_id": ("uuid", "YES"),
    "accepted_event_id": ("uuid", "YES"),
    "snapshot_id": ("uuid", "YES"),
    "source_global_position": ("bigint", "YES"),
    "identity_source": ("text", "NO"),
    "actor_id": ("text", "YES"),
    "actor_role": ("text", "YES"),
    "runtime_role": ("text", "YES"),
    "elapsed_ms": ("bigint", "YES"),
    "validation_elapsed_ms": ("bigint", "YES"),
    "replay_elapsed_ms": ("bigint", "YES"),
    "transaction_elapsed_ms": ("bigint", "YES"),
    "lock_wait_ms": ("bigint", "YES"),
    "fallback_required": ("text", "NO"),
    "rebuild_required": ("text", "NO"),
    "operator_review_required": ("text", "NO"),
    "retry_candidate": ("text", "NO"),
    "admission_disposition": ("text", "YES"),
    "evidence_summary": ("jsonb", "NO"),
    "metadata": ("jsonb", "NO"),
    "materialization_provenance": ("text", "NO"),
    "materialized_at": ("timestamp with time zone", "NO"),
}


def _insert_order_event(connection: Connection[Any]) -> UUID:
    accepted_event_id = uuid4()
    connection.execute(
        """
        INSERT INTO order_events (
            accepted_event_id,
            order_id,
            sequence,
            event_type,
            request_id,
            amount,
            occurred_at_ms,
            proof_prev_event_id,
            proof_prev_version,
            proof_prev_status,
            payload_json,
            proof_json,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            1,
            'CREATED',
            %s,
            100.00,
            1700000000000,
            NULL,
            0,
            'INIT',
            '{}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb
        )
        """,
        (
            accepted_event_id,
            f"order-{uuid4()}",
            f"request-{uuid4()}",
        ),
    )
    return accepted_event_id


def _insert_decision_receipt(
    connection: Connection[Any],
    **overrides: object,
) -> tuple[UUID, datetime]:
    values: dict[str, object] = {
        "receipt_id": uuid4(),
        "receipt_serialization_version": 1,
        "outcome_id": uuid4(),
        "ok": True,
        "boundary": "RUNTIME_GOVERNANCE",
        "category": "VALID",
        "semantic_code": "SEMANTICALLY_VALID",
        "severity": "INFO",
        "risk_level": "LOW",
        "reversibility": "REVERSIBLE",
        "reason": "Runtime evidence is semantically valid.",
        "evidence_source": "RUNTIME_OBSERVATION",
        "subject_type": "UNKNOWN",
        "subject_id": None,
        "order_id": None,
        "request_id": None,
        "candidate_event_id": None,
        "accepted_event_id": None,
        "snapshot_id": None,
        "source_global_position": None,
        "identity_source": "UNKNOWN",
        "actor_id": None,
        "actor_role": None,
        "runtime_role": None,
        "elapsed_ms": None,
        "validation_elapsed_ms": None,
        "replay_elapsed_ms": None,
        "transaction_elapsed_ms": None,
        "lock_wait_ms": None,
        "fallback_required": "NOT_EVALUATED",
        "rebuild_required": "NOT_EVALUATED",
        "operator_review_required": "NOT_EVALUATED",
        "retry_candidate": "NOT_EVALUATED",
        "admission_disposition": None,
        "evidence_summary": {},
        "metadata": {},
        "materialization_provenance": "LIVE_RESULT",
    }
    values.update(overrides)

    row = connection.execute(
        """
        INSERT INTO decision_receipts (
            receipt_id,
            receipt_serialization_version,
            outcome_id,
            ok,
            boundary,
            category,
            semantic_code,
            severity,
            risk_level,
            reversibility,
            reason,
            evidence_source,
            subject_type,
            subject_id,
            order_id,
            request_id,
            candidate_event_id,
            accepted_event_id,
            snapshot_id,
            source_global_position,
            identity_source,
            actor_id,
            actor_role,
            runtime_role,
            elapsed_ms,
            validation_elapsed_ms,
            replay_elapsed_ms,
            transaction_elapsed_ms,
            lock_wait_ms,
            fallback_required,
            rebuild_required,
            operator_review_required,
            retry_candidate,
            admission_disposition,
            evidence_summary,
            metadata,
            materialization_provenance
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING receipt_id, materialized_at
        """,
        (
            values["receipt_id"],
            values["receipt_serialization_version"],
            values["outcome_id"],
            values["ok"],
            values["boundary"],
            values["category"],
            values["semantic_code"],
            values["severity"],
            values["risk_level"],
            values["reversibility"],
            values["reason"],
            values["evidence_source"],
            values["subject_type"],
            values["subject_id"],
            values["order_id"],
            values["request_id"],
            values["candidate_event_id"],
            values["accepted_event_id"],
            values["snapshot_id"],
            values["source_global_position"],
            values["identity_source"],
            values["actor_id"],
            values["actor_role"],
            values["runtime_role"],
            values["elapsed_ms"],
            values["validation_elapsed_ms"],
            values["replay_elapsed_ms"],
            values["transaction_elapsed_ms"],
            values["lock_wait_ms"],
            values["fallback_required"],
            values["rebuild_required"],
            values["operator_review_required"],
            values["retry_candidate"],
            values["admission_disposition"],
            Jsonb(values["evidence_summary"]),
            Jsonb(values["metadata"]),
            values["materialization_provenance"],
        ),
    ).fetchone()

    assert row is not None
    return row


def test_decision_receipts_has_exact_foundational_columns(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    rows = db_connection.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'decision_receipts'
        ORDER BY ordinal_position
        """
    ).fetchall()

    assert {name: (data_type, nullable) for name, data_type, nullable in rows} == (
        REQUIRED_COLUMNS
    )


def test_receipt_id_is_the_uuid_primary_key(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    rows = db_connection.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = 'decision_receipts'
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """
    ).fetchall()

    assert rows == [("receipt_id",)]

    receipt_id = uuid4()
    _insert_decision_receipt(db_connection, receipt_id=receipt_id)
    with pytest.raises(UniqueViolation):
        _insert_decision_receipt(db_connection, receipt_id=receipt_id)


@pytest.mark.parametrize("version", [0, 2])
def test_serialization_version_is_exactly_one(
    db_connection: Connection[Any],
    clean_database: None,
    version: int,
) -> None:
    with pytest.raises(CheckViolation):
        _insert_decision_receipt(
            db_connection,
            receipt_serialization_version=version,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "boundary",
        "category",
        "semantic_code",
        "severity",
        "risk_level",
        "reversibility",
        "evidence_source",
        "subject_type",
        "identity_source",
        "fallback_required",
        "rebuild_required",
        "operator_review_required",
        "retry_candidate",
        "admission_disposition",
        "materialization_provenance",
    ],
)
def test_enum_vocabulary_checks_reject_unknown_values(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
) -> None:
    with pytest.raises(CheckViolation):
        _insert_decision_receipt(
            db_connection,
            **{field_name: "NOT_A_CURRENT_VALUE"},
        )


CURRENT_ENUM_FIELDS = (
    ("boundary", SemanticBoundary),
    ("category", SemanticOutcomeCategory),
    ("semantic_code", SemanticOutcomeCode),
    ("severity", SemanticSeverity),
    ("risk_level", SemanticRiskLevel),
    ("reversibility", SemanticReversibility),
    ("evidence_source", DecisionReceiptEvidenceSource),
    ("subject_type", DecisionReceiptSubjectType),
    ("identity_source", DecisionReceiptIdentitySource),
)


@pytest.mark.parametrize(
    ("field_name", "enum_value"),
    [
        (field_name, member.value)
        for field_name, enum_type in CURRENT_ENUM_FIELDS
        for member in enum_type
    ],
    ids=[
        f"{field_name}-{member.value}"
        for field_name, enum_type in CURRENT_ENUM_FIELDS
        for member in enum_type
    ],
)
def test_every_current_source_enum_value_is_accepted(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
    enum_value: str,
) -> None:
    _insert_decision_receipt(
        db_connection,
        **{field_name: enum_value},
    )


@pytest.mark.parametrize(
    ("field_name", "flag_value"),
    [
        (field_name, flag_value)
        for field_name in (
            "fallback_required",
            "rebuild_required",
            "operator_review_required",
            "retry_candidate",
        )
        for flag_value in ("TRUE", "FALSE", "NOT_EVALUATED")
    ],
)
def test_every_tri_state_flag_value_is_accepted(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
    flag_value: str,
) -> None:
    _insert_decision_receipt(
        db_connection,
        **{field_name: flag_value},
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "reason",
        "subject_id",
        "order_id",
        "request_id",
        "actor_id",
        "actor_role",
        "runtime_role",
    ],
)
@pytest.mark.parametrize("blank_value", ["", "   "])
def test_required_and_optional_strings_reject_blank_values(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
    blank_value: str,
) -> None:
    with pytest.raises(CheckViolation):
        _insert_decision_receipt(
            db_connection,
            **{field_name: blank_value},
        )


def test_source_global_position_must_be_non_negative(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    _insert_decision_receipt(db_connection, source_global_position=0)

    with pytest.raises(CheckViolation):
        _insert_decision_receipt(db_connection, source_global_position=-1)


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
def test_cost_fields_must_be_non_negative(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
) -> None:
    _insert_decision_receipt(db_connection, **{field_name: 0})

    with pytest.raises(CheckViolation):
        _insert_decision_receipt(db_connection, **{field_name: -1})


@pytest.mark.parametrize("field_name", ["evidence_summary", "metadata"])
def test_jsonb_evidence_fields_must_be_objects(
    db_connection: Connection[Any],
    clean_database: None,
    field_name: str,
) -> None:
    with pytest.raises(CheckViolation):
        _insert_decision_receipt(db_connection, **{field_name: []})


@pytest.mark.parametrize(
    ("disposition", "candidate_kind", "accepted_kind"),
    [
        ("ADMITTED_TO_ACCEPTED_HISTORY", "accepted", "accepted"),
        ("MATCHED_EXISTING_ACCEPTED_EVENT", None, "accepted"),
        (
            "IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY",
            "candidate",
            "accepted",
        ),
        ("SEMANTIC_ADMISSION_REJECTED", "candidate", None),
        ("APPEND_CONCURRENCY_CONFLICT", "candidate", None),
        ("APPEND_TECHNICAL_FAILURE", "candidate", None),
        ("COMMIT_OUTCOME_UNRESOLVED", "candidate", None),
        ("APPEND_ADMISSION_NOT_REACHED", None, None),
        ("APPEND_ADMISSION_NOT_REACHED", "candidate", None),
        ("UNKNOWN", None, None),
    ],
)
def test_valid_admission_identity_shapes_are_accepted(
    db_connection: Connection[Any],
    clean_database: None,
    disposition: str,
    candidate_kind: str | None,
    accepted_kind: str | None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)
    candidate_event_id = (
        accepted_event_id
        if candidate_kind == "accepted"
        else uuid4() if candidate_kind == "candidate" else None
    )
    stored_accepted_event_id = (
        accepted_event_id if accepted_kind == "accepted" else None
    )

    _insert_decision_receipt(
        db_connection,
        candidate_event_id=candidate_event_id,
        accepted_event_id=stored_accepted_event_id,
        admission_disposition=disposition,
    )


@pytest.mark.parametrize(
    ("disposition", "candidate_kind", "accepted_kind"),
    [
        ("ADMITTED_TO_ACCEPTED_HISTORY", None, "accepted"),
        ("ADMITTED_TO_ACCEPTED_HISTORY", "candidate", None),
        ("ADMITTED_TO_ACCEPTED_HISTORY", "candidate", "accepted"),
        ("MATCHED_EXISTING_ACCEPTED_EVENT", None, None),
        ("IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY", "candidate", None),
        ("SEMANTIC_ADMISSION_REJECTED", None, None),
        ("SEMANTIC_ADMISSION_REJECTED", "candidate", "accepted"),
        ("APPEND_CONCURRENCY_CONFLICT", None, None),
        ("APPEND_CONCURRENCY_CONFLICT", "candidate", "accepted"),
        ("APPEND_TECHNICAL_FAILURE", None, None),
        ("APPEND_TECHNICAL_FAILURE", "candidate", "accepted"),
        ("COMMIT_OUTCOME_UNRESOLVED", None, None),
        ("COMMIT_OUTCOME_UNRESOLVED", "candidate", "accepted"),
        ("APPEND_ADMISSION_NOT_REACHED", None, "accepted"),
    ],
)
def test_invalid_admission_identity_shapes_are_rejected(
    db_connection: Connection[Any],
    clean_database: None,
    disposition: str,
    candidate_kind: str | None,
    accepted_kind: str | None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)
    candidate_event_id = (
        accepted_event_id
        if candidate_kind == "accepted"
        else uuid4() if candidate_kind == "candidate" else None
    )
    stored_accepted_event_id = (
        accepted_event_id if accepted_kind == "accepted" else None
    )

    with pytest.raises(CheckViolation):
        _insert_decision_receipt(
            db_connection,
            candidate_event_id=candidate_event_id,
            accepted_event_id=stored_accepted_event_id,
            admission_disposition=disposition,
        )


@pytest.mark.parametrize("disposition", [None, "UNKNOWN"])
def test_null_and_unknown_admission_add_no_identity_requirements(
    db_connection: Connection[Any],
    clean_database: None,
    disposition: str | None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)

    _insert_decision_receipt(
        db_connection,
        candidate_event_id=uuid4(),
        accepted_event_id=accepted_event_id,
        admission_disposition=disposition,
    )


def test_accepted_event_id_references_accepted_history(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    with pytest.raises(ForeignKeyViolation):
        _insert_decision_receipt(
            db_connection,
            accepted_event_id=uuid4(),
            admission_disposition="MATCHED_EXISTING_ACCEPTED_EVENT",
        )


def test_admitted_write_side_event_has_scoped_unique_producer_identity(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)
    values = {
        "candidate_event_id": accepted_event_id,
        "accepted_event_id": accepted_event_id,
        "evidence_source": "WRITE_SIDE_ADMISSION",
        "admission_disposition": "ADMITTED_TO_ACCEPTED_HISTORY",
    }
    _insert_decision_receipt(db_connection, **values)

    with pytest.raises(UniqueViolation):
        _insert_decision_receipt(db_connection, **values)


def test_same_accepted_event_is_allowed_for_non_admitted_dispositions(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)

    _insert_decision_receipt(
        db_connection,
        accepted_event_id=accepted_event_id,
        evidence_source="WRITE_SIDE_ADMISSION",
        admission_disposition="MATCHED_EXISTING_ACCEPTED_EVENT",
    )
    _insert_decision_receipt(
        db_connection,
        accepted_event_id=accepted_event_id,
        evidence_source="WRITE_SIDE_ADMISSION",
        admission_disposition=(
            "IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY"
        ),
    )


def test_admitted_event_uniqueness_is_scoped_to_write_side_evidence(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    accepted_event_id = _insert_order_event(db_connection)
    values = {
        "candidate_event_id": accepted_event_id,
        "accepted_event_id": accepted_event_id,
        "admission_disposition": "ADMITTED_TO_ACCEPTED_HISTORY",
    }

    _insert_decision_receipt(
        db_connection,
        evidence_source="RUNTIME_OBSERVATION",
        **values,
    )
    _insert_decision_receipt(
        db_connection,
        evidence_source="RUNTIME_OBSERVATION",
        **values,
    )


def test_outcome_id_is_not_unique(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    outcome_id = uuid4()

    _insert_decision_receipt(db_connection, outcome_id=outcome_id)
    _insert_decision_receipt(db_connection, outcome_id=outcome_id)


@pytest.mark.parametrize(
    "provenance",
    ["LIVE_RESULT", "ACCEPTED_HISTORY_RECONCILIATION"],
)
def test_materialization_provenance_values_are_accepted(
    db_connection: Connection[Any],
    clean_database: None,
    provenance: str,
) -> None:
    _insert_decision_receipt(
        db_connection,
        materialization_provenance=provenance,
    )


def test_materialized_at_is_database_generated_and_timezone_aware(
    db_connection: Connection[Any],
    clean_database: None,
) -> None:
    _receipt_id, materialized_at = _insert_decision_receipt(db_connection)

    assert isinstance(materialized_at, datetime)
    assert materialized_at.tzinfo is not None
    assert materialized_at.utcoffset() is not None
