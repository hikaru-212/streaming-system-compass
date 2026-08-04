"""PostgreSQL persistence for versioned DecisionReceipt semantic evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
    serialize_decision_receipt,
)
from src.compass.runtime.json_types import JsonValue
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


__all__ = ["PostgresDecisionReceiptStore"]


_ROW_COLUMNS = """
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
    materialization_provenance,
    materialized_at
"""


class PostgresDecisionReceiptStore:
    """Persist and load typed DecisionReceipt rows through PostgreSQL.

    Responsibility:
        Insert one version 1 receipt row, classify identical or conflicting
        duplicates, hydrate every semantic and persistence-envelope field, and
        load by receipt identity or admitted write-side producer identity.

    Connection and transaction ownership:
        The caller owns the supplied psycopg connection and transaction. The
        connection must have ``autocommit`` disabled. The store never commits,
        rolls back, changes connection configuration, opens another connection,
        or reports durable-commit acknowledgement.

    Concurrency and isolation:
        Typed concurrent duplicate and conflict classification is guaranteed at
        PostgreSQL ``READ COMMITTED`` isolation. At ``REPEATABLE READ`` or
        ``SERIALIZABLE``, an invisible concurrent winner may cause psycopg to
        raise its native ``SerializationFailure``. The store does not catch or
        translate that failure; the caller owns rollback and any decision to
        retry the complete transaction. A serialization failure is not retry
        authorization.

    Non-goals:
        The store performs no runtime materialization orchestration,
        accepted-history reconciliation, producer mapping, retry or policy,
        scanning, outbox work, publication, logging, or diagnostics.
    """

    def __init__(self, connection: Connection[object]) -> None:
        """Bind storage operations to one caller-owned psycopg connection.

        Args:
            connection: Existing PostgreSQL connection whose lifetime and
                transaction completion remain owned by the caller.

        Raises:
            TypeError: If ``connection`` is not a psycopg connection.
            ValueError: If the connection has autocommit enabled.

        Non-goals:
            Construction starts no transaction, performs no schema setup, and
            opens no additional connection. It does not change connection
            configuration to make an unsupported mode appear valid.
        """
        if not isinstance(connection, Connection):
            raise TypeError("connection must be psycopg.Connection")
        if connection.autocommit:
            raise ValueError("connection.autocommit must be False")
        self._connection = connection

    def insert(
        self,
        receipt: DecisionReceipt,
        *,
        materialization_provenance: (
            DecisionReceiptMaterializationProvenance
        ),
    ) -> DecisionReceiptInsertResult:
        """Insert or classify one receipt inside the caller-owned transaction.

        Args:
            receipt: Valid shared DecisionReceipt semantic payload.
            materialization_provenance: Separate persistence-envelope evidence.

        Returns:
            ``INSERTED`` with the statement-returned row, or
            ``ALREADY_PRESENT`` with the original row when the same receipt ID
            already owns an identical complete versioned semantic payload.

        Raises:
            TypeError: If either public argument has the wrong type.
            ValueError: If serializer version 1 rejects persistence portability.
            DecisionReceiptConflictError: If receipt content or admitted
                producer identity conflicts with an existing row.
            psycopg.errors.SerializationFailure: If stronger transaction
                isolation cannot observe a concurrent uniqueness winner. The
                caller must roll back before reusing the transaction.
            RuntimeError: If PostgreSQL reports no inserted row but no
                classifiable existing identity can be found.

        Invariants:
            Serialization runs before SQL. Envelope fields never participate in
            payload equality. Existing rows are never updated, replaced, or
            enriched. ``INSERTED`` reports statement success only.

        Non-goals:
            This method never commits, rolls back, acknowledges durability,
            orchestrates materialization, reconciles history, or selects retry
            or runtime policy.
        """
        if not isinstance(receipt, DecisionReceipt):
            raise TypeError("receipt must be DecisionReceipt")
        if not isinstance(
            materialization_provenance,
            DecisionReceiptMaterializationProvenance,
        ):
            raise TypeError(
                "materialization_provenance must be "
                "DecisionReceiptMaterializationProvenance"
            )

        serialized_payload = serialize_decision_receipt(receipt)
        receipt_body = _serialized_receipt_body(serialized_payload)
        evidence_summary = _serialized_json_object(
            receipt_body["evidence_summary"],
            "evidence_summary",
        )
        metadata = _serialized_json_object(
            receipt_body["metadata"],
            "metadata",
        )

        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
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
                    %(receipt_id)s,
                    %(receipt_serialization_version)s,
                    %(outcome_id)s,
                    %(ok)s,
                    %(boundary)s,
                    %(category)s,
                    %(semantic_code)s,
                    %(severity)s,
                    %(risk_level)s,
                    %(reversibility)s,
                    %(reason)s,
                    %(evidence_source)s,
                    %(subject_type)s,
                    %(subject_id)s,
                    %(order_id)s,
                    %(request_id)s,
                    %(candidate_event_id)s,
                    %(accepted_event_id)s,
                    %(snapshot_id)s,
                    %(source_global_position)s,
                    %(identity_source)s,
                    %(actor_id)s,
                    %(actor_role)s,
                    %(runtime_role)s,
                    %(elapsed_ms)s,
                    %(validation_elapsed_ms)s,
                    %(replay_elapsed_ms)s,
                    %(transaction_elapsed_ms)s,
                    %(lock_wait_ms)s,
                    %(fallback_required)s,
                    %(rebuild_required)s,
                    %(operator_review_required)s,
                    %(retry_candidate)s,
                    %(admission_disposition)s,
                    %(evidence_summary)s,
                    %(metadata)s,
                    %(materialization_provenance)s
                )
                ON CONFLICT DO NOTHING
                RETURNING
                    {_ROW_COLUMNS}
                """,
                {
                    "receipt_id": receipt.receipt_id,
                    "receipt_serialization_version": (
                        DECISION_RECEIPT_SERIALIZATION_VERSION
                    ),
                    "outcome_id": receipt.outcome_id,
                    "ok": receipt.ok,
                    "boundary": receipt.boundary.value,
                    "category": receipt.category.value,
                    "semantic_code": receipt.semantic_code.value,
                    "severity": receipt.severity.value,
                    "risk_level": receipt.risk_level.value,
                    "reversibility": receipt.reversibility.value,
                    "reason": receipt.reason,
                    "evidence_source": receipt.evidence_source.value,
                    "subject_type": receipt.subject.subject_type.value,
                    "subject_id": receipt.subject.subject_id,
                    "order_id": receipt.correlation.order_id,
                    "request_id": receipt.correlation.request_id,
                    "candidate_event_id": (
                        receipt.correlation.candidate_event_id
                    ),
                    "accepted_event_id": receipt.correlation.accepted_event_id,
                    "snapshot_id": receipt.correlation.snapshot_id,
                    "source_global_position": (
                        receipt.correlation.source_global_position
                    ),
                    "identity_source": (
                        receipt.correlation.identity_source.value
                    ),
                    "actor_id": receipt.actor.actor_id,
                    "actor_role": receipt.actor.actor_role,
                    "runtime_role": receipt.actor.runtime_role,
                    "elapsed_ms": receipt.cost_summary.elapsed_ms,
                    "validation_elapsed_ms": (
                        receipt.cost_summary.validation_elapsed_ms
                    ),
                    "replay_elapsed_ms": (
                        receipt.cost_summary.replay_elapsed_ms
                    ),
                    "transaction_elapsed_ms": (
                        receipt.cost_summary.transaction_elapsed_ms
                    ),
                    "lock_wait_ms": receipt.cost_summary.lock_wait_ms,
                    "fallback_required": (
                        receipt.flags.fallback_required.value
                    ),
                    "rebuild_required": receipt.flags.rebuild_required.value,
                    "operator_review_required": (
                        receipt.flags.operator_review_required.value
                    ),
                    "retry_candidate": receipt.flags.retry_candidate.value,
                    "admission_disposition": (
                        receipt.admission_evidence.disposition.value
                        if receipt.admission_evidence is not None
                        else None
                    ),
                    "evidence_summary": Jsonb(evidence_summary),
                    "metadata": Jsonb(metadata),
                    "materialization_provenance": (
                        materialization_provenance.value
                    ),
                },
            )
            inserted_row = cursor.fetchone()

        if inserted_row is not None:
            return DecisionReceiptInsertResult(
                status=DecisionReceiptInsertStatus.INSERTED,
                record=_persisted_decision_receipt_from_row(inserted_row),
            )

        existing_by_receipt_id = self.load_by_receipt_id(receipt.receipt_id)
        if existing_by_receipt_id is not None:
            if _same_versioned_payload(
                existing_by_receipt_id,
                serialized_payload,
            ):
                return DecisionReceiptInsertResult(
                    status=DecisionReceiptInsertStatus.ALREADY_PRESENT,
                    record=existing_by_receipt_id,
                )
            raise DecisionReceiptConflictError(
                category=(
                    DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
                ),
                receipt_id=receipt.receipt_id,
                accepted_event_id=receipt.correlation.accepted_event_id,
            )

        accepted_event_id = _admitted_write_side_accepted_event_id(receipt)
        if accepted_event_id is not None:
            existing_by_producer = (
                self.load_admitted_write_side_materialization_by_accepted_event_id(
                    accepted_event_id
                )
            )
            if existing_by_producer is not None:
                raise DecisionReceiptConflictError(
                    category=(
                        DecisionReceiptConflictCategory
                        .ACCEPTED_PRODUCER_IDENTITY_CONFLICT
                    ),
                    receipt_id=receipt.receipt_id,
                    accepted_event_id=accepted_event_id,
                )

        raise RuntimeError(
            "DecisionReceipt insert returned no row and no existing receipt "
            "identity could be classified"
        )

    def load_by_receipt_id(
        self,
        receipt_id: UUID,
    ) -> PersistedDecisionReceipt | None:
        """Load one receipt row by its application-generated UUID.

        Args:
            receipt_id: Exact receipt identity to query.

        Returns:
            Fully hydrated semantic receipt and persistence envelope, or
            ``None`` when the row is absent in the current transaction view.

        Raises:
            TypeError: If ``receipt_id`` is not a UUID.
            ValueError: If a stored version, enum, timestamp, or shared receipt
                invariant is malformed or unsupported.

        Non-goals:
            This read does not commit, roll back, lock for orchestration,
            acknowledge durability, or select policy.
        """
        _require_uuid(receipt_id, "receipt_id")
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    {_ROW_COLUMNS}
                FROM decision_receipts
                WHERE receipt_id = %s
                """,
                (receipt_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return _persisted_decision_receipt_from_row(row)

    def load_admitted_write_side_materialization_by_accepted_event_id(
        self,
        accepted_event_id: UUID,
    ) -> PersistedDecisionReceipt | None:
        """Load the unique newly admitted write-side receipt for one event.

        Args:
            accepted_event_id: Accepted-history UUID used by the scoped producer
                identity.

        Returns:
            The row whose evidence source is ``WRITE_SIDE_ADMISSION`` and whose
            disposition is ``ADMITTED_TO_ACCEPTED_HISTORY``, or ``None``.

        Raises:
            TypeError: If ``accepted_event_id`` is not a UUID.
            ValueError: If the stored row is malformed or unsupported.

        Invariants:
            The migration's partial unique index permits at most one matching
            row. Other receipt families sharing the event identity are ignored.

        Non-goals:
            This method does not reconcile missing receipts, scan history,
            commit, roll back, or grant accepted-history authority.
        """
        _require_uuid(accepted_event_id, "accepted_event_id")
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    {_ROW_COLUMNS}
                FROM decision_receipts
                WHERE accepted_event_id = %s
                  AND evidence_source = 'WRITE_SIDE_ADMISSION'
                  AND admission_disposition = 'ADMITTED_TO_ACCEPTED_HISTORY'
                """,
                (accepted_event_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None
        return _persisted_decision_receipt_from_row(row)


def _serialized_receipt_body(
    payload: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    version = payload["receipt_serialization_version"]
    if version != DECISION_RECEIPT_SERIALIZATION_VERSION:
        raise ValueError("serialized receipt version must be 1")
    receipt_body = payload["receipt"]
    if not isinstance(receipt_body, Mapping):
        raise TypeError("serialized receipt body must be a mapping")
    return receipt_body


def _serialized_json_object(
    value: JsonValue,
    field_name: str,
) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise TypeError(f"serialized {field_name} must be a mapping")
    return cast(dict[str, JsonValue], value)


def _same_versioned_payload(
    existing: PersistedDecisionReceipt,
    incoming_payload: Mapping[str, JsonValue],
) -> bool:
    if (
        existing.receipt_serialization_version
        != DECISION_RECEIPT_SERIALIZATION_VERSION
    ):
        return False
    return _same_serialized_json_value(
        serialize_decision_receipt(existing.receipt),
        incoming_payload,
    )


def _same_serialized_json_value(left: object, right: object) -> bool:
    """Compare complete serialized JSON values without Python numeric coercion."""
    if isinstance(left, Mapping):
        if not isinstance(right, Mapping):
            return False

        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            return False
        if any(type(key) is not str for key in left_keys | right_keys):
            raise TypeError("serialized payload object keys must be strings")

        return all(
            _same_serialized_json_value(left[key], right[key])
            for key in left_keys
        )

    if isinstance(left, list):
        if not isinstance(right, list) or len(left) != len(right):
            return False
        return all(
            _same_serialized_json_value(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )

    if left is None or right is None:
        return left is None and right is None

    if type(left) is not type(right):
        return False
    if type(left) in {str, bool, int, float}:
        return bool(left == right)

    raise TypeError("serialized payload contains an unsupported JSON value")


def _admitted_write_side_accepted_event_id(
    receipt: DecisionReceipt,
) -> UUID | None:
    if (
        receipt.evidence_source
        is DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION
        and receipt.admission_evidence is not None
        and receipt.admission_evidence.disposition
        is EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
    ):
        return receipt.correlation.accepted_event_id
    return None


def _persisted_decision_receipt_from_row(
    row: Mapping[str, Any],
) -> PersistedDecisionReceipt:
    version = row["receipt_serialization_version"]
    if type(version) is not int:
        raise TypeError("stored receipt_serialization_version must be int")
    if version != DECISION_RECEIPT_SERIALIZATION_VERSION:
        raise ValueError("stored receipt_serialization_version must be 1")

    admission_disposition = row["admission_disposition"]
    admission_evidence = (
        None
        if admission_disposition is None
        else DecisionReceiptAdmissionEvidence(
            disposition=EventAdmissionDisposition(admission_disposition)
        )
    )

    receipt = DecisionReceipt(
        receipt_id=row["receipt_id"],
        outcome_id=row["outcome_id"],
        ok=row["ok"],
        boundary=SemanticBoundary(row["boundary"]),
        category=SemanticOutcomeCategory(row["category"]),
        semantic_code=SemanticOutcomeCode(row["semantic_code"]),
        severity=SemanticSeverity(row["severity"]),
        risk_level=SemanticRiskLevel(row["risk_level"]),
        reversibility=SemanticReversibility(row["reversibility"]),
        reason=row["reason"],
        evidence_source=DecisionReceiptEvidenceSource(row["evidence_source"]),
        subject=DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType(row["subject_type"]),
            subject_id=row["subject_id"],
        ),
        correlation=DecisionReceiptCorrelation(
            order_id=row["order_id"],
            request_id=row["request_id"],
            candidate_event_id=row["candidate_event_id"],
            accepted_event_id=row["accepted_event_id"],
            snapshot_id=row["snapshot_id"],
            source_global_position=row["source_global_position"],
            identity_source=DecisionReceiptIdentitySource(
                row["identity_source"]
            ),
        ),
        actor=DecisionReceiptActor(
            actor_id=row["actor_id"],
            actor_role=row["actor_role"],
            runtime_role=row["runtime_role"],
        ),
        cost_summary=DecisionReceiptCostSummary(
            elapsed_ms=row["elapsed_ms"],
            validation_elapsed_ms=row["validation_elapsed_ms"],
            replay_elapsed_ms=row["replay_elapsed_ms"],
            transaction_elapsed_ms=row["transaction_elapsed_ms"],
            lock_wait_ms=row["lock_wait_ms"],
        ),
        flags=DecisionReceiptFlags(
            fallback_required=DecisionReceiptFlagState(
                row["fallback_required"]
            ),
            rebuild_required=DecisionReceiptFlagState(row["rebuild_required"]),
            operator_review_required=DecisionReceiptFlagState(
                row["operator_review_required"]
            ),
            retry_candidate=DecisionReceiptFlagState(row["retry_candidate"]),
        ),
        admission_evidence=admission_evidence,
        evidence_summary=row["evidence_summary"],
        metadata=row["metadata"],
    )

    # Typed row hydration reconstructs the runtime contract, while serializer
    # v1 additionally owns persistence portability such as nested int64 bounds.
    serialize_decision_receipt(receipt)

    return PersistedDecisionReceipt(
        receipt=receipt,
        receipt_serialization_version=version,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance(
                row["materialization_provenance"]
            )
        ),
        materialized_at=row["materialized_at"],
    )


def _require_uuid(value: object, field_name: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be UUID")
