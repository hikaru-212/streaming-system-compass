"""Bounded Level-C runtime for the Stage 4B.2 PR7 experiment.

This module owns only PR7's fixed synchronized-burst schedule, immutable raw
records, deterministic validation and descriptive aggregation, plus the
level-scoped PostgreSQL resource topology needed by a later authorized run.
It does not expose a command-line entry point, publish evidence, choose worker
levels, retry work, or generalize the frozen PR6 two-worker runtime.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from queue import Queue
import random
import re
import statistics
import threading
import time
from types import MappingProxyType
from typing import Any, ContextManager, Protocol

from experiments.stage4b2.postgres_bounded_concurrency import (
    LEVEL_C_SCHEMA_NAME,
    LEVEL_C_SCHEMA_VERSION,
    required_connections,
)


RETAINED_WORKER_LEVELS = (1, 2, 4, 8)
WARMUP_BATCHES_PER_CELL = 3
RECORDED_BATCHES_PER_CELL = 30
RECORDED_SCHEDULE_SEED = 73
EXACT_CELL_COUNT = 16

SMOKE_WARMUP_BATCHES_PER_CELL = 0
SMOKE_BATCHES_PER_CELL = 1
SMOKE_EXACT_CELL_COUNT = 16
SMOKE_TOTAL_BATCHES = 16
SMOKE_TOTAL_PLANNED_INVOCATIONS = 60
SMOKE_EVIDENCE_KIND = "POSTGRESQL_SMOKE"

CANONICAL_AMOUNT = Decimal("100.00")
CANONICAL_EXPECTED_SEQUENCE = 1

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

_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_STOP_WORKER = object()


class BoundedConcurrencyRuntimeError(RuntimeError):
    """Report a PR7 harness defect without assigning producer semantics."""


class UnsupportedCohortError(BoundedConcurrencyRuntimeError):
    """Reject a normal producer combination outside the exact PR7 cohorts."""


class ObservationVerificationError(BoundedConcurrencyRuntimeError):
    """Report an untimed durable-observation verification failure."""


class ConnectionReuseVerificationError(BoundedConcurrencyRuntimeError):
    """Report an untimed lane-connection reuse or IDLE verification failure."""


class WorkloadFamily(str, Enum):
    """Identify the two non-pooled PR7 workload families."""

    SAME_ORDER_HOT_STREAM = "SAME_ORDER_HOT_STREAM"
    DIFFERENT_ORDER_GENERAL_CONCURRENCY = (
        "DIFFERENT_ORDER_GENERAL_CONCURRENCY"
    )


class Composition(str, Enum):
    """Identify the two accepted PR6 compositions retained by PR7."""

    PRE_OCC = "PRE_OCC"
    IN_PESSIMISTIC = "IN_PESSIMISTIC"


class RejectionStage(str, Enum):
    """Identify the exact producer admission stage that rejected a request."""

    APPEND = "append"
    PREPARE_STREAM = "prepare_stream"


class Cohort(str, Enum):
    """Identify one exact non-pooled PR7 invocation cohort."""

    ACCEPTED = "ACCEPTED"
    APPEND_STALE_WRITE = "ADMISSION_REJECTED_APPEND_STALE_WRITE"
    PREPARE_LOCK_TIMEOUT = "ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT"


class PhaseState(str, Enum):
    """Preserve the four PR3 measurement-presence meanings."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REACHED = "NOT_REACHED"
    NOT_COLLECTED = "NOT_COLLECTED"
    MEASURED = "MEASURED"


class EvidenceStatus(str, Enum):
    """Distinguish structurally valid from invalid Level-C raw evidence."""

    VALID = "VALID"
    INVALID_RUN = "INVALID_RUN"


class SmokeStatus(str, Enum):
    """Distinguish structural validity from a stopped invalid smoke."""

    STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
    INVALID_SMOKE = "INVALID_SMOKE"


@dataclass(frozen=True)
class PhaseRecord:
    """Retain one PR3 phase without rewriting absence as measured zero."""

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
class CellPlan:
    """Describe one exact worker-level, workload, and composition cell."""

    cell_index: int
    level_order_position: int
    workload_order_position: int
    composition_order_position: int
    worker_level: int
    workload_family: WorkloadFamily
    composition: Composition

    def __post_init__(self) -> None:
        for name in (
            "cell_index",
            "level_order_position",
            "workload_order_position",
            "composition_order_position",
        ):
            _require_non_negative_int(getattr(self, name), name)
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("cell worker level is not retained by PR7")
        if self.workload_order_position not in (0, 1):
            raise ValueError("workload order position must be 0 or 1")
        if self.composition_order_position not in (0, 1):
            raise ValueError("composition order position must be 0 or 1")


@dataclass(frozen=True)
class BatchPlan:
    """Describe one fixed warmup or recorded synchronized burst."""

    plan_index: int
    cell: CellPlan
    batch_index: int
    recorded: bool
    lane_identity_rotation: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.plan_index, "plan_index")
        _require_non_negative_int(self.batch_index, "batch_index")
        _require_non_negative_int(
            self.lane_identity_rotation,
            "lane_identity_rotation",
        )
        if type(self.recorded) is not bool:
            raise TypeError("recorded must be bool")
        limit = (
            RECORDED_BATCHES_PER_CELL
            if self.recorded
            else WARMUP_BATCHES_PER_CELL
        )
        if self.batch_index >= limit:
            raise ValueError("batch index exceeds its fixed cell count")
        if self.lane_identity_rotation >= self.cell.worker_level:
            raise ValueError("lane identity rotation must fit the worker level")


@dataclass(frozen=True)
class ExperimentSchedule:
    """Hold the complete fixed PR7 schedule generated before execution."""

    seed: int
    retained_worker_levels: tuple[int, ...]
    warmup_batches_per_cell: int
    recorded_batches_per_cell: int
    cells: tuple[CellPlan, ...]
    batches: tuple[BatchPlan, ...]

    def __post_init__(self) -> None:
        if type(self.seed) is not int:
            raise TypeError("schedule seed must be int")
        if self.retained_worker_levels != RETAINED_WORKER_LEVELS:
            raise ValueError("schedule retained levels must be exactly 1, 2, 4, 8")
        if self.warmup_batches_per_cell != WARMUP_BATCHES_PER_CELL:
            raise ValueError("PR7 warmup batches per cell must remain 3")
        if self.recorded_batches_per_cell != RECORDED_BATCHES_PER_CELL:
            raise ValueError("PR7 recorded batches per cell must remain 30")

    @property
    def recorded_batches(self) -> tuple[BatchPlan, ...]:
        """Return the predetermined recorded subset without extending it."""

        return tuple(batch for batch in self.batches if batch.recorded)


@dataclass(frozen=True)
class InvocationSpec:
    """Hold one lane's fully prepared identities outside producer timing."""

    plan: BatchPlan
    lane_index: int
    connection_slot: int
    identity_position: int
    request_id: str
    order_id: str

    def __post_init__(self) -> None:
        level = self.plan.cell.worker_level
        for name in ("lane_index", "connection_slot", "identity_position"):
            value = getattr(self, name)
            _require_non_negative_int(value, name)
            if value >= level:
                raise ValueError(f"{name} must fit the worker level")
        if self.connection_slot != self.lane_index:
            raise ValueError("one persistent connection slot must own each lane")
        if not self.request_id or not self.order_id:
            raise ValueError("prepared request and order identities must be non-empty")


@dataclass(frozen=True)
class InvocationRecord:
    """Store one PR7 invocation observation without governance identity."""

    schema_name: str
    schema_version: int
    run_id: str
    invocation_index: int
    cell_index: int
    batch_index: int
    lane_index: int
    connection_slot: int
    worker_level: int
    workload_family: WorkloadFamily
    composition: Composition
    external_elapsed_ns: int
    start_offset_ns: int
    producer_outcome: str | None
    rejection_stage: RejectionStage | None
    stream_admission_verdict: str | None
    append_admission_verdict: str | None
    cohort: Cohort | None
    measurement_availability: str | None
    phases: tuple[PhaseRecord, ...] | None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.schema_name != LEVEL_C_SCHEMA_NAME:
            raise ValueError("invocation schema name is not PR7 Level-C")
        if self.schema_version != LEVEL_C_SCHEMA_VERSION:
            raise ValueError("invocation schema version is not PR7 version 1")
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        for name in (
            "invocation_index",
            "cell_index",
            "batch_index",
            "lane_index",
            "connection_slot",
            "external_elapsed_ns",
            "start_offset_ns",
        ):
            _require_non_negative_int(getattr(self, name), name)
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("invocation worker level is not retained")
        if self.lane_index >= self.worker_level:
            raise ValueError("invocation lane must fit the worker level")
        if self.connection_slot >= self.worker_level:
            raise ValueError("connection slot must fit the worker level")
        if self.phases is not None:
            names = tuple(phase.name for phase in self.phases)
            if len(names) != len(set(names)):
                raise ValueError("phases must not contain duplicate names")
        if self.exception_type is not None:
            if not self.exception_type:
                raise ValueError("exception type must be a non-empty class name")
            if any(
                value is not None
                for value in (
                    self.producer_outcome,
                    self.rejection_stage,
                    self.stream_admission_verdict,
                    self.append_admission_verdict,
                    self.cohort,
                    self.measurement_availability,
                    self.phases,
                )
            ):
                raise ValueError("exception observation cannot contain normal evidence")


@dataclass(frozen=True)
class TypedOutcomeCount:
    """Count one exact supported or invalid terminal observation label."""

    outcome: str
    count: int

    def __post_init__(self) -> None:
        if not self.outcome:
            raise ValueError("typed outcome label must not be empty")
        _require_positive_int(self.count, "count")


@dataclass(frozen=True)
class BatchRecord:
    """Store one release-to-last-completion synchronized-burst record."""

    schema_name: str
    schema_version: int
    run_id: str
    batch_record_index: int
    cell_index: int
    batch_index: int
    worker_level: int
    workload_family: WorkloadFamily
    composition: Composition
    release_reference_ns: int
    first_start_offset_ns: int
    last_start_offset_ns: int
    batch_elapsed_ns: int
    completed_count: int
    accepted_count: int
    typed_outcome_counts: tuple[TypedOutcomeCount, ...]

    def __post_init__(self) -> None:
        if self.schema_name != LEVEL_C_SCHEMA_NAME:
            raise ValueError("batch schema name is not PR7 Level-C")
        if self.schema_version != LEVEL_C_SCHEMA_VERSION:
            raise ValueError("batch schema version is not PR7 version 1")
        if not self.run_id:
            raise ValueError("run_id must not be empty")
        for name in (
            "batch_record_index",
            "cell_index",
            "batch_index",
            "release_reference_ns",
            "first_start_offset_ns",
            "last_start_offset_ns",
            "batch_elapsed_ns",
            "completed_count",
            "accepted_count",
        ):
            _require_non_negative_int(getattr(self, name), name)
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("batch worker level is not retained")
        if self.last_start_offset_ns < self.first_start_offset_ns:
            raise ValueError("last start offset cannot precede first start offset")
        if self.accepted_count > self.completed_count:
            raise ValueError("accepted count cannot exceed completed count")
        labels = tuple(item.outcome for item in self.typed_outcome_counts)
        if len(labels) != len(set(labels)) or labels != tuple(sorted(labels)):
            raise ValueError("typed outcome counts must be unique and sorted")
        if sum(item.count for item in self.typed_outcome_counts) != self.completed_count:
            raise ValueError("typed outcome counts must equal completed count")

    @property
    def release_skew_ns(self) -> int:
        """Return observed first-to-last invocation-start skew."""

        return self.last_start_offset_ns - self.first_start_offset_ns


