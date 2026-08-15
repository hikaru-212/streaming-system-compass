from __future__ import annotations

from psycopg import Connection
from psycopg.rows import dict_row

from src.storage.order_event_hydration import (
    ORDER_EVENT_SELECT_COLUMNS,
    row_to_order_event,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord


class PostgresOrderEventTailSource:
    """Load one order's accepted-history tail by aggregate-local sequence.

    Responsibility:
    - read accepted events for one order strictly after a local sequence;
    - order the result by local sequence;
    - retain ``global_position`` only as lineage metadata.

    Connection and transaction ownership:
    - the caller owns the supplied connection and transaction;
    - this source performs no commit, rollback, fallback, or trust decision.

    Important invariant:
    - unrelated orders cannot advance this tail cursor.
    """

    def __init__(self, connection: Connection) -> None:
        """Bind same-order tail reads to a caller-owned connection.

        Construction performs no read and starts no transaction. PostgreSQL
        observation orchestration must supply the transaction boundary. This
        source establishes neither snapshot trust nor fallback policy.
        """
        self.connection = connection

    def load_after_sequence(
        self,
        order_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        """Return one order's visible events after a local sequence.

        ``order_id`` must be non-empty, ``sequence`` non-negative, and ``limit``
        positive. Results contain only that order and are ordered by ascending
        local sequence; global position is returned only as lineage. The caller
        owns the connection transaction. This method does not establish
        snapshot trust, fill sequence gaps, or choose fallback policy.
        """
        if not order_id.strip():
            raise ValueError("order_id must not be empty")
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if limit <= 0:
            raise ValueError("limit must be positive")

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    global_position,
                    {ORDER_EVENT_SELECT_COLUMNS}
                FROM order_events
                WHERE order_id = %(order_id)s
                  AND sequence > %(sequence)s
                ORDER BY sequence ASC
                LIMIT %(limit)s
                """,
                {"order_id": order_id, "sequence": sequence, "limit": limit},
            )
            rows = cursor.fetchall()

        return [
            ProjectionEventRecord(
                global_position=row["global_position"],
                event=row_to_order_event(row),
            )
            for row in rows
        ]
