from __future__ import annotations

from typing import Protocol

from src.core.order.state import OrderState


class ProjectionStoreProtocol(Protocol):
    """
    Minimal read-side state store contract for the first projection runtime.

    This store owns projected state persistence only.
    It does NOT:
    - classify sequence policy
    - validate domain transition legality
    - decide checkpoint progression
    """

    def load_state(self, order_id: str) -> OrderState | None:
        ...

    def save_state(self, state: OrderState) -> None:
        ...

    def clear(self) -> None:
        ...


class InMemoryProjectionStore:
    """
    In-memory projection state store used for Stage 3 baseline.

    This is intentionally simple:
    - one current projected state per order_id
    - no buffering
    - no version conflict resolution
    - no external persistence semantics
    """

    def __init__(self) -> None:
        self._states: dict[str, OrderState] = {}

    def load_state(self, order_id: str) -> OrderState | None:
        return self._states.get(order_id)

    def save_state(self, state: OrderState) -> None:
        self._states[state.order_id] = state

    def clear(self) -> None:
        self._states.clear()

    def all_states(self) -> dict[str, OrderState]:
        return dict(self._states)
    