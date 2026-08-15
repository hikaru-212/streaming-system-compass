from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import Connection

from tests.integration.security.helpers import grant_runtime_roles_to_current_user


def _test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL permission tests")
    return database_url


def _assert_test_database(connection: Connection[object]) -> None:
    """Refuse destructive permission tests against a non-test database."""
    row = connection.execute("SELECT current_database()").fetchone()
    database_name = row[0]

    if not database_name.endswith("_test"):
        raise RuntimeError(
            "Refusing to run destructive PostgreSQL security tests against "
            f"non-test database: {database_name}. Please check TEST_DATABASE_URL."
        )


def reset_role_as_best_effort(connection: Connection[object]) -> None:
    connection.rollback()
    connection.execute("RESET ROLE")
    connection.commit()


@pytest.fixture()
def connection() -> Iterator[Connection[object]]:
    with psycopg.connect(_test_database_url()) as conn:
        _assert_test_database(conn)
        # The safety SELECT opens an implicit transaction. Close it so fixture
        # setup begins from an idle connection before any role or table mutation.
        conn.rollback()
        reset_role_as_best_effort(conn)
        conn.execute(
            """
            TRUNCATE
                decision_receipts,
                projection_snapshots,
                projection_order_progress,
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

        reset_role_as_best_effort(conn)
        conn.execute(
            """
            TRUNCATE
                decision_receipts,
                projection_snapshots,
                projection_order_progress,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
        conn.commit()
