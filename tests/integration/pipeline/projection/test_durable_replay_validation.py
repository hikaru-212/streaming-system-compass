from decimal import Decimal

from psycopg import Connection

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.state import OrderState
from src.pipeline.projection.replay_validator import (
    DurableReplayValidator,
    ReplayValidationStatus,
)
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


def make_paid_state(
    *,
    order_id: str,
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("100.00"),
    version: int = 2,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=OrderStatus.PAID,
        total_amount=total_amount,
        paid_amount=paid_amount,
        version=version,
    )


def make_validator(
    connection: Connection,
) -> DurableReplayValidator:
    return DurableReplayValidator(
        event_store=PostgresEventStore(connection),
        projection_store=PostgresProjectionStore(connection),
    )


def test_validate_order_returns_match_when_projection_matches_replay(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

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

    projection_store.save_state(
        make_paid_state(
            order_id="order-001",
        )
    )

    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.MATCH
    assert result.matched is True
    assert result.order_id == "order-001"
    assert result.expected_state == make_paid_state(order_id="order-001")
    assert result.persisted_state == make_paid_state(order_id="order-001")
    assert result.reason == "Persisted projection state matches replay-derived state"


def test_validate_order_returns_missing_projection_when_history_exists_but_state_missing(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    validator = make_validator(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.MISSING_PROJECTION
    assert result.matched is False
    assert result.order_id == "order-001"
    assert result.expected_state == make_created_state(order_id="order-001")
    assert result.persisted_state is None
    assert result.reason == "Accepted history exists but projection state is missing"


def test_validate_order_returns_drift_when_projection_differs_from_replay(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

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

    projection_store.save_state(
        make_created_state(
            order_id="order-001",
        )
    )

    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.DRIFT
    assert result.matched is False
    assert result.order_id == "order-001"
    assert result.expected_state == make_paid_state(order_id="order-001")
    assert result.persisted_state == make_created_state(order_id="order-001")
    assert result.reason == "Persisted projection state differs from replay-derived state"


def test_validate_order_returns_drift_when_projection_is_ahead_of_replay(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)

    projection_store.save_state(
        make_paid_state(order_id="order-001")
    )

    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.DRIFT
    assert result.matched is False
    assert result.order_id == "order-001"
    assert result.expected_state == make_created_state(order_id="order-001")
    assert result.persisted_state == make_paid_state(order_id="order-001")
    assert result.reason == "Persisted projection state differs from replay-derived state"


def test_validate_order_returns_no_accepted_history_when_history_is_empty(
    db_connection: Connection,
    clean_database: None,
) -> None:
    validator = make_validator(db_connection)

    result = validator.validate_order("missing-order")

    assert result.status == ReplayValidationStatus.NO_ACCEPTED_HISTORY
    assert result.matched is False
    assert result.order_id == "missing-order"
    assert result.expected_state is None
    assert result.persisted_state is None
    assert result.reason == "No accepted history exists for order"


def test_validate_order_does_not_mutate_accepted_history(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    projection_store.save_state(
        make_created_state(
            order_id="order-001",
        )
    )
    db_connection.commit()

    before_history = event_store.load("order-001")

    result = validator.validate_order("order-001")

    after_history = event_store.load("order-001")

    assert result.status == ReplayValidationStatus.MATCH
    assert after_history == before_history


def test_validate_order_does_not_advance_checkpoint_progress(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    checkpoint_store = PostgresCheckpointStore(db_connection)
    validator = make_validator(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
    )

    event_store.append(created_event, expected_current_version=0)
    projection_store.save_state(
        make_created_state(
            order_id="order-001",
        )
    )
    checkpoint_store.save_checkpoint(
        ProjectionCheckpoint(
            worker_name=WORKER_NAME,
            cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
            cursor_value="0",
        )
    )

    db_connection.commit()

    before_checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    result = validator.validate_order("order-001")

    after_checkpoint = checkpoint_store.load_checkpoint(WORKER_NAME)

    assert result.status == ReplayValidationStatus.MATCH
    assert before_checkpoint is not None
    assert after_checkpoint == before_checkpoint


def test_validate_order_replays_events_in_aggregate_sequence_order(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

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

    projection_store.save_state(
        make_paid_state(
            order_id="order-001",
        )
    )

    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT global_position
            FROM order_events
            WHERE order_id = %s AND sequence = 1
            """,
            ("order-001",),
        )
        created_global_position = cursor.fetchone()[0]
    
        cursor.execute(
            """
            SELECT global_position
            FROM order_events
            WHERE order_id = %s AND sequence = 2
            """,
            ("order-001",),
        )
        paid_global_position = cursor.fetchone()[0]

        cursor.execute(
            """UPDATE order_events
            SET global_position = %s
            WHERE order_id = %s AND sequence = 1
            """,
            (paid_global_position + 100, "order-001"),
        )

        cursor.execute(
            """UPDATE order_events
            SET global_position = %s
            WHERE order_id = %s AND sequence = 2
            """,
            (created_global_position, "order-001"),
        )

        cursor.execute(
            """UPDATE order_events
            SET global_position = %s
            WHERE order_id = %s AND sequence = 1
            """,
            (paid_global_position, "order-001"),
        )

    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.MATCH
    assert result.expected_state == make_paid_state(order_id="order-001")
    assert result.persisted_state == make_paid_state(order_id="order-001")


def test_validate_order_decimal_round_trip_does_not_create_false_drift(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    validator = make_validator(db_connection)

    created_event = make_created_event(
        request_id="request-create",
        order_id="order-001",
        amount=Decimal("100"),
    )

    event_store.append(created_event, expected_current_version=0)

    projection_store.save_state(
        OrderState(
            order_id="order-001",
            status=OrderStatus.CREATED,
            total_amount=Decimal("100.00"),
            paid_amount=Decimal("0.00"),
            version=1,
        )
    )

    db_connection.commit()

    result = validator.validate_order("order-001")

    assert result.status == ReplayValidationStatus.MATCH
    assert result.expected_state is not None
    assert result.persisted_state is not None
    assert result.expected_state.total_amount == Decimal("100")
    assert result.persisted_state.total_amount == Decimal("100.00")
    assert result.expected_state == result.persisted_state
    