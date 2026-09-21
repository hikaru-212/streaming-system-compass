"""Causal retry schedules through real admission/public writers; no sleeps or SQL."""

from dataclasses import fields, replace, MISSING
from threading import Event, Lock
from unittest.mock import Mock

import pytest

from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission
from experiments.load_capacity_protection.pr4_model import Protection, ProtectionMode, derive_overlap
from experiments.load_capacity_protection.pr5_characterization import CharacterizationError, run_characterization
from experiments.load_capacity_protection.pr5_model import (
    JITTER_ALGORITHM, LogicalTerminal, RetryConfig, RetryPolicy, retry_delay_ns, seeded_jitter,
)
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from tests.experiments.load_capacity_protection.test_capacity_admission import connection
from tests.experiments.load_capacity_protection.test_postgres_characterization import (
    CountingClock, FakeWriterFailure, identity, result_for, workload,
)


def config(policy=RetryPolicy.IMMEDIATE_RETRY, attempts=4, **changes):
    values = dict(policy=policy, max_attempts_per_logical_request=attempts,
                  fixed_delay_ns=None, base_delay_ns=None, backoff_cap_ns=None,
                  jitter_max_ns=None, jitter_seed=None, jitter_algorithm=None)
    if policy is RetryPolicy.FIXED_BACKOFF:
        values.update(fixed_delay_ns=100)
    if policy in (RetryPolicy.EXPONENTIAL_BACKOFF, RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER):
        values.update(base_delay_ns=100, backoff_cap_ns=350)
    if policy is RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER:
        values.update(jitter_max_ns=50, jitter_seed=17, jitter_algorithm=JITTER_ALGORITHM)
    return RetryConfig(**(values | changes))


class FakeClock(CountingClock):
    def advance_to(self, target):
        with self.lock:
            self.value = max(self.value, target)

    def wait_until(self, eligible, stopped):
        self.advance_to(eligible)


def trajectory(monkeypatch, retry=None, *, eventual=True, n=2, bound=1, k=2):
    """Hold bound writers until two refusals (accept later), or every budget expires."""
    retry = retry or config()
    clock = FakeClock()
    admission = ObservedAdmission(bound, clock_ns=clock)
    items = workload(k)
    retained = tuple(PostgresLoadLane(i, connection(), capacity_admission=admission) for i in range(n))
    by_request = {item.signature.request_id: item for item in items}
    held, release, holder_returned = Event(), Event(), Event()
    lock = Lock()
    active = refusals = 0
    target = 2 if eventual else (k - bound) * retry.max_attempts_per_logical_request
    calls, effects, waits = [], {}, []

    def execute(**kwargs):
        nonlocal active
        item = by_request[kwargs['request_id']]
        if item.workload_index < bound:
            with lock:
                active += 1
                if active == bound:
                    held.set()
            assert release.wait(5)
        assert item.workload_index not in effects
        result = result_for(item)
        effects[item.workload_index] = (item.signature, result.accepted_event)
        return result

    for lane in retained:
        monkeypatch.setattr(lane.writer, '_execute_command', execute)

    class Lane:
        capacity_admission = admission

        def __init__(self, lane):
            self.lane = lane

        def __call__(self, item):
            nonlocal refusals
            calls.append((self.lane.lane_id, item))
            if item.workload_index >= bound:
                assert held.wait(5)
            try:
                result = self.lane(item)
                if item.workload_index < bound:
                    holder_returned.set()
                return result
            except WriterCapacityRefused:
                with lock:
                    refusals += 1
                    if refusals == target:
                        release.set()
                raise

    def waiter(eligible, stopped):
        waits.append(eligible)
        if eventual and release.is_set():
            assert holder_returned.wait(5)
            # The retrying lane has no permit; after holder release the real
            # gate is available before the retry starts. No SQL was performed.
            assert BoundedWriterAdmission.run(admission, lambda: True)
        clock.advance_to(eligible)

    try:
        cell = run_characterization(identity(n), Protection(ProtectionMode.PROTECTED, bound), retry,
                                    items, tuple(Lane(l) for l in retained), admission=admission,
                                    clock_ns=clock, wait_until=waiter)
    finally:
        release.set()
    return cell, effects, calls, waits, retained


