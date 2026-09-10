"""PR4 persistent lanes and experiment-owned observation of the PR3 run seam."""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from threading import Barrier, Lock, Thread, local

from experiments.load_capacity_protection.evidence import project_observation
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadOuterPhase, LoadRequestObservation,
)
from experiments.load_capacity_protection.postgres_characterization import _failure_evidence
from experiments.load_capacity_protection.pr4_model import (
    Characterization, ProtectionMode, RequestObservation,
)
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome, PostgresWriteSideResult
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementDelivery
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused


class ObservationDefect(RuntimeError):
    """An experiment seam was bypassed or invoked more than once."""


@dataclass
class _Attempt:
    times: dict = field(default_factory=dict)
    calls: int = 0
    defect: bool = False


class ObservedAdmission(BoundedWriterAdmission):
    """One shared real PR3 budget with thread-local per-attempt timing custody.

Delegates exactly once to super().run; it never acquires/releases permits itself.
The injected monotonic clock must be thread-safe and non-raising. Observation
work inside the permit adds overhead, retained as an interpretation limitation.
"""

    def __init__(self, bound: int, *, clock_ns: Callable[[], int]):
        super().__init__(bound)
        self.clock_ns = clock_ns
        self._current = local()

    @contextmanager
    def observe(self, attempt: _Attempt):
        """Bind one scheduler attempt to this thread without holding a permit."""
        if getattr(self._current, "attempt", None) is not None:
            raise ObservationDefect("nested observation")
        self._current.attempt = attempt
        try:
            yield
        finally:
            self._current.attempt = None

    def run(self, operation):
        """Preserve exact result/exception; distinguish refusal by lack of entry."""
        attempt = getattr(self._current, "attempt", None)
        if attempt is None:
            raise ObservationDefect("admission called outside observed attempt")
        attempt.calls += 1
        if attempt.calls != 1:
            attempt.defect = True
            raise ObservationDefect("more than one admission attempt for one item")

        def stamp(name):
            try:
                attempt.times[name] = self.clock_ns()
            except BaseException:
                attempt.defect = True
                raise

        stamp("capacity_attempt_ns")

        def observed_operation():
            stamp("capacity_admitted_ns")
            stamp("protected_writer_entry_ns")
            try:
                return operation()
            finally:
                stamp("protected_writer_exit_ns")

        try:
            return super().run(observed_operation)
        except WriterCapacityRefused:
            # A body may itself raise this exception class. Only an exception
            # before admission is evidence of this gate refusing the attempt.
            if "capacity_admitted_ns" not in attempt.times:
                stamp("capacity_refused_ns")
            raise
        finally:
            # For admitted work super().run's finally has already released.
            # This is an upper observation boundary, not the release instant.
            stamp("admission_return_ns")


class CharacterizationError(RuntimeError):
    """Retain partial observations after quiescence on a harness defect."""

    def __init__(self, cell, failures):
        super().__init__("PR4 harness defect; partial evidence retained")
        self.cell = cell
        self.failures = failures


