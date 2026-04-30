from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from tests.shared.replay_reducer import reduce_history_to_state


class TestBrokenContinuityHistories:
    def test_aggregate_replay_fails_on_sequence_gap(self, created_event):
        gap_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=3,  # gap: missing sequence 2
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        history = [created_event, gap_event]

        aggregate = OrderAggregate("order-123")

        try:
            for event in history:
                aggregate.apply(event)
            assert False, "Expected replay with sequence gap to fail"
        except ValueError as exc:
            assert "Sequence discontinuity" in str(exc)

    def test_reducer_fails_on_sequence_gap(self, created_event):
        gap_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=3,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        history = [created_event, gap_event]

        try:
            reduce_history_to_state(history)
            assert False, "Expected replay reduction with sequence gap to fail"
        except ValueError as exc:
            assert "Broken sequence" in str(exc)