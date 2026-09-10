"""PR4-only configuration and immutable observations; no admission policy or I/O.

PR1's public-call ledger remains frozen. PR4 names public calls and protected
bodies separately and represents refusal without a production result/failure.
"""

from dataclasses import dataclass
from enum import Enum
from random import Random

from experiments.load_capacity_protection.evidence import (
    Cohort, LoadRunPlan, ProducerEvidence, VerificationEvidence as PR1VerificationEvidence,
)
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadCellIdentity, LoadCellObservation, LoadFailureEvidence,
    LoadWorkItem, LoadWriterOverlap,
)
from src.core.order.enums import CommandType
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
)
from src.storage.idempotency_store import RequestSignature


class ProtectionMode(str, Enum):
    UNPROTECTED = "unprotected"
    PROTECTED = "protected"


@dataclass(frozen=True, kw_only=True)
class VerificationEvidence(PR1VerificationEvidence):
    """PR1 durable facts plus raw idempotency rows matching request OR order.

The extra count detects an orphan/mismatched mapping that a request-key lookup
alone could miss. None means unavailable, never verified absence.
"""

    identity_idempotency_count: int | None = None

    def __post_init__(self):
        for value in (self.request_event_count, self.identity_idempotency_count):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("durable row counts must be non-negative integers or absent")


@dataclass(frozen=True)
class Protection:
    mode: ProtectionMode
    bound: int | None

    def __post_init__(self):
        if type(self.mode) is not ProtectionMode:
            raise TypeError("explicit ProtectionMode required")
        if self.mode is ProtectionMode.UNPROTECTED:
            if self.bound is not None:
                raise ValueError("unprotected bound must be absent")
        elif type(self.bound) is not int or self.bound <= 0:
            raise ValueError("protected bound must be an explicit positive integer")


@dataclass(frozen=True)
class ComparisonPlan(LoadRunPlan):
    """Explicit A/B configuration; eight is never a library default.

Inherited values keep PR1's finite CREATE fixture and retained-connection budget.
Each round visits declared levels with adjacent opposite conditions, reversing
which mode leads by level and repetition. Seed controls item permutation only.
"""

    protection_bound: int
    pairing_order: str
    first_mode: ProtectionMode

    def __post_init__(self):
        super().__post_init__()
        Protection(ProtectionMode.PROTECTED, self.protection_bound)
        if self.pairing_order != "alternating_adjacent_pairs":
            raise ValueError("unsupported pairing order")
        if type(self.first_mode) is not ProtectionMode:
            raise TypeError("first_mode must be explicit")


@dataclass(frozen=True)
class ScheduledCell:
    identity: LoadCellIdentity
    cohort: Cohort
    protection: Protection
    execution_index: int
    pair_index: int
    position_in_pair: int


def declared_cells(plan: ComparisonPlan) -> tuple[ScheduledCell, ...]:
    """Return the entire predetermined order, including separately labeled warmups."""
    plan.__post_init__()
    result = []
    opposite = (ProtectionMode.PROTECTED if plan.first_mode is ProtectionMode.UNPROTECTED
                else ProtectionMode.UNPROTECTED)
    for cohort, count in ((Cohort.WARMUP, plan.warmups), (Cohort.RECORDED, plan.repetitions)):
        for repetition in range(count):
            for level_index, concurrency in enumerate(plan.concurrency_levels):
                modes = (plan.first_mode, opposite)
                if (repetition + level_index) % 2:
                    modes = modes[::-1]
                pair_index = len(result) // 2
                for position, mode in enumerate(modes):
                    result.append(ScheduledCell(
                        LoadCellIdentity(
                            plan.run_id, f"pr4-level-{level_index}-{cohort.value}-{mode.value}",
                            repetition, concurrency,
                        ), cohort, Protection(
                            mode, plan.protection_bound if mode is ProtectionMode.PROTECTED else None,
                        ), len(result), pair_index, position,
                    ))
    return tuple(result)


def prepare_workload(plan: ComparisonPlan, scheduled: ScheduledCell) -> tuple[LoadWorkItem, ...]:
    """Prepare disjoint cell identities and the same seeded index permutation."""
    if scheduled not in declared_cells(plan):
        raise ValueError("cell is not declared")
    identity = scheduled.identity
    prefix = f"pr4-load:{plan.run_id}:{identity.cell_id}:{identity.repetition}"
    items = [LoadWorkItem(index, RequestSignature(
        f"{prefix}:request-{index}", CommandType.CREATE, f"{prefix}:order-{index}", plan.amount,
    )) for index in range(plan.k)]
    Random(plan.ordering_seed).shuffle(items)
    return tuple(items)


