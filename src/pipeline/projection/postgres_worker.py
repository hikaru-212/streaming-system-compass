from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
)
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)
from src.storage.postgres_projection_eligible_event_source import (
    PostgresProjectionEligibleEventSource,
)
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.postgres_projection_store import PostgresProjectionStore
from src.storage.projection_progress_store import ProjectionOrderProgress


@dataclass(frozen=True)
class PostgresProjectionWorkerResult:
    """
    Human-readable result for integration tests and debugging.

    action:
    - "applied"
    - "no_event"
    """

    worker_name: str
    action: str
    global_position: int | None
    order_id: str | None
    event_sequence: int | None
    projected_version: int | None
    reason: str


class PostgresProjectionWorker:
    """Apply the current order-state projection with per-order durable progress.

    Responsibility:
    - discover a currently visible accepted event whose order-local sequence is
      exactly next for the immutable current projection definition and epoch;
    - apply the canonical reducer;
    - commit projection state and per-order progress atomically.

    Connection and transaction ownership:
    - every PostgreSQL collaborator must share the exact supplied connection;
    - ``process_next`` requires that connection to be idle and owns one genuine
      top-level transaction for its durable result.

    Invariants:
    - progress for one order never excludes an event for another order;
    - state and progress either both commit or both roll back;
    - ``global_position`` is lineage and a scheduling tie-breaker, not a
      complete committed-history frontier.

    Non-goals:
    - accepted-event admission or validation;
    - exactly-once processing;
    - leases, heartbeats, or competing-worker orchestration;
    - globally ordered projections;
    - use or migration of legacy scalar checkpoint evidence.

    The supported production topology remains one active worker for this
    projection definition and epoch. ``worker_name`` is operational identity
    only and is deliberately absent from durable progress identity.
    """

    def __init__(
        self,
        connection: Connection,
        *,
        worker_name: str,
        event_source: PostgresProjectionEligibleEventSource | None = None,
        projection_store: PostgresProjectionStore | None = None,
        progress_store: PostgresProjectionProgressStore | None = None,
    ) -> None:
        """Construct a single-active-worker projection processor.

        ``connection`` is the caller-supplied PostgreSQL connection and
        ``worker_name`` is operational identity only. The worker always applies
        ``order_state_projection`` epoch 1; callers cannot select another
        definition because ``projection_states`` is keyed only by ``order_id``.
        Injected PostgreSQL collaborators are accepted for testing, but they
        must own the identical connection object. Construction fails before
        processing if that atomicity boundary is not satisfied. Construction
        starts no transaction and performs no rebuild, leasing, or epoch
        migration.
        """
        if not worker_name.strip():
            raise ValueError("worker_name must not be empty")

        self.connection = connection
        self.worker_name = worker_name
        self.projection_name = ORDER_STATE_PROJECTION_NAME
        self.projection_epoch = ORDER_STATE_PROJECTION_EPOCH
        self.event_source = event_source or PostgresProjectionEligibleEventSource(
            connection
        )
        self.projection_store = projection_store or PostgresProjectionStore(connection)
        self.progress_store = progress_store or PostgresProjectionProgressStore(
            connection
        )

        for collaborator_name, collaborator in (
            ("event_source", self.event_source),
            ("projection_store", self.projection_store),
            ("progress_store", self.progress_store),
        ):
            if collaborator.connection is not connection:
                raise ValueError(
                    f"{collaborator_name} must share the exact worker connection"
                )

    def process_next(self) -> PostgresProjectionWorkerResult:
        """Process at most one currently visible exact-next accepted event.

        The connection must be idle on entry. This method then owns a top-level
        PostgreSQL transaction that atomically persists projection state and
        exact-next per-order progress. It returns applied-event lineage, or
        ``no_event`` when no currently visible accepted event is eligible for
        this projection definition and epoch.

        ``no_event`` is not proof that no accepted event can commit later.
        There is no leasing, retry policy, or multi-worker claim behavior.
        """
        if self.connection.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError(
                "PostgresProjectionWorker.process_next requires an idle "
                "connection so it can own a top-level transaction"
            )

        with self.connection.transaction():
            records = self.event_source.load_eligible(
                projection_name=self.projection_name,
                projection_epoch=self.projection_epoch,
                limit=1,
            )

            if not records:
                return PostgresProjectionWorkerResult(
                    worker_name=self.worker_name,
                    action="no_event",
                    global_position=None,
                    order_id=None,
                    event_sequence=None,
                    projected_version=None,
                    reason=(
                        "no currently visible accepted event is eligible as the "
                        "next order-local event for this projection definition "
                        "and epoch"
                    ),
                )

            record = records[0]
            event = record.event

            current_state = self.projection_store.load_state(event.order_id)
            if current_state is None:
                current_state = build_empty_projection_state(event.order_id)

            next_state = reduce_order_event(current_state, event)

            self.projection_store.save_state(next_state)
            self.progress_store.advance_progress(
                ProjectionOrderProgress(
                    projection_name=self.projection_name,
                    projection_epoch=self.projection_epoch,
                    order_id=event.order_id,
                    last_sequence=event.sequence,
                    last_event_id=event.event_id,
                    last_global_position=record.global_position,
                )
            )

            return PostgresProjectionWorkerResult(
                worker_name=self.worker_name,
                action="applied",
                global_position=record.global_position,
                order_id=event.order_id,
                event_sequence=event.sequence,
                projected_version=next_state.version,
                reason="accepted event applied and per-order progress advanced",
            )
