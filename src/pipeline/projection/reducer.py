from __future__ import annotations
from decimal import Decimal

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.state import OrderState


def build_empty_projection_state(order_id: str) -> OrderState:
    """
    Build the initial read-side state for one order.

    Important semantics:
    - This is NOT write-side truth creation.
    - This is only the empty derived state before any accepted event is reduced.
    """
    return OrderState(
        order_id=order_id,
        status=OrderStatus.INIT,
        total_amount=Decimal("0.00"),
        paid_amount=Decimal("0.00"),
        version=0,
    )


def reduce_order_event(current_state: OrderState, event: OrderEvent) -> OrderState:
    """
    Pure deterministic projection reducer.

    Responsibility:
    - Transform one accepted event into the next projected state.

    This function intentionally does NOT:
    - load from storage
    - save to storage
    - manage checkpoints / offsets
    - decide skip / retry / buffering policy

    Those responsibilities belong to the projection worker.

    Invariants expected here:
    - event belongs to the same order as current_state
    - event.sequence must be exactly current_state.version + 1
    - event is already accepted history from the write-side boundary

    Even though the worker checks sequence before calling the reducer,
    the reducer still defends its own local invariants so that the pure
    transition function cannot be silently misused by another caller.
    """
    if event.order_id != current_state.order_id:
        raise ValueError(
            f"Projection reducer order_id mismatch: "
            f"state.order_id={current_state.order_id}, event.order_id={event.order_id}"
        )

    expected_next_sequence = current_state.version + 1
    if event.sequence != expected_next_sequence:
        raise ValueError(
            f"Projection reducer sequence violation: "
            f"expected {expected_next_sequence}, got {event.sequence}"
        )

    if event.event_type == EventType.CREATED:
        if current_state.status != OrderStatus.INIT:
            raise ValueError(
                "Projection reducer invalid transition: CREATED must follow INIT"
            )

        return OrderState(
            order_id=current_state.order_id,
            status=OrderStatus.CREATED,
            total_amount=event.amount,
            paid_amount=Decimal("0.00"),
            version=event.sequence,
        )

    if event.event_type == EventType.PAID:
        if current_state.status != OrderStatus.CREATED:
            raise ValueError(
                "Projection reducer invalid transition: PAID must follow CREATED"
            )

        if event.amount != current_state.total_amount:
            raise ValueError(
                "Projection reducer amount mismatch: "
                "PAID amount must equal projected total_amount in v1"
            )

        return OrderState(
            order_id=current_state.order_id,
            status=OrderStatus.PAID,
            total_amount=current_state.total_amount,
            paid_amount=event.amount,
            version=event.sequence,
        )

    raise ValueError(
        f"Projection reducer received unsupported event type: {event.event_type}"
    )