from collections.abc import Callable
from contextlib import closing
from uuid import uuid4

from psycopg import Connection

from src.core.order.enums import OrderStatus
from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
)
from src.pipeline.projection.postgres_worker import PostgresProjectionWorker
from src.storage.postgres_checkpoint_store import PostgresCheckpointStore
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.postgres_projection_store import PostgresProjectionStore
from tests.shared.order_events import make_created_event


def load_global_position(
    connection: Connection,
    *,
    accepted_event_id: str,
) -> int | None:
    """Return one event's PostgreSQL-assigned global position if visible.

    The supplied connection determines the transaction visibility boundary.
    Returning ``None`` therefore means that this connection cannot currently
    observe the accepted-event row; it does not prove that another open
    transaction has not already allocated the position.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT global_position
            FROM order_events
            WHERE accepted_event_id = %s
            """,
            (accepted_event_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return int(row[0])


def test_worker_processes_late_committing_lower_global_position_per_order(
    db_connection: Connection,
    db_connection_factory: Callable[[], Connection],
    clean_database: None,
) -> None:
    """A higher committed position must not permanently exclude a lower one.

    This deterministic schedule proves that projection progress is scoped by
    order-local sequence rather than by one scalar global-position frontier.
    """
    run_id = uuid4().hex
    event_a = make_created_event(
        request_id=f"stage-3-5c-request-a-{run_id}",
        order_id=f"stage-3-5c-order-a-{run_id}",
    )
    event_b = make_created_event(
        request_id=f"stage-3-5c-request-b-{run_id}",
        order_id=f"stage-3-5c-order-b-{run_id}",
    )
    worker_name = f"stage-3-5c-worker-{run_id}"

    assert event_a.event_id != event_b.event_id
    assert event_a.request_id != event_b.request_id
    assert event_a.order_id != event_b.order_id

    # Ensure the fixture connection is not already inside an implicit transaction.
    db_connection.rollback()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=worker_name,
    )

    with (
        closing(db_connection_factory()) as lower_position_connection,
        closing(db_connection_factory()) as higher_position_connection,
        closing(db_connection_factory()) as observer_connection,
    ):
        lower_position_connection.rollback()
        higher_position_connection.rollback()
        observer_connection.rollback()

        observer_projection_store = PostgresProjectionStore(observer_connection)
        observer_checkpoint_store = PostgresCheckpointStore(observer_connection)
        observer_progress_store = PostgresProjectionProgressStore(observer_connection)
        observer_event_store = PostgresEventStore(observer_connection)

        lower_event_store = PostgresEventStore(lower_position_connection)
        lower_event_store.append(event_a, expected_current_version=0)
        position_a = load_global_position(
            lower_position_connection,
            accepted_event_id=event_a.event_id,
        )

        assert position_a is not None

        higher_event_store = PostgresEventStore(higher_position_connection)
        higher_event_store.append(event_b, expected_current_version=0)
        position_b = load_global_position(
            higher_position_connection,
            accepted_event_id=event_b.event_id,
        )

        assert position_b is not None
        assert position_a < position_b

        higher_position_connection.commit()

        # T2 is committed here while T1 remains open and uncommitted.
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_b.event_id,
            )
            == position_b
        )
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_a.event_id,
            )
            is None
        )
        observer_connection.rollback()

        first_result = worker.process_next()

        assert first_result.action == "applied"
        assert first_result.global_position == position_b
        assert first_result.order_id == event_b.order_id
        assert first_result.event_sequence == 1
        assert first_result.projected_version == 1

        projected_b_after_first_run = observer_projection_store.load_state(
            event_b.order_id
        )
        progress_b_after_first_run = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_b.order_id,
        )

        assert projected_b_after_first_run is not None
        assert projected_b_after_first_run.status == OrderStatus.CREATED
        assert projected_b_after_first_run.version == 1
        assert observer_projection_store.load_state(event_a.order_id) is None
        assert progress_b_after_first_run is not None
        assert progress_b_after_first_run.last_sequence == 1
        assert progress_b_after_first_run.last_event_id == event_b.event_id
        assert progress_b_after_first_run.last_global_position == position_b
        assert observer_checkpoint_store.load_checkpoint(worker_name) is None
        observer_connection.rollback()

        lower_position_connection.commit()

        # T1 commits here after the worker has durably progressed order B.
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_a.event_id,
            )
            == position_a
        )
        assert position_a < position_b
        observer_connection.rollback()

        second_result = worker.process_next()

        assert second_result.action == "applied"
        assert second_result.global_position == position_a
        assert second_result.order_id == event_a.order_id

        third_result = worker.process_next()
        assert third_result.action == "no_event"

        final_projected_a = observer_projection_store.load_state(event_a.order_id)
        final_projected_b = observer_projection_store.load_state(event_b.order_id)
        final_checkpoint = observer_checkpoint_store.load_checkpoint(worker_name)
        final_progress_a = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_a.order_id,
        )
        final_progress_b = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_b.order_id,
        )
        durable_event_a_history = observer_event_store.load(event_a.order_id)

        assert final_projected_a is not None
        assert final_projected_a.status == OrderStatus.CREATED
        assert final_projected_a.version == 1
        assert final_projected_b is not None
        assert final_projected_b.status == OrderStatus.CREATED
        assert final_projected_b.version == 1
        assert final_progress_a is not None
        assert final_progress_a.last_event_id == event_a.event_id
        assert final_progress_a.last_global_position == position_a
        assert final_progress_b == progress_b_after_first_run
        assert final_checkpoint is None
        assert durable_event_a_history == [event_a]


