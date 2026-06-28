from __future__ import annotations

from psycopg import Connection

from src.core.order.events import OrderEvent
from src.storage.postgres_event_store import PostgresEventStore


class PostgresAcceptedHistoryEventSource:
    """
    Read-only accepted-history source for replay validators.

    This adapter exposes the accepted-history read boundary needed by
    projection replay validators without giving those validators direct
    access to write-side append/idempotency responsibilities.

    It does NOT:
    - append accepted events
    - mutate accepted history
    - manage idempotency
    - decide admission
    - advance checkpoints
    - write projection state
    - write snapshots

    It only loads accepted events for one order in aggregate-local
    sequence order.

    The current implementation delegates hydration and ordering to
    PostgresEventStore.load(), which is the existing durable accepted-history
    read path for order_events.
    """

    def __init__(self, connection: Connection) -> None:
        self._event_store = PostgresEventStore(connection)

    def load(self, order_id: str) -> list[OrderEvent]:
        return self._event_store.load(order_id)