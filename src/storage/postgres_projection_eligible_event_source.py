from __future__ import annotations

from psycopg import Connection
from psycopg.rows import dict_row

from src.pipeline.projection.order_projection_definition import (
    require_current_order_state_projection,
)
from src.storage.order_event_hydration import (
    row_to_order_event,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord


class PostgresProjectionEligibleEventSource:
    """Discover visible accepted events eligible for per-order projection.

    Responsibility:
    - return events whose local sequence is exactly one greater than durable
      progress for the same projection definition, epoch, and order;
    - use ``global_position`` only as deterministic scheduling metadata.

    Inputs and outputs:
    - the caller supplies the current production definition and a positive
      limit;
    - returned records retain global-position lineage around the domain event.

    Connection and transaction ownership:
    - the caller owns the connection and transaction;
    - this source never commits or rolls back.

    Invariants:
    - absent progress means sequence zero;
    - local gaps fail closed because only the exact next sequence is eligible;
    - progress for one order cannot exclude events for another order.

    Non-goals:
    - proving that no event can commit later;
    - global committed-history ordering;
    - worker leasing or event claiming.
    """

    def __init__(self, connection: Connection) -> None:
        """Bind eligible-event discovery to a caller-owned connection.

        Construction performs no query and starts no transaction. A worker must
        share this exact connection with state and progress persistence. This
        source does not claim events or establish multi-worker coordination.
        """
        self.connection = connection

    def load_eligible(
        self,
        *,
        projection_name: str,
        projection_epoch: int,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        """Return currently visible exact-next events in deterministic order.

        ``projection_name`` and ``projection_epoch`` must match the immutable
        production definition ``order_state_projection`` epoch 1; positive
        ``limit`` bounds the result. Each returned event is exactly one local
        sequence beyond its order's durable progress, with absent progress
        treated as zero. The caller owns the connection transaction. This read
        neither claims events, supports concurrent epochs, nor proves that no
        event can commit later.
        """
        require_current_order_state_projection(
            projection_name=projection_name,
            projection_epoch=projection_epoch,
        )
        if limit <= 0:
            raise ValueError("limit must be positive")

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    event.global_position,
                    event.accepted_event_id,
                    event.order_id,
                    event.sequence,
                    event.event_type,
                    event.request_id,
                    event.amount,
                    event.occurred_at_ms,
                    event.proof_prev_event_id,
                    event.proof_prev_version,
                    event.proof_prev_status
                FROM order_events AS event
                LEFT JOIN projection_order_progress AS progress
                  ON progress.projection_name = %(projection_name)s
                 AND progress.projection_epoch = %(projection_epoch)s
                 AND progress.order_id = event.order_id
                WHERE
                    event.sequence = COALESCE(progress.last_sequence, 0) + 1
                ORDER BY
                    event.global_position ASC,
                    event.order_id ASC,
                    event.sequence ASC
                LIMIT %(limit)s
                """,
                {
                    "projection_name": projection_name,
                    "projection_epoch": projection_epoch,
                    "limit": limit,
                },
            )
            rows = cursor.fetchall()

        return [
            ProjectionEventRecord(
                global_position=row["global_position"],
                event=row_to_order_event(row),
            )
            for row in rows
        ]
