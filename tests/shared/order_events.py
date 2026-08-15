from __future__ import annotations

from decimal import Decimal

from src.core.order.enums import EventType
from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


def make_created_event(
    *,
    request_id: str = "create-request-001",
    order_id: str = "order-001",
    sequence: int = 1,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=EventType.CREATED,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )


def make_paid_event(
    *,
    previous_event: OrderEvent,
    request_id: str = "pay-request-001",
    sequence: int | None = None,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    target_sequence = sequence if sequence is not None else previous_event.sequence + 1

    if target_sequence <= previous_event.sequence:
        raise ValueError(
            "paid event sequence must be greater than previous event sequence"
        )

    return OrderEvent.create(
        request_id=request_id,
        order_id=previous_event.order_id,
        sequence=target_sequence,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=previous_event.sequence,
            prev_event_id=previous_event.event_id,
        ),
    )