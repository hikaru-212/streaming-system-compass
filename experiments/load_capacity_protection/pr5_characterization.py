"""Retained-lane PR5 caller reactions outside the unchanged writer/authority owners."""

from dataclasses import replace
from threading import Barrier, Event, Lock, Thread

from experiments.load_capacity_protection.evidence import project_observation
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadOuterPhase, LoadRequestObservation,
)
from experiments.load_capacity_protection.postgres_characterization import _failure_evidence
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission, ObservationDefect, _Attempt
from experiments.load_capacity_protection.pr4_model import RequestObservation
from experiments.load_capacity_protection.pr5_model import (
    AttemptEvidence, LogicalTerminal, empty_characterization, retry_delay_ns,
)
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome, PostgresWriteSideResult
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementDelivery
from src.pipeline.transactional.writer_capacity import WriterCapacityRefused


class CharacterizationError(RuntimeError):
    """Quiescent partial logical/attempt evidence survives a harness defect."""

    def __init__(self, cell, failures):
        super().__init__("PR5 harness defect; partial evidence retained")
        self.cell, self.failures = cell, failures


def elapsed_waiter(clock_ns):
    """Build an interruptible real elapsed waiter; construction does no waiting.

The supplied clock must be the scheduler's monotonic ns clock. The stop event
wakes waiting lanes on failures elsewhere. No admission, connection operation,
transaction or owner lock is acquired here. Deterministic tests inject a fake.
"""
    def wait_until(eligible_ns, stopped):
        while not stopped.is_set():
            remaining = eligible_ns - clock_ns()
            if remaining <= 0:
                return
            # Bound the OS wait conversion even for very large explicit delays.
            stopped.wait(min(remaining, 60_000_000_000) / 1_000_000_000)
    return wait_until


