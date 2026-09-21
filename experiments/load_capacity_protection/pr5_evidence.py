"""PR5 raw trajectories, strict distinct codec, and descriptive attempt metrics."""

from dataclasses import dataclass, fields
import json
from pathlib import Path
from typing import get_type_hints

from experiments.load_capacity_protection import evidence as pr1
from experiments.load_capacity_protection import pr4_evidence as pr4
from experiments.load_capacity_protection.model import LoadAcknowledgement
from experiments.load_capacity_protection.pr4_model import derive_overlap
from experiments.load_capacity_protection.pr5_model import (
    AttemptEvidence, Characterization, LogicalRequestEvidence, LogicalTerminal,
    RetryConfig, RetryPlan, RetryPolicy, ScheduledCell, declared_cells, prepare_workload,
)


SCHEMA_VERSION = 1
METHOD_VERSION = "pr5-retry-refusal-amplification-v1"
TOPOLOGY = "N distinct retained lane connections plus one control; same lane/connection across retries"
OBSERVATION = "measured public CREATE; real shared PR3 observed admission; caller retry outside released capacity"


@dataclass(frozen=True)
class CellEvidence:
    plan: RetryPlan
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
        self.cell.__post_init__()
        if self.execution_order != declared_cells(self.plan) or self.scheduled not in self.execution_order:
            raise ValueError("cell order differs from declaration")
        if (self.cell.identity != self.scheduled.identity or self.cell.retry != self.scheduled.retry
                or self.cell.protection.bound != self.plan.protection_bound
                or self.cell.planned != prepare_workload(self.plan, self.scheduled)):
            raise ValueError("cell differs from plan")
        if self.topology != TOPOLOGY or self.observation_method != OBSERVATION:
            raise ValueError("unsupported topology/observation")
        for value in (self.preparation_elapsed_ns, self.setup_elapsed_ns,
                      self.verification_elapsed_ns, self.quiescent_observation_ns):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("invalid cell timing")
        finals = [r.final_terminal_ns for r in self.cell.logical_requests if r.final_terminal_ns is not None]
        if self.quiescent_observation_ns is not None and finals and self.quiescent_observation_ns < max(finals):
            raise ValueError("quiescence precedes completion")

    @property
    def incomplete(self):
        normal = {LogicalTerminal.ACKNOWLEDGED_ACCEPTED,
                  LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL}
        return bool(self.problems or self.harness_failures or any(
            r.terminal_state not in normal for r in self.cell.logical_requests
        ))


def logical_summaries(cell):
    """Reconstruct each intent without consulting scheduler internals."""
    return tuple({
        "logical_request_index": r.item.workload_index,
        "attempts": len(r.attempts),
        "capacity_refusals": sum(a.observation.capacity_refused_ns is not None for a in r.attempts),
        "terminal_state": r.terminal_state.value,
        "first_attempt_ns": r.first_attempt_ns,
        "final_terminal_ns": r.final_terminal_ns,
        "completion_latency_ns": r.completion_latency_ns,
        "first_attempt_to_terminal_ns": (r.final_terminal_ns - r.first_attempt_ns
            if r.final_terminal_ns is not None and r.first_attempt_ns is not None else None),
        "accepted_event_id": (r.attempts[-1].observation.result.accepted_event.event_id
            if r.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED
            and r.attempts[-1].observation.result.accepted_event is not None else None),
    } for r in cell.logical_requests)


