# pyright: reportArgumentType=false, reportReturnType=false
"""Test-only composition of existing write-side, mapper, and receipt owner.

The harness owns invocation order, fixture identity allocation, provenance
selection, and separate observation of business and governance results. Those
test responsibilities do not select their future production owner or implement
automatic materialization, failure policy, retry, or reconciliation.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.compass.runtime.decision_receipt import DecisionReceipt
from src.compass.runtime.write_side_decision_receipt_mapping import (
    map_postgres_write_side_result_to_decision_receipt,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
    ValidationContext,
)
from src.core.order.enums import CommandType, OrderStatus
from src.core.order.events import OrderEvent
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
)
from src.storage.idempotency_store import (
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_decision_receipt_store import (
    PostgresDecisionReceiptStore,
)
from src.storage.postgres_decision_receipt_transaction_owner import (
    DecisionReceiptConnectionDisposition,
    DecisionReceiptRollbackDisposition,
    DecisionReceiptTransactionDurability,
    DecisionReceiptTransactionFailureCategory,
    PostgresDecisionReceiptConnectionFactory,
    PostgresDecisionReceiptTransactionOwner,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


pytestmark = pytest.mark.usefixtures("clean_database")

# Test-fixture value only; this is not a production timeout recommendation.
TEST_ONLY_IDLE_OWNER_TIMEOUT_MS = 5000
PROVENANCE = DecisionReceiptMaterializationProvenance.LIVE_RESULT


def acquire_clean_test_connection(
    connection_factory: Callable[[], Connection[object]],
) -> Connection[object]:
    """End the shared fixture's database-name guard transaction."""
    connection = connection_factory()
    if connection.info.transaction_status is TransactionStatus.INTRANS:
        connection.rollback()
    assert connection.info.transaction_status is TransactionStatus.IDLE
    return connection


def _status_value(status: OrderStatus | None) -> str | None:
    return status.value if status is not None else None


class AllowingValidationRuntime:
    """Return source-consistent allowing evidence for the real write side."""

    def decide(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> ValidationDecision:
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="Integration harness allowed the candidate event.",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                    "actual_prev_status": _status_value(
                        context.actual_prev_status
                    ),
                },
            ),
        )


class BlockingValidationRuntime:
    """Return source-consistent blocking evidence for the optional live path."""

    def decide(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> ValidationDecision:
        return ValidationDecision(
            action=EnforcementAction.BLOCK,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="Integration harness blocked the candidate event.",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                    "actual_prev_status": _status_value(
                        context.actual_prev_status
                    ),
                },
            ),
        )


class CapturingGovernanceConnectionFactory:
    """Acquire clean dedicated governance connections and capture identity."""

    def __init__(
        self,
        connection_factory: Callable[[], Connection[object]],
    ) -> None:
        self._connection_factory = connection_factory
        self.connections: list[Connection[object]] = []
        self.backend_pids: list[int] = []
        self.entry_statuses: list[TransactionStatus] = []

    def __call__(self) -> Connection[object]:
        connection = acquire_clean_test_connection(self._connection_factory)
        assert connection.autocommit is False
        status = connection.info.transaction_status
        self.connections.append(connection)
        self.backend_pids.append(connection.info.backend_pid)
        self.entry_statuses.append(status)
        return connection


class InjectedReceiptStoreFailure(RuntimeError):
    """Mark a test-harness failure injected after a real receipt INSERT."""


class InsertThenRaiseStore:
    """Delegate a real INSERT, retain its evidence, then inject failure."""

    def __init__(
        self,
        store: PostgresDecisionReceiptStore,
        observed_results: list[DecisionReceiptInsertResult],
    ) -> None:
        self._store = store
        self._observed_results = observed_results

    def insert(
        self,
        receipt: DecisionReceipt,
        *,
        materialization_provenance: DecisionReceiptMaterializationProvenance,
    ) -> DecisionReceiptInsertResult:
        result = self._store.insert(
            receipt,
            materialization_provenance=materialization_provenance,
        )
        self._observed_results.append(result)
        raise InjectedReceiptStoreFailure(
            "failure injected after real receipt INSERT"
        )


