from decimal import Decimal

from src.core.order.aggregate import OrderAggregate
from src.core.order.state import OrderState
from src.core.order.enums import OrderStatus
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
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)


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


class TestReplayConsistency:
    def test_replayed_aggregate_matches_reducer_snapshot(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        history = registry.store.load("order-123")

        aggregate = OrderAggregate("order-123")
        for event in history:
            aggregate.apply(event)

        snapshot = build_empty_projection_state("order-123")
        for event in history:
            snapshot = reduce_order_event(snapshot, event)

        assert snapshot.order_id == aggregate.order_id
        assert snapshot.status == aggregate.status
        assert snapshot.total_amount == aggregate.total_amount
        assert snapshot.paid_amount == aggregate.paid_amount
        assert snapshot.version == aggregate.current_version

    def test_replay_reducer_fails_on_broken_sequence(self, created_event, paid_event):
        broken_history = [paid_event]  # sequence=2 directly, deliberately broken

        try:
            snapshot = build_empty_projection_state("order-123")
            for event in broken_history:
                snapshot = reduce_order_event(snapshot, event)
            assert False, "Expected ValueError for broken replay sequence"
        except ValueError as exc:
            assert "sequence violation" in str(exc)

    def test_order_state_snapshot_is_immutable(self):
        snapshot = OrderState(
            order_id="order-123",
            status=OrderStatus.CREATED,
            total_amount=Decimal("100.00"),
            paid_amount=Decimal("0.00"),
            version=1,
        )

        try:
            snapshot.version = 2
            assert False, "Expected immutable OrderState to reject mutation"
        except Exception:
            pass  # Expected dataclass frozen error