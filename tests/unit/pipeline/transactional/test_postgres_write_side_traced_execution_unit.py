from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from typing import cast

import pytest
from psycopg import Connection

from src.compass.transition.runtime import ValidationRuntime

from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideExecution,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
    _PostgresWriteSideTraceCollector,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
    PostgresWriteSideExecutionTrace,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


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


def _result(outcome: PostgresWriteSideOutcome) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=outcome,
        accepted_event=None,
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.MISS,
            reason="Unit-test idempotency decision",
        ),
    )


def _trace_at(
    validation_placement: ValidationPlacement,
    terminal_checkpoint: Checkpoint,
) -> PostgresWriteSideExecutionTrace:
    checkpoints = (
        PRE_CHECKPOINTS
        if validation_placement is ValidationPlacement.PRE_TRANSACTION
        else IN_CHECKPOINTS
    )
    terminal_index = checkpoints.index(terminal_checkpoint)
    return PostgresWriteSideExecutionTrace(
        validation_placement=validation_placement,
        checkpoints=checkpoints[: terminal_index + 1],
    )


ALLOWED_EXECUTIONS = (
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.REPLAY,
        Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.REPLAY,
        Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.CONFLICT,
        Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.CONFLICT,
        Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        Checkpoint.VALIDATION_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        Checkpoint.APPEND_ADMISSION_RETURNED,
    ),
    (
        ValidationPlacement.PRE_TRANSACTION,
        PostgresWriteSideOutcome.ACCEPTED,
        Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.REPLAY,
        Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.CONFLICT,
        Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        Checkpoint.VALIDATION_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.ADMISSION_REJECTED,
        Checkpoint.APPEND_ADMISSION_RETURNED,
    ),
    (
        ValidationPlacement.IN_TRANSACTION,
        PostgresWriteSideOutcome.ACCEPTED,
        Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
    ),
)


def test_execution_has_exact_field_surface_and_retains_objects_by_identity():
    result = _result(PostgresWriteSideOutcome.ADMISSION_REJECTED)
    trace = _trace_at(
        ValidationPlacement.IN_TRANSACTION,
        Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    )

    execution = PostgresWriteSideExecution(result=result, trace=trace)

    assert tuple(field.name for field in fields(execution)) == (
        "result",
        "trace",
    )
    assert execution.result is result
    assert execution.trace is trace


def test_execution_is_frozen():
    execution = PostgresWriteSideExecution(
        result=_result(PostgresWriteSideOutcome.ADMISSION_REJECTED),
        trace=_trace_at(
            ValidationPlacement.IN_TRANSACTION,
            Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
        ),
    )

    with pytest.raises(FrozenInstanceError):
        setattr(execution, "trace", execution.trace)


def test_execution_rejects_wrong_result_type():
    with pytest.raises(TypeError):
        PostgresWriteSideExecution(
            result="not-a-result",  # type: ignore[arg-type]
            trace=_trace_at(
                ValidationPlacement.IN_TRANSACTION,
                Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
            ),
        )


def test_execution_rejects_wrong_trace_type():
    with pytest.raises(TypeError):
        PostgresWriteSideExecution(
            result=_result(PostgresWriteSideOutcome.ADMISSION_REJECTED),
            trace="not-a-trace",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("validation_placement", "outcome", "terminal_checkpoint"),
    ALLOWED_EXECUTIONS,
)
def test_execution_accepts_every_current_terminal_compatibility(
    validation_placement,
    outcome,
    terminal_checkpoint,
):
    result = _result(outcome)
    trace = _trace_at(validation_placement, terminal_checkpoint)

    execution = PostgresWriteSideExecution(result=result, trace=trace)

    assert execution.result is result
    assert execution.trace is trace


@pytest.mark.parametrize(
    ("validation_placement", "outcome", "terminal_checkpoint"),
    [
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.ACCEPTED,
            Checkpoint.VALIDATION_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            Checkpoint.ACCEPTED_HISTORY_OBSERVED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.REPLAY,
            Checkpoint.VALIDATION_RETURNED,
        ),
    ],
)
def test_execution_rejects_source_incoherent_terminal_combinations(
    validation_placement,
    outcome,
    terminal_checkpoint,
):
    with pytest.raises(ValueError):
        PostgresWriteSideExecution(
            result=_result(outcome),
            trace=_trace_at(validation_placement, terminal_checkpoint),
        )


def test_in_trace_rejects_preliminary_only_terminal_before_envelope_exists():
    with pytest.raises(ValueError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
            checkpoints=(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,),
        )


