from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)

def _insert_projection_state_as_test_owner(
    connection: Connection[object],
    *,
    order_id: str = "order-projection-state-baseline",
) -> str:
    connection.execute(
        """
        INSERT INTO projection_states (
            order_id,
            status,
            total_amount,
            paid_amount,
            version,
            last_sequence
        )
        VALUES (%s, 'CREATED', %s, %s, 1, 1)
        """,
        (order_id, Decimal("100.00"), Decimal("0.00")),
    )

    # Commit fixture setup before entering runtime_role().
    #
    # runtime_role() intentionally rolls back at entry to guarantee a clean
    # Layer 2 permission probe. Therefore, prerequisite rows that must be
    # visible to the role under test have to be committed by the test owner
    # before the permission probe begins.
    connection.commit()

    return order_id


def _valid_projection_state_insert_statement() -> tuple[str, tuple[object, ...]]:
    order_id = f"order-{uuid4()}"

    return (
        """
        INSERT INTO projection_states (
            order_id,
            status,
            total_amount,
            paid_amount,
            version,
            last_sequence
        )
        VALUES (%s, 'CREATED', %s, %s, 1, 1)
        RETURNING order_id
        """,
        (order_id, Decimal("100.00"), Decimal("0.00")),
    )


def test_projection_worker_can_select_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT order_id FROM projection_states",
    )

    assert rows == [(order_id,)]


def test_projection_worker_can_insert_projection_states(
    connection: Connection[object],
) -> None:
    statement, params = _valid_projection_state_insert_statement()

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    )

    assert rows is not None
    assert len(rows) == 1
    assert rows[0][0] == params[0]


def test_projection_worker_can_update_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE projection_states
            SET
                status = 'PAID',
                paid_amount = %s,
                version = 2,
                last_sequence = 2
            WHERE order_id = %s
            RETURNING order_id
        """,
        params=(Decimal("100.00"), order_id),
    )

    assert rows == [(order_id,)]


def test_projection_worker_can_delete_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM projection_states
            WHERE order_id = %s
            RETURNING order_id
        """,
        params=(order_id,),
    )

    assert rows == [(order_id,)]


def test_app_writer_cannot_select_projection_states(
    connection: Connection[object],
) -> None:
    _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT order_id FROM projection_states",
    )


def test_app_writer_cannot_insert_projection_states(
    connection: Connection[object],
) -> None:
    statement, params = _valid_projection_state_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )


def test_app_writer_cannot_update_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            UPDATE projection_states
            SET updated_at = now()
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


def test_app_writer_cannot_delete_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            DELETE FROM projection_states
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


def test_snapshot_worker_can_select_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT order_id FROM projection_states",
    )

    assert rows == [(order_id,)]


def test_snapshot_worker_cannot_insert_projection_states(
    connection: Connection[object],
) -> None:
    statement, params = _valid_projection_state_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement=statement,
        params=params,
    )


def test_snapshot_worker_cannot_update_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            UPDATE projection_states
            SET updated_at = now()
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


def test_snapshot_worker_cannot_delete_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            DELETE FROM projection_states
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


def test_readonly_can_select_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_readonly",
        statement="SELECT order_id FROM projection_states",
    )

    assert rows == [(order_id,)]


def test_readonly_cannot_insert_projection_states(
    connection: Connection[object],
) -> None:
    statement, params = _valid_projection_state_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement=statement,
        params=params,
    )


def test_readonly_cannot_update_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            UPDATE projection_states
            SET updated_at = now()
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


def test_readonly_cannot_delete_projection_states(
    connection: Connection[object],
) -> None:
    order_id = _insert_projection_state_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            DELETE FROM projection_states
            WHERE order_id = %s
        """,
        params=(order_id,),
    )