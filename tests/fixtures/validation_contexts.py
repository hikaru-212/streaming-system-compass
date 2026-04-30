import pytest

from src.core.order.enums import OrderStatus
from src.compass.transition.types import ValidationContext


@pytest.fixture
def created_validation_context(created_event):
    return ValidationContext(
        actual_prev_event=created_event,
        actual_prev_version=1,
        actual_prev_status=OrderStatus.CREATED,
    )


@pytest.fixture
def empty_history_validation_context():
    return ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=OrderStatus.INIT,
    )