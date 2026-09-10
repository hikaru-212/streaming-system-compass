"""Causal PR4 schedules through real PR3 writer wrappers, with no database I/O."""

from dataclasses import fields, replace
from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.load_capacity_protection.model import LoadAcknowledgement
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from experiments.load_capacity_protection.pr4_characterization import (
    CharacterizationError, ObservedAdmission, _Attempt, run_characterization,
)
from experiments.load_capacity_protection.pr4_model import (
    Protection, ProtectionMode, derive_accounting, derive_overlap,
)
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused
from tests.experiments.load_capacity_protection.test_capacity_admission import connection
from tests.experiments.load_capacity_protection.test_postgres_characterization import (
    CountingClock, FakeWriterFailure, identity, result_for, workload,
)


def saturation(monkeypatch, *, n=5, bound=2, k=17):
    """Hold exactly bound bodies until all other items have been refused once."""
    clock = CountingClock()
    admission = ObservedAdmission(bound, clock_ns=clock)
    items = workload(k)
    retained = tuple(PostgresLoadLane(i, connection(), capacity_admission=admission) for i in range(n))
    held, all_refused = Event(), Event()
    lock = Lock()
    active = refused = 0
    calls = []
    by_request = {item.signature.request_id: item for item in items}

    def execute(**kwargs):
        nonlocal active
        with lock:
            active += 1
            if active == bound:
                held.set()
        assert all_refused.wait(5)
        return result_for(by_request[kwargs['request_id']])

    class Lane:
        capacity_admission = admission

        def __init__(self, target):
            self.target = target

        def __call__(self, item):
            nonlocal refused
            with lock:
                calls.append(item.workload_index)
            if item.workload_index >= bound:
                assert held.wait(5)
            try:
                return self.target(item)
            except WriterCapacityRefused:
                with lock:
                    refused += 1
                    if refused == k - bound:
                        all_refused.set()
                raise

    for lane in retained:
        monkeypatch.setattr(lane.writer, '_execute_command', execute)
    cell = run_characterization(
        identity(n), Protection(ProtectionMode.PROTECTED, bound), items,
        tuple(Lane(lane) for lane in retained), admission=admission, clock_ns=clock,
    )
    return cell, admission, retained, calls


def test_shared_bound_excess_offer_refusals_continue_and_do_not_become_writer_work(monkeypatch):
    cell, admission, retained, calls = saturation(monkeypatch)
    counts = derive_accounting(cell)
    assert cell.identity.configured_concurrency == 5 > admission.bound == 2
    assert all(lane.writer._capacity_admission is admission for lane in retained)
    assert counts.planned == counts.offered == counts.dispatched == counts.terminal == 17
    assert counts.capacity_attempts == 17
    assert counts.capacity_admitted == counts.protected_writer_entered == counts.writer_terminal == 2
    assert counts.acknowledged_accepted == 2 and counts.capacity_refused == 15
    assert counts.native_writer_failures == 0 and counts.residual_workload_indices == ()
    assert sorted(calls) == list(range(17))  # One offer/attempt, no replacement or retry.
    assert derive_overlap(cell, protected=True).maximum_complete_interval_overlap == 2
    assert derive_overlap(cell, protected=False).maximum_complete_interval_overlap > 2
    for row in cell.observations:
        assert row.dispatch_ns < row.capacity_attempt_ns < row.admission_return_ns < row.terminal_observation_ns
        if row.capacity_refused_ns is not None:
            assert not row.writer_entered
            assert row.protected_writer_entry_ns is row.protected_writer_exit_ns is None
            assert row.result is row.measurement is row.measurement_availability is row.failure is None
            assert row.acknowledgement is LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
        else:
            assert row.capacity_attempt_ns < row.capacity_admitted_ns < row.protected_writer_entry_ns
            assert row.protected_writer_exit_ns < row.admission_return_ns < row.public_call_exit_ns
            assert row.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
    assert BoundedWriterAdmission.run(admission, lambda: 'released') == 'released'
    for lane in retained:
        lane.connection.cursor.assert_not_called()
        lane.connection.rollback.assert_not_called()
        lane.connection.commit.assert_not_called()
    assert not any('authority' in f.name or 'retry' in f.name or 'replanning' in f.name
                   for f in fields(type(cell.observations[0])))


