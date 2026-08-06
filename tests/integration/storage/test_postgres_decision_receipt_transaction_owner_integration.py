# pyright: reportArgumentType=false, reportReturnType=false
from __future__ import annotations

from collections.abc import Callable
from typing import cast
from dataclasses import replace
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

import pytest
from psycopg import Connection
from psycopg.pq import TransactionStatus

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptEvidenceSource,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
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
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
    PersistedDecisionReceipt,
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
    PostgresDecisionReceiptTransactionResult,
)


pytestmark = pytest.mark.usefixtures("clean_database")

# Test-fixture value matching the characterized experiment, not a production
# timeout recommendation.
TEST_ONLY_IDLE_OWNER_TIMEOUT_MS = 5000
OWNER_THREAD_TIMEOUT_SECONDS = 20.0
POLL_TIMEOUT_SECONDS = 5.0
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


class InjectedStoreFailure(RuntimeError):
    """Mark deterministic failure injected after a real receipt INSERT."""


class CommitAcknowledgementLost(RuntimeError):
    """Mark acknowledged-response loss after the underlying commit succeeds."""


class CapturingDedicatedConnectionFactory:
    """Acquire clean dedicated connections and retain them for assertions."""

    def __init__(
        self,
        connection_factory: Callable[[], Connection[object]],
    ) -> None:
        self._connection_factory = connection_factory
        self.connections: list[Connection[object]] = []
        self.backend_pids: list[int] = []

    def __call__(self) -> Connection[object]:
        connection = acquire_clean_test_connection(self._connection_factory)
        assert connection.autocommit is False
        self.connections.append(connection)
        self.backend_pids.append(connection.info.backend_pid)
        return connection


class InsertThenRaiseStore:
    """Execute the real store INSERT before injecting a test-only failure."""

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
        raise InjectedStoreFailure("failure injected after real receipt INSERT")


