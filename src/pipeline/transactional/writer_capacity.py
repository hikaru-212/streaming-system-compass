"""Process-local, fail-fast admission for explicitly shared writer work.

This module owns execution capacity only. It has no database, semantic-result,
transaction, retry, or invocation-authority dependency.
"""

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from threading import BoundedSemaphore, Lock, get_ident
from time import monotonic_ns
from typing import TypeVar
from uuid import UUID


_T = TypeVar("_T")


@dataclass(frozen=True)
class WriterAttemptIdentity:
    """Correlate observation with one owner's logical invocation and attempt."""

    logical_invocation_id: UUID
    request_id: str
    attempt_number: int


class WriterCapacityEventKind(Enum):
    """Source boundaries, independent of retry eligibility and writer outcome."""

    CALL_STARTED = "call_started"
    REFUSED = "refused"
    BODY_ENTERED = "body_entered"
    BODY_EXITED = "body_exited"
    RELEASED = "released"
    CALL_COMPLETED = "call_completed"


@dataclass(frozen=True)
class WriterCapacityObservation:
    """A clocked boundary; RELEASED follows release, even on writer failure."""

    identity: WriterAttemptIdentity
    kind: WriterCapacityEventKind
    observed_ns: int
    thread_id: int


@dataclass(frozen=True)
class WriterCapacityObservationFailure:
    """Missing boundary evidence; never an admission fact or retry permission."""

    identity: WriterAttemptIdentity
    kind: WriterCapacityEventKind
    exception_class: str
    thread_id: int


class WriterCapacityObserver:
    """Retain optional boundary evidence without participating in admission.

    The composing caller owns retention and should use one recorder per bounded
    observation population. Clock failures, invalid readings and regressions
    produce separate failure records, never fabricated timestamps. No business
    callbacks are supported. The injected clock must be observation-only.
    """

    def __init__(self, *, clock_ns: Callable[[], int] = monotonic_ns) -> None:
        """Validate the clock without reading it or performing I/O."""
        if not callable(clock_ns):
            raise TypeError("clock_ns must be callable")
        self._clock = clock_ns
        self._lock = Lock()
        self._events: list[WriterCapacityObservation] = []
        self._failures: list[WriterCapacityObservationFailure] = []
        self._last_ns: int | None = None

    @property
    def observations(self) -> tuple[WriterCapacityObservation, ...]:
        """Return a thread-safe immutable snapshot of successful observations."""
        with self._lock:
            return tuple(self._events)

    @property
    def failures(self) -> tuple[WriterCapacityObservationFailure, ...]:
        """Return missing-boundary diagnoses without provider messages."""
        with self._lock:
            return tuple(self._failures)

    def _record(self, identity: WriterAttemptIdentity, kind: WriterCapacityEventKind) -> None:
        # This try owns observation only. In particular, it never encloses the
        # protected operation. Even a same-typed refusal from the clock cannot
        # reach the request owner's private refusal-provenance view.
        with self._lock:
            try:
                now = self._clock()
                if type(now) is not int or now < 0:
                    raise ValueError("observation clock must return nonnegative integer ns")
                if self._last_ns is not None and now < self._last_ns:
                    raise ValueError("observation clock regressed")
                self._last_ns = now
                self._events.append(WriterCapacityObservation(identity, kind, now, get_ident()))
            except Exception as error:
                self._failures.append(WriterCapacityObservationFailure(
                    identity, kind, type(error).__name__, get_ident(),
                ))


# Context-local binding is restored after each synchronous attempt. It neither
# adds a gate wrapper nor shares a mutable 'current request' across threads.
_OBSERVATION: ContextVar[tuple[object, WriterAttemptIdentity, WriterCapacityObserver] | None] = (
    ContextVar("writer_capacity_observation", default=None)
)


class WriterCapacityRefused(Exception):
    """No capacity was acquired; the supplied writer operation was not called.

    This exception carries no producer result, semantic/concurrency verdict,
    acknowledgement, retryability, or reinvocation/replanning authorization.
    It does not imply anything about a caller's pre-existing transaction state.
    """


class BoundedWriterAdmission:
    """Bound synchronous operations sharing this exact process-local object.

    The composing caller owns one instance for its writer population and passes
    it to each writer. Independent instances establish independent budgets, not
    a combined limit. Connections retain their existing exclusive ownership.

    No capacity waiting, request queue, fairness, timeout, rate policy, or
    distributed coordination is provided. There is no default numerical bound.
    """

    def __init__(self, bound: int) -> None:
        """Create an explicit positive-integer budget without acquiring capacity.

        Booleans and non-integers raise TypeError; zero and negative integers
        raise ValueError. Construction performs no I/O or dependency creation.
        """
        if type(bound) is not int:
            raise TypeError("bound must be an integer")
        if bound <= 0:
            raise ValueError("bound must be positive")
        self._bound = bound
        self._permits = BoundedSemaphore(bound)

    @property
    def bound(self) -> int:
        """Return the configured bound; this is configuration, not live occupancy."""
        return self._bound

    @contextmanager
    def observe_attempt(self, identity: WriterAttemptIdentity, observer: WriterCapacityObserver):
        """Bind optional observation to this gate in the current execution context.

        The synchronous owner supplies exact identity before its public writer
        call. Nested bindings restore their predecessor. Only the concrete
        recorder is accepted; no observer controls acquisition or invocation.
        Configuration errors occur before writer execution. This binding creates
        no retry permission and is not required for ordinary unobserved calls.
        """
        if type(identity) is not WriterAttemptIdentity or type(observer) is not WriterCapacityObserver:
            raise TypeError("observation requires concrete identity and observer")
        token = _OBSERVATION.set((self, identity, observer))
        try:
            yield
        finally:
            _OBSERVATION.reset(token)

    def run(self, operation: Callable[[], _T]) -> _T:
        """Admit once, call once, and release before returning or propagating.

        Args:
            operation: Synchronous protected writer call with its inputs bound.
                It must complete its work before returning, not launch detached
                work or return an awaitable whose execution outlives this call.

        Returns:
            The identical operation result, without interpretation or wrapping.

        Raises:
            WriterCapacityRefused: No slot was available; operation was not run.
            Exception: Operation exceptions propagate unchanged after release.

        The finally block owns release on every Python unwinding path, including
        process-level exceptions without translating them. Process termination
        and asynchronous work are outside this synchronous lifetime guarantee.

        Optional observation brackets the body and reports release before call
        completion. Observation failures are retained separately by the concrete
        recorder and cannot replace the result/error or issue a refusal. Without
        a binding, no observation clock reads or evidence allocations occur.
        """
        observation = _OBSERVATION.get()
        if observation is not None and observation[0] is not self:
            observation = None
        if observation is None:
            if not self._permits.acquire(blocking=False):
                raise WriterCapacityRefused("writer capacity unavailable")
            try:
                return operation()
            finally:
                self._permits.release()

        def record(kind: WriterCapacityEventKind) -> None:
            observation[2]._record(observation[1], kind)

        record(WriterCapacityEventKind.CALL_STARTED)
        try:
            if not self._permits.acquire(blocking=False):
                record(WriterCapacityEventKind.REFUSED)
                raise WriterCapacityRefused("writer capacity unavailable")
            try:
                record(WriterCapacityEventKind.BODY_ENTERED)
                try:
                    return operation()
                finally:
                    record(WriterCapacityEventKind.BODY_EXITED)
            finally:
                self._permits.release()
                record(WriterCapacityEventKind.RELEASED)
        finally:
            record(WriterCapacityEventKind.CALL_COMPLETED)
