"""Deterministic PR4 instrumentation tests for the frozen PR3 contract."""

from dataclasses import fields
from decimal import Decimal
import hashlib
from inspect import getdoc, signature
import json
from pathlib import Path
from typing import cast

import pytest
from psycopg import Connection

from src.compass.transition.runtime import ValidationRuntime
from src.compass.transition.types import EnforcementAction
from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideExecution,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionTrace,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementDelivery,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurementState,
)
from src.pipeline.transactional import (
    postgres_write_side as write_side_module,
    postgres_write_side_measurement as measurement_contract,
    postgres_write_side_measurement_instrumentation as instrumentation,
)
from src.storage.idempotency_store import IdempotencyVerdict
from src.storage.postgres_event_store import PostgresEventStore
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_characterization import (
    _CommitFailure,
    _FakeConnection,
    _ManualClock,
    _MeasuredRejectingGate,
    _MeasuredValidationRuntime,
    _Phase,
    _Probe,
    _ProducerFailure,
    _RollbackFailure,
    _Scenario,
    _install_source_boundary_probe,
)


State = PostgresWriteSidePhaseMeasurementState
Availability = PostgresWriteSideMeasurementAvailability
MeasurementPhase = instrumentation._PostgresWriteSideMeasurementPhase
Recorder = instrumentation._PostgresWriteSideMeasurementRecorder
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _require_result(
    delivery: PostgresWriteSideMeasurementDelivery,
) -> PostgresWriteSideResult:
    """Narrow one delivery to the legacy producer-result shape for assertions."""
    producer_value = delivery.producer_value
    assert isinstance(producer_value, PostgresWriteSideResult)
    return producer_value


def _require_execution(
    delivery: PostgresWriteSideMeasurementDelivery,
) -> PostgresWriteSideExecution:
    """Narrow one delivery to the traced producer-execution shape for assertions."""
    producer_value = delivery.producer_value
    assert isinstance(producer_value, PostgresWriteSideExecution)
    return producer_value


def _require_measurement(
    delivery: PostgresWriteSideMeasurementDelivery,
) -> PostgresWriteSideMeasurement:
    """Narrow one available delivery to its immutable measurement snapshot."""
    measurement = delivery.measurement
    assert measurement is not None
    return measurement


def _build_preview_writer(
    connection: _FakeConnection,
) -> PostgresTransactionalWriteSide:
    scenario = connection.scenario
    if (
        scenario.placement is ValidationPlacement.PRE_TRANSACTION
        and not scenario.preparation_admitted
    ):
        gate_factory = lambda uow: _MeasuredRejectingGate(connection)
    elif scenario.placement is ValidationPlacement.IN_TRANSACTION:
        gate_factory = lambda uow: PostgresPessimisticAdmissionGate(
            connection=uow.connection,
            event_store=uow.event_store,
        )
    else:
        gate_factory = lambda uow: PostgresOptimisticAdmissionGate(
            uow.event_store
        )

    return PostgresTransactionalWriteSide(
        connection=cast(Connection, connection),
        validation_runtime=cast(
            ValidationRuntime,
            _MeasuredValidationRuntime(connection),
        ),
        admission_gate_factory=gate_factory,
        config=PostgresWriteSideConfig(
            validation_placement=scenario.placement
        ),
    )


def _install_preview_boundaries(monkeypatch) -> None:
    _install_source_boundary_probe(monkeypatch)

    def try_lock_stream(gate, order_id: str) -> bool:
        connection = cast(_FakeConnection, gate.connection)
        connection.probe.clock.advance(5)
        return connection.scenario.preparation_admitted

    monkeypatch.setattr(
        PostgresPessimisticAdmissionGate,
        "_try_lock_stream",
        try_lock_stream,
    )


