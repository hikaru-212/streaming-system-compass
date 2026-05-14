from decimal import Decimal
import pytest

from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.compass.transition.types import (
    ValidationContext,
    ValidationMode,
    ValidationVerdict,
)
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestNoOpValidator:
    def test_noop_validator_returns_skipped(self, created_event):
        validator = NoOpValidator()
        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(created_event, context)

        assert result.verdict == ValidationVerdict.SKIPPED
        assert result.validation_mode == ValidationMode.OFF
        assert result.logic_validation_time_ms == 0.0
        assert result.io_time_ms == 0.0
        assert result.total_time_ms >= 0.0


class TestFullProofValidatorSuccess:
    def test_validate_created_from_empty_history_passes(self, created_event):
        validator = FullProofValidator()
        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(created_event, context)

        assert result.verdict == ValidationVerdict.PASSED
        assert result.validation_mode == ValidationMode.STRICT
        assert result.event_id == created_event.event_id
        assert result.logic_validation_time_ms >= 0.0
        assert result.io_time_ms == 0.0
        assert result.total_time_ms >= result.logic_validation_time_ms

    def test_validate_paid_after_created_passes(self, created_event, paid_event):
        validator = FullProofValidator()
        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(paid_event, context)

        assert result.verdict == ValidationVerdict.PASSED
        assert result.validation_mode == ValidationMode.STRICT
        assert result.event_id == paid_event.event_id


class TestFullProofValidatorFailures:
    def test_wrong_sequence_fails(self, created_event):
        validator = FullProofValidator()

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

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "Sequence violation" in result.reason

    def test_wrong_prev_event_id_fails(self, created_event):
        validator = FullProofValidator()

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id="wrong-event-id",
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "Predecessor mismatch" in result.reason

    def test_wrong_prev_version_fails(self, created_event):
        validator = FullProofValidator()

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=999,
                prev_event_id=created_event.event_id,
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_version" in result.reason or "Proof mismatch" in result.reason

    def test_wrong_claimed_prev_status_for_created_fails(self):
        validator = FullProofValidator()

        broken_event = OrderEvent.create(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,   # 故意錯
                prev_version=0,
                prev_event_id=None,
            ),
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason

    def test_wrong_claimed_prev_status_for_paid_fails(self, created_event):
        validator = FullProofValidator()

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.INIT,   # 故意錯
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason

    def test_actual_history_mismatch_for_paid_fails(self):
        validator = FullProofValidator()

        broken_event = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=0,
                prev_event_id=None,
            ),
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(broken_event, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason