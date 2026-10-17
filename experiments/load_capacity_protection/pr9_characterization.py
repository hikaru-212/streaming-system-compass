"""Real PR8 owner adapter and PR9 accounting; never dispatch an extra attempt."""

from dataclasses import fields
from threading import get_ident

from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.pr9_model import (
    DurableEvidence, MeasurementEvidence, RequestEvidence, ResultEvidence, WaitEvidence,
)
from src.bootstrap.build_postgres_writer_request import build_postgres_writer_request
from src.compass.transition.runtime import ValidationDispatcher, ValidationPolicy, ValidationRuntime
from src.compass.transition.types import ValidationMode
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.enums import EventType
from src.pipeline.postgres_writer_request import WriterRetryEventKind as Retry
from src.pipeline.transactional.postgres_admission import PostgresOptimisticAdmissionGate
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome as Outcome
from src.pipeline.transactional.postgres_write_side_config import PostgresWriteSideConfig, ValidationPlacement
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurementAvailability as Availability, PostgresWriteSidePhaseMeasurementState as PhaseState,
)
from src.pipeline.transactional.writer_capacity import WriterAttemptIdentity, WriterCapacityEventKind as Capacity
from src.storage.idempotency_store import IdempotencyVerdict


class ProductionLane:
    """Retain one connection and synchronous thread per lane until quiescence.

    Every logical item uses the real builder with identical observation settings.
    Storage and validation remain production implementations. There is exactly
    one invoke() call here; the production owner alone controls attempts.
    """

    def __init__(self, lane_id, connection):
        if connection.closed or connection.autocommit or connection.info.transaction_status != TransactionStatus.IDLE:
            raise ValueError("lane requires open, idle, non-autocommit connection")
        self.lane_id, self.connection = lane_id, connection
        self.runtime = ValidationRuntime(
            dispatcher=ValidationDispatcher(strict_validator=FullProofValidator(), off_validator=NoOpValidator()),
            policy=ValidationPolicy(), mode=ValidationMode.STRICT,
        )
        self.config = PostgresWriteSideConfig(
            validation_mode=ValidationMode.STRICT, validation_placement=ValidationPlacement.PRE_TRANSACTION,
        )

    def invoke(self, index, signature, offer_ns, *, gate, observer, policy, clock_ns, wait):
        problems, waits = [], []
        connection = self.connection

        def sample(operation, label):
            try:
                return operation()
            except BaseException as error:
                problems.append(f"{label}:{type(error).__name__}")
                return None

        def timestamp():
            def read():
                value = clock_ns()
                if type(value) is not int or value < 0:
                    raise ValueError("invalid timestamp")
                return value
            return sample(read, "timestamp")

        def resources():
            return (id(connection), get_ident(),
                    sample(lambda: connection.info.transaction_status.name, "transaction_sample"),
                    sample(lambda: not connection.closed, "connection_sample"))

        def observed_wait(delay):
            # The owner recorded RETRY_SCHEDULED before calling this seam. The
            # shared gate already returned. No SQL or business callback is used
            # for sampling, and sampling failures cannot turn into a refusal.
            scheduled = owner.observations[-1]
            key = WriterAttemptIdentity(scheduled.logical_invocation_id, scheduled.request_id,
                                        scheduled.attempt_number)
            before, started = resources(), timestamp()
            try:
                wait(delay)
            finally:
                ended, after = timestamp(), resources()
                waits.append(WaitEvidence(key, delay, started, ended, before[0], after[0],
                    before[1], after[1], before[2], after[2], before[3], after[3]))

        owner = build_postgres_writer_request(
            request_signature=signature, business_connection=connection, validation_runtime=self.runtime,
            capacity_admission=gate, retry_policy=policy, capacity_observer=observer, measure_writer=True,
            admission_gate_factory=lambda uow: PostgresOptimisticAdmissionGate(uow.event_store),
            write_side_config=self.config, clock=lambda: float(clock_ns() / 1_000_000_000), wait=observed_wait,
        )
        invoked = timestamp()
        result, exception = None, None
        try:
            value = owner.invoke()
            result = ResultEvidence(value.outcome, value.accepted_event, value.idempotency_decision.verdict,
                value.stream_admission_result.verdict if value.stream_admission_result else None,
                value.admission_result.verdict if value.admission_result else None)
        except BaseException as error:
            exception = type(error).__name__
        terminal = timestamp()
        retry = owner.observations
        logical_id = retry[0].logical_invocation_id
        return RequestEvidence(index, signature, self.lane_id, get_ident(), id(connection),
            offer_ns, invoked, terminal, result, exception, retry,
            tuple(e for e in observer.observations if e.identity.logical_invocation_id == logical_id),
            tuple(e for e in observer.failures if e.identity.logical_invocation_id == logical_id),
            tuple(MeasurementEvidence(m.identity, m.delivery.availability, m.delivery.measurement)
                  for m in owner.measurements), tuple(waits), tuple(problems))


