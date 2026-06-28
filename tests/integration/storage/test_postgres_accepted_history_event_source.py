from __future__ import annotations

from decimal import Decimal

from psycopg import Connection

from src.core.order.enums import EventType
from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.storage.postgres_accepted_history_event_source import (
    PostgresAcceptedHistoryEventSource,
)
from src.storage.postgres_event_store import PostgresEventStore


def make_created_event(
    *,
    order_id: str = "order-001",
    request_id: str = "create-001",
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
    request_id: str = "pay-001",
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=previous_event.order_id,
        sequence=previous_event.sequence + 1,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=previous_event.sequence,
            prev_event_id=previous_event.event_id,
        ),
    )


def test_load_returns_empty_list_when_order_has_no_accepted_history(
    db_connection: Connection,
    clean_database: None,
) -> None:
    source = PostgresAcceptedHistoryEventSource(db_connection)

    loaded_events = source.load("missing-order")

    assert loaded_events == []


def test_load_returns_accepted_events_ordered_by_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresAcceptedHistoryEventSource(db_connection)

    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    event_store.append(created_event, expected_current_version=0)
    event_store.append(paid_event, expected_current_version=1)

    loaded_events = source.load("order-001")

    assert [event.sequence for event in loaded_events] == [1, 2]
    assert [event.event_type for event in loaded_events] == [
        EventType.CREATED,
        EventType.PAID,
    ]

    assert loaded_events[0].event_id == created_event.event_id
    assert loaded_events[0].order_id == "order-001"
    assert loaded_events[0].request_id == "create-001"
    assert loaded_events[0].amount == Decimal("100.00")
    assert loaded_events[0].proof.prev_status == OrderStatus.INIT
    assert loaded_events[0].proof.prev_version == 0
    assert loaded_events[0].proof.prev_event_id is None

    assert loaded_events[1].event_id == paid_event.event_id
    assert loaded_events[1].order_id == "order-001"
    assert loaded_events[1].request_id == "pay-001"
    assert loaded_events[1].amount == Decimal("100.00")
    assert loaded_events[1].proof.prev_status == OrderStatus.CREATED
    assert loaded_events[1].proof.prev_version == 1
    assert loaded_events[1].proof.prev_event_id == created_event.event_id


def test_load_filters_events_by_order_id(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresAcceptedHistoryEventSource(db_connection)

    order_001_created = make_created_event(
        order_id="order-001",
        request_id="create-001",
    )
    order_002_created = make_created_event(
        order_id="order-002",
        request_id="create-002",
    )

    event_store.append(order_001_created, expected_current_version=0)
    event_store.append(order_002_created, expected_current_version=0)

    loaded_events = source.load("order-001")

    assert len(loaded_events) == 1
    assert loaded_events[0].order_id == "order-001"
    assert loaded_events[0].event_id == order_001_created.event_id
    assert loaded_events[0].request_id == "create-001"


def test_load_preserves_event_hydration_fields(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresAcceptedHistoryEventSource(db_connection)

    created_event = make_created_event(
        order_id="order-001",
        request_id="create-001",
        amount=Decimal("123.45"),
    )

    event_store.append(created_event, expected_current_version=0)

    loaded_events = source.load("order-001")

    assert len(loaded_events) == 1

    loaded_event = loaded_events[0]

    assert loaded_event.event_id == created_event.event_id
    assert loaded_event.request_id == created_event.request_id
    assert loaded_event.order_id == created_event.order_id
    assert loaded_event.sequence == created_event.sequence
    assert loaded_event.event_type == created_event.event_type
    assert loaded_event.amount == Decimal("123.45")
    assert loaded_event.proof.prev_status == OrderStatus.INIT
    assert loaded_event.proof.prev_version == 0
    assert loaded_event.proof.prev_event_id is None


def test_load_does_not_mutate_accepted_history(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresAcceptedHistoryEventSource(db_connection)

    created_event = make_created_event()

    event_store.append(created_event, expected_current_version=0)

    first_load = source.load("order-001")
    second_load = source.load("order-001")

    assert first_load == second_load
    assert len(second_load) == 1
    assert second_load[0].event_id == created_event.event_id