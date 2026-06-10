from decimal import Decimal
from uuid import UUID
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg import errors


def insert_created_event(
    connection: Connection,
    *,
    order_id: str,
    request_id: str,
    sequence: int = 1,
    global_position: int | None = None,
) -> UUID:
    accepted_event_id = uuid4()

    if global_position is None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_events (
                    accepted_event_id,
                    order_id,
                    sequence,
                    event_type,
                    request_id,
                    amount,
                    occurred_at_ms,
                    proof_prev_event_id,
                    proof_prev_version,
                    proof_prev_status,
                    payload_json,
                    proof_json,
                    metadata_json
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'CREATED',
                    %s,
                    %s,
                    %s,
                    NULL,
                    0,
                    'INIT',
                    '{}'::jsonb,
                    '{}'::jsonb,
                    '{}'::jsonb
                )
                """,
                (
                    accepted_event_id,
                    order_id,
                    sequence,
                    request_id,
                    Decimal("100.00"),
                    1_700_000_000_000,
                ),
            )
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_events (
                    accepted_event_id,
                    global_position,
                    order_id,
                    sequence,
                    event_type,
                    request_id,
                    amount,
                    occurred_at_ms,
                    proof_prev_event_id,
                    proof_prev_version,
                    proof_prev_status,
                    payload_json,
                    proof_json,
                    metadata_json
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'CREATED',
                    %s,
                    %s,
                    %s,
                    NULL,
                    0,
                    'INIT',
                    '{}'::jsonb,
                    '{}'::jsonb,
                    '{}'::jsonb
                )
                """,
                (
                    accepted_event_id,
                    global_position,
                    order_id,
                    sequence,
                    request_id,
                    Decimal("100.00"),
                    1_700_000_000_000,
                ),
            )

    return accepted_event_id


def test_order_events_global_position_column_exists(
    db_connection: Connection,
    clean_database: None,
) -> None:
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                column_name,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = 'order_events'
               AND column_name = 'global_position'
            """
        )
        row = cursor.fetchone()

    assert row is not None

    column_name, is_nullable, column_default = row

    assert column_name == "global_position"
    assert is_nullable == "NO"
    assert column_default is not None
    assert "order_events_global_position_seq" in column_default


def test_inserted_order_events_receive_global_positions(
    db_connection: Connection,
    clean_database: None,
) -> None:
    event_a = insert_created_event(
        db_connection,
        order_id="order-a",
        request_id="request-a",
    )
    event_b = insert_created_event(
        db_connection,
        order_id="order-b",
        request_id="request-b",
    )
    event_c = insert_created_event(
        db_connection,
        order_id="order-c",
        request_id="request-c",
    )

    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT accepted_event_id, global_position
            FROM order_events
            WHERE accepted_event_id = ANY(%s)
            ORDER BY global_position ASC
            """,
            ([event_a, event_b, event_c],),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == [event_a, event_b, event_c]

    positions = [row[1] for row in rows]

    assert positions == sorted(positions)
    assert len(set(positions)) == 3
    assert all(position > 0 for position in positions)


def test_global_position_is_unique(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_created_event(
        db_connection,
        order_id="order-a",
        request_id="request-a",
        global_position=1,
    )
    db_connection.commit()

    with pytest.raises(errors.UniqueViolation):
        insert_created_event(
            db_connection,
            order_id="order-b",
            request_id="request-b",
            global_position=1,
        )
    
    db_connection.rollback()


def test_global_position_is_independent_from_aggregate_local_sequence(
    db_connection: Connection,
    clean_database: None,
) -> None:
    insert_created_event(
        db_connection,
        order_id="order-a",
        request_id="request-a",
        sequence=1,
    )
    insert_created_event(
        db_connection,
        order_id="order-b",
        request_id="request-b",
        sequence=1,
    )

    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT order_id, sequence, global_position
            FROM order_events
            ORDER BY global_position ASC
            """
        )
        rows = cursor.fetchall()

    assert len(rows) == 2

    order_a, order_b = rows

    assert order_a[0] == "order-a"
    assert order_a[1] == 1

    assert order_b[0] == "order-b"
    assert order_b[1] == 1

    assert order_a[2] != order_b[2]
    assert order_a[2] < order_b[2]
