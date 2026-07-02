from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
    grant_runtime_roles_to_current_user,
)


def _test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL permission tests")
    return database_url


def _reset_role_as_best_effort(connection: Connection[object]) -> None:
    """Return the session to the test-owner role before owner cleanup.

    Permission probes use SET ROLE. The normal helper cleanup already resets the
    role, but fixture teardown should still defend itself against unexpected
    failures that may leave the session role changed or the transaction aborted.

    This is test-owner cleanup protection, not production role-switching logic.
    """

    connection.rollback()
    connection.execute("RESET ROLE")
    connection.commit()


@pytest.fixture()
def connection() -> Iterator[Connection[object]]:
    """Provide an isolated test-owner connection for permission probes.

    The permission helpers intentionally use SET ROLE from this test-owner
    connection. Setup and cleanup remain owned by the test owner because these
    are Layer 2 permission-boundary tests, not production runtime flows.

    These tests must run only against TEST_DATABASE_URL. Some probes, especially
    sequence probes using nextval(...), may have non-transactional side effects
    that are safe only inside an isolated test database with fixture cleanup.
    """

    with psycopg.connect(_test_database_url()) as conn:
        _reset_role_as_best_effort(conn)
        conn.execute(
            """
            TRUNCATE
                projection_snapshots,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
        conn.commit()

        grant_runtime_roles_to_current_user(conn)

        yield conn

        _reset_role_as_best_effort(conn)
        conn.execute(
            """
            TRUNCATE
                projection_snapshots,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
        conn.commit()


def _insert_order_event_as_test_owner(
    connection: Connection[object],
    *,
    order_id: str = "order-idempotency-permission-baseline",
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

    # Commit fixture setup before entering runtime_role().
    #
    # runtime_role() intentionally rolls back at entry to guarantee a clean
    # Layer 2 permission probe. Therefore, prerequisite rows that must be
    # visible to the role under test have to be committed by the test owner
    # before the permission probe begins.
    #
    # This is fixture setup, not a simulation of the full write-side atomic
    # transaction between order_events and idempotency_records.
    connection.commit()

    return accepted_event_id


def _insert_idempotency_record_as_test_owner(
    connection: Connection[object],
    *,
    request_id: str = "request-idempotency-baseline",
    order_id: str = "order-idempotency-permission-baseline",
) -> str:
    accepted_event_id = _insert_order_event_as_test_owner(
        connection,
        order_id=order_id,
    )

    connection.execute(
        """
        INSERT INTO idempotency_records (
            request_id,
            order_id,
            command_type,
            amount,
            fingerprint_version,
            semantic_fingerprint,
            accepted_event_id,
            result_sequence,
            status
        )
        VALUES (
            %s,
            %s,
            'create',
            %s,
            1,
            %s,
            %s,
            1,
            'SUCCEEDED'
        )
        """,
        (
            request_id,
            order_id,
            Decimal("100.00"),
            f"fingerprint-{uuid4()}",
            accepted_event_id,
        ),
    )
    connection.commit()

    return request_id


def _valid_idempotency_insert_statement(
    connection: Connection[object],
) -> tuple[str, tuple[object, ...]]:
    order_id = f"order-{uuid4()}"
    request_id = f"request-{uuid4()}"
    accepted_event_id = _insert_order_event_as_test_owner(
        connection,
        order_id=order_id,
    )

    return (
        """
        INSERT INTO idempotency_records (
            request_id,
            order_id,
            command_type,
            amount,
            fingerprint_version,
            semantic_fingerprint,
            accepted_event_id,
            result_sequence,
            status
        )
        VALUES (
            %s,
            %s,
            'create',
            %s,
            1,
            %s,
            %s,
            1,
            'SUCCEEDED'
        )
        RETURNING request_id
        """,
        (
            request_id,
            order_id,
            Decimal("100.00"),
            f"fingerprint-{uuid4()}",
            accepted_event_id,
        ),
    )


def test_app_writer_can_select_idempotency_records(
    connection: Connection[object],
) -> None:
    _insert_idempotency_record_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT request_id FROM idempotency_records",
    )

    assert rows is not None
    assert len(rows) == 1


def test_app_writer_can_insert_idempotency_records(
    connection: Connection[object],
) -> None:
    statement, params = _valid_idempotency_insert_statement(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )

    assert rows is not None
    assert len(rows) == 1


def test_app_writer_cannot_update_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            UPDATE idempotency_records
            SET semantic_fingerprint = %s
            WHERE request_id = %s
        """,
        params=(f"fingerprint-{uuid4()}", request_id),
    )


def test_app_writer_cannot_delete_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_app_writer",
        statement="""
            DELETE FROM idempotency_records
            WHERE request_id = %s
        """,
        params=(request_id,),
    )


def test_projection_worker_cannot_select_idempotency_records(
    connection: Connection[object],
) -> None:
    _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT request_id FROM idempotency_records",
    )


def test_projection_worker_cannot_insert_idempotency_records(
    connection: Connection[object],
) -> None:
    statement, params = _valid_idempotency_insert_statement(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement=statement,
        params=params,
    )


def test_projection_worker_cannot_update_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            UPDATE idempotency_records
            SET semantic_fingerprint = %s
            WHERE request_id = %s
        """,
        params=(f"fingerprint-{uuid4()}", request_id),
    )


