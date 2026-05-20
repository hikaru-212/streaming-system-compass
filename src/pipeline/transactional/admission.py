from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from src.core.order.events import OrderEvent
from src.storage.event_store import EventStore


class AdmissionVerdict(Enum):
    """
    Persistence admission result.

    This is intentionally separate from:
    - domain legality
    - validation truth
    - idempotency replay classification
    """
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass
class AdmissionResult:
    """
    Result of the persistence admission boundary.
    """
    verdict: AdmissionVerdict
    reason: str
    candidate_event_id: str
    accepted_event_id: str | None


@runtime_checkable
class ConcurrencyGate(Protocol):
    """
    Structural contract for the persistence admission boundary.

    Registry depends only on this contract:
    - candidate event
    - expected current version
    - admission result

    Concrete strategies may differ:
    - optimistic version gate
    - pessimistic lock-based gate
    - test fake gate
    """
    def admit(self, candidate_event: OrderEvent, expected_current_version: int) -> AdmissionResult:
        ...


class OptimisticVersionGate:
    """
    Version-based optimistic admission strategy.

    Strategy:
    - do not lock first
    - rely on append-time continuity check in EventStore
    - reject stale writers when store version no longer matches expectation
    """

    def __init__(self, store: EventStore):
        self.store = store

    def admit(self, candidate_event: OrderEvent, expected_current_version: int) -> AdmissionResult:
        try:
            self.store.append(candidate_event, expected_current_version)
        except ValueError as exc:
            return AdmissionResult(
                verdict=AdmissionVerdict.REJECTED,
                reason=f"Admission rejected by optimistic version gate: {exc}",
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )

        return AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Event admitted by optimistic version gate",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=candidate_event.event_id,
        )