@dataclass(frozen=True)
class LaneOwnershipRecord:
    """Retain sanitized stable lane/thread/connection-slot ownership."""

    worker_level: int
    lane_index: int
    connection_slot: int
    thread_id: int

    def __post_init__(self) -> None:
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("ownership worker level is not retained")
        _require_non_negative_int(self.lane_index, "lane_index")
        _require_non_negative_int(self.connection_slot, "connection_slot")
        _require_positive_int(self.thread_id, "thread_id")
        if self.lane_index != self.connection_slot:
            raise ValueError("lane and connection slot ownership must be identical")


@dataclass(frozen=True)
class ValidationIssue:
    """Describe one deterministic evidence-accounting defect."""

    code: str
    detail: str


@dataclass(frozen=True)
class RunValidationResult:
    """Return structural Level-C validity without authorizing publication."""

    status: EvidenceStatus
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class RecordedExecutionResult:
    """Return one fixed execution's raw records and one-shot validation."""

    schedule: ExperimentSchedule
    invocations: tuple[InvocationRecord, ...]
    batches: tuple[BatchRecord, ...]
    ownership: tuple[LaneOwnershipRecord, ...]
    validation: RunValidationResult


@dataclass(frozen=True)
class SmokeCellPlan:
    """Wrap one low-level synchronized burst in the distinct smoke boundary."""

    smoke_cell_index: int
    mechanics_plan: BatchPlan

    def __post_init__(self) -> None:
        _require_non_negative_int(self.smoke_cell_index, "smoke_cell_index")
        if self.smoke_cell_index != self.mechanics_plan.cell.cell_index:
            raise ValueError("smoke cell index must match the frozen cell order")
        if self.mechanics_plan.plan_index != self.smoke_cell_index:
            raise ValueError("smoke mechanics plan must occur exactly once")
        if not self.mechanics_plan.recorded or self.mechanics_plan.batch_index != 0:
            raise ValueError("smoke cell requires one non-warmup synchronized burst")

    @property
    def worker_level(self) -> int:
        """Return the reviewed worker level for this smoke cell."""

        return self.mechanics_plan.cell.worker_level

    @property
    def workload_family(self) -> WorkloadFamily:
        """Return the non-pooled workload family for this smoke cell."""

        return self.mechanics_plan.cell.workload_family

    @property
    def composition(self) -> Composition:
        """Return the retained composition for this smoke cell."""

        return self.mechanics_plan.cell.composition


@dataclass(frozen=True)
class SmokeSchedule:
    """Hold exactly one smoke burst for each canonical seed-73 cell."""

    seed: int
    retained_worker_levels: tuple[int, ...]
    warmup_batches_per_cell: int
    smoke_batches_per_cell: int
    cells: tuple[SmokeCellPlan, ...]

    def __post_init__(self) -> None:
        if self.seed != RECORDED_SCHEDULE_SEED:
            raise ValueError("smoke schedule must use the canonical seed 73")
        if self.retained_worker_levels != RETAINED_WORKER_LEVELS:
            raise ValueError("smoke retained levels must be exactly 1, 2, 4, 8")
        if self.warmup_batches_per_cell != SMOKE_WARMUP_BATCHES_PER_CELL:
            raise ValueError("smoke schedule has no warmup batches")
        if self.smoke_batches_per_cell != SMOKE_BATCHES_PER_CELL:
            raise ValueError("smoke schedule requires exactly one burst per cell")
        if len(self.cells) != SMOKE_EXACT_CELL_COUNT:
            raise ValueError("smoke schedule requires exactly 16 cells")
        indexes = tuple(cell.smoke_cell_index for cell in self.cells)
        if indexes != tuple(range(SMOKE_EXACT_CELL_COUNT)):
            raise ValueError("smoke cells must preserve exact canonical order")

    @property
    def batches(self) -> tuple[BatchPlan, ...]:
        """Return the sixteen low-level mechanics plans, never canonical records."""

        return tuple(cell.mechanics_plan for cell in self.cells)

    @property
    def planned_invocation_count(self) -> int:
        """Return the fixed 4 * (1 + 2 + 4 + 8) smoke accounting."""

        return sum(cell.worker_level for cell in self.cells)


@dataclass(frozen=True)
class SmokeInvocationObservation:
    """Keep one low-level observation inside the non-canonical smoke envelope."""

    smoke_cell_index: int
    request_id: str
    order_id: str
    record: InvocationRecord

    def __post_init__(self) -> None:
        _require_non_negative_int(self.smoke_cell_index, "smoke_cell_index")
        if self.record.cell_index != self.smoke_cell_index:
            raise ValueError("smoke invocation does not match its smoke cell")
        if not self.request_id or not self.order_id:
            raise ValueError("smoke invocation identities must be non-empty")


@dataclass(frozen=True)
class SmokeBatchObservation:
    """Keep one low-level batch observation outside canonical aggregation."""

    smoke_cell_index: int
    record: BatchRecord

    def __post_init__(self) -> None:
        _require_non_negative_int(self.smoke_cell_index, "smoke_cell_index")
        if self.record.cell_index != self.smoke_cell_index:
            raise ValueError("smoke batch does not match its smoke cell")

    @property
    def release_skew_ns(self) -> int:
        """Expose raw skew for later human review without a threshold."""

        return self.record.release_skew_ns


@dataclass(frozen=True)
class SmokeRuntimeFacts:
    """Retain sanitized level-scoped topology facts needed by the smoke gate."""

    worker_level: int
    lane_count: int
    thread_count: int
    connection_count: int
    topology_label: str
    postgresql_server_version: str | None
    isolation_level: str
    autocommit: bool

    def __post_init__(self) -> None:
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("smoke runtime facts require a retained level")
        for name in ("lane_count", "thread_count", "connection_count"):
            if getattr(self, name) != self.worker_level:
                raise ValueError(f"{name} must equal the smoke worker level")
        if not self.topology_label or not self.isolation_level:
            raise ValueError("smoke runtime facts require sanitized topology labels")
        if type(self.autocommit) is not bool:
            raise TypeError("smoke autocommit fact must be bool")


@dataclass(frozen=True)
class SmokeValidationIssue:
    """Describe one smoke-local defect without retaining an exception message."""

    code: str
    smoke_cell_index: int
    detail: str

    def __post_init__(self) -> None:
        if not self.code or not self.detail:
            raise ValueError("smoke issue code and detail must be non-empty")
        _require_non_negative_int(self.smoke_cell_index, "smoke_cell_index")


@dataclass(frozen=True)
class SmokeExecutionResult:
    """Return in-memory smoke correctness evidence, never canonical evidence."""

    evidence_kind: str
    schedule: SmokeSchedule
    status: SmokeStatus
    invocations: tuple[SmokeInvocationObservation, ...]
    batches: tuple[SmokeBatchObservation, ...]
    ownership: tuple[LaneOwnershipRecord, ...]
    runtime_facts: tuple[SmokeRuntimeFacts, ...]
    issues: tuple[SmokeValidationIssue, ...]
    failed_cell_index: int | None
    release_skew_human_review_required: bool = True

    def __post_init__(self) -> None:
        if self.evidence_kind != SMOKE_EVIDENCE_KIND:
            raise ValueError("smoke result must remain explicitly non-canonical")
        if self.release_skew_human_review_required is not True:
            raise ValueError("smoke cannot authorize its own release-skew review")
        if self.status is SmokeStatus.STRUCTURALLY_VALID:
            if self.issues or self.failed_cell_index is not None:
                raise ValueError("valid smoke cannot retain an invalidity marker")
            if len(self.batches) != SMOKE_TOTAL_BATCHES:
                raise ValueError("valid smoke requires all sixteen batches")
            if len(self.invocations) != SMOKE_TOTAL_PLANNED_INVOCATIONS:
                raise ValueError("valid smoke requires all sixty invocations")
            if len(self.ownership) != sum(RETAINED_WORKER_LEVELS):
                raise ValueError("valid smoke requires exact persistent ownership")
            expected_level_order = tuple(
                dict.fromkeys(cell.worker_level for cell in self.schedule.cells)
            )
            if tuple(
                item.worker_level for item in self.runtime_facts
            ) != expected_level_order:
                raise ValueError("valid smoke requires each level topology once")
        else:
            if not self.issues or self.failed_cell_index is None:
                raise ValueError("invalid smoke requires its first failed cell")


@dataclass(frozen=True)
class DescriptiveStatistics:
    """Store count/min/max/mean/median; p95 is intentionally absent."""

    count: int
    minimum: float
    maximum: float
    mean: float
    median: float


@dataclass(frozen=True)
class PhaseAggregate:
    """Describe one measured phase independently from other phase intervals."""

    phase_name: str
    statistics_ns: DescriptiveStatistics


@dataclass(frozen=True)
class InvocationAggregate:
    """Aggregate one exact level/family/composition/cohort without pooling."""

    run_id: str
    worker_level: int
    workload_family: WorkloadFamily
    composition: Composition
    cohort: Cohort
    external_elapsed_ns: DescriptiveStatistics
    phases: tuple[PhaseAggregate, ...]


@dataclass(frozen=True)
class BatchCompletionRates:
    """Describe protocol-qualified rates for one synchronized burst only."""

    accepted_completion_rate_per_second: float
    all_completion_rate_per_second: float


@dataclass(frozen=True)
class BatchRateAggregate:
    """Aggregate synchronized-burst rates for one exact non-pooled cell."""

    run_id: str
    worker_level: int
    workload_family: WorkloadFamily
    composition: Composition
    accepted_completion_rate_per_second: DescriptiveStatistics
    all_completion_rate_per_second: DescriptiveStatistics


@dataclass(frozen=True)
class LaneRuntime:
    """Own one persistent connection and both preconstructed PR7 writers."""

    lane_index: int
    connection: Any
    writers: Mapping[Composition, Any]

    def __post_init__(self) -> None:
        _require_non_negative_int(self.lane_index, "lane_index")
        if set(self.writers) != set(Composition):
            raise ValueError("each PR7 lane requires exactly PRE and IN writers")
        for writer in self.writers.values():
            owner = getattr(writer, "_connection", None)
            if owner is None:
                owner = getattr(writer, "connection", None)
            if owner is not None and owner is not self.connection:
                raise ValueError("a lane writer must own its lane connection")


ResetDatabase = Callable[[], None]
PrepareBatch = Callable[[BatchPlan, tuple[InvocationSpec, ...]], None]
VerifyObservation = Callable[[Any, Any, InvocationSpec], None]
VerifyConnection = Callable[[Any], None]


@dataclass(frozen=True)
class LevelRuntime:
    """Hold all preconstructed resources and untimed hooks for one level.

    The caller must construct exactly ``worker_level`` connections, writers,
    validators, and lane objects before yielding this topology. Lane 0 owns
    reset and setup work only while no synchronized batch is active. No
    dedicated controller or observer connection is represented here.
    """

    worker_level: int
    lanes: tuple[LaneRuntime, ...]
    reset_database: ResetDatabase
    prepare_batch: PrepareBatch
    verify_observation: VerifyObservation
    verify_connection: VerifyConnection
    topology_label: str = "guarded-test-postgresql"
    postgresql_server_version: str | None = None
    isolation_level: str = "UNAVAILABLE"
    autocommit: bool = False

    def __post_init__(self) -> None:
        if self.worker_level not in RETAINED_WORKER_LEVELS:
            raise ValueError("runtime worker level is not retained")
        if required_connections(self.worker_level) != self.worker_level:
            raise ValueError("PR7 runtime connection formula must remain N")
        if len(self.lanes) != self.worker_level:
            raise ValueError("runtime requires exactly N persistent lanes")
        indexes = tuple(lane.lane_index for lane in self.lanes)
        if indexes != tuple(range(self.worker_level)):
            raise ValueError("runtime lanes must be ordered exactly 0 through N-1")
        connections = tuple(id(lane.connection) for lane in self.lanes)
        if len(set(connections)) != self.worker_level:
            raise ValueError("worker lanes cannot share a connection")

    def lane(self, lane_index: int) -> LaneRuntime:
        """Return the persistent owner of one exact lane index."""

        if lane_index < 0 or lane_index >= self.worker_level:
            raise BoundedConcurrencyRuntimeError("planned lane is unavailable")
        return self.lanes[lane_index]


