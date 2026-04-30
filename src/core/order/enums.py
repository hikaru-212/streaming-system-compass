from enum import Enum


class EventType(Enum):
    """
    Domain event vocabulary for the minimal v1 write-side model.

    Current v1 scope:
    - CREATED
    - PAID

    This enum answers:
    - what kind of accepted fact this event represents

    It does NOT answer:
    - whether the event is legal
    - whether the event truthfully follows accepted history
    """
    CREATED = "created"
    PAID = "paid"


class OrderStatus(Enum):
    """
    Domain state vocabulary for the current minimal order lifecycle.

    Current v1 scope:
    INIT -> CREATED -> PAID

    Important:
    - status meaning belongs to the domain specification
    - status legality is enforced by the aggregate
    """
    INIT = "init"
    CREATED = "created"
    PAID = "paid"


class CommandType(Enum):
    """
    Request / command identity category used by orchestration.

    Why this exists:
    - idempotency is request-based, not status-based
    - CREATE and PAY are different business actions
    - the same request_id reused across different command semantics
      should not be treated as a safe replay
    """
    CREATE = "create"
    PAY = "pay"