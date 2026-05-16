from decimal import Decimal
import pytest

from src.pipeline.transactional.registry import OrderRegistry
from src.pipeline.transactional.admission import OptimisticVersionGate
from src.storage.event_store import EventStore
from src.storage.idempotency_store import IdempotencyProvider, IdempotencyVerdict
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode


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


class TestIdempotencyReplayAndConflict:
    def test_same_create_request_replays_prior_result(self):
        registry = build_registry()

        first = registry.handle_create("create-001", "order-123", Decimal("100.00"))
        second = registry.handle_create("create-001", "order-123", Decimal("100.00"))

        assert second == first

        history = registry.store.load("order-123")
        assert len(history) == 1

    def test_same_create_request_id_with_different_payload_conflicts(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        conflict = registry.handle_create("create-001", "order-123", Decimal("10.00"))

        assert conflict.verdict == IdempotencyVerdict.CONFLICT

        history = registry.store.load("order-123")
        assert len(history) == 1

    def test_same_pay_request_replays_prior_result(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", Decimal("100.00"))

        first = registry.handle_pay("pay-001", "order-123", Decimal("100.00"))
        second = registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        assert second == first

        history = registry.store.load("order-123")
        assert len(history) == 2

    def test_same_pay_request_id_with_different_payload_conflicts(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        conflict = registry.handle_pay("pay-001", "order-123", Decimal("10.00"))

        assert conflict.verdict == IdempotencyVerdict.CONFLICT

        history = registry.store.load("order-123")
        assert len(history) == 2

    def test_different_request_id_after_paid_is_new_action_not_replay(self):
        registry = build_registry()

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        with pytest.raises(ValueError, match="Order is already paid"):
            registry.handle_pay("pay-002", "order-123", Decimal("100.00"))