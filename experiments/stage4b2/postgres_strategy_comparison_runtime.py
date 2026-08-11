"""Recorded PostgreSQL runtime for the Stage 4B.2 PR6 experiment.

The accepted comparison module owns protocol and evidence semantics.  This
module owns only the experiment's database lifecycle, fixed two-lane execution,
external timing, source-grounded sample conversion, and atomic evidence output.
It exposes no command-line entry point and never extends a recorded schedule.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
import os
from pathlib import Path
from queue import Queue
import re
import subprocess
import tempfile
import threading
import time
from typing import Any

from experiments.stage4b2.postgres_strategy_comparison import (
    PR3_PHASE_NAMES,
    PROJECT_ROOT,
    SCHEMA_VERSION,
    AggregateResult,
    Cohort,
    Composition,
    EnvironmentManifest,
    EvidenceStatus,
    ExperimentError,
    ExperimentSample,
    ExperimentSchedule,
    LoadedBaseline,
    PairedDifferenceResult,
    PhaseRecord,
    PhaseState,
    ProtocolConfig,
    RejectionStage,
    RunValidationResult,
    SamplePlan,
    Scenario,
    Surface,
    TimedInvocation,
    UnsupportedCohortError,
    _build_preflight_validation_runtime,
    _build_preflight_writers,
    _guard_preflight_test_database,
    _preflight_admission_gate_factory,
    _require_select_one_and_restore_idle,
    _require_strict_full_proof_validation,
    aggregate_paired_differences,
    aggregate_samples,
    aggregates_to_json,
    build_environment_manifest,
    classify_cohort,
    deterministic_sample_token,
    generate_recorded_schedule,
    load_frozen_baseline,
    manifest_to_json,
    samples_to_jsonl,
    time_after_start_gate,
    time_public_invocation,
    unload_frozen_baseline,
    validate_recorded_run,
)


CANONICAL_AMOUNT = Decimal("100.00")
CANONICAL_COMMAND = "CREATE"
CANONICAL_HISTORY_DEPTH = 0
CANONICAL_EXPECTED_SEQUENCE = 1
SCHEMA_OR_MIGRATION_IDENTITY = "migrations-through-007"
_CONNECTION_SLOTS = (0, 1)
_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class RecordedRuntimeError(ExperimentError):
    """Report a runtime-lifecycle defect without changing producer semantics."""


@dataclass(frozen=True)
class SequentialCompositionRuntime:
    """Own one persistent Scenario-A connection and its two writer surfaces."""

    connection: Any
    current_writer: Any
    frozen_writer: Any


@dataclass(frozen=True)
class ConcurrentLaneRuntime:
    """Own one persistent B/C connection and both current compositions."""

    connection_slot: int
    connection: Any
    current_writers: Mapping[Composition, Any]

    def __post_init__(self) -> None:
        if self.connection_slot not in _CONNECTION_SLOTS:
            raise ValueError("PR6 concurrent connection slot must be 0 or 1")
        if set(self.current_writers) != set(Composition):
            raise ValueError("each PR6 lane requires PRE and IN current writers")


@dataclass(frozen=True)
class LockNonAcquisitionRuntime:
    """Own the Scenario-E measured IN connection, writer, and locker connection."""

    measured_connection: Any
    measured_writer: Any
    locker_connection: Any


VerifyConnection = Callable[[Any], None]
VerifyObservation = Callable[[Any, Any, Surface, str, str], None]
ResetDatabase = Callable[[], None]
AcquireLock = Callable[[Any, str], None]
ReleaseLock = Callable[[Any], None]


@dataclass(frozen=True)
class RuntimeTopology:
    """Hold all preconstructed runtime objects and lifecycle hooks for one run.

    Connections, writers, validators, and gates must be constructed before this
    object is passed to the executor.  The executor owns neither credentials nor
    connection construction and cannot vary the fixed two-lane arrangement.
    """

    sequential: Mapping[Composition, SequentialCompositionRuntime]
    concurrent_lanes: tuple[ConcurrentLaneRuntime, ConcurrentLaneRuntime]
    lock_non_acquisition: LockNonAcquisitionRuntime
    reset_database: ResetDatabase
    verify_connection: VerifyConnection
    verify_observation: VerifyObservation
    acquire_lock: AcquireLock
    release_lock: ReleaseLock
    postgresql_server_version: str | None = None
    isolation_level: str = "UNAVAILABLE"
    autocommit: bool = False
    topology_label: str = "guarded-test-postgresql"
    connection_arrangement: str = (
        "persistent A connection per composition; two persistent B/C lane "
        "connections; separate persistent E measured and locker connections"
    )

    def __post_init__(self) -> None:
        if set(self.sequential) != set(Composition):
            raise ValueError("Scenario A requires one runtime per composition")
        slots = tuple(lane.connection_slot for lane in self.concurrent_lanes)
        if set(slots) != set(_CONNECTION_SLOTS) or len(set(slots)) != 2:
            raise ValueError("PR6 runtime requires exactly connection slots 0 and 1")
        lane_connections = tuple(lane.connection for lane in self.concurrent_lanes)
        if lane_connections[0] is lane_connections[1]:
            raise ValueError("PR6 worker lanes cannot share a connection")
        if (
            self.lock_non_acquisition.measured_connection
            is self.lock_non_acquisition.locker_connection
        ):
            raise ValueError("Scenario E requires a separate locker connection")

    def lane(self, connection_slot: int) -> ConcurrentLaneRuntime:
        """Return the preconstructed owner of one deterministic connection slot."""

        for lane in self.concurrent_lanes:
            if lane.connection_slot == connection_slot:
                return lane
        raise RecordedRuntimeError("schedule selected an unavailable connection slot")


@dataclass(frozen=True)
class RecordedExecutionResult:
    """Return the fixed raw samples and their one-shot structural validation."""

    samples: tuple[ExperimentSample, ...]
    validation: RunValidationResult


@dataclass(frozen=True)
class EvidenceWriteResult:
    """Identify one atomically completed, structurally valid evidence directory."""

    directory: Path
    manifest_path: Path
    samples_path: Path
    aggregates_path: Path


@dataclass
class _LaneTask:
    invocation: Callable[[], Any]
    completed: threading.Event = field(default_factory=threading.Event)
    value: Any = None
    error: BaseException | None = None


_STOP_WORKER = object()


class _FixedTwoLaneWorkers:
    """Keep exactly two persistent threads, each bound to one connection slot."""

    def __init__(self) -> None:
        self._queues: tuple[Queue[Any], Queue[Any]] = (Queue(), Queue())
        self._thread_ids: list[int | None] = [None, None]
        self._threads = tuple(
            threading.Thread(
                target=self._worker,
                args=(slot,),
                name=f"stage4b2-pr6-lane-{slot}",
            )
            for slot in _CONNECTION_SLOTS
        )
        for thread in self._threads:
            thread.start()

    @property
    def thread_ids(self) -> tuple[int | None, int | None]:
        """Expose thread identities for deterministic orchestration tests only."""

        return tuple(self._thread_ids)

    def run_pair(self, invocations: Mapping[int, Callable[[], Any]]) -> tuple[Any, Any]:
        """Run one callable on each fixed slot and wait without retrying either."""

        if set(invocations) != set(_CONNECTION_SLOTS):
            raise RecordedRuntimeError("a concurrent batch requires exactly slots 0 and 1")
        tasks = tuple(_LaneTask(invocations[slot]) for slot in _CONNECTION_SLOTS)
        for slot, task in zip(_CONNECTION_SLOTS, tasks, strict=True):
            self._queues[slot].put(task)
        for task in tasks:
            task.completed.wait()
        for task in tasks:
            if task.error is not None:
                raise task.error
        return tasks[0].value, tasks[1].value

    def close(self) -> None:
        """Stop only the two owned worker threads after all submitted work ends."""

        for queue in self._queues:
            queue.put(_STOP_WORKER)
        for thread in self._threads:
            thread.join()

    def _worker(self, slot: int) -> None:
        self._thread_ids[slot] = threading.get_ident()
        while True:
            item = self._queues[slot].get()
            if item is _STOP_WORKER:
                return
            task: _LaneTask = item
            try:
                task.value = task.invocation()
            except BaseException as exc:
                task.error = exc
            finally:
                task.completed.set()


class _BatchStartReference:
    """Capture one monotonic reference as the two-lane barrier releases."""

    def __init__(self, clock: Callable[[], int]) -> None:
        self._clock = clock
        self.reference_ns: int | None = None

    def mark_release(self) -> None:
        reading = self._clock()
        if type(reading) is not int:
            raise TypeError("external clock must return an integer nanosecond reading")
        self.reference_ns = reading


class _OffsetClock:
    """Record the first timer reading relative to a shared batch reference."""

    def __init__(
        self,
        *,
        clock: Callable[[], int],
        reference: _BatchStartReference,
    ) -> None:
        self._clock = clock
        self._reference = reference
        self.start_offset_ns: int | None = None

    def __call__(self) -> int:
        reading = self._clock()
        if self.start_offset_ns is None:
            reference_ns = self._reference.reference_ns
            if reference_ns is None:
                raise RecordedRuntimeError("batch reference was not captured before timing")
            offset = reading - reference_ns
            if offset < 0:
                raise RecordedRuntimeError("worker timer preceded the batch reference")
            self.start_offset_ns = offset
        return reading


class RecordedScheduleExecutor:
    """Consume exactly one accepted fixed schedule using preconstructed resources.

    The executor performs fixed warmup, a guarded reset, then Scenario A, B, C,
    and E in schedule order.  It never retries, replaces, appends, or adaptively
    extends a plan and it never implements a Scenario-D invocation surface.
    """

    def __init__(
        self,
        *,
        topology: RuntimeTopology,
        clock: Callable[[], int] = time.perf_counter_ns,
    ) -> None:
        self._topology = topology
        self._clock = clock

    def execute(
        self,
        *,
        run_id: str,
        schedule: ExperimentSchedule,
        protocol: ProtocolConfig,
    ) -> RecordedExecutionResult:
        """Warm the runtime, execute every fixed plan once, and validate once."""

        _require_safe_run_id(run_id)
        expected_schedule = generate_recorded_schedule(
            protocol=protocol,
            seed=schedule.seed,
        )
        if schedule != expected_schedule:
            raise RecordedRuntimeError(
                "executor accepts only the exact deterministic recorded schedule"
            )

        workers = _FixedTwoLaneWorkers()
        try:
            self._topology.reset_database()
            self._run_warmup(run_id=run_id, protocol=protocol, workers=workers)
            self._topology.reset_database()
            samples = self._execute_plans(
                run_id=run_id,
                schedule=schedule,
                workers=workers,
            )
        finally:
            workers.close()

        validation = validate_recorded_run(
            samples=samples,
            schedule=schedule,
            protocol=protocol,
        )
        return RecordedExecutionResult(samples=tuple(samples), validation=validation)

    def _run_warmup(
        self,
        *,
        run_id: str,
        protocol: ProtocolConfig,
        workers: _FixedTwoLaneWorkers,
    ) -> None:
        warmup_index = 0
        for _cycle in range(protocol.sequential_warmup_cycles):
            for composition in Composition:
                runtime = self._topology.sequential[composition]
                for surface in Surface:
                    request_id, order_id = _warmup_identities(run_id, warmup_index)
                    warmup_index += 1
                    writer = (
                        runtime.frozen_writer
                        if surface is Surface.FROZEN_BASELINE
                        else runtime.current_writer
                    )
                    value = _invoke_writer(
                        writer=writer,
                        surface=surface,
                        request_id=request_id,
                        order_id=order_id,
                    )
                    self._verify_after_invocation(
                        connection=runtime.connection,
                        value=value,
                        surface=surface,
                        request_id=request_id,
                        order_id=order_id,
                    )

        for composition in Composition:
            for batch in range(protocol.concurrent_warmup_batches_per_composition):
                order_id = _warmup_token(run_id, composition.value, batch, "order")
                barrier = threading.Barrier(2)
                invocations: dict[int, Callable[[], Any]] = {}
                identities: dict[int, tuple[str, str, Surface]] = {}
                for slot in _CONNECTION_SLOTS:
                    lane = self._topology.lane(slot)
                    request_id = _warmup_token(
                        run_id,
                        composition.value,
                        batch * 2 + slot,
                        "request",
                    )
                    identities[slot] = (
                        request_id,
                        order_id,
                        Surface.CURRENT_MEASURED,
                    )
                    writer = lane.current_writers[composition]
                    invocations[slot] = _untimed_after_gate(
                        barrier=barrier,
                        writer=writer,
                        request_id=request_id,
                        order_id=order_id,
                    )
                values = workers.run_pair(invocations)
                for slot, value in zip(_CONNECTION_SLOTS, values, strict=True):
                    request_id, shared_order_id, surface = identities[slot]
                    self._verify_after_invocation(
                        connection=self._topology.lane(slot).connection,
                        value=value,
                        surface=surface,
                        request_id=request_id,
                        order_id=shared_order_id,
                    )

    def _execute_plans(
        self,
        *,
        run_id: str,
        schedule: ExperimentSchedule,
        workers: _FixedTwoLaneWorkers,
    ) -> list[ExperimentSample]:
        samples: list[ExperimentSample] = []
        index = 0
        plans = schedule.samples
        while index < len(plans):
            plan = plans[index]
            if plan.scenario is Scenario.A_UNCONTENDED:
                samples.append(self._execute_scenario_a(run_id=run_id, plan=plan))
                index += 1
                continue
            if plan.scenario in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}:
                batch = plans[index : index + 2]
                _require_batch_pair(batch)
                samples.extend(
                    self._execute_concurrent_batch(
                        run_id=run_id,
                        plans=batch,
                        workers=workers,
                    )
                )
                index += 2
                continue
            if plan.scenario is Scenario.E_LOCK_NON_ACQUISITION:
                samples.append(self._execute_scenario_e(run_id=run_id, plan=plan))
                index += 1
                continue
            raise RecordedRuntimeError("Scenario D has no executor")
        return samples

    def _execute_scenario_a(
        self,
        *,
        run_id: str,
        plan: SamplePlan,
    ) -> ExperimentSample:
        runtime = self._topology.sequential[plan.composition]
        writer = (
            runtime.frozen_writer
            if plan.surface is Surface.FROZEN_BASELINE
            else runtime.current_writer
        )
        request_id, order_id = _plan_identities(run_id=run_id, plan=plan)
        timed = time_public_invocation(
            lambda: _invoke_writer(
                writer=writer,
                surface=plan.surface,
                request_id=request_id,
                order_id=order_id,
            ),
            clock=self._clock,
        )
        sample = sample_from_timed_invocation(
            run_id=run_id,
            plan=plan,
            timed=timed,
            start_offset_ns=None,
        )
        self._verify_timed_observation(
            connection=runtime.connection,
            timed=timed,
            surface=plan.surface,
            request_id=request_id,
            order_id=order_id,
        )
        return sample

    def _execute_concurrent_batch(
        self,
        *,
        run_id: str,
        plans: Sequence[SamplePlan],
        workers: _FixedTwoLaneWorkers,
    ) -> tuple[ExperimentSample, ExperimentSample]:
        reference = _BatchStartReference(self._clock)
        barrier = threading.Barrier(2, action=reference.mark_release)
        order_ids = _batch_order_ids(run_id=run_id, plans=plans)
        jobs: dict[int, Callable[[], Any]] = {}
        context_by_slot: dict[int, tuple[SamplePlan, str, str, _OffsetClock]] = {}
        for plan in plans:
            lane = self._topology.lane(plan.connection_slot)
            request_id = _plan_token(run_id, plan, "request")
            order_id = order_ids[plan.lane_index]
            offset_clock = _OffsetClock(clock=self._clock, reference=reference)
            writer = lane.current_writers[plan.composition]
            jobs[plan.connection_slot] = _timed_after_gate(
                barrier=barrier,
                writer=writer,
                request_id=request_id,
                order_id=order_id,
                clock=offset_clock,
            )
            context_by_slot[plan.connection_slot] = (
                plan,
                request_id,
                order_id,
                offset_clock,
            )

        observations = workers.run_pair(jobs)
        samples: list[ExperimentSample] = []
        for slot, timed in zip(_CONNECTION_SLOTS, observations, strict=True):
            plan, request_id, order_id, offset_clock = context_by_slot[slot]
            if offset_clock.start_offset_ns is None:
                raise RecordedRuntimeError("concurrent timer did not record a start offset")
            sample = sample_from_timed_invocation(
                run_id=run_id,
                plan=plan,
                timed=timed,
                start_offset_ns=offset_clock.start_offset_ns,
            )
            lane = self._topology.lane(slot)
            self._verify_timed_observation(
                connection=lane.connection,
                timed=timed,
                surface=plan.surface,
                request_id=request_id,
                order_id=order_id,
            )
            samples.append(sample)
        ordered = sorted(samples, key=lambda sample: sample.sample_index)
        return ordered[0], ordered[1]

    def _execute_scenario_e(
        self,
        *,
        run_id: str,
        plan: SamplePlan,
    ) -> ExperimentSample:
        runtime = self._topology.lock_non_acquisition
        request_id, order_id = _plan_identities(run_id=run_id, plan=plan)
        self._topology.acquire_lock(runtime.locker_connection, order_id)
        try:
            timed = time_public_invocation(
                lambda: _invoke_writer(
                    writer=runtime.measured_writer,
                    surface=Surface.CURRENT_MEASURED,
                    request_id=request_id,
                    order_id=order_id,
                ),
                clock=self._clock,
            )
        finally:
            self._topology.release_lock(runtime.locker_connection)

        sample = sample_from_timed_invocation(
            run_id=run_id,
            plan=plan,
            timed=timed,
            start_offset_ns=None,
        )
        self._verify_timed_observation(
            connection=runtime.measured_connection,
            timed=timed,
            surface=plan.surface,
            request_id=request_id,
            order_id=order_id,
        )
        self._topology.verify_connection(runtime.locker_connection)
        return sample

    def _verify_timed_observation(
        self,
        *,
        connection: Any,
        timed: TimedInvocation,
        surface: Surface,
        request_id: str,
        order_id: str,
    ) -> None:
        if timed.exception_type is None:
            self._topology.verify_observation(
                connection,
                timed.value,
                surface,
                request_id,
                order_id,
            )
        self._topology.verify_connection(connection)

    def _verify_after_invocation(
        self,
        *,
        connection: Any,
        value: Any,
        surface: Surface,
        request_id: str,
        order_id: str,
    ) -> None:
        self._topology.verify_observation(
            connection,
            value,
            surface,
            request_id,
            order_id,
        )
        self._topology.verify_connection(connection)


def sample_from_timed_invocation(
    *,
    run_id: str,
    plan: SamplePlan,
    timed: TimedInvocation,
    start_offset_ns: int | None,
) -> ExperimentSample:
    """Convert exact producer evidence into one immutable experiment sample."""

    if timed.exception_type is not None:
        return ExperimentSample(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            sample_index=plan.sample_index,
            block_index=plan.block_index,
            batch_index=plan.batch_index,
            lane_index=plan.lane_index,
            scenario=plan.scenario,
            composition=plan.composition,
            surface=plan.surface,
            command=CANONICAL_COMMAND,
            history_depth=CANONICAL_HISTORY_DEPTH,
            expected_sequence=CANONICAL_EXPECTED_SEQUENCE,
            producer_outcome=None,
            rejection_stage=None,
            stream_admission_verdict=None,
            append_admission_verdict=None,
            cohort=None,
            measurement_availability=None,
            external_elapsed_ns=timed.elapsed_ns,
            start_offset_ns=start_offset_ns,
            phases=None,
            exception_type=timed.exception_type,
        )

    raw_value = timed.value
    measurement_availability: str | None = None
    phases: tuple[PhaseRecord, ...] | None = None
    if plan.surface is Surface.CURRENT_MEASURED:
        measurement_availability = _enum_value(
            getattr(raw_value, "availability", None)
        )
        if measurement_availability not in {"AVAILABLE", "UNAVAILABLE"}:
            raise RecordedRuntimeError("measured producer returned invalid availability")
        if measurement_availability == "AVAILABLE":
            measurement = getattr(raw_value, "measurement", None)
            if measurement is None:
                raise RecordedRuntimeError("AVAILABLE delivery omitted measurement")
            phases = tuple(
                _phase_record(name, getattr(measurement, name, None))
                for name in PR3_PHASE_NAMES
            )
        producer_value = getattr(raw_value, "producer_value", None)
    else:
        producer_value = raw_value

    producer_outcome = _enum_value(getattr(producer_value, "outcome", None))
    stream_admission_verdict = _nested_verdict(
        getattr(producer_value, "stream_admission_result", None)
    )
    append_admission_verdict = _nested_verdict(
        getattr(producer_value, "admission_result", None)
    )
    rejection_stage = _rejection_stage(
        producer_outcome=producer_outcome,
        stream_admission_verdict=stream_admission_verdict,
        append_admission_verdict=append_admission_verdict,
    )
    cohort: Cohort | None = None
    try:
        cohort = classify_cohort(
            producer_outcome=producer_outcome,
            rejection_stage=rejection_stage,
            stream_admission_verdict=stream_admission_verdict,
            append_admission_verdict=append_admission_verdict,
        )
    except UnsupportedCohortError:
        pass

    return ExperimentSample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        sample_index=plan.sample_index,
        block_index=plan.block_index,
        batch_index=plan.batch_index,
        lane_index=plan.lane_index,
        scenario=plan.scenario,
        composition=plan.composition,
        surface=plan.surface,
        command=CANONICAL_COMMAND,
        history_depth=CANONICAL_HISTORY_DEPTH,
        expected_sequence=CANONICAL_EXPECTED_SEQUENCE,
        producer_outcome=producer_outcome,
        rejection_stage=rejection_stage,
        stream_admission_verdict=stream_admission_verdict,
        append_admission_verdict=append_admission_verdict,
        cohort=cohort,
        measurement_availability=measurement_availability,
        external_elapsed_ns=timed.elapsed_ns,
        start_offset_ns=start_offset_ns,
        phases=phases,
    )


def write_evidence_directory(
    *,
    output_root: Path,
    run_id: str,
    manifest: EnvironmentManifest,
    execution: RecordedExecutionResult,
    schedule: ExperimentSchedule,
    protocol: ProtocolConfig,
) -> EvidenceWriteResult | None:
    """Atomically publish valid evidence, or publish nothing for a stopped run.

    Each file is completed and renamed inside a hidden staging directory.  The
    directory itself becomes visible under ``run_id`` only after every payload
    succeeds.  A process interruption may leave a hidden staging directory but
    cannot leave a complete-looking final run directory.
    """

    _require_safe_run_id(run_id)
    validation = validate_recorded_run(
        samples=execution.samples,
        schedule=schedule,
        protocol=protocol,
    )
    if validation != execution.validation:
        raise RecordedRuntimeError("execution validation changed before evidence write")
    if validation.status is not EvidenceStatus.VALID:
        return None
    if any(sample.run_id != run_id for sample in execution.samples):
        raise RecordedRuntimeError("sample run_id does not match evidence directory")

    aggregates: tuple[AggregateResult, ...] = aggregate_samples(execution.samples)
    paired: tuple[PairedDifferenceResult, ...] = aggregate_paired_differences(
        execution.samples
    )
    payloads = {
        "manifest.json": manifest_to_json(manifest),
        "samples.jsonl": samples_to_jsonl(execution.samples),
        "aggregates.json": aggregates_to_json(aggregates, paired),
    }

    output_root.mkdir(parents=True, exist_ok=True)
    final_directory = output_root / run_id
    if final_directory.exists():
        raise FileExistsError("refusing to overwrite an existing evidence run")
    staging_directory = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.staging-", dir=output_root)
    )
    for name, payload in payloads.items():
        _atomic_write_text(staging_directory / name, payload)
    _fsync_directory(staging_directory)
    os.replace(staging_directory, final_directory)
    _fsync_directory(output_root)
    return EvidenceWriteResult(
        directory=final_directory,
        manifest_path=final_directory / "manifest.json",
        samples_path=final_directory / "samples.jsonl",
        aggregates_path=final_directory / "aggregates.json",
    )


def build_recorded_run_manifest(
    *,
    topology: RuntimeTopology,
    schedule: ExperimentSchedule,
    protocol: ProtocolConfig,
) -> EnvironmentManifest:
    """Capture sanitized source and runtime facts immediately before a real run."""

    source_commit, source_tree_clean = _source_identity()
    return build_environment_manifest(
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean,
        topology_label=topology.topology_label,
        schema_or_migration_identity=SCHEMA_OR_MIGRATION_IDENTITY,
        isolation_level=topology.isolation_level,
        autocommit=topology.autocommit,
        connection_arrangement=topology.connection_arrangement,
        schedule_seed=schedule.seed,
        protocol=protocol,
        postgresql_server_version=topology.postgresql_server_version,
    )


@contextmanager
def open_postgres_runtime(database_url: str) -> Any:
    """Construct the accepted real PostgreSQL topology before warmup.

    The URL is passed only to the connection constructor and is never retained,
    serialized, or exposed.  Opening verifies the `_test` guard but performs no
    reset, warmup, timed invocation, sample emission, or aggregate generation.
    """

    if not isinstance(database_url, str) or not database_url:
        raise RecordedRuntimeError("test database configuration is absent")
    from src.storage.postgres_connection import connect_postgres

    loaded: LoadedBaseline | None = None
    connections: list[Any] = []
    try:
        loaded = load_frozen_baseline()
        for _purpose in range(6):
            connection = connect_postgres(database_url)
            connections.append(connection)
            _guard_preflight_test_database(connection)

        sequential_connections = {
            Composition.PRE_OCC: connections[0],
            Composition.IN_PESSIMISTIC: connections[1],
        }
        sequential: dict[Composition, SequentialCompositionRuntime] = {}
        for composition, connection in sequential_connections.items():
            current_writer, frozen_writer = _build_preflight_writers(
                connection=connection,
                composition=composition,
                loaded=loaded,
            )
            sequential[composition] = SequentialCompositionRuntime(
                connection=connection,
                current_writer=current_writer,
                frozen_writer=frozen_writer,
            )

        concurrent_lanes = tuple(
            ConcurrentLaneRuntime(
                connection_slot=slot,
                connection=connections[2 + slot],
                current_writers={
                    composition: _build_current_writer(
                        connection=connections[2 + slot],
                        composition=composition,
                    )
                    for composition in Composition
                },
            )
            for slot in _CONNECTION_SLOTS
        )
        lock_runtime = LockNonAcquisitionRuntime(
            measured_connection=connections[4],
            measured_writer=_build_current_writer(
                connection=connections[4],
                composition=Composition.IN_PESSIMISTIC,
            ),
            locker_connection=connections[5],
        )
        control_connection = sequential[Composition.PRE_OCC].connection
        server_version, isolation_level = _postgres_runtime_facts(control_connection)
        topology = RuntimeTopology(
            sequential=sequential,
            concurrent_lanes=(concurrent_lanes[0], concurrent_lanes[1]),
            lock_non_acquisition=lock_runtime,
            reset_database=lambda: _guarded_postgres_reset(
                control_connection=control_connection,
                all_connections=tuple(connections),
            ),
            verify_connection=_require_select_one_and_restore_idle,
            verify_observation=_verify_postgres_observation,
            acquire_lock=_acquire_postgres_advisory_lock,
            release_lock=_release_postgres_advisory_lock,
            postgresql_server_version=server_version,
            isolation_level=isolation_level,
            autocommit=bool(control_connection.autocommit),
        )
        yield topology
    finally:
        for connection in connections:
            connection.close()
        if loaded is not None:
            unload_frozen_baseline(loaded)


def _build_current_writer(*, connection: Any, composition: Composition) -> Any:
    from src.pipeline.transactional.postgres_write_side import (
        PostgresTransactionalWriteSide,
    )
    from src.pipeline.transactional.postgres_write_side_config import (
        PostgresWriteSideConfig,
        ValidationPlacement,
    )

    placement = (
        ValidationPlacement.PRE_TRANSACTION
        if composition is Composition.PRE_OCC
        else ValidationPlacement.IN_TRANSACTION
    )
    writer = PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=_build_preflight_validation_runtime(),
        admission_gate_factory=_preflight_admission_gate_factory(composition),
        config=PostgresWriteSideConfig(validation_placement=placement),
    )
    if type(writer) is not PostgresTransactionalWriteSide:
        raise RecordedRuntimeError("recorded current writer is not the exact class")
    if getattr(writer, "_connection", None) is not connection:
        raise RecordedRuntimeError("recorded writer does not own the planned connection")
    return writer


def _invoke_writer(
    *,
    writer: Any,
    surface: Surface,
    request_id: str,
    order_id: str,
) -> Any:
    if surface is Surface.CURRENT_MEASURED:
        return writer.create_order_with_measurement(
            request_id=request_id,
            order_id=order_id,
            amount=CANONICAL_AMOUNT,
        )
    return writer.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=CANONICAL_AMOUNT,
    )


def _timed_after_gate(
    *,
    barrier: threading.Barrier,
    writer: Any,
    request_id: str,
    order_id: str,
    clock: Callable[[], int],
) -> Callable[[], TimedInvocation]:
    def invoke() -> TimedInvocation:
        return time_after_start_gate(
            wait_for_start=barrier.wait,
            invocation=lambda: _invoke_writer(
                writer=writer,
                surface=Surface.CURRENT_MEASURED,
                request_id=request_id,
                order_id=order_id,
            ),
            clock=clock,
        )

    return invoke


def _untimed_after_gate(
    *,
    barrier: threading.Barrier,
    writer: Any,
    request_id: str,
    order_id: str,
) -> Callable[[], Any]:
    def invoke() -> Any:
        barrier.wait()
        return _invoke_writer(
            writer=writer,
            surface=Surface.CURRENT_MEASURED,
            request_id=request_id,
            order_id=order_id,
        )

    return invoke


def _phase_record(name: str, phase: Any) -> PhaseRecord:
    state = _enum_value(getattr(phase, "state", None))
    try:
        phase_state = PhaseState(state)
    except ValueError as exc:
        raise RecordedRuntimeError(f"invalid PR3 phase state for {name}") from exc
    return PhaseRecord(
        name=name,
        state=phase_state,
        elapsed_ns=getattr(phase, "elapsed_ns", None),
    )


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        raise RecordedRuntimeError("producer evidence contained an invalid enum value")
    return raw


def _nested_verdict(value: Any) -> str | None:
    if value is None:
        return None
    return _enum_value(getattr(value, "verdict", None))


def _rejection_stage(
    *,
    producer_outcome: str,
    stream_admission_verdict: str | None,
    append_admission_verdict: str | None,
) -> RejectionStage | None:
    if producer_outcome != "ADMISSION_REJECTED":
        return None
    if append_admission_verdict is not None:
        return RejectionStage.APPEND
    if stream_admission_verdict is not None:
        return RejectionStage.PREPARE_STREAM
    return None


def _plan_identities(*, run_id: str, plan: SamplePlan) -> tuple[str, str]:
    return _plan_token(run_id, plan, "request"), _plan_token(run_id, plan, "order")


def _plan_token(run_id: str, plan: SamplePlan, purpose: str) -> str:
    token = deterministic_sample_token(
        run_id=run_id,
        sample_index=plan.sample_index,
        lane_index=plan.lane_index,
        purpose=purpose,
    )
    return f"pr6-{purpose}-{token}"


def _batch_order_ids(*, run_id: str, plans: Sequence[SamplePlan]) -> dict[int, str]:
    first = min(plans, key=lambda plan: plan.sample_index)
    if first.scenario is Scenario.B_SAME_ORDER:
        shared = _plan_token(run_id, first, "shared-order")
        return {0: shared, 1: shared}
    if first.scenario is Scenario.C_DIFFERENT_ORDER:
        return {plan.lane_index: _plan_token(run_id, plan, "order") for plan in plans}
    raise RecordedRuntimeError("only Scenario B/C define concurrent order identities")


def _warmup_identities(run_id: str, index: int) -> tuple[str, str]:
    return (
        _warmup_token(run_id, "sequential", index, "request"),
        _warmup_token(run_id, "sequential", index, "order"),
    )


def _warmup_token(run_id: str, group: str, index: int, purpose: str) -> str:
    token = deterministic_sample_token(
        run_id=f"{run_id}|warmup|{group}",
        sample_index=index,
        lane_index=0,
        purpose=purpose,
    )
    return f"pr6-warmup-{purpose}-{token}"


def _require_batch_pair(plans: Sequence[SamplePlan]) -> None:
    if len(plans) != 2:
        raise RecordedRuntimeError("a B/C batch must contain exactly two plans")
    first, second = plans
    if (
        first.scenario is not second.scenario
        or first.composition is not second.composition
        or first.batch_index != second.batch_index
        or {first.lane_index, second.lane_index} != {0, 1}
        or {first.connection_slot, second.connection_slot} != {0, 1}
    ):
        raise RecordedRuntimeError("concurrent schedule pair is structurally invalid")


def _require_safe_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or _SAFE_RUN_ID.fullmatch(run_id) is None:
        raise ValueError("run_id must be a path-safe non-empty identifier")


def _atomic_write_text(path: Path, payload: str) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, path)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _source_identity() -> tuple[str, bool]:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RecordedRuntimeError("source commit is not a full Git object identity")
    return commit, status == ""


def _postgres_runtime_facts(connection: Any) -> tuple[str | None, str]:
    server_version = getattr(connection.info, "server_version", None)
    with connection.cursor() as cursor:
        cursor.execute("SHOW transaction_isolation")
        row = cursor.fetchone()
    connection.rollback()
    _require_select_one_and_restore_idle(connection)
    isolation = row[0] if row and isinstance(row[0], str) else "UNAVAILABLE"
    return (
        None if server_version is None else str(server_version),
        isolation.upper().replace(" ", "_"),
    )


def _guarded_postgres_reset(
    *,
    control_connection: Any,
    all_connections: Sequence[Any],
) -> None:
    for connection in all_connections:
        _require_select_one_and_restore_idle(connection)
    _guard_preflight_test_database(control_connection)
    with control_connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE
                decision_receipts,
                projection_snapshots,
                projection_order_progress,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
    control_connection.commit()
    for connection in all_connections:
        _require_select_one_and_restore_idle(connection)


def _acquire_postgres_advisory_lock(connection: Any, order_id: str) -> None:
    from psycopg.pq import TransactionStatus

    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise RecordedRuntimeError("Scenario-E locker was not IDLE before setup")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))
            """,
            ("order_events_stream", order_id),
        )


