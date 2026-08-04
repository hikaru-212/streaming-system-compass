from decimal import Decimal

import pytest
from psycopg import Connection

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.state import OrderState
from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
)
from src.pipeline.projection.postgres_worker import PostgresProjectionWorker
from src.storage.postgres_checkpoint_store import (
    CheckpointCursorKind,
    PostgresCheckpointStore,
    ProjectionCheckpoint,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_eligible_event_source import (
    PostgresProjectionEligibleEventSource,
)
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.postgres_projection_store import PostgresProjectionStore


WORKER_NAME = "order-projection-worker"


def make_created_event(
    *,
    request_id: str,
    order_id: str,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=1,
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
    request_id: str,
    order_id: str,
    previous_event: OrderEvent,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=2,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=1,
            prev_event_id=previous_event.event_id,
        ),
    )


def make_created_state(
    *,
    order_id: str,
    total_amount: Decimal = Decimal("100.00"),
    version: int = 1,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=OrderStatus.CREATED,
        total_amount=total_amount,
        paid_amount=Decimal("0.00"),
        version=version,
    )


def test_process_next_returns_no_event_when_accepted_history_is_empty(
    db_connection: Connection,
    clean_database: None,
) -> None:
    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    result = worker.process_next()

    assert result.action == "no_event"
    assert result.global_position is None
    assert result.reason == (
        "no currently visible accepted event is eligible as the next order-local "
        "event for this projection definition and epoch"
    )

    checkpoint_store = PostgresCheckpointStore(db_connection)

    assert checkpoint_store.load_checkpoint(WORKER_NAME) is None


def test_process_next_applies_created_event_and_advances_per_order_progress(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    result = worker.process_next()

    assert result.action == "applied"
    assert result.order_id == "order-001"
    assert result.event_sequence == 1
    assert result.projected_version == 1
    assert result.global_position is not None
    assert result.global_position > 0

    state = projection_store.load_state("order-001")

    assert state is not None
    assert state.order_id == "order-001"
    assert state.status == OrderStatus.CREATED
    assert state.total_amount == Decimal("100.00")
    assert state.paid_amount == Decimal("0.00")
    assert state.version == 1

    progress = progress_store.load_progress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id="order-001",
    )

    assert progress is not None
    assert progress.last_sequence == 1
    assert progress.last_event_id == created_event.event_id
    assert progress.last_global_position == result.global_position
    assert checkpoint_store.load_checkpoint(WORKER_NAME) is None


def test_process_next_applies_paid_event_after_created_event(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )
    paid_event = make_paid_event(
        request_id="request-pay",
        order_id="order-001",
        previous_event=created_event,
    )

    event_store.append(created_event, expected_current_version=0)
    event_store.append(paid_event, expected_current_version=1)
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    first_result = worker.process_next()
    second_result = worker.process_next()

    assert first_result.action == "applied"
    assert first_result.event_sequence == 1

    assert second_result.action == "applied"
    assert second_result.event_sequence == 2
    assert second_result.global_position is not None
    assert first_result.global_position is not None
    assert second_result.global_position > first_result.global_position

    state = projection_store.load_state("order-001")

    assert state is not None
    assert state.status == OrderStatus.PAID
    assert state.total_amount == Decimal("100.00")
    assert state.paid_amount == Decimal("100.00")
    assert state.version == 2

    progress = progress_store.load_progress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id="order-001",
    )

    assert progress is not None
    assert progress.last_sequence == 2
    assert progress.last_event_id == paid_event.event_id
    assert progress.last_global_position == second_result.global_position


def test_process_next_resumes_from_existing_per_order_progress(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )
    paid_event = make_paid_event(
        request_id="request-pay",
        order_id="order-001",
        previous_event=created_event,
    )

    event_store.append(created_event, expected_current_version=0)
    event_store.append(paid_event, expected_current_version=1)
    db_connection.commit()

    first_worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    first_result = first_worker.process_next()

    assert first_result.action == "applied"
    assert first_result.event_sequence == 1

    resumed_worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    second_result = resumed_worker.process_next()

    assert second_result.action == "applied"
    assert second_result.event_sequence == 2

    state = projection_store.load_state("order-001")
    progress = progress_store.load_progress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id="order-001",
    )

    assert state is not None
    assert state.status == OrderStatus.PAID
    assert state.version == 2

    assert progress is not None
    assert progress.last_sequence == 2
    assert progress.last_event_id == paid_event.event_id


