from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict

from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent


@dataclass(frozen=True)
class RequestSignature:
    """
    Semantic identity of one request.

    Why this exists:
    - same request_id is not enough by itself
    - replay is safe only when the retried payload is semantically identical
    - if the same request_id is reused with a different payload,
      the system must reject as idempotency conflict
    """
    request_id: str
    command_type: CommandType
    order_id: str
    amount: float


@dataclass(frozen=True)
class IdempotencyRecord:
    """
    Stored replay memory for one request that successfully produced an accepted event.

    This record binds:
    - the semantic request signature
    - the event that became accepted history

    It must not be created for rejected candidate events.
    """
    signature: RequestSignature
    accepted_event: OrderEvent


class IdempotencyVerdict(Enum):
    """
    Request-level idempotency outcome.

    MISS:
    - no prior request with this request_id

    REPLAY:
    - same request_id and same semantic payload

    CONFLICT:
    - same request_id reused with different semantic payload
    """
    MISS = "miss"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class IdempotencyDecision:
    """
    Result returned by idempotency lookup.

    Important boundary:
    - this is NOT domain legality
    - this is NOT semantic truth validation
    - this is request replay / conflict classification
    """
    verdict: IdempotencyVerdict
    reason: str
    record: Optional[IdempotencyRecord] = None


class IdempotencyProvider:
    """
    In-memory request replay store.

    Responsibility:
    - remember previously accepted request signatures
    - replay semantically identical retries
    - reject request_id reuse with different payload

    Does NOT own:
    - domain legality
    - append-time concurrency admission
    - proof truth against accepted history
    """

    def __init__(self):
        self.records_by_request_id: Dict[str, IdempotencyRecord] = {}

    def check(self, signature: RequestSignature) -> IdempotencyDecision:
        """
        Classify incoming request against prior request memory.
        """
        existing = self.records_by_request_id.get(signature.request_id)

        if existing is None:
            return IdempotencyDecision(
                verdict=IdempotencyVerdict.MISS,
                reason="No prior request with this request_id",
            )

        if existing.signature == signature:
            return IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="Semantically identical retry detected",
                record=existing,
            )

        return IdempotencyDecision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=existing,
        )

    def record(self, signature: RequestSignature, accepted_event: OrderEvent) -> None:
        """
        Persist replay memory only after the request has produced an accepted event.

        Important sequencing rule:
        - do NOT record request memory before event admission succeeds
        - otherwise the system could remember a request that never actually became fact
        """
        self.records_by_request_id[signature.request_id] = IdempotencyRecord(
            signature=signature,
            accepted_event=accepted_event,
        )