def refused_only(request):
    """Classify source-observed absence of body entry, never exception type alone."""
    dispatches = [e for e in request.retry if e.kind is Retry.ATTEMPT_DISPATCHED]
    return (bool(dispatches) and not request.observation_failures
            and all([e.kind for e in request.capacity if e.identity.attempt_number == d.attempt_number]
                    == [Capacity.CALL_STARTED, Capacity.REFUSED, Capacity.CALL_COMPLETED] for d in dispatches))


def verify_durable(request, durable: DurableEvidence):
    """Check exact acknowledgement linkage or reliable refusal-only absence.

    Unknown/ambiguous effects are retained for reconciliation, never converted
    into acceptance. This function has no authority to invoke or retry a writer.
    """
    if durable.failure is not None:
        return ("durable_unavailable",)
    result, signature = request.result, request.signature
    if result is not None and result.outcome is Outcome.ACCEPTED:
        event = result.accepted_event
        valid = (event is not None and event.request_id == signature.request_id
                 and event.order_id == signature.order_id and event.amount == signature.amount
                 and event.sequence == 1 and event.event_type is EventType.CREATED
                 and durable.accepted_events == (event,) and durable.request_event_count == 1
                 and durable.identity_idempotency_count == 1
                 and durable.idempotency_verdict is IdempotencyVerdict.REPLAY
                 and durable.idempotency_signature == signature and durable.idempotency_event == event)
        return () if valid else ("accepted_effect_or_linkage_mismatch",)
    if refused_only(request):
        absent = (durable.accepted_events == () and durable.request_event_count == 0
                  and durable.identity_idempotency_count == 0
                  and durable.idempotency_verdict is IdempotencyVerdict.MISS
                  and durable.idempotency_signature is None and durable.idempotency_event is None)
        return () if absent else ("refusal_has_effect_or_unknown_absence",)
    return ("unexpected_terminal_requires_reconciliation",)


