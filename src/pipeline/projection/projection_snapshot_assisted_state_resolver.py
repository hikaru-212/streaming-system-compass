from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from src.core.order.state import OrderState


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