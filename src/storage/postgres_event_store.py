from __future__ import annotations

from typing import List, Optional

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.core.order.events import OrderEvent
from src.storage.order_event_hydration import (
    ORDER_EVENT_SELECT_COLUMNS,
    row_to_order_event,
)


class PostgresEventStore:
    """
    PostgreSQL-backed accepted-history store.

    Responsibility:
    - persist accepted events into order_events
    - provide replayable event history
    - protect append-time continuity via expected_current_version

    This store does NOT decide:
    - domain legality
    - proof truth
    - idempotency replay policy
    - transaction orchestration across event + idempotency writes
    """

    def __init__(self, connection: Connection):
        self._connection = connection

    def append(self, candidate_event: OrderEvent, expected_current_version: int) -> None:
        """
        Append candidate event only if durable store continuity still matches caller expectation.

        Invariant:
        - before appending sequence N, store must currently contain exactly N-1 accepted events
        """
        current_version_in_store = self._current_version(candidate_event.order_id)

        if current_version_in_store != expected_current_version:
            raise ValueError(
                f"Version conflict: store_version={current_version_in_store}, "
                f"expected_version={expected_current_version}"
            )

        expected_new_sequence = expected_current_version + 1
        if candidate_event.sequence != expected_new_sequence:
            raise ValueError(
                f"Append-time continuity broken: expected event sequence {expected_new_sequence}, "
                f"but event contains sequence {candidate_event.sequence}"
            )

        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_events (
                    accepted_event_id,
                    order_id,
                    sequence,
                    event_type,
                    request_id,
                    amount,
                    occurred_at_ms,
                    proof_prev_event_id,
                    proof_prev_version,
                    proof_prev_status,
                    payload_json,
                    proof_json,
                    metadata_json
                )
                VALUES (
                    %(accepted_event_id)s,
                    %(order_id)s,
                    %(sequence)s,
                    %(event_type)s,
                    %(request_id)s,
                    %(amount)s,
                    %(occurred_at_ms)s,
                    %(proof_prev_event_id)s,
                    %(proof_prev_version)s,
                    %(proof_prev_status)s,
                    %(payload_json)s,
                    %(proof_json)s,
                    %(metadata_json)s
                )
                """,
                {
                    "accepted_event_id": candidate_event.event_id,
                    "order_id": candidate_event.order_id,
                    "sequence": candidate_event.sequence,
                    "event_type": candidate_event.event_type.value,
                    "request_id": candidate_event.request_id,
                    "amount": candidate_event.amount,
                    "occurred_at_ms": candidate_event.occurred_at_ms,
                    "proof_prev_event_id": candidate_event.proof.prev_event_id,
                    "proof_prev_version": candidate_event.proof.prev_version,
                    "proof_prev_status": candidate_event.proof.prev_status.value,
                    "payload_json": Jsonb({}),
                    "proof_json": Jsonb(
                        {
                            "prev_event_id": candidate_event.proof.prev_event_id,
                            "prev_version": candidate_event.proof.prev_version,
                            "prev_status": candidate_event.proof.prev_status.value,
                        }
                    ),
                    "metadata_json": Jsonb({}),
                },
            )

    def load(self, order_id: str) -> List[OrderEvent]:
        """
        Return accepted history for one aggregate stream ordered by sequence.
        """
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    {ORDER_EVENT_SELECT_COLUMNS}
                FROM order_events
                WHERE order_id = %(order_id)s
                ORDER BY sequence ASC
                """,
                {"order_id": order_id},
            )

            rows = cursor.fetchall()

        return [row_to_order_event(row) for row in rows]

    def last_event(self, order_id: str) -> Optional[OrderEvent]:
        """
        Convenience lookup for the latest accepted event in one stream.
        """
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                f"""
                SELECT
                    {ORDER_EVENT_SELECT_COLUMNS}  
                FROM order_events
                WHERE order_id = %(order_id)s
                ORDER BY sequence DESC
                LIMIT 1
                """,
                {"order_id": order_id},
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return row_to_order_event(row)

    def _current_version(self, order_id: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(sequence), 0)
                FROM order_events
                WHERE order_id = %(order_id)s
                """,
                {"order_id": order_id},
            )

            result = cursor.fetchone()

        return int(result[0])