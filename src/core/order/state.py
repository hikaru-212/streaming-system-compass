from dataclasses import dataclass
from decimal import Decimal

from .enums import OrderStatus


@dataclass(frozen=True)
class OrderState:
    """
    Immutable derived state snapshot for the order domain.

    Why frozen=True:
    - accepted history is the source of truth
    - state is a derived replay / projection result
    - callers should not silently mutate projected state in place
    - a new logical state should appear as a new snapshot

    Important distinction:
    - this is NOT the aggregate execution object
    - the aggregate may remain mutable during command handling / replay
    - this class represents a read-side / snapshot-style value object
    """
    order_id: str
    status: OrderStatus
    total_amount: Decimal
    paid_amount: Decimal
    version: int