def test_projection_worker_cannot_delete_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="""
            DELETE FROM idempotency_records
            WHERE request_id = %s
        """,
        params=(request_id,),
    )


def test_snapshot_worker_cannot_select_idempotency_records(
    connection: Connection[object],
) -> None:
    _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT request_id FROM idempotency_records",
    )


def test_snapshot_worker_cannot_insert_idempotency_records(
    connection: Connection[object],
) -> None:
    statement, params = _valid_idempotency_insert_statement(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement=statement,
        params=params,
    )


def test_snapshot_worker_cannot_update_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            UPDATE idempotency_records
            SET semantic_fingerprint = %s
            WHERE request_id = %s
        """,
        params=(f"fingerprint-{uuid4()}", request_id),
    )


def test_snapshot_worker_cannot_delete_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="""
            DELETE FROM idempotency_records
            WHERE request_id = %s
        """,
        params=(request_id,),
    )


def test_readonly_can_select_idempotency_records(
    connection: Connection[object],
) -> None:
    _insert_idempotency_record_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role="compass_readonly",
        statement="SELECT request_id FROM idempotency_records",
    )

    assert rows is not None
    assert len(rows) == 1


def test_readonly_cannot_insert_idempotency_records(
    connection: Connection[object],
) -> None:
    statement, params = _valid_idempotency_insert_statement(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement=statement,
        params=params,
    )


def test_readonly_cannot_update_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            UPDATE idempotency_records
            SET semantic_fingerprint = %s
            WHERE request_id = %s
        """,
        params=(f"fingerprint-{uuid4()}", request_id),
    )


def test_readonly_cannot_delete_idempotency_records(
    connection: Connection[object],
) -> None:
    request_id = _insert_idempotency_record_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="""
            DELETE FROM idempotency_records
            WHERE request_id = %s
        """,
        params=(request_id,),
    )


# nextval() is non-transactional in PostgreSQL. These probes must run only
# against the isolated TEST_DATABASE_URL database, where fixture cleanup resets
# owned sequences with TRUNCATE ... RESTART IDENTITY CASCADE.
def test_app_writer_can_consume_order_events_global_position_sequence(
    connection: Connection[object],
) -> None:
    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement="SELECT nextval('order_events_global_position_seq')",
    )

    assert rows is not None
    assert len(rows) == 1


def test_projection_worker_cannot_consume_order_events_global_position_sequence(
    connection: Connection[object],
) -> None:
    assert_role_cannot_execute(
        connection,
        role="compass_projection_worker",
        statement="SELECT nextval('order_events_global_position_seq')",
    )


def test_snapshot_worker_cannot_consume_order_events_global_position_sequence(
    connection: Connection[object],
) -> None:
    assert_role_cannot_execute(
        connection,
        role="compass_snapshot_worker",
        statement="SELECT nextval('order_events_global_position_seq')",
    )


def test_readonly_cannot_consume_order_events_global_position_sequence(
    connection: Connection[object],
) -> None:
    assert_role_cannot_execute(
        connection,
        role="compass_readonly",
        statement="SELECT nextval('order_events_global_position_seq')",
    )