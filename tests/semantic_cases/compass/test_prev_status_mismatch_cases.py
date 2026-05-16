from decimal import Decimal

from src.compass.transition.validators import FullProofValidator
from src.compass.transition.types import ValidationContext, ValidationVerdict
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestPrevStatusMismatchCases:
    def test_created_candidate_claiming_created_as_prev_status_should_fail(self):
        """
        Semantic failure class:
        - CREATED must truthfully follow INIT in the current v1 world
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,  # deliberate mismatch
                prev_version=0,
                prev_event_id=None,
            ),
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(broken_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason

    def test_paid_candidate_claiming_init_as_prev_status_should_fail(self, created_event):
        """
        Semantic failure class:
        - PAID must truthfully follow CREATED in the current v1 world
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.INIT,  # deliberate mismatch
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(broken_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason

    def test_paid_candidate_against_actual_init_history_should_fail(self):
        """
        Semantic failure class:
        - actual accepted history says INIT
        - candidate pretends to be a valid PAID successor
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
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

        result = validator.validate(broken_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_status" in result.reason or "actual history" in result.reason