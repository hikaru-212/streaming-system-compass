from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from psycopg.pq import TransactionStatus

from src.core.order.state import OrderState
from src.pipeline.projection.reducer import (
    build_empty_projection_state,
    reduce_order_event,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_projection_store import PostgresProjectionStore


class ReplayValidationStatus(Enum):
    """
    Minimal durable replay validation status.

    This is intentionally smaller than Stage 4 SemanticOutcome.

    It only describes whether persisted projection state matches the state
    derived by replaying accepted history through the canonical reducer.
    """

    MATCH = "MATCH"
    MISSING_PROJECTION = "MISSING_PROJECTION"
    DRIFT = "DRIFT"
    NO_ACCEPTED_HISTORY = "NO_ACCEPTED_HISTORY"


@dataclass(frozen=True)
class ReplayValidationResult:
    """
    Result of comparing replay-derived state with persisted projection state.

    expected_state:
    - state derived from accepted history through the canonical reducer

    persisted_state:
    - state loaded from projection_states

    This result does not decide recovery policy.
    It is not a Stage 4 SemanticOutcome.
    """

    order_id: str
    status: ReplayValidationStatus
    expected_state: OrderState | None
    persisted_state: OrderState | None
    reason: str

    @property
    def matched(self) -> bool:
        return self.status == ReplayValidationStatus.MATCH


class DurableReplayValidator:
    """Compare projection state with accepted replay in one PostgreSQL snapshot.

    Responsibility:
    - load accepted history for one order;
    - replay it through the canonical projection reducer;
    - compare it with persisted projection state.

    Connection and transaction ownership:
    - both PostgreSQL stores must share the exact same connection;
    - ``validate_order`` requires an idle connection and owns one explicit
      top-level repeatable-read, read-only transaction so both reads form one
      database observation.

    This validator does not mutate durable data, rebuild projection state,
    classify SemanticOutcome, or choose recovery policy.
    """

    def __init__(
        self,
        *,
        event_store: PostgresEventStore,
        projection_store: PostgresProjectionStore,
    ) -> None:
        if event_store.connection is not projection_store.connection:
            raise ValueError(
                "event_store and projection_store must share the exact "
                "validator connection"
            )
        self.event_store = event_store
        self.projection_store = projection_store
        self.connection = event_store.connection

    def validate_order(self, order_id: str) -> ReplayValidationResult:
        """Validate one order using one top-level database observation.

        ``order_id`` selects accepted history and persisted projection state.
        The returned typed result reports match, missing projection, drift, or
        no accepted history. The shared connection must be idle on entry; this
        method owns and completes the transaction. It performs no mutation,
        rebuild, fallback, or runtime-policy decision.
        """
        if self.connection.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError(
                "DurableReplayValidator.validate_order requires an idle "
                "connection so it can own a top-level transaction"
            )

        with self.connection.transaction():
            self.connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            return self._validate_order(order_id)

    def _validate_order(self, order_id: str) -> ReplayValidationResult:
        accepted_events = self.event_store.load(order_id)

        if not accepted_events:
            persisted_state = self.projection_store.load_state(order_id)

            return ReplayValidationResult(
                order_id=order_id,
                status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
                expected_state=None,
                persisted_state=persisted_state,
                reason="No accepted history exists for order",
            )

        expected_state = build_empty_projection_state(order_id)

        for event in accepted_events:
            expected_state = reduce_order_event(expected_state, event)

        persisted_state = self.projection_store.load_state(order_id)

        if persisted_state is None:
            return ReplayValidationResult(
                order_id=order_id,
                status=ReplayValidationStatus.MISSING_PROJECTION,
                expected_state=expected_state,
                persisted_state=None,
                reason="Accepted history exists but projection state is missing",
            )

        if persisted_state != expected_state:
            return ReplayValidationResult(
                order_id=order_id,
                status=ReplayValidationStatus.DRIFT,
                expected_state=expected_state,
                persisted_state=persisted_state,
                reason="Persisted projection state differs from replay-derived state",
            )

        return ReplayValidationResult(
            order_id=order_id,
            status=ReplayValidationStatus.MATCH,
            expected_state=expected_state,
            persisted_state=persisted_state,
            reason="Persisted projection state matches replay-derived state",
        )
