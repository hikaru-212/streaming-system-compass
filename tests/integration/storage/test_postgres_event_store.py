import uuid
from decimal import Decimal

import pytest

from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.storage.postgres_event_store import PostgresEventStore
from tests.shared.order_events import make_created_event
from tests.shared.order_events import make_paid_event


pytestmark = pytest.mark.usefixtures("clean_database")

def test_append_and_load_returns_ordered_history(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )
    paid = make_paid_event(previous_event=created, request_id="pay-001")

    store.append(created, expected_current_version=0)
    store.append(paid, expected_current_version=1)
    db_connection.commit()

    history = store.load(created.order_id)

    assert history == [created, paid]
    assert history[0].sequence == 1
    assert history[1].sequence == 2


def test_last_event_returns_latest_event(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )
    paid = make_paid_event(previous_event=created, request_id="pay-001")

    store.append(created, expected_current_version=0)
    store.append(paid, expected_current_version=1)
    db_connection.commit()

    last = store.last_event(created.order_id)

    assert last == paid
    assert last.sequence == 2


def test_append_rejects_stale_expected_version(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )

    store.append(created, expected_current_version=0)
    db_connection.commit()

    stale_event = OrderEvent.create(
        request_id="create-002",
        order_id=created.order_id,
        sequence=2,
        event_type=EventType.CREATED,
        amount=Decimal("50.00"),
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )

    with pytest.raises(ValueError, match="Version conflict"):
        store.append(stale_event, expected_current_version=0)


def test_uuid_decimal_and_proof_status_round_trip(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )

    store.append(created, expected_current_version=0)
    db_connection.commit()

    loaded = store.load(created.order_id)[0]

    parsed_event_id = uuid.UUID(loaded.event_id)

    assert str(parsed_event_id) == created.event_id
    assert loaded.amount == Decimal("100.00")
    assert loaded.proof.prev_status == OrderStatus.INIT
    assert loaded.proof.prev_version == 0
    assert loaded.proof.prev_event_id is None


def test_jsonb_fields_and_event_schema_version_are_persisted(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )

    store.append(created, expected_current_version=0)
    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                event_schema_version,
                payload_json,
                proof_json,
                metadata_json
            FROM order_events
            WHERE accepted_event_id = %s
            """,
            (created.event_id,),
        )
        row = cursor.fetchone()

    assert row[0] == 1
    assert row[1] == {}
    assert row[2]["prev_event_id"] is None
    assert row[2]["prev_version"] == 0
    assert row[2]["prev_status"] == OrderStatus.INIT.value
    assert row[3] == {}


def test_append_rejects_broken_sequence(db_connection):
    store = PostgresEventStore(db_connection)

    created = make_created_event(
        request_id="create-001",
        order_id="order-postgres-1",
    )
    store.append(created, expected_current_version=0)
    db_connection.commit()

    broken_event = OrderEvent.create(
        request_id="pay-001",
        order_id=created.order_id,
        sequence=1,  # should be 2
        event_type=EventType.PAID,
        amount=Decimal("100.00"),
        proof=Proof(
            prev_status=OrderStatus.CREATED,
            prev_version=1,
            prev_event_id=created.event_id,
        ),
    )

    with pytest.raises(ValueError, match="Append-time continuity broken"):
        store.append(broken_event, expected_current_version=1)