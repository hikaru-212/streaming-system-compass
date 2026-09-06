"""Declared PR1 cells, resource ownership, and post-quiescence verification.

There is no CLI, automatic execution, connection default, sweep parameter
default, or capacity interpretation. Calling the PostgreSQL factory/cleanup
requires separately approved database scope. Injected resources support pure
tests of the same plan and evidence mechanics.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
import os
from pathlib import Path
import platform
from random import Random
import subprocess
from typing import ContextManager

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.evidence import (
    CellEvidence, Cohort, ConnectionFact, LoadRunPlan, LocalProvenance,
    RuntimeProvenance, RunProblem, VerificationEvidence, idempotency_evidence,
    project_observation,
)
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadCellIdentity, LoadCellObservation, LoadDurableStatus, LoadWorkItem,
)
from experiments.load_capacity_protection.postgres_characterization import (
    LoadHarnessError, LoadLaneCallable, _failure_evidence, run_characterization,
)
from experiments.load_capacity_protection.model import LoadOuterPhase
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from src.core.order.enums import CommandType, EventType
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.postgres_connection import connect_postgres
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


@dataclass(frozen=True)
class PreparedRuntime:
    """Already prepared resources; its factory context owns their eventual close."""

    lanes: tuple[LoadLaneCallable, ...]
    provenance: RuntimeProvenance
    verify: Callable[[LoadWorkItem], VerificationEvidence]
    cleanup: Callable[[], None]


RuntimeFactory = Callable[
    [LoadRunPlan, LoadCellIdentity, tuple[LoadWorkItem, ...]], ContextManager[PreparedRuntime]
]


def declared_cells(plan: LoadRunPlan) -> Iterator[tuple[Cohort, LoadCellIdentity]]:
    """Ordered levels, each with explicit warmups then explicit recorded repetitions."""
    for level_index, concurrency in enumerate(plan.concurrency_levels):
        for cohort, count in ((Cohort.WARMUP, plan.warmups), (Cohort.RECORDED, plan.repetitions)):
            for repetition in range(count):
                yield cohort, LoadCellIdentity(
                    plan.run_id, f"level-{level_index}-{cohort.value}", repetition, concurrency,
                )


def prepare_workload(plan: LoadRunPlan, identity: LoadCellIdentity) -> tuple[LoadWorkItem, ...]:
    """Deterministic, disjoint run/level/cohort/repetition identities; exactly K CREATEs.

The same index permutation is used for every cell, from the explicitly supplied
seed and Python Random.shuffle algorithm. Runtime/version provenance qualifies
that algorithm. No identities or extra work depend on outcomes.
"""
    if identity not in tuple(cell for _, cell in declared_cells(plan)):
        raise ValueError("cell is not in the declared plan")
    prefix = f"pr1-load:{plan.run_id}:{identity.cell_id}:{identity.repetition}"
    items = [LoadWorkItem(index, RequestSignature(
        f"{prefix}:request-{index}", CommandType.CREATE, f"{prefix}:order-{index}", plan.amount,
    )) for index in range(plan.k)]
    Random(plan.ordering_seed).shuffle(items)
    return tuple(items)


def collect_local_provenance(root: Path, *, clock_identity: str | None) -> LocalProvenance:
    """Read local software/hardware facts without hostname, DSN, or untracked scans.

Working-tree qualification covers tracked changes only, explicitly declaring
untracked files uninspected. The caller must qualify any relevant untracked
implementation separately; a source commit alone does not authenticate it.
"""
    def git(*args):
        try:
            result = subprocess.run(
                ("git", *args), cwd=root, capture_output=True, text=True, check=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=no")
    qualification = None if status is None else (
        ("tracked_modified" if status else "tracked_clean") + ";untracked_not_inspected"
    )
    return LocalProvenance(
        commit, qualification, platform.python_version(), psycopg.__version__,
        platform.system() or None, platform.machine() or None, os.cpu_count(), clock_identity,
    )


def _problem(stage: str, error: Exception) -> RunProblem:
    # Use the existing safe extractor, but do not invent per-request entry or
    # acknowledgement for a cell-level setup/verification/cleanup failure.
    safe = _failure_evidence(
        error, LoadOuterPhase.SCHEDULING, False, LoadAcknowledgement.UNKNOWN,
    )
    return RunProblem(stage, "exception", safe.exception_class, safe.sqlstate)


class EvidenceSinkError(RuntimeError):
    """Output failed after resources closed; immutable raw evidence remains accessible."""

    def __init__(self, retained: tuple[CellEvidence, ...]):
        super().__init__("evidence output failed; retain the attached raw cells")
        self.retained = retained


def verification_problems(observation, verification: VerificationEvidence) -> tuple[str, ...]:
    """Check only the existing independent-CREATE correctness witness semantics."""
    if verification.status is LoadDurableStatus.UNKNOWN:
        return ("verification_unknown",)
    if observation.acknowledgement is LoadAcknowledgement.UNKNOWN:
        return ()  # Reconciliation must not invent acknowledgement.
    if observation.acknowledgement is LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE:
        return () if (
            verification.status is LoadDurableStatus.ABSENT
            and verification.request_event_count == 0
            and verification.idempotency is not None
            and verification.idempotency.verdict is IdempotencyVerdict.MISS
        ) else ("unexpected_durable_effect",)
    events, signature = verification.accepted_events, observation.item.signature
    if len(events) != 1 or verification.request_event_count != 1:
        return ("accepted_effect_count_mismatch",)
    event = events[0]
    expected = observation.result.accepted_event
    if (
        event.event_type is not EventType.CREATED or event.sequence != 1
        or (event.request_id, event.order_id, event.amount) != (
            signature.request_id, signature.order_id, signature.amount,
        ) or event != expected
    ):
        return ("accepted_effect_identity_mismatch",)
    idem = verification.idempotency
    if idem is None or (
        idem.verdict is not IdempotencyVerdict.REPLAY
        or idem.signature != signature or idem.accepted_event != event
    ):
        return ("idempotency_mapping_mismatch",)
    return ()


def run_plan(
    plan: LoadRunPlan, factory: RuntimeFactory, *, clock_ns: Callable[[], int],
    local: LocalProvenance, sink: Callable[[CellEvidence], None],
) -> tuple[CellEvidence, ...]:
    """Run declared cells, preserving each cell after close and before proceeding.

