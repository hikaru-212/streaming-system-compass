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
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
    ProjectionSnapshotReplayValidator,
)
from src.storage.postgres_projection_event_source import ProjectionEventRecord
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


class FakeSnapshotStore:
    def __init__(self, snapshot: ProjectionSnapshot | None) -> None:
        self.snapshot = snapshot
        self.loaded_order_ids: list[str] = []

    def load_latest_snapshot(self, order_id: str) -> ProjectionSnapshot | None:
        self.loaded_order_ids.append(order_id)
        return self.snapshot


class FakeAcceptedHistoryStore:
    def __init__(self, events: list[OrderEvent]) -> None:
        self.events = events
        self.loaded_order_ids: list[str] = []

    def load(self, order_id: str) -> list[OrderEvent]:
        self.loaded_order_ids.append(order_id)
        return [
            event
            for event in self.events
            if event.order_id == order_id
        ]


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


def make_validator(
    *,
    snapshot: ProjectionSnapshot | None,
    accepted_events: list[OrderEvent],
    tail_records: list[ProjectionEventRecord],
    tail_event_limit: int = 1000,
) -> ProjectionSnapshotReplayValidator:
    return ProjectionSnapshotReplayValidator(
        snapshot_store=FakeSnapshotStore(snapshot),
        accepted_history_store=FakeAcceptedHistoryStore(accepted_events),
        tail_event_source=FakeTailEventSource(tail_records),
        tail_event_limit=tail_event_limit,
    )


def test_projection_snapshot_replay_validation_status_values() -> None:
    assert ProjectionSnapshotReplayValidationStatus.MATCH.value == "MATCH"
    assert (
        ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT.value
        == "MISSING_SNAPSHOT"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus
        .NO_ACCEPTED_HISTORY_FOR_ORDER
        .value
        == "NO_ACCEPTED_HISTORY_FOR_ORDER"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY.value
        == "INVALID_SNAPSHOT_BOUNDARY"
    )
    assert (
        ProjectionSnapshotReplayValidationStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        .value
        == "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
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
        status=(
            ProjectionSnapshotReplayValidationStatus
            .NO_ACCEPTED_HISTORY_FOR_ORDER
        ),
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


def test_tail_event_source_contract_violation_result_preserves_states() -> None:
    snapshot_assisted_state = make_order_state()
    authority_state = make_order_state()

    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        order_id="order-001",
        snapshot_id=uuid4(),
        source_global_position=10,
        snapshot_assisted_state=snapshot_assisted_state,
        authority_state=authority_state,
        reason="Tail event source returned non-advancing global_position.",
    )

    assert result.is_match is False
    assert (
        result.status
        == (
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        )
    )
    assert result.snapshot_assisted_state == snapshot_assisted_state
    assert result.authority_state == authority_state
    assert result.reason == (
        "Tail event source returned non-advancing global_position."
    )


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
        ProjectionSnapshotReplayValidationStatus.TAIL_EVENT_SOURCE_CONTRACT_VIOLATION,
        ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT,
    ):
        result = ProjectionSnapshotReplayValidationResult(
            status=status,
            order_id="order-001",
        )

        assert result.is_match is False


