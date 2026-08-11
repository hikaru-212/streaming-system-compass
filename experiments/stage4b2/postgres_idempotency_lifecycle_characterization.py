"""Typed accounting for the post-PR6 Layer-1 PostgreSQL characterization.

This experiment-owned module defines the fixed A--H schedule, exact production
phase shapes, sample validation, and path-local descriptive aggregation.  It
does not connect to PostgreSQL, invoke a producer, modify production behavior,
write evidence, or define governance, retry, or strategy-selection semantics.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import statistics


SCHEMA_VERSION = 1
RECORDED_SAMPLES_PER_PATH = 10

PHASE_NAMES = (
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

CONTAMINATED_D_E_TIMING_FIELDS = (
    "external_elapsed_ns",
    "producer_write_invocation",
    "validation_runtime_call",
)


class Layer1Error(RuntimeError):
    """Base error for supplemental Layer-1 accounting failures."""


class Layer1ClassificationError(Layer1Error):
    """Report producer evidence that cannot identify exactly one A--H path."""


class Layer1Path(str, Enum):
    """Identify exactly one accepted supplemental production path."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"


class ValidationPlacementIdentity(str, Enum):
    """Retain the selected production validation placement."""

    PRE_TRANSACTION = "PRE_TRANSACTION"
    IN_TRANSACTION = "IN_TRANSACTION"


class AdmissionComposition(str, Enum):
    """Retain the exact admission composition used by Layer 1."""

    PRE_OCC = "PRE_OCC"
    IN_PESSIMISTIC = "IN_PESSIMISTIC"


class ProducerOutcome(str, Enum):
    """Retain every current typed producer outcome for invalid-run diagnosis."""

    ACCEPTED = "ACCEPTED"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    VALIDATION_BLOCKED = "VALIDATION_BLOCKED"
    ADMISSION_REJECTED = "ADMISSION_REJECTED"


class IdempotencyLifecyclePosition(str, Enum):
    """Locate one observed idempotency verdict in the production lifecycle."""

    PRELIMINARY = "PRELIMINARY"
    AUTHORITATIVE = "AUTHORITATIVE"


class IdempotencyVerdictIdentity(str, Enum):
    """Retain the exact request-id classification at one lifecycle position."""

    MISS = "MISS"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"


class MeasurementAvailability(str, Enum):
    """Mirror the production measurement delivery availability."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class PhaseState(str, Enum):
    """Mirror all four production measurement-presence states."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REACHED = "NOT_REACHED"
    NOT_COLLECTED = "NOT_COLLECTED"
    MEASURED = "MEASURED"


