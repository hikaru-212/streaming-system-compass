from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.pipeline.projection.reducer import reduce_order_event
from src.storage.postgres_projection_event_source import ProjectionEventRecord
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


SUPPORTED_SNAPSHOT_SCHEMA_VERSION = 1
SUPPORTED_REDUCER_VERSION = "order_projection_reducer:v1"


class ProjectionSnapshotAssistedResolutionStatus(str, Enum):
    RESOLVED_FROM_SNAPSHOT = "RESOLVED_FROM_SNAPSHOT"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    INVALID_SNAPSHOT_PRECONDITION = "INVALID_SNAPSHOT_PRECONDITION"
    INVALID_SNAPSHOT_COMPATIBILITY = "INVALID_SNAPSHOT_COMPATIBILITY"
    TAIL_EVENT_SOURCE_CONTRACT_VIOLATION = (
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    )
    TAIL_REPLAY_FAILED = "TAIL_REPLAY_FAILED"


@dataclass(frozen=True)
class ProjectionSnapshotAssistedResolutionResult:
    order_id: str
    status: ProjectionSnapshotAssistedResolutionStatus

    resolved_state: OrderState | None = None

    snapshot_id: UUID | None = None
    source_global_position: int | None = None

    reason: str | None = None

    @property
    def is_resolved(self) -> bool:
        return (
            self.status
            == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
        )


class ProjectionSnapshotLookupProtocol(Protocol):
    def load_snapshot(
        self,
        snapshot_id: UUID,
    ) -> ProjectionSnapshot | None:
        ...


class ProjectionTailEventSourceProtocol(Protocol):
    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        ...


class ProjectionSnapshotAssistedStateResolver:
    """
    Resolve read-side projection state from an explicitly qualified projection
    snapshot plus projection tail events.

    This resolver does NOT:
    - select the latest persisted snapshot
    - validate snapshot equivalence against accepted-history authority replay
    - mutate accepted history
    - mutate projection state
    - advance checkpoints
    - write snapshots
    - decide fallback / quarantine / rebuild policy
    - produce SemanticOutcome
    """

    def __init__(
        self,
        *,
        snapshot_store: ProjectionSnapshotLookupProtocol,
        tail_event_source: ProjectionTailEventSourceProtocol,
        tail_event_limit: int = 1000,
    ) -> None:
        if tail_event_limit <= 0:
            raise ValueError("tail_event_limit must be positive")

        self._snapshot_store = snapshot_store
        self._tail_event_source = tail_event_source
        self._tail_event_limit = tail_event_limit

    def resolve_order(
        self,
        order_id: str,
        *,
        trusted_snapshot_id: UUID | None,
    ) -> ProjectionSnapshotAssistedResolutionResult:
        if trusted_snapshot_id is None:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .INVALID_SNAPSHOT_PRECONDITION
                ),
                reason="trusted_snapshot_id is required.",
            )

        snapshot = self._snapshot_store.load_snapshot(trusted_snapshot_id)

        if snapshot is None:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
                snapshot_id=trusted_snapshot_id,
                reason="Projection snapshot was not found.",
            )

        invalid_reason = _validate_snapshot_compatibility(
            snapshot=snapshot,
            requested_order_id=order_id,
        )
        if invalid_reason is not None:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .INVALID_SNAPSHOT_COMPATIBILITY
                ),
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                reason=invalid_reason,
            )

        try:
            resolved_state = _hydrate_snapshot_state(snapshot)
        except ValueError as exc:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .INVALID_SNAPSHOT_COMPATIBILITY
                ),
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                reason=str(exc),
            )

        try:
            tail_records = self._load_all_tail_records(
                source_global_position=snapshot.source_global_position,
            )
        except ValueError as exc:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
                ),
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                reason=str(exc),
            )

        target_tail_events = [
            record.event
            for record in tail_records
            if record.event.order_id == order_id
        ]

        try:
            for event in target_tail_events:
                resolved_state = reduce_order_event(resolved_state, event)
        except ValueError as exc:
            return ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
                snapshot_id=snapshot.snapshot_id,
                source_global_position=snapshot.source_global_position,
                reason=f"Snapshot-assisted tail replay failed: {exc}",
            )

        return ProjectionSnapshotAssistedResolutionResult(
            order_id=order_id,
            status=ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT,
            resolved_state=resolved_state,
            snapshot_id=snapshot.snapshot_id,
            source_global_position=snapshot.source_global_position,
            reason="Projection state resolved from snapshot and tail replay.",
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


def _validate_snapshot_compatibility(
    *,
    snapshot: ProjectionSnapshot,
    requested_order_id: str,
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

    if snapshot.state_version < 0:
        return "Snapshot state_version must be non-negative."

    if snapshot.state_version > snapshot.source_event_sequence:
        return (
            "Snapshot state_version must not be ahead of "
            "source_event_sequence."
        )

    if snapshot.state_version != snapshot.source_event_sequence:
        return (
            "Current order projection reducer requires snapshot state_version "
            "to equal source_event_sequence."
        )

    if snapshot.snapshot_schema_version != SUPPORTED_SNAPSHOT_SCHEMA_VERSION:
        return (
            "Snapshot snapshot_schema_version is not supported by this "
            "resolver: "
            f"snapshot.snapshot_schema_version={snapshot.snapshot_schema_version}, "
            f"supported_snapshot_schema_version={SUPPORTED_SNAPSHOT_SCHEMA_VERSION}"
        )

    if snapshot.reducer_version != SUPPORTED_REDUCER_VERSION:
        return (
            "Snapshot reducer_version is not supported by this resolver: "
            f"snapshot.reducer_version={snapshot.reducer_version}, "
            f"supported_reducer_version={SUPPORTED_REDUCER_VERSION}"
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