"""Versioned PR1 raw evidence, safe projections, and descriptive readback.

The codec uses an explicit type allowlist. It never imports a type named by a
file, serializes a live producer object, or reconstructs a production result.
Producer facts omit reason strings, validator metadata, and governance carriers;
the retained outcomes, verdicts, event identities and phase values are the
capacity-characterization observation, not a new semantic result contract.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
import re
from types import UnionType
from typing import Union, cast, get_args, get_origin, get_type_hints

from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadAccounting, LoadCellIdentity, LoadCellObservation,
    LoadDurableStatus, LoadFailureEvidence, LoadOuterPhase, LoadWorkItem,
    LoadWriterOverlap, derive_accounting, derive_timing, derive_writer_overlap,
)
from src.compass.transition.types import EnforcementAction, ValidationMode, ValidationVerdict
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.transactional.admission import AdmissionVerdict, AppendVersionMismatchEvidence
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurement, PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import IdempotencyDecision, IdempotencyVerdict, RequestSignature


SCHEMA_VERSION = 1
METHOD_VERSION = "pr1-unprotected-finite-load-v1"


@dataclass(frozen=True)
class LoadRunPlan:
    """All execution choices are explicit; construction performs no I/O.

Only one control connection and the current stop-and-drain mechanic are
implemented. A hard deadline is deliberately unsupported, not silently chosen.
Cleanup is restricted to verified successful cells. This declaration is not
human authorization to run a database experiment.
"""

    run_id: str
    k: int
    concurrency_levels: tuple[int, ...]
    warmups: int
    repetitions: int
    ordering_seed: int
    amount: Decimal
    test_database: str
    control_connections: int
    connection_budget: int
    connect_timeout_seconds: int
    stop_policy: str
    cleanup_policy: str

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.run_id):
            raise ValueError("run_id must be a bounded namespace identifier")
        for name in ("k", "repetitions", "connection_budget", "connect_timeout_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be an explicit positive integer")
        if type(self.warmups) is not int or self.warmups < 0:
            raise ValueError("warmups must be an explicit non-negative integer")
        if type(self.ordering_seed) is not int:
            raise ValueError("ordering_seed must be explicit")
        if type(self.concurrency_levels) is not tuple or not self.concurrency_levels:
            raise ValueError("concurrency_levels must be an explicit ordered tuple")
        if any(type(n) is not int or n <= 0 for n in self.concurrency_levels):
            raise ValueError("concurrency levels must be positive integers")
        if len(set(self.concurrency_levels)) != len(self.concurrency_levels):
            raise ValueError("concurrency levels must be distinct")
        if type(self.amount) is not Decimal or not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("amount must be a finite positive Decimal")
        if self.amount != self.amount.quantize(Decimal("0.01")):
            raise ValueError("amount must already be canonical cents")
        if not self.test_database or not self.test_database.endswith("_test"):
            raise ValueError("an explicit _test database name is required")
        if type(self.control_connections) is not int or self.control_connections != 1:
            raise ValueError("this runner requires exactly one declared control connection")
        if self.required_connections > self.connection_budget:
            raise ValueError("declared connection budget is insufficient")
        if self.stop_policy != "stop_claims_and_drain_without_deadline":
            raise ValueError("unsupported stop/deadline policy")
        if self.cleanup_policy != "delete_verified_cell_rows":
            raise ValueError("unsupported cleanup policy")

    @property
    def required_connections(self) -> int:
        return max(self.concurrency_levels) + self.control_connections


class Cohort(str, Enum):
    WARMUP = "warmup"
    RECORDED = "recorded"


@dataclass(frozen=True)
class LocalProvenance:
    source_commit: str | None
    working_tree: str | None
    python_version: str | None
    psycopg_version: str | None
    platform_system: str | None
    machine: str | None
    logical_cpus: int | None
    clock_identity: str | None


@dataclass(frozen=True)
class ConnectionFact:
    lane_id: int | None  # None identifies the declared control/verification connection.
    database: str | None
    postgres_version: int | None
    backend_pid: int | None
    isolation: str | None
    autocommit: bool | None


@dataclass(frozen=True)
class RuntimeProvenance:
    connections: tuple[ConnectionFact, ...]
    placement: str | None
    gate_identity: str | None
    validation_mode: str | None
    runtime_identity: str | None
    validator_identity: str | None


@dataclass(frozen=True)
class RunProblem:
    """Runner-stage diagnostic; no request acknowledgement is inferred here."""

    stage: str
    code: str
    exception_class: str | None = None
    sqlstate: str | None = None


@dataclass(frozen=True)
class IdempotencyEvidence:
    verdict: IdempotencyVerdict
    signature: RequestSignature | None
    accepted_event: OrderEvent | None


def idempotency_evidence(decision: IdempotencyDecision | None) -> IdempotencyEvidence | None:
    if decision is None:
        return None
    return IdempotencyEvidence(
        decision.verdict, decision.record.signature if decision.record else None,
        decision.record.accepted_event if decision.record else None,
    )


@dataclass(frozen=True)
class ProducerEvidence:
    outcome: PostgresWriteSideOutcome
    accepted_event: OrderEvent | None
    idempotency: IdempotencyEvidence
    preparation_verdict: AdmissionVerdict | None
    append_verdict: AdmissionVerdict | None
    candidate_event_id: str | None
    appended_event_id: str | None
    version_mismatch: AppendVersionMismatchEvidence | None
    validation_action: EnforcementAction | None
    validation_verdict: ValidationVerdict | None
    validation_mode: ValidationMode | None
    validator_name: str | None


@dataclass(frozen=True)
class VerificationEvidence:
    status: LoadDurableStatus
    accepted_events: tuple[OrderEvent, ...]
    idempotency: IdempotencyEvidence | None
    request_event_count: int | None
    problems: tuple[str, ...]
    failure: RunProblem | None = None


@dataclass(frozen=True)
class RequestEvidence:
    item: LoadWorkItem
    lane_id: int | None
    offer_ns: int | None
    dispatch_ns: int | None
    writer_entry_ns: int | None
    writer_exit_ns: int | None
    terminal_observation_ns: int | None
    result: ProducerEvidence | None
    measurement: PostgresWriteSideMeasurement | None
    measurement_availability: PostgresWriteSideMeasurementAvailability | None
    failure: LoadFailureEvidence | None
    acknowledgement: LoadAcknowledgement
    verification: VerificationEvidence | None

    def __post_init__(self):
        times = (self.offer_ns, self.dispatch_ns, self.writer_entry_ns,
                 self.writer_exit_ns, self.terminal_observation_ns)
        known = [value for value in times if value is not None]
        if any(type(value) is not int or value < 0 for value in known) or known != sorted(known):
            raise ValueError("invalid outer timestamp order")
        if self.writer_exit_ns is not None and self.writer_entry_ns is None:
            raise ValueError("exit without entry")
        if (self.dispatch_ns is not None or self.writer_entry_ns is not None) and self.lane_id is None:
            raise ValueError("dispatch/entry requires a lane")
        if self.result is not None and self.failure is not None:
            raise ValueError("result and failure cannot coexist")
        if self.result is not None:
            expected = (LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                        if self.result.outcome is PostgresWriteSideOutcome.ACCEPTED
                        else LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE)
            if self.acknowledgement is not expected or self.writer_exit_ns is None:
                raise ValueError("normal return acknowledgement/interval mismatch")
        elif self.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED:
            raise ValueError("acknowledgement requires a normal accepted return")
        if self.terminal_observation_ns is not None and (
            (self.result is None and self.failure is None)
            or (self.writer_entry_ns is not None and self.writer_exit_ns is None)
        ):
            raise ValueError("terminal observation requires a completed return/failure")
        if self.failure is not None and (
            self.failure.acknowledgement is not self.acknowledgement
            or self.failure.writer_entered != (self.writer_entry_ns is not None)
        ):
            raise ValueError("failure attribution mismatch")
        if self.result is None:
            expected = (LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
                        if self.failure is not None and not self.failure.writer_entered
                        else LoadAcknowledgement.UNKNOWN)
            if self.acknowledgement is not expected:
                raise ValueError("failure/missing-result acknowledgement mismatch")
        if (self.measurement is not None) != (
            self.measurement_availability is PostgresWriteSideMeasurementAvailability.AVAILABLE
        ):
            raise ValueError("measurement availability mismatch")
        if self.measurement_availability is not None and self.result is None:
            raise ValueError("measurement delivery requires a normal return")


@dataclass(frozen=True)
class CellEvidence:
    plan: LoadRunPlan
    identity: LoadCellIdentity
    cohort: Cohort
    planned: tuple[LoadWorkItem, ...]
    observations: tuple[RequestEvidence, ...]
    local: LocalProvenance
    runtime: RuntimeProvenance | None
    preparation_elapsed_ns: int | None
    setup_elapsed_ns: int | None
    verification_elapsed_ns: int | None
    quiescent_observation_ns: int | None
    cleanup_completed: bool
    problems: tuple[RunProblem, ...]
    harness_failures: tuple[LoadFailureEvidence, ...]

    def __post_init__(self):
        LoadCellObservation(self.identity, self.planned)  # Reuse independent identity validation.
        if self.identity.run_id != self.plan.run_id or len(self.planned) != self.plan.k:
            raise ValueError("cell does not match declared run/K")
        if self.identity.configured_concurrency not in self.plan.concurrency_levels:
            raise ValueError("undeclared concurrency")
        planned = {item.workload_index: item for item in self.planned}
        seen = set()
        lane_intervals = {}
        for observation in self.observations:
            index = observation.item.workload_index
            if planned.get(index) != observation.item or index in seen:
                raise ValueError("observation does not reconcile with plan")
            seen.add(index)
            if observation.lane_id is not None and not (
                0 <= observation.lane_id < self.identity.configured_concurrency
            ):
                raise ValueError("invalid lane identity")
            if observation.writer_exit_ns is not None and observation.writer_exit_ns > observation.writer_entry_ns:
                lane_intervals.setdefault(observation.lane_id, []).append(
                    (observation.writer_entry_ns, observation.writer_exit_ns)
                )
        for intervals in lane_intervals.values():
            ordered = sorted(intervals)
            if any(right[0] < left[1] for left, right in zip(ordered, ordered[1:])):
                raise ValueError("overlapping calls on one lane")
        offers = {o.offer_ns for o in self.observations if o.offer_ns is not None}
        if len(offers) > 1:
            raise ValueError("cell must share one offer boundary")
        for value in (self.preparation_elapsed_ns, self.setup_elapsed_ns,
                      self.verification_elapsed_ns, self.quiescent_observation_ns):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("invalid cell timing observation")

    @property
    def accounting(self) -> LoadAccounting:
        # These existing pure helpers read only the shared ledger attributes;
        # no producer result or measurement is manufactured for readback.
        return derive_accounting(cast(LoadCellObservation, self))

    @property
    def overlap(self) -> LoadWriterOverlap:
        return derive_writer_overlap(cast(LoadCellObservation, self))

    @property
    def incomplete(self) -> bool:
        return bool(self.accounting.residual_workload_indices)


def project_observation(observation) -> RequestEvidence:
    """Freeze the selected production facts, without diagnostic strings/metadata."""
    result = observation.result
    producer = None
    if result is not None:
        validation = result.validation_decision
        admission = result.admission_result
        producer = ProducerEvidence(
            result.outcome, result.accepted_event, idempotency_evidence(result.idempotency_decision),
            result.stream_admission_result.verdict if result.stream_admission_result else None,
            admission.verdict if admission else None,
            admission.candidate_event_id if admission else None,
            admission.accepted_event_id if admission else None,
            admission.append_version_mismatch_evidence if admission else None,
            validation.action if validation else None,
            validation.validation_result.verdict if validation else None,
            validation.validation_result.validation_mode if validation else None,
            validation.validation_result.validator_name if validation else None,
        )
    verification = observation.verification
    return RequestEvidence(
        observation.item, observation.lane_id, observation.offer_ns, observation.dispatch_ns,
        observation.writer_entry_ns, observation.writer_exit_ns, observation.terminal_observation_ns,
        producer, observation.measurement, observation.measurement_availability, observation.failure,
        observation.acknowledgement,
        VerificationEvidence(verification.status, verification.accepted_events,
                             idempotency_evidence(verification.idempotency_decision), None, ())
        if verification is not None else None,
    )


def descriptive_statistics(cell: CellEvidence) -> dict:
    """Reproducible raw latency samples and counts; no percentiles or capacity policy.

