"""Experiment-only infrastructure for Stage 4B.2 PR6.

This module owns deterministic accounting for the future controlled PostgreSQL
comparison.  It deliberately does not connect to PostgreSQL, construct a
production writer, run a benchmark, choose a strategy, or authorize additional
samples after a fixed protocol completes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from importlib import metadata
from itertools import permutations
import json
from pathlib import Path
import platform as platform_module
import random
import statistics
import sys
import time
from types import ModuleType
from typing import Any, TypeVar


# Version 1 remains mutable only until PR6 emits its first canonical recorded run.
SCHEMA_VERSION = 1
FIXED_PR6_WORKER_COUNT = 2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SOURCE_PATH = (
    PROJECT_ROOT
    / "tests/fixtures/stage4b2_measurement/"
    "postgres_write_side_pr3_baseline.py.source"
)
BASELINE_PROVENANCE_PATH = (
    PROJECT_ROOT / "tests/fixtures/stage4b2_measurement/provenance.json"
)

EXPECTED_BASELINE_SHA256 = (
    "34bac8a3e67d6a43f870d26ae48642ff1893c5360cbf3ec2c0e1f1cd6630196d"
)
EXPECTED_BASELINE_GIT_BLOB = "c1706c1ce5f498d45301263450b4df2f27d28753"
EXPECTED_BASELINE_PR4_BASE_HEAD = (
    "fd3733d57ff82beeaf9d54446924f8830c49db76"
)
EXPECTED_BASELINE_ROLE = "frozen experiment-only pre-PR4 source reference"
EXPECTED_BASELINE_SOURCE_PATH = "src/pipeline/transactional/postgres_write_side.py"
EXPECTED_BASELINE_SNAPSHOT_PATH = (
    "tests/fixtures/stage4b2_measurement/"
    "postgres_write_side_pr3_baseline.py.source"
)
EXPECTED_BASELINE_SOURCE_STATE = (
    "committed Stage 4B.2 PR3 parent before PR4 instrumentation"
)
EXPECTED_BASELINE_MAINTENANCE_POLICY = (
    "intentionally frozen; never track production changes or receive bug fixes"
)
DEFAULT_BASELINE_MODULE_NAME = (
    "_stage4b2_pr6_frozen_postgres_write_side_"
    f"{EXPECTED_BASELINE_SHA256[:12]}"
)
PRODUCTION_WRITE_SIDE_MODULE_NAME = (
    "src.pipeline.transactional.postgres_write_side"
)

PR3_PHASE_NAMES = (
    "producer_write_invocation",
    "business_uow",
    "validation_runtime_call",
    "preliminary_idempotency_check",
    "preliminary_read_cleanup",
    "authoritative_idempotency_check",
    "accepted_history_load",
    "concurrency_preparation_call",
    "pessimistic_advisory_try_lock_call",
    "append_admission_call",
    "idempotency_record_call",
    "commit_finalization",
    "rollback_finalization",
)


class ExperimentError(RuntimeError):
    """Base error for experiment-owned validation and loading failures."""


class UnsupportedCohortError(ExperimentError):
    """Raised when producer evidence is not an accepted PR6 latency cohort."""


class BaselineIntegrityError(ExperimentError):
    """Raised when frozen-baseline content or provenance is not exact."""


class BaselineLoadError(ExperimentError):
    """Raised when the verified baseline cannot load in an isolated namespace."""


class PreflightError(ExperimentError):
    """Raised when untimed PostgreSQL compatibility evidence is not coherent."""


class PreflightSafetyError(PreflightError):
    """Raised before writes when the connected database fails the test guard."""


class Composition(str, Enum):
    """Identify one canonical composition only inside the PR6 experiment."""

    PRE_OCC = "PRE_OCC"
    IN_PESSIMISTIC = "IN_PESSIMISTIC"


class Surface(str, Enum):
    """Identify one observer-effect execution surface."""

    FROZEN_BASELINE = "FROZEN_BASELINE"
    CURRENT_UNMEASURED = "CURRENT_UNMEASURED"
    CURRENT_MEASURED = "CURRENT_MEASURED"


class Scenario(str, Enum):
    """Identify one fixed PR6 scenario; D is intentionally absent."""

    A_UNCONTENDED = "A_UNCONTENDED"
    B_SAME_ORDER = "B_SAME_ORDER"
    C_DIFFERENT_ORDER = "C_DIFFERENT_ORDER"
    E_LOCK_NON_ACQUISITION = "E_LOCK_NON_ACQUISITION"


class RejectionStage(str, Enum):
    """Identify where a typed admission rejection returned."""

    APPEND = "append"
    PREPARE_STREAM = "prepare_stream"


class Cohort(str, Enum):
    """Identify one non-pooled PR6 latency cohort."""

    ACCEPTED = "ACCEPTED"
    APPEND_STALE_WRITE = "ADMISSION_REJECTED_APPEND_STALE_WRITE"
    PREPARE_LOCK_TIMEOUT = "ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT"


class PhaseState(str, Enum):
    """Mirror the four PR3 measurement-presence meanings for raw evidence."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REACHED = "NOT_REACHED"
    NOT_COLLECTED = "NOT_COLLECTED"
    MEASURED = "MEASURED"


class EvidenceStatus(str, Enum):
    """Distinguish a valid run from invalid or insufficient evidence."""

    VALID = "VALID"
    INVALID_RUN = "INVALID_RUN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class PhaseRecord:
    """Represent one named PR3 phase without losing absence semantics."""

    name: str
    state: PhaseState
    elapsed_ns: int | None

    def __post_init__(self) -> None:
        if self.name not in PR3_PHASE_NAMES:
            raise ValueError(f"unknown PR3 phase: {self.name}")
        if self.state is PhaseState.MEASURED:
            _require_non_negative_int(self.elapsed_ns, "elapsed_ns")
        elif self.elapsed_ns is not None:
            raise ValueError("unmeasured phase state requires elapsed_ns=None")


@dataclass(frozen=True)
class ExperimentSample:
    """Store one future raw invocation sample as immutable experiment evidence.

    ``sample_index``, ``batch_index``, and ``lane_index`` are experiment-local
    accounting coordinates.  They do not identify a governed execution or
    retry attempt.  Exception markers retain only a type name and invalidate
    the run; they never become latency cohorts.
    """

    schema_version: int
    run_id: str
    sample_index: int
    block_index: int
    batch_index: int
    lane_index: int
    scenario: Scenario
    composition: Composition
    surface: Surface
    command: str
    history_depth: int
    expected_sequence: int
    producer_outcome: str | None
    rejection_stage: RejectionStage | None
    stream_admission_verdict: str | None
    append_admission_verdict: str | None
    cohort: Cohort | None
    measurement_availability: str | None
    external_elapsed_ns: int
    start_offset_ns: int | None
    phases: tuple[PhaseRecord, ...] | None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        for name in ("sample_index", "block_index", "batch_index", "lane_index"):
            _require_non_negative_int(getattr(self, name), name)
        _require_non_negative_int(self.history_depth, "history_depth")
        _require_positive_int(self.expected_sequence, "expected_sequence")
        _require_non_negative_int(self.external_elapsed_ns, "external_elapsed_ns")
        if self.start_offset_ns is not None:
            _require_non_negative_int(self.start_offset_ns, "start_offset_ns")
        if not self.command:
            raise ValueError("command must not be empty")

        if self.phases is not None:
            names = tuple(phase.name for phase in self.phases)
            if len(names) != len(set(names)):
                raise ValueError("phases must not contain duplicate names")
            if set(names) != set(PR3_PHASE_NAMES):
                raise ValueError("available measured phases must contain all PR3 fields")

        if self.exception_type is not None:
            if not isinstance(self.exception_type, str) or not self.exception_type:
                raise ValueError("exception_type must be a non-empty class name")
            if self.producer_outcome is not None or self.cohort is not None:
                raise ValueError(
                    "exception evidence requires null producer outcome and cohort"
                )
            if any(
                value is not None
                for value in (
                    self.rejection_stage,
                    self.stream_admission_verdict,
                    self.append_admission_verdict,
                    self.measurement_availability,
                    self.phases,
                )
            ):
                raise ValueError(
                    "exception evidence has no normal result or measurement delivery"
                )
            return

        if not isinstance(self.producer_outcome, str) or not self.producer_outcome:
            raise ValueError("normal sample producer_outcome must be non-empty")
        if self.surface is Surface.CURRENT_MEASURED:
            if self.measurement_availability not in {"AVAILABLE", "UNAVAILABLE"}:
                raise ValueError(
                    "current measured samples require explicit availability"
                )
            if self.measurement_availability == "AVAILABLE" and self.phases is None:
                raise ValueError("available measurement requires all phases")
            if self.measurement_availability == "UNAVAILABLE" and self.phases is not None:
                raise ValueError("unavailable measurement requires phases=None")
        elif self.measurement_availability is not None or self.phases is not None:
            raise ValueError(
                "frozen and current-unmeasured samples serialize measurement as null"
            )

        if self.cohort is not None:
            classified = classify_cohort(
                producer_outcome=self.producer_outcome,
                rejection_stage=self.rejection_stage,
                stream_admission_verdict=self.stream_admission_verdict,
                append_admission_verdict=self.append_admission_verdict,
            )
            if classified is not self.cohort:
                raise ValueError("cohort does not match deterministic classification")


