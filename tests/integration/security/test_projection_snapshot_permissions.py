from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)


def _unique_positive_bigint() -> int:
    """Generate a positive bigint suitable for unique test cursor positions.

    projection_snapshots.source_global_position is globally unique. Permission
    probes should not depend on a fixed cursor value such as 1, even though
    successful probes are rolled back by runtime_role().
    """

    return uuid4().int % 9_000_000_000 + 1


def _insert_projection_snapshot_as_test_owner(
    connection: Connection[object],
    *,
    order_id: str = "order-snapshot-baseline",
    source_event_sequence: int = 1,
    source_global_position: int | None = None,
) -> UUID:
    snapshot_id = uuid4()
    source_event_id = str(uuid4())
    resolved_source_global_position = (
        source_global_position
        if source_global_position is not None
        else _unique_positive_bigint()
    )

    connection.execute(
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
            'CREATED',
            %s,
            %s,
            1,
            1,
            'projection-reducer-v1',
            %s,
            '{}'::jsonb,
            'test-owner'
        )
        """,
        (
            snapshot_id,
            order_id,
            source_event_id,
            source_event_sequence,
            resolved_source_global_position,
            Decimal("100.00"),
            Decimal("0.00"),
            f"payload-hash-{uuid4()}",
        ),
    )

    # Commit fixture setup before entering runtime_role().
    #
    # runtime_role() intentionally rolls back at entry to guarantee a clean
    # Layer 2 permission probe. Therefore, prerequisite rows that must be
    # visible to the role under test have to be committed by the test owner
    # before the permission probe begins.
    connection.commit()

    return snapshot_id


def _valid_projection_snapshot_insert_statement() -> tuple[
    UUID,
    tuple[object, ...],
    UUID,
]:
    snapshot_id = uuid4()
    order_id = f"order-{uuid4()}"
    source_event_id = str(uuid4())
    source_global_position = _unique_positive_bigint()

    return (
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
            1,
            %s,
            'CREATED',
            %s,
            %s,
            1,
            1,
            'projection-reducer-v1',
            %s,
            '{}'::jsonb,
            'snapshot-worker'
        )
        RETURNING snapshot_id
        """,
        (
            snapshot_id,
            order_id,
            source_event_id,
            source_global_position,
            Decimal("100.00"),
            Decimal("0.00"),
            f"payload-hash-{uuid4()}",
        ),
        snapshot_id,
    )


def test_snapshot_worker_can_select_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT snapshot_id FROM projection_snapshots",
    )

    assert rows == [(snapshot_id,)]


def test_snapshot_worker_can_insert_projection_snapshots(
    connection: Connection[object],
) -> None:
    statement, params, snapshot_id = _valid_projection_snapshot_insert_statement()

    rows = assert_role_can_execute(
        connection,
        role="compass_snapshot_worker",
        statement=statement,
        params=params,
    )

    assert rows == [(snapshot_id,)]


def test_snapshot_worker_cannot_update_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            UPDATE projection_snapshots
            SET created_at = now()
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_snapshot_worker_cannot_delete_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            DELETE FROM projection_snapshots
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_projection_worker_can_select_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT snapshot_id FROM projection_snapshots",
    )

    assert rows == [(snapshot_id,)]


def test_projection_worker_cannot_insert_projection_snapshots(
    connection: Connection[object],
) -> None:
    statement, params, _snapshot_id = _valid_projection_snapshot_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    )


def test_projection_worker_cannot_update_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE projection_snapshots
            SET created_at = now()
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_projection_worker_cannot_delete_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM projection_snapshots
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_readonly_can_select_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_readonly",
        statement="SELECT snapshot_id FROM projection_snapshots",
    )

    assert rows == [(snapshot_id,)]


def test_readonly_cannot_insert_projection_snapshots(
    connection: Connection[object],
) -> None:
    statement, params, _snapshot_id = _valid_projection_snapshot_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement=statement,
        params=params,
    )


def test_readonly_cannot_update_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            UPDATE projection_snapshots
            SET created_at = now()
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_readonly_cannot_delete_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            DELETE FROM projection_snapshots
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_app_writer_cannot_select_projection_snapshots(
    connection: Connection[object],
) -> None:
    _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT snapshot_id FROM projection_snapshots",
    )


def test_app_writer_cannot_insert_projection_snapshots(
    connection: Connection[object],
) -> None:
    statement, params, _snapshot_id = _valid_projection_snapshot_insert_statement()

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )


def test_app_writer_cannot_update_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            UPDATE projection_snapshots
            SET created_at = now()
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )


def test_app_writer_cannot_delete_projection_snapshots(
    connection: Connection[object],
) -> None:
    snapshot_id = _insert_projection_snapshot_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            DELETE FROM projection_snapshots
            WHERE snapshot_id = %s
        """,
        params=(snapshot_id,),
    )