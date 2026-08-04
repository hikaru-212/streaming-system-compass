"""Typed persistence-envelope contracts for durable DecisionReceipt rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from src.compass.runtime.decision_receipt import DecisionReceipt


__all__ = [
    "DecisionReceiptMaterializationProvenance",
    "DecisionReceiptInsertStatus",
    "PersistedDecisionReceipt",
    "DecisionReceiptInsertResult",
    "DecisionReceiptConflictCategory",
    "DecisionReceiptConflictError",
]


class DecisionReceiptMaterializationProvenance(str, Enum):
    """Identify how a durable receipt row was materialized.

    These stable values belong to the persistence envelope rather than the
    DecisionReceipt semantic payload. They record whether a row came from a
    live result or a future accepted-history reconciliation path. Defining the
    latter vocabulary does not implement reconciliation.
    """

    LIVE_RESULT = "LIVE_RESULT"
    ACCEPTED_HISTORY_RECONCILIATION = "ACCEPTED_HISTORY_RECONCILIATION"


class DecisionReceiptInsertStatus(str, Enum):
    """Classify one insert statement inside a caller-owned transaction.

    ``INSERTED`` means the SQL insert statement returned a new row.
    ``ALREADY_PRESENT`` means an identical versioned semantic payload already
    occupied the same receipt identity. Neither status proves that the caller
    subsequently committed the transaction, and no ``PERSISTED`` status is
    defined at this storage boundary.
    """

    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@dataclass(frozen=True)
class PersistedDecisionReceipt:
    """Represent one DecisionReceipt row observed in the current transaction.

    Args:
        receipt: The hydrated shared semantic receipt.
        receipt_serialization_version: Exact portable payload version stored by
            the row. Foundational persistence accepts only version 1.
        materialization_provenance: Persistence-envelope evidence describing
            how the row was created.
        materialized_at: Database-generated timezone-aware row timestamp.

    Invariants:
        Values are immutable, the serialization version is exactly 1, and the
        materialization timestamp is timezone-aware.

    Non-goals:
        This record does not prove that the transaction which inserted the row
        committed, grant accepted-history authority, or perform orchestration,
        reconciliation, retry, publication, or policy selection.
    """

    receipt: DecisionReceipt
    receipt_serialization_version: int
    materialization_provenance: DecisionReceiptMaterializationProvenance
    materialized_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, DecisionReceipt):
            raise TypeError("receipt must be DecisionReceipt")
        if type(self.receipt_serialization_version) is not int:
            raise TypeError("receipt_serialization_version must be int")
        if self.receipt_serialization_version != 1:
            raise ValueError("receipt_serialization_version must be 1")
        if not isinstance(
            self.materialization_provenance,
            DecisionReceiptMaterializationProvenance,
        ):
            raise TypeError(
                "materialization_provenance must be "
                "DecisionReceiptMaterializationProvenance"
            )
        if not isinstance(self.materialized_at, datetime):
            raise TypeError("materialized_at must be datetime")
        if (
            self.materialized_at.tzinfo is None
            or self.materialized_at.utcoffset() is None
        ):
            raise ValueError("materialized_at must be timezone-aware")


@dataclass(frozen=True)
class DecisionReceiptInsertResult:
    """Return statement-level receipt insertion classification and row data.

    Args:
        status: ``INSERTED`` or ``ALREADY_PRESENT`` classification.
        record: The newly returned or previously existing database row observed
            inside the caller-owned transaction.

    Invariants:
        Both fields are immutable and use the explicit persistence contracts.

    Non-goals:
        This result does not acknowledge transaction commit or durable
        persistence and does not authorize retry, replacement, or enrichment.
    """

    status: DecisionReceiptInsertStatus
    record: PersistedDecisionReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.status, DecisionReceiptInsertStatus):
            raise TypeError("status must be DecisionReceiptInsertStatus")
        if not isinstance(self.record, PersistedDecisionReceipt):
            raise TypeError("record must be PersistedDecisionReceipt")


class DecisionReceiptConflictCategory(str, Enum):
    """Provide stable, storage-owned DecisionReceipt conflict categories.

    Categories distinguish reuse of one receipt identity with different
    semantic content from occupation of one admitted write-side producer
    identity by another receipt. They contain no database constraint names,
    SQL diagnostics, policy decisions, or retry authorization.
    """

    RECEIPT_ID_CONTENT_CONFLICT = "RECEIPT_ID_CONTENT_CONFLICT"
    ACCEPTED_PRODUCER_IDENTITY_CONFLICT = (
        "ACCEPTED_PRODUCER_IDENTITY_CONFLICT"
    )


class DecisionReceiptConflictError(RuntimeError):
    """Report a classified receipt conflict using only safe identifiers.

    Args:
        category: Stable storage-owned conflict category.
        receipt_id: Incoming receipt identity involved in the conflict.
        accepted_event_id: Optional accepted-event identity for an admitted
            producer conflict.

    Attributes:
        category: Stable conflict category.
        receipt_id: Safe incoming receipt UUID.
        accepted_event_id: Safe accepted-event UUID when applicable.

    Non-goals:
        The error never exposes SQL text, constraint names as authority, raw
        psycopg exceptions, connection details, receipt payloads, or metadata.
        It does not select retry, replacement, enrichment, or runtime policy.
    """

    def __init__(
        self,
        *,
        category: DecisionReceiptConflictCategory,
        receipt_id: UUID,
        accepted_event_id: UUID | None = None,
    ) -> None:
        """Create one safe conflict error from typed category and identifiers."""
        if not isinstance(category, DecisionReceiptConflictCategory):
            raise TypeError("category must be DecisionReceiptConflictCategory")
        if not isinstance(receipt_id, UUID):
            raise TypeError("receipt_id must be UUID")
        if accepted_event_id is not None and not isinstance(
            accepted_event_id,
            UUID,
        ):
            raise TypeError("accepted_event_id must be UUID or None")
        if (
            category
            is DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
            and accepted_event_id is None
        ):
            raise ValueError(
                "accepted_event_id is required for an accepted producer conflict"
            )

        self._category = category
        self._receipt_id = receipt_id
        self._accepted_event_id = accepted_event_id
        super().__init__(f"DecisionReceipt conflict: {category.value}")

    @property
    def category(self) -> DecisionReceiptConflictCategory:
        """Return the stable storage-owned conflict category."""
        return self._category

    @property
    def receipt_id(self) -> UUID:
        """Return the safe incoming receipt identity."""
        return self._receipt_id

    @property
    def accepted_event_id(self) -> UUID | None:
        """Return the safe accepted-event identity when one applies."""
        return self._accepted_event_id
