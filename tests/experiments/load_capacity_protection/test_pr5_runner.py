"""PR5 session/durable/adapter witnesses, using fake stores and connections only."""

from contextlib import contextmanager
from dataclasses import asdict, fields, replace, MISSING
from threading import Event, Lock
from unittest.mock import Mock

import pytest

from experiments.load_capacity_protection import pr5_postgres_runtime as postgres
from experiments.load_capacity_protection.evidence import Cohort, IdempotencyEvidence
from experiments.load_capacity_protection.model import LoadDurableStatus
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission
from experiments.load_capacity_protection.pr4_model import VerificationEvidence
from experiments.load_capacity_protection.pr5_evidence import dumps_evidence, loads_evidence, recorded_statistics, summaries
from experiments.load_capacity_protection.pr5_model import RetryPlan, RetryPolicy, LogicalTerminal, declared_cells, prepare_workload
from experiments.load_capacity_protection.pr5_runner import EvidenceSinkError, run_plan, verification_problems
from experiments.load_capacity_protection.runner import ReservedIdentitiesExist
from src.pipeline.transactional.writer_capacity import WriterCapacityRefused
from src.storage.idempotency_store import IdempotencyDecision, IdempotencyVerdict
from tests.experiments.load_capacity_protection.test_evidence import plan as pr1_plan
from tests.experiments.load_capacity_protection.test_postgres_characterization import result_for
from tests.experiments.load_capacity_protection.test_pr4_runner import FakeFactory as PR4Factory, absent, source
from tests.experiments.load_capacity_protection.test_pr5_characterization import FakeClock, config
from tests.experiments.load_capacity_protection.test_runner import ConnectionDouble


def plan(**changes):
    return RetryPlan(**(asdict(pr1_plan()) | dict(
        k=7, concurrency_levels=(3,), connection_budget=4, repetitions=2,
        protection_bound=1, policies=(config(RetryPolicy.NO_RETRY, attempts=1), config()),
        policy_order='rotating_policy_blocks',
    ) | changes))


class FakeFactory(PR4Factory):
    """Reuse unchanged fault/provenance fakes; successful cells exercise all budgets."""

    def __init__(self, failure=None, *, eventual=False):
        super().__init__(failure=failure, saturate=False)
        self.eventual = eventual
        self.release = self.returned = None

    @contextmanager
    def __call__(self, declaration, scheduled, workload, admission):
        with super().__call__(declaration, scheduled, workload, admission) as base:
            if self.failure:
                yield base
                return
            held, release, returned = Event(), Event(), Event()
            self.release, self.returned = release, returned
            holder = workload[0]
            durable, attempted = {}, {}
            lock = Lock()
            refused = 0
            target = (2 if self.eventual and scheduled.retry.policy is not RetryPolicy.NO_RETRY
                      else (declaration.k - 1) * scheduled.retry.max_attempts_per_logical_request)
            calls = self.calls

            class Lane:
                capacity_admission = admission

                def __call__(self, item):
                    nonlocal refused
                    calls.append(item)
                    with lock:
                        attempted[item.workload_index] = attempted.get(item.workload_index, 0) + 1
                    if item != holder:
                        assert held.wait(5)

                    def operation():
                        if item == holder:
                            held.set()
                            assert release.wait(5)
                        assert item.workload_index not in durable
                        result = result_for(item)
                        durable[item.workload_index] = result.accepted_event
                        return result
                    try:
                        result = admission.run(operation)
                        if item == holder:
                            returned.set()
                        return result
                    except WriterCapacityRefused:
                        with lock:
                            refused += 1
                            if refused == target:
                                release.set()
                        raise

            def verify(item):
                event = durable.get(item.workload_index)
                if event is None:
                    return absent()
                return VerificationEvidence(LoadDurableStatus.PRESENT, (event,),
                                            IdempotencyEvidence(IdempotencyVerdict.REPLAY, item.signature, event),
                                            1, (), identity_idempotency_count=1)

            def cleanup(accepted):
                assert all(i.workload_index in durable for i in accepted)
                self.cleaned.append((scheduled, accepted))

            try:
                yield replace(base, lanes=tuple(Lane() for _ in base.lanes), verify=verify, cleanup=cleanup)
            finally:
                release.set()


