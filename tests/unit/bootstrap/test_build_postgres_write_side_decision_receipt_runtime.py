from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from psycopg import Connection

from src.bootstrap import (
    build_postgres_write_side_decision_receipt_runtime as builder,
)
from src.compass.transition.runtime import (
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import ValidationMode
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.enums import CommandType
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
)
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_runtime_owner as runtime_owner,
)
from src.storage.idempotency_store import RequestSignature
from src.storage.postgres_decision_receipt_transaction_owner import (
    PostgresDecisionReceiptTransactionOwner,
)


RECEIPT_TIMEOUT_MS = 5000
PostgresWriteSideDecisionReceiptRuntimeOwner = (
    runtime_owner.PostgresWriteSideDecisionReceiptRuntimeOwner
)


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="bootstrap-decision-receipt-request",
        command_type=CommandType.CREATE,
        order_id="bootstrap-decision-receipt-order",
        amount=Decimal("100.00"),
    )


def _validation_runtime() -> ValidationRuntime:
    return ValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=FullProofValidator(),
            off_validator=NoOpValidator(),
        ),
        policy=ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )


def test_builder_constructs_real_postgres_runtime_graph_without_connecting(
) -> None:
    business_connection = cast(Connection[object], object())
    receipt_connection = cast(Connection[object], object())
    receipt_factory_calls = 0

    def receipt_connection_factory() -> Connection[object]:
        nonlocal receipt_factory_calls
        receipt_factory_calls += 1
        return receipt_connection

    runtime = builder.build_postgres_write_side_decision_receipt_runtime(
        request_signature=_signature(),
        business_connection=business_connection,
        validation_runtime=_validation_runtime(),
        receipt_connection_factory=receipt_connection_factory,
        receipt_idle_in_transaction_session_timeout_ms=RECEIPT_TIMEOUT_MS,
    )

    assert isinstance(
        runtime,
        PostgresWriteSideDecisionReceiptRuntimeOwner,
    )
    invocation_owner = runtime.__dict__["_invocation_owner"]
    writer = invocation_owner.__dict__["_writer"]
    receipt_owner = runtime.__dict__["_receipt_transaction_owner"]
    assert isinstance(writer, PostgresTransactionalWriteSide)
    assert writer.__dict__["_connection"] is business_connection
    assert isinstance(
        receipt_owner,
        PostgresDecisionReceiptTransactionOwner,
    )
    assert receipt_owner.__dict__[
        "_idle_in_transaction_session_timeout_ms"
    ] == RECEIPT_TIMEOUT_MS
    assert receipt_factory_calls == 0

    acquired = receipt_owner.__dict__["_connection_factory"]()

    assert acquired is receipt_connection
    assert acquired is not business_connection
    assert receipt_factory_calls == 1


def test_builder_guard_rejects_business_connection_as_governance_connection(
) -> None:
    business_connection = cast(Connection[object], object())
    runtime = builder.build_postgres_write_side_decision_receipt_runtime(
        request_signature=_signature(),
        business_connection=business_connection,
        validation_runtime=_validation_runtime(),
        receipt_connection_factory=lambda: business_connection,
        receipt_idle_in_transaction_session_timeout_ms=RECEIPT_TIMEOUT_MS,
    )
    receipt_owner = runtime.__dict__["_receipt_transaction_owner"]

    with pytest.raises(
        RuntimeError,
        match="returned the business connection",
    ):
        receipt_owner.__dict__["_connection_factory"]()


def test_builder_rejects_non_callable_receipt_factory() -> None:
    with pytest.raises(
        TypeError,
        match="receipt_connection_factory must be callable",
    ):
        builder.build_postgres_write_side_decision_receipt_runtime(
            request_signature=_signature(),
            business_connection=cast(Connection[object], object()),
            validation_runtime=_validation_runtime(),
            receipt_connection_factory=cast(object, None),
            receipt_idle_in_transaction_session_timeout_ms=RECEIPT_TIMEOUT_MS,
        )


def test_builder_has_no_in_memory_runtime_dependency() -> None:
    for forbidden_name in (
        "EventStore",
        "IdempotencyProvider",
        "OptimisticVersionGate",
        "OrderRegistry",
    ):
        assert forbidden_name not in builder.__dict__
