"""Declared runner schedules using fake resources only; no database execution."""

from contextlib import contextmanager
from threading import Lock
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.evidence import (
    Cohort, IdempotencyEvidence, LoadRunPlan, RuntimeProvenance, VerificationEvidence,
    dumps_evidence, loads_evidence,
)
from experiments.load_capacity_protection.model import LoadAcknowledgement, LoadDurableStatus
from experiments.load_capacity_protection.runner import (
    EvidenceSinkError, PreparedRuntime, ReservedIdentitiesExist, cleanup_cell_rows,
    declared_cells, postgres_runtime, prepare_workload, run_plan,
)
from experiments.load_capacity_protection import runner
from src.storage.idempotency_store import IdempotencyVerdict
from tests.experiments.load_capacity_protection.test_evidence import local, plan
from tests.experiments.load_capacity_protection.test_postgres_characterization import (
    CountingClock, FakeWriterFailure, result_for,
)


class FakeFactory:
    def __init__(self, *, fail_writer=False, fail_setup=False, fail_verify=False,
                 mismatch=False, fail_cleanup=False, fail_close=False):
        self.fail_writer = fail_writer
        self.fail_setup = fail_setup
        self.fail_verify = fail_verify
        self.mismatch = mismatch
        self.fail_cleanup = fail_cleanup
        self.fail_close = fail_close
        self.cells = []
        self.calls = []
        self.cleaned = []
        self.closed = []
        self.running = 0
        self.lock = Lock()

    @contextmanager
    def __call__(self, declaration, identity, workload):
        self.cells.append((identity, workload))
        if self.fail_setup:
            raise RuntimeError("private setup error text")
        durable = {}

        def make_lane():
            def invoke(item):
                with self.lock:
                    self.running += 1
                try:
                    self.calls.append(item)
                    result = result_for(item)
                    durable[item.signature.request_id] = result.accepted_event
                    if self.fail_writer:
                        raise FakeWriterFailure()
                    return result
                finally:
                    with self.lock:
                        self.running -= 1
            return invoke

        def verify(item):
            assert self.running == 0
            if self.fail_verify:
                raise RuntimeError("private verification error")
            event = durable.get(item.signature.request_id)
            if event is None or self.mismatch:
                return VerificationEvidence(
                    LoadDurableStatus.ABSENT, (), IdempotencyEvidence(IdempotencyVerdict.MISS, None, None),
                    0, (),
                )
            return VerificationEvidence(
                LoadDurableStatus.PRESENT, (event,),
                IdempotencyEvidence(IdempotencyVerdict.REPLAY, item.signature, event), 1, (),
            )

        def cleanup():
            assert self.running == 0
            if self.fail_cleanup:
                raise RuntimeError("private cleanup error")
            self.cleaned.append(identity)

        try:
            yield PreparedRuntime(
                tuple(make_lane() for _ in range(identity.configured_concurrency)),
                RuntimeProvenance((), None, None, None, None, None), verify, cleanup,
            )
        finally:
            assert self.running == 0
            self.closed.append(identity)
            if self.fail_close:
                raise RuntimeError("private close error")


def execute(declaration, factory):
    exported = []

    def sink(cell):
        assert not factory.running
        assert factory.closed or factory.fail_setup
        exported.append(loads_evidence(dumps_evidence(cell)))

    cells = run_plan(declaration, factory, clock_ns=CountingClock(), local=local(), sink=sink)
    assert tuple(exported) == cells
    return cells


def test_required_inputs_have_no_hidden_execution_defaults():
    with pytest.raises(TypeError):
        LoadRunPlan(run_id="missing-inputs")
    declaration = plan(k=5, concurrency_levels=(3, 1), connection_budget=4)
    assert declaration.k == 5
    assert declaration.required_connections == 4
    for _, identity in declared_cells(declaration):
        assert len(prepare_workload(declaration, identity)) == 5


