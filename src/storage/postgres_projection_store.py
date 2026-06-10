from __future__ import annotations

from decimal import Decimal

from psycopg import Connection

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.storage.projection_store import ProjectionStoreProtocol


class PostgresProjectionStore(ProjectionStoreProtocol):
    """
    PostgreSQL-backed projection state store.

    Responsibility:
    - persist derived read-side state into projection_states
    - load derived read-side state by order_id
    - clear projection state for tests / rebuild paths

    This store does NOT:
    - run the projection reducer
    - decide event sequencing policy
    - manage checkpoint progress
    - validate semantic drift
    - decide replay / rebuild orchestration

    Transaction ownership:
    - this store does not commit or rollback
    - the caller owns the transaction boundary
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def load_state(self, order_id: str) -> OrderState | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    order_id,
                    status,
                    total_amount,
                    paid_amount,
                    version
                FROM projection_states
                WHERE order_id = %s
                """,
                (order_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        (
            stored_order_id,
            status,
            total_amount,
            paid_amount,
            version,
        ) = row

        return OrderState(
            order_id=stored_order_id,
            status=OrderStatus(status),
            total_amount=Decimal(total_amount),
            paid_amount=Decimal(paid_amount),
            version=version,
        )

    def save_state(self, state: OrderState) -> None:
        """
        Save the latest derived projection state.

        In the current projection model, OrderState.version represents the
        last aggregate-local accepted event sequence reflected by this state.

        Therefore:
            projection_states.last_sequence = state.version

        This mapping should be revisited during Stage 3.5D if projection state
        later needs separate concepts such as projection_version, reducer_version,
        snapshot lineage, or projection schema version.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_states (
                    order_id,
                    status,
                    total_amount,
                    paid_amount,
                    version,
                    last_sequence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    total_amount = EXCLUDED.total_amount,
                    paid_amount = EXCLUDED.paid_amount,
                    version = EXCLUDED.version,
                    last_sequence = EXCLUDED.last_sequence,
                    updated_at = now()
                """,
                (
                    state.order_id,
                    state.status.value,
                    state.total_amount,
                    state.paid_amount,
                    state.version,
                    state.version,
                ),
            )

    def clear(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM projection_states")