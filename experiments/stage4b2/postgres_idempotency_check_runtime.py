"""Real-PostgreSQL runtime for exact Layer-2 idempotency-check cells.

Primary samples time the current production ``PostgresIdempotencyStore.check``
call and its context-appropriate rollback separately. Fixture work, context
construction, the T control's neutral ``SELECT 1``, reuse verification, and
structural SQL observation remain outside those boundaries. The structural
observer delegates the production cursor unchanged and is never installed for
primary cost samples.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter_ns
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from experiments.stage4b2.postgres_idempotency_check_characterization import (
    Layer2Context,
    Layer2Sample,
    Layer2SamplePlan,
    Layer2Schedule,
    Layer2StructuralSample,
    Layer2Verdict,
    RunValidationResult,
    SCHEMA_VERSION,
    T_SETUP_SQL_IDENTITY,
    TransactionStatusIdentity,
    generate_recorded_schedule,
    generate_smoke_schedule,
    validate_run,
    validate_structural_run,
)


CANONICAL_AMOUNT = Decimal("100.00")
CONFLICTING_AMOUNT = Decimal("999.00")


class Layer2RuntimeError(RuntimeError):
    """Report experiment-owned setup, clock, or verification failures."""


@dataclass(frozen=True)
class TimedCheckCall:
    """Retain the check boundary's value or ordinary exception type."""

    value: Any | None
    elapsed_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_elapsed(self.elapsed_ns)
        if self.exception_type is None and self.value is None:
            raise ValueError("normal check timing requires a value")
        if self.exception_type is not None:
            if not self.exception_type or self.value is not None:
                raise ValueError("exception timing retains only a type name")


@dataclass(frozen=True)
class TimedCleanupCall:
    """Retain cleanup elapsed independently from the check boundary."""

    elapsed_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        _require_elapsed(self.elapsed_ns)
        if self.exception_type is not None and not self.exception_type:
            raise ValueError("exception_type must be a non-empty type name")


@dataclass(frozen=True)
class Layer2RuntimeResult:
    """Return one complete primary schedule and structural validation result."""

    schedule: Layer2Schedule
    samples: tuple[Layer2Sample, ...]
    validation: RunValidationResult


@dataclass(frozen=True)
class Layer2StructuralRuntimeResult:
    """Return the separate nine-cell SQL-observation result."""

    schedule: Layer2Schedule
    samples: tuple[Layer2StructuralSample, ...]
    validation: RunValidationResult


@dataclass(frozen=True)
class _Fixture:
    signature: Any
    seed_signature: Any | None
    accepted_event: Any | None


class _ContextSession:
    """Own experiment setup around one exact production store instance."""

    def __init__(self, store: Any, cleanup: Callable[[], None], uow: Any) -> None:
        self.store = store
        self.cleanup = cleanup
        self._uow = uow

    def finish_after_cleanup(self, cleanup_succeeded: bool) -> None:
        """Close an explicitly finished UOW without adding finalization SQL."""

        if self._uow is not None and cleanup_succeeded:
            self._uow.__exit__(None, None, None)


