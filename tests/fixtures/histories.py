import pytest


@pytest.fixture
def created_history(created_event):
    return [created_event]


@pytest.fixture
def created_and_paid_history(created_event, paid_event):
    return [created_event, paid_event]