@pytest.mark.parametrize("changes", [
    {"k": 0}, {"concurrency_levels": ()}, {"concurrency_levels": (True,)},
    {"concurrency_levels": (2, 2)}, {"warmups": -1}, {"repetitions": 0},
    {"connection_budget": 2}, {"control_connections": 2},
    {"test_database": "production"}, {"stop_policy": "hard_timeout"},
    {"cleanup_policy": "truncate_everything"},
])
def test_config_validation_precedes_any_factory_execution(changes):
    factory = FakeFactory()
    with pytest.raises(ValueError):
        execute(plan(**changes), factory)
    assert factory.cells == factory.calls == []


def test_deterministic_namespaces_fixed_k_and_warmup_separation():
    declaration = plan(k=3, concurrency_levels=(1, 2), warmups=1, repetitions=2)
    factory = FakeFactory()
    cells = execute(declaration, factory)
    assert [cell.cohort for cell in cells] == [Cohort.WARMUP, Cohort.RECORDED, Cohort.RECORDED] * 2
    assert len([cell for cell in cells if cell.cohort is Cohort.RECORDED]) == 4
    assert len(factory.calls) == 18
    assert len({item.signature.request_id for item in factory.calls}) == 18
    assert len({item.signature.order_id for item in factory.calls}) == 18
    assert len(factory.closed) == len(factory.cleaned) == 6
    for cell in cells:
        assert cell.plan.k == len(cell.planned) == cell.accounting.acknowledged_accepted == 3
        assert cell.cleanup_completed
        assert not cell.incomplete and not cell.problems
        assert prepare_workload(declaration, cell.identity) == cell.planned
        assert all(o.verification.status is LoadDurableStatus.PRESENT for o in cell.observations)
    assert len({tuple(item.workload_index for item in cell.planned) for cell in cells}) == 1


def test_writer_failure_preserves_ambiguous_durable_effect_and_stops_plan():
    factory = FakeFactory(fail_writer=True)
    cells = execute(plan(k=3, concurrency_levels=(1,), repetitions=2), factory)
    assert len(cells) == 1
    cell, = cells
    assert cell.incomplete and len(cell.accounting.residual_workload_indices) == 2
    failed = next(o for o in cell.observations if o.failure)
    assert failed.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert failed.verification.status is LoadDurableStatus.PRESENT
    assert failed.result is failed.measurement is None
    assert cell.accounting.acknowledged_accepted == 0
    assert not factory.cleaned and len(factory.closed) == 1


@pytest.mark.parametrize("option, stage", [
    ("fail_setup", "setup"), ("fail_verify", "verification"),
    ("mismatch", "verification"), ("fail_cleanup", "cleanup"), ("fail_close", "close"),
])
def test_runner_failure_retains_prior_evidence_and_stops(option, stage):
    factory = FakeFactory(**{option: True})
    cells = execute(plan(repetitions=2), factory)
    cell, = cells
    assert any(problem.stage == stage for problem in cell.problems)
    assert "private" not in dumps_evidence(cell)
    if option == "fail_setup":
        assert cell.observations == ()
        assert cell.accounting.offered == 0
        assert cell.accounting.residual_workload_indices == (0,)
    else:
        assert cell.accounting.acknowledged_accepted == 1
        assert cell.observations[0].result is not None
    if option in ("fail_verify", "mismatch"):
        assert not factory.cleaned


def test_sink_failure_keeps_raw_cell_and_closes_resources_without_another_cell():
    factory = FakeFactory()

    def failing_sink(cell):
        raise OSError("private output error")

    with pytest.raises(EvidenceSinkError) as raised:
        run_plan(plan(repetitions=2), factory, clock_ns=CountingClock(), local=local(), sink=failing_sink)
    assert len(raised.value.retained) == len(factory.closed) == 1
    assert raised.value.retained[0].accounting.acknowledged_accepted == 1


def test_tampered_configuration_is_rechecked_before_factory_call():
    declaration = plan()
    object.__setattr__(declaration, "connection_budget", 0)
    factory = FakeFactory()
    with pytest.raises(ValueError):
        execute(declaration, factory)
    assert factory.cells == []


def test_failed_warmup_stops_before_any_recorded_cohort():
    factory = FakeFactory(fail_writer=True)
    cells = execute(plan(warmups=1, repetitions=2, concurrency_levels=(1,)), factory)
    assert len(cells) == 1 and cells[0].cohort is Cohort.WARMUP
    assert not factory.cleaned


