import uuid

from tests.fixtures.order_events import build_created_event


def test_order_event_create_assigns_valid_event_id():
    event = build_created_event()

    parsed_event_id = uuid.UUID(event.event_id)

    assert str(parsed_event_id) == event.event_id