class BatchTimingSource(Protocol):
    """Provide one common monotonic reference and per-lane clock readings."""

    def release_reference_ns(self) -> int:
        """Capture the one reference from the release-barrier action."""

    def invocation_start_ns(self, lane_index: int) -> int:
        """Capture one lane's start immediately before its public call."""

    def invocation_stop_ns(self, lane_index: int) -> int:
        """Capture one lane's stop on normal return or ordinary exception."""


class _PerfCounterBatchTimingSource:
    """Use one monotonic nanosecond clock domain for a real batch."""

    def release_reference_ns(self) -> int:
        return time.perf_counter_ns()

    def invocation_start_ns(self, lane_index: int) -> int:
        del lane_index
        return time.perf_counter_ns()

    def invocation_stop_ns(self, lane_index: int) -> int:
        del lane_index
        return time.perf_counter_ns()


BatchTimingSourceFactory = Callable[[BatchPlan], BatchTimingSource]
OpenLevelRuntime = Callable[[int], ContextManager[LevelRuntime]]


@dataclass(frozen=True)
class _TimedObservation:
    """Retain raw return or exception type plus exact external timestamps."""

    value: Any | None
    invocation_start_ns: int
    invocation_stop_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_non_negative_int(self.invocation_start_ns, "invocation_start_ns")
        _require_non_negative_int(self.invocation_stop_ns, "invocation_stop_ns")
        if self.invocation_stop_ns < self.invocation_start_ns:
            raise ValueError("invocation stop cannot precede start")
        if self.exception_type is None and self.value is None:
            raise ValueError("normal timed observation requires a value")
        if self.exception_type is not None:
            if not self.exception_type or self.value is not None:
                raise ValueError("exception observation retains type name only")

    @property
    def elapsed_ns(self) -> int:
        return self.invocation_stop_ns - self.invocation_start_ns


@dataclass
class _LaneTask:
    invocation: Callable[[], _TimedObservation]
    completed: threading.Event = field(default_factory=threading.Event)
    value: _TimedObservation | None = None
    error: BaseException | None = None


class _PersistentLaneWorkers:
    """Keep exactly N persistent threads, each bound to one lane queue."""

    def __init__(self, runtime: LevelRuntime) -> None:
        self._runtime = runtime
        self._queues = tuple(Queue[Any]() for _lane in runtime.lanes)
        self._thread_ids: list[int | None] = [None] * runtime.worker_level
        self._started = tuple(threading.Event() for _lane in runtime.lanes)
        self._closed = False
        self._threads = tuple(
            threading.Thread(
                target=self._worker,
                args=(lane.lane_index,),
                name=(
                    f"stage4b2-pr7-level-{runtime.worker_level}-"
                    f"lane-{lane.lane_index}"
                ),
            )
            for lane in runtime.lanes
        )
        for thread in self._threads:
            thread.start()
        for started in self._started:
            started.wait()

    @property
    def thread_ids(self) -> tuple[int, ...]:
        """Return stable identities after every persistent thread has started."""

        if any(thread_id is None for thread_id in self._thread_ids):
            raise BoundedConcurrencyRuntimeError("worker thread did not start")
        return tuple(int(thread_id) for thread_id in self._thread_ids)

    def run_batch(
        self,
        invocations: Mapping[int, Callable[[], _TimedObservation]],
    ) -> tuple[_TimedObservation, ...]:
        """Submit exactly one invocation per lane and never retry a task."""

        expected = set(range(self._runtime.worker_level))
        if self._closed or set(invocations) != expected:
            raise BoundedConcurrencyRuntimeError(
                "a batch requires exactly one task for every persistent lane"
            )
        tasks = tuple(
            _LaneTask(invocation=invocations[lane_index])
            for lane_index in range(self._runtime.worker_level)
        )
        for lane_index, task in enumerate(tasks):
            self._queues[lane_index].put(task)
        for task in tasks:
            task.completed.wait()
        for task in tasks:
            if task.error is not None:
                raise task.error
            if task.value is None:
                raise BoundedConcurrencyRuntimeError("worker omitted its observation")
        return tuple(task.value for task in tasks if task.value is not None)

    def close(self) -> None:
        """Stop only the N threads owned by this worker-level topology."""

        if self._closed:
            return
        self._closed = True
        for queue in self._queues:
            queue.put(_STOP_WORKER)
        for thread in self._threads:
            thread.join()

    def _worker(self, lane_index: int) -> None:
        self._thread_ids[lane_index] = threading.get_ident()
        self._started[lane_index].set()
        while True:
            item = self._queues[lane_index].get()
            if item is _STOP_WORKER:
                return
            task: _LaneTask = item
            try:
                task.value = task.invocation()
            except BaseException as exc:
                task.error = exc
            finally:
                task.completed.set()


class _ReleaseReference:
    """Capture one common reference in the barrier action."""

    def __init__(self, timing: BatchTimingSource) -> None:
        self._timing = timing
        self.reference_ns: int | None = None

    def capture(self) -> None:
        self.reference_ns = _read_clock(
            self._timing.release_reference_ns(),
            "release_reference_ns",
        )


def generate_fixed_schedule(
    *,
    seed: int = RECORDED_SCHEDULE_SEED,
) -> ExperimentSchedule:
    """Generate all 16 cells and their immutable 3+30 batch schedule.

    The seed shuffles the four level blocks. Workload-first order alternates by
    level position. Composition-first order alternates by matched workload pair,
    yielding four PRE-first and four IN-first pairs overall and two of each for
    each workload family. Lane identity positions rotate deterministically while
    lane-to-thread and lane-to-connection ownership remain fixed.
    """

    if type(seed) is not int:
        raise TypeError("schedule seed must be int")
    rng = random.Random(seed)
    level_order = list(RETAINED_WORKER_LEVELS)
    rng.shuffle(level_order)

    cells: list[CellPlan] = []
    batches: list[BatchPlan] = []
    plan_index = 0
    for level_position, worker_level in enumerate(level_order):
        workload_order = (
            (
                WorkloadFamily.SAME_ORDER_HOT_STREAM,
                WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
            )
            if level_position % 2 == 0
            else (
                WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
                WorkloadFamily.SAME_ORDER_HOT_STREAM,
            )
        )
        for workload_position, workload_family in enumerate(workload_order):
            pair_index = level_position * 2 + workload_position
            composition_order = (
                (Composition.PRE_OCC, Composition.IN_PESSIMISTIC)
                if pair_index % 2 == 0
                else (Composition.IN_PESSIMISTIC, Composition.PRE_OCC)
            )
            for composition_position, composition in enumerate(composition_order):
                cell = CellPlan(
                    cell_index=len(cells),
                    level_order_position=level_position,
                    workload_order_position=workload_position,
                    composition_order_position=composition_position,
                    worker_level=worker_level,
                    workload_family=workload_family,
                    composition=composition,
                )
                cells.append(cell)
                for recorded, count in (
                    (False, WARMUP_BATCHES_PER_CELL),
                    (True, RECORDED_BATCHES_PER_CELL),
                ):
                    for batch_index in range(count):
                        batches.append(
                            BatchPlan(
                                plan_index=plan_index,
                                cell=cell,
                                batch_index=batch_index,
                                recorded=recorded,
                                lane_identity_rotation=(
                                    batch_index + cell.cell_index
                                )
                                % worker_level,
                            )
                        )
                        plan_index += 1

    schedule = ExperimentSchedule(
        seed=seed,
        retained_worker_levels=RETAINED_WORKER_LEVELS,
        warmup_batches_per_cell=WARMUP_BATCHES_PER_CELL,
        recorded_batches_per_cell=RECORDED_BATCHES_PER_CELL,
        cells=tuple(cells),
        batches=tuple(batches),
    )
    if len(schedule.cells) != EXACT_CELL_COUNT:
        raise BoundedConcurrencyRuntimeError("fixed schedule did not produce 16 cells")
    return schedule


def generate_smoke_schedule() -> SmokeSchedule:
    """Generate one smoke burst in each canonical seed-73 cell, in exact order.

    The returned type is deliberately distinct from ``ExperimentSchedule``.
    Its low-level batch plans exist only to reuse synchronized release and
    identity mechanics; they cannot weaken the canonical 3+30 invariant.
    """

    canonical = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    smoke_cells = tuple(
        SmokeCellPlan(
            smoke_cell_index=cell.cell_index,
            mechanics_plan=BatchPlan(
                plan_index=cell.cell_index,
                cell=cell,
                batch_index=0,
                recorded=True,
                lane_identity_rotation=cell.cell_index % cell.worker_level,
            ),
        )
        for cell in canonical.cells
    )
    schedule = SmokeSchedule(
        seed=RECORDED_SCHEDULE_SEED,
        retained_worker_levels=RETAINED_WORKER_LEVELS,
        warmup_batches_per_cell=SMOKE_WARMUP_BATCHES_PER_CELL,
        smoke_batches_per_cell=SMOKE_BATCHES_PER_CELL,
        cells=smoke_cells,
    )
    if schedule.planned_invocation_count != SMOKE_TOTAL_PLANNED_INVOCATIONS:
        raise BoundedConcurrencyRuntimeError(
            "fixed smoke schedule did not produce sixty invocations"
        )
    return schedule


def prepare_invocation_specs(
    *,
    run_id: str,
    plan: BatchPlan,
) -> tuple[InvocationSpec, ...]:
    """Prepare all request and order identities before a batch reaches timing."""

    _require_safe_run_id(run_id)
    level = plan.cell.worker_level
    shared_order_id = _identity_token(
        run_id=run_id,
        plan=plan,
        identity_position=0,
        purpose="shared-order",
    )
    specs: list[InvocationSpec] = []
    for lane_index in range(level):
        identity_position = (lane_index + plan.lane_identity_rotation) % level
        request_id = _identity_token(
            run_id=run_id,
            plan=plan,
            identity_position=identity_position,
            purpose="request",
        )
        order_id = (
            shared_order_id
            if plan.cell.workload_family is WorkloadFamily.SAME_ORDER_HOT_STREAM
            else _identity_token(
                run_id=run_id,
                plan=plan,
                identity_position=identity_position,
                purpose="independent-order",
            )
        )
        specs.append(
            InvocationSpec(
                plan=plan,
                lane_index=lane_index,
                connection_slot=lane_index,
                identity_position=identity_position,
                request_id=request_id,
                order_id=order_id,
            )
        )
    return tuple(specs)


