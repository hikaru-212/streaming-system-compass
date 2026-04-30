from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional.registry import OrderRegistry
from src.pipeline.transactional.admission import OptimisticVersionGate
from src.storage.event_store import EventStore
from src.storage.idempotency_store import IdempotencyProvider
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode
from src.core.order.enums import OrderStatus


def build_registry() -> OrderRegistry:
    store = EventStore()
    idem = IdempotencyProvider()

    strict_validator = FullProofValidator()
    off_validator = NoOpValidator()

    dispatcher = ValidationDispatcher(
        strict_validator=strict_validator,
        off_validator=off_validator,
    )
    policy = ValidationPolicy()
    validation_runtime = ValidationRuntime(
        dispatcher=dispatcher,
        policy=policy,
        mode=ValidationMode.STRICT,
    )

    gate = OptimisticVersionGate(store)

    return OrderRegistry(
        store=store,
        idem=idem,
        validation_runtime=validation_runtime,
        gate=gate,
    )


class TestTransactionFlowCreatePay:
    def test_create_then_pay_end_to_end(self):
        registry = build_registry()

        created = registry.handle_create("create-001", "order-123", 100.0)
        paid = registry.handle_pay("pay-001", "order-123", 100.0)

        assert created.sequence == 1
        assert paid.sequence == 2

        history = registry.store.load("order-123")
        assert len(history) == 2
        assert history[0] == created
        assert history[1] == paid

    def test_replay_history_reconstructs_final_state(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", 100.0)
        registry.handle_pay("pay-001", "order-123", 100.0)

        history = registry.store.load("order-123")

        aggregate = OrderAggregate("order-123")
        for event in history:
            aggregate.apply(event)

        assert aggregate.status == OrderStatus.PAID
        assert aggregate.total_amount == 100.0
        assert aggregate.paid_amount == 100.0
        assert aggregate.current_version == 2

    def test_store_last_event_matches_paid_event(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", 100.0)
        paid = registry.handle_pay("pay-001", "order-123", 100.0)

        last = registry.store.last_event("order-123")

        assert last == paid
        assert last.sequence == 2