def test_replacement_worker_recovers_late_commit_from_durable_progress(
    db_connection: Connection,
    db_connection_factory: Callable[[], Connection],
    clean_database: None,
) -> None:
    """A fresh worker connection and identity must continue repaired progress.

    The first worker processes the higher-position committed event and is then
    fully disposed. A replacement worker with a different ``worker_name`` and
    PostgreSQL connection must still discover the later-committing lower
    position because durable progress belongs to the projection definition,
    epoch, and order—not to either worker instance.
    """
    run_id = uuid4().hex
    event_a = make_created_event(
        request_id=f"restart-request-a-{run_id}",
        order_id=f"restart-order-a-{run_id}",
    )
    event_b = make_created_event(
        request_id=f"restart-request-b-{run_id}",
        order_id=f"restart-order-b-{run_id}",
    )
    initial_worker_name = f"restart-initial-worker-{run_id}"
    replacement_worker_name = f"restart-replacement-worker-{run_id}"

    db_connection.rollback()

    with (
        closing(db_connection_factory()) as lower_position_connection,
        closing(db_connection_factory()) as higher_position_connection,
        closing(db_connection_factory()) as observer_connection,
    ):
        lower_position_connection.rollback()
        higher_position_connection.rollback()
        observer_connection.rollback()

        observer_projection_store = PostgresProjectionStore(observer_connection)
        observer_progress_store = PostgresProjectionProgressStore(observer_connection)
        observer_checkpoint_store = PostgresCheckpointStore(observer_connection)
        observer_event_store = PostgresEventStore(observer_connection)

        PostgresEventStore(lower_position_connection).append(
            event_a,
            expected_current_version=0,
        )
        position_a = load_global_position(
            lower_position_connection,
            accepted_event_id=event_a.event_id,
        )
        assert position_a is not None

        PostgresEventStore(higher_position_connection).append(
            event_b,
            expected_current_version=0,
        )
        position_b = load_global_position(
            higher_position_connection,
            accepted_event_id=event_b.event_id,
        )
        assert position_b is not None
        assert position_a < position_b
        higher_position_connection.commit()

        # The independent observer sees only the higher-position committed row.
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_b.event_id,
            )
            == position_b
        )
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_a.event_id,
            )
            is None
        )
        observer_connection.rollback()

        # Worker process/connection generation 1 handles order B and disappears.
        with closing(db_connection_factory()) as initial_worker_connection:
            initial_worker_connection.rollback()
            initial_worker = PostgresProjectionWorker(
                initial_worker_connection,
                worker_name=initial_worker_name,
            )

            first_result = initial_worker.process_next()

            assert first_result.action == "applied"
            assert first_result.global_position == position_b
            assert first_result.order_id == event_b.order_id
            assert first_result.event_sequence == 1
            assert first_result.projected_version == 1

        # The first worker connection is closed before the lower transaction commits.
        projected_b = observer_projection_store.load_state(event_b.order_id)
        progress_b = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_b.order_id,
        )

        assert projected_b is not None
        assert projected_b.status == OrderStatus.CREATED
        assert projected_b.version == 1
        assert observer_projection_store.load_state(event_a.order_id) is None
        assert progress_b is not None
        assert progress_b.last_sequence == 1
        assert progress_b.last_event_id == event_b.event_id
        assert progress_b.last_global_position == position_b
        assert (
            observer_checkpoint_store.load_checkpoint(initial_worker_name)
            is None
        )
        observer_connection.rollback()

        lower_position_connection.commit()

        # The lower position becomes durable only after worker generation 1 is gone.
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=event_a.event_id,
            )
            == position_a
        )
        assert position_a < position_b
        observer_connection.rollback()

        # Worker generation 2 uses a fresh connection and a different worker name.
        with closing(db_connection_factory()) as replacement_worker_connection:
            replacement_worker_connection.rollback()
            replacement_worker = PostgresProjectionWorker(
                replacement_worker_connection,
                worker_name=replacement_worker_name,
            )

            second_result = replacement_worker.process_next()
            third_result = replacement_worker.process_next()

            assert second_result.action == "applied"
            assert second_result.global_position == position_a
            assert second_result.order_id == event_a.order_id
            assert second_result.event_sequence == 1
            assert second_result.projected_version == 1
            assert third_result.action == "no_event"

        final_projected_a = observer_projection_store.load_state(event_a.order_id)
        final_projected_b = observer_projection_store.load_state(event_b.order_id)
        final_progress_a = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_a.order_id,
        )
        final_progress_b = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=event_b.order_id,
        )
        durable_event_a_history = observer_event_store.load(event_a.order_id)

        assert final_projected_a is not None
        assert final_projected_a.status == OrderStatus.CREATED
        assert final_projected_a.version == 1
        assert final_projected_b == projected_b

        assert final_progress_a is not None
        assert final_progress_a.last_sequence == 1
        assert final_progress_a.last_event_id == event_a.event_id
        assert final_progress_a.last_global_position == position_a
        assert final_progress_b == progress_b

        assert (
            observer_checkpoint_store.load_checkpoint(initial_worker_name)
            is None
        )
        assert (
            observer_checkpoint_store.load_checkpoint(replacement_worker_name)
            is None
        )
        assert durable_event_a_history == [event_a]