def test_unprotected_has_no_synthetic_capacity_or_protected_body_events(monkeypatch):
    clock = CountingClock()
    lane = PostgresLoadLane(0, connection(), capacity_admission=None)
    item, = workload(1)
    monkeypatch.setattr(lane.writer, '_execute_command', lambda **kw: result_for(item))
    cell = run_characterization(identity(1), Protection(ProtectionMode.UNPROTECTED, None),
                                (item,), (lane,), admission=None, clock_ns=clock)
    row, = cell.observations
    counts = derive_accounting(cell)
    assert counts.capacity_attempts is counts.capacity_admitted is counts.capacity_refused is None
    assert counts.protected_writer_entered is None
    assert counts.writer_entered == counts.acknowledged_accepted == 1
    for name in ('capacity_attempt_ns', 'capacity_admitted_ns', 'capacity_refused_ns',
                 'protected_writer_entry_ns', 'protected_writer_exit_ns', 'admission_return_ns'):
        assert getattr(row, name) is None
    assert row.measurement is not None


@pytest.mark.parametrize('error', [FakeWriterFailure(), WriterCapacityRefused('from inside body')])
def test_admitted_native_failure_stops_claims_without_refusal_relabeling(monkeypatch, error):
    clock = CountingClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    lane = PostgresLoadLane(0, connection(), capacity_admission=admission)
    monkeypatch.setattr(lane.writer, '_execute_command', Mock(side_effect=error))
    cell = run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1),
                                workload(3), (lane,), admission=admission, clock_ns=clock)
    failed = cell.observations[0]
    counts = derive_accounting(cell)
    assert failed.capacity_admitted_ns is not None and failed.capacity_refused_ns is None
    assert failed.failure.exception_class.endswith(type(error).__name__)
    assert failed.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert failed.result is failed.measurement is None
    assert counts.native_writer_failures == 1 and counts.capacity_refused == 0
    assert counts.residual_workload_indices == (1, 2)
    assert BoundedWriterAdmission.run(admission, lambda: True)


def test_adapter_preserves_value_exception_identity_and_post_release_boundary():
    clock = CountingClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    value, error = object(), FakeWriterFailure()
    first = _Attempt()
    with admission.observe(first):
        assert admission.run(lambda: value) is value
    assert first.times['protected_writer_exit_ns'] < first.times['admission_return_ns']
    second = _Attempt()
    with admission.observe(second), pytest.raises(FakeWriterFailure) as raised:
        admission.run(Mock(side_effect=error))
    assert raised.value is error
    assert BoundedWriterAdmission.run(admission, lambda: value) is value


@pytest.mark.parametrize('kind', ['bypass', 'double', 'wrong_return', 'pre_entry'])
def test_harness_contract_defects_are_not_native_failures(kind):
    clock = CountingClock()
    admission = ObservedAdmission(1, clock_ns=clock)
    item, = workload(1)

    class Lane:
        capacity_admission = admission

        def __call__(self, item):
            if kind == 'pre_entry':
                raise RuntimeError('not a writer failure')
            if kind == 'bypass':
                return result_for(item)
            result = admission.run(lambda: object() if kind == 'wrong_return' else result_for(item))
            if kind == 'double':
                admission.run(lambda: result)
            return result

    with pytest.raises(CharacterizationError) as raised:
        run_characterization(identity(1), Protection(ProtectionMode.PROTECTED, 1),
                             (item,), (Lane(),), admission=admission, clock_ns=clock)
    assert raised.value.failures
    assert derive_accounting(raised.value.cell).native_writer_failures == 0
    assert derive_accounting(raised.value.cell).residual_workload_indices == (0,)


def test_rejects_per_lane_gates_and_unprotected_gate_before_execution():
    clock = CountingClock()
    shared = ObservedAdmission(1, clock_ns=clock)
    lanes = tuple(PostgresLoadLane(i, connection(), capacity_admission=ObservedAdmission(1, clock_ns=clock))
                  for i in range(2))
    with pytest.raises(ValueError, match='same declared'):
        run_characterization(identity(2), Protection(ProtectionMode.PROTECTED, 1),
                             workload(2), lanes, admission=shared, clock_ns=clock)
    with pytest.raises(ValueError, match='unprotected'):
        run_characterization(identity(2), Protection(ProtectionMode.UNPROTECTED, None),
                             workload(2), lanes, admission=shared, clock_ns=clock)


def test_refusal_model_rejects_fabricated_producer_evidence(monkeypatch):
    cell, *_ = saturation(monkeypatch)
    refused = next(o for o in cell.observations if o.capacity_refused_ns is not None)
    accepted = next(o for o in cell.observations if o.result is not None)
    with pytest.raises(ValueError, match='writer evidence'):
        replace(refused, result=accepted.result)
    with pytest.raises(ValueError, match='prerequisite'):
        replace(refused, protected_writer_entry_ns=refused.capacity_refused_ns)