@dataclass(frozen=True)
class ProtocolConfig:
    """Hold bounded PR6 counts without turning them into performance contracts."""

    sequential_warmup_cycles: int = 5
    concurrent_warmup_batches_per_composition: int = 3
    observer_schedule_repetitions: int = 5
    scenario_a_samples_per_surface_per_composition: int = 30
    scenario_b_batches_per_composition: int = 30
    scenario_c_batches_per_composition: int = 30
    scenario_e_samples: int = 30
    scenario_b_core_cohort_minimum: int = 20
    worker_count: int = FIXED_PR6_WORKER_COUNT

    def __post_init__(self) -> None:
        for name in (
            "sequential_warmup_cycles",
            "concurrent_warmup_batches_per_composition",
            "observer_schedule_repetitions",
            "scenario_a_samples_per_surface_per_composition",
            "scenario_b_batches_per_composition",
            "scenario_c_batches_per_composition",
            "scenario_e_samples",
            "scenario_b_core_cohort_minimum",
        ):
            _require_positive_int(getattr(self, name), name)
        if self.worker_count != FIXED_PR6_WORKER_COUNT:
            raise ValueError("Stage 4B.2 PR6 worker_count is fixed at 2")
        expected_a = self.observer_schedule_repetitions * 6
        if self.scenario_a_samples_per_surface_per_composition != expected_a:
            raise ValueError(
                "Scenario A count must equal six observer permutations per repetition"
            )
        if (
            self.scenario_b_core_cohort_minimum
            > self.scenario_b_batches_per_composition
        ):
            raise ValueError(
                "Scenario B cohort minimum cannot exceed fixed batches per composition"
            )


@dataclass(frozen=True)
class SamplePlan:
    """Describe one deterministic future sample without executing it."""

    sample_index: int
    block_index: int
    batch_index: int
    lane_index: int
    connection_slot: int
    scenario: Scenario
    composition: Composition
    surface: Surface


@dataclass(frozen=True)
class ExperimentSchedule:
    """Hold the complete fixed recorded schedule for one PR6 run."""

    seed: int
    worker_count: int
    samples: tuple[SamplePlan, ...]


@dataclass(frozen=True)
class TimedInvocation:
    """Retain external elapsed evidence for one normal or exceptional invocation.

    Ordinary ``Exception`` instances retain only their class name. Tracebacks,
    messages, and arbitrary representations do not enter experiment evidence.
    Process-control ``BaseException`` subclasses remain outside this model.
    """

    value: Any | None
    elapsed_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int(self.elapsed_ns, "elapsed_ns")
        if self.exception_type is None:
            if self.value is None:
                raise ValueError("normal invocation observation requires a value")
            return
        if not isinstance(self.exception_type, str) or not self.exception_type:
            raise ValueError("exception_type must be a non-empty class name")
        if self.value is not None:
            raise ValueError("exceptional invocation observation has no value")


@dataclass(frozen=True)
class PreflightCellResult:
    """Report structural compatibility for one untimed preflight cell."""

    surface: Surface
    composition: Composition
    accepted: bool
    expected_sequence_one: bool
    event_persisted: bool
    connection_idle: bool
    connection_reusable: bool
    measurement_available: bool | None
    baseline_verified: bool | None

    def __post_init__(self) -> None:
        for name in (
            "accepted",
            "expected_sequence_one",
            "event_persisted",
            "connection_idle",
            "connection_reusable",
        ):
            if getattr(self, name) is not True:
                raise PreflightError(f"preflight cell failed structural check: {name}")
        if self.surface is Surface.CURRENT_MEASURED:
            if self.measurement_available is not True:
                raise PreflightError("measured preflight cell must be AVAILABLE")
        elif self.measurement_available is not None:
            raise PreflightError("unmeasured preflight cells use measurement N/A")
        if self.surface is Surface.FROZEN_BASELINE:
            if self.baseline_verified is not True:
                raise PreflightError("frozen preflight cell must verify its baseline")
        elif self.baseline_verified is not None:
            raise PreflightError("current preflight cells use baseline verification N/A")


@dataclass(frozen=True)
class PostgresPreflightResult:
    """Report the six-cell compatibility preflight without latency evidence."""

    cells: tuple[PreflightCellResult, ...]
    same_connection_sequential_reuse: bool
    frozen_current_compatible: bool
    canonical_pre_compatible: bool
    canonical_in_pessimistic_compatible: bool
    current_measured_available: bool

    def __post_init__(self) -> None:
        expected_cells = {
            (surface, composition)
            for surface in Surface
            for composition in Composition
        }
        observed_cells = {
            (cell.surface, cell.composition) for cell in self.cells
        }
        if len(self.cells) != 6 or observed_cells != expected_cells:
            raise PreflightError("preflight must contain exactly six unique cells")
        for name in (
            "same_connection_sequential_reuse",
            "frozen_current_compatible",
            "canonical_pre_compatible",
            "canonical_in_pessimistic_compatible",
            "current_measured_available",
        ):
            if getattr(self, name) is not True:
                raise PreflightError(f"preflight summary failed: {name}")


@dataclass(frozen=True)
class BaselineProvenance:
    """Represent the exact accepted identity of the frozen PR3 source."""

    artifact_role: str
    source_path: str
    snapshot_path: str
    sha256: str
    git_blob: str
    pr4_base_head: str
    source_state: str
    maintenance_policy: str


@dataclass(frozen=True)
class LoadedBaseline:
    """Return one verified isolated baseline module and its provenance."""

    module_name: str
    module: ModuleType
    provenance: BaselineProvenance


@dataclass(frozen=True)
class NamedCount:
    """Name one manifest protocol count without a mutable mapping."""

    name: str
    count: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("count name must not be empty")
        _require_non_negative_int(self.count, "count")


@dataclass(frozen=True)
class EnvironmentManifest:
    """Store sanitized method and environment metadata for one future run."""

    schema_version: int
    source_commit: str
    source_tree_clean_before_run: bool
    baseline_sha256: str
    baseline_git_blob: str
    python_implementation: str
    python_version: str
    psycopg_version: str
    postgresql_server_version: str | None
    platform: str
    architecture: str
    topology_label: str
    schema_or_migration_identity: str
    isolation_level: str
    autocommit: bool
    connection_arrangement: str
    validator: str
    validation_runtime: str
    validation_mode: str
    command: str
    amount: str
    history_depth: int
    timer_source: str
    preflight_counts: tuple[NamedCount, ...]
    warmup_counts: tuple[NamedCount, ...]
    recorded_counts: tuple[NamedCount, ...]
    schedule_seed: int
    ordering_method: str
    worker_count: int
    stop_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.worker_count != FIXED_PR6_WORKER_COUNT:
            raise ValueError("manifest worker_count must be 2 for PR6")
        _require_non_negative_int(self.history_depth, "history_depth")
        if type(self.source_tree_clean_before_run) is not bool:
            raise TypeError("source_tree_clean_before_run must be bool")
        if type(self.autocommit) is not bool:
            raise TypeError("autocommit must be bool")
        if not self.stop_rules:
            raise ValueError("manifest must record stop rules")
        _reject_secret_shaped_manifest_values(self)


@dataclass(frozen=True)
class DescriptiveStatistics:
    """Store the default PR6 descriptive statistics; p95 is intentionally absent."""

    count: int
    minimum_ns: int
    maximum_ns: int
    mean_ns: float
    median_ns: float


@dataclass(frozen=True)
class PhaseAggregate:
    """Aggregate one internal phase independently without interval summation."""

    phase_name: str
    statistics: DescriptiveStatistics


@dataclass(frozen=True)
class AggregateResult:
    """Store one exact comparable cohort's descriptive evidence."""

    run_id: str
    scenario: Scenario
    surface: Surface
    composition: Composition
    command: str
    history_depth: int
    expected_sequence: int
    cohort: Cohort
    external_elapsed: DescriptiveStatistics
    phases: tuple[PhaseAggregate, ...]


@dataclass(frozen=True)
class PairedDifferenceResult:
    """Describe matched IN-minus-PRE external differences for Scenario A."""

    run_id: str
    scenario: Scenario
    surface: Surface
    command: str
    history_depth: int
    expected_sequence: int
    cohort: Cohort
    count: int
    mean_in_minus_pre_ns: float
    median_in_minus_pre_ns: float


@dataclass(frozen=True)
class ValidationIssue:
    """Record one deterministic run-accounting defect or insufficiency."""

    code: str
    detail: str


@dataclass(frozen=True)
class RunValidationResult:
    """Return invalid-run and insufficient-evidence findings separately."""

    status: EvidenceStatus
    issues: tuple[ValidationIssue, ...]


