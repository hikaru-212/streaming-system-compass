from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from src.core.common.money import money_to_storage_string
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


FINGERPRINT_VERSION = 1


def build_semantic_fingerprint(signature: RequestSignature) -> str:
    """
    Build the durable semantic fingerprint for request-level idempotency.

    request_id is intentionally excluded because it is already the lookup key.

    The fingerprint represents the semantic effect of the request payload:
    - command type
    - target order
    - canonical money amount

    If the semantic basis changes later, FINGERPRINT_VERSION should advance.
    """
    return "|".join(
        [
            f"v{FINGERPRINT_VERSION}",
            signature.command_type.value,
            signature.order_id,
            money_to_storage_string(signature.amount),
        ]
    )


class PostgresIdempotencyStore:
    """
    PostgreSQL-backed request replay / conflict store.

    Responsibility:
    - classify request_id as MISS / REPLAY / CONFLICT
    - persist successful request-to-accepted-event mappings
    - preserve semantic fingerprint and fingerprint version durably

    This store does NOT decide:
    - domain legality
    - event transition truth
    - append-time concurrency admission
    - transaction orchestration across event append + idempotency record write
    """

    def __init__(self, connection: Connection):
        self._connection = connection

    def check(self, signature: RequestSignature) -> IdempotencyDecision:
        """
        Classify an incoming request against durable idempotency memory.
        """
        existing = self._load_record(signature.request_id)

        if existing is None:
            return IdempotencyDecision(
                verdict=IdempotencyVerdict.MISS,
                reason="No prior request with this request_id",
            )

        expected_fingerprint = build_semantic_fingerprint(signature)

        if (
            existing["fingerprint_version"] == FINGERPRINT_VERSION
            and existing["semantic_fingerprint"] == expected_fingerprint
        ):
            return IdempotencyDecision(
                verdict=IdempotencyVerdict.REPLAY,
                reason="Semantically identical retry detected",
                record=self._row_to_idempotency_record(existing),
            )

        return IdempotencyDecision(
            verdict=IdempotencyVerdict.CONFLICT,
            reason="Same request_id reused with different payload",
            record=self._row_to_idempotency_record(existing),
        )

    def record(self, signature: RequestSignature, accepted_event: OrderEvent) -> None:
        """
        Persist replay memory only after the request has produced an accepted event.

        Important sequencing rule:
        - do NOT record request memory before event admission succeeds
        - accepted_event_id must already exist in order_events
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO idempotency_records (
                    request_id,
                    order_id,
                    command_type,
                    amount,
                    fingerprint_version,
                    semantic_fingerprint,
                    accepted_event_id,
                    result_sequence,
                    status
                )
                VALUES (
                    %(request_id)s,
                    %(order_id)s,
                    %(command_type)s,
                    %(amount)s,
                    %(fingerprint_version)s,
                    %(semantic_fingerprint)s,
                    %(accepted_event_id)s,
                    %(result_sequence)s,
                    %(status)s
                )
                """,
                {
                    "request_id": signature.request_id,
                    "order_id": signature.order_id,
                    "command_type": signature.command_type.value,
                    "amount": Decimal(money_to_storage_string(signature.amount)),
                    "fingerprint_version": FINGERPRINT_VERSION,
                    "semantic_fingerprint": build_semantic_fingerprint(signature),
                    "accepted_event_id": accepted_event.event_id,
                    "result_sequence": accepted_event.sequence,
                    "status": "SUCCEEDED",
                },
            )

    def _load_record(self, request_id: str) -> dict[str, Any] | None:
        with self._connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    i.request_id,
                    i.order_id AS idem_order_id,
                    i.command_type,
                    i.amount AS idem_amount,
                    i.fingerprint_version,
                    i.semantic_fingerprint,
                    i.accepted_event_id,
                    i.result_sequence,
                    i.status,

                    e.accepted_event_id AS event_accepted_event_id,
                    e.order_id AS event_order_id,
                    e.sequence AS event_sequence,
                    e.event_type AS event_type,
                    e.request_id AS event_request_id,
                    e.amount AS event_amount,
                    e.occurred_at_ms,
                    e.proof_prev_event_id,
                    e.proof_prev_version,
                    e.proof_prev_status
                FROM idempotency_records i
                JOIN order_events e
                  ON i.accepted_event_id = e.accepted_event_id
                WHERE i.request_id = %(request_id)s
                """,
                {"request_id": request_id},
            )

            return cursor.fetchone()

    def _row_to_idempotency_record(self, row: dict[str, Any]) -> IdempotencyRecord:
        signature = RequestSignature(
            request_id=row["request_id"],
            command_type=CommandType(row["command_type"]),
            order_id=row["idem_order_id"],
            amount=Decimal(row["idem_amount"]),
        )

        accepted_event = OrderEvent(
            event_id=str(row["event_accepted_event_id"]),
            request_id=row["event_request_id"],
            order_id=row["event_order_id"],
            sequence=row["event_sequence"],
            event_type=EventType(row["event_type"]),
            amount=Decimal(row["event_amount"]),
            occurred_at_ms=row["occurred_at_ms"],
            proof=Proof(
                prev_event_id=(
                    str(row["proof_prev_event_id"])
                    if row["proof_prev_event_id"] is not None
                    else None
                ),
                prev_version=row["proof_prev_version"],
                prev_status=OrderStatus(row["proof_prev_status"]),
            ),
        )

        return IdempotencyRecord(
            signature=signature,
            accepted_event=accepted_event,
        )