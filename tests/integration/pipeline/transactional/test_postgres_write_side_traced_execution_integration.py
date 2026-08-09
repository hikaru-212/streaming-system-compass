from decimal import Decimal

import pytest

from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import EventType
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
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
    PostgresWriteSideExecutionTrace,
)
from src.storage.idempotency_store import IdempotencyVerdict
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")

Checkpoint = PostgresWriteSideExecutionCheckpoint

PRE_CHECKPOINTS = (
    Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.ACCEPTED_HISTORY_OBSERVED,
    Checkpoint.VALIDATION_RETURNED,
    Checkpoint.BUSINESS_UOW_REACHED,
    Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    Checkpoint.APPEND_ADMISSION_RETURNED,
    Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)

IN_CHECKPOINTS = (
    Checkpoint.BUSINESS_UOW_REACHED,
    Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    Checkpoint.ACCEPTED_HISTORY_OBSERVED,
    Checkpoint.VALIDATION_RETURNED,
    Checkpoint.APPEND_ADMISSION_RETURNED,
    Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)


class _ValidationRuntime:
    def __init__(
        self,
        *,
        action: EnforcementAction,
        before_decision=None,
    ) -> None:
        self._action = action
        self._before_decision = before_decision

    def decide(self, candidate_event, context):
        if self._before_decision is not None:
            self._before_decision()

        verdict = (
            ValidationVerdict.PASSED
            if self._action is EnforcementAction.ALLOW
            else ValidationVerdict.FAILED
        )
        return ValidationDecision(
            action=self._action,
            validation_result=ValidationResult(
                verdict=verdict,
                reason="Traced-execution validation decision",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )


class _UnexpectedValidationRuntime:
    def decide(self, candidate_event, context):
        raise AssertionError("validation must not be reached")


def _build_write_side(
    connection,
    *,
    placement: ValidationPlacement,
    validation_runtime,
    admission_gate_factory=None,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=admission_gate_factory,
        config=PostgresWriteSideConfig(validation_placement=placement),
    )


def _pessimistic_gate_factory(uow):
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def _accept_create(connection, *, request_id: str, order_id: str):
    write_side = _build_write_side(
        connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
        ),
    )
    return write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=Decimal("100.00"),
    )


def _invoke_create(
    write_side: PostgresTransactionalWriteSide,
    *,
    with_trace: bool,
    request_id: str,
    order_id: str,
) -> tuple[PostgresWriteSideResult, PostgresWriteSideExecutionTrace | None]:
    if with_trace:
        execution = write_side.create_order_with_trace(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
        assert isinstance(execution, PostgresWriteSideExecution)
        return execution.result, execution.trace

    return (
        write_side.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        ),
        None,
    )


def _invoke_pay(
    write_side: PostgresTransactionalWriteSide,
    *,
    with_trace: bool,
    request_id: str,
    order_id: str,
) -> tuple[PostgresWriteSideResult, PostgresWriteSideExecutionTrace | None]:
    if with_trace:
        execution = write_side.pay_order_with_trace(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
        assert isinstance(execution, PostgresWriteSideExecution)
        return execution.result, execution.trace

    return (
        write_side.pay_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        ),
        None,
    )


