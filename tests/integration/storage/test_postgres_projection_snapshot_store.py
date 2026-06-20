from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg import errors

from src.storage.postgres_projection_snapshot_store import (
    PostgresProjectionSnapshotStore,
    ProjectionSnapshot,
    SnapshotWriteCollisionError,
)


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


def count_projection_snapshots(connection: Connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM projection_snapshots")
        return cursor.fetchone()[0]


def test_load_latest_snapshot_returns_none_when_missing(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    assert store.load_latest_snapshot("missing-order") is None


def test_projection_snapshot_model_can_be_constructed() -> None:
    snapshot = make_snapshot(
        metadata={"source": "unit-test"},
    )

    assert snapshot.order_id == "order-001"
    assert snapshot.source_event_sequence == 1
    assert snapshot.source_global_position == 1
    assert snapshot.state_status == "CREATED"
    assert snapshot.total_amount == Decimal("100.00")
    assert snapshot.paid_amount == Decimal("0.00")
    assert snapshot.state_version == 1
    assert snapshot.snapshot_schema_version == 1
    assert snapshot.reducer_version == "order_projection_reducer:v1"
    assert snapshot.payload_hash == "sha256:test-payload-hash"
    assert snapshot.metadata == {"source": "unit-test"}
    assert snapshot.created_by == "test"
    assert snapshot.created_at is None


def test_snapshot_write_collision_error_type_exists() -> None:
    error = SnapshotWriteCollisionError("collision")

    assert str(error) == "collision"


def test_save_and_load_latest_projection_snapshot(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)
    snapshot = make_snapshot(
        metadata={"source": "unit-test", "attempt": 1},
    )

    store.save_snapshot(snapshot)

    loaded = store.load_latest_snapshot("order-001")

    assert loaded is not None
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.order_id == "order-001"
    assert loaded.source_event_id == snapshot.source_event_id
    assert loaded.source_event_sequence == 1
    assert loaded.source_global_position == 1
    assert loaded.state_status == "CREATED"
    assert loaded.total_amount == Decimal("100.00")
    assert loaded.paid_amount == Decimal("0.00")
    assert loaded.state_version == 1
    assert loaded.snapshot_schema_version == 1
    assert loaded.reducer_version == "order_projection_reducer:v1"
    assert loaded.payload_hash == "sha256:test-payload-hash"
    assert loaded.metadata == {"source": "unit-test", "attempt": 1}
    assert loaded.created_by == "test"
    assert loaded.created_at is not None


def test_load_latest_snapshot_uses_highest_source_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    older_snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=10,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
        payload_hash="sha256:older",
    )
    newer_source_snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=2,
        source_global_position=20,
        state_status="PAID",
        paid_amount=Decimal("100.00"),
        state_version=2,
        payload_hash="sha256:newer",
    )

    store.save_snapshot(older_snapshot)
    store.save_snapshot(newer_source_snapshot)

    loaded = store.load_latest_snapshot("order-001")

    assert loaded is not None
    assert loaded.source_global_position == 20
    assert loaded.source_event_sequence == 2
    assert loaded.state_status == "PAID"
    assert loaded.payload_hash == "sha256:newer"


def test_clear_snapshots_removes_only_one_order(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=1,
        )
    )
    store.save_snapshot(
        make_snapshot(
            order_id="order-002",
            source_event_sequence=1,
            source_global_position=2,
        )
    )

    store.clear_snapshots("order-001")

    assert store.load_latest_snapshot("order-001") is None
    assert store.load_latest_snapshot("order-002") is not None
    assert count_projection_snapshots(db_connection) == 1


def test_same_full_source_boundary_and_same_payload_hash_is_idempotent_success(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    source_event_id = uuid4()

    first = make_snapshot(
        snapshot_id=uuid4(),
        order_id="order-001",
        source_event_id=source_event_id,
        source_event_sequence=1,
        source_global_position=1,
        payload_hash="sha256:same",
    )
    duplicate = make_snapshot(
        snapshot_id=uuid4(),
        order_id="order-001",
        source_event_id=source_event_id,
        source_event_sequence=1,
        source_global_position=1,
        payload_hash="sha256:same",
    )

    store.save_snapshot(first)
    store.save_snapshot(duplicate)

    assert count_projection_snapshots(db_connection) == 1

    loaded = store.load_latest_snapshot("order-001")
    assert loaded is not None
    assert loaded.snapshot_id == first.snapshot_id
    assert loaded.payload_hash == "sha256:same"


def test_same_source_event_id_with_different_lineage_and_payload_hash_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    source_event_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=source_event_id,
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-002",
                source_event_id=source_event_id,
                source_event_sequence=1,
                source_global_position=2,
                payload_hash="sha256:second",
            )
        )


def test_same_source_global_position_with_different_lineage_and_payload_hash_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-002",
                source_event_sequence=1,
                source_global_position=1,
                payload_hash="sha256:second",
            )
        )