def classify_cohort(
    *,
    producer_outcome: str,
    rejection_stage: RejectionStage | None,
    stream_admission_verdict: str | None,
    append_admission_verdict: str | None,
) -> Cohort:
    """Classify only accepted PR6 latency cohorts and reject every other outcome."""

    if (
        producer_outcome == "ACCEPTED"
        and rejection_stage is None
        and stream_admission_verdict == "ADMITTED"
        and append_admission_verdict == "ADMITTED"
    ):
        return Cohort.ACCEPTED
    if (
        producer_outcome == "ADMISSION_REJECTED"
        and rejection_stage is RejectionStage.APPEND
        and append_admission_verdict == "STALE_WRITE"
        and stream_admission_verdict == "ADMITTED"
    ):
        return Cohort.APPEND_STALE_WRITE
    if (
        producer_outcome == "ADMISSION_REJECTED"
        and rejection_stage is RejectionStage.PREPARE_STREAM
        and stream_admission_verdict == "LOCK_TIMEOUT"
        and append_admission_verdict is None
    ):
        return Cohort.PREPARE_LOCK_TIMEOUT
    raise UnsupportedCohortError(
        "producer evidence is replay, conflict, unsupported, or not a retained "
        "PR6 latency cohort"
    )


def is_derived_scenario_d(sample: ExperimentSample) -> bool:
    """Return whether a natural Scenario-B PRE stale sample explains mechanism D."""

    return (
        sample.scenario is Scenario.B_SAME_ORDER
        and sample.composition is Composition.PRE_OCC
        and sample.cohort is Cohort.APPEND_STALE_WRITE
    )


def generate_sequential_observer_schedule(
    *,
    seed: int,
    repetitions: int = 5,
    start_sample_index: int = 0,
) -> tuple[SamplePlan, ...]:
    """Generate all six observer permutations with alternating composition order."""

    _require_positive_int(repetitions, "repetitions")
    _require_non_negative_int(start_sample_index, "start_sample_index")
    rng = random.Random(seed)
    surface_permutations = list(permutations(tuple(Surface)))
    plans: list[SamplePlan] = []
    sample_index = start_sample_index

    for repetition in range(repetitions):
        ordered_permutations = list(surface_permutations)
        rng.shuffle(ordered_permutations)
        for permutation_position, surface_order in enumerate(ordered_permutations):
            round_index = repetition * len(surface_permutations) + permutation_position
            composition_order = (
                (Composition.PRE_OCC, Composition.IN_PESSIMISTIC)
                if round_index % 2 == 0
                else (Composition.IN_PESSIMISTIC, Composition.PRE_OCC)
            )
            for surface in surface_order:
                for composition in composition_order:
                    plans.append(
                        SamplePlan(
                            sample_index=sample_index,
                            block_index=repetition,
                            batch_index=round_index,
                            lane_index=0,
                            connection_slot=0,
                            scenario=Scenario.A_UNCONTENDED,
                            composition=composition,
                            surface=surface,
                        )
                    )
                    sample_index += 1
    return tuple(plans)


def generate_concurrent_batch_schedule(
    *,
    scenario: Scenario,
    batches_per_composition: int,
    start_sample_index: int = 0,
) -> tuple[SamplePlan, ...]:
    """Generate fixed two-lane B/C batches without a worker-count parameter."""

    if scenario not in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}:
        raise ValueError("concurrent PR6 schedule supports only Scenario B or C")
    _require_positive_int(batches_per_composition, "batches_per_composition")
    _require_non_negative_int(start_sample_index, "start_sample_index")
    plans: list[SamplePlan] = []
    sample_index = start_sample_index

    for matched_round in range(batches_per_composition):
        composition_order = (
            (Composition.PRE_OCC, Composition.IN_PESSIMISTIC)
            if matched_round % 2 == 0
            else (Composition.IN_PESSIMISTIC, Composition.PRE_OCC)
        )
        for composition_position, composition in enumerate(composition_order):
            batch_index = matched_round * 2 + composition_position
            connection_slots = (0, 1) if batch_index % 2 == 0 else (1, 0)
            for lane_index, connection_slot in enumerate(connection_slots):
                plans.append(
                    SamplePlan(
                        sample_index=sample_index,
                        block_index=matched_round,
                        batch_index=batch_index,
                        lane_index=lane_index,
                        connection_slot=connection_slot,
                        scenario=scenario,
                        composition=composition,
                        surface=Surface.CURRENT_MEASURED,
                    )
                )
                sample_index += 1
    return tuple(plans)


def generate_scenario_e_schedule(
    *,
    sample_count: int,
    start_sample_index: int = 0,
) -> tuple[SamplePlan, ...]:
    """Generate fixed IN/measured lock-non-acquisition sample plans."""

    _require_positive_int(sample_count, "sample_count")
    _require_non_negative_int(start_sample_index, "start_sample_index")
    return tuple(
        SamplePlan(
            sample_index=start_sample_index + index,
            block_index=index // 5,
            batch_index=index,
            lane_index=0,
            connection_slot=0,
            scenario=Scenario.E_LOCK_NON_ACQUISITION,
            composition=Composition.IN_PESSIMISTIC,
            surface=Surface.CURRENT_MEASURED,
        )
        for index in range(sample_count)
    )


def generate_recorded_schedule(
    *,
    protocol: ProtocolConfig,
    seed: int,
) -> ExperimentSchedule:
    """Generate the entire fixed run; observed outcomes cannot extend this schedule."""

    sequential = generate_sequential_observer_schedule(
        seed=seed,
        repetitions=protocol.observer_schedule_repetitions,
    )
    scenario_b = generate_concurrent_batch_schedule(
        scenario=Scenario.B_SAME_ORDER,
        batches_per_composition=protocol.scenario_b_batches_per_composition,
        start_sample_index=len(sequential),
    )
    scenario_c = generate_concurrent_batch_schedule(
        scenario=Scenario.C_DIFFERENT_ORDER,
        batches_per_composition=protocol.scenario_c_batches_per_composition,
        start_sample_index=len(sequential) + len(scenario_b),
    )
    scenario_e = generate_scenario_e_schedule(
        sample_count=protocol.scenario_e_samples,
        start_sample_index=len(sequential) + len(scenario_b) + len(scenario_c),
    )
    return ExperimentSchedule(
        seed=seed,
        worker_count=protocol.worker_count,
        samples=(*sequential, *scenario_b, *scenario_c, *scenario_e),
    )


def deterministic_sample_token(
    *,
    run_id: str,
    sample_index: int,
    lane_index: int,
    purpose: str,
) -> str:
    """Return a fixed-width experiment token generated outside invocation timing."""

    if not run_id or not purpose:
        raise ValueError("run_id and purpose must not be empty")
    _require_non_negative_int(sample_index, "sample_index")
    _require_non_negative_int(lane_index, "lane_index")
    material = f"{run_id}|{sample_index}|{lane_index}|{purpose}".encode("utf-8")
    return sha256(material).hexdigest()[:32]


T = TypeVar("T")


