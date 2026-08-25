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
class AppendVersionMismatchEvidence:
    """Retain one append-time expected/current version inequality.

    Args:
        expected_current_version: Version supplied to append admission.
        observed_current_version: Authoritative version observed by storage.

    This record contains only physical append evidence. It does not identify a
    stream, classify retryability or recovery, interpret semantic meaning, or
    authorize another invocation or any execution.

    Raises:
        TypeError: If either version is not an exact integer.
        ValueError: If either version is negative or the versions are equal.
    """

    expected_current_version: int
    observed_current_version: int

    def __post_init__(self) -> None:
        if type(self.expected_current_version) is not int:
            raise TypeError("expected_current_version must be int")
        if type(self.observed_current_version) is not int:
            raise TypeError("observed_current_version must be int")
        if self.expected_current_version < 0:
            raise ValueError("expected_current_version must be non-negative")
        if self.observed_current_version < 0:
            raise ValueError("observed_current_version must be non-negative")
        if self.expected_current_version == self.observed_current_version:
            raise ValueError(
                "expected_current_version and observed_current_version "
                "must differ"
            )


@dataclass(frozen=True)
class StreamAdmissionResult:
    """
    Stream-level preparation evidence from ConcurrencyGate.prepare_stream(...).

    Responsibility:
    - record the preparation verdict, reason, and aggregate-stream identity

    Important invariant:
    - orchestration placement determines when preparation occurs
    - IN_TRANSACTION may prepare before candidate construction
    - PRE_TRANSACTION may prepare after candidate construction and an allowing
      validation decision
    - this result proves neither candidate existence nor invocation of
      append_if_admitted(...)

    Explicit non-goals:
    - it is distinct from candidate-level AdmissionResult
    - it is not event-append success or transaction-commit evidence
    """

    verdict: AdmissionVerdict
    reason: str
    order_id: str

    @property
    def admitted(self) -> bool:
        return self.verdict == AdmissionVerdict.ADMITTED


@dataclass(frozen=True)
class AdmissionResult:
    """Result of the append-time persistence admission boundary.

    Args:
        verdict: Existing append-admission technical outcome.
        reason: Human-readable diagnostic description.
        candidate_event_id: Identity of the candidate presented for append.
        accepted_event_id: Accepted identity when append admission succeeded.
        append_version_mismatch_evidence: Optional physical version inequality
            retained only for its characterized append source.

    AdmissionResult answers whether a candidate event was allowed to occupy the
    next accepted-history position. Version-mismatch evidence is ordinary
    retained structure and participates in equality, hashing, and
    representation. Those structural operations do not define semantic
    equivalence or re-invocation authority.

    It is intentionally not a Stage 4 SemanticOutcome.

    Raises:
        TypeError: If non-``None`` version evidence has the wrong type.
        ValueError: If version evidence accompanies a non-stale verdict, an
            accepted event, or no candidate identity.
    """

    verdict: AdmissionVerdict
    reason: str
    candidate_event_id: str
    accepted_event_id: str | None = None
    append_version_mismatch_evidence: (
        AppendVersionMismatchEvidence | None
    ) = None

    def __post_init__(self) -> None:
        """Validate coherence only when version-mismatch evidence is present."""

        evidence = self.append_version_mismatch_evidence
        if evidence is None:
            return
        if not isinstance(evidence, AppendVersionMismatchEvidence):
            raise TypeError(
                "append_version_mismatch_evidence must be "
                "AppendVersionMismatchEvidence or None"
            )
        if self.verdict is not AdmissionVerdict.STALE_WRITE:
            raise ValueError(
                "append_version_mismatch_evidence requires STALE_WRITE verdict"
            )
        if self.accepted_event_id is not None:
            raise ValueError(
                "append_version_mismatch_evidence requires no accepted_event_id"
            )
        if self.candidate_event_id is None:
            raise ValueError(
                "append_version_mismatch_evidence requires candidate_event_id"
            )

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

    def append_if_admitted(
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

    def append_if_admitted(
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
