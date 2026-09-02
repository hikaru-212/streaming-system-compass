"""Build the PostgreSQL write-side runtime with DecisionReceipt custody."""

from __future__ import annotations

from psycopg import Connection

from src.compass.transition.runtime import ValidationRuntime
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_runtime_owner,
)
from src.pipeline.transactional.postgres_write_side import (
    AdmissionGateFactory,
    PostgresTransactionalWriteSide,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
)
from src.storage.idempotency_store import RequestSignature
from src.storage.postgres_decision_receipt_transaction_owner import (
    PostgresDecisionReceiptConnectionFactory,
    PostgresDecisionReceiptTransactionOwner,
)


__all__ = ("build_postgres_write_side_decision_receipt_runtime",)

PostgresWriteSideDecisionReceiptRuntimeOwner = (
    postgres_write_side_decision_receipt_runtime_owner
    .PostgresWriteSideDecisionReceiptRuntimeOwner
)


def build_postgres_write_side_decision_receipt_runtime(
    *,
    request_signature: RequestSignature,
    business_connection: Connection[object],
    validation_runtime: ValidationRuntime,
    receipt_connection_factory: PostgresDecisionReceiptConnectionFactory,
    receipt_idle_in_transaction_session_timeout_ms: int,
    admission_gate_factory: AdmissionGateFactory | None = None,
    write_side_config: PostgresWriteSideConfig | None = None,
) -> PostgresWriteSideDecisionReceiptRuntimeOwner:
    """Build one canonical live PostgreSQL invocation-and-receipt runtime.

    Args:
        request_signature: Complete request identity retained by the resulting
            invocation owner for A1 and any Stage 4E-authorized A2.
        business_connection: Caller-owned PostgreSQL connection used only by
            the transactional business writer and its existing UOW.
        validation_runtime: Existing Compass validation runtime supplied to the
            PostgreSQL writer.
        receipt_connection_factory: Purpose-specific factory that supplies a
            fresh, idle governance connection to each receipt persistence
            operation.
        receipt_idle_in_transaction_session_timeout_ms: Mandatory positive
            receipt-transaction idle-owner timeout passed unchanged to the
            existing transaction owner.
        admission_gate_factory: Optional existing write-side admission factory.
        write_side_config: Optional existing PostgreSQL writer configuration.

    Returns:
        One ``PostgresWriteSideDecisionReceiptRuntimeOwner`` that privately
        retains the real PostgreSQL writer and receipt transaction owner.

    Transaction ownership:
        The business connection is retained only by
        ``PostgresTransactionalWriteSide``. Receipt persistence is reached only
        through ``PostgresDecisionReceiptTransactionOwner``, whose guarded
        factory must return a different connection object. That owner creates
        the real ``PostgresDecisionReceiptStore`` only after a completed handle
        explicitly enters ``compose_receipt``.

    Failure behavior:
        Existing constructor validation propagates. A non-callable receipt
        factory is rejected here before the guarded wrapper can hide it.
        If the factory later returns the exact business connection, the receipt
        transaction owner reports its existing connection-acquisition failure
        result; the business connection is neither entered nor closed by the
        receipt path.

    Non-goals:
        This builder does not open the business connection, read environment
        variables, invoke a request, compose a receipt automatically, share a
        transaction, select semantic policy, create an outbox, reconcile
        history, or establish process-independent uniqueness.
    """

    if not callable(receipt_connection_factory):
        raise TypeError("receipt_connection_factory must be callable")

    writer = PostgresTransactionalWriteSide(
        connection=business_connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=admission_gate_factory,
        config=write_side_config,
    )

    def acquire_dedicated_receipt_connection() -> Connection[object]:
        """Acquire governance ownership without accepting business reuse."""

        connection = receipt_connection_factory()
        if connection is business_connection:
            raise RuntimeError(
                "receipt_connection_factory returned the business connection"
            )
        return connection

    receipt_transaction_owner = PostgresDecisionReceiptTransactionOwner(
        acquire_dedicated_receipt_connection,
        idle_in_transaction_session_timeout_ms=(
            receipt_idle_in_transaction_session_timeout_ms
        ),
    )
    return PostgresWriteSideDecisionReceiptRuntimeOwner(
        request_signature=request_signature,
        writer=writer,
        receipt_transaction_owner=receipt_transaction_owner,
    )
