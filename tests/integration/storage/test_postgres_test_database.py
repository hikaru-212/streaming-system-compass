import os

import pytest
from psycopg import Connection
from psycopg.conninfo import conninfo_to_dict
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")


def test_connected_to_test_database(db_connection: Connection):
    configured_database = conninfo_to_dict(
        os.environ["TEST_DATABASE_URL"]
    ).get("dbname")

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()

    assert configured_database is not None
    assert row[0] == configured_database
    assert row[0].endswith("_test")


def test_required_tables_exist(db_connection: Connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                  'decision_receipts',
                  'idempotency_records',
                  'order_events'
              )
            ORDER BY table_name;
            """
        )
        tables = [row[0] for row in cursor.fetchall()]

    assert tables == [
        "decision_receipts",
        "idempotency_records",
        "order_events",
    ]


def test_database_starts_empty(db_connection: Connection):
    assert count_rows(db_connection, "decision_receipts") == 0
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
