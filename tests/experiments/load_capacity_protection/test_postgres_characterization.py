"""Causal schedules for the experiment harness; no database or real-time claims."""

from dataclasses import fields, replace
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event, Lock, current_thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection import postgres_characterization as harness
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement,
    LoadCellIdentity,
    LoadOuterPhase,
    LoadWorkItem,
    derive_accounting,
    derive_timing,
    derive_writer_overlap,
)
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.compass.transition.types import ValidationMode
from src.compass.transition.validators import FullProofValidator
from src.pipeline.transactional.postgres_admission import PostgresOptimisticAdmissionGate
from src.pipeline.transactional.postgres_unit_of_work import PostgresWriteSideUnitOfWork
from src.pipeline.transactional.postgres_write_side_config import ValidationPlacement
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSideMeasurementDelivery,
    PostgresWriteSidePhaseMeasurement,
    PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


# Deadlines only fail broken causal schedules; they never create the ordering.
TEST_DEADLINE = 5


class CountingClock:
    def __init__(self):
        self.lock = Lock()
        self.value = 0

    def __call__(self):
        with self.lock:
            self.value += 1
            return self.value


def workload(k):
    return tuple(
        LoadWorkItem(index, RequestSignature(
            f"request-{index}", CommandType.CREATE, f"order-{index}", Decimal("10.00"),
        ))
        for index in range(k)
    )


def identity(n):
    return LoadCellIdentity("test-run", "test-cell", 0, n)


def result_for(item, *, replay=False):
    signature = item.signature
    event = OrderEvent(
        f"event-{item.workload_index}", signature.request_id, signature.order_id,
        1, EventType.CREATED, signature.amount, 123, Proof(OrderStatus.INIT, 0, None),
    )
    return PostgresWriteSideResult(
        PostgresWriteSideOutcome.REPLAY if replay else PostgresWriteSideOutcome.ACCEPTED,
        event,
        IdempotencyDecision(
            IdempotencyVerdict.REPLAY if replay else IdempotencyVerdict.MISS,
            "deterministic fixture",
            IdempotencyRecord(signature, event) if replay else None,
        ),
    )


class RecordingLane:
    def __init__(self, rendezvous=None):
        self.calls = []
        self.thread_ids = set()
        self.active = False
        self.rendezvous = rendezvous

    def __call__(self, item):
        assert not self.active
        self.active = True
        try:
            self.calls.append(item)
            self.thread_ids.add(current_thread().ident)
            if self.rendezvous is not None:
                self.rendezvous.wait(timeout=TEST_DEADLINE)
            return result_for(item)
        finally:
            self.active = False


def test_execution_and_imports_use_the_load_worktree():
    root = Path(__file__).resolve().parents[3]
    assert Path.cwd() == root
    assert Path(harness.__file__).resolve().is_relative_to(root)
    import src.pipeline.transactional.postgres_write_side as writer_module
    assert Path(writer_module.__file__).resolve().is_relative_to(root)


@pytest.mark.parametrize("n", [1, 3])
def test_fixed_k_and_unique_execution_do_not_depend_on_worker_count(n):
    prepared = workload(7)
    lanes = tuple(RecordingLane() for _ in range(n))
    result = harness.run_characterization(identity(n), prepared, lanes, clock_ns=CountingClock())
    calls = [item for lane in lanes for item in lane.calls]
    assert len(calls) == len(set(calls)) == len(prepared)
    assert set(calls) == set(prepared)
    assert result.planned is prepared
    assert tuple(obs.item for obs in result.observations) == prepared
    counts = derive_accounting(result)
    assert counts.planned == counts.offered == counts.dispatched == counts.terminal == 7
    assert counts.acknowledged_accepted == 7
    assert counts.residual_workload_indices == ()


