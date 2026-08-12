"""Deterministic Stage 4B.2 PR2 measurement-mechanics characterization.

Everything in this module is test-owned.  The helpers characterize clock,
boundary, topology, finalization, and delivery semantics against the current
write-side implementation without defining the later PR3 production contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import SimpleNamespace
from typing import Any, TypeVar, cast

import pytest
from psycopg import Connection

from src.compass.transition import validators as validators_module
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.compass.transition.validators import NoOpValidator
from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideExecution,
    PostgresWriteSideOutcome,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


class _Phase(str, Enum):
    """Test-owned names for candidate measurement boundaries."""

    WHOLE_WRITE_INVOCATION = "whole_write_invocation"
    BUSINESS_UOW_LIFECYCLE = "business_uow_lifecycle"
    VALIDATION_RUNTIME_CALL = "validation_runtime_call"
    VALIDATOR_LOCAL = "validator_local"
    PRELIMINARY_IDEMPOTENCY_CHECK = "preliminary_idempotency_check"
    PRELIMINARY_READ_CLEANUP = "preliminary_read_cleanup"
    AUTHORITATIVE_IDEMPOTENCY_CHECK = "authoritative_idempotency_check"
    ACCEPTED_HISTORY_LOAD = "accepted_history_load"
    CONCURRENCY_PREPARATION_CALL = "concurrency_preparation_call"
    PESSIMISTIC_ADVISORY_TRY_LOCK_CALL = (
        "pessimistic_advisory_try_lock_call"
    )
    APPEND_ADMISSION_CALL = "append_admission_call"
    IDEMPOTENCY_RECORD_CALL = "idempotency_record_call"
    COMMIT_FINALIZATION = "commit_finalization"
    ROLLBACK_FINALIZATION = "rollback_finalization"


class _Presence(str, Enum):
    """Test-only proof vocabulary, not a proposed PR3 representation."""

    NOT_APPLICABLE = "not_applicable"
    NOT_REACHED = "not_reached"
    NOT_COLLECTED = "not_collected"
    MEASURED = "measured"


class _Availability(str, Enum):
    """Test-only post-UOW delivery states."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class _Interval:
    """Retain raw integer clock readings for deterministic assertions."""

    started_ns: int
    stopped_ns: int

    @property
    def elapsed_ns(self) -> int:
        return self.stopped_ns - self.started_ns

    def contains(self, other: _Interval) -> bool:
        return (
            self.started_ns <= other.started_ns
            and other.stopped_ns <= self.stopped_ns
        )


@dataclass
class _ManualClock:
    """Smallest fake for the candidate ``perf_counter_ns``-shaped seam."""

    now_ns: int = 0

    def perf_counter_ns(self) -> int:
        return self.now_ns

    def advance(self, elapsed_ns: int) -> None:
        if elapsed_ns < 0:
            raise ValueError("manual clock cannot move backwards")
        self.now_ns += elapsed_ns


_T = TypeVar("_T")


@dataclass
class _Probe:
    """Record only normally completed intervals around current call sites."""

    clock: _ManualClock
    suppressed: set[_Phase] = field(default_factory=set)
    reached: set[_Phase] = field(default_factory=set)
    intervals: dict[_Phase, _Interval] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    def call(self, phase: _Phase, operation: Callable[[], _T]) -> _T:
        self.reached.add(phase)
        self.events.append(f"{phase.value}:start")
        if phase in self.suppressed:
            return operation()

        started_ns = self.clock.perf_counter_ns()
        result = operation()
        stopped_ns = self.clock.perf_counter_ns()
        self.intervals[phase] = _Interval(started_ns, stopped_ns)
        self.events.append(f"{phase.value}:stop")
        return result

    def start(self, phase: _Phase) -> int | None:
        self.reached.add(phase)
        self.events.append(f"{phase.value}:start")
        if phase in self.suppressed:
            return None
        return self.clock.perf_counter_ns()

    def finish(self, phase: _Phase, started_ns: int | None) -> None:
        if started_ns is None:
            return
        self.intervals[phase] = _Interval(
            started_ns,
            self.clock.perf_counter_ns(),
        )
        self.events.append(f"{phase.value}:stop")

    def interval(self, phase: _Phase) -> _Interval:
        return self.intervals[phase]

    def presence(
        self,
        phase: _Phase,
        *,
        applicable: set[_Phase],
    ) -> _Presence:
        if phase not in applicable:
            return _Presence.NOT_APPLICABLE
        if phase not in self.reached:
            return _Presence.NOT_REACHED
        if phase not in self.intervals:
            return _Presence.NOT_COLLECTED
        return _Presence.MEASURED


_DURATION_NS = {
    _Phase.VALIDATOR_LOCAL: 7,
    _Phase.PRELIMINARY_IDEMPOTENCY_CHECK: 11,
    _Phase.PRELIMINARY_READ_CLEANUP: 13,
    _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK: 17,
    _Phase.ACCEPTED_HISTORY_LOAD: 19,
    _Phase.CONCURRENCY_PREPARATION_CALL: 23,
    _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL: 5,
    _Phase.APPEND_ADMISSION_CALL: 29,
    _Phase.IDEMPOTENCY_RECORD_CALL: 31,
    _Phase.COMMIT_FINALIZATION: 37,
    _Phase.ROLLBACK_FINALIZATION: 41,
}


class _CommitFailure(RuntimeError):
    pass


class _RollbackFailure(RuntimeError):
    pass


class _ProducerFailure(RuntimeError):
    pass


class _MeasurementConstructionFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class _Scenario:
    placement: ValidationPlacement
    idempotency_verdicts: tuple[IdempotencyVerdict, ...]
    validation_action: EnforcementAction = EnforcementAction.ALLOW
    preparation_admitted: bool = True
    append_admitted: bool = True
    pessimistic: bool = False
    validation_raises: bool = False
    commit_raises: bool = False
    rollback_raises: bool = False


class _FakeConnection:
    """Connection double retaining current UOW commit/rollback behavior."""

    def __init__(self, scenario: _Scenario, probe: _Probe) -> None:
        self.autocommit = False
        self.scenario = scenario
        self.probe = probe
        self.history = []
        self.idempotency_check_index = 0
        self.inside_uow = False
        self.inside_uow_rollback = False
        self.commit_calls = 0
        self.rollback_calls = 0
        self.committed = False

    def commit(self) -> None:
        self.commit_calls += 1
        self.probe.clock.advance(_DURATION_NS[_Phase.COMMIT_FINALIZATION])
        if self.scenario.commit_raises:
            raise _CommitFailure("commit failed")
        self.committed = True

    def rollback(self) -> None:
        self.rollback_calls += 1
        if self.inside_uow_rollback:
            self.probe.clock.advance(
                _DURATION_NS[_Phase.ROLLBACK_FINALIZATION]
            )
            if self.scenario.rollback_raises:
                raise _RollbackFailure("rollback failed")
            return

        def clean_preliminary_read() -> None:
            self.probe.clock.advance(
                _DURATION_NS[_Phase.PRELIMINARY_READ_CLEANUP]
            )

        self.probe.call(
            _Phase.PRELIMINARY_READ_CLEANUP,
            clean_preliminary_read,
        )


def _idempotency_decision(
    verdict: IdempotencyVerdict,
    signature: RequestSignature,
) -> IdempotencyDecision:
    if verdict is IdempotencyVerdict.MISS:
        return IdempotencyDecision(verdict=verdict, reason="test-owned miss")

    aggregate = OrderAggregate(signature.order_id)
    accepted_event = aggregate.create(
        request_id=signature.request_id,
        total_amount=signature.amount,
    )
    record = IdempotencyRecord(
        signature=signature,
        accepted_event=accepted_event,
    )
    return IdempotencyDecision(
        verdict=verdict,
        reason="test-owned replay or conflict",
        record=record,
    )


class _MeasuredValidationRuntime:
    """Deterministic nested runtime/validator timing without real latency."""

    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def decide(self, candidate_event, context) -> ValidationDecision:
        probe = self._connection.probe

        def decide() -> ValidationDecision:
            probe.clock.advance(3)
            if self._connection.scenario.validation_raises:
                raise _ProducerFailure("validation producer failed")

            def validate() -> ValidationResult:
                probe.clock.advance(_DURATION_NS[_Phase.VALIDATOR_LOCAL])
                verdict = (
                    ValidationVerdict.PASSED
                    if self._connection.scenario.validation_action
                    is EnforcementAction.ALLOW
                    else ValidationVerdict.FAILED
                )
                return ValidationResult(
                    verdict=verdict,
                    reason="test-owned deterministic validation",
                    candidate_event_id=candidate_event.event_id,
                    validator_name=self.__class__.__name__,
                    validation_mode=ValidationMode.STRICT,
                    logic_validation_time_ms=0.0,
                    io_time_ms=0.0,
                    total_time_ms=(
                        _DURATION_NS[_Phase.VALIDATOR_LOCAL] / 1_000_000
                    ),
                    metadata={},
                )

            validation_result = probe.call(_Phase.VALIDATOR_LOCAL, validate)
            probe.clock.advance(5)
            return ValidationDecision(
                action=self._connection.scenario.validation_action,
                validation_result=validation_result,
            )

        return probe.call(_Phase.VALIDATION_RUNTIME_CALL, decide)


class _MeasuredOptimisticGate(PostgresOptimisticAdmissionGate):
    def __init__(self, uow: PostgresWriteSideUnitOfWork) -> None:
        super().__init__(uow.event_store)
        self._connection = cast(_FakeConnection, uow.connection)

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        probe = self._connection.probe

        def prepare() -> StreamAdmissionResult:
            probe.clock.advance(
                _DURATION_NS[_Phase.CONCURRENCY_PREPARATION_CALL]
            )
            return super(_MeasuredOptimisticGate, self).prepare_stream(order_id)

        return probe.call(_Phase.CONCURRENCY_PREPARATION_CALL, prepare)

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        return self._connection.probe.call(
            _Phase.APPEND_ADMISSION_CALL,
            lambda: super(_MeasuredOptimisticGate, self).append_if_admitted(
                candidate_event,
                expected_current_version,
            ),
        )


class _MeasuredPessimisticGate(PostgresPessimisticAdmissionGate):
    def __init__(self, uow: PostgresWriteSideUnitOfWork) -> None:
        super().__init__(
            connection=uow.connection,
            event_store=uow.event_store,
        )
        self._connection = cast(_FakeConnection, uow.connection)

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        probe = self._connection.probe

        def prepare() -> StreamAdmissionResult:
            probe.clock.advance(2)
            result = super(_MeasuredPessimisticGate, self).prepare_stream(
                order_id
            )
            probe.clock.advance(3)
            return result

        return probe.call(_Phase.CONCURRENCY_PREPARATION_CALL, prepare)

    def _try_lock_stream(self, order_id: str) -> bool:
        probe = self._connection.probe

        def try_lock() -> bool:
            probe.clock.advance(
                _DURATION_NS[_Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL]
            )
            return self._connection.scenario.preparation_admitted

        return probe.call(
            _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL,
            try_lock,
        )

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        return self._connection.probe.call(
            _Phase.APPEND_ADMISSION_CALL,
            lambda: super(_MeasuredPessimisticGate, self).append_if_admitted(
                candidate_event,
                expected_current_version,
            ),
        )


class _MeasuredRejectingGate:
    """Exercise the current injectable PRE preparation-rejection path."""

    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        def reject() -> StreamAdmissionResult:
            self._connection.probe.clock.advance(
                _DURATION_NS[_Phase.CONCURRENCY_PREPARATION_CALL]
            )
            return StreamAdmissionResult(
                verdict=AdmissionVerdict.LOCK_TIMEOUT,
                reason="test-owned preparation rejection",
                order_id=order_id,
            )

        return self._connection.probe.call(
            _Phase.CONCURRENCY_PREPARATION_CALL,
            reject,
        )

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        raise AssertionError("append must not follow preparation rejection")


def _install_source_boundary_probe(monkeypatch) -> None:
    """Wrap current source boundaries without changing production modules."""

    original_enter = PostgresWriteSideUnitOfWork.__enter__
    original_exit = PostgresWriteSideUnitOfWork.__exit__
    original_commit = PostgresWriteSideUnitOfWork.commit
    original_rollback = PostgresWriteSideUnitOfWork.rollback

    def enter(uow):
        connection = cast(_FakeConnection, uow.connection)
        started_ns = connection.probe.start(_Phase.BUSINESS_UOW_LIFECYCLE)
        entered = original_enter(uow)
        connection.inside_uow = True
        setattr(uow, "_measurement_characterization_start", started_ns)
        return entered

    def exit_uow(uow, exc_type, exc, traceback):
        connection = cast(_FakeConnection, uow.connection)
        try:
            result = original_exit(uow, exc_type, exc, traceback)
        finally:
            connection.inside_uow = False

        connection.probe.finish(
            _Phase.BUSINESS_UOW_LIFECYCLE,
            getattr(uow, "_measurement_characterization_start"),
        )
        return result

    def commit(uow):
        connection = cast(_FakeConnection, uow.connection)
        return connection.probe.call(
            _Phase.COMMIT_FINALIZATION,
            lambda: original_commit(uow),
        )

    def rollback(uow):
        connection = cast(_FakeConnection, uow.connection)

        def finalize() -> None:
            connection.inside_uow_rollback = True
            try:
                original_rollback(uow)
            finally:
                connection.inside_uow_rollback = False

        return connection.probe.call(_Phase.ROLLBACK_FINALIZATION, finalize)

    def check_idempotency(store, signature):
        connection = cast(_FakeConnection, store._connection)
        phase = (
            _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK
            if connection.inside_uow
            else _Phase.PRELIMINARY_IDEMPOTENCY_CHECK
        )

        def check() -> IdempotencyDecision:
            connection.probe.clock.advance(_DURATION_NS[phase])
            try:
                verdict = connection.scenario.idempotency_verdicts[
                    connection.idempotency_check_index
                ]
            except IndexError as exc:
                raise AssertionError("unexpected idempotency check") from exc
            connection.idempotency_check_index += 1
            return _idempotency_decision(verdict, signature)

        return connection.probe.call(phase, check)

    def record_idempotency(store, signature, accepted_event):
        connection = cast(_FakeConnection, store._connection)

        def record() -> None:
            connection.probe.clock.advance(
                _DURATION_NS[_Phase.IDEMPOTENCY_RECORD_CALL]
            )

        return connection.probe.call(_Phase.IDEMPOTENCY_RECORD_CALL, record)

    def load_history(store, order_id):
        connection = cast(_FakeConnection, store._connection)

        def load():
            connection.probe.clock.advance(
                _DURATION_NS[_Phase.ACCEPTED_HISTORY_LOAD]
            )
            return list(connection.history)

        return connection.probe.call(_Phase.ACCEPTED_HISTORY_LOAD, load)

    def append_event(store, candidate_event, expected_current_version):
        connection = cast(_FakeConnection, store._connection)
        connection.probe.clock.advance(
            _DURATION_NS[_Phase.APPEND_ADMISSION_CALL]
        )
        if not connection.scenario.append_admitted:
            raise ValueError("test-owned stale write")

    monkeypatch.setattr(PostgresWriteSideUnitOfWork, "__enter__", enter)
    monkeypatch.setattr(PostgresWriteSideUnitOfWork, "__exit__", exit_uow)
    monkeypatch.setattr(PostgresWriteSideUnitOfWork, "commit", commit)
    monkeypatch.setattr(PostgresWriteSideUnitOfWork, "rollback", rollback)
    monkeypatch.setattr(PostgresIdempotencyStore, "check", check_idempotency)
    monkeypatch.setattr(PostgresIdempotencyStore, "record", record_idempotency)
    monkeypatch.setattr(PostgresEventStore, "load", load_history)
    monkeypatch.setattr(PostgresEventStore, "append", append_event)


def _build_write_side(
    connection: _FakeConnection,
) -> PostgresTransactionalWriteSide:
    if (
        connection.scenario.placement is ValidationPlacement.PRE_TRANSACTION
        and not connection.scenario.preparation_admitted
    ):
        gate_factory = lambda uow: _MeasuredRejectingGate(connection)
    elif connection.scenario.pessimistic:
        gate_factory = _MeasuredPessimisticGate
    else:
        gate_factory = _MeasuredOptimisticGate

    return PostgresTransactionalWriteSide(
        connection=cast(Connection, connection),
        validation_runtime=cast(
            ValidationRuntime,
            _MeasuredValidationRuntime(connection),
        ),
        admission_gate_factory=gate_factory,
        config=PostgresWriteSideConfig(
            validation_placement=connection.scenario.placement
        ),
    )


@dataclass(frozen=True)
class _MeasurementSnapshot:
    """Test-only snapshot; deliberately not the future PR3 contract."""

    intervals: tuple[tuple[_Phase, _Interval], ...]


@dataclass(frozen=True)
class _Delivery:
    """Test-only result-first delivery prototype for the PR2 safety proof."""

    producer_value: Any
    measurement: _MeasurementSnapshot | None
    availability: _Availability


def _build_snapshot(probe: _Probe) -> _MeasurementSnapshot:
    probe.events.append("measurement_construction:start")
    snapshot = _MeasurementSnapshot(tuple(probe.intervals.items()))
    probe.events.append("measurement_construction:stop")
    return snapshot


def _deliver_after_uow(
    operation: Callable[[], _T],
    probe: _Probe,
    *,
    build_measurement: Callable[[_Probe], _MeasurementSnapshot] = _build_snapshot,
) -> _Delivery:
    """Prototype a post-UOW result-first delivery without changing an API."""

    started_ns = probe.start(_Phase.WHOLE_WRITE_INVOCATION)
    producer_value = operation()
    probe.finish(_Phase.WHOLE_WRITE_INVOCATION, started_ns)

    try:
        measurement = build_measurement(probe)
    except _MeasurementConstructionFailure:
        return _Delivery(
            producer_value=producer_value,
            measurement=None,
            availability=_Availability.UNAVAILABLE,
        )

    return _Delivery(
        producer_value=producer_value,
        measurement=measurement,
        availability=_Availability.AVAILABLE,
    )


def _execute_scenario(
    monkeypatch,
    scenario: _Scenario,
    *,
    with_trace: bool = False,
    build_measurement: Callable[[_Probe], _MeasurementSnapshot] = _build_snapshot,
) -> tuple[_Delivery, _FakeConnection, _Probe]:
    _install_source_boundary_probe(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(scenario, probe)
    write_side = _build_write_side(connection)
    if with_trace:
        operation = lambda: write_side.create_order_with_trace(
            request_id="characterization-request",
            order_id="characterization-order",
            amount=Decimal("100.00"),
        )
    else:
        operation = lambda: write_side.create_order(
            request_id="characterization-request",
            order_id="characterization-order",
            amount=Decimal("100.00"),
        )
    delivery = _deliver_after_uow(
        operation,
        probe,
        build_measurement=build_measurement,
    )
    return delivery, connection, probe


@dataclass(frozen=True)
class _PathCase:
    name: str
    scenario: _Scenario
    outcome: PostgresWriteSideOutcome
    measured_phases: frozenset[_Phase]


_WHOLE = {_Phase.WHOLE_WRITE_INVOCATION}
_PRE_BEFORE_VALIDATION = {
    _Phase.PRELIMINARY_IDEMPOTENCY_CHECK,
    _Phase.PRELIMINARY_READ_CLEANUP,
}
_PRE_THROUGH_VALIDATION = {
    *_PRE_BEFORE_VALIDATION,
    _Phase.ACCEPTED_HISTORY_LOAD,
    _Phase.VALIDATION_RUNTIME_CALL,
    _Phase.VALIDATOR_LOCAL,
}
_UOW_AUTH_ROLLBACK = {
    _Phase.BUSINESS_UOW_LIFECYCLE,
    _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
    _Phase.ROLLBACK_FINALIZATION,
}
_IN_PREP = {
    _Phase.BUSINESS_UOW_LIFECYCLE,
    _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
    _Phase.CONCURRENCY_PREPARATION_CALL,
    _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL,
}


PATH_CASES = (
    _PathCase(
        "pre preliminary replay",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
        ),
        PostgresWriteSideOutcome.REPLAY,
        frozenset(_WHOLE | _PRE_BEFORE_VALIDATION),
    ),
    _PathCase(
        "pre preliminary conflict",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.CONFLICT,),
        ),
        PostgresWriteSideOutcome.CONFLICT,
        frozenset(_WHOLE | _PRE_BEFORE_VALIDATION),
    ),
    _PathCase(
        "pre validation block",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            validation_action=EnforcementAction.BLOCK,
        ),
        PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        frozenset(_WHOLE | _PRE_THROUGH_VALIDATION),
    ),
    _PathCase(
        "pre authoritative replay",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.REPLAY),
        ),
        PostgresWriteSideOutcome.REPLAY,
        frozenset(_WHOLE | _PRE_THROUGH_VALIDATION | _UOW_AUTH_ROLLBACK),
    ),
    _PathCase(
        "pre authoritative conflict",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.CONFLICT),
        ),
        PostgresWriteSideOutcome.CONFLICT,
        frozenset(_WHOLE | _PRE_THROUGH_VALIDATION | _UOW_AUTH_ROLLBACK),
    ),
    _PathCase(
        "pre preparation rejection",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
            preparation_admitted=False,
        ),
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        frozenset(
            _WHOLE
            | _PRE_THROUGH_VALIDATION
            | _UOW_AUTH_ROLLBACK
            | {_Phase.CONCURRENCY_PREPARATION_CALL}
        ),
    ),
    _PathCase(
        "pre stale append",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
            append_admitted=False,
        ),
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        frozenset(
            _WHOLE
            | _PRE_THROUGH_VALIDATION
            | _UOW_AUTH_ROLLBACK
            | {
                _Phase.CONCURRENCY_PREPARATION_CALL,
                _Phase.APPEND_ADMISSION_CALL,
            }
        ),
    ),
    _PathCase(
        "pre accepted",
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        PostgresWriteSideOutcome.ACCEPTED,
        frozenset(
            _WHOLE
            | _PRE_THROUGH_VALIDATION
            | {
                _Phase.BUSINESS_UOW_LIFECYCLE,
                _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
                _Phase.CONCURRENCY_PREPARATION_CALL,
                _Phase.APPEND_ADMISSION_CALL,
                _Phase.IDEMPOTENCY_RECORD_CALL,
                _Phase.COMMIT_FINALIZATION,
            }
        ),
    ),
    _PathCase(
        "in authoritative replay",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.REPLAY,
        frozenset(_WHOLE | _UOW_AUTH_ROLLBACK),
    ),
    _PathCase(
        "in authoritative conflict",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.CONFLICT,),
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.CONFLICT,
        frozenset(_WHOLE | _UOW_AUTH_ROLLBACK),
    ),
    _PathCase(
        "in preparation rejection",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            preparation_admitted=False,
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        frozenset(_WHOLE | _IN_PREP | {_Phase.ROLLBACK_FINALIZATION}),
    ),
    _PathCase(
        "in validation block",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            validation_action=EnforcementAction.BLOCK,
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        frozenset(
            _WHOLE
            | _IN_PREP
            | {
                _Phase.ACCEPTED_HISTORY_LOAD,
                _Phase.VALIDATION_RUNTIME_CALL,
                _Phase.VALIDATOR_LOCAL,
                _Phase.ROLLBACK_FINALIZATION,
            }
        ),
    ),
    _PathCase(
        "in append rejection",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            append_admitted=False,
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        frozenset(
            _WHOLE
            | _IN_PREP
            | {
                _Phase.ACCEPTED_HISTORY_LOAD,
                _Phase.VALIDATION_RUNTIME_CALL,
                _Phase.VALIDATOR_LOCAL,
                _Phase.APPEND_ADMISSION_CALL,
                _Phase.ROLLBACK_FINALIZATION,
            }
        ),
    ),
    _PathCase(
        "in accepted",
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        PostgresWriteSideOutcome.ACCEPTED,
        frozenset(
            _WHOLE
            | _IN_PREP
            | {
                _Phase.ACCEPTED_HISTORY_LOAD,
                _Phase.VALIDATION_RUNTIME_CALL,
                _Phase.VALIDATOR_LOCAL,
                _Phase.APPEND_ADMISSION_CALL,
                _Phase.IDEMPOTENCY_RECORD_CALL,
                _Phase.COMMIT_FINALIZATION,
            }
        ),
    ),
)


def test_manual_perf_counter_ns_seam_preserves_nonzero_and_zero_measurements():
    probe = _Probe(_ManualClock())

    probe.call(
        _Phase.PRELIMINARY_IDEMPOTENCY_CHECK,
        lambda: probe.clock.advance(37),
    )
    probe.call(_Phase.PRELIMINARY_READ_CLEANUP, lambda: None)

    assert (
        probe.interval(_Phase.PRELIMINARY_IDEMPOTENCY_CHECK).elapsed_ns == 37
    )
    assert probe.interval(_Phase.PRELIMINARY_READ_CLEANUP).elapsed_ns == 0
    assert all(
        type(reading) is int
        for interval in probe.intervals.values()
        for reading in (interval.started_ns, interval.stopped_ns)
    )


def test_presence_semantics_keep_four_states_distinct():
    probe = _Probe(
        _ManualClock(),
        suppressed={_Phase.VALIDATION_RUNTIME_CALL},
    )
    applicable = {
        _Phase.WHOLE_WRITE_INVOCATION,
        _Phase.BUSINESS_UOW_LIFECYCLE,
        _Phase.VALIDATION_RUNTIME_CALL,
    }

    probe.call(_Phase.WHOLE_WRITE_INVOCATION, lambda: None)
    probe.call(_Phase.VALIDATION_RUNTIME_CALL, lambda: None)

    assert probe.presence(
        _Phase.PRELIMINARY_IDEMPOTENCY_CHECK,
        applicable=applicable,
    ) is _Presence.NOT_APPLICABLE
    assert probe.presence(
        _Phase.BUSINESS_UOW_LIFECYCLE,
        applicable=applicable,
    ) is _Presence.NOT_REACHED
    assert probe.presence(
        _Phase.VALIDATION_RUNTIME_CALL,
        applicable=applicable,
    ) is _Presence.NOT_COLLECTED
    assert probe.presence(
        _Phase.WHOLE_WRITE_INVOCATION,
        applicable=applicable,
    ) is _Presence.MEASURED
    assert probe.interval(_Phase.WHOLE_WRITE_INVOCATION).elapsed_ns == 0


@pytest.mark.parametrize("path_case", PATH_CASES, ids=lambda case: case.name)
def test_current_normal_return_paths_have_exact_measurement_presence(
    monkeypatch,
    path_case: _PathCase,
):
    delivery, connection, probe = _execute_scenario(
        monkeypatch,
        path_case.scenario,
    )

    assert delivery.producer_value.outcome is path_case.outcome
    assert set(probe.intervals) == set(path_case.measured_phases)
    assert connection.commit_calls == (
        1 if _Phase.COMMIT_FINALIZATION in path_case.measured_phases else 0
    )
    assert connection.committed is (
        _Phase.COMMIT_FINALIZATION in path_case.measured_phases
    )


@pytest.mark.parametrize(
    "scenario",
    [
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
    ],
    ids=["pre accepted", "in accepted"],
)
def test_accepted_intervals_preserve_containment_and_reject_additive_totals(
    monkeypatch,
    scenario: _Scenario,
):
    _, _, probe = _execute_scenario(monkeypatch, scenario)
    whole = probe.interval(_Phase.WHOLE_WRITE_INVOCATION)
    uow = probe.interval(_Phase.BUSINESS_UOW_LIFECYCLE)

    assert whole.contains(uow)
    for phase in (
        _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
        _Phase.CONCURRENCY_PREPARATION_CALL,
        _Phase.APPEND_ADMISSION_CALL,
        _Phase.IDEMPOTENCY_RECORD_CALL,
        _Phase.COMMIT_FINALIZATION,
    ):
        assert uow.contains(probe.interval(phase))

    validation = probe.interval(_Phase.VALIDATION_RUNTIME_CALL)
    assert validation.contains(probe.interval(_Phase.VALIDATOR_LOCAL))

    if scenario.placement is ValidationPlacement.IN_TRANSACTION:
        assert uow.contains(probe.interval(_Phase.ACCEPTED_HISTORY_LOAD))
        assert uow.contains(validation)
        preparation = probe.interval(_Phase.CONCURRENCY_PREPARATION_CALL)
        assert preparation.contains(
            probe.interval(_Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL)
        )
    else:
        assert not uow.contains(probe.interval(_Phase.ACCEPTED_HISTORY_LOAD))
        assert not uow.contains(validation)

    nested_sum = sum(
        interval.elapsed_ns
        for phase, interval in probe.intervals.items()
        if phase is not _Phase.WHOLE_WRITE_INVOCATION
    )
    assert nested_sum > whole.elapsed_ns


@pytest.mark.parametrize(
    ("placement", "expected_inside_uow"),
    [
        (ValidationPlacement.PRE_TRANSACTION, False),
        (ValidationPlacement.IN_TRANSACTION, True),
    ],
)
def test_aggregate_context_and_candidate_preparation_preserve_uow_placement(
    monkeypatch,
    placement: ValidationPlacement,
    expected_inside_uow: bool,
):
    _install_source_boundary_probe(monkeypatch)
    probe = _Probe(_ManualClock())
    scenario = _Scenario(
        placement,
        (
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS)
            if placement is ValidationPlacement.PRE_TRANSACTION
            else (IdempotencyVerdict.MISS,)
        ),
        pessimistic=placement is ValidationPlacement.IN_TRANSACTION,
    )
    connection = _FakeConnection(scenario, probe)
    write_side = _build_write_side(connection)
    observed: list[tuple[str, bool]] = []
    original_rehydrate = write_side._rehydrate_aggregate_from_history
    original_context = write_side._build_validation_context
    original_create = OrderAggregate.create

    def observe_rehydration(order_id, history):
        observed.append(("aggregate_rehydration", connection.inside_uow))
        aggregate = original_rehydrate(order_id, history)
        setattr(aggregate, "_measurement_characterization", True)
        return aggregate

    def observe_context(*, aggregate, actual_prev_event):
        observed.append(("validation_context", connection.inside_uow))
        return original_context(
            aggregate=aggregate,
            actual_prev_event=actual_prev_event,
        )

    def observe_candidate(aggregate, request_id, total_amount):
        if getattr(aggregate, "_measurement_characterization", False):
            observed.append(("candidate_construction", connection.inside_uow))
        return original_create(aggregate, request_id, total_amount)

    monkeypatch.setattr(
        write_side,
        "_rehydrate_aggregate_from_history",
        observe_rehydration,
    )
    monkeypatch.setattr(write_side, "_build_validation_context", observe_context)
    monkeypatch.setattr(OrderAggregate, "create", observe_candidate)

    _deliver_after_uow(
        lambda: write_side.create_order(
            request_id="cpu-placement-request",
            order_id="cpu-placement-order",
            amount=Decimal("100.00"),
        ),
        probe,
    )

    assert observed == [
        ("aggregate_rehydration", expected_inside_uow),
        ("validation_context", expected_inside_uow),
        ("candidate_construction", expected_inside_uow),
    ]


@pytest.mark.parametrize(
    ("scenario", "finalization_phase"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
            ),
            _Phase.COMMIT_FINALIZATION,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
            ),
            _Phase.ROLLBACK_FINALIZATION,
        ),
    ],
    ids=["accepted commit", "normal non-accepted rollback"],
)
def test_finalization_returns_before_uow_and_whole_intervals_finish(
    monkeypatch,
    scenario: _Scenario,
    finalization_phase: _Phase,
):
    _, _, probe = _execute_scenario(monkeypatch, scenario)

    assert probe.events.index(
        f"{finalization_phase.value}:stop"
    ) < probe.events.index(f"{_Phase.BUSINESS_UOW_LIFECYCLE.value}:stop")
    assert probe.events.index(
        f"{_Phase.BUSINESS_UOW_LIFECYCLE.value}:stop"
    ) < probe.events.index(f"{_Phase.WHOLE_WRITE_INVOCATION.value}:stop")
    assert probe.events.index(
        f"{_Phase.WHOLE_WRITE_INVOCATION.value}:stop"
    ) < probe.events.index("measurement_construction:start")


def test_trace_construction_remains_precommit_while_measurement_finishes_post_uow(
    monkeypatch,
):
    original_execution_post_init = PostgresWriteSideExecution.__post_init__
    observed_probe: _Probe | None = None

    def observe_execution_construction(execution):
        original_execution_post_init(execution)
        assert observed_probe is not None
        observed_probe.events.append("trace_execution_constructed")

    monkeypatch.setattr(
        PostgresWriteSideExecution,
        "__post_init__",
        observe_execution_construction,
    )
    _install_source_boundary_probe(monkeypatch)
    probe = _Probe(_ManualClock())
    observed_probe = probe
    scenario = _Scenario(
        ValidationPlacement.IN_TRANSACTION,
        (IdempotencyVerdict.MISS,),
        pessimistic=True,
    )
    connection = _FakeConnection(scenario, probe)
    write_side = _build_write_side(connection)

    delivery = _deliver_after_uow(
        lambda: write_side.create_order_with_trace(
            request_id="traced-characterization-request",
            order_id="traced-characterization-order",
            amount=Decimal("100.00"),
        ),
        probe,
    )

    assert isinstance(delivery.producer_value, PostgresWriteSideExecution)
    assert probe.events.index("trace_execution_constructed") < probe.events.index(
        f"{_Phase.COMMIT_FINALIZATION.value}:stop"
    )
    assert probe.events.index(
        f"{_Phase.COMMIT_FINALIZATION.value}:stop"
    ) < probe.events.index(f"{_Phase.BUSINESS_UOW_LIFECYCLE.value}:stop")
    assert probe.events.index(
        f"{_Phase.WHOLE_WRITE_INVOCATION.value}:stop"
    ) < probe.events.index("measurement_construction:start")


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
@pytest.mark.parametrize(
    (
        "scenario",
        "expected_outcome",
        "expected_committed",
        "expected_finalization",
    ),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
            ),
            PostgresWriteSideOutcome.ACCEPTED,
            True,
            _Phase.COMMIT_FINALIZATION,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
            ),
            PostgresWriteSideOutcome.REPLAY,
            False,
            _Phase.ROLLBACK_FINALIZATION,
        ),
    ],
    ids=["accepted", "normal-non-accepted-replay"],
)
def test_post_uow_measurement_failure_preserves_normal_return_producer_value(
    monkeypatch,
    with_trace: bool,
    scenario: _Scenario,
    expected_outcome: PostgresWriteSideOutcome,
    expected_committed: bool,
    expected_finalization: _Phase,
):
    """Measurement-owned failure must not rewrite a completed producer result."""

    def fail_measurement(probe: _Probe) -> _MeasurementSnapshot:
        probe.events.append("measurement_construction:failed")
        raise _MeasurementConstructionFailure("future artifact rejected")

    delivery, connection, probe = _execute_scenario(
        monkeypatch,
        scenario,
        with_trace=with_trace,
        build_measurement=fail_measurement,
    )

    producer_value = delivery.producer_value
    if with_trace:
        assert type(producer_value) is PostgresWriteSideExecution
        result = producer_value.result
        assert not hasattr(producer_value.trace, "measurement")
    else:
        result = producer_value

    assert result.outcome is expected_outcome
    assert delivery.availability is _Availability.UNAVAILABLE
    assert delivery.measurement is None
    assert connection.committed is expected_committed
    assert connection.commit_calls == (1 if expected_committed else 0)
    assert connection.rollback_calls == (0 if expected_committed else 1)
    assert probe.events.index(
        f"{expected_finalization.value}:stop"
    ) < probe.events.index("measurement_construction:failed")


