from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID

from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.state import OrderState
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


class ProjectionSnapshotReplayValidationStatus(str, Enum):
    MATCH = "MATCH"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    NO_ACCEPTED_HISTORY_FOR_ORDER = "NO_ACCEPTED_HISTORY_FOR_ORDER"
    INVALID_SNAPSHOT_BOUNDARY = "INVALID_SNAPSHOT_BOUNDARY"
    TAIL_EVENT_SOURCE_CONTRACT_VIOLATION = (
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    )
    SNAPSHOT_ASSISTED_DRIFT = "SNAPSHOT_ASSISTED_DRIFT"


@dataclass(frozen=True)
class ProjectionSnapshotReplayValidationResult:
    status: ProjectionSnapshotReplayValidationStatus
    order_id: str

    snapshot_id: UUID | None = None
    source_global_position: int | None = None

    snapshot_assisted_state: OrderState | None = None
    authority_state: OrderState | None = None

    reason: str | None = None

    @property
    def is_match(self) -> bool:
        return self.status == ProjectionSnapshotReplayValidationStatus.MATCH


class ProjectionSnapshotStoreProtocol(Protocol):
    def load_latest_snapshot(self, order_id: str) -> ProjectionSnapshot | None:
        ...


class AcceptedHistoryStoreProtocol(Protocol):
    def load(self, order_id: str) -> list[OrderEvent]:
        ...


class ProjectionTailEventSourceProtocol(Protocol):
    def load_after_sequence(
        self,
        order_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        ...


class ProjectionSnapshotReplayValidator:
    """Compare snapshot-assisted state with accepted-history authority replay.

    The snapshot tail is loaded for exactly one order and advanced by contiguous
    order-local sequence. ``source_global_position`` remains returned lineage;
    it is not a tail cursor or completeness proof.

    The generic validator does not own database connections or transactions.
    PostgreSQL callers that describe the result as one database observation
    must use a PostgreSQL orchestration boundary that supplies one connection
    and one explicit top-level transaction.

    This validator does not mutate state, establish snapshot trust, select
    fallback policy, or produce a SemanticOutcome.
    """

    def __init__(
        self,
        *,
        snapshot_store: ProjectionSnapshotStoreProtocol,
        accepted_history_store: AcceptedHistoryStoreProtocol,
        tail_event_source: ProjectionTailEventSourceProtocol,
        tail_event_limit: int = 1000,
    ) -> None:
        if tail_event_limit <= 0:
            raise ValueError("tail_event_limit must be positive")

        self._snapshot_store = snapshot_store
        self._accepted_history_store = accepted_history_store
        self._tail_event_source = tail_event_source
        self._tail_event_limit = tail_event_limit

    def validate_order(
        self,
        order_id: str,
    ) -> ProjectionSnapshotReplayValidationResult:
        """Compare one order's snapshot path with accepted-history replay.

        ``order_id`` selects both authority history and the same-order snapshot
        tail. The result classifies match, missing evidence, invalid boundary,
        tail contract failure, or drift and contains relevant reconstructed
        states. Tail replay must be contiguous by local sequence.

        This generic method owns no connection or transaction and makes no
        fallback, trust, mutation, or runtime-policy decision.
        """
        snapshot = self._snapshot_store.load_latest_snapshot(order_id)
        accepted_events = self._accepted_history_store.load(order_id)

        if not accepted_events:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .NO_ACCEPTED_HISTORY_FOR_ORDER
                ),
                order_id=order_id,
                snapshot_id=(
                    snapshot.snapshot_id
                    if snapshot is not None
                    else None
                ),
                source_global_position=(
                    snapshot.source_global_position
                    if snapshot is not None
                    else None
                ),
                snapshot_assisted_state=None,
                authority_state=None,
                reason="No accepted history exists for order.",
            )

        authority_state = _replay_authority_state(
            order_id=order_id,
            accepted_events=accepted_events,
        )
        authority_max_sequence = max(
            event.sequence
            for event in accepted_events
        )

        if snapshot is None:
            return ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
                order_id=order_id,
                snapshot_id=None,
                source_global_position=None,
                snapshot_assisted_state=None,
                authority_state=authority_state,
                reason=(
                    "No projection snapshot exists for order; "
                    "authority state was reconstructed from accepted history."
                ),
            )

        invalid_reason = _validate_snapshot_boundary(
            snapshot=snapshot,
            requested_order_id=order_id,
            authority_max_sequence=authority_max_sequence,
        )
        if invalid_reason is not None:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .INVALID_SNAPSHOT_BOUNDARY
                ),
                order_id=order_id,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                snapshot_assisted_state=None,
                authority_state=authority_state,
                reason=invalid_reason,
            )

        try:
            snapshot_assisted_state = _hydrate_snapshot_state(snapshot)
        except ValueError as exc:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .INVALID_SNAPSHOT_BOUNDARY
                ),
                order_id=order_id,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                snapshot_assisted_state=None,
                authority_state=authority_state,
                reason=str(exc),
            )

        try:
            tail_records = self._load_all_tail_records(
                order_id=order_id,
                source_event_sequence=snapshot.source_event_sequence,
            )
        except ValueError as exc:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
                ),
                order_id=order_id,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                snapshot_assisted_state=snapshot_assisted_state,
                authority_state=authority_state,
                reason=str(exc),
            )

        try:
            for record in tail_records:
                snapshot_assisted_state = reduce_order_event(
                    snapshot_assisted_state,
                    record.event,
                )
        except ValueError as exc:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .SNAPSHOT_ASSISTED_DRIFT
                ),
                order_id=order_id,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                snapshot_assisted_state=snapshot_assisted_state,
                authority_state=authority_state,
                reason=f"Snapshot-assisted tail replay failed: {exc}",
            )

        if snapshot_assisted_state != authority_state:
            return ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .SNAPSHOT_ASSISTED_DRIFT
                ),
                order_id=order_id,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                snapshot_assisted_state=snapshot_assisted_state,
                authority_state=authority_state,
                reason=(
                    "Snapshot-assisted replay differs from "
                    "accepted-history replay."
                ),
            )

        return ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MATCH,
            order_id=order_id,
            snapshot_id=snapshot.snapshot_id,
            source_global_position=snapshot.source_global_position,
            snapshot_assisted_state=snapshot_assisted_state,
            authority_state=authority_state,
            reason="Snapshot-assisted replay matches accepted-history replay.",
        )

    def _load_all_tail_records(
        self,
        *,
        order_id: str,
        source_event_sequence: int,
    ) -> list[ProjectionEventRecord]:
        """Load a complete contiguous tail for one order by local sequence."""
        records: list[ProjectionEventRecord] = []
        current_sequence = source_event_sequence

        while True:
            batch = self._tail_event_source.load_after_sequence(
                order_id,
                current_sequence,
                limit=self._tail_event_limit,
            )

            if not batch:
                return records

            for record in batch:
                expected_sequence = current_sequence + 1
                if record.event.order_id != order_id:
                    raise ValueError(
                        "Tail event source returned an event for a different "
                        "order_id."
                    )
                if record.event.sequence != expected_sequence:
                    raise ValueError(
                        "Tail event source returned a non-contiguous "
                        "order-local sequence: "
                        f"expected {expected_sequence}, "
                        f"got {record.event.sequence}."
                    )
                current_sequence = record.event.sequence

            records.extend(batch)