def test_each_persistent_lane_resource_is_reused_on_one_thread():
    rendezvous = Barrier(3)
    lanes = tuple(RecordingLane(rendezvous) for _ in range(3))
    result = harness.run_characterization(
        identity(3), workload(6), lanes, clock_ns=CountingClock(),
    )
    assert derive_accounting(result).acknowledged_accepted == 6
    assert [len(lane.calls) for lane in lanes] == [2, 2, 2]
    assert all(len(lane.thread_ids) == 1 and not lane.active for lane in lanes)
    assert len(set.union(*(lane.thread_ids for lane in lanes))) == 3


def test_fast_lane_replenishes_before_slow_lane_finishes_without_global_batch_barrier():
    slow_entered = Event()
    fast_replenished = Event()
    slow_finished = Event()
    fast_calls = []

    def slow(item):
        slow_entered.set()
        try:
            assert fast_replenished.wait(TEST_DEADLINE)
            return result_for(item)
        finally:
            slow_finished.set()

    def fast(item):
        fast_calls.append(item)
        if len(fast_calls) == 1:
            assert slow_entered.wait(TEST_DEADLINE)
        else:
            assert not slow_finished.is_set()
            fast_replenished.set()
        return result_for(item)

    result = harness.run_characterization(
        identity(2), workload(3), (fast, slow), clock_ns=CountingClock(),
    )
    assert derive_accounting(result).acknowledged_accepted == 3
    assert len(fast_calls) == 2
    fast_first, fast_next = sorted(
        (obs for obs in result.observations if obs.lane_id == 0),
        key=lambda obs: obs.dispatch_ns,
    )
    slow_observation, = (obs for obs in result.observations if obs.lane_id == 1)
    assert fast_first.terminal_observation_ns < fast_next.dispatch_ns
    assert fast_next.writer_entry_ns < slow_observation.writer_exit_ns
    assert fast_next.offer_ns < slow_observation.writer_entry_ns < fast_next.dispatch_ns
    assert derive_writer_overlap(result).maximum_complete_interval_overlap == 2


def test_single_offer_boundary_precedes_dispatch_and_pending_scheduling_wait():
    lane = RecordingLane()
    result = harness.run_characterization(
        identity(1), workload(3), (lane,), clock_ns=CountingClock(),
    )
    assert {obs.offer_ns for obs in result.observations} == {1}
    for obs in result.observations:
        assert obs.offer_ns < obs.dispatch_ns < obs.writer_entry_ns
        assert obs.writer_entry_ns < obs.writer_exit_ns < obs.terminal_observation_ns
        assert obs.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
        assert obs.verification is None
    first, second, third = result.observations
    assert second.offer_ns < first.writer_entry_ns < first.writer_exit_ns < second.dispatch_ns
    assert first.terminal_observation_ns < second.dispatch_ns
    assert second.terminal_observation_ns < third.dispatch_ns
    assert derive_timing(second).scheduler_queue_wait_ns > derive_timing(first).scheduler_queue_wait_ns


def test_normal_replay_is_a_completion_without_new_acknowledged_work():
    def replay(item):
        return result_for(item, replay=True)

    result = harness.run_characterization(
        identity(1), workload(2), (replay,), clock_ns=CountingClock(),
    )
    counts = derive_accounting(result)
    assert counts.terminal == 2
    assert counts.acknowledged_accepted == 0
    assert all(
        obs.acknowledgement is LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
        for obs in result.observations
    )


class FakeWriterFailure(Exception):
    sqlstate = "08006"

    def __str__(self):
        raise AssertionError("exception text must never be inspected")


