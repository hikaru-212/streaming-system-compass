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
    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        ...


class ProjectionSnapshotReplayValidator:
    """
    Validate whether a projection snapshot-assisted replay path reconstructs
    the same OrderState as accepted-history replay.

    This validator does NOT:
    - mutate accepted history
    - mutate projection state
    - advance checkpoints
    - write snapshots
    - decide runtime recovery policy
    - produce SemanticOutcome
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
                source_global_position=snapshot.source_global_position,
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

        target_tail_events = [
            record.event
            for record in tail_records
            if record.event.order_id == order_id
        ]

        try:
            for event in target_tail_events:
                snapshot_assisted_state = reduce_order_event(
                    snapshot_assisted_state,
                    event,
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
        source_global_position: int,
    ) -> list[ProjectionEventRecord]:
        records: list[ProjectionEventRecord] = []
        current_position = source_global_position

        while True:
            batch = self._tail_event_source.load_after(
                current_position,
                limit=self._tail_event_limit,
            )

            if not batch:
                return records

            previous_position = current_position

            for record in batch:
                if record.global_position <= previous_position:
                    raise ValueError(
                        "Tail event source returned non-advancing "
                        "global_position."
                    )

                previous_position = record.global_position

            records.extend(batch)
            current_position = previous_position


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