class ConnectionDouble:
    """Records SQL intent without a driver/network connection or durable mutation."""

    def __init__(self, pid, *, database="compass_test", occupied=False):
        self.database = database
        self.occupied = occupied
        self.closed = False
        self.autocommit = False
        self.info = SimpleNamespace(
            backend_pid=pid, server_version=160000, transaction_status=TransactionStatus.IDLE,
        )
        self.queries = []
        self.row = None

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, args=None):
        self.queries.append((sql, args))
        if "current_setting" in sql:
            self.row = (self.database, "read committed")
        elif "current_database" in sql:
            self.row = (self.database,)
        else:
            self.row = (int(self.occupied),)

    def fetchone(self):
        return self.row

    def rollback(self):
        pass

    def close(self):
        self.closed = True

    @contextmanager
    def transaction(self):
        yield


def test_postgres_factory_guards_distinct_resources_and_scoped_cleanup_with_doubles(monkeypatch):
    connections = []

    def connect(url, *, connect_timeout_seconds):
        assert url == "postgresql://unit@unused/compass_test"
        assert connect_timeout_seconds == 5
        connection = ConnectionDouble(len(connections) + 1)
        connections.append(connection)
        return connection

    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://unit@unused/compass_test")
    monkeypatch.setattr(runner, "connect_postgres", connect)
    declaration = plan(k=3)
    _, identity = next(declared_cells(declaration))
    workload = prepare_workload(declaration, identity)
    with postgres_runtime(declaration, identity, workload) as runtime:
        assert len(runtime.lanes) == 2 and len(connections) == 3
        assert len(runtime.provenance.connections) == 3
        assert runtime.provenance.placement == "PRE_TRANSACTION"
        assert runtime.provenance.validator_identity.endswith("FullProofValidator")
        runtime.cleanup()
    assert all(connection.closed for connection in connections)
    deletions = [(sql, args) for sql, args in connections[0].queries if sql.startswith("DELETE")]
    assert len(deletions) == 6
    assert all("idempotency_records" in sql for sql, _ in deletions[:3])
    assert all("order_events" in sql for sql, _ in deletions[3:])
    expected = [(item.signature.request_id, item.signature.order_id) for item in workload]
    assert [args for _, args in deletions] == expected * 2
    assert all("request_id = %s AND order_id = %s" in sql for sql, _ in deletions)
    assert not any(word in sql for sql, _ in connections[0].queries
                   for word in ("TRUNCATE", "CASCADE", "RESTART", "decision_receipts", "projection_"))


@pytest.mark.parametrize("kind", ["missing_url", "wrong_declared_database", "wrong_actual_database", "occupied"])
def test_postgres_preflight_refuses_without_writes_and_closes_open_resources(monkeypatch, kind):
    connections = []

    def connect(*args, **kwargs):
        connection = ConnectionDouble(
            1, database="unexpected_test" if kind == "wrong_actual_database" else "compass_test",
            occupied=kind == "occupied",
        )
        connections.append(connection)
        return connection

    monkeypatch.setattr(runner, "connect_postgres", connect)
    if kind == "missing_url":
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    else:
        database = "different_test" if kind == "wrong_declared_database" else "compass_test"
        monkeypatch.setenv("TEST_DATABASE_URL", f"postgresql://unit@unused/{database}")
    declaration = plan()
    _, identity = next(declared_cells(declaration))
    workload = prepare_workload(declaration, identity)
    with pytest.raises((ValueError, ReservedIdentitiesExist)):
        with postgres_runtime(declaration, identity, workload):
            pytest.fail("preflight must not yield runnable resources")
    assert all(connection.closed for connection in connections)
    assert not any(sql.startswith("DELETE") for c in connections for sql, _ in c.queries)
    if kind in ("missing_url", "wrong_declared_database"):
        assert connections == []


def test_separately_callable_cleanup_rechecks_database_before_deleting():
    declaration = plan()
    _, identity = next(declared_cells(declaration))
    connection = ConnectionDouble(1, database="production")
    with pytest.raises(ValueError, match="cleanup connection"):
        cleanup_cell_rows(connection, declaration, identity, prepare_workload(declaration, identity))
    assert not any(sql.startswith("DELETE") for sql, _ in connection.queries)