def time_public_invocation(
    invocation: Callable[[], T],
    *,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> TimedInvocation:
    """Time one public call and retain ordinary exceptions as invalid evidence."""

    started_ns = _read_external_clock(clock)
    try:
        value = invocation()
    except Exception as exc:
        stopped_ns = _read_external_clock(clock)
        elapsed_ns = _external_elapsed(started_ns, stopped_ns)
        return TimedInvocation(
            value=None,
            elapsed_ns=elapsed_ns,
            exception_type=type(exc).__name__,
        )
    stopped_ns = _read_external_clock(clock)
    return TimedInvocation(
        value=value,
        elapsed_ns=_external_elapsed(started_ns, stopped_ns),
    )


def time_after_start_gate(
    *,
    wait_for_start: Callable[[], object],
    invocation: Callable[[], T],
    clock: Callable[[], int] = time.perf_counter_ns,
) -> TimedInvocation:
    """Wait at the future B/C start gate before starting external timing."""

    wait_for_start()
    return time_public_invocation(invocation, clock=clock)


def verify_baseline_fixture(
    *,
    source_path: Path = BASELINE_SOURCE_PATH,
    provenance_path: Path = BASELINE_PROVENANCE_PATH,
) -> BaselineProvenance:
    """Verify frozen source bytes and every accepted historical identity field."""

    try:
        raw_provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineIntegrityError("baseline provenance is unreadable") from exc
    if not isinstance(raw_provenance, dict):
        raise BaselineIntegrityError("baseline provenance must be a JSON object")

    try:
        provenance = BaselineProvenance(**raw_provenance)
    except (TypeError, ValueError) as exc:
        raise BaselineIntegrityError("baseline provenance shape is invalid") from exc

    expected = BaselineProvenance(
        artifact_role=EXPECTED_BASELINE_ROLE,
        source_path=EXPECTED_BASELINE_SOURCE_PATH,
        snapshot_path=EXPECTED_BASELINE_SNAPSHOT_PATH,
        sha256=EXPECTED_BASELINE_SHA256,
        git_blob=EXPECTED_BASELINE_GIT_BLOB,
        pr4_base_head=EXPECTED_BASELINE_PR4_BASE_HEAD,
        source_state=EXPECTED_BASELINE_SOURCE_STATE,
        maintenance_policy=EXPECTED_BASELINE_MAINTENANCE_POLICY,
    )
    if provenance != expected:
        raise BaselineIntegrityError("baseline provenance does not match accepted PR4 metadata")

    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise BaselineIntegrityError("frozen baseline source is unreadable") from exc
    observed_sha256 = sha256(source_bytes).hexdigest()
    if observed_sha256 != provenance.sha256:
        raise BaselineIntegrityError(
            "frozen baseline SHA-256 does not match accepted provenance"
        )
    return provenance


def load_frozen_baseline(
    *,
    source_path: Path = BASELINE_SOURCE_PATH,
    provenance_path: Path = BASELINE_PROVENANCE_PATH,
    module_name: str = DEFAULT_BASELINE_MODULE_NAME,
) -> LoadedBaseline:
    """Compile and execute the verified snapshot in one isolated module namespace."""

    provenance = verify_baseline_fixture(
        source_path=source_path,
        provenance_path=provenance_path,
    )
    if (
        module_name == PRODUCTION_WRITE_SIDE_MODULE_NAME
        or not module_name.startswith("_stage4b2_pr6_frozen_")
        or module_name in sys.modules
    ):
        raise BaselineLoadError("baseline module name is not fresh and experiment-isolated")

    try:
        source_text = source_path.read_text(encoding="utf-8")
        code = compile(source_text, str(source_path), "exec", dont_inherit=True)
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise BaselineLoadError("verified frozen baseline cannot compile") from exc

    module = ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise BaselineLoadError(
            "verified frozen baseline is incompatible with current dependencies"
        ) from exc
    return LoadedBaseline(
        module_name=module_name,
        module=module,
        provenance=provenance,
    )


def unload_frozen_baseline(loaded: LoadedBaseline) -> None:
    """Remove only the exact experiment module installed by the isolated loader."""

    if sys.modules.get(loaded.module_name) is loaded.module:
        del sys.modules[loaded.module_name]


def preflight_surface_order(composition: Composition) -> tuple[Surface, ...]:
    """Return the fixed sequential surface order for one preflight connection.

    PRE proves frozen-to-current reuse. IN proves current-to-frozen reuse. Both
    orders execute the same three cells exactly once and never imply benchmark
    ordering or recorded experiment scheduling.
    """

    if composition is Composition.PRE_OCC:
        return (
            Surface.FROZEN_BASELINE,
            Surface.CURRENT_UNMEASURED,
            Surface.CURRENT_MEASURED,
        )
    if composition is Composition.IN_PESSIMISTIC:
        return (
            Surface.CURRENT_UNMEASURED,
            Surface.CURRENT_MEASURED,
            Surface.FROZEN_BASELINE,
        )
    raise TypeError("composition must be a PR6 Composition")


def run_postgres_preflight(database_url: str) -> PostgresPreflightResult:
    """Run six untimed compatibility cells against one guarded test database.

    The supplied URL is consumed only by the connection constructor and is
    never retained, serialized, or printed. This function creates six fresh
    accepted CREATE records. It performs no warmup, external timing, raw-sample
    generation, aggregation, comparison, cleanup truncation, or concurrency.
    """

    if not isinstance(database_url, str) or not database_url:
        raise PreflightSafetyError("test database configuration is absent")

    from src.storage.postgres_connection import connect_postgres

    loaded = load_frozen_baseline()
    cells: list[PreflightCellResult] = []
    try:
        for composition in Composition:
            connection = connect_postgres(database_url)
            try:
                _guard_preflight_test_database(connection)
                current_writer, frozen_writer = _build_preflight_writers(
                    connection=connection,
                    composition=composition,
                    loaded=loaded,
                )
                for surface in preflight_surface_order(composition):
                    writer = (
                        frozen_writer
                        if surface is Surface.FROZEN_BASELINE
                        else current_writer
                    )
                    cells.append(
                        _run_preflight_cell(
                            connection=connection,
                            writer=writer,
                            surface=surface,
                            composition=composition,
                            loaded=loaded,
                        )
                    )
            finally:
                connection.close()
    finally:
        unload_frozen_baseline(loaded)

    return PostgresPreflightResult(
        cells=tuple(cells),
        same_connection_sequential_reuse=True,
        frozen_current_compatible=True,
        canonical_pre_compatible=True,
        canonical_in_pessimistic_compatible=True,
        current_measured_available=True,
    )


def run_postgres_preflight_from_environment() -> PostgresPreflightResult:
    """Run the preflight using only inherited ``TEST_DATABASE_URL`` state."""

    import os

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise PreflightSafetyError(
            "CURRENT CODEX PROCESS DOES NOT HAVE TEST_DATABASE_URL"
        )
    return run_postgres_preflight(database_url)


def format_postgres_preflight(result: PostgresPreflightResult) -> str:
    """Format structural preflight facts without latency or connection metadata."""

    lines = ["PR6 untimed PostgreSQL preflight: PASS"]
    for cell in result.cells:
        measurement = (
            "yes" if cell.measurement_available is True else "not-applicable"
        )
        baseline = "yes" if cell.baseline_verified is True else "not-applicable"
        lines.append(
            " ".join(
                (
                    f"surface={cell.surface.value}",
                    f"composition={cell.composition.value}",
                    "accepted=yes",
                    "sequence_one=yes",
                    "persisted=yes",
                    "connection_idle=yes",
                    "connection_reusable=yes",
                    f"measurement_available={measurement}",
                    f"baseline_verified={baseline}",
                )
            )
        )
    lines.extend(
        (
            "same_connection_sequential_reuse=yes",
            "frozen_current_compatible=yes",
            "canonical_pre_compatible=yes",
            "canonical_in_pessimistic_compatible=yes",
            "current_measured_available=yes",
            "recorded_comparison=NOT_STARTED",
            "empirical_result=NONE",
        )
    )
    return "\n".join(lines)


def _guard_preflight_test_database(connection: Any) -> None:
    """Apply the repository's `_test` guard before any preflight write."""

    from psycopg.pq import TransactionStatus

    database_name: object = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
        if row is not None:
            database_name = row[0]
    finally:
        if connection.info.transaction_status is not TransactionStatus.IDLE:
            connection.rollback()

    if not isinstance(database_name, str) or not database_name.endswith("_test"):
        raise PreflightSafetyError(
            "refusing PR6 preflight because database name does not end with _test"
        )
    if connection.autocommit:
        raise PreflightSafetyError("PR6 preflight requires autocommit disabled")
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise PreflightError("test-database guard did not restore connection IDLE")


def _build_preflight_writers(
    *,
    connection: Any,
    composition: Composition,
    loaded: LoadedBaseline,
) -> tuple[Any, Any]:
    """Build separate current/frozen writers on one sequential connection."""

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
    config = PostgresWriteSideConfig(validation_placement=placement)
    admission_gate_factory = _preflight_admission_gate_factory(composition)
    current_runtime = _build_preflight_validation_runtime()
    frozen_runtime = _build_preflight_validation_runtime()
    _require_equivalent_validation_stacks(current_runtime, frozen_runtime)

    current_writer = PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=current_runtime,
        admission_gate_factory=admission_gate_factory,
        config=config,
    )
    frozen_writer_class = getattr(
        loaded.module,
        "PostgresTransactionalWriteSide",
        None,
    )
    if (
        frozen_writer_class is None
        or frozen_writer_class.__module__ != loaded.module_name
        or loaded.module_name == PRODUCTION_WRITE_SIDE_MODULE_NAME
    ):
        raise PreflightError("frozen writer class is not isolated historical source")
    frozen_writer = frozen_writer_class(
        connection=connection,
        validation_runtime=frozen_runtime,
        admission_gate_factory=admission_gate_factory,
        config=config,
    )
    if type(current_writer) is not PostgresTransactionalWriteSide:
        raise PreflightError("current writer is not the exact production class")
    if type(frozen_writer) is not frozen_writer_class:
        raise PreflightError("frozen writer is not the exact isolated class")
    if (
        getattr(current_writer, "_connection", None) is not connection
        or getattr(frozen_writer, "_connection", None) is not connection
    ):
        raise PreflightError("current and frozen writers must share one connection")
    return current_writer, frozen_writer


def _build_preflight_validation_runtime() -> Any:
    """Construct one real, preflight-owned FullProofValidator STRICT stack."""

    from src.compass.transition.runtime import (
        ValidationDispatcher,
        ValidationPolicy,
        ValidationRuntime,
    )
    from src.compass.transition.types import ValidationMode
    from src.compass.transition.validators import FullProofValidator, NoOpValidator

    dispatcher = ValidationDispatcher(
        strict_validator=FullProofValidator(),
        off_validator=NoOpValidator(),
    )
    return ValidationRuntime(
        dispatcher=dispatcher,
        policy=ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )


def _require_equivalent_validation_stacks(current: Any, frozen: Any) -> None:
    """Fail unless separate current/frozen stacks have exact equivalent types."""

    current_shape = (
        type(current),
        type(current.dispatcher),
        type(current.dispatcher.strict_validator),
        type(current.dispatcher.off_validator),
        type(current.policy),
        current.mode,
    )
    frozen_shape = (
        type(frozen),
        type(frozen.dispatcher),
        type(frozen.dispatcher.strict_validator),
        type(frozen.dispatcher.off_validator),
        type(frozen.policy),
        frozen.mode,
    )
    if current is frozen or current_shape != frozen_shape:
        raise PreflightError(
            "current and frozen validation stacks must be separate and equivalent"
        )


