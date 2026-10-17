"""PR9-only declarations and raw evidence; no live numerical defaults."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid5

from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent
from src.pipeline.postgres_writer_request import WriterRetryObservation
from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
)
from src.pipeline.transactional.writer_capacity import (
    WriterAttemptIdentity, WriterCapacityObservation, WriterCapacityObservationFailure,
)
from src.pipeline.writer_retry_policy import WriterRetryPolicy
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature


METHOD = "pr9-production-retry-validation-v1"
SCHEMA = 1
COMPOSITION = "real-builder/measured/PRE_TRANSACTION/OCC/STRICT/FullProof/retained-lanes-v1"


@dataclass(frozen=True)
class Plan:
    run_id: UUID
    logical_requests: int
    concurrency_levels: tuple[int, ...]
    capacity_bound: int
    retry_policy: WriterRetryPolicy
    warmup_pairs: int
    recorded_pairs: int
    amount: Decimal
    test_database: str
    connection_budget: int
    connect_timeout_seconds: int
    stop_policy: str
    retention_policy: str

    def __post_init__(self):
        if type(self.run_id) is not UUID or type(self.retry_policy) is not WriterRetryPolicy:
            raise TypeError("explicit run UUID and retry policy required")
        for name in ("logical_requests", "capacity_bound", "recorded_pairs", "connection_budget", "connect_timeout_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be an explicit positive integer")
        if type(self.warmup_pairs) is not int or self.warmup_pairs < 0:
            raise ValueError("warmup_pairs must be an explicit nonnegative integer")
        if (type(self.concurrency_levels) is not tuple or not self.concurrency_levels
                or any(type(n) is not int or n <= 0 for n in self.concurrency_levels)
                or len(set(self.concurrency_levels)) != len(self.concurrency_levels)):
            raise ValueError("distinct positive concurrency levels required")
        if self.connection_budget < max(self.concurrency_levels) + 1:
            raise ValueError("budget must include retained lanes plus control")
        if type(self.amount) is not Decimal or not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("finite positive amount required")
        if self.amount != self.amount.quantize(Decimal("0.01")):
            raise ValueError("canonical cents required")
        if type(self.test_database) is not str or not self.test_database.endswith("_test"):
            raise ValueError("explicit test database required")
        if self.retry_policy.max_attempts < 2:
            raise ValueError("enabled comparison must allow a retry")
        if self.stop_policy != "stop_claims_and_drain_without_deadline":
            raise ValueError("explicit supported stop policy required")
        if self.retention_policy != "retain_rows":
            raise ValueError("PR9 provides no deletion or cleanup operation")


@dataclass(frozen=True)
class Cell:
    cohort: str
    pair_index: int
    concurrency: int
    enabled: bool
    execution_index: int


def schedule(plan: Plan) -> tuple[Cell, ...]:
    """Adjacent counterbalanced pairs, with disjoint warmup/recorded cohorts."""
    result = []
    for cohort, count in (("warmup", plan.warmup_pairs), ("recorded", plan.recorded_pairs)):
        for concurrency in plan.concurrency_levels:
            for pair in range(count):
                for enabled in ((False, True) if pair % 2 == 0 else (True, False)):
                    result.append(Cell(cohort, pair, concurrency, enabled, len(result)))
    return tuple(result)


def workload(plan: Plan, cell: Cell) -> tuple[RequestSignature, ...]:
    """Equivalent CREATE content/order, fresh identity per cell and logical item."""
    return tuple(RequestSignature(
        str(uuid5(plan.run_id, f"{cell.execution_index}/{index}/request")), CommandType.CREATE,
        str(uuid5(plan.run_id, f"{cell.execution_index}/{index}/order")), plan.amount,
    ) for index in range(plan.logical_requests))


@dataclass(frozen=True)
class Source:
    commit: str
    tracked_clean: bool
    machinery_committed: bool
    python: str
    psycopg: str
    platform: str
    clock: str


@dataclass(frozen=True)
class ConnectionEvidence:
    lane_id: int | None
    connection_id: int
    backend_pid: int
    database: str
    server_version: int
    isolation: str
    autocommit: bool
    opened_ns: int | None
    closed_ns: int | None = None
    close_failure: str | None = None


@dataclass(frozen=True)
class ResultEvidence:
    outcome: PostgresWriteSideOutcome
    accepted_event: OrderEvent | None
    idempotency_verdict: IdempotencyVerdict
    preparation_verdict: AdmissionVerdict | None
    append_verdict: AdmissionVerdict | None


@dataclass(frozen=True)
class MeasurementEvidence:
    identity: WriterAttemptIdentity
    availability: PostgresWriteSideMeasurementAvailability
    measurement: PostgresWriteSideMeasurement | None


@dataclass(frozen=True)
class WaitEvidence:
    identity: WriterAttemptIdentity
    requested_seconds: float
    started_ns: int | None
    ended_ns: int | None
    connection_before: int | None
    connection_after: int | None
    thread_before: int | None
    thread_after: int | None
    transaction_before: str | None
    transaction_after: str | None
    open_before: bool | None
    open_after: bool | None


@dataclass(frozen=True)
class DurableEvidence:
    accepted_events: tuple[OrderEvent, ...]
    request_event_count: int | None
    identity_idempotency_count: int | None
    idempotency_verdict: IdempotencyVerdict | None
    idempotency_signature: RequestSignature | None
    idempotency_event: OrderEvent | None
    failure: str | None


@dataclass(frozen=True)
class RequestEvidence:
    index: int
    signature: RequestSignature
    lane_id: int
    thread_id: int
    connection_id: int
    offer_ns: int | None
    invoked_ns: int | None
    terminal_ns: int | None
    result: ResultEvidence | None
    exception_class: str | None
    retry: tuple[WriterRetryObservation, ...]
    capacity: tuple[WriterCapacityObservation, ...]
    observation_failures: tuple[WriterCapacityObservationFailure, ...]
    measurements: tuple[MeasurementEvidence, ...]
    waits: tuple[WaitEvidence, ...]
    problems: tuple[str, ...]
    durable: DurableEvidence | None = None


@dataclass(frozen=True)
class UnobservedRequestEvidence:
    """An offered identity without a complete invocation record, never an acknowledgement."""

    index: int
    signature: RequestSignature
    durable: DurableEvidence


@dataclass(frozen=True)
class CellEvidence:
    plan: Plan
    cell: Cell
    before: Source
    after: Source | None
    composition: str
    connections: tuple[ConnectionEvidence, ...]
    requests: tuple[RequestEvidence, ...]
    problems: tuple[str, ...]
    unobserved: tuple[UnobservedRequestEvidence, ...] = ()


@dataclass(frozen=True)
class RunEvidence:
    plan: Plan
    cells: tuple[CellEvidence, ...]
    problems: tuple[str, ...]
