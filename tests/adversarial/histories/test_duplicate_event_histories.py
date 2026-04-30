from src.core.order.aggregate import OrderAggregate
from tests.shared.replay_reducer import reduce_history_to_state


class TestDuplicateEventHistories:
    def test_aggregate_replay_fails_on_duplicate_created_event(self, created_event):
        history = [created_event, created_event]  # duplicate sequence=1

        aggregate = OrderAggregate("order-123")

        try:
            for event in history:
                aggregate.apply(event)
            assert False, "Expected duplicate event replay to fail"
        except ValueError as exc:
            assert "Sequence discontinuity" in str(exc)

    def test_reducer_fails_on_duplicate_created_event(self, created_event):
        history = [created_event, created_event]

        try:
            reduce_history_to_state(history)
            assert False, "Expected duplicate event replay reduction to fail"
        except ValueError as exc:
            assert "Broken sequence" in str(exc)