def run_characterization(identity, protection, workload, lanes, *, admission, clock_ns):
    """Offer K once to N retained lanes; refusals continue, native failures stop.

Each lane must expose capacity_admission and invoke the same supplied gate via
the public writer. None means unprotected. No retries, pacing, replacement lanes,
or hard cancellation exist. Workers join before callers may verify/clean rows.
"""
    Characterization(identity, protection, workload, ())
    protected = protection.mode is ProtectionMode.PROTECTED
    if type(lanes) is not tuple or len(lanes) != identity.configured_concurrency:
        raise ValueError("exact declared lane population required")
    if len({id(lane) for lane in lanes}) != len(lanes) or not all(callable(lane) for lane in lanes):
        raise ValueError("distinct callable lanes required")
    if protected:
        if not isinstance(admission, ObservedAdmission) or admission.bound != protection.bound:
            raise ValueError("one observed admission matching the declared bound required")
        if admission.clock_ns is not clock_ns:
            raise ValueError("admission and scheduler must share the clock")
    elif admission is not None:
        raise ValueError("unprotected requires capacity_admission=None")
    if any(getattr(lane, "capacity_admission", object()) is not admission for lane in lanes):
        raise ValueError("every lane must retain the same declared admission object")

    observations = [RequestObservation(item, protection) for item in workload]
    lock = Lock()
    cursor = 0
    stopped = False
    offer = None
    failures = []

    def stop():
        nonlocal stopped
        with lock:
            stopped = True

    def release():
        nonlocal offer
        offer = clock_ns()

    ready = Barrier(len(lanes) + 1, action=release)

    def worker(lane_id, lane):
        nonlocal cursor
        observation = None
        phase = LoadOuterPhase.SCHEDULING
        try:
            ready.wait()
            while True:
                with lock:
                    if stopped or cursor == len(workload):
                        return
                    index = cursor
                    cursor += 1
                    observation = observations[index]
                phase = LoadOuterPhase.DISPATCHED
                observation = replace(observation, lane_id=lane_id, offer_ns=offer, dispatch_ns=clock_ns())
                observations[index] = observation
                attempt = _Attempt()
                returned = error = None
                # Binding the thread-local journal is outside the public interval.
                def invoke():
                    nonlocal returned, error, observation
                    entry = clock_ns()
                    try:
                        returned = lane(observation.item)
                    except BaseException as caught:
                        error = caught
                    finally:
                        exit_ns = clock_ns()
                        values = dict(attempt.times)
                        if "capacity_refused_ns" in values:
                            values["acknowledgement"] = LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
                        observation = replace(observation, public_call_entry_ns=entry,
                                              public_call_exit_ns=exit_ns, **values)
                        observations[index] = observation

                phase = LoadOuterPhase.WRITER_CALL
                if protected:
                    with admission.observe(attempt):
                        invoke()
                else:
                    invoke()
                if attempt.defect or (protected and attempt.calls != 1):
                    raise ObservationDefect("admission observation contract failed")
                if observation.capacity_refused_ns is not None:
                    if not isinstance(error, WriterCapacityRefused):
                        raise ObservationDefect("refusal did not propagate")
                elif error is not None:
                    stop()
                    if not observation.writer_entered or isinstance(error, ObservationDefect):
                        raise ObservationDefect("failure outside observed writer body")
                    observation = replace(observation, failure=_failure_evidence(
                        error, LoadOuterPhase.WRITER_CALL, True, LoadAcknowledgement.UNKNOWN,
                    ))
                else:
                    phase = LoadOuterPhase.TERMINAL_OBSERVATION
                    if isinstance(returned, PostgresWriteSideMeasurementDelivery):
                        result, measurement, availability = (
                            returned.producer_value, returned.measurement, returned.availability,
                        )
                    else:
                        result, measurement, availability = returned, None, None
                    if type(result) is not PostgresWriteSideResult:
                        raise ObservationDefect("invalid writer delivery")
                    acknowledgement = (
                        LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                        if result.outcome is PostgresWriteSideOutcome.ACCEPTED
                        else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
                    )
                    # Reuse only PR1's safe normal-return fact projection. No
                    # PR1 request or production result is created for refusal.
                    projected = project_observation(LoadRequestObservation(
                        identity, observation.item, lane_id=lane_id,
                        writer_entry_ns=observation.public_call_entry_ns,
                        writer_exit_ns=observation.public_call_exit_ns, result=result,
                        measurement=measurement, measurement_availability=availability,
                        acknowledgement=acknowledgement,
                    ))
                    observation = replace(observation, result=projected.result,
                                          measurement=measurement, measurement_availability=availability,
                                          acknowledgement=acknowledgement)
                phase = LoadOuterPhase.TERMINAL_OBSERVATION
                observations[index] = observation
                observations[index] = replace(observation, terminal_observation_ns=clock_ns())
        except BaseException as error:
            stop()
            entered = observation is not None and observation.writer_entered
            # Harness failures are cell evidence, never native writer failures.
            safe_phase = phase if phase is not LoadOuterPhase.WRITER_CALL or entered else LoadOuterPhase.DISPATCHED
            failure = _failure_evidence(error, safe_phase, entered, LoadAcknowledgement.UNKNOWN)
            with lock:
                failures.append(failure)

    threads = [Thread(target=worker, args=(i, lane), name=f"pr4-lane-{i}") for i, lane in enumerate(lanes)]
    started = []
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
        ready.wait()
    except BaseException as error:
        stop()
        ready.abort()
        failures.append(_failure_evidence(error, LoadOuterPhase.SCHEDULING, False, LoadAcknowledgement.UNKNOWN))
    finally:
        for thread in started:
            thread.join()
    retained = Characterization(identity, protection, workload,
                                tuple(replace(o, offer_ns=offer) for o in observations))
    if failures:
        raise CharacterizationError(retained, tuple(failures))
    return retained
