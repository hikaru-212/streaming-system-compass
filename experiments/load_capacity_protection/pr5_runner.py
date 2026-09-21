"""Explicit PR5 session ownership: provenance, quiescence, verification and output."""

from dataclasses import replace

from experiments.load_capacity_protection.evidence import RunProblem
from experiments.load_capacity_protection.model import LoadDurableStatus
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission
from experiments.load_capacity_protection.pr4_model import Protection, ProtectionMode, VerificationEvidence, derive_overlap
from experiments.load_capacity_protection.pr4_runner import (
    PreparedRuntime, _require_source, _runtime_identity, verification_problems as pr4_verification_problems,
)
from experiments.load_capacity_protection.pr5_characterization import CharacterizationError, run_characterization
from experiments.load_capacity_protection.pr5_evidence import CellEvidence, OBSERVATION, TOPOLOGY
from experiments.load_capacity_protection.pr5_model import (
    LogicalTerminal, RetryPlan, declared_cells, empty_characterization, prepare_workload,
)
from experiments.load_capacity_protection.runner import _problem


class EvidenceSinkError(RuntimeError):
    def __init__(self, retained):
        super().__init__("PR5 evidence sink failed; raw cells retained")
        self.retained = retained


def verification_problems(request, verification):
    """Verify the final logical effect; earlier pre-body refusals wrote nothing.

Accepted work needs one exact CREATED event and exactly one raw idempotency row
matching request OR order. Refusal-only exhaustion needs reliable absence in
both stores. Native/ambiguous failures retain separate durable reconciliation,
never retrospective acknowledgement. No retry decision follows verification.
"""
    if not request.attempts:
        return ("unattempted_logical_request",)
    row = request.attempts[-1].observation
    issues = pr4_verification_problems(row, verification)
    if request.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED and (
        verification.status is not LoadDurableStatus.PRESENT or verification.identity_idempotency_count != 1
    ):
        issues += ("accepted_idempotency_count_or_presence_mismatch",)
    return issues


def run_plan(plan, factory, *, clock_ns, wait_until, source_provider, sink):
    """Run an explicitly approved plan; definition/import alone authorizes no I/O.

All lanes in each cell receive the same real gate. Stop later cells on native,
ambiguous, harness, verification, source, cleanup or close failures. Normal
capacity refusal and exhausted experiment budgets permit continuation. Only
fully verified cells may clean exact accepted identities after quiescence.
The explicit sink runs after resource closure; sink failure retains raw cells.
"""
    if type(plan) is not RetryPlan:
        raise TypeError("RetryPlan required")
    plan.__post_init__()
    if not all(callable(v) for v in (factory, clock_ns, wait_until, source_provider, sink)):
        raise TypeError("explicit factory, clock, waiter, source provider and sink required")
    baseline = source_provider()
    _require_source(baseline)
    if not all((baseline.python_version, baseline.psycopg_version, baseline.platform_system,
                baseline.machine, baseline.clock_identity)) or type(baseline.logical_cpus) is not int or baseline.logical_cpus < 1:
        raise ValueError("complete sanitized local provenance required")
    order = declared_cells(plan)
    retained, environment = [], None
    for scheduled in order:
        before = after = facts = policy = None
        start = clock_ns()
        workload = prepare_workload(plan, scheduled)
        preparation_elapsed = clock_ns() - start
        protection = Protection(ProtectionMode.PROTECTED, plan.protection_bound)
        cell = empty_characterization(scheduled.identity, protection, scheduled.retry, workload)
        problems, harness_failures = [], ()
        setup_elapsed = verification_elapsed = quiescent = None
        cleaned = False
        stage = "source"
        setup_start = clock_ns()
        try:
            before = source_provider()
            _require_source(before)
            if before != baseline:
                raise ValueError("source/local environment changed")
            admission = ObservedAdmission(plan.protection_bound, clock_ns=clock_ns)
            stage = "setup"
            with factory(plan, scheduled, workload, admission) as runtime:
                setup_elapsed = clock_ns() - setup_start
                facts, policy = runtime.provenance, runtime.validation_policy_identity
                actual = _runtime_identity(runtime, plan, scheduled.identity.configured_concurrency)
                if environment is not None and actual != environment:
                    raise ValueError("database or writer composition drift")
                environment = actual
                stage = "execution"
                try:
                    cell = run_characterization(scheduled.identity, protection, scheduled.retry, workload,
                                                runtime.lanes, admission=admission, clock_ns=clock_ns,
                                                wait_until=wait_until)
                except CharacterizationError as error:
                    cell, harness_failures = error.cell, error.failures
                    problems.append(RunProblem("execution", "harness_defect"))
                quiescent = clock_ns()
                stage = "verification"
                verification_start = clock_ns()
                verified = []
                for request in cell.logical_requests:
                    try:
                        verification = runtime.verify(request.item)
                        if type(verification) is not VerificationEvidence:
                            raise TypeError("exact durable verification facts required")
                        issues = verification.problems + verification_problems(request, verification)
                        if verification.failure is not None and not issues:
                            issues = ("verification_failure",)
                        verification = replace(verification, problems=issues)
                        if issues:
                            problems.append(RunProblem("verification", "correctness_unverified_or_mismatch"))
                    except Exception as error:
                        problems.append(_problem("verification", error))
                        verification = VerificationEvidence(LoadDurableStatus.UNKNOWN, (), None, None,
                                                            ("verification_unavailable",))
                    verified.append(replace(request, verification=verification))
                cell = replace(cell, logical_requests=tuple(verified))
                verification_elapsed = clock_ns() - verification_start
                if any(r.terminal_state not in (
                    LogicalTerminal.ACKNOWLEDGED_ACCEPTED,
                    LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL,
                ) for r in cell.logical_requests):
                    problems.append(RunProblem("execution", "incomplete_native_or_unexpected_outcome"))
                if derive_overlap(cell, protected=True).maximum_complete_interval_overlap > plan.protection_bound:
                    problems.append(RunProblem("execution", "protected_overlap_exceeds_bound"))
                stage = "source"
                after = source_provider()
                if after != baseline:
                    problems.append(RunProblem("source", "source_or_local_environment_drift"))
                stage = "cleanup"
                if not problems:
                    accepted = tuple(r.item for r in cell.logical_requests
                                     if r.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED)
                    if accepted:
                        runtime.cleanup(accepted)
                    cleaned = True
                stage = "close"
        except Exception as error:
            if setup_elapsed is None:
                setup_elapsed = clock_ns() - setup_start
            problems.append(_problem(stage, error))
        evidence = CellEvidence(plan, scheduled, order, cell, before, after, facts, TOPOLOGY, OBSERVATION,
                                policy, preparation_elapsed, setup_elapsed, verification_elapsed, quiescent,
                                cleaned, tuple(problems), harness_failures)
        retained.append(evidence)
        try:
            sink(evidence)
        except Exception:
            raise EvidenceSinkError(tuple(retained)) from None
        if evidence.incomplete:
            break
    return tuple(retained)