@pytest.mark.parametrize("sqlstate, expected", [("08006", "08006"), (None, None), ("unsafe text", None)])
def test_writer_failure_retains_evidence_and_stops_claims_without_reusing_resource(sqlstate, expected):
    calls = []

    def invoke(item):
        calls.append(item)
        if item.workload_index == 1:
            error = FakeWriterFailure()
            error.sqlstate = sqlstate
            raise error
        return result_for(item)

    result = harness.run_characterization(
        identity(1), workload(4), (invoke,), clock_ns=CountingClock(),
    )
    counts = derive_accounting(result)
    assert [item.workload_index for item in calls] == [0, 1]
    assert counts.offered == counts.planned == 4
    assert counts.dispatched == counts.writer_entered == counts.terminal == 2
    assert counts.acknowledged_accepted == 1
    assert counts.residual_workload_indices == (2, 3)
    failed = result.observations[1]
    assert failed.result is failed.measurement is failed.measurement_availability is None
    assert failed.failure.exception_class == f"{__name__}.FakeWriterFailure"
    assert failed.failure.sqlstate == expected
    assert failed.failure.phase is LoadOuterPhase.WRITER_CALL
    assert failed.failure.writer_entered
    assert failed.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert failed.writer_entry_ns < failed.writer_exit_ns < failed.terminal_observation_ns
    for residual in result.observations[2:]:
        assert residual.offer_ns == failed.offer_ns
        assert residual.dispatch_ns is residual.writer_entry_ns is None
        assert residual.terminal_observation_ns is residual.failure is None


def test_already_entered_calls_are_retained_when_failures_stop_further_claims():
    both_entered = Barrier(2)

    def make_lane():
        def invoke(item):
            both_entered.wait(timeout=TEST_DEADLINE)
            raise FakeWriterFailure()
        return invoke

    result = harness.run_characterization(
        identity(2), workload(5), (make_lane(), make_lane()), clock_ns=CountingClock(),
    )
    counts = derive_accounting(result)
    assert counts.terminal == counts.dispatched == 2
    assert counts.residual_workload_indices == (2, 3, 4)
    overlap = derive_writer_overlap(result)
    assert overlap.maximum_complete_interval_overlap == 2
    assert overlap.unclosed_interval_count == 0


def test_invalid_return_is_harness_defect_and_preserves_prior_accepted_result():
    def invoke(item):
        return result_for(item) if item.workload_index == 0 else None

    with pytest.raises(harness.LoadHarnessError) as raised:
        harness.run_characterization(
            identity(1), workload(3), (invoke,), clock_ns=CountingClock(),
        )
    result = raised.value.cell
    assert derive_accounting(result).acknowledged_accepted == 1
    assert derive_accounting(result).residual_workload_indices == (1, 2)
    assert result.observations[1].writer_exit_ns is not None
    assert result.observations[1].result is result.observations[1].failure is None
    assert raised.value.failures[0].exception_class == "builtins.TypeError"
    assert raised.value.failures[0].phase is LoadOuterPhase.TERMINAL_OBSERVATION


@pytest.mark.parametrize("failing_tick, expected_dispatch", [(6, None), (7, 6)])
def test_new_claim_observation_failure_cannot_inherit_previous_accepted_evidence(
    failing_tick, expected_dispatch,
):
    class NextRequestFailingClock(CountingClock):
        def __call__(self):
            value = super().__call__()
            # Request 0 uses ticks 2–5; request 1 dispatch/entry use 6/7.
            if value == failing_tick:
                raise RuntimeError("test current-request observation failure")
            return value

    lane = RecordingLane()
    with pytest.raises(harness.LoadHarnessError) as raised:
        harness.run_characterization(
            identity(1), workload(3), (lane,), clock_ns=NextRequestFailingClock(),
        )
    previous, current, pending = raised.value.cell.observations
    assert [item.workload_index for item in lane.calls] == [0]
    assert previous.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert previous.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
    assert previous.terminal_observation_ns == 5
    assert current.item.workload_index == 1
    assert current.dispatch_ns == expected_dispatch
    assert current.writer_entry_ns is current.writer_exit_ns is None
    assert current.result is current.failure is current.terminal_observation_ns is None
    assert current.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert pending.dispatch_ns is None
    failure, = raised.value.failures
    assert failure.exception_class == "builtins.RuntimeError"
    assert failure.phase is LoadOuterPhase.DISPATCHED
    assert failure.writer_entered is False
    assert failure.acknowledgement is LoadAcknowledgement.UNKNOWN
    counts = derive_accounting(raised.value.cell)
    assert counts.planned == counts.offered == 3
    assert counts.writer_entered == counts.terminal == counts.acknowledged_accepted == 1
    assert counts.residual_workload_indices == (1, 2)


