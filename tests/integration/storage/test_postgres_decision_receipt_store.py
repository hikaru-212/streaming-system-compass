# pyright: reportIndexIssue=false
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from psycopg import Connection, IsolationLevel
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    IdleInTransactionSessionTimeout,
    InFailedSqlTransaction,
    SerializationFailure,
)
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlagState,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.read_side_decision_receipt_mapping import (
    map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
    map_projection_snapshot_replay_validation_result_to_decision_receipt,
    map_replay_validation_result_to_decision_receipt,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.compass.runtime.write_side_decision_receipt_mapping import (
    map_postgres_write_side_result_to_decision_receipt,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.replay_validator import (
    ReplayValidationResult,
    ReplayValidationStatus,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptConflictCategory,
    DecisionReceiptConflictError,
    DecisionReceiptInsertResult,
    DecisionReceiptInsertStatus,
    DecisionReceiptMaterializationProvenance,
)
from src.storage.postgres_decision_receipt_store import (
    PostgresDecisionReceiptStore,
)
from tests.unit.compass.runtime.test_read_side_decision_receipt_mapping import (
    CREATED_STATE,
    ORDER_ID,
    PAID_STATE,
)
from tests.unit.compass.runtime.test_write_side_decision_receipt_mapping import (
    make_accepted_result,
    make_validation_blocked_result,
)


INT64_MAX = 2**63 - 1
TEST_ONLY_IDLE_OWNER_TIMEOUT = "3s"
IDLE_OWNER_OUTER_TIMEOUT_SECONDS = 15.0


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
            order_id="order-receipt-store",
            request_id="request-receipt-store",
            candidate_event_id=accepted_event_id,
            accepted_event_id=accepted_event_id,
            snapshot_id=uuid4(),
            source_global_position=17,
            identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
        ),
        "actor": DecisionReceiptActor(
            actor_id="writer-001",
            actor_role="service",
            runtime_role="write-side",
        ),
        "cost_summary": DecisionReceiptCostSummary(
            elapsed_ms=13,
            validation_elapsed_ms=2,
            replay_elapsed_ms=0,
            transaction_elapsed_ms=8,
            lock_wait_ms=1,
        ),
        "flags": DecisionReceiptFlags(
            fallback_required=DecisionReceiptFlagState.FALSE,
            rebuild_required=DecisionReceiptFlagState.NOT_EVALUATED,
            operator_review_required=DecisionReceiptFlagState.TRUE,
            retry_candidate=DecisionReceiptFlagState.FALSE,
        ),
        "admission_evidence": DecisionReceiptAdmissionEvidence(
            disposition=(
                EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
            )
        ),
        "evidence_summary": {
            "technical_status": "SUCCESS",
            "checks": [True, False, None],
            "nested": {"count": 2, "ratio": 0.5},
        },
        "metadata": {
            "labels": ["write-side", {"source": "integration-test"}],
            "attempt": 1,
        },
    }
    values.update(overrides)
    return DecisionReceipt(**values)  # type: ignore[arg-type]


def mapper_produced_receipts() -> list[DecisionReceipt]:
    """Build representative PR4/PR5 receipts through public mapper APIs."""

    snapshot_id = UUID("00000000-0000-0000-0000-000000000806")
    return [
        map_postgres_write_side_result_to_decision_receipt(
            receipt_id=UUID(int=810),
            outcome_id=UUID(int=910),
            result=make_accepted_result(),
        ),
        map_postgres_write_side_result_to_decision_receipt(
            receipt_id=UUID(int=811),
            outcome_id=UUID(int=911),
            result=make_validation_blocked_result(with_stream=True),
        ),
        map_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=812),
            outcome_id=UUID(int=912),
            result=ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.MATCH,
                expected_state=CREATED_STATE,
                persisted_state=CREATED_STATE,
                reason="Projection matches accepted-history replay.",
            ),
        ),
        map_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=813),
            outcome_id=UUID(int=913),
            result=ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
                expected_state=None,
                persisted_state=CREATED_STATE,
                reason="No accepted history exists for order.",
            ),
        ),
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=814),
            outcome_id=UUID(int=914),
            result=ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MATCH,
                order_id=ORDER_ID,
                snapshot_id=snapshot_id,
                source_global_position=10,
                snapshot_assisted_state=PAID_STATE,
                authority_state=PAID_STATE,
                reason="Snapshot-assisted replay matches authority.",
            ),
        ),
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=UUID(int=815),
            outcome_id=UUID(int=915),
            result=ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .NO_ACCEPTED_HISTORY_FOR_ORDER
                ),
                order_id=ORDER_ID,
                snapshot_id=snapshot_id,
                source_global_position=0,
                snapshot_assisted_state=None,
                authority_state=None,
                reason="No accepted history exists for order.",
            ),
        ),
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=UUID(int=816),
            outcome_id=UUID(int=916),
            result=ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                resolved_state=PAID_STATE,
                snapshot_id=snapshot_id,
                source_global_position=10,
                reason="Projection resolved from snapshot and tail.",
            ),
        ),
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=UUID(int=817),
            outcome_id=UUID(int=917),
            result=ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .TAIL_REPLAY_FAILED
                ),
                resolved_state=None,
                snapshot_id=snapshot_id,
                source_global_position=10,
                reason="Snapshot-assisted tail replay failed.",
            ),
        ),
    ]


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


