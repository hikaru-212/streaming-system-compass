from decimal import Decimal
import pytest

from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationResult,
    ValidationVerdict,
    ValidationMode,
)
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    OptimisticVersionGate,
)
from src.storage.idempotency_store import IdempotencyVerdict


class FakeValidationRuntimeAllow:
    def decide(self, event, context):
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="ok",
                event_id=event.event_id,
                validator_name="FakeValidationRuntimeAllow",
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )


class FakeValidationRuntimeBlock:
    def decide(self, event, context):
        return ValidationDecision(
            action=EnforcementAction.BLOCK,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="blocked by fake validation runtime",
                event_id=event.event_id,
                validator_name="FakeValidationRuntimeBlock",
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )


class FakeGateReject:
    def admit(self, event, expected_current_version):
        return AdmissionResult(
            verdict=AdmissionVerdict.REJECTED,
            reason="rejected by fake gate",
            event_id=event.event_id,
        )


class TestRegistryHelpers:
    def test_rehydrate_aggregate_from_history(self, empty_store, created_event, paid_event):
        from src.storage.idempotency_store import IdempotencyProvider
        from src.pipeline.transactional.registry import OrderRegistry

        empty_store.append(created_event, expected_current_version=0)
        empty_store.append(paid_event, expected_current_version=1)

        registry = OrderRegistry(
            store=empty_store,
            idem=IdempotencyProvider(),
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        aggregate, history = registry._rehydrate_aggregate("order-123")

        assert len(history) == 2
        assert aggregate.status.name == "PAID"
        assert aggregate.total_amount == Decimal("100.00")
        assert aggregate.paid_amount == Decimal("100.00")
        assert aggregate.current_version == 2

    def test_build_validation_context_uses_rehydrated_aggregate_state(self, empty_store, created_event):
        from src.storage.idempotency_store import IdempotencyProvider
        from src.pipeline.transactional.registry import OrderRegistry

        empty_store.append(created_event, expected_current_version=0)

        registry = OrderRegistry(
            store=empty_store,
            idem=IdempotencyProvider(),
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        aggregate, history = registry._rehydrate_aggregate("order-123")
        actual_prev_event = history[-1]
        context = registry._build_validation_context(aggregate, actual_prev_event)

        assert context.actual_prev_event == created_event
        assert context.actual_prev_version == 1
        assert context.actual_prev_status.name == "CREATED"


class TestHandleCreate:
    def test_handle_create_success(self, empty_store, empty_idempotency_provider):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        result = registry.handle_create("create-001", "order-123", Decimal("100.00"))

        assert result.request_id == "create-001"
        assert result.order_id == "order-123"
        assert result.sequence == 1
        assert result.amount == Decimal("100.00")

        history = empty_store.load("order-123")
        assert len(history) == 1
        assert history[0] == result

    def test_handle_create_same_request_same_payload_replays_prior_event(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        first = registry.handle_create("create-001", "order-123", Decimal("100.00"))
        second = registry.handle_create("create-001", "order-123", Decimal("100.00"))

        assert second == first
        history = empty_store.load("order-123")
        assert len(history) == 1

    def test_handle_create_same_request_different_payload_conflicts(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        conflict = registry.handle_create("create-001", "order-123", Decimal("10.00"))

        assert conflict.verdict == IdempotencyVerdict.CONFLICT
        history = empty_store.load("order-123")
        assert len(history) == 1

    def test_handle_create_validation_block_stops_before_persistence(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeBlock(),
            gate=OptimisticVersionGate(empty_store),
        )

        result = registry.handle_create("create-001", "order-123", Decimal("100.00"))

        assert result.action == EnforcementAction.BLOCK
        assert empty_store.load("order-123") == []

    def test_handle_create_gate_reject_stops_before_idempotency_record(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry
        from src.core.order.enums import CommandType
        from src.storage.idempotency_store import RequestSignature

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=FakeGateReject(),
        )

        result = registry.handle_create("create-001", "order-123", Decimal("100.00"))

        assert result.verdict == AdmissionVerdict.REJECTED
        assert empty_store.load("order-123") == []

        decision = empty_idempotency_provider.check(
            RequestSignature(
                request_id="create-001",
                command_type=CommandType.CREATE,
                order_id="order-123",
                amount=Decimal("100.00"),
            )
        )
        assert decision.verdict == IdempotencyVerdict.MISS


class TestHandlePay:
    def test_handle_pay_success_after_create(self, empty_store, empty_idempotency_provider):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        created = registry.handle_create("create-001", "order-123", Decimal("100.00"))
        paid = registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        assert created.sequence == 1
        assert paid.sequence == 2
        assert paid.amount == Decimal("100.00")

        history = empty_store.load("order-123")
        assert len(history) == 2
        assert history[1] == paid

    def test_handle_pay_same_request_same_payload_replays_prior_event(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        first = registry.handle_pay("pay-001", "order-123", Decimal("100.00"))
        second = registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        assert second == first
        history = empty_store.load("order-123")
        assert len(history) == 2

    def test_handle_pay_same_request_different_payload_conflicts(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        conflict = registry.handle_pay("pay-001", "order-123", Decimal("10.00"))

        assert conflict.verdict == IdempotencyVerdict.CONFLICT

    def test_handle_pay_different_request_after_paid_raises_aggregate_error(
        self,
        empty_store,
        empty_idempotency_provider,
    ):
        from src.pipeline.transactional.registry import OrderRegistry

        registry = OrderRegistry(
            store=empty_store,
            idem=empty_idempotency_provider,
            validation_runtime=FakeValidationRuntimeAllow(),
            gate=OptimisticVersionGate(empty_store),
        )

        registry.handle_create("create-001", "order-123", Decimal("100.00"))
        registry.handle_pay("pay-001", "order-123", Decimal("100.00"))

        with pytest.raises(ValueError, match="Order is already paid"):
            registry.handle_pay("pay-002", "order-123", Decimal("100.00"))