def _preflight_admission_gate_factory(
    composition: Composition,
) -> Callable[[Any], Any]:
    """Return a factory for the exact current canonical PostgreSQL gate class."""

    from src.pipeline.transactional.postgres_admission import (
        PostgresOptimisticAdmissionGate,
        PostgresPessimisticAdmissionGate,
    )

    if composition is Composition.PRE_OCC:
        def _optimistic(uow: Any) -> Any:
            gate = PostgresOptimisticAdmissionGate(uow.event_store)
            if type(gate) is not PostgresOptimisticAdmissionGate:
                raise PreflightError("PRE gate is not exact current optimistic class")
            return gate

        return _optimistic

    if composition is Composition.IN_PESSIMISTIC:
        def _pessimistic(uow: Any) -> Any:
            gate = PostgresPessimisticAdmissionGate(
                connection=uow.connection,
                event_store=uow.event_store,
            )
            if type(gate) is not PostgresPessimisticAdmissionGate:
                raise PreflightError("IN gate is not exact current pessimistic class")
            return gate

        return _pessimistic

    raise TypeError("composition must be a PR6 Composition")


def _run_preflight_cell(
    *,
    connection: Any,
    writer: Any,
    surface: Surface,
    composition: Composition,
    loaded: LoadedBaseline,
) -> PreflightCellResult:
    """Execute one fresh, untimed CREATE cell and verify durable structure."""

    from decimal import Decimal
    from uuid import uuid4

    from psycopg.pq import TransactionStatus

    token = uuid4().hex
    request_id = f"pr6-preflight-request-{token}"
    order_id = f"pr6-preflight-order-{token}"
    measurement_available: bool | None = None
    if surface is Surface.CURRENT_MEASURED:
        delivery = writer.create_order_with_measurement(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
        producer_value = _require_available_measurement(delivery, composition)
        measurement_available = True
    else:
        producer_value = writer.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )

    _require_accepted_create(
        producer_value,
        request_id=request_id,
        order_id=order_id,
    )
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise PreflightError("producer invocation did not return connection IDLE")
    _require_select_one_and_restore_idle(connection)
    _require_persisted_event(
        connection,
        producer_value.accepted_event,
        order_id=order_id,
        request_id=request_id,
    )
    _require_select_one_and_restore_idle(connection)

    baseline_verified: bool | None = None
    if surface is Surface.FROZEN_BASELINE:
        if type(writer).__module__ != loaded.module_name:
            raise PreflightError("frozen cell substituted a non-historical writer")
        baseline_verified = True
    else:
        from src.pipeline.transactional.postgres_write_side import (
            PostgresTransactionalWriteSide,
        )

        if type(writer) is not PostgresTransactionalWriteSide:
            raise PreflightError("current cell substituted a non-current writer")

    return PreflightCellResult(
        surface=surface,
        composition=composition,
        accepted=True,
        expected_sequence_one=True,
        event_persisted=True,
        connection_idle=True,
        connection_reusable=True,
        measurement_available=measurement_available,
        baseline_verified=baseline_verified,
    )


def _require_available_measurement(delivery: Any, composition: Composition) -> Any:
    """Validate current AVAILABLE delivery shape without comparing elapsed values."""

    from src.pipeline.transactional.postgres_write_side_measurement import (
        PostgresWriteSideMeasurementAvailability,
        PostgresWriteSidePhaseMeasurementState,
    )

    if (
        delivery.availability
        is not PostgresWriteSideMeasurementAvailability.AVAILABLE
        or delivery.measurement is None
    ):
        raise PreflightError("current measured preflight delivery is not AVAILABLE")
    measurement = delivery.measurement
    required = REQUIRED_MEASURED_PHASES[(composition, Cohort.ACCEPTED)]
    for phase_name in PR3_PHASE_NAMES:
        phase = getattr(measurement, phase_name, None)
        if phase is None:
            raise PreflightError("current measured preflight shape is incomplete")
        if phase.state is PostgresWriteSidePhaseMeasurementState.NOT_COLLECTED:
            raise PreflightError("current measured preflight retained NOT_COLLECTED")
        if (
            phase_name in required
            and phase.state is not PostgresWriteSidePhaseMeasurementState.MEASURED
        ):
            raise PreflightError("current measured preflight lost a required phase")
    return delivery.producer_value


def _require_accepted_create(
    producer_value: Any,
    *,
    request_id: str,
    order_id: str,
) -> None:
    """Validate one normal accepted CREATE result without timing interpretation."""

    event = getattr(producer_value, "accepted_event", None)
    outcome = getattr(getattr(producer_value, "outcome", None), "value", None)
    stream_verdict = getattr(
        getattr(producer_value, "stream_admission_result", None),
        "verdict",
        None,
    )
    append_verdict = getattr(
        getattr(producer_value, "admission_result", None),
        "verdict",
        None,
    )
    validation = getattr(producer_value, "validation_decision", None)
    validation_result = getattr(validation, "validation_result", None)
    if outcome != "ACCEPTED" or event is None:
        raise PreflightError("preflight CREATE did not return ACCEPTED")
    if (
        event.request_id != request_id
        or event.order_id != order_id
        or event.sequence != 1
        or str(event.amount) != "100.00"
    ):
        raise PreflightError("preflight CREATE returned an unexpected event shape")
    if (
        getattr(stream_verdict, "value", None) != "ADMITTED"
        or getattr(append_verdict, "value", None) != "ADMITTED"
    ):
        raise PreflightError("preflight CREATE did not use admitted stream/append paths")
    _require_strict_full_proof_validation(validation_result)


def _require_strict_full_proof_validation(validation_result: Any) -> None:
    """Require the real strict validator and enum member without serialization."""

    from src.compass.transition.types import ValidationMode

    if getattr(validation_result, "validator_name", None) != "FullProofValidator":
        raise PreflightError("preflight CREATE did not use FullProofValidator")
    if (
        getattr(validation_result, "validation_mode", None)
        is not ValidationMode.STRICT
    ):
        raise PreflightError(
            "preflight CREATE did not use ValidationMode.STRICT"
        )


def _require_select_one_and_restore_idle(connection: Any) -> None:
    """Prove one connection remains usable and restore it to IDLE."""

    from psycopg.pq import TransactionStatus

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
    if row != (1,):
        raise PreflightError("post-invocation SELECT 1 did not succeed")
    connection.rollback()
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise PreflightError("post-invocation SELECT 1 did not restore IDLE")


def _require_persisted_event(
    connection: Any,
    expected_event: Any,
    *,
    order_id: str,
    request_id: str,
) -> None:
    """Verify exactly one accepted event and restore the read transaction IDLE."""

    from psycopg.pq import TransactionStatus

    from src.storage.postgres_event_store import PostgresEventStore

    try:
        history = PostgresEventStore(connection).load(order_id)
    finally:
        connection.rollback()
    if (
        history != [expected_event]
        or history[0].request_id != request_id
        or history[0].sequence != 1
    ):
        raise PreflightError("accepted preflight event did not persist exactly")
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise PreflightError("persistence verification did not restore IDLE")


DEFAULT_STOP_RULES = (
    "baseline integrity or isolated-load preflight fails",
    "canonical composition or lifecycle invariants cannot be enforced",
    "setup, coordination, or cleanup enters an invocation timer",
    "a recorded block is incomplete, duplicated, or adaptively extended",
    "a measured sample is unavailable or loses a required phase reading",
    "Scenario B returns an unexpected exception or insufficient core cohorts",
    "fixed two-worker coordination is not credible in the recorded environment",
    "the method begins varying worker count or characterizing saturation",
)


