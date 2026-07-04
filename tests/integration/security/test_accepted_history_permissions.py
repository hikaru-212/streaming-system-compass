from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)


def _insert_order_event_as_test_owner(
    connection: Connection[object],
    *,
    order_id: str = "order-permission-baseline",
) -> str:
    accepted_event_id = str(uuid4())
    request_id = f"request-{uuid4()}"

    connection.execute(
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
            1,
            'CREATED',
            %s,
            %s,
            1700000000000,
            NULL,
            0,
            'INIT',
            '{}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb
        )
        """,
        (accepted_event_id, order_id, request_id, Decimal("100.00")),
    )
    connection.commit()

    return accepted_event_id


def _valid_order_event_insert_statement() -> tuple[str, tuple[object, ...]]:
    accepted_event_id = str(uuid4())
    order_id = f"order-{uuid4()}"
    request_id = f"request-{uuid4()}"

    return (
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
            1,
            'CREATED',
            %s,
            %s,
            1700000000000,
            NULL,
            0,
            'INIT',
            '{}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb
        )
        RETURNING accepted_event_id
        """,
        (accepted_event_id, order_id, request_id, Decimal("100.00")),
    )


def test_app_writer_can_select_order_events(connection: Connection[object]) -> None:
    _insert_order_event_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT accepted_event_id FROM order_events",
    )

    assert rows is not None
    assert len(rows) == 1


def test_app_writer_can_insert_order_events(connection: Connection[object]) -> None:
    statement, params = _valid_order_event_insert_statement()

    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )

    assert rows is not None
    assert len(rows) == 1


def test_app_writer_cannot_update_order_events(connection: Connection[object]) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            UPDATE order_events
            SET amount = %s
            WHERE accepted_event_id = %s
        """,
        params=(Decimal("999.00"), accepted_event_id),
    )


def test_app_writer_cannot_delete_order_events(connection: Connection[object]) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            DELETE FROM order_events
            WHERE accepted_event_id = %s
        """,
        params=(accepted_event_id,),
    )


def test_projection_worker_can_select_order_events(
    connection: Connection[object],
) -> None:
    _insert_order_event_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT accepted_event_id FROM order_events",
    )

    assert rows is not None
    assert len(rows) == 1


def test_projection_worker_cannot_insert_order_events(
    connection: Connection[object],
) -> None:
    statement, params = _valid_order_event_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    )


def test_projection_worker_cannot_update_order_events(
    connection: Connection[object],
) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE order_events
            SET amount = %s
            WHERE accepted_event_id = %s
        """,
        params=(Decimal("999.00"), accepted_event_id),
    )


def test_projection_worker_cannot_delete_order_events(
    connection: Connection[object],
) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM order_events
            WHERE accepted_event_id = %s
        """,
        params=(accepted_event_id,),
    )


def test_snapshot_worker_can_select_order_events(connection: Connection[object]) -> None:
    _insert_order_event_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT accepted_event_id FROM order_events",
    )

    assert rows is not None
    assert len(rows) == 1


def test_snapshot_worker_cannot_insert_order_events(
    connection: Connection[object],
) -> None:
    statement, params = _valid_order_event_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement=statement,
        params=params,
    )


def test_snapshot_worker_cannot_update_order_events(
    connection: Connection[object],
) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            UPDATE order_events
            SET amount = %s
            WHERE accepted_event_id = %s
        """,
        params=(Decimal("999.00"), accepted_event_id),
    )


def test_snapshot_worker_cannot_delete_order_events(
    connection: Connection[object],
) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            DELETE FROM order_events
            WHERE accepted_event_id = %s
        """,
        params=(accepted_event_id,),
    )


def test_readonly_can_select_order_events(connection: Connection[object]) -> None:
    _insert_order_event_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_readonly",
        statement="SELECT accepted_event_id FROM order_events",
    )

    assert rows is not None
    assert len(rows) == 1


def test_readonly_cannot_insert_order_events(connection: Connection[object]) -> None:
    statement, params = _valid_order_event_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement=statement,
        params=params,
    )


def test_readonly_cannot_update_order_events(connection: Connection[object]) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            UPDATE order_events
            SET amount = %s
            WHERE accepted_event_id = %s
        """,
        params=(Decimal("999.00"), accepted_event_id),
    )


def test_readonly_cannot_delete_order_events(connection: Connection[object]) -> None:
    accepted_event_id = _insert_order_event_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            DELETE FROM order_events
            WHERE accepted_event_id = %s
        """,
        params=(accepted_event_id,),
    )