def test_rolled_back_lower_global_position_does_not_block_other_order(
    db_connection: Connection,
    db_connection_factory: Callable[[], Connection],
    clean_database: None,
) -> None:
    """A consumed but rolled-back sequence value creates no event obligation."""
    run_id = uuid4().hex
    rolled_back_event = make_created_event(
        request_id=f"rollback-request-a-{run_id}",
        order_id=f"rollback-order-a-{run_id}",
    )
    committed_event = make_created_event(
        request_id=f"rollback-request-b-{run_id}",
        order_id=f"rollback-order-b-{run_id}",
    )
    worker_name = f"rollback-worker-{run_id}"
    db_connection.rollback()
    worker = PostgresProjectionWorker(db_connection, worker_name=worker_name)

    with (
        closing(db_connection_factory()) as lower_position_connection,
        closing(db_connection_factory()) as higher_position_connection,
        closing(db_connection_factory()) as observer_connection,
    ):
        lower_position_connection.rollback()
        higher_position_connection.rollback()
        observer_connection.rollback()

        PostgresEventStore(lower_position_connection).append(
            rolled_back_event,
            expected_current_version=0,
        )
        rolled_back_position = load_global_position(
            lower_position_connection,
            accepted_event_id=rolled_back_event.event_id,
        )
        assert rolled_back_position is not None

        PostgresEventStore(higher_position_connection).append(
            committed_event,
            expected_current_version=0,
        )
        committed_position = load_global_position(
            higher_position_connection,
            accepted_event_id=committed_event.event_id,
        )
        assert committed_position is not None
        assert rolled_back_position < committed_position
        higher_position_connection.commit()
        lower_position_connection.rollback()

        result = worker.process_next()

        assert result.action == "applied"
        assert result.order_id == committed_event.order_id
        assert result.global_position == committed_position

        observer_progress_store = PostgresProjectionProgressStore(
            observer_connection
        )
        assert (
            observer_progress_store.load_progress(
                projection_name=ORDER_STATE_PROJECTION_NAME,
                projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
                order_id=rolled_back_event.order_id,
            )
            is None
        )
        committed_progress = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=committed_event.order_id,
        )
        assert committed_progress is not None
        assert committed_progress.last_global_position == committed_position
        assert (
            load_global_position(
                observer_connection,
                accepted_event_id=rolled_back_event.event_id,
            )
            is None
        )
