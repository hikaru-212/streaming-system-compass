from src.storage.idempotency_store import (
    IdempotencyProvider,
    IdempotencyVerdict,
    RequestSignature,
)
from src.core.order.enums import CommandType


class TestIdempotencyProvider:
    def test_check_returns_miss_for_unseen_request(self):
        provider = IdempotencyProvider()

        signature = RequestSignature(
            request_id="create-001",
            command_type=CommandType.CREATE,
            order_id="order-123",
            amount=100.0,
        )

        decision = provider.check(signature)

        assert decision.verdict == IdempotencyVerdict.MISS
        assert decision.record is None

    def test_record_then_check_same_signature_returns_replay(self, created_event):
        provider = IdempotencyProvider()

        signature = RequestSignature(
            request_id="create-001",
            command_type=CommandType.CREATE,
            order_id="order-123",
            amount=100.0,
        )
        provider.record(signature, created_event)

        decision = provider.check(signature)

        assert decision.verdict == IdempotencyVerdict.REPLAY
        assert decision.record is not None
        assert decision.record.signature == signature
        assert decision.record.accepted_event == created_event

    def test_same_request_id_different_amount_returns_conflict(self, created_event):
        provider = IdempotencyProvider()

        original = RequestSignature(
            request_id="pay-001",
            command_type=CommandType.PAY,
            order_id="order-123",
            amount=100.0,
        )
        provider.record(original, created_event)

        changed = RequestSignature(
            request_id="pay-001",
            command_type=CommandType.PAY,
            order_id="order-123",
            amount=10.0,
        )

        decision = provider.check(changed)

        assert decision.verdict == IdempotencyVerdict.CONFLICT
        assert decision.record is not None
        assert decision.record.signature == original

    def test_same_request_id_different_order_id_returns_conflict(self, created_event):
        provider = IdempotencyProvider()

        original = RequestSignature(
            request_id="pay-001",
            command_type=CommandType.PAY,
            order_id="order-123",
            amount=100.0,
        )
        provider.record(original, created_event)

        changed = RequestSignature(
            request_id="pay-001",
            command_type=CommandType.PAY,
            order_id="order-999",
            amount=100.0,
        )

        decision = provider.check(changed)

        assert decision.verdict == IdempotencyVerdict.CONFLICT

    def test_same_request_id_different_command_type_returns_conflict(self, created_event):
        provider = IdempotencyProvider()

        original = RequestSignature(
            request_id="same-001",
            command_type=CommandType.CREATE,
            order_id="order-123",
            amount=100.0,
        )
        provider.record(original, created_event)

        changed = RequestSignature(
            request_id="same-001",
            command_type=CommandType.PAY,
            order_id="order-123",
            amount=100.0,
        )

        decision = provider.check(changed)

        assert decision.verdict == IdempotencyVerdict.CONFLICT