@pytest.mark.parametrize('policy', list(RetryPolicy))
def test_stable_identity_monotone_attempts_budget_and_real_bound(monkeypatch, policy):
    retry = config(policy, attempts=1 if policy is RetryPolicy.NO_RETRY else 4)
    cell, effects, calls, waits, lanes = trajectory(monkeypatch, retry, eventual=False, n=5, bound=2, k=11)
    assert len(cell.logical_requests) == 11
    assert len(cell.observations) == 2 + 9 * retry.max_attempts_per_logical_request
    assert derive_overlap(cell, protected=True).maximum_complete_interval_overlap == 2
    assert len(effects) == 2
    for request in cell.logical_requests:
        assert [a.attempt_index for a in request.attempts] == list(range(1, len(request.attempts) + 1))
        assert len({a.observation.lane_id for a in request.attempts}) == 1
        assert all(a.observation.item is request.item for a in request.attempts)
        if request.item.workload_index >= 2:
            assert request.terminal_state is LogicalTerminal.RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL
            assert len(request.attempts) == retry.max_attempts_per_logical_request
            for a in request.attempts:
                row = a.observation
                assert row.capacity_refused_ns is not None
                assert row.result is row.measurement is row.failure is None
                assert row.protected_writer_entry_ns is row.protected_writer_exit_ns is None
            for a, b in zip(request.attempts, request.attempts[1:]):
                assert b.observation.dispatch_ns >= a.next_retry_eligible_ns
                assert b.observation.dispatch_ns > a.observation.admission_return_ns
    for lane in lanes:
        lane.connection.cursor.assert_not_called()
        lane.connection.commit.assert_not_called()
        lane.connection.rollback.assert_not_called()
    assert not hasattr(WriterCapacityRefused(), 'retry_authority')
    assert all('authority' not in f.name for f in fields(RetryConfig))


@pytest.mark.parametrize('policy', list(RetryPolicy)[1:])
def test_refused_twice_then_exactly_one_accepted_effect_and_no_later_attempt(monkeypatch, policy):
    cell, effects, calls, waits, _ = trajectory(monkeypatch, config(policy))
    request = cell.logical_requests[1]
    assert len(request.attempts) == 3
    assert request.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED
    assert [item for _, item in calls if item.workload_index == 1] == [request.item] * 3
    assert effects[1] == (request.item.signature, request.attempts[-1].observation.result.accepted_event)
    assert len(effects) == 2 and len(waits) == 2
    assert request.attempts[-1].scheduled_retry_delay_ns is None
    with pytest.raises(ValueError, match='retry must follow'):
        replace(request, attempts=request.attempts + (replace(request.attempts[-1], attempt_index=4),))


def test_delay_formulas_and_seeded_jitter():
    fixed = config(RetryPolicy.FIXED_BACKOFF)
    exponential = config(RetryPolicy.EXPONENTIAL_BACKOFF, attempts=7)
    assert [retry_delay_ns(fixed, 3, a) for a in range(1, 5)] == [100, 100, 100, None]
    assert [retry_delay_ns(exponential, 3, a) for a in range(1, 7)] == [100, 200, 350, 350, 350, 350]
    jitter = config(RetryPolicy.EXPONENTIAL_BACKOFF_WITH_JITTER)
    expected = [retry_delay_ns(jitter, 3, a) for a in range(1, 4)]
    assert expected == [108, 201, 354]
    assert len({retry_delay_ns(jitter, i, 1) for i in range(10)}) > 1
    assert retry_delay_ns(jitter, 3, 3, jitter_source=lambda *args: 50) == 400
    with pytest.raises(ValueError):
        retry_delay_ns(jitter, 3, 1, jitter_source=lambda *args: 51)
    assert retry_delay_ns(config(attempts=2), 0, 1) == 0
    assert retry_delay_ns(config(RetryPolicy.NO_RETRY, attempts=1), 0, 1) is None
    huge = config(RetryPolicy.EXPONENTIAL_BACKOFF, attempts=10**9)
    assert retry_delay_ns(huge, 0, 10**8) == 350
    assert seeded_jitter(17, 3, 1, 50) == 8


@pytest.mark.parametrize('changes', [
    {'max_attempts_per_logical_request': 0}, {'max_attempts_per_logical_request': True},
    {'fixed_delay_ns': 1}, {'policy': 'immediate_retry'}, {'jitter_seed': 1},
])
def test_invalid_policy_configuration(changes):
    with pytest.raises((TypeError, ValueError)):
        replace(config(), **changes)
    assert all(f.default is MISSING and f.default_factory is MISSING for f in fields(RetryConfig))