def build_environment_manifest(
    *,
    source_commit: str,
    source_tree_clean_before_run: bool,
    topology_label: str,
    schema_or_migration_identity: str,
    isolation_level: str,
    autocommit: bool,
    connection_arrangement: str,
    schedule_seed: int,
    protocol: ProtocolConfig | None = None,
    postgresql_server_version: str | None = None,
    psycopg_version: str | None = None,
    python_implementation: str | None = None,
    python_version: str | None = None,
    platform: str | None = None,
    architecture: str | None = None,
) -> EnvironmentManifest:
    """Build a sanitized manifest without reading database credentials or hostname."""

    if protocol is None:
        protocol = ProtocolConfig()
    if psycopg_version is None:
        try:
            psycopg_version = metadata.version("psycopg")
        except metadata.PackageNotFoundError:
            psycopg_version = "UNAVAILABLE"
    preflight_counts = (
        NamedCount("sequential_samples_per_surface_composition_cell", 1),
        NamedCount("surface_composition_cells", 6),
    )
    warmup_counts = (
        NamedCount("sequential_cycles", protocol.sequential_warmup_cycles),
        NamedCount(
            "concurrent_batches_per_composition",
            protocol.concurrent_warmup_batches_per_composition,
        ),
    )
    recorded_counts = (
        NamedCount(
            "scenario_a_samples_per_surface_per_composition",
            protocol.scenario_a_samples_per_surface_per_composition,
        ),
        NamedCount(
            "scenario_b_batches_per_composition",
            protocol.scenario_b_batches_per_composition,
        ),
        NamedCount(
            "scenario_c_batches_per_composition",
            protocol.scenario_c_batches_per_composition,
        ),
        NamedCount("scenario_e_samples", protocol.scenario_e_samples),
        NamedCount(
            "scenario_b_core_cohort_minimum",
            protocol.scenario_b_core_cohort_minimum,
        ),
    )
    return EnvironmentManifest(
        schema_version=SCHEMA_VERSION,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        baseline_sha256=EXPECTED_BASELINE_SHA256,
        baseline_git_blob=EXPECTED_BASELINE_GIT_BLOB,
        python_implementation=(
            python_implementation or platform_module.python_implementation()
        ),
        python_version=python_version or platform_module.python_version(),
        psycopg_version=psycopg_version,
        postgresql_server_version=postgresql_server_version,
        platform=platform or platform_module.system(),
        architecture=architecture or platform_module.machine(),
        topology_label=topology_label,
        schema_or_migration_identity=schema_or_migration_identity,
        isolation_level=isolation_level,
        autocommit=autocommit,
        connection_arrangement=connection_arrangement,
        validator="FullProofValidator",
        validation_runtime="ValidationRuntime+ValidationDispatcher+ValidationPolicy",
        validation_mode="STRICT",
        command="CREATE",
        amount="100.00",
        history_depth=0,
        timer_source="time.perf_counter_ns",
        preflight_counts=preflight_counts,
        warmup_counts=warmup_counts,
        recorded_counts=recorded_counts,
        schedule_seed=schedule_seed,
        ordering_method=(
            "seeded six-surface-permutation cycles; alternating PRE/IN order; "
            "alternating fixed two-lane B/C batches"
        ),
        worker_count=protocol.worker_count,
        stop_rules=DEFAULT_STOP_RULES,
    )


def sample_to_dict(sample: ExperimentSample) -> dict[str, Any]:
    """Convert one sample to a stable JSON-ready mapping."""

    phases = None
    if sample.phases is not None:
        by_name = {phase.name: phase for phase in sample.phases}
        phases = {
            name: {
                "state": by_name[name].state.value,
                "elapsed_ns": by_name[name].elapsed_ns,
            }
            for name in PR3_PHASE_NAMES
        }
    return {
        "schema_version": sample.schema_version,
        "run_id": sample.run_id,
        "sample_index": sample.sample_index,
        "block_index": sample.block_index,
        "batch_index": sample.batch_index,
        "lane_index": sample.lane_index,
        "scenario": sample.scenario.value,
        "composition": sample.composition.value,
        "surface": sample.surface.value,
        "command": sample.command,
        "history_depth": sample.history_depth,
        "expected_sequence": sample.expected_sequence,
        "producer_outcome": sample.producer_outcome,
        "rejection_stage": (
            None if sample.rejection_stage is None else sample.rejection_stage.value
        ),
        "stream_admission_verdict": sample.stream_admission_verdict,
        "append_admission_verdict": sample.append_admission_verdict,
        "cohort": None if sample.cohort is None else sample.cohort.value,
        "measurement_availability": sample.measurement_availability,
        "external_elapsed_ns": sample.external_elapsed_ns,
        "start_offset_ns": sample.start_offset_ns,
        "phases": phases,
        "exception_type": sample.exception_type,
    }


def sample_from_dict(raw: Mapping[str, Any]) -> ExperimentSample:
    """Reconstruct one sample from deterministic JSON data."""

    raw_phases = raw.get("phases")
    phases = None
    if raw_phases is not None:
        if not isinstance(raw_phases, Mapping):
            raise ValueError("phases must be an object or null")
        phases = tuple(
            PhaseRecord(
                name=name,
                state=PhaseState(raw_phases[name]["state"]),
                elapsed_ns=raw_phases[name]["elapsed_ns"],
            )
            for name in PR3_PHASE_NAMES
        )
    rejection_stage = raw.get("rejection_stage")
    cohort = raw.get("cohort")
    return ExperimentSample(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        sample_index=raw["sample_index"],
        block_index=raw["block_index"],
        batch_index=raw["batch_index"],
        lane_index=raw["lane_index"],
        scenario=Scenario(raw["scenario"]),
        composition=Composition(raw["composition"]),
        surface=Surface(raw["surface"]),
        command=raw["command"],
        history_depth=raw["history_depth"],
        expected_sequence=raw["expected_sequence"],
        producer_outcome=raw["producer_outcome"],
        rejection_stage=(
            None if rejection_stage is None else RejectionStage(rejection_stage)
        ),
        stream_admission_verdict=raw.get("stream_admission_verdict"),
        append_admission_verdict=raw.get("append_admission_verdict"),
        cohort=None if cohort is None else Cohort(cohort),
        measurement_availability=raw.get("measurement_availability"),
        external_elapsed_ns=raw["external_elapsed_ns"],
        start_offset_ns=raw.get("start_offset_ns"),
        phases=phases,
        exception_type=raw.get("exception_type"),
    )


def samples_to_jsonl(samples: Iterable[ExperimentSample]) -> str:
    """Serialize exactly one sample object per deterministic JSONL line."""

    lines = [
        json.dumps(sample_to_dict(sample), sort_keys=True, separators=(",", ":"))
        for sample in samples
    ]
    return "" if not lines else "\n".join(lines) + "\n"


def samples_from_jsonl(payload: str) -> tuple[ExperimentSample, ...]:
    """Deserialize deterministic JSONL without accepting blank interior records."""

    if not payload:
        return ()
    lines = payload.splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("JSONL must not contain blank sample lines")
    return tuple(sample_from_dict(json.loads(line)) for line in lines)


def manifest_to_dict(manifest: EnvironmentManifest) -> dict[str, Any]:
    """Convert the fixed sanitized manifest schema to JSON-ready data."""

    return {
        "schema_version": manifest.schema_version,
        "source_commit": manifest.source_commit,
        "source_tree_clean_before_run": manifest.source_tree_clean_before_run,
        "baseline_sha256": manifest.baseline_sha256,
        "baseline_git_blob": manifest.baseline_git_blob,
        "python_implementation": manifest.python_implementation,
        "python_version": manifest.python_version,
        "psycopg_version": manifest.psycopg_version,
        "postgresql_server_version": manifest.postgresql_server_version,
        "platform": manifest.platform,
        "architecture": manifest.architecture,
        "topology_label": manifest.topology_label,
        "schema_or_migration_identity": manifest.schema_or_migration_identity,
        "isolation_level": manifest.isolation_level,
        "autocommit": manifest.autocommit,
        "connection_arrangement": manifest.connection_arrangement,
        "validator": manifest.validator,
        "validation_runtime": manifest.validation_runtime,
        "validation_mode": manifest.validation_mode,
        "command": manifest.command,
        "amount": manifest.amount,
        "history_depth": manifest.history_depth,
        "timer_source": manifest.timer_source,
        "preflight_counts": _counts_to_dict(manifest.preflight_counts),
        "warmup_counts": _counts_to_dict(manifest.warmup_counts),
        "recorded_counts": _counts_to_dict(manifest.recorded_counts),
        "schedule_seed": manifest.schedule_seed,
        "ordering_method": manifest.ordering_method,
        "worker_count": manifest.worker_count,
        "stop_rules": list(manifest.stop_rules),
    }


def manifest_to_json(manifest: EnvironmentManifest) -> str:
    """Serialize one sanitized manifest with stable keys and a final newline."""

    return json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"


def aggregate_samples(samples: Sequence[ExperimentSample]) -> tuple[AggregateResult, ...]:
    """Aggregate exact cohorts without pooling outcomes or summing internal phases."""

    grouped: dict[
        tuple[str, Scenario, Surface, Composition, str, int, int, Cohort],
        list[ExperimentSample],
    ] = defaultdict(list)
    for sample in samples:
        if sample.exception_type is not None or sample.cohort is None:
            raise ValueError("invalid or unsupported samples cannot be aggregated")
        if not _cohort_allowed_for_scenario(sample):
            raise ValueError("sample cohort is not retained for its scenario/composition")
        if (
            sample.surface is Surface.CURRENT_MEASURED
            and sample.measurement_availability != "AVAILABLE"
        ):
            raise ValueError("unavailable measured samples cannot be aggregated")
        key = (
            sample.run_id,
            sample.scenario,
            sample.surface,
            sample.composition,
            sample.command,
            sample.history_depth,
            sample.expected_sequence,
            sample.cohort,
        )
        grouped[key].append(sample)

    results: list[AggregateResult] = []
    for key in sorted(grouped, key=lambda item: tuple(_sort_value(part) for part in item)):
        (
            run_id,
            scenario,
            surface,
            composition,
            command,
            history_depth,
            expected_sequence,
            cohort,
        ) = key
        cohort_samples = grouped[key]
        phase_aggregates: list[PhaseAggregate] = []
        for phase_name in PR3_PHASE_NAMES:
            elapsed_values = [
                phase.elapsed_ns
                for sample in cohort_samples
                for phase in (sample.phases or ())
                if phase.name == phase_name and phase.state is PhaseState.MEASURED
            ]
            if elapsed_values:
                phase_aggregates.append(
                    PhaseAggregate(
                        phase_name=phase_name,
                        statistics=_describe([int(value) for value in elapsed_values]),
                    )
                )
        results.append(
            AggregateResult(
                run_id=run_id,
                scenario=scenario,
                surface=surface,
                composition=composition,
                command=command,
                history_depth=history_depth,
                expected_sequence=expected_sequence,
                cohort=cohort,
                external_elapsed=_describe(
                    [sample.external_elapsed_ns for sample in cohort_samples]
                ),
                phases=tuple(phase_aggregates),
            )
        )
    return tuple(results)


