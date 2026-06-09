from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import dict_row

from src.core.order.events import OrderEvent
from src.storage.order_event_hydration import (
    ORDER_EVENT_SELECT_COLUMNS,
    row_to_order_event,
)


@dataclass(frozen=True)
class ProjectionEventRecord:
    """
    Accepted event record for durable projection consumption.

    global_position is storage / event-log metadata.

    It is not domain event meaning and should not be added to OrderEvent.
    """

    global_position: int
    event: OrderEvent


class PostgresProjectionEventSource:
    """
    PostgreSQL-backed accepted-history event source for projection workers.

    Responsibility:
    - load accepted events after a global event-log position
    - return events ordered by global_position
    - preserve the distinction between domain event and storage cursor metadata

    This source does NOT:
    - run the reducer
    - update projection state
    - update checkpoints
    - commit or rollback transactions
    - validate semantic drift
    - decide replay / rebuild orchestration
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        if global_position < 0:
            raise ValueError("global_position must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    global_position,
                    {ORDER_EVENT_SELECT_COLUMNS}
                FROM order_events
                WHERE global_position > %(global_position)s
                ORDER BY global_position ASC
                LIMIT %(limit)s
                """,
                {
                    "global_position": global_position,
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