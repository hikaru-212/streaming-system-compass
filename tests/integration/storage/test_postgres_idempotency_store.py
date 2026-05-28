from decimal import Decimal

import pytest
from psycopg.errors import ForeignKeyViolation

from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import (
    FINGERPRINT_VERSION,
    PostgresIdempotencyStore,
    build_semantic_fingerprint,
)


pytestmark = pytest.mark.usefixtures("clean_database")


def build_created_event(order_id: str = "order-idem-1") -> OrderEvent:
    return OrderEvent.create(
        request_id="create-request-001",
        order_id=order_id,
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("100.00"),
        proof=Proof(
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        ),
    )


def build_signature(
    *,
    request_id: str = "idem-request-001",
    command_type: CommandType = CommandType.CREATE,
    order_id: str = "order-idem-1",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=command_type,
        order_id=order_id,
        amount=amount,
    )


def persist_accepted_event(db_connection, event: OrderEvent) -> None:
    event_store = PostgresEventStore(db_connection)
    event_store.append(event, expected_current_version=event.sequence - 1)
    db_connection.commit()


def test_unseen_request_returns_miss(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    signature = build_signature()

    decision = store.check(signature)

    assert decision.verdict == IdempotencyVerdict.MISS
    assert decision.record is None
    assert decision.reason == "No prior request with this request_id"


def test_record_then_same_signature_returns_replay(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    persist_accepted_event(db_connection, event)

    signature = build_signature(order_id=event.order_id, amount=event.amount)

    store.record(signature, event)
    db_connection.commit()

    decision = store.check(signature)

    assert decision.verdict == IdempotencyVerdict.REPLAY
    assert decision.record is not None
    assert decision.record.signature == signature
    assert decision.record.accepted_event == event


def test_same_request_id_with_different_amount_returns_conflict(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    persist_accepted_event(db_connection, event)

    original_signature = build_signature(order_id=event.order_id, amount=event.amount)
    conflicting_signature = build_signature(
        request_id=original_signature.request_id,
        order_id=event.order_id,
        amount=Decimal("200.00"),
    )

    store.record(original_signature, event)
    db_connection.commit()

    decision = store.check(conflicting_signature)

    assert decision.verdict == IdempotencyVerdict.CONFLICT
    assert decision.record is not None
    assert decision.record.signature == original_signature
    assert decision.record.accepted_event == event


def test_same_request_id_with_different_order_id_returns_conflict(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    persist_accepted_event(db_connection, event)

    original_signature = build_signature(order_id=event.order_id, amount=event.amount)
    conflicting_signature = build_signature(
        request_id=original_signature.request_id,
        order_id="different-order-id",
        amount=event.amount,
    )

    store.record(original_signature, event)
    db_connection.commit()

    decision = store.check(conflicting_signature)

    assert decision.verdict == IdempotencyVerdict.CONFLICT
    assert decision.record is not None
    assert decision.record.signature == original_signature
    assert decision.record.accepted_event == event


def test_same_request_id_with_different_command_type_returns_conflict(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    persist_accepted_event(db_connection, event)

    original_signature = build_signature(
        command_type=CommandType.CREATE,
        order_id=event.order_id,
        amount=event.amount,
    )
    conflicting_signature = build_signature(
        request_id=original_signature.request_id,
        command_type=CommandType.PAY,
        order_id=event.order_id,
        amount=event.amount,
    )

    store.record(original_signature, event)
    db_connection.commit()

    decision = store.check(conflicting_signature)

    assert decision.verdict == IdempotencyVerdict.CONFLICT
    assert decision.record is not None
    assert decision.record.signature == original_signature
    assert decision.record.accepted_event == event


def test_idempotency_record_survives_new_connection(
    db_connection,
    db_connection_factory,
):
    event = build_created_event()
    persist_accepted_event(db_connection, event)

    signature = build_signature(order_id=event.order_id, amount=event.amount)

    store = PostgresIdempotencyStore(db_connection)
    store.record(signature, event)
    db_connection.commit()

    new_connection = db_connection_factory()
    try:
        new_store = PostgresIdempotencyStore(new_connection)

        decision = new_store.check(signature)

        assert decision.verdict == IdempotencyVerdict.REPLAY
        assert decision.record is not None
        assert decision.record.signature == signature
        assert decision.record.accepted_event == event
    finally:
        new_connection.close()


def test_record_requires_existing_accepted_event(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    signature = build_signature(order_id=event.order_id, amount=event.amount)

    with pytest.raises(ForeignKeyViolation):
        store.record(signature, event)

    db_connection.rollback()


def test_semantic_fingerprint_excludes_request_id():
    signature_a = build_signature(request_id="request-a")
    signature_b = build_signature(request_id="request-b")

    assert build_semantic_fingerprint(signature_a) == build_semantic_fingerprint(
        signature_b
    )


def test_semantic_fingerprint_changes_when_semantic_payload_changes():
    signature = build_signature(amount=Decimal("100.00"))
    changed_amount = build_signature(
        request_id=signature.request_id,
        amount=Decimal("200.00"),
    )

    assert build_semantic_fingerprint(signature) != build_semantic_fingerprint(
        changed_amount
    )


def test_semantic_fingerprint_uses_current_version_prefix():
    signature = build_signature()

    fingerprint = build_semantic_fingerprint(signature)

    assert fingerprint.startswith(f"v{FINGERPRINT_VERSION}|")


def test_conflict_does_not_overwrite_existing_record(db_connection):
    store = PostgresIdempotencyStore(db_connection)

    event = build_created_event()
    persist_accepted_event(db_connection, event)

    original_signature = build_signature(order_id=event.order_id, amount=event.amount)
    conflicting_signature = build_signature(
        request_id=original_signature.request_id,
        order_id=event.order_id,
        amount=Decimal("200.00"),
    )

    store.record(original_signature, event)
    db_connection.commit()

    conflict_decision = store.check(conflicting_signature)

    assert conflict_decision.verdict == IdempotencyVerdict.CONFLICT

    replay_decision = store.check(original_signature)

    assert replay_decision.verdict == IdempotencyVerdict.REPLAY
    assert replay_decision.record is not None
    assert replay_decision.record.signature == original_signature
    assert replay_decision.record.accepted_event == event