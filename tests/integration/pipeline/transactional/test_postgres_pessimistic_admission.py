import os
from decimal import Decimal

import psycopg
import pytest

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_admission import (
    PostgresPessimisticAdmissionGate,
)
from src.storage.postgres_event_store import PostgresEventStore


pytestmark = pytest.mark.usefixtures("clean_database")


def count_rows(db_connection, table_name: str) -> int:
    with db_connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result = cursor.fetchone()

    return result[0]


def build_created_event(
    *,
    request_id: str = "create-request-001",
    order_id: str = "order-pessimistic-admission-1",
    sequence: int = 1,
    amount: Decimal = Decimal("100.00"),
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=EventType.CREATED,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )


def build_paid_event(
    *,
    request_id: str = "pay-request-001",
    order_id: str = "order-pessimistic-admission-1",
    sequence: int = 2,
    amount: Decimal = Decimal("100.00"),
    prev_event_id: str = "previous-event-id",
) -> OrderEvent:
    return OrderEvent.create(
        request_id=request_id,
        order_id=order_id,
        sequence=sequence,
        event_type=EventType.PAID,
        amount=amount,
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=1,
            prev_event_id=prev_event_id,
        ),
    )


def test_postgres_pessimistic_gate_admits_fresh_created_event(db_connection):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresPessimisticAdmissionGate(
        connection=db_connection,
        event_store=event_store,
    )

    candidate_event = build_created_event()

    result = gate.admit(candidate_event, expected_current_version=0)
    db_connection.commit()

    assert result.verdict == AdmissionVerdict.ADMITTED
    assert result.admitted is True
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id == candidate_event.event_id

    assert count_rows(db_connection, "order_events") == 1


def test_postgres_pessimistic_gate_rejects_stale_expected_version(
    db_connection,
):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresPessimisticAdmissionGate(
        connection=db_connection,
        event_store=event_store,
    )

    created_event = build_created_event()
    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    stale_candidate = build_paid_event(
        request_id="pay-request-001",
        prev_event_id=created_event.event_id,
    )

    result = gate.admit(stale_candidate, expected_current_version=0)

    assert result.verdict == AdmissionVerdict.STALE_WRITE
    assert result.admitted is False
    assert result.candidate_event_id == stale_candidate.event_id
    assert result.accepted_event_id is None

    assert count_rows(db_connection, "order_events") == 1


def test_postgres_pessimistic_gate_returns_lock_timeout_when_stream_lock_is_held(
    db_connection,
):
    locked_order_id = "order-pessimistic-locked"

    locker_connection = psycopg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        with locker_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_advisory_xact_lock(
                    hashtext(%s),
                    hashtext(%s)
                )
                """,
                ("order_events_stream", locked_order_id),
            )

        event_store = PostgresEventStore(db_connection)
        gate = PostgresPessimisticAdmissionGate(
            connection=db_connection,
            event_store=event_store,
        )

        candidate_event = build_created_event(
            request_id="create-request-locked",
            order_id=locked_order_id,
        )

        result = gate.admit(candidate_event, expected_current_version=0)

        assert result.verdict == AdmissionVerdict.LOCK_TIMEOUT
        assert result.admitted is False
        assert result.candidate_event_id == candidate_event.event_id
        assert result.accepted_event_id is None

        assert count_rows(db_connection, "order_events") == 0
    finally:
        locker_connection.rollback()
        locker_connection.close()


def test_postgres_pessimistic_gate_rejects_autocommit_connection(db_connection):
    db_connection.autocommit = True

    try:
        event_store = PostgresEventStore(db_connection)
        gate = PostgresPessimisticAdmissionGate(
            connection=db_connection,
            event_store=event_store,
        )

        candidate_event = build_created_event()

        result = gate.admit(candidate_event, expected_current_version=0)

        assert result.verdict == AdmissionVerdict.INFRASTRUCTURE_ERROR
        assert result.admitted is False
        assert result.accepted_event_id is None
        assert count_rows(db_connection, "order_events") == 0
    finally:
        db_connection.autocommit = False