def _execute_preview(
    monkeypatch,
    scenario: _Scenario,
    *,
    traced: bool = False,
    fail_final_construction: bool = False,
    whole_clock_failure: str | None = None,
):
    if whole_clock_failure not in {None, "start", "stop"}:
        raise ValueError("whole_clock_failure must be None, 'start', or 'stop'")

    _install_preview_boundaries(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(scenario, probe)
    writer = _build_preview_writer(connection)

    class ControlledClock:
        def __init__(self) -> None:
            self.fail_next = whole_clock_failure == "start"

        def __call__(self) -> int:
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError("preview whole-invocation clock failed")
            return probe.clock.perf_counter_ns()

    controlled_clock = ControlledClock()
    monkeypatch.setattr(
        instrumentation.time,
        "perf_counter_ns",
        controlled_clock,
    )

    producer_values = []
    original_execute = writer._execute_command

    def capture_producer_value(**kwargs):
        producer_value = original_execute(**kwargs)
        producer_values.append(producer_value)
        if whole_clock_failure == "stop":
            controlled_clock.fail_next = True
        return producer_value

    monkeypatch.setattr(writer, "_execute_command", capture_producer_value)

    if fail_final_construction:
        def fail_measurement(_recorder):
            raise RuntimeError("preview final measurement construction failed")

        monkeypatch.setattr(Recorder, "_build_measurement", fail_measurement)

    method = (
        writer.create_order_with_trace_and_measurement
        if traced
        else writer.create_order_with_measurement
    )
    delivery = method(
        request_id="pr4-preview-request",
        order_id="pr4-preview-order",
        amount=Decimal("100.00"),
    )
    return delivery, connection, probe, producer_values


def _assert_phase_states(
    measurement,
    *,
    measured: set[str],
    not_applicable: set[str],
) -> None:
    for field in fields(measurement):
        phase = getattr(measurement, field.name)
        if field.name in measured:
            assert phase.state is State.MEASURED
            assert phase.elapsed_ns is not None
        elif field.name in not_applicable:
            assert phase.state is State.NOT_APPLICABLE
            assert phase.elapsed_ns is None
        else:
            assert phase.state is State.NOT_REACHED
            assert phase.elapsed_ns is None


def test_pre_accepted_populates_exact_pr3_surface(monkeypatch) -> None:
    delivery, connection, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
    )

    assert delivery.availability is Availability.AVAILABLE
    assert _require_result(delivery).outcome is PostgresWriteSideOutcome.ACCEPTED
    assert connection.committed is True
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        },
        not_applicable={"pessimistic_advisory_try_lock_call"},
    )


def test_pre_preliminary_replay_is_measured_without_business_uow(monkeypatch) -> None:
    delivery, connection, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
        ),
    )

    assert _require_result(delivery).outcome is PostgresWriteSideOutcome.REPLAY
    assert connection.commit_calls == 0
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        not_applicable={"pessimistic_advisory_try_lock_call"},
    )


def test_pre_stale_append_measures_normal_rollback_path(monkeypatch) -> None:
    delivery, connection, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
            append_admitted=False,
        ),
    )

    assert (
        _require_result(delivery).outcome
        is PostgresWriteSideOutcome.ADMISSION_REJECTED
    )
    assert connection.committed is False
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "append_admission_call",
            "rollback_finalization",
        },
        not_applicable={"pessimistic_advisory_try_lock_call"},
    )


def test_in_pessimistic_accepted_populates_exact_pr3_surface(monkeypatch) -> None:
    delivery, connection, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
    )

    assert delivery.availability is Availability.AVAILABLE
    assert _require_result(delivery).outcome is PostgresWriteSideOutcome.ACCEPTED
    assert connection.committed is True
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        },
        not_applicable={
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    )


def test_in_pessimistic_non_acquisition_stops_before_history_and_validation(
    monkeypatch,
) -> None:
    delivery, _, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            preparation_admitted=False,
            pessimistic=True,
        ),
    )

    assert (
        _require_result(delivery).outcome
        is PostgresWriteSideOutcome.ADMISSION_REJECTED
    )
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "rollback_finalization",
        },
        not_applicable={
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    )


def test_in_validation_block_measures_history_validation_and_rollback(
    monkeypatch,
) -> None:
    delivery, _, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            validation_action=EnforcementAction.BLOCK,
            pessimistic=True,
        ),
    )

    assert (
        _require_result(delivery).outcome
        is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )
    _assert_phase_states(
        _require_measurement(delivery),
        measured={
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "rollback_finalization",
        },
        not_applicable={
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    )


def test_measured_zero_is_retained_as_measured(monkeypatch) -> None:
    delivery, _, _, _ = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
    )

    preparation = _require_measurement(delivery).concurrency_preparation_call
    assert preparation.state is State.MEASURED
    assert preparation.elapsed_ns == 0