def test_execution_does_not_revalidate_nested_primary_result_semantics():
    result_without_nested_accepted_evidence = _result(
        PostgresWriteSideOutcome.ACCEPTED
    )

    execution = PostgresWriteSideExecution(
        result=result_without_nested_accepted_evidence,
        trace=_trace_at(
            ValidationPlacement.PRE_TRANSACTION,
            Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
        ),
    )

    assert execution.result is result_without_nested_accepted_evidence


def test_execution_excludes_unowned_responsibilities():
    execution = PostgresWriteSideExecution(
        result=_result(PostgresWriteSideOutcome.ADMISSION_REJECTED),
        trace=_trace_at(
            ValidationPlacement.IN_TRANSACTION,
            Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
        ),
    )
    forbidden_attributes = {
        "outcome",
        "verdict",
        "reason",
        "exception",
        "receipt",
        "retry",
        "attempt",
        "strategy",
        "lock_acquired",
        "policy",
        "timing",
        "cost",
        "durability",
        "rollback_disposition",
        "connection_disposition",
    }

    assert all(
        not hasattr(execution, attribute)
        for attribute in forbidden_attributes
    )


def test_collector_first_checkpoint_creates_valid_trace():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )

    collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)

    assert collector.trace.validation_placement is ValidationPlacement.PRE_TRANSACTION
    assert collector.trace.checkpoints == PRE_CHECKPOINTS[:1]


def test_collector_advances_through_new_immutable_prefixes():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )
    collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)
    first_trace = collector.trace

    collector.record(Checkpoint.ACCEPTED_HISTORY_OBSERVED)

    assert collector.trace is not first_trace
    assert first_trace.checkpoints == PRE_CHECKPOINTS[:1]
    assert collector.trace.checkpoints == PRE_CHECKPOINTS[:2]


def test_collector_rejects_duplicate_checkpoint_immediately():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )
    collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)
    valid_trace = collector.trace

    with pytest.raises(ValueError):
        collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)

    assert collector.trace is valid_trace


def test_collector_rejects_skipped_checkpoint_immediately():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )
    collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)

    with pytest.raises(ValueError):
        collector.record(Checkpoint.VALIDATION_RETURNED)


def test_collector_rejects_wrong_first_checkpoint_immediately():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )

    with pytest.raises(ValueError):
        collector.record(Checkpoint.ACCEPTED_HISTORY_OBSERVED)


def test_collector_rejects_checkpoint_from_wrong_placement_immediately():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.IN_TRANSACTION
    )

    with pytest.raises(ValueError):
        collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)


def test_collectors_preserve_actual_placement_and_are_independent():
    pre_collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.PRE_TRANSACTION
    )
    in_collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.IN_TRANSACTION
    )

    pre_collector.record(Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED)
    in_collector.record(Checkpoint.BUSINESS_UOW_REACHED)

    assert (
        pre_collector.trace.validation_placement
        is ValidationPlacement.PRE_TRANSACTION
    )
    assert in_collector.trace.validation_placement is ValidationPlacement.IN_TRANSACTION
    assert pre_collector.trace.checkpoints == PRE_CHECKPOINTS[:1]
    assert in_collector.trace.checkpoints == IN_CHECKPOINTS[:1]


def test_collector_has_no_trace_before_first_checkpoint():
    collector = _PostgresWriteSideTraceCollector(
        ValidationPlacement.IN_TRANSACTION
    )

    with pytest.raises(RuntimeError):
        _ = collector.trace


class _CommitFailure(Exception):
    pass


class _EnvelopeConstructionFailure(Exception):
    pass


class _TraceConstructionFailure(Exception):
    pass


class _AggregateRehydrationFailure(Exception):
    pass


class _FakeConnection:
    def __init__(
        self,
        *,
        history=None,
        fail_commit: bool = False,
    ) -> None:
        self.autocommit = False
        self.events: list[str] = []
        self.history = [] if history is None else history
        self.fail_commit = fail_commit

    def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise _CommitFailure

    def rollback(self) -> None:
        self.events.append("rollback")


class _AllowingValidationRuntime:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def decide(self, candidate_event, context):
        self._events.append("validation")
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="Pure unit validation allowed candidate",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )


class _AdmittedGate:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        self._events.append("concurrency_preparation")
        return StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Pure unit preparation admitted stream",
            order_id=order_id,
        )

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        self._events.append("append_admission")
        return AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Pure unit append admitted candidate",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=candidate_event.event_id,
        )


def _install_successful_store_fakes(monkeypatch) -> None:
    def check_idempotency(store, signature):
        store._connection.events.append("idempotency_check")
        return IdempotencyDecision(
            verdict=IdempotencyVerdict.MISS,
            reason="Pure unit idempotency miss",
        )

    def record_idempotency(store, signature, accepted_event):
        store._connection.events.append("idempotency_persistence")

    def load_history(store, order_id):
        store._connection.events.append("history_load")
        return list(store._connection.history)

    monkeypatch.setattr(PostgresIdempotencyStore, "check", check_idempotency)
    monkeypatch.setattr(PostgresIdempotencyStore, "record", record_idempotency)
    monkeypatch.setattr(PostgresEventStore, "load", load_history)