All required configuration is validated before the factory can execute DB code.
Warmups are labeled records, never merged into the recorded cohort. An incomplete
cell, native writer failure, unexpected normal outcome, harness defect, unknown
verification, or cleanup/close failure stops the remaining plan without retries.
Verified successful cells alone use the explicitly declared scoped cleanup.
The sink owns persistence; a sink failure exposes all retained cells and stops.
The existing scheduler's non-cancellable wait-for-quiescence behavior is unchanged.
"""
    if type(plan) is not LoadRunPlan:
        raise TypeError("plan must be LoadRunPlan")
    plan.__post_init__()
    if type(local) is not LocalProvenance:
        raise TypeError("local provenance must be explicit, including unavailable fields")
    if not callable(factory) or not callable(clock_ns) or not callable(sink):
        raise TypeError("factory, clock, and sink must be supplied callables")
    retained = []
    for cohort, identity in declared_cells(plan):
        preparation_start = clock_ns()
        workload = prepare_workload(plan, identity)
        preparation_elapsed = clock_ns() - preparation_start
        cell = LoadCellObservation(identity, workload)
        raw = ()
        facts = None
        problems = []
        harness_failures = ()
        setup_elapsed = verification_elapsed = quiescent = None
        cleaned = False
        stage = "setup"
        setup_start = clock_ns()
        try:
            with factory(plan, identity, workload) as runtime:
                setup_elapsed = clock_ns() - setup_start
                facts = runtime.provenance
                if len(runtime.lanes) != identity.configured_concurrency:
                    raise ValueError("runtime lane count differs from declared concurrency")
                stage = "execution"
                try:
                    cell = run_characterization(identity, workload, runtime.lanes, clock_ns=clock_ns)
                except LoadHarnessError as error:
                    cell, harness_failures = error.cell, error.failures
                    problems.append(RunProblem("execution", "harness_defect"))
                quiescent = clock_ns()
                raw = tuple(project_observation(o) for o in cell.observations)
                stage = "verification"
                verification_start = clock_ns()
                verified = []
                for observation in raw:
                    try:
                        verification = runtime.verify(observation.item)
                        issues = verification.problems + verification_problems(observation, verification)
                        verification = replace(verification, problems=issues)
                        if issues:
                            problems.append(RunProblem("verification", "correctness_unverified_or_mismatch"))
                    except Exception as error:
                        problems.append(_problem("verification", error))
                        verification = VerificationEvidence(
                            LoadDurableStatus.UNKNOWN, (), None, None, ("verification_unavailable",),
                        )
                    verified.append(replace(observation, verification=verification))
                raw = tuple(verified)
                verification_elapsed = clock_ns() - verification_start
                if len(raw) != plan.k or any(
                    o.terminal_observation_ns is None
                    or o.acknowledgement is not LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
                    for o in raw
                ):
                    problems.append(RunProblem("execution", "incomplete_or_nonaccepted_cell"))
                stage = "cleanup"
                if not problems:
                    runtime.cleanup()
                    cleaned = True
                stage = "close"
        except Exception as error:
            if setup_elapsed is None:
                setup_elapsed = clock_ns() - setup_start
            problems.append(_problem(stage, error))
        evidence = CellEvidence(
            plan, identity, cohort, workload, raw, local, facts, preparation_elapsed,
            setup_elapsed, verification_elapsed, quiescent, cleaned, tuple(problems), harness_failures,
        )
        retained.append(evidence)
        try:
            sink(evidence)
        except Exception:
            raise EvidenceSinkError(tuple(retained)) from None
        if problems:
            break
    return tuple(retained)


class ReservedIdentitiesExist(RuntimeError):
    """Preflight refusal: never erase pre-existing rows to start a run."""


def _require_empty(control, workload: tuple[LoadWorkItem, ...]) -> None:
    request_ids = [item.signature.request_id for item in workload]
    order_ids = [item.signature.order_id for item in workload]
    with control.cursor() as cursor:
        for table in ("order_events", "idempotency_records"):
            cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE request_id = ANY(%s) OR order_id = ANY(%s)",
                (request_ids, order_ids),
            )
            if cursor.fetchone()[0] != 0:
                raise ReservedIdentitiesExist("reserved characterization identities already exist")
    control.rollback()


def cleanup_cell_rows(control, plan: LoadRunPlan, identity: LoadCellIdentity,
                      workload: tuple[LoadWorkItem, ...]) -> None:
    """Separately callable MUTATION: delete exact declared request/order pairs only.

