"""Real-PostgreSQL correctness evidence for Stage 4B.2 PR5 measurement."""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

import pytest
from psycopg.pq import TransactionStatus

from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import CommandType, EventType
from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_admission import (
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
    PostgresWriteSideExecutionCheckpoint,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import (
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.shared.postgres import count_rows


State = PostgresWriteSidePhaseMeasurementState
Availability = PostgresWriteSideMeasurementAvailability
Checkpoint = PostgresWriteSideExecutionCheckpoint

pytestmark = pytest.mark.usefixtures("clean_database")

_PRE_ACCEPTED_MEASURED = frozenset(
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
)
_IN_ACCEPTED_MEASURED = frozenset(
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
)
_IN_VALIDATION_BLOCK_MEASURED = frozenset(
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
)
_IN_LOCK_REJECTED_MEASURED = frozenset(
    {
        "producer_write_invocation",
        "business_uow",
        "authoritative_idempotency_check",
        "concurrency_preparation_call",
        "pessimistic_advisory_try_lock_call",
        "rollback_finalization",
    }
)
_PRE_NOT_APPLICABLE = frozenset({"pessimistic_advisory_try_lock_call"})
_IN_NOT_APPLICABLE = frozenset(
    {"preliminary_idempotency_check", "preliminary_read_cleanup"}
)


class _ValidationRuntime:
    """Return one deterministic validation decision and retain observed context."""

    def __init__(self, action: EnforcementAction) -> None:
        self.action = action
        self.contexts = []

    def decide(self, candidate_event, context) -> ValidationDecision:
        self.contexts.append(context)
        verdict = (
            ValidationVerdict.PASSED
            if self.action is EnforcementAction.ALLOW
            else ValidationVerdict.FAILED
        )
        return ValidationDecision(
            action=self.action,
            validation_result=ValidationResult(
                verdict=verdict,
                reason="PR5 deterministic PostgreSQL validation",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                    "actual_prev_status": context.actual_prev_status.value,
                },
            ),
        )


class _UnexpectedValidationRuntime:
    """Fail if an advisory-lock rejection incorrectly reaches validation."""

    def decide(self, candidate_event, context):
        raise AssertionError("validation must not follow try-lock non-acquisition")


def _pessimistic_gate_factory(uow):
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def _build_write_side(
    connection,
    *,
    placement: ValidationPlacement,
    validation_runtime,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=(
            _pessimistic_gate_factory
            if placement is ValidationPlacement.IN_TRANSACTION
            else None
        ),
        config=PostgresWriteSideConfig(validation_placement=placement),
    )


def _result_from(value) -> PostgresWriteSideResult:
    if isinstance(value, PostgresWriteSideExecution):
        return value.result
    assert isinstance(value, PostgresWriteSideResult)
    return value


def _assert_measurement_shape(
    measurement: PostgresWriteSideMeasurement,
    *,
    measured: frozenset[str],
    not_applicable: frozenset[str],
) -> None:
    for field in fields(measurement):
        phase = getattr(measurement, field.name)
        if field.name in measured:
            assert phase.state is State.MEASURED
            assert type(phase.elapsed_ns) is int
            assert phase.elapsed_ns >= 0
        elif field.name in not_applicable:
            assert phase.state is State.NOT_APPLICABLE
            assert phase.elapsed_ns is None
        else:
            assert phase.state is State.NOT_REACHED
            assert phase.elapsed_ns is None


def _assert_idle_and_reusable(connection) -> None:
    assert connection.info.transaction_status is TransactionStatus.IDLE
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    connection.rollback()
    assert connection.info.transaction_status is TransactionStatus.IDLE


@dataclass(frozen=True)
class _AcceptedApiPair:
    name: str
    unmeasured_method: str
    measured_method: str
    placement: ValidationPlacement
    traced: bool
    command_type: CommandType


_ACCEPTED_API_PAIRS = (
    _AcceptedApiPair(
        name="pre-create-legacy",
        unmeasured_method="create_order",
        measured_method="create_order_with_measurement",
        placement=ValidationPlacement.PRE_TRANSACTION,
        traced=False,
        command_type=CommandType.CREATE,
    ),
    _AcceptedApiPair(
        name="in-create-traced",
        unmeasured_method="create_order_with_trace",
        measured_method="create_order_with_trace_and_measurement",
        placement=ValidationPlacement.IN_TRANSACTION,
        traced=True,
        command_type=CommandType.CREATE,
    ),
    _AcceptedApiPair(
        name="pre-pay-legacy",
        unmeasured_method="pay_order",
        measured_method="pay_order_with_measurement",
        placement=ValidationPlacement.PRE_TRANSACTION,
        traced=False,
        command_type=CommandType.PAY,
    ),
    _AcceptedApiPair(
        name="in-pay-traced",
        unmeasured_method="pay_order_with_trace",
        measured_method="pay_order_with_trace_and_measurement",
        placement=ValidationPlacement.IN_TRANSACTION,
        traced=True,
        command_type=CommandType.PAY,
    ),
)


@dataclass(frozen=True)
class _AcceptedRun:
    result: PostgresWriteSideResult
    trace: object | None
    request_id: str
    order_id: str


def _seed_order(connection, *, order_id: str, request_id: str) -> None:
    writer = _build_write_side(
        connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(EnforcementAction.ALLOW),
    )
    result = writer.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=Decimal("100.00"),
    )
    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    _assert_idle_and_reusable(connection)


def _invoke_accepted(
    writer: PostgresTransactionalWriteSide,
    *,
    method_name: str,
    request_id: str,
    order_id: str,
    measured: bool,
) -> tuple[_AcceptedRun, PostgresWriteSideMeasurement | None]:
    value = getattr(writer, method_name)(
        request_id=request_id,
        order_id=order_id,
        amount=Decimal("100.00"),
    )
    if measured:
        assert value.availability is Availability.AVAILABLE
        assert value.measurement is not None
        measurement = value.measurement
        producer_value = value.producer_value
    else:
        measurement = None
        producer_value = value

    if isinstance(producer_value, PostgresWriteSideExecution):
        trace = producer_value.trace
    else:
        trace = None
    return (
        _AcceptedRun(
            result=_result_from(producer_value),
            trace=trace,
            request_id=request_id,
            order_id=order_id,
        ),
        measurement,
    )


def _normalize_accepted_business(run: _AcceptedRun):
    result = run.result
    event = result.accepted_event
    assert event is not None
    assert event.request_id == run.request_id
    assert event.order_id == run.order_id
    validation = result.validation_decision
    assert validation is not None
    admission = result.admission_result
    assert admission is not None
    stream = result.stream_admission_result
    assert stream is not None

    normalized_trace = None
    if run.trace is not None:
        normalized_trace = (
            run.trace.validation_placement,
            run.trace.checkpoints,
            run.trace.terminal_checkpoint,
            tuple(field.name for field in fields(run.trace)),
        )

    return (
        result.outcome,
        event.event_type,
        event.amount,
        event.sequence,
        event.proof.prev_status,
        event.proof.prev_version,
        event.proof.prev_event_id is not None,
        result.idempotency_decision.verdict,
        result.idempotency_decision.record is not None,
        stream.verdict,
        validation.action,
        validation.validation_result.verdict,
        validation.validation_result.validation_mode,
        validation.validation_result.metadata,
        admission.verdict,
        admission.accepted_event_id == event.event_id,
        normalized_trace,
    )


def _assert_run_persisted(connection, run: _AcceptedRun, command_type: CommandType):
    event = run.result.accepted_event
    assert event is not None
    loaded = PostgresEventStore(connection).load(run.order_id)
    assert loaded[-1] == event

    replay = PostgresIdempotencyStore(connection).check(
        RequestSignature(
            request_id=run.request_id,
            command_type=command_type,
            order_id=run.order_id,
            amount=Decimal("100.00"),
        )
    )
    assert replay.verdict is IdempotencyVerdict.REPLAY
    assert replay.record is not None
    assert replay.record.accepted_event == event


@pytest.mark.parametrize(
    "api_pair",
    _ACCEPTED_API_PAIRS,
    ids=lambda api_pair: api_pair.name,
)
def test_accepted_measured_and_unmeasured_persistence_match(
    db_connection,
    api_pair: _AcceptedApiPair,
) -> None:
    unmeasured_order_id = f"pr5-{api_pair.name}-unmeasured-order"
    measured_order_id = f"pr5-{api_pair.name}-measured-order"
    unmeasured_request_id = f"pr5-{api_pair.name}-unmeasured-request"
    measured_request_id = f"pr5-{api_pair.name}-measured-request"

    if api_pair.command_type is CommandType.PAY:
        _seed_order(
            db_connection,
            order_id=unmeasured_order_id,
            request_id=f"{unmeasured_request_id}-seed",
        )
        _seed_order(
            db_connection,
            order_id=measured_order_id,
            request_id=f"{measured_request_id}-seed",
        )

    unmeasured_writer = _build_write_side(
        db_connection,
        placement=api_pair.placement,
        validation_runtime=_ValidationRuntime(EnforcementAction.ALLOW),
    )
    unmeasured, _ = _invoke_accepted(
        unmeasured_writer,
        method_name=api_pair.unmeasured_method,
        request_id=unmeasured_request_id,
        order_id=unmeasured_order_id,
        measured=False,
    )
    _assert_idle_and_reusable(db_connection)

    measured_writer = _build_write_side(
        db_connection,
        placement=api_pair.placement,
        validation_runtime=_ValidationRuntime(EnforcementAction.ALLOW),
    )
    measured, measurement = _invoke_accepted(
        measured_writer,
        method_name=api_pair.measured_method,
        request_id=measured_request_id,
        order_id=measured_order_id,
        measured=True,
    )
    _assert_idle_and_reusable(db_connection)

    assert measurement is not None
    _assert_measurement_shape(
        measurement,
        measured=(
            _PRE_ACCEPTED_MEASURED
            if api_pair.placement is ValidationPlacement.PRE_TRANSACTION
            else _IN_ACCEPTED_MEASURED
        ),
        not_applicable=(
            _PRE_NOT_APPLICABLE
            if api_pair.placement is ValidationPlacement.PRE_TRANSACTION
            else _IN_NOT_APPLICABLE
        ),
    )
    assert _normalize_accepted_business(measured) == (
        _normalize_accepted_business(unmeasured)
    )

    if api_pair.traced:
        assert measured.trace is not None
        assert measured.trace.terminal_checkpoint is (
            Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED
        )
    else:
        assert measured.trace is None

    _assert_run_persisted(db_connection, unmeasured, api_pair.command_type)
    _assert_run_persisted(db_connection, measured, api_pair.command_type)
    expected_rows = 4 if api_pair.command_type is CommandType.PAY else 2
    assert count_rows(db_connection, "order_events") == expected_rows
    assert count_rows(db_connection, "idempotency_records") == expected_rows
    db_connection.rollback()
    assert db_connection.info.transaction_status is TransactionStatus.IDLE