def aggregate_paired_differences(
    samples: Sequence[ExperimentSample],
) -> tuple[PairedDifferenceResult, ...]:
    """Aggregate matched Scenario-A IN-minus-PRE external elapsed differences."""

    pairs: dict[
        tuple[str, Surface, str, int, int, Cohort, int],
        dict[Composition, ExperimentSample],
    ] = defaultdict(dict)
    for sample in samples:
        if sample.scenario is not Scenario.A_UNCONTENDED:
            continue
        if sample.cohort is None or sample.exception_type is not None:
            raise ValueError("invalid Scenario A sample cannot form a pair")
        key = (
            sample.run_id,
            sample.surface,
            sample.command,
            sample.history_depth,
            sample.expected_sequence,
            sample.cohort,
            sample.batch_index,
        )
        if sample.composition in pairs[key]:
            raise ValueError("matched Scenario A pair contains a duplicate composition")
        pairs[key][sample.composition] = sample

    differences: dict[
        tuple[str, Surface, str, int, int, Cohort],
        list[int],
    ] = defaultdict(list)
    for key, by_composition in pairs.items():
        if set(by_composition) != set(Composition):
            raise ValueError("matched Scenario A pair is incomplete")
        (
            run_id,
            surface,
            command,
            history_depth,
            expected_sequence,
            cohort,
            _batch_index,
        ) = key
        difference = (
            by_composition[Composition.IN_PESSIMISTIC].external_elapsed_ns
            - by_composition[Composition.PRE_OCC].external_elapsed_ns
        )
        differences[
            (run_id, surface, command, history_depth, expected_sequence, cohort)
        ].append(difference)

    return tuple(
        PairedDifferenceResult(
            run_id=key[0],
            scenario=Scenario.A_UNCONTENDED,
            surface=key[1],
            command=key[2],
            history_depth=key[3],
            expected_sequence=key[4],
            cohort=key[5],
            count=len(values),
            mean_in_minus_pre_ns=statistics.fmean(values),
            median_in_minus_pre_ns=float(statistics.median(values)),
        )
        for key, values in sorted(
            differences.items(), key=lambda item: tuple(_sort_value(part) for part in item[0])
        )
    )


