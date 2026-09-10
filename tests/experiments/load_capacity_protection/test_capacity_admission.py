"""Shared lane injection and PR4 observation seams; no PostgreSQL execution."""

from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.model import derive_accounting
from experiments.load_capacity_protection.postgres_characterization import run_characterization
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused
from tests.experiments.load_capacity_protection.test_postgres_characterization import (
    CountingClock, identity, result_for, workload,
)


def connection():
    return SimpleNamespace(
        closed=False, autocommit=False,
        info=SimpleNamespace(transaction_status=TransactionStatus.IDLE),
        cursor=Mock(side_effect=AssertionError('no SQL permitted')),
        rollback=Mock(side_effect=AssertionError('no rollback permitted')),
        commit=Mock(side_effect=AssertionError('no commit permitted')),
    )


def test_distinct_lanes_share_one_explicit_capacity_object(monkeypatch):
    admission = BoundedWriterAdmission(1)
    lanes = [PostgresLoadLane(i, connection(), capacity_admission=admission) for i in range(2)]
    assert lanes[0].connection is not lanes[1].connection
    assert lanes[0].writer is not lanes[1].writer
    assert all(lane.writer._capacity_admission is admission for lane in lanes)
    expected = result_for(workload(1)[0])

    def execute(**kwargs):
        with pytest.raises(WriterCapacityRefused):
            lanes[1](workload(1)[0])
        return expected

    monkeypatch.setattr(lanes[0].writer, '_execute_command', execute)
    assert lanes[0](workload(1)[0]).producer_value is expected
    monkeypatch.setattr(lanes[1].writer, '_execute_command', lambda **kwargs: expected)
    assert lanes[1](workload(1)[0]).producer_value is expected
    assert PostgresLoadLane(2, connection()).writer._capacity_admission is None
    for lane in lanes:
        lane.connection.cursor.assert_not_called()
        lane.connection.commit.assert_not_called()
        lane.connection.rollback.assert_not_called()


def test_existing_scheduler_and_admitted_operation_seam_distinguish_excess_offer(monkeypatch):
    clock = CountingClock()
    first_entered = Event()
    refused = Event()
    lock = Lock()
    observations = []
    calls = 0

    class ObservedAdmission(BoundedWriterAdmission):
        def run(self, operation):
            nonlocal calls
            record = {'offered': clock(), 'entry': None, 'exit': None, 'refused': False}
            with lock:
                call = calls
                calls += 1
            if call:
                assert first_entered.wait(5)

            def observed_operation():
                record['entry'] = clock()
                first_entered.set()
                try:
                    return operation()
                finally:
                    record['exit'] = clock()

            try:
                return super().run(observed_operation)
            except WriterCapacityRefused:
                assert record['entry'] is None
                record['refused'] = True
                refused.set()
                raise
            finally:
                record['terminal'] = clock()
                with lock:
                    observations.append(record)

    admission = ObservedAdmission(1)
    lanes = tuple(PostgresLoadLane(i, connection(), capacity_admission=admission) for i in range(2))
    items = workload(2)
    by_request = {item.signature.request_id: item for item in items}

    def execute(**kwargs):
        # An admitted call cannot finish until another offered call was refused.
        assert refused.wait(5)
        return result_for(by_request[kwargs['request_id']])

    for lane in lanes:
        monkeypatch.setattr(lane.writer, '_execute_command', execute)
    cell = run_characterization(identity(2), items, lanes, clock_ns=clock)
    assert calls == len(observations) == 2
    admitted = [o for o in observations if o['entry'] is not None]
    rejected = [o for o in observations if o['refused']]
    assert len(admitted) == len(rejected) == 1
    assert admitted[0]['offered'] < admitted[0]['entry'] < admitted[0]['exit'] < admitted[0]['terminal']
    assert rejected[0]['entry'] is rejected[0]['exit'] is None
    assert rejected[0]['offered'] < rejected[0]['terminal']
    assert BoundedWriterAdmission.run(admission, lambda: 'released') == 'released'

    # PR1's frozen ledger brackets offered calls, including refusal. PR4 must
    # adapt it, rather than label these outer intervals as admitted overlap.
    accounting = derive_accounting(cell)
    assert accounting.writer_entered == 2
    failures = [o for o in cell.observations if o.failure is not None]
    assert len(failures) == 1 and failures[0].result is None
    assert failures[0].measurement is None