class RecordedScheduleExecutor:
    """Consume one exact fixed schedule with level-scoped persistent resources.

    For each worker level, the supplied provider must open exactly N persistent
    connections and construct all writers and validators before yielding. This
    executor then starts exactly N persistent lane threads before the first
    warmup, reuses them across that level's four cells, and closes the topology
    only after every predetermined batch has been consumed once.
    """

    def __init__(
        self,
        *,
        open_level_runtime: OpenLevelRuntime,
        timing_source_factory: BatchTimingSourceFactory | None = None,
    ) -> None:
        self._open_level_runtime = open_level_runtime
        self._timing_source_factory = (
            timing_source_factory
            if timing_source_factory is not None
            else lambda _plan: _PerfCounterBatchTimingSource()
        )

    def execute(
        self,
        *,
        run_id: str,
        schedule: ExperimentSchedule,
    ) -> RecordedExecutionResult:
        """Execute 3 warmups and 30 recorded batches for every fixed cell once."""

        _require_safe_run_id(run_id)
        if schedule != generate_fixed_schedule(seed=schedule.seed):
            raise BoundedConcurrencyRuntimeError(
                "executor accepts only the exact deterministic PR7 schedule"
            )

        invocations: list[InvocationRecord] = []
        batches: list[BatchRecord] = []
        ownership: list[LaneOwnershipRecord] = []
        invocation_index = 0
        batch_record_index = 0

        cells_by_level: dict[int, list[CellPlan]] = defaultdict(list)
        for cell in schedule.cells:
            cells_by_level[cell.worker_level].append(cell)
        ordered_levels = tuple(dict.fromkeys(cell.worker_level for cell in schedule.cells))

        for worker_level in ordered_levels:
            with self._open_level_runtime(worker_level) as runtime:
                if runtime.worker_level != worker_level:
                    raise BoundedConcurrencyRuntimeError(
                        "runtime provider returned the wrong worker level"
                    )
                workers = _PersistentLaneWorkers(runtime)
                try:
                    ownership.extend(
                        LaneOwnershipRecord(
                            worker_level=worker_level,
                            lane_index=lane_index,
                            connection_slot=lane_index,
                            thread_id=thread_id,
                        )
                        for lane_index, thread_id in enumerate(workers.thread_ids)
                    )
                    for cell in cells_by_level[worker_level]:
                        cell_batches = tuple(
                            plan for plan in schedule.batches if plan.cell == cell
                        )
                        warmups = tuple(
                            plan for plan in cell_batches if not plan.recorded
                        )
                        recorded = tuple(
                            plan for plan in cell_batches if plan.recorded
                        )
                        runtime.reset_database()
                        for plan in warmups:
                            warmup_records, _batch = self._execute_batch(
                                run_id=run_id,
                                plan=plan,
                                runtime=runtime,
                                workers=workers,
                                invocation_index=0,
                                batch_record_index=0,
                            )
                            for record in warmup_records:
                                issues = _invocation_evidence_issues(record)
                                if issues:
                                    raise BoundedConcurrencyRuntimeError(
                                        "warmup produced invalid Level-C evidence"
                                    )
                        runtime.reset_database()
                        for plan in recorded:
                            cell_invocations, batch = self._execute_batch(
                                run_id=run_id,
                                plan=plan,
                                runtime=runtime,
                                workers=workers,
                                invocation_index=invocation_index,
                                batch_record_index=batch_record_index,
                            )
                            invocations.extend(cell_invocations)
                            batches.append(batch)
                            invocation_index += worker_level
                            batch_record_index += 1
                finally:
                    workers.close()

        validation = validate_recorded_run(
            schedule=schedule,
            invocations=invocations,
            batches=batches,
            ownership=ownership,
        )
        return RecordedExecutionResult(
            schedule=schedule,
            invocations=tuple(invocations),
            batches=tuple(batches),
            ownership=tuple(ownership),
            validation=validation,
        )

    def _execute_batch(
        self,
        *,
        run_id: str,
        plan: BatchPlan,
        runtime: LevelRuntime,
        workers: _PersistentLaneWorkers,
        invocation_index: int,
        batch_record_index: int,
    ) -> tuple[tuple[InvocationRecord, ...], BatchRecord]:
        specs = prepare_invocation_specs(run_id=run_id, plan=plan)
        runtime.prepare_batch(plan, specs)
        timing = self._timing_source_factory(plan)
        release = _ReleaseReference(timing)
        barrier = threading.Barrier(runtime.worker_level, action=release.capture)

        jobs: dict[int, Callable[[], _TimedObservation]] = {}
        for spec in specs:
            lane = runtime.lane(spec.lane_index)
            writer = lane.writers[plan.cell.composition]
            jobs[spec.lane_index] = _timed_after_barrier(
                barrier=barrier,
                timing=timing,
                spec=spec,
                writer=writer,
            )

        observations = workers.run_batch(jobs)
        reference_ns = release.reference_ns
        if reference_ns is None:
            raise BoundedConcurrencyRuntimeError("batch release reference is missing")

        records: list[InvocationRecord] = []
        for lane_index, (spec, observation) in enumerate(
            zip(specs, observations, strict=True)
        ):
            if observation.invocation_start_ns < reference_ns:
                raise BoundedConcurrencyRuntimeError(
                    "invocation timer preceded the release reference"
                )
            record = invocation_record_from_timed_observation(
                run_id=run_id,
                invocation_index=invocation_index + lane_index,
                spec=spec,
                observation=observation,
                release_reference_ns=reference_ns,
            )
            records.append(record)

        # Classification is complete before these hooks. Both verification
        # hooks run only after every lane captured its invocation stop reading.
        for spec, observation in zip(specs, observations, strict=True):
            lane = runtime.lane(spec.lane_index)
            if observation.exception_type is None:
                try:
                    runtime.verify_observation(
                        lane.connection,
                        observation.value,
                        spec,
                    )
                except Exception as exc:
                    raise ObservationVerificationError(
                        "post-timing observation verification failed: "
                        f"{type(exc).__name__}"
                    ) from exc
            try:
                runtime.verify_connection(lane.connection)
            except Exception as exc:
                raise ConnectionReuseVerificationError(
                    "post-timing connection reuse verification failed: "
                    f"{type(exc).__name__}"
                ) from exc

        batch = _build_batch_record(
            run_id=run_id,
            batch_record_index=batch_record_index,
            plan=plan,
            release_reference_ns=reference_ns,
            records=records,
        )
        return tuple(records), batch


class SmokeScheduleExecutor:
    """Execute the fixed smoke once and stop after the first invalid cell.

    Each worker-level topology is opened once, starts exactly N persistent lane
    threads, and is reused across that level's four smoke cells. The executor
    shares the canonical low-level synchronized-batch mechanics but returns
    only the distinct ``SmokeExecutionResult`` envelope. It never retries,
    replaces, extends, aggregates, serializes, or publishes a smoke cell.
    """

    def __init__(
        self,
        *,
        open_level_runtime: OpenLevelRuntime,
        timing_source_factory: BatchTimingSourceFactory | None = None,
    ) -> None:
        self._open_level_runtime = open_level_runtime
        self._batch_executor = RecordedScheduleExecutor(
            open_level_runtime=open_level_runtime,
            timing_source_factory=timing_source_factory,
        )

    def execute(
        self,
        *,
        run_id: str,
        schedule: SmokeSchedule,
    ) -> SmokeExecutionResult:
        """Execute exactly sixteen smoke bursts unless the first invalid cell stops it."""

        _require_safe_run_id(run_id)
        if schedule != generate_smoke_schedule():
            raise BoundedConcurrencyRuntimeError(
                "smoke executor accepts only the exact seed-73 smoke schedule"
            )

        invocations: list[SmokeInvocationObservation] = []
        batches: list[SmokeBatchObservation] = []
        ownership: list[LaneOwnershipRecord] = []
        runtime_facts: list[SmokeRuntimeFacts] = []
        invocation_index = 0
        batch_record_index = 0

        cells_by_level: dict[int, list[SmokeCellPlan]] = defaultdict(list)
        for cell in schedule.cells:
            cells_by_level[cell.worker_level].append(cell)
        ordered_levels = tuple(
            dict.fromkeys(cell.worker_level for cell in schedule.cells)
        )

        for worker_level in ordered_levels:
            level_cells = cells_by_level[worker_level]
            first_cell_index = level_cells[0].smoke_cell_index
            active_cell_index = first_cell_index
            try:
                with self._open_level_runtime(worker_level) as runtime:
                    if runtime.worker_level != worker_level:
                        return _invalid_smoke_result(
                            schedule=schedule,
                            invocations=invocations,
                            batches=batches,
                            ownership=ownership,
                            runtime_facts=runtime_facts,
                            issue=SmokeValidationIssue(
                                code="RUNTIME_LEVEL_MISMATCH",
                                smoke_cell_index=first_cell_index,
                                detail=f"worker_level={worker_level}",
                            ),
                        )
                    workers = _PersistentLaneWorkers(runtime)
                    try:
                        thread_ids = workers.thread_ids
                        if len(set(thread_ids)) != worker_level:
                            return _invalid_smoke_result(
                                schedule=schedule,
                                invocations=invocations,
                                batches=batches,
                                ownership=ownership,
                                runtime_facts=runtime_facts,
                                issue=SmokeValidationIssue(
                                    code="THREAD_OWNERSHIP_VIOLATION",
                                    smoke_cell_index=first_cell_index,
                                    detail=f"worker_level={worker_level}",
                                ),
                            )
                        level_ownership = tuple(
                            LaneOwnershipRecord(
                                worker_level=worker_level,
                                lane_index=lane_index,
                                connection_slot=lane_index,
                                thread_id=thread_id,
                            )
                            for lane_index, thread_id in enumerate(
                                thread_ids
                            )
                        )
                        ownership.extend(level_ownership)
                        runtime_facts.append(
                            SmokeRuntimeFacts(
                                worker_level=worker_level,
                                lane_count=len(runtime.lanes),
                                thread_count=len(thread_ids),
                                connection_count=len(
                                    {id(lane.connection) for lane in runtime.lanes}
                                ),
                                topology_label=runtime.topology_label,
                                postgresql_server_version=(
                                    runtime.postgresql_server_version
                                ),
                                isolation_level=runtime.isolation_level,
                                autocommit=runtime.autocommit,
                            )
                        )
                        for smoke_cell in level_cells:
                            active_cell_index = smoke_cell.smoke_cell_index
                            plan = smoke_cell.mechanics_plan
                            try:
                                runtime.reset_database()
                                specs = prepare_invocation_specs(
                                    run_id=run_id,
                                    plan=plan,
                                )
                                raw_records, raw_batch = (
                                    self._batch_executor._execute_batch(
                                        run_id=run_id,
                                        plan=plan,
                                        runtime=runtime,
                                        workers=workers,
                                        invocation_index=invocation_index,
                                        batch_record_index=batch_record_index,
                                    )
                                )
                            except ObservationVerificationError as exc:
                                return _invalid_smoke_result(
                                    schedule=schedule,
                                    invocations=invocations,
                                    batches=batches,
                                    ownership=ownership,
                                    runtime_facts=runtime_facts,
                                    issue=_smoke_exception_issue(
                                        code="DURABLE_VERIFICATION_FAILURE",
                                        smoke_cell_index=(
                                            smoke_cell.smoke_cell_index
                                        ),
                                        exc=exc,
                                    ),
                                )
                            except ConnectionReuseVerificationError as exc:
                                return _invalid_smoke_result(
                                    schedule=schedule,
                                    invocations=invocations,
                                    batches=batches,
                                    ownership=ownership,
                                    runtime_facts=runtime_facts,
                                    issue=_smoke_exception_issue(
                                        code="CONNECTION_REUSE_FAILURE",
                                        smoke_cell_index=(
                                            smoke_cell.smoke_cell_index
                                        ),
                                        exc=exc,
                                    ),
                                )
                            except Exception as exc:
                                return _invalid_smoke_result(
                                    schedule=schedule,
                                    invocations=invocations,
                                    batches=batches,
                                    ownership=ownership,
                                    runtime_facts=runtime_facts,
                                    issue=_smoke_exception_issue(
                                        code="SMOKE_BATCH_EXECUTION_FAILURE",
                                        smoke_cell_index=(
                                            smoke_cell.smoke_cell_index
                                        ),
                                        exc=exc,
                                    ),
                                )

                            wrapped_invocations = tuple(
                                SmokeInvocationObservation(
                                    smoke_cell_index=(
                                        smoke_cell.smoke_cell_index
                                    ),
                                    request_id=spec.request_id,
                                    order_id=spec.order_id,
                                    record=record,
                                )
                                for spec, record in zip(
                                    specs,
                                    raw_records,
                                    strict=True,
                                )
                            )
                            wrapped_batch = SmokeBatchObservation(
                                smoke_cell_index=smoke_cell.smoke_cell_index,
                                record=raw_batch,
                            )
                            invocations.extend(wrapped_invocations)
                            batches.append(wrapped_batch)
                            issues = _smoke_cell_issues(
                                cell=smoke_cell,
                                invocations=wrapped_invocations,
                                batch=wrapped_batch,
                            )
                            if issues:
                                return SmokeExecutionResult(
                                    evidence_kind=SMOKE_EVIDENCE_KIND,
                                    schedule=schedule,
                                    status=SmokeStatus.INVALID_SMOKE,
                                    invocations=tuple(invocations),
                                    batches=tuple(batches),
                                    ownership=tuple(ownership),
                                    runtime_facts=tuple(runtime_facts),
                                    issues=issues,
                                    failed_cell_index=(
                                        smoke_cell.smoke_cell_index
                                    ),
                                )
                            invocation_index += worker_level
                            batch_record_index += 1
                    finally:
                        workers.close()
            except Exception as exc:
                return _invalid_smoke_result(
                    schedule=schedule,
                    invocations=invocations,
                    batches=batches,
                    ownership=ownership,
                    runtime_facts=runtime_facts,
                    issue=_smoke_exception_issue(
                        code="LEVEL_RUNTIME_FAILURE",
                        smoke_cell_index=active_cell_index,
                        exc=exc,
                    ),
                )

        return SmokeExecutionResult(
            evidence_kind=SMOKE_EVIDENCE_KIND,
            schedule=schedule,
            status=SmokeStatus.STRUCTURALLY_VALID,
            invocations=tuple(invocations),
            batches=tuple(batches),
            ownership=tuple(ownership),
            runtime_facts=tuple(runtime_facts),
            issues=(),
            failed_cell_index=None,
        )


