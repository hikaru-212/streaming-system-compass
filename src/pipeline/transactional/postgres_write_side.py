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
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


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

    PR6 makes validation placement explicit.

    Default behavior remains:

    - ValidationMode.STRICT
    - ValidationPlacement.IN_TRANSACTION

    PRE_TRANSACTION is now supported as a separate orchestration path.
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

    def _rehydrate_aggregate_from_history(
        self,
        order_id: str,
        history: list[OrderEvent],
    ) -> OrderAggregate:
        aggregate = OrderAggregate(order_id)

        for historical_event in history:
            aggregate.apply(historical_event)

        return aggregate

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
        aggregate = self._rehydrate_aggregate_from_history(order_id, history)

        return aggregate, history

    def _build_validation_context(
        self,
        *,
        aggregate: OrderAggregate,
        actual_prev_event: Optional[OrderEvent],
    ) -> ValidationContext:
        """
        Build Compass Layer 1 validation context from accepted history.
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
        """
        if self._config.validation_placement == ValidationPlacement.IN_TRANSACTION:
            return self._execute_in_transaction_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=command_type,
                build_candidate_event=build_candidate_event,
            )

        if self._config.validation_placement == ValidationPlacement.PRE_TRANSACTION:
            return self._execute_pre_transaction_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=command_type,
                build_candidate_event=build_candidate_event,
            )

        raise NotImplementedError(
            "Unsupported validation placement: "
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
        Execute the durable write-side flow with Compass validation inside the
        PostgreSQL unit-of-work boundary.

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
                )

            if idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=idempotency_decision,
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
                )

            expected_current_version = aggregate.current_version

            # append-time admission has a physical side effect:
            # if admitted, the candidate event is appended to order_events here.
            admission_result = admission_gate.append_if_admitted(
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

    def _execute_pre_transaction_command(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
        command_type: CommandType,
        build_candidate_event: CandidateEventBuilder,
    ) -> PostgresWriteSideResult:
        """
        Execute Compass validation before entering the PostgreSQL write-side
        unit-of-work boundary.

        This path intentionally performs:

        1. preliminary idempotency check outside the write transaction
        2. accepted-history loading outside the write transaction
        3. candidate event creation and Compass validation outside the write transaction
        4. authoritative idempotency re-check inside the write transaction
        5. append-time admission inside the write transaction

        The second idempotency check and append-time admission are required
        because pre-transaction validation can become stale before append.
        """
        signature = RequestSignature(
            request_id=request_id,
            command_type=command_type,
            order_id=order_id,
            amount=amount,
        )

        read_idempotency_store = PostgresIdempotencyStore(self._connection)
        read_event_store = PostgresEventStore(self._connection)

        try:
            preliminary_idempotency_decision = read_idempotency_store.check(signature)

            if preliminary_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.REPLAY,
                    accepted_event=preliminary_idempotency_decision.record.accepted_event,
                    idempotency_decision=preliminary_idempotency_decision,
                )
            
            if preliminary_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=preliminary_idempotency_decision,
                )
            
            history = read_event_store.load(order_id)
        finally:
            # Close the implicit read transaction before CPU-side validation or return.
            # This keeps PRE_TRANSACTION validation from holding an open PostgreSQL
            # transaction while Compass validation runs.
            self._connection.rollback()
            
        aggregate = self._rehydrate_aggregate_from_history(order_id, history)
        actual_prev_event = history[-1] if history else None
        validation_context = self._build_validation_context(
            aggregate=aggregate,
            actual_prev_event=actual_prev_event,
        )

        # The candidate event is validated before the write transaction begins.
        candidate_event = build_candidate_event(aggregate)

        validation_decision = self._validation_runtime.decide(
            candidate_event,
            validation_context,
        )
        if validation_decision.action != EnforcementAction.ALLOW:
            return PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                accepted_event=None,
                idempotency_decision=preliminary_idempotency_decision,
                validation_decision=validation_decision,
            )

        expected_current_version = aggregate.current_version

        with PostgresWriteSideUnitOfWork(self._connection) as uow:
            authoritative_idempotency_decision = uow.idempotency_store.check(signature)

            if authoritative_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.REPLAY,
                    accepted_event=authoritative_idempotency_decision.record.accepted_event,
                    idempotency_decision=authoritative_idempotency_decision,
                    validation_decision=validation_decision,
                )

            if authoritative_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.CONFLICT,
                    accepted_event=None,
                    idempotency_decision=authoritative_idempotency_decision,
                    validation_decision=validation_decision,
                )

            admission_gate = self._admission_gate_factory(uow)
            stream_admission_result = admission_gate.prepare_stream(order_id)

            if not stream_admission_result.admitted:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                    accepted_event=None,
                    idempotency_decision=authoritative_idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                )

            # append-time admission has a physical side effect:
            # if admitted, the candidate event is appended to order_events here.
            admission_result = admission_gate.append_if_admitted(
                candidate_event,
                expected_current_version=expected_current_version,
            )

            if not admission_result.admitted:
                uow.rollback()
                return PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                    accepted_event=None,
                    idempotency_decision=authoritative_idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                    admission_result=admission_result,
                )

            uow.idempotency_store.record(signature, candidate_event)

            return PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ACCEPTED,
                accepted_event=candidate_event,
                idempotency_decision=authoritative_idempotency_decision,
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