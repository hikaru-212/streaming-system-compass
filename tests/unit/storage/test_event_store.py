from decimal import Decimal
import pytest

from src.storage.event_store import EventStore
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestEventStoreAppend:
    def test_append_first_event_success(self, created_event):
        store = EventStore()

        store.append(created_event, expected_current_version=0)

        history = store.load("order-123")
        assert len(history) == 1
        assert history[0] == created_event

    def test_append_second_event_success(self, created_event, paid_event):
        store = EventStore()
        store.append(created_event, expected_current_version=0)

        store.append(paid_event, expected_current_version=1)

        history = store.load("order-123")
        assert len(history) == 2
        assert history[0] == created_event
        assert history[1] == paid_event

    def test_append_with_stale_expected_version_should_fail(self, created_event):
        store = EventStore()
        store.append(created_event, expected_current_version=0)

        stale_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        with pytest.raises(ValueError, match="Version conflict"):
            store.append(stale_event, expected_current_version=0)

    def test_append_with_broken_sequence_should_fail(self):
        store = EventStore()

        broken_event = OrderEvent.create(
            request_id="create-001",
            order_id="order-123",
            sequence=99,
            event_type=EventType.CREATED,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.INIT,
                prev_version=0,
                prev_event_id=None,
            ),
        )

        with pytest.raises(ValueError, match="Append-time continuity broken"):
            store.append(broken_event, expected_current_version=0)


class TestEventStoreLoadAndLastEvent:
    def test_load_missing_order_returns_empty_list(self):
        store = EventStore()

        assert store.load("missing-order") == []

    def test_last_event_missing_order_returns_none(self):
        store = EventStore()

        assert store.last_event("missing-order") is None

    def test_last_event_returns_latest_event(self, created_event, paid_event):
        store = EventStore()
        store.append(created_event, expected_current_version=0)
        store.append(paid_event, expected_current_version=1)

        assert store.last_event("order-123") == paid_event

    def test_load_returns_copy_not_original_reference(self, created_event):
        store = EventStore()
        store.append(created_event, expected_current_version=0)

        loaded = store.load("order-123")
        loaded.clear()

        actual_history = store.load("order-123")
        assert len(actual_history) == 1
        assert actual_history[0] == created_event