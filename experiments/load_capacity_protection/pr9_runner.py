"""Same-source paired PR9 runner. No live CLI or selected matrix is supplied."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import platform
import re
import subprocess
from threading import Barrier, Event
from time import monotonic_ns, sleep

import psycopg

from experiments.load_capacity_protection.pr9_characterization import request_problems, summarize
from experiments.load_capacity_protection.pr9_model import (
    COMPOSITION, CellEvidence, DurableEvidence, RunEvidence, Source, UnobservedRequestEvidence, schedule, workload,
)
from experiments.load_capacity_protection.pr9_postgres_runtime import postgres_runtime
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityObserver


REQUIRED_PATHS = (
    "src/pipeline/transactional/writer_capacity.py", "src/pipeline/postgres_writer_request.py",
    "src/bootstrap/build_postgres_writer_request.py", "src/pipeline/writer_retry_policy.py",
    "src/pipeline/transactional/postgres_write_side.py",
    *(f"experiments/load_capacity_protection/pr9_{name}.py" for name in
      ("model", "evidence", "characterization", "postgres_runtime", "runner")),
)


def collect_source(root: Path):
    """Require committed machinery and clean tracked source; never enumerate scripts.

    No untracked inventory, environment values, remote operation or secret file
    read is performed. HEAD alone cannot qualify uncommitted experiment code.
    """
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    head = git("rev-parse", "HEAD")
    if head.returncode:
        raise ValueError("source revision unavailable")
    clean = git("diff", "--quiet", "HEAD", "--").returncode == 0
    committed = git("ls-files", "--error-unmatch", "--", *REQUIRED_PATHS).returncode == 0
    # ls-files also sees newly staged files; require every path in HEAD itself.
    committed = committed and all(git("cat-file", "-e", f"HEAD:{path}").returncode == 0 for path in REQUIRED_PATHS)
    return Source(head.stdout.strip(), clean, committed, platform.python_version(), psycopg.__version__,
                  f"{platform.system()} {platform.release()} {platform.machine()}",
                  "monotonic_ns; production retry seconds=ns/1e9")


def require_source(source):
    if (type(source) is not Source or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source.commit)
            or source.tracked_clean is not True or source.machinery_committed is not True):
        raise ValueError("same-source run requires clean committed production and PR9 machinery")


def topology(runtime, plan, cell):
    facts = runtime.connections
    if (len(runtime.lanes) != cell.concurrency or len(facts) != cell.concurrency + 1
            or {f.lane_id for f in facts} != {None, *range(cell.concurrency)}
            or len({f.connection_id for f in facts}) != len(facts)
            or len({f.backend_pid for f in facts}) != len(facts)
            or any(f.database != plan.test_database or f.autocommit for f in facts)):
        raise ValueError("retained topology mismatch")
    for lane in runtime.lanes:
        if not any(f.lane_id == lane.lane_id and f.connection_id == id(lane.connection) for f in facts):
            raise ValueError("lane connection evidence mismatch")
    return tuple((f.lane_id, f.database, f.server_version, f.isolation, f.autocommit) for f in facts)


def run_pairs(plan, *, root, sink, runtime_factory=postgres_runtime, source_provider=None,
              clock_ns=monotonic_ns, wait=sleep):
    """Run adjacent A/B cells only after a separately approved explicit live plan.

    Fixed finite work is assigned index modulo N, identically in both conditions.
    Each lane invokes once per logical item; production owns all retry decisions.
    Unexpected execution/evidence stops later claims and cells; active work drains
    without a deadline. Verification runs after drain. The sink receives an
    immutable cumulative raw snapshot after each cell, including invalid cells.
    No database setup, deletion or automatic live approval is implied by this API.
    """
    source_provider = source_provider or (lambda: collect_source(root))
    initial = source_provider()
    require_source(initial)
    cells, run_problems, pair_topology = [], [], {}
    for cell in schedule(plan):
        try:
            before = source_provider()
        except Exception as error:
            run_problems.append(f"source_unavailable_before_cell:{type(error).__name__}")
            break
        if before != initial:
            run_problems.append("source_changed_before_cell")
            break
        signatures = workload(plan, cell)
        gate = BoundedWriterAdmission(plan.capacity_bound)
        policy = plan.retry_policy if cell.enabled else None
        requests, unobserved, problems, runtime = [], [], [], None
        try:
            with runtime_factory(plan, cell, signatures, clock_ns) as runtime:
                identity = topology(runtime, plan, cell)
                pair = (cell.cohort, cell.pair_index, cell.concurrency)
                if pair in pair_topology and pair_topology[pair] != identity:
                    raise ValueError("paired fixture or topology drift")
                pair_topology[pair] = identity
                stop, start, ready = Event(), Event(), Barrier(cell.concurrency + 1)
                offered = None

                def lane_work(lane):
                    observations = []
                    failures = []
                    ready.wait()
                    start.wait()
                    for index in range(lane.lane_id, len(signatures), cell.concurrency):
                        if stop.is_set():
                            break
                        try:
                            observer = WriterCapacityObserver(clock_ns=clock_ns)
                            request = lane.invoke(index, signatures[index], offered, gate=gate, observer=observer,
                                                  policy=policy, clock_ns=clock_ns, wait=wait)
                        except BaseException as error:
                            failures.append(f"lane_failure:{type(error).__name__}")
                            stop.set()
                            break
                        observations.append(request)
                        if request_problems(request, policy):
                            stop.set()
                    return observations, failures

                with ThreadPoolExecutor(max_workers=cell.concurrency) as executor:
                    try:
                        futures = [executor.submit(lane_work, lane) for lane in runtime.lanes]
                        ready.wait()
                        offered = clock_ns()
                        start.set()
                    except BaseException:
                        stop.set()
                        ready.abort()
                        start.set()
                        raise
                    for future in futures:
                        try:
                            observations, failures = future.result()
                            requests.extend(observations)
                            problems.extend(failures)
                        except BaseException as error:
                            stop.set()
                            problems.append(f"lane_failure:{type(error).__name__}")
                requests.sort(key=lambda r: r.index)
                verified = []
                for request in requests:
                    try:
                        durable = runtime.verify(request.signature)
                    except Exception as error:
                        durable = DurableEvidence((), None, None, None, None, None, type(error).__name__)
                    request = replace(request, durable=durable)
                    problems.extend(request_problems(request, policy))
                    verified.append(request)
                requests = verified
                for index, signature in enumerate(signatures):
                    if any(r.index == index for r in requests):
                        continue
                    try:
                        durable = runtime.verify(signature)
                    except Exception as error:
                        durable = DurableEvidence((), None, None, None, None, None, type(error).__name__)
                    unobserved.append(UnobservedRequestEvidence(index, signature, durable))
        except Exception as error:
            problems.append(f"runtime_failure:{type(error).__name__}")
        try:
            after = source_provider()
        except Exception as error:
            after = None
            problems.append(f"source_unavailable_after_cell:{type(error).__name__}")
        if after != before:
            problems.append("source_changed_during_cell")
        if len(requests) != plan.logical_requests:
            problems.append("logical_cohort_incomplete")
        events = [r.result.accepted_event.event_id for r in requests
                  if r.result and r.result.accepted_event is not None]
        if len(events) != len(set(events)):
            problems.append("duplicate_accepted_event_identity")
        facts = tuple(runtime.connections) if runtime is not None else ()
        if any(f.opened_ns is None or f.closed_ns is None or f.close_failure is not None for f in facts):
            problems.append("connection_retention_incomplete")
        for index, signature in enumerate(signatures):
            if not any(r.index == index for r in (*requests, *unobserved)):
                unobserved.append(UnobservedRequestEvidence(index, signature,
                    DurableEvidence((), None, None, None, None, None, "verification_not_reached")))
        evidence = CellEvidence(plan, cell, before, after, COMPOSITION, facts, tuple(requests),
                                tuple(dict.fromkeys(problems)), tuple(unobserved))
        overlap = summarize(evidence)["protected_writer_overlap"]
        if overlap is not None and overlap > plan.capacity_bound:
            evidence = replace(evidence, problems=(*evidence.problems, "writer_bound_exceeded"))
        cells.append(evidence)
        if evidence.problems:
            run_problems.append("invalid_cell_stopped_later_cells")
        snapshot = RunEvidence(plan, tuple(cells), tuple(run_problems))
        try:
            sink(snapshot)
        except Exception as error:
            run_problems.append(f"evidence_sink_failure:{type(error).__name__}")
        if run_problems:
            break
    return RunEvidence(plan, tuple(cells), tuple(run_problems))
