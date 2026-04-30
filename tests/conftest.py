import pytest

from src.storage.event_store import EventStore
from src.storage.idempotency_store import IdempotencyProvider
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode
from src.pipeline.transactional.admission import OptimisticVersionGate
from src.pipeline.transactional.registry import OrderRegistry


pytest_plugins = [
    "tests.fixtures.order_events",
    "tests.fixtures.histories",
    "tests.fixtures.request_signatures",
    "tests.fixtures.validation_contexts",
]


@pytest.fixture
def empty_store():
    return EventStore()


@pytest.fixture
def empty_idempotency_provider():
    return IdempotencyProvider()


@pytest.fixture
def strict_validator():
    return FullProofValidator()


@pytest.fixture
def off_validator():
    return NoOpValidator()


@pytest.fixture
def strict_validation_runtime(strict_validator, off_validator):
    dispatcher = ValidationDispatcher(
        strict_validator=strict_validator,
        off_validator=off_validator,
    )
    policy = ValidationPolicy()
    return ValidationRuntime(
        dispatcher=dispatcher,
        policy=policy,
        mode=ValidationMode.STRICT,
    )


@pytest.fixture
def off_validation_runtime(strict_validator, off_validator):
    dispatcher = ValidationDispatcher(
        strict_validator=strict_validator,
        off_validator=off_validator,
    )
    policy = ValidationPolicy()
    return ValidationRuntime(
        dispatcher=dispatcher,
        policy=policy,
        mode=ValidationMode.OFF,
    )


@pytest.fixture
def optimistic_gate(empty_store):
    return OptimisticVersionGate(empty_store)


@pytest.fixture
def registry_with_strict_compass(
    empty_store,
    empty_idempotency_provider,
    strict_validation_runtime,
):
    gate = OptimisticVersionGate(empty_store)
    return OrderRegistry(
        store=empty_store,
        idem=empty_idempotency_provider,
        validation_runtime=strict_validation_runtime,
        gate=gate,
    )


@pytest.fixture
def registry_without_compass(
    empty_store,
    empty_idempotency_provider,
    off_validation_runtime,
):
    gate = OptimisticVersionGate(empty_store)
    return OrderRegistry(
        store=empty_store,
        idem=empty_idempotency_provider,
        validation_runtime=off_validation_runtime,
        gate=gate,
    )


@pytest.fixture
def init_aggregate():
    from src.core.order.aggregate import OrderAggregate
    return OrderAggregate("order-123")