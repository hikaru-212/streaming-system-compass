from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import Any, cast
from datetime import datetime, timezone
from inspect import getdoc, signature
from typing import cast
from uuid import UUID

import pytest
from psycopg import Connection
from psycopg.errors import IdleInTransactionSessionTimeout
from psycopg.pq import TransactionStatus

import src.storage.postgres_decision_receipt_transaction_owner as owner_module
from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptEvidenceSource,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptConflictCategory,
    DecisionReceiptConflictError,
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
    PersistedDecisionReceipt,
)
from src.storage.postgres_decision_receipt_store import (
    PostgresDecisionReceiptStore,
)
from src.storage.postgres_decision_receipt_transaction_owner import (
    DecisionReceiptCleanupFailureCategory,
    DecisionReceiptConnectionDisposition,
    DecisionReceiptRollbackDisposition,
    DecisionReceiptTransactionDurability,
    DecisionReceiptTransactionFailureCategory,
    PostgresDecisionReceiptConnectionFactory,
    PostgresDecisionReceiptTransactionOwner,
    PostgresDecisionReceiptTransactionResult,
)


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000901")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000902")
MATERIALIZED_AT = datetime(2026, 8, 5, tzinfo=timezone.utc)
PROVENANCE = DecisionReceiptMaterializationProvenance.LIVE_RESULT


class SentinelDatabaseError(RuntimeError):
    def __init__(self, *, sqlstate: str | None = None) -> None:
        super().__init__("sentinel database failure")
        self.sqlstate = sqlstate


class FakeConnectionInfo:
    def __init__(
        self,
        events: list[str],
        transaction_status: TransactionStatus,
        *,
        status_error: Exception | None = None,
    ) -> None:
        self._events = events
        self._transaction_status = transaction_status
        self._status_error = status_error

    @property
    def transaction_status(self) -> TransactionStatus:
        self._events.append("transaction_status")
        if self._status_error is not None:
            raise self._status_error
        return self._transaction_status


