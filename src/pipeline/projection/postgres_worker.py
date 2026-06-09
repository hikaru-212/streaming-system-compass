from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection

from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)
from src.storage.postgres_checkpoint_store import (
    CheckpointCursorKind,
    PostgresCheckpointStore,
    ProjectionCheckpoint,
)
from src.storage.postgres_projection_event_source import PostgresProjectionEventSource
from src.storage.postgres_projection_store import PostgresProjectionStore


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
    """
    PostgreSQL-backed projection worker baseline.

    Responsibility:
    - read accepted events after durable checkpoint progress
    - apply the canonical projection reducer
    - persist derived projection state
    - persist checkpoint progress
    - commit projection state and checkpoint progress atomically

    This worker assumes a single active process per worker_name.

    This worker does NOT:
    - validate candidate-event truth claims
    - perform write-side admission
    - implement out-of-order buffering
    - implement DLQ
    - implement watermark semantics
    - coordinate distributed multi-worker execution
    - implement worker leasing
    - implement checkpoint row locking
    - perform Compass Layer 2 validation

    Boundary decision:
    - this worker only accepts GLOBAL_POSITION checkpoints
    - projection-state / checkpoint mismatch should fail fast
    - silent repair / skipped_already_projected behavior is intentionally out of scope
    """

    def __init__(
        self,
        connection: Connection,
        *,
        worker_name: str,
        event_source: PostgresProjectionEventSource | None = None,
        projection_store: PostgresProjectionStore | None = None,
        checkpoint_store: PostgresCheckpointStore | None = None,
    ) -> None:
        self.connection = connection
        self.worker_name = worker_name
        self.event_source = event_source or PostgresProjectionEventSource(connection)
        self.projection_store = projection_store or PostgresProjectionStore(connection)
        self.checkpoint_store = checkpoint_store or PostgresCheckpointStore(connection)

    def process_next(self) -> PostgresProjectionWorkerResult:
        """
        Process at most one accepted event.

        The read-side transaction boundary is intentionally owned here.

        Within one PostgreSQL transaction, this worker:

        1. loads checkpoint progress
        2. loads the next accepted event after that progress
        3. loads current derived projection state
        4. applies the canonical reducer
        5. saves projection state
        6. saves checkpoint progress

        If any step fails, projection state and checkpoint progress roll back
        together.
        """

        with self.connection.transaction():
            last_global_position = self._load_last_global_position()

            records = self.event_source.load_after(
                last_global_position,
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
                    reason="no accepted event after checkpoint",
                )

            record = records[0]
            event = record.event

            current_state = self.projection_store.load_state(event.order_id)
            if current_state is None:
                current_state = build_empty_projection_state(event.order_id)

            next_state = reduce_order_event(current_state, event)

            self.projection_store.save_state(next_state)
            self.checkpoint_store.save_checkpoint(
                ProjectionCheckpoint(
                    worker_name=self.worker_name,
                    cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
                    cursor_value=str(record.global_position),
                )
            )

            return PostgresProjectionWorkerResult(
                worker_name=self.worker_name,
                action="applied",
                global_position=record.global_position,
                order_id=event.order_id,
                event_sequence=event.sequence,
                projected_version=next_state.version,
                reason="accepted event applied and checkpoint advanced",
            )

    def _load_last_global_position(self) -> int:
        checkpoint = self.checkpoint_store.load_checkpoint(self.worker_name)

        if checkpoint is None:
            return 0

        if checkpoint.cursor_kind != CheckpointCursorKind.GLOBAL_POSITION:
            raise ValueError(
                "PostgresProjectionWorker requires GLOBAL_POSITION checkpoint, "
                f"got {checkpoint.cursor_kind}"
            )

        return int(checkpoint.cursor_value)