"""Process-local, fail-fast admission for explicitly shared writer work.

This module owns execution capacity only. It has no database, semantic-result,
transaction, retry, or invocation-authority dependency.
"""

from collections.abc import Callable
from threading import BoundedSemaphore
from typing import TypeVar


_T = TypeVar("_T")


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

        Observation seam:
            An experiment adapter may override run and delegate exactly once to
            super().run with an operation wrapper. Wrapper entry/exit bracket
            admitted writer work; outer return/raise occurs after release (or
            refusal without acquisition). Observers must preserve the original
            value/exception and must not invoke the operation outside admission.
            No production timestamps, observers, or evidence are allocated here.
        """
        if not self._permits.acquire(blocking=False):
            raise WriterCapacityRefused("writer capacity unavailable")
        try:
            return operation()
        finally:
            self._permits.release()