@pytest.mark.parametrize('error', [FakeWriterFailure(), WriterCapacityRefused('inside body')])
def test_native_failure_never_retries_or_becomes_capacity_refusal(monkeypatch, error):
    clock = FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    lane = PostgresLoadLane(0, connection(), capacity_admission=admission)
    monkeypatch.setattr(lane.writer, '_execute_command', Mock(side_effect=error))
    waiter = Mock(side_effect=AssertionError('no retry waiting allowed'))
    cell = run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1), config(), workload(3),
                                (lane,), admission=admission, clock_ns=clock, wait_until=waiter)
    request = cell.logical_requests[0]
    assert request.terminal_state is LogicalTerminal.NATIVE_WRITER_FAILURE
    assert len(request.attempts) == 1
    assert request.attempts[0].observation.capacity_refused_ns is None
    assert request.attempts[0].observation.failure.exception_class.endswith(type(error).__name__)
    assert not cell.logical_requests[1].attempts
    waiter.assert_not_called()


@pytest.mark.parametrize('outcome', [o for o in PostgresWriteSideOutcome if o is not PostgresWriteSideOutcome.ACCEPTED])
def test_normal_nonaccepted_is_terminal_without_retry(monkeypatch, outcome):
    clock = FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    item, = workload(1)
    lane = PostgresLoadLane(0, connection(), capacity_admission=admission)
    monkeypatch.setattr(lane.writer, '_execute_command', lambda **kw: replace(result_for(item, replay=True), outcome=outcome))
    cell = run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1), config(), (item,),
                                (lane,), admission=admission, clock_ns=clock,
                                wait_until=Mock(side_effect=AssertionError('no retry')))
    assert cell.logical_requests[0].terminal_state is LogicalTerminal.NON_ACCEPTED_WRITER_RESULT
    assert len(cell.observations) == 1


@pytest.mark.parametrize('kind', ['bypass', 'double', 'wrong_return', 'pre_entry'])
def test_harness_defect_preserves_partial_attempt_and_never_retries(kind):
    clock = FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)

    class Lane:
        capacity_admission = admission

        def __call__(self, item):
            if kind == 'pre_entry':
                raise RuntimeError('private harness detail')
            if kind == 'bypass':
                return result_for(item)
            value = admission.run(lambda: object() if kind == 'wrong_return' else result_for(item))
            if kind == 'double':
                admission.run(lambda: value)
            return value

    with pytest.raises(CharacterizationError) as raised:
        run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1), config(), workload(1),
                             (Lane(),), admission=admission, clock_ns=clock, wait_until=clock.wait_until)
    request, = raised.value.cell.logical_requests
    assert request.terminal_state is LogicalTerminal.INCOMPLETE
    assert len(request.attempts) == 1
    assert raised.value.failures


@pytest.mark.parametrize('stop_other_lane', [False, True])
def test_backoff_does_not_block_unrelated_lane_and_stop_cancels_pending_retry(stop_other_lane):
    clock = FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    held, waiting, other_done = Event(), Event(), Event()
    order = []

    class Lane:
        capacity_admission = admission

        def __call__(self, item):
            if item.workload_index == 1:
                assert held.wait(5)

            def operation():
                index = item.workload_index
                order.append(index)
                if index == 0:
                    held.set()
                    assert waiting.wait(5)
                if index == 2:
                    if stop_other_lane:
                        raise FakeWriterFailure()
                return result_for(item)
            try:
                return admission.run(operation)
            finally:
                if item.workload_index == 2:
                    other_done.set()

    def waiter(eligible, stopped):
        waiting.set()
        assert other_done.wait(5)  # The holder's lane claimed fresh work during this delay.
        if stop_other_lane:
            assert stopped.wait(5)
        clock.advance_to(eligible)

    cell = run_characterization(identity(2), Protection(ProtectionMode.PROTECTED, 1),
                                config(RetryPolicy.FIXED_BACKOFF), workload(3), (Lane(), Lane()),
                                admission=admission, clock_ns=clock, wait_until=waiter)
    assert order[:2] == [0, 2]
    request = cell.logical_requests[1]
    if stop_other_lane:
        assert request.terminal_state is LogicalTerminal.INCOMPLETE
        assert len(request.attempts) == 1 and request.final_terminal_ns is None
        assert request.attempts[0].next_retry_eligible_ns is not None
    else:
        assert order[-1] == 1
        assert request.terminal_state is LogicalTerminal.ACKNOWLEDGED_ACCEPTED


def test_wrong_gate_is_rejected_before_execution():
    clock = FakeClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    lane = PostgresLoadLane(0, connection(), capacity_admission=ObservedAdmission(1, clock_ns=clock))
    with pytest.raises(ValueError, match='same declared'):
        run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1), config(), workload(1),
                             (lane,), admission=admission, clock_ns=clock, wait_until=clock.wait_until)
