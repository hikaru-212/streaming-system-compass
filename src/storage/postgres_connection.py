"""PostgreSQL connection helpers.

This module owns low-level PostgreSQL connection creation.

It does not own:
- event-store semantics
- idempotency semantics
- transaction orchestration
- domain validation
"""

from __future__ import annotations

import os

import psycopg
from psycopg import Connection


DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10


def get_database_url_from_env() -> str:
    """Load the PostgreSQL connection URL from environment variables."""
    database_url = os.environ.get(DATABASE_URL_ENV)

    if not database_url:
        raise RuntimeError(
            f"{DATABASE_URL_ENV} environment variable is required "
            "to create a PostgreSQL connection."
        )

    return database_url


def connect_postgres(
    database_url: str | None = None,
    *,
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> Connection:
    """Create a PostgreSQL connection.

    The caller owns the connection lifecycle and should close it directly
    or use it as a context manager.

    A finite connection timeout prevents the application from hanging
    indefinitely when PostgreSQL is unavailable.
    """
    return psycopg.connect(
        database_url or get_database_url_from_env(),
        connect_timeout=connect_timeout_seconds,
    )