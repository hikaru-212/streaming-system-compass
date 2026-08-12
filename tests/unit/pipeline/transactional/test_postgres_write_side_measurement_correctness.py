"""Stage 4B.2 PR5 correctness evidence for PostgreSQL write measurement.

These tests exercise the actual PR4 measured producer APIs.  Existing PR2
manual-clock probes remain independent endpoint oracles: production recorder
values are compared with source-boundary start/stop observations, never with
arithmetic sums of overlapping child intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import cast

import pytest
from psycopg import Connection

from src.compass.transition.types import EnforcementAction
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType, EventType
from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import AdmissionVerdict
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
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurementState,
)
from src.pipeline.transactional import (
    postgres_write_side_measurement_instrumentation as instrumentation,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_characterization import (
    _DURATION_NS,
    _FakeConnection,
    _ManualClock,
    _Phase,
    _Probe,
    _Scenario,
    _install_source_boundary_probe,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_instrumentation import (
    _build_preview_writer,
)


State = PostgresWriteSidePhaseMeasurementState
Availability = PostgresWriteSideMeasurementAvailability
MeasurementPhase = instrumentation._PostgresWriteSideMeasurementPhase
Recorder = instrumentation._PostgresWriteSideMeasurementRecorder
Checkpoint = PostgresWriteSideExecutionCheckpoint

_PHASE_FIELD_NAMES = (
    "producer_write_invocation",
    "business_uow",
    "validation_runtime_call",
    "preliminary_idempotency_check",
    "preliminary_read_cleanup",
    "authoritative_idempotency_check",
    "accepted_history_load",
    "concurrency_preparation_call",
    "pessimistic_advisory_try_lock_call",
    "append_admission_call",
    "idempotency_record_call",
    "commit_finalization",
    "rollback_finalization",
)

_FIELD_TO_ORACLE_PHASE = {
    "producer_write_invocation": _Phase.WHOLE_WRITE_INVOCATION,
    "business_uow": _Phase.BUSINESS_UOW_LIFECYCLE,
    "validation_runtime_call": _Phase.VALIDATION_RUNTIME_CALL,
    "preliminary_idempotency_check": _Phase.PRELIMINARY_IDEMPOTENCY_CHECK,
    "preliminary_read_cleanup": _Phase.PRELIMINARY_READ_CLEANUP,
    "authoritative_idempotency_check": _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
    "accepted_history_load": _Phase.ACCEPTED_HISTORY_LOAD,
    "concurrency_preparation_call": _Phase.CONCURRENCY_PREPARATION_CALL,
    "pessimistic_advisory_try_lock_call": (
        _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL
    ),
    "append_admission_call": _Phase.APPEND_ADMISSION_CALL,
    "idempotency_record_call": _Phase.IDEMPOTENCY_RECORD_CALL,
    "commit_finalization": _Phase.COMMIT_FINALIZATION,
    "rollback_finalization": _Phase.ROLLBACK_FINALIZATION,
}


@dataclass(frozen=True)
class _CorrectnessCase:
    """Describe one canonical normal-return source path."""

    code: str
    scenario: _Scenario
    expected_outcome: PostgresWriteSideOutcome
    measured_fields: frozenset[str]
    not_applicable_fields: frozenset[str]
    commit_calls: int
    rollback_calls: int
    traced: bool
    trace_terminal: Checkpoint


_PRE_NOT_APPLICABLE = frozenset({"pessimistic_advisory_try_lock_call"})
_IN_NOT_APPLICABLE = frozenset(
    {"preliminary_idempotency_check", "preliminary_read_cleanup"}
)

_CASES = (
    _CorrectnessCase(
        code="P1",
        scenario=_Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
        ),
        expected_outcome=PostgresWriteSideOutcome.ACCEPTED,
        measured_fields=frozenset(
            {
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
            }
        ),
        not_applicable_fields=_PRE_NOT_APPLICABLE,
        commit_calls=1,
        rollback_calls=1,
        traced=False,
        trace_terminal=Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
    ),
    _CorrectnessCase(
        code="P2",
        scenario=_Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
        ),
        expected_outcome=PostgresWriteSideOutcome.REPLAY,
        measured_fields=frozenset(
            {
                "producer_write_invocation",
                "preliminary_idempotency_check",
                "preliminary_read_cleanup",
            }
        ),
        not_applicable_fields=_PRE_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=1,
        traced=False,
        trace_terminal=Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    ),
    _CorrectnessCase(
        code="P3",
        scenario=_Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            validation_action=EnforcementAction.BLOCK,
        ),
        expected_outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        measured_fields=frozenset(
            {
                "producer_write_invocation",
                "validation_runtime_call",
                "preliminary_idempotency_check",
                "preliminary_read_cleanup",
                "accepted_history_load",
            }
        ),
        not_applicable_fields=_PRE_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=1,
        traced=False,
        trace_terminal=Checkpoint.VALIDATION_RETURNED,
    ),
    _CorrectnessCase(
        code="P4",
        scenario=_Scenario(
            ValidationPlacement.PRE_TRANSACTION,
            (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS),
            append_admitted=False,
        ),
        expected_outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        measured_fields=frozenset(
            {
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
            }
        ),
        not_applicable_fields=_PRE_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=2,
        traced=False,
        trace_terminal=Checkpoint.APPEND_ADMISSION_RETURNED,
    ),
    _CorrectnessCase(
        code="I1",
        scenario=_Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            pessimistic=True,
        ),
        expected_outcome=PostgresWriteSideOutcome.ACCEPTED,
        measured_fields=frozenset(
            {
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
            }
        ),
        not_applicable_fields=_IN_NOT_APPLICABLE,
        commit_calls=1,
        rollback_calls=0,
        traced=True,
        trace_terminal=Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
    ),
    _CorrectnessCase(
        code="I2",
        scenario=_Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.REPLAY,),
            pessimistic=True,
        ),
        expected_outcome=PostgresWriteSideOutcome.REPLAY,
        measured_fields=frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "authoritative_idempotency_check",
                "rollback_finalization",
            }
        ),
        not_applicable_fields=_IN_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=1,
        traced=True,
        trace_terminal=Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    ),
    _CorrectnessCase(
        code="I3",
        scenario=_Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            preparation_admitted=False,
            pessimistic=True,
        ),
        expected_outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        measured_fields=frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "authoritative_idempotency_check",
                "concurrency_preparation_call",
                "pessimistic_advisory_try_lock_call",
                "rollback_finalization",
            }
        ),
        not_applicable_fields=_IN_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=1,
        traced=True,
        trace_terminal=Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    ),
    _CorrectnessCase(
        code="I4",
        scenario=_Scenario(
            ValidationPlacement.IN_TRANSACTION,
            (IdempotencyVerdict.MISS,),
            validation_action=EnforcementAction.BLOCK,
            pessimistic=True,
        ),
        expected_outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        measured_fields=frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "validation_runtime_call",
                "authoritative_idempotency_check",
                "accepted_history_load",
                "concurrency_preparation_call",
                "pessimistic_advisory_try_lock_call",
                "rollback_finalization",
            }
        ),
        not_applicable_fields=_IN_NOT_APPLICABLE,
        commit_calls=0,
        rollback_calls=1,
        traced=True,
        trace_terminal=Checkpoint.VALIDATION_RETURNED,
    ),
)

_CASES_BY_CODE = {case.code: case for case in _CASES}


@dataclass
class _ExecutionRun:
    """Retain one measured or unmeasured fake-source execution."""

    producer_value: PostgresWriteSideResult | PostgresWriteSideExecution
    result: PostgresWriteSideResult
    measurement: PostgresWriteSideMeasurement | None
    connection: _FakeConnection
    probe: _Probe


def _connection_from_gate(gate) -> _FakeConnection:
    """Recover the test-owned connection from a current PostgreSQL gate."""
    return cast(_FakeConnection, gate.event_store.connection)


def _install_independent_boundary_oracle(monkeypatch) -> None:
    """Observe the same source calls independently from the PR4 recorder."""
    _install_source_boundary_probe(monkeypatch)

    original_optimistic_prepare = PostgresOptimisticAdmissionGate.prepare_stream
    original_optimistic_append = PostgresOptimisticAdmissionGate.append_if_admitted
    original_pessimistic_prepare = PostgresPessimisticAdmissionGate.prepare_stream
    original_pessimistic_append = PostgresPessimisticAdmissionGate.append_if_admitted

    def optimistic_prepare(gate, order_id):
        connection = _connection_from_gate(gate)
        return connection.probe.call(
            _Phase.CONCURRENCY_PREPARATION_CALL,
            lambda: original_optimistic_prepare(gate, order_id),
        )

    def optimistic_append(gate, candidate_event, expected_current_version):
        connection = _connection_from_gate(gate)
        return connection.probe.call(
            _Phase.APPEND_ADMISSION_CALL,
            lambda: original_optimistic_append(
                gate,
                candidate_event,
                expected_current_version,
            ),
        )

    def pessimistic_prepare(gate, order_id):
        connection = _connection_from_gate(gate)
        return connection.probe.call(
            _Phase.CONCURRENCY_PREPARATION_CALL,
            lambda: original_pessimistic_prepare(gate, order_id),
        )

    def pessimistic_try_lock(gate, order_id):
        connection = cast(_FakeConnection, gate.connection)

        def try_lock() -> bool:
            connection.probe.clock.advance(
                _DURATION_NS[_Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL]
            )
            return connection.scenario.preparation_admitted

        return connection.probe.call(
            _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL,
            try_lock,
        )

    def pessimistic_append(gate, candidate_event, expected_current_version):
        connection = _connection_from_gate(gate)
        return connection.probe.call(
            _Phase.APPEND_ADMISSION_CALL,
            lambda: original_pessimistic_append(
                gate,
                candidate_event,
                expected_current_version,
            ),
        )

    monkeypatch.setattr(
        PostgresOptimisticAdmissionGate,
        "prepare_stream",
        optimistic_prepare,
    )
    monkeypatch.setattr(
        PostgresOptimisticAdmissionGate,
        "append_if_admitted",
        optimistic_append,
    )
    monkeypatch.setattr(
        PostgresPessimisticAdmissionGate,
        "prepare_stream",
        pessimistic_prepare,
    )
    monkeypatch.setattr(
        PostgresPessimisticAdmissionGate,
        "_try_lock_stream",
        pessimistic_try_lock,
    )
    monkeypatch.setattr(
        PostgresPessimisticAdmissionGate,
        "append_if_admitted",
        pessimistic_append,
    )


def _result_from(
    producer_value: PostgresWriteSideResult | PostgresWriteSideExecution,
) -> PostgresWriteSideResult:
    if isinstance(producer_value, PostgresWriteSideExecution):
        return producer_value.result
    return producer_value


def _execute_create_case(
    monkeypatch,
    case: _CorrectnessCase,
    *,
    measured: bool,
) -> _ExecutionRun:
    """Run one canonical CREATE through the allocated public capability."""
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(case.scenario, probe)
    writer = _build_preview_writer(connection)

    if measured:
        monkeypatch.setattr(
            instrumentation.time,
            "perf_counter_ns",
            probe.clock.perf_counter_ns,
        )
        original_execute = writer._execute_command

        def observe_whole_invocation(**kwargs):
            return probe.call(
                _Phase.WHOLE_WRITE_INVOCATION,
                lambda: original_execute(**kwargs),
            )

        monkeypatch.setattr(writer, "_execute_command", observe_whole_invocation)
        method = (
            writer.create_order_with_trace_and_measurement
            if case.traced
            else writer.create_order_with_measurement
        )
        delivery = method(
            request_id=f"pr5-{case.code.lower()}-request",
            order_id=f"pr5-{case.code.lower()}-order",
            amount=Decimal("100.00"),
        )
        assert delivery.availability is Availability.AVAILABLE
        assert delivery.measurement is not None
        producer_value = delivery.producer_value
        measurement = delivery.measurement
    else:
        method = (
            writer.create_order_with_trace
            if case.traced
            else writer.create_order
        )
        producer_value = method(
            request_id=f"pr5-{case.code.lower()}-request",
            order_id=f"pr5-{case.code.lower()}-order",
            amount=Decimal("100.00"),
        )
        measurement = None

    return _ExecutionRun(
        producer_value=producer_value,
        result=_result_from(producer_value),
        measurement=measurement,
        connection=connection,
        probe=probe,
    )


def _expected_state(case: _CorrectnessCase, field_name: str) -> State:
    if field_name in case.measured_fields:
        return State.MEASURED
    if field_name in case.not_applicable_fields:
        return State.NOT_APPLICABLE
    return State.NOT_REACHED


def _expected_detail_elapsed_ns(
    case: _CorrectnessCase,
    field_name: str,
) -> int | None:
    """Return only independently characterized detail-operation deltas."""
    direct_phase_fields = {
        "preliminary_idempotency_check": _Phase.PRELIMINARY_IDEMPOTENCY_CHECK,
        "preliminary_read_cleanup": _Phase.PRELIMINARY_READ_CLEANUP,
        "authoritative_idempotency_check": (
            _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK
        ),
        "accepted_history_load": _Phase.ACCEPTED_HISTORY_LOAD,
        "pessimistic_advisory_try_lock_call": (
            _Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL
        ),
        "append_admission_call": _Phase.APPEND_ADMISSION_CALL,
        "idempotency_record_call": _Phase.IDEMPOTENCY_RECORD_CALL,
        "commit_finalization": _Phase.COMMIT_FINALIZATION,
        "rollback_finalization": _Phase.ROLLBACK_FINALIZATION,
    }
    if field_name in direct_phase_fields:
        return _DURATION_NS[direct_phase_fields[field_name]]
    if field_name == "validation_runtime_call":
        return 3 + _DURATION_NS[_Phase.VALIDATOR_LOCAL] + 5
    if field_name == "concurrency_preparation_call":
        if case.scenario.placement is ValidationPlacement.PRE_TRANSACTION:
            return 0
        return _DURATION_NS[_Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL]
    return None


def _assert_exact_phase_matrix_and_elapsed(
    case: _CorrectnessCase,
    run: _ExecutionRun,
) -> None:
    measurement = run.measurement
    assert measurement is not None
    assert tuple(field.name for field in fields(measurement)) == _PHASE_FIELD_NAMES

    for field_name in _PHASE_FIELD_NAMES:
        actual = getattr(measurement, field_name)
        expected_state = _expected_state(case, field_name)
        assert actual.state is expected_state, f"{case.code} {field_name}"

        if expected_state is not State.MEASURED:
            assert actual.elapsed_ns is None
            continue

        assert type(actual.elapsed_ns) is int
        oracle_phase = _FIELD_TO_ORACLE_PHASE[field_name]
        independent_interval = run.probe.interval(oracle_phase)
        assert actual.elapsed_ns == independent_interval.elapsed_ns

        expected_detail = _expected_detail_elapsed_ns(case, field_name)
        if expected_detail is not None:
            assert actual.elapsed_ns == expected_detail


def _normalize_event(event: OrderEvent | None):
    if event is None:
        return None
    return (
        event.request_id,
        event.order_id,
        event.event_type,
        event.amount,
        event.sequence,
        event.proof.prev_status,
        event.proof.prev_version,
        event.proof.prev_event_id is not None,
    )


def _normalize_idempotency(decision: IdempotencyDecision):
    record = decision.record
    normalized_record = None
    if record is not None:
        signature = record.signature
        normalized_record = (
            signature.request_id,
            signature.command_type,
            signature.order_id,
            signature.amount,
            _normalize_event(record.accepted_event),
        )
    return decision.verdict, decision.reason, normalized_record


def _normalize_stream_admission(result):
    if result is None:
        return None
    return result.verdict, result.admitted, result.reason, result.order_id


def _normalize_validation(decision):
    if decision is None:
        return None
    result = decision.validation_result
    return (
        decision.action,
        result.verdict,
        result.reason,
        result.validator_name,
        result.validation_mode,
        result.logic_validation_time_ms,
        result.io_time_ms,
        result.total_time_ms,
        result.metadata,
    )


def _normalize_append_admission(result):
    if result is None:
        return None
    return (
        result.verdict,
        result.admitted,
        result.reason,
        result.candidate_event_id is not None,
        result.accepted_event_id is not None,
        result.accepted_event_id == result.candidate_event_id,
    )


def _normalize_result(result: PostgresWriteSideResult):
    return (
        result.outcome,
        _normalize_event(result.accepted_event),
        _normalize_idempotency(result.idempotency_decision),
        _normalize_stream_admission(result.stream_admission_result),
        _normalize_validation(result.validation_decision),
        _normalize_append_admission(result.admission_result),
    )


def _assert_business_parity(
    measured: _ExecutionRun,
    unmeasured: _ExecutionRun,
) -> None:
    assert _normalize_result(measured.result) == _normalize_result(unmeasured.result)
    assert measured.connection.commit_calls == unmeasured.connection.commit_calls
    assert measured.connection.rollback_calls == unmeasured.connection.rollback_calls
    assert measured.connection.committed is unmeasured.connection.committed

    if isinstance(measured.producer_value, PostgresWriteSideExecution):
        assert isinstance(unmeasured.producer_value, PostgresWriteSideExecution)
        measured_trace = measured.producer_value.trace
        unmeasured_trace = unmeasured.producer_value.trace
        assert measured_trace.validation_placement is (
            unmeasured_trace.validation_placement
        )
        assert measured_trace.checkpoints == unmeasured_trace.checkpoints
        assert measured_trace.terminal_checkpoint is (
            unmeasured_trace.terminal_checkpoint
        )
        assert tuple(field.name for field in fields(measured_trace)) == (
            "validation_placement",
            "checkpoints",
        )
    else:
        assert isinstance(unmeasured.producer_value, PostgresWriteSideResult)


def _assert_strict_event_order(probe: _Probe, *events: str) -> None:
    positions = [probe.events.index(event) for event in events]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.code)
def test_canonical_matrix_has_exact_states_elapsed_and_business_parity(
    monkeypatch,
    case: _CorrectnessCase,
) -> None:
    _install_independent_boundary_oracle(monkeypatch)

    measured = _execute_create_case(monkeypatch, case, measured=True)
    unmeasured = _execute_create_case(monkeypatch, case, measured=False)

    assert measured.result.outcome is case.expected_outcome
    assert measured.connection.commit_calls == case.commit_calls
    assert measured.connection.rollback_calls == case.rollback_calls
    _assert_exact_phase_matrix_and_elapsed(case, measured)
    _assert_business_parity(measured, unmeasured)

    if case.traced:
        execution = cast(PostgresWriteSideExecution, measured.producer_value)
        assert execution.trace.terminal_checkpoint is case.trace_terminal

    if case.code == "P4":
        assert measured.result.stream_admission_result is not None
        assert (
            measured.result.stream_admission_result.verdict
            is AdmissionVerdict.ADMITTED
        )
        assert measured.result.admission_result is not None
        assert measured.result.admission_result.verdict is AdmissionVerdict.STALE_WRITE

    if case.code == "I3":
        assert measured.result.stream_admission_result is not None
        assert (
            measured.result.stream_admission_result.verdict
            is AdmissionVerdict.LOCK_TIMEOUT
        )
        assert measured.result.validation_decision is None
        assert measured.result.admission_result is None


@pytest.mark.parametrize("case_code", ["P1", "I1", "P4"])
def test_parent_and_nested_boundaries_preserve_independent_containment(
    monkeypatch,
    case_code: str,
) -> None:
    _install_independent_boundary_oracle(monkeypatch)
    case = _CASES_BY_CODE[case_code]
    run = _execute_create_case(monkeypatch, case, measured=True)
    probe = run.probe

    whole = probe.interval(_Phase.WHOLE_WRITE_INVOCATION)
    uow = probe.interval(_Phase.BUSINESS_UOW_LIFECYCLE)
    assert whole.contains(uow)

    for phase in (
        _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK,
        _Phase.CONCURRENCY_PREPARATION_CALL,
        _Phase.APPEND_ADMISSION_CALL,
        (
            _Phase.COMMIT_FINALIZATION
            if case_code in {"P1", "I1"}
            else _Phase.ROLLBACK_FINALIZATION
        ),
    ):
        assert uow.contains(probe.interval(phase))

    if case_code == "I1":
        preparation = probe.interval(_Phase.CONCURRENCY_PREPARATION_CALL)
        try_lock = probe.interval(_Phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL)
        assert preparation.contains(try_lock)
        _assert_strict_event_order(
            probe,
            "whole_write_invocation:start",
            "business_uow_lifecycle:start",
            "concurrency_preparation_call:start",
            "pessimistic_advisory_try_lock_call:start",
            "pessimistic_advisory_try_lock_call:stop",
            "concurrency_preparation_call:stop",
            "business_uow_lifecycle:stop",
            "whole_write_invocation:stop",
        )
    else:
        child = (
            _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK
            if case_code == "P1"
            else _Phase.APPEND_ADMISSION_CALL
        )
        _assert_strict_event_order(
            probe,
            "whole_write_invocation:start",
            "business_uow_lifecycle:start",
            f"{child.value}:start",
            f"{child.value}:stop",
            "business_uow_lifecycle:stop",
            "whole_write_invocation:stop",
        )


def test_reached_detail_clock_failure_is_available_and_not_collected(
    monkeypatch,
) -> None:
    _install_independent_boundary_oracle(monkeypatch)
    case = _CASES_BY_CODE["I4"]
    original_finish = Recorder.finish
    injected = False

    def fail_validation_stop(self, phase, started_ns):
        nonlocal injected
        if phase is MeasurementPhase.VALIDATION_RUNTIME_CALL and not injected:
            injected = True
            original_clock = self._clock

            def failing_clock() -> int:
                raise RuntimeError("PR5 validation stop clock failed")

            self._clock = failing_clock
            try:
                return original_finish(self, phase, started_ns)
            finally:
                self._clock = original_clock
        return original_finish(self, phase, started_ns)

    monkeypatch.setattr(Recorder, "finish", fail_validation_stop)
    run = _execute_create_case(monkeypatch, case, measured=True)
    unmeasured = _execute_create_case(monkeypatch, case, measured=False)
    measurement = run.measurement
    assert measurement is not None

    assert injected is True
    assert run.result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert run.connection.commit_calls == 0
    assert run.connection.rollback_calls == 1
    _assert_business_parity(run, unmeasured)

    for field_name in _PHASE_FIELD_NAMES:
        actual = getattr(measurement, field_name)
        if field_name == "validation_runtime_call":
            assert actual.state is State.NOT_COLLECTED
            assert actual.elapsed_ns is None
        else:
            assert actual.state is _expected_state(case, field_name)


def _make_seed_and_paid_replay(
    *,
    order_id: str,
    request_id: str,
) -> tuple[OrderEvent, IdempotencyDecision]:
    aggregate = OrderAggregate(order_id)
    seed = aggregate.create(
        request_id=f"{request_id}-seed",
        total_amount=Decimal("100.00"),
    )
    aggregate.apply(seed)
    paid = aggregate.pay(request_id, Decimal("100.00"))
    signature = RequestSignature(
        request_id=request_id,
        command_type=CommandType.PAY,
        order_id=order_id,
        amount=Decimal("100.00"),
    )
    return seed, IdempotencyDecision(
        verdict=IdempotencyVerdict.REPLAY,
        reason="test-owned paid replay",
        record=IdempotencyRecord(signature=signature, accepted_event=paid),
    )


def _install_paid_replay_override(monkeypatch) -> None:
    """Return a PAID replay event while retaining the independent check timer."""
    original_check = PostgresIdempotencyStore.check

    def check(store, signature):
        connection = cast(_FakeConnection, store._connection)
        decision = getattr(connection, "pr5_paid_replay", None)
        if decision is None:
            return original_check(store, signature)

        phase = (
            _Phase.AUTHORITATIVE_IDEMPOTENCY_CHECK
            if connection.inside_uow
            else _Phase.PRELIMINARY_IDEMPOTENCY_CHECK
        )

        def return_replay():
            connection.probe.clock.advance(_DURATION_NS[phase])
            connection.idempotency_check_index += 1
            return decision

        return connection.probe.call(phase, return_replay)

    monkeypatch.setattr(PostgresIdempotencyStore, "check", check)


def _execute_pay_parity_side(
    monkeypatch,
    *,
    measured: bool,
    traced: bool,
    replay: bool,
) -> _ExecutionRun:
    scenario = _Scenario(
        ValidationPlacement.PRE_TRANSACTION,
        (
            (IdempotencyVerdict.REPLAY,)
            if replay
            else (IdempotencyVerdict.MISS, IdempotencyVerdict.MISS)
        ),
    )
    probe = _Probe(_ManualClock())
    connection = _FakeConnection(scenario, probe)
    order_id = "pr5-pay-order"
    request_id = "pr5-pay-request"
    seed, replay_decision = _make_seed_and_paid_replay(
        order_id=order_id,
        request_id=request_id,
    )
    connection.history = [seed]
    if replay:
        setattr(connection, "pr5_paid_replay", replay_decision)

    writer = _build_preview_writer(connection)
    if measured:
        monkeypatch.setattr(
            instrumentation.time,
            "perf_counter_ns",
            probe.clock.perf_counter_ns,
        )
        method = (
            writer.pay_order_with_trace_and_measurement
            if traced
            else writer.pay_order_with_measurement
        )
        delivery = method(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
        assert delivery.availability is Availability.AVAILABLE
        assert delivery.measurement is not None
        producer_value = delivery.producer_value
        measurement = delivery.measurement
    else:
        method = writer.pay_order_with_trace if traced else writer.pay_order
        producer_value = method(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
        measurement = None

    return _ExecutionRun(
        producer_value=producer_value,
        result=_result_from(producer_value),
        measurement=measurement,
        connection=connection,
        probe=probe,
    )


@pytest.mark.parametrize("traced", [False, True], ids=["legacy", "traced"])
@pytest.mark.parametrize("replay", [False, True], ids=["accepted", "replay"])
def test_pay_measured_and_unmeasured_business_semantics_match(
    monkeypatch,
    traced: bool,
    replay: bool,
) -> None:
    _install_independent_boundary_oracle(monkeypatch)
    if replay:
        _install_paid_replay_override(monkeypatch)

    measured = _execute_pay_parity_side(
        monkeypatch,
        measured=True,
        traced=traced,
        replay=replay,
    )
    unmeasured = _execute_pay_parity_side(
        monkeypatch,
        measured=False,
        traced=traced,
        replay=replay,
    )

    expected_outcome = (
        PostgresWriteSideOutcome.REPLAY
        if replay
        else PostgresWriteSideOutcome.ACCEPTED
    )
    assert measured.result.outcome is expected_outcome
    assert measured.result.accepted_event is not None
    assert measured.result.accepted_event.event_type is EventType.PAID
    _assert_business_parity(measured, unmeasured)

    if traced:
        execution = cast(PostgresWriteSideExecution, measured.producer_value)
        expected_terminal = (
            Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
            if replay
            else Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED
        )
        assert execution.trace.terminal_checkpoint is expected_terminal