def _assert_trace(
    trace: PostgresWriteSideExecutionTrace | None,
    *,
    with_trace: bool,
    placement: ValidationPlacement,
    checkpoints: tuple[PostgresWriteSideExecutionCheckpoint, ...],
) -> None:
    if not with_trace:
        assert trace is None
        return

    assert trace is not None
    assert trace.validation_placement is placement
    assert trace.checkpoints == checkpoints
    assert trace.terminal_checkpoint is checkpoints[-1]


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_pre_validation_block_match(
    db_connection,
    with_trace,
):
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.BLOCK,
        ),
    )

    result, trace = _invoke_create(
        write_side,
        with_trace=with_trace,
        request_id="pre-block-request",
        order_id="pre-block-order",
    )

    assert result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is None
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.BLOCK
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:3],
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_pre_authoritative_replay_match(
    db_connection,
    db_connection_factory,
    with_trace,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []

    def accept_same_request_during_validation():
        concurrent_results.append(
            _accept_create(
                concurrent_connection,
                request_id="pre-authoritative-replay-request",
                order_id="pre-authoritative-replay-order",
            )
        )

    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
            before_decision=accept_same_request_during_validation,
        ),
    )

    try:
        result, trace = _invoke_create(
            write_side,
            with_trace=with_trace,
            request_id="pre-authoritative-replay-request",
            order_id="pre-authoritative-replay-order",
        )
    finally:
        concurrent_connection.close()

    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome is PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome is PostgresWriteSideOutcome.REPLAY
    assert result.idempotency_decision.verdict is IdempotencyVerdict.REPLAY
    assert result.accepted_event == concurrent_results[0].accepted_event
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.ALLOW
    assert result.stream_admission_result is None
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:5],
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_pre_occ_conflict_match(
    db_connection,
    db_connection_factory,
    monkeypatch,
    with_trace,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    competitor_started = False
    original_prepare = PostgresOptimisticAdmissionGate.prepare_stream

    def prepare_after_competing_create(gate, order_id):
        nonlocal competitor_started
        result = original_prepare(gate, order_id)
        if not competitor_started:
            competitor_started = True
            concurrent_results.append(
                _accept_create(
                    concurrent_connection,
                    request_id="competing-occ-request",
                    order_id="pre-occ-order",
                )
            )
        return result

    monkeypatch.setattr(
        PostgresOptimisticAdmissionGate,
        "prepare_stream",
        prepare_after_competing_create,
    )
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
        ),
    )

    try:
        result, trace = _invoke_create(
            write_side,
            with_trace=with_trace,
            request_id="pre-occ-request",
            order_id="pre-occ-order",
        )
    finally:
        concurrent_connection.close()

    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome is PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict is AdmissionVerdict.STALE_WRITE
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:7],
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_in_pessimistic_accepted_match(
    db_connection,
    with_trace,
):
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    result, trace = _invoke_create(
        write_side,
        with_trace=with_trace,
        request_id="in-pessimistic-accepted-request",
        order_id="in-pessimistic-accepted-order",
    )

    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert result.accepted_event is not None
    assert result.accepted_event.event_type is EventType.CREATED
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict is AdmissionVerdict.ADMITTED
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=IN_CHECKPOINTS,
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_in_pessimistic_lock_non_acquisition_match(
    db_connection,
    db_connection_factory,
    with_trace,
):
    order_id = "in-pessimistic-locked-order"
    locker_connection = db_connection_factory()
    locker_gate = PostgresPessimisticAdmissionGate(
        connection=locker_connection,
        event_store=PostgresEventStore(locker_connection),
    )
    locker_result = locker_gate.prepare_stream(order_id)
    assert locker_result.verdict is AdmissionVerdict.ADMITTED

    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_UnexpectedValidationRuntime(),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    try:
        result, trace = _invoke_create(
            write_side,
            with_trace=with_trace,
            request_id="in-pessimistic-locked-request",
            order_id=order_id,
        )
    finally:
        locker_connection.rollback()
        locker_connection.close()

    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.LOCK_TIMEOUT
    assert result.validation_decision is None
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=IN_CHECKPOINTS[:3],
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_in_pessimistic_validation_block_match(
    db_connection,
    with_trace,
):
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.BLOCK,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    result, trace = _invoke_create(
        write_side,
        with_trace=with_trace,
        request_id="in-pessimistic-block-request",
        order_id="in-pessimistic-block-order",
    )

    assert result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.BLOCK
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=IN_CHECKPOINTS[:5],
    )


@pytest.mark.parametrize("with_trace", [False, True], ids=["legacy", "traced"])
def test_legacy_and_traced_pay_accepted_match(db_connection, with_trace):
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
        ),
    )
    create_result = write_side.create_order(
        request_id="pay-setup-create-request",
        order_id="pay-order",
        amount=Decimal("100.00"),
    )
    assert create_result.accepted_event is not None

    result, trace = _invoke_pay(
        write_side,
        with_trace=with_trace,
        request_id="pay-request",
        order_id="pay-order",
    )

    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert result.accepted_event is not None
    assert result.accepted_event.event_type is EventType.PAID
    assert result.accepted_event.sequence == 2
    assert result.accepted_event.proof.prev_event_id == (
        create_result.accepted_event.event_id
    )
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action is EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict is AdmissionVerdict.ADMITTED
    assert count_rows(db_connection, "order_events") == 2
    assert count_rows(db_connection, "idempotency_records") == 2
    _assert_trace(
        trace,
        with_trace=with_trace,
        placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS,
    )


def test_traced_record_failure_propagates_without_execution_envelope(
    db_connection,
    monkeypatch,
):
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_ValidationRuntime(
            action=EnforcementAction.ALLOW,
        ),
    )

    def fail_record(self, signature, accepted_event):
        raise RuntimeError("forced idempotency record failure")

    monkeypatch.setattr(PostgresIdempotencyStore, "record", fail_record)

    with pytest.raises(RuntimeError, match="forced idempotency record failure"):
        write_side.create_order_with_trace(
            request_id="traced-record-failure-request",
            order_id="traced-record-failure-order",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0
