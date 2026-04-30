from src.compass.transition.validators import FullProofValidator
from src.compass.transition.types import ValidationContext, ValidationVerdict
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class TestPredecessorMismatchCases:
    def test_paid_candidate_with_wrong_prev_event_id_should_fail(self, created_event):
        """
        Semantic failure class:
        - candidate claims the wrong predecessor identity

        Why this matters:
        - sequence may still look plausible
        - status claim may still look plausible
        - but the candidate is not truthfully anchored to accepted history
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="pay-001",
            order_id="order-123",
            sequence=2,
            event_type=EventType.PAID,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.CREATED,
                prev_version=1,
                prev_event_id="wrong-prev-event-id",  # deliberate mismatch
            ),
        )

        context = ValidationContext(
            actual_prev_event=created_event,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

        result = validator.validate(broken_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_event_id" in result.reason or "Predecessor mismatch" in result.reason

    def test_created_candidate_claiming_non_none_prev_event_id_should_fail(self):
        """
        Semantic failure class:
        - empty history should imply no predecessor event
        - candidate falsely claims one exists
        """
        validator = FullProofValidator()

        broken_candidate = OrderEvent.create(
            request_id="create-001",
            order_id="order-123",
            sequence=1,
            event_type=EventType.CREATED,
            amount=100.0,
            proof=Proof(
                prev_status=OrderStatus.INIT,
                prev_version=0,
                prev_event_id="fake-prev-id",  # deliberate mismatch
            ),
        )

        context = ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

        result = validator.validate(broken_candidate, context)

        assert result.verdict == ValidationVerdict.FAILED
        assert "prev_event_id" in result.reason or "Predecessor mismatch" in result.reason