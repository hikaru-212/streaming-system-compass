from typing import List, Optional

from src.core.order.events import OrderEvent


class EventStore:
    """
    In-memory accepted-history store.

    Storage shape:
        order_id -> [event1, event2, event3, ...]

    Responsibility:
    - persist accepted events
    - provide replayable event history
    - protect append-time continuity via expected_current_version

    This store does NOT decide:
    - domain legality
    - proof truth
    - idempotency replay policy
    """

    def __init__(self):
        self.events_by_order_id = {}

    def append(self, candidate_event: OrderEvent, expected_current_version: int) -> None:
        """
        Append candidate event only if store continuity still matches caller expectation.

        Invariant:
        - before appending sequence N, store must currently contain exactly N-1 accepted events

        Why this matters:
        - this is the persistence-side optimistic admission guard
        - stale writers must be rejected here
        """
        order_id = candidate_event.order_id

        if order_id in self.events_by_order_id:
            event_stream = self.events_by_order_id[order_id]
        else:
            event_stream = []
            self.events_by_order_id[order_id] = event_stream

        current_version_in_store = len(event_stream)
        
        # Concurrency Gate: prevent Stale write
        if current_version_in_store != expected_current_version:
            raise ValueError(
                f"Version conflict: store_version={current_version_in_store}, "
                f"expected_version={expected_current_version}"
            )

        # Continuity Gate:
        expected_new_sequence = expected_current_version + 1
        if candidate_event.sequence != expected_new_sequence:
            raise ValueError(
                f"Append-time continuity broken: expected event sequence {expected_new_sequence}, "
                f"but event contains sequence {candidate_event.sequence}"
            )

        event_stream.append(candidate_event)

    def load(self, order_id: str) -> List[OrderEvent]:
        """
        Return accepted history for one aggregate stream.

        Replay rule:
        - callers should treat returned events as the durable source of truth
        - mutation of history itself must not happen through this method
        """
        if order_id in self.events_by_order_id:
            return list(self.events_by_order_id[order_id])
        return []

    def last_event(self, order_id: str) -> Optional[OrderEvent]:
        """
        Convenience lookup for the latest accepted event in one stream.
        """
        history = self.load(order_id)
        if history:
            return history[-1]
        return None