def aggregates_to_json(
    aggregates: Sequence[AggregateResult],
    paired_differences: Sequence[PairedDifferenceResult] = (),
) -> str:
    """Serialize descriptive aggregates without thresholds, p95, or decisions."""

    payload = {
        "schema_version": SCHEMA_VERSION,
        "aggregates": [_aggregate_to_dict(result) for result in aggregates],
        "paired_differences": [
            {
                "run_id": result.run_id,
                "scenario": result.scenario.value,
                "surface": result.surface.value,
                "command": result.command,
                "history_depth": result.history_depth,
                "expected_sequence": result.expected_sequence,
                "cohort": result.cohort.value,
                "count": result.count,
                "mean_in_minus_pre_ns": result.mean_in_minus_pre_ns,
                "median_in_minus_pre_ns": result.median_in_minus_pre_ns,
            }
            for result in paired_differences
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


REQUIRED_MEASURED_PHASES: Mapping[
    tuple[Composition, Cohort], frozenset[str]
] = {
    (Composition.PRE_OCC, Cohort.ACCEPTED): frozenset(
        {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        }
    ),
    (Composition.IN_PESSIMISTIC, Cohort.ACCEPTED): frozenset(
        {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        }
    ),
    (Composition.PRE_OCC, Cohort.APPEND_STALE_WRITE): frozenset(
        {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "append_admission_call",
            "rollback_finalization",
        }
    ),
    (Composition.IN_PESSIMISTIC, Cohort.PREPARE_LOCK_TIMEOUT): frozenset(
        {
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "rollback_finalization",
        }
    ),
}


def validate_recorded_run(
    *,
    samples: Sequence[ExperimentSample],
    schedule: ExperimentSchedule,
    protocol: ProtocolConfig,
) -> RunValidationResult:
    """Validate fixed accounting and report insufficiency without running more work."""

    invalid: list[ValidationIssue] = []
    insufficient: list[ValidationIssue] = []
    if schedule.worker_count != FIXED_PR6_WORKER_COUNT:
        invalid.append(
            ValidationIssue("INVALID_WORKER_COUNT", "PR6 schedule worker_count must be 2")
        )

    plan_by_index: dict[int, SamplePlan] = {}
    for plan in schedule.samples:
        if plan.sample_index in plan_by_index:
            invalid.append(
                ValidationIssue(
                    "DUPLICATE_PLANNED_SAMPLE",
                    f"sample_index={plan.sample_index}",
                )
            )
        plan_by_index[plan.sample_index] = plan
    invalid.extend(_validate_schedule_balance(schedule, protocol))

    samples_by_index: dict[int, ExperimentSample] = {}
    duplicate_sample_indexes: set[int] = set()
    for sample in samples:
        if sample.sample_index in samples_by_index:
            duplicate_sample_indexes.add(sample.sample_index)
        samples_by_index[sample.sample_index] = sample
    for sample_index in sorted(duplicate_sample_indexes):
        invalid.append(
            ValidationIssue("DUPLICATE_SAMPLE", f"sample_index={sample_index}")
        )

    planned_indexes = set(plan_by_index)
    observed_indexes = set(samples_by_index)
    for sample_index in sorted(planned_indexes - observed_indexes):
        invalid.append(ValidationIssue("MISSING_SAMPLE", f"sample_index={sample_index}"))
    for sample_index in sorted(observed_indexes - planned_indexes):
        invalid.append(
            ValidationIssue(
                "RECORDED_COUNT_EXCEEDED",
                f"unplanned sample_index={sample_index}; adaptive extension is forbidden",
            )
        )

    for sample_index in sorted(planned_indexes & observed_indexes):
        plan = plan_by_index[sample_index]
        sample = samples_by_index[sample_index]
        expected_identity = (
            plan.block_index,
            plan.batch_index,
            plan.lane_index,
            plan.scenario,
            plan.composition,
            plan.surface,
        )
        observed_identity = (
            sample.block_index,
            sample.batch_index,
            sample.lane_index,
            sample.scenario,
            sample.composition,
            sample.surface,
        )
        if observed_identity != expected_identity:
            invalid.append(
                ValidationIssue(
                    "SAMPLE_PLAN_MISMATCH",
                    f"sample_index={sample_index}",
                )
            )
        if sample.exception_type is not None:
            invalid.append(
                ValidationIssue(
                    "UNEXPECTED_EXCEPTION",
                    f"sample_index={sample_index}; type={sample.exception_type}",
                )
            )
        elif sample.cohort is None:
            invalid.append(
                ValidationIssue(
                    "UNSUPPORTED_OUTCOME",
                    f"sample_index={sample_index}",
                )
            )
        elif not _cohort_allowed_for_scenario(sample):
            invalid.append(
                ValidationIssue(
                    "UNEXPECTED_SCENARIO_COHORT",
                    f"sample_index={sample_index}; scenario={sample.scenario.value}; "
                    f"composition={sample.composition.value}; cohort={sample.cohort.value}",
                )
            )
        if (
            sample.exception_type is None
            and plan.surface is Surface.CURRENT_MEASURED
        ):
            if sample.measurement_availability != "AVAILABLE":
                invalid.append(
                    ValidationIssue(
                        "MEASUREMENT_UNAVAILABLE",
                        f"sample_index={sample_index}",
                    )
                )
            elif sample.cohort is not None:
                phases = {phase.name: phase for phase in sample.phases or ()}
                required = REQUIRED_MEASURED_PHASES.get(
                    (sample.composition, sample.cohort), frozenset()
                )
                for phase_name in sorted(required):
                    phase = phases.get(phase_name)
                    if phase is None or phase.state is not PhaseState.MEASURED:
                        invalid.append(
                            ValidationIssue(
                                "REQUIRED_PHASE_NOT_COLLECTED",
                                f"sample_index={sample_index}; phase={phase_name}",
                            )
                        )
        if plan.scenario in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}:
            if sample.start_offset_ns is None:
                invalid.append(
                    ValidationIssue(
                        "MISSING_START_OFFSET",
                        f"sample_index={sample_index}",
                    )
                )
        elif sample.start_offset_ns is not None:
            invalid.append(
                ValidationIssue(
                    "UNEXPECTED_START_OFFSET",
                    f"sample_index={sample_index}",
                )
            )

    invalid.extend(_validate_observed_blocks(samples_by_index, plan_by_index))

    scenario_b_counts = Counter(
        (sample.composition, sample.cohort)
        for sample in samples
        if sample.scenario is Scenario.B_SAME_ORDER
        and sample.exception_type is None
        and sample.cohort is not None
    )
    required_b_cohorts = (
        (Composition.PRE_OCC, Cohort.ACCEPTED),
        (Composition.PRE_OCC, Cohort.APPEND_STALE_WRITE),
        (Composition.IN_PESSIMISTIC, Cohort.ACCEPTED),
        (Composition.IN_PESSIMISTIC, Cohort.PREPARE_LOCK_TIMEOUT),
    )
    for key in required_b_cohorts:
        observed = scenario_b_counts[key]
        if observed < protocol.scenario_b_core_cohort_minimum:
            insufficient.append(
                ValidationIssue(
                    "SCENARIO_B_COHORT_INSUFFICIENT",
                    f"composition={key[0].value}; cohort={key[1].value}; "
                    f"observed={observed}; required={protocol.scenario_b_core_cohort_minimum}",
                )
            )

    if invalid:
        return RunValidationResult(EvidenceStatus.INVALID_RUN, tuple(invalid))
    if insufficient:
        return RunValidationResult(
            EvidenceStatus.INSUFFICIENT_EVIDENCE, tuple(insufficient)
        )
    return RunValidationResult(EvidenceStatus.VALID, ())


def _validate_schedule_balance(
    schedule: ExperimentSchedule,
    protocol: ProtocolConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    counts = Counter(
        (plan.scenario, plan.surface, plan.composition) for plan in schedule.samples
    )
    for surface in Surface:
        for composition in Composition:
            observed = counts[(Scenario.A_UNCONTENDED, surface, composition)]
            expected = protocol.scenario_a_samples_per_surface_per_composition
            if observed != expected:
                issues.append(
                    ValidationIssue(
                        "UNBALANCED_COMPOSITION_SCHEDULE",
                        f"Scenario A {surface.value}/{composition.value}: "
                        f"observed={observed}; expected={expected}",
                    )
                )
    for scenario, batches in (
        (Scenario.B_SAME_ORDER, protocol.scenario_b_batches_per_composition),
        (Scenario.C_DIFFERENT_ORDER, protocol.scenario_c_batches_per_composition),
    ):
        for composition in Composition:
            observed = counts[(scenario, Surface.CURRENT_MEASURED, composition)]
            expected = batches * FIXED_PR6_WORKER_COUNT
            if observed != expected:
                issues.append(
                    ValidationIssue(
                        "UNBALANCED_COMPOSITION_SCHEDULE",
                        f"{scenario.value}/{composition.value}: "
                        f"observed={observed}; expected={expected}",
                    )
                )
    e_count = counts[
        (
            Scenario.E_LOCK_NON_ACQUISITION,
            Surface.CURRENT_MEASURED,
            Composition.IN_PESSIMISTIC,
        )
    ]
    if e_count != protocol.scenario_e_samples:
        issues.append(
            ValidationIssue(
                "UNBALANCED_COMPOSITION_SCHEDULE",
                f"Scenario E observed={e_count}; expected={protocol.scenario_e_samples}",
            )
        )
    return issues


def _validate_observed_blocks(
    samples_by_index: Mapping[int, ExperimentSample],
    plan_by_index: Mapping[int, SamplePlan],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    observed_a: dict[tuple[int, Surface], set[Composition]] = defaultdict(set)
    observed_concurrent: dict[tuple[Scenario, int, Composition], set[int]] = (
        defaultdict(set)
    )
    for sample_index, sample in samples_by_index.items():
        if sample_index not in plan_by_index:
            continue
        if sample.scenario is Scenario.A_UNCONTENDED:
            observed_a[(sample.batch_index, sample.surface)].add(sample.composition)
        elif sample.scenario in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}:
            observed_concurrent[
                (sample.scenario, sample.batch_index, sample.composition)
            ].add(sample.lane_index)

    planned_a = {
        (plan.batch_index, plan.surface)
        for plan in plan_by_index.values()
        if plan.scenario is Scenario.A_UNCONTENDED
    }
    for key in sorted(planned_a, key=lambda item: (item[0], item[1].value)):
        if observed_a[key] != set(Composition):
            issues.append(
                ValidationIssue(
                    "INCOMPLETE_MATCHED_BLOCK",
                    f"Scenario A batch={key[0]}; surface={key[1].value}",
                )
            )

    planned_concurrent = {
        (plan.scenario, plan.batch_index, plan.composition)
        for plan in plan_by_index.values()
        if plan.scenario in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}
    }
    for key in sorted(
        planned_concurrent,
        key=lambda item: (item[0].value, item[1], item[2].value),
    ):
        if observed_concurrent[key] != {0, 1}:
            issues.append(
                ValidationIssue(
                    "INCOMPLETE_MATCHED_BLOCK",
                    f"{key[0].value} batch={key[1]}; composition={key[2].value}",
                )
            )
    return issues


def _aggregate_to_dict(result: AggregateResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "scenario": result.scenario.value,
        "surface": result.surface.value,
        "composition": result.composition.value,
        "command": result.command,
        "history_depth": result.history_depth,
        "expected_sequence": result.expected_sequence,
        "cohort": result.cohort.value,
        "external_elapsed": _statistics_to_dict(result.external_elapsed),
        "phases": {
            phase.phase_name: _statistics_to_dict(phase.statistics)
            for phase in result.phases
        },
    }


def _statistics_to_dict(result: DescriptiveStatistics) -> dict[str, Any]:
    return {
        "count": result.count,
        "min_ns": result.minimum_ns,
        "max_ns": result.maximum_ns,
        "mean_ns": result.mean_ns,
        "median_ns": result.median_ns,
    }


def _cohort_allowed_for_scenario(sample: ExperimentSample) -> bool:
    if sample.scenario in {
        Scenario.A_UNCONTENDED,
        Scenario.C_DIFFERENT_ORDER,
    }:
        return sample.cohort is Cohort.ACCEPTED
    if sample.scenario is Scenario.B_SAME_ORDER:
        if sample.composition is Composition.PRE_OCC:
            return sample.cohort in {
                Cohort.ACCEPTED,
                Cohort.APPEND_STALE_WRITE,
            }
        return sample.cohort in {
            Cohort.ACCEPTED,
            Cohort.PREPARE_LOCK_TIMEOUT,
        }
    return (
        sample.scenario is Scenario.E_LOCK_NON_ACQUISITION
        and sample.composition is Composition.IN_PESSIMISTIC
        and sample.cohort is Cohort.PREPARE_LOCK_TIMEOUT
    )


def _describe(values: Sequence[int]) -> DescriptiveStatistics:
    if not values:
        raise ValueError("descriptive aggregation requires at least one value")
    return DescriptiveStatistics(
        count=len(values),
        minimum_ns=min(values),
        maximum_ns=max(values),
        mean_ns=statistics.fmean(values),
        median_ns=float(statistics.median(values)),
    )


def _counts_to_dict(counts: Sequence[NamedCount]) -> dict[str, int]:
    if len({count.name for count in counts}) != len(counts):
        raise ValueError("manifest count names must be unique")
    return {count.name: count.count for count in counts}


def _read_external_clock(clock: Callable[[], int]) -> int:
    reading = clock()
    if type(reading) is not int:
        raise TypeError("external clock must return an integer nanosecond reading")
    return reading


def _external_elapsed(started_ns: int, stopped_ns: int) -> int:
    elapsed_ns = stopped_ns - started_ns
    if elapsed_ns < 0:
        raise ExperimentError("external experiment clock moved backwards")
    return elapsed_ns


def _sort_value(value: object) -> str:
    return value.value if isinstance(value, Enum) else str(value)


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_positive_int(value: object, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _reject_secret_shaped_manifest_values(manifest: EnvironmentManifest) -> None:
    forbidden_fragments = (
        "://",
        "password=",
        "username=",
        "user=",
        "host=",
        "port=",
        "dsn=",
        "test_database_url",
    )
    values = (
        manifest.topology_label,
        manifest.schema_or_migration_identity,
        manifest.connection_arrangement,
        manifest.ordering_method,
        *manifest.stop_rules,
    )
    for value in values:
        lowered = value.lower()
        if any(fragment in lowered for fragment in forbidden_fragments):
            raise ValueError("manifest metadata contains a secret-shaped value")


def main(argv: Sequence[str] | None = None) -> None:
    """Expose only the explicit untimed preflight; refuse recorded execution."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Stage 4B.2 PR6 experiment infrastructure"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="run only the guarded six-cell untimed PostgreSQL preflight",
    )
    args = parser.parse_args(argv)
    if not args.preflight:
        raise SystemExit(
            "PR6 recorded execution is disabled; pass --preflight only for the "
            "separately authorized untimed compatibility check."
        )
    try:
        result = run_postgres_preflight_from_environment()
    except PreflightError as exc:
        raise SystemExit(f"PR6 untimed preflight failed: {exc}") from None
    except Exception as exc:
        raise SystemExit(
            f"PR6 untimed preflight failed: {type(exc).__name__}"
        ) from None
    print(format_postgres_preflight(result))


if __name__ == "__main__":
    main()