def count_receipts(connection: Connection[object]) -> int:
    row = connection.execute("SELECT COUNT(*) FROM decision_receipts").fetchone()
    assert row is not None
    return row[0]


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
                materialization_provenance=(
                    DecisionReceiptMaterializationProvenance.LIVE_RESULT
                ),
            )
        except BaseException as exc:
            outcome.put(exc)
        else:
            outcome.put(result)
        finally:
            finished.set()

    thread = Thread(target=insert_receipt, daemon=True)
    thread.start()
    return thread, finished, outcome


def wait_for_backend_lock(
    observer: Connection[object],
    *,
    backend_pid: int,
    finished: Event,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_wait_state: tuple[object, object] | None = None

    while monotonic() < deadline:
        # PostgreSQL statistics observations may remain transaction-cached,
        # so each polling iteration must explicitly refresh the snapshot.
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
            last_wait_state = (row[0], row[1])
            if row[0] == "Lock":
                return
        if finished.wait(0.01):
            raise AssertionError(
                "concurrent insert completed before reaching a lock wait"
            )

    raise AssertionError(
        "concurrent insert did not reach a PostgreSQL lock wait; "
        f"last wait state was {last_wait_state}"
    )


def _apply_transaction_local_idle_owner_timeout(
    connection: Connection[object],
) -> None:
    row = connection.execute(
        """
        SELECT set_config(
            'idle_in_transaction_session_timeout',
            %s,
            true
        )
        """,
        (TEST_ONLY_IDLE_OWNER_TIMEOUT,),
    ).fetchone()
    assert row is not None
    assert isinstance(row, tuple)
    assert row[0] == TEST_ONLY_IDLE_OWNER_TIMEOUT


def _wait_for_backend_absence(
    observer: Connection[object],
    *,
    backend_pid: int,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_backend_state: tuple[object, object, object] | None = None

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

        assert isinstance(row, tuple)
        last_backend_state = (row[0], row[1], row[2])
        sleep(0.01)

    raise AssertionError(
        f"backend {backend_pid} remained in pg_stat_activity after "
        f"{timeout_seconds:.1f} seconds; "
        f"last state was {last_backend_state}"
    )


def await_concurrent_outcome(
    thread: Thread,
    finished: Event,
    outcome: Queue[object],
    *,
    timeout_seconds: float = 5.0,
) -> object:
    assert finished.wait(timeout_seconds), "concurrent insert did not finish"
    thread.join(timeout=1.0)
    assert not thread.is_alive(), "concurrent insert thread remained alive"
    try:
        return outcome.get_nowait()
    except Empty as exc:
        raise AssertionError("concurrent insert produced no outcome") from exc


def test_idle_in_transaction_timeout_can_be_scoped_to_one_transaction(
    db_connection_factory: Callable[[], Connection[object]],
) -> None:
    connection = db_connection_factory()
    try:
        connection.rollback()
        initial_row = connection.execute(
            "SHOW idle_in_transaction_session_timeout"
        ).fetchone()
        assert initial_row is not None
        assert isinstance(initial_row, tuple)
        initial_value = initial_row[0]

        _apply_transaction_local_idle_owner_timeout(connection)
        local_row = connection.execute(
            "SHOW idle_in_transaction_session_timeout"
        ).fetchone()
        assert local_row is not None
        assert isinstance(local_row, tuple)
        assert local_row[0] == TEST_ONLY_IDLE_OWNER_TIMEOUT

        connection.rollback()
        assert connection.info.transaction_status is TransactionStatus.IDLE
        restored_row = connection.execute(
            "SHOW idle_in_transaction_session_timeout"
        ).fetchone()
        assert restored_row is not None
        assert isinstance(restored_row, tuple)
        assert restored_row[0] == initial_value
    finally:
        if not connection.closed:
            connection.rollback()
        connection.close()


def test_idle_owner_timeout_rolls_back_and_releases_conflicting_receipt_insert(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    db_connection.commit()

    owner_receipt = make_admitted_receipt(accepted_event_id)
    contender_receipt = replace(
        owner_receipt,
        receipt_id=uuid4(),
        outcome_id=uuid4(),
        metadata={"transaction_owner": "contender"},
    )
    owner_connection = db_connection_factory()
    contender_connection: Connection[object] | None = None
    thread: Thread | None = None
    finished: Event | None = None

    try:
        owner_connection.rollback()
        owner_connection.isolation_level = IsolationLevel.READ_COMMITTED
        owner_backend_pid = owner_connection.info.backend_pid
        owner_result = PostgresDecisionReceiptStore(owner_connection).insert(
            owner_receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )
        assert owner_result.status is DecisionReceiptInsertStatus.INSERTED

        # The owner must remain uncommitted so its speculative unique-index
        # entry can block the competing admitted-producer identity.
        contender_connection = db_connection_factory()
        contender_connection.rollback()
        contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
        contender_backend_pid = contender_connection.info.backend_pid
        thread, finished, outcome = start_concurrent_insert(
            contender_connection,
            contender_receipt,
        )

        # Observing PostgreSQL's Lock wait distinguishes real database
        # blocking from a worker that is merely slow or unscheduled.
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()

        # Activate the local timeout only after proving the contender is
        # blocked, so the owner receives the complete test-only idle window.
        _apply_transaction_local_idle_owner_timeout(owner_connection)

        # No further owner work is sent. Server-side session termination rolls
        # back its open transaction and releases the uniqueness contender.
        observed = await_concurrent_outcome(
            thread,
            finished,
            outcome,
            timeout_seconds=IDLE_OWNER_OUTER_TIMEOUT_SECONDS,
        )
        assert isinstance(observed, DecisionReceiptInsertResult)
        assert observed.status is DecisionReceiptInsertStatus.INSERTED
        assert observed.record.receipt == contender_receipt

        _wait_for_backend_absence(
            db_connection,
            backend_pid=owner_backend_pid,
        )

        contender_connection.commit()

        # A fresh transaction proves durable state without reusing either
        # participant's prior transaction snapshot.
        with db_connection_factory() as verification_connection:
            verification_store = PostgresDecisionReceiptStore(
                verification_connection
            )
            assert (
                verification_store.load_by_receipt_id(
                    owner_receipt.receipt_id
                )
                is None
            )
            assert (
                verification_store.load_by_receipt_id(
                    contender_receipt.receipt_id
                )
                == observed.record
            )
            assert (
                verification_store
                .load_admitted_write_side_materialization_by_accepted_event_id(
                    accepted_event_id,
                )
                == observed.record
            )
            assert count_receipts(verification_connection) == 1

        with pytest.raises(IdleInTransactionSessionTimeout) as raised:
            owner_connection.execute("SELECT 1")

        assert raised.value.sqlstate == "25P03"
        assert owner_connection.info.transaction_status is (
            TransactionStatus.UNKNOWN
        )
        assert owner_connection.closed
        assert owner_connection.broken
        # The server-terminated owner is broken rather than a connection that
        # can be rolled back and returned for reuse; cleanup must discard it.
    finally:
        if thread is not None:
            if thread.is_alive():
                owner_connection.close()
                assert finished is not None
                assert finished.wait(IDLE_OWNER_OUTER_TIMEOUT_SECONDS)
            thread.join(timeout=1.0)
            assert not thread.is_alive()
        if contender_connection is not None:
            if not contender_connection.closed:
                contender_connection.rollback()
            contender_connection.close()
        owner_connection.close()


def test_insert_minimal_runtime_receipt_returns_statement_level_inserted(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)
    receipt = make_minimal_receipt()

    result = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert result.status is DecisionReceiptInsertStatus.INSERTED
    assert result.record.receipt == receipt
    assert result.record.receipt_serialization_version == 1
    assert result.record.materialized_at.tzinfo is not None
    assert result.record.materialized_at.utcoffset() is not None


def test_fully_populated_admitted_receipt_and_envelope_round_trip(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    receipt = make_admitted_receipt(accepted_event_id)
    store = PostgresDecisionReceiptStore(db_connection)

    inserted = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.ACCEPTED_HISTORY_RECONCILIATION
        ),
    )
    loaded_by_receipt = store.load_by_receipt_id(receipt.receipt_id)
    loaded_by_event = (
        store.load_admitted_write_side_materialization_by_accepted_event_id(
            accepted_event_id
        )
    )

    assert inserted.status is DecisionReceiptInsertStatus.INSERTED
    assert loaded_by_receipt == inserted.record
    assert loaded_by_event == inserted.record
    assert inserted.record.receipt == receipt
    assert inserted.record.receipt.evidence_summary == receipt.evidence_summary
    assert inserted.record.receipt.metadata == receipt.metadata
    assert inserted.record.receipt.flags == receipt.flags
    assert inserted.record.materialization_provenance is (
        DecisionReceiptMaterializationProvenance.ACCEPTED_HISTORY_RECONCILIATION
    )


@pytest.mark.parametrize(
    "receipt",
    mapper_produced_receipts(),
    ids=[
        "write-accepted",
        "write-validation-blocked",
        "replay-match",
        "replay-no-history-with-persisted-state",
        "snapshot-match-with-lineage",
        "snapshot-no-history-with-lineage-zero-position",
        "assisted-resolved",
        "assisted-tail-replay-failed",
    ],
)
def test_pr4_pr5_mapper_produced_receipts_round_trip_through_store(
    db_connection: Connection[object],
    clean_database: None,
    receipt: DecisionReceipt,
) -> None:
    accepted_event_id = receipt.correlation.accepted_event_id
    if accepted_event_id is not None:
        insert_accepted_event(db_connection, accepted_event_id)

    store = PostgresDecisionReceiptStore(db_connection)
    inserted = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert inserted.status is DecisionReceiptInsertStatus.INSERTED
    db_connection.commit()

    loaded = store.load_by_receipt_id(receipt.receipt_id)
    assert loaded is not None
    assert loaded.receipt == receipt
    assert loaded.materialization_provenance is (
        DecisionReceiptMaterializationProvenance.LIVE_RESULT
    )

    if receipt.evidence_source is not (
        DecisionReceiptEvidenceSource.WRITE_SIDE_ADMISSION
    ):
        assert accepted_event_id is None
        assert loaded.receipt.admission_evidence is None

    if receipt.receipt_id == UUID(int=813):
        assert loaded.receipt.evidence_summary == {
            "technical_status": "NO_ACCEPTED_HISTORY",
            "expected_state_present": False,
            "persisted_state_present": True,
        }

    if receipt.receipt_id == UUID(int=815):
        assert loaded.receipt.correlation.snapshot_id is not None
        assert loaded.receipt.correlation.source_global_position == 0
        assert loaded.receipt.correlation.identity_source is (
            DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
        )
        assert loaded.receipt.evidence_summary == {
            "technical_status": "NO_ACCEPTED_HISTORY_FOR_ORDER",
            "snapshot_artifact_present": True,
            "snapshot_assisted_state_present": False,
            "authority_state_present": False,
        }

    if receipt.receipt_id == UUID(int=817):
        assert loaded.receipt.flags == DecisionReceiptFlags()
        assert all(
            state is DecisionReceiptFlagState.NOT_EVALUATED
            for state in (
                loaded.receipt.flags.fallback_required,
                loaded.receipt.flags.rebuild_required,
                loaded.receipt.flags.operator_review_required,
                loaded.receipt.flags.retry_candidate,
            )
        )


def test_missing_receipt_and_admitted_materialization_loads_return_none(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)

    assert store.load_by_receipt_id(uuid4()) is None
    assert (
        store.load_admitted_write_side_materialization_by_accepted_event_id(
            uuid4()
        )
        is None
    )


@pytest.mark.parametrize(
    "provenance",
    list(DecisionReceiptMaterializationProvenance),
)
def test_materialization_provenance_round_trips(
    db_connection: Connection[object],
    clean_database: None,
    provenance: DecisionReceiptMaterializationProvenance,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)

    result = store.insert(
        make_minimal_receipt(),
        materialization_provenance=provenance,
    )

    assert result.record.materialization_provenance is provenance


def test_insert_does_not_commit_and_caller_rollback_removes_row(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)

    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with db_connection_factory() as other_connection:
        other_store = PostgresDecisionReceiptStore(other_connection)
        assert other_store.load_by_receipt_id(receipt.receipt_id) is None

    db_connection.rollback()
    assert store.load_by_receipt_id(receipt.receipt_id) is None


def test_caller_commit_makes_inserted_row_visible_to_new_connection(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    db_connection.commit()

    with db_connection_factory() as other_connection:
        loaded = PostgresDecisionReceiptStore(
            other_connection
        ).load_by_receipt_id(receipt.receipt_id)
        assert loaded is not None
        assert loaded.receipt == receipt


def test_load_does_not_commit_pending_insert(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert store.load_by_receipt_id(receipt.receipt_id) is not None
    db_connection.rollback()
    assert store.load_by_receipt_id(receipt.receipt_id) is None


def test_identical_duplicate_with_same_provenance_is_already_present(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    first = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    duplicate = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert duplicate.status is DecisionReceiptInsertStatus.ALREADY_PRESENT
    assert duplicate.record == first.record
    assert count_receipts(db_connection) == 1


def test_identical_duplicate_with_different_provenance_preserves_envelope(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    first = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    duplicate = store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.ACCEPTED_HISTORY_RECONCILIATION
        ),
    )

    assert duplicate.status is DecisionReceiptInsertStatus.ALREADY_PRESENT
    assert duplicate.record == first.record
    assert duplicate.record.materialization_provenance is (
        DecisionReceiptMaterializationProvenance.LIVE_RESULT
    )
    assert duplicate.record.materialized_at == first.record.materialized_at


def test_same_receipt_id_with_different_payload_is_content_conflict(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt(metadata={"original": True})
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(DecisionReceiptConflictError) as raised:
        store.insert(
            replace(receipt, reason="Different semantic reason."),
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert raised.value.category is (
        DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
    )
    loaded = store.load_by_receipt_id(receipt.receipt_id)
    assert loaded is not None
    assert loaded.receipt == receipt
    assert loaded.receipt.metadata == {"original": True}


@pytest.mark.parametrize(
    ("field_name", "original_value", "conflicting_value"),
    [
        (
            "evidence_summary",
            {"nested": {"value": True}},
            {"nested": {"value": 1}},
        ),
        (
            "metadata",
            {"nested": [False]},
            {"nested": [0]},
        ),
        (
            "evidence_summary",
            {"nested": {"value": 1}},
            {"nested": {"value": 1.0}},
        ),
    ],
    ids=["bool-vs-int", "false-vs-zero", "int-vs-float"],
)
def test_same_receipt_id_with_different_json_scalar_types_is_conflict(
    db_connection: Connection[object],
    clean_database: None,
    field_name: str,
    original_value: dict[str, object],
    conflicting_value: dict[str, object],
) -> None:
    original = make_minimal_receipt(**{field_name: original_value})
    conflicting = replace(original, **{field_name: conflicting_value})
    store = PostgresDecisionReceiptStore(db_connection)
    first = store.insert(
        original,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(DecisionReceiptConflictError) as raised:
        store.insert(
            conflicting,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert raised.value.category is (
        DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
    )
    loaded = store.load_by_receipt_id(original.receipt_id)
    assert loaded is not None
    assert loaded == first.record
    assert loaded.receipt == original


def test_same_json_object_with_different_insertion_order_is_already_present(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    original_evidence: dict[str, object] = {}
    original_evidence["first"] = {"enabled": True}
    original_evidence["second"] = [1, 2]

    reordered_evidence: dict[str, object] = {}
    reordered_evidence["second"] = [1, 2]
    reordered_evidence["first"] = {"enabled": True}

    original = make_minimal_receipt(evidence_summary=original_evidence)
    reordered = replace(original, evidence_summary=reordered_evidence)
    store = PostgresDecisionReceiptStore(db_connection)
    first = store.insert(
        original,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    duplicate = store.insert(
        reordered,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert duplicate.status is DecisionReceiptInsertStatus.ALREADY_PRESENT
    assert duplicate.record == first.record


def test_same_receipt_id_with_reordered_json_list_is_content_conflict(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    original = make_minimal_receipt(
        evidence_summary={"ordered": ["first", "second", "third"]}
    )
    conflicting = replace(
        original,
        evidence_summary={"ordered": ["third", "second", "first"]},
    )
    store = PostgresDecisionReceiptStore(db_connection)
    first = store.insert(
        original,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(DecisionReceiptConflictError) as raised:
        store.insert(
            conflicting,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert raised.value.category is (
        DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
    )
    assert store.load_by_receipt_id(original.receipt_id) == first.record


def test_same_admitted_producer_with_different_receipt_id_is_conflict(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    first = make_admitted_receipt(accepted_event_id)
    second = replace(first, receipt_id=uuid4())
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        first,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(DecisionReceiptConflictError) as raised:
        store.insert(
            second,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert raised.value.category is (
        DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
    )
    assert raised.value.accepted_event_id == accepted_event_id
    assert count_receipts(db_connection) == 1
    assert store.load_by_receipt_id(first.receipt_id) is not None
    assert store.load_by_receipt_id(second.receipt_id) is None


def test_same_admitted_producer_with_different_payload_is_conflict(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    first = make_admitted_receipt(accepted_event_id)
    second = replace(
        first,
        receipt_id=uuid4(),
        reason="Different admitted receipt evidence.",
    )
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        first,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(DecisionReceiptConflictError) as raised:
        store.insert(
            second,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert raised.value.category is (
        DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
    )


def test_same_accepted_event_is_allowed_for_non_admitted_receipt_family(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    correlation = DecisionReceiptCorrelation(
        accepted_event_id=accepted_event_id,
        identity_source=DecisionReceiptIdentitySource.ACCEPTED_HISTORY,
    )
    admission = DecisionReceiptAdmissionEvidence(
        disposition=EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT
    )
    first = make_minimal_receipt(
        correlation=correlation,
        admission_evidence=admission,
    )
    second = replace(first, receipt_id=uuid4(), outcome_id=uuid4())
    store = PostgresDecisionReceiptStore(db_connection)

    first_result = store.insert(
        first,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )
    second_result = store.insert(
        second,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert first_result.status is DecisionReceiptInsertStatus.INSERTED
    assert second_result.status is DecisionReceiptInsertStatus.INSERTED
    assert count_receipts(db_connection) == 2
    assert (
        store.load_admitted_write_side_materialization_by_accepted_event_id(
            accepted_event_id
        )
        is None
    )


def test_duplicate_classification_leaves_connection_reusable(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    next_result = store.insert(
        make_minimal_receipt(),
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert next_result.status is DecisionReceiptInsertStatus.INSERTED
    assert count_receipts(db_connection) == 2


@pytest.mark.parametrize("conflict_kind", ["receipt-id", "producer"])
def test_conflict_classification_leaves_connection_reusable(
    db_connection: Connection[object],
    clean_database: None,
    conflict_kind: str,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)
    if conflict_kind == "receipt-id":
        first = make_minimal_receipt()
        conflicting = replace(first, reason="Different semantic reason.")
    else:
        accepted_event_id = insert_accepted_event(db_connection)
        first = make_admitted_receipt(accepted_event_id)
        conflicting = replace(first, receipt_id=uuid4())

    store.insert(
        first,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )
    with pytest.raises(DecisionReceiptConflictError):
        store.insert(
            conflicting,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    next_result = store.insert(
        make_minimal_receipt(),
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )
    assert next_result.status is DecisionReceiptInsertStatus.INSERTED


def test_concurrent_identical_receipt_classifies_after_winner_commits(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    db_connection.isolation_level = IsolationLevel.READ_COMMITTED
    receipt = make_minimal_receipt()
    first_store = PostgresDecisionReceiptStore(db_connection)
    first = first_store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    contender_connection = db_connection_factory()
    contender_connection.rollback()
    contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
    contender_backend_pid = contender_connection.info.backend_pid
    thread, finished, outcome = start_concurrent_insert(
        contender_connection,
        receipt,
    )
    try:
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()
        db_connection.commit()

        observed = await_concurrent_outcome(thread, finished, outcome)
        assert isinstance(observed, DecisionReceiptInsertResult)
        assert observed.status is DecisionReceiptInsertStatus.ALREADY_PRESENT
        assert observed.record == first.record
    finally:
        if thread.is_alive():
            db_connection.rollback()
            assert finished.wait(5.0)
            thread.join(timeout=1.0)
        contender_connection.rollback()
        contender_connection.close()


def test_concurrent_receipt_content_conflict_classifies_after_winner_commits(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    db_connection.isolation_level = IsolationLevel.READ_COMMITTED
    original = make_minimal_receipt(metadata={"owner": "first"})
    conflicting = replace(original, reason="Different semantic reason.")
    first_store = PostgresDecisionReceiptStore(db_connection)
    first = first_store.insert(
        original,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    contender_connection = db_connection_factory()
    contender_connection.rollback()
    contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
    contender_backend_pid = contender_connection.info.backend_pid
    thread, finished, outcome = start_concurrent_insert(
        contender_connection,
        conflicting,
    )
    try:
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()
        db_connection.commit()

        observed = await_concurrent_outcome(thread, finished, outcome)
        assert isinstance(observed, DecisionReceiptConflictError)
        assert observed.category is (
            DecisionReceiptConflictCategory.RECEIPT_ID_CONTENT_CONFLICT
        )
        assert first_store.load_by_receipt_id(original.receipt_id) == first.record
    finally:
        if thread.is_alive():
            db_connection.rollback()
            assert finished.wait(5.0)
            thread.join(timeout=1.0)
        contender_connection.rollback()
        contender_connection.close()


def test_concurrent_admitted_producer_conflict_classifies_after_winner_commits(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    db_connection.isolation_level = IsolationLevel.READ_COMMITTED
    accepted_event_id = insert_accepted_event(db_connection)
    db_connection.commit()

    original = make_admitted_receipt(accepted_event_id)
    conflicting = replace(original, receipt_id=uuid4(), outcome_id=uuid4())
    first_store = PostgresDecisionReceiptStore(db_connection)
    first = first_store.insert(
        original,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    contender_connection = db_connection_factory()
    contender_connection.rollback()
    contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
    contender_backend_pid = contender_connection.info.backend_pid
    thread, finished, outcome = start_concurrent_insert(
        contender_connection,
        conflicting,
    )
    try:
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()
        db_connection.commit()

        observed = await_concurrent_outcome(thread, finished, outcome)
        assert isinstance(observed, DecisionReceiptConflictError)
        assert observed.category is (
            DecisionReceiptConflictCategory.ACCEPTED_PRODUCER_IDENTITY_CONFLICT
        )
        assert observed.accepted_event_id == accepted_event_id
        assert first_store.load_by_receipt_id(original.receipt_id) == first.record
        assert first_store.load_by_receipt_id(conflicting.receipt_id) is None
        assert count_receipts(db_connection) == 1
        assert (
            first_store.load_admitted_write_side_materialization_by_accepted_event_id(
                accepted_event_id
            )
            == first.record
        )
    finally:
        if thread.is_alive():
            db_connection.rollback()
            assert finished.wait(5.0)
            thread.join(timeout=1.0)
        contender_connection.rollback()
        contender_connection.close()


def test_concurrent_identical_receipt_inserts_after_winner_rolls_back(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    db_connection.isolation_level = IsolationLevel.READ_COMMITTED
    receipt = make_minimal_receipt()
    PostgresDecisionReceiptStore(db_connection).insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    contender_connection = db_connection_factory()
    contender_connection.rollback()
    contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
    contender_backend_pid = contender_connection.info.backend_pid
    thread, finished, outcome = start_concurrent_insert(
        contender_connection,
        receipt,
    )
    try:
        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()
        db_connection.rollback()

        observed = await_concurrent_outcome(thread, finished, outcome)
        assert isinstance(observed, DecisionReceiptInsertResult)
        assert observed.status is DecisionReceiptInsertStatus.INSERTED
        assert observed.record.receipt == receipt
    finally:
        if thread.is_alive():
            db_connection.rollback()
            assert finished.wait(5.0)
            thread.join(timeout=1.0)
        contender_connection.rollback()
        contender_connection.close()


def test_concurrent_identical_receipt_inserts_after_winner_connection_closes_without_commit(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    winner_connection = db_connection_factory()
    contender_connection: Connection[object] | None = None
    thread: Thread | None = None
    finished: Event | None = None
    receipt = make_minimal_receipt()

    try:
        winner_connection.rollback()
        winner_connection.isolation_level = IsolationLevel.READ_COMMITTED
        PostgresDecisionReceiptStore(winner_connection).insert(
            receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

        contender_connection = db_connection_factory()
        contender_connection.rollback()
        contender_connection.isolation_level = IsolationLevel.READ_COMMITTED
        contender_backend_pid = contender_connection.info.backend_pid
        thread, finished, outcome = start_concurrent_insert(
            contender_connection,
            receipt,
        )

        wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=finished,
        )
        assert not finished.is_set()

        winner_connection.close()

        observed = await_concurrent_outcome(thread, finished, outcome)
        assert isinstance(observed, DecisionReceiptInsertResult)
        assert observed.status is DecisionReceiptInsertStatus.INSERTED
        assert observed.record.receipt == receipt

        contender_connection.commit()

        with db_connection_factory() as verification_connection:
            loaded = PostgresDecisionReceiptStore(
                verification_connection
            ).load_by_receipt_id(receipt.receipt_id)
            assert loaded is not None
            assert loaded == observed.record
            assert loaded.receipt == receipt
    finally:
        if not winner_connection.closed:
            winner_connection.close()
        if thread is not None:
            if thread.is_alive():
                assert finished is not None
                assert finished.wait(5.0)
            thread.join(timeout=1.0)
            assert not thread.is_alive()
        if contender_connection is not None:
            contender_connection.rollback()
            contender_connection.close()


@pytest.mark.parametrize(
    "isolation_level",
    [IsolationLevel.REPEATABLE_READ, IsolationLevel.SERIALIZABLE],
    ids=["repeatable-read", "serializable"],
)
def test_stronger_isolation_surfaces_native_serialization_failure(
    db_connection: Connection[object],
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
    isolation_level: IsolationLevel,
) -> None:
    receipt = make_minimal_receipt()
    contender_connection = db_connection_factory()
    contender_connection.rollback()
    contender_connection.isolation_level = isolation_level
    contender_store = PostgresDecisionReceiptStore(contender_connection)
    try:
        assert contender_store.load_by_receipt_id(receipt.receipt_id) is None

        PostgresDecisionReceiptStore(db_connection).insert(
            receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )
        db_connection.commit()

        with pytest.raises(SerializationFailure):
            contender_store.insert(
                receipt,
                materialization_provenance=(
                    DecisionReceiptMaterializationProvenance.LIVE_RESULT
                ),
            )

        assert contender_connection.info.transaction_status is (
            TransactionStatus.INERROR
        )
        with pytest.raises(InFailedSqlTransaction):
            contender_connection.execute("SELECT 1")

        contender_connection.rollback()
        assert contender_connection.info.transaction_status is (
            TransactionStatus.IDLE
        )
        assert contender_store.load_by_receipt_id(receipt.receipt_id) is not None
    finally:
        contender_connection.rollback()
        contender_connection.close()


def test_typed_integer_overflow_fails_before_sql(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt(
        correlation=DecisionReceiptCorrelation(
            source_global_position=INT64_MAX + 1
        )
    )
    store = PostgresDecisionReceiptStore(db_connection)

    with pytest.raises(ValueError, match="signed 64-bit"):
        store.insert(
            receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert count_receipts(db_connection) == 0


def test_nested_json_integer_overflow_fails_before_sql(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt(
        evidence_summary={"nested": [INT64_MAX + 1]}
    )
    store = PostgresDecisionReceiptStore(db_connection)

    with pytest.raises(ValueError, match="signed 64-bit"):
        store.insert(
            receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )

    assert count_receipts(db_connection) == 0


def test_load_rejects_schema_valid_row_with_nested_integer_overflow(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt_id = uuid4()
    db_connection.execute(
        """
        INSERT INTO decision_receipts (
            receipt_id,
            receipt_serialization_version,
            outcome_id,
            ok,
            boundary,
            category,
            semantic_code,
            severity,
            risk_level,
            reversibility,
            reason,
            evidence_source,
            subject_type,
            identity_source,
            fallback_required,
            rebuild_required,
            operator_review_required,
            retry_candidate,
            evidence_summary,
            metadata,
            materialization_provenance
        )
        VALUES (
            %s,
            1,
            %s,
            TRUE,
            'RUNTIME_GOVERNANCE',
            'VALID',
            'SEMANTICALLY_VALID',
            'INFO',
            'LOW',
            'REVERSIBLE',
            'Runtime evidence is semantically valid.',
            'RUNTIME_OBSERVATION',
            'UNKNOWN',
            'UNKNOWN',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            %s,
            '{}'::jsonb,
            'LIVE_RESULT'
        )
        """,
        (
            receipt_id,
            uuid4(),
            Jsonb({"nested": [INT64_MAX + 1]}),
        ),
    )

    with pytest.raises(ValueError, match="signed 64-bit"):
        PostgresDecisionReceiptStore(db_connection).load_by_receipt_id(
            receipt_id
        )


def test_schema_prevents_constructing_unsupported_stored_version(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_minimal_receipt()
    store = PostgresDecisionReceiptStore(db_connection)
    store.insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    with pytest.raises(CheckViolation):
        db_connection.execute(
            """
            UPDATE decision_receipts
            SET receipt_serialization_version = 2
            WHERE receipt_id = %s
            """,
            (receipt.receipt_id,),
        )
    db_connection.rollback()


def test_unknown_accepted_event_id_fails_foreign_key(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    receipt = make_admitted_receipt(uuid4())
    store = PostgresDecisionReceiptStore(db_connection)

    with pytest.raises(ForeignKeyViolation):
        store.insert(
            receipt,
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )
    db_connection.rollback()


def test_existing_accepted_event_allows_receipt_insert(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    receipt = make_admitted_receipt(accepted_event_id)

    result = PostgresDecisionReceiptStore(db_connection).insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert result.status is DecisionReceiptInsertStatus.INSERTED


def test_generic_store_does_not_revalidate_producer_order_request_correlation(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    accepted_event_id = insert_accepted_event(db_connection)
    event_row = db_connection.execute(
        """
        SELECT order_id, request_id
        FROM order_events
        WHERE accepted_event_id = %s
        """,
        (accepted_event_id,),
    ).fetchone()
    assert event_row is not None

    receipt = make_admitted_receipt(accepted_event_id)
    assert receipt.correlation.order_id != event_row[0]
    assert receipt.correlation.request_id != event_row[1]

    # The accepted-event foreign key proves event existence only. Producer
    # mappers own truthful order/request correlation. Foundational generic
    # storage does not re-evaluate producer semantics.
    result = PostgresDecisionReceiptStore(db_connection).insert(
        receipt,
        materialization_provenance=(
            DecisionReceiptMaterializationProvenance.LIVE_RESULT
        ),
    )

    assert result.status is DecisionReceiptInsertStatus.INSERTED
    assert result.record.receipt == receipt


def test_store_rejects_autocommit_connection_without_mutating_setting(
    db_connection_factory: Callable[[], Connection[object]],
    clean_database: None,
) -> None:
    connection = db_connection_factory()
    connection.rollback()
    connection.autocommit = True
    try:
        with pytest.raises(ValueError, match="autocommit must be False"):
            PostgresDecisionReceiptStore(connection)

        assert connection.autocommit is True
    finally:
        connection.close()


def test_insert_rejects_invalid_public_argument_types_before_sql(
    db_connection: Connection[object],
    clean_database: None,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)

    with pytest.raises(TypeError, match="receipt must be DecisionReceipt"):
        store.insert(
            object(),  # type: ignore[arg-type]
            materialization_provenance=(
                DecisionReceiptMaterializationProvenance.LIVE_RESULT
            ),
        )
    with pytest.raises(TypeError, match="materialization_provenance"):
        store.insert(
            make_minimal_receipt(),
            materialization_provenance="LIVE_RESULT",  # type: ignore[arg-type]
        )

    assert count_receipts(db_connection) == 0


@pytest.mark.parametrize(
    "method_name",
    [
        "load_by_receipt_id",
        "load_admitted_write_side_materialization_by_accepted_event_id",
    ],
)
def test_load_methods_reject_non_uuid_identifiers(
    db_connection: Connection[object],
    clean_database: None,
    method_name: str,
) -> None:
    store = PostgresDecisionReceiptStore(db_connection)
    method = getattr(store, method_name)

    with pytest.raises(TypeError, match="must be UUID"):
        method("not-a-uuid")
