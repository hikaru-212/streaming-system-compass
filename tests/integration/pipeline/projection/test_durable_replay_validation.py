from contextlib import closing
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


def test_validator_rejects_stores_on_different_connections(
    db_connection: Connection,
    db_connection_factory,
    clean_database: None,
) -> None:
    other_connection = db_connection_factory()
    other_connection.rollback()
    try:
        with pytest.raises(ValueError, match="must share the exact"):
            DurableReplayValidator(
                event_store=PostgresEventStore(db_connection),
                projection_store=PostgresProjectionStore(other_connection),
            )
    finally:
        other_connection.close()


def test_validate_order_rejects_outer_transaction(
    db_connection: Connection,
    clean_database: None,
) -> None:
    validator = make_validator(db_connection)

    db_connection.execute("SELECT 1")
    with pytest.raises(RuntimeError, match="requires an idle connection"):
        validator.validate_order("order-001")
    db_connection.rollback()


def test_validate_order_returns_match_when_projection_matches_replay(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)
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
    assert (
        progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id="order-001",
        )
        is None
    )


def test_validate_order_keeps_repeatable_read_observation_when_state_changes_between_reads(
    db_connection: Connection,
    db_connection_factory,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T1 retains its snapshot when T2 commits between validator reads."""
    order_id = "order-repeatable-read-state-mutation"
    event_store = PostgresEventStore(db_connection)
    created_event = make_created_event(
        request_id="request-repeatable-read-state-mutation",
        order_id=order_id,
    )
    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    worker = PostgresProjectionWorker(
        db_connection,
        worker_name="repeatable-read-setup-worker",
    )
    applied = worker.process_next()
    assert applied.action == "applied"

    projection_store = PostgresProjectionStore(db_connection)
    progress_store = PostgresProjectionProgressStore(db_connection)
    original_state = projection_store.load_state(order_id)
    original_progress = progress_store.load_progress(
        projection_name=ORDER_STATE_PROJECTION_NAME,
        projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
        order_id=order_id,
    )
    assert original_state is not None
    assert original_state == make_created_state(order_id=order_id)
    assert original_progress is not None
    assert original_progress.last_sequence == original_state.version
    db_connection.rollback()

    with (
        closing(db_connection_factory()) as writer_connection,
        closing(db_connection_factory()) as observer_connection,
    ):
        writer_connection.rollback()
        observer_connection.rollback()
        writer_projection_store = PostgresProjectionStore(writer_connection)
        observer_projection_store = PostgresProjectionStore(observer_connection)
        observer_progress_store = PostgresProjectionProgressStore(observer_connection)
        changed_state = make_created_state(
            order_id=order_id,
            total_amount=Decimal("125.00"),
            version=original_state.version,
        )

        validator_event_store = PostgresEventStore(db_connection)
        validator = DurableReplayValidator(
            event_store=validator_event_store,
            projection_store=PostgresProjectionStore(db_connection),
        )
        load_accepted_history = validator_event_store.load
        mutation_committed = False

        def load_history_then_commit_state_mutation(
            selected_order_id: str,
        ) -> list[OrderEvent]:
            nonlocal mutation_committed
            # The accepted-history SELECT establishes T1's snapshot before T2
            # commits the independently mutable same-version projection state.
            accepted_history = load_accepted_history(selected_order_id)
            writer_projection_store.save_state(changed_state)
            writer_connection.commit()
            mutation_committed = True
            return accepted_history

        monkeypatch.setattr(
            validator_event_store,
            "load",
            load_history_then_commit_state_mutation,
        )

        observed_before_mutation = validator.validate_order(order_id)

        assert mutation_committed is True
        assert observed_before_mutation.status == ReplayValidationStatus.MATCH
        assert observed_before_mutation.expected_state == original_state
        assert observed_before_mutation.persisted_state == original_state

        independently_observed_state = observer_projection_store.load_state(order_id)
        independently_observed_progress = observer_progress_store.load_progress(
            projection_name=ORDER_STATE_PROJECTION_NAME,
            projection_epoch=ORDER_STATE_PROJECTION_EPOCH,
            order_id=order_id,
        )

        assert independently_observed_state is not None
        assert independently_observed_state == changed_state
        assert independently_observed_state.version == original_state.version
        assert independently_observed_progress is not None
        assert independently_observed_progress == original_progress
        assert independently_observed_progress.last_sequence == changed_state.version
        observer_connection.rollback()

        monkeypatch.setattr(validator_event_store, "load", load_accepted_history)
        observed_after_mutation = validator.validate_order(order_id)

        assert observed_after_mutation.status == ReplayValidationStatus.DRIFT
        assert observed_after_mutation.expected_state == original_state
        assert observed_after_mutation.persisted_state == changed_state


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
    db_connection.rollback()

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
    db_connection.rollback()

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
