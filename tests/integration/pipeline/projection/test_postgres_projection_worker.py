from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import Connection

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.state import OrderState
from src.pipeline.projection.postgres_worker import PostgresProjectionWorker
from src.storage.postgres_checkpoint_store import (
    CheckpointCursorKind,
    PostgresCheckpointStore,
    ProjectionCheckpoint,
)
from src.storage.postgres_event_store import PostgresEventStore
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
    assert result.reason == "no accepted event after checkpoint"

    checkpoint_store = PostgresCheckpointStore(db_connection)

    assert checkpoint_store.load_checkpoint(WORKER_NAME) is None


def test_process_next_applies_created_event_and_advances_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
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

    checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    assert checkpoint is not None
    assert checkpoint.cursor_kind == CheckpointCursorKind.GLOBAL_POSITION
    assert checkpoint.cursor_value == str(result.global_position)


def test_process_next_applies_paid_event_after_created_event(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)

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

    checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    assert checkpoint is not None
    assert checkpoint.cursor_kind == CheckpointCursorKind.GLOBAL_POSITION
    assert checkpoint.cursor_value == str(second_result.global_position)


def test_process_next_resumes_from_existing_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)

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
    checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    assert state is not None
    assert state.status == OrderStatus.PAID
    assert state.version == 2

    assert checkpoint is not None
    assert checkpoint.cursor_value == str(second_result.global_position)


def test_process_next_returns_no_event_after_checkpoint_reaches_latest_event(
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


def test_process_next_rejects_non_global_position_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    checkpoint_store = PostgresCheckpointStore(db_connection)

    checkpoint_store.save_checkpoint(
        ProjectionCheckpoint(
            worker_name=WORKER_NAME,
            cursor_kind=CheckpointCursorKind.EVENT_ID,
            cursor_value=str(uuid4()),
        )
    )
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name=WORKER_NAME,
    )

    with pytest.raises(
        ValueError,
        match="requires GLOBAL_POSITION checkpoint",
    ):
        worker.process_next()


def test_process_next_fails_fast_when_projection_state_is_ahead_of_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)

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
    checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    assert state is not None
    assert state.status == OrderStatus.CREATED
    assert state.version == 1

    assert checkpoint is None


def test_projection_state_and_checkpoint_rollback_together_on_checkpoint_failure(
    db_connection: Connection,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
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
        projection_store=projection_store,
        checkpoint_store=checkpoint_store,
    )

    def fail_save_checkpoint(*args, **kwargs) -> None:
        raise RuntimeError("simulated checkpoint failure")

    monkeypatch.setattr(
        worker.checkpoint_store,
        "save_checkpoint",
        fail_save_checkpoint,
    )

    with pytest.raises(RuntimeError, match="simulated checkpoint failure"):
        worker.process_next()

    assert projection_store.load_state("order-001") is None
    assert checkpoint_store.load_checkpoint(WORKER_NAME) is None