def _build_write_side(
    connection: _FakeConnection,
    validation_placement: ValidationPlacement,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=cast(Connection, connection),
        validation_runtime=cast(
            ValidationRuntime,
            _AllowingValidationRuntime(connection.events),
        ),
        admission_gate_factory=lambda uow: _AdmittedGate(connection.events),
        config=PostgresWriteSideConfig(
            validation_placement=validation_placement
        ),
    )


@pytest.mark.parametrize(
    ("validation_placement", "expected_checkpoints"),
    [
        (ValidationPlacement.PRE_TRANSACTION, PRE_CHECKPOINTS),
        (ValidationPlacement.IN_TRANSACTION, IN_CHECKPOINTS),
    ],
)
def test_legacy_and_traced_create_share_path_and_preserve_result_type(
    monkeypatch,
    validation_placement,
    expected_checkpoints,
):
    _install_successful_store_fakes(monkeypatch)
    legacy_connection = _FakeConnection()
    traced_connection = _FakeConnection()

    legacy_result = _build_write_side(
        legacy_connection,
        validation_placement,
    ).create_order(
        request_id="legacy-request",
        order_id="legacy-order",
        amount=Decimal("100.00"),
    )
    traced_execution = _build_write_side(
        traced_connection,
        validation_placement,
    ).create_order_with_trace(
        request_id="traced-request",
        order_id="traced-order",
        amount=Decimal("100.00"),
    )

    assert type(legacy_result) is PostgresWriteSideResult
    assert type(traced_execution) is PostgresWriteSideExecution
    assert legacy_result.outcome is traced_execution.result.outcome
    assert traced_execution.trace.validation_placement is validation_placement
    assert traced_execution.trace.checkpoints == expected_checkpoints
    assert legacy_connection.events == traced_connection.events


def test_legacy_call_does_not_create_collector_trace_or_envelope(
    monkeypatch,
):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection()
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )

    def reject_collector_construction(self, validation_placement):
        raise AssertionError("legacy call must not construct trace collector")

    monkeypatch.setattr(
        _PostgresWriteSideTraceCollector,
        "__init__",
        reject_collector_construction,
    )

    result = write_side.create_order(
        request_id="legacy-only-request",
        order_id="legacy-only-order",
        amount=Decimal("100.00"),
    )

    assert type(result) is PostgresWriteSideResult
    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED


def test_traced_pay_returns_execution_from_shared_pre_path(monkeypatch):
    _install_successful_store_fakes(monkeypatch)
    seed_aggregate = OrderAggregate("pay-order")
    created_event = seed_aggregate.create(
        request_id="seed-request",
        total_amount=Decimal("100.00"),
    )
    connection = _FakeConnection(history=[created_event])
    write_side = _build_write_side(
        connection,
        ValidationPlacement.PRE_TRANSACTION,
    )

    execution = write_side.pay_order_with_trace(
        request_id="pay-request",
        order_id="pay-order",
        amount=Decimal("100.00"),
    )

    assert type(execution) is PostgresWriteSideExecution
    assert execution.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert execution.trace.checkpoints == PRE_CHECKPOINTS


def test_accepted_trace_and_envelope_are_constructed_before_commit(
    monkeypatch,
):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection()
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )
    original_trace_post_init = PostgresWriteSideExecutionTrace.__post_init__
    original_execution_post_init = PostgresWriteSideExecution.__post_init__

    def observe_trace_validation(trace):
        original_trace_post_init(trace)
        if (
            trace.terminal_checkpoint
            is Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED
        ):
            connection.events.append("final_trace_validated")

    def observe_execution_construction(execution):
        original_execution_post_init(execution)
        connection.events.append("execution_constructed")

    monkeypatch.setattr(
        PostgresWriteSideExecutionTrace,
        "__post_init__",
        observe_trace_validation,
    )
    monkeypatch.setattr(
        PostgresWriteSideExecution,
        "__post_init__",
        observe_execution_construction,
    )

    execution = write_side.create_order_with_trace(
        request_id="precommit-ordering-request",
        order_id="precommit-ordering-order",
        amount=Decimal("100.00"),
    )

    assert type(execution) is PostgresWriteSideExecution
    assert connection.events.index("idempotency_persistence") < connection.events.index(
        "final_trace_validated"
    )
    assert connection.events.index("final_trace_validated") < connection.events.index(
        "execution_constructed"
    )
    assert connection.events.index("execution_constructed") < connection.events.index(
        "commit"
    )


