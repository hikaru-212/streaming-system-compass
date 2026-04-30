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


def build_transactional_runtime(
    validation_mode: ValidationMode = ValidationMode.STRICT,
) -> OrderRegistry:
    """
    Compose the transactional write-side runtime.

    Responsibility of this composition root:
    - instantiate concrete storage implementations
    - instantiate concrete validation components
    - instantiate concrete admission strategy
    - wire them into one OrderRegistry

    Important boundary:
    - business logic must NOT live here
    - this file only decides how interfaces are wired to implementations

    Current runtime composition:
    - EventStore -> in-memory accepted-history store
    - IdempotencyProvider -> in-memory request replay store
    - Compass Layer 1 -> ValidationDispatcher + ValidationPolicy + ValidationRuntime
    - Admission Gate -> OptimisticVersionGate
    - Transactional Orchestrator -> OrderRegistry
    """
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
        mode=validation_mode,
    )

    gate = OptimisticVersionGate(store)

    return OrderRegistry(
        store=store,
        idem=idem,
        validation_runtime=validation_runtime,
        gate=gate,
    )