def _timed_after_barrier(
    *,
    barrier: threading.Barrier,
    timing: BatchTimingSource,
    spec: InvocationSpec,
    writer: Any,
) -> Callable[[], _TimedObservation]:
    def invoke() -> _TimedObservation:
        barrier.wait()
        started_ns = _read_clock(
            timing.invocation_start_ns(spec.lane_index),
            "invocation_start_ns",
        )
        try:
            value = writer.create_order_with_measurement(
                request_id=spec.request_id,
                order_id=spec.order_id,
                amount=CANONICAL_AMOUNT,
            )
        except Exception as exc:
            stopped_ns = _read_clock(
                timing.invocation_stop_ns(spec.lane_index),
                "invocation_stop_ns",
            )
            return _TimedObservation(
                value=None,
                invocation_start_ns=started_ns,
                invocation_stop_ns=stopped_ns,
                exception_type=type(exc).__name__,
            )
        stopped_ns = _read_clock(
            timing.invocation_stop_ns(spec.lane_index),
            "invocation_stop_ns",
        )
        return _TimedObservation(
            value=value,
            invocation_start_ns=started_ns,
            invocation_stop_ns=stopped_ns,
        )

    return invoke


def classify_cohort(
    *,
    producer_outcome: str,
    rejection_stage: RejectionStage | None,
    stream_admission_verdict: str | None,
    append_admission_verdict: str | None,
) -> Cohort:
    """Classify only the three exact supported Level-C terminal cohorts."""

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
        and stream_admission_verdict == "ADMITTED"
        and append_admission_verdict == "STALE_WRITE"
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
        "producer evidence is not an exact retained Level-C cohort"
    )


def invocation_record_from_timed_observation(
    *,
    run_id: str,
    invocation_index: int,
    spec: InvocationSpec,
    observation: _TimedObservation,
    release_reference_ns: int,
) -> InvocationRecord:
    """Convert one raw measured delivery without hiding invalid evidence."""

    start_offset_ns = observation.invocation_start_ns - release_reference_ns
    common = dict(
        schema_name=LEVEL_C_SCHEMA_NAME,
        schema_version=LEVEL_C_SCHEMA_VERSION,
        run_id=run_id,
        invocation_index=invocation_index,
        cell_index=spec.plan.cell.cell_index,
        batch_index=spec.plan.batch_index,
        lane_index=spec.lane_index,
        connection_slot=spec.connection_slot,
        worker_level=spec.plan.cell.worker_level,
        workload_family=spec.plan.cell.workload_family,
        composition=spec.plan.cell.composition,
        external_elapsed_ns=observation.elapsed_ns,
        start_offset_ns=start_offset_ns,
    )
    if observation.exception_type is not None:
        return InvocationRecord(
            **common,
            producer_outcome=None,
            rejection_stage=None,
            stream_admission_verdict=None,
            append_admission_verdict=None,
            cohort=None,
            measurement_availability=None,
            phases=None,
            exception_type=observation.exception_type,
        )

    raw_delivery = observation.value
    availability = _enum_value_or_none(getattr(raw_delivery, "availability", None))
    phases: tuple[PhaseRecord, ...] | None = None
    if availability == "AVAILABLE":
        measurement = getattr(raw_delivery, "measurement", None)
        if measurement is not None:
            parsed = tuple(
                phase
                for name in PR3_PHASE_NAMES
                if (phase := _parse_phase(name, getattr(measurement, name, None)))
                is not None
            )
            phases = parsed
    producer_value = getattr(raw_delivery, "producer_value", None)
    producer_outcome = _enum_value_or_none(
        getattr(producer_value, "outcome", None)
    )
    stream_admission_verdict = _nested_verdict_or_none(
        getattr(producer_value, "stream_admission_result", None)
    )
    append_admission_verdict = _nested_verdict_or_none(
        getattr(producer_value, "admission_result", None)
    )
    rejection_stage = _rejection_stage(
        producer_outcome=producer_outcome,
        stream_admission_verdict=stream_admission_verdict,
        append_admission_verdict=append_admission_verdict,
    )
    cohort: Cohort | None = None
    if producer_outcome is not None:
        try:
            cohort = classify_cohort(
                producer_outcome=producer_outcome,
                rejection_stage=rejection_stage,
                stream_admission_verdict=stream_admission_verdict,
                append_admission_verdict=append_admission_verdict,
            )
        except UnsupportedCohortError:
            pass

    return InvocationRecord(
        **common,
        producer_outcome=producer_outcome,
        rejection_stage=rejection_stage,
        stream_admission_verdict=stream_admission_verdict,
        append_admission_verdict=append_admission_verdict,
        cohort=cohort,
        measurement_availability=availability,
        phases=phases,
    )


def validate_recorded_run(
    *,
    schedule: ExperimentSchedule,
    invocations: Sequence[InvocationRecord],
    batches: Sequence[BatchRecord],
    ownership: Sequence[LaneOwnershipRecord],
) -> RunValidationResult:
    """Validate exact accounting; no finding authorizes replacement work."""

    issues: list[ValidationIssue] = []
    expected_schedule = generate_fixed_schedule(seed=schedule.seed)
    if schedule != expected_schedule:
        issues.append(
            ValidationIssue(
                "NON_CANONICAL_SCHEDULE",
                "schedule differs from the exact fixed generator",
            )
        )

    expected_invocations: dict[
        tuple[int, int, int], tuple[int, BatchPlan]
    ] = {}
    expected_batches: dict[tuple[int, int], tuple[int, BatchPlan]] = {}
    next_invocation_index = 0
    next_batch_record_index = 0
    for plan in schedule.batches:
        if not plan.recorded:
            continue
        expected_batches[(plan.cell.cell_index, plan.batch_index)] = (
            next_batch_record_index,
            plan,
        )
        for lane_index in range(plan.cell.worker_level):
            expected_invocations[
                (plan.cell.cell_index, plan.batch_index, lane_index)
            ] = (next_invocation_index, plan)
            next_invocation_index += 1
        next_batch_record_index += 1

    observed_invocations: dict[tuple[int, int, int], InvocationRecord] = {}
    invocation_indexes: set[int] = set()
    for record in invocations:
        key = (record.cell_index, record.batch_index, record.lane_index)
        if key in observed_invocations:
            issues.append(ValidationIssue("DUPLICATE_INVOCATION", str(key)))
        observed_invocations[key] = record
        if record.invocation_index in invocation_indexes:
            issues.append(
                ValidationIssue(
                    "DUPLICATE_INVOCATION_INDEX",
                    f"invocation_index={record.invocation_index}",
                )
            )
        invocation_indexes.add(record.invocation_index)

    for key in sorted(set(expected_invocations) - set(observed_invocations)):
        issues.append(ValidationIssue("MISSING_INVOCATION", str(key)))
    for key in sorted(set(observed_invocations) - set(expected_invocations)):
        issues.append(
            ValidationIssue(
                "UNPLANNED_INVOCATION",
                f"{key}; adaptive extension is forbidden",
            )
        )

    for key in sorted(set(expected_invocations) & set(observed_invocations)):
        expected_index, plan = expected_invocations[key]
        record = observed_invocations[key]
        expected_identity = (
            LEVEL_C_SCHEMA_NAME,
            LEVEL_C_SCHEMA_VERSION,
            expected_index,
            plan.cell.cell_index,
            plan.batch_index,
            key[2],
            key[2],
            plan.cell.worker_level,
            plan.cell.workload_family,
            plan.cell.composition,
        )
        observed_identity = (
            record.schema_name,
            record.schema_version,
            record.invocation_index,
            record.cell_index,
            record.batch_index,
            record.lane_index,
            record.connection_slot,
            record.worker_level,
            record.workload_family,
            record.composition,
        )
        if observed_identity != expected_identity:
            issues.append(ValidationIssue("INVOCATION_PLAN_MISMATCH", str(key)))
        issues.extend(_invocation_evidence_issues(record))

    observed_batches: dict[tuple[int, int], BatchRecord] = {}
    batch_indexes: set[int] = set()
    for batch in batches:
        key = (batch.cell_index, batch.batch_index)
        if key in observed_batches:
            issues.append(ValidationIssue("DUPLICATE_BATCH", str(key)))
        observed_batches[key] = batch
        if batch.batch_record_index in batch_indexes:
            issues.append(
                ValidationIssue(
                    "DUPLICATE_BATCH_RECORD_INDEX",
                    f"batch_record_index={batch.batch_record_index}",
                )
            )
        batch_indexes.add(batch.batch_record_index)

    for key in sorted(set(expected_batches) - set(observed_batches)):
        issues.append(ValidationIssue("MISSING_BATCH", str(key)))
    for key in sorted(set(observed_batches) - set(expected_batches)):
        issues.append(
            ValidationIssue(
                "UNPLANNED_BATCH",
                f"{key}; replacement or adaptive extension is forbidden",
            )
        )

    for key in sorted(set(expected_batches) & set(observed_batches)):
        expected_index, plan = expected_batches[key]
        batch = observed_batches[key]
        expected_identity = (
            LEVEL_C_SCHEMA_NAME,
            LEVEL_C_SCHEMA_VERSION,
            expected_index,
            plan.cell.cell_index,
            plan.batch_index,
            plan.cell.worker_level,
            plan.cell.workload_family,
            plan.cell.composition,
        )
        observed_identity = (
            batch.schema_name,
            batch.schema_version,
            batch.batch_record_index,
            batch.cell_index,
            batch.batch_index,
            batch.worker_level,
            batch.workload_family,
            batch.composition,
        )
        if observed_identity != expected_identity:
            issues.append(ValidationIssue("BATCH_PLAN_MISMATCH", str(key)))

        records = tuple(
            observed_invocations[item]
            for item in sorted(observed_invocations)
            if item[0] == key[0] and item[1] == key[1]
        )
        if batch.completed_count != plan.cell.worker_level:
            issues.append(
                ValidationIssue(
                    "INCOMPLETE_BATCH",
                    f"{key}; completed_count={batch.completed_count}",
                )
            )
        if len(records) == plan.cell.worker_level:
            expected_accepted = sum(
                record.cohort is Cohort.ACCEPTED for record in records
            )
            if batch.accepted_count != expected_accepted:
                issues.append(ValidationIssue("ACCEPTED_COUNT_MISMATCH", str(key)))
            expected_counts = _typed_counts(records)
            if batch.typed_outcome_counts != expected_counts:
                issues.append(ValidationIssue("OUTCOME_COUNT_MISMATCH", str(key)))
            expected_first = min(record.start_offset_ns for record in records)
            expected_last = max(record.start_offset_ns for record in records)
            expected_elapsed = max(
                record.start_offset_ns + record.external_elapsed_ns
                for record in records
            )
            if (
                batch.first_start_offset_ns != expected_first
                or batch.last_start_offset_ns != expected_last
                or batch.batch_elapsed_ns != expected_elapsed
            ):
                issues.append(ValidationIssue("BATCH_TIMING_MISMATCH", str(key)))

    expected_ownership = {
        (level, lane_index, lane_index)
        for level in RETAINED_WORKER_LEVELS
        for lane_index in range(level)
    }
    observed_ownership = {
        (item.worker_level, item.lane_index, item.connection_slot)
        for item in ownership
    }
    if len(ownership) != sum(RETAINED_WORKER_LEVELS):
        issues.append(
            ValidationIssue(
                "OWNERSHIP_COUNT_MISMATCH",
                "ownership must contain exactly one record per retained lane",
            )
        )
    if observed_ownership != expected_ownership:
        issues.append(
            ValidationIssue(
                "CONNECTION_OWNERSHIP_VIOLATION",
                "lane and connection-slot ownership is not exact",
            )
        )
    thread_ids_by_level: dict[int, set[int]] = defaultdict(set)
    for item in ownership:
        thread_ids_by_level[item.worker_level].add(item.thread_id)
    for level in RETAINED_WORKER_LEVELS:
        if len(thread_ids_by_level[level]) != level:
            issues.append(
                ValidationIssue(
                    "THREAD_OWNERSHIP_VIOLATION",
                    f"worker_level={level}",
                )
            )

    run_ids = {record.run_id for record in invocations} | {
        batch.run_id for batch in batches
    }
    if len(run_ids) != 1:
        issues.append(
            ValidationIssue(
                "RUN_ID_MISMATCH",
                "all invocation and batch records must share one run identity",
            )
        )
    return RunValidationResult(
        status=EvidenceStatus.INVALID_RUN if issues else EvidenceStatus.VALID,
        issues=tuple(issues),
    )


