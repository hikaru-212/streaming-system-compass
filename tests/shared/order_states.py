from __future__ import annotations

from decimal import Decimal

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState


def make_order_state(
    *,
    order_id: str = "order-001",
    status: OrderStatus = OrderStatus.CREATED,
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    version: int = 1,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        version=version,
    )