def request_problems(request, policy):
    """Reconcile original PR8 observations with independent gate/wait evidence."""
    problems = list(request.problems)
    if request.observation_failures:
        problems.append("capacity_observation_incomplete")
    attempts = [e for e in request.retry if e.kind is Retry.ATTEMPT_DISPATCHED]
    maximum = policy.max_attempts if policy is not None else 1
    if not attempts or [e.attempt_number for e in attempts] != list(range(1, len(attempts) + 1)) or len(attempts) > maximum:
        problems.append("attempt_budget_or_order")
    logical = request.retry[0].logical_invocation_id if request.retry else None
    if any(e.logical_invocation_id != logical or e.request_id != request.signature.request_id for e in request.retry):
        problems.append("retry_identity")
    if any(e.identity.logical_invocation_id != logical or e.identity.request_id != request.signature.request_id
           or e.thread_id != request.thread_id for e in request.capacity):
        problems.append("capacity_identity_or_thread")
    last_completed = None
    refused = set()
    for attempt in attempts:
        events = [e for e in request.capacity if e.identity.attempt_number == attempt.attempt_number]
        kinds = [e.kind for e in events]
        if kinds == [Capacity.CALL_STARTED, Capacity.REFUSED, Capacity.CALL_COMPLETED]:
            refused.add(attempt.attempt_number)
        elif kinds != [Capacity.CALL_STARTED, Capacity.BODY_ENTERED, Capacity.BODY_EXITED,
                       Capacity.RELEASED, Capacity.CALL_COMPLETED]:
            problems.append("capacity_interval_incomplete")
        if events:
            times = [e.observed_ns for e in events]
            if times != sorted(times) or (last_completed is not None and times[0] < last_completed):
                problems.append("attempts_not_serial")
            last_completed = times[-1]
        if attempt.attempt_number > 1 and attempt.attempt_number - 1 not in refused:
            problems.append("retry_after_body")
    for event in request.retry:
        if event.kind is Retry.CAPACITY_REFUSED and policy is not None:
            if event.pre_body_refusal is not (event.attempt_number in refused):
                problems.append("refusal_provenance_mismatch")
        if event.kind is Retry.ELIGIBILITY_DECIDED:
            expected = policy is not None and event.attempt_number in refused
            if event.eligible is not expected:
                problems.append("eligibility_mismatch")
    for interval in request.waits:
        before = [e for e in request.capacity if e.identity == interval.identity]
        valid = (interval.identity.logical_invocation_id == logical
                 and interval.identity.attempt_number in refused and bool(before)
                 and interval.started_ns is not None and interval.ended_ns is not None
                 and before[-1].observed_ns <= interval.started_ns <= interval.ended_ns
                 and interval.connection_before == interval.connection_after == request.connection_id
                 and interval.thread_before == interval.thread_after == request.thread_id
                 and interval.open_before is True and interval.open_after is True
                 and interval.transaction_before == interval.transaction_after == "IDLE")
        if not valid:
            problems.append("wait_resource_or_release_witness")
    scheduled = [e for e in request.retry if e.kind is Retry.RETRY_SCHEDULED]
    ready = [e for e in request.retry if e.kind is Retry.RETRY_READY]
    if len(scheduled) != len(ready) or len(scheduled) != max(0, len(attempts) - 1):
        problems.append("incomplete_retry_schedule")
    for start, end in zip(scheduled, ready):
        matching = [w for w in request.waits if w.identity.attempt_number == start.attempt_number]
        if (not matching or policy is None or start.delay_seconds != policy.delay_before_retry(start.attempt_number)
                or start.not_before is None or end.observed_at is None or end.observed_at < start.not_before):
            problems.append("delay_not_observed")
        next_dispatch = next((e for e in attempts if e.attempt_number == start.attempt_number + 1), None)
        if (end.attempt_number != start.attempt_number or next_dispatch is None
                or next_dispatch.observed_at is None or end.observed_at is None
                or next_dispatch.observed_at < end.observed_at):
            problems.append("dispatch_before_ready")
    exhausted = any(e.kind is Retry.BUDGET_EXHAUSTED for e in request.retry)
    if exhausted and (policy is None or len(attempts) != maximum or len(refused) != maximum
                      or request.result is not None or request.exception_class != "WriterCapacityRetryExhausted"):
        problems.append("exhaustion_mismatch")
    if request.exception_class is not None:
        expected_refusal_terminal = refused_only(request) and (
            exhausted or (policy is None and request.exception_class == "WriterCapacityRefused")
        )
        if not expected_refusal_terminal:
            problems.append("unexpected_writer_failure")
    if request.result is not None:
        if request.result.outcome is not Outcome.ACCEPTED:
            problems.append("unexpected_nonaccepted_terminal")
        if not request.retry or request.retry[-1].kind is not Retry.TERMINAL_RESULT:
            problems.append("terminal_result_mismatch")
        if len(request.measurements) != 1:
            problems.append("measurement_missing")
    for delivery in request.measurements:
        if (delivery.identity.logical_invocation_id != logical
                or delivery.identity.request_id != request.signature.request_id
                or delivery.identity.attempt_number != len(attempts)):
            problems.append("measurement_identity")
        if delivery.availability is not Availability.AVAILABLE or delivery.measurement is None:
            problems.append("measurement_unavailable")
        elif any(getattr(delivery.measurement, f.name).state is PhaseState.NOT_COLLECTED
                 for f in fields(delivery.measurement)):
            problems.append("measurement_incomplete")
    if len({e.identity.attempt_number for e in request.capacity}) != len(attempts):
        problems.append("capacity_attempt_count")
    if (request.offer_ns is None or request.invoked_ns is None or request.terminal_ns is None
            or not request.offer_ns <= request.invoked_ns <= request.terminal_ns):
        problems.append("logical_timestamps_incomplete")
    if request.durable is not None:
        problems.extend(verify_durable(request, request.durable))
    return tuple(dict.fromkeys(problems))


def peak(intervals):
    """Half-open interval sweep, with exits ordered before entries at a tie."""
    events = [(start, 1) for start, end in intervals if start < end]
    events += [(end, -1) for start, end in intervals if start < end]
    current = maximum = 0
    for _, change in sorted(events):
        current += change
        maximum = max(maximum, current)
    return maximum


