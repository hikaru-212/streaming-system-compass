"""Distinct PR4 evidence codec and descriptive metrics; no success classifier."""

from dataclasses import dataclass, fields
import json
from pathlib import Path
from typing import get_type_hints

from experiments.load_capacity_protection import evidence as pr1
from experiments.load_capacity_protection.model import LoadAcknowledgement
from experiments.load_capacity_protection.pr4_model import (
    Accounting, Characterization, ComparisonPlan, Protection, ProtectionMode,
    RequestObservation, ScheduledCell, VerificationEvidence, declared_cells, derive_accounting, derive_overlap,
    prepare_workload,
)
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSidePhaseMeasurementState


SCHEMA_VERSION = 1
METHOD_VERSION = "pr4-protected-vs-unprotected-v1"
TOPOLOGY = "N distinct retained lane connections plus one control; writer-work protection only"
OBSERVATION = "measured public CREATE in both modes; protected super.run callback timing; post-release upper boundary"


@dataclass(frozen=True)
class CellEvidence:
    plan: ComparisonPlan
    scheduled: ScheduledCell
    execution_order: tuple[ScheduledCell, ...]
    cell: Characterization
    local_before: pr1.LocalProvenance | None
    local_after: pr1.LocalProvenance | None
    runtime: pr1.RuntimeProvenance | None
    topology: str
    observation_method: str
    validation_policy_identity: str | None
    preparation_elapsed_ns: int | None
    setup_elapsed_ns: int | None
    verification_elapsed_ns: int | None
    quiescent_observation_ns: int | None
    cleanup_completed: bool
    problems: tuple[pr1.RunProblem, ...]
    harness_failures: tuple[pr1.LoadFailureEvidence, ...]

    def __post_init__(self):
        if self.execution_order != declared_cells(self.plan) or self.scheduled not in self.execution_order:
            raise ValueError("cell order differs from declared plan")
        if (self.cell.identity != self.scheduled.identity
                or self.cell.protection != self.scheduled.protection
                or self.cell.planned != prepare_workload(self.plan, self.scheduled)):
            raise ValueError("cell differs from declaration")
        if self.topology != TOPOLOGY or self.observation_method != OBSERVATION:
            raise ValueError("unsupported topology/observation method")
        for value in (self.preparation_elapsed_ns, self.setup_elapsed_ns,
                      self.verification_elapsed_ns, self.quiescent_observation_ns):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("invalid cell timing")

    @property
    def accounting(self) -> Accounting:
        return derive_accounting(self.cell)

    @property
    def incomplete(self) -> bool:
        return bool(self.accounting.residual_workload_indices or self.problems or self.harness_failures)


def summaries(evidence: CellEvidence) -> dict:
    """Recompute counts; capacity None is N/A, never implicit admission."""
    protected = evidence.scheduled.protection.mode is ProtectionMode.PROTECTED
    return {
        "accounting": evidence.accounting,
        "public_call_overlap": derive_overlap(evidence.cell, protected=False),
        "protected_writer_overlap": derive_overlap(evidence.cell, protected=True) if protected else None,
        "harness_failures": len(evidence.harness_failures),
        "evidence_problems": len(evidence.problems),
        "incomplete": evidence.incomplete,
    }


def descriptive_statistics(evidence: CellEvidence) -> dict:
    """Raw samples with explicit cohorts/counts; ratios keep their denominators.

No percentile, pooled repetition, acceptance threshold, or performance pass/fail
is selected. Incomplete cells have no completed-cell throughput. Phase absence
stays absent. Warmup identity remains attached; recorded_statistics excludes it.
"""
    rows = evidence.cell.observations
    counts = evidence.accounting
    offers = {o.offer_ns for o in rows if o.offer_ns is not None}
    ends = [o.terminal_observation_ns for o in rows if o.terminal_observation_ns is not None]
    elapsed = max(ends) - next(iter(offers)) if len(offers) == 1 and ends else None
    intervals = {
        "public_call_ns": ("public_call_entry_ns", "public_call_exit_ns"),
        "protected_writer_body_ns": ("protected_writer_entry_ns", "protected_writer_exit_ns"),
        "scheduler_wait_ns": ("offer_ns", "dispatch_ns"),
        "dispatch_to_public_call_ns": ("dispatch_ns", "public_call_entry_ns"),
        "admission_to_body_ns": ("capacity_admitted_ns", "protected_writer_entry_ns"),
        "attempt_to_admitted_ns": ("capacity_attempt_ns", "capacity_admitted_ns"),
        "attempt_to_refused_ns": ("capacity_attempt_ns", "capacity_refused_ns"),
        "body_exit_to_admission_return_ns": ("protected_writer_exit_ns", "admission_return_ns"),
        "public_exit_to_terminal_ns": ("public_call_exit_ns", "terminal_observation_ns"),
        "outer_terminal_latency_ns": ("offer_ns", "terminal_observation_ns"),
    }
    cohorts = {
        "all": rows,
        "acknowledged_accepted": tuple(o for o in rows if o.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED),
        "capacity_refused": tuple(o for o in rows if o.capacity_refused_ns is not None),
        "native_failure": tuple(o for o in rows if o.failure is not None),
    }
    samples = {}
    for cohort, observations in cohorts.items():
        values = {
            name: tuple(getattr(o, end) - getattr(o, start) for o in observations
                        if getattr(o, start) is not None and getattr(o, end) is not None)
            for name, (start, end) in intervals.items()
        }
        for phase in (f.name for f in fields(pr1.PostgresWriteSideMeasurement)):
            values[f"phase.{phase}"] = tuple(
                getattr(o.measurement, phase).elapsed_ns for o in observations
                if o.measurement is not None
                and getattr(o.measurement, phase).state is PostgresWriteSidePhaseMeasurementState.MEASURED
            )
        samples[cohort] = values

    def ratio(numerator, denominator):
        return numerator / denominator if numerator is not None and denominator else None

    return {
        **summaries(evidence), "cohort": evidence.scheduled.cohort.value,
        "mode": evidence.scheduled.protection.mode.value, "bound": evidence.scheduled.protection.bound,
        "k": evidence.plan.k, "offered_concurrency": evidence.cell.identity.configured_concurrency,
        "observed_elapsed_ns": elapsed,
        "completed_cell_elapsed_ns": elapsed if not evidence.incomplete else None,
        "acknowledged_accepted_per_second": (
            counts.acknowledged_accepted * 1_000_000_000 / elapsed
            if not evidence.incomplete and elapsed is not None and elapsed > 0 else None
        ),
        "accepted_proportion_of_offered": ratio(counts.acknowledged_accepted, counts.offered),
        "admission_ratio_of_attempted": ratio(counts.capacity_admitted, counts.capacity_attempts),
        "refusal_ratio_of_attempted": ratio(counts.capacity_refused, counts.capacity_attempts),
        "refusal_proportion_of_offered": ratio(counts.capacity_refused, counts.offered),
        "samples": samples,
        "sample_counts": {cohort: {name: len(value) for name, value in values.items()}
                          for cohort, values in samples.items()},
    }


