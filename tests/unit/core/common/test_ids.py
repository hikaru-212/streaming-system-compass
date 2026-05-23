import uuid

from src.core.common.ids import generate_event_id


def test_generate_event_id_returns_valid_uuid_string():
    event_id = generate_event_id()

    parsed_event_id = uuid.UUID(event_id)

    assert str(parsed_event_id) == event_id