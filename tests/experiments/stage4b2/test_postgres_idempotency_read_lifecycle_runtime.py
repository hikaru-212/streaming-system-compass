from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

import experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime as runtime
from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleSample,
    IdempotencyVerdictIdentity,
    Layer3Control,
    RunValidity,
    TransactionStatusIdentity,
    generate_recorded_schedule,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime import (
    _execute_control_a_sample,
    _execute_control_b_sample,
    execute_until_invalid,
    time_control_a_idle_rollback,
    time_control_b_preliminary_read_lifecycle,
)
from src.core.order.enums import CommandType
from src.storage.idempotency_store import RequestSignature


class _ProcessControlSignal(BaseException):
    pass


def _valid_sample(plan):
    if plan.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
        return ControlAIdleRollbackSample(
            control=plan.control,
            sample_index=plan.sample_index,
            round_index=plan.round_index,
            status_before_cleanup=TransactionStatusIdentity.IDLE,
            cleanup_elapsed_ns=10,
            status_after_cleanup=TransactionStatusIdentity.IDLE,
        )
    return ControlBPreliminaryReadLifecycleSample(
        control=plan.control,
        sample_index=plan.sample_index,
        round_index=plan.round_index,
        returned_idempotency_verdict=IdempotencyVerdictIdentity.MISS,
        history_count=0,
        idempotency_check_elapsed_ns=20,
        accepted_history_load_elapsed_ns=30,
        cleanup_elapsed_ns=20,
        lifecycle_elapsed_ns=150,
        status_before_check=TransactionStatusIdentity.IDLE,
        status_after_check=TransactionStatusIdentity.INTRANS,
        status_after_history=TransactionStatusIdentity.INTRANS,
        status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
    )


def test_control_a_timer_wraps_rollback_only() -> None:
    events = []
    readings = iter((100, 125))

    def clock():
        events.append("clock")
        return next(readings)

    observed = time_control_a_idle_rollback(
        lambda: events.append("rollback"),
        clock=clock,
    )

    assert events == ["clock", "rollback", "clock"]
    assert observed.cleanup_elapsed_ns == 25
    assert observed.exception_type is None


def test_control_b_direct_lifecycle_wraps_separate_component_timers() -> None:
    events = []
    readings = iter((0, 10, 30, 40, 70, 80, 100, 150))
    statuses = iter(
        (
            TransactionStatusIdentity.INTRANS,
            TransactionStatusIdentity.INTRANS,
            TransactionStatusIdentity.IDLE,
        )
    )

    def clock():
        events.append("clock")
        return next(readings)

    def status_reader():
        events.append("status")
        return next(statuses)

    observed = time_control_b_preliminary_read_lifecycle(
        lambda: events.append("check") or SimpleNamespace(verdict="MISS"),
        lambda: events.append("history") or [],
        lambda: events.append("cleanup"),
        status_reader,
        clock=clock,
    )

    assert events == [
        "clock",
        "clock",
        "check",
        "clock",
        "status",
        "clock",
        "history",
        "clock",
        "status",
        "clock",
        "cleanup",
        "clock",
        "clock",
        "status",
    ]
    assert observed.idempotency_check_elapsed_ns == 20
    assert observed.accepted_history_load_elapsed_ns == 30
    assert observed.cleanup_elapsed_ns == 20
    assert observed.lifecycle_elapsed_ns == 150
    assert observed.lifecycle_elapsed_ns != (
        observed.idempotency_check_elapsed_ns
        + observed.accepted_history_load_elapsed_ns
        + observed.cleanup_elapsed_ns
    )


