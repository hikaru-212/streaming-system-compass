"""Explicit capacity-refusal retry configuration; no deployment defaults."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class WriterRetryPolicy:
    """Configure a finite attempt ceiling and every intentional retry delay.

    ``max_attempts`` includes the initial attempt. ``retry_delays_seconds`` is
    an immutable tuple with exactly max_attempts - 1 positive finite floats.
    Entry zero precedes attempt two. Repeated or increasing values can express
    different schedules without selecting a fixed/exponential algorithm.

    Supplying this object explicitly enables capacity retry; supplying None to
    the request composition disables it. There are no numerical defaults.
    This configuration conveys no semantic or Stage 4E authority, performs no
    I/O, and holds no mutable budget shared between logical requests.
    """

    max_attempts: int
    retry_delays_seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        """Reject invalid or mutable configuration before writer execution."""
        if type(self.max_attempts) is not int:
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must include at least the initial attempt")
        if type(self.retry_delays_seconds) is not tuple:
            raise TypeError("retry_delays_seconds must be a tuple")
        if len(self.retry_delays_seconds) != self.max_attempts - 1:
            raise ValueError("supply exactly max_attempts - 1 retry delays")
        for delay in self.retry_delays_seconds:
            if type(delay) is not float:
                raise TypeError("each retry delay must be float seconds")
            if not isfinite(delay) or delay <= 0:
                raise ValueError("each retry delay must be positive and finite")

    def delay_before_retry(self, retry_index: int) -> float:
        """Return the delay for a one-based additional attempt; reject overflow.

        Index one precedes total attempt two. No delay or allowance is generated
        beyond the configured sequence. This lookup never spends budget.
        """
        if type(retry_index) is not int:
            raise TypeError("retry_index must be an integer")
        if not 1 <= retry_index < self.max_attempts:
            raise ValueError("retry_index is outside the configured budget")
        return self.retry_delays_seconds[retry_index - 1]

    @property
    def max_delay_seconds(self) -> float | None:
        """Return the configured maximum, or None when no retry is configured."""
        return max(self.retry_delays_seconds, default=None)
