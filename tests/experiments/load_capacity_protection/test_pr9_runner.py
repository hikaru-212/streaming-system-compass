"""Paired orchestration with the real builder, owner, concrete gate and measured API."""

from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest

from experiments.load_capacity_protection import pr9_characterization as adapter
from experiments.load_capacity_protection.pr9_characterization import ProductionLane, summarize
from experiments.load_capacity_protection.pr9_model import ConnectionEvidence, Plan, Source, schedule, workload
from experiments.load_capacity_protection.pr9_postgres_runtime import PreparedRuntime
from experiments.load_capacity_protection.pr9_runner import collect_source, require_source, run_pairs
from src.pipeline.transactional.postgres_write_side import PostgresTransactionalWriteSide
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission
from src.storage.idempotency_store import RequestSignature
from tests.experiments.load_capacity_protection.test_pr9_characterization import Clock, connection, accepted_durable, absent
from tests.unit.pipeline.test_postgres_writer_request import POLICY, _accepted_result


SOURCE = Source("a" * 40, True, True, "test-python", "test-psycopg", "test-platform", "test-clock")


def plan(**changes):
    # Values belong solely to deterministic tests, never a live matrix/example.
    return replace(Plan(UUID(int=99), 2, (2,), 1, POLICY, 0, 1, Decimal("2.00"),
                        "pr9_fixture_test", 3, 2, "stop_claims_and_drain_without_deadline", "retain_rows"), **changes)


def paired_fixture(monkeypatch):
    clock, active, builds = Clock(), {}, []
    original_invoke, original_build = ProductionLane.invoke, adapter.build_postgres_writer_request

    def builder(**kwargs):
        builds.append(kwargs)
        assert type(kwargs["capacity_admission"]) is BoundedWriterAdmission
        return original_build(**kwargs)
    monkeypatch.setattr(adapter, "build_postgres_writer_request", builder)

    def invoke(lane, *args, **kwargs):
        if lane.lane_id == 1:
            assert active["entered"].wait(5)
        try:
            return original_invoke(lane, *args, **kwargs)
        finally:
            if lane.lane_id == 0:
                active["returned"].set()
            elif not active["enabled"]:
                active["release"].set()
    monkeypatch.setattr(ProductionLane, "invoke", invoke)

    def body(writer, **kwargs):
        if writer._connection.lane_id == 0:
            active["entered"].set()
            assert active["release"].wait(5)
        signature = RequestSignature(**{k: kwargs[k] for k in ("request_id", "command_type", "order_id", "amount")})
        result = _accepted_result(signature)
        assert signature.request_id not in active["effects"]
        active["effects"][signature.request_id] = result.accepted_event
        return result
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)

    def wait(delay):
        active["release"].set()
        assert active["returned"].wait(5)
        clock.wait(delay)

    @contextmanager
    def runtime(p, cell, signatures, clock_ns):
        active.update(enabled=cell.enabled, entered=Event(), release=Event(), returned=Event(), effects={})
        conns = [connection() for _ in range(cell.concurrency + 1)]
        facts, lanes = [], []
        for index, conn in enumerate(conns):
            lane_id = index if index < cell.concurrency else None
            conn.lane_id = lane_id
            facts.append(ConnectionEvidence(lane_id, id(conn), index + 101, p.test_database,
                                             170000, "read committed", False, clock.read()))
            if lane_id is not None:
                lanes.append(ProductionLane(lane_id, conn))
        def verify(signature):
            event = active["effects"].get(signature.request_id)
            return accepted_durable(signature, event) if event else absent()
        try:
            yield PreparedRuntime(tuple(lanes), facts, verify)
        finally:
            active["release"].set()
            for index, conn in enumerate(conns):
                conn.closed = True
                facts[index] = replace(facts[index], closed_ns=clock.read())
    return clock, runtime, wait, builds


def run_fixture(monkeypatch, *, declaration=None, source_provider=lambda: SOURCE, sink=None):
    clock, runtime, wait, builds = paired_fixture(monkeypatch)
    snapshots = []
    evidence = run_pairs(declaration or plan(), root=Path.cwd(), sink=sink or snapshots.append,
                         runtime_factory=runtime, source_provider=source_provider, clock_ns=clock.read, wait=wait)
    return evidence, snapshots, builds