def test_terminal_recording_failure_cannot_erase_already_retained_accepted_return():
    class TerminalFailingClock(CountingClock):
        def __call__(self):
            value = super().__call__()
            if value == 5:
                raise RuntimeError("test observation failure")
            return value

    lane = RecordingLane()
    with pytest.raises(harness.LoadHarnessError) as raised:
        harness.run_characterization(
            identity(1), workload(2), (lane,), clock_ns=TerminalFailingClock(),
        )
    observed = raised.value.cell.observations[0]
    assert observed.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert observed.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
    assert observed.terminal_observation_ns is None
    assert observed.failure is None
    assert len(lane.calls) == 1
    assert derive_accounting(raised.value.cell).residual_workload_indices == (0, 1)
    assert raised.value.failures[0].acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED


@pytest.mark.parametrize("k", [0, 1])
def test_k_less_than_n_leaves_unused_lanes_harmless_and_does_not_invent_overlap(k):
    lanes = tuple(RecordingLane() for _ in range(4))
    result = harness.run_characterization(
        identity(4), workload(k), lanes, clock_ns=CountingClock(),
    )
    assert sum(len(lane.calls) for lane in lanes) == k
    assert derive_writer_overlap(result).maximum_complete_interval_overlap == k


def test_touching_half_open_call_intervals_do_not_create_false_overlap():
    ticks = iter((0, 0, 1, 5, 5, 5, 5, 9, 9))
    result = harness.run_characterization(
        identity(1), workload(2), (RecordingLane(),), clock_ns=lambda: next(ticks),
    )
    first, second = result.observations
    assert first.writer_exit_ns == second.writer_entry_ns == 5
    assert derive_writer_overlap(result).maximum_complete_interval_overlap == 1


@pytest.mark.parametrize("available", [True, False])
def test_measured_delivery_reuses_exact_production_result_and_measurement(available):
    measured = PostgresWriteSidePhaseMeasurement(PostgresWriteSidePhaseMeasurementState.MEASURED, 1)
    phases = {field.name: measured for field in fields(PostgresWriteSideMeasurement)}
    phases["rollback_finalization"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_REACHED,
    )
    phases["pessimistic_advisory_try_lock_call"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_APPLICABLE,
    )
    measurement = PostgresWriteSideMeasurement(**phases) if available else None
    availability = (
        PostgresWriteSideMeasurementAvailability.AVAILABLE if available
        else PostgresWriteSideMeasurementAvailability.UNAVAILABLE
    )
    prepared = workload(1)
    producer_result = result_for(prepared[0])

    def invoke(item):
        return PostgresWriteSideMeasurementDelivery(producer_result, availability, measurement)

    result = harness.run_characterization(
        identity(1), prepared, (invoke,), clock_ns=CountingClock(),
    )
    observed, = result.observations
    assert observed.result is producer_result
    assert observed.measurement is measurement
    assert observed.measurement_availability is availability
    assert observed.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED


def test_invalid_workload_and_lane_ownership_are_rejected_before_execution():
    lane = RecordingLane()
    with pytest.raises(ValueError, match="duplicate"):
        harness.run_characterization(identity(1), (workload(1)[0],) * 2, (lane,))
    with pytest.raises(ValueError, match="one callable"):
        harness.run_characterization(identity(2), workload(1), (lane,))
    with pytest.raises(ValueError, match="distinct resource owners"):
        harness.run_characterization(identity(2), workload(1), (lane, lane))
    with pytest.raises(ValueError, match="distinct resource owners"):
        harness.run_characterization(identity(2), workload(1), (lane.__call__, lane.__call__))
    assert lane.calls == []