def test_envelope_construction_failure_occurs_before_commit_and_rolls_back(
    monkeypatch,
):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection()
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )

    def fail_execution_construction(execution):
        connection.events.append("execution_construction_failed")
        raise _EnvelopeConstructionFailure

    monkeypatch.setattr(
        PostgresWriteSideExecution,
        "__post_init__",
        fail_execution_construction,
    )

    with pytest.raises(_EnvelopeConstructionFailure):
        write_side.create_order_with_trace(
            request_id="envelope-failure-request",
            order_id="envelope-failure-order",
            amount=Decimal("100.00"),
        )

    assert "commit" not in connection.events
    assert connection.events.index(
        "idempotency_persistence"
    ) < connection.events.index("execution_construction_failed")
    assert connection.events.index(
        "execution_construction_failed"
    ) < connection.events.index("rollback")


def test_final_trace_validation_failure_occurs_before_commit_and_rolls_back(
    monkeypatch,
):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection()
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )
    original_trace_post_init = PostgresWriteSideExecutionTrace.__post_init__

    def fail_final_trace_validation(trace):
        original_trace_post_init(trace)
        if (
            trace.terminal_checkpoint
            is Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED
        ):
            connection.events.append("final_trace_validation_failed")
            raise _TraceConstructionFailure

    monkeypatch.setattr(
        PostgresWriteSideExecutionTrace,
        "__post_init__",
        fail_final_trace_validation,
    )

    with pytest.raises(_TraceConstructionFailure):
        write_side.create_order_with_trace(
            request_id="trace-failure-request",
            order_id="trace-failure-order",
            amount=Decimal("100.00"),
        )

    assert "commit" not in connection.events
    assert connection.events.index(
        "idempotency_persistence"
    ) < connection.events.index("final_trace_validation_failed")
    assert connection.events.index(
        "final_trace_validation_failed"
    ) < connection.events.index("rollback")


def test_commit_failure_prevents_traced_execution_delivery(monkeypatch):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection(fail_commit=True)
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )
    original_execution_post_init = PostgresWriteSideExecution.__post_init__

    def observe_execution_construction(execution):
        original_execution_post_init(execution)
        connection.events.append("execution_constructed")

    monkeypatch.setattr(
        PostgresWriteSideExecution,
        "__post_init__",
        observe_execution_construction,
    )
    delivered = False

    with pytest.raises(_CommitFailure):
        write_side.create_order_with_trace(
            request_id="commit-failure-request",
            order_id="commit-failure-order",
            amount=Decimal("100.00"),
        )
        delivered = True

    assert delivered is False
    assert connection.events.index("execution_constructed") < connection.events.index(
        "commit"
    )


def test_in_history_checkpoint_precedes_aggregate_rehydration_failure(
    monkeypatch,
):
    _install_successful_store_fakes(monkeypatch)
    connection = _FakeConnection()
    write_side = _build_write_side(
        connection,
        ValidationPlacement.IN_TRANSACTION,
    )
    original_trace_post_init = PostgresWriteSideExecutionTrace.__post_init__

    def observe_trace_validation(trace):
        original_trace_post_init(trace)
        if trace.terminal_checkpoint is Checkpoint.ACCEPTED_HISTORY_OBSERVED:
            connection.events.append("history_checkpoint")

    def fail_rehydration(order_id, history):
        connection.events.append("aggregate_rehydration")
        raise _AggregateRehydrationFailure

    monkeypatch.setattr(
        PostgresWriteSideExecutionTrace,
        "__post_init__",
        observe_trace_validation,
    )
    monkeypatch.setattr(
        write_side,
        "_rehydrate_aggregate_from_history",
        fail_rehydration,
    )

    with pytest.raises(_AggregateRehydrationFailure):
        write_side.create_order_with_trace(
            request_id="rehydration-failure-request",
            order_id="rehydration-failure-order",
            amount=Decimal("100.00"),
        )

    assert connection.events.index("history_load") < connection.events.index(
        "history_checkpoint"
    )
    assert connection.events.index("history_checkpoint") < connection.events.index(
        "aggregate_rehydration"
    )
    assert connection.events.index("aggregate_rehydration") < connection.events.index(
        "rollback"
    )


def test_pr6_does_not_depend_on_clean_commit_checkpoint():
    assert not hasattr(Checkpoint, "CLEAN_COMMIT_RETURNED")
    assert all(
        checkpoint.name != "CLEAN_COMMIT_RETURNED"
        for checkpoint in (*PRE_CHECKPOINTS, *IN_CHECKPOINTS)
    )