def aggregate_invocations(
    invocations: Sequence[InvocationRecord],
) -> tuple[InvocationAggregate, ...]:
    """Aggregate exact typed cohorts without pooling outcomes or families."""

    if any(not isinstance(record, InvocationRecord) for record in invocations):
        raise TypeError("canonical aggregation accepts InvocationRecord only")

    grouped: dict[
        tuple[str, int, WorkloadFamily, Composition, Cohort],
        list[InvocationRecord],
    ] = defaultdict(list)
    for record in invocations:
        if _invocation_evidence_issues(record):
            raise ValueError("invalid or unsupported invocation cannot be aggregated")
        assert record.cohort is not None
        grouped[
            (
                record.run_id,
                record.worker_level,
                record.workload_family,
                record.composition,
                record.cohort,
            )
        ].append(record)

    aggregates: list[InvocationAggregate] = []
    for key in sorted(grouped, key=lambda item: tuple(_sort_value(v) for v in item)):
        run_id, worker_level, workload_family, composition, cohort = key
        records = grouped[key]
        phases: list[PhaseAggregate] = []
        for phase_name in PR3_PHASE_NAMES:
            values = [
                phase.elapsed_ns
                for record in records
                for phase in record.phases or ()
                if phase.name == phase_name and phase.state is PhaseState.MEASURED
            ]
            if values:
                phases.append(
                    PhaseAggregate(
                        phase_name=phase_name,
                        statistics_ns=_describe(
                            [float(value) for value in values if value is not None]
                        ),
                    )
                )
        aggregates.append(
            InvocationAggregate(
                run_id=run_id,
                worker_level=worker_level,
                workload_family=workload_family,
                composition=composition,
                cohort=cohort,
                external_elapsed_ns=_describe(
                    [float(record.external_elapsed_ns) for record in records]
                ),
                phases=tuple(phases),
            )
        )
    return tuple(aggregates)


def batch_completion_rates(batch: BatchRecord) -> BatchCompletionRates:
    """Derive only synchronized-burst completion rates for one batch."""

    if not isinstance(batch, BatchRecord):
        raise TypeError("canonical batch rates accept BatchRecord only")
    if batch.batch_elapsed_ns <= 0:
        raise ValueError("batch elapsed must be positive for completion rates")
    scale = 1_000_000_000 / batch.batch_elapsed_ns
    return BatchCompletionRates(
        accepted_completion_rate_per_second=batch.accepted_count * scale,
        all_completion_rate_per_second=batch.completed_count * scale,
    )


def aggregate_batch_rates(
    batches: Sequence[BatchRecord],
) -> tuple[BatchRateAggregate, ...]:
    """Aggregate protocol-qualified batch rates by exact Level-C cell."""

    if any(not isinstance(batch, BatchRecord) for batch in batches):
        raise TypeError("canonical aggregation accepts BatchRecord only")

    grouped: dict[
        tuple[str, int, WorkloadFamily, Composition],
        list[BatchCompletionRates],
    ] = defaultdict(list)
    for batch in batches:
        grouped[
            (
                batch.run_id,
                batch.worker_level,
                batch.workload_family,
                batch.composition,
            )
        ].append(batch_completion_rates(batch))
    results: list[BatchRateAggregate] = []
    for key in sorted(grouped, key=lambda item: tuple(_sort_value(v) for v in item)):
        run_id, worker_level, workload_family, composition = key
        rates = grouped[key]
        results.append(
            BatchRateAggregate(
                run_id=run_id,
                worker_level=worker_level,
                workload_family=workload_family,
                composition=composition,
                accepted_completion_rate_per_second=_describe(
                    [rate.accepted_completion_rate_per_second for rate in rates]
                ),
                all_completion_rate_per_second=_describe(
                    [rate.all_completion_rate_per_second for rate in rates]
                ),
            )
        )
    return tuple(results)


def invocation_record_to_dict(record: InvocationRecord) -> dict[str, Any]:
    """Serialize one stable PR7 invocation without endpoint or governance data."""

    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "run_id": record.run_id,
        "invocation_index": record.invocation_index,
        "cell_index": record.cell_index,
        "batch_index": record.batch_index,
        "lane_index": record.lane_index,
        "connection_slot": record.connection_slot,
        "worker_level": record.worker_level,
        "workload_family": record.workload_family.value,
        "composition": record.composition.value,
        "external_elapsed_ns": record.external_elapsed_ns,
        "start_offset_ns": record.start_offset_ns,
        "producer_outcome": record.producer_outcome,
        "rejection_stage": (
            None if record.rejection_stage is None else record.rejection_stage.value
        ),
        "stream_admission_verdict": record.stream_admission_verdict,
        "append_admission_verdict": record.append_admission_verdict,
        "cohort": None if record.cohort is None else record.cohort.value,
        "measurement_availability": record.measurement_availability,
        "phases": (
            None
            if record.phases is None
            else [
                {
                    "name": phase.name,
                    "state": phase.state.value,
                    "elapsed_ns": phase.elapsed_ns,
                }
                for phase in record.phases
            ]
        ),
        "exception_type": record.exception_type,
    }


def batch_record_to_dict(batch: BatchRecord) -> dict[str, Any]:
    """Serialize one stable PR7 batch without interpreting completion rates."""

    return {
        "schema_name": batch.schema_name,
        "schema_version": batch.schema_version,
        "run_id": batch.run_id,
        "batch_record_index": batch.batch_record_index,
        "cell_index": batch.cell_index,
        "batch_index": batch.batch_index,
        "worker_level": batch.worker_level,
        "workload_family": batch.workload_family.value,
        "composition": batch.composition.value,
        "release_reference_ns": batch.release_reference_ns,
        "first_start_offset_ns": batch.first_start_offset_ns,
        "last_start_offset_ns": batch.last_start_offset_ns,
        "batch_elapsed_ns": batch.batch_elapsed_ns,
        "completed_count": batch.completed_count,
        "accepted_count": batch.accepted_count,
        "typed_outcome_counts": [
            {"outcome": item.outcome, "count": item.count}
            for item in batch.typed_outcome_counts
        ],
    }


def invocation_records_to_jsonl(
    records: Sequence[InvocationRecord],
) -> str:
    """Return deterministic in-memory JSONL; this function publishes no file."""

    return "".join(
        json.dumps(invocation_record_to_dict(record), sort_keys=True) + "\n"
        for record in records
    )


def batch_records_to_jsonl(records: Sequence[BatchRecord]) -> str:
    """Return deterministic in-memory JSONL; this function publishes no file."""

    return "".join(
        json.dumps(batch_record_to_dict(record), sort_keys=True) + "\n"
        for record in records
    )


@contextmanager
def open_postgres_level_runtime(
    *,
    database_url: str,
    worker_level: int,
) -> Iterator[LevelRuntime]:
    """Pre-open exactly N guarded PostgreSQL lanes for a later authorized run.

    The URL is passed only to the repository connection constructor and is not
    retained or serialized. Opening constructs every connection, validation
    runtime, gate factory, composition writer, and lane before yielding. It does
    not invoke a producer, warm up, time work, or publish evidence by itself.
    """

    if not isinstance(database_url, str) or not database_url:
        raise BoundedConcurrencyRuntimeError("test database configuration is absent")
    if worker_level not in RETAINED_WORKER_LEVELS:
        raise BoundedConcurrencyRuntimeError("worker level is not retained by PR7")
    from src.storage.postgres_connection import connect_postgres

    connections: list[Any] = []
    try:
        for _lane_index in range(worker_level):
            connection = connect_postgres(database_url)
            connections.append(connection)
            _guard_test_database(connection)
        lanes = tuple(
            LaneRuntime(
                lane_index=lane_index,
                connection=connection,
                writers={
                    composition: _build_current_writer(
                        connection=connection,
                        composition=composition,
                    )
                    for composition in Composition
                },
            )
            for lane_index, connection in enumerate(connections)
        )
        control_connection = connections[0]
        server_version, isolation_level = _postgres_runtime_facts(control_connection)
        yield LevelRuntime(
            worker_level=worker_level,
            lanes=lanes,
            reset_database=lambda: _guarded_postgres_reset(
                control_connection=control_connection,
                all_connections=tuple(connections),
            ),
            prepare_batch=lambda plan, specs: _prepare_postgres_batch(
                connection=control_connection,
                plan=plan,
                specs=specs,
            ),
            verify_observation=_verify_postgres_observation,
            verify_connection=_require_select_one_and_restore_idle,
            postgresql_server_version=server_version,
            isolation_level=isolation_level,
            autocommit=bool(control_connection.autocommit),
        )
    finally:
        for connection in connections:
            connection.close()


def run_postgres_smoke(
    *,
    database_url: str,
    run_id: str,
    timing_source_factory: BatchTimingSourceFactory | None = None,
) -> SmokeExecutionResult:
    """Run only the guarded PostgreSQL smoke when separately authorized.

    This callable opens each reviewed worker-level topology once, delegates to
    the fixed smoke executor, and returns in-memory correctness evidence. It is
    never called on import, exposes no canonical execution, creates no pool,
    changes no server configuration, publishes nothing, and derives no
    capacity, throughput, admission, or rate-limit policy.
    """

    @contextmanager
    def open_level(worker_level: int) -> Iterator[LevelRuntime]:
        with open_postgres_level_runtime(
            database_url=database_url,
            worker_level=worker_level,
        ) as runtime:
            yield runtime

    return SmokeScheduleExecutor(
        open_level_runtime=open_level,
        timing_source_factory=timing_source_factory,
    ).execute(
        run_id=run_id,
        schedule=generate_smoke_schedule(),
    )


