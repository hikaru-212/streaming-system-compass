from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.sql import Identifier
from psycopg.sql import SQL


def count_rows(connection: Connection[Any], table_name: str) -> int:
    with connection.cursor() as cursor:
        query = SQL("SELECT COUNT(*) FROM {}").format(Identifier(table_name))
        cursor.execute(query)
        row = cursor.fetchone()

    assert row is not None
    return row[0]