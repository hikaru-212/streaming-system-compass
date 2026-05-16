from decimal import Decimal
import pytest

from src.core.order.enums import CommandType
from src.storage.idempotency_store import RequestSignature


def build_create_signature(
    request_id: str = "create-001",
    order_id: str = "order-123",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=CommandType.CREATE,
        order_id=order_id,
        amount=amount,
    )


def build_pay_signature(
    request_id: str = "pay-001",
    order_id: str = "order-123",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=CommandType.PAY,
        order_id=order_id,
        amount=amount,
    )


@pytest.fixture
def create_signature():
    return build_create_signature()


@pytest.fixture
def pay_signature():
    return build_pay_signature()