def test_validator_returns_missing_snapshot_with_authority_state_when_history_exists() -> None:
    created_event = make_created_event()
    validator = make_validator(
        snapshot=None,
        accepted_events=[created_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    expected_authority_state = OrderState(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )

    assert result.status == ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT
    assert result.is_match is False
    assert result.order_id == "order-001"
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.snapshot_assisted_state is None
    assert result.authority_state == expected_authority_state
    assert result.reason is not None
    assert "authority state was reconstructed" in result.reason


def test_validator_returns_no_accepted_history_when_no_snapshot_and_no_history() -> None:
    validator = make_validator(
        snapshot=None,
        accepted_events=[],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER
    )
    assert result.is_match is False
    assert result.order_id == "order-001"
    assert result.snapshot_id is None
    assert result.source_global_position is None
    assert result.snapshot_assisted_state is None
    assert result.authority_state is None
    assert result.reason is not None
    assert "No accepted history" in result.reason


def test_validator_returns_no_accepted_history_for_order_when_snapshot_exists_without_history() -> None:
    snapshot = make_snapshot()
    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER
    )
    assert result.is_match is False
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.source_global_position == snapshot.source_global_position
    assert result.snapshot_assisted_state is None
    assert result.authority_state is None


def test_validator_matches_when_snapshot_has_no_tail_and_equals_authority_replay() -> None:
    created_event = make_created_event()
    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.is_match is True
    assert result.snapshot_assisted_state == make_order_state()
    assert result.authority_state == make_order_state()


def test_validator_matches_when_tail_replay_reconstructs_authority_state() -> None:
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

    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event, paid_event],
        tail_records=[tail_record],
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.is_match is True
    assert result.source_global_position == 1
    assert result.snapshot_assisted_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    assert result.authority_state == result.snapshot_assisted_state


def test_validator_ignores_tail_events_for_other_orders() -> None:
    created_event = make_created_event(order_id="order-001")
    other_created_event = make_created_event(
        order_id="order-002",
        request_id="create-other",
    )

    snapshot = make_snapshot(
        order_id="order-001",
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    other_tail_record = ProjectionEventRecord(
        global_position=2,
        event=other_created_event,
    )

    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event, other_created_event],
        tail_records=[other_tail_record],
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.snapshot_assisted_state == make_order_state()
    assert result.authority_state == make_order_state()


def test_validator_detects_drift_when_tail_source_misses_accepted_event() -> None:
    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)

    stale_snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )

    validator = make_validator(
        snapshot=stale_snapshot,
        accepted_events=[created_event, paid_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
    )
    assert result.is_match is False
    assert result.snapshot_assisted_state == make_order_state()
    assert result.authority_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    assert result.reason is not None
    assert "differs from accepted-history replay" in result.reason


def test_validator_rejects_snapshot_ahead_of_authority_boundary() -> None:
    created_event = make_created_event()

    ahead_snapshot = make_snapshot(
        source_event_sequence=2,
        source_global_position=2,
        state_status="PAID",
        paid_amount=Decimal("100.00"),
        state_version=2,
    )

    validator = make_validator(
        snapshot=ahead_snapshot,
        accepted_events=[created_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.is_match is False
    assert result.snapshot_id == ahead_snapshot.snapshot_id
    assert result.source_global_position == ahead_snapshot.source_global_position
    assert result.snapshot_assisted_state is None
    assert result.authority_state == make_order_state(
        status=OrderStatus.CREATED,
        paid_amount=Decimal("0.00"),
        version=1,
    )
    assert result.reason is not None
    assert "ahead of accepted history" in result.reason


def test_validator_rejects_snapshot_order_id_mismatch() -> None:
    created_event = make_created_event(order_id="order-001")
    snapshot = make_snapshot(order_id="different-order")

    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.authority_state == make_order_state()
    assert result.snapshot_assisted_state is None
    assert result.reason is not None
    assert "order_id does not match" in result.reason


@pytest.mark.parametrize(
    "snapshot",
    [
        make_snapshot(source_global_position=0),
        make_snapshot(source_event_sequence=0),
        make_snapshot(state_version=-1),
        make_snapshot(state_version=2, source_event_sequence=1),
        make_snapshot(state_status="INIT"),
    ],
)
def test_validator_rejects_invalid_snapshot_boundary(
    snapshot: ProjectionSnapshot,
) -> None:
    created_event = make_created_event()
    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.is_match is False
    assert result.snapshot_assisted_state is None
    assert result.authority_state == make_order_state()


def test_validator_rejects_snapshot_state_version_behind_source_sequence() -> None:
    created_event = make_created_event()
    paid_event = make_paid_event(previous_event=created_event)
    snapshot = make_snapshot(
        source_event_sequence=2,
        source_global_position=2,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )
    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event, paid_event],
        tail_records=[],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.INVALID_SNAPSHOT_BOUNDARY
    )
    assert result.snapshot_assisted_state is None
    assert result.authority_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    assert result.reason is not None
    assert "state_version" in result.reason
    assert "source_event_sequence" in result.reason


def test_validator_uses_tail_events_after_snapshot_global_position() -> None:
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
    validator = ProjectionSnapshotReplayValidator(
        snapshot_store=FakeSnapshotStore(snapshot),
        accepted_history_store=FakeAcceptedHistoryStore(
            [created_event, paid_event],
        ),
        tail_event_source=tail_source,
        tail_event_limit=25,
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert tail_source.load_after_calls == [(10, 25), (11, 25)]
    assert result.snapshot_assisted_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )


def test_validator_loads_tail_records_across_pages() -> None:
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

    validator = ProjectionSnapshotReplayValidator(
        snapshot_store=FakeSnapshotStore(snapshot),
        accepted_history_store=FakeAcceptedHistoryStore(
            [created_event, paid_event],
        ),
        tail_event_source=tail_source,
        tail_event_limit=1,
    )

    result = validator.validate_order("order-001")

    assert result.status == ProjectionSnapshotReplayValidationStatus.MATCH
    assert result.snapshot_assisted_state == make_order_state(
        status=OrderStatus.PAID,
        paid_amount=Decimal("100.00"),
        version=2,
    )
    assert tail_source.load_after_calls == [(1, 1), (2, 1)]


def test_validator_reports_tail_contract_violation_when_tail_event_source_does_not_advance() -> None:
    created_event = make_created_event()
    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )

    validator = ProjectionSnapshotReplayValidator(
        snapshot_store=FakeSnapshotStore(snapshot),
        accepted_history_store=FakeAcceptedHistoryStore([created_event]),
        tail_event_source=NonAdvancingTailEventSource(),
        tail_event_limit=1,
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == (
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        )
    )
    assert result.snapshot_assisted_state == make_order_state()
    assert result.authority_state == make_order_state()
    assert result.reason is not None
    assert "non-advancing global_position" in result.reason