def test_ordinary_exception_retains_only_class_and_still_cleans_up() -> None:
    readings = iter((0, 10, 20, 30, 40, 50))
    statuses = iter(
        (
            TransactionStatusIdentity.INTRANS,
            TransactionStatusIdentity.INTRANS,
            TransactionStatusIdentity.IDLE,
        )
    )
    events = []

    def fail_check():
        raise ValueError("message must not enter Layer-3 evidence")

    observed = time_control_b_preliminary_read_lifecycle(
        fail_check,
        lambda: events.append("history") or [],
        lambda: events.append("cleanup"),
        lambda: next(statuses),
        clock=lambda: next(readings),
    )

    assert observed.exception_type == "ValueError"
    assert not hasattr(observed, "exception_message")
    assert observed.accepted_history_load_elapsed_ns is None
    assert "history" not in events
    assert events == ["cleanup"]


def test_timing_seams_do_not_catch_process_control_baseexception() -> None:
    def stop():
        raise _ProcessControlSignal()

    with pytest.raises(_ProcessControlSignal):
        time_control_a_idle_rollback(stop, clock=lambda: 1)
    with pytest.raises(_ProcessControlSignal):
        time_control_b_preliminary_read_lifecycle(
            stop,
            lambda: [],
            lambda: None,
            lambda: TransactionStatusIdentity.IDLE,
            clock=lambda: 1,
        )


@pytest.mark.parametrize("failure_index", (0, 1, 17))
def test_first_invalid_sample_stops_without_retry_or_replacement(
    failure_index,
) -> None:
    schedule = generate_recorded_schedule()
    calls = []

    def execute(plan):
        calls.append(plan.sample_index)
        sample = _valid_sample(plan)
        if plan.sample_index == failure_index:
            if isinstance(sample, ControlAIdleRollbackSample):
                return replace(
                    sample,
                    status_after_cleanup=TransactionStatusIdentity.INTRANS,
                )
            return replace(
                sample,
                returned_idempotency_verdict=IdempotencyVerdictIdentity.REPLAY,
            )
        return sample

    samples = execute_until_invalid(schedule, execute)

    assert calls == list(range(failure_index + 1))
    assert len(samples) == failure_index + 1
    assert calls.count(failure_index) == 1


def test_execution_exception_stops_without_runtime_retry() -> None:
    schedule = generate_recorded_schedule()
    calls = []

    def execute(plan):
        calls.append(plan.sample_index)
        if plan.sample_index == 2:
            raise RuntimeError("setup failure")
        return _valid_sample(plan)

    with pytest.raises(RuntimeError, match="setup failure"):
        execute_until_invalid(schedule, execute)

    assert calls == [0, 1, 2]


def test_all_valid_plans_execute_once_without_adaptive_extension() -> None:
    schedule = generate_recorded_schedule()
    calls = []

    samples = execute_until_invalid(
        schedule,
        lambda plan: calls.append(plan.sample_index) or _valid_sample(plan),
    )

    assert calls == list(range(60))
    assert len(samples) == 60


class _FakeTransactionStatus:
    def __init__(self, name="IDLE") -> None:
        self.name = name


class _FakeCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None, **kwargs):
        normalized = " ".join(str(query).split())
        self.connection.events.append(f"sql:{normalized}")
        self.connection.status.name = "INTRANS"
        self.row = (1,) if normalized == "SELECT 1" else None
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class _FakeConnection:
    autocommit = False

    def __init__(self) -> None:
        self.status = _FakeTransactionStatus()
        self.info = SimpleNamespace(transaction_status=self.status)
        self.events = []

    def cursor(self, *args, **kwargs):
        return _FakeCursor(self)

    def rollback(self):
        self.events.append("rollback")
        self.status.name = "IDLE"


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="layer3-fresh-request",
        command_type=CommandType.CREATE,
        order_id="layer3-fresh-order",
        amount=Decimal("100.00"),
    )


def test_control_a_sample_starts_idle_and_executes_no_sql() -> None:
    plan = generate_recorded_schedule().samples[0]
    connection = _FakeConnection()
    readings = iter((5, 8))

    sample = _execute_control_a_sample(
        plan=plan,
        connection=connection,
        clock=lambda: connection.events.append("clock") or next(readings),
    )

    assert sample.status_before_cleanup is TransactionStatusIdentity.IDLE
    assert sample.status_after_cleanup is TransactionStatusIdentity.IDLE
    assert sample.cleanup_elapsed_ns == 3
    assert connection.events == ["clock", "rollback", "clock"]
    assert not any(event.startswith("sql:") for event in connection.events)


