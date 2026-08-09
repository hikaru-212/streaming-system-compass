from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, cast

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
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
    PostgresWriteSideExecutionTrace,
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


def _accepted_event_from_replay(
    decision: IdempotencyDecision,
) -> OrderEvent:
    """Return the accepted event required by a REPLAY idempotency decision."""
    record = decision.record
    if record is None:
        raise RuntimeError("REPLAY idempotency decision must include a record")
    return record.accepted_event


def _default_admission_gate_factory(
    uow: PostgresWriteSideUnitOfWork,
) -> ConcurrencyGate:
    """Build the default optimistic append-admission gate."""
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


_ALLOWED_EXECUTION_TERMINALS = frozenset(
    {
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.REPLAY,
            PostgresWriteSideExecutionCheckpoint
            .PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.REPLAY,
            PostgresWriteSideExecutionCheckpoint
            .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.CONFLICT,
            PostgresWriteSideExecutionCheckpoint
            .PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.CONFLICT,
            PostgresWriteSideExecutionCheckpoint
            .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.ADMISSION_REJECTED,
            PostgresWriteSideExecutionCheckpoint.CONCURRENCY_PREPARATION_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.ADMISSION_REJECTED,
            PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            PostgresWriteSideOutcome.ACCEPTED,
            PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.REPLAY,
            PostgresWriteSideExecutionCheckpoint
            .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.CONFLICT,
            PostgresWriteSideExecutionCheckpoint
            .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.ADMISSION_REJECTED,
            PostgresWriteSideExecutionCheckpoint.CONCURRENCY_PREPARATION_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.ADMISSION_REJECTED,
            PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            PostgresWriteSideOutcome.ACCEPTED,
            PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
        ),
    }
)


@dataclass(frozen=True)
class PostgresWriteSideExecution:
    """Compose one primary write result with its bounded execution topology.

    Args:
        result: Existing producer result for this normal-returning execution.
        trace: Immutable PR5 trace produced by the same write-side invocation.

    Invariants:
        The trace placement, primary outcome, and terminal checkpoint must match
        one current normal-return path. Nested idempotency, validation, stream,
        append, and accepted-event semantics remain owned by ``result``.

    Failure behavior:
        Construction rejects wrong field types and terminal combinations that
        current PRE_TRANSACTION or IN_TRANSACTION execution cannot return.

    Non-goals:
        This envelope does not reinterpret result evidence, establish transaction
        durability, relate attempts, authorize retry, select strategy, or own
        policy, timing, cost, persistence, SemanticOutcome, or DecisionReceipt.
    """

    result: PostgresWriteSideResult
    trace: PostgresWriteSideExecutionTrace

    def __post_init__(self) -> None:
        """Validate only producer-result and terminal-topology compatibility."""
        if not isinstance(self.result, PostgresWriteSideResult):
            raise TypeError("result must be PostgresWriteSideResult")
        if not isinstance(self.trace, PostgresWriteSideExecutionTrace):
            raise TypeError("trace must be PostgresWriteSideExecutionTrace")

        execution_terminal = (
            self.trace.validation_placement,
            self.result.outcome,
            self.trace.terminal_checkpoint,
        )
        if execution_terminal not in _ALLOWED_EXECUTION_TERMINALS:
            raise ValueError(
                "result outcome and trace terminal checkpoint are incompatible "
                "for validation placement"
            )


class _PostgresWriteSideTraceCollector:
    """Incrementally validate trace evidence for one write-side invocation.

    The collector is private, mutable, and invocation-local. Every recording
    operation constructs an accepted immutable PR5 trace, so duplicate, skipped,
    reordered, or wrong-placement checkpoints fail at their instrumentation
    boundary. No collector is stored on ``PostgresTransactionalWriteSide``.
    """

    def __init__(self, validation_placement: ValidationPlacement) -> None:
        self._validation_placement = validation_placement
        self._trace: PostgresWriteSideExecutionTrace | None = None

    def record(
        self,
        checkpoint: PostgresWriteSideExecutionCheckpoint,
    ) -> None:
        """Append and immediately validate one bounded execution checkpoint."""
        checkpoints = () if self._trace is None else self._trace.checkpoints
        validated_trace = PostgresWriteSideExecutionTrace(
            validation_placement=self._validation_placement,
            checkpoints=(*checkpoints, checkpoint),
        )
        self._trace = validated_trace

    @property
    def trace(self) -> PostgresWriteSideExecutionTrace:
        """Return the latest valid trace after at least one checkpoint."""
        if self._trace is None:
            raise RuntimeError("trace collector has no validated checkpoint")
        return self._trace


_PostgresWriteSideCommandResult = (
    PostgresWriteSideResult | PostgresWriteSideExecution
)


def _record_checkpoint(
    collector: _PostgresWriteSideTraceCollector | None,
    checkpoint: PostgresWriteSideExecutionCheckpoint,
) -> None:
    """Record a checkpoint only when the invocation requested traced delivery."""
    if collector is not None:
        collector.record(checkpoint)