class FakeConnection:
    def __init__(
        self,
        events: list[str],
        *,
        autocommit: bool = False,
        transaction_status: TransactionStatus = TransactionStatus.IDLE,
        autocommit_error: Exception | None = None,
        status_error: Exception | None = None,
        timeout_error: Exception | None = None,
        commit_error: Exception | None = None,
        rollback_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.events = events
        self._autocommit = autocommit
        self._autocommit_error = autocommit_error
        self.info = FakeConnectionInfo(
            events,
            transaction_status,
            status_error=status_error,
        )
        self.timeout_error = timeout_error
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.closed = False
        self.broken = False
        self.timeout_parameters: tuple[str] | None = None
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    @property
    def autocommit(self) -> bool:
        self.events.append("autocommit")
        if self._autocommit_error is not None:
            raise self._autocommit_error
        return self._autocommit

    def execute(self, query: str, parameters: tuple[str]) -> None:
        assert "idle_in_transaction_session_timeout" in query
        assert "set_config" in query
        assert "true" in query
        self.timeout_parameters = parameters
        self.events.append(f"timeout:{parameters[0]}")
        if self.timeout_error is not None:
            raise self.timeout_error

    def commit(self) -> None:
        self.commit_calls += 1
        self.events.append("commit")
        if self.commit_error is not None:
            if isinstance(
                self.commit_error,
                IdleInTransactionSessionTimeout,
            ):
                self.closed = True
                self.broken = True
            raise self.commit_error

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.events.append("rollback")
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self) -> None:
        self.close_calls += 1
        self.events.append("close")
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeConnectionFactory:
    def __init__(
        self,
        events: list[str],
        connection: FakeConnection | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.connection = connection
        self.error = error
        self.calls = 0

    def __call__(self) -> Connection[object]:
        self.calls += 1
        self.events.append("factory")
        if self.error is not None:
            raise self.error
        assert self.connection is not None
        return cast(Connection[object], self.connection)


class FakeStore:
    def __init__(
        self,
        events: list[str],
        *,
        result: DecisionReceiptInsertResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.result = result
        self.error = error
        self.calls = 0

    def insert(
        self,
        receipt: DecisionReceipt,
        *,
        materialization_provenance: DecisionReceiptMaterializationProvenance,
    ) -> DecisionReceiptInsertResult:
        self.calls += 1
        self.events.append("insert")
        assert receipt == make_receipt()
        assert materialization_provenance is PROVENANCE
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class TransactionOwnerUnderTest(PostgresDecisionReceiptTransactionOwner):
    def __init__(
        self,
        connection_factory: PostgresDecisionReceiptConnectionFactory,
        store: FakeStore,
        *,
        idle_in_transaction_session_timeout_ms: int = 3000,
    ) -> None:
        super().__init__(
            connection_factory,
            idle_in_transaction_session_timeout_ms=(
                idle_in_transaction_session_timeout_ms
            ),
        )
        self._fake_store = store

    def _build_store(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptStore:
        del connection
        self._fake_store.events.append("build_store")
        return cast(PostgresDecisionReceiptStore, self._fake_store)


def make_receipt() -> DecisionReceipt:
    return DecisionReceipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        ok=True,
        boundary=SemanticBoundary.RUNTIME_GOVERNANCE,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
        reason="Runtime evidence is semantically valid.",
        evidence_source=DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    )


def make_statement_result(
    status: DecisionReceiptInsertStatus,
) -> DecisionReceiptInsertResult:
    return DecisionReceiptInsertResult(
        status=status,
        record=PersistedDecisionReceipt(
            receipt=make_receipt(),
            receipt_serialization_version=1,
            materialization_provenance=PROVENANCE,
            materialized_at=MATERIALIZED_AT,
        ),
    )


def make_conflict_error() -> DecisionReceiptConflictError:
    return DecisionReceiptConflictError(
        category=DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT,
        receipt_id=RECEIPT_ID,
    )


def build_owner(
    connection: FakeConnection,
    store: FakeStore,
    events: list[str],
) -> PostgresDecisionReceiptTransactionOwner:
    factory = FakeConnectionFactory(events, connection)
    return TransactionOwnerUnderTest(factory, store)


def persist(
    owner: PostgresDecisionReceiptTransactionOwner,
) -> PostgresDecisionReceiptTransactionResult:
    return owner.persist(
        make_receipt(),
        materialization_provenance=PROVENANCE,
    )


def test_positive_integer_timeout_is_accepted_without_acquisition() -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(events)

    PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=1,
    )

    assert factory.calls == 0
    assert events == []


def test_non_callable_connection_factory_is_rejected() -> None:
    with pytest.raises(TypeError, match="connection_factory must be callable"):
        PostgresDecisionReceiptTransactionOwner(
            cast(PostgresDecisionReceiptConnectionFactory, object()),
            idle_in_transaction_session_timeout_ms=3000,
        )


@pytest.mark.parametrize("invalid_timeout", [0, -1])
def test_non_positive_timeout_is_rejected_before_factory_invocation(
    invalid_timeout: int,
) -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(events)

    with pytest.raises(ValueError, match="greater than zero"):
        PostgresDecisionReceiptTransactionOwner(
            factory,
            idle_in_transaction_session_timeout_ms=invalid_timeout,
        )

    assert factory.calls == 0
    assert events == []


@pytest.mark.parametrize("invalid_timeout", [True, False, 1.5, "3000"])
def test_non_integer_timeout_is_rejected_before_factory_invocation(
    invalid_timeout: object,
) -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(events)

    with pytest.raises(TypeError, match="must be int"):
        PostgresDecisionReceiptTransactionOwner(
            factory,
            idle_in_transaction_session_timeout_ms=(
                invalid_timeout  # type: ignore[arg-type]
            ),
        )

    assert factory.calls == 0
    assert events == []


def test_invalid_receipt_is_rejected_before_factory_invocation() -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(events)
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=3000,
    )

    with pytest.raises(TypeError, match="receipt must be DecisionReceipt"):
        owner.persist(
            object(),  # type: ignore[arg-type]
            materialization_provenance=PROVENANCE,
        )

    assert factory.calls == 0
    assert events == []


def test_invalid_provenance_is_rejected_before_factory_invocation() -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(events)
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=3000,
    )

    with pytest.raises(TypeError, match="materialization_provenance must be"):
        owner.persist(
            make_receipt(),
            materialization_provenance=object(),  # type: ignore[arg-type]
        )

    assert factory.calls == 0
    assert events == []


def test_acquisition_failure_returns_typed_non_committed_evidence() -> None:
    events: list[str] = []
    factory = FakeConnectionFactory(
        events,
        error=SentinelDatabaseError(sqlstate="08001"),
    )
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=3000,
    )

    result = persist(owner)

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.CONNECTION_ACQUISITION_FAILED
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    )
    assert result.connection_disposition is None
    assert result.sqlstate == "08001"
    assert events == ["factory"]


def test_autocommit_connection_fails_closed_before_transaction_work() -> None:
    events: list[str] = []
    connection = FakeConnection(events, autocommit=True)
    store = FakeStore(events)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert connection.close_calls == 1
    assert connection.rollback_calls == 0
    assert store.calls == 0
    assert events == ["factory", "autocommit", "close"]


def test_non_idle_connection_is_discarded_before_transaction_work() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        transaction_status=TransactionStatus.INTRANS,
    )
    store = FakeStore(events)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.TRANSACTION_NOT_IDLE
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert connection.close_calls == 1
    assert connection.rollback_calls == 0
    assert store.calls == 0
    assert events == ["factory", "autocommit", "transaction_status", "close"]


def test_connection_state_inspection_failure_discards_connection() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        status_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events)

    result = persist(build_owner(connection, store, events))

    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.CONNECTION_STATE_UNAVAILABLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert result.sqlstate == "08006"
    assert connection.close_calls == 1
    assert store.calls == 0


def test_autocommit_inspection_failure_discards_connection() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        autocommit_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.CONNECTION_STATE_UNAVAILABLE
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert result.sqlstate == "08006"
    assert connection.close_calls == 1
    assert connection.rollback_calls == 0
    assert store.calls == 0
    assert events == ["factory", "autocommit", "close"]


def test_successful_operation_order_is_exact() -> None:
    events: list[str] = []
    connection = FakeConnection(events)
    store = FakeStore(
        events,
        result=make_statement_result(DecisionReceiptInsertStatus.INSERTED),
    )

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert connection.timeout_parameters == ("3000ms",)
    assert events == [
        "factory",
        "autocommit",
        "transaction_status",
        "timeout:3000ms",
        "build_store",
        "insert",
        "commit",
        "close",
    ]


def test_inserted_becomes_committed_only_after_commit_acknowledgement() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.INSERTED
    )
    connection = FakeConnection(events)
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert result.statement_result is statement_result
    assert result.failure_category is None
    assert result.conflict_error is None
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert events.index("commit") > events.index("insert")
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def test_already_present_commits_without_conflict_classification() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.ALREADY_PRESENT
    )
    connection = FakeConnection(events)
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert result.statement_result is statement_result
    assert result.failure_category is None
    assert result.conflict_error is None
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0


def test_timeout_configuration_failure_rolls_back_without_store_call() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        timeout_error=SentinelDatabaseError(sqlstate="22023"),
    )
    store = FakeStore(events)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.TIMEOUT_CONFIGURATION_FAILED
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert result.sqlstate == "22023"
    assert store.calls == 0
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert events[-2:] == ["rollback", "close"]


def test_ordinary_store_failure_rolls_back_and_closes() -> None:
    events: list[str] = []
    connection = FakeConnection(events)
    store = FakeStore(
        events,
        error=SentinelDatabaseError(sqlstate="XX000"),
    )

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.STORE_OPERATION_FAILED
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert result.statement_result is None
    assert result.sqlstate == "XX000"
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_typed_conflict_evidence_is_preserved_without_policy_fields() -> None:
    events: list[str] = []
    conflict = make_conflict_error()
    connection = FakeConnection(events)
    store = FakeStore(events, error=conflict)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.CONFLICT
    )

    conflict_error = result.conflict_error

    assert conflict_error is not None
    assert conflict_error.category is (
        DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    result_fields = {item.name for item in fields(result)}
    for forbidden_field in (
        "semantic_outcome",
        "semantic_validity",
        "retry_candidate",
        "retry_authorized",
        "operator_action",
        "fallback",
    ):
        assert forbidden_field not in result_fields


def test_rollback_failure_remains_not_committed_and_discards() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        rollback_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events, error=SentinelDatabaseError())

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.rollback_disposition is DecisionReceiptRollbackDisposition.FAILED
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert result.cleanup_failures == (
        DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
    )
    assert result.sqlstate == "08006"
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_close_failure_after_precommit_rollback_preserves_not_committed() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        close_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events, error=SentinelDatabaseError(sqlstate="XX000"))

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.STORE_OPERATION_FAILED
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED
    )
    assert result.cleanup_failures == (
        DecisionReceiptCleanupFailureCategory.CONNECTION_CLOSE_FAILED,
    )
    assert result.sqlstate == "XX000"
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_rollback_and_close_failure_preserve_both_cleanup_categories() -> None:
    events: list[str] = []
    connection = FakeConnection(
        events,
        rollback_error=SentinelDatabaseError(sqlstate="08006"),
        close_error=SentinelDatabaseError(sqlstate="08003"),
    )
    store = FakeStore(events, error=SentinelDatabaseError(sqlstate="XX000"))

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.rollback_disposition is DecisionReceiptRollbackDisposition.FAILED
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED
    )
    assert result.cleanup_failures == (
        DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
        DecisionReceiptCleanupFailureCategory.CONNECTION_CLOSE_FAILED,
    )
    assert result.sqlstate == "XX000"
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_generic_commit_exception_is_unknown_and_discards() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.INSERTED
    )
    connection = FakeConnection(
        events,
        commit_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.UNKNOWN
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
    )
    assert result.statement_result is statement_result
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert result.sqlstate == "08006"
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def test_characterized_idle_owner_timeout_overrides_commit_ambiguity() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.INSERTED
    )
    timeout_error = IdleInTransactionSessionTimeout("owner timed out")
    connection = FakeConnection(events, commit_error=timeout_error)
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert timeout_error.sqlstate == "25P03"
    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
    )
    assert result.statement_result is statement_result
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert result.sqlstate == "25P03"
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def test_idle_owner_timeout_is_also_recognized_by_sqlstate() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.INSERTED
    )
    connection = FakeConnection(
        events,
        commit_error=SentinelDatabaseError(sqlstate="25P03"),
    )
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.NOT_COMMITTED
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
    )
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert connection.rollback_calls == 0


