from uuid import uuid4

from psycopg import Connection

from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_eligible_event_source import (
    PostgresProjectionEligibleEventSource,
)
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.projection_progress_store import ProjectionOrderProgress
from tests.shared.order_events import make_created_event


def test_discovery_returns_only_exact_next_events_for_each_order(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)
    source = PostgresProjectionEligibleEventSource(db_connection)
    event_a = make_created_event(order_id="eligible-order-a", request_id="request-a")
    event_b = make_created_event(order_id="eligible-order-b", request_id="request-b")

    event_store.append(event_a, expected_current_version=0)
    event_store.append(event_b, expected_current_version=0)
    db_connection.commit()

    first = source.load_eligible(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        limit=1,
    )[0]
    progress_store.advance_progress(
        ProjectionOrderProgress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=first.event.order_id,
            last_sequence=first.event.sequence,
            last_event_id=first.event.event_id,
            last_global_position=first.global_position,
        )
    )
    db_connection.commit()

    remaining = source.load_eligible(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        limit=10,
    )

    assert [record.event.event_id for record in remaining] == [event_b.event_id]


def test_rolled_back_global_position_does_not_block_other_orders(
    db_connection: Connection,
    db_connection_factory,
    clean_database: None,
) -> None:
    rolled_back_connection = db_connection_factory()
    try:
        rolled_back_connection.rollback()
        rolled_back_store = PostgresEventStore(rolled_back_connection)
        rolled_back_event = make_created_event(
            order_id="rolled-back-order",
            request_id="rolled-back-request",
        )
        rolled_back_store.append(rolled_back_event, expected_current_version=0)
        rolled_back_connection.rollback()

        committed_event = make_created_event(
            order_id="committed-order",
            request_id="committed-request",
        )
        PostgresEventStore(db_connection).append(
            committed_event,
            expected_current_version=0,
        )
        db_connection.commit()

        records = PostgresProjectionEligibleEventSource(db_connection).load_eligible(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            limit=10,
        )

        assert [record.event.event_id for record in records] == [
            committed_event.event_id
        ]
    finally:
        rolled_back_connection.close()


def test_order_local_sequence_gap_is_not_eligible(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_id = uuid4()
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO order_events (
                accepted_event_id,
                order_id,
                sequence,
                event_type,
                request_id,
                amount,
                occurred_at_ms,
                proof_prev_event_id,
                proof_prev_version,
                proof_prev_status
            )
            VALUES (%s, %s, 2, 'PAID', %s, 100.00, 1, %s, 1, 'CREATED')
            """,
            (
                event_id,
                "gapped-order",
                f"gapped-request-{uuid4()}",
                uuid4(),
            ),
        )
    db_connection.commit()

    records = PostgresProjectionEligibleEventSource(db_connection).load_eligible(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        limit=10,
    )

    assert records == []
