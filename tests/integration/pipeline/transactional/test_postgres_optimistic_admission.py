import pytest

from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
)
from src.storage.postgres_event_store import PostgresEventStore
from tests.shared.order_events import make_created_event
from tests.shared.order_events import make_paid_event
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")


def test_postgres_optimistic_gate_prepare_stream_is_noop(db_connection):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresOptimisticAdmissionGate(event_store)

    result = gate.prepare_stream("order-admission-1")

    assert result.verdict == AdmissionVerdict.ADMITTED
    assert result.admitted is True
    assert result.order_id == "order-admission-1"

    assert count_rows(db_connection, "order_events") == 0


def test_postgres_optimistic_gate_admits_fresh_created_event(db_connection):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresOptimisticAdmissionGate(event_store)

    candidate_event = make_created_event(order_id="order-admission-1")

    result = gate.append_if_admitted(candidate_event, expected_current_version=0)
    db_connection.commit()

    assert result.verdict == AdmissionVerdict.ADMITTED
    assert result.admitted is True
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id == candidate_event.event_id

    assert count_rows(db_connection, "order_events") == 1


def test_postgres_optimistic_gate_rejects_stale_expected_version(
    db_connection,
):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresOptimisticAdmissionGate(event_store)

    created_event = make_created_event(order_id="order-admission-1")
    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    stale_candidate = make_paid_event(
        previous_event=created_event,
        request_id="pay-request-001",
    )

    result = gate.append_if_admitted(stale_candidate, expected_current_version=0)

    assert result.verdict == AdmissionVerdict.STALE_WRITE
    assert result.admitted is False
    assert result.candidate_event_id == stale_candidate.event_id
    assert result.accepted_event_id is None

    assert count_rows(db_connection, "order_events") == 1


def test_postgres_optimistic_gate_rejects_stale_writer_after_competing_append(
    db_connection,
):
    event_store = PostgresEventStore(db_connection)
    gate = PostgresOptimisticAdmissionGate(event_store)

    created_event = make_created_event(order_id="order-admission-1")
    event_store.append(created_event, expected_current_version=0)
    db_connection.commit()

    winning_event = make_paid_event(
        previous_event=created_event,
        request_id="pay-worker-a",
    )
    stale_event = make_paid_event(
        previous_event=created_event,
        request_id="pay-worker-b",
    )

    winning_result = gate.append_if_admitted(winning_event, expected_current_version=1)
    db_connection.commit()

    stale_result = gate.append_if_admitted(stale_event, expected_current_version=1)

    assert winning_result.verdict == AdmissionVerdict.ADMITTED
    assert stale_result.verdict == AdmissionVerdict.STALE_WRITE
    assert stale_result.admitted is False
    assert stale_result.accepted_event_id is None

    loaded_events = event_store.load("order-admission-1")

    assert loaded_events == [created_event, winning_event]
    assert count_rows(db_connection, "order_events") == 2