class InsertThenRaiseOwner(PostgresDecisionReceiptTransactionOwner):
    """Inject failure through the protected store-construction test seam."""

    def __init__(
        self,
        connection_factory: PostgresDecisionReceiptConnectionFactory,
        *,
        idle_in_transaction_session_timeout_ms: int,
    ) -> None:
        super().__init__(
            connection_factory,
            idle_in_transaction_session_timeout_ms=(
                idle_in_transaction_session_timeout_ms
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


class PausingAfterInsertStore:
    """Pause Python after a real INSERT so PostgreSQL observes an idle owner."""

    def __init__(
        self,
        store: PostgresDecisionReceiptStore,
        connection: Connection[object],
        statement_completed: Event,
        release_owner: Event,
        observed_results: list[DecisionReceiptInsertResult],
        observed_timeout_settings: list[tuple[int, str]],
    ) -> None:
        self._store = store
        self._connection = connection
        self._statement_completed = statement_completed
        self._release_owner = release_owner
        self._observed_results = observed_results
        self._observed_timeout_settings = observed_timeout_settings

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
        self._observed_timeout_settings.append(
            read_idle_owner_timeout_setting(self._connection)
        )
        self._statement_completed.set()
        if not self._release_owner.wait(OWNER_THREAD_TIMEOUT_SECONDS):
            raise AssertionError("test harness did not release receipt owner")
        return result


class PausingAfterInsertOwner(PostgresDecisionReceiptTransactionOwner):
    """Expose a bounded post-INSERT idle phase using the protected test seam."""

    def __init__(
        self,
        connection_factory: PostgresDecisionReceiptConnectionFactory,
        *,
        statement_completed: Event,
        release_owner: Event,
    ) -> None:
        super().__init__(
            connection_factory,
            idle_in_transaction_session_timeout_ms=(
                TEST_ONLY_IDLE_OWNER_TIMEOUT_MS
            ),
        )
        self._statement_completed = statement_completed
        self._release_owner = release_owner
        self.observed_results: list[DecisionReceiptInsertResult] = []
        self.observed_timeout_settings: list[tuple[int, str]] = []

    def _build_store(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptStore:
        return cast(
            PostgresDecisionReceiptStore,
            PausingAfterInsertStore(
                PostgresDecisionReceiptStore(connection),
                connection,
                self._statement_completed,
                self._release_owner,
                self.observed_results,
                self.observed_timeout_settings,
            ),
        )


class DelegatingConnection:
    """Delegate the connection surface used by the owner to real psycopg."""

    def __init__(self, connection: Connection[object]) -> None:
        self.underlying = connection

    @property
    def autocommit(self) -> bool:
        return self.underlying.autocommit

    @property
    def info(self):
        return self.underlying.info

    @property
    def closed(self) -> bool:
        return self.underlying.closed

    @property
    def broken(self) -> bool:
        return self.underlying.broken

    def execute(self, query: str, parameters: object = None):
        return self.underlying.execute(query, parameters)

    def commit(self) -> None:
        self.underlying.commit()

    def rollback(self) -> None:
        self.underlying.rollback()

    def close(self) -> None:
        self.underlying.close()


class ScopeObservingConnection(DelegatingConnection):
    """Observe the timeout inside and immediately after the owner transaction."""

    def __init__(self, connection: Connection[object]) -> None:
        super().__init__(connection)
        self.local_setting: tuple[int, str] | None = None
        self.post_commit_setting: tuple[int, str] | None = None

    def execute(self, query: str, parameters: object = None):
        result = self.underlying.execute(query, parameters)
        if "set_config" in query:
            self.local_setting = read_idle_owner_timeout_setting(
                self.underlying
            )
        return result

    def commit(self) -> None:
        self.underlying.commit()
        # This test-only observation opens a new transaction after the receipt
        # commit solely to prove the SET LOCAL value was restored on this same
        # session. The owner's subsequent close rolls that observation back.
        self.post_commit_setting = read_idle_owner_timeout_setting(
            self.underlying
        )


class CommitAcknowledgementLostConnection(DelegatingConnection):
    """Commit for real, then withhold acknowledgement from the owner."""

    def __init__(self, connection: Connection[object]) -> None:
        super().__init__(connection)
        self.underlying_commit_succeeded = False

    def commit(self) -> None:
        self.underlying.commit()
        self.underlying_commit_succeeded = True
        raise CommitAcknowledgementLost(
            "underlying commit succeeded before acknowledgement was lost"
        )


class UnwrappingOwner(PostgresDecisionReceiptTransactionOwner):
    """Bind the real store to the real connection behind a test-only wrapper."""

    def _build_store(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptStore:
        assert isinstance(connection, DelegatingConnection)
        return PostgresDecisionReceiptStore(connection.underlying)


def make_minimal_receipt(**overrides: object) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": uuid4(),
        "outcome_id": uuid4(),
        "ok": True,
        "boundary": SemanticBoundary.RUNTIME_GOVERNANCE,
        "category": SemanticOutcomeCategory.VALID,
        "semantic_code": SemanticOutcomeCode.SEMANTICALLY_VALID,
        "severity": SemanticSeverity.INFO,
        "risk_level": SemanticRiskLevel.LOW,
        "reversibility": SemanticReversibility.REVERSIBLE,
        "reason": "Runtime evidence is semantically valid.",
        "evidence_source": DecisionReceiptEvidenceSource.RUNTIME_OBSERVATION,
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def make_admitted_receipt(
    accepted_event_id: UUID,
    **overrides: object,
) -> DecisionReceipt:
    values: dict[str, object] = {
        "receipt_id": uuid4(),
        "outcome_id": uuid4(),
        "ok": True,
        "boundary": SemanticBoundary.LAYER_1_WRITE_SIDE,
        "category": SemanticOutcomeCategory.VALID,
        "semantic_code": SemanticOutcomeCode.SEMANTICALLY_VALID,
        "severity": SemanticSeverity.INFO,
        "risk_level": SemanticRiskLevel.LOW,
        "reversibility": SemanticReversibility.REVERSIBLE,
        "reason": "Candidate event was admitted to accepted history.",
        "evidence_source": DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION,
        "subject": DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.ACCEPTED_EVENT,
            subject_id=str(accepted_event_id),
        ),
        "correlation": DecisionReceiptCorrelation(
            order_id="order-owner-integration",
            request_id="request-owner-integration",
            candidate_event_id=accepted_event_id,
            accepted_event_id=accepted_event_id,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        "admission_evidence": DecisionReceiptAdmissionEvidence(
            disposition=(
                EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
            )
        ),
        "metadata": {"fixture_identity_owner": "integration-test"},
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def insert_accepted_event(
    connection: Connection[object],
    accepted_event_id: UUID | None = None,
) -> UUID:
    resolved_event_id = accepted_event_id or uuid4()
    connection.execute(
        """
        INSERT INTO order_events (
            accepted_event_id,
            order_id,
            sequence,
            event_type,
            request_id,
            amount,
            occurred_at_ms,
            proof_prev_event_id,
            proof_prev_version,
            proof_prev_status,
            payload_json,
            proof_json,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            1,
            'CREATED',
            %s,
            100.00,
            1700000000000,
            NULL,
            0,
            'INIT',
            '{}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb
        )
        """,
        (
            resolved_event_id,
            f"order-{uuid4()}",
            f"request-{uuid4()}",
        ),
    )
    return resolved_event_id


def read_idle_owner_timeout_setting(
    connection: Connection[object],
) -> tuple[int, str]:
    row = connection.execute(
        """
        SELECT setting::bigint, unit
        FROM pg_settings
        WHERE name = 'idle_in_transaction_session_timeout'
        """
    ).fetchone()

    assert row is not None
    setting, unit = cast(tuple[object, object], row)
    return int(setting), str(unit)


def count_receipts(connection: Connection[object]) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM decision_receipts"
    ).fetchone()

    assert row is not None
    (count,) = cast(tuple[object], row)
    return int(count)


def load_receipt_fresh(
    connection_factory: Callable[[], Connection[object]],
    receipt_id: UUID,
) -> PersistedDecisionReceipt | None:
    connection = connection_factory()
    try:
        return PostgresDecisionReceiptStore(connection).load_by_receipt_id(
            receipt_id
        )
    finally:
        if not connection.closed:
            connection.rollback()
        connection.close()


def start_persist(
    owner: PostgresDecisionReceiptTransactionOwner,
    receipt: DecisionReceipt,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def persist_receipt() -> None:
        try:
            result = owner.persist(
                receipt,
                materialization_provenance=PROVENANCE,
            )
        except BaseException as error:
            outcome.put(error)
        else:
            outcome.put(result)
        finally:
            finished.set()

    thread = Thread(target=persist_receipt, daemon=True)
    thread.start()
    return thread, finished, outcome


def start_concurrent_insert(
    connection: Connection[object],
    receipt: DecisionReceipt,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def insert_receipt() -> None:
        try:
            result = PostgresDecisionReceiptStore(connection).insert(
                receipt,
                materialization_provenance=PROVENANCE,
            )
        except BaseException as error:
            outcome.put(error)
        else:
            outcome.put(result)
        finally:
            finished.set()

    thread = Thread(target=insert_receipt, daemon=True)
    thread.start()
    return thread, finished, outcome


def await_thread_outcome(
    thread: Thread,
    finished: Event,
    outcome: Queue[object],
    *,
    timeout_seconds: float,
) -> object:
    assert finished.wait(timeout_seconds), "database worker did not finish"
    thread.join(timeout=1.0)
    assert not thread.is_alive(), "database worker thread remained alive"
    try:
        return outcome.get_nowait()
    except Empty as error:
        raise AssertionError("database worker produced no outcome") from error


def wait_for_backend_lock(
    observer: Connection[object],
    *,
    backend_pid: int,
    finished: Event,
    timeout_seconds: float = POLL_TIMEOUT_SECONDS,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_wait_state: tuple[object, object] | None = None

    while monotonic() < deadline:
        observer.execute("SELECT pg_stat_clear_snapshot()")
        row = observer.execute(
            """
            SELECT wait_event_type, wait_event
            FROM pg_stat_activity
            WHERE pid = %s
            """,
            (backend_pid,),
        ).fetchone()
        if row is not None:
            wait_event_type, wait_event = cast(
                tuple[str | None, str | None],
                row,
            )
            last_wait_state = (wait_event_type, wait_event)
            if wait_event_type == "Lock":
                return
        if finished.wait(0.01):
            raise AssertionError(
                "contender completed before reaching a PostgreSQL Lock wait"
            )

    raise AssertionError(
        "contender did not reach a PostgreSQL Lock wait; "
        f"last wait state was {last_wait_state}"
    )


def wait_for_backend_absence(
    observer: Connection[object],
    *,
    backend_pid: int,
    timeout_seconds: float = POLL_TIMEOUT_SECONDS,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_state: tuple[object, object, object] | None = None

    while monotonic() < deadline:
        observer.execute("SELECT pg_stat_clear_snapshot()")
        row = observer.execute(
            """
            SELECT state, wait_event_type, wait_event
            FROM pg_stat_activity
            WHERE pid = %s
            """,
            (backend_pid,),
        ).fetchone()
        if row is None:
            return
        typed_row = cast(
            tuple[str, str | None, str | None],
            row,
        )
        last_state = typed_row
        Event().wait(0.01)

    raise AssertionError(
        f"owner backend remained visible; last state was {last_state}"
    )


def test_owner_commits_insert_and_fresh_connection_observes_receipt(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    receipt = make_minimal_receipt()
    factory = CapturingDedicatedConnectionFactory(db_connection_factory)
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=5000,
    )

    result = owner.persist(receipt, materialization_provenance=PROVENANCE)

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert result.statement_result is not None
    assert result.statement_result.status is DecisionReceiptInsertStatus.INSERTED
    assert result.statement_result.record.receipt == receipt
    assert result.statement_result.record.materialization_provenance is PROVENANCE
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert len(factory.connections) == 1
    assert factory.connections[0].closed
    assert load_receipt_fresh(
        db_connection_factory,
        receipt.receipt_id,
    ) == result.statement_result.record


def test_owner_commits_identical_duplicate_on_separate_connections(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    receipt = make_minimal_receipt()
    factory = CapturingDedicatedConnectionFactory(db_connection_factory)
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=5000,
    )

    first = owner.persist(receipt, materialization_provenance=PROVENANCE)
    duplicate = owner.persist(receipt, materialization_provenance=PROVENANCE)

    assert first.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert first.statement_result is not None
    assert first.statement_result.status is DecisionReceiptInsertStatus.INSERTED
    assert duplicate.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert duplicate.statement_result is not None
    assert duplicate.statement_result.status is (
        DecisionReceiptInsertStatus.ALREADY_PRESENT
    )
    assert duplicate.conflict_error is None
    assert len(factory.connections) == 2
    assert factory.connections[0] is not factory.connections[1]
    assert all(connection.closed for connection in factory.connections)

    verification = db_connection_factory()
    try:
        assert count_receipts(verification) == 1
        assert (
            PostgresDecisionReceiptStore(verification).load_by_receipt_id(
                receipt.receipt_id
            )
            == first.statement_result.record
        )
    finally:
        verification.rollback()
        verification.close()


def test_owner_preserves_typed_conflict_and_rolls_back(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    db_connection.commit()
    original = make_admitted_receipt(accepted_event_id)
    conflicting = replace(
        original,
        receipt_id=uuid4(),
        outcome_id=uuid4(),
        reason="Conflicting materialization for the same accepted producer.",
    )
    factory = CapturingDedicatedConnectionFactory(db_connection_factory)
    owner = PostgresDecisionReceiptTransactionOwner(
        factory,
        idle_in_transaction_session_timeout_ms=5000,
    )

    first = owner.persist(original, materialization_provenance=PROVENANCE)
    conflict = owner.persist(conflicting, materialization_provenance=PROVENANCE)

    assert first.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert conflict.durability is (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )
    assert conflict.failure_category is (
        DecisionReceiptTransactionFailureCategory.CONFLICT
    )
    assert conflict.conflict_error is not None
    assert conflict.conflict_error.category is (
        DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
    )
    assert conflict.conflict_error.accepted_event_id == accepted_event_id
    assert conflict.statement_result is None
    assert conflict.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert conflict.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )

    verification = db_connection_factory()
    try:
        store = PostgresDecisionReceiptStore(verification)
        loaded = store.load_by_receipt_id(original.receipt_id)
        assert loaded is not None
        assert loaded.receipt == original
        assert store.load_by_receipt_id(conflicting.receipt_id) is None
        assert count_receipts(verification) == 1
    finally:
        verification.rollback()
        verification.close()


def test_owner_rolls_back_real_insert_after_test_only_store_failure(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Failure injection is fake; INSERT, rollback, and observation are real."""
    receipt = make_minimal_receipt()
    factory = CapturingDedicatedConnectionFactory(db_connection_factory)
    owner = InsertThenRaiseOwner(
        factory,
        idle_in_transaction_session_timeout_ms=5000,
    )

    result = owner.persist(receipt, materialization_provenance=PROVENANCE)

    assert len(owner.observed_results) == 1
    assert owner.observed_results[0].status is (
        DecisionReceiptInsertStatus.INSERTED
    )
    assert result.durability is (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.STORE_OPERATION_FAILED
    )
    assert result.statement_result is None
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.CONFIRMED
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.CLOSED
    )
    assert factory.connections[0].closed
    assert load_receipt_fresh(
        db_connection_factory,
        receipt.receipt_id,
    ) is None


def test_production_owner_idle_timeout_releases_contender_and_classifies_result(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Exercise production owner policy around the real Level 1 mechanism."""
    accepted_event_id = insert_accepted_event(db_connection)
    db_connection.commit()
    owner_receipt = make_admitted_receipt(accepted_event_id)
    contender_receipt = replace(
        owner_receipt,
        receipt_id=uuid4(),
        outcome_id=uuid4(),
        metadata={"fixture_owner": "contender"},
    )
    factory = CapturingDedicatedConnectionFactory(db_connection_factory)
    statement_completed = Event()
    release_owner = Event()
    owner = PausingAfterInsertOwner(
        factory,
        statement_completed=statement_completed,
        release_owner=release_owner,
    )
    owner_thread: Thread | None = None
    owner_finished: Event | None = None
    contender_connection: Connection[object] | None = None
    contender_thread: Thread | None = None
    contender_finished: Event | None = None

    try:
        owner_thread, owner_finished, owner_outcome = start_persist(
            owner,
            owner_receipt,
        )
        assert statement_completed.wait(POLL_TIMEOUT_SECONDS)
        assert len(factory.connections) == 1
        owner_connection = factory.connections[0]
        owner_backend_pid = factory.backend_pids[0]
        assert owner.observed_timeout_settings == [
            (TEST_ONLY_IDLE_OWNER_TIMEOUT_MS, "ms")
        ]

        contender_connection = acquire_clean_test_connection(
            db_connection_factory
        )
        assert contender_connection.info.transaction_status is (
            TransactionStatus.IDLE
        )
        contender_backend_pid = contender_connection.info.backend_pid
        contender_thread, contender_finished, contender_outcome = (
            start_concurrent_insert(contender_connection, contender_receipt)
        )
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=contender_finished,
        )
        assert not contender_finished.is_set()

        contender_observed = await_thread_outcome(
            contender_thread,
            contender_finished,
            contender_outcome,
            timeout_seconds=OWNER_THREAD_TIMEOUT_SECONDS,
        )
        assert isinstance(contender_observed, DecisionReceiptInsertResult)
        assert contender_observed.status is DecisionReceiptInsertStatus.INSERTED

        release_owner.set()
        owner_observed = await_thread_outcome(
            owner_thread,
            owner_finished,
            owner_outcome,
            timeout_seconds=OWNER_THREAD_TIMEOUT_SECONDS,
        )
        assert isinstance(
            owner_observed,
            PostgresDecisionReceiptTransactionResult,
        )
        assert owner_observed.durability is (
            DecisionReceiptTransactionDurability.NOT_COMMITTED
        )
        assert owner_observed.failure_category is (
            DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
        )
        assert owner_observed.statement_result == owner.observed_results[0]
        assert owner_observed.rollback_disposition is (
            DecisionReceiptRollbackDisposition.NOT_POSSIBLE
        )
        assert owner_observed.connection_disposition is (
            DecisionReceiptConnectionDisposition.DISCARDED
        )
        assert owner_observed.sqlstate == "25P03"

        wait_for_backend_absence(
            db_connection,
            backend_pid=owner_backend_pid,
        )
        assert owner_connection.closed
        assert owner_connection.broken

        contender_connection.commit()
        verification = db_connection_factory()
        try:
            store = PostgresDecisionReceiptStore(verification)
            assert store.load_by_receipt_id(owner_receipt.receipt_id) is None
            assert (
                store.load_by_receipt_id(contender_receipt.receipt_id)
                == contender_observed.record
            )
            assert count_receipts(verification) == 1
        finally:
            verification.rollback()
            verification.close()
    finally:
        release_owner.set()
        if owner_thread is not None:
            if owner_thread.is_alive() and factory.connections:
                factory.connections[0].close()
            owner_thread.join(timeout=OWNER_THREAD_TIMEOUT_SECONDS)
            assert not owner_thread.is_alive()
        if contender_thread is not None:
            if (
                contender_thread.is_alive()
                and contender_connection is not None
                and not contender_connection.closed
            ):
                contender_connection.close()
            contender_thread.join(timeout=OWNER_THREAD_TIMEOUT_SECONDS)
            assert not contender_thread.is_alive()
        if contender_connection is not None:
            if not contender_connection.closed:
                contender_connection.rollback()
            contender_connection.close()


def test_owner_timeout_setting_is_transaction_local_and_session_restored(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    baseline_connection = db_connection_factory()
    try:
        baseline_setting = read_idle_owner_timeout_setting(baseline_connection)
    finally:
        baseline_connection.rollback()
        baseline_connection.close()

    underlying = acquire_clean_test_connection(db_connection_factory)
    same_session_baseline = read_idle_owner_timeout_setting(underlying)
    underlying.rollback()
    assert underlying.info.transaction_status is TransactionStatus.IDLE

    observing_connection = ScopeObservingConnection(underlying)

    def connection_factory() -> Connection[object]:
        assert underlying.info.transaction_status is TransactionStatus.IDLE
        return cast(Connection[object], observing_connection)

    owner = UnwrappingOwner(
        connection_factory,
        idle_in_transaction_session_timeout_ms=(
            TEST_ONLY_IDLE_OWNER_TIMEOUT_MS
        ),
    )
    receipt = make_minimal_receipt()

    result = owner.persist(receipt, materialization_provenance=PROVENANCE)

    assert result.durability is DecisionReceiptTransactionDurability.COMMITTED
    assert observing_connection.local_setting == (
        TEST_ONLY_IDLE_OWNER_TIMEOUT_MS,
        "ms",
    )
    assert observing_connection.post_commit_setting == same_session_baseline
    assert underlying.closed

    fresh_connection = db_connection_factory()
    try:
        assert read_idle_owner_timeout_setting(fresh_connection) == (
            baseline_setting
        )
    finally:
        fresh_connection.rollback()
        fresh_connection.close()


def test_owner_reports_unknown_when_real_commit_acknowledgement_is_withheld(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    """Model deterministic acknowledgement loss, not a network simulation."""
    underlying = acquire_clean_test_connection(db_connection_factory)
    ambiguous_connection = CommitAcknowledgementLostConnection(underlying)

    def connection_factory() -> Connection[object]:
        assert underlying.info.transaction_status is TransactionStatus.IDLE
        return cast(Connection[object], ambiguous_connection)

    owner = UnwrappingOwner(
        connection_factory,
        idle_in_transaction_session_timeout_ms=5000,
    )
    receipt = make_minimal_receipt()

    result = owner.persist(receipt, materialization_provenance=PROVENANCE)

    assert ambiguous_connection.underlying_commit_succeeded
    assert result.durability is DecisionReceiptTransactionDurability.UNKNOWN
    assert result.durability is not (
        DecisionReceiptTransactionDurability.NOT_COMMITTED
    )
    assert result.failure_category is (
        DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
    )
    assert result.statement_result is not None
    assert result.statement_result.status is DecisionReceiptInsertStatus.INSERTED
    assert result.rollback_disposition is (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    )
    assert result.connection_disposition is (
        DecisionReceiptConnectionDisposition.DISCARDED
    )
    assert underlying.closed
    assert load_receipt_fresh(
        db_connection_factory,
        receipt.receipt_id,
    ) == result.statement_result.record
