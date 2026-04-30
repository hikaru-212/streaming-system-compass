from src.core.order.enums import EventType, OrderStatus, CommandType
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.transactional.registry import OrderRegistry
from src.pipeline.transactional.admission import OptimisticVersionGate
from src.storage.event_store import EventStore
from src.storage.idempotency_store import (
    IdempotencyProvider,
    RequestSignature,
    IdempotencyVerdict,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode, EnforcementAction


def build_registry_with_real_compass() -> OrderRegistry:
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


class TestRegistryWithCompass:
    def test_valid_create_still_passes_with_real_compass(self):
        registry = build_registry_with_real_compass()

        result = registry.handle_create("create-001", "order-123", 100.0)

        assert result.sequence == 1
        history = registry.store.load("order-123")
        assert len(history) == 1
        assert history[0] == result

    def test_valid_pay_still_passes_with_real_compass(self):
        registry = build_registry_with_real_compass()

        registry.handle_create("create-001", "order-123", 100.0)
        result = registry.handle_pay("pay-001", "order-123", 100.0)

        assert result.sequence == 2
        history = registry.store.load("order-123")
        assert len(history) == 2
        assert history[1] == result

    def test_compass_blocks_candidate_with_wrong_prev_event_id(self):
        registry = build_registry_with_real_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id="wrong-event-id",   # 故意錯
            ),
        )

        decision = registry.validation_runtime.decide(broken_event, context)

        assert decision.action == EnforcementAction.BLOCK
        assert decision.validation_result.event_id == broken_event.event_id
        assert "prev_event_id" in decision.validation_result.reason or "Predecessor mismatch" in decision.validation_result.reason

        history_after = registry.store.load("order-123")
        assert len(history_after) == 1
        assert history_after[0] == created

    def test_compass_blocks_candidate_with_wrong_prev_version(self):
        registry = build_registry_with_real_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=999,   # 故意錯
                prev_event_id=created.event_id,
            ),
        )

        decision = registry.validation_runtime.decide(broken_event, context)

        assert decision.action == EnforcementAction.BLOCK
        assert decision.validation_result.event_id == broken_event.event_id
        assert "prev_version" in decision.validation_result.reason or "Proof mismatch" in decision.validation_result.reason

        history_after = registry.store.load("order-123")
        assert len(history_after) == 1
        assert history_after[0] == created

    def test_compass_blocks_candidate_with_wrong_prev_status_claim(self):
        registry = build_registry_with_real_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.INIT,   # 故意錯
                prev_version=1,
                prev_event_id=created.event_id,
            ),
        )

        decision = registry.validation_runtime.decide(broken_event, context)

        assert decision.action == EnforcementAction.BLOCK
        assert decision.validation_result.event_id == broken_event.event_id
        assert "prev_status" in decision.validation_result.reason or "actual history" in decision.validation_result.reason

        history_after = registry.store.load("order-123")
        assert len(history_after) == 1
        assert history_after[0] == created

    def test_validation_block_means_candidate_never_becomes_accepted_fact(self):
        """
        This test makes the separation explicit:

        - candidate event may be constructed
        - Compass may classify it as semantically untrustworthy
        - once blocked, it must not enter accepted history
        """
        registry = build_registry_with_real_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        blocked_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=99,   # 故意 stale / broken sequence
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created.event_id,
            ),
        )

        decision = registry.validation_runtime.decide(blocked_candidate, context)

        assert decision.action == EnforcementAction.BLOCK

        accepted_history = registry.store.load("order-123")
        assert len(accepted_history) == 1
        assert accepted_history[0] == created

    def test_blocked_candidate_should_not_be_recorded_as_idempotent_success(self):
        """
        A blocked candidate must not pollute request replay memory.

        Why this matters:
        - idempotency memory should only record accepted requests
        - otherwise the system could replay a request that never actually became fact
        """
        registry = build_registry_with_real_compass()

        created = registry.handle_create("create-001", "order-123", 100.0)

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        blocked_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.INIT,   # 故意錯
                prev_version=1,
                prev_event_id=created.event_id,
            ),
        )

        decision = registry.validation_runtime.decide(blocked_candidate, context)

        assert decision.action == EnforcementAction.BLOCK

        idem_decision = registry.idem.check(
            RequestSignature(
                request_id="pay-001",
                command_type=CommandType.PAY,
                order_id="order-123",
                amount=100.0,
            )
        )
        assert idem_decision.verdict == IdempotencyVerdict.MISS