@pytest.mark.parametrize(
    "readings",
    [
        [RuntimeError("preview clock failed")],
        ["not-an-integer"],
        [True],
        [10, 9],
    ],
    ids=["exception", "invalid-type", "boolean", "backwards-delta"],
)
def test_clock_failure_makes_only_the_reached_phase_not_collected(
    readings: list[object],
) -> None:
    scripted_readings = iter(readings)

    def clock() -> int:
        reading = next(scripted_readings)
        if isinstance(reading, Exception):
            raise reading
        return cast(int, reading)

    recorder = Recorder(
        validation_placement=ValidationPlacement.PRE_TRANSACTION,
        clock=clock,
    )

    result = recorder.measure_call(
        MeasurementPhase.PRELIMINARY_IDEMPOTENCY_CHECK,
        lambda: "producer operation returned",
    )
    phase = recorder._phase_measurement(
        MeasurementPhase.PRELIMINARY_IDEMPOTENCY_CHECK
    )

    assert result == "producer operation returned"
    assert phase.state is State.NOT_COLLECTED
    assert phase.elapsed_ns is None


@pytest.mark.parametrize("traced", [False, True], ids=["legacy", "traced"])
def test_delivery_preserves_exact_producer_value_by_identity(
    monkeypatch,
    traced: bool,
) -> None:
    delivery, _, _, producer_values = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        traced=traced,
    )

    assert len(producer_values) == 1
    assert delivery.producer_value is producer_values[0]
    if traced:
        assert type(delivery.producer_value) is PostgresWriteSideExecution


def test_traced_delivery_preserves_trace_identity_and_timing_free_surface(
    monkeypatch,
) -> None:
    delivery, _, _, producer_values = _execute_preview(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        traced=True,
    )
    original_execution = producer_values[0]
    traced_execution = _require_execution(delivery)
    original_trace = traced_execution.trace

    assert traced_execution is original_execution
    assert traced_execution.trace is original_trace
    assert tuple(field.name for field in fields(original_trace)) == (
        "validation_placement",
        "checkpoints",
    )
    assert not any(
        "time" in field.name or "elapsed" in field.name
        for field in fields(PostgresWriteSideExecutionTrace)
    )


@pytest.mark.parametrize(
    ("method_name", "traced"),
    [
        ("pay_order_with_measurement", False),
        ("pay_order_with_trace_and_measurement", True),
    ],
)
def test_pay_measured_surfaces_preserve_the_same_explicit_delivery(
    monkeypatch,
    method_name: str,
    traced: bool,
) -> None:
    _install_preview_boundaries(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        probe,
    )
    aggregate = OrderAggregate("pr4-preview-measured-pay-order")
    connection.history = [
        aggregate.create(
            request_id="pr4-preview-measured-pay-seed",
            total_amount=Decimal("100.00"),
        )
    ]
    writer = _build_preview_writer(connection)
    monkeypatch.setattr(
        instrumentation.time,
        "perf_counter_ns",
        probe.clock.perf_counter_ns,
    )

    delivery = getattr(writer, method_name)(
        request_id=f"pr4-preview-{method_name}",
        order_id="pr4-preview-measured-pay-order",
        amount=Decimal("100.00"),
    )

    assert delivery.availability is Availability.AVAILABLE
    producer_result = (
        _require_execution(delivery).result
        if traced
        else _require_result(delivery)
    )
    assert producer_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert isinstance(delivery.producer_value, PostgresWriteSideExecution) is traced


