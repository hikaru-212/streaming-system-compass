from decimal import Decimal
import pytest

from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestOrderAggregateInit:
    def test_init_with_valid_order_id(self):
        agg = OrderAggregate("order-123")

        assert agg.order_id == "order-123"
        assert agg.current_version == 0
        assert agg.status == OrderStatus.INIT
        assert agg.total_amount == Decimal("0.00")
        assert agg.paid_amount == Decimal("0.00")
        assert agg.last_event_id is None

    @pytest.mark.parametrize("bad_order_id", ["", "   "])
    def test_init_with_empty_order_id_should_fail(self, bad_order_id):
        with pytest.raises(ValueError, match="order_id must not be empty"):
            OrderAggregate(bad_order_id)


class TestCreateCommand:
    def test_create_success_from_init(self):
        agg = OrderAggregate("order-123")

        event = agg.create("create-001", Decimal("100.00"))

        assert event.order_id == "order-123"
        assert event.request_id == "create-001"
        assert event.sequence == 1
        assert event.event_type == EventType.CREATED
        assert event.amount == Decimal("100.00")
        assert event.proof.prev_status == OrderStatus.INIT
        assert event.proof.prev_version == 0
        assert event.proof.prev_event_id is None

    @pytest.mark.parametrize("bad_request_id", ["", "   "])
    def test_create_with_empty_request_id_should_fail(self, bad_request_id):
        agg = OrderAggregate("order-123")

        with pytest.raises(ValueError, match="request_id must not be empty"):
            agg.create(bad_request_id, Decimal("100.00"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0.00"), Decimal("-1.00"), Decimal("-100.00")])
    def test_create_with_non_positive_total_amount_should_fail(self, bad_amount):
        agg = OrderAggregate("order-123")

        with pytest.raises(ValueError, match="money amount must be positive"):
            agg.create("create-001", bad_amount)

    def test_create_after_already_created_should_fail(self, created_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        with pytest.raises(ValueError, match="Already created"):
            agg.create("create-002", Decimal("100.00"))


class TestPayCommand:
    def test_pay_success_after_created(self, created_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        event = agg.pay("pay-001", Decimal("100.00"))

        assert event.order_id == "order-123"
        assert event.request_id == "pay-001"
        assert event.sequence == 2
        assert event.event_type == EventType.PAID
        assert event.amount == Decimal("100.00")
        assert event.proof.prev_status == OrderStatus.CREATED
        assert event.proof.prev_version == 1
        assert event.proof.prev_event_id == created_event.event_id

    @pytest.mark.parametrize("bad_request_id", ["", "   "])
    def test_pay_with_empty_request_id_should_fail(self, bad_request_id, created_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        with pytest.raises(ValueError, match="request_id must not be empty"):
            agg.pay(bad_request_id, Decimal("100.00"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0.00"), Decimal("-1.00"), Decimal("-100.00")])
    def test_pay_with_non_positive_payment_amount_should_fail(self, bad_amount, created_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        with pytest.raises(ValueError, match="money amount must be positive"):
            agg.pay("pay-001", bad_amount)

    def test_pay_before_created_should_fail(self):
        agg = OrderAggregate("order-123")

        with pytest.raises(ValueError, match="Cannot pay before order is created"):
            agg.pay("pay-001", Decimal("100.00"))

    def test_pay_with_amount_not_equal_total_amount_should_fail(self, created_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        with pytest.raises(ValueError, match="v1 full-payment rule violated"):
            agg.pay("pay-001", Decimal("50.00"))

    def test_pay_after_already_paid_should_fail(self, created_event, paid_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)
        agg.apply(paid_event)

        with pytest.raises(ValueError, match="Order is already paid"):
            agg.pay("pay-002", Decimal("100.00"))


class TestApplyEvent:
    def test_apply_created_updates_state(self, created_event):
        agg = OrderAggregate("order-123")

        agg.apply(created_event)

        assert agg.status == OrderStatus.CREATED
        assert agg.total_amount == Decimal("100.00")
        assert agg.current_version == 1
        assert agg.last_event_id == created_event.event_id

    def test_apply_paid_updates_state_without_accumulation(self, created_event, paid_event):
        agg = OrderAggregate("order-123")
        agg.apply(created_event)

        agg.apply(paid_event)

        assert agg.status == OrderStatus.PAID
        assert agg.paid_amount == Decimal("100.00")
        assert agg.current_version == 2
        assert agg.last_event_id == paid_event.event_id

    def test_apply_with_order_id_mismatch_should_fail(self):
        agg = OrderAggregate("order-123")

        wrong_event = OrderEvent.create(
            request_id="create-001",
            order_id="order-999",
            sequence=1,
            event_type=EventType.CREATED,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.INIT,
                prev_version=0,
                prev_event_id=None,
            ),
        )

        with pytest.raises(ValueError, match="Order id mismatch during apply"):
            agg.apply(wrong_event)

    def test_apply_with_sequence_discontinuity_should_fail(self, paid_event):
        agg = OrderAggregate("order-123")

        with pytest.raises(ValueError, match="Sequence discontinuity during apply"):
            agg.apply(paid_event)

    def test_replay_created_then_paid_reconstructs_correct_final_state(self, created_event, paid_event):
        agg = OrderAggregate("order-123")

        agg.apply(created_event)
        agg.apply(paid_event)

        assert agg.status == OrderStatus.PAID
        assert agg.total_amount == Decimal("100.00")
        assert agg.paid_amount == Decimal("100.00")
        assert agg.current_version == 2
        assert agg.last_event_id == paid_event.event_id