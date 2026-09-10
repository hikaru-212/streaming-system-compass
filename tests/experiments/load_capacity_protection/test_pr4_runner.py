"""PR4 plan, verification and resource tests; all connections and writes are fakes."""

from contextlib import contextmanager
from dataclasses import asdict, fields, replace, MISSING
from threading import Event, Lock
from unittest.mock import Mock

import pytest

from experiments.load_capacity_protection.evidence import (
    Cohort, ConnectionFact, IdempotencyEvidence, LocalProvenance, RuntimeProvenance,
)
from experiments.load_capacity_protection.model import LoadAcknowledgement, LoadDurableStatus
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission
from experiments.load_capacity_protection.pr4_evidence import dumps_evidence, loads_evidence, recorded_statistics
from experiments.load_capacity_protection.pr4_model import (
    ComparisonPlan, ProtectionMode, VerificationEvidence, declared_cells, prepare_workload,
)
from experiments.load_capacity_protection.pr4_runner import (
    EvidenceSinkError, PreparedRuntime, run_plan, verification_problems,
)
from experiments.load_capacity_protection import pr4_postgres_runtime as postgres
from experiments.load_capacity_protection.runner import ReservedIdentitiesExist
from src.storage.idempotency_store import IdempotencyDecision, IdempotencyVerdict
from src.pipeline.transactional.writer_capacity import WriterCapacityRefused
from tests.experiments.load_capacity_protection.test_evidence import plan as pr1_plan
from tests.experiments.load_capacity_protection.test_postgres_characterization import CountingClock, FakeWriterFailure, result_for
from tests.experiments.load_capacity_protection.test_runner import ConnectionDouble


def plan(**changes):
    values = asdict(pr1_plan()) | dict(
        k=7, concurrency_levels=(3,), connection_budget=4, repetitions=2,
        protection_bound=1, pairing_order='alternating_adjacent_pairs',
        first_mode=ProtectionMode.UNPROTECTED,
    )
    return ComparisonPlan(**(values | changes))


def source():
    return LocalProvenance('a' * 40, 'tracked_clean;untracked_not_inspected',
                           'unit-python', 'unit-psycopg', 'unit', 'unit', 4, 'CountingClock')


def absent(**changes):
    return replace(VerificationEvidence(
        LoadDurableStatus.ABSENT, (), IdempotencyEvidence(IdempotencyVerdict.MISS, None, None),
        0, (), identity_idempotency_count=0,
    ), **changes)


class FakeFactory:
    def __init__(self, failure=None, saturate=True):
        self.failure = failure
        self.saturate = saturate
        self.cells, self.closed, self.cleaned, self.calls, self.admissions = [], [], [], [], []

    @contextmanager
    def __call__(self, declaration, scheduled, workload, admission):
        self.cells.append(scheduled)
        self.admissions.append(admission)
        if self.failure == 'setup':
            raise RuntimeError('private setup detail')
        n = scheduled.identity.configured_concurrency
        saturation = self.saturate and admission is not None and n > admission.bound
        holders = {i.workload_index for i in workload[:admission.bound]} if saturation else set()
        held, done = Event(), Event()
        lock = Lock()
        active = refused = 0
        durable = {}
        calls = self.calls
        failure = self.failure

        class Lane:
            capacity_admission = admission

            def __call__(self, item):
                nonlocal active, refused
                calls.append(item)
                if saturation and item.workload_index not in holders:
                    assert held.wait(5)

                def operation():
                    nonlocal active
                    if saturation:
                        with lock:
                            active += 1
                            if active == admission.bound:
                                held.set()
                        assert done.wait(5)
                    result = result_for(item)
                    durable[item.workload_index] = result.accepted_event
                    if failure == 'native':
                        raise FakeWriterFailure()
                    if failure == 'delivery':
                        return object()
                    return result
                try:
                    return operation() if admission is None else admission.run(operation)
                except WriterCapacityRefused:
                    with lock:
                        refused += 1
                        if refused == declaration.k - admission.bound:
                            done.set()
                    raise

        def verify(item):
            if failure == 'verify':
                raise RuntimeError('private verification detail')
            event = durable.get(item.workload_index)
            if event is None:
                return absent(identity_idempotency_count=1 if failure == 'refused_effect' else 0)
            if failure == 'accepted_absent':
                return absent()
            return VerificationEvidence(
                LoadDurableStatus.PRESENT, (event,),
                IdempotencyEvidence(IdempotencyVerdict.REPLAY, item.signature, event), 1, (),
                identity_idempotency_count=1,
            )

        def cleanup(accepted):
            if failure == 'cleanup':
                raise RuntimeError('private cleanup detail')
            assert all(i.workload_index in durable for i in accepted)
            self.cleaned.append((scheduled, accepted))

        facts = tuple(ConnectionFact(i, declaration.test_database, 160015, index + 1,
                                     'read committed', False) for index, i in enumerate((None, *range(n))))
        if failure == 'environment' and len(self.cells) > 1:
            facts = tuple(replace(fact, postgres_version=170000) for fact in facts)
        try:
            yield PreparedRuntime(tuple(Lane() for _ in range(n)), RuntimeProvenance(
                facts, 'PRE_TRANSACTION', 'OCC', 'strict', 'ValidationRuntime', 'FullProofValidator',
            ), 'ValidationPolicy', verify, cleanup)
        finally:
            self.closed.append(scheduled)
            if failure == 'close':
                raise RuntimeError('private close detail')