def run_characterization(identity, protection, retry, workload, lanes, *, admission, clock_ns, wait_until):
    """Offer K once; each lane retains its current logical request across retries.

Only observed pre-body WriterCapacityRefused reaches experiment policy. Native
failures and unexpected normal results stop claims and pending retries; admitted
calls drain. Per-request attempt limits include the initial call, giving a hard
K*M attempt ceiling (not a wall-clock deadline). Waiting holds no scheduler lock
or capacity permit. Other lanes proceed independently; no fairness is promised.
"""
    cell = empty_characterization(identity, protection, retry, workload)
    if type(lanes) is not tuple or len(lanes) != identity.configured_concurrency:
        raise ValueError("exact declared lane population required")
    if len({id(lane) for lane in lanes}) != len(lanes) or not all(callable(lane) for lane in lanes):
        raise ValueError("distinct callable lanes required")
    if (not isinstance(admission, ObservedAdmission) or admission.bound != protection.bound
            or admission.clock_ns is not clock_ns):
        raise ValueError("one real shared observed admission and clock required")
    if any(getattr(lane, "capacity_admission", None) is not admission for lane in lanes):
        raise ValueError("all lanes must retain the same declared admission")
    if not callable(wait_until):
        raise TypeError("explicit retry waiter required")
    requests = list(cell.logical_requests)
    lock, stopped = Lock(), Event()
    cursor, offer = 0, None
    failures = []

    def release():
        nonlocal offer
        offer = clock_ns()

    ready = Barrier(len(lanes) + 1, action=release)

    def worker(lane_id, lane):
        nonlocal cursor
        row = None
        phase = LoadOuterPhase.SCHEDULING
        try:
            ready.wait()
            while not stopped.is_set():
                with lock:
                    if stopped.is_set() or cursor == len(workload):
                        return
                    index = cursor
                    cursor += 1
                request = replace(requests[index], offer_ns=offer)
                requests[index] = request
                while not stopped.is_set():
                    phase = LoadOuterPhase.DISPATCHED
                    row = RequestObservation(request.item, protection, lane_id=lane_id,
                                             offer_ns=offer, dispatch_ns=clock_ns())
                    number = len(request.attempts) + 1

                    def retain():
                        requests[index] = replace(request, attempts=request.attempts + (AttemptEvidence(number, row),))

                    retain()
                    journal = _Attempt()
                    returned = error = None
                    phase = LoadOuterPhase.WRITER_CALL
                    with admission.observe(journal):
                        entry = clock_ns()
                        try:
                            returned = lane(request.item)
                        except BaseException as caught:
                            error = caught
                        finally:
                            values = dict(journal.times)
                            if "capacity_refused_ns" in values:
                                values["acknowledgement"] = LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
                            row = replace(row, public_call_entry_ns=entry, public_call_exit_ns=clock_ns(), **values)
                            retain()
                    if journal.defect or journal.calls != 1:
                        raise ObservationDefect("admission observation contract failed")
                    if row.capacity_refused_ns is not None:
                        if not isinstance(error, WriterCapacityRefused):
                            raise ObservationDefect("refusal did not propagate")
                    elif error is not None:
                        stopped.set()
                        if not row.writer_entered or isinstance(error, ObservationDefect):
                            raise ObservationDefect("failure outside observed writer body")
                        row = replace(row, failure=_failure_evidence(
                            error, LoadOuterPhase.WRITER_CALL, True, LoadAcknowledgement.UNKNOWN,
                        ))
                    else:
                        phase = LoadOuterPhase.TERMINAL_OBSERVATION
                        if isinstance(returned, PostgresWriteSideMeasurementDelivery):
                            result, measurement, availability = returned.producer_value, returned.measurement, returned.availability
                        else:
                            result, measurement, availability = returned, None, None
                        if type(result) is not PostgresWriteSideResult:
                            raise ObservationDefect("invalid writer delivery")
                        acknowledged = (LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                                        if result.outcome is PostgresWriteSideOutcome.ACCEPTED
                                        else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE)
                        projected = project_observation(LoadRequestObservation(
                            identity, request.item, lane_id=lane_id,
                            writer_entry_ns=row.public_call_entry_ns, writer_exit_ns=row.public_call_exit_ns,
                            result=result, measurement=measurement, measurement_availability=availability,
                            acknowledgement=acknowledged,
                        ))
                        row = replace(row, result=projected.result, measurement=measurement,
                                      measurement_availability=availability, acknowledgement=acknowledged)
                        if acknowledged is not LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED:
                            stopped.set()
                    phase = LoadOuterPhase.TERMINAL_OBSERVATION
                    row = replace(row, terminal_observation_ns=clock_ns())
                    retain()
                    if row.capacity_refused_ns is not None:
                        delay = retry_delay_ns(retry, request.item.workload_index, number)
                        if delay is not None:
                            attempt = AttemptEvidence(number, row, delay, row.capacity_refused_ns + delay)
                            request = replace(request, attempts=request.attempts + (attempt,))
                            requests[index] = request
                            # The public call and super().run have returned. In the
                            # real adapter, refused entry did no SQL and the retained
                            # connection remains idle. Never wait under the claim lock.
                            phase = LoadOuterPhase.SCHEDULING
                            wait_until(attempt.next_retry_eligible_ns, stopped)
                            if not stopped.is_set() and clock_ns() < attempt.next_retry_eligible_ns:
                                raise ObservationDefect("waiter returned before retry eligibility")
                            continue
                        state = LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL
                    elif row.failure is not None:
                        state = LogicalTerminal.NATIVE_WRITER_FAILURE
                    elif row.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED:
                        state = LogicalTerminal.ACKNOWLEDGED_ACCEPTED
                    else:
                        state = LogicalTerminal.NON_ACCEPTED_WRITER_RESULT
                    request = replace(requests[index], terminal_state=state, final_terminal_ns=clock_ns())
                    requests[index] = request
                    break
        except BaseException as error:
            stopped.set()
            entered = row is not None and row.writer_entered
            safe_phase = phase if phase is not LoadOuterPhase.WRITER_CALL or entered else LoadOuterPhase.DISPATCHED
            with lock:
                failures.append(_failure_evidence(error, safe_phase, entered, LoadAcknowledgement.UNKNOWN))

    threads = [Thread(target=worker, args=(i, lane), name=f"pr5-lane-{i}") for i, lane in enumerate(lanes)]
    started = []
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
        ready.wait()
    except BaseException as error:
        stopped.set()
        ready.abort()
        failures.append(_failure_evidence(error, LoadOuterPhase.SCHEDULING, False, LoadAcknowledgement.UNKNOWN))
    finally:
        for thread in started:
            thread.join()
    cell = replace(cell, logical_requests=tuple(replace(r, offer_ns=offer) for r in requests))
    if failures:
        raise CharacterizationError(cell, tuple(failures))
    return cell
