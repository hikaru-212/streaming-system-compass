from decimal import Decimal

from src.compass.transition.validators import FullProofValidator
from src.compass.transition.types import ValidationContext, ValidationVerdict
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestPrevVersionMismatchCases:
    def test_paid_candidate_with_wrong_prev_version_should_fail(self, created_event):
        """
        Semantic failure class:
        - candidate claims the wrong predecessor version
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=999,  # deliberate mismatch
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
        assert "prev_version" in result.reason or "Proof mismatch" in result.reason

    def test_created_candidate_with_nonzero_prev_version_on_empty_history_should_fail(self):
        """
        Semantic failure class:
        - empty history implies predecessor version 0
        - candidate falsely claims otherwise
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.INIT,
                prev_version=5,   # deliberate mismatch
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
        assert "prev_version" in result.reason or "Proof mismatch" in result.reason