def test_whole_invocation_stop_excludes_post_stop_artifact_construction_work(
    monkeypatch,
):
    construction_elapsed_ns = 101

    def build_after_stop(probe: _Probe) -> _MeasurementSnapshot:
        probe.events.append("measurement_construction:start")
        probe.clock.advance(construction_elapsed_ns)
        snapshot = _MeasurementSnapshot(tuple(probe.intervals.items()))
        probe.events.append("measurement_construction:stop")
        return snapshot

    _, _, probe = _execute_scenario(
        monkeypatch,
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        build_measurement=build_after_stop,
    )
    whole = probe.interval(_Phase.WHOLE_WRITE_INVOCATION)

    assert probe.clock.now_ns - whole.stopped_ns == construction_elapsed_ns
    assert probe.events.index(
        f"{_Phase.WHOLE_WRITE_INVOCATION.value}:stop"
    ) < probe.events.index("measurement_construction:start")


def test_precommit_measurement_construction_failure_would_force_rollback(
    monkeypatch,
):
    _install_source_boundary_probe(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(
        _Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
        ),
        probe,
    )

    with pytest.raises(_MeasurementConstructionFailure):
        with PostgresWriteSideUnitOfWork(cast(Connection, connection)):
            raise _MeasurementConstructionFailure("constructed before commit")

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert _Phase.ROLLBACK_FINALIZATION in probe.intervals


@pytest.mark.parametrize(
    ("scenario", "exception_type", "expected_finalization"),
    [
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
                validation_raises=True,
            ),
            _ProducerFailure,
            _Phase.ROLLBACK_FINALIZATION,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.MISS,),
                pessimistic=True,
                commit_raises=True,
            ),
            _CommitFailure,
            _Phase.COMMIT_FINALIZATION,
        ),
        (
            _Scenario(
                ValidationPlacement.IN_TRANSACTION,
                (IdempotencyVerdict.REPLAY,),
                pessimistic=True,
                rollback_raises=True,
            ),
            _RollbackFailure,
            _Phase.ROLLBACK_FINALIZATION,
        ),
    ],
    ids=["producer exception", "commit exception", "rollback exception"],
)
def test_existing_producer_and_finalization_exceptions_are_not_swallowed(
    monkeypatch,
    scenario: _Scenario,
    exception_type: type[Exception],
    expected_finalization: _Phase,
):
    _install_source_boundary_probe(monkeypatch)
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(scenario, probe)
    write_side = _build_write_side(connection)
    builder_called = False

    def unexpected_builder(_: _Probe) -> _MeasurementSnapshot:
        nonlocal builder_called
        builder_called = True
        raise AssertionError("measurement construction must not run")

    with pytest.raises(exception_type):
        _deliver_after_uow(
            lambda: write_side.create_order(
                request_id="exception-characterization-request",
                order_id="exception-characterization-order",
                amount=Decimal("100.00"),
            ),
            probe,
            build_measurement=unexpected_builder,
        )

    assert builder_called is False
    assert _Phase.WHOLE_WRITE_INVOCATION not in probe.intervals
    assert expected_finalization in probe.reached


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_post_uow_wrapper_preserves_existing_api_value_by_identity(
    monkeypatch,
    with_trace: bool,
):
    delivery, connection, _ = _execute_scenario(
        monkeypatch,
        _Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        with_trace=with_trace,
    )

    assert delivery.availability is _Availability.AVAILABLE
    assert connection.committed is True
    if with_trace:
        execution = delivery.producer_value
        assert type(execution) is PostgresWriteSideExecution
        assert execution.result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert execution.result.accepted_event is not None
        assert not hasattr(execution.trace, "measurement")
    else:
        result = delivery.producer_value
        assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert result.accepted_event is not None


def test_existing_validator_total_is_local_not_full_runtime_elapsed(monkeypatch):
    class _TickingClock(_ManualClock):
        def perf_counter_ns(self) -> int:
            reading = self.now_ns
            self.advance(5)
            return reading

        def perf_counter(self) -> float:
            return self.perf_counter_ns() / 1_000_000_000

    clock = _TickingClock()
    probe = _Probe(clock)
    validator = NoOpValidator()
    runtime = ValidationRuntime(
        dispatcher=ValidationDispatcher(validator, validator),
        policy=ValidationPolicy(),
        mode=ValidationMode.OFF,
    )
    aggregate = OrderAggregate("validator-timing-order")
    candidate_event = aggregate.create(
        request_id="validator-timing-request",
        total_amount=Decimal("100.00"),
    )
    context = ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=aggregate.status,
    )
    monkeypatch.setattr(
        validators_module,
        "time",
        SimpleNamespace(perf_counter=clock.perf_counter),
    )

    decision = probe.call(
        _Phase.VALIDATION_RUNTIME_CALL,
        lambda: runtime.decide(candidate_event, context),
    )

    validator_local_ns = int(
        decision.validation_result.total_time_ms * 1_000_000
    )
    runtime_ns = probe.interval(_Phase.VALIDATION_RUNTIME_CALL).elapsed_ns
    assert validator_local_ns == 5
    assert runtime_ns == 15
    assert runtime_ns > validator_local_ns