class _ObservedConnection:
    """Delegate one real connection while observing cursor.execute identities."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self.normalized_sql_identities: list[str] = []

    def cursor(self, *args: Any, **kwargs: Any) -> Any:
        return _ObservedCursor(
            self._connection.cursor(*args, **kwargs),
            self.normalized_sql_identities,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


class _ObservedCursor:
    """Record SQL text, then delegate execution/fetch/hydration unchanged."""

    def __init__(self, cursor: Any, identities: list[str]) -> None:
        self._cursor = cursor
        self._identities = identities

    def __enter__(self) -> _ObservedCursor:
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        return self._cursor.__exit__(exc_type, exc, traceback)

    def execute(self, query: Any, params: Any = None, **kwargs: Any) -> Any:
        self._identities.append(normalize_sql_identity(query))
        return self._cursor.execute(query, params, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def time_check_call(
    invocation: Callable[[], Any],
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> TimedCheckCall:
    """Time exactly one production check call and catch ordinary Exception."""

    started_ns = _read_clock(clock)
    try:
        value = invocation()
    except Exception as exc:
        stopped_ns = _read_clock(clock)
        return TimedCheckCall(
            value=None,
            elapsed_ns=_elapsed(started_ns, stopped_ns),
            exception_type=type(exc).__name__,
        )
    stopped_ns = _read_clock(clock)
    return TimedCheckCall(
        value=value,
        elapsed_ns=_elapsed(started_ns, stopped_ns),
    )


def time_cleanup_call(
    cleanup: Callable[[], None],
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> TimedCleanupCall:
    """Time only one context-appropriate finalization call."""

    started_ns = _read_clock(clock)
    try:
        cleanup()
    except Exception as exc:
        stopped_ns = _read_clock(clock)
        return TimedCleanupCall(
            elapsed_ns=_elapsed(started_ns, stopped_ns),
            exception_type=type(exc).__name__,
        )
    stopped_ns = _read_clock(clock)
    return TimedCleanupCall(elapsed_ns=_elapsed(started_ns, stopped_ns))


def execute_fixed_schedule(
    schedule: Layer2Schedule,
    execute_one: Callable[[Layer2SamplePlan], Any],
) -> tuple[Any, ...]:
    """Execute each predeclared cell once, without replacement or retry."""

    return tuple(execute_one(plan) for plan in schedule.samples)


def normalize_sql_identity(query: Any) -> str:
    """Normalize whitespace in SQL text observed from the production cursor."""

    if not isinstance(query, str):
        raise Layer2RuntimeError("structural observer expected current string SQL")
    normalized = " ".join(query.split())
    if not normalized:
        raise Layer2RuntimeError("structural observer received empty SQL")
    return normalized


def run_layer2_smoke(
    database_url: str,
    *,
    run_id: str,
    clock: Callable[[], int] = perf_counter_ns,
) -> Layer2RuntimeResult:
    """Run one primary-cost correctness smoke for every exact cell."""

    return _run_primary_schedule(
        database_url=database_url,
        run_id=run_id,
        schedule=generate_smoke_schedule(),
        clock=clock,
    )


def run_layer2_recorded(
    database_url: str,
    *,
    run_id: str,
    clock: Callable[[], int] = perf_counter_ns,
) -> Layer2RuntimeResult:
    """Run the fixed 270-sample schedule only when separately authorized."""

    return _run_primary_schedule(
        database_url=database_url,
        run_id=run_id,
        schedule=generate_recorded_schedule(),
        clock=clock,
    )


def run_layer2_structural(
    database_url: str,
    *,
    run_id: str,
) -> Layer2StructuralRuntimeResult:
    """Run the separate low-observation nine-cell SQL characterization."""

    _require_runtime_inputs(database_url, run_id)
    schedule = generate_smoke_schedule()
    control, subject = _open_guarded_connections(database_url)
    connections = (control, subject)
    try:
        def execute(plan: Layer2SamplePlan) -> Layer2StructuralSample:
            _reset_database(control, connections)
            fixture = _build_fixture(run_id, plan)
            _seed_fixture(control, fixture)
            return _execute_structural_sample(
                run_id=run_id,
                plan=plan,
                fixture=fixture,
                connection=subject,
            )

        samples = execute_fixed_schedule(schedule, execute)
        return Layer2StructuralRuntimeResult(
            schedule=schedule,
            samples=samples,
            validation=validate_structural_run(schedule, samples),
        )
    finally:
        _close_connections(connections)


def _run_primary_schedule(
    *,
    database_url: str,
    run_id: str,
    schedule: Layer2Schedule,
    clock: Callable[[], int],
) -> Layer2RuntimeResult:
    _require_runtime_inputs(database_url, run_id)
    control, subject = _open_guarded_connections(database_url)
    connections = (control, subject)
    try:
        def execute(plan: Layer2SamplePlan) -> Layer2Sample:
            _reset_database(control, connections)
            fixture = _build_fixture(run_id, plan)
            _seed_fixture(control, fixture)
            return _execute_primary_sample(
                run_id=run_id,
                plan=plan,
                fixture=fixture,
                connection=subject,
                clock=clock,
            )

        samples = execute_fixed_schedule(schedule, execute)
        return Layer2RuntimeResult(
            schedule=schedule,
            samples=samples,
            validation=validate_run(schedule, samples),
        )
    finally:
        _close_connections(connections)


def _execute_primary_sample(
    *,
    run_id: str,
    plan: Layer2SamplePlan,
    fixture: _Fixture,
    connection: Any,
    clock: Callable[[], int],
) -> Layer2Sample:
    session = _prepare_context(connection, plan.cell.context)
    before = _transaction_status(connection)
    checked = time_check_call(
        lambda: session.store.check(fixture.signature),
        clock=clock,
    )
    after_check = _transaction_status(connection)
    cleaned = time_cleanup_call(session.cleanup, clock=clock)
    after_cleanup = _transaction_status(connection)
    session.finish_after_cleanup(cleaned.exception_type is None)
    reuse_ok, final_status = _verify_reuse(connection)

    exception_type = checked.exception_type or cleaned.exception_type
    returned = (
        None
        if checked.value is None
        else _returned_verdict(checked.value)
    )
    return Layer2Sample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        sample_index=plan.sample_index,
        planned_context=plan.cell.context,
        planned_verdict=plan.cell.verdict,
        returned_verdict=returned,
        check_elapsed_ns=checked.elapsed_ns,
        cleanup_elapsed_ns=cleaned.elapsed_ns,
        transaction_status_before_check=before,
        transaction_status_after_check=after_check,
        transaction_status_after_cleanup=after_cleanup,
        reuse_select_succeeded=reuse_ok,
        final_transaction_status=final_status,
        exception_type=exception_type,
    )


def _execute_structural_sample(
    *,
    run_id: str,
    plan: Layer2SamplePlan,
    fixture: _Fixture,
    connection: Any,
) -> Layer2StructuralSample:
    observed_connection = _ObservedConnection(connection)
    session = _prepare_context(
        connection,
        plan.cell.context,
        store_connection=observed_connection,
    )
    before = _transaction_status(connection)
    decision = None
    exception_type = None
    try:
        decision = session.store.check(fixture.signature)
    except Exception as exc:
        exception_type = type(exc).__name__
    after_check = _transaction_status(connection)
    cleanup_succeeded = True
    try:
        session.cleanup()
    except Exception as exc:
        cleanup_succeeded = False
        exception_type = exception_type or type(exc).__name__
    after_cleanup = _transaction_status(connection)
    session.finish_after_cleanup(cleanup_succeeded)
    reuse_ok, final_status = _verify_reuse(connection)

    return Layer2StructuralSample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        sample_index=plan.sample_index,
        planned_context=plan.cell.context,
        planned_verdict=plan.cell.verdict,
        returned_verdict=(None if decision is None else _returned_verdict(decision)),
        transaction_status_before_check=before,
        transaction_status_after_check=after_check,
        transaction_status_after_cleanup=after_cleanup,
        reuse_select_succeeded=reuse_ok,
        final_transaction_status=final_status,
        check_sql_statement_count=len(
            observed_connection.normalized_sql_identities
        ),
        normalized_check_sql_identities=tuple(
            observed_connection.normalized_sql_identities
        ),
        setup_sql_identity=(
            T_SETUP_SQL_IDENTITY
            if plan.cell.context is Layer2Context.T
            else None
        ),
        exception_type=exception_type,
    )


def _prepare_context(
    connection: Any,
    context: Layer2Context,
    *,
    store_connection: Any | None = None,
) -> _ContextSession:
    from src.pipeline.transactional.postgres_unit_of_work import (
        PostgresWriteSideUnitOfWork,
    )
    from src.storage.postgres_idempotency_store import PostgresIdempotencyStore

    owned_connection = connection if store_connection is None else store_connection
    if context is Layer2Context.P:
        return _ContextSession(
            PostgresIdempotencyStore(owned_connection),
            connection.rollback,
            None,
        )

    uow = PostgresWriteSideUnitOfWork(owned_connection)
    uow.__enter__()
    if context is Layer2Context.T:
        with connection.cursor() as cursor:
            cursor.execute(T_SETUP_SQL_IDENTITY)
            if cursor.fetchone() != (1,):
                raise Layer2RuntimeError("T neutral SELECT 1 did not return one")
    elif context is not Layer2Context.U:
        raise Layer2RuntimeError("unknown Layer-2 context")
    return _ContextSession(uow.idempotency_store, uow.rollback, uow)


def _build_fixture(run_id: str, plan: Layer2SamplePlan) -> _Fixture:
    from src.core.order.enums import CommandType, EventType, OrderStatus
    from src.core.order.events import OrderEvent
    from src.core.order.proofs import Proof
    from src.storage.idempotency_store import RequestSignature

    token = f"layer2:{run_id}:{plan.sample_index}:{plan.cell.identity}"
    request_id = str(uuid5(NAMESPACE_URL, f"{token}:request"))
    order_id = str(uuid5(NAMESPACE_URL, f"{token}:order"))
    signature = RequestSignature(
        request_id=request_id,
        command_type=CommandType.CREATE,
        order_id=order_id,
        amount=CANONICAL_AMOUNT,
    )
    if plan.cell.verdict is Layer2Verdict.MISS:
        return _Fixture(signature, None, None)

    seed_amount = (
        CANONICAL_AMOUNT
        if plan.cell.verdict is Layer2Verdict.REPLAY
        else CONFLICTING_AMOUNT
    )
    seed_signature = RequestSignature(
        request_id=request_id,
        command_type=CommandType.CREATE,
        order_id=order_id,
        amount=seed_amount,
    )
    accepted_event = OrderEvent(
        event_id=str(uuid5(NAMESPACE_URL, f"{token}:accepted-event")),
        request_id=request_id,
        order_id=order_id,
        sequence=1,
        event_type=EventType.CREATED,
        amount=seed_amount,
        occurred_at_ms=1_700_000_000_000 + plan.sample_index,
        proof=Proof(
            prev_event_id=None,
            prev_version=0,
            prev_status=OrderStatus.INIT,
        ),
    )
    return _Fixture(signature, seed_signature, accepted_event)


def _seed_fixture(connection: Any, fixture: _Fixture) -> None:
    if fixture.seed_signature is None:
        return
    from src.storage.postgres_event_store import PostgresEventStore
    from src.storage.postgres_idempotency_store import PostgresIdempotencyStore

    try:
        PostgresEventStore(connection).append(
            fixture.accepted_event,
            expected_current_version=0,
        )
        PostgresIdempotencyStore(connection).record(
            fixture.seed_signature,
            fixture.accepted_event,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _returned_verdict(decision: Any) -> Layer2Verdict:
    raw = getattr(getattr(decision, "verdict", None), "value", None)
    if not isinstance(raw, str):
        raise Layer2RuntimeError("production check returned an invalid verdict")
    try:
        return Layer2Verdict(raw.upper())
    except ValueError as exc:
        raise Layer2RuntimeError("production check returned an unknown verdict") from exc


def _open_guarded_connections(database_url: str) -> tuple[Any, Any]:
    _require_runtime_inputs(database_url, "guarded-open")
    from src.storage.postgres_connection import connect_postgres

    opened: list[Any] = []
    try:
        for _ in range(2):
            opened.append(connect_postgres(database_url))
        for connection in opened:
            _guard_test_connection(connection)
    except BaseException:
        _close_connections(tuple(opened))
        raise
    return opened[0], opened[1]


def _guard_test_connection(connection: Any) -> None:
    if connection.autocommit:
        raise Layer2RuntimeError("Layer 2 requires autocommit disabled")
    row = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
    finally:
        connection.rollback()
    if row is None or not isinstance(row[0], str) or not row[0].endswith("_test"):
        raise Layer2RuntimeError("refusing Layer 2 outside a database ending _test")
    reuse_ok, final = _verify_reuse(connection)
    if not reuse_ok or final is not TransactionStatusIdentity.IDLE:
        raise Layer2RuntimeError("guarded connection is not IDLE and reusable")


def _reset_database(control: Any, connections: tuple[Any, ...]) -> None:
    for connection in connections:
        reuse_ok, final = _verify_reuse(connection)
        if not reuse_ok or final is not TransactionStatusIdentity.IDLE:
            raise Layer2RuntimeError("pre-reset connection is not IDLE and reusable")
    with control.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE
                decision_receipts,
                projection_snapshots,
                projection_order_progress,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
    control.commit()
    for connection in connections:
        reuse_ok, final = _verify_reuse(connection)
        if not reuse_ok or final is not TransactionStatusIdentity.IDLE:
            raise Layer2RuntimeError("post-reset connection is not IDLE and reusable")


def _verify_reuse(connection: Any) -> tuple[bool, TransactionStatusIdentity]:
    reuse_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            reuse_ok = cursor.fetchone() == (1,)
    except Exception:
        reuse_ok = False
    finally:
        with suppress(Exception):
            connection.rollback()
    return reuse_ok, _transaction_status(connection)


def _transaction_status(connection: Any) -> TransactionStatusIdentity:
    name = getattr(connection.info.transaction_status, "name", None)
    try:
        return TransactionStatusIdentity(name)
    except ValueError:
        return TransactionStatusIdentity.UNKNOWN


def _close_connections(connections: tuple[Any, ...]) -> None:
    for connection in connections:
        with suppress(Exception):
            connection.rollback()
        connection.close()


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
        raise Layer2RuntimeError("clock moved backwards")
    return elapsed_ns


def _require_elapsed(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("elapsed_ns must be a non-negative integer")
