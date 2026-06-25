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
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationStatus,
    ProjectionSnapshotReplayValidator,
)
from src.storage.postgres_accepted_history_event_source import (
    PostgresAcceptedHistoryEventSource,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_event_source import (
    PostgresProjectionEventSource,
    ProjectionEventRecord,
)
from src.storage.postgres_projection_snapshot_store import (
    PostgresProjectionSnapshotStore,
    ProjectionSnapshot,
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


def make_snapshot(
    *,
    snapshot_id: UUID | None = None,
    order_id: str = "order-001",
    source_event_id: UUID,
    source_event_sequence: int,
    source_global_position: int,
    state_status: str,
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal,
    state_version: int,
    snapshot_schema_version: int = 1,
    reducer_version: str = "order_projection_reducer:v1",
    payload_hash: str = "sha256:test-payload-hash",
    metadata: dict | None = None,
    created_by: str = "test",
) -> ProjectionSnapshot:
    if snapshot_id is None:
        snapshot_id = uuid4()

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


def make_validator(
    connection: Connection,
    *,
    tail_event_limit: int = 1000,
) -> ProjectionSnapshotReplayValidator:
    return ProjectionSnapshotReplayValidator(
        snapshot_store=PostgresProjectionSnapshotStore(connection),
        accepted_history_store=PostgresAcceptedHistoryEventSource(connection),
        tail_event_source=PostgresProjectionEventSource(connection),
        tail_event_limit=tail_event_limit,
    )


def load_projection_event_records(
    connection: Connection,
) -> list[ProjectionEventRecord]:
    return PostgresProjectionEventSource(connection).load_after(
        0,
        limit=1000,
    )


def find_record_for_event(
    records: list[ProjectionEventRecord],
    event: OrderEvent,
) -> ProjectionEventRecord:
    for record in records:
        if record.event.event_id == event.event_id:
            return record

    raise AssertionError(f"Projection event record not found: {event.event_id}")


def expected_created_state(
    *,
    order_id: str = "order-001",
    amount: Decimal = Decimal("100.00"),
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=OrderStatus.CREATED,
        total_amount=amount,
        paid_amount=Decimal("0.00"),
        version=1,
    )


def expected_paid_state(
    *,
    order_id: str = "order-001",
    amount: Decimal = Decimal("100.00"),
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=OrderStatus.PAID,
        total_amount=amount,
        paid_amount=amount,
        version=2,
    )


def test_postgres_validator_matches_snapshot_with_no_tail(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event()

    event_store.append(created_event, expected_current_version=0)

    records = load_projection_event_records(db_connection)
    created_record = find_record_for_event(records, created_event)

    snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=created_event.event_id,
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=created_event.sequence,
        payload_hash="sha256:created-snapshot",
    )
    snapshot_store.save_snapshot(snapshot)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.is_match is True
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == created_record.global_position
    assert result.snapshot_assisted_state == expected_created_state()
    assert result.authority_state == expected_created_state()
    assert result.snapshot_assisted_state == result.authority_state


def test_postgres_validator_matches_snapshot_with_tail_replay(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    event_store.append(created_event, expected_current_version=0)
    event_store.append(paid_event, expected_current_version=1)

    records = load_projection_event_records(db_connection)
    created_record = find_record_for_event(records, created_event)

    snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=created_event.event_id,
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=created_event.sequence,
        payload_hash="sha256:created-snapshot",
    )
    snapshot_store.save_snapshot(snapshot)

    validator = make_validator(
        db_connection,
        tail_event_limit=1,
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.is_match is True
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == created_record.global_position
    assert result.snapshot_assisted_state == expected_paid_state()
    assert result.authority_state == expected_paid_state()
    assert result.snapshot_assisted_state == result.authority_state


def test_postgres_validator_detects_drift_when_snapshot_payload_disagrees_with_claimed_boundary(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    event_store.append(created_event, expected_current_version=0)
    event_store.append(paid_event, expected_current_version=1)

    records = load_projection_event_records(db_connection)
    paid_record = find_record_for_event(records, paid_event)

    # This snapshot claims the PAID boundary but carries CREATED payload.
    # PR4 currently classifies this as SNAPSHOT_ASSISTED_DRIFT because
    # lineage-specific diagnostics are deferred to a future refinement.
    inconsistent_snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=paid_event.event_id,
        source_event_sequence=paid_event.sequence,
        source_global_position=paid_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=paid_event.sequence,
        payload_hash="sha256:inconsistent-paid-boundary",
    )
    snapshot_store.save_snapshot(inconsistent_snapshot)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
    )
    assert result.is_match is False
    assert result.snapshot_id == inconsistent_snapshot.snapshot_id
    assert result.source_global_position == paid_record.global_position
    assert result.snapshot_assisted_state == OrderState(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=2,
    )
    assert result.authority_state == expected_paid_state()
    assert result.reason is not None
    assert "differs from accepted-history replay" in result.reason


def test_postgres_validator_returns_missing_snapshot_when_history_exists(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)

    created_event = make_created_event()

    event_store.append(created_event, expected_current_version=0)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT
    assert result.is_match is False
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.snapshot_assisted_state is None
    assert result.authority_state == expected_created_state()
    assert result.reason is not None
    assert "authority state was reconstructed" in result.reason


def test_postgres_validator_returns_no_accepted_history_when_snapshot_exists_without_history(
    db_connection: Connection,
    clean_database: None,
) -> None:
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=uuid4(),
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
        payload_hash="sha256:orphan-snapshot",
    )
    snapshot_store.save_snapshot(snapshot)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER
    )
    assert result.is_match is False
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.snapshot_assisted_state is None
    assert result.authority_state is None
    assert result.reason is not None
    assert "No accepted history" in result.reason


def test_postgres_validator_rejects_snapshot_when_state_version_does_not_match_source_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

    created_event = make_created_event()

    event_store.append(created_event, expected_current_version=0)

    records = load_projection_event_records(db_connection)
    created_record = find_record_for_event(records, created_event)

    incompatible_snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=created_event.event_id,
        source_event_sequence=created_event.sequence,
        source_global_position=created_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=0,
        payload_hash="sha256:incompatible-state-version",
    )
    snapshot_store.save_snapshot(incompatible_snapshot)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.is_match is False
    assert result.snapshot_id == incompatible_snapshot.snapshot_id
    assert result.source_global_position == created_record.global_position
    assert result.snapshot_assisted_state is None
    assert result.authority_state == expected_created_state()
    assert result.reason is not None
    assert "state_version" in result.reason
    assert "source_event_sequence" in result.reason


def test_postgres_validator_ignores_tail_events_for_other_orders(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_store = PostgresEventStore(db_connection)
    snapshot_store = PostgresProjectionSnapshotStore(db_connection)

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

    records = load_projection_event_records(db_connection)
    order_001_record = find_record_for_event(records, order_001_created)

    snapshot = make_snapshot(
        order_id="order-001",
        source_event_id=order_001_created.event_id,
        source_event_sequence=order_001_created.sequence,
        source_global_position=order_001_record.global_position,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=order_001_created.sequence,
        payload_hash="sha256:order-001-created-snapshot",
    )
    snapshot_store.save_snapshot(snapshot)

    validator = make_validator(db_connection)

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.is_match is True
    assert result.snapshot_assisted_state == expected_created_state(
        order_id="order-001",
    )
    assert result.authority_state == expected_created_state(
        order_id="order-001",
    )