def test_validator_reports_tail_contract_violation_when_tail_event_source_returns_out_of_order_positions() -> None:
    created_event = make_created_event()
    snapshot = make_snapshot(
        source_event_sequence=1,
        source_global_position=1,
        state_status="CREATED",
        paid_amount=Decimal("0.00"),
        state_version=1,
    )

    validator = ProjectionSnapshotReplayValidator(
        snapshot_store=FakeSnapshotStore(snapshot),
        accepted_history_store=FakeAcceptedHistoryStore([created_event]),
        tail_event_source=OutOfOrderTailEventSource(),
        tail_event_limit=10,
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == (
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        )
    )
    assert result.snapshot_assisted_state == make_order_state()
    assert result.authority_state == make_order_state()
    assert result.reason is not None
    assert "non-advancing global_position" in result.reason


def test_validator_returns_drift_when_tail_replay_violates_transition_rule() -> None:
    created_event = make_created_event()

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

    validator = make_validator(
        snapshot=snapshot,
        accepted_events=[created_event],
        tail_records=[
            ProjectionEventRecord(
                global_position=2,
                event=duplicate_created_event,
            )
        ],
    )

    result = validator.validate_order("order-001")

    assert (
        result.status
        == ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
    )
    assert result.reason is not None
    assert "tail replay failed" in result.reason


def test_validator_rejects_non_positive_tail_event_limit() -> None:
    with pytest.raises(ValueError, match="tail_event_limit must be positive"):
        ProjectionSnapshotReplayValidator(
            snapshot_store=FakeSnapshotStore(None),
            accepted_history_store=FakeAcceptedHistoryStore([]),
            tail_event_source=FakeTailEventSource([]),
            tail_event_limit=0,
        )