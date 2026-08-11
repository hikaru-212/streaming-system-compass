"""Typed accounting for post-PR6 Layer-2 idempotency-check characterization.

This experiment-owned module defines the exact P/U/T by
MISS/REPLAY/CONFLICT factorial, immutable smoke and recorded schedules,
sample validation, structural-SQL validation, and cell-local descriptive
aggregation. It does not connect to PostgreSQL, implement an idempotency
algorithm, or define a production strategy.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import random
import statistics


SCHEMA_VERSION = 1
RECORDED_SAMPLES_PER_CELL = 30
RECORDED_SCHEDULE_SEED = 4_202_702
T_SETUP_SQL_IDENTITY = "SELECT 1"


class Layer2Error(RuntimeError):
    """Base error for supplemental Layer-2 accounting failures."""


class Layer2Context(str, Enum):
    """Identify the exact application/physical transaction context."""

    P = "P"
    U = "U"
    T = "T"


class Layer2Verdict(str, Enum):
    """Identify the exact planned and returned idempotency verdict."""

    MISS = "MISS"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


class TransactionStatusIdentity(str, Enum):
    """Retain psycopg transaction status without importing the driver here."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    INTRANS = "INTRANS"
    INERROR = "INERROR"
    UNKNOWN = "UNKNOWN"


class ScheduleKind(str, Enum):
    """Distinguish unrecorded smoke from the fixed recorded schedule."""

    SMOKE = "SMOKE"
    RECORDED = "RECORDED"


class RunValidity(str, Enum):
    """Classify complete primary or structural run validation."""

    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class Layer2Cell:
    """Identify one exact context by verdict cell, with no strategy identity."""

    context: Layer2Context
    verdict: Layer2Verdict

    def __post_init__(self) -> None:
        if not isinstance(self.context, Layer2Context):
            raise TypeError("context must be Layer2Context")
        if not isinstance(self.verdict, Layer2Verdict):
            raise TypeError("verdict must be Layer2Verdict")

    @property
    def identity(self) -> str:
        """Return the human-readable exact-cell identity."""

        return f"{self.context.value}-{self.verdict.value}"


ALL_CELLS = tuple(
    Layer2Cell(context=context, verdict=verdict)
    for context in Layer2Context
    for verdict in Layer2Verdict
)

EXPECTED_BEFORE_STATUS: Mapping[Layer2Context, TransactionStatusIdentity] = {
    Layer2Context.P: TransactionStatusIdentity.IDLE,
    Layer2Context.U: TransactionStatusIdentity.IDLE,
    Layer2Context.T: TransactionStatusIdentity.INTRANS,
}


@dataclass(frozen=True)
class Layer2SamplePlan:
    """Plan one invocation without attempt, execution, or governance identity."""

    sample_index: int
    cell: Layer2Cell

    def __post_init__(self) -> None:
        _require_non_negative_int(self.sample_index, "sample_index")
        if not isinstance(self.cell, Layer2Cell):
            raise TypeError("cell must be Layer2Cell")


@dataclass(frozen=True)
class Layer2Schedule:
    """Hold one immutable, non-adaptive Layer-2 schedule."""

    kind: ScheduleKind
    samples: tuple[Layer2SamplePlan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScheduleKind):
            raise TypeError("kind must be ScheduleKind")
        expected_cells = _expected_schedule_cells(self.kind)
        expected = tuple(
            Layer2SamplePlan(sample_index=index, cell=cell)
            for index, cell in enumerate(expected_cells)
        )
        if self.samples != expected:
            raise ValueError(
                f"{self.kind.value} schedule must equal its fixed Layer-2 plan"
            )


