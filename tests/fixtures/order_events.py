from decimal import Decimal
import pytest

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


def build_created_event(
    request_id: str = "create-001",
    order_id: str = "order-123",
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=1,
        event_type=EventType.CREATED,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )


def build_paid_event(
    created_event: OrderEvent,
    request_id: str = "pay-001",
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=created_event.order_id,
        sequence=2,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=1,
            prev_event_id=created_event.event_id,
        ),
    )


@pytest.fixture
def created_event():
    return build_created_event()


@pytest.fixture
def paid_event(created_event):
    return build_paid_event(created_event)