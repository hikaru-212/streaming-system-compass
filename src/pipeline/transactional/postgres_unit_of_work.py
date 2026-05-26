from __future__ import annotations

from psycopg import Connection

from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


class PostgresWriteSideUnitOfWork:
    """
    Transaction boundary for the PostgreSQL-backed write side.

    This unit of work coordinates the durable write-side stores that must
    participate in the same database transaction:

    - PostgresEventStore
    - PostgresIdempotencyStore

    It does not own domain semantics, Compass validation, command creation,
    or retry policy.

    Its responsibility is physical transaction control:

    - commit all write-side persistence changes together
    - rollback all write-side persistence changes together
    """

    def __init__(self, connection: Connection):
        self.connection = connection
        self.event_store = PostgresEventStore(connection)
        self.idempotency_store = PostgresIdempotencyStore(connection)
        self._finished = False

    def __enter__(self) -> PostgresWriteSideUnitOfWork:
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None:
            if not self._finished:
                self.rollback()
            return False

        if not self._finished:
            self.commit()

        return False

    def commit(self) -> None:
        """
        Commit all changes made through the stores in this unit of work.
        """
        self.connection.commit()
        self._finished = True

    def rollback(self) -> None:
        """
        Roll back all changes made through the stores in this unit of work.
        """
        self.connection.rollback()
        self._finished = True