def _build_current_writer(*, connection: Any, composition: Composition) -> Any:
    """Build one exact current measured writer for a retained composition."""

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
        validation_runtime=_build_validation_runtime(),
        admission_gate_factory=_admission_gate_factory(composition),
        config=PostgresWriteSideConfig(validation_placement=placement),
    )
    if type(writer) is not PostgresTransactionalWriteSide:
        raise BoundedConcurrencyRuntimeError("writer is not the exact current class")
    if getattr(writer, "_connection", None) is not connection:
        raise BoundedConcurrencyRuntimeError("writer does not own its lane connection")
    return writer


def _build_validation_runtime() -> Any:
    """Construct one lane-and-composition-owned FullProofValidator STRICT stack."""

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
    runtime = ValidationRuntime(
        dispatcher=dispatcher,
        policy=ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )
    if type(runtime.dispatcher.strict_validator) is not FullProofValidator:
        raise BoundedConcurrencyRuntimeError("strict validator is not FullProofValidator")
    if runtime.mode is not ValidationMode.STRICT:
        raise BoundedConcurrencyRuntimeError("validation mode is not STRICT")
    return runtime


def _admission_gate_factory(composition: Composition) -> Callable[[Any], Any]:
    """Return the exact optimistic or concrete pessimistic gate constructor."""

    from src.pipeline.transactional.postgres_admission import (
        PostgresOptimisticAdmissionGate,
        PostgresPessimisticAdmissionGate,
    )

    if composition is Composition.PRE_OCC:
        def optimistic(uow: Any) -> Any:
            gate = PostgresOptimisticAdmissionGate(uow.event_store)
            if type(gate) is not PostgresOptimisticAdmissionGate:
                raise BoundedConcurrencyRuntimeError("PRE gate class changed")
            return gate

        return optimistic
    if composition is Composition.IN_PESSIMISTIC:
        def pessimistic(uow: Any) -> Any:
            gate = PostgresPessimisticAdmissionGate(
                connection=uow.connection,
                event_store=uow.event_store,
            )
            if type(gate) is not PostgresPessimisticAdmissionGate:
                raise BoundedConcurrencyRuntimeError("IN gate class changed")
            return gate

        return pessimistic
    raise TypeError("composition must be a PR7 Composition")


def _guard_test_database(connection: Any) -> None:
    """Apply the repository `_test` guard and restore the connection to IDLE."""

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
        raise BoundedConcurrencyRuntimeError(
            "refusing PR7 runtime because database name does not end with _test"
        )
    if connection.autocommit:
        raise BoundedConcurrencyRuntimeError("PR7 runtime requires autocommit disabled")
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise BoundedConcurrencyRuntimeError("database guard did not restore IDLE")


def _guarded_postgres_reset(
    *,
    control_connection: Any,
    all_connections: Sequence[Any],
) -> None:
    """Reset only the guarded test tables while every worker lane is idle."""

    for connection in all_connections:
        _require_select_one_and_restore_idle(connection)
    _guard_test_database(control_connection)
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


def _prepare_postgres_batch(
    *,
    connection: Any,
    plan: BatchPlan,
    specs: Sequence[InvocationSpec],
) -> None:
    """Prove every prepared order has empty accepted history before release."""

    del plan
    from src.storage.postgres_event_store import PostgresEventStore

    store = PostgresEventStore(connection)
    try:
        for order_id in sorted({spec.order_id for spec in specs}):
            if store.load(order_id):
                raise BoundedConcurrencyRuntimeError(
                    "prepared batch order did not have empty history"
                )
    finally:
        connection.rollback()
    _require_select_one_and_restore_idle(connection)


def _verify_postgres_observation(
    connection: Any,
    raw_delivery: Any,
    spec: InvocationSpec,
) -> None:
    """Verify durable accepted/rejected behavior after batch timing ends."""

    from psycopg.pq import TransactionStatus
    from src.storage.postgres_event_store import PostgresEventStore

    producer_value = getattr(raw_delivery, "producer_value", None)
    outcome = _enum_value_or_none(getattr(producer_value, "outcome", None))
    event = getattr(producer_value, "accepted_event", None)
    validation = getattr(producer_value, "validation_decision", None)
    validation_result = getattr(validation, "validation_result", None)
    if validation_result is not None:
        _require_strict_full_proof_validation(validation_result)
    elif outcome == "ACCEPTED":
        raise BoundedConcurrencyRuntimeError(
            "accepted CREATE omitted strict validation evidence"
        )
    if outcome == "ACCEPTED":
        if (
            event is None
            or event.request_id != spec.request_id
            or event.order_id != spec.order_id
            or event.sequence != CANONICAL_EXPECTED_SEQUENCE
            or str(event.amount) != str(CANONICAL_AMOUNT)
        ):
            raise BoundedConcurrencyRuntimeError(
                "accepted CREATE returned an unexpected event"
            )
    try:
        history = PostgresEventStore(connection).load(spec.order_id)
    finally:
        connection.rollback()
    if outcome == "ACCEPTED":
        if history != [event]:
            raise BoundedConcurrencyRuntimeError(
                "accepted CREATE did not persist exactly once"
            )
    elif any(observed.request_id == spec.request_id for observed in history):
        raise BoundedConcurrencyRuntimeError(
            "rejected CREATE request appeared in accepted history"
        )
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise BoundedConcurrencyRuntimeError(
            "persistence verification did not restore IDLE"
        )


def _require_strict_full_proof_validation(validation_result: Any) -> None:
    from src.compass.transition.types import ValidationMode

    if getattr(validation_result, "validator_name", None) != "FullProofValidator":
        raise BoundedConcurrencyRuntimeError(
            "CREATE did not use FullProofValidator"
        )
    if getattr(validation_result, "validation_mode", None) is not ValidationMode.STRICT:
        raise BoundedConcurrencyRuntimeError("CREATE did not use ValidationMode.STRICT")


def _require_select_one_and_restore_idle(connection: Any) -> None:
    """Prove one lane connection remains reusable and restore it to IDLE."""

    from psycopg.pq import TransactionStatus

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
    if row != (1,):
        raise BoundedConcurrencyRuntimeError("post-invocation SELECT 1 failed")
    connection.rollback()
    if connection.info.transaction_status is not TransactionStatus.IDLE:
        raise BoundedConcurrencyRuntimeError("worker connection did not restore IDLE")


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


def _frozen_phase_matrix(
    states: Mapping[str, PhaseState],
) -> Mapping[str, PhaseState]:
    """Freeze one exact thirteen-phase topology after validating its vocabulary."""

    if set(states) != set(PR3_PHASE_NAMES) or len(states) != len(PR3_PHASE_NAMES):
        raise BoundedConcurrencyRuntimeError(
            "phase-state matrix must define every PR3 phase exactly once"
        )
    return MappingProxyType(dict(states))


EXPECTED_PHASE_STATE_MATRICES: Mapping[
    tuple[Composition, Cohort], Mapping[str, PhaseState]
] = MappingProxyType(
    {
        (
            Composition.PRE_OCC,
            Cohort.ACCEPTED,
        ): _frozen_phase_matrix(
            {
                "producer_write_invocation": PhaseState.MEASURED,
                "business_uow": PhaseState.MEASURED,
                "validation_runtime_call": PhaseState.MEASURED,
                "preliminary_idempotency_check": PhaseState.MEASURED,
                "preliminary_read_cleanup": PhaseState.MEASURED,
                "authoritative_idempotency_check": PhaseState.MEASURED,
                "accepted_history_load": PhaseState.MEASURED,
                "concurrency_preparation_call": PhaseState.MEASURED,
                "pessimistic_advisory_try_lock_call": PhaseState.NOT_APPLICABLE,
                "append_admission_call": PhaseState.MEASURED,
                "idempotency_record_call": PhaseState.MEASURED,
                "commit_finalization": PhaseState.MEASURED,
                "rollback_finalization": PhaseState.NOT_REACHED,
            }
        ),
        (
            Composition.PRE_OCC,
            Cohort.APPEND_STALE_WRITE,
        ): _frozen_phase_matrix(
            {
                "producer_write_invocation": PhaseState.MEASURED,
                "business_uow": PhaseState.MEASURED,
                "validation_runtime_call": PhaseState.MEASURED,
                "preliminary_idempotency_check": PhaseState.MEASURED,
                "preliminary_read_cleanup": PhaseState.MEASURED,
                "authoritative_idempotency_check": PhaseState.MEASURED,
                "accepted_history_load": PhaseState.MEASURED,
                "concurrency_preparation_call": PhaseState.MEASURED,
                "pessimistic_advisory_try_lock_call": PhaseState.NOT_APPLICABLE,
                "append_admission_call": PhaseState.MEASURED,
                "idempotency_record_call": PhaseState.NOT_REACHED,
                "commit_finalization": PhaseState.NOT_REACHED,
                "rollback_finalization": PhaseState.MEASURED,
            }
        ),
        (
            Composition.IN_PESSIMISTIC,
            Cohort.ACCEPTED,
        ): _frozen_phase_matrix(
            {
                "producer_write_invocation": PhaseState.MEASURED,
                "business_uow": PhaseState.MEASURED,
                "validation_runtime_call": PhaseState.MEASURED,
                "preliminary_idempotency_check": PhaseState.NOT_APPLICABLE,
                "preliminary_read_cleanup": PhaseState.NOT_APPLICABLE,
                "authoritative_idempotency_check": PhaseState.MEASURED,
                "accepted_history_load": PhaseState.MEASURED,
                "concurrency_preparation_call": PhaseState.MEASURED,
                "pessimistic_advisory_try_lock_call": PhaseState.MEASURED,
                "append_admission_call": PhaseState.MEASURED,
                "idempotency_record_call": PhaseState.MEASURED,
                "commit_finalization": PhaseState.MEASURED,
                "rollback_finalization": PhaseState.NOT_REACHED,
            }
        ),
        (
            Composition.IN_PESSIMISTIC,
            Cohort.PREPARE_LOCK_TIMEOUT,
        ): _frozen_phase_matrix(
            {
                "producer_write_invocation": PhaseState.MEASURED,
                "business_uow": PhaseState.MEASURED,
                "validation_runtime_call": PhaseState.NOT_REACHED,
                "preliminary_idempotency_check": PhaseState.NOT_APPLICABLE,
                "preliminary_read_cleanup": PhaseState.NOT_APPLICABLE,
                "authoritative_idempotency_check": PhaseState.MEASURED,
                "accepted_history_load": PhaseState.NOT_REACHED,
                "concurrency_preparation_call": PhaseState.MEASURED,
                "pessimistic_advisory_try_lock_call": PhaseState.MEASURED,
                "append_admission_call": PhaseState.NOT_REACHED,
                "idempotency_record_call": PhaseState.NOT_REACHED,
                "commit_finalization": PhaseState.NOT_REACHED,
                "rollback_finalization": PhaseState.MEASURED,
            }
        ),
    }
)