@pytest.mark.parametrize(
    ("scenario", "expected_finalization"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
            ),
            MeasurementPhase.COMMIT_FINALIZATION,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
            ),
            MeasurementPhase.ROLLBACK_FINALIZATION,
        ),
    ],
    ids=["commit", "rollback"],
)
def test_finalization_uow_whole_and_construction_order(
    monkeypatch,
    scenario: _Scenario,
    expected_finalization: MeasurementPhase,
) -> None:
    events: list[object] = []
    original_finish = Recorder.finish
    original_build_delivery = Recorder.build_delivery

    def observe_finish(self, phase, started_ns):
        original_finish(self, phase, started_ns)
        if phase in {
            MeasurementPhase.COMMIT_FINALIZATION,
            MeasurementPhase.ROLLBACK_FINALIZATION,
            MeasurementPhase.BUSINESS_UOW,
            MeasurementPhase.PRODUCER_WRITE_INVOCATION,
        }:
            events.append(phase)

    def observe_build_delivery(self, producer_value):
        events.append("measurement_construction")
        return original_build_delivery(self, producer_value)

    monkeypatch.setattr(Recorder, "finish", observe_finish)
    monkeypatch.setattr(Recorder, "build_delivery", observe_build_delivery)

    _execute_preview(monkeypatch, scenario)

    assert events.index(expected_finalization) < events.index(
        MeasurementPhase.BUSINESS_UOW
    )
    assert events.index(MeasurementPhase.BUSINESS_UOW) < events.index(
        MeasurementPhase.PRODUCER_WRITE_INVOCATION
    )
    assert events.index(
        MeasurementPhase.PRODUCER_WRITE_INVOCATION
    ) < events.index("measurement_construction")


@pytest.mark.parametrize("traced", [False, True], ids=["legacy", "traced"])
@pytest.mark.parametrize(
    "scenario",
    [
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
            pessimistic=True,
        ),
    ],
    ids=["accepted", "normal-nonaccepted"],
)
def test_post_return_construction_failure_preserves_exact_business_value(
    monkeypatch,
    traced: bool,
    scenario: _Scenario,
) -> None:
    delivery, connection, _, producer_values = _execute_preview(
        monkeypatch,
        scenario,
        traced=traced,
        fail_final_construction=True,
    )

    assert delivery.availability is Availability.UNAVAILABLE
    assert delivery.measurement is None
    assert delivery.producer_value is producer_values[0]
    assert connection.committed is (
        scenario.idempotency_verdicts == (IdempotencyVerdict.MISS,)
    )


@pytest.mark.parametrize(
    ("scenario", "traced", "expected_outcome", "expected_committed"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
            ),
            False,
            PostgresWriteSideOutcome.ACCEPTED,
            True,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
            ),
            True,
            PostgresWriteSideOutcome.REPLAY,
            False,
        ),
    ],
    ids=["accepted-legacy", "normal-nonaccepted-traced"],
)
def test_available_delivery_construction_failure_uses_frozen_fallback(
    monkeypatch,
    scenario: _Scenario,
    traced: bool,
    expected_outcome: PostgresWriteSideOutcome,
    expected_committed: bool,
) -> None:
    built_snapshots = []
    available_attempts = []
    original_build_measurement = Recorder._build_measurement

    def observe_snapshot_construction(recorder):
        snapshot = original_build_measurement(recorder)
        built_snapshots.append(snapshot)
        return snapshot

    def fail_only_available_delivery(
        *,
        producer_value,
        availability,
        measurement,
    ):
        if availability is Availability.AVAILABLE:
            available_attempts.append((producer_value, measurement))
            raise RuntimeError("preview AVAILABLE delivery construction failed")
        return PostgresWriteSideMeasurementDelivery(
            producer_value=producer_value,
            availability=availability,
            measurement=measurement,
        )

    monkeypatch.setattr(
        Recorder,
        "_build_measurement",
        observe_snapshot_construction,
    )
    monkeypatch.setattr(
        measurement_contract,
        "PostgresWriteSideMeasurementDelivery",
        fail_only_available_delivery,
    )

    delivery, connection, _, producer_values = _execute_preview(
        monkeypatch,
        scenario,
        traced=traced,
    )

    assert len(built_snapshots) == 1
    assert len(available_attempts) == 1
    attempted_producer, attempted_measurement = available_attempts[0]
    assert attempted_producer is producer_values[0]
    assert attempted_measurement is built_snapshots[0]
    assert type(delivery) is PostgresWriteSideMeasurementDelivery
    assert delivery.producer_value is producer_values[0]
    producer_result = (
        _require_execution(delivery).result
        if traced
        else _require_result(delivery)
    )
    assert producer_result.outcome is expected_outcome
    assert delivery.availability is Availability.UNAVAILABLE
    assert delivery.measurement is None
    assert connection.committed is expected_committed


