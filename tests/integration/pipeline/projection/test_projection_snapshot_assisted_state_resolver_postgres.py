from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from uuid import uuid4

from psycopg import Connection

from src.core.order.enums import EventType
from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedStateResolver,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidator,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_event_source import (
    PostgresProjectionEventSource,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord
from src.storage.postgres_projection_snapshot_store import (
    PostgresProjectionSnapshotStore,
)
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


def make_snapshot(
    *,
    snapshot_id: UUID | None = None,
    order_id: str = "order-001",
    source_event_id: UUID | None = None,
    source_event_sequence: int = 1,
    source_global_position: int = 1,
    state_status: str = "CREATED",
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    state_version: int = 1,
    snapshot_schema_version: int = 1,
    reducer_version: str = "order_projection_reducer:v1",
    payload_hash: str = "sha256:test-payload-hash",
    metadata: dict | None = None,
    created_by: str = "test",
) -> ProjectionSnapshot:
    if snapshot_id is None:
        snapshot_id = uuid4()

    if source_event_id is None:
        source_event_id = uuid4()

    if metadata is None:
        metadata = {}

    return ProjectionSnapshot(
        snapshot_id=snapshot_id,
        order_id=order_id,
        source_event_id=source_event_id,
        source_event_sequence=source_event_sequence,
        source_global_position=source_global_position,
        state_status=state_status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        state_version=state_version,
        snapshot_schema_version=snapshot_schema_version,
        reducer_version=reducer_version,
        payload_hash=payload_hash,
        metadata=metadata,
        created_by=created_by,
    )


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


def make_resolver(
    connection: Connection,
) -> ProjectionSnapshotAssistedStateResolver:
    return ProjectionSnapshotAssistedStateResolver(
        snapshot_store=PostgresProjectionSnapshotStore(connection),
        tail_event_source=PostgresProjectionEventSource(connection),
        tail_event_limit=1000,
    )


def make_validator(
    connection: Connection,
) -> ProjectionSnapshotReplayValidator:
    return ProjectionSnapshotReplayValidator(
        snapshot_store=PostgresProjectionSnapshotStore(connection),
        accepted_history_store=PostgresEventStore(connection),
        tail_event_source=PostgresProjectionEventSource(connection),
        tail_event_limit=1000,
    )


def append_order_events(
    connection: Connection,
    *events: OrderEvent,
) -> None:
    event_store = PostgresEventStore(connection)

    for event in events:
        event_store.append(
            event,
            expected_current_version=event.sequence - 1,
        )

    connection.commit()


def load_projection_tail_records(
    connection: Connection,
) -> list[ProjectionEventRecord]:
    source = PostgresProjectionEventSource(connection)
    return source.load_after(0, limit=100)


def find_record_for_event(
    records: list[ProjectionEventRecord],
    event: OrderEvent,
) -> ProjectionEventRecord:
    for record in records:
        if record.event.event_id == event.event_id:
            return record

    raise AssertionError(f"Projection record not found for event {event.event_id}")


def count_rows(
    connection: Connection,
    table_name: str,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result = cursor.fetchone()

    return int(result[0])


def test_postgres_resolver_resolves_persisted_snapshot_with_no_tail(
    db_connection: Connection,
    clean_database: None,
) -> None:
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)
    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )

    snapshot_store.save_snapshot(snapshot)
    db_connection.commit()

    resolver = make_resolver(db_connection)

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.is_resolved is True
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == 1
    assert result.resolved_state == OrderState(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )


def test_postgres_resolver_resolves_persisted_snapshot_with_real_tail_event(
    db_connection: Connection,
    clean_database: None,
) -> None:
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    append_order_events(
        db_connection,
        created_event,
        paid_event,
    )

    records = load_projection_tail_records(db_connection)

    assert len(records) == 2
    assert records[0].event == created_event
    assert records[1].event == paid_event

    created_record = find_record_for_event(records, created_event)

    snapshot = make_snapshot(
        source_event_id=UUID(created_event.event_id),
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=created_event.sequence,
    )

    snapshot_store.save_snapshot(snapshot)
    db_connection.commit()

    resolver = make_resolver(db_connection)

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.is_resolved is True
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == created_record.global_position
    assert result.resolved_state == OrderState(
        order_id="order-001",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )


