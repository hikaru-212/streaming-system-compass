from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)


def _insert_accepted_event_as_owner(
    connection: Connection[object],
) -> tuple[UUID, int, str]:
    event_id = uuid4()
    order_id = f"permission-order-{uuid4()}"
    row = connection.execute(
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
            proof_prev_status
        )
        VALUES (%s, %s, 1, 'CREATED', %s, 100.00, 1700000000000, NULL, 0, 'INIT')
        RETURNING global_position
        """,
        (event_id, order_id, f"permission-request-{uuid4()}"),
    ).fetchone()
    connection.commit()
    return event_id, int(row[0]), order_id


def _insert_statement(
    event_id: UUID,
    global_position: int,
    order_id: str,
) -> tuple[str, tuple[object, ...]]:
    return (
        """
        INSERT INTO projection_order_progress (
            projection_name,
            projection_epoch,
            order_id,
            last_sequence,
            last_event_id,
            last_global_position
        )
        VALUES ('order_state_projection', 1, %s, 1, %s, %s)
        RETURNING order_id
        """,
        (order_id, event_id, global_position),
    )


def _insert_progress_as_owner(
    connection: Connection[object],
) -> tuple[UUID, int, str]:
    event_id, global_position, order_id = _insert_accepted_event_as_owner(connection)
    statement, params = _insert_statement(event_id, global_position, order_id)
    connection.execute(statement, params)
    connection.commit()
    return event_id, global_position, order_id


def test_projection_worker_can_insert_projection_progress(
    connection: Connection[object],
) -> None:
    event_id, global_position, order_id = _insert_accepted_event_as_owner(connection)
    statement, params = _insert_statement(event_id, global_position, order_id)

    assert assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    ) == [(order_id,)]


def test_projection_worker_can_select_projection_progress(
    connection: Connection[object],
) -> None:
    _, _, order_id = _insert_progress_as_owner(connection)

    assert assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            SELECT last_sequence
            FROM projection_order_progress
            WHERE projection_name = 'order_state_projection'
              AND projection_epoch = 1
              AND order_id = %s
        """,
        params=(order_id,),
    ) == [(1,)]


def test_projection_worker_can_update_projection_progress(
    connection: Connection[object],
) -> None:
    first_event_id, _, order_id = _insert_progress_as_owner(connection)
    second_event_id = uuid4()
    row = connection.execute(
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
            proof_prev_status
        )
        VALUES (%s, %s, 2, 'PAID', %s, 100.00, 1700000000001, %s, 1, 'CREATED')
        RETURNING global_position
        """,
        (
            second_event_id,
            order_id,
            f"permission-request-{uuid4()}",
            first_event_id,
        ),
    ).fetchone()
    connection.commit()

    assert assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE projection_order_progress
            SET
                last_sequence = 2,
                last_event_id = %s,
                last_global_position = %s
            WHERE projection_name = 'order_state_projection'
              AND projection_epoch = 1
              AND order_id = %s
            RETURNING last_sequence
        """,
        params=(second_event_id, int(row[0]), order_id),
    ) == [(2,)]


def test_projection_worker_cannot_delete_projection_progress(
    connection: Connection[object],
) -> None:
    _, _, order_id = _insert_progress_as_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM projection_order_progress
            WHERE projection_name = 'order_state_projection'
              AND projection_epoch = 1
              AND order_id = %s
            RETURNING order_id
        """,
        params=(order_id,),
    )


def test_unauthorized_roles_cannot_mutate_projection_progress(
    connection: Connection[object],
) -> None:
    event_id, global_position, order_id = _insert_accepted_event_as_owner(connection)
    statement, params = _insert_statement(event_id, global_position, order_id)

    for role in (
        "compass_app_writer",
        "compass_snapshot_worker",
        "compass_readonly",
    ):
        assert_role_cannot_execute(
            connection,
            role=role,
            statement=statement,
            params=params,
        )


def test_unauthorized_roles_cannot_update_or_delete_projection_progress(
    connection: Connection[object],
) -> None:
    _, _, order_id = _insert_progress_as_owner(connection)

    for role in (
        "compass_app_writer",
        "compass_snapshot_worker",
        "compass_readonly",
    ):
        assert_role_cannot_execute(
            connection,
            role=role,
            statement="""
                UPDATE projection_order_progress
                SET updated_at = now()
                WHERE order_id = %s
            """,
            params=(order_id,),
        )
        assert_role_cannot_execute(
            connection,
            role=role,
            statement="""
                DELETE FROM projection_order_progress
                WHERE order_id = %s
            """,
            params=(order_id,),
        )


def test_app_writer_cannot_inspect_projection_progress(
    connection: Connection[object],
) -> None:
    _, _, order_id = _insert_progress_as_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            SELECT last_sequence
            FROM projection_order_progress
            WHERE order_id = %s
        """,
        params=(order_id,),
    )


@pytest.mark.parametrize(
    "role",
    ["compass_snapshot_worker", "compass_readonly"],
)
def test_observer_roles_can_inspect_projection_progress(
    connection: Connection[object],
    role: str,
) -> None:
    _, _, order_id = _insert_progress_as_owner(connection)

    assert assert_role_can_execute(
        connection,
        role=role,
        statement="""
            SELECT projection_name, projection_epoch, order_id, last_sequence
            FROM projection_order_progress
            WHERE order_id = %s
        """,
        params=(order_id,),
    ) == [("order_state_projection", 1, order_id, 1)]
