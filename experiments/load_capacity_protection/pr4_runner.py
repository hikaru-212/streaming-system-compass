"""Explicit PR4 paired execution, source checks and post-quiescence ownership."""

from collections.abc import Callable
from dataclasses import dataclass, replace
import re

from experiments.load_capacity_protection.evidence import LocalProvenance, RunProblem, RuntimeProvenance
from experiments.load_capacity_protection.model import LoadAcknowledgement, LoadDurableStatus
from experiments.load_capacity_protection.pr4_characterization import (
    CharacterizationError, ObservedAdmission, run_characterization,
)
from experiments.load_capacity_protection.pr4_evidence import CellEvidence, OBSERVATION, TOPOLOGY
from experiments.load_capacity_protection.pr4_model import (
    Characterization, ComparisonPlan, ProtectionMode, VerificationEvidence,
    declared_cells, derive_accounting, derive_overlap, prepare_workload,
)
from experiments.load_capacity_protection.runner import _problem, verification_problems as pr1_verification_problems
from src.storage.idempotency_store import IdempotencyVerdict


@dataclass(frozen=True)
class PreparedRuntime:
    """Factory-owned retained lanes; cleanup accepts only verified accepted items."""

    lanes: tuple
    provenance: RuntimeProvenance
    validation_policy_identity: str
    verify: Callable
    cleanup: Callable


class EvidenceSinkError(RuntimeError):
    def __init__(self, retained):
        super().__init__("PR4 evidence sink failed; raw cells retained")
        self.retained = retained


def verification_problems(observation, verification: VerificationEvidence) -> tuple[str, ...]:
    """Keep the accepted witness unchanged and require reliable refused absence."""
    if observation.capacity_refused_ns is None:
        return pr1_verification_problems(observation, verification)
    idem = verification.idempotency
    if (
        verification.status is LoadDurableStatus.ABSENT
        and verification.accepted_events == () and verification.request_event_count == 0
        and verification.identity_idempotency_count == 0
        and idem is not None and idem.verdict is IdempotencyVerdict.MISS
        and idem.signature is None and idem.accepted_event is None
    ):
        return ()
    return ("capacity_refusal_absence_unverified_or_violated",)


def _require_source(local):
    if (type(local) is not LocalProvenance or not isinstance(local.source_commit, str)
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", local.source_commit) is None
            or local.working_tree != "tracked_clean;untracked_not_inspected"):
        raise ValueError("explicit committed source and clean tracked tree required for comparison")


def _runtime_identity(runtime, plan, concurrency):
    """Validate topology and derive comparable facts, excluding per-cell PIDs."""
    facts = runtime.provenance
    connections = facts.connections
    if (len(connections) != concurrency + 1
            or {c.lane_id for c in connections} != {None, *range(concurrency)}
            or any(c.backend_pid is None for c in connections)
            or len({c.backend_pid for c in connections}) != concurrency + 1):
        raise ValueError("distinct N retained connections plus control required")
    environments = {(c.database, c.postgres_version, c.isolation, c.autocommit) for c in connections}
    if len(environments) != 1:
        raise ValueError("connection environments disagree")
    database, version, isolation, autocommit = next(iter(environments))
    if database != plan.test_database or version is None or not isolation or autocommit is not False:
        raise ValueError("runtime environment is unverified")
    composition = (facts.placement, facts.gate_identity, facts.validation_mode,
                   facts.runtime_identity, facts.validator_identity, runtime.validation_policy_identity)
    if not all(composition):
        raise ValueError("writer/validation composition must be explicit")
    return (database, version, isolation, autocommit, *composition)


def run_plan(plan, factory, *, clock_ns, source_provider, sink):
    """Execute only an explicitly authorized plan with an explicit resource factory.

The factory receives (plan, scheduled, workload, shared_admission). It must
inject that exact object across all lanes; unprotected receives None. Source
facts are sampled before/after every cell and compared across one run session.
Native/ambiguous/evidence failures stop later cells; normal refusals do not.
Cleanup follows verification of the whole cell and targets accepted items only.
No deadline, retries, adaptive order, replacement samples or success threshold.
"""
    if type(plan) is not ComparisonPlan:
        raise TypeError("ComparisonPlan required")
    plan.__post_init__()
    if not all(callable(value) for value in (factory, clock_ns, source_provider, sink)):
        raise TypeError("factory, clock, source provider and sink must be explicit")
    baseline = source_provider()
    _require_source(baseline)
    order = declared_cells(plan)
    retained = []
    environment = None
    for scheduled in order:
        before = None
        preparation_start = clock_ns()
        workload = prepare_workload(plan, scheduled)
        preparation_elapsed = clock_ns() - preparation_start
        cell = Characterization(scheduled.identity, scheduled.protection, workload, ())
        problems, harness_failures = [], ()
        facts = policy = after = None
        setup_elapsed = verification_elapsed = quiescent = None
        cleaned = False
        stage = "source"
        setup_start = clock_ns()
        try:
            before = source_provider()
            _require_source(before)
            if before != baseline:
                raise ValueError("source/local environment changed during run")
            admission = (ObservedAdmission(plan.protection_bound, clock_ns=clock_ns)
                         if scheduled.protection.mode is ProtectionMode.PROTECTED else None)
            stage = "setup"
            with factory(plan, scheduled, workload, admission) as runtime:
                setup_elapsed = clock_ns() - setup_start
                facts, policy = runtime.provenance, runtime.validation_policy_identity
                actual_environment = _runtime_identity(runtime, plan, scheduled.identity.configured_concurrency)
                if environment is not None and actual_environment != environment:
                    raise ValueError("A/B database or writer composition drift")
                environment = actual_environment
                stage = "execution"
                try:
                    cell = run_characterization(
                        scheduled.identity, scheduled.protection, workload, runtime.lanes,
                        admission=admission, clock_ns=clock_ns,
                    )
                except CharacterizationError as error:
                    cell, harness_failures = error.cell, error.failures
                    problems.append(RunProblem("execution", "harness_defect"))
                quiescent = clock_ns()
                stage = "verification"
                verification_start = clock_ns()
                verified = []
                for observation in cell.observations:
                    try:
                        verification = runtime.verify(observation.item)
                        if type(verification) is not VerificationEvidence:
                            raise TypeError("PR4 verification facts required")
                        issues = verification.problems + verification_problems(observation, verification)
                        if verification.failure is not None and not issues:
                            issues = ("verification_failure",)
                        verification = replace(verification, problems=issues)
                        if issues:
                            problems.append(RunProblem("verification", "correctness_unverified_or_mismatch"))
                    except Exception as error:
                        problems.append(_problem("verification", error))
                        verification = VerificationEvidence(
                            LoadDurableStatus.UNKNOWN, (), None, None, ("verification_unavailable",),
                        )
                    verified.append(replace(observation, verification=verification))
                cell = replace(cell, observations=tuple(verified))
                verification_elapsed = clock_ns() - verification_start
                counts = derive_accounting(cell)
                if counts.residual_workload_indices or any(
                    o.failure is not None or (o.capacity_refused_ns is None
                        and o.acknowledgement is not LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED)
                    for o in cell.observations
                ):
                    problems.append(RunProblem("execution", "incomplete_native_or_unexpected_outcome"))
                if scheduled.protection.mode is ProtectionMode.PROTECTED:
                    overlap = derive_overlap(cell, protected=True)
                    if overlap.maximum_complete_interval_overlap > plan.protection_bound:
                        problems.append(RunProblem("execution", "protected_overlap_exceeds_bound"))
                stage = "source"
                after = source_provider()
                if after != baseline:
                    problems.append(RunProblem("source", "source_or_local_environment_drift"))
                stage = "cleanup"
                if not problems:
                    accepted = tuple(o.item for o in cell.observations
                                     if o.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED)
                    if accepted:
                        runtime.cleanup(accepted)
                    cleaned = True  # Also true when verified absence requires no deletes.
                stage = "close"
        except Exception as error:
            if setup_elapsed is None:
                setup_elapsed = clock_ns() - setup_start
            problems.append(_problem(stage, error))
        evidence = CellEvidence(
            plan, scheduled, order, cell, before, after, facts, TOPOLOGY, OBSERVATION,
            policy, preparation_elapsed, setup_elapsed, verification_elapsed, quiescent,
            cleaned, tuple(problems), harness_failures,
        )
        retained.append(evidence)
        try:
            sink(evidence)
        except Exception:
            raise EvidenceSinkError(tuple(retained)) from None
        if evidence.incomplete:
            break
    return tuple(retained)