def test_same_source_ab_real_production_path_and_retained_resource_accounting(monkeypatch):
    evidence, snapshots, builds = run_fixture(monkeypatch)
    assert evidence.problems == ()
    assert len(evidence.cells) == len(snapshots) == 2
    disabled, enabled = evidence.cells
    assert disabled.problems == enabled.problems == ()
    a, b = summarize(disabled), summarize(enabled)
    assert (a["logical_requests"], a["attempts"], a["acknowledged_accepted"]) == (2, 2, 1)
    assert (b["logical_requests"], b["attempts"], b["acknowledged_accepted"]) == (2, 3, 2)
    assert b["attempt_amplification"] == 1.5 and b["completion_proportion"] == 1
    assert b["retry_attempts"] == b["accepted_after_retry"] == 1
    assert a["protected_writer_overlap"] == b["protected_writer_overlap"] == 1
    assert b["waiting_logical_peak"] == b["waiting_retained_connections_peak"] == 1
    assert b["waiting_retained_connection_ns"] > 0
    assert a["retained_connections"] == b["retained_connections"] == 3
    assert b["completion_throughput_per_second"] > 0
    assert b["body_latency_ns"] and b["phase_samples"]
    assert all(item["measure_writer"] is True and item["capacity_observer"] is not None for item in builds)
    assert [item["retry_policy"] is None for item in builds] == [True, True, False, False]
    assert all(c.before == c.after == SOURCE for c in evidence.cells)
    assert all(r.durable is not None for c in evidence.cells for r in c.requests)


def test_warmups_recorded_pairs_counterbalance_and_identities_stay_separate(monkeypatch):
    declaration = plan(warmup_pairs=1, recorded_pairs=2)
    cells = schedule(declaration)
    assert [c.enabled for c in cells] == [False, True, False, True, True, False]
    assert [c.cohort for c in cells] == ["warmup"] * 2 + ["recorded"] * 4
    signatures = [s for c in cells for s in workload(declaration, c)]
    assert len({s.request_id for s in signatures}) == len(signatures)
    assert len({s.order_id for s in signatures}) == len(signatures)
    evidence, _, _ = run_fixture(monkeypatch, declaration=declaration)
    assert evidence.problems == () and len(evidence.cells) == 6
    assert all(len(c.requests) == 2 for c in evidence.cells)


@pytest.mark.parametrize("source", [replace(SOURCE, commit="unknown"), replace(SOURCE, tracked_clean=False),
                                    replace(SOURCE, machinery_committed=False)])
def test_source_qualification_rejects_uncommitted_machinery_before_runtime(source):
    with pytest.raises(ValueError):
        require_source(source)
    with pytest.raises(ValueError):
        run_pairs(plan(), root=Path.cwd(), sink=lambda x: None, source_provider=lambda: source,
                  runtime_factory=lambda *a: pytest.fail("must not open runtime"))


def test_source_drift_preserves_invalid_cell_and_stops_pair(monkeypatch):
    sources = iter([SOURCE, SOURCE, replace(SOURCE, commit="b" * 40)])
    evidence, snapshots, _ = run_fixture(monkeypatch, source_provider=lambda: next(sources))
    assert len(evidence.cells) == 1 and evidence.problems
    assert "source_changed_during_cell" in evidence.cells[0].problems
    assert snapshots[-1] == evidence


def test_source_guard_checks_head_membership_and_never_enumerates_untracked(monkeypatch):
    calls = []
    def git(args, **kwargs):
        calls.append(args)
        code = 1 if args[1] == "cat-file" and args[-1].endswith("pr9_runner.py") else 0
        from types import SimpleNamespace
        return SimpleNamespace(returncode=code, stdout="a" * 40)
    monkeypatch.setattr("experiments.load_capacity_protection.pr9_runner.subprocess.run", git)
    assert collect_source(Path.cwd()).machinery_committed is False
    assert not any("status" in args or "--others" in args or "scripts/" in args for args in calls)


