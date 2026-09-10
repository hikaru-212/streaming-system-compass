"""Immutable PR1 observations and pure accounting; no execution or policy.

These contracts record what an experiment observed. They do not authenticate a
producer return, verify a database, or decide whether an experiment is valid
capacity evidence. Production results and measurements retain their meanings.
"""

from dataclasses import dataclass
from enum import Enum
import re

from src.core.order.events import OrderEvent
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
)
from src.storage.idempotency_store import IdempotencyDecision, RequestSignature


def _nonnegative(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


class LoadAcknowledgement(str, Enum):
    """Outer acknowledgement knowledge, independent of subsequent durability."""

    ACKNOWLEDGED_ACCEPTED = "acknowledged_accepted"
    NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE = "no_new_acknowledged_accepted_write"
    UNKNOWN = "unknown"


class LoadOuterPhase(str, Enum):
    """Locations in the experiment, not a production lifecycle."""

    CONNECTION_PREPARATION = "connection_preparation"
    SCHEDULING = "scheduling"
    DISPATCHED = "dispatched"
    WRITER_CALL = "writer_call"
    TERMINAL_OBSERVATION = "terminal_observation"
    DURABLE_VERIFICATION = "durable_verification"


@dataclass(frozen=True)
class LoadWorkItem:
    """One planned item; retain the complete existing semantic identity as-is.

Fixture legality and configuration belong to the future harness. Keeping the
signature unchanged also permits recording an incorrectly prepared fixture.
"""

    workload_index: int
    signature: RequestSignature

    def __post_init__(self) -> None:
        _nonnegative(self.workload_index, "workload_index")
        if not isinstance(self.signature, RequestSignature):
            raise TypeError("signature must be RequestSignature")


@dataclass(frozen=True)
class LoadCellIdentity:
    """Locate a repetition without treating configured concurrency as overlap."""

    run_id: str
    cell_id: str
    repetition: int
    configured_concurrency: int

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a nonempty string")
        if not isinstance(self.cell_id, str) or not self.cell_id:
            raise ValueError("cell_id must be a nonempty string")
        _nonnegative(self.repetition, "repetition")
        _nonnegative(self.configured_concurrency, "configured_concurrency")
        if self.configured_concurrency == 0:
            raise ValueError("configured_concurrency must be positive")


@dataclass(frozen=True)
class LoadFailureEvidence:
    """Safe failure metadata only; callers must supply directly observed facts.

Class identity is a qualified Python identifier, not an exception message.
SQLSTATE is an optional directly available five-character code. No extractor,
traceback, diagnostic message, connection, or synthetic producer result is held.
"""

    exception_class: str
    phase: LoadOuterPhase
    writer_entered: bool
    acknowledgement: LoadAcknowledgement
    sqlstate: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.exception_class, str) or not all(
            part.isidentifier() for part in self.exception_class.split(".")
        ):
            raise ValueError("exception_class must be a qualified class identity")
        if not isinstance(self.phase, LoadOuterPhase):
            raise TypeError("phase must be LoadOuterPhase")
        if type(self.writer_entered) is not bool:
            raise TypeError("writer_entered must be bool")
        if not isinstance(self.acknowledgement, LoadAcknowledgement):
            raise TypeError("acknowledgement must be LoadAcknowledgement")
        if self.phase in (
            LoadOuterPhase.CONNECTION_PREPARATION,
            LoadOuterPhase.SCHEDULING,
            LoadOuterPhase.DISPATCHED,
        ) and self.writer_entered:
            raise ValueError("pre-entry phase cannot report writer entry")
        if self.phase is LoadOuterPhase.WRITER_CALL and not self.writer_entered:
            raise ValueError("writer-call phase requires writer entry")
        if self.sqlstate is not None and (
            not isinstance(self.sqlstate, str)
            or re.fullmatch(r"[0-9A-Z]{5}", self.sqlstate) is None
        ):
            raise ValueError("sqlstate must be a directly observed SQLSTATE code")


class LoadDurableStatus(str, Enum):
    """Durable effect observation, not client acknowledgement or correctness."""

    PRESENT = "durable_effect_present"
    ABSENT = "durable_effect_absent_after_reliable_verification"
    UNKNOWN = "verification_unavailable_or_unknown"


@dataclass(frozen=True)
class LoadDurableVerification:
    """Preserve verification linkage, including evidence of correctness loss.

Events come from durable reads, not a writer return. Multiple events and a
missing/mismatched idempotency decision remain representable for later checks.
UNKNOWN can retain partial reads. ABSENT requires reliable verification by the
future harness; construction alone cannot establish that reliability.
"""

    status: LoadDurableStatus
    accepted_events: tuple[OrderEvent, ...] = ()
    idempotency_decision: IdempotencyDecision | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, LoadDurableStatus):
            raise TypeError("status must be LoadDurableStatus")
        if type(self.accepted_events) is not tuple or not all(
            isinstance(event, OrderEvent) for event in self.accepted_events
        ):
            raise TypeError("accepted_events must be a tuple of OrderEvent")
        if self.idempotency_decision is not None and not isinstance(
            self.idempotency_decision, IdempotencyDecision
        ):
            raise TypeError("idempotency_decision must be IdempotencyDecision")
        if self.status is LoadDurableStatus.PRESENT and not self.accepted_events:
            raise ValueError("PRESENT requires observed durable events")
        if self.status is LoadDurableStatus.ABSENT and self.accepted_events:
            raise ValueError("ABSENT cannot contain observed durable events")


