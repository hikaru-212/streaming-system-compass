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
    - Stage 4 SemanticOutcome / RuntimeDecision
    """

    ADMITTED = "ADMITTED"
    STALE_WRITE = "STALE_WRITE"
    LOCK_TIMEOUT = "LOCK_TIMEOUT"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"


@dataclass(frozen=True)
class AdmissionResult:
    """
    Result of the persistence admission boundary.

    AdmissionResult answers whether a candidate event was allowed to occupy the
    next accepted-history position.

    It is intentionally not a Stage 4 SemanticOutcome.
    """

    verdict: AdmissionVerdict
    reason: str
    candidate_event_id: str
    accepted_event_id: str | None = None

    @property
    def admitted(self) -> bool:
        return self.verdict == AdmissionVerdict.ADMITTED


@runtime_checkable
class ConcurrencyGate(Protocol):
    """
    Structural contract for the persistence admission boundary.

    The caller depends only on:
    - candidate event
    - expected current version
    - admission result

    Concrete strategies may differ:
    - optimistic version gate
    - pessimistic lock-based gate
    - test fake gate

    This protocol may later be renamed to AdmissionGate once the PostgreSQL
    admission boundary is fully established.
    """

    def admit(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        ...


class OptimisticVersionGate:
    """
    Version-based optimistic admission strategy for the in-memory baseline.

    Strategy:
    - do not lock first
    - rely on append-time continuity check in EventStore
    - reject stale writers when store version no longer matches expectation

    PostgreSQL-specific gates should translate storage conflicts into stable
    AdmissionResult values instead of leaking raw database exceptions upward.
    """

    def __init__(self, store: EventStore):
        self.store = store

    def admit(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        try:
            self.store.append(candidate_event, expected_current_version)
        except ValueError as exc:
            return AdmissionResult(
                verdict=AdmissionVerdict.STALE_WRITE,
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