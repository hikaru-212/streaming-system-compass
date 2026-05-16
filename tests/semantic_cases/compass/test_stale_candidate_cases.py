from decimal import Decimal

from src.compass.transition.validators import FullProofValidator
from src.compass.transition.types import ValidationContext, ValidationVerdict
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestStaleCandidateCases:
    def test_candidate_with_stale_sequence_should_fail(self, created_event):
        """
        Semantic failure class:
        - accepted history is already at version 1
        - candidate does not advance correctly to version 2
        """
        validator = FullProofValidator()

        stale_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=1,  # stale
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(stale_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "Sequence violation" in result.reason

    def test_candidate_with_future_sequence_gap_should_fail(self, created_event):
        """
        Semantic failure class:
        - candidate jumps ahead and leaves a gap in the accepted history
        """
        validator = FullProofValidator()

        future_gap_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=99,  # deliberate gap
            event_type=EventType.PAID,
            amount=Decimal("100.00"),
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id=created_event.event_id,
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(future_gap_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "Sequence violation" in result.reason