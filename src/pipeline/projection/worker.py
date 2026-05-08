from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.core.order.events import OrderEvent
from src.core.order.state import OrderState
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)
from src.storage.checkpoint_store import CheckpointStoreProtocol
from src.storage.projection_store import ProjectionStoreProtocol


@dataclass(frozen=True)
class ProjectionRecord:
    """
    One accepted event together with its stream position.

    offset:
        Position in the accepted event stream.
        This is processing metadata, not domain truth.

    event:
        One already-accepted write-side event.
    """

    offset: int
    event: OrderEvent


@dataclass(frozen=True)
class ProjectionProcessResult:
    """
    Human-readable result for testing and debugging.

    action:
        - "applied"
        - "skipped_already_consumed"
        - "skipped_already_projected"
    """

    offset: int
    order_id: str
    event_sequence: int
    action: str
    projected_version: int
    reason: str


class ProjectionSequenceGapError(Exception):
    """
    Raised when the worker sees a future sequence gap.

    Example:
    - current projected version = 1
    - incoming event.sequence = 3

    First-version policy:
    - no buffering
    - no out-of-order queue
    - fail fast
    """


class ProjectionWorker:
    """
    First-version projection worker.

    Design goal:
    - deterministic
    - replay-safe
    - checkpoint-aware
    - deliberately conservative

    This worker consumes only accepted history.

    It does NOT:
    - validate candidate-event truth claims
    - do write-side admission
    - perform out-of-order buffering
    - do TTL / pending queue / DLQ logic

    Current policy:
    1. offset <= checkpoint                 -> already consumed, skip
    2. event.sequence <= state.version      -> already projected / late, skip
    3. event.sequence == state.version + 1  -> reduce and persist
    4. event.sequence > state.version + 1   -> raise ProjectionSequenceGapError
    """

    def __init__(
        self,
        worker_name: str,
        projection_store: ProjectionStoreProtocol,
        checkpoint_store: CheckpointStoreProtocol,
    ) -> None:
        self.worker_name = worker_name
        self.projection_store = projection_store
        self.checkpoint_store = checkpoint_store

    def process_record(self, record: ProjectionRecord) -> ProjectionProcessResult:
        """
        Process exactly one accepted record.

        Side-effect order is intentional:

        1. Read checkpoint
        2. Read current projected state
        3. Validate processing order / sequence assumptions
        4. Run pure reducer
        5. Save projected state
        6. Save checkpoint

        Important limitation in this first version:
        - projection state save and checkpoint save are not yet guaranteed
          to be atomically committed together.
        - later versions should tighten this with stronger storage semantics.
        """
        current_offset = self.checkpoint_store.load_offset(self.worker_name)
        if record.offset <= current_offset:
            current_state = self._load_or_init_state(record.event.order_id)
            return ProjectionProcessResult(
                offset=record.offset,
                order_id=record.event.order_id,
                event_sequence=record.event.sequence,
                action="skipped_already_consumed",
                projected_version=current_state.version,
                reason="record offset already checkpointed",
            )

        current_state = self._load_or_init_state(record.event.order_id)

        # Basic projection-side idempotency / late-event defense:
        # if this event sequence is not newer than the projected state version,
        # we do not apply it again.
        if record.event.sequence <= current_state.version:
            self.checkpoint_store.save_offset(self.worker_name, record.offset)
            return ProjectionProcessResult(
                offset=record.offset,
                order_id=record.event.order_id,
                event_sequence=record.event.sequence,
                action="skipped_already_projected",
                projected_version=current_state.version,
                reason="event sequence is already reflected in projected state",
            )

        expected_next_sequence = current_state.version + 1
        if record.event.sequence > expected_next_sequence:
            raise ProjectionSequenceGapError(
                f"Projection worker sequence gap: "
                f"expected {expected_next_sequence}, got {record.event.sequence}"
            )

        next_state = reduce_order_event(current_state, record.event)

        # Side effects are intentionally concentrated after all validation passes.
        self.projection_store.save_state(next_state)
        self.checkpoint_store.save_offset(self.worker_name, record.offset)

        return ProjectionProcessResult(
            offset=record.offset,
            order_id=record.event.order_id,
            event_sequence=record.event.sequence,
            action="applied",
            projected_version=next_state.version,
            reason="projection state advanced successfully",
        )

    def replay(
        self, records: Iterable[ProjectionRecord]
    ) -> list[ProjectionProcessResult]:
        """
        Deterministically rebuild projection state from accepted history records.

        This uses the same process_record path as live processing.
        That is intentional: replay and incremental projection must share
        the same reduction semantics.
        """
        results: list[ProjectionProcessResult] = []
        for record in records:
            results.append(self.process_record(record))
        return results

    def _load_or_init_state(self, order_id: str) -> OrderState:
        """
        Load projected state for one order, or create an empty read-side state
        if this order has not been projected yet.
        """
        state = self.projection_store.load_state(order_id)
        if state is not None:
            return state
        return build_empty_projection_state(order_id)