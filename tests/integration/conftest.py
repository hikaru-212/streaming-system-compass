import os
from typing import Callable, Iterator

import pytest
from psycopg import Connection

from src.storage.postgres_connection import connect_postgres


TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"


def assert_test_database(connection: Connection) -> None:
    """
    Refuse to run destructive integration tests against a non-test database.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()

    database_name = row[0]

    if not database_name.endswith("_test"):
        raise RuntimeError(
            "Refusing to run destructive PostgreSQL integration tests against "
            f"non-test database: {database_name}. "
            f"Please check {TEST_DATABASE_URL_ENV}."
        )


def get_test_database_url() -> str:
    database_url = os.environ.get(TEST_DATABASE_URL_ENV)

    if not database_url:
        raise RuntimeError(
            f"{TEST_DATABASE_URL_ENV} is required for PostgreSQL integration tests. "
            "Do not run destructive DB tests against DATABASE_URL directly."
        )

    return database_url


@pytest.fixture
def db_connection_factory() -> Callable[[], Connection]:
    """
    Return a factory that always creates connections to TEST_DATABASE_URL.
    """

    def _connect() -> Connection:
        connection = connect_postgres(get_test_database_url())
        assert_test_database(connection)
        return connection

    return _connect


@pytest.fixture
def db_connection(db_connection_factory: Callable[[], Connection]) -> Iterator[Connection]:
    """
    Create a PostgreSQL connection for destructive integration tests.
    """
    connection = db_connection_factory()

    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def clean_database(db_connection: Connection) -> None:
    """
    Reset write-side persistence tables before each DB integration test.
    """
    with db_connection.cursor() as cursor:
       cursor.execute(
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

    db_connection.commit()