def test_process_next_returns_no_event_after_progress_reaches_latest_event(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    first_result = worker.process_next()
    second_result = worker.process_next()

    assert first_result.action == "applied"
    assert second_result.action == "no_event"
    assert second_result.global_position is None


def test_process_next_does_not_bootstrap_from_legacy_global_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)
    created_event = make_created_event(
        request_id="request-create-legacy",
        order_id="order-legacy",
    )
    event_store.append(created_event, expected_current_version=0)

    checkpoint_store.save_checkpoint(
        ProjectionCheckpoint(
            worker_name=WORKER_NAME,
            cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
            cursor_value=str(10**12),
        )
    )
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    result = worker.process_next()

    assert result.action == "applied"
    assert result.order_id == created_event.order_id
    assert result.event_sequence == 1
    checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)
    assert checkpoint is not None
    assert checkpoint.cursor_value == str(10**12)


def test_process_next_fails_fast_when_projection_state_is_ahead_of_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)

    projection_store.save_state(
        make_created_state(
            order_id="order-001",
            version=1,
        )
    )

    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    with pytest.raises(ValueError):
        worker.process_next()

    state = projection_store.load_state("order-001")
    progress = progress_store.load_progress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id="order-001",
    )

    assert state is not None
    assert state.status == OrderStatus.CREATED
    assert state.version == 1

    assert progress is None


def test_projection_state_and_progress_rollback_together_on_progress_failure(
    db_connection: Connection,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
        projection_store=projection_store,
        progress_store=progress_store,
    )
    advance_progress = worker.progress_store.advance_progress

    def fail_advance_progress(*args, **kwargs) -> None:
        raise RuntimeError("simulated progress failure")

    monkeypatch.setattr(
        worker.progress_store,
        "advance_progress",
        fail_advance_progress,
    )

    with pytest.raises(RuntimeError, match="simulated progress failure"):
        worker.process_next()

    assert projection_store.load_state("order-001") is None
    assert (
        progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id="order-001",
        )
        is None
    )
    db_connection.rollback()

    monkeypatch.setattr(
        worker.progress_store,
        "advance_progress",
        advance_progress,
    )
    retried_result = worker.process_next()
    assert retried_result.action == "applied"
    assert retried_result.order_id == created_event.order_id


@pytest.mark.parametrize(
    "collaborator_name",
    ["event_source", "projection_store", "progress_store"],
)
def test_worker_rejects_collaborator_on_different_connection(
    db_connection: Connection,
    db_connection_factory,
    clean_database: None,
    collaborator_name: str,
) -> None:
    other_connection = db_connection_factory()
    other_connection.rollback()
    try:
        collaborators = {
            "event_source": PostgresProjectionEligibleEventSource(db_connection),
            "projection_store": PostgresProjectionStore(db_connection),
            "progress_store": PostgresProjectionProgressStore(db_connection),
        }
        if collaborator_name == "event_source":
            collaborators[collaborator_name] = (
                PostgresProjectionEligibleEventSource(other_connection)
            )
        elif collaborator_name == "projection_store":
            collaborators[collaborator_name] = PostgresProjectionStore(
                other_connection
            )
        else:
            collaborators[collaborator_name] = PostgresProjectionProgressStore(
                other_connection
            )

        with pytest.raises(
            ValueError,
            match=f"{collaborator_name} must share the exact worker connection",
        ):
            PostgresProjectionWorker(
                db_connection,
                worker_name=f"{WORKER_NAME}-{collaborator_name}",
                **collaborators,
            )
    finally:
        other_connection.close()


def test_process_next_rejects_outer_transaction_before_processing(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    event = make_created_event(
        request_id="request-outer-transaction",
        order_id="order-outer-transaction",
    )
    event_store.append(event, expected_current_version=0)
    db_connection.commit()
    worker = PostgresProjectionWorker(db_connection, worker_name=WORKER_NAME)

    db_connection.execute("SELECT 1")
    with pytest.raises(RuntimeError, match="requires an idle connection"):
        worker.process_next()
    db_connection.rollback()

    assert PostgresProjectionStore(db_connection).load_state(event.order_id) is None


def test_worker_name_is_not_independent_projection_progress_identity(
    db_connection: Connection,
    clean_database: None,
) -> None:
    # This is a sequential identity check, not a competing-worker guarantee.
    # The production boundary remains one active worker per definition/epoch.
    event_store = PostgresEventStore(db_connection)
    event = make_created_event(
        request_id="request-shared-progress",
        order_id="order-shared-progress",
    )
    event_store.append(event, expected_current_version=0)
    db_connection.commit()

    first = PostgresProjectionWorker(
        db_connection,
        worker_name=f"{WORKER_NAME}-one",
    )
    second = PostgresProjectionWorker(
        db_connection,
        worker_name=f"{WORKER_NAME}-two",
    )

    assert first.process_next().action == "applied"
    assert second.process_next().action == "no_event"
