from __future__ import annotations

from uuid import uuid4

from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)


def _insert_projection_checkpoint_as_test_owner(
    connection: Connection[object],
    *,
    worker_name: str = "projection-worker-baseline",
) -> str:
    connection.execute(
        """
        INSERT INTO projection_checkpoints (
            worker_name,
            cursor_kind,
            cursor_value
        )
        VALUES (%s, 'GLOBAL_POSITION', '1')
        """,
        (worker_name,),
    )

    # Commit fixture setup before entering runtime_role().
    #
    # runtime_role() intentionally rolls back at entry to guarantee a clean
    # Layer 2 permission probe. Therefore, prerequisite rows that must be
    # visible to the role under test have to be committed by the test owner
    # before the permission probe begins.
    connection.commit()

    return worker_name


def _valid_projection_checkpoint_insert_statement() -> tuple[
    str,
    tuple[object, ...],
    str,
]:
    worker_name = f"projection-worker-{uuid4()}"

    return (
        """
        INSERT INTO projection_checkpoints (
            worker_name,
            cursor_kind,
            cursor_value
        )
        VALUES (%s, 'GLOBAL_POSITION', '1')
        RETURNING worker_name
        """,
        (worker_name,),
        worker_name,
    )


def test_projection_worker_can_select_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT worker_name FROM projection_checkpoints",
    )

    assert rows == [(worker_name,)]


def test_projection_worker_can_insert_projection_checkpoints(
    connection: Connection[object],
) -> None:
    statement, params, worker_name = _valid_projection_checkpoint_insert_statement()

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    )

    assert rows == [(worker_name,)]


def test_projection_worker_can_update_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE projection_checkpoints
            SET cursor_value = '2'
            WHERE worker_name = %s
            RETURNING worker_name
        """,
        params=(worker_name,),
    )

    assert rows == [(worker_name,)]


def test_projection_worker_can_delete_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM projection_checkpoints
            WHERE worker_name = %s
            RETURNING worker_name
        """,
        params=(worker_name,),
    )

    assert rows == [(worker_name,)]


def test_app_writer_cannot_select_projection_checkpoints(
    connection: Connection[object],
) -> None:
    _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT worker_name FROM projection_checkpoints",
    )


def test_app_writer_cannot_insert_projection_checkpoints(
    connection: Connection[object],
) -> None:
    statement, params, _worker_name = _valid_projection_checkpoint_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )


def test_app_writer_cannot_update_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            UPDATE projection_checkpoints
            SET updated_at = now()
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )


def test_app_writer_cannot_delete_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            DELETE FROM projection_checkpoints
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )


def test_snapshot_worker_can_select_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT worker_name FROM projection_checkpoints",
    )

    assert rows == [(worker_name,)]


def test_snapshot_worker_cannot_insert_projection_checkpoints(
    connection: Connection[object],
) -> None:
    statement, params, _worker_name = _valid_projection_checkpoint_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement=statement,
        params=params,
    )


def test_snapshot_worker_cannot_update_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            UPDATE projection_checkpoints
            SET updated_at = now()
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )


def test_snapshot_worker_cannot_delete_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            DELETE FROM projection_checkpoints
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )


def test_readonly_can_select_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_readonly",
        statement="SELECT worker_name FROM projection_checkpoints",
    )

    assert rows == [(worker_name,)]


def test_readonly_cannot_insert_projection_checkpoints(
    connection: Connection[object],
) -> None:
    statement, params, _worker_name = _valid_projection_checkpoint_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement=statement,
        params=params,
    )


def test_readonly_cannot_update_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            UPDATE projection_checkpoints
            SET updated_at = now()
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )


def test_readonly_cannot_delete_projection_checkpoints(
    connection: Connection[object],
) -> None:
    worker_name = _insert_projection_checkpoint_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            DELETE FROM projection_checkpoints
            WHERE worker_name = %s
        """,
        params=(worker_name,),
    )