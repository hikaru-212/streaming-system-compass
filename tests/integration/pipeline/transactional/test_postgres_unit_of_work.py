from decimal import Decimal

import pytest
from psycopg.errors import UniqueViolation

from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from tests.shared.order_events import make_created_event
from tests.shared.order_events import make_paid_event
from tests.shared.postgres import count_rows
from tests.shared.request_signatures import make_request_signature
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


pytestmark = pytest.mark.usefixtures("clean_database")


def persist_successful_create(db_connection) -> tuple[OrderEvent, RequestSignature]:
    event = make_created_event(order_id="order-uow-1")
    signature = make_request_signature(
        request_id=event.request_id,
        command_type=CommandType.CREATE,
        order_id=event.order_id,
        amount=event.amount,
    )

    with PostgresWriteSideUnitOfWork(db_connection) as uow:
        uow.event_store.append(event, expected_current_version=0)
        uow.idempotency_store.record(signature, event)

    return event, signature


def test_successful_transaction_commits_event_and_idempotency_record(db_connection):
    event = make_created_event(order_id="order-uow-1")
    signature = make_request_signature(
        request_id=event.request_id,
        command_type=CommandType.CREATE,
        order_id=event.order_id,
        amount=event.amount,
    )

    with PostgresWriteSideUnitOfWork(db_connection) as uow:
        uow.event_store.append(event, expected_current_version=0)
        uow.idempotency_store.record(signature, event)

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1

    decision = PostgresIdempotencyStore(db_connection).check(signature)

    assert decision.verdict == IdempotencyVerdict.REPLAY
    assert decision.record is not None
    assert decision.record.accepted_event == event


def test_explicit_rollback_discards_event_and_idempotency_record(db_connection):
    event = make_created_event(order_id="order-uow-1")
    signature = make_request_signature(
        request_id=event.request_id,
        command_type=CommandType.CREATE,
        order_id=event.order_id,
        amount=event.amount,
    )

    with PostgresWriteSideUnitOfWork(db_connection) as uow:
        uow.event_store.append(event, expected_current_version=0)
        uow.idempotency_store.record(signature, event)
        uow.rollback()

    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_idempotency_failure_rolls_back_appended_event(db_connection):
    created_event, original_signature = persist_successful_create(db_connection)

    paid_event = make_paid_event(previous_event=created_event)
    duplicate_request_signature = make_request_signature(
        request_id=original_signature.request_id,
        command_type=CommandType.PAY,
        order_id=paid_event.order_id,
        amount=paid_event.amount,
    )

    with pytest.raises(UniqueViolation):
        with PostgresWriteSideUnitOfWork(db_connection) as uow:
            uow.event_store.append(paid_event, expected_current_version=1)
            uow.idempotency_store.record(duplicate_request_signature, paid_event)

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1

    loaded_events = PostgresEventStore(db_connection).load(created_event.order_id)

    assert loaded_events == [created_event]


def test_replay_check_does_not_create_new_event_or_record(db_connection):
    created_event, original_signature = persist_successful_create(db_connection)

    store = PostgresIdempotencyStore(db_connection)

    decision = store.check(original_signature)

    assert decision.verdict == IdempotencyVerdict.REPLAY
    assert decision.record is not None
    assert decision.record.accepted_event == created_event

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_conflict_check_does_not_create_new_event_or_record(db_connection):
    created_event, original_signature = persist_successful_create(db_connection)

    conflicting_signature = make_request_signature(
        request_id=original_signature.request_id,
        command_type=CommandType.CREATE,
        order_id=created_event.order_id,
        amount=Decimal("999.00"),
    )

    store = PostgresIdempotencyStore(db_connection)

    decision = store.check(conflicting_signature)

    assert decision.verdict == IdempotencyVerdict.CONFLICT
    assert decision.record is not None
    assert decision.record.accepted_event == created_event

    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1