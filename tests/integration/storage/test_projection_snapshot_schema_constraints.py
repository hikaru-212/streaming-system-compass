from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg import errors


def insert_projection_snapshot(
    connection: Connection,
    *,
    snapshot_id=None,
    order_id: str = "order-001",
    source_event_id=None,
    source_event_sequence: int = 1,
    source_global_position: int = 1,
    state_status: str = "CREATED",
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    state_version: int = 1,
    snapshot_schema_version: int = 1,
    reducer_version: str = "order_projection_reducer:v1",
    payload_hash: str = "sha256:test-payload-hash",
    metadata_json: str = "{}",
    created_by: str = "test",
) -> None:
    if snapshot_id is None:
        snapshot_id = uuid4()

    if source_event_id is None:
        source_event_id = uuid4()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_snapshots (
                snapshot_id,
                order_id,
                source_event_id,
                source_event_sequence,
                source_global_position,
                state_status,
                total_amount,
                paid_amount,
                state_version,
                snapshot_schema_version,
                reducer_version,
                payload_hash,
                metadata_json,
                created_by
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s
            )
            """,
            (
                snapshot_id,
                order_id,
                source_event_id,
                source_event_sequence,
                source_global_position,
                state_status,
                total_amount,
                paid_amount,
                state_version,
                snapshot_schema_version,
                reducer_version,
                payload_hash,
                metadata_json,
                created_by,
            ),
        )


def test_insert_valid_projection_snapshot(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_projection_snapshot(db_connection)

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                order_id,
                source_event_sequence,
                source_global_position,
                state_status,
                total_amount,
                paid_amount,
                state_version,
                snapshot_schema_version,
                reducer_version,
                payload_hash,
                metadata_json,
                created_by
            FROM projection_snapshots
            WHERE order_id = %s
            """,
            ("order-001",),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == "order-001"
    assert row[1] == 1
    assert row[2] == 1
    assert row[3] == "CREATED"
    assert row[4] == Decimal("100.00")
    assert row[5] == Decimal("0.00")
    assert row[6] == 1
    assert row[7] == 1
    assert row[8] == "order_projection_reducer:v1"
    assert row[9] == "sha256:test-payload-hash"
    assert row[10] == {}
    assert row[11] == "test"


@pytest.mark.parametrize(
    ("field_name", "override"),
    [
        ("order_id", {"order_id": ""}),
        ("source_event_sequence", {"source_event_sequence": 0}),
        ("source_global_position", {"source_global_position": 0}),
        ("state_status", {"state_status": "INIT"}),
        ("state_status", {"state_status": "UNKNOWN"}),
        ("total_amount", {"total_amount": Decimal("-1.00")}),
        ("paid_amount", {"paid_amount": Decimal("-1.00")}),
        (
            "paid_amount",
            {
                "total_amount": Decimal("100.00"),
                "paid_amount": Decimal("101.00"),
            },
        ),
        ("state_version", {"state_version": -1}),
        (
            "state_version",
            {
                "state_version": 2,
                "source_event_sequence": 1,
            },
        ),
        ("snapshot_schema_version", {"snapshot_schema_version": 0}),
        ("reducer_version", {"reducer_version": ""}),
        ("payload_hash", {"payload_hash": ""}),
        ("created_by", {"created_by": ""}),
        ("metadata_json", {"metadata_json": "[]"}),
    ],
)
def test_projection_snapshot_rejects_invalid_shape(
    db_connection: Connection,
    clean_database: None,
    field_name: str,
    override: dict,
) -> None:
    with pytest.raises(errors.CheckViolation):
        insert_projection_snapshot(db_connection, **override)


def test_projection_snapshot_allows_state_version_less_than_source_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_projection_snapshot(
        db_connection,
        source_event_sequence=3,
        source_global_position=3,
        state_version=2,
    )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT state_version, source_event_sequence
            FROM projection_snapshots
            WHERE order_id = %s
            """,
            ("order-001",),
        )
        row = cursor.fetchone()

    assert row == (2, 3)


def test_projection_snapshot_rejects_duplicate_order_source_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_projection_snapshot(
        db_connection,
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=1,
    )

    with pytest.raises(errors.UniqueViolation):
        insert_projection_snapshot(
            db_connection,
            order_id="order-001",
            source_event_sequence=1,
            source_global_position=2,
        )


def test_projection_snapshot_rejects_duplicate_source_global_position(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_projection_snapshot(
        db_connection,
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=1,
    )

    with pytest.raises(errors.UniqueViolation):
        insert_projection_snapshot(
            db_connection,
            order_id="order-002",
            source_event_sequence=1,
            source_global_position=1,
        )


def test_projection_snapshot_rejects_duplicate_source_event_id(
    db_connection: Connection,
    clean_database: None,
) -> None:
    shared_event_id = uuid4()

    insert_projection_snapshot(
        db_connection,
        order_id="order-001",
        source_event_id=shared_event_id,
        source_event_sequence=1,
        source_global_position=1,
    )

    with pytest.raises(errors.UniqueViolation):
        insert_projection_snapshot(
            db_connection,
            order_id="order-002",
            source_event_id=shared_event_id,
            source_event_sequence=1,
            source_global_position=2,
        )


def test_projection_snapshot_allows_same_source_sequence_for_different_orders(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_projection_snapshot(
        db_connection,
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=1,
    )
    insert_projection_snapshot(
        db_connection,
        order_id="order-002",
        source_event_sequence=1,
        source_global_position=2,
    )

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM projection_snapshots")
        count = cursor.fetchone()[0]

    assert count == 2