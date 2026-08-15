from __future__ import annotations

from decimal import Decimal

from src.core.order.enums import CommandType
from src.storage.idempotency_store import RequestSignature


def make_request_signature(
    *,
    request_id: str,
    command_type: CommandType,
    order_id: str,
    amount: Decimal,
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=command_type,
        order_id=order_id,
        amount=amount,
    )


def make_create_signature(
    *,
    request_id: str = "create-request-001",
    order_id: str = "order-001",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return make_request_signature(
        request_id=request_id,
        command_type=CommandType.CREATE,
        order_id=order_id,
        amount=amount,
    )


def make_pay_signature(
    *,
    request_id: str = "pay-request-001",
    order_id: str = "order-001",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return make_request_signature(
        request_id=request_id,
        command_type=CommandType.PAY,
        order_id=order_id,
        amount=amount,
    )