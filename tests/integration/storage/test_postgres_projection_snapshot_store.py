from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg import errors

from src.storage.postgres_projection_snapshot_store import (
    PostgresProjectionSnapshotStore,
    SnapshotWriteCollisionError,
)
from tests.shared.postgres import count_rows
from tests.shared.projection_snapshots import make_snapshot



def test_load_latest_snapshot_returns_none_when_missing(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    assert store.load_latest_snapshot("missing-order") is None


def test_load_snapshot_returns_snapshot_by_snapshot_id(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)
    snapshot = make_snapshot(
        metadata={"source": "unit-test", "lookup": "by-id"},
    )

    store.save_snapshot(snapshot)

    loaded = store.load_snapshot(snapshot.snapshot_id)

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
    assert loaded.metadata == {"source": "unit-test", "lookup": "by-id"}
    assert loaded.created_by == "test"
    assert loaded.created_at is not None


def test_load_snapshot_returns_none_when_missing(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionSnapshotStore(db_connection)

    assert store.load_snapshot(uuid4()) is None


def test_load_snapshot_does_not_select_latest_snapshot_for_order(
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
    newer_snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=2,
        source_global_position=20,
        state_status="PAID",
        paid_amount=Decimal("100.00"),
        state_version=2,
        payload_hash="sha256:newer",
    )

    store.save_snapshot(older_snapshot)
    store.save_snapshot(newer_snapshot)

    latest = store.load_latest_snapshot("order-001")
    loaded_by_id = store.load_snapshot(older_snapshot.snapshot_id)

    assert latest is not None
    assert latest.snapshot_id == newer_snapshot.snapshot_id
    assert latest.source_global_position == 20

    assert loaded_by_id is not None
    assert loaded_by_id.snapshot_id == older_snapshot.snapshot_id
    assert loaded_by_id.source_global_position == 10
    assert loaded_by_id.payload_hash == "sha256:older"


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
    assert count_rows(db_connection, "projection_snapshots") == 1


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

    assert count_rows(db_connection, "projection_snapshots") == 1

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

    assert count_rows(db_connection, "projection_snapshots") == 2


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

    assert count_rows(db_connection, "projection_snapshots") == 2


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

    assert count_rows(db_connection, "projection_snapshots") == 2


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