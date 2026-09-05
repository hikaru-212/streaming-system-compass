"""Finite closed-loop experiment mechanics with injected, retained lane callables.

There is no PostgreSQL construction, database access, live runner, serialization,
or capacity policy here. Supplying real resources requires separate approval.
"""

from collections.abc import Callable
from dataclasses import replace
import re
from threading import Barrier, Lock, Thread
from time import monotonic_ns

from experiments.load_capacity_protection.model import (
    LoadAcknowledgement,
    LoadCellIdentity,
    LoadCellObservation,
    LoadFailureEvidence,
    LoadOuterPhase,
    LoadRequestObservation,
    LoadWorkItem,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurementDelivery,
)


LoadLaneCallable = Callable[
    [LoadWorkItem], PostgresWriteSideResult | PostgresWriteSideMeasurementDelivery
]


class LoadHarnessError(RuntimeError):
    """Harness defect with retained observations, separate from writer failures.

No exception messages or tracebacks are copied into evidence. A bad return type
or observation failure does not become a fabricated producer outcome. The cell
can remain partial; it must not be treated as a valid completed characterization.
"""

    def __init__(
        self, cell: LoadCellObservation, failures: tuple[LoadFailureEvidence, ...]
    ) -> None:
        super().__init__("experiment harness failed; retained cell is incomplete")
        self.cell = cell
        self.failures = failures


def _failure_evidence(
    error: BaseException,
    phase: LoadOuterPhase,
    entered: bool,
    acknowledgement: LoadAcknowledgement,
) -> LoadFailureEvidence:
    """Read only type identity and an optional direct, syntactically safe code."""
    try:
        sqlstate = getattr(error, "sqlstate", None)
    except Exception:
        sqlstate = None
    if not isinstance(sqlstate, str) or re.fullmatch(r"[0-9A-Z]{5}", sqlstate) is None:
        sqlstate = None
    error_type = type(error)
    return LoadFailureEvidence(
        exception_class=f"{error_type.__module__}.{error_type.__name__}",
        phase=phase,
        writer_entered=entered,
        acknowledgement=acknowledgement,
        sqlstate=sqlstate,
    )