def _validate_snapshot_boundary(
    *,
    snapshot: ProjectionSnapshot,
    requested_order_id: str,
    authority_max_sequence: int,
) -> str | None:
    if snapshot.order_id != requested_order_id:
        return (
            "Snapshot order_id does not match requested order_id: "
            f"snapshot.order_id={snapshot.order_id}, "
            f"requested_order_id={requested_order_id}"
        )

    if snapshot.source_global_position <= 0:
        return "Snapshot source_global_position must be positive."

    if snapshot.source_event_sequence <= 0:
        return "Snapshot source_event_sequence must be positive."

    if snapshot.source_event_sequence > authority_max_sequence:
        return (
            "Snapshot source_event_sequence is ahead of accepted history: "
            f"snapshot.source_event_sequence={snapshot.source_event_sequence}, "
            f"authority_max_sequence={authority_max_sequence}"
        )

    if snapshot.state_version < 0:
        return "Snapshot state_version must be non-negative."

    if snapshot.state_version > snapshot.source_event_sequence:
        return (
            "Snapshot state_version must not be ahead of "
            "source_event_sequence."
        )

    # Empty projection state starts at version 0, but persisted snapshots in the
    # current reducer model must point to at least one accepted event. Because this
    # reducer maps one accepted order event to one projection version, a usable
    # snapshot must have state_version == source_event_sequence.
    if snapshot.state_version != snapshot.source_event_sequence:
        return (
            "Current order projection reducer requires snapshot state_version "
            "to equal source_event_sequence."
        )

    supported_snapshot_statuses = {
        OrderStatus.CREATED.value,
        OrderStatus.PAID.value,
    }

    if snapshot.state_status not in supported_snapshot_statuses:
        return f"Unsupported snapshot state_status: {snapshot.state_status}"

    return None


def _hydrate_snapshot_state(snapshot: ProjectionSnapshot) -> OrderState:
    try:
        status = OrderStatus(snapshot.state_status)
    except ValueError as exc:
        raise ValueError(
            f"Unsupported snapshot state_status: {snapshot.state_status}"
        ) from exc

    return OrderState(
        order_id=snapshot.order_id,
        status=status,
        total_amount=snapshot.total_amount,
        paid_amount=snapshot.paid_amount,
        version=snapshot.state_version,
    )


def _replay_authority_state(
    *,
    order_id: str,
    accepted_events: list[OrderEvent],
) -> OrderState:
    state = build_empty_projection_state(order_id)

    for event in accepted_events:
        state = reduce_order_event(state, event)

    return state
