from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID
from uuid import uuid4

from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


def make_snapshot(
    *,
    snapshot_id: UUID | None = None,
    order_id: str = "order-001",
    source_event_id: UUID | None = None,
    source_event_sequence: int = 1,
    source_global_position: int = 1,
    state_status: str = "CREATED",
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    state_version: int = 1,
    snapshot_schema_version: int = 1,
    reducer_version: str = "order_projection_reducer:v1",
    payload_hash: str = "sha256:test-payload-hash",
    metadata: dict[str, Any] | None = None,
    created_by: str = "test",
) -> ProjectionSnapshot:
    return ProjectionSnapshot(
        snapshot_id=snapshot_id or uuid4(),
        order_id=order_id,
        source_event_id=source_event_id or uuid4(),
        source_event_sequence=source_event_sequence,
        source_global_position=source_global_position,
        state_status=state_status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        state_version=state_version,
        snapshot_schema_version=snapshot_schema_version,
        reducer_version=reducer_version,
        payload_hash=payload_hash,
        metadata=dict(metadata) if metadata is not None else {},
        created_by=created_by,
    )