@pytest.fixture
def unconnected_lane_resource():
    # A property-only stand-in: any SQL or lifecycle operation fails this unit test.
    return SimpleNamespace(
        autocommit=False, closed=False,
        info=SimpleNamespace(transaction_status=TransactionStatus.IDLE),
        cursor=Mock(side_effect=AssertionError("unit test must not execute SQL")),
        close=Mock(side_effect=AssertionError("resource cleanup belongs to caller")),
        commit=Mock(side_effect=AssertionError("unit test must not commit")),
        rollback=Mock(side_effect=AssertionError("unit test must not roll back")),
    )


def test_postgres_lane_constructs_explicit_current_composition_without_io(unconnected_lane_resource):
    lane = PostgresLoadLane(0, unconnected_lane_resource)
    other = PostgresLoadLane(1, unconnected_lane_resource)
    assert lane.lane_id == 0
    assert lane.connection is unconnected_lane_resource
    assert lane.writer is not other.writer
    assert lane.validation_runtime is not other.validation_runtime
    assert lane.config.validation_mode is ValidationMode.STRICT
    assert lane.config.validation_placement is ValidationPlacement.PRE_TRANSACTION
    assert lane.validation_runtime.mode is ValidationMode.STRICT
    validator = lane.validation_runtime.dispatcher.strict_validator
    assert type(validator) is FullProofValidator
    assert lane.validation_runtime.dispatcher.select(None, ValidationMode.STRICT) is validator
    # Inspect actual constructor wiring, not only experiment metadata.
    assert lane.writer._connection is lane.connection
    assert lane.writer._config is lane.config
    assert lane.writer._validation_runtime is lane.validation_runtime
    uow = PostgresWriteSideUnitOfWork(lane.connection)
    gate = lane.writer._admission_gate_factory(uow)
    assert type(gate) is PostgresOptimisticAdmissionGate
    assert gate.event_store is uow.event_store
    assert gate.event_store.connection is lane.connection
    unconnected_lane_resource.cursor.assert_not_called()
    unconnected_lane_resource.close.assert_not_called()


def test_postgres_lane_forwards_exact_signature_and_delivery_on_retained_writer(
    unconnected_lane_resource, monkeypatch,
):
    lane = PostgresLoadLane(0, unconnected_lane_resource)
    retained_writer = lane.writer
    item = workload(1)[0]
    delivery = PostgresWriteSideMeasurementDelivery(
        result_for(item), PostgresWriteSideMeasurementAvailability.UNAVAILABLE, None,
    )
    measured_create = Mock(return_value=delivery)
    monkeypatch.setattr(retained_writer, "create_order_with_measurement", measured_create)
    for item in workload(2):
        assert lane(item) is delivery
        forwarded = measured_create.call_args.kwargs
        assert forwarded["request_id"] is item.signature.request_id
        assert forwarded["order_id"] is item.signature.order_id
        assert forwarded["amount"] is item.signature.amount
        assert lane.writer is retained_writer
    assert measured_create.call_count == 2
    pay = replace(item, signature=replace(item.signature, command_type=CommandType.PAY))
    with pytest.raises(ValueError, match="only CREATE"):
        lane(pay)
    assert measured_create.call_count == 2
    error = FakeWriterFailure()
    measured_create.side_effect = error
    with pytest.raises(FakeWriterFailure) as raised:
        lane(item)
    assert raised.value is error
    for operation in ("cursor", "close", "commit", "rollback"):
        getattr(unconnected_lane_resource, operation).assert_not_called()


@pytest.mark.parametrize("state", ["closed", "autocommit", "transaction"])
def test_postgres_lane_rejects_unready_resource_without_changing_it(unconnected_lane_resource, state):
    if state == "transaction":
        unconnected_lane_resource.info.transaction_status = TransactionStatus.INTRANS
    else:
        setattr(unconnected_lane_resource, state, True)
    with pytest.raises(ValueError):
        PostgresLoadLane(0, unconnected_lane_resource)
    for operation in ("cursor", "close", "commit", "rollback"):
        getattr(unconnected_lane_resource, operation).assert_not_called()