def _invocation_evidence_issues(record: InvocationRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    identity = (
        f"cell={record.cell_index}; batch={record.batch_index}; "
        f"lane={record.lane_index}"
    )
    if record.connection_slot != record.lane_index:
        issues.append(ValidationIssue("CONNECTION_OWNERSHIP_VIOLATION", identity))
    if record.exception_type is not None:
        issues.append(
            ValidationIssue(
                "UNEXPECTED_EXCEPTION",
                f"{identity}; type={record.exception_type}",
            )
        )
        return issues
    expected_matrix: Mapping[str, PhaseState] | None = None
    if record.cohort is None:
        issues.append(ValidationIssue("UNSUPPORTED_OUTCOME", identity))
    else:
        expected_matrix = EXPECTED_PHASE_STATE_MATRICES.get(
            (record.composition, record.cohort)
        )
        if expected_matrix is None:
            issues.append(
                ValidationIssue(
                    "UNSUPPORTED_COMPOSITION_COHORT",
                    f"{identity}; composition={record.composition.value}; "
                    f"cohort={record.cohort.value}",
                )
            )
        elif (
            record.workload_family
            is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
            and record.cohort is not Cohort.ACCEPTED
        ):
            issues.append(
                ValidationIssue(
                    "UNSUPPORTED_WORKLOAD_COHORT",
                    f"{identity}; cohort={record.cohort.value}",
                )
            )
    if record.measurement_availability != "AVAILABLE":
        issues.append(ValidationIssue("MEASUREMENT_UNAVAILABLE", identity))
        return issues
    names = tuple(phase.name for phase in record.phases or ())
    if set(names) != set(PR3_PHASE_NAMES) or len(names) != len(PR3_PHASE_NAMES):
        issues.append(ValidationIssue("MISSING_PHASE_RECORD", identity))
        return issues
    if expected_matrix is not None:
        phases = {phase.name: phase for phase in record.phases or ()}
        for phase_name in PR3_PHASE_NAMES:
            expected_state = expected_matrix[phase_name]
            observed_state = phases[phase_name].state
            if observed_state is not expected_state:
                issues.append(
                    ValidationIssue(
                        "PHASE_STATE_MISMATCH",
                        f"{identity}; phase={phase_name}; "
                        f"expected={expected_state.value}; "
                        f"observed={observed_state.value}",
                    )
                )
    return issues


def _smoke_cell_issues(
    *,
    cell: SmokeCellPlan,
    invocations: Sequence[SmokeInvocationObservation],
    batch: SmokeBatchObservation,
) -> tuple[SmokeValidationIssue, ...]:
    """Validate one completed smoke cell before any later cell may execute."""

    issues: list[SmokeValidationIssue] = []
    plan = cell.mechanics_plan
    raw_records = tuple(item.record for item in invocations)
    identity = f"cell={cell.smoke_cell_index}"

    if len(invocations) != cell.worker_level:
        issues.append(
            SmokeValidationIssue(
                code="INCOMPLETE_INVOCATION_ACCOUNTING",
                smoke_cell_index=cell.smoke_cell_index,
                detail=f"{identity}; count={len(invocations)}",
            )
        )

    lanes = tuple(item.record.lane_index for item in invocations)
    if lanes != tuple(range(cell.worker_level)):
        issues.append(
            SmokeValidationIssue(
                code="LANE_ACCOUNTING_MISMATCH",
                smoke_cell_index=cell.smoke_cell_index,
                detail=f"{identity}; lanes={lanes}",
            )
        )

    for item in invocations:
        record = item.record
        expected_identity = (
            plan.cell.cell_index,
            plan.batch_index,
            record.lane_index,
            plan.cell.worker_level,
            plan.cell.workload_family,
            plan.cell.composition,
        )
        observed_identity = (
            record.cell_index,
            record.batch_index,
            record.connection_slot,
            record.worker_level,
            record.workload_family,
            record.composition,
        )
        if observed_identity != expected_identity:
            issues.append(
                SmokeValidationIssue(
                    code="SMOKE_INVOCATION_PLAN_MISMATCH",
                    smoke_cell_index=cell.smoke_cell_index,
                    detail=f"{identity}; lane={record.lane_index}",
                )
            )
        issues.extend(
            SmokeValidationIssue(
                code=issue.code,
                smoke_cell_index=cell.smoke_cell_index,
                detail=issue.detail,
            )
            for issue in _invocation_evidence_issues(record)
        )

    request_ids = tuple(item.request_id for item in invocations)
    order_ids = tuple(item.order_id for item in invocations)
    if len(set(request_ids)) != cell.worker_level:
        issues.append(
            SmokeValidationIssue(
                code="REQUEST_IDENTITY_MISMATCH",
                smoke_cell_index=cell.smoke_cell_index,
                detail=f"{identity}; request identities are not distinct",
            )
        )
    expected_order_count = (
        1
        if cell.workload_family is WorkloadFamily.SAME_ORDER_HOT_STREAM
        else cell.worker_level
    )
    if len(set(order_ids)) != expected_order_count:
        issues.append(
            SmokeValidationIssue(
                code="ORDER_IDENTITY_MISMATCH",
                smoke_cell_index=cell.smoke_cell_index,
                detail=(
                    f"{identity}; expected_distinct_orders={expected_order_count}"
                ),
            )
        )

    if cell.worker_level == 1 and any(
        record.cohort is not Cohort.ACCEPTED for record in raw_records
    ):
        issues.append(
            SmokeValidationIssue(
                code="UNCONTENDED_COHORT_MISMATCH",
                smoke_cell_index=cell.smoke_cell_index,
                detail=f"{identity}; worker_level=1 must be ACCEPTED",
            )
        )

    raw_batch = batch.record
    expected_batch_identity = (
        plan.cell.cell_index,
        plan.batch_index,
        plan.cell.worker_level,
        plan.cell.workload_family,
        plan.cell.composition,
    )
    observed_batch_identity = (
        raw_batch.cell_index,
        raw_batch.batch_index,
        raw_batch.worker_level,
        raw_batch.workload_family,
        raw_batch.composition,
    )
    if observed_batch_identity != expected_batch_identity:
        issues.append(
            SmokeValidationIssue(
                code="SMOKE_BATCH_PLAN_MISMATCH",
                smoke_cell_index=cell.smoke_cell_index,
                detail=identity,
            )
        )
    if raw_batch.completed_count != cell.worker_level:
        issues.append(
            SmokeValidationIssue(
                code="INCOMPLETE_BATCH_ACCOUNTING",
                smoke_cell_index=cell.smoke_cell_index,
                detail=(
                    f"{identity}; completed_count={raw_batch.completed_count}"
                ),
            )
        )
    if len(raw_records) == cell.worker_level:
        expected_accepted = sum(
            record.cohort is Cohort.ACCEPTED for record in raw_records
        )
        expected_counts = _typed_counts(raw_records)
        expected_first = min(record.start_offset_ns for record in raw_records)
        expected_last = max(record.start_offset_ns for record in raw_records)
        expected_elapsed = max(
            record.start_offset_ns + record.external_elapsed_ns
            for record in raw_records
        )
        if raw_batch.accepted_count != expected_accepted:
            issues.append(
                SmokeValidationIssue(
                    code="SMOKE_ACCEPTED_COUNT_MISMATCH",
                    smoke_cell_index=cell.smoke_cell_index,
                    detail=identity,
                )
            )
        if raw_batch.typed_outcome_counts != expected_counts:
            issues.append(
                SmokeValidationIssue(
                    code="SMOKE_OUTCOME_COUNT_MISMATCH",
                    smoke_cell_index=cell.smoke_cell_index,
                    detail=identity,
                )
            )
        if (
            raw_batch.first_start_offset_ns != expected_first
            or raw_batch.last_start_offset_ns != expected_last
            or raw_batch.batch_elapsed_ns != expected_elapsed
        ):
            issues.append(
                SmokeValidationIssue(
                    code="SMOKE_TIMING_MISMATCH",
                    smoke_cell_index=cell.smoke_cell_index,
                    detail=identity,
                )
            )
    return tuple(issues)


def _smoke_exception_issue(
    *,
    code: str,
    smoke_cell_index: int,
    exc: Exception,
) -> SmokeValidationIssue:
    """Retain only exception class identity at the smoke boundary."""

    cause = exc.__cause__
    exception_type = type(cause if isinstance(cause, Exception) else exc).__name__
    return SmokeValidationIssue(
        code=code,
        smoke_cell_index=smoke_cell_index,
        detail=f"cell={smoke_cell_index}; type={exception_type}",
    )


def _invalid_smoke_result(
    *,
    schedule: SmokeSchedule,
    invocations: Sequence[SmokeInvocationObservation],
    batches: Sequence[SmokeBatchObservation],
    ownership: Sequence[LaneOwnershipRecord],
    runtime_facts: Sequence[SmokeRuntimeFacts],
    issue: SmokeValidationIssue,
) -> SmokeExecutionResult:
    """Build an incomplete invalid result without retry or replacement."""

    return SmokeExecutionResult(
        evidence_kind=SMOKE_EVIDENCE_KIND,
        schedule=schedule,
        status=SmokeStatus.INVALID_SMOKE,
        invocations=tuple(invocations),
        batches=tuple(batches),
        ownership=tuple(ownership),
        runtime_facts=tuple(runtime_facts),
        issues=(issue,),
        failed_cell_index=issue.smoke_cell_index,
    )


def _build_batch_record(
    *,
    run_id: str,
    batch_record_index: int,
    plan: BatchPlan,
    release_reference_ns: int,
    records: Sequence[InvocationRecord],
) -> BatchRecord:
    return BatchRecord(
        schema_name=LEVEL_C_SCHEMA_NAME,
        schema_version=LEVEL_C_SCHEMA_VERSION,
        run_id=run_id,
        batch_record_index=batch_record_index,
        cell_index=plan.cell.cell_index,
        batch_index=plan.batch_index,
        worker_level=plan.cell.worker_level,
        workload_family=plan.cell.workload_family,
        composition=plan.cell.composition,
        release_reference_ns=release_reference_ns,
        first_start_offset_ns=min(record.start_offset_ns for record in records),
        last_start_offset_ns=max(record.start_offset_ns for record in records),
        batch_elapsed_ns=max(
            record.start_offset_ns + record.external_elapsed_ns
            for record in records
        ),
        completed_count=len(records),
        accepted_count=sum(record.cohort is Cohort.ACCEPTED for record in records),
        typed_outcome_counts=_typed_counts(records),
    )


def _typed_counts(records: Sequence[InvocationRecord]) -> tuple[TypedOutcomeCount, ...]:
    counts = Counter(_typed_outcome_label(record) for record in records)
    return tuple(
        TypedOutcomeCount(outcome=outcome, count=counts[outcome])
        for outcome in sorted(counts)
    )


def _typed_outcome_label(record: InvocationRecord) -> str:
    if record.exception_type is not None:
        return f"EXCEPTION::{record.exception_type}"
    if record.cohort is not None:
        return record.cohort.value
    stage = None if record.rejection_stage is None else record.rejection_stage.value
    return "::".join(
        (
            "UNSUPPORTED",
            record.producer_outcome or "MISSING",
            stage or "NONE",
            record.stream_admission_verdict or "NONE",
            record.append_admission_verdict or "NONE",
        )
    )


def _identity_token(
    *,
    run_id: str,
    plan: BatchPlan,
    identity_position: int,
    purpose: str,
) -> str:
    material = "|".join(
        (
            run_id,
            str(plan.plan_index),
            "recorded" if plan.recorded else "warmup",
            str(plan.batch_index),
            str(identity_position),
            purpose,
        )
    ).encode("utf-8")
    return sha256(material).hexdigest()[:32]


def _enum_value_or_none(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _nested_verdict_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _enum_value_or_none(getattr(value, "verdict", None))


def _rejection_stage(
    *,
    producer_outcome: str | None,
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


def _parse_phase(name: str, phase: Any) -> PhaseRecord | None:
    state_value = _enum_value_or_none(getattr(phase, "state", None))
    try:
        state = PhaseState(state_value) if state_value is not None else None
    except ValueError:
        return None
    if state is None:
        return None
    try:
        return PhaseRecord(
            name=name,
            state=state,
            elapsed_ns=getattr(phase, "elapsed_ns", None),
        )
    except (TypeError, ValueError):
        return None


def _describe(values: Sequence[float]) -> DescriptiveStatistics:
    if not values:
        raise ValueError("descriptive statistics require at least one value")
    return DescriptiveStatistics(
        count=len(values),
        minimum=min(values),
        maximum=max(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
    )


def _sort_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _read_clock(value: Any, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must return an integer nanosecond reading")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _require_safe_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or _SAFE_RUN_ID.fullmatch(run_id) is None:
        raise ValueError("run_id must be a safe experiment-local token")


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise TypeError(f"{name} must be a non-negative int")


def _require_positive_int(value: object, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise TypeError(f"{name} must be a positive int")
