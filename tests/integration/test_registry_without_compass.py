import pytest

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


def build_registry_without_compass() -> OrderRegistry:
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
        mode=ValidationMode.OFF,   # 關鍵：Compass validation bypassed
    )

    gate = OptimisticVersionGate(store)

    return OrderRegistry(
        store=store,
        idem=idem,
        validation_runtime=validation_runtime,
        gate=gate,
    )


class TestRegistryWithoutCompass:
    def test_create_and_pay_still_run_without_compass(self):
        registry = build_registry_without_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)
        paid = registry.handle_pay("pay-001", "order-123", 100.0)

        assert created.sequence == 1
        assert paid.sequence == 2

        history = registry.store.load("order-123")
        assert len(history) == 2

    def test_idempotency_replay_still_works_without_compass(self):
        registry = build_registry_without_compass()

        first = registry.handle_create("create-001", "order-123", 100.0)
        second = registry.handle_create("create-001", "order-123", 100.0)

        assert second == first
        history = registry.store.load("order-123")
        assert len(history) == 1

    def test_payload_conflict_still_works_without_compass(self):
        registry = build_registry_without_compass()

        registry.handle_create("create-001", "order-123", 100.0)
        conflict = registry.handle_create("create-001", "order-123", 10.0)

        assert hasattr(conflict, "verdict")
        assert conflict.verdict.value == "conflict"

    def test_without_compass_system_relies_on_aggregate_and_admission_boundaries(self):
        """
        This test documents the boundary difference explicitly:

        - Without Compass, the system can still run.
        - Aggregate legality still applies.
        - Idempotency still applies.
        - Admission gate still applies.
        - What is missing is the explicit semantic-truth validation layer.
        """
        registry = build_registry_without_compass()

        registry.handle_create("create-001", "order-123", 100.0)
        registry.handle_pay("pay-001", "order-123", 100.0)

        with pytest.raises(ValueError, match="Order is already paid"):
            registry.handle_pay("pay-002", "order-123", 100.0)