def execute(declaration=None, factory=None, source_provider=source):
    declaration = declaration or plan()
    factory = factory or FakeFactory()
    exported = []

    def sink(cell):
        assert factory.closed or factory.failure == 'setup' or not factory.cells
        exported.append(loads_evidence(dumps_evidence(cell)))

    cells = run_plan(declaration, factory, clock_ns=CountingClock(), source_provider=source_provider, sink=sink)
    assert tuple(exported) == cells
    return cells, factory


def test_explicit_plan_has_no_hidden_eight_and_counterbalances_adjacent_pairs():
    assert all(f.default is MISSING and f.default_factory is MISSING for f in fields(ComparisonPlan))
    with pytest.raises(TypeError):
        ComparisonPlan(**asdict(pr1_plan()))
    declaration = plan(concurrency_levels=(3, 5), connection_budget=6, warmups=1, repetitions=3, protection_bound=2)
    order = declared_cells(declaration)
    assert order == declared_cells(declaration)
    assert len(order) == 16
    recorded = [c for c in order if c.cohort is Cohort.RECORDED]
    assert [c.protection.mode for c in recorded[:8]] == [
        ProtectionMode.UNPROTECTED, ProtectionMode.PROTECTED, ProtectionMode.PROTECTED, ProtectionMode.UNPROTECTED,
        ProtectionMode.PROTECTED, ProtectionMode.UNPROTECTED, ProtectionMode.UNPROTECTED, ProtectionMode.PROTECTED,
    ]
    requests = []
    for i, scheduled in enumerate(order):
        assert scheduled.execution_index == i and scheduled.position_in_pair == i % 2
        items = prepare_workload(declaration, scheduled)
        assert len(items) == declaration.k
        requests.extend(item.signature.request_id for item in items)
    assert len(set(requests)) == len(requests)
    assert len({tuple(i.workload_index for i in prepare_workload(declaration, c)) for c in order}) == 1
    assert declaration.required_connections == 6


@pytest.mark.parametrize('changes', [
    {'protection_bound': 0}, {'protection_bound': True}, {'pairing_order': 'grouped'},
    {'first_mode': None}, {'k': 0}, {'connection_budget': 3},
])
def test_invalid_plan_rejected_before_execution(changes):
    with pytest.raises((TypeError, ValueError)):
        plan(**changes)