def test_postgres_resolver_reads_tail_strictly_after_snapshot_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event(
        request_id="create-strict-tail",
    )
    paid_event = make_paid_event(
        previous_event=created_event,
        request_id="pay-strict-tail",
    )

    append_order_events(
        db_connection,
        created_event,
        paid_event,
    )

    records = load_projection_tail_records(db_connection)
    created_record = find_record_for_event(records, created_event)
    paid_record = find_record_for_event(records, paid_event)

    assert paid_record.global_position > created_record.global_position

    snapshot = make_snapshot(
        source_event_id=UUID(created_event.event_id),
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=created_event.sequence,
    )

    snapshot_store.save_snapshot(snapshot)
    db_connection.commit()

    resolver = make_resolver(db_connection)

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.is_resolved is True
    assert result.resolved_state == OrderState(
        order_id="order-001",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )


def test_postgres_validator_match_result_can_supply_trusted_snapshot_id_for_resolver(
    db_connection: Connection,
    clean_database: None,
) -> None:
    """
    Demonstrate the current ephemeral trust path.

    This is intentionally not the final optimized runtime path. It proves that
    PR4 can produce a qualified snapshot_id through authority validation, and
    PR4.5 can consume that id. Because no durable validation receipt exists yet,
    this path pays PR4 authority-validation cost before resolver usage.
    """
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event(
        request_id="create-pr4-to-pr45",
    )
    paid_event = make_paid_event(
        previous_event=created_event,
        request_id="pay-pr4-to-pr45",
    )

    append_order_events(
        db_connection,
        created_event,
        paid_event,
    )

    records = load_projection_tail_records(db_connection)
    created_record = find_record_for_event(records, created_event)

    snapshot = make_snapshot(
        source_event_id=UUID(created_event.event_id),
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=created_event.sequence,
    )

    snapshot_store.save_snapshot(snapshot)
    db_connection.commit()

    validator = make_validator(db_connection)

    validation_result = validator.validate_order("order-001")

    assert validation_result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert validation_result.snapshot_id == snapshot.snapshot_id
    assert validation_result.authority_state == OrderState(
        order_id="order-001",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )

    trusted_snapshot_id = validation_result.snapshot_id

    assert trusted_snapshot_id is not None

    resolver = make_resolver(db_connection)

    resolution_result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=trusted_snapshot_id,
    )

    assert (
        resolution_result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert resolution_result.is_resolved is True
    assert resolution_result.snapshot_id == trusted_snapshot_id
    assert resolution_result.resolved_state == validation_result.authority_state


def test_postgres_resolver_does_not_mutate_durable_tables(
    db_connection: Connection,
    clean_database: None,
) -> None:
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)
    snapshot = make_snapshot()

    snapshot_store.save_snapshot(snapshot)
    db_connection.commit()

    before_counts = {
        "order_events": count_rows(db_connection, "order_events"),
        "projection_snapshots": count_rows(db_connection, "projection_snapshots"),
        "projection_states": count_rows(db_connection, "projection_states"),
        "projection_checkpoints": count_rows(
            db_connection,
            "projection_checkpoints",
        ),
    }

    resolver = make_resolver(db_connection)

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    after_counts = {
        "order_events": count_rows(db_connection, "order_events"),
        "projection_snapshots": count_rows(db_connection, "projection_snapshots"),
        "projection_states": count_rows(db_connection, "projection_states"),
        "projection_checkpoints": count_rows(
            db_connection,
            "projection_checkpoints",
        ),
    }

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert after_counts == before_counts
