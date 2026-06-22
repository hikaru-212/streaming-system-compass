from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
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


def test_projection_snapshot_replay_validation_status_values() -> None:
    assert ProjectionSnapshotReplayValidationStatus.MATCH.value == "MATCH"
    assert (
        ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT.value
        == "MISSING_SNAPSHOT"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER.value
        == "NO_ACCEPTED_HISTORY_FOR_ORDER"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY.value
        == "INVALID_SNAPSHOT_BOUNDARY"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT.value
        == "SNAPSHOT_ASSISTED_DRIFT"
    )


def test_match_result_reports_is_match_true() -> None:
    snapshot_id = uuid4()
    state = make_order_state()

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MATCH,
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=state,
        authority_state=state,
    )

    assert result.is_match is True
    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.order_id == "order-001"
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert result.snapshot_assisted_state == state
    assert result.authority_state == state
    assert result.reason is None


def test_missing_snapshot_result_can_preserve_authority_state() -> None:
    authority_state = make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
        order_id="order-001",
        authority_state=authority_state,
        reason="No projection snapshot found for order.",
    )

    assert result.is_match is False
    assert result.status == ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT
    assert result.order_id == "order-001"
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.snapshot_assisted_state is None
    assert result.authority_state == authority_state
    assert result.reason == "No projection snapshot found for order."


def test_no_accepted_history_for_order_result_has_no_authority_and_no_snapshot_assisted_state() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER,
        order_id="order-001",
        reason="No accepted history exists for order.",
    )

    assert result.is_match is False
    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER
    )
    assert result.order_id == "order-001"
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.snapshot_assisted_state is None
    assert result.authority_state is None
    assert result.reason == "No accepted history exists for order."


def test_invalid_snapshot_boundary_result_can_preserve_authority_state() -> None:
    snapshot_id = uuid4()
    authority_state = make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY,
        order_id="order-001",
        snapshot_id=snapshot_id,
        source_global_position=10,
        snapshot_assisted_state=None,
        authority_state=authority_state,
        reason="Snapshot source boundary is invalid.",
    )

    assert result.is_match is False
    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.order_id == "order-001"
    assert result.snapshot_id == snapshot_id
    assert result.source_global_position == 10
    assert result.snapshot_assisted_state is None
    assert result.authority_state == authority_state
    assert result.reason == "Snapshot source boundary is invalid."


def test_snapshot_assisted_drift_result_preserves_both_states() -> None:
    snapshot_assisted_state = make_order_state(
        status=OrderStatus.CREATED,
        paid_amount=Decimal("0.00"),
        version=1,
    )
    authority_state = make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )

    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT,
        order_id="order-001",
        snapshot_id=uuid4(),
        source_global_position=10,
        snapshot_assisted_state=snapshot_assisted_state,
        authority_state=authority_state,
        reason="Snapshot-assisted replay does not match authority replay.",
    )

    assert result.is_match is False
    assert result.snapshot_assisted_state == snapshot_assisted_state
    assert result.authority_state == authority_state
    assert result.reason == "Snapshot-assisted replay does not match authority replay."


def test_non_match_statuses_report_is_match_false() -> None:
    for status in (
        ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
        ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER,
        ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY,
        ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT,
    ):
        result = ProjectionSnapshotReplayValidationResult(
            status=status,
            order_id="order-001",
        )

        assert result.is_match is False