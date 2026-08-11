"""Typed accounting for post-PR6 Layer-3 read-lifecycle controls.

This experiment-owned module defines exactly the IDLE rollback baseline and
the PRE-like preliminary read lifecycle, their immutable 30-by-2 schedule,
sample validation, and control-local descriptive aggregation. It does not
connect to PostgreSQL, compare PRE with IN, sum component timings, or define a
production optimization.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import statistics


RECORDED_ROUNDS = 30


class Layer3Error(RuntimeError):
    """Report Layer-3 accounting failures without translating business errors.

    This experiment-owned error does not define production retry or recovery.
    """


class Layer3Control(str, Enum):
    """Identify exactly one accepted Layer-3 explanatory control.

    The identity carries no PRE/IN strategy or counterfactual composition.
    """

    CONTROL_A_IDLE_ROLLBACK = "CONTROL_A_IDLE_ROLLBACK"
    CONTROL_B_PRELIMINARY_READ_LIFECYCLE = (
        "CONTROL_B_PRELIMINARY_READ_LIFECYCLE"
    )


class IdempotencyVerdictIdentity(str, Enum):
    """Retain an observed production verdict without implementing its logic.

    The model records classification evidence but does not reconstruct it.
    """

    MISS = "MISS"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


class TransactionStatusIdentity(str, Enum):
    """Retain psycopg transaction status without importing the driver.

    These labels are lifecycle evidence, not a transaction-management API.
    """

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    INTRANS = "INTRANS"
    INERROR = "INERROR"
    UNKNOWN = "UNKNOWN"


class RunValidity(str, Enum):
    """Classify complete Layer-3 schedule and lifecycle validation.

    Validity does not repair samples or authorize retry and publication.
    """

    VALID = "VALID"
    INVALID = "INVALID"


ALL_CONTROLS = tuple(Layer3Control)


@dataclass(frozen=True)
class Layer3SamplePlan:
    """Plan one fixed control execution in the immutable recorded schedule.

    The coordinate carries no retry, attempt, execution, or governance identity.
    """

    sample_index: int
    round_index: int
    control: Layer3Control

    def __post_init__(self) -> None:
        _require_non_negative_int(self.sample_index, "sample_index")
        _require_non_negative_int(self.round_index, "round_index")
        if not isinstance(self.control, Layer3Control):
            raise TypeError("control must be Layer3Control")

    @property
    def coordinate(self) -> tuple[int, int, Layer3Control]:
        """Return the exact schedule coordinate owned by this plan.

        The coordinate is accounting identity, not a retry or attempt identity.
        """

        return (self.sample_index, self.round_index, self.control)


@dataclass(frozen=True)
class Layer3Schedule:
    """Hold the immutable 60-sample Layer-3 recorded schedule.

    Construction rejects adaptive extension, reordering, and replacement.
    """

    samples: tuple[Layer3SamplePlan, ...]

    def __post_init__(self) -> None:
        expected = _expected_sample_plans()
        if self.samples != expected:
            raise ValueError("schedule must equal the fixed Layer-3 plan")


@dataclass(frozen=True)
class ControlAIdleRollbackSample:
    """Retain only the IDLE rollback control's cleanup boundary and state.

    The sample contains no SQL, reuse, active-transaction, or strategy metric.
    """

    control: Layer3Control
    sample_index: int
    round_index: int
    status_before_cleanup: TransactionStatusIdentity | None
    cleanup_elapsed_ns: int | None
    status_after_cleanup: TransactionStatusIdentity | None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.control is not Layer3Control.CONTROL_A_IDLE_ROLLBACK:
            raise ValueError("Control-A sample must retain the Control-A identity")
        _validate_sample_metadata(self)

    @property
    def coordinate(self) -> tuple[int, int, Layer3Control]:
        """Return the exact schedule coordinate represented by this sample.

        The coordinate does not imply execution retry or governance semantics.
        """

        return (self.sample_index, self.round_index, self.control)


@dataclass(frozen=True)
class ControlBPreliminaryReadLifecycleSample:
    """Retain direct PRE-like read-lifecycle timings and transaction evidence.

    The lifecycle elapsed field is a direct outer observation. This record has
    no component-sum or synthetic database-time field and makes no strategy
    comparison.
    """

    control: Layer3Control
    sample_index: int
    round_index: int
    returned_idempotency_verdict: IdempotencyVerdictIdentity | None
    history_count: int | None
    idempotency_check_elapsed_ns: int | None
    accepted_history_load_elapsed_ns: int | None
    cleanup_elapsed_ns: int | None
    lifecycle_elapsed_ns: int | None
    status_before_check: TransactionStatusIdentity | None
    status_after_check: TransactionStatusIdentity | None
    status_after_history: TransactionStatusIdentity | None
    status_after_cleanup: TransactionStatusIdentity | None
    reuse_select_succeeded: bool | None
    final_transaction_status: TransactionStatusIdentity | None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if (
            self.control
            is not Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE
        ):
            raise ValueError("Control-B sample must retain the Control-B identity")
        _validate_sample_metadata(self)
        if self.returned_idempotency_verdict is not None and not isinstance(
            self.returned_idempotency_verdict,
            IdempotencyVerdictIdentity,
        ):
            raise TypeError(
                "returned_idempotency_verdict must be a verdict identity or None"
            )
        if self.history_count is not None and type(self.history_count) is not int:
            raise TypeError("history_count must be int or None")
        if self.reuse_select_succeeded is not None and type(
            self.reuse_select_succeeded
        ) is not bool:
            raise TypeError("reuse_select_succeeded must be bool or None")

    @property
    def coordinate(self) -> tuple[int, int, Layer3Control]:
        """Return the exact schedule coordinate represented by this sample.

        The coordinate does not imply execution retry or governance semantics.
        """

        return (self.sample_index, self.round_index, self.control)


Layer3Sample = ControlAIdleRollbackSample | ControlBPreliminaryReadLifecycleSample


@dataclass(frozen=True)
class ValidationIssue:
    """Describe one schedule or lifecycle failure without repairing evidence.

    The issue is experiment accounting, not a production error classification.
    """

    code: str
    sample_index: int | None
    detail: str


@dataclass(frozen=True)
class RunValidationResult:
    """Return whether fixed-schedule evidence satisfies every Layer-3 rule.

    The result neither publishes evidence nor authorizes another execution.
    """

    validity: RunValidity
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class DescriptiveStatistics:
    """Retain the five authorized descriptive statistics in nanoseconds.

    It intentionally has no p95, pooled score, or causal interpretation.
    """

    count: int
    minimum_ns: int
    mean_ns: float
    median_ns: float
    maximum_ns: int


@dataclass(frozen=True)
class ControlAIdleRollbackAggregate:
    """Aggregate only Control A cleanup elapsed.

    The aggregate is not pooled with Control B or labeled PRE cleanup cost.
    """

    control: Layer3Control
    cleanup_elapsed_ns: DescriptiveStatistics


@dataclass(frozen=True)
class ControlBPreliminaryReadLifecycleAggregate:
    """Aggregate Control B timing fields independently.

    It never sums components or ranks a production strategy.
    """

    control: Layer3Control
    idempotency_check_elapsed_ns: DescriptiveStatistics
    accepted_history_load_elapsed_ns: DescriptiveStatistics
    cleanup_elapsed_ns: DescriptiveStatistics
    lifecycle_elapsed_ns: DescriptiveStatistics


Layer3Aggregate = (
    ControlAIdleRollbackAggregate | ControlBPreliminaryReadLifecycleAggregate
)


def generate_recorded_schedule() -> Layer3Schedule:
    """Return the deterministic 30-round, two-control recorded schedule.

    The result is fixed accounting, not an adaptive execution policy.
    """

    return Layer3Schedule(_expected_sample_plans())


def schedule_control_counts(
    schedule: Layer3Schedule,
) -> Mapping[Layer3Control, int]:
    """Expose exact per-control counts for fixed-schedule accounting.

    Counts are not pooled timing statistics or a strategy score.
    """

    return Counter(plan.control for plan in schedule.samples)


def validate_sample(
    plan: Layer3SamplePlan,
    sample: Layer3Sample,
) -> RunValidationResult:
    """Validate one planned sample for immediate first-invalid stopping.

    This check owns only schedule-coordinate and lifecycle evidence. It does
    not repair, replace, or reinterpret an invalid sample.
    """

    issues: list[ValidationIssue] = []
    _validate_sample_against_plan(plan, sample, issues)
    return _validation_result(issues)


def validate_run(
    schedule: Layer3Schedule,
    samples: Sequence[Layer3Sample],
) -> RunValidationResult:
    """Validate exact 60-sample accounting and every control invariant.

    Missing, duplicate, reordered, or unplanned coordinates remain explicit
    invalid evidence. The function never creates replacement observations.
    """

    issues: list[ValidationIssue] = []
    if len(samples) != len(schedule.samples):
        issues.append(
            ValidationIssue(
                "SAMPLE_COUNT_MISMATCH",
                None,
                f"expected {len(schedule.samples)} samples, got {len(samples)}",
            )
        )

    expected_by_coordinate = {
        plan.coordinate: plan for plan in schedule.samples
    }
    observed_coordinates = [sample.coordinate for sample in samples]
    coordinate_counts = Counter(observed_coordinates)

    for coordinate, count in coordinate_counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    "DUPLICATE_SAMPLE_COORDINATE",
                    coordinate[0],
                    f"coordinate observed {count} times",
                )
            )
        if coordinate not in expected_by_coordinate:
            issues.append(
                ValidationIssue(
                    "UNPLANNED_SAMPLE_COORDINATE",
                    coordinate[0],
                    "sample coordinate is not in the fixed schedule",
                )
            )

    observed_coordinate_set = set(observed_coordinates)
    for plan in schedule.samples:
        if plan.coordinate not in observed_coordinate_set:
            issues.append(
                ValidationIssue(
                    "MISSING_SAMPLE_COORDINATE",
                    plan.sample_index,
                    "planned sample coordinate is absent",
                )
            )

    for position, sample in enumerate(samples):
        if position < len(schedule.samples):
            expected_plan = schedule.samples[position]
            if sample.coordinate != expected_plan.coordinate:
                issues.append(
                    ValidationIssue(
                        "SAMPLE_ORDER_MISMATCH",
                        sample.sample_index,
                        "sample does not occupy its fixed schedule position",
                    )
                )
        plan = expected_by_coordinate.get(sample.coordinate)
        if plan is not None:
            _validate_sample_against_plan(plan, sample, issues)

    return _validation_result(issues)


def aggregate_recorded_samples(
    samples: Sequence[Layer3Sample],
) -> tuple[Layer3Aggregate, Layer3Aggregate]:
    """Aggregate two controls separately after exact recorded-run validation.

    Component fields remain independent. No p95, pooled control score,
    synthetic database-time total, or PRE/IN ranking is produced.
    """

    schedule = generate_recorded_schedule()
    validation = validate_run(schedule, samples)
    if validation.validity is not RunValidity.VALID:
        raise Layer3Error("cannot aggregate an invalid Layer-3 recorded run")

    control_a = [
        sample
        for sample in samples
        if isinstance(sample, ControlAIdleRollbackSample)
    ]
    control_b = [
        sample
        for sample in samples
        if isinstance(sample, ControlBPreliminaryReadLifecycleSample)
    ]
    if len(control_a) != RECORDED_ROUNDS or len(control_b) != RECORDED_ROUNDS:
        raise Layer3Error("aggregation must retain exact 30/30 control accounting")

    return (
        ControlAIdleRollbackAggregate(
            control=Layer3Control.CONTROL_A_IDLE_ROLLBACK,
            cleanup_elapsed_ns=_statistics(
                _required_timings(control_a, "cleanup_elapsed_ns")
            ),
        ),
        ControlBPreliminaryReadLifecycleAggregate(
            control=Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE,
            idempotency_check_elapsed_ns=_statistics(
                _required_timings(control_b, "idempotency_check_elapsed_ns")
            ),
            accepted_history_load_elapsed_ns=_statistics(
                _required_timings(control_b, "accepted_history_load_elapsed_ns")
            ),
            cleanup_elapsed_ns=_statistics(
                _required_timings(control_b, "cleanup_elapsed_ns")
            ),
            lifecycle_elapsed_ns=_statistics(
                _required_timings(control_b, "lifecycle_elapsed_ns")
            ),
        ),
    )


def _expected_sample_plans() -> tuple[Layer3SamplePlan, ...]:
    return tuple(
        Layer3SamplePlan(
            sample_index=(round_index * len(ALL_CONTROLS)) + control_index,
            round_index=round_index,
            control=control,
        )
        for round_index in range(RECORDED_ROUNDS)
        for control_index, control in enumerate(ALL_CONTROLS)
    )


def _validate_sample_against_plan(
    plan: Layer3SamplePlan,
    sample: Layer3Sample,
    issues: list[ValidationIssue],
) -> None:
    index = sample.sample_index
    if sample.coordinate != plan.coordinate:
        issues.append(
            ValidationIssue(
                "PLANNED_COORDINATE_MISMATCH",
                index,
                "sample coordinate differs from its plan",
            )
        )
    if sample.exception_type is not None:
        issues.append(
            ValidationIssue(
                "UNEXPECTED_EXCEPTION",
                index,
                f"ordinary exception escaped: {sample.exception_type}",
            )
        )
    if plan.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
        if not isinstance(sample, ControlAIdleRollbackSample):
            issues.append(
                ValidationIssue(
                    "CONTROL_SAMPLE_TYPE_MISMATCH",
                    index,
                    "Control-A plan requires a Control-A sample",
                )
            )
            return
        _validate_control_a(sample, issues)
        return
    if plan.control is Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE:
        if not isinstance(sample, ControlBPreliminaryReadLifecycleSample):
            issues.append(
                ValidationIssue(
                    "CONTROL_SAMPLE_TYPE_MISMATCH",
                    index,
                    "Control-B plan requires a Control-B sample",
                )
            )
            return
        _validate_control_b(sample, issues)
        return
    issues.append(
        ValidationIssue("UNKNOWN_CONTROL", index, "plan has an unknown control")
    )


def _validate_control_a(
    sample: ControlAIdleRollbackSample,
    issues: list[ValidationIssue],
) -> None:
    index = sample.sample_index
    _expect_status(
        sample.status_before_cleanup,
        TransactionStatusIdentity.IDLE,
        "CONTROL_A_BEFORE_STATUS_MISMATCH",
        index,
        issues,
    )
    _require_timing(sample.cleanup_elapsed_ns, "cleanup_elapsed_ns", index, issues)
    _expect_status(
        sample.status_after_cleanup,
        TransactionStatusIdentity.IDLE,
        "CONTROL_A_AFTER_STATUS_MISMATCH",
        index,
        issues,
    )


def _validate_control_b(
    sample: ControlBPreliminaryReadLifecycleSample,
    issues: list[ValidationIssue],
) -> None:
    index = sample.sample_index
    if sample.returned_idempotency_verdict is not IdempotencyVerdictIdentity.MISS:
        issues.append(
            ValidationIssue(
                "CONTROL_B_VERDICT_MISMATCH",
                index,
                "production idempotency check must return exact MISS",
            )
        )
    if sample.history_count != 0:
        issues.append(
            ValidationIssue(
                "CONTROL_B_HISTORY_NOT_EMPTY",
                index,
                "production accepted-history load must return empty history",
            )
        )
    for field in (
        "idempotency_check_elapsed_ns",
        "accepted_history_load_elapsed_ns",
        "cleanup_elapsed_ns",
        "lifecycle_elapsed_ns",
    ):
        _require_timing(getattr(sample, field), field, index, issues)
    for value, expected, code in (
        (
            sample.status_before_check,
            TransactionStatusIdentity.IDLE,
            "CONTROL_B_BEFORE_STATUS_MISMATCH",
        ),
        (
            sample.status_after_check,
            TransactionStatusIdentity.INTRANS,
            "CONTROL_B_AFTER_CHECK_STATUS_MISMATCH",
        ),
        (
            sample.status_after_history,
            TransactionStatusIdentity.INTRANS,
            "CONTROL_B_AFTER_HISTORY_STATUS_MISMATCH",
        ),
        (
            sample.status_after_cleanup,
            TransactionStatusIdentity.IDLE,
            "CONTROL_B_AFTER_CLEANUP_STATUS_MISMATCH",
        ),
        (
            sample.final_transaction_status,
            TransactionStatusIdentity.IDLE,
            "CONTROL_B_FINAL_STATUS_MISMATCH",
        ),
    ):
        _expect_status(value, expected, code, index, issues)
    if sample.reuse_select_succeeded is not True:
        issues.append(
            ValidationIssue(
                "CONTROL_B_REUSE_FAILED",
                index,
                "post-lifecycle SELECT 1 reuse must succeed",
            )
        )


def _expect_status(
    actual: TransactionStatusIdentity | None,
    expected: TransactionStatusIdentity,
    code: str,
    index: int,
    issues: list[ValidationIssue],
) -> None:
    if actual is not expected:
        issues.append(
            ValidationIssue(
                code,
                index,
                f"expected transaction status {expected.value}",
            )
        )


def _require_timing(
    value: int | None,
    field: str,
    index: int,
    issues: list[ValidationIssue],
) -> None:
    if type(value) is not int or value < 0:
        issues.append(
            ValidationIssue(
                "MISSING_OR_INVALID_TIMING",
                index,
                f"{field} must be a non-negative integer",
            )
        )


def _statistics(values: Sequence[int]) -> DescriptiveStatistics:
    if not values:
        raise Layer3Error("cannot aggregate an empty timing field")
    return DescriptiveStatistics(
        count=len(values),
        minimum_ns=min(values),
        mean_ns=statistics.fmean(values),
        median_ns=statistics.median(values),
        maximum_ns=max(values),
    )


def _required_timings(samples: Sequence[object], field: str) -> list[int]:
    values = [getattr(sample, field) for sample in samples]
    if any(type(value) is not int or value < 0 for value in values):
        raise Layer3Error(f"{field} contains missing or invalid timing")
    return values


def _validation_result(issues: list[ValidationIssue]) -> RunValidationResult:
    return RunValidationResult(
        validity=RunValidity.INVALID if issues else RunValidity.VALID,
        issues=tuple(issues),
    )


def _validate_sample_metadata(
    sample: ControlAIdleRollbackSample | ControlBPreliminaryReadLifecycleSample,
) -> None:
    _require_non_negative_int(sample.sample_index, "sample_index")
    _require_non_negative_int(sample.round_index, "round_index")
    if sample.exception_type is not None and (
        not isinstance(sample.exception_type, str) or not sample.exception_type
    ):
        raise ValueError("exception_type must be a non-empty class name or None")
    status_fields = (
        ("status_before_cleanup", "status_after_cleanup")
        if isinstance(sample, ControlAIdleRollbackSample)
        else (
            "status_before_check",
            "status_after_check",
            "status_after_history",
            "status_after_cleanup",
            "final_transaction_status",
        )
    )
    for field in status_fields:
        value = getattr(sample, field)
        if value is not None and not isinstance(value, TransactionStatusIdentity):
            raise TypeError(f"{field} must be a transaction status or None")


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