def run_characterization(
    cell: LoadCellIdentity,
    prepared_workload: tuple[LoadWorkItem, ...],
    lane_callables: tuple[LoadLaneCallable, ...],
    *,
    clock_ns: Callable[[], int] = monotonic_ns,
) -> LoadCellObservation:
    """Execute predetermined K once, through N persistent experiment workers.

Inputs are prepared before the run. Tuple position identifies each lane and
must match configured concurrency. Each callable must exclusively own its
resource for this run; different wrappers must not hide a shared resource.
Obvious callable/bound-owner aliases are rejected, but closures cannot be
inspected to prove resource independence. Resources are neither created nor
closed here. K may be smaller than N, including an empty prepared workload.

All workers rendezvous once. The barrier action captures a common offer time
before any claim. Subsequent claims use a shared cursor, without batch barriers.
The injected clock must be thread-safe, non-raising, and monotonic in one domain.
Writer entry/exit timestamps immediately surround the injected call; measurement
delivery decoding and minimal observation retention follow the exit boundary.

Any escaping writer exception stops new claims across the cell. Calls already
claimed may finish; the failing resource is never reused. Completed evidence
and offered-but-undispatched residuals survive. This conservative mechanic does
not authorize a future database recovery/continuation policy. Harness defects
instead raise LoadHarnessError after joining workers, with retained evidence.

This synchronous mechanic has no abort/deadline API and cannot cancel a stuck
call. Callables must eventually return or raise. Tests supply bounded causal
waits; live-run deadline and resource cleanup responsibilities remain deferred.
"""
    LoadCellObservation(cell, prepared_workload)
    if type(lane_callables) is not tuple or len(lane_callables) != cell.configured_concurrency:
        raise ValueError("supply exactly one callable per configured lane in a tuple")
    if not all(callable(lane) for lane in lane_callables) or not callable(clock_ns):
        raise TypeError("lanes and clock_ns must be callable")
    owners = [
        owner if (owner := getattr(lane, "__self__", None)) is not None else lane
        for lane in lane_callables
    ]
    if len({id(owner) for owner in owners}) != len(owners):
        raise ValueError("lane callables must have distinct resource owners")

    schedule_lock = Lock()
    next_index = 0
    stopped = False
    offer_ns: int | None = None
    # Preparation is outside the release boundary. Each claimed slot has one
    # worker owner; the caller reads these slots only after joining every worker.
    observations = [LoadRequestObservation(cell, item) for item in prepared_workload]
    harness_failures: list[LoadFailureEvidence] = []

    def release() -> None:
        nonlocal offer_ns
        offer_ns = clock_ns()

    ready = Barrier(len(lane_callables) + 1, action=release)

    def stop_claims() -> None:
        nonlocal stopped
        with schedule_lock:
            stopped = True

    def worker(lane_id: int, invoke: LoadLaneCallable) -> None:
        nonlocal next_index
        observation: LoadRequestObservation | None = None
        phase = LoadOuterPhase.SCHEDULING
        try:
            ready.wait()
            while True:
                with schedule_lock:
                    if stopped or next_index == len(prepared_workload):
                        return
                    index = next_index
                    # Select current-item evidence before dispatch observation can
                    # fail; never attribute a new claim to the previous return.
                    observation = observations[index]
                    next_index += 1
                phase = LoadOuterPhase.DISPATCHED
                observation = replace(
                    observation, lane_id=lane_id, offer_ns=offer_ns,
                    dispatch_ns=clock_ns(),
                )
                observations[index] = observation
                # No model construction, lock, or recording lies between the
                # entry reading and invocation or between return and exit reading.
                entry_ns = clock_ns()
                phase = LoadOuterPhase.WRITER_CALL
                try:
                    returned = invoke(observation.item)
                except BaseException as error:
                    exit_ns = clock_ns()
                    stop_claims()
                    observation = replace(
                        observation, writer_entry_ns=entry_ns, writer_exit_ns=exit_ns,
                    )
                    observations[index] = observation
                    phase = LoadOuterPhase.TERMINAL_OBSERVATION
                    failure = _failure_evidence(
                        error, LoadOuterPhase.WRITER_CALL, True, LoadAcknowledgement.UNKNOWN,
                    )
                    observation = replace(observation, failure=failure)
                else:
                    exit_ns = clock_ns()
                    # Keep a completed interval even if delivery decoding exposes
                    # a harness contract defect. Such a defect is not a writer throw.
                    observation = replace(
                        observation, writer_entry_ns=entry_ns, writer_exit_ns=exit_ns,
                    )
                    observations[index] = observation
                    phase = LoadOuterPhase.TERMINAL_OBSERVATION
                    if isinstance(returned, PostgresWriteSideMeasurementDelivery):
                        result = returned.producer_value
                        measurement = returned.measurement
                        availability = returned.availability
                    else:
                        result = returned
                        measurement = availability = None
                    if type(result) is not PostgresWriteSideResult:
                        raise TypeError("lane must return an untraced writer result or delivery")
                    acknowledgement = (
                        LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                        if result.outcome is PostgresWriteSideOutcome.ACCEPTED
                        else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
                    )
                    observation = replace(
                        observation, result=result, measurement=measurement,
                        measurement_availability=availability,
                        acknowledgement=acknowledgement,
                    )
                phase = LoadOuterPhase.TERMINAL_OBSERVATION
                # Retain the return/failure before taking the terminal reading.
                # Updating the immutable timestamped snapshot precedes replenishment.
                observations[index] = observation
                observation = replace(observation, terminal_observation_ns=clock_ns())
                observations[index] = observation
        except BaseException as error:
            stop_claims()
            failure = _failure_evidence(
                error, phase,
                observation is not None and observation.writer_entry_ns is not None,
                observation.acknowledgement if observation is not None
                else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE,
            )
            with schedule_lock:
                harness_failures.append(failure)

    threads = [
        Thread(target=worker, args=(lane_id, lane), name=f"load-lane-{lane_id}")
        for lane_id, lane in enumerate(lane_callables)
    ]
    started: list[Thread] = []
    try:
        for thread in threads:
            thread.start()
            started.append(thread)
        ready.wait()
    except BaseException as error:
        stop_claims()
        ready.abort()
        harness_failures.append(_failure_evidence(
            error, LoadOuterPhase.SCHEDULING, False,
            LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE,
        ))
    finally:
        for thread in started:
            thread.join()

    # All K became eligible together, including residual items never claimed.
    # Filling their shared offer timestamp after quiescence avoids an O(K)
    # ledger traversal delaying release or entering the replenishment loop.
    retained = LoadCellObservation(
        cell, prepared_workload,
        tuple(replace(observation, offer_ns=offer_ns) for observation in observations),
    )
    if harness_failures:
        raise LoadHarnessError(retained, tuple(harness_failures))
    return retained