def test_refused_cells_continue_pair_plan_warmups_excluded_and_cleanup_only_accepted():
    cells, factory = execute(plan(warmups=1))
    assert len(cells) == len(factory.closed) == 6
    assert len(recorded_statistics(cells)) == 4
    assert all(not c.incomplete and c.cleanup_completed for c in cells)
    for cell, (_, cleaned), admission in zip(cells, factory.cleaned, factory.admissions):
        assert cell.local_before == cell.local_after == source()
        assert cell.execution_order == declared_cells(cell.plan)
        assert len(cleaned) == cell.accounting.acknowledged_accepted
        if cell.scheduled.protection.mode is ProtectionMode.PROTECTED:
            assert admission.bound == 1
            assert cell.accounting.capacity_refused == 6
            assert len(cleaned) == 1
        else:
            assert admission is None
            assert len(cleaned) == 7


@pytest.mark.parametrize('failure', ['setup', 'native', 'delivery', 'verify', 'accepted_absent', 'cleanup', 'close'])
def test_failures_stop_later_cells_retain_evidence_and_hide_private_messages(failure):
    cells, factory = execute(plan(concurrency_levels=(1,), warmups=1), FakeFactory(failure=failure))
    cell, = cells
    assert cell.incomplete and cell.scheduled.cohort is Cohort.WARMUP
    assert 'private' not in dumps_evidence(cell)
    if failure not in ('cleanup', 'close'):
        assert not factory.cleaned
    if failure == 'native':
        assert cell.accounting.native_writer_failures == 1
        assert cell.accounting.acknowledged_accepted == 0
        assert len(cell.accounting.residual_workload_indices) == 6
        row = cell.cell.observations[0]
        assert row.verification.status is LoadDurableStatus.PRESENT
        assert row.acknowledgement is LoadAcknowledgement.UNKNOWN


def test_refused_durable_effect_stops_without_cleaning():
    cells, factory = execute(plan(first_mode=ProtectionMode.PROTECTED), FakeFactory('refused_effect'))
    cell, = cells
    assert cell.accounting.capacity_refused == 6
    assert cell.incomplete and not factory.cleaned
    assert any('capacity_refusal_absence' in issue for row in cell.cell.observations
               for issue in row.verification.problems)


def test_refused_verification_requires_both_event_and_mapping_absence():
    observation = Mock(capacity_refused_ns=1)
    assert verification_problems(observation, absent()) == ()
    for changes in ({'status': LoadDurableStatus.UNKNOWN}, {'request_event_count': 1},
                    {'identity_idempotency_count': None}, {'identity_idempotency_count': 1},
                    {'idempotency': None}):
        assert verification_problems(observation, absent(**changes))


def test_accepted_verification_keeps_exact_event_sequence_signature_and_idempotency_rules():
    cells, _ = execute(plan(concurrency_levels=(1,), k=1, repetitions=1))
    observation = cells[0].cell.observations[0]
    verified = observation.verification
    assert verification_problems(observation, verified) == ()
    event, = verified.accepted_events
    for changes in ({'sequence': 2}, {'request_id': 'wrong'}, {'order_id': 'wrong'}, {'amount': event.amount + 1}):
        assert verification_problems(observation, replace(verified, accepted_events=(replace(event, **changes),)))
    assert verification_problems(observation, replace(verified, accepted_events=(event, event)))
    assert verification_problems(observation, replace(verified, idempotency=absent().idempotency))


def test_source_and_database_drift_stop_comparison():
    cells, factory = execute(factory=FakeFactory('environment'))
    assert len(cells) == 2 and cells[-1].incomplete and len(factory.cleaned) == 1
    probes = iter([source(), source(), replace(source(), source_commit='b' * 40)])
    cells, factory = execute(source_provider=lambda: next(probes))
    assert len(cells) == 1 and cells[0].incomplete and not factory.cleaned
    assert cells[0].local_before.source_commit != cells[0].local_after.source_commit
    with pytest.raises(ValueError, match='committed source'):
        execute(source_provider=lambda: replace(source(), working_tree='tracked_modified'))


def test_sink_failure_retains_raw_cells_after_close():
    factory = FakeFactory()
    with pytest.raises(EvidenceSinkError) as raised:
        run_plan(plan(), factory, clock_ns=CountingClock(), source_provider=source,
                 sink=Mock(side_effect=OSError('private output')))
    assert len(raised.value.retained) == len(factory.closed) == 1