class InsertThenRaiseOwner(PostgresDecisionReceiptTransactionOwner):
    """Inject failure only through the owner's protected construction seam."""

    def __init__(
        self,
        connection_factory: PostgresDecisionReceiptConnectionFactory,
    ) -> None:
        super().__init__(
            connection_factory,
            idle_in_transaction_session_timeout_ms=(
                TEST_ONLY_IDLE_OWNER_TIMEOUT_MS
            ),
        )
        self.observed_results: list[DecisionReceiptInsertResult] = []

    def _build_store(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptStore:
        return cast(
            PostgresDecisionReceiptStore,
            InsertThenRaiseStore(
                PostgresDecisionReceiptStore(connection),
                self.observed_results,
            ),
        )


def build_write_side(
    connection: Connection[object],
    *,
    validation_runtime: AllowingValidationRuntime | BlockingValidationRuntime,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,  # type: ignore[arg-type]
    )


def map_with_test_harness_identity(
    result: PostgresWriteSideResult,
) -> DecisionReceipt:
    """Allocate executable fixture identity without selecting production policy."""
    return map_postgres_write_side_result_to_decision_receipt(
        receipt_id=uuid4(),
        outcome_id=uuid4(),
        result=result,
    )


def verify_accepted_business_state(
    connection: Connection[object],
    *,
    order_id: str,
    request_id: str,
    amount: Decimal,
    accepted_event_id: str,
) -> None:
    history = PostgresEventStore(connection).load(order_id)
    assert len(history) == 1
    assert history[0].event_id == accepted_event_id
    decision = PostgresIdempotencyStore(connection).check(
        RequestSignature(
            request_id=request_id,
            command_type=CommandType.CREATE,
            order_id=order_id,
            amount=amount,
        )
    )
    assert decision.verdict is IdempotencyVerdict.REPLAY
    assert decision.record is not None
    assert decision.record.accepted_event.event_id == accepted_event_id


def test_accepted_write_side_result_maps_and_commits_on_separate_connection(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Compose production components without introducing an orchestrator."""
    order_id = f"order-composition-{uuid4()}"
    request_id = f"request-composition-{uuid4()}"
    amount = Decimal("100.00")
    business_connection = db_connection
    business_backend_pid = business_connection.info.backend_pid
    assert business_connection.info.transaction_status is TransactionStatus.IDLE
    write_side = build_write_side(
        business_connection,
        validation_runtime=AllowingValidationRuntime(),
    )

    business_result = write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=amount,
    )

    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert business_result.accepted_event is not None
    assert business_connection.info.transaction_status is TransactionStatus.IDLE
    original_business_result = business_result
    receipt = map_with_test_harness_identity(business_result)
    governance_factory = CapturingGovernanceConnectionFactory(
        db_connection_factory
    )
    owner = PostgresDecisionReceiptTransactionOwner(
        governance_factory,
        idle_in_transaction_session_timeout_ms=(
            TEST_ONLY_IDLE_OWNER_TIMEOUT_MS
        ),
    )

    receipt_result = owner.persist(
        receipt,
        materialization_provenance=PROVENANCE,
    )

    assert receipt_result.durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    assert receipt_result.statement_result is not None
    assert receipt_result.statement_result.status is (
        DecisionReceiptInsertStatus.INSERTED
    )
    assert len(governance_factory.connections) == 1
    governance_connection = governance_factory.connections[0]
    assert governance_connection is not business_connection
    assert governance_factory.backend_pids[0] != business_backend_pid
    assert governance_factory.entry_statuses == [TransactionStatus.IDLE]
    assert governance_connection.closed
    assert not business_connection.closed
    assert business_connection.info.transaction_status is TransactionStatus.IDLE
    assert business_result is original_business_result
    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED

    verification = db_connection_factory()
    try:
        verify_accepted_business_state(
            verification,
            order_id=order_id,
            request_id=request_id,
            amount=amount,
            accepted_event_id=business_result.accepted_event.event_id,
        )
        stored = PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(receipt.receipt_id)
        assert stored == receipt_result.statement_result.record
        assert stored is not None
        assert stored.receipt == receipt
        assert stored.materialization_provenance is PROVENANCE
    finally:
        verification.rollback()
        verification.close()


def test_receipt_rollback_does_not_rewrite_accepted_business_truth(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Business commit is real; injected receipt failure rolls back separately."""
    order_id = f"order-composition-failure-{uuid4()}"
    request_id = f"request-composition-failure-{uuid4()}"
    amount = Decimal("125.00")
    business_connection = db_connection
    business_backend_pid = business_connection.info.backend_pid
    write_side = build_write_side(
        business_connection,
        validation_runtime=AllowingValidationRuntime(),
    )

    business_result = write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=amount,
    )

    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert business_result.accepted_event is not None
    assert business_connection.info.transaction_status is TransactionStatus.IDLE
    original_business_result = business_result
    receipt = map_with_test_harness_identity(business_result)
    governance_factory = CapturingGovernanceConnectionFactory(
        db_connection_factory
    )
    owner = InsertThenRaiseOwner(governance_factory)

    receipt_result = owner.persist(
        receipt,
        materialization_provenance=PROVENANCE,
    )

    assert owner.observed_results[0].status is (
        DecisionReceiptInsertStatus.INSERTED
    )
    assert receipt_result.durability is (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )
    assert receipt_result.failure_category is (
        DecisionReceiptTransactionFailureCategory.STORE_OPERATION_FAILED
    )
    assert receipt_result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert receipt_result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert governance_factory.connections[0] is not business_connection
    assert governance_factory.backend_pids[0] != business_backend_pid
    assert governance_factory.connections[0].closed
    assert business_result is original_business_result
    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED

    verification = db_connection_factory()
    try:
        verify_accepted_business_state(
            verification,
            order_id=order_id,
            request_id=request_id,
            amount=amount,
            accepted_event_id=business_result.accepted_event.event_id,
        )
        assert (
            PostgresDecisionReceiptStore(
                verification
            ).load_by_receipt_id(receipt.receipt_id)
            is None
        )
    finally:
        verification.rollback()
        verification.close()


def test_validation_blocked_result_can_use_same_separate_governance_owner(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Exercise an already-supported typed non-ACCEPTED mapper composition."""
    order_id = f"order-composition-blocked-{uuid4()}"
    request_id = f"request-composition-blocked-{uuid4()}"
    amount = Decimal("75.00")
    business_connection = db_connection
    business_backend_pid = business_connection.info.backend_pid
    write_side = build_write_side(
        business_connection,
        validation_runtime=BlockingValidationRuntime(),
    )

    business_result = write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=amount,
    )

    assert business_result.outcome is (
        PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )
    assert business_result.accepted_event is None
    assert business_connection.info.transaction_status is TransactionStatus.IDLE
    original_business_result = business_result
    receipt = map_with_test_harness_identity(business_result)
    governance_factory = CapturingGovernanceConnectionFactory(
        db_connection_factory
    )
    owner = PostgresDecisionReceiptTransactionOwner(
        governance_factory,
        idle_in_transaction_session_timeout_ms=(
            TEST_ONLY_IDLE_OWNER_TIMEOUT_MS
        ),
    )

    receipt_result = owner.persist(
        receipt,
        materialization_provenance=PROVENANCE,
    )

    assert receipt_result.durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    assert receipt_result.statement_result is not None
    assert receipt_result.statement_result.status is (
        DecisionReceiptInsertStatus.INSERTED
    )
    assert governance_factory.connections[0] is not business_connection
    assert governance_factory.backend_pids[0] != business_backend_pid
    assert governance_factory.connections[0].closed
    assert business_result is original_business_result
    assert business_result.outcome is (
        PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )

    verification = db_connection_factory()
    try:
        assert PostgresEventStore(verification).load(order_id) == []
        idempotency = PostgresIdempotencyStore(verification).check(
            RequestSignature(
                request_id=request_id,
                command_type=CommandType.CREATE,
                order_id=order_id,
                amount=amount,
            )
        )
        assert idempotency.verdict is IdempotencyVerdict.MISS
        stored = PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(receipt.receipt_id)
        assert stored == receipt_result.statement_result.record
        assert stored is not None
        assert stored.receipt == receipt
    finally:
        verification.rollback()
        verification.close()