def execute(declaration=None, factory=None, source_provider=source):
    declaration, factory = declaration or plan(), factory or FakeFactory()
    clock = FakeClock()
    exported = []

    def waiter(eligible, stopped):
        if factory.eventual and factory.release.is_set():
            assert factory.returned.wait(5)
        clock.advance_to(eligible)

    def sink(cell):
        assert factory.closed or factory.failure == 'setup' or not factory.cells
        exported.append(loads_evidence(dumps_evidence(cell)))

    cells = run_plan(declaration, factory, clock_ns=clock, wait_until=waiter,
                     source_provider=source_provider, sink=sink)
    assert tuple(exported) == cells
    return cells, factory


def test_explicit_plan_contemporaneous_control_and_full_counterbalance():
    policies = tuple(config(p, attempts=1 if p is RetryPolicy.NO_RETRY else 4) for p in RetryPolicy)
    declaration = plan(policies=policies, concurrency_levels=(3, 5), connection_budget=6, warmups=1, repetitions=5)
    assert all(f.default is MISSING and f.default_factory is MISSING for f in fields(RetryPlan))
    order = declared_cells(declaration)
    assert order == declared_cells(declaration) and len(order) == 60
    recorded = [c for c in order if c.cohort is Cohort.RECORDED]
    for n in declaration.concurrency_levels:
        for p in RetryPolicy:
            assert sorted(c.position_in_block for c in recorded
                          if c.identity.configured_concurrency == n and c.retry.policy is p) == list(range(5))
    ids, permutations = [], set()
    for i, scheduled in enumerate(order):
        assert scheduled.execution_index == i
        items = prepare_workload(declaration, scheduled)
        ids.extend(item.signature.request_id for item in items)
        permutations.add(tuple(item.workload_index for item in items))
    assert len(set(ids)) == len(ids) and len(permutations) == 1
    assert declaration.required_connections == 6


@pytest.mark.parametrize('changes', [
    {'policies': ()}, {'policies': (config(),)},
    {'policies': (config(RetryPolicy.NO_RETRY, 1),) * 2},
    {'protection_bound': 0}, {'protection_bound': True}, {'policy_order': 'adaptive'}, {'connection_budget': 2},
])
def test_invalid_matrix_rejected(changes):
    with pytest.raises((ValueError, TypeError)):
        plan(**changes)


def test_budget_exhaustion_is_normal_unrelated_work_continues_warmups_separate():
    cells, factory = execute(plan(warmups=1))
    assert len(cells) == len(factory.closed) == 6
    assert len(recorded_statistics(cells)) == 4
    for cell, (_, accepted) in zip(cells, factory.cleaned):
        assert not cell.incomplete and cell.cleanup_completed
        counts = summaries(cell)
        assert counts['logical_requests'] == 7
        assert counts['total_attempts'] == 1 + 6 * cell.scheduled.retry.max_attempts_per_logical_request
        assert counts['retry_budget_exhausted_logical_requests'] == 6
        assert len(accepted) == counts['acknowledged_accepted_logical_requests'] == 1
        for request in cell.cell.logical_requests:
            assert verification_problems(request, request.verification) == ()
            if request.terminal_state is LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL:
                assert request.verification == absent()


