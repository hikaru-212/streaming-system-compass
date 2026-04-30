from dataclasses import dataclass
import time
import uuid

from .enums import EventType
from .proofs import Proof


@dataclass(frozen=True)
class OrderEvent:
    """
    Immutable event fact for the order stream.

    Important boundary:
    - this class materializes event data
    - it does NOT decide domain legality
    - it does NOT decide next sequence
    - it does NOT validate truth against accepted history

    Those responsibilities live in:
    - aggregate -> command legality / sequence / proof generation
    - Compass Layer 1 -> truth validation
    - admission gate -> append-time continuity protection
    """
    event_id: str
    request_id: str
    order_id: str
    sequence: int
    event_type: EventType
    amount: float
    occurred_at_ms: int
    proof: Proof

    @staticmethod
    def create(
        request_id: str,
        order_id: str,
        sequence: int,
        event_type: EventType,
        amount: float,
        proof: Proof,
    ) -> "OrderEvent":
        """
        Event factory.

        Why keep this small:
        - event creation should stay a materialization step
        - business legality should remain in aggregate methods
        - sequence truth should not be decided by external callers

        Technical debt note:
        - amount currently uses float only as a skeleton-phase simplification
        - money should eventually use Decimal or smallest-unit integers
        """
        return OrderEvent(
            event_id=uuid.uuid4().hex,
            request_id=request_id,
            order_id=order_id,
            sequence=sequence,
            event_type=event_type,
            amount=amount,
            occurred_at_ms=int(time.time() * 1000),
            proof=proof,
        )