def summaries(evidence):
    cell = evidence.cell
    rows, requests = cell.observations, cell.logical_requests
    total = len(rows)
    return {
        "logical_requests": len(cell.planned),
        "offered_logical_requests": sum(r.offer_ns is not None for r in requests),
        "total_attempts": total,
        "capacity_attempts": sum(o.capacity_attempt_ns is not None for o in rows),
        "capacity_refused_attempts": sum(o.capacity_refused_ns is not None for o in rows),
        "admitted_attempts": sum(o.capacity_admitted_ns is not None for o in rows),
        "terminal_attempts": sum(o.terminal_observation_ns is not None for o in rows),
        "acknowledged_accepted_logical_requests": sum(
            r.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED for r in requests),
        "retry_budget_exhausted_logical_requests": sum(
            r.terminal_state is LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL for r in requests),
        "terminal_logical_requests": sum(r.final_terminal_ns is not None for r in requests),
        "native_writer_failures": sum(o.failure is not None for o in rows),
        "total_retries": sum(max(0, len(r.attempts) - 1) for r in requests),
        "attempt_amplification_factor": total / len(cell.planned),
        "residual_logical_request_indices": tuple(r.item.workload_index for r in requests
                                                   if r.terminal_state is LogicalTerminal.INCOMPLETE),
        "protected_writer_overlap": derive_overlap(cell, protected=True),
        "public_call_overlap": derive_overlap(cell, protected=False),
        "harness_failures": len(evidence.harness_failures),
        "evidence_problems": len(evidence.problems),
        "incomplete": evidence.incomplete,
    }


def descriptive_statistics(evidence):
    """No policy winner, percentile, universal rate window, or pooled repetitions.

Completion proportion means acknowledged accepted logical requests / K. Terminal
drain proportion separately includes refusal-budget exhaustion. Useful logical
completion and accepted writer throughput coincide for this CREATE-only fixture;
attempt throughput and generic logical-terminal throughput remain separate.
"""
    counts = summaries(evidence)
    logical = logical_summaries(evidence.cell)
    rows = evidence.cell.observations
    offers = [r.offer_ns for r in evidence.cell.logical_requests if r.offer_ns is not None]
    ends = [r.final_terminal_ns for r in evidence.cell.logical_requests if r.final_terminal_ns is not None]
    elapsed = max(ends) - min(offers) if offers and ends else None

    def rate(count):
        return count * 1e9 / elapsed if not evidence.incomplete and elapsed and elapsed > 0 else None

    accepted = counts["acknowledged_accepted_logical_requests"]
    return {
        **counts, "cohort": evidence.scheduled.cohort.value, "policy": evidence.scheduled.retry.policy.value,
        "logical": logical, "observed_elapsed_ns": elapsed,
        "time_to_drain_logical_workload_ns": elapsed if not evidence.incomplete else None,
        "attempts_per_logical_request": tuple(r["attempts"] for r in logical),
        "capacity_refusals_per_logical_request": tuple(r["capacity_refusals"] for r in logical),
        "logical_completion_proportion": accepted / evidence.plan.k,
        "logical_terminal_proportion": counts["terminal_logical_requests"] / evidence.plan.k,
        "attempts_per_second": rate(counts["total_attempts"]),
        "accepted_writer_per_second": rate(accepted),
        "logical_completion_per_second": rate(accepted),
        "logical_terminals_per_second": rate(counts["terminal_logical_requests"]),
        "attempt_dispatch_timestamps_ns": tuple(o.dispatch_ns for o in rows if o.dispatch_ns is not None),
        "capacity_attempt_timestamps_ns": tuple(o.capacity_attempt_ns for o in rows if o.capacity_attempt_ns is not None),
        "retry_lateness_ns": tuple(
            b.observation.dispatch_ns - a.next_retry_eligible_ns
            for r in evidence.cell.logical_requests for a, b in zip(r.attempts, r.attempts[1:])
        ),
        "accepted_phase_samples": {
            f.name: tuple(getattr(o.measurement, f.name).elapsed_ns for o in rows
                          if o.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                          and o.measurement is not None
                          and getattr(o.measurement, f.name).state is pr1.PostgresWriteSidePhaseMeasurementState.MEASURED)
            for f in fields(pr1.PostgresWriteSideMeasurement)
        },
    }


