from __future__ import annotations

from uuid import UUID

from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedStateResolver,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidator,
)
from src.storage.postgres_accepted_history_event_source import (
    PostgresAcceptedHistoryEventSource,
)
from src.storage.postgres_order_event_tail_source import (
    PostgresOrderEventTailSource,
)
from src.storage.postgres_projection_snapshot_store import (
    PostgresProjectionSnapshotStore,
)


class PostgresProjectionSnapshotReplayValidator:
    """Run snapshot replay validation as one PostgreSQL observation.

    Responsibility:
    - construct all PostgreSQL readers on the exact supplied connection;
    - execute snapshot, accepted-history, and local-tail reads inside one
      explicit top-level repeatable-read, read-only transaction;
    - delegate semantic comparison to ``ProjectionSnapshotReplayValidator``.

    The connection must be idle on entry and remains caller-owned. This class
    performs no mutation, snapshot trust decision, fallback, or recovery
    policy. It does not create a cross-database or distributed snapshot.
    """

    def __init__(
        self,
        connection: Connection,
        *,
        tail_event_limit: int = 1000,
    ) -> None:
        """Construct same-connection readers for one observation boundary.

        ``connection`` remains caller-owned and positive ``tail_event_limit``
        bounds local-tail pages. All readers are created on that exact
        connection. Construction starts no transaction and establishes no
        snapshot trust, fallback, or recovery policy.
        """
        self.connection = connection
        self._validator = ProjectionSnapshotReplayValidator(
            snapshot_store=PostgresProjectionSnapshotStore(connection),
            accepted_history_store=PostgresAcceptedHistoryEventSource(connection),
            tail_event_source=PostgresOrderEventTailSource(connection),
            tail_event_limit=tail_event_limit,
        )

    def validate_order(
        self,
        order_id: str,
    ) -> ProjectionSnapshotReplayValidationResult:
        """Validate one order inside one top-level PostgreSQL transaction.

        ``order_id`` selects snapshot, accepted history, and local tail. The
        returned typed result comes from the generic validator. The supplied
        connection must be idle and is caller-owned; this method owns only the
        observation transaction. It performs no mutation, fallback, or trust
        policy.
        """
        _require_idle_connection(
            self.connection,
            operation="PostgresProjectionSnapshotReplayValidator.validate_order",
        )
        with self.connection.transaction():
            _set_consistent_read_transaction(self.connection)
            return self._validator.validate_order(order_id)


class PostgresProjectionSnapshotAssistedStateResolver:
    """Resolve a trusted snapshot and local tail as one PostgreSQL observation.

    The snapshot lookup and per-order contiguous tail use the exact supplied
    connection inside one explicit top-level repeatable-read, read-only
    transaction. The connection is caller-owned.

    This boundary does not establish snapshot trust, compare accepted-history
    authority, mutate durable state, or choose fallback/runtime policy.
    """

    def __init__(
        self,
        connection: Connection,
        *,
        tail_event_limit: int = 1000,
    ) -> None:
        """Construct same-connection readers for one observation boundary.

        ``connection`` remains caller-owned and positive ``tail_event_limit``
        bounds local-tail pages. Snapshot lookup and tail source share that
        exact connection. Construction starts no transaction and establishes no
        snapshot trust, fallback, or runtime action.
        """
        self.connection = connection
        self._resolver = ProjectionSnapshotAssistedStateResolver(
            snapshot_store=PostgresProjectionSnapshotStore(connection),
            tail_event_source=PostgresOrderEventTailSource(connection),
            tail_event_limit=tail_event_limit,
        )

    def resolve_order(
        self,
        order_id: str,
        *,
        trusted_snapshot_id: UUID | None,
    ) -> ProjectionSnapshotAssistedResolutionResult:
        """Resolve one trusted snapshot inside one PostgreSQL transaction.

        ``trusted_snapshot_id`` is an explicit caller qualification for
        ``order_id``. The returned typed result contains resolved state or a
        failure classification. The connection must be idle and remains
        caller-owned; this method owns the observation transaction. It neither
        establishes trust nor chooses fallback or runtime action.
        """
        _require_idle_connection(
            self.connection,
            operation=(
                "PostgresProjectionSnapshotAssistedStateResolver.resolve_order"
            ),
        )
        with self.connection.transaction():
            _set_consistent_read_transaction(self.connection)
            return self._resolver.resolve_order(
                order_id,
                trusted_snapshot_id=trusted_snapshot_id,
            )


def _require_idle_connection(
    connection: Connection,
    *,
    operation: str,
) -> None:
    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError(
            f"{operation} requires an idle connection so it can own a "
            "top-level transaction"
        )


def _set_consistent_read_transaction(connection: Connection) -> None:
    # PostgreSQL READ COMMITTED uses a new snapshot per statement. The validator
    # and resolver make several related reads, so one transaction alone is not
    # enough to describe them as one observation.
    connection.execute(
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
