from dataclasses import dataclass
from decimal import Decimal
import time
import uuid


from src.core.common.money import normalize_money

from .enums import EventType
from .proofs import Proof


@dataclass(frozen=True)
class OrderEvent:
    """
    Immutable event-shaped data for the order stream.

    Important boundary:
    - this class materializes event data
    - it does NOT decide domain legality
    - it does NOT decide next sequence
    - it does NOT validate truth against accepted history
    - it does NOT decide whether the event has become accepted history

    Identity lifecycle:
    - event_id is assigned when an event-shaped candidate is created.
    - before append, this value should be interpreted as candidate_event_id.
    - after successful append to the event log, the same value may be referenced as accepted_event_id.
    - event_id alone does not imply accepted history.
    - only presence in the event log grants accepted-event status.

    Those responsibilities live in:
    - aggregate -> command legality / sequence / proof generation
    - Compass Layer 1 -> truth validation
    - admission gate -> append-time continuity protection
    - event store -> accepted-history membership
    """
    event_id: str
    request_id: str
    order_id: str
    sequence: int
    event_type: EventType
    amount: Decimal
    occurred_at_ms: int
    proof: Proof

    @staticmethod
    def create(
        request_id: str,
        order_id: str,
        sequence: int,
        event_type: EventType,
        amount: Decimal,
        proof: Proof,
    ) -> "OrderEvent":
        """
        Event factory.

        Why keep this small:
        - event creation should stay a materialization step
        - business legality should remain in aggregate methods
        - sequence truth should not be decided by external callers
        """
        return OrderEvent(
            event_id=uuid.uuid4().hex,
            request_id=request_id,
            order_id=order_id,
            sequence=sequence,
            event_type=event_type,
            amount=normalize_money(amount),
            occurred_at_ms=int(time.time() * 1000),
            proof=proof,
        )