def test_control_b_uses_production_check_and_history_seams_then_untimed_reuse() -> None:
    plan = generate_recorded_schedule().samples[1]
    connection = _FakeConnection()
    readings = iter((0, 10, 30, 40, 70, 80, 100, 150))

    def clock():
        value = next(readings)
        connection.events.append(f"clock:{value}")
        return value

    sample = _execute_control_b_sample(
        plan=plan,
        connection=connection,
        signature=_signature(),
        order_id="layer3-fresh-order",
        clock=clock,
    )

    sql_events = [
        event.removeprefix("sql:")
        for event in connection.events
        if event.startswith("sql:")
    ]
    assert len(sql_events) == 3
    assert "FROM idempotency_records i" in sql_events[0]
    assert "FROM order_events" in sql_events[1]
    assert sql_events[2] == "SELECT 1"
    assert connection.events.index("sql:SELECT 1") > connection.events.index(
        "clock:150"
    )
    assert sample.returned_idempotency_verdict is IdempotencyVerdictIdentity.MISS
    assert sample.history_count == 0
    assert sample.status_before_check is TransactionStatusIdentity.IDLE
    assert sample.status_after_check is TransactionStatusIdentity.INTRANS
    assert sample.status_after_history is TransactionStatusIdentity.INTRANS
    assert sample.status_after_cleanup is TransactionStatusIdentity.IDLE
    assert sample.reuse_select_succeeded is True
    assert sample.final_transaction_status is TransactionStatusIdentity.IDLE
    assert sample.lifecycle_elapsed_ns == 150
    assert sample.lifecycle_elapsed_ns != (
        sample.idempotency_check_elapsed_ns
        + sample.accepted_history_load_elapsed_ns
        + sample.cleanup_elapsed_ns
    )


def test_recorded_runtime_stops_after_first_invalid_sample(monkeypatch) -> None:
    control_connection = object()
    subject_connection = object()
    reset_indexes = []
    closed = []

    monkeypatch.setattr(
        runtime,
        "_open_guarded_connections",
        lambda database_url: (control_connection, subject_connection),
    )
    monkeypatch.setattr(
        runtime,
        "_reset_database",
        lambda control, connections: reset_indexes.append(len(reset_indexes)),
    )
    monkeypatch.setattr(
        runtime,
        "_build_control_b_fixture",
        lambda run_id, plan: (object(), "fresh-order"),
    )
    monkeypatch.setattr(
        runtime,
        "_execute_control_a_sample",
        lambda **kwargs: _valid_sample(kwargs["plan"]),
    )

    def invalid_control_b(**kwargs):
        return replace(
            _valid_sample(kwargs["plan"]),
            returned_idempotency_verdict=IdempotencyVerdictIdentity.CONFLICT,
        )

    monkeypatch.setattr(runtime, "_execute_control_b_sample", invalid_control_b)
    monkeypatch.setattr(
        runtime,
        "_close_connections",
        lambda connections: closed.append(connections),
    )

    result = runtime.run_layer3_recorded(
        "configured-test-database",
        run_id="layer3-unit",
        clock=lambda: 1,
    )

    assert len(result.samples) == 2
    assert result.validation.validity is RunValidity.INVALID
    assert reset_indexes == [0, 1]
    assert closed == [(control_connection, subject_connection)]


def test_runtime_has_no_cli_evidence_writer_or_counterfactual_surface() -> None:
    assert not hasattr(runtime, "main")
    assert not hasattr(runtime, "write_evidence_directory")
    assert not hasattr(runtime, "PRE_NO_PRELIMINARY")
    assert not hasattr(runtime, "IN_OCC")