def _finalize_result(
    result: PostgresWriteSideResult,
    collector: _PostgresWriteSideTraceCollector | None,
) -> _PostgresWriteSideCommandResult:
    """Return the legacy result or construct its traced envelope in place."""
    if collector is None:
        return result
    return PostgresWriteSideExecution(result=result, trace=collector.trace)


class PostgresTransactionalWriteSide:
    """
    PostgreSQL-backed transactional write-side flow.

    PR6 makes validation placement explicit.

    Default behavior is:

    - ValidationMode.STRICT
    - ValidationPlacement.PRE_TRANSACTION
    - PostgresOptimisticAdmissionGate

    IN_TRANSACTION remains available through explicit configuration.
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
        trace_collector: _PostgresWriteSideTraceCollector | None,
    ) -> tuple[OrderAggregate, list[OrderEvent]]:
        """
        Rebuild aggregate state from durable accepted history.

        This mirrors the existing in-memory Registry rule:
        replay accepted history through Aggregate.apply(event).
        """
        history = uow.event_store.load(order_id)
        _record_checkpoint(
            trace_collector,
            PostgresWriteSideExecutionCheckpoint.ACCEPTED_HISTORY_OBSERVED,
        )
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
        trace_collector: _PostgresWriteSideTraceCollector | None = None,
    ) -> _PostgresWriteSideCommandResult:
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
                trace_collector=trace_collector,
            )

        if self._config.validation_placement == ValidationPlacement.PRE_TRANSACTION:
            return self._execute_pre_transaction_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=command_type,
                build_candidate_event=build_candidate_event,
                trace_collector=trace_collector,
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
        trace_collector: _PostgresWriteSideTraceCollector | None,
    ) -> _PostgresWriteSideCommandResult:
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
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.BUSINESS_UOW_REACHED,
            )
            idempotency_decision = uow.idempotency_store.check(signature)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint
                .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
            )

            if idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.REPLAY,
                        accepted_event=_accepted_event_from_replay(idempotency_decision),
                        idempotency_decision=idempotency_decision,
                    ),
                    trace_collector,
                )

            if idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.CONFLICT,
                        accepted_event=None,
                        idempotency_decision=idempotency_decision,
                    ),
                    trace_collector,
                )

            admission_gate = self._admission_gate_factory(uow)
            stream_admission_result = admission_gate.prepare_stream(order_id)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint
                .CONCURRENCY_PREPARATION_RETURNED,
            )

            if not stream_admission_result.admitted:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                        accepted_event=None,
                        idempotency_decision=idempotency_decision,
                        stream_admission_result=stream_admission_result,
                    ),
                    trace_collector,
                )

            aggregate, history = self._rehydrate_aggregate(
                uow,
                order_id,
                trace_collector,
            )
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
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
            )
            if validation_decision.action != EnforcementAction.ALLOW:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                        accepted_event=None,
                        idempotency_decision=idempotency_decision,
                        stream_admission_result=stream_admission_result,
                        validation_decision=validation_decision,
                    ),
                    trace_collector,
                )

            expected_current_version = aggregate.current_version

            # append-time admission has a physical side effect:
            # if admitted, the candidate event is appended to order_events here.
            admission_result = admission_gate.append_if_admitted(
                candidate_event,
                expected_current_version=expected_current_version,
            )
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
            )

            if not admission_result.admitted:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                        accepted_event=None,
                        idempotency_decision=idempotency_decision,
                        stream_admission_result=stream_admission_result,
                        validation_decision=validation_decision,
                        admission_result=admission_result,
                    ),
                    trace_collector,
                )

            uow.idempotency_store.record(signature, candidate_event)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
            )

            return _finalize_result(
                PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ACCEPTED,
                    accepted_event=candidate_event,
                    idempotency_decision=idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                    admission_result=admission_result,
                ),
                trace_collector,
            )

        raise RuntimeError(
            "IN_TRANSACTION write-side flow exited without returning a result"
        )

    def _execute_pre_transaction_command(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
        command_type: CommandType,
        build_candidate_event: CandidateEventBuilder,
        trace_collector: _PostgresWriteSideTraceCollector | None,
    ) -> _PostgresWriteSideCommandResult:
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
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint
                .PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
            )

            if preliminary_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.REPLAY,
                        accepted_event=_accepted_event_from_replay(
                            preliminary_idempotency_decision
                        ),
                        idempotency_decision=preliminary_idempotency_decision,
                    ),
                    trace_collector,
                )

            if preliminary_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.CONFLICT,
                        accepted_event=None,
                        idempotency_decision=preliminary_idempotency_decision,
                    ),
                    trace_collector,
                )

            history = read_event_store.load(order_id)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.ACCEPTED_HISTORY_OBSERVED,
            )
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
        _record_checkpoint(
            trace_collector,
            PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
        )
        if validation_decision.action != EnforcementAction.ALLOW:
            return _finalize_result(
                PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                    accepted_event=None,
                    idempotency_decision=preliminary_idempotency_decision,
                    validation_decision=validation_decision,
                ),
                trace_collector,
            )

        expected_current_version = aggregate.current_version

        with PostgresWriteSideUnitOfWork(self._connection) as uow:
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.BUSINESS_UOW_REACHED,
            )
            authoritative_idempotency_decision = uow.idempotency_store.check(signature)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint
                .AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
            )

            if authoritative_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.REPLAY,
                        accepted_event=_accepted_event_from_replay(
                            authoritative_idempotency_decision
                        ),
                        idempotency_decision=authoritative_idempotency_decision,
                        validation_decision=validation_decision,
                    ),
                    trace_collector,
                )

            if authoritative_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.CONFLICT,
                        accepted_event=None,
                        idempotency_decision=authoritative_idempotency_decision,
                        validation_decision=validation_decision,
                    ),
                    trace_collector,
                )

            admission_gate = self._admission_gate_factory(uow)
            stream_admission_result = admission_gate.prepare_stream(order_id)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint
                .CONCURRENCY_PREPARATION_RETURNED,
            )

            if not stream_admission_result.admitted:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                        accepted_event=None,
                        idempotency_decision=authoritative_idempotency_decision,
                        stream_admission_result=stream_admission_result,
                        validation_decision=validation_decision,
                    ),
                    trace_collector,
                )

            # append-time admission has a physical side effect:
            # if admitted, the candidate event is appended to order_events here.
            admission_result = admission_gate.append_if_admitted(
                candidate_event,
                expected_current_version=expected_current_version,
            )
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
            )

            if not admission_result.admitted:
                uow.rollback()
                return _finalize_result(
                    PostgresWriteSideResult(
                        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                        accepted_event=None,
                        idempotency_decision=authoritative_idempotency_decision,
                        stream_admission_result=stream_admission_result,
                        validation_decision=validation_decision,
                        admission_result=admission_result,
                    ),
                    trace_collector,
                )

            uow.idempotency_store.record(signature, candidate_event)
            _record_checkpoint(
                trace_collector,
                PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
            )

            return _finalize_result(
                PostgresWriteSideResult(
                    outcome=PostgresWriteSideOutcome.ACCEPTED,
                    accepted_event=candidate_event,
                    idempotency_decision=authoritative_idempotency_decision,
                    stream_admission_result=stream_admission_result,
                    validation_decision=validation_decision,
                    admission_result=admission_result,
                ),
                trace_collector,
            )

        raise RuntimeError(
            "PRE_TRANSACTION write-side flow exited without returning a result"
        )

    def create_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        """Execute CREATE and return the existing primary producer result.

        The legacy API creates no trace collector or execution envelope. Current
        result values, transaction behavior, and exception propagation remain
        unchanged.
        """
        return cast(
            PostgresWriteSideResult,
            self._execute_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=CommandType.CREATE,
                build_candidate_event=lambda aggregate: aggregate.create(
                    request_id,
                    amount,
                ),
            ),
        )

    def create_order_with_trace(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideExecution:
        """Execute CREATE and return its primary result with bounded topology.

        The invocation uses one private collector for the writer's actual
        validation placement. Normal accepted execution constructs the immutable
        trace and envelope inside the business UOW before clean context exit and
        commit. Existing exceptions continue to propagate without guaranteed
        traced delivery.
        """
        trace_collector = _PostgresWriteSideTraceCollector(
            self._config.validation_placement
        )
        return cast(
            PostgresWriteSideExecution,
            self._execute_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=CommandType.CREATE,
                build_candidate_event=lambda aggregate: aggregate.create(
                    request_id,
                    amount,
                ),
                trace_collector=trace_collector,
            ),
        )

    def pay_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        """Execute PAY and return the existing primary producer result.

        The legacy API creates no trace collector or execution envelope. Current
        result values, transaction behavior, and exception propagation remain
        unchanged.
        """
        return cast(
            PostgresWriteSideResult,
            self._execute_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=CommandType.PAY,
                build_candidate_event=lambda aggregate: aggregate.pay(
                    request_id,
                    amount,
                ),
            ),
        )

    def pay_order_with_trace(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideExecution:
        """Execute PAY and return its primary result with bounded topology.

        The invocation uses one private collector for the writer's actual
        validation placement. Normal accepted execution constructs the immutable
        trace and envelope inside the business UOW before clean context exit and
        commit. Existing exceptions continue to propagate without guaranteed
        traced delivery.
        """
        trace_collector = _PostgresWriteSideTraceCollector(
            self._config.validation_placement
        )
        return cast(
            PostgresWriteSideExecution,
            self._execute_command(
                request_id=request_id,
                order_id=order_id,
                amount=amount,
                command_type=CommandType.PAY,
                build_candidate_event=lambda aggregate: aggregate.pay(
                    request_id,
                    amount,
                ),
                trace_collector=trace_collector,
            ),
        )
