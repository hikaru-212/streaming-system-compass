from decimal import Decimal

from src.pipeline.transactional.registry import OrderRegistry
from src.pipeline.transactional.admission import OptimisticVersionGate, AdmissionVerdict
from src.storage.event_store import EventStore
from src.storage.idempotency_store import IdempotencyProvider, RequestSignature, IdempotencyVerdict
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode, EnforcementAction
from src.core.order.enums import CommandType


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


class TestConcurrencyAdmission:
    def test_optimistic_gate_rejects_stale_write_under_concurrent_collision(self):
        registry = build_registry()

        # establish version=1 baseline
        registry.handle_create("create-001", "order-123", Decimal("100.00"))

        # worker A reads version=1
        agg_a, history_a = registry._rehydrate_aggregate("order-123")
        context_a = registry._build_validation_context(agg_a, history_a[-1])
        event_a = agg_a.pay("pay-worker-a", Decimal("100.00"))

        # worker B reads the same version=1 before A commits
        agg_b, history_b = registry._rehydrate_aggregate("order-123")
        context_b = registry._build_validation_context(agg_b, history_b[-1])
        event_b = agg_b.pay("pay-worker-b", Decimal("100.00"))

        # semantic truth still passes for both candidates against their local read context
        decision_a = registry.validation_runtime.decide(event_a, context_a)
        decision_b = registry.validation_runtime.decide(event_b, context_b)

        assert decision_a.action == EnforcementAction.ALLOW
        assert decision_b.action == EnforcementAction.ALLOW

        # A wins the append race
        admission_a = registry.gate.append_if_admitted(event_a, expected_current_version=1)
        assert admission_a.verdict == AdmissionVerdict.ADMITTED

        # B becomes stale and must be rejected by the admission boundary
        admission_b = registry.gate.append_if_admitted(event_b, expected_current_version=1)
        assert admission_b.verdict == AdmissionVerdict.STALE_WRITE
        assert "Version conflict" in admission_b.reason

        # accepted history must contain only one successful pay
        history = registry.store.load("order-123")
        assert len(history) == 2
        assert history[0].request_id == "create-001"
        assert history[1].request_id == "pay-worker-a"

        # stale candidate must not be recorded as accepted idempotency success
        idem_decision = registry.idem.check(
            RequestSignature(
                request_id="pay-worker-b",
                command_type=CommandType.PAY,
                order_id="order-123",
                amount=Decimal("100.00"),
            )
        )
        assert idem_decision.verdict == IdempotencyVerdict.MISS