from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from psycopg import Connection


class CheckpointCursorKind(str, Enum):
    """
    Durable checkpoint cursor kind.

    This mirrors projection_checkpoints.cursor_kind.

    It intentionally does not decide the final worker scanning strategy.
    PR4 should decide how the PostgreSQL-backed projection worker scans
    accepted history.
    """

    UNSPECIFIED = "UNSPECIFIED"
    APPENDED_AT = "APPENDED_AT"
    EVENT_ID = "EVENT_ID"
    GLOBAL_POSITION = "GLOBAL_POSITION"


@dataclass(frozen=True)
class ProjectionCheckpoint:
    """
    Durable projection worker checkpoint.

    worker_name identifies the projection worker.

    cursor_kind / cursor_value together describe the worker's durable
    progress bookmark.

    This is intentionally more general than the old in-memory integer offset
    because order_events.sequence is aggregate-local and must not be reused
    as a global projection cursor.
    """

    worker_name: str
    cursor_kind: CheckpointCursorKind
    cursor_value: str


class PostgresCheckpointStore:
    """
    PostgreSQL-backed projection checkpoint store.

    Responsibility:
    - persist projection worker progress into projection_checkpoints
    - load projection worker progress by worker_name
    - clear checkpoints for tests / rebuild paths

    This store does NOT:
    - scan accepted history
    - decide the final cursor strategy
    - run the projection worker
    - persist projection state
    - validate semantic drift
    - decide replay / rebuild orchestration

    Transaction ownership:
    - this store does not commit or rollback
    - the caller owns the transaction boundary
    - cursor resources are scoped to each method call through context managers
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def load_checkpoint(self, worker_name: str) -> ProjectionCheckpoint | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    worker_name,
                    cursor_kind,
                    cursor_value
                FROM projection_checkpoints
                WHERE worker_name = %s
                """,
                (worker_name,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        (
            stored_worker_name,
            cursor_kind,
            cursor_value,
        ) = row

        return ProjectionCheckpoint(
            worker_name=stored_worker_name,
            cursor_kind=CheckpointCursorKind(cursor_kind),
            cursor_value=cursor_value,
        )

    def save_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_checkpoints (
                    worker_name,
                    cursor_kind,
                    cursor_value
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (worker_name)
                DO UPDATE SET
                    cursor_kind = EXCLUDED.cursor_kind,
                    cursor_value = EXCLUDED.cursor_value,
                    updated_at = now()
                """,
                (
                    checkpoint.worker_name,
                    checkpoint.cursor_kind.value,
                    checkpoint.cursor_value,
                ),
            )

    def clear(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM projection_checkpoints")