from decimal import Decimal
import pytest

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.projection.worker import (
    ProjectionRecord,
    ProjectionSequenceGapError,
    ProjectionWorker,
)
from src.storage.checkpoint_store import InMemoryCheckpointStore
from src.storage.projection_store import InMemoryProjectionStore


def make_event(
    *,
    request_id: str,
    order_id: str,
    sequence: int,
    event_type: EventType,
    amount: Decimal,
    prev_status: OrderStatus,
    prev_version: int,
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=event_type,
        amount=amount,
        proof=Proof(
            prev_status=prev_status,
            prev_version=prev_version,
            prev_event_id=None,
        ),
    )


def build_worker() -> tuple[ProjectionWorker, InMemoryProjectionStore, InMemoryCheckpointStore]:
    projection_store = InMemoryProjectionStore()
    checkpoint_store = InMemoryCheckpointStore()
    worker = ProjectionWorker(
        worker_name="projection-worker-v1",
        projection_store=projection_store,
        checkpoint_store=checkpoint_store,
    )
    return worker, projection_store, checkpoint_store


def test_worker_applies_created_event_and_advances_checkpoint():
    worker, projection_store, checkpoint_store = build_worker()

    event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )
    record = ProjectionRecord(offset=10, event=event)

    result = worker.process_record(record)

    state = projection_store.load_state("order-123")
    assert result.action == "applied"
    assert state is not None
    assert state.status == OrderStatus.CREATED
    assert state.version == 1
    assert checkpoint_store.load_offset("projection-worker-v1") == 10


def test_worker_skips_already_consumed_offset():
    worker, projection_store, checkpoint_store = build_worker()

    event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )
    record = ProjectionRecord(offset=10, event=event)

    worker.process_record(record)
    result = worker.process_record(record)

    assert result.action == "skipped_already_consumed"
    assert checkpoint_store.load_offset("projection-worker-v1") == 10


def test_worker_skips_already_projected_sequence_but_advances_offset():
    worker, projection_store, checkpoint_store = build_worker()

    first_event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )
    worker.process_record(ProjectionRecord(offset=10, event=first_event))

    duplicate_sequence_event = make_event(
        request_id="create-002",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )
    result = worker.process_record(
        ProjectionRecord(offset=11, event=duplicate_sequence_event)
    )

    assert result.action == "skipped_already_projected"
    assert checkpoint_store.load_offset("projection-worker-v1") == 11


def test_worker_raises_on_future_sequence_gap():
    worker, _, _ = build_worker()

    gap_event = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=2,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )

    with pytest.raises(ProjectionSequenceGapError, match="sequence gap"):
        worker.process_record(ProjectionRecord(offset=10, event=gap_event))


def test_worker_replay_uses_same_runtime_path():
    worker, projection_store, checkpoint_store = build_worker()

    created = make_event(
        request_id="create-001",
        order_id="order-123",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
    )
    paid = make_event(
        request_id="pay-001",
        order_id="order-123",
        sequence=2,
        event_type=EventType.PAID,
        amount=Decimal("100.00"),
        prev_status=OrderStatus.CREATED,
        prev_version=1,
    )

    results = worker.replay(
        [
            ProjectionRecord(offset=10, event=created),
            ProjectionRecord(offset=11, event=paid),
        ]
    )

    assert len(results) == 2
    assert results[0].action == "applied"
    assert results[1].action == "applied"

    final_state = projection_store.load_state("order-123")
    assert final_state is not None
    assert final_state.status == OrderStatus.PAID
    assert final_state.version == 2
    assert checkpoint_store.load_offset("projection-worker-v1") == 11