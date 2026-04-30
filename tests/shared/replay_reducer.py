from typing import Iterable

from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.state import OrderState


def reduce_history_to_state(history: Iterable[OrderEvent]) -> OrderState:
    """
    Test-side replay helper used to validate replay consistency.

    Why this lives under tests/ for now:
    - it supports replay-baseline verification before Phase 3 projection runtime
    - it is intentionally lightweight
    - it is not yet the formal projection worker or read-side runtime module

    Important rule:
    - this helper must stay aligned with the currently accepted event semantics
    - once Phase 3 starts formally, this logic should be promoted into src/pipeline/projection/
    """
    current_state = OrderState(
        order_id="unknown",
        status=OrderStatus.INIT,
        total_amount=0.0,
        paid_amount=0.0,
        version=0,
    )

    for event in history:
        expected_next_sequence = current_state.version + 1
        if event.sequence != expected_next_sequence:
            raise ValueError(
                f"Broken sequence during replay reduction: "
                f"expected {expected_next_sequence}, got {event.sequence}"
            )

        if event.event_type.value == "created":
            current_state = OrderState(
                order_id=event.order_id,
                status=OrderStatus.CREATED,
                total_amount=event.amount,
                paid_amount=0.0,
                version=event.sequence,
            )
        elif event.event_type.value == "paid":
            current_state = OrderState(
                order_id=event.order_id,
                status=OrderStatus.PAID,
                total_amount=current_state.total_amount,
                paid_amount=event.amount,
                version=event.sequence,
            )

    return current_state