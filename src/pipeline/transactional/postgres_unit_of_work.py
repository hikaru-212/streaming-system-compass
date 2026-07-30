from __future__ import annotations

from psycopg import Connection

from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


class PostgresWriteSideUnitOfWork:
    """
    Transaction boundary for the PostgreSQL-backed write side.

    Responsibility:
    - coordinate PostgresEventStore and PostgresIdempotencyStore through one
      shared local transaction

    Invariant:
    - connection.autocommit must be False when the unit of work is entered

    Lifecycle:
    - a clean exit commits when the unit of work is unfinished
    - an exceptional exit rolls back when the unit of work is unfinished
    - an explicit commit or rollback prevents automatic __exit__ finalization

    Non-goals:
    - commit-ambiguity reconciliation
    - duplicate-finish behavior redesign
    - domain semantics, Compass validation, command creation, or retry policy
    """

    def __init__(self, connection: Connection):
        self.connection = connection
        self.event_store = PostgresEventStore(connection)
        self.idempotency_store = PostgresIdempotencyStore(connection)
        self._finished = False

    def __enter__(self) -> PostgresWriteSideUnitOfWork:
        if self.connection.autocommit:
            raise RuntimeError(
                "PostgresWriteSideUnitOfWork requires connection.autocommit=False"
            )

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
