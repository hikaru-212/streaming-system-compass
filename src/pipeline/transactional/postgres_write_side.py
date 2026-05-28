from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from psycopg import Connection

from src.compass.transition.runtime import ValidationRuntime
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationDecision,
)
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
    RequestSignature,
)


class PostgresWriteSideOutcome(Enum):
    """
    Result type for the PostgreSQL-backed transactional write-side flow.

    This is intentionally small for Stage 3.5B PR4.
    It is not the Stage 4 SemanticOutcome model.
    """

    ACCEPTED = "ACCEPTED"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    VALIDATION_BLOCKED = "VALIDATION_BLOCKED"


@dataclass(frozen=True)
class PostgresWriteSideResult:
    """
    Result returned by the PostgreSQL-backed transactional write-side flow.

    accepted_event:
    - present for ACCEPTED and REPLAY
    - absent for CONFLICT and VALIDATION_BLOCKED

    idempotency_decision:
    - records the durable idempotency classification used by this flow

    validation_decision:
    - present when Compass Layer 1 validation was executed
    - absent for REPLAY / CONFLICT paths because no candidate event is created
    """

    outcome: PostgresWriteSideOutcome
    accepted_event: OrderEvent | None
    idempotency_decision: IdempotencyDecision
    validation_decision: ValidationDecision | None = None


class PostgresTransactionalWriteSide:
    """
    Minimal PostgreSQL-backed transactional write-side flow.

    This class coordinates:

    - durable idempotency check
    - durable accepted-history loading
    - aggregate rehydration
    - candidate event creation through the aggregate
    - Compass Layer 1 transition-truth validation
    - accepted event append
    - idempotency result recording
    - commit / rollback through PostgresWriteSideUnitOfWork

    This is a durable Registry-like flow, but it does not yet introduce
    PostgreSQL-backed concurrency admission strategies. That boundary is
    intentionally deferred to PR5.
    """

    def __init__(
        self,
        connection: Connection,
        validation_runtime: ValidationRuntime,
    ):
        self._connection = connection
        self._validation_runtime = validation_runtime


    def _rehydrate_aggregate(
        self,
        uow: PostgresWriteSideUnitOfWork,
        order_id: str,
    ) -> tuple[OrderAggregate, list[OrderEvent]]:
        """
        Rebuild aggregate state from durable accepted history.

        This mirrors the existing in-memory Registry rule:
        replay accepted history through Aggregate.apply(event).
        """
        history = uow.event_store.load(order_id)
        aggregate = OrderAggregate(order_id)

        for historical_event in history:
            aggregate.apply(historical_event)

        return aggregate, history

    def _build_validation_context(
        self,
        *,
        aggregate: OrderAggregate,
        actual_prev_event: Optional[OrderEvent],
    ) -> ValidationContext:
        """
        Build Compass Layer 1 validation context from accepted history.

        Source of truth:
        - actual_prev_event comes from accepted history
        - actual_prev_version comes from the rehydrated aggregate
        - actual_prev_status comes from the rehydrated aggregate
        """
        return ValidationContext(
            actual_prev_event=actual_prev_event,
            actual_prev_version=aggregate.current_version,
            actual_prev_status=aggregate.status,
        )
    

    def create_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        signature = RequestSignature(
            request_id=request_id,
            command_type=CommandType.CREATE,
            order_id=order_id,
            amount=amount,
        )

        with PostgresWriteSideUnitOfWork(self._connection) as uow:
            idempotency_decision = uow.idempotency_store.check(signature)

            if idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.REPLAY,
                    accepted_event=idempotency_decision.record.accepted_event,
                    idempotency_decision=idempotency_decision,
                    validation_decision=None,
                )

            if idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    validation_decision=None,
                )

            aggregate, history = self._rehydrate_aggregate(uow, order_id)
            actual_prev_event = history[-1] if history else None
            validation_context = self._build_validation_context(
                aggregate=aggregate,
                actual_prev_event=actual_prev_event,
            )

            candidate_event = aggregate.create(request_id, amount)

            validation_decision = self._validation_runtime.decide(
                candidate_event,
                validation_context,
            )
            if validation_decision.action != EnforcementAction.ALLOW:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    validation_decision=validation_decision,
                )

            expected_current_version = aggregate.current_version

            # PR5 will replace or wrap this direct append with a PostgreSQL-backed
            # admission gate. For PR4, this keeps the durable transaction boundary
            # focused on append + idempotency atomicity.
            uow.event_store.append(
                candidate_event,
                expected_current_version=expected_current_version,
            )
            uow.idempotency_store.record(signature, candidate_event)

            return PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ACCEPTED,
                accepted_event=candidate_event,
                idempotency_decision=idempotency_decision,
                validation_decision=validation_decision,
            )

    def pay_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        signature = RequestSignature(
            request_id=request_id,
            command_type=CommandType.PAY,
            order_id=order_id,
            amount=amount,
        )

        with PostgresWriteSideUnitOfWork(self._connection) as uow:
            idempotency_decision = uow.idempotency_store.check(signature)

            if idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.REPLAY,
                    accepted_event=idempotency_decision.record.accepted_event,
                    idempotency_decision=idempotency_decision,
                    validation_decision=None,
                )

            if idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    validation_decision=None,
                )

            aggregate, history = self._rehydrate_aggregate(uow, order_id)
            actual_prev_event = history[-1] if history else None
            validation_context = self._build_validation_context(
                aggregate=aggregate,
                actual_prev_event=actual_prev_event,
            )

            candidate_event = aggregate.pay(request_id, amount)

            validation_decision = self._validation_runtime.decide(
                candidate_event,
                validation_context,
            )
            if validation_decision.action != EnforcementAction.ALLOW:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    validation_decision=validation_decision,
                )

            expected_current_version = aggregate.current_version

            # PR5 will replace or wrap this direct append with a PostgreSQL-backed
            # admission gate.
            uow.event_store.append(
                candidate_event,
                expected_current_version=expected_current_version,
            )
            uow.idempotency_store.record(signature, candidate_event)

            return PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ACCEPTED,
                accepted_event=candidate_event,
                idempotency_decision=idempotency_decision,
                validation_decision=validation_decision,
            )

