import pytest
from psycopg import Connection

from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_event_source import (
    PostgresProjectionEventSource,
)
from tests.shared.order_events import make_created_event


def test_load_after_zero_returns_events_ordered_by_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresProjectionEventSource(db_connection)

    event_a = make_created_event(
        request_id="request-a",
        order_id="order-a",
    )
    event_b = make_created_event(
        request_id="request-b",
        order_id="order-b",
    )

    event_store.append(event_a, expected_current_version=0)
    event_store.append(event_b, expected_current_version=0)
    db_connection.commit()

    records = source.load_after(0, limit=10)

    assert len(records) == 2

    assert records[0].global_position > 0
    assert records[1].global_position > 0
    assert records[0].global_position < records[1].global_position

    assert records[0].event == event_a
    assert records[1].event == event_b


def test_load_after_skips_already_consumed_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresProjectionEventSource(db_connection)

    event_a = make_created_event(
        request_id="request-a",
        order_id="order-a",
    )
    event_b = make_created_event(
        request_id="request-b",
        order_id="order-b",
    )

    event_store.append(event_a, expected_current_version=0)
    event_store.append(event_b, expected_current_version=0)
    db_connection.commit()

    first_batch = source.load_after(0, limit=1)

    assert len(first_batch) == 1

    first_record = first_batch[0]

    remaining_records = source.load_after(first_record.global_position, limit=10)

    assert len(remaining_records) == 1
    assert remaining_records[0].event == event_b
    assert remaining_records[0].global_position > first_record.global_position

def test_load_after_respects_limit(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresProjectionEventSource(db_connection)

    event_a = make_created_event(
        request_id="request-a",
        order_id="order-a",
    )
    event_b = make_created_event(
        request_id="request-b",
        order_id="order-b",
    )

    event_store.append(event_a, expected_current_version=0)
    event_store.append(event_b, expected_current_version=0)
    db_connection.commit()

    records = source.load_after(0, limit=1)

    assert len(records) == 1
    assert records[0].event == event_a


def test_load_after_returns_empty_list_when_no_events_exist(
    db_connection: Connection,
    clean_database: None,
) -> None:
    source = PostgresProjectionEventSource(db_connection)

    records = source.load_after(0, limit=10)

    assert records == []


def test_load_after_rejects_negative_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    source = PostgresProjectionEventSource(db_connection)

    with pytest.raises(ValueError, match="global_position must be non-negative"):
        source.load_after(-1, limit=10)


def test_load_after_rejects_non_positive_limit(
    db_connection: Connection,
    clean_database: None,
) -> None:
    source = PostgresProjectionEventSource(db_connection)

    with pytest.raises(ValueError, match="limit must be positive"):
        source.load_after(0, limit=0)


def test_projection_event_source_preserves_event_identity(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    source = PostgresProjectionEventSource(db_connection)

    event = make_created_event(
        request_id="request-a",
        order_id="order-a",
    )

    event_store.append(event, expected_current_version=0)
    db_connection.commit()

    records = source.load_after(0, limit=10)

    assert len(records) == 1
    assert records[0].event.event_id == event.event_id
    assert records[0].event == event
    assert not hasattr(records[0].event, "global_position")