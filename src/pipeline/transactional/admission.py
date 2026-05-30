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
class StreamAdmissionResult:
    """
    Result of the stream-preparation boundary.

    StreamAdmissionResult answers whether a writer may enter the critical
    section for one aggregate stream before accepted-history loading,
    aggregate rehydration, candidate-event creation, and validation.

    It does not refer to a candidate event because candidate_event does not
    exist yet at this phase.
    """

    verdict: AdmissionVerdict
    reason: str
    order_id: str

    @property
    def admitted(self) -> bool:
        return self.verdict == AdmissionVerdict.ADMITTED


@dataclass(frozen=True)
class AdmissionResult:
    """
    Result of the append-time persistence admission boundary.

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
    - stream preparation result
    - candidate event
    - expected current version
    - append-time admission result

    Concrete strategies may differ:
    - optimistic version gate
    - pessimistic lock-based gate
    - test fake gate

    Two-phase admission exists because optimistic and pessimistic strategies
    need different lock timing:

    - optimistic admission usually performs no stream preparation
    - pessimistic admission may acquire a stream lock before rehydration /
      validation work begins
    """

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        ...

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
    - use prepare_stream as a no-op
    - rely on append-time continuity check in EventStore
    - reject stale writers when store version no longer matches expectation

    PostgreSQL-specific gates should translate storage conflicts into stable
    AdmissionResult values instead of leaking raw database exceptions upward.
    """

    def __init__(self, store: EventStore):
        self.store = store

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Optimistic admission does not pre-lock stream",
            order_id=order_id,
        )

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
