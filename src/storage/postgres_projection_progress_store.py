from __future__ import annotations

from psycopg import Connection
from psycopg.rows import dict_row

from src.pipeline.projection.order_projection_definition import (
    require_current_order_state_projection,
)
from src.storage.projection_progress_store import (
    ProjectionOrderProgress,
    ProjectionProgressConflictError,
    ProjectionProgressStoreProtocol,
)


class PostgresProjectionProgressStore(ProjectionProgressStoreProtocol):
    """Persist exact-next per-order projection progress in PostgreSQL.

    Responsibility:
    - load progress by the current projection definition, epoch, and order;
    - atomically advance progress only when accepted-event lineage matches and
      the incoming sequence is exactly the durable next local sequence.

    Connection and transaction ownership:
    - the caller owns the supplied connection and transaction;
    - this store never commits or rolls back;
    - a worker must share this exact connection with its state store and source.

    Non-goals:
    - global cursor management;
    - worker leasing or multi-worker claims;
    - retry policy;
    - accepted-history mutation.
    """

    def __init__(self, connection: Connection) -> None:
        """Bind progress persistence to a caller-owned PostgreSQL connection.

        The same connection must be shared with worker discovery and state
        persistence when atomic application is required. Construction starts
        no transaction and performs no schema setup, retry, or policy action.
        """
        self.connection = connection

    def load_progress(
        self,
        *,
        projection_name: str,
        projection_epoch: int,
        order_id: str,
    ) -> ProjectionOrderProgress | None:
        """Return progress for one projection/epoch/order identity.

        A missing row returns ``None`` and represents local sequence zero.
        Projection identity must be the supported production
        ``order_state_projection`` epoch 1, and ``order_id`` must be non-empty.
        The caller owns transaction and connection lifetime; this read performs
        no locking, retry, epoch selection, or policy decision.
        """
        _validate_identity(
            projection_name=projection_name,
            projection_epoch=projection_epoch,
            order_id=order_id,
        )

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    last_event_id,
                    last_global_position
                FROM projection_order_progress
                WHERE projection_name = %s
                  AND projection_epoch = %s
                  AND order_id = %s
                """,
                (projection_name, projection_epoch, order_id),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return _progress_from_row(row)

    def advance_progress(self, progress: ProjectionOrderProgress) -> None:
        """Advance progress by one with accepted-event lineage verification.

        The single SQL statement admits sequence 1 only when no progress row
        exists, and admits later sequences only when durable progress is exactly
        one lower. Accepted-event identity, order, sequence, and global-position
        lineage must all match. A stale caller, regression, skip, or mismatch
        raises ``ProjectionProgressConflictError``. The caller owns the
        connection transaction, so this update can commit atomically with
        projection state. It performs no retry, leasing, or accepted-history
        mutation.
        """
        require_current_order_state_projection(
            projection_name=progress.projection_name,
            projection_epoch=progress.projection_epoch,
        )
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                WITH accepted_event AS (
                    SELECT
                        order_id,
                        sequence,
                        accepted_event_id,
                        global_position
                    FROM order_events
                    WHERE accepted_event_id = %(last_event_id)s
                      AND order_id = %(order_id)s
                      AND sequence = %(last_sequence)s
                      AND global_position = %(last_global_position)s
                ),
                updated AS (
                    UPDATE projection_order_progress AS progress
                    SET
                        last_sequence = event.sequence,
                        last_event_id = event.accepted_event_id,
                        last_global_position = event.global_position,
                        updated_at = now()
                    FROM accepted_event AS event
                    WHERE progress.projection_name = %(projection_name)s
                      AND progress.projection_epoch = %(projection_epoch)s
                      AND progress.order_id = event.order_id
                      AND progress.last_sequence + 1 = event.sequence
                    RETURNING
                        progress.projection_name,
                        progress.projection_epoch,
                        progress.order_id,
                        progress.last_sequence,
                        progress.last_event_id,
                        progress.last_global_position
                ),
                inserted AS (
                    INSERT INTO projection_order_progress (
                        projection_name,
                        projection_epoch,
                        order_id,
                        last_sequence,
                        last_event_id,
                        last_global_position
                    )
                    SELECT
                        %(projection_name)s,
                        %(projection_epoch)s,
                        event.order_id,
                        event.sequence,
                        event.accepted_event_id,
                        event.global_position
                    FROM accepted_event AS event
                    WHERE event.sequence = 1
                      AND NOT EXISTS (SELECT 1 FROM updated)
                    ON CONFLICT (
                        projection_name,
                        projection_epoch,
                        order_id
                    )
                    DO NOTHING
                    RETURNING
                        projection_name,
                        projection_epoch,
                        order_id,
                        last_sequence,
                        last_event_id,
                        last_global_position
                )
                SELECT
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    last_event_id,
                    last_global_position
                FROM updated
                UNION ALL
                SELECT
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    last_event_id,
                    last_global_position
                FROM inserted
                """,
                {
                    "projection_name": progress.projection_name,
                    "projection_epoch": progress.projection_epoch,
                    "order_id": progress.order_id,
                    "last_sequence": progress.last_sequence,
                    "last_event_id": progress.last_event_id,
                    "last_global_position": progress.last_global_position,
                },
            )
            row = cursor.fetchone()

        if row is None:
            raise ProjectionProgressConflictError(
                "Projection progress must cite accepted-event lineage and advance "
                "by exactly one order-local sequence"
            )


def _validate_identity(
    *,
    projection_name: str,
    projection_epoch: int,
    order_id: str,
) -> None:
    require_current_order_state_projection(
        projection_name=projection_name,
        projection_epoch=projection_epoch,
    )
    if not order_id.strip():
        raise ValueError("order_id must not be empty")


def _progress_from_row(row) -> ProjectionOrderProgress:
    return ProjectionOrderProgress(
        projection_name=row["projection_name"],
        projection_epoch=row["projection_epoch"],
        order_id=row["order_id"],
        last_sequence=row["last_sequence"],
        last_event_id=str(row["last_event_id"]),
        last_global_position=row["last_global_position"],
    )