def _release_postgres_advisory_lock(connection: Any) -> None:
    from psycopg.pq import TransactionStatus

    connection.rollback()
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise RecordedRuntimeError("Scenario-E locker did not return to IDLE")


def _verify_postgres_observation(
    connection: Any,
    raw_value: Any,
    surface: Surface,
    request_id: str,
    order_id: str,
) -> None:
    from psycopg.pq import TransactionStatus
    from src.storage.postgres_event_store import PostgresEventStore

    producer_value = (
        getattr(raw_value, "producer_value", None)
        if surface is Surface.CURRENT_MEASURED
        else raw_value
    )
    outcome = _enum_value(getattr(producer_value, "outcome", None))
    event = getattr(producer_value, "accepted_event", None)
    validation = getattr(producer_value, "validation_decision", None)
    validation_result = getattr(validation, "validation_result", None)
    if validation_result is not None:
        _require_strict_full_proof_validation(validation_result)
    elif outcome == "ACCEPTED":
        raise RecordedRuntimeError("accepted CREATE omitted validation evidence")
    if outcome == "ACCEPTED":
        if (
            event is None
            or event.request_id != request_id
            or event.order_id != order_id
            or event.sequence != CANONICAL_EXPECTED_SEQUENCE
            or str(event.amount) != str(CANONICAL_AMOUNT)
        ):
            raise RecordedRuntimeError("accepted CREATE returned an unexpected event")
    try:
        history = PostgresEventStore(connection).load(order_id)
    finally:
        connection.rollback()
    if outcome == "ACCEPTED":
        if history != [event]:
            raise RecordedRuntimeError("accepted CREATE did not persist exactly once")
    elif any(observed.request_id == request_id for observed in history):
        raise RecordedRuntimeError("rejected CREATE request appeared in accepted history")
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise RecordedRuntimeError("persistence verification did not restore IDLE")