Samples include all observations with both required boundaries, in stored order.
Use per-request outcomes to select other cohorts later. An incomplete run has no
completed-run throughput. Total outer latency includes finite scheduling delay.
"""
    starts = {o.offer_ns for o in cell.observations if o.offer_ns is not None}
    ends = [o.terminal_observation_ns for o in cell.observations if o.terminal_observation_ns is not None]
    start = next(iter(starts)) if len(starts) == 1 else None
    end = max(ends) if ends else None
    elapsed = end - start if start is not None and end is not None else None
    timing = [derive_timing(o) for o in cell.observations]
    samples = {
        name: tuple(getattr(value, name) for value in timing if getattr(value, name) is not None)
        for name in ("external_writer_call_ns", "scheduler_queue_wait_ns", "total_outer_latency_ns")
    }
    return {
        "accounting": cell.accounting, "overlap": cell.overlap,
        "offer_ns": start, "last_terminal_ns": end, "observed_elapsed_ns": elapsed,
        "completed_run_elapsed_ns": elapsed if not cell.incomplete else None,
        "acknowledged_accepted_per_second": (
            cell.accounting.acknowledged_accepted * 1_000_000_000 / elapsed
            if not cell.incomplete and elapsed is not None and elapsed > 0 else None
        ),
        "samples": samples,
        "sample_counts": {name: len(values) for name, values in samples.items()},
    }


_RECORDS = {cls.__name__: cls for cls in (
    LoadRunPlan, LocalProvenance, ConnectionFact, RuntimeProvenance, RunProblem,
    IdempotencyEvidence, ProducerEvidence, VerificationEvidence, RequestEvidence, CellEvidence,
    LoadCellIdentity, LoadWorkItem, RequestSignature, OrderEvent, Proof,
    LoadFailureEvidence, PostgresWriteSideMeasurement, PostgresWriteSidePhaseMeasurement,
    AppendVersionMismatchEvidence, LoadAccounting, LoadWriterOverlap,
)}
_ENUMS = {cls.__name__: cls for cls in (
    Cohort, LoadAcknowledgement, LoadDurableStatus, LoadOuterPhase,
    CommandType, EventType, OrderStatus, PostgresWriteSideOutcome,
    PostgresWriteSideMeasurementAvailability, PostgresWriteSidePhaseMeasurementState,
    IdempotencyVerdict, AdmissionVerdict, EnforcementAction, ValidationMode, ValidationVerdict,
)}


def _encode(value):
    if type(value) in (str, int, bool, float) or value is None:
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError("non-finite Decimal")
        return {"decimal": str(value)}
    if type(value) is tuple:
        return {"tuple": [_encode(item) for item in value]}
    if type(value) in _ENUMS.values():
        return {"enum": type(value).__name__, "value": value.value}
    if type(value) in _RECORDS.values():
        return {"record": type(value).__name__, "fields": {
            field.name: _encode(getattr(value, field.name)) for field in fields(value)
        }}
    raise TypeError("value is not an allowed experiment evidence type")


def _matches(value, annotation):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (UnionType, Union):
        return any(_matches(value, arg) for arg in args)
    if origin is tuple:
        return type(value) is tuple and all(_matches(item, args[0]) for item in value)
    return type(value) is annotation


def _decode(value):
    if type(value) in (str, int, bool, float) or value is None:
        return value
    if type(value) is not dict:
        raise ValueError("invalid evidence node")
    if set(value) == {"decimal"}:
        if type(value["decimal"]) is not str:
            raise ValueError("Decimal evidence must be an exact string")
        result = Decimal(value["decimal"])
        if not result.is_finite():
            raise ValueError("non-finite Decimal")
        return result
    if set(value) == {"tuple"} and type(value["tuple"]) is list:
        return tuple(_decode(item) for item in value["tuple"])
    if set(value) == {"enum", "value"} and value["enum"] in _ENUMS:
        return _ENUMS[value["enum"]](value["value"])
    if set(value) == {"record", "fields"} and value["record"] in _RECORDS:
        cls = _RECORDS[value["record"]]
        hints = get_type_hints(cls)
        if set(value["fields"]) != set(hints):
            raise ValueError("missing or unknown evidence fields")
        decoded = {name: _decode(item) for name, item in value["fields"].items()}
        if any(not _matches(decoded[name], hint) for name, hint in hints.items()):
            raise ValueError("evidence field type mismatch")
        return cls(**decoded)
    raise ValueError("unknown evidence type/tag")


def dumps_evidence(cell: CellEvidence) -> str:
    """Serialize raw evidence plus independently reproducible ledger summaries."""
    return json.dumps({
        "schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
        "cell": _encode(cell), "accounting": _encode(cell.accounting),
        "overlap": _encode(cell.overlap),
    }, sort_keys=True, indent=2, allow_nan=False) + "\n"


def loads_evidence(text: str) -> CellEvidence:
    """Reject unsupported versions and inconsistent summaries; no dynamic imports."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    document = json.loads(text, object_pairs_hook=unique_object)
    if type(document) is not dict or set(document) != {
        "schema_version", "method_version", "cell", "accounting", "overlap",
    }:
        raise ValueError("invalid evidence envelope")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported evidence schema version")
    if document["method_version"] != METHOD_VERSION:
        raise ValueError("unsupported evidence method version")
    cell = _decode(document["cell"])
    if type(cell) is not CellEvidence:
        raise ValueError("expected cell evidence")
    if _decode(document["accounting"]) != cell.accounting or _decode(document["overlap"]) != cell.overlap:
        raise ValueError("evidence summaries do not reconcile")
    return cell


def write_evidence(path: Path, cell: CellEvidence) -> None:
    """Explicit exclusive-create output; existing evidence is never overwritten."""
    text = dumps_evidence(cell)
    with path.open("x", encoding="utf-8") as output:
        output.write(text)


def read_evidence(path: Path) -> CellEvidence:
    return loads_evidence(path.read_text(encoding="utf-8"))
