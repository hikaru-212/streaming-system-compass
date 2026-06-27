from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)


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