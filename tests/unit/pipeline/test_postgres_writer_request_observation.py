"""Real builder/owner/public-writer seams, with deterministic fake storage."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, get_ident

import pytest

from src.core.order.enums import CommandType
from src.pipeline.postgres_writer_request import WriterRetryEventKind as RetryKind
from src.pipeline.transactional import postgres_write_side_measurement_instrumentation as instrumentation
from src.pipeline.transactional.postgres_write_side import PostgresTransactionalWriteSide
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementAvailability as Availability
from src.pipeline.transactional.writer_capacity import (
    BoundedWriterAdmission, WriterCapacityEventKind as Kind, WriterCapacityObserver, WriterCapacityRefused,
)
from tests.unit.pipeline.test_postgres_writer_request import (
    Clock, POLICY, build, events, occupied, _accepted_result, _signature,
)


@pytest.mark.parametrize("policy", [None, POLICY])
@pytest.mark.parametrize("command", list(CommandType))
def test_measured_delivery_is_separate_and_primary_identity_unchanged(monkeypatch, policy, command):
    signature = _signature(command_type=command)
    result = _accepted_result(signature)
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", lambda *a, **k: result)
    observer = WriterCapacityObserver()
    owner = build(BoundedWriterAdmission(1), Clock(), signature=signature, policy=policy,
                  capacity_observer=observer, measure_writer=True)
    assert owner.measurements == ()
    assert owner.invoke() is result
    measured, = owner.measurements
    assert measured.delivery.producer_value is result
    assert measured.delivery.availability is Availability.AVAILABLE
    assert measured.identity == observer.observations[0].identity
    assert measured.identity.logical_invocation_id == owner.observations[0].logical_invocation_id
    assert [e.attempt_number for e in events(owner, RetryKind.ATTEMPT_DISPATCHED)] == [1]


def test_measurement_clock_failure_preserves_result_and_unavailability(monkeypatch):
    result = _accepted_result(_signature())
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", lambda *a, **k: result)
    def fail():
        raise WriterCapacityRefused("instrumentation is not admission")
    monkeypatch.setattr(instrumentation.time, "perf_counter_ns", fail)
    owner = build(BoundedWriterAdmission(1), Clock(), measure_writer=True)
    assert owner.invoke() is result
    delivery = owner.measurements[0].delivery
    assert delivery.availability is Availability.UNAVAILABLE
    assert delivery.measurement is None
    assert not events(owner, RetryKind.CAPACITY_REFUSED)


def test_observer_failure_cannot_authorize_retry(monkeypatch):
    result = _accepted_result(_signature())
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", lambda *a, **k: result)
    def fail():
        raise WriterCapacityRefused()
    observer = WriterCapacityObserver(clock_ns=fail)
    owner = build(BoundedWriterAdmission(1), Clock(), capacity_observer=observer)
    assert owner.invoke() is result
    assert not events(owner, RetryKind.CAPACITY_REFUSED)
    assert len(observer.failures) == 5


def test_measured_refusal_retries_after_call_completion_with_exact_identity(monkeypatch):
    gate, clock = BoundedWriterAdmission(1), Clock()
    observer = WriterCapacityObserver(clock_ns=lambda: int(clock.now * 1e9))
    result = _accepted_result(_signature())
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", lambda *a, **k: result)
    with occupied(gate) as free:
        def wait(delay):
            assert observer.observations[-1].kind is Kind.CALL_COMPLETED
            assert owner.measurements == ()
            assert not any(e.kind is Kind.BODY_ENTERED for e in observer.observations)
            free()
            assert gate.run(lambda: True)
            clock.wait(delay)
        owner = build(gate, clock, capacity_observer=observer, measure_writer=True, wait=wait)
        assert owner.invoke() is result
    assert events(owner, RetryKind.ELIGIBILITY_DECIDED)[0].eligible is True
    assert {e.identity.logical_invocation_id for e in observer.observations} == {
        owner.observations[0].logical_invocation_id,
    }
    assert [e.identity.attempt_number for e in observer.observations if e.kind is Kind.CALL_STARTED] == [1, 2]
    assert owner.measurements[0].identity.attempt_number == 2


def test_shared_concrete_gate_correlates_concurrent_threads_without_cross_talk(monkeypatch):
    gate, observer, barrier = BoundedWriterAdmission(2), WriterCapacityObserver(), Barrier(2)
    bodies = {}
    def body(writer, **kwargs):
        bodies[kwargs["request_id"]] = get_ident()
        barrier.wait(5)
        return _accepted_result(replace(_signature(), request_id=kwargs["request_id"]))
    monkeypatch.setattr(PostgresTransactionalWriteSide, "_execute_command", body)
    owners = [build(gate, Clock(), capacity_observer=observer,
                    signature=replace(_signature(), request_id=f"request-{i}")) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(owner.invoke) for owner in owners]
        for future in futures:
            future.result(5)
    for owner in owners:
        logical_id = owner.observations[0].logical_invocation_id
        observations = [e for e in observer.observations if e.identity.logical_invocation_id == logical_id]
        assert len(observations) == 5
        assert {e.thread_id for e in observations} == {bodies[observations[0].identity.request_id]}
        assert {e.identity.attempt_number for e in observations} == {1}