def attempt_windows(evidence, *, width_ns: int, origin_ns: int):
    """Sparse half-open capacity-attempt bins; omitted bins have zero attempts.

The caller selects both width and origin; negative bin indices are supported.
Each returned pair is (bin_index, count). Exact raw timestamps remain available.
"""
    if type(width_ns) is not int or width_ns <= 0 or type(origin_ns) is not int or origin_ns < 0:
        raise ValueError("explicit positive width and nonnegative origin required")
    bins = {}
    for row in evidence.cell.observations:
        if row.capacity_attempt_ns is not None:
            index = (row.capacity_attempt_ns - origin_ns) // width_ns
            bins[index] = bins.get(index, 0) + 1
    return tuple(sorted(bins.items()))


def recorded_statistics(cells):
    return tuple(descriptive_statistics(c) for c in cells if c.scheduled.cohort is pr1.Cohort.RECORDED)


_RECORDS = {cls.__name__: cls for cls in (
    RetryConfig, RetryPlan, ScheduledCell, AttemptEvidence, LogicalRequestEvidence, Characterization, CellEvidence,
)}
_ENUMS = {cls.__name__: cls for cls in (RetryPolicy, LogicalTerminal)}


def _encode(value):
    if type(value) in _ENUMS.values():
        return {"pr5_enum": type(value).__name__, "value": value.value}
    if type(value) is tuple:
        return {"tuple": [_encode(item) for item in value]}
    if type(value) in _RECORDS.values():
        return {"pr5_record": type(value).__name__, "fields": {
            f.name: _encode(getattr(value, f.name)) for f in fields(value)
        }}
    return pr4._encode(value)


def _decode(value):
    if type(value) is dict:
        if set(value) == {"pr5_enum", "value"} and value["pr5_enum"] in _ENUMS:
            return _ENUMS[value["pr5_enum"]](value["value"])
        if set(value) == {"tuple"} and type(value["tuple"]) is list:
            return tuple(_decode(item) for item in value["tuple"])
        if set(value) == {"pr5_record", "fields"}:
            cls = _RECORDS.get(value["pr5_record"])
            if cls is None or type(value["fields"]) is not dict:
                raise ValueError("unknown PR5 record")
            hints = get_type_hints(cls)
            if set(value["fields"]) != set(hints):
                raise ValueError("missing or unknown PR5 fields")
            decoded = {name: _decode(item) for name, item in value["fields"].items()}
            if any(not pr1._matches(decoded[name], hint) for name, hint in hints.items()):
                raise ValueError("PR5 field type mismatch")
            return cls(**decoded)
    return pr4._decode(value)


def dumps_evidence(evidence):
    if type(evidence) is not CellEvidence:
        raise TypeError("PR5 CellEvidence required")
    evidence.__post_init__()
    return json.dumps({
        "schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION, "cell": _encode(evidence),
        "summaries": {name: _encode(value) for name, value in summaries(evidence).items()},
        "logical_summaries": logical_summaries(evidence.cell),
    }, sort_keys=True, indent=2, allow_nan=False) + "\n"


def loads_evidence(text):
    """Fail closed on versions, duplicate keys, unknown types/fields or corrupt trajectories."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    document = json.loads(text, object_pairs_hook=unique)
    if type(document) is not dict or set(document) != {
        "schema_version", "method_version", "cell", "summaries", "logical_summaries",
    }:
        raise ValueError("invalid PR5 envelope")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported PR5 schema version")
    if document["method_version"] != METHOD_VERSION:
        raise ValueError("unsupported PR5 method version")
    evidence = _decode(document["cell"])
    if type(evidence) is not CellEvidence:
        raise ValueError("expected PR5 evidence")
    expected = json.loads(dumps_evidence(evidence))
    for name in ("summaries", "logical_summaries"):
        if json.dumps(document[name], sort_keys=True) != json.dumps(expected[name], sort_keys=True):
            raise ValueError("PR5 summaries do not reconcile")
    return evidence


def write_evidence(path: Path, evidence):
    """Exclusive creation only; callers explicitly own path and live authorization."""
    text = dumps_evidence(evidence)
    with path.open("x", encoding="utf-8") as output:
        output.write(text)


def read_evidence(path: Path):
    return loads_evidence(path.read_text(encoding="utf-8"))