@dataclass(frozen=True)
class LoadRequestObservation:
    """One immutable snapshot per planned request, including incomplete work.

None means an unavailable boundary. Exit requires entry to support half-open
intervals; other missing timestamps are retained rather than reconstructed.
Normal result means an actual public writer return. Measurement availability
is the production delivery status; None means no delivery status was observed.
Verification is separate and never changes acknowledgement knowledge.
"""

    cell: LoadCellIdentity
    item: LoadWorkItem
    lane_id: int | None = None
    offer_ns: int | None = None
    dispatch_ns: int | None = None
    writer_entry_ns: int | None = None
    writer_exit_ns: int | None = None
    terminal_observation_ns: int | None = None
    result: PostgresWriteSideResult | None = None
    measurement: PostgresWriteSideMeasurement | None = None
    measurement_availability: PostgresWriteSideMeasurementAvailability | None = None
    failure: LoadFailureEvidence | None = None
    acknowledgement: LoadAcknowledgement = LoadAcknowledgement.UNKNOWN
    verification: LoadDurableVerification | None = None

    def __post_init__(self) -> None:
        for value, expected in (
            (self.cell, LoadCellIdentity), (self.item, LoadWorkItem),
            (self.acknowledgement, LoadAcknowledgement),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"expected {expected.__name__}")
        for value, expected in (
            (self.result, PostgresWriteSideResult),
            (self.measurement, PostgresWriteSideMeasurement),
            (self.measurement_availability, PostgresWriteSideMeasurementAvailability),
            (self.failure, LoadFailureEvidence),
            (self.verification, LoadDurableVerification),
        ):
            if value is not None and not isinstance(value, expected):
                raise TypeError(f"expected {expected.__name__} or None")
        if self.lane_id is not None:
            _nonnegative(self.lane_id, "lane_id")
            if self.lane_id >= self.cell.configured_concurrency:
                raise ValueError("lane_id outside configured lane range")
        if (self.dispatch_ns is not None or self.writer_entry_ns is not None) and (
            self.lane_id is None
        ):
            raise ValueError("dispatch or writer entry requires lane assignment")
        previous = None
        for name in (
            "offer_ns", "dispatch_ns", "writer_entry_ns", "writer_exit_ns",
            "terminal_observation_ns",
        ):
            value = getattr(self, name)
            if value is not None:
                _nonnegative(value, name)
                if previous is not None and value < previous:
                    raise ValueError("timestamps must be ordered")
                previous = value
        if self.writer_exit_ns is not None and self.writer_entry_ns is None:
            raise ValueError("writer exit requires writer entry")
        if self.result is not None and self.failure is not None:
            raise ValueError("normal result and escaping failure are exclusive")
        if self.result is not None:
            if self.writer_exit_ns is None:
                raise ValueError("normal result requires a completed writer interval")
            expected_ack = (
                LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                if self.result.outcome is PostgresWriteSideOutcome.ACCEPTED
                else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
            )
        elif self.failure is not None:
            if self.failure.writer_entered != (self.writer_entry_ns is not None):
                raise ValueError("failure writer-entered fact disagrees with entry")
            expected_ack = (
                LoadAcknowledgement.UNKNOWN if self.failure.writer_entered
                else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
            )
            if self.failure.acknowledgement is not self.acknowledgement:
                raise ValueError("failure acknowledgement disagrees with observation")
        else:
            expected_ack = LoadAcknowledgement.UNKNOWN
        if self.acknowledgement is not expected_ack:
            raise ValueError("acknowledgement disagrees with observed return/failure")
        if self.terminal_observation_ns is not None:
            if self.result is None and self.failure is None:
                raise ValueError("terminal observation requires result or failure")
            if self.writer_entry_ns is not None and self.writer_exit_ns is None:
                raise ValueError("entered terminal observation requires writer exit")
        available = PostgresWriteSideMeasurementAvailability.AVAILABLE
        if (self.measurement is not None) != (self.measurement_availability is available):
            raise ValueError("measurement must agree with delivery availability")
        if self.measurement_availability is not None and self.result is None:
            raise ValueError("measurement delivery requires a normal writer result")


@dataclass(frozen=True)
class LoadTiming:
    """Derived deltas; total outer latency includes finite scheduling delay."""

    scheduler_queue_wait_ns: int | None
    dispatch_to_entry_ns: int | None
    external_writer_call_ns: int | None
    terminal_observation_overhead_ns: int | None
    total_outer_latency_ns: int | None


