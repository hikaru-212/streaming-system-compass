from typing import Optional

from .enums import EventType, OrderStatus
from .events import OrderEvent
from .proofs import Proof


class OrderAggregate:
    """
    Aggregate for the minimal v1 order write-side model.

    Aggregate owns:
    - domain legality
    - status transition legality
    - amount-related business legality
    - next sequence decision for candidate events
    - proof generation from current aggregate state

    Aggregate does NOT own:
    - idempotency replay policy
    - request dedup memory
    - transition-truth comparison against accepted history
    - append-time concurrency admission
    - persistence

    Single source of truth rule:
    - all aggregate state mutation must happen through apply(event)
    """

    def __init__(self, order_id: str):
        """
        v1 identity rule:
        - order_id identifies the aggregate / event stream
        - identity exists independently of current status
        - empty order_id is illegal
        """
        if not order_id or not order_id.strip():
            raise ValueError("order_id must not be empty")

        self.order_id = order_id
        self.current_version = 0
        self.status = OrderStatus.INIT
        self.total_amount = 0.0
        self.paid_amount = 0.0
        self.last_event_id: Optional[str] = None

    @staticmethod
    def _require_non_empty_request_id(request_id: str) -> None:
        """
        Request identity must be explicit.

        Why this belongs here:
        - the aggregate owns command-level business legality
        - empty request_id is not a valid business command input in v1
        """
        if not request_id or not request_id.strip():
            raise ValueError("request_id must not be empty")

    @staticmethod
    def _require_positive_amount(amount: float, field_name: str = "amount") -> None:
        """
        Positive-money rule for the current v1 model.

        Current v1 explicitly does NOT allow:
        - zero amount
        - negative amount
        """
        if amount <= 0:
            raise ValueError(f"{field_name} must be positive")

    def create(self, request_id: str, total_amount: float) -> OrderEvent:
        """
        Command legality for create.

        Invariants:
        - CREATED can only be produced from INIT
        - create request_id must not be empty
        - total_amount must be positive
        - CREATED.amount defines total_amount in v1
        """
        self._require_non_empty_request_id(request_id)
        self._require_positive_amount(total_amount, "total_amount")

        if self.status != OrderStatus.INIT:
            raise ValueError("Already created")

        next_version = self.current_version + 1

        # Proof must come from current aggregate state,
        # not from external caller input.
        proof = Proof(
            prev_status=self.status,
            prev_version=self.current_version,
            prev_event_id=self.last_event_id,
        )

        return OrderEvent.create(
            request_id=request_id,
            order_id=self.order_id,
            sequence=next_version,
            event_type=EventType.CREATED,
            amount=total_amount,
            proof=proof,
        )

    def pay(self, request_id: str, payment_amount: float) -> OrderEvent:
        """
        Command legality for pay.

        Invariants:
        - PAID can only be produced from CREATED
        - pay request_id must not be empty
        - payment_amount must be positive
        - in v1, PAID means full payment completion
        - therefore payment_amount must equal total_amount
        """
        self._require_non_empty_request_id(request_id)
        self._require_positive_amount(payment_amount, "payment_amount")

        if self.status == OrderStatus.PAID:
            raise ValueError("Order is already paid")
        elif self.status == OrderStatus.INIT:
            raise ValueError("Cannot pay before order is created")

        if payment_amount != self.total_amount:
            raise ValueError(
                f"v1 full-payment rule violated: pay amount must equal total_amount "
                f"(got {payment_amount}, expected {self.total_amount})"
            )

        next_version = self.current_version + 1

        proof = Proof(
            prev_status=self.status,
            prev_version=self.current_version,
            prev_event_id=self.last_event_id,
        )

        return OrderEvent.create(
            request_id=request_id,
            order_id=self.order_id,
            sequence=next_version,
            event_type=EventType.PAID,
            amount=payment_amount,
            proof=proof,
        )

    def apply(self, event: OrderEvent) -> None:
        """
        Single source of truth for aggregate state mutation.

        Used by:
        - replay of accepted history
        - local application of a newly admitted event

        Important separation:
        - command legality happens before event creation
        - apply(event) assumes the event is already accepted / trusted
        - apply(event) must NOT re-run command-level legality checks

        v1 event/state alignment:
        - CREATED.amount sets total_amount
        - PAID.amount sets paid_amount
        - PAID does NOT introduce accumulation semantics in v1
        """
        if event.order_id != self.order_id:
            raise ValueError(
                f"Order id mismatch during apply: aggregate={self.order_id}, event={event.order_id}"
            )

        if event.sequence != self.current_version + 1:
            raise ValueError(
                f"Sequence discontinuity during apply: expected {self.current_version + 1}, got {event.sequence}"
            )

        if event.event_type == EventType.CREATED:
            self.status = OrderStatus.CREATED
            self.total_amount = event.amount

        elif event.event_type == EventType.PAID:
            self.status = OrderStatus.PAID
            self.paid_amount = event.amount

        self.current_version = event.sequence
        self.last_event_id = event.event_id