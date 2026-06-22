from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from src.core.order.state import OrderState


class ProjectionSnapshotReplayValidationStatus(str, Enum):
    MATCH = "MATCH"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    NO_ACCEPTED_HISTORY_FOR_ORDER = "NO_ACCEPTED_HISTORY_FOR_ORDER"
    INVALID_SNAPSHOT_BOUNDARY = "INVALID_SNAPSHOT_BOUNDARY"
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