def test_in_pessimistic_measured_validation_block_rolls_back_cleanly(
    db_connection,
) -> None:
    validation_runtime = _ValidationRuntime(EnforcementAction.BLOCK)
    writer = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=validation_runtime,
    )

    delivery = writer.create_order_with_measurement(
        request_id="pr5-in-validation-block-request",
        order_id="pr5-in-validation-block-order",
        amount=Decimal("100.00"),
    )

    assert delivery.availability is Availability.AVAILABLE
    assert delivery.measurement is not None
    result = _result_from(delivery.producer_value)
    assert result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.BLOCK
    assert result.admission_result is None
    assert len(validation_runtime.contexts) == 1
    assert validation_runtime.contexts[0].actual_prev_version == 0

    _assert_measurement_shape(
        delivery.measurement,
        measured=_IN_VALIDATION_BLOCK_MEASURED,
        not_applicable=_IN_NOT_APPLICABLE,
    )
    assert delivery.measurement.rollback_finalization.state is State.MEASURED
    assert delivery.measurement.commit_finalization.state is State.NOT_REACHED
    _assert_idle_and_reusable(db_connection)
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
    db_connection.rollback()
    assert db_connection.info.transaction_status is TransactionStatus.IDLE


def test_in_pessimistic_measured_try_lock_non_acquisition_rolls_back_cleanly(
    db_connection,
    db_connection_factory,
) -> None:
    order_id = "pr5-in-pessimistic-locked-order"
    locker_connection = db_connection_factory()
    locker_gate = PostgresPessimisticAdmissionGate(
        connection=locker_connection,
        event_store=PostgresEventStore(locker_connection),
    )

    try:
        locker_result = locker_gate.prepare_stream(order_id)
        assert locker_result.verdict is AdmissionVerdict.ADMITTED

        writer = _build_write_side(
            db_connection,
            placement=ValidationPlacement.IN_TRANSACTION,
            validation_runtime=_UnexpectedValidationRuntime(),
        )
        delivery = writer.create_order_with_trace_and_measurement(
            request_id="pr5-in-pessimistic-locked-request",
            order_id=order_id,
            amount=Decimal("100.00"),
        )

        assert delivery.availability is Availability.AVAILABLE
        assert delivery.measurement is not None
        execution = delivery.producer_value
        assert isinstance(execution, PostgresWriteSideExecution)
        result = execution.result
        assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        assert result.stream_admission_result is not None
        assert (
            result.stream_admission_result.verdict
            is AdmissionVerdict.LOCK_TIMEOUT
        )
        assert result.validation_decision is None
        assert result.admission_result is None
        assert execution.trace.terminal_checkpoint is (
            Checkpoint.CONCURRENCY_PREPARATION_RETURNED
        )

        _assert_measurement_shape(
            delivery.measurement,
            measured=_IN_LOCK_REJECTED_MEASURED,
            not_applicable=_IN_NOT_APPLICABLE,
        )
        assert (
            delivery.measurement.pessimistic_advisory_try_lock_call.state
            is State.MEASURED
        )
        assert delivery.measurement.accepted_history_load.state is State.NOT_REACHED
        assert delivery.measurement.validation_runtime_call.state is State.NOT_REACHED
        assert delivery.measurement.append_admission_call.state is State.NOT_REACHED
        assert delivery.measurement.rollback_finalization.state is State.MEASURED

        _assert_idle_and_reusable(db_connection)
        assert count_rows(db_connection, "order_events") == 0
        assert count_rows(db_connection, "idempotency_records") == 0
        db_connection.rollback()
        assert db_connection.info.transaction_status is TransactionStatus.IDLE
    finally:
        locker_connection.rollback()
        locker_connection.close()
