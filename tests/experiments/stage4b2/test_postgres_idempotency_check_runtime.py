from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

import pytest

from experiments.stage4b2.postgres_idempotency_check_characterization import (
    Layer2Context,
    Layer2Verdict,
    TransactionStatusIdentity,
    generate_smoke_schedule,
)
from experiments.stage4b2.postgres_idempotency_check_runtime import (
    _ObservedConnection,
    _prepare_context,
    _transaction_status,
    execute_fixed_schedule,
    normalize_sql_identity,
    time_check_call,
    time_cleanup_call,
)
from src.core.order.enums import CommandType
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature


class _ProcessControlSignal(BaseException):
    pass


def test_check_timer_wraps_only_exact_invocation() -> None:
    events = []
    readings = iter((100, 145))

    def clock():
        events.append("clock")
        return next(readings)

    observed = time_check_call(
        lambda: events.append("check") or "decision",
        clock=clock,
    )

    assert events == ["clock", "check", "clock"]
    assert observed.value == "decision"
    assert observed.elapsed_ns == 45
    assert observed.exception_type is None


def test_cleanup_timer_wraps_only_finalization_call() -> None:
    events = []
    readings = iter((200, 225))

    def clock():
        events.append("clock")
        return next(readings)

    observed = time_cleanup_call(
        lambda: events.append("cleanup"),
        clock=clock,
    )

    assert events == ["clock", "cleanup", "clock"]
    assert observed.elapsed_ns == 25
    assert observed.exception_type is None


@pytest.mark.parametrize(
    ("timer", "expected_elapsed"),
    ((time_check_call, 8), (time_cleanup_call, 8)),
)
def test_timers_retain_only_ordinary_exception_type(timer, expected_elapsed) -> None:
    readings = iter((10, 18))

    def fail() -> None:
        raise ValueError("message must not enter evidence")

    observed = timer(fail, clock=lambda: next(readings))

    assert observed.elapsed_ns == expected_elapsed
    assert observed.exception_type == "ValueError"
    assert not hasattr(observed, "exception_message")


@pytest.mark.parametrize("timer", (time_check_call, time_cleanup_call))
def test_timers_do_not_catch_process_control_baseexception(timer) -> None:
    def stop() -> None:
        raise _ProcessControlSignal()

    with pytest.raises(_ProcessControlSignal):
        timer(stop, clock=lambda: 1)


def test_fixed_executor_invokes_each_smoke_cell_once_without_retry() -> None:
    schedule = generate_smoke_schedule()
    calls = []

    observed = execute_fixed_schedule(
        schedule,
        lambda plan: calls.append((plan.sample_index, plan.cell)) or plan,
    )

    assert tuple(calls) == tuple(
        (plan.sample_index, plan.cell) for plan in schedule.samples
    )
    assert observed == schedule.samples
    assert len(calls) == 9


def test_fixed_executor_stops_without_replacement_after_failure() -> None:
    schedule = generate_smoke_schedule()
    calls = []

    def execute(plan):
        calls.append(plan.cell)
        if plan.sample_index == 2:
            raise RuntimeError("structural failure")
        return plan

    with pytest.raises(RuntimeError, match="structural failure"):
        execute_fixed_schedule(schedule, execute)

    assert calls == [plan.cell for plan in schedule.samples[:3]]


def test_sql_identity_normalizes_only_whitespace() -> None:
    assert normalize_sql_identity("\n SELECT  value\n FROM table  ") == (
        "SELECT value FROM table"
    )


@dataclass
class _FakeTransactionStatus:
    name: str


class _FakeCursor:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None, **kwargs):
        self.connection.executed.append(normalize_sql_identity(query))
        self.connection.status.name = "INTRANS"
        self.row = (1,) if normalize_sql_identity(query) == "SELECT 1" else None
        return self

    def fetchone(self):
        return self.row


class _FakeConnection:
    autocommit = False

    def __init__(self) -> None:
        self.status = _FakeTransactionStatus("IDLE")
        self.info = SimpleNamespace(transaction_status=self.status)
        self.executed = []
        self.rollbacks = 0

    def cursor(self, *args, **kwargs):
        return _FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1
        self.status.name = "IDLE"


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="layer2-request",
        command_type=CommandType.CREATE,
        order_id="layer2-order",
        amount=Decimal("100.00"),
    )


@pytest.mark.parametrize(
    ("context", "expected_before"),
    (
        (Layer2Context.P, TransactionStatusIdentity.IDLE),
        (Layer2Context.U, TransactionStatusIdentity.IDLE),
        (Layer2Context.T, TransactionStatusIdentity.INTRANS),
    ),
)
def test_context_preparation_and_exact_check_statuses(context, expected_before) -> None:
    connection = _FakeConnection()
    session = _prepare_context(connection, context)

    assert _transaction_status(connection) is expected_before
    decision = session.store.check(_signature())

    assert decision.verdict is IdempotencyVerdict.MISS
    assert _transaction_status(connection) is TransactionStatusIdentity.INTRANS
    session.cleanup()
    assert _transaction_status(connection) is TransactionStatusIdentity.IDLE
    session.finish_after_cleanup(True)


def test_t_neutral_select_is_setup_not_observed_check_sql() -> None:
    connection = _FakeConnection()
    observed_connection = _ObservedConnection(connection)
    session = _prepare_context(
        connection,
        Layer2Context.T,
        store_connection=observed_connection,
    )

    assert connection.executed == ["SELECT 1"]
    assert observed_connection.normalized_sql_identities == []
    decision = session.store.check(_signature())

    assert decision.verdict is IdempotencyVerdict.MISS
    assert len(observed_connection.normalized_sql_identities) == 1
    assert observed_connection.normalized_sql_identities[0] != "SELECT 1"
    assert connection.executed[0] == "SELECT 1"
    assert len(connection.executed) == 2
    session.cleanup()
    session.finish_after_cleanup(True)


def test_primary_context_has_no_sql_observer() -> None:
    connection = _FakeConnection()
    session = _prepare_context(connection, Layer2Context.P)

    assert not isinstance(session.store._connection, _ObservedConnection)


def test_fake_verdict_identity_fixture_remains_exact() -> None:
    assert tuple(verdict.value for verdict in Layer2Verdict) == (
        "MISS",
        "REPLAY",
        "CONFLICT",
    )