def test_same_order_source_sequence_with_different_lineage_and_payload_hash_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-001",
                source_event_sequence=1,
                source_global_position=2,
                payload_hash="sha256:second",
            )
        )


def test_allows_same_source_event_sequence_for_different_orders(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )
    store.save_snapshot(
        make_snapshot(
            order_id="order-002",
            source_event_sequence=1,
            source_global_position=2,
            payload_hash="sha256:second",
        )
    )

    assert count_projection_snapshots(db_connection) == 2


def test_store_preserves_database_shape_constraints(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    try:
        with pytest.raises(errors.CheckViolation):
            store.save_snapshot(
                make_snapshot(
                    state_status="INIT",
                )
            )
    finally:
        db_connection.rollback()

    assert store.load_latest_snapshot("order-001") is None


def test_caller_owned_rollback_removes_saved_snapshot(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(make_snapshot())

    assert store.load_latest_snapshot("order-001") is not None

    db_connection.rollback()

    assert store.load_latest_snapshot("order-001") is None


def test_connection_remains_usable_after_idempotent_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)
    source_event_id = uuid4()

    first = make_snapshot(
        order_id="order-001",
        source_event_id=source_event_id,
        source_event_sequence=1,
        source_global_position=1,
        payload_hash="sha256:same",
    )
    duplicate = make_snapshot(
        order_id="order-001",
        source_event_id=source_event_id,
        source_event_sequence=1,
        source_global_position=1,
        payload_hash="sha256:same",
    )

    store.save_snapshot(first)
    store.save_snapshot(duplicate)

    store.save_snapshot(
        make_snapshot(
            order_id="order-002",
            source_event_sequence=1,
            source_global_position=2,
            payload_hash="sha256:other",
        )
    )

    assert count_projection_snapshots(db_connection) == 2


def test_connection_remains_usable_after_snapshot_write_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)
    source_event_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=source_event_id,
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-002",
                source_event_id=source_event_id,
                source_event_sequence=1,
                source_global_position=2,
                payload_hash="sha256:second",
            )
        )

    store.save_snapshot(
        make_snapshot(
            order_id="order-003",
            source_event_sequence=1,
            source_global_position=3,
            payload_hash="sha256:third",
        )
    )

    assert count_projection_snapshots(db_connection) == 2


def test_same_source_event_id_same_payload_hash_but_different_lineage_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    source_event_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=source_event_id,
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:same",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-002",
                source_event_id=source_event_id,
                source_event_sequence=99,
                source_global_position=99,
                payload_hash="sha256:same",
            )
        )


def test_same_source_global_position_same_payload_hash_but_different_event_id_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=uuid4(),
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:same",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-002",
                source_event_id=uuid4(),
                source_event_sequence=1,
                source_global_position=1,
                payload_hash="sha256:same",
            )
        )


def test_same_order_source_sequence_same_payload_hash_but_different_global_position_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:same",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-001",
                source_event_sequence=1,
                source_global_position=2,
                payload_hash="sha256:same",
            )
        )


def test_snapshot_id_conflict_without_matching_source_boundary_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    snapshot_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            snapshot_id=snapshot_id,
            order_id="order-001",
            source_event_id=uuid4(),
            source_event_sequence=1,
            source_global_position=1,
            payload_hash="sha256:first",
        )
    )

    with pytest.raises(
        SnapshotWriteCollisionError,
        match="no matching source-boundary snapshot could be found",
    ):
        store.save_snapshot(
            make_snapshot(
                snapshot_id=snapshot_id,
                order_id="order-002",
                source_event_id=uuid4(),
                source_event_sequence=1,
                source_global_position=2,
                payload_hash="sha256:second",
            )
        )


def test_same_source_boundary_and_payload_hash_but_different_reducer_version_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    source_event_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=source_event_id,
            source_event_sequence=1,
            source_global_position=1,
            reducer_version="order_projection_reducer:v1",
            payload_hash="sha256:same",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-001",
                source_event_id=source_event_id,
                source_event_sequence=1,
                source_global_position=1,
                reducer_version="order_projection_reducer:v2",
                payload_hash="sha256:same",
            )
        )


def test_same_source_boundary_and_payload_hash_but_different_schema_version_raises_collision(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    source_event_id = uuid4()

    store.save_snapshot(
        make_snapshot(
            order_id="order-001",
            source_event_id=source_event_id,
            source_event_sequence=1,
            source_global_position=1,
            snapshot_schema_version=1,
            payload_hash="sha256:same",
        )
    )

    with pytest.raises(SnapshotWriteCollisionError):
        store.save_snapshot(
            make_snapshot(
                order_id="order-001",
                source_event_id=source_event_id,
                source_event_sequence=1,
                source_global_position=1,
                snapshot_schema_version=2,
                payload_hash="sha256:same",
            )
        )