def test_close_failure_after_commit_preserves_committed_durability() -> None:
    events: list[str] = []
    statement_result = make_statement_result(
        DecisionReceiptInsertStatus.INSERTED
    )
    connection = FakeConnection(
        events,
        close_error=SentinelDatabaseError(sqlstate="08006"),
    )
    store = FakeStore(events, result=statement_result)

    result = persist(build_owner(connection, store, events))

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert result.statement_result is statement_result
    assert result.failure_category is None
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED
    )
    assert result.cleanup_failures == (
        DecisionReceiptCleanupFailureCategory.CONNECTION_CLOSE_FAILED,
    )
    assert result.sqlstate == "08006"
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def make_transaction_result(
    **values: object,
) -> PostgresDecisionReceiptTransactionResult:
    kwargs = cast(dict[str, Any], values)
    return PostgresDecisionReceiptTransactionResult(**kwargs)


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="committed-closed",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.ALREADY_PRESENT
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="committed-close-failed",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.UNKNOWN,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="unknown-discarded",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.UNKNOWN,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="unknown-close-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_ACQUISITION_FAILED
                ),
            },
            id="acquisition-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="autocommit-closed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="autocommit-close-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .TRANSACTION_NOT_IDLE
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="transaction-not-idle-discarded",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_STATE_UNAVAILABLE
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="connection-state-close-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .TIMEOUT_CONFIGURATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="timeout-configuration-rolled-back",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.FAILED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .TIMEOUT_CONFIGURATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
                ),
            },
            id="timeout-configuration-rollback-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="store-failed-close-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.FAILED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="store-rollback-and-close-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.CONFLICT
                ),
                "conflict_error": make_conflict_error(),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="conflict-rolled-back",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.FAILED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.CONFLICT
                ),
                "conflict_error": make_conflict_error(),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
                ),
            },
            id="conflict-rollback-failed",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="idle-owner-timeout-before-statement-evidence",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="idle-owner-timeout-after-statement-close-failed",
        ),
    ],
)
def test_every_owner_emitted_result_shape_is_constructible(
    values: dict[str, object],
) -> None:
    make_transaction_result(**values)


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="committed-without-statement",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="committed-with-failure-category",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "conflict_error": make_conflict_error(),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="committed-with-conflict-evidence",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
            },
            id="committed-without-connection-disposition",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.UNKNOWN,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="unknown-without-statement",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.UNKNOWN,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="unknown-with-non-commit-failure",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_ACQUISITION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="acquisition-failure-with-connection-disposition",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.CONFLICT
                ),
                "conflict_error": make_conflict_error(),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="conflict-with-statement-evidence",
        ),
        pytest.param(
            {
                "durability": DecisionReceiptTransactionDurability.COMMITTED,
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                "statement_result": make_statement_result(
                    DecisionReceiptInsertStatus.INSERTED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory.CONFLICT
                ),
                "conflict_error": make_conflict_error(),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
            },
            id="conflict-with-committed-durability",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.FAILED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            },
            id="rollback-failed-without-cleanup-evidence",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
                ),
            },
            id="rollback-cleanup-without-failed-disposition",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLEANUP_FAILED
                ),
            },
            id="cleanup-failed-without-close-evidence",
        ),
        pytest.param(
            {
                "durability": (
                    DecisionReceiptTransactionDurability.NOT_COMMITTED
                ),
                "rollback_disposition": (
                    DecisionReceiptRollbackDisposition.CONFIRMED
                ),
                "failure_category": (
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
                "connection_disposition": (
                    DecisionReceiptConnectionDisposition.CLOSED
                ),
                "cleanup_failures": (
                    DecisionReceiptCleanupFailureCategory
                    .CONNECTION_CLOSE_FAILED,
                ),
            },
            id="close-evidence-without-cleanup-failed-disposition",
        ),
    ],
)
def test_contradictory_public_result_shapes_are_rejected(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        make_transaction_result(**values)


def test_result_is_frozen_and_public_fields_are_exact() -> None:
    result = PostgresDecisionReceiptTransactionResult(
        durability=DecisionReceiptTransactionDurability.COMMITTED,
        rollback_disposition=DecisionReceiptRollbackDisposition.NOT_REQUIRED,
        statement_result=make_statement_result(
            DecisionReceiptInsertStatus.INSERTED
        ),
        connection_disposition=DecisionReceiptConnectionDisposition.CLOSED,
    )

    assert [item.name for item in fields(result)] == [
        "durability",
        "rollback_disposition",
        "statement_result",
        "failure_category",
        "conflict_error",
        "connection_disposition",
        "sqlstate",
        "cleanup_failures",
    ]
    with pytest.raises(FrozenInstanceError):
        result.durability = (  # type: ignore[misc]
            DecisionReceiptTransactionDurability.UNKNOWN
        )


def test_public_api_requires_factory_and_does_not_accept_connection_on_persist(
) -> None:
    assert list(signature(PostgresDecisionReceiptTransactionOwner).parameters) == [
        "connection_factory",
        "idle_in_transaction_session_timeout_ms",
    ]
    assert list(
        signature(PostgresDecisionReceiptTransactionOwner.persist).parameters
    ) == ["self", "receipt", "materialization_provenance"]
    assert (
        signature(PostgresDecisionReceiptTransactionOwner.persist)
        .parameters["materialization_provenance"]
        .kind.name
        == "KEYWORD_ONLY"
    )
    assert "connection" not in signature(
        PostgresDecisionReceiptTransactionOwner.persist
    ).parameters


def test_public_surface_and_docstrings_are_complete() -> None:
    assert owner_module.__all__ == [
        "PostgresDecisionReceiptConnectionFactory",
        "DecisionReceiptTransactionDurability",
        "DecisionReceiptRollbackDisposition",
        "DecisionReceiptConnectionDisposition",
        "DecisionReceiptTransactionFailureCategory",
        "DecisionReceiptCleanupFailureCategory",
        "PostgresDecisionReceiptTransactionResult",
        "PostgresDecisionReceiptTransactionOwner",
    ]
    public_objects = [
        PostgresDecisionReceiptConnectionFactory,
        PostgresDecisionReceiptConnectionFactory.__call__,
        DecisionReceiptTransactionDurability,
        DecisionReceiptRollbackDisposition,
        DecisionReceiptConnectionDisposition,
        DecisionReceiptTransactionFailureCategory,
        DecisionReceiptCleanupFailureCategory,
        PostgresDecisionReceiptTransactionResult,
        PostgresDecisionReceiptTransactionOwner,
        PostgresDecisionReceiptTransactionOwner.__init__,
        PostgresDecisionReceiptTransactionOwner.persist,
    ]

    for public_object in public_objects:
        docstring = getdoc(public_object)
        assert docstring is not None
        assert len(docstring.split()) >= 8


def test_owner_module_does_not_import_forbidden_orchestration_authorities() -> None:
    for forbidden_name in (
        "SemanticOutcome",
        "DecisionReceiptMapper",
        "DiagnosticTrace",
        "ResolutionTrace",
        "AttemptLog",
        "RetryPolicy",
        "AcceptedEventPostgresUnitOfWork",
    ):
        assert forbidden_name not in owner_module.__dict__
