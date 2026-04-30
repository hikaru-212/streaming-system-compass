from src.core.order.aggregate import OrderAggregate
from tests.shared.replay_reducer import reduce_history_to_state


class TestOutOfOrderHistories:
    def test_aggregate_replay_fails_when_paid_comes_before_created(self, created_event, paid_event):
        history = [paid_event, created_event]  # out of order

        aggregate = OrderAggregate("order-123")

        try:
            for event in history:
                aggregate.apply(event)
            assert False, "Expected out-of-order replay to fail"
        except ValueError as exc:
            assert "Sequence discontinuity" in str(exc)

    def test_reducer_fails_when_paid_comes_before_created(self, created_event, paid_event):
        history = [paid_event, created_event]

        try:
            reduce_history_to_state(history)
            assert False, "Expected out-of-order replay reduction to fail"
        except ValueError as exc:
            assert "Broken sequence" in str(exc)