@pytest.mark.parametrize(
    "whole_clock_failure",
    ["start", "stop"],
    ids=["start-clock-failure", "stop-clock-failure"],
)
@pytest.mark.parametrize(
    ("scenario", "expected_outcome", "expected_committed"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
            ),
            PostgresWriteSideOutcome.ACCEPTED,
            True,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
            ),
            PostgresWriteSideOutcome.REPLAY,
            False,
        ),
    ],
    ids=["accepted", "normal-nonaccepted"],
)
def test_whole_invocation_clock_failure_preserves_business_truth_as_unavailable(
    monkeypatch,
    whole_clock_failure: str,
    scenario: _Scenario,
    expected_outcome: PostgresWriteSideOutcome,
    expected_committed: bool,
) -> None:
    delivery, connection, _, producer_values = _execute_preview(
        monkeypatch,
        scenario,
        whole_clock_failure=whole_clock_failure,
    )

    assert delivery.producer_value is producer_values[0]
    assert _require_result(delivery).outcome is expected_outcome
    assert delivery.availability is Availability.UNAVAILABLE
    assert delivery.measurement is None
    assert connection.committed is expected_committed


@pytest.mark.parametrize(
    ("scenario", "exception_type"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
                validation_raises=True,
            ),
            _ProducerFailure,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
                commit_raises=True,
            ),
            _CommitFailure,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
                rollback_raises=True,
            ),
            _RollbackFailure,
        ),
    ],
    ids=["producer", "commit", "rollback"],
)
def test_existing_exceptions_propagate_without_measurement_delivery(
    monkeypatch,
    scenario: _Scenario,
    exception_type: type[Exception],
) -> None:
    _install_preview_boundaries(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(scenario, probe)
    writer = _build_preview_writer(connection)
    monkeypatch.setattr(
        instrumentation.time,
        "perf_counter_ns",
        probe.clock.perf_counter_ns,
    )
    delivery_called = False

    def unexpected_delivery(self, producer_value):
        nonlocal delivery_called
        delivery_called = True
        raise AssertionError("delivery must not follow producer exception")

    monkeypatch.setattr(Recorder, "build_delivery", unexpected_delivery)

    with pytest.raises(exception_type):
        writer.create_order_with_measurement(
            request_id="pr4-preview-exception-request",
            order_id="pr4-preview-exception-order",
            amount=Decimal("100.00"),
        )

    assert delivery_called is False


@pytest.mark.parametrize(
    ("method_name", "traced"),
    [
        ("create_order", False),
        ("create_order_with_trace", True),
        ("pay_order", False),
        ("pay_order_with_trace", True),
    ],
)
def test_existing_apis_create_no_recorder_and_read_no_measurement_clock(
    monkeypatch,
    method_name: str,
    traced: bool,
) -> None:
    _install_preview_boundaries(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        probe,
    )
    if method_name.startswith("pay_order"):
        aggregate = OrderAggregate("pr4-preview-unmeasured-order")
        connection.history = [
            aggregate.create(
                request_id="pr4-preview-seed-create",
                total_amount=Decimal("100.00"),
            )
        ]
    writer = _build_preview_writer(connection)

    def forbidden_clock_read() -> int:
        raise AssertionError("unmeasured API read the measurement clock")

    def forbidden_recorder_creation(_validation_placement):
        raise AssertionError("unmeasured API created a measurement recorder")

    monkeypatch.setattr(
        instrumentation.time,
        "perf_counter_ns",
        forbidden_clock_read,
    )
    monkeypatch.setattr(
        write_side_module,
        "_new_measurement_recorder",
        forbidden_recorder_creation,
    )
    method = getattr(writer, method_name)

    value = method(
        request_id=f"pr4-preview-{method_name}",
        order_id="pr4-preview-unmeasured-order",
        amount=Decimal("100.00"),
    )

    assert value is not None
    assert isinstance(value, PostgresWriteSideExecution) is traced


def test_public_surface_is_explicit_and_existing_signatures_are_unchanged() -> None:
    existing_methods = (
        "create_order",
        "create_order_with_trace",
        "pay_order",
        "pay_order_with_trace",
    )
    measured_methods = (
        "create_order_with_measurement",
        "create_order_with_trace_and_measurement",
        "pay_order_with_measurement",
        "pay_order_with_trace_and_measurement",
    )

    for method_name in (*existing_methods, *measured_methods):
        parameters = tuple(
            signature(
                getattr(PostgresTransactionalWriteSide, method_name)
            ).parameters
        )
        assert parameters == ("self", "request_id", "order_id", "amount")

    assert not any(
        "enabled" in parameter
        for method_name in existing_methods
        for parameter in signature(
            getattr(PostgresTransactionalWriteSide, method_name)
        ).parameters
    )


def test_measured_methods_document_only_the_canonical_composition_pair() -> None:
    measured_methods = (
        "create_order_with_measurement",
        "create_order_with_trace_and_measurement",
        "pay_order_with_measurement",
        "pay_order_with_trace_and_measurement",
    )

    for method_name in measured_methods:
        docstring = getdoc(
            getattr(PostgresTransactionalWriteSide, method_name)
        )
        assert docstring is not None
        assert "PRE_TRANSACTION" in docstring
        assert "optimistic/OCC" in docstring
        assert "IN_TRANSACTION" in docstring
        assert "concrete PostgreSQL pessimistic" in docstring
        assert "not an interpretation-safe" in docstring


def test_pessimistic_adapter_copies_no_private_gate_state_or_bound_method() -> None:
    connection = _FakeConnection(
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        _Probe(_ManualClock()),
    )
    event_store = cast(PostgresEventStore, object())
    ordinary_gate = PostgresPessimisticAdmissionGate(
        connection=cast(Connection, connection),
        event_store=event_store,
    )
    recorder = Recorder(
        validation_placement=ValidationPlacement.IN_TRANSACTION,
        clock=connection.probe.clock.perf_counter_ns,
    )

    measured_gate = instrumentation._instrument_concrete_pessimistic_gate(
        ordinary_gate,
        recorder,
    )

    assert type(measured_gate) is (
        instrumentation._MeasuredPostgresPessimisticAdmissionGate
    )
    assert measured_gate.connection is ordinary_gate.connection
    assert measured_gate.event_store is ordinary_gate.event_store
    assert measured_gate._prepared_order_ids is not (
        ordinary_gate._prepared_order_ids
    )
    assert measured_gate._prepared_order_ids == set()
    assert "_unmeasured_try_lock_stream" not in vars(measured_gate)


def test_frozen_pr3_baseline_is_non_importable_and_experiment_only() -> None:
    fixture_directory = (
        REPOSITORY_ROOT / "tests/fixtures/stage4b2_measurement"
    )
    snapshot_path = (
        fixture_directory / "postgres_write_side_pr3_baseline.py.source"
    )
    provenance = json.loads(
        (fixture_directory / "provenance.json").read_text(encoding="utf-8")
    )
    fixture_readme = (fixture_directory / "README.md").read_text(
        encoding="utf-8"
    )

    assert snapshot_path.suffix == ".source"
    assert hashlib.sha256(snapshot_path.read_bytes()).hexdigest() == (
        "34bac8a3e67d6a43f870d26ae48642ff1893c5360cbf3ec2c0e1f1cd6630196d"
    )
    assert provenance["sha256"] == (
        "34bac8a3e67d6a43f870d26ae48642ff1893c5360cbf3ec2c0e1f1cd6630196d"
    )
    assert provenance["source_path"] == (
        "src/pipeline/transactional/postgres_write_side.py"
    )
    assert provenance["pr4_base_head"] == (
        "fd3733d57ff82beeaf9d54446924f8830c49db76"
    )
    assert "experiment reference material only" in fixture_readme
    assert "must never import or execute it" in fixture_readme
    assert "frozen from the committed Stage 4B.2 PR3 parent" in fixture_readme
    assert "fd3733d57ff82beeaf9d54446924f8830c49db76" in fixture_readme

    forbidden_reference = "postgres_write_side_pr3_baseline"
    for production_module in (REPOSITORY_ROOT / "src").rglob("*.py"):
        assert forbidden_reference not in production_module.read_text(
            encoding="utf-8"
        )
