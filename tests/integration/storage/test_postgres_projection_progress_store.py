import pytest
from psycopg import Connection

from src.core.order.events import OrderEvent
from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_event_source import PostgresProjectionEventSource
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.projection_progress_store import (
    ProjectionOrderProgress,
    ProjectionProgressConflictError,
)
from tests.shared.order_events import make_created_event, make_paid_event


def _progress_for_event(
    connection: Connection,
    event: OrderEvent,
) -> ProjectionOrderProgress:
    records = PostgresProjectionEventSource(connection).load_after(0, limit=100)
    record = next(item for item in records if item.event.event_id == event.event_id)
    return ProjectionOrderProgress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id=event.order_id,
        last_sequence=event.sequence,
        last_event_id=event.event_id,
        last_global_position=record.global_position,
    )


def test_missing_progress_means_sequence_zero(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionProgressStore(db_connection)

    assert (
        store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id="missing-order",
        )
        is None
    )


def test_progress_advances_only_by_exact_next_order_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    store = PostgresProjectionProgressStore(db_connection)
    created = make_created_event(order_id="order-progress")
    paid = make_paid_event(previous_event=created)

    event_store.append(created, expected_current_version=0)
    event_store.append(paid, expected_current_version=1)
    db_connection.commit()

    created_progress = _progress_for_event(db_connection, created)
    paid_progress = _progress_for_event(db_connection, paid)

    store.advance_progress(created_progress)
    store.advance_progress(paid_progress)
    db_connection.commit()

    assert (
        store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=created.order_id,
        )
        == paid_progress
    )


def test_progress_rejects_missing_predecessor_regression_and_skip(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    store = PostgresProjectionProgressStore(db_connection)
    created = make_created_event(order_id="order-progress-guard")
    paid = make_paid_event(previous_event=created)

    event_store.append(created, expected_current_version=0)
    event_store.append(paid, expected_current_version=1)
    db_connection.commit()

    created_progress = _progress_for_event(db_connection, created)
    paid_progress = _progress_for_event(db_connection, paid)

    with pytest.raises(ProjectionProgressConflictError):
        store.advance_progress(paid_progress)
    db_connection.rollback()

    store.advance_progress(created_progress)
    db_connection.commit()

    with pytest.raises(ProjectionProgressConflictError):
        store.advance_progress(created_progress)
    db_connection.rollback()

    skipped_progress = ProjectionOrderProgress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id=created.order_id,
        last_sequence=3,
        last_event_id=paid.event_id,
        last_global_position=paid_progress.last_global_position,
    )
    with pytest.raises(ProjectionProgressConflictError):
        store.advance_progress(skipped_progress)
    db_connection.rollback()


def test_progress_write_rolls_back_with_caller_transaction(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    store = PostgresProjectionProgressStore(db_connection)
    created = make_created_event(order_id="order-progress-rollback")

    event_store.append(created, expected_current_version=0)
    db_connection.commit()
    progress = _progress_for_event(db_connection, created)

    store.advance_progress(progress)
    db_connection.rollback()

    assert (
        store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=created.order_id,
        )
        is None
    )
