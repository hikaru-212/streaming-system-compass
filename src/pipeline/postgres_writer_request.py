"""Caller-owned capacity retry outside transactional and Stage 4E owners."""

from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from math import isfinite
from threading import Lock
from time import monotonic, sleep
from typing import TypeVar
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.compass.transition.runtime import ValidationRuntime
from src.core.order.enums import CommandType
from src.pipeline.transactional.postgres_write_side import (
    AdmissionGateFactory,
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import PostgresWriteSideConfig
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementDelivery
from src.pipeline.transactional.writer_capacity import (
    BoundedWriterAdmission,
    WriterAttemptIdentity,
    WriterCapacityObserver,
    WriterCapacityRefused,
)
from src.pipeline.writer_retry_policy import WriterRetryPolicy
from src.storage.idempotency_store import RequestSignature


_T = TypeVar("_T")


class WriterRetryEventKind(Enum):
    """Technical request/attempt observations, never semantic authority."""

    LOGICAL_STARTED = "logical_started"
    ATTEMPT_DISPATCHED = "attempt_dispatched"
    CAPACITY_REFUSED = "capacity_refused"
    ELIGIBILITY_DECIDED = "eligibility_decided"
    RETRY_SCHEDULED = "retry_scheduled"
    RETRY_READY = "retry_ready"
    TERMINAL_RESULT = "terminal_result"
    TERMINAL_FAILURE = "terminal_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class WriterRetryObservation:
    """Bounded in-memory evidence for one logical invocation and its attempts.

    ``attempt_number`` is the number of dispatched attempts, initially zero;
    it is also total budget spent. Scheduled/ready events refer to the refused
    attempt; the following dispatch increments it. Monotonic seconds describe
    scheduling and dispatch, not SQL timing. Only TERMINAL_RESULT has an outcome.
    Identity omits business payload and errors omit provider messages. No event
    issues authority, and no observer callback can change execution or results.
    """

    logical_invocation_id: UUID
    request_id: str
    kind: WriterRetryEventKind
    attempt_number: int
    pre_body_refusal: bool | None = None
    eligible: bool | None = None
    delay_seconds: float | None = None
    not_before: float | None = None
    observed_at: float | None = None
    outcome: PostgresWriteSideOutcome | None = None


class WriterCapacityRetryExhausted(Exception):
    """All configured attempts ended in verified pre-body capacity refusal.

    The final original refusal is retained and chained, with total attempts
    spent. This is neither a writer result nor a new eligible refusal. It has
    no semantic, acknowledgement, reconciliation, or Stage 4E meaning.
    """

    def __init__(
        self, attempts_spent: int, final_refusal: WriterCapacityRefused,
    ) -> None:
        """Retain exhaustion context without copying payload or provider text."""
        super().__init__("writer capacity retry budget exhausted")
        self.attempts_spent = attempts_spent
        self.final_refusal = final_refusal


@dataclass(frozen=True)
class WriterAttemptMeasurement:
    """Separate measured delivery after a normally returning public writer call.

    Refused/exceptional attempts have no delivery. UNAVAILABLE and individual
    NOT_COLLECTED phases retain the existing measurement contract, never zero.
    The delivery's producer_value is the same object returned by invoke().
    """

    identity: WriterAttemptIdentity
    delivery: PostgresWriteSideMeasurementDelivery


class WriterRetryCancelled(Exception):
    """Caller cancellation stopped dispatch; already spent budget is retained."""


class WriterRetryExpired(Exception):
    """The caller's monotonic dispatch deadline expired; no writer was aborted."""


class _AttemptAdmission(BoundedWriterAdmission):
    """Observe the unchanged shared gate without allocating another permit pool.

    Only a concrete BoundedWriterAdmission is accepted by enabled composition.
    Consequently pre-body provenance comes from its reviewed run implementation,
    not an arbitrary adapter's exception type. This private view is used by just
    one serial request owner; it never retries, waits, or translates an exception.
    """

    def __init__(self, shared: BoundedWriterAdmission) -> None:
        """Retain the reviewed gate; this view owns no independent permits."""
        self._shared = shared
        self.refusal: WriterCapacityRefused | None = None

    @property
    def bound(self) -> int:
        """Expose the shared configured bound without observing occupancy."""
        return self._shared.bound

    def run(self, operation: Callable[[], _T]) -> _T:
        """Delegate once, preserving the result/error and tracking body entry."""
        self.refusal = None
        entered = False

        def body() -> _T:
            nonlocal entered
            entered = True
            return operation()

        try:
            return self._shared.run(body)
        except WriterCapacityRefused as error:
            # The shared gate has returned/unwound. A same-typed body exception
            # is deliberately not recorded as an eligible boundary refusal.
            if not entered:
                self.refusal = error
            raise


class PostgresWriterRequest:
    """Own one direct CREATE/PAY request with optional serial capacity retry.

    This is a separate consumer of the public writer, outside Stage 4E. It keeps
    the exact immutable RequestSignature and a private concrete writer. The
    caller grants exclusive connection custody through invoke(), including
    waits, and must enter without caller-held locks or session advisory locks.
    Enabled retry verifies IDLE transaction status before dispatch and waiting;
    it never commits, rolls back, closes, or repairs the caller's connection.

    A short lock protects one-shot invocation and observation snapshots. It is
    never held across writer execution, clock/cancellation callbacks, or waiting.
    Reusing this owner raises RuntimeError even after failure. Callers must not
    reconstruct/nest owners to reset the same live request's finite budget.

    No Stage 4E handle, reinvocation API, receipt, semantic result, queue, shared
    rate allowance, or durable/restart lifecycle is created. Retained threads,
    connections and waiting callers are not bounded by this mechanism.
    """

    def __init__(
        self,
        *,
        request_signature: RequestSignature,
        business_connection: Connection,
        validation_runtime: ValidationRuntime,
        capacity_admission: BoundedWriterAdmission | None = None,
        retry_policy: WriterRetryPolicy | None = None,
        admission_gate_factory: AdmissionGateFactory | None = None,
        write_side_config: PostgresWriteSideConfig | None = None,
        wait: Callable[[float], None] = sleep,
        clock: Callable[[], float] = monotonic,
        cancelled: Callable[[], bool] | None = None,
        expires_at: float | None = None,
        capacity_observer: WriterCapacityObserver | None = None,
        measure_writer: bool = False,
    ) -> None:
        """Validate configuration and retain caller-owned synchronous resources.

        None policy preserves one public-writer call and its exact result/error,
        without clock, wait, or connection-state checks. Enabled policy requires
        the concrete shared gate; subclasses have unverified refusal provenance.
        Invalid structural inputs fail before execution; no connection is opened.

        ``wait`` takes seconds; ``clock`` must be finite and monotonic. Early
        wakes are rechecked. Cancellation is cooperative before/after waits and
        before dispatch; a caller can inject an interruptible waiter. Expiry
        caps waiting and dispatch, not a running writer. Neither can turn a
        returned writer result into a retry. Lifetime controls require a policy.
        Callback/wait failures propagate terminally and never authorize retry.

        Optional capacity observation uses the concrete gate's context-local
        identity binding. Optional measured calls reuse the existing writer
        instrumentation; measurements are delivered through a separate snapshot.
        Neither option changes eligibility, the primary result, or Stage 4E.
        """
        if type(request_signature) is not RequestSignature:
            raise TypeError("request_signature must be RequestSignature")
        if (type(request_signature.request_id) is not str
                or type(request_signature.order_id) is not str
                or type(request_signature.amount) is not Decimal):
            raise TypeError("request_signature must contain string IDs and Decimal amount")
        if request_signature.command_type not in (CommandType.CREATE, CommandType.PAY):
            raise ValueError("only CREATE and PAY are supported")
        if retry_policy is not None and type(retry_policy) is not WriterRetryPolicy:
            raise TypeError("retry_policy must be WriterRetryPolicy or None")
        if retry_policy is not None and type(capacity_admission) is not BoundedWriterAdmission:
            raise TypeError("enabled retry requires concrete BoundedWriterAdmission")
        if capacity_observer is not None:
            if type(capacity_observer) is not WriterCapacityObserver:
                raise TypeError("capacity_observer must be concrete WriterCapacityObserver")
            if type(capacity_admission) is not BoundedWriterAdmission:
                raise TypeError("observation requires concrete BoundedWriterAdmission")
        if type(measure_writer) is not bool:
            raise TypeError("measure_writer must be bool")
        if not callable(wait) or not callable(clock):
            raise TypeError("wait and clock must be callable")
        if cancelled is not None and not callable(cancelled):
            raise TypeError("cancelled must be callable or None")
        if expires_at is not None:
            if type(expires_at) is not float or not isfinite(expires_at):
                raise ValueError("expires_at must be finite monotonic float seconds")
        if retry_policy is None and (cancelled is not None or expires_at is not None):
            raise ValueError("retry lifetime controls require an explicit policy")

        self._signature = request_signature
        self._connection = business_connection
        self._policy = retry_policy
        self._capacity = capacity_admission
        self._capacity_observer = capacity_observer
        self._measure_writer = measure_writer
        self._measurements: list[WriterAttemptMeasurement] = []
        self._admission = (
            _AttemptAdmission(capacity_admission) if retry_policy is not None else None
        )
        self._writer = PostgresTransactionalWriteSide(
            connection=business_connection,
            validation_runtime=validation_runtime,
            admission_gate_factory=admission_gate_factory,
            config=write_side_config,
            capacity_admission=self._admission or capacity_admission,
        )
        self._wait = wait
        self._clock = clock
        self._cancelled = cancelled
        self._expires_at = expires_at
        self._last_time: float | None = None
        self._lock = Lock()
        self._started = False
        self._attempts = 0
        self._logical_id = uuid4()
        self._events: list[WriterRetryObservation] = []

    @property
    def observations(self) -> tuple[WriterRetryObservation, ...]:
        """Return an immutable snapshot, bounded by this request's finite budget.

        No persistence, callbacks, payload logging or SQL observation is provided.
        The caller may retain/export these technical events under its own policy.
        """
        with self._lock:
            return tuple(self._events)

    @property
    def measurements(self) -> tuple[WriterAttemptMeasurement, ...]:
        """Return separate normal-return deliveries; absence is not zero timing.

        A single-use request can deliver at most one normal terminal measurement.
        Native exceptions and pre-body refusals provide no measured delivery.
        Availability and phase completeness remain independently inspectable.
        """
        with self._lock:
            return tuple(self._measurements)

    def invoke(self) -> PostgresWriteSideResult:
        """Execute this logical request once, returning the identical writer result.

        Only configured, observed pre-body capacity refusals can continue. All
        normal results and other exceptions are terminal. Exhaustion chains the
        final refusal in WriterCapacityRetryExhausted. Cancellation/expiry and
        wait/clock/resource failures are terminal without resetting this owner.
        The owner holds no lifecycle lock, permit or transaction across waits.
        """
        with self._lock:
            if self._started:
                raise RuntimeError("logical writer request has already started")
            self._started = True
        self._record(WriterRetryEventKind.LOGICAL_STARTED)
        try:
            return self._execute()
        except BaseException:
            # No callback/clock/provider formatting can mask the original error.
            # Class names alone also cannot turn a body/callback exception into
            # a policy-issued cancellation, expiry or exhaustion observation.
            if self._events[-1].kind not in (
                WriterRetryEventKind.BUDGET_EXHAUSTED,
                WriterRetryEventKind.CANCELLED,
                WriterRetryEventKind.EXPIRED,
            ):
                self._record(WriterRetryEventKind.TERMINAL_FAILURE)
            raise

    def _execute(self) -> PostgresWriteSideResult:
        maximum = self._policy.max_attempts if self._policy is not None else 1
        while self._attempts < maximum:
            timestamp = None
            if self._policy is not None:
                timestamp = self._check_lifetime()
                self._require_idle()
            # Spend exactly once immediately before the synchronous public call.
            # No wait or external callback lies between spend and dispatch.
            self._attempts += 1
            self._record(WriterRetryEventKind.ATTEMPT_DISPATCHED, observed_at=timestamp)
            try:
                result = self._invoke_writer()
            except WriterCapacityRefused as error:
                proven = self._admission is not None and self._admission.refusal is error
                eligible = self._policy is not None and proven
                self._record(
                    WriterRetryEventKind.CAPACITY_REFUSED,
                    pre_body_refusal=proven if self._admission is not None else None,
                )
                self._record(WriterRetryEventKind.ELIGIBILITY_DECIDED, eligible=eligible)
                if not eligible:
                    raise
                if self._attempts == maximum:
                    self._record(WriterRetryEventKind.BUDGET_EXHAUSTED)
                    raise WriterCapacityRetryExhausted(self._attempts, error) from error
                self._backoff(self._policy.delay_before_retry(self._attempts))
            else:
                self._record(WriterRetryEventKind.TERMINAL_RESULT, outcome=result.outcome)
                return result
        raise AssertionError("finite request loop exited without a terminal disposition")

    def _invoke_writer(self) -> PostgresWriteSideResult:
        identity = WriterAttemptIdentity(self._logical_id, self._signature.request_id, self._attempts)
        binding = (
            self._capacity.observe_attempt(identity, self._capacity_observer)
            if self._capacity_observer is not None else nullcontext()
        )
        signature = self._signature
        if self._measure_writer:
            method = (
                self._writer.create_order_with_measurement
                if signature.command_type is CommandType.CREATE
                else self._writer.pay_order_with_measurement
            )
        else:
            method = (
                self._writer.create_order if signature.command_type is CommandType.CREATE
                else self._writer.pay_order
            )
        with binding:
            value = method(request_id=signature.request_id, order_id=signature.order_id,
                           amount=signature.amount)
        if self._measure_writer:
            # The existing measured API owns failure-safe artifact construction.
            # No experiment callback or measurement interpretation runs here.
            with self._lock:
                self._measurements.append(WriterAttemptMeasurement(identity, value))
            return value.producer_value
        return value

    def _backoff(self, delay: float) -> None:
        started = self._check_lifetime()
        not_before = started + delay
        if not isfinite(not_before) or not_before <= started:
            raise ValueError("retry delay cannot be represented by the monotonic clock")
        self._record(
            WriterRetryEventKind.RETRY_SCHEDULED,
            delay_seconds=delay, not_before=not_before, observed_at=started,
        )
        now = started
        while now < not_before:
            # Refusal acquired no permit and never entered the body; checking
            # caller state also excludes a transaction predating that refusal.
            self._require_idle()
            remaining = not_before - now
            if self._expires_at is not None:
                remaining = min(remaining, self._expires_at - now)
            self._wait(remaining)
            after = self._check_lifetime()
            if after <= now:
                raise RuntimeError("wait returned without monotonic progress")
            now = after
        self._record(WriterRetryEventKind.RETRY_READY, not_before=not_before, observed_at=now)

    def _check_lifetime(self) -> float:
        if self._cancelled is not None:
            cancelled = self._cancelled()
            if type(cancelled) is not bool:
                raise TypeError("cancelled must return bool")
            if cancelled:
                self._record(WriterRetryEventKind.CANCELLED)
                raise WriterRetryCancelled("writer retry cancelled")
        now = self._clock()
        if type(now) is not float or not isfinite(now):
            raise ValueError("clock must return finite float seconds")
        if self._last_time is not None and now < self._last_time:
            raise ValueError("clock must be monotonic")
        self._last_time = now
        if self._expires_at is not None and now >= self._expires_at:
            self._record(WriterRetryEventKind.EXPIRED)
            raise WriterRetryExpired("writer retry dispatch deadline expired")
        return now

    def _require_idle(self) -> None:
        if self._connection.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("capacity retry requires an idle business connection")

    def _record(self, kind: WriterRetryEventKind, **fields) -> None:
        observation = WriterRetryObservation(
            logical_invocation_id=self._logical_id,
            request_id=self._signature.request_id,
            kind=kind,
            attempt_number=self._attempts,
            **fields,
        )
        with self._lock:
            self._events.append(observation)
