"""Concrete-gate observation is evidence only, including on failed clocks."""

from uuid import uuid4

import pytest

from src.pipeline.transactional.writer_capacity import (
    BoundedWriterAdmission, WriterAttemptIdentity, WriterCapacityEventKind as Kind,
    WriterCapacityObserver, WriterCapacityRefused,
)
from tests.unit.pipeline.test_postgres_writer_request import occupied


def identity(number=1):
    return WriterAttemptIdentity(uuid4(), "request", number)


@pytest.mark.parametrize("failure", [None, ValueError("writer"), KeyboardInterrupt()])
def test_body_release_completion_order_and_exact_result_or_error(failure):
    gate, observer, key, value = BoundedWriterAdmission(1), WriterCapacityObserver(), identity(), object()

    def body():
        assert [e.kind for e in observer.observations] == [Kind.CALL_STARTED, Kind.BODY_ENTERED]
        if failure is not None:
            raise failure
        return value

    with gate.observe_attempt(key, observer):
        if failure is None:
            assert gate.run(body) is value
        else:
            with pytest.raises(type(failure)) as raised:
                gate.run(body)
            assert raised.value is failure
    assert [e.kind for e in observer.observations] == [
        Kind.CALL_STARTED, Kind.BODY_ENTERED, Kind.BODY_EXITED, Kind.RELEASED, Kind.CALL_COMPLETED,
    ]
    assert {e.identity for e in observer.observations} == {key}
    assert gate.run(lambda: value) is value
    assert len(observer.observations) == 5  # Binding reset; ordinary calls allocate no evidence.


def test_refusal_observes_no_body_or_release():
    gate, observer = BoundedWriterAdmission(1), WriterCapacityObserver()
    with occupied(gate), gate.observe_attempt(identity(), observer):
        with pytest.raises(WriterCapacityRefused) as raised:
            gate.run(lambda: pytest.fail("no body"))
    assert vars(raised.value) == {}
    assert [e.kind for e in observer.observations] == [Kind.CALL_STARTED, Kind.REFUSED, Kind.CALL_COMPLETED]


@pytest.mark.parametrize("observer_error", [ValueError(), WriterCapacityRefused()])
@pytest.mark.parametrize("writer_error", [None, RuntimeError("original")])
def test_failed_observer_cannot_replace_writer_result_or_error(observer_error, writer_error):
    def broken_clock():
        raise observer_error

    observer = WriterCapacityObserver(clock_ns=broken_clock)
    gate, value = BoundedWriterAdmission(1), object()

    def body():
        if writer_error is not None:
            raise writer_error
        return value

    with gate.observe_attempt(identity(), observer):
        if writer_error is None:
            assert gate.run(body) is value
        else:
            with pytest.raises(RuntimeError) as raised:
                gate.run(body)
            assert raised.value is writer_error
    assert observer.observations == ()
    assert len(observer.failures) == 5
    assert {f.exception_class for f in observer.failures} == {type(observer_error).__name__}
    assert gate.run(lambda: value) is value


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit()])
@pytest.mark.parametrize("interrupt_read", range(1, 6))
def test_observer_process_interruption_propagates_and_releases_capacity(interruption, interrupt_read):
    gate, entered, reads = BoundedWriterAdmission(1), [], 0

    def clock():
        nonlocal reads
        reads += 1
        if reads == interrupt_read:
            raise interruption
        return reads

    observer = WriterCapacityObserver(clock_ns=clock)
    with pytest.raises(type(interruption)) as raised:
        with gate.observe_attempt(identity(), observer):
            gate.run(lambda: entered.append(True))

    assert raised.value is interruption
    assert observer.failures == ()
    assert entered == ([True] if interrupt_read >= 3 else [])
    observed = observer.observations
    assert gate.run(lambda: "released") == "released"
    assert observer.observations == observed


def test_nested_binding_is_restored_and_does_not_observe_other_gate():
    gate, other, observer = BoundedWriterAdmission(1), BoundedWriterAdmission(1), WriterCapacityObserver()
    outer, inner = identity(), identity(2)
    with gate.observe_attempt(outer, observer):
        other.run(lambda: None)
        with gate.observe_attempt(inner, observer):
            gate.run(lambda: None)
        gate.run(lambda: None)
    assert [e.identity for e in observer.observations if e.kind is Kind.BODY_ENTERED] == [inner, outer]


def test_release_precedes_release_and_completion_observation():
    from concurrent.futures import ThreadPoolExecutor
    gate, reads = BoundedWriterAdmission(1), []
    with ThreadPoolExecutor(max_workers=1) as pool:
        def clock():
            reads.append(1)
            if len(reads) in (4, 5):
                assert pool.submit(gate.run, lambda: "released").result(5) == "released"
            return len(reads)
        with gate.observe_attempt(identity(), WriterCapacityObserver(clock_ns=clock)):
            assert gate.run(lambda: "result") == "result"
    assert len(reads) == 5