@dataclass(frozen=True)
class RequestObservation:
    """One attempt at one item, with safe facts only and no retry authority.

Admission timestamps are callback observations, not exact semaphore instants.
admission_return_ns follows release for admitted work. Protected body timestamps
are absent for refusals and unprotected calls; public-call timestamps cover both.
An incomplete observation may preserve partial boundaries without a terminal.
"""

    item: LoadWorkItem
    protection: Protection
    lane_id: int | None = None
    offer_ns: int | None = None
    dispatch_ns: int | None = None
    public_call_entry_ns: int | None = None
    capacity_attempt_ns: int | None = None
    capacity_admitted_ns: int | None = None
    capacity_refused_ns: int | None = None
    protected_writer_entry_ns: int | None = None
    protected_writer_exit_ns: int | None = None
    admission_return_ns: int | None = None
    public_call_exit_ns: int | None = None
    terminal_observation_ns: int | None = None
    result: ProducerEvidence | None = None
    measurement: PostgresWriteSideMeasurement | None = None
    measurement_availability: PostgresWriteSideMeasurementAvailability | None = None
    failure: LoadFailureEvidence | None = None
    acknowledgement: LoadAcknowledgement = LoadAcknowledgement.UNKNOWN
    verification: VerificationEvidence | None = None

    def __post_init__(self):
        self.protection.__post_init__()
        names = (
            "offer_ns", "dispatch_ns", "public_call_entry_ns", "capacity_attempt_ns",
            "capacity_admitted_ns", "capacity_refused_ns", "protected_writer_entry_ns",
            "protected_writer_exit_ns", "admission_return_ns", "public_call_exit_ns",
            "terminal_observation_ns",
        )
        known = [getattr(self, name) for name in names if getattr(self, name) is not None]
        if any(type(v) is not int or v < 0 for v in known) or known != sorted(known):
            raise ValueError("invalid PR4 timestamp order")
        if self.lane_id is not None and (type(self.lane_id) is not int or self.lane_id < 0):
            raise ValueError("invalid lane")
        if self.dispatch_ns is not None and (self.lane_id is None or self.offer_ns is None):
            raise ValueError("dispatch requires lane and offer")
        if self.public_call_entry_ns is not None and self.dispatch_ns is None:
            raise ValueError("public call requires dispatch")
        for end, start in (
            (self.public_call_exit_ns, self.public_call_entry_ns),
            (self.capacity_attempt_ns, self.public_call_entry_ns),
            (self.capacity_admitted_ns, self.capacity_attempt_ns),
            (self.capacity_refused_ns, self.capacity_attempt_ns),
            (self.protected_writer_entry_ns, self.capacity_admitted_ns),
            (self.protected_writer_exit_ns, self.protected_writer_entry_ns),
            (self.admission_return_ns, self.capacity_attempt_ns),
        ):
            if end is not None and start is None:
                raise ValueError("PR4 boundary without prerequisite")
        if self.protection.mode is ProtectionMode.UNPROTECTED and any(
            getattr(self, name) is not None for name in names[3:9]
        ):
            raise ValueError("unprotected capacity/body fields are not applicable")
        if self.capacity_refused_ns is not None:
            if any(value is not None for value in (
                self.capacity_admitted_ns, self.protected_writer_entry_ns,
                self.protected_writer_exit_ns, self.result, self.failure,
                self.measurement, self.measurement_availability,
            )):
                raise ValueError("capacity refusal cannot carry writer evidence")
            expected = LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
        elif self.result is not None:
            if self.failure is not None or self.public_call_exit_ns is None:
                raise ValueError("result requires completed normal call")
            if self.protection.mode is ProtectionMode.PROTECTED and self.protected_writer_exit_ns is None:
                raise ValueError("protected result requires observed body exit")
            expected = (LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                        if self.result.outcome is PostgresWriteSideOutcome.ACCEPTED
                        else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE)
        else:
            expected = LoadAcknowledgement.UNKNOWN
        if self.acknowledgement is not expected:
            raise ValueError("acknowledgement does not match PR4 observation")
        if self.failure is not None and (
            not self.writer_entered or not self.failure.writer_entered
            or self.failure.acknowledgement is not LoadAcknowledgement.UNKNOWN
        ):
            raise ValueError("native writer failure requires body entry")
        if self.terminal_observation_ns is not None and (
            self.public_call_exit_ns is None
            or (self.result is None and self.failure is None and self.capacity_refused_ns is None)
            or (self.protection.mode is ProtectionMode.PROTECTED and self.admission_return_ns is None)
        ):
            raise ValueError("terminal requires completed observed call")
        if (self.measurement is not None) != (
            self.measurement_availability is PostgresWriteSideMeasurementAvailability.AVAILABLE
        ) or (self.measurement_availability is not None and self.result is None):
            raise ValueError("measurement delivery mismatch")

    @property
    def writer_entered(self) -> bool:
        return (self.protected_writer_entry_ns is not None
                if self.protection.mode is ProtectionMode.PROTECTED
                else self.public_call_entry_ns is not None)


