import pytest
from psycopg import Connection
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")


def test_connected_to_test_database(db_connection: Connection):
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()

    assert row[0] == "compass_test"


def test_required_tables_exist(db_connection: Connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('order_events', 'idempotency_records')
            ORDER BY table_name;
            """
        )
        tables = [row[0] for row in cursor.fetchall()]

    assert tables == ["idempotency_records", "order_events"]


def test_database_starts_empty(db_connection: Connection):
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0