from src.core.order.aggregate import OrderAggregate
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)


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
            state = build_empty_projection_state("order-123")
            for event in history:
                state = reduce_order_event(state, event)
            assert False, "Expected out-of-order replay reduction to fail"
        except ValueError as exc:
            assert "sequence violation" in str(exc)