@dataclass(frozen=True)
class Characterization:
    identity: LoadCellIdentity
    protection: Protection
    planned: tuple[LoadWorkItem, ...]
    observations: tuple[RequestObservation, ...]

    def __post_init__(self):
        LoadCellObservation(self.identity, self.planned)
        planned = {item.workload_index: item for item in self.planned}
        seen, offers, lanes = set(), set(), {}
        for observation in self.observations:
            index = observation.item.workload_index
            if planned.get(index) != observation.item or index in seen:
                raise ValueError("observation does not reconcile with workload")
            seen.add(index)
            if observation.protection != self.protection:
                raise ValueError("mixed protection modes")
            if observation.offer_ns is not None:
                offers.add(observation.offer_ns)
            if observation.lane_id is not None and observation.lane_id >= self.identity.configured_concurrency:
                raise ValueError("lane outside declared concurrency")
            if observation.public_call_exit_ns is not None:
                lanes.setdefault(observation.lane_id, []).append(
                    (observation.public_call_entry_ns, observation.public_call_exit_ns),
                )
        if len(offers) > 1:
            raise ValueError("multiple offer boundaries")
        for intervals in lanes.values():
            intervals.sort()
            if any(b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
                raise ValueError("overlapping public calls on one lane")


@dataclass(frozen=True)
class Accounting:
    planned: int
    offered: int
    dispatched: int
    capacity_attempts: int | None
    capacity_admitted: int | None
    capacity_refused: int | None
    protected_writer_entered: int | None
    writer_entered: int
    writer_terminal: int
    terminal: int
    acknowledged_accepted: int
    native_writer_failures: int
    residual_workload_indices: tuple[int, ...]


def derive_accounting(cell: Characterization) -> Accounting:
    """None counts mean not applicable for unprotected admission/body observations."""
    rows = cell.observations
    def count(name):
        return sum(getattr(o, name) is not None for o in rows)
    def capacity(name):
        return count(name) if cell.protection.mode is ProtectionMode.PROTECTED else None
    terminal = {o.item.workload_index for o in rows if o.terminal_observation_ns is not None}
    return Accounting(
        len(cell.planned), count("offer_ns"), count("dispatch_ns"),
        capacity("capacity_attempt_ns"), capacity("capacity_admitted_ns"),
        capacity("capacity_refused_ns"), capacity("protected_writer_entry_ns"),
        sum(o.writer_entered for o in rows),
        sum(o.writer_entered and o.terminal_observation_ns is not None for o in rows),
        len(terminal), sum(o.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED for o in rows),
        count("failure"), tuple(i.workload_index for i in cell.planned if i.workload_index not in terminal),
    )


def derive_overlap(cell: Characterization, *, protected: bool) -> LoadWriterOverlap:
    """Half-open application intervals only; unfinished intervals remain visible."""
    prefix = "protected_writer" if protected else "public_call"
    endpoints, complete, unclosed = [], 0, 0
    for observation in cell.observations:
        start = getattr(observation, f"{prefix}_entry_ns")
        end = getattr(observation, f"{prefix}_exit_ns")
        if start is None:
            continue
        if end is None:
            unclosed += 1
        else:
            complete += 1
            if end > start:
                endpoints.extend(((start, 1), (end, -1)))
    active = maximum = 0
    for _, change in sorted(endpoints):
        active += change
        maximum = max(maximum, active)
    return LoadWriterOverlap(maximum, complete, unclosed)