def test_eventual_accepted_has_one_durable_event_and_mapping_after_two_refusals():
    cells, _ = execute(plan(k=2, concurrency_levels=(2,), repetitions=1), FakeFactory(eventual=True))
    request = next(r for r in cells[1].cell.logical_requests if len(r.attempts) > 1)
    assert request.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED
    assert len(request.attempts) == 3
    assert verification_problems(request, request.verification) == ()
    assert request.verification.identity_idempotency_count == 1
    assert len(request.verification.accepted_events) == 1
    assert request.verification.idempotency.signature == request.item.signature
    assert request.verification.idempotency.accepted_event == request.attempts[-1].observation.result.accepted_event
    for changes in ({'identity_idempotency_count': 0}, {'identity_idempotency_count': 2},
                    {'identity_idempotency_count': None}, {'accepted_events': ()}, {'request_event_count': 2},
                    {'idempotency': absent().idempotency}):
        assert verification_problems(request, replace(request.verification, **changes))
    event, = request.verification.accepted_events
    for changes in ({'sequence': 2}, {'request_id': 'wrong'}, {'order_id': 'wrong'}, {'amount': event.amount + 1}):
        assert verification_problems(request, replace(request.verification, accepted_events=(replace(event, **changes),)))


@pytest.mark.parametrize('failure', ['setup', 'native', 'delivery', 'verify', 'accepted_absent', 'cleanup', 'close'])
def test_failures_stop_plan_preserve_partial_evidence_without_private_messages(failure):
    cells, factory = execute(plan(warmups=1, concurrency_levels=(1,)), FakeFactory(failure))
    cell, = cells
    assert cell.incomplete and cell.scheduled.cohort is Cohort.WARMUP
    assert 'private' not in dumps_evidence(cell)
    if failure not in ('cleanup', 'close'):
        assert not factory.cleaned
    if failure == 'native':
        request = cell.cell.logical_requests[0]
        assert request.terminal_state is LogicalTerminal.NATIVE_WRITER_FAILURE
        assert len(request.attempts) == 1
        assert request.verification.status is LoadDurableStatus.PRESENT
        assert summaries(cell)['acknowledged_accepted_logical_requests'] == 0


def test_source_drift_and_sink_failure_stop_with_raw_evidence():
    probes = iter([source(), source(), replace(source(), source_commit='b' * 40)])
    cells, factory = execute(source_provider=lambda: next(probes))
    assert len(cells) == 1 and cells[0].incomplete and not factory.cleaned
    with pytest.raises(ValueError, match='committed source'):
        execute(source_provider=lambda: replace(source(), working_tree='tracked_modified'))
    factory, clock = FakeFactory(), FakeClock()
    with pytest.raises(EvidenceSinkError) as raised:
        run_plan(plan(), factory, clock_ns=clock, wait_until=clock.wait_until, source_provider=source,
                 sink=Mock(side_effect=OSError('private output')))
    assert len(raised.value.retained) == len(factory.closed) == 1


def test_refusal_absence_requires_no_orphan_mapping():
    cells, _ = execute(plan(repetitions=1))
    request = next(r for r in cells[0].cell.logical_requests if r.terminal_state is not LogicalTerminal.ACKNOWLEDGED_ACCEPTED)
    for changes in ({'identity_idempotency_count': 1}, {'identity_idempotency_count': None},
                    {'request_event_count': 1}, {'idempotency': None}, {'status': LoadDurableStatus.UNKNOWN}):
        assert verification_problems(request, absent(**changes))


def test_postgres_adapter_retains_n_plus_one_connections_and_exact_cleanup(monkeypatch):
    declaration = plan()
    scheduled = declared_cells(declaration)[0]
    items, clock = prepare_workload(declaration, scheduled), FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    connections = []

    def connect(*args, **kwargs):
        c = ConnectionDouble(len(connections) + 1)
        connections.append(c)
        return c

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
    assert not any(word in sql for c in connections for sql, _ in c.queries
                   for word in ('TRUNCATE', 'CASCADE', 'VACUUM', 'RESTART'))


@pytest.mark.parametrize('kind', ['missing', 'wrong_url', 'wrong_actual', 'occupied', 'duplicate_pid'])
def test_postgres_preflight_is_nonmutating_and_closes_partial_setup(monkeypatch, kind):
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
        with postgres.postgres_runtime(declaration, scheduled, prepare_workload(declaration, scheduled),
                                       ObservedAdmission(1, clock_ns=FakeClock())):
            pytest.fail('preflight must not yield')
    assert all(c.closed for c in connections)
    assert not any(sql.startswith('DELETE') for c in connections for sql, _ in c.queries)