class TransactionStatusIdentity(str, Enum):
    """Retain psycopg transaction status without importing the driver here."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    INTRANS = "INTRANS"
    INERROR = "INERROR"
    UNKNOWN = "UNKNOWN"


class TimingEligibility(str, Enum):
    """Separate latency evidence from coordination-contaminated structure."""

    UNCONTAMINATED = "UNCONTAMINATED"
    STRUCTURAL_ONLY_COORDINATION_CONTAMINATED = (
        "STRUCTURAL_ONLY_COORDINATION_CONTAMINATED"
    )


class ScheduleKind(str, Enum):
    """Distinguish unrecorded smoke from the fixed recorded schedule."""

    SMOKE = "SMOKE"
    RECORDED = "RECORDED"


class RunValidity(str, Enum):
    """Classify structural validation of one complete fixed schedule."""

    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class IdempotencyLifecycleObservation:
    """Record one ordered idempotency verdict and its production position."""

    position: IdempotencyLifecyclePosition
    verdict: IdempotencyVerdictIdentity


@dataclass(frozen=True)
class PhaseRecord:
    """Retain one exact production phase state and optional elapsed value."""

    name: str
    state: PhaseState
    elapsed_ns: int | None

    def __post_init__(self) -> None:
        if self.name not in PHASE_NAMES:
            raise ValueError(f"unknown Layer-1 phase: {self.name}")
        if not isinstance(self.state, PhaseState):
            raise TypeError("state must be PhaseState")
        if self.state is PhaseState.MEASURED:
            _require_non_negative_int(self.elapsed_ns, "elapsed_ns")
        elif self.elapsed_ns is not None:
            raise ValueError("only MEASURED phases may retain elapsed_ns")


@dataclass(frozen=True)
class DurableVerificationResult:
    """Retain path-specific post-timing durable verification markers."""

    verified: bool
    event_count: int | None
    idempotency_record_count: int | None
    preexisting_state_unchanged: bool | None = None
    winner_is_sole_event: bool | None = None
    result_references_winner: bool | None = None
    losing_candidate_absent: bool | None = None

    def __post_init__(self) -> None:
        if type(self.verified) is not bool:
            raise TypeError("verified must be bool")
        for name in ("event_count", "idempotency_record_count"):
            value = getattr(self, name)
            if value is not None:
                _require_non_negative_int(value, name)
        for name in (
            "preexisting_state_unchanged",
            "winner_is_sole_event",
            "result_references_winner",
            "losing_candidate_absent",
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or None")


@dataclass(frozen=True)
class Layer1SamplePlan:
    """Plan exactly one invocation; it is not an attempt or execution identity."""

    sample_index: int
    path: Layer1Path

    def __post_init__(self) -> None:
        _require_non_negative_int(self.sample_index, "sample_index")
        if not isinstance(self.path, Layer1Path):
            raise TypeError("path must be Layer1Path")


@dataclass(frozen=True)
class Layer1Schedule:
    """Hold one immutable, non-adaptive smoke or recorded A--H schedule."""

    kind: ScheduleKind
    samples: tuple[Layer1SamplePlan, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScheduleKind):
            raise TypeError("kind must be ScheduleKind")
        expected_paths = (
            tuple(Layer1Path)
            if self.kind is ScheduleKind.SMOKE
            else tuple(
                path
                for _ in range(RECORDED_SAMPLES_PER_PATH)
                for path in Layer1Path
            )
        )
        expected = tuple(
            Layer1SamplePlan(sample_index=index, path=path)
            for index, path in enumerate(expected_paths)
        )
        if self.samples != expected:
            raise ValueError(
                f"{self.kind.value} schedule must equal its fixed A--H plan"
            )


@dataclass(frozen=True)
class Layer1Sample:
    """Retain one normal or exceptional public producer invocation.

    ``sample_index`` is experiment-local accounting only. No attempt,
    execution, governance, retry, or strategy-selection identity is created.
    D/E retain raw structural timings while explicit contamination metadata
    makes the affected fields ineligible for latency aggregation.
    """

    schema_version: int
    run_id: str
    sample_index: int
    planned_path: Layer1Path
    classified_path: Layer1Path | None
    validation_placement: ValidationPlacementIdentity
    admission_composition: AdmissionComposition
    external_elapsed_ns: int
    producer_outcome: ProducerOutcome | None
    idempotency_observations: tuple[IdempotencyLifecycleObservation, ...]
    measurement_availability: MeasurementAvailability | None
    phases: tuple[PhaseRecord, ...] | None
    producer_return_transaction_status: TransactionStatusIdentity | None
    reuse_select_succeeded: bool | None
    final_transaction_status: TransactionStatusIdentity | None
    durable_verification: DurableVerificationResult
    timing_eligibility: TimingEligibility
    contaminated_timing_fields: tuple[str, ...]
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        _require_non_negative_int(self.sample_index, "sample_index")
        _require_non_negative_int(self.external_elapsed_ns, "external_elapsed_ns")
        if not isinstance(self.planned_path, Layer1Path):
            raise TypeError("planned_path must be Layer1Path")
        if self.classified_path is not None and not isinstance(
            self.classified_path,
            Layer1Path,
        ):
            raise TypeError("classified_path must be Layer1Path or None")
        if not isinstance(self.validation_placement, ValidationPlacementIdentity):
            raise TypeError("validation_placement has the wrong type")
        if not isinstance(self.admission_composition, AdmissionComposition):
            raise TypeError("admission_composition has the wrong type")
        if not isinstance(self.durable_verification, DurableVerificationResult):
            raise TypeError("durable_verification has the wrong type")
        if not isinstance(self.timing_eligibility, TimingEligibility):
            raise TypeError("timing_eligibility has the wrong type")
        if any(
            not isinstance(observation, IdempotencyLifecycleObservation)
            for observation in self.idempotency_observations
        ):
            raise TypeError("idempotency observations have the wrong type")
        for name in (
            "producer_return_transaction_status",
            "final_transaction_status",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(
                value,
                TransactionStatusIdentity,
            ):
                raise TypeError(f"{name} has the wrong type")
        if len(self.contaminated_timing_fields) != len(
            set(self.contaminated_timing_fields)
        ):
            raise ValueError("contaminated_timing_fields must be unique")
        allowed_timing_fields = {"external_elapsed_ns", *PHASE_NAMES}
        if not set(self.contaminated_timing_fields) <= allowed_timing_fields:
            raise ValueError("contaminated_timing_fields contains an unknown field")

        if self.phases is not None:
            names = tuple(phase.name for phase in self.phases)
            if names != PHASE_NAMES:
                raise ValueError("phases must contain all thirteen fields in order")

        if self.exception_type is not None:
            if not isinstance(self.exception_type, str) or not self.exception_type:
                raise ValueError("exception_type must be a non-empty class name")
            if any(
                value is not None
                for value in (
                    self.classified_path,
                    self.producer_outcome,
                    self.measurement_availability,
                    self.phases,
                    self.producer_return_transaction_status,
                    self.reuse_select_succeeded,
                    self.final_transaction_status,
                )
            ) or self.idempotency_observations:
                raise ValueError(
                    "exception sample cannot claim normal-return evidence"
                )
            return

        if not isinstance(self.producer_outcome, ProducerOutcome):
            raise TypeError("normal sample producer_outcome has the wrong type")
        if self.measurement_availability is None:
            raise ValueError("normal sample requires measurement availability")
        if (
            self.measurement_availability is MeasurementAvailability.AVAILABLE
            and self.phases is None
        ):
            raise ValueError("AVAILABLE measurement requires all phases")
        if (
            self.measurement_availability is MeasurementAvailability.UNAVAILABLE
            and self.phases is not None
        ):
            raise ValueError("UNAVAILABLE measurement requires phases=None")
        if self.reuse_select_succeeded is not None and type(
            self.reuse_select_succeeded
        ) is not bool:
            raise TypeError("reuse_select_succeeded must be bool or None")


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
    """Retain only the accepted path-local descriptive statistics."""

    count: int
    minimum_ns: int
    mean_ns: float
    median_ns: float
    maximum_ns: int


@dataclass(frozen=True)
class PhaseAggregate:
    """Aggregate one non-overlapping interpretation boundary independently."""

    phase_name: str
    statistics: DescriptiveStatistics


@dataclass(frozen=True)
class PathAggregate:
    """Aggregate exactly one A--H cohort without PRE/IN pooling."""

    path: Layer1Path
    external_elapsed: DescriptiveStatistics | None
    phases: tuple[PhaseAggregate, ...]
    unavailable_timing_fields: tuple[str, ...]


EXPECTED_CONFIGURATION: Mapping[
    Layer1Path,
    tuple[ValidationPlacementIdentity, AdmissionComposition, ProducerOutcome],
] = {
    Layer1Path.A: (
        ValidationPlacementIdentity.PRE_TRANSACTION,
        AdmissionComposition.PRE_OCC,
        ProducerOutcome.ACCEPTED,
    ),
    Layer1Path.B: (
        ValidationPlacementIdentity.PRE_TRANSACTION,
        AdmissionComposition.PRE_OCC,
        ProducerOutcome.REPLAY,
    ),
    Layer1Path.C: (
        ValidationPlacementIdentity.PRE_TRANSACTION,
        AdmissionComposition.PRE_OCC,
        ProducerOutcome.CONFLICT,
    ),
    Layer1Path.D: (
        ValidationPlacementIdentity.PRE_TRANSACTION,
        AdmissionComposition.PRE_OCC,
        ProducerOutcome.REPLAY,
    ),
    Layer1Path.E: (
        ValidationPlacementIdentity.PRE_TRANSACTION,
        AdmissionComposition.PRE_OCC,
        ProducerOutcome.CONFLICT,
    ),
    Layer1Path.F: (
        ValidationPlacementIdentity.IN_TRANSACTION,
        AdmissionComposition.IN_PESSIMISTIC,
        ProducerOutcome.ACCEPTED,
    ),
    Layer1Path.G: (
        ValidationPlacementIdentity.IN_TRANSACTION,
        AdmissionComposition.IN_PESSIMISTIC,
        ProducerOutcome.REPLAY,
    ),
    Layer1Path.H: (
        ValidationPlacementIdentity.IN_TRANSACTION,
        AdmissionComposition.IN_PESSIMISTIC,
        ProducerOutcome.CONFLICT,
    ),
}


EXPECTED_LIFECYCLE: Mapping[
    Layer1Path,
    tuple[IdempotencyLifecycleObservation, ...],
] = {
    Layer1Path.A: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.PRELIMINARY,
            IdempotencyVerdictIdentity.MISS,
        ),
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.MISS,
        ),
    ),
    Layer1Path.B: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.PRELIMINARY,
            IdempotencyVerdictIdentity.REPLAY,
        ),
    ),
    Layer1Path.C: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.PRELIMINARY,
            IdempotencyVerdictIdentity.CONFLICT,
        ),
    ),
    Layer1Path.D: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.PRELIMINARY,
            IdempotencyVerdictIdentity.MISS,
        ),
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.REPLAY,
        ),
    ),
    Layer1Path.E: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.PRELIMINARY,
            IdempotencyVerdictIdentity.MISS,
        ),
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.CONFLICT,
        ),
    ),
    Layer1Path.F: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.MISS,
        ),
    ),
    Layer1Path.G: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.REPLAY,
        ),
    ),
    Layer1Path.H: (
        IdempotencyLifecycleObservation(
            IdempotencyLifecyclePosition.AUTHORITATIVE,
            IdempotencyVerdictIdentity.CONFLICT,
        ),
    ),
}


def _phase_shape(
    measured: set[str],
    not_applicable: set[str],
) -> Mapping[str, PhaseState]:
    return {
        name: (
            PhaseState.MEASURED
            if name in measured
            else PhaseState.NOT_APPLICABLE
            if name in not_applicable
            else PhaseState.NOT_REACHED
        )
        for name in PHASE_NAMES
    }


EXPECTED_PHASE_STATES: Mapping[Layer1Path, Mapping[str, PhaseState]] = {
    Layer1Path.A: _phase_shape(
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
        },
        {"pessimistic_advisory_try_lock_call"},
    ),
    Layer1Path.B: _phase_shape(
        {
            "producer_write_invocation",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        {"pessimistic_advisory_try_lock_call"},
    ),
    Layer1Path.C: _phase_shape(
        {
            "producer_write_invocation",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        {"pessimistic_advisory_try_lock_call"},
    ),
    Layer1Path.D: _phase_shape(
        {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "rollback_finalization",
        },
        {"pessimistic_advisory_try_lock_call"},
    ),
    Layer1Path.E: _phase_shape(
        {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "rollback_finalization",
        },
        {"pessimistic_advisory_try_lock_call"},
    ),
    Layer1Path.F: _phase_shape(
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
        },
        {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    ),
    Layer1Path.G: _phase_shape(
        {
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "rollback_finalization",
        },
        {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    ),
    Layer1Path.H: _phase_shape(
        {
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "rollback_finalization",
        },
        {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    ),
}


def generate_smoke_schedule() -> Layer1Schedule:
    """Return exactly one unrecorded correctness invocation per A--H path."""

    return Layer1Schedule(
        kind=ScheduleKind.SMOKE,
        samples=tuple(
            Layer1SamplePlan(sample_index=index, path=path)
            for index, path in enumerate(Layer1Path)
        ),
    )


def generate_recorded_schedule() -> Layer1Schedule:
    """Return the immutable 80-sample Layer-1 schedule fixed before execution."""

    paths = tuple(
        path
        for _ in range(RECORDED_SAMPLES_PER_PATH)
        for path in Layer1Path
    )
    return Layer1Schedule(
        kind=ScheduleKind.RECORDED,
        samples=tuple(
            Layer1SamplePlan(sample_index=index, path=path)
            for index, path in enumerate(paths)
        ),
    )


def classify_path(
    *,
    validation_placement: ValidationPlacementIdentity,
    admission_composition: AdmissionComposition,
    producer_outcome: ProducerOutcome,
    phases: Sequence[PhaseRecord],
) -> Layer1Path:
    """Classify one normal result using placement, composition, and reach state."""

    by_name = _phase_mapping(phases)
    if validation_placement is ValidationPlacementIdentity.PRE_TRANSACTION:
        if admission_composition is not AdmissionComposition.PRE_OCC:
            raise Layer1ClassificationError("PRE path requires PRE_OCC")
        if by_name["preliminary_idempotency_check"].state is not PhaseState.MEASURED:
            raise Layer1ClassificationError("PRE path omitted preliminary lookup")
        authoritative = (
            by_name["authoritative_idempotency_check"].state
            is PhaseState.MEASURED
        )
        if producer_outcome is ProducerOutcome.ACCEPTED and authoritative:
            return Layer1Path.A
        if producer_outcome is ProducerOutcome.REPLAY:
            return Layer1Path.D if authoritative else Layer1Path.B
        if producer_outcome is ProducerOutcome.CONFLICT:
            return Layer1Path.E if authoritative else Layer1Path.C
        raise Layer1ClassificationError("PRE result is outside A--E")

    if validation_placement is not ValidationPlacementIdentity.IN_TRANSACTION:
        raise Layer1ClassificationError("unknown validation placement")
    if admission_composition is not AdmissionComposition.IN_PESSIMISTIC:
        raise Layer1ClassificationError("IN path requires IN_PESSIMISTIC")
    if by_name["authoritative_idempotency_check"].state is not PhaseState.MEASURED:
        raise Layer1ClassificationError("IN path omitted authoritative lookup")
    try:
        return {
            ProducerOutcome.ACCEPTED: Layer1Path.F,
            ProducerOutcome.REPLAY: Layer1Path.G,
            ProducerOutcome.CONFLICT: Layer1Path.H,
        }[producer_outcome]
    except KeyError as exc:
        raise Layer1ClassificationError("IN result is outside F--H") from exc


def validate_run(
    schedule: Layer1Schedule,
    samples: Sequence[Layer1Sample],
) -> RunValidationResult:
    """Validate exact schedule accounting and every normal-return invariant."""

    issues: list[ValidationIssue] = []
    if len(samples) != len(schedule.samples):
        issues.append(
            ValidationIssue(
                code="SAMPLE_COUNT_MISMATCH",
                sample_index=None,
                detail=(
                    f"expected {len(schedule.samples)} samples, got {len(samples)}"
                ),
            )
        )

    for plan, sample in zip(schedule.samples, samples):
        _validate_sample(plan, sample, issues)

    return RunValidationResult(
        validity=RunValidity.INVALID if issues else RunValidity.VALID,
        issues=tuple(issues),
    )


def aggregate_recorded_samples(
    samples: Sequence[Layer1Sample],
) -> tuple[PathAggregate, ...]:
    """Aggregate only exact A--H cohorts after fixed-run validation succeeds."""

    schedule = generate_recorded_schedule()
    validation = validate_run(schedule, samples)
    if validation.validity is not RunValidity.VALID:
        raise Layer1Error("cannot aggregate an invalid Layer-1 recorded run")

    by_path: dict[Layer1Path, list[Layer1Sample]] = defaultdict(list)
    for sample in samples:
        by_path[sample.planned_path].append(sample)

    aggregates: list[PathAggregate] = []
    for path in Layer1Path:
        path_samples = by_path[path]
        contaminated = (
            CONTAMINATED_D_E_TIMING_FIELDS
            if path in {Layer1Path.D, Layer1Path.E}
            else ()
        )
        external = (
            None
            if "external_elapsed_ns" in contaminated
            else _describe([sample.external_elapsed_ns for sample in path_samples])
        )
        phase_aggregates: list[PhaseAggregate] = []
        for phase_name in PHASE_NAMES:
            if phase_name in contaminated:
                continue
            elapsed = [
                _phase_mapping(sample.phases or ())[phase_name].elapsed_ns
                for sample in path_samples
                if _phase_mapping(sample.phases or ())[phase_name].state
                is PhaseState.MEASURED
            ]
            if elapsed:
                phase_aggregates.append(
                    PhaseAggregate(
                        phase_name=phase_name,
                        statistics=_describe([int(value) for value in elapsed]),
                    )
                )
        aggregates.append(
            PathAggregate(
                path=path,
                external_elapsed=external,
                phases=tuple(phase_aggregates),
                unavailable_timing_fields=contaminated,
            )
        )
    return tuple(aggregates)


def _validate_sample(
    plan: Layer1SamplePlan,
    sample: Layer1Sample,
    issues: list[ValidationIssue],
) -> None:
    index = plan.sample_index

    def add(code: str, detail: str) -> None:
        issues.append(ValidationIssue(code=code, sample_index=index, detail=detail))

    if sample.sample_index != index or sample.planned_path is not plan.path:
        add("SCHEDULE_MISMATCH", "sample index/path differs from fixed plan")
    expected_placement, expected_admission, expected_outcome = EXPECTED_CONFIGURATION[
        plan.path
    ]
    if (
        sample.validation_placement is not expected_placement
        or sample.admission_composition is not expected_admission
    ):
        add("COMPOSITION_MISMATCH", "placement/admission differs from path")
    if sample.exception_type is not None:
        add("UNEXPECTED_EXCEPTION", sample.exception_type)
        return
    if sample.producer_outcome is not expected_outcome:
        add("OUTCOME_MISMATCH", "producer outcome differs from planned path")
    if sample.classified_path is not plan.path:
        add("PATH_CLASSIFICATION_MISMATCH", "classified path differs from plan")
    if sample.idempotency_observations != EXPECTED_LIFECYCLE[plan.path]:
        add("IDEMPOTENCY_LIFECYCLE_MISMATCH", "ordered observations differ")
    if sample.measurement_availability is not MeasurementAvailability.AVAILABLE:
        add("MEASUREMENT_UNAVAILABLE", "measurement must be AVAILABLE")
    elif sample.phases is not None:
        observed = _phase_mapping(sample.phases)
        for name, expected_state in EXPECTED_PHASE_STATES[plan.path].items():
            if observed[name].state is not expected_state:
                add(
                    "PHASE_STATE_MISMATCH",
                    f"{name}: expected {expected_state.value}, got "
                    f"{observed[name].state.value}",
                )
    else:
        add("MEASUREMENT_PHASES_MISSING", "available phases are missing")
    if (
        sample.producer_return_transaction_status
        is not TransactionStatusIdentity.IDLE
    ):
        add("PRODUCER_RETURN_NOT_IDLE", "producer connection was not IDLE")
    if sample.reuse_select_succeeded is not True:
        add("CONNECTION_REUSE_FAILED", "SELECT 1 reuse did not succeed")
    if sample.final_transaction_status is not TransactionStatusIdentity.IDLE:
        add("FINAL_TRANSACTION_NOT_IDLE", "cleanup did not restore IDLE")
    _validate_durable(plan.path, sample.durable_verification, add)

    expected_eligibility = (
        TimingEligibility.STRUCTURAL_ONLY_COORDINATION_CONTAMINATED
        if plan.path in {Layer1Path.D, Layer1Path.E}
        else TimingEligibility.UNCONTAMINATED
    )
    expected_contamination = (
        CONTAMINATED_D_E_TIMING_FIELDS
        if plan.path in {Layer1Path.D, Layer1Path.E}
        else ()
    )
    if (
        sample.timing_eligibility is not expected_eligibility
        or sample.contaminated_timing_fields != expected_contamination
    ):
        add(
            "TIMING_CONTAMINATION_MISMATCH",
            "timing eligibility does not match the accepted D/E boundary",
        )


def _validate_durable(
    path: Layer1Path,
    durable: DurableVerificationResult,
    add,
) -> None:
    if not durable.verified:
        add("DURABLE_VERIFICATION_FAILED", "durable verification is not marked valid")
        return
    if durable.event_count != 1 or durable.idempotency_record_count != 1:
        add("DURABLE_ROW_COUNT_MISMATCH", "expected one event and one record")
    if path in {Layer1Path.B, Layer1Path.C, Layer1Path.G, Layer1Path.H}:
        if durable.preexisting_state_unchanged is not True:
            add("DURABLE_STATE_CHANGED", "pre-existing state did not remain exact")
    if path in {Layer1Path.D, Layer1Path.E}:
        if durable.winner_is_sole_event is not True:
            add("WINNER_NOT_SOLE_EVENT", "winner is not the sole accepted event")
        if durable.result_references_winner is not True:
            add("RESULT_WINNER_MISMATCH", "outer result does not reference winner")
    if path is Layer1Path.E and durable.losing_candidate_absent is not True:
        add("LOSING_CANDIDATE_PRESENT", "path-E losing candidate was persisted")


def _phase_mapping(phases: Sequence[PhaseRecord]) -> Mapping[str, PhaseRecord]:
    if tuple(phase.name for phase in phases) != PHASE_NAMES:
        raise Layer1ClassificationError(
            "phase evidence must contain all thirteen fields in exact order"
        )
    return {phase.name: phase for phase in phases}


def _describe(values: Sequence[int]) -> DescriptiveStatistics:
    if not values:
        raise ValueError("descriptive statistics require at least one value")
    return DescriptiveStatistics(
        count=len(values),
        minimum_ns=min(values),
        mean_ns=statistics.fmean(values),
        median_ns=float(statistics.median(values)),
        maximum_ns=max(values),
    )


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
