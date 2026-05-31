from __future__ import annotations

from collections.abc import Callable
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
from src.pipeline.transactional.admission import (
    AdmissionResult,
    ConcurrencyGate,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
    RequestSignature,
)


AdmissionGateFactory = Callable[[PostgresWriteSideUnitOfWork], ConcurrencyGate]
CandidateEventBuilder = Callable[[OrderAggregate], OrderEvent]


def _default_admission_gate_factory(
    uow: PostgresWriteSideUnitOfWork,
) -> ConcurrencyGate:
    return PostgresOptimisticAdmissionGate(uow.event_store)


class PostgresWriteSideOutcome(Enum):
    """
    Result type for the PostgreSQL-backed transactional write-side flow.

    This is intentionally small for Stage 3.5B.
    It is not the Stage 4 SemanticOutcome model.
    """

    ACCEPTED = "ACCEPTED"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    VALIDATION_BLOCKED = "VALIDATION_BLOCKED"
    ADMISSION_REJECTED = "ADMISSION_REJECTED"


@dataclass(frozen=True)
class PostgresWriteSideResult:
    """
    Result returned by the PostgreSQL-backed transactional write-side flow.

    accepted_event:
    - present for ACCEPTED and REPLAY
    - absent for CONFLICT, VALIDATION_BLOCKED, and ADMISSION_REJECTED

    idempotency_decision:
    - records the durable idempotency classification used by this flow

    stream_admission_result:
    - present when stream preparation was executed
    - absent for REPLAY / CONFLICT paths because replay/conflict are resolved
      before stream preparation

    validation_decision:
    - present when Compass Layer 1 validation was executed
    - absent for REPLAY / CONFLICT paths because no candidate event is created
    - absent for prepare-time ADMISSION_REJECTED because validation is not run

    admission_result:
    - present when append-time admission was executed
    - absent for REPLAY / CONFLICT / VALIDATION_BLOCKED paths
    - absent for prepare-time ADMISSION_REJECTED
    """

    outcome: PostgresWriteSideOutcome
    accepted_event: OrderEvent | None
    idempotency_decision: IdempotencyDecision
    stream_admission_result: StreamAdmissionResult | None = None
    validation_decision: ValidationDecision | None = None
    admission_result: AdmissionResult | None = None


class PostgresTransactionalWriteSide:
    """
    PostgreSQL-backed transactional write-side flow.

    This class coordinates:

    - durable idempotency check
    - stream preparation / early concurrency admission
    - durable accepted-history loading
    - aggregate rehydration
    - candidate event creation through the aggregate
    - Compass Layer 1 transition-truth validation
    - append-time PostgreSQL admission
    - idempotency result recording
    - commit / rollback through PostgresWriteSideUnitOfWork

    This is a durable Registry-like flow.

    The write-side flow does not directly own the concrete admission strategy.
    It receives an admission_gate_factory so the caller can choose:

    - optimistic admission
    - pessimistic admission
    - test fake admission

    The write side stores the factory, not a concrete gate instance. A new gate
    is built inside each unit-of-work scope so stateful gates do not leak state
    across commands or transactions.

    PR6 makes validation placement explicit.

    The default config preserves the current behavior:

    - ValidationMode.STRICT
    - ValidationPlacement.IN_TRANSACTION

    PRE_TRANSACTION is intentionally not implemented in this commit.
    """

    def __init__(
        self,
        connection: Connection,
        validation_runtime: ValidationRuntime,
        admission_gate_factory: AdmissionGateFactory | None = None,
        config: PostgresWriteSideConfig | None = None,
    ):
        self._connection = connection
        self._validation_runtime = validation_runtime
        self._admission_gate_factory = (
            admission_gate_factory or _default_admission_gate_factory
        )
        self._config = config or PostgresWriteSideConfig()

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

    def _execute_command(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
        command_type: CommandType,
        build_candidate_event: CandidateEventBuilder,
    ) -> PostgresWriteSideResult:
        """
        Dispatch command execution by validation placement.

        Commit 3 only makes the existing IN_TRANSACTION path explicit.
        PRE_TRANSACTION will be added in a later commit.
        """
        if self._config.validation_placement == ValidationPlacement.IN_TRANSACTION:
            return self._execute_in_transaction_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=command_type,
                build_candidate_event=build_candidate_event,
            )

        raise NotImplementedError(
            "Unsupported validation placement for this commit: "
            f"{self._config.validation_placement}"
        )

    def _execute_in_transaction_command(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
        command_type: CommandType,
        build_candidate_event: CandidateEventBuilder,
    ) -> PostgresWriteSideResult:
        """
        Execute the current durable write-side flow with Compass validation
        inside the PostgreSQL unit-of-work boundary.

        This is the existing Stage 3.5B PR5 behavior, now named explicitly
        as the IN_TRANSACTION validation placement path.

        Important:
        PostgresWriteSideUnitOfWork commits on a clean context-manager exit.
        Therefore, every non-accepted early return inside this method must call
        uow.rollback() before returning.
        """
        signature = RequestSignature(
            request_id=request_id,
            command_type=command_type,
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
                    stream_admission_result=None,
                    validation_decision=None,
                    admission_result=None,
                )

            if idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    stream_admission_result=None,
                    validation_decision=None,
                    admission_result=None,
                )

            admission_gate = self._admission_gate_factory(uow)

            stream_admission_result = admission_gate.prepare_stream(order_id)

            if not stream_admission_result.admitted:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=None,
                    admission_result=None,
                )

            aggregate, history = self._rehydrate_aggregate(uow, order_id)
            actual_prev_event = history[-1] if history else None
            validation_context = self._build_validation_context(
                aggregate=aggregate,
                actual_prev_event=actual_prev_event,
            )

            # The candidate event is not accepted history until validation and admission pass.
            candidate_event = build_candidate_event(aggregate)

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
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                    admission_result=None,
                )

            expected_current_version = aggregate.current_version

            # append-time admission has a physical side effect:
            # if admitted, the candidate event is appended to order_events here.
            admission_result = admission_gate.admit(
                candidate_event,
                expected_current_version=expected_current_version,
            )

            if not admission_result.admitted:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                    admission_result=admission_result,
                )

            uow.idempotency_store.record(signature, candidate_event)

            return PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ACCEPTED,
                accepted_event=candidate_event,
                idempotency_decision=idempotency_decision,
                stream_admission_result=stream_admission_result,
                validation_decision=validation_decision,
                admission_result=admission_result,
            )

    def create_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._execute_command(
            request_id=request_id,
            order_id=order_id,
            amount=amount,
            command_type=CommandType.CREATE,
            build_candidate_event=lambda aggregate: aggregate.create(
                request_id,
                amount,
            ),
        )

    def pay_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._execute_command(
            request_id=request_id,
            order_id=order_id,
            amount=amount,
            command_type=CommandType.PAY,
            build_candidate_event=lambda aggregate: aggregate.pay(
                request_id,
                amount,
            ),
        )