def recorded_statistics(cells: tuple[CellEvidence, ...]) -> tuple[dict, ...]:
    """Keep whole recorded cells separate; never include warmups in this cohort."""
    return tuple(descriptive_statistics(cell) for cell in cells if cell.scheduled.cohort is pr1.Cohort.RECORDED)


_RECORDS = {cls.__name__: cls for cls in (
    ComparisonPlan, Protection, ScheduledCell, VerificationEvidence, RequestObservation,
    Characterization, Accounting, CellEvidence,
)}


def _encode(value):
    if type(value) is ProtectionMode:
        return {"pr4_enum": "ProtectionMode", "value": value.value}
    if type(value) is tuple:
        return {"tuple": [_encode(item) for item in value]}
    if type(value) in _RECORDS.values():
        return {"pr4_record": type(value).__name__, "fields": {
            f.name: _encode(getattr(value, f.name)) for f in fields(value)
        }}
    # Reuse frozen fact codecs without changing PR1's type registry or envelope.
    return pr1._encode(value)


def _decode(value):
    if type(value) is dict:
        if set(value) == {"pr4_enum", "value"} and value["pr4_enum"] == "ProtectionMode":
            return ProtectionMode(value["value"])
        if set(value) == {"tuple"} and type(value["tuple"]) is list:
            return tuple(_decode(item) for item in value["tuple"])
        if set(value) == {"pr4_record", "fields"}:
            cls = _RECORDS.get(value["pr4_record"])
            if cls is None or type(value["fields"]) is not dict:
                raise ValueError("unknown PR4 record")
            hints = get_type_hints(cls)
            if set(value["fields"]) != set(hints):
                raise ValueError("missing or unknown PR4 fields")
            decoded = {name: _decode(item) for name, item in value["fields"].items()}
            if any(not pr1._matches(decoded[name], hint) for name, hint in hints.items()):
                raise ValueError("PR4 field type mismatch")
            return cls(**decoded)
    return pr1._decode(value)


def dumps_evidence(evidence: CellEvidence) -> str:
    """Serialize only PR4 facts; exclusive file creation is a separate operation."""
    if type(evidence) is not CellEvidence:
        raise TypeError("PR4 CellEvidence required")
    return json.dumps({
        "schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
        "cell": _encode(evidence),
        "summaries": {name: _encode(value) for name, value in summaries(evidence).items()},
    }, sort_keys=True, indent=2, allow_nan=False) + "\n"


def loads_evidence(text: str) -> CellEvidence:
    """Fail closed on unsupported versions, tags, fields, types or summaries."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    document = json.loads(text, object_pairs_hook=unique)
    if type(document) is not dict or set(document) != {"schema_version", "method_version", "cell", "summaries"}:
        raise ValueError("invalid PR4 envelope")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported PR4 schema version")
    if document["method_version"] != METHOD_VERSION:
        raise ValueError("unsupported PR4 method version")
    cell = _decode(document["cell"])
    if type(cell) is not CellEvidence:
        raise ValueError("expected PR4 evidence")
    expected = {name: _encode(value) for name, value in summaries(cell).items()}
    if json.dumps(document["summaries"], sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("PR4 summaries do not reconcile")
    return cell


def write_evidence(path: Path, evidence: CellEvidence) -> None:
    """Write a new PR4 file only, never overwrite prior evidence."""
    text = dumps_evidence(evidence)
    with path.open("x", encoding="utf-8") as output:
        output.write(text)


def read_evidence(path: Path) -> CellEvidence:
    return loads_evidence(path.read_text(encoding="utf-8"))