@dataclass(frozen=True)
class Layer2Sample:
    """Retain one primary-cost sample with separate check/cleanup boundaries."""

    schema_version: int
    run_id: str
    sample_index: int
    planned_context: Layer2Context
    planned_verdict: Layer2Verdict
    returned_verdict: Layer2Verdict | None
    check_elapsed_ns: int
    cleanup_elapsed_ns: int
    transaction_status_before_check: TransactionStatusIdentity | None
    transaction_status_after_check: TransactionStatusIdentity | None
    transaction_status_after_cleanup: TransactionStatusIdentity | None
    reuse_select_succeeded: bool | None
    final_transaction_status: TransactionStatusIdentity | None
    structural_sql_observation_identity: None = None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        _require_non_negative_int(self.sample_index, "sample_index")
        _require_non_negative_int(self.check_elapsed_ns, "check_elapsed_ns")
        _require_non_negative_int(self.cleanup_elapsed_ns, "cleanup_elapsed_ns")
        if not isinstance(self.planned_context, Layer2Context):
            raise TypeError("planned_context must be Layer2Context")
        if not isinstance(self.planned_verdict, Layer2Verdict):
            raise TypeError("planned_verdict must be Layer2Verdict")
        if self.returned_verdict is not None and not isinstance(
            self.returned_verdict,
            Layer2Verdict,
        ):
            raise TypeError("returned_verdict must be Layer2Verdict or None")
        for name in (
            "transaction_status_before_check",
            "transaction_status_after_check",
            "transaction_status_after_cleanup",
            "final_transaction_status",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(
                value,
                TransactionStatusIdentity,
            ):
                raise TypeError(f"{name} has the wrong type")
        if self.reuse_select_succeeded is not None and type(
            self.reuse_select_succeeded
        ) is not bool:
            raise TypeError("reuse_select_succeeded must be bool or None")
        if self.structural_sql_observation_identity is not None:
            raise ValueError("primary timing samples cannot retain SQL tracing")
        if self.exception_type is not None:
            if not isinstance(self.exception_type, str) or not self.exception_type:
                raise ValueError("exception_type must be a non-empty class name")
        elif self.returned_verdict is None:
            raise ValueError("normal sample requires returned_verdict")

    @property
    def cell(self) -> Layer2Cell:
        """Return this sample's exact planned cell."""

        return Layer2Cell(self.planned_context, self.planned_verdict)


@dataclass(frozen=True)
class Layer2StructuralSample:
    """Retain separate low-observation SQL structure, never primary timing."""

    schema_version: int
    run_id: str
    sample_index: int
    planned_context: Layer2Context
    planned_verdict: Layer2Verdict
    returned_verdict: Layer2Verdict | None
    transaction_status_before_check: TransactionStatusIdentity | None
    transaction_status_after_check: TransactionStatusIdentity | None
    transaction_status_after_cleanup: TransactionStatusIdentity | None
    reuse_select_succeeded: bool | None
    final_transaction_status: TransactionStatusIdentity | None
    check_sql_statement_count: int
    normalized_check_sql_identities: tuple[str, ...]
    setup_sql_identity: str | None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        _require_non_negative_int(self.sample_index, "sample_index")
        _require_non_negative_int(
            self.check_sql_statement_count,
            "check_sql_statement_count",
        )
        if not isinstance(self.planned_context, Layer2Context):
            raise TypeError("planned_context must be Layer2Context")
        if not isinstance(self.planned_verdict, Layer2Verdict):
            raise TypeError("planned_verdict must be Layer2Verdict")
        if self.returned_verdict is not None and not isinstance(
            self.returned_verdict,
            Layer2Verdict,
        ):
            raise TypeError("returned_verdict must be Layer2Verdict or None")
        for name in (
            "transaction_status_before_check",
            "transaction_status_after_check",
            "transaction_status_after_cleanup",
            "final_transaction_status",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(
                value,
                TransactionStatusIdentity,
            ):
                raise TypeError(f"{name} has the wrong type")
        if self.reuse_select_succeeded is not None and type(
            self.reuse_select_succeeded
        ) is not bool:
            raise TypeError("reuse_select_succeeded must be bool or None")
        if self.check_sql_statement_count != len(
            self.normalized_check_sql_identities
        ):
            raise ValueError("statement count must match normalized identities")
        if any(
            not isinstance(identity, str) or not identity
            for identity in self.normalized_check_sql_identities
        ):
            raise ValueError("normalized SQL identities must be non-empty strings")
        expected_setup = (
            T_SETUP_SQL_IDENTITY
            if self.planned_context is Layer2Context.T
            else None
        )
        if self.setup_sql_identity != expected_setup:
            raise ValueError("setup SQL identity does not match context")
        if self.exception_type is not None:
            if not isinstance(self.exception_type, str) or not self.exception_type:
                raise ValueError("exception_type must be a non-empty class name")
        elif self.returned_verdict is None:
            raise ValueError("normal structural sample requires returned_verdict")

    @property
    def cell(self) -> Layer2Cell:
        """Return this sample's exact planned cell."""

        return Layer2Cell(self.planned_context, self.planned_verdict)


@dataclass(frozen=True)
class ValidationIssue:
    """Describe one deterministic schedule or sample validity failure."""

    code: str
    sample_index: int | None
    detail: str


@dataclass(frozen=True)
class RunValidationResult:
    """Return whether every fixed-schedule sample is structurally valid."""

    validity: RunValidity
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class DescriptiveStatistics:
    """Retain only the accepted cell-local descriptive statistics."""

    count: int
    minimum_ns: int
    mean_ns: float
    median_ns: float
    maximum_ns: int


@dataclass(frozen=True)
class CellAggregate:
    """Aggregate exactly one cell without context or verdict pooling."""

    cell: Layer2Cell
    check_elapsed_ns: DescriptiveStatistics
    cleanup_elapsed_ns: DescriptiveStatistics


def generate_smoke_schedule() -> Layer2Schedule:
    """Return exactly one unrecorded sample for each of the nine cells."""

    return _schedule(ScheduleKind.SMOKE)


def generate_recorded_schedule() -> Layer2Schedule:
    """Return the fixed counterbalanced 270-sample recorded schedule."""

    return _schedule(ScheduleKind.RECORDED)


def validate_run(
    schedule: Layer2Schedule,
    samples: Sequence[Layer2Sample],
) -> RunValidationResult:
    """Validate complete primary-cost accounting and lifecycle invariants."""

    issues: list[ValidationIssue] = []
    if len(samples) != len(schedule.samples):
        issues.append(
            ValidationIssue(
                "SAMPLE_COUNT_MISMATCH",
                None,
                f"expected {len(schedule.samples)} samples, got {len(samples)}",
            )
        )
    for plan, sample in zip(schedule.samples, samples):
        _validate_common_sample(plan, sample, issues)
        if sample.structural_sql_observation_identity is not None:
            issues.append(
                ValidationIssue(
                    "PRIMARY_SQL_OBSERVER_PRESENT",
                    sample.sample_index,
                    "primary timing sample retained structural SQL observation",
                )
            )
    return _validation_result(issues)


def validate_structural_run(
    schedule: Layer2Schedule,
    samples: Sequence[Layer2StructuralSample],
) -> RunValidationResult:
    """Validate separate SQL structure without treating it as cost evidence."""

    issues: list[ValidationIssue] = []
    if len(samples) != len(schedule.samples):
        issues.append(
            ValidationIssue(
                "SAMPLE_COUNT_MISMATCH",
                None,
                f"expected {len(schedule.samples)} samples, got {len(samples)}",
            )
        )
    identities: list[str] = []
    for plan, sample in zip(schedule.samples, samples):
        _validate_common_sample(plan, sample, issues)
        if sample.check_sql_statement_count != 1:
            issues.append(
                ValidationIssue(
                    "CHECK_SQL_COUNT_MISMATCH",
                    sample.sample_index,
                    "exact production check() must emit one observed statement",
                )
            )
        if sample.check_sql_statement_count == 1:
            identities.append(sample.normalized_check_sql_identities[0])
        expected_setup = (
            T_SETUP_SQL_IDENTITY if plan.cell.context is Layer2Context.T else None
        )
        if sample.setup_sql_identity != expected_setup:
            issues.append(
                ValidationIssue(
                    "SETUP_SQL_IDENTITY_MISMATCH",
                    sample.sample_index,
                    "neutral setup SQL must appear only for T",
                )
            )
    if identities and len(set(identities)) != 1:
        issues.append(
            ValidationIssue(
                "CHECK_SQL_IDENTITY_MISMATCH",
                None,
                "check() SQL identity differs across exact cells",
            )
        )
    return _validation_result(issues)


def aggregate_recorded_samples(
    samples: Sequence[Layer2Sample],
) -> tuple[CellAggregate, ...]:
    """Aggregate exactly nine cells after fixed-run validation succeeds."""

    schedule = generate_recorded_schedule()
    validation = validate_run(schedule, samples)
    if validation.validity is not RunValidity.VALID:
        raise Layer2Error("cannot aggregate an invalid Layer-2 recorded run")

    grouped: dict[Layer2Cell, list[Layer2Sample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.cell].append(sample)
    if set(grouped) != set(ALL_CELLS):
        raise Layer2Error("aggregation must retain exactly nine cells")

    return tuple(
        CellAggregate(
            cell=cell,
            check_elapsed_ns=_statistics(
                [sample.check_elapsed_ns for sample in grouped[cell]]
            ),
            cleanup_elapsed_ns=_statistics(
                [sample.cleanup_elapsed_ns for sample in grouped[cell]]
            ),
        )
        for cell in ALL_CELLS
    )


def schedule_cell_counts(schedule: Layer2Schedule) -> Mapping[Layer2Cell, int]:
    """Expose exact-cell counts for deterministic schedule assertions."""

    return Counter(plan.cell for plan in schedule.samples)


def _schedule(kind: ScheduleKind) -> Layer2Schedule:
    cells = _expected_schedule_cells(kind)
    return Layer2Schedule(
        kind=kind,
        samples=tuple(
            Layer2SamplePlan(sample_index=index, cell=cell)
            for index, cell in enumerate(cells)
        ),
    )


def _expected_schedule_cells(kind: ScheduleKind) -> tuple[Layer2Cell, ...]:
    if kind is ScheduleKind.SMOKE:
        return ALL_CELLS
    if kind is not ScheduleKind.RECORDED:
        raise TypeError("kind must be ScheduleKind")

    rng = random.Random(RECORDED_SCHEDULE_SEED)
    rounds: list[Layer2Cell] = []
    # Three independently permuted nine-rotation cycles give each cell every
    # within-round position exactly three times across the first 27 rounds.
    for _ in range(3):
        base = list(ALL_CELLS)
        rng.shuffle(base)
        for rotation in range(len(base)):
            rounds.extend(base[rotation:] + base[:rotation])
    # The remaining three rounds use distinct rotations, so each cell gains
    # one of three positions and no position dominates the fixed 30 rounds.
    base = list(ALL_CELLS)
    rng.shuffle(base)
    for rotation in rng.sample(range(len(base)), 3):
        rounds.extend(base[rotation:] + base[:rotation])
    return tuple(rounds)


def _validate_common_sample(
    plan: Layer2SamplePlan,
    sample: Layer2Sample | Layer2StructuralSample,
    issues: list[ValidationIssue],
) -> None:
    index = sample.sample_index
    if sample.schema_version != SCHEMA_VERSION:
        issues.append(
            ValidationIssue("SCHEMA_VERSION_MISMATCH", index, "wrong schema version")
        )
    if index != plan.sample_index:
        issues.append(
            ValidationIssue("SAMPLE_INDEX_MISMATCH", index, "wrong sample index")
        )
    if sample.cell != plan.cell:
        issues.append(
            ValidationIssue("PLANNED_CELL_MISMATCH", index, "wrong planned cell")
        )
    if sample.exception_type is not None:
        issues.append(
            ValidationIssue(
                "UNEXPECTED_EXCEPTION",
                index,
                f"ordinary exception escaped: {sample.exception_type}",
            )
        )
    if sample.returned_verdict is not plan.cell.verdict:
        issues.append(
            ValidationIssue("VERDICT_MISMATCH", index, "returned verdict differs")
        )
    expected_before = EXPECTED_BEFORE_STATUS[plan.cell.context]
    if sample.transaction_status_before_check is not expected_before:
        issues.append(
            ValidationIssue(
                "BEFORE_STATUS_MISMATCH",
                index,
                f"expected {expected_before.value} before check",
            )
        )
    if sample.transaction_status_after_check is not TransactionStatusIdentity.INTRANS:
        issues.append(
            ValidationIssue(
                "AFTER_CHECK_STATUS_MISMATCH",
                index,
                "normal exact check must leave the physical transaction INTRANS",
            )
        )
    if sample.transaction_status_after_cleanup is not TransactionStatusIdentity.IDLE:
        issues.append(
            ValidationIssue(
                "AFTER_CLEANUP_STATUS_MISMATCH",
                index,
                "cleanup must return the connection to IDLE",
            )
        )
    if sample.reuse_select_succeeded is not True:
        issues.append(
            ValidationIssue(
                "REUSE_SELECT_FAILED",
                index,
                "SELECT 1 reuse did not succeed",
            )
        )
    if sample.final_transaction_status is not TransactionStatusIdentity.IDLE:
        issues.append(
            ValidationIssue(
                "FINAL_STATUS_MISMATCH",
                index,
                "post-reuse rollback must restore IDLE",
            )
        )


def _validation_result(issues: list[ValidationIssue]) -> RunValidationResult:
    return RunValidationResult(
        RunValidity.INVALID if issues else RunValidity.VALID,
        tuple(issues),
    )


def _statistics(values: Sequence[int]) -> DescriptiveStatistics:
    if not values:
        raise Layer2Error("cannot aggregate an empty cell")
    return DescriptiveStatistics(
        count=len(values),
        minimum_ns=min(values),
        mean_ns=statistics.fmean(values),
        median_ns=statistics.median(values),
        maximum_ns=max(values),
    )


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
