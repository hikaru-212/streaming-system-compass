import pytest

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)


def make_event(
    *,
    request_id: str,
    order_id: str,
    sequence: int,
    event_type: EventType,
    amount: float,
) -> OrderEvent:
    # Projection should not depend on proof internals,
    # but accepted write-side events still carry proof in the current core model.
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=event_type,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.INIT if sequence == 1 else OrderStatus.CREATED,
            prev_version=sequence - 1,
            prev_event_id=None,
        ),
    )


def test_build_empty_projection_state():
    state = build_empty_projection_state("order-123")

    assert state.order_id == "order-123"
    assert state.status == OrderStatus.INIT
    assert state.total_amount == 0.0
    assert state.paid_amount == 0.0
    assert state.version == 0


def test_reduce_created_from_init():
    state = build_empty_projection_state("order-123")
    event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=100.0,
    )

    next_state = reduce_order_event(state, event)

    assert next_state.status == OrderStatus.CREATED
    assert next_state.total_amount == 100.0
    assert next_state.paid_amount == 0.0
    assert next_state.version == 1


def test_reduce_paid_from_created():
    created_state = reduce_order_event(
        build_empty_projection_state("order-123"),
        make_event(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=100.0,
        ),
    )

    paid_event = make_event(
        request_id="pay-001",
        order_id="order-123",
        sequence=2,
        event_type=EventType.PAID,
        amount=100.0,
    )

    next_state = reduce_order_event(created_state, paid_event)

    assert next_state.status == OrderStatus.PAID
    assert next_state.total_amount == 100.0
    assert next_state.paid_amount == 100.0
    assert next_state.version == 2


def test_reduce_raises_on_order_id_mismatch():
    state = build_empty_projection_state("order-123")
    event = make_event(
        request_id="create-001",
        order_id="order-999",
        sequence=1,
        event_type=EventType.CREATED,
        amount=100.0,
    )

    with pytest.raises(ValueError, match="order_id mismatch"):
        reduce_order_event(state, event)


def test_reduce_raises_on_sequence_gap():
    state = build_empty_projection_state("order-123")
    event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=2,
        event_type=EventType.CREATED,
        amount=100.0,
    )

    with pytest.raises(ValueError, match="sequence violation"):
        reduce_order_event(state, event)


def test_reduce_raises_on_invalid_paid_amount():
    created_state = reduce_order_event(
        build_empty_projection_state("order-123"),
        make_event(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=100.0,
        ),
    )

    paid_event = make_event(
        request_id="pay-001",
        order_id="order-123",
        sequence=2,
        event_type=EventType.PAID,
        amount=50.0,
    )

    with pytest.raises(ValueError, match="amount mismatch"):
        reduce_order_event(created_state, paid_event)