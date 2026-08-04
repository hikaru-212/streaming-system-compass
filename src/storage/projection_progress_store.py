from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProjectionProgressConflictError(RuntimeError):
    """Raised when progress would regress, skip a sequence, or cite invalid lineage."""


@dataclass(frozen=True)
class ProjectionOrderProgress:
    """Durable progress for one order under one projection definition and epoch.

    Responsibility:
    - describe the last accepted order-local event durably applied to a projection.

    Inputs and outputs:
    - values are immutable storage-boundary data;
    - ``last_event_id`` and ``last_global_position`` are lineage, not authority.

    Invariants:
    - projection name and order ID are non-empty;
    - epoch, sequence, and global position are positive;
    - persisted updates advance by exactly one order-local sequence.

    Non-goals:
    - worker leasing;
    - globally ordered projection progress;
    - retry or recovery policy.
    """

    projection_name: str
    projection_epoch: int
    order_id: str
    last_sequence: int
    last_event_id: str
    last_global_position: int

    def __post_init__(self) -> None:
        if not self.projection_name.strip():
            raise ValueError("projection_name must not be empty")
        if self.projection_epoch <= 0:
            raise ValueError("projection_epoch must be positive")
        if not self.order_id.strip():
            raise ValueError("order_id must not be empty")
        if self.last_sequence <= 0:
            raise ValueError("last_sequence must be positive")
        if not self.last_event_id.strip():
            raise ValueError("last_event_id must not be empty")
        if self.last_global_position <= 0:
            raise ValueError("last_global_position must be positive")


class ProjectionProgressStoreProtocol(Protocol):
    """Persistence protocol for order-local projection progress."""

    def load_progress(
        self,
        *,
        projection_name: str,
        projection_epoch: int,
        order_id: str,
    ) -> ProjectionOrderProgress | None:
        """Load one identity, returning ``None`` for sequence zero.

        Implementations leave connection and transaction ownership to callers
        and must not infer progress from another order or legacy checkpoint.
        """

    def advance_progress(self, progress: ProjectionOrderProgress) -> None:
        """Persist one exact-next accepted order-local sequence.

        Implementations must reject stale, regressive, skipped, or mismatched
        lineage and leave transaction completion and retry policy to callers.
        """
