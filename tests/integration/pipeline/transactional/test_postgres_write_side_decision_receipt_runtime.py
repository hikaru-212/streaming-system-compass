from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.bootstrap.build_postgres_write_side_decision_receipt_runtime import (
    build_postgres_write_side_decision_receipt_runtime,
)
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.enums import CommandType
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_runtime_owner as runtime_owner,
)
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.storage.decision_receipt_store import (
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
    DecisionReceiptTransactionDurability,
    DecisionReceiptTransactionFailureCategory,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")

TEST_ONLY_RECEIPT_TIMEOUT_MS = 5000
PROVENANCE = DecisionReceiptMaterializationProvenance.LIVE_RESULT
PostgresWriteSideDecisionReceiptPersistenceEligibility = (
    runtime_owner.PostgresWriteSideDecisionReceiptPersistenceEligibility
)
PostgresWriteSideDecisionReceiptRuntimeDelivery = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeDelivery
)
PostgresWriteSideDecisionReceiptRuntimeOwner = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeOwner
)
PostgresWriteSideDecisionReceiptRuntimeStatus = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeStatus
)


class _CleanReceiptConnectionFactory:
    """Supply idle dedicated test connections and retain identity evidence."""

    def __init__(
        self,
        connection_factory: Callable[[], Connection[object]],
    ) -> None:
        self._connection_factory = connection_factory
        self.connections: list[Connection[object]] = []
        self.backend_pids: list[int] = []
        self.entry_statuses: list[TransactionStatus] = []

    def __call__(self) -> Connection[object]:
        connection = self._connection_factory()
        if connection.info.transaction_status is TransactionStatus.INTRANS:
            connection.rollback()
        status = connection.info.transaction_status
        assert status is TransactionStatus.IDLE
        self.connections.append(connection)
        self.backend_pids.append(connection.info.backend_pid)
        self.entry_statuses.append(status)
        return connection


class _AutocommitReceiptConnectionFactory(
    _CleanReceiptConnectionFactory
):
    """Prevent receipt entry through the real owner's autocommit guard."""

    def __call__(self) -> Connection[object]:
        connection = super().__call__()
        connection.autocommit = True
        return connection


class _BlockingValidationRuntime:
    """Produce one deterministic validation block before business append."""

    def decide(self, candidate_event, context) -> ValidationDecision:
        return ValidationDecision(
            action=EnforcementAction.BLOCK,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason=(
                    "Integration validation blocked the candidate event."
                ),
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={
                    "actual_prev_version": context.actual_prev_version,
                },
            ),
        )


class _CompetingAppendGate:
    """Commit one real competitor before the retained real append attempt."""

    def __init__(
        self,
        *,
        event_store: PostgresEventStore,
        competing_write: Callable[[], PostgresWriteSideResult],
        competing_results: list[PostgresWriteSideResult],
    ) -> None:
        self._delegate = PostgresOptimisticAdmissionGate(event_store)
        self._competing_write = competing_write
        self._competing_results = competing_results
        self._append_entered = False

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return self._delegate.prepare_stream(order_id)

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        if self._append_entered:
            raise AssertionError("competing append injection must run once")
        self._append_entered = True
        competing_result = self._competing_write()
        assert competing_result.outcome is PostgresWriteSideOutcome.ACCEPTED
        self._competing_results.append(competing_result)
        return self._delegate.append_if_admitted(
            candidate_event,
            expected_current_version,
        )


class _CompetingAppendGateFactory:
    """Build the bounded real-gate concurrency seam for one invocation."""

    def __init__(
        self,
        competing_write: Callable[[], PostgresWriteSideResult],
    ) -> None:
        self._competing_write = competing_write
        self.competing_results: list[PostgresWriteSideResult] = []
        self.gates: list[_CompetingAppendGate] = []

    def __call__(
        self,
        uow: PostgresWriteSideUnitOfWork,
    ) -> _CompetingAppendGate:
        gate = _CompetingAppendGate(
            event_store=uow.event_store,
            competing_write=self._competing_write,
            competing_results=self.competing_results,
        )
        self.gates.append(gate)
        return gate


def _validation_runtime() -> ValidationRuntime:
    return ValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=FullProofValidator(),
            off_validator=NoOpValidator(),
        ),
        policy=ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )


def _signature(
    *,
    prefix: str,
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    suffix = uuid4()
    return RequestSignature(
        request_id=f"{prefix}-request-{suffix}",
        command_type=CommandType.CREATE,
        order_id=f"{prefix}-order-{suffix}",
        amount=amount,
    )


def _runtime(
    *,
    signature: RequestSignature,
    business_connection: Connection[object],
    receipt_connection_factory: Callable[[], Connection[object]],
    validation_runtime: ValidationRuntime | None = None,
    admission_gate_factory=None,
    write_side_config: PostgresWriteSideConfig | None = None,
) -> PostgresWriteSideDecisionReceiptRuntimeOwner:
    return build_postgres_write_side_decision_receipt_runtime(
        request_signature=signature,
        business_connection=business_connection,
        validation_runtime=(validation_runtime or _validation_runtime()),
        receipt_connection_factory=receipt_connection_factory,
        receipt_idle_in_transaction_session_timeout_ms=(
            TEST_ONLY_RECEIPT_TIMEOUT_MS
        ),
        admission_gate_factory=admission_gate_factory,
        write_side_config=write_side_config,
    )


def _persistence_result(
    delivery: PostgresWriteSideDecisionReceiptRuntimeDelivery,
):
    persistence_delivery = delivery.persistence_delivery
    assert persistence_delivery is not None
    persistence_result = persistence_delivery.persistence_result
    assert persistence_result is not None
    return persistence_result


def _receipt(delivery: PostgresWriteSideDecisionReceiptRuntimeDelivery):
    persistence_delivery = delivery.persistence_delivery
    assert persistence_delivery is not None
    receipt = persistence_delivery.materialization_delivery.receipt
    assert receipt is not None
    return receipt


def _verify_accepted_business_state(
    connection: Connection[object],
    *,
    signature: RequestSignature,
    result: PostgresWriteSideResult,
) -> None:
    accepted_event = result.accepted_event
    assert accepted_event is not None
    history = PostgresEventStore(connection).load(signature.order_id)
    assert len(history) == 1
    assert history[0].event_id == accepted_event.event_id
    idempotency = PostgresIdempotencyStore(connection).check(signature)
    assert idempotency.verdict is IdempotencyVerdict.REPLAY
    assert idempotency.record is not None
    assert idempotency.record.accepted_event.event_id == (
        accepted_event.event_id
    )


def _pessimistic_gate_factory(
    uow: PostgresWriteSideUnitOfWork,
) -> PostgresPessimisticAdmissionGate:
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def test_real_accepted_runtime_commits_business_and_one_cached_receipt(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    signature = _signature(prefix="pr3-runtime-accepted")
    governance_factory = _CleanReceiptConnectionFactory(
        db_connection_factory
    )
    business_backend_pid = db_connection.info.backend_pid
    runtime = _runtime(
        signature=signature,
        business_connection=db_connection,
        receipt_connection_factory=governance_factory,
    )

    completion = runtime.invoke_initial()
    business_result = completion.business_result

    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert business_result.accepted_event is not None
    assert db_connection.info.transaction_status is TransactionStatus.IDLE
    assert governance_factory.connections == []

    before_receipt = db_connection_factory()
    try:
        _verify_accepted_business_state(
            before_receipt,
            signature=signature,
            result=business_result,
        )
        assert count_rows(before_receipt, "decision_receipts") == 0
    finally:
        before_receipt.rollback()
        before_receipt.close()

    first = completion.compose_receipt()
    second = completion.compose_receipt()

    assert second is first
    assert first.business_result is business_result
    assert first.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_COMPLETED
    )
    persistence_result = _persistence_result(first)
    assert persistence_result.durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    receipt = _receipt(first)
    assert len(governance_factory.connections) == 1
    assert governance_factory.connections[0] is not db_connection
    assert governance_factory.backend_pids[0] != business_backend_pid
    assert governance_factory.entry_statuses == [TransactionStatus.IDLE]
    assert governance_factory.connections[0].closed
    assert not db_connection.closed

    verification = db_connection_factory()
    try:
        _verify_accepted_business_state(
            verification,
            signature=signature,
            result=business_result,
        )
        assert count_rows(verification, "decision_receipts") == 1
        stored = PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(receipt.receipt_id)
        assert stored is not None
        assert stored.receipt == receipt
        assert stored.materialization_provenance is PROVENANCE
        assert stored.receipt.correlation.request_id == signature.request_id
        assert stored.receipt.correlation.order_id == signature.order_id
        assert stored.receipt.correlation.accepted_event_id == UUID(
            business_result.accepted_event.event_id
        )
    finally:
        verification.rollback()
        verification.close()


def test_real_validation_block_persists_receipt_without_business_effect(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    signature = _signature(prefix="pr3-runtime-blocked")
    governance_factory = _CleanReceiptConnectionFactory(
        db_connection_factory
    )
    runtime = _runtime(
        signature=signature,
        business_connection=db_connection,
        receipt_connection_factory=governance_factory,
        validation_runtime=cast(
            ValidationRuntime,
            _BlockingValidationRuntime(),
        ),
    )

    completion = runtime.invoke_initial()
    business_result = completion.business_result
    delivery = completion.compose_receipt()

    assert business_result.outcome is (
        PostgresWriteSideOutcome.VALIDATION_BLOCKED
    )
    assert business_result.accepted_event is None
    assert delivery.business_result is business_result
    assert delivery.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_COMPLETED
    )
    assert _persistence_result(delivery).durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    receipt = _receipt(delivery)
    assert governance_factory.connections[0] is not db_connection

    verification = db_connection_factory()
    try:
        assert PostgresEventStore(verification).load(signature.order_id) == []
        assert PostgresIdempotencyStore(verification).check(
            signature
        ).verdict is IdempotencyVerdict.MISS
        assert count_rows(verification, "order_events") == 0
        assert count_rows(verification, "idempotency_records") == 0
        assert count_rows(verification, "decision_receipts") == 1
        stored = PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(receipt.receipt_id)
        assert stored is not None
        assert stored.receipt == receipt
        assert stored.receipt.correlation.accepted_event_id is None
        assert stored.materialization_provenance is PROVENANCE
    finally:
        verification.rollback()
        verification.close()


def test_real_append_stale_result_fails_closed_without_receipt_row(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    signature = _signature(prefix="pr3-runtime-stale")
    competitor_connection = db_connection_factory()
    if competitor_connection.info.transaction_status is (
        TransactionStatus.INTRANS
    ):
        competitor_connection.rollback()
    competitor_writer = PostgresTransactionalWriteSide(
        connection=competitor_connection,
        validation_runtime=_validation_runtime(),
    )

    def competing_write() -> PostgresWriteSideResult:
        return competitor_writer.create_order(
            request_id=f"competitor-{uuid4()}",
            order_id=signature.order_id,
            amount=signature.amount,
        )

    gate_factory = _CompetingAppendGateFactory(competing_write)
    governance_factory = _CleanReceiptConnectionFactory(
        db_connection_factory
    )
    runtime = _runtime(
        signature=signature,
        business_connection=db_connection,
        receipt_connection_factory=governance_factory,
        admission_gate_factory=gate_factory,
    )

    try:
        completion = runtime.invoke_initial()
    finally:
        competitor_connection.close()
    business_result = completion.business_result
    delivery = completion.compose_receipt()

    assert len(gate_factory.gates) == 1
    assert len(gate_factory.competing_results) == 1
    assert business_result.outcome is (
        PostgresWriteSideOutcome.ADMISSION_REJECTED
    )
    assert business_result.admission_result is not None
    assert business_result.admission_result.verdict is (
        AdmissionVerdict.STALE_WRITE
    )
    append_evidence = (
        business_result.admission_result.append_version_mismatch_evidence
    )
    assert append_evidence is not None
    assert completion.persistence_eligibility is (
        PostgresWriteSideDecisionReceiptPersistenceEligibility.INELIGIBLE
    )
    assert delivery.business_result is business_result
    assert delivery.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_INELIGIBLE
    )
    assert delivery.persistence_delivery is None
    assert governance_factory.connections == []

    verification = db_connection_factory()
    try:
        assert count_rows(verification, "order_events") == 1
        assert count_rows(verification, "idempotency_records") == 1
        assert count_rows(verification, "decision_receipts") == 0
    finally:
        verification.rollback()
        verification.close()


def test_real_receipt_entry_failure_preserves_committed_business_state(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    signature = _signature(prefix="pr3-runtime-receipt-failure")
    governance_factory = _AutocommitReceiptConnectionFactory(
        db_connection_factory
    )
    runtime = _runtime(
        signature=signature,
        business_connection=db_connection,
        receipt_connection_factory=governance_factory,
    )

    completion = runtime.invoke_initial()
    business_result = completion.business_result
    delivery = completion.compose_receipt()

    assert business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert delivery.business_result is business_result
    assert delivery.status is (
        PostgresWriteSideDecisionReceiptRuntimeStatus.PERSISTENCE_COMPLETED
    )
    persistence_result = _persistence_result(delivery)
    assert persistence_result.durability is (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )
    assert persistence_result.failure_category is (
        DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
    )
    assert governance_factory.connections[0] is not db_connection
    assert governance_factory.connections[0].closed
    assert not db_connection.closed

    verification = db_connection_factory()
    try:
        _verify_accepted_business_state(
            verification,
            signature=signature,
            result=business_result,
        )
        assert count_rows(verification, "order_events") == 1
        assert count_rows(verification, "idempotency_records") == 1
        assert count_rows(verification, "decision_receipts") == 0
    finally:
        verification.rollback()
        verification.close()


def test_existing_real_lock_timeout_a1_and_accepted_a2_keep_two_receipts(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    signature = _signature(prefix="pr3-runtime-a1-a2")
    governance_factory = _CleanReceiptConnectionFactory(
        db_connection_factory
    )
    runtime = _runtime(
        signature=signature,
        business_connection=db_connection,
        receipt_connection_factory=governance_factory,
        admission_gate_factory=_pessimistic_gate_factory,
        write_side_config=PostgresWriteSideConfig(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
        ),
    )
    lock_holder = db_connection_factory()
    if lock_holder.info.transaction_status is TransactionStatus.INTRANS:
        lock_holder.rollback()
    holder_gate = PostgresPessimisticAdmissionGate(
        connection=lock_holder,
        event_store=PostgresEventStore(lock_holder),
    )

    try:
        holder_result = holder_gate.prepare_stream(signature.order_id)
        assert holder_result.verdict is AdmissionVerdict.ADMITTED
        a1 = runtime.invoke_initial()
        a1_delivery = a1.compose_receipt()
    finally:
        lock_holder.rollback()
        lock_holder.close()

    authority = runtime.evaluate_reinvocation_authority()
    a2 = runtime.invoke_authorized_reinvocation()
    a2_delivery = a2.compose_receipt()

    assert isinstance(authority, ReinvocationAuthorization)
    assert a1 is runtime.initial_completion
    assert a2 is runtime.authorized_reinvocation_completion
    assert a2 is not a1
    assert a1.business_result.outcome is (
        PostgresWriteSideOutcome.ADMISSION_REJECTED
    )
    assert a1.business_result.stream_admission_result is not None
    assert a1.business_result.stream_admission_result.verdict is (
        AdmissionVerdict.LOCK_TIMEOUT
    )
    assert a2.business_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert _persistence_result(a1_delivery).durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    assert _persistence_result(a2_delivery).durability is (
        DecisionReceiptTransactionDurability.COMMITTED
    )
    a1_receipt = _receipt(a1_delivery)
    a2_receipt = _receipt(a2_delivery)
    assert a1_receipt.receipt_id != a2_receipt.receipt_id
    assert a1_receipt.outcome_id != a2_receipt.outcome_id
    assert a1_receipt.correlation.accepted_event_id is None
    assert a2.business_result.accepted_event is not None
    assert a2_receipt.correlation.accepted_event_id == UUID(
        a2.business_result.accepted_event.event_id
    )
    assert a1.compose_receipt() is a1_delivery
    assert a2.compose_receipt() is a2_delivery
    assert len(governance_factory.connections) == 2
    assert all(
        connection is not db_connection
        for connection in governance_factory.connections
    )

    verification = db_connection_factory()
    try:
        _verify_accepted_business_state(
            verification,
            signature=signature,
            result=a2.business_result,
        )
        assert count_rows(verification, "decision_receipts") == 2
        assert PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(a1_receipt.receipt_id) is not None
        assert PostgresDecisionReceiptStore(
            verification
        ).load_by_receipt_id(a2_receipt.receipt_id) is not None
    finally:
        verification.rollback()
        verification.close()