def test_sink_failure_stops_after_draining_and_retains_raw_evidence(monkeypatch):
    def sink(value):
        raise ValueError("sink unavailable")
    evidence, _, _ = run_fixture(monkeypatch, sink=sink)
    assert len(evidence.cells) == 1
    assert evidence.problems == ("evidence_sink_failure:ValueError",)
    assert all(c.closed_ns is not None for c in evidence.cells[0].connections)


def test_later_lane_failure_preserves_prior_records_and_verifies_every_offered_identity(monkeypatch):
    clock, runtime, wait, _ = paired_fixture(monkeypatch)
    original = ProductionLane.invoke
    def fail_later(lane, index, *args, **kwargs):
        if index == 2:
            raise ValueError("test instrumentation failure before invocation record")
        return original(lane, index, *args, **kwargs)
    monkeypatch.setattr(ProductionLane, "invoke", fail_later)
    evidence = run_pairs(plan(logical_requests=4), root=Path.cwd(), sink=lambda x: None,
                         runtime_factory=runtime, source_provider=lambda: SOURCE, clock_ns=clock.read, wait=wait)
    assert len(evidence.cells) == 1 and evidence.problems
    cell, = evidence.cells
    assert {0, 1}.issubset({r.index for r in cell.requests})
    assert 2 in {r.index for r in cell.unobserved}
    assert {r.index for r in (*cell.requests, *cell.unobserved)} == set(range(4))
    assert all(r.durable is not None and r.durable.failure is None for r in (*cell.requests, *cell.unobserved))
    assert not summarize(cell)["valid"]


def test_unavailable_post_cell_source_is_missing_not_fabricated(monkeypatch):
    calls = []
    def source():
        calls.append(1)
        if len(calls) == 3:
            raise ValueError("source unavailable")
        return SOURCE
    evidence, _, _ = run_fixture(monkeypatch, source_provider=source)
    assert len(evidence.cells) == 1 and evidence.cells[0].after is None
    assert "source_unavailable_after_cell:ValueError" in evidence.cells[0].problems


def test_runtime_drift_invalidates_enabled_pair_before_dispatch(monkeypatch):
    clock, original_runtime, wait, builds = paired_fixture(monkeypatch)
    @contextmanager
    def drift(p, cell, signatures, clock_ns):
        with original_runtime(p, cell, signatures, clock_ns) as runtime:
            if cell.enabled:
                runtime.connections[:] = [replace(f, server_version=999) for f in runtime.connections]
            yield runtime
    evidence = run_pairs(plan(), root=Path.cwd(), sink=lambda x: None, runtime_factory=drift,
                         source_provider=lambda: SOURCE, clock_ns=clock.read, wait=wait)
    assert len(evidence.cells) == 2 and evidence.problems
    assert len(builds) == 2
    assert "runtime_failure:ValueError" in evidence.cells[-1].problems


@pytest.mark.parametrize("changes", [{"capacity_bound": 0}, {"connection_budget": 2},
                                    {"concurrency_levels": (2, 2)}, {"retention_policy": "delete"},
                                    {"warmup_pairs": -1}, {"logical_requests": True}])
def test_explicit_plan_validation(changes):
    with pytest.raises((TypeError, ValueError)):
        plan(**changes)


def test_experiment_has_no_alternate_retry_scheduler_or_stage4e_path():
    root = Path(__file__).parents[3]
    sources = [(root / "experiments/load_capacity_protection" / f"pr9_{name}.py").read_text()
               for name in ("characterization", "runner", "postgres_runtime")]
    import ast
    imports = [node.module or "" for source in sources for node in ast.walk(ast.parse(source))
               if isinstance(node, ast.ImportFrom)]
    assert not any(any(term in name for term in ("pr5", "pr4", "reinvocation", "rate_limiter", "queue", "asyncio", "random"))
                   for name in imports)
    assert sources[0].count("owner.invoke()") == 1
    assert "while" not in {node.__class__.__name__.lower() for source in sources for node in ast.walk(ast.parse(source))}