def derive_timing(observation: LoadRequestObservation) -> LoadTiming:
    """Derive only deltas whose two boundaries are present; never sum phases."""
    def delta(start: int | None, end: int | None) -> int | None:
        return None if start is None or end is None else end - start

    return LoadTiming(
        delta(observation.offer_ns, observation.dispatch_ns),
        delta(observation.dispatch_ns, observation.writer_entry_ns),
        delta(observation.writer_entry_ns, observation.writer_exit_ns),
        delta(observation.writer_exit_ns, observation.terminal_observation_ns),
        delta(observation.offer_ns, observation.terminal_observation_ns),
    )


@dataclass(frozen=True)
class LoadCellObservation:
    """Plan plus at most one current snapshot per item, including residual work.

K is exactly len(planned); counters are derived, never independently supplied.
Tuple inputs prevent subsequent collection mutation. Only identity/accounting
consistency is validated here, not fixture legality or capacity interpretation.
"""

    identity: LoadCellIdentity
    planned: tuple[LoadWorkItem, ...]
    observations: tuple[LoadRequestObservation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.identity, LoadCellIdentity):
            raise TypeError("identity must be LoadCellIdentity")
        if type(self.planned) is not tuple or not all(
            isinstance(item, LoadWorkItem) for item in self.planned
        ):
            raise TypeError("planned must be a tuple of LoadWorkItem")
        if type(self.observations) is not tuple or not all(
            isinstance(item, LoadRequestObservation) for item in self.observations
        ):
            raise TypeError("observations must be a tuple of LoadRequestObservation")
        for identities in (
            [item.workload_index for item in self.planned],
            [item.signature.request_id for item in self.planned],
            [item.signature.order_id for item in self.planned],
        ):
            if len(set(identities)) != len(identities):
                raise ValueError("duplicate independent workload identity")
        plan = {item.workload_index: item for item in self.planned}
        seen = set()
        for observation in self.observations:
            index = observation.item.workload_index
            if observation.cell != self.identity:
                raise ValueError("observation belongs to another cell")
            if plan.get(index) != observation.item:
                raise ValueError("observation does not match planned item")
            if index in seen:
                raise ValueError("duplicate request observation")
            seen.add(index)
        # A persistent lane cannot execute two writer calls simultaneously.
        # Incomplete intervals are retained; no exit is invented to validate them.
        lanes: dict[int, list[tuple[int, int]]] = {}
        for observation in self.observations:
            if observation.writer_exit_ns is not None:
                # The per-request contract has already established both facts.
                assert observation.lane_id is not None
                assert observation.writer_entry_ns is not None
                lanes.setdefault(observation.lane_id, []).append(
                    (observation.writer_entry_ns, observation.writer_exit_ns)
                )
        for intervals in lanes.values():
            previous_exit = None
            for start, end in sorted(intervals):
                if start == end:
                    continue
                if previous_exit is not None and start < previous_exit:
                    raise ValueError("overlapping writer calls on one lane")
                previous_exit = end


@dataclass(frozen=True)
class LoadAccounting:
    """Counts of observed boundaries; absence does not invent a prior boundary.

Residual indices include every planned item without a terminal observation,
whether unoffered, queued, in flight, or incompletely observed. There is no
capacity-refusal count: this experiment has no capacity-refusal mechanism.
"""

    planned: int
    offered: int
    dispatched: int
    writer_entered: int
    terminal: int
    acknowledged_accepted: int
    residual_workload_indices: tuple[int, ...]


def derive_accounting(cell: LoadCellObservation) -> LoadAccounting:
    """Reconcile planned K with terminal observations and explicit residuals."""
    observations = cell.observations
    terminal = {
        observation.item.workload_index for observation in observations
        if observation.terminal_observation_ns is not None
    }
    return LoadAccounting(
        planned=len(cell.planned),
        offered=sum(item.offer_ns is not None for item in observations),
        dispatched=sum(item.dispatch_ns is not None for item in observations),
        writer_entered=sum(item.writer_entry_ns is not None for item in observations),
        terminal=len(terminal),
        acknowledged_accepted=sum(
            item.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
            for item in observations
        ),
        residual_workload_indices=tuple(
            item.workload_index for item in cell.planned
            if item.workload_index not in terminal
        ),
    )


@dataclass(frozen=True)
class LoadWriterOverlap:
    """Application-call overlap from complete intervals only.

When unclosed calls exist, the maximum is only a lower bound. This is neither
physical transaction overlap nor PostgreSQL CPU concurrency. Raw timestamps
remain available for later time-weighted profiles, ramp and drain analysis.
"""

    maximum_complete_interval_overlap: int
    complete_interval_count: int
    unclosed_interval_count: int


def derive_writer_overlap(cell: LoadCellObservation) -> LoadWriterOverlap:
    """Sweep half-open [entry, exit) intervals; touching endpoints do not overlap."""
    endpoints: list[tuple[int, int]] = []
    complete = unclosed = 0
    for observation in cell.observations:
        start, end = observation.writer_entry_ns, observation.writer_exit_ns
        if start is None:
            continue
        if end is None:
            unclosed += 1
            continue
        complete += 1
        if start != end:
            endpoints.extend(((start, 1), (end, -1)))
    active = maximum = 0
    for _, change in sorted(endpoints):
        active += change
        maximum = max(maximum, active)
    return LoadWriterOverlap(maximum, complete, unclosed)
