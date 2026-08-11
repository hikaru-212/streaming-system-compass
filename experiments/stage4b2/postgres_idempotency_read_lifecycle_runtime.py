"""Execution mechanics for post-PR6 Layer-3 lifecycle controls.

Control A times only a direct rollback beginning from IDLE. Control B directly
times the current production idempotency check, accepted-history load, and
rollback inside one independently timed lifecycle. Setup, identity generation,
store construction, reset, reuse verification, and final cleanup stay outside
the claimed boundaries. This module has no CLI, evidence writer, strategy
comparison, retry, or counterfactual production behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter_ns
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleSample,
    IdempotencyVerdictIdentity,
    Layer3Control,
    Layer3Sample,
    Layer3SamplePlan,
    Layer3Schedule,
    RunValidationResult,
    RunValidity,
    TransactionStatusIdentity,
    generate_recorded_schedule,
    validate_run,
    validate_sample,
)


CANONICAL_AMOUNT = Decimal("100.00")


class Layer3RuntimeError(RuntimeError):
    """Report setup or clock failure without defining production behavior.

    This error supplies no retry, publication, or architecture policy.
    """


@dataclass(frozen=True)
class TimedControlAObservation:
    """Retain only one directly timed rollback and its exception class.

    The elapsed boundary begins immediately before the supplied rollback call
    and ends immediately after it returns or raises an ordinary exception. It
    does not include SQL, connection setup, or active-transaction work.
    """

    cleanup_elapsed_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_elapsed(self.cleanup_elapsed_ns)
        _require_exception_type(self.exception_type)


@dataclass(frozen=True)
class TimedControlBObservation:
    """Retain nested component calls and one direct outer lifecycle timing.

    The lifecycle boundary begins immediately before the production check and
    ends immediately after direct rollback. Component timings remain separate;
    no field derives or represents a component sum or server-side database
    time. Ordinary failures retain only their first exception class name.
    """

    decision: Any | None
    history: Sequence[Any] | None
    idempotency_check_elapsed_ns: int
    accepted_history_load_elapsed_ns: int | None
    cleanup_elapsed_ns: int
    lifecycle_elapsed_ns: int
    status_after_check: TransactionStatusIdentity
    status_after_history: TransactionStatusIdentity
    status_after_cleanup: TransactionStatusIdentity
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_elapsed(self.idempotency_check_elapsed_ns)
        if self.accepted_history_load_elapsed_ns is not None:
            _require_elapsed(self.accepted_history_load_elapsed_ns)
        _require_elapsed(self.cleanup_elapsed_ns)
        _require_elapsed(self.lifecycle_elapsed_ns)
        _require_exception_type(self.exception_type)


@dataclass(frozen=True)
class Layer3RuntimeResult:
    """Return executed samples and validation without publishing evidence.

    A partial tuple is intentional after the first invalid sample. The result
    does not retry, replace observations, serialize evidence, or make an
    architectural interpretation.
    """

    schedule: Layer3Schedule
    samples: tuple[Layer3Sample, ...]
    validation: RunValidationResult


def time_control_a_idle_rollback(
    rollback: Callable[[], None],
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> TimedControlAObservation:
    """Time exactly one IDLE rollback call and retain only exception class.

    The caller owns the before/after transaction-state observations. This
    function performs no SQL, retry, connection preparation, or interpretation.
    """

    started_ns = _read_clock(clock)
    exception_type = None
    try:
        rollback()
    except Exception as exc:
        exception_type = type(exc).__name__
    stopped_ns = _read_clock(clock)
    return TimedControlAObservation(
        cleanup_elapsed_ns=_elapsed(started_ns, stopped_ns),
        exception_type=exception_type,
    )


def time_control_b_preliminary_read_lifecycle(
    check: Callable[[], Any],
    load_history: Callable[[], Sequence[Any]],
    rollback: Callable[[], None],
    status_reader: Callable[[], TransactionStatusIdentity],
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> TimedControlBObservation:
    """Directly time one PRE-like check/load/rollback lifecycle.

    The outer timer starts immediately before the nested check timer and stops
    immediately after the nested cleanup timer. Check, history, and cleanup are
    independently timed rather than summed. The status reader records physical
    lifecycle evidence without substituting SQL, and this function performs no
    setup, reuse verification, retry, or strategy comparison.
    """

    lifecycle_started_ns = _read_clock(clock)

    check_started_ns = _read_clock(clock)
    decision = None
    exception_type = None
    try:
        decision = check()
    except Exception as exc:
        exception_type = type(exc).__name__
    check_stopped_ns = _read_clock(clock)
    status_after_check = status_reader()

    history: Sequence[Any] | None = None
    history_elapsed_ns: int | None = None
    if exception_type is None:
        history_started_ns = _read_clock(clock)
        try:
            history = load_history()
        except Exception as exc:
            exception_type = type(exc).__name__
        history_stopped_ns = _read_clock(clock)
        history_elapsed_ns = _elapsed(history_started_ns, history_stopped_ns)
    status_after_history = status_reader()

    cleanup_started_ns = _read_clock(clock)
    try:
        rollback()
    except Exception as exc:
        exception_type = exception_type or type(exc).__name__
    cleanup_stopped_ns = _read_clock(clock)
    lifecycle_stopped_ns = _read_clock(clock)
    status_after_cleanup = status_reader()

    return TimedControlBObservation(
        decision=decision,
        history=history,
        idempotency_check_elapsed_ns=_elapsed(
            check_started_ns,
            check_stopped_ns,
        ),
        accepted_history_load_elapsed_ns=history_elapsed_ns,
        cleanup_elapsed_ns=_elapsed(cleanup_started_ns, cleanup_stopped_ns),
        lifecycle_elapsed_ns=_elapsed(
            lifecycle_started_ns,
            lifecycle_stopped_ns,
        ),
        status_after_check=status_after_check,
        status_after_history=status_after_history,
        status_after_cleanup=status_after_cleanup,
        exception_type=exception_type,
    )


def execute_until_invalid(
    schedule: Layer3Schedule,
    execute_one: Callable[[Layer3SamplePlan], Layer3Sample],
) -> tuple[Layer3Sample, ...]:
    """Execute fixed plans once and stop immediately after the first invalid sample.

    An execution exception propagates and therefore also stops the schedule.
    No retry, replacement, adaptive extension, or invalid-evidence repair is
    performed.
    """

    samples: list[Layer3Sample] = []
    for plan in schedule.samples:
        sample = execute_one(plan)
        samples.append(sample)
        if validate_sample(plan, sample).validity is RunValidity.INVALID:
            break
    return tuple(samples)


def run_layer3_recorded(
    database_url: str,
    *,
    run_id: str,
    clock: Callable[[], int] = perf_counter_ns,
) -> Layer3RuntimeResult:
    """Run the fixed 60-sample Layer-3 PostgreSQL schedule when authorized.

    The function uses the exact production idempotency and event stores. All
    setup is outside timing, and the first invalid sample stops later plans.
    It has no retry, CLI, evidence persistence, strategy comparison, or
    counterfactual behavior; callers must separately authorize live execution.
    """

    _require_runtime_inputs(database_url, run_id)
    schedule = generate_recorded_schedule()
    control_connection, subject_connection = _open_guarded_connections(
        database_url
    )
    connections = (control_connection, subject_connection)
    try:
        def execute(plan: Layer3SamplePlan) -> Layer3Sample:
            _reset_database(control_connection, connections)
            if plan.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
                return _execute_control_a_sample(
                    plan=plan,
                    connection=subject_connection,
                    clock=clock,
                )
            if (
                plan.control
                is Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE
            ):
                signature, order_id = _build_control_b_fixture(run_id, plan)
                return _execute_control_b_sample(
                    plan=plan,
                    connection=subject_connection,
                    signature=signature,
                    order_id=order_id,
                    clock=clock,
                )
            raise Layer3RuntimeError("unknown Layer-3 control")

        samples = execute_until_invalid(schedule, execute)
        return Layer3RuntimeResult(
            schedule=schedule,
            samples=samples,
            validation=validate_run(schedule, samples),
        )
    finally:
        _close_connections(connections)


def _execute_control_a_sample(
    *,
    plan: Layer3SamplePlan,
    connection: Any,
    clock: Callable[[], int],
) -> ControlAIdleRollbackSample:
    before = _transaction_status(connection)
    timed = time_control_a_idle_rollback(connection.rollback, clock=clock)
    after = _transaction_status(connection)
    return ControlAIdleRollbackSample(
        control=plan.control,
        sample_index=plan.sample_index,
        round_index=plan.round_index,
        status_before_cleanup=before,
        cleanup_elapsed_ns=timed.cleanup_elapsed_ns,
        status_after_cleanup=after,
        exception_type=timed.exception_type,
    )


def _execute_control_b_sample(
    *,
    plan: Layer3SamplePlan,
    connection: Any,
    signature: Any,
    order_id: str,
    clock: Callable[[], int],
) -> ControlBPreliminaryReadLifecycleSample:
    from src.storage.postgres_event_store import PostgresEventStore
    from src.storage.postgres_idempotency_store import PostgresIdempotencyStore

    idempotency_store = PostgresIdempotencyStore(connection)
    event_store = PostgresEventStore(connection)
    before = _transaction_status(connection)
    timed = time_control_b_preliminary_read_lifecycle(
        lambda: idempotency_store.check(signature),
        lambda: event_store.load(order_id),
        connection.rollback,
        lambda: _transaction_status(connection),
        clock=clock,
    )
    reuse_succeeded, final_status = _verify_reuse(connection)

    exception_type = timed.exception_type
    returned_verdict = None
    if timed.decision is not None:
        try:
            returned_verdict = _returned_verdict(timed.decision)
        except Exception as exc:
            exception_type = exception_type or type(exc).__name__

    history_count = None
    if timed.history is not None:
        try:
            history_count = len(timed.history)
        except Exception as exc:
            exception_type = exception_type or type(exc).__name__

    return ControlBPreliminaryReadLifecycleSample(
        control=plan.control,
        sample_index=plan.sample_index,
        round_index=plan.round_index,
        returned_idempotency_verdict=returned_verdict,
        history_count=history_count,
        idempotency_check_elapsed_ns=timed.idempotency_check_elapsed_ns,
        accepted_history_load_elapsed_ns=(
            timed.accepted_history_load_elapsed_ns
        ),
        cleanup_elapsed_ns=timed.cleanup_elapsed_ns,
        lifecycle_elapsed_ns=timed.lifecycle_elapsed_ns,
        status_before_check=before,
        status_after_check=timed.status_after_check,
        status_after_history=timed.status_after_history,
        status_after_cleanup=timed.status_after_cleanup,
        reuse_select_succeeded=reuse_succeeded,
        final_transaction_status=final_status,
        exception_type=exception_type,
    )


def _build_control_b_fixture(
    run_id: str,
    plan: Layer3SamplePlan,
) -> tuple[Any, str]:
    from src.core.order.enums import CommandType
    from src.storage.idempotency_store import RequestSignature

    token = f"layer3:{run_id}:{plan.sample_index}:{plan.round_index}"
    request_id = str(uuid5(NAMESPACE_URL, f"{token}:request"))
    order_id = str(uuid5(NAMESPACE_URL, f"{token}:order"))
    return (
        RequestSignature(
            request_id=request_id,
            command_type=CommandType.CREATE,
            order_id=order_id,
            amount=CANONICAL_AMOUNT,
        ),
        order_id,
    )


def _returned_verdict(decision: Any) -> IdempotencyVerdictIdentity:
    raw = getattr(getattr(decision, "verdict", None), "value", None)
    if not isinstance(raw, str):
        raise Layer3RuntimeError("production check returned an invalid verdict")
    try:
        return IdempotencyVerdictIdentity(raw.upper())
    except ValueError as exc:
        raise Layer3RuntimeError(
            "production check returned an unknown verdict"
        ) from exc


def _verify_reuse(
    connection: Any,
) -> tuple[bool, TransactionStatusIdentity]:
    reuse_succeeded = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            reuse_succeeded = cursor.fetchone() == (1,)
    except Exception:
        reuse_succeeded = False
    finally:
        with suppress(Exception):
            connection.rollback()
    return reuse_succeeded, _transaction_status(connection)


def _transaction_status(connection: Any) -> TransactionStatusIdentity:
    name = getattr(connection.info.transaction_status, "name", None)
    try:
        return TransactionStatusIdentity(name)
    except ValueError:
        return TransactionStatusIdentity.UNKNOWN


def _open_guarded_connections(database_url: str) -> tuple[Any, Any]:
    from experiments.stage4b2.postgres_idempotency_check_runtime import (
        _open_guarded_connections as open_layer2_guarded_connections,
    )

    return open_layer2_guarded_connections(database_url)


def _reset_database(control: Any, connections: tuple[Any, ...]) -> None:
    from experiments.stage4b2.postgres_idempotency_check_runtime import (
        _reset_database as reset_layer2_database,
    )

    reset_layer2_database(control, connections)


def _close_connections(connections: tuple[Any, ...]) -> None:
    from experiments.stage4b2.postgres_idempotency_check_runtime import (
        _close_connections as close_layer2_connections,
    )

    close_layer2_connections(connections)


def _require_runtime_inputs(database_url: str, run_id: str) -> None:
    if not isinstance(database_url, str) or not database_url:
        raise ValueError("database_url must be a non-empty string")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")


def _read_clock(clock: Callable[[], int]) -> int:
    reading = clock()
    if type(reading) is not int:
        raise TypeError("clock must return integer nanoseconds")
    return reading


def _elapsed(started_ns: int, stopped_ns: int) -> int:
    elapsed_ns = stopped_ns - started_ns
    if elapsed_ns < 0:
        raise Layer3RuntimeError("clock moved backwards")
    return elapsed_ns


def _require_elapsed(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("elapsed_ns must be a non-negative integer")


def _require_exception_type(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError("exception_type must be a non-empty class name or None")
