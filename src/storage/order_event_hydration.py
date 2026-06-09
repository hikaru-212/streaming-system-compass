from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


ORDER_EVENT_SELECT_COLUMNS = """
    accepted_event_id,
    order_id,
    sequence,
    event_type,
    request_id,
    amount,
    occurred_at_ms,
    proof_prev_event_id,
    proof_prev_version,
    proof_prev_status
"""


def row_to_order_event(row: Mapping[str, Any]) -> OrderEvent:
    """
    Hydrate an OrderEvent from an order_events database row.

    This helper is intentionally shared by PostgreSQL storage readers.

    It keeps the database-row-to-domain-event translation in one place so that:
    - PostgresEventStore.load()
    - PostgresEventStore.last_event()
    - PostgresProjectionEventSource.load_after()

    all reconstruct OrderEvent using the same mapping.

    Storage metadata such as global_position should remain outside OrderEvent.
    """

    return OrderEvent(
        event_id=str(row["accepted_event_id"]),
        request_id=row["request_id"],
        order_id=row["order_id"],
        sequence=row["sequence"],
        event_type=EventType(row["event_type"]),
        amount=Decimal(row["amount"]),
        occurred_at_ms=row["occurred_at_ms"],
        proof=Proof(
            prev_event_id=(
                str(row["proof_prev_event_id"])
                if row["proof_prev_event_id"] is not None
                else None
            ),
            prev_version=row["proof_prev_version"],
            prev_status=OrderStatus(row["proof_prev_status"]),
        ),
    )