def summarize(cell):
    """Per-cell metrics only; no warmup pooling or replacement of missing timing.

    Raw samples retain denominators and permit later reviewed percentiles. Body,
    UOW and commit durations overlap and must not be summed as SQL/CPU cost.
    """
    requests = cell.requests
    attempts = sum(e.kind is Retry.ATTEMPT_DISPATCHED for r in requests for e in r.retry)
    accepted = [r for r in requests if r.result and r.result.outcome is Outcome.ACCEPTED]
    bodies, calls, waiting, actual_waits, phase_samples = [], [], [], [], {}
    for r in requests:
        for start_kind, end_kind, output in ((Capacity.BODY_ENTERED, Capacity.BODY_EXITED, bodies),
                                           (Capacity.CALL_STARTED, Capacity.CALL_COMPLETED, calls)):
            starts = {e.identity: e.observed_ns for e in r.capacity if e.kind is start_kind}
            output.extend((starts[e.identity], e.observed_ns) for e in r.capacity
                          if e.kind is end_kind and e.identity in starts)
        schedules = {e.attempt_number: e for e in r.retry if e.kind is Retry.RETRY_SCHEDULED}
        for e in r.retry:
            if e.kind is Retry.RETRY_READY and e.attempt_number in schedules:
                start = schedules[e.attempt_number].observed_at
                if start is not None and e.observed_at is not None:
                    waiting.append((round(start * 1e9), round(e.observed_at * 1e9)))
        actual_waits.extend((w.started_ns, w.ended_ns) for w in r.waits
                            if w.started_ns is not None and w.ended_ns is not None)
        for delivery in r.measurements:
            if delivery.measurement is not None:
                for f in fields(delivery.measurement):
                    phase = getattr(delivery.measurement, f.name)
                    phase_samples.setdefault(f.name, []).append((phase.state.value, phase.elapsed_ns))
    offers = [r.offer_ns for r in requests if r.offer_ns is not None]
    ends = [r.terminal_ns for r in requests if r.terminal_ns is not None]
    drain = max(ends) - min(offers) if ends and offers else None
    k = cell.plan.logical_requests
    policy = cell.plan.retry_policy if cell.cell.enabled else None
    diagnoses = [request_problems(r, policy) for r in requests]
    body_complete = bool(requests) and not cell.unobserved and not any(
        r.observation_failures or any(code in problems for code in (
            "capacity_interval_incomplete", "capacity_attempt_count", "capacity_identity_or_thread", "attempts_not_serial",
        )) for r, problems in zip(requests, diagnoses)
    )
    wait_complete = bool(requests) and not cell.unobserved and not any(
        any(code in problems for code in ("wait_resource_or_release_witness", "incomplete_retry_schedule",
                                          "delay_not_observed", "dispatch_before_ready"))
        for problems in diagnoses
    )
    overlap = peak(bodies) if body_complete else None
    complete = (not cell.problems and len(requests) == k and not cell.unobserved
                and cell.before == cell.after and cell.before.tracked_clean and cell.before.machinery_committed
                and all(not problems and r.durable is not None for r, problems in zip(requests, diagnoses))
                and overlap is not None and overlap <= cell.plan.capacity_bound)
    return {
        "logical_requests": k, "observed_logical_requests": len(requests), "attempts": attempts,
        "capacity_refusals": sum(e.kind is Capacity.REFUSED for r in requests for e in r.capacity),
        "retry_attempts": sum(max(0, sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in r.retry) - 1) for r in requests),
        "budget_exhaustions": sum(any(e.kind is Retry.BUDGET_EXHAUSTED for e in r.retry) for r in requests),
        "acknowledged_accepted": len(accepted), "attempt_amplification": attempts / k,
        "completion_proportion": len(accepted) / k, "time_to_drain_ns": drain,
        "completion_throughput_per_second": len(accepted) * 1e9 / drain if drain else None,
        "accepted_completion_latency_ns": tuple(r.terminal_ns - r.offer_ns for r in accepted
                                                if r.terminal_ns is not None and r.offer_ns is not None),
        "logical_terminal_latency_ns": tuple(r.terminal_ns - r.offer_ns for r in requests
                                             if r.terminal_ns is not None and r.offer_ns is not None),
        "logical_invocation_latency_ns": tuple(r.terminal_ns - r.invoked_ns for r in requests
                                               if r.terminal_ns is not None and r.invoked_ns is not None),
        "first_dispatch_latency_ns": tuple(r.capacity[0].observed_ns - r.offer_ns for r in requests
                                           if r.capacity and r.offer_ns is not None),
        "accepted_after_retry": sum(sum(e.kind is Retry.ATTEMPT_DISPATCHED for e in r.retry) > 1 for r in accepted),
        "body_latency_ns": tuple(end - start for start, end in bodies),
        "admission_call_latency_ns": tuple(end - start for start, end in calls),
        "protected_writer_overlap": overlap,
        "waiting_logical_peak": peak(waiting) if wait_complete else None,
        "waiting_retained_connections_peak": peak(waiting) if wait_complete else None,
        "waiting_retained_connection_ns": sum(end - start for start, end in waiting) if wait_complete else None,
        "retry_wait_intervals_ns": tuple(waiting), "actual_wait_intervals_ns": tuple(actual_waits),
        "actual_wait_duration_ns": sum(end - start for start, end in actual_waits),
        "retained_connections": len(cell.connections) if len(cell.connections) == cell.cell.concurrency + 1 else None,
        "phase_samples": phase_samples,
        "valid": complete,
    }