def test_source_probe_failure_retains_prior_cells_and_unoffered_current_cell():
    probes = iter([source(), source(), source(), OSError('private source failure')])

    def provider():
        result = next(probes)
        if isinstance(result, Exception):
            raise result
        return result

    cells, factory = execute(source_provider=provider)
    assert len(cells) == 2 and len(factory.cells) == 1
    assert cells[-1].incomplete and cells[-1].local_before is None
    assert cells[-1].accounting.offered == 0
    assert cells[-1].accounting.residual_workload_indices
    assert cells[-1].problems[0].stage == 'source'
    assert 'private' not in dumps_evidence(cells[-1])


@pytest.mark.parametrize('mode', list(ProtectionMode))
def test_real_factory_uses_n_plus_one_connections_and_deletes_only_exact_accepted_subset(monkeypatch, mode):
    declaration = plan(first_mode=mode)
    scheduled = declared_cells(declaration)[0]
    items = prepare_workload(declaration, scheduled)
    clock = CountingClock()
    admission = ObservedAdmission(1, clock_ns=clock) if mode is ProtectionMode.PROTECTED else None
    connections = []

    def connect(*args, **kwargs):
        connection = ConnectionDouble(len(connections) + 1)
        connections.append(connection)
        return connection

    monkeypatch.setenv('TEST_DATABASE_URL', 'postgresql://unit@unused/compass_test')
    monkeypatch.setattr(postgres, 'connect_postgres', connect)
    monkeypatch.setattr(postgres, 'PostgresEventStore', lambda c: Mock(load=Mock(return_value=[])))
    monkeypatch.setattr(postgres, 'PostgresIdempotencyStore', lambda c: Mock(
        check=Mock(return_value=IdempotencyDecision(IdempotencyVerdict.MISS, 'unit'))))
    with postgres.postgres_runtime(declaration, scheduled, items, admission) as runtime:
        assert len(connections) == 4
        assert all(lane.writer._capacity_admission is admission for lane in runtime.lanes)
        assert runtime.verify(items[0]) == absent()
        runtime.cleanup(items[:1])
    assert all(c.closed for c in connections)
    deletions = [(sql, args) for sql, args in connections[0].queries if sql.startswith('DELETE')]
    assert len(deletions) == 2
    assert [args for _, args in deletions] == [(items[0].signature.request_id, items[0].signature.order_id)] * 2
    assert all('request_id = %s AND order_id = %s' in sql for sql, _ in deletions)
    assert any('request_id = %s OR order_id = %s' in sql for sql, _ in connections[0].queries)
    assert not any(word in sql for c in connections for sql, _ in c.queries
                   for word in ('TRUNCATE', 'CASCADE', 'VACUUM', 'RESTART'))


@pytest.mark.parametrize('kind', ['missing', 'wrong_url', 'wrong_actual', 'occupied', 'duplicate_pid'])
def test_live_factory_preflight_fails_without_writes_using_only_connection_doubles(monkeypatch, kind):
    declaration = plan()
    scheduled = declared_cells(declaration)[0]
    connections = []

    def connect(*args, **kwargs):
        c = ConnectionDouble(1 if kind == 'duplicate_pid' else len(connections) + 1,
                             database='unexpected_test' if kind == 'wrong_actual' else 'compass_test',
                             occupied=kind == 'occupied')
        connections.append(c)
        return c

    monkeypatch.setattr(postgres, 'connect_postgres', connect)
    if kind == 'missing':
        monkeypatch.delenv('TEST_DATABASE_URL', raising=False)
    else:
        name = 'other_test' if kind == 'wrong_url' else 'compass_test'
        monkeypatch.setenv('TEST_DATABASE_URL', f'postgresql://unit@unused/{name}')
    with pytest.raises((ValueError, ReservedIdentitiesExist)):
        with postgres.postgres_runtime(declaration, scheduled, prepare_workload(declaration, scheduled), None):
            pytest.fail('preflight must not yield')
    assert all(c.closed for c in connections)
    assert not any(sql.startswith('DELETE') for c in connections for sql, _ in c.queries)
