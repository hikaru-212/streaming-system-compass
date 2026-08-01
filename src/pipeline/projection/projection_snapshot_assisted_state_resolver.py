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
    def load_after_sequence(
        self,
        order_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        ...


class ProjectionSnapshotAssistedStateResolver:
    """Resolve state from an explicitly trusted snapshot and its local tail.

    The tail source is constrained to the requested order and traversed by
    contiguous event sequence. Snapshot ``source_global_position`` is lineage,
    not a completeness cursor.

    The generic resolver owns no database connection or transaction.
    PostgreSQL callers that need one coherent database observation must use the
    PostgreSQL orchestration boundary.

    This resolver does not establish snapshot trust, compare against accepted
    authority, mutate durable state, or choose fallback/runtime policy.
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
        """Resolve one order from an explicitly trusted snapshot and local tail.

        ``trusted_snapshot_id`` must identify a compatible snapshot for
        ``order_id``. The returned typed result describes resolved state or the
        relevant precondition, compatibility, source-contract, or replay
        failure. Tail events must be exact-next local sequences for the same
        order.

        This generic method owns no connection or transaction, does not
        establish trust, and performs no mutation, fallback, or runtime action.
        """
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
                order_id=order_id,
                source_event_sequence=snapshot.source_event_sequence,
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

        try:
            for record in tail_records:
                resolved_state = reduce_order_event(
                    resolved_state,
                    record.event,
                )
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
