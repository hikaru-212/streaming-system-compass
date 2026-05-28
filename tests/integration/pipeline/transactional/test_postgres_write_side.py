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
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
)
from src.storage.idempotency_store import IdempotencyVerdict
from src.storage.postgres_connection import connect_postgres
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


def _status_value(status):
    return status.value if status is not None else None


class FakeValidationRuntimeAllow:
    def decide(self, candidate_event, context):
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="Fake validation allowed candidate event",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                    "actual_prev_status": _status_value(context.actual_prev_status),
                },
            ),
        )


class FakeValidationRuntimeBlock:
    def decide(self, candidate_event, context):
        return ValidationDecision(
            action=EnforcementAction.BLOCK,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="Fake validation blocked candidate event",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                    "actual_prev_status": _status_value(context.actual_prev_status),
                },
            ),
        )


@pytest.fixture
def db_connection():
    connection = connect_postgres()
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def clean_database(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE idempotency_records, order_events RESTART IDENTITY CASCADE"
        )
    db_connection.commit()


@pytest.fixture
def write_side(db_connection):
    return PostgresTransactionalWriteSide(
        connection=db_connection,
        validation_runtime=FakeValidationRuntimeAllow(),
    )


def count_rows(db_connection, table_name: str) -> int:
    with db_connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result = cursor.fetchone()

    return result[0]


def test_create_order_accepts_event_and_records_idempotency(db_connection, write_side):
    result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert result.outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.accepted_event is not None
    assert result.accepted_event.event_type == EventType.CREATED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_create_order_replay_returns_previous_accepted_event_without_new_rows(
    db_connection,
    write_side,
):
    first_result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    replay_result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert replay_result.outcome == PostgresWriteSideOutcome.REPLAY
    assert replay_result.idempotency_decision.verdict == IdempotencyVerdict.REPLAY
    assert replay_result.accepted_event == first_result.accepted_event
    assert replay_result.validation_decision is None

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_create_order_conflict_does_not_create_new_rows(db_connection, write_side):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    conflict_result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("999.00"),
    )

    assert conflict_result.outcome == PostgresWriteSideOutcome.CONFLICT
    assert conflict_result.idempotency_decision.verdict == IdempotencyVerdict.CONFLICT
    assert conflict_result.accepted_event is None
    assert conflict_result.validation_decision is None

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_create_order_validation_block_does_not_create_new_rows(db_connection):
    write_side = PostgresTransactionalWriteSide(
        connection=db_connection,
        validation_runtime=FakeValidationRuntimeBlock(),
    )

    result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.BLOCK

    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_create_order_record_failure_rolls_back_appended_event(
    db_connection,
    write_side,
    monkeypatch,
):
    def fail_record(self, signature, accepted_event):
        raise RuntimeError("forced idempotency record failure")

    monkeypatch.setattr(PostgresIdempotencyStore, "record", fail_record)

    with pytest.raises(RuntimeError, match="forced idempotency record failure"):
        write_side.create_order(
            request_id="create-request-001",
            order_id="order-write-side-1",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_pay_order_accepts_second_event_and_records_idempotency(
    db_connection,
    write_side,
):
    create_result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    pay_result = write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert pay_result.outcome == PostgresWriteSideOutcome.ACCEPTED
    assert pay_result.accepted_event is not None
    assert pay_result.accepted_event.event_type == EventType.PAID
    assert pay_result.accepted_event.sequence == 2
    assert pay_result.accepted_event.proof.prev_event_id == (
        create_result.accepted_event.event_id
    )
    assert pay_result.validation_decision is not None
    assert pay_result.validation_decision.action == EnforcementAction.ALLOW

    assert count_rows(db_connection, "order_events") == 2
    assert count_rows(db_connection, "idempotency_records") == 2


def test_pay_order_replay_returns_previous_paid_event_without_new_rows(
    db_connection,
    write_side,
):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    first_pay_result = write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    replay_pay_result = write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert replay_pay_result.outcome == PostgresWriteSideOutcome.REPLAY
    assert replay_pay_result.idempotency_decision.verdict == IdempotencyVerdict.REPLAY
    assert replay_pay_result.accepted_event == first_pay_result.accepted_event
    assert replay_pay_result.validation_decision is None

    assert count_rows(db_connection, "order_events") == 2
    assert count_rows(db_connection, "idempotency_records") == 2


def test_pay_order_conflict_does_not_create_new_rows(db_connection, write_side):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    conflict_result = write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("999.00"),
    )

    assert conflict_result.outcome == PostgresWriteSideOutcome.CONFLICT
    assert conflict_result.idempotency_decision.verdict == IdempotencyVerdict.CONFLICT
    assert conflict_result.accepted_event is None
    assert conflict_result.validation_decision is None

    assert count_rows(db_connection, "order_events") == 2
    assert count_rows(db_connection, "idempotency_records") == 2


def test_pay_order_validation_block_does_not_create_second_event(
    db_connection,
):
    create_write_side = PostgresTransactionalWriteSide(
        connection=db_connection,
        validation_runtime=FakeValidationRuntimeAllow(),
    )
    block_write_side = PostgresTransactionalWriteSide(
        connection=db_connection,
        validation_runtime=FakeValidationRuntimeBlock(),
    )

    create_write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    result = block_write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    assert result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.BLOCK

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_pay_order_record_failure_rolls_back_second_event(
    db_connection,
    write_side,
    monkeypatch,
):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    def fail_record(self, signature, accepted_event):
        raise RuntimeError("forced idempotency record failure")

    monkeypatch.setattr(PostgresIdempotencyStore, "record", fail_record)

    with pytest.raises(RuntimeError, match="forced idempotency record failure"):
        write_side.pay_order(
            request_id="pay-request-001",
            order_id="order-write-side-1",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_create_order_rejects_existing_history_and_rolls_back(
    db_connection,
    write_side,
):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    with pytest.raises(ValueError, match="Already created"):
        write_side.create_order(
            request_id="create-request-002",
            order_id="order-write-side-1",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_pay_order_requires_existing_history(db_connection, write_side):
    with pytest.raises(ValueError, match="Cannot pay before order is created"):
        write_side.pay_order(
            request_id="pay-request-001",
            order_id="missing-order",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_pay_order_requires_latest_state_to_be_unpaid(db_connection, write_side):
    write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )
    write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    with pytest.raises(ValueError, match="Order is already paid"):
        write_side.pay_order(
            request_id="pay-request-002",
            order_id="order-write-side-1",
            amount=Decimal("100.00"),
        )

    assert count_rows(db_connection, "order_events") == 2
    assert count_rows(db_connection, "idempotency_records") == 2


def test_accepted_history_can_be_loaded_after_transactional_flow(
    db_connection,
    write_side,
):
    create_result = write_side.create_order(
        request_id="create-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )
    pay_result = write_side.pay_order(
        request_id="pay-request-001",
        order_id="order-write-side-1",
        amount=Decimal("100.00"),
    )

    loaded_events = PostgresEventStore(db_connection).load("order-write-side-1")

    assert loaded_events == [
        create_result.accepted_event,
        pay_result.accepted_event,
    ]