from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class SnapshotWriteCollisionError(Exception):
    """Raised when a projection snapshot collides with different lineage or payload evidence."""


@dataclass(frozen=True)
class ProjectionSnapshot:
    snapshot_id: UUID
    order_id: str

    source_event_id: UUID
    source_event_sequence: int
    source_global_position: int

    state_status: str
    total_amount: Decimal
    paid_amount: Decimal
    state_version: int

    snapshot_schema_version: int
    reducer_version: str
    payload_hash: str

    metadata: dict[str, Any]
    created_by: str
    created_at: datetime | None = None


class PostgresProjectionSnapshotStore:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def save_snapshot(self, snapshot: ProjectionSnapshot) -> None:
        inserted = self._insert_snapshot(snapshot)

        if inserted:
            return

        existing_snapshots = self._load_existing_source_boundary_snapshots(snapshot)

        if not existing_snapshots:
            raise SnapshotWriteCollisionError(
                "Projection snapshot insert conflicted, but no matching "
                "source-boundary snapshot could be found."
            )

        if all(
            _same_snapshot_evidence(existing, snapshot)
            for existing in existing_snapshots
        ):
            return

        raise SnapshotWriteCollisionError(
            "Projection snapshot source boundary already exists with "
            "different lineage or payload evidence."
        )

    def load_latest_snapshot(self, order_id: str) -> ProjectionSnapshot | None:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    snapshot_id,
                    order_id,
                    source_event_id,
                    source_event_sequence,
                    source_global_position,
                    state_status,
                    total_amount,
                    paid_amount,
                    state_version,
                    snapshot_schema_version,
                    reducer_version,
                    payload_hash,
                    metadata_json,
                    created_by,
                    created_at
                FROM projection_snapshots
                WHERE order_id = %s
                ORDER BY source_global_position DESC
                LIMIT 1
                """,
                (order_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return _projection_snapshot_from_row(row)

    def load_snapshot(self, snapshot_id: UUID) -> ProjectionSnapshot | None:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    snapshot_id,
                    order_id,
                    source_event_id,
                    source_event_sequence,
                    source_global_position,
                    state_status,
                    total_amount,
                    paid_amount,
                    state_version,
                    snapshot_schema_version,
                    reducer_version,
                    payload_hash,
                    metadata_json,
                    created_by,
                    created_at
                FROM projection_snapshots
                WHERE snapshot_id = %s
                """,
                (snapshot_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return _projection_snapshot_from_row(row)

    def clear_snapshots(self, order_id: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM projection_snapshots
                WHERE order_id = %s
                """,
                (order_id,),
            )

    def _insert_snapshot(self, snapshot: ProjectionSnapshot) -> bool:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_snapshots (
                    snapshot_id,
                    order_id,
                    source_event_id,
                    source_event_sequence,
                    source_global_position,
                    state_status,
                    total_amount,
                    paid_amount,
                    state_version,
                    snapshot_schema_version,
                    reducer_version,
                    payload_hash,
                    metadata_json,
                    created_by
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT DO NOTHING
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.order_id,
                    snapshot.source_event_id,
                    snapshot.source_event_sequence,
                    snapshot.source_global_position,
                    snapshot.state_status,
                    snapshot.total_amount,
                    snapshot.paid_amount,
                    snapshot.state_version,
                    snapshot.snapshot_schema_version,
                    snapshot.reducer_version,
                    snapshot.payload_hash,
                    Jsonb(snapshot.metadata),
                    snapshot.created_by,
                ),
            )
            return cursor.rowcount == 1

    def _load_existing_source_boundary_snapshots(
        self,
        snapshot: ProjectionSnapshot,
    ) -> list[ProjectionSnapshot]:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    snapshot_id,
                    order_id,
                    source_event_id,
                    source_event_sequence,
                    source_global_position,
                    state_status,
                    total_amount,
                    paid_amount,
                    state_version,
                    snapshot_schema_version,
                    reducer_version,
                    payload_hash,
                    metadata_json,
                    created_by,
                    created_at
                FROM projection_snapshots
                WHERE
                    source_event_id = %s
                    OR source_global_position = %s
                    OR (
                        order_id = %s
                        AND source_event_sequence = %s
                    )
                ORDER BY source_global_position DESC
                """,
                (
                    snapshot.source_event_id,
                    snapshot.source_global_position,
                    snapshot.order_id,
                    snapshot.source_event_sequence,
                ),
            )
            rows = cursor.fetchall()

        return [_projection_snapshot_from_row(row) for row in rows]


def _projection_snapshot_from_row(row: dict[str, Any]) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        snapshot_id=row["snapshot_id"],
        order_id=row["order_id"],
        source_event_id=row["source_event_id"],
        source_event_sequence=row["source_event_sequence"],
        source_global_position=row["source_global_position"],
        state_status=row["state_status"],
        total_amount=row["total_amount"],
        paid_amount=row["paid_amount"],
        state_version=row["state_version"],
        snapshot_schema_version=row["snapshot_schema_version"],
        reducer_version=row["reducer_version"],
        payload_hash=row["payload_hash"],
        metadata=row["metadata_json"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _same_source_boundary(
    existing: ProjectionSnapshot,
    incoming: ProjectionSnapshot,
) -> bool:
    return (
        existing.order_id == incoming.order_id
        and existing.source_event_id == incoming.source_event_id
        and existing.source_event_sequence == incoming.source_event_sequence
        and existing.source_global_position == incoming.source_global_position
    )


def _same_snapshot_evidence(
    existing: ProjectionSnapshot,
    incoming: ProjectionSnapshot,
) -> bool:
    return (
        _same_source_boundary(existing, incoming)
        and existing.snapshot_schema_version == incoming.snapshot_schema_version
        and existing.reducer_version == incoming.reducer_version
        and existing.payload_hash == incoming.payload_hash
    )