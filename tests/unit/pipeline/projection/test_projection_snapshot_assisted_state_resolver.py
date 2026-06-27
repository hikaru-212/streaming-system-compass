from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from uuid import uuid4

import pytest

from src.core.order.enums import EventType
from src.core.order.enums import OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedStateResolver,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


class FakeSnapshotStore:
    def __init__(self, snapshots: list[ProjectionSnapshot]) -> None:
        self.snapshots = {
            snapshot.snapshot_id: snapshot
            for snapshot in snapshots
        }
        self.loaded_snapshot_ids: list[UUID] = []

    def load_snapshot(
        self,
        snapshot_id: UUID,
    ) -> ProjectionSnapshot | None:
        self.loaded_snapshot_ids.append(snapshot_id)
        return self.snapshots.get(snapshot_id)


class FakeTailEventSource:
    def __init__(self, records: list[ProjectionEventRecord]) -> None:
        self.records = records
        self.load_after_calls: list[tuple[int, int]] = []

    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        self.load_after_calls.append((global_position, limit))
        return [
            record
            for record in self.records
            if record.global_position > global_position
        ][:limit]


class NonAdvancingTailEventSource:
    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        created_event = make_created_event()

        return [
            ProjectionEventRecord(
                global_position=global_position,
                event=created_event,
            )
        ]


class OutOfOrderTailEventSource:
    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        created_event = make_created_event()
        paid_event = make_paid_event(previous_event=created_event)

        return [
            ProjectionEventRecord(
                global_position=global_position + 2,
                event=paid_event,
            ),
            ProjectionEventRecord(
                global_position=global_position + 1,
                event=created_event,
            ),
        ]


def make_order_state(
    *,
    order_id: str = "order-001",
    status: OrderStatus = OrderStatus.CREATED,
    total_amount: Decimal = Decimal("100.00"),
    paid_amount: Decimal = Decimal("0.00"),
    version: int = 1,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        version=version,
    )


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
    metadata: dict | None = None,
    created_by: str = "test",
) -> ProjectionSnapshot:
    if snapshot_id is None:
        snapshot_id = uuid4()

    if source_event_id is None:
        source_event_id = uuid4()

    if metadata is None:
        metadata = {}

    return ProjectionSnapshot(
        snapshot_id=snapshot_id,
        order_id=order_id,
        source_event_id=source_event_id,
        source_event_sequence=source_event_sequence,
        source_global_position=source_global_position,
        state_status=state_status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        state_version=state_version,
        snapshot_schema_version=snapshot_schema_version,
        reducer_version=reducer_version,
        payload_hash=payload_hash,
        metadata=metadata,
        created_by=created_by,
    )


def make_created_event(
    *,
    order_id: str = "order-001",
    request_id: str = "create-001",
    sequence: int = 1,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=EventType.CREATED,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )


def make_paid_event(
    *,
    previous_event: OrderEvent,
    request_id: str = "pay-001",
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=previous_event.order_id,
        sequence=previous_event.sequence + 1,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=previous_event.sequence,
            prev_event_id=previous_event.event_id,
        ),
    )


def make_resolver(
    *,
    snapshots: list[ProjectionSnapshot],
    tail_records: list[ProjectionEventRecord],
    tail_event_limit: int = 1000,
) -> ProjectionSnapshotAssistedStateResolver:
    return ProjectionSnapshotAssistedStateResolver(
        snapshot_store=FakeSnapshotStore(snapshots),
        tail_event_source=FakeTailEventSource(tail_records),
        tail_event_limit=tail_event_limit,
    )


def test_projection_snapshot_assisted_resolution_status_values() -> None:
    assert (
        ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT.value
        == "RESOLVED_FROM_SNAPSHOT"
    )
    assert (
        ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT.value
        == "MISSING_SNAPSHOT"
    )
    assert (
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_PRECONDITION
        .value
        == "INVALID_SNAPSHOT_PRECONDITION"
    )
    assert (
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_COMPATIBILITY
        .value
        == "INVALID_SNAPSHOT_COMPATIBILITY"
    )
    assert (
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        .value
        == "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    )
    assert (
        ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED.value
        == "TAIL_REPLAY_FAILED"
    )


def test_resolved_from_snapshot_result_reports_is_resolved_true() -> None:
    snapshot_id = uuid4()
    resolved_state = make_order_state()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .RESOLVED_FROM_SNAPSHOT
        ),
        resolved_state=resolved_state,
        snapshot_id=snapshot_id,
        source_global_position=10,
    )

    assert result.is_resolved is True
    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .RESOLVED_FROM_SNAPSHOT
    )
    assert result.order_id == "order-001"
    assert result.resolved_state == resolved_state
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert result.reason is None


def test_missing_snapshot_result_reports_is_resolved_false() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        reason="Projection snapshot was not found.",
    )

    assert result.is_resolved is False
    assert result.status == ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT
    assert result.order_id == "order-001"
    assert result.resolved_state is None
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.reason == "Projection snapshot was not found."


def test_invalid_snapshot_precondition_result_reports_is_resolved_false() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_PRECONDITION
        ),
        reason="trusted_snapshot_id is required.",
    )

    assert result.is_resolved is False
    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_PRECONDITION
    )
    assert result.resolved_state is None
    assert result.reason == "trusted_snapshot_id is required."


def test_invalid_snapshot_compatibility_result_can_preserve_snapshot_boundary() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_COMPATIBILITY
        ),
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Snapshot reducer_version is not supported by this resolver.",
    )

    assert result.is_resolved is False
    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_COMPATIBILITY
    )
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert (
        result.reason
        == "Snapshot reducer_version is not supported by this resolver."
    )


def test_tail_event_source_contract_violation_result_can_preserve_snapshot_boundary() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Tail event source returned non-advancing global_position.",
    )

    assert result.is_resolved is False
    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    )
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert result.reason == (
        "Tail event source returned non-advancing global_position."
    )


def test_tail_replay_failed_result_does_not_expose_resolved_state() -> None:
    snapshot_id = uuid4()

    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
        snapshot_id=snapshot_id,
        source_global_position=10,
        reason="Snapshot-assisted tail replay failed.",
    )

    assert result.is_resolved is False
    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED
    )
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert result.reason == "Snapshot-assisted tail replay failed."


def test_unresolved_statuses_report_is_resolved_false() -> None:
    unresolved_statuses = (
        ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        (
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_PRECONDITION
        ),
        (
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_COMPATIBILITY
        ),
        (
            ProjectionSnapshotAssistedResolutionStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
    )

    for status in unresolved_statuses:
        result = ProjectionSnapshotAssistedResolutionResult(
            order_id="order-001",
            status=status,
            reason=f"{status.value} test reason.",
        )

        assert result.is_resolved is False
        assert result.resolved_state is None


def test_resolution_result_does_not_expose_authority_state() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
    )

    assert not hasattr(result, "authority_state")


def test_resolver_rejects_missing_trusted_snapshot_id() -> None:
    resolver = make_resolver(
        snapshots=[],
        tail_records=[],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=None,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.INVALID_SNAPSHOT_PRECONDITION
    )
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.reason == "trusted_snapshot_id is required."


def test_resolver_returns_missing_snapshot_when_snapshot_id_not_found() -> None:
    missing_snapshot_id = uuid4()
    resolver = make_resolver(
        snapshots=[],
        tail_records=[],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=missing_snapshot_id,
    )

    assert result.status == ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == missing_snapshot_id
    assert result.source_global_position is None
    assert result.reason == "Projection snapshot was not found."


def test_resolver_loads_snapshot_by_trusted_snapshot_id() -> None:
    target_snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=10,
        payload_hash="sha256:target",
    )
    newer_snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=2,
        source_global_position=20,
        state_status="PAID",
        paid_amount=Decimal("100.00"),
        state_version=2,
        payload_hash="sha256:newer",
    )
    snapshot_store = FakeSnapshotStore([target_snapshot, newer_snapshot])
    resolver = ProjectionSnapshotAssistedStateResolver(
        snapshot_store=snapshot_store,
        tail_event_source=FakeTailEventSource([]),
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=target_snapshot.snapshot_id,
    )

    assert result.is_resolved is True
    assert result.snapshot_id == target_snapshot.snapshot_id
    assert result.source_global_position == 10
    assert snapshot_store.loaded_snapshot_ids == [target_snapshot.snapshot_id]


def test_resolver_resolves_valid_snapshot_with_no_tail() -> None:
    snapshot = make_snapshot()
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.is_resolved is True
    assert result.resolved_state == make_order_state()
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason == "Projection state resolved from snapshot and tail replay."


def test_resolver_resolves_valid_snapshot_with_same_order_tail() -> None:
    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    tail_record = ProjectionEventRecord(
        global_position=2,
        event=paid_event,
    )
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[tail_record],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.is_resolved is True
    assert result.resolved_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )


def test_resolver_ignores_tail_events_for_other_orders() -> None:
    snapshot = make_snapshot(order_id="order-001")
    other_created_event = make_created_event(
        order_id="order-002",
        request_id="create-other",
    )
    other_tail_record = ProjectionEventRecord(
        global_position=2,
        event=other_created_event,
    )
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[other_tail_record],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.resolved_state == make_order_state()


def test_resolver_uses_tail_events_after_snapshot_global_position() -> None:
    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=10,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    source_event_record = ProjectionEventRecord(
        global_position=10,
        event=created_event,
    )
    tail_event_record = ProjectionEventRecord(
        global_position=11,
        event=paid_event,
    )
    tail_source = FakeTailEventSource(
        records=[source_event_record, tail_event_record],
    )
    resolver = ProjectionSnapshotAssistedStateResolver(
        snapshot_store=FakeSnapshotStore([snapshot]),
        tail_event_source=tail_source,
        tail_event_limit=25,
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert tail_source.load_after_calls == [(10, 25), (11, 25)]
    assert result.resolved_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )


def test_resolver_loads_tail_records_across_pages() -> None:
    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    tail_source = FakeTailEventSource(
        records=[
            ProjectionEventRecord(
                global_position=2,
                event=paid_event,
            ),
        ],
    )
    resolver = ProjectionSnapshotAssistedStateResolver(
        snapshot_store=FakeSnapshotStore([snapshot]),
        tail_event_source=tail_source,
        tail_event_limit=1,
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
    )
    assert result.resolved_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    assert tail_source.load_after_calls == [(1, 1), (2, 1)]


def test_resolver_rejects_snapshot_order_id_mismatch() -> None:
    snapshot = make_snapshot(order_id="different-order")
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.INVALID_SNAPSHOT_COMPATIBILITY
    )
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason is not None
    assert "order_id does not match" in result.reason


@pytest.mark.parametrize(
    "snapshot",
    [
        make_snapshot(source_global_position=0),
        make_snapshot(source_event_sequence=0),
        make_snapshot(state_version=-1),
        make_snapshot(state_version=2, source_event_sequence=1),
        make_snapshot(state_version=1, source_event_sequence=2),
        make_snapshot(state_status="INIT"),
        make_snapshot(snapshot_schema_version=2),
        make_snapshot(reducer_version="order_projection_reducer:v2"),
    ],
)
def test_resolver_rejects_invalid_snapshot_compatibility(
    snapshot: ProjectionSnapshot,
) -> None:
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert (
        result.status
        == ProjectionSnapshotAssistedResolutionStatus.INVALID_SNAPSHOT_COMPATIBILITY
    )
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason is not None


def test_resolver_reports_tail_contract_violation_when_tail_event_source_does_not_advance() -> None:
    snapshot = make_snapshot()
    resolver = ProjectionSnapshotAssistedStateResolver(
        snapshot_store=FakeSnapshotStore([snapshot]),
        tail_event_source=NonAdvancingTailEventSource(),
        tail_event_limit=1,
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    )
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason is not None
    assert "non-advancing global_position" in result.reason


def test_resolver_reports_tail_contract_violation_when_tail_event_source_returns_out_of_order_positions() -> None:
    snapshot = make_snapshot()
    resolver = ProjectionSnapshotAssistedStateResolver(
        snapshot_store=FakeSnapshotStore([snapshot]),
        tail_event_source=OutOfOrderTailEventSource(),
        tail_event_limit=10,
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert result.status == (
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    )
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason is not None
    assert "non-advancing global_position" in result.reason


def test_resolver_returns_tail_replay_failed_when_tail_replay_violates_transition_rule() -> None:
    duplicate_created_event = make_created_event(
        request_id="create-duplicate",
        sequence=2,
    )

    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    resolver = make_resolver(
        snapshots=[snapshot],
        tail_records=[
            ProjectionEventRecord(
                global_position=2,
                event=duplicate_created_event,
            )
        ],
    )

    result = resolver.resolve_order(
        "order-001",
        trusted_snapshot_id=snapshot.snapshot_id,
    )

    assert result.status == ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED
    assert result.is_resolved is False
    assert result.resolved_state is None
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.reason is not None
    assert "tail replay failed" in result.reason


def test_resolver_rejects_non_positive_tail_event_limit() -> None:
    with pytest.raises(ValueError, match="tail_event_limit must be positive"):
        ProjectionSnapshotAssistedStateResolver(
            snapshot_store=FakeSnapshotStore([]),
            tail_event_source=FakeTailEventSource([]),
            tail_event_limit=0,
        )
