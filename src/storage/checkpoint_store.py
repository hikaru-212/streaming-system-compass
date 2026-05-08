from __future__ import annotations

from typing import Protocol


class CheckpointStoreProtocol(Protocol):
    """
    Minimal checkpoint contract for the first projection runtime.

    The checkpoint tracks how far this worker has already consumed
    the accepted event stream.
    """

    def load_offset(self, worker_name: str) -> int:
        ...

    def save_offset(self, worker_name: str, offset: int) -> None:
        ...

    def clear(self) -> None:
        ...


class InMemoryCheckpointStore:
    """
    In-memory checkpoint store used for Stage 3 baseline.

    This store persists only processing progress metadata.
    It does NOT know anything about:
    - domain legality
    - projection state meaning
    - replay equivalence
    """

    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}

    def load_offset(self, worker_name: str) -> int:
        return self._offsets.get(worker_name, -1)

    def save_offset(self, worker_name: str, offset: int) -> None:
        self._offsets[worker_name] = offset

    def clear(self) -> None:
        self._offsets.clear()

    def all_offsets(self) -> dict[str, int]:
        return dict(self._offsets)