Requires approval and quiescence. No pre-run deletion, TRUNCATE, CASCADE, sequence
reset, DecisionReceipt or projection cleanup. The runner calls this only after
full successful verification; uncertain or failed cells retain rows for review.
"""
    plan.__post_init__()
    if workload != prepare_workload(plan, identity):
        raise ValueError("cleanup identities differ from declared workload")
    if control.autocommit:
        raise ValueError("cleanup requires autocommit disabled")
    control.rollback()
    with control.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != plan.test_database:
            raise ValueError("cleanup connection differs from declared test database")
    control.rollback()
    with control.transaction():
        with control.cursor() as cursor:
            for table in ("idempotency_records", "order_events"):
                for item in workload:
                    cursor.execute(
                        f"DELETE FROM {table} WHERE request_id = %s AND order_id = %s",
                        (item.signature.request_id, item.signature.order_id),
                    )
    _require_empty(control, workload)


@contextmanager
def postgres_runtime(
    plan: LoadRunPlan, identity: LoadCellIdentity, workload: tuple[LoadWorkItem, ...],
) -> Iterator[PreparedRuntime]:
    """Real guarded factory, invoked only by a separately authorized live caller.

Use explicit TEST_DATABASE_URL only. Validate its declared database before
opening anything, then guard every actual connection. The control connection
is shared sequentially for preflight, verification and scoped cleanup; it is
never a writer lane. Setup failure closes every resource opened so far.
"""
    plan.__post_init__()
    if workload != prepare_workload(plan, identity):
        raise ValueError("runtime workload differs from declaration")
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise ValueError("TEST_DATABASE_URL is required")
    if conninfo_to_dict(database_url).get("dbname") != plan.test_database:
        raise ValueError("TEST_DATABASE_URL does not name the declared test database")
    facts = []
    with ExitStack() as resources:
        def connect(lane_id):
            connection = connect_postgres(
                database_url, connect_timeout_seconds=plan.connect_timeout_seconds,
            )
            resources.callback(connection.close)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_setting('transaction_isolation')")
                database, isolation = cursor.fetchone()
            if database != plan.test_database or not database.endswith("_test"):
                raise ValueError("connected database differs from declared test database")
            if connection.autocommit:
                raise ValueError("retained connections must have autocommit disabled")
            connection.rollback()
            if connection.info.transaction_status is not TransactionStatus.IDLE:
                raise ValueError("guard did not restore idle connection")
            facts.append(ConnectionFact(
                lane_id, database, connection.info.server_version, connection.info.backend_pid,
                isolation, connection.autocommit,
            ))
            return connection

        control = connect(None)
        _require_empty(control, workload)
        lanes = tuple(PostgresLoadLane(index, connect(index))
                      for index in range(identity.configured_concurrency))
        if len({fact.backend_pid for fact in facts}) != identity.configured_concurrency + 1:
            raise ValueError("runtime connections are not distinct")

        def verify(item):
            # A new read transaction after quiescence, including after any failed
            # previous verification. Partial reads survive a later read failure.
            control.rollback()
            history = ()
            decision = None
            count = None
            try:
                history = tuple(PostgresEventStore(control).load(item.signature.order_id))
                decision = idempotency_evidence(PostgresIdempotencyStore(control).check(item.signature))
                with control.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM order_events WHERE request_id = %s",
                                   (item.signature.request_id,))
                    count = cursor.fetchone()[0]
                status = LoadDurableStatus.PRESENT if history or count else LoadDurableStatus.ABSENT
                return VerificationEvidence(status, history, decision, count, ())
            except Exception as error:
                return VerificationEvidence(
                    LoadDurableStatus.UNKNOWN, history, decision, count, ("verification_unavailable",),
                    _problem("verification", error),
                )

        provenance = RuntimeProvenance(
            tuple(facts), lanes[0].config.validation_placement.value,
            "src.pipeline.transactional.postgres_admission.PostgresOptimisticAdmissionGate",
            lanes[0].validation_runtime.mode.value,
            f"{type(lanes[0].validation_runtime).__module__}.{type(lanes[0].validation_runtime).__name__}",
            f"{type(lanes[0].validation_runtime.dispatcher.strict_validator).__module__}."
            f"{type(lanes[0].validation_runtime.dispatcher.strict_validator).__name__}",
        )
        yield PreparedRuntime(lanes, provenance, verify,
                              lambda: cleanup_cell_rows(control, plan, identity, workload))
