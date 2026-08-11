from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic

import pytest
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import AdmissionVerdict
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
from src.storage.idempotency_store import (
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")


class _CheckpointRecorder:
    """Observe test-only semantic boundaries without defining trace vocabulary."""

    def __init__(
        self,
        *,
        idempotency_labels: list[str],
        history_labels: list[str],
        after_optimistic_preparation=None,
        before_pessimistic_append=None,
    ) -> None:
        self.events: list[str] = []
        self.enabled = True
        self._idempotency_labels = iter(idempotency_labels)
        self._history_labels = iter(history_labels)
        self._after_optimistic_preparation = after_optimistic_preparation
        self._before_pessimistic_append = before_pessimistic_append

    def record(self, event: str) -> None:
        if self.enabled:
            self.events.append(event)

    @contextmanager
    def paused(self):
        was_enabled = self.enabled
        self.enabled = False
        try:
            yield
        finally:
            self.enabled = was_enabled

    def install(self, monkeypatch) -> None:
        original_uow_enter = PostgresWriteSideUnitOfWork.__enter__
        original_uow_commit = PostgresWriteSideUnitOfWork.commit
        original_uow_rollback = PostgresWriteSideUnitOfWork.rollback
        original_idempotency_check = PostgresIdempotencyStore.check
        original_idempotency_record = PostgresIdempotencyStore.record
        original_history_load = PostgresEventStore.load
        original_optimistic_prepare = PostgresOptimisticAdmissionGate.prepare_stream
        original_optimistic_append = (
            PostgresOptimisticAdmissionGate.append_if_admitted
        )
        original_pessimistic_prepare = (
            PostgresPessimisticAdmissionGate.prepare_stream
        )
        original_pessimistic_append = (
            PostgresPessimisticAdmissionGate.append_if_admitted
        )

        def enter_uow(uow):
            entered_uow = original_uow_enter(uow)
            self.record("business_uow_reached")
            return entered_uow

        def commit_uow(uow):
            original_uow_commit(uow)
            self.record("clean_commit_returned")

        def rollback_uow(uow):
            original_uow_rollback(uow)
            self.record("rollback_acknowledged")

        def check_idempotency(store, signature):
            decision = original_idempotency_check(store, signature)
            if self.enabled:
                try:
                    label = next(self._idempotency_labels)
                except StopIteration as exc:
                    raise AssertionError(
                        "unexpected extra idempotency checkpoint"
                    ) from exc
                self.events.append(label)
            return decision

        def record_idempotency(store, signature, accepted_event):
            original_idempotency_record(store, signature, accepted_event)
            self.record("idempotency_persistence_completed")

        def load_history(store, order_id):
            history = original_history_load(store, order_id)
            if self.enabled:
                try:
                    label = next(self._history_labels)
                except StopIteration as exc:
                    raise AssertionError(
                        "unexpected extra accepted-history checkpoint"
                    ) from exc
                self.events.append(label)
            return history

        def prepare_optimistically(gate, order_id):
            result = original_optimistic_prepare(gate, order_id)
            self.record("optimistic_preparation_completed")
            if self.enabled and self._after_optimistic_preparation is not None:
                self._after_optimistic_preparation()
            return result

        def append_optimistically(
            gate,
            candidate_event,
            expected_current_version,
        ):
            result = original_optimistic_append(
                gate,
                candidate_event,
                expected_current_version,
            )
            self.record("append_admission_returned")
            return result

        def prepare_pessimistically(gate, order_id):
            result = original_pessimistic_prepare(gate, order_id)
            self.record("pessimistic_preparation_returned")
            return result

        def append_pessimistically(
            gate,
            candidate_event,
            expected_current_version,
        ):
            if self.enabled and self._before_pessimistic_append is not None:
                self._before_pessimistic_append()
            result = original_pessimistic_append(
                gate,
                candidate_event,
                expected_current_version,
            )
            self.record("append_admission_returned")
            return result

        monkeypatch.setattr(PostgresWriteSideUnitOfWork, "__enter__", enter_uow)
        monkeypatch.setattr(PostgresWriteSideUnitOfWork, "commit", commit_uow)
        monkeypatch.setattr(PostgresWriteSideUnitOfWork, "rollback", rollback_uow)
        monkeypatch.setattr(PostgresIdempotencyStore, "check", check_idempotency)
        monkeypatch.setattr(PostgresIdempotencyStore, "record", record_idempotency)
        monkeypatch.setattr(PostgresEventStore, "load", load_history)
        monkeypatch.setattr(
            PostgresOptimisticAdmissionGate,
            "prepare_stream",
            prepare_optimistically,
        )
        monkeypatch.setattr(
            PostgresOptimisticAdmissionGate,
            "append_if_admitted",
            append_optimistically,
        )
        monkeypatch.setattr(
            PostgresPessimisticAdmissionGate,
            "prepare_stream",
            prepare_pessimistically,
        )
        monkeypatch.setattr(
            PostgresPessimisticAdmissionGate,
            "append_if_admitted",
            append_pessimistically,
        )


class _RecordingValidationRuntime:
    def __init__(
        self,
        recorder: _CheckpointRecorder | None,
        action: EnforcementAction,
        before_decision=None,
        after_decision=None,
    ) -> None:
        self._recorder = recorder
        self._action = action
        self._before_decision = before_decision
        self._after_decision = after_decision

    def decide(self, candidate_event, context):
        if self._before_decision is not None:
            self._before_decision()

        verdict = (
            ValidationVerdict.PASSED
            if self._action == EnforcementAction.ALLOW
            else ValidationVerdict.FAILED
        )
        decision = ValidationDecision(
            action=self._action,
            validation_result=ValidationResult(
                verdict=verdict,
                reason="Characterization validation decision",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )

        if self._recorder is not None:
            self._recorder.record("validation_completed")

        if self._after_decision is not None:
            self._after_decision()

        return decision


class _UnexpectedValidationRuntime:
    def decide(self, candidate_event, context):
        raise AssertionError("validation must not be reached")


POLL_TIMEOUT_SECONDS = 5.0


class _RollbackAfterAppend(RuntimeError):
    """Test-only sentinel used to force owner rollback after a real event INSERT."""


class _PostAppendPauseOptimisticGate:
    """Pause after a real optimistic append returns but before UOW finalization."""

    def __init__(
        self,
        delegate: PostgresOptimisticAdmissionGate,
        *,
        append_returned: Event,
        release_owner: Event,
        rollback_after_release: bool,
    ) -> None:
        self._delegate = delegate
        self._append_returned = append_returned
        self._release_owner = release_owner
        self._rollback_after_release = rollback_after_release

    def prepare_stream(self, order_id):
        return self._delegate.prepare_stream(order_id)

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version,
    ):
        result = self._delegate.append_if_admitted(
            candidate_event,
            expected_current_version,
        )
        if result.verdict != AdmissionVerdict.ADMITTED:
            raise AssertionError(
                "owner append must succeed before the uncommitted-position pause"
            )

        self._append_returned.set()
        assert self._release_owner.wait(
            POLL_TIMEOUT_SECONDS
        ), "owner was not released after its append returned"

        if self._rollback_after_release:
            raise _RollbackAfterAppend(
                "force rollback after append returned but before commit"
            )

        return result


def _post_append_pause_gate_factory(
    *,
    append_returned: Event,
    release_owner: Event,
    rollback_after_release: bool,
):
    def factory(uow):
        return _PostAppendPauseOptimisticGate(
            PostgresOptimisticAdmissionGate(uow.event_store),
            append_returned=append_returned,
            release_owner=release_owner,
            rollback_after_release=rollback_after_release,
        )

    return factory


def _configure_read_committed(connection) -> None:
    connection.rollback()
    connection.isolation_level = IsolationLevel.READ_COMMITTED


def _start_create(
    write_side: PostgresTransactionalWriteSide,
    *,
    request_id: str,
    order_id: str,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def run_create() -> None:
        try:
            result = write_side.create_order(
                request_id=request_id,
                order_id=order_id,
                amount=Decimal("100.00"),
            )
        except BaseException as error:
            outcome.put(error)
        else:
            outcome.put(result)
        finally:
            finished.set()

    thread = Thread(target=run_create, daemon=True)
    thread.start()
    return thread, finished, outcome


def _await_thread_outcome(
    thread: Thread,
    finished: Event,
    outcome: Queue[object],
    *,
    timeout_seconds: float = POLL_TIMEOUT_SECONDS,
) -> object:
    assert finished.wait(timeout_seconds), "write-side worker did not finish"
    thread.join(timeout=1.0)
    assert not thread.is_alive(), "write-side worker thread remained alive"

    try:
        return outcome.get_nowait()
    except Empty as error:
        raise AssertionError("write-side worker produced no outcome") from error


def _wait_for_backend_lock(
    observer,
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
            last_wait_state = (row[0], row[1])
            if row[0] == "Lock":
                return

        if finished.wait(0.01):
            raise AssertionError(
                "contender completed before reaching a PostgreSQL Lock wait"
            )

    raise AssertionError(
        "contender did not reach a PostgreSQL Lock wait; "
        f"last wait state was {last_wait_state}"
    )


def _build_write_side(
    connection,
    *,
    placement: ValidationPlacement,
    validation_runtime,
    admission_gate_factory=None,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=admission_gate_factory,
        config=PostgresWriteSideConfig(validation_placement=placement),
    )


def _pessimistic_gate_factory(uow):
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def _accept_create(
    connection,
    *,
    request_id: str,
    order_id: str,
    amount: Decimal = Decimal("100.00"),
):
    write_side = _build_write_side(
        connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
    )
    return write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=amount,
    )


def _assert_idle_and_reusable(connection) -> None:
    """Prove one producer connection is clean and reusable after finalization."""
    assert connection.info.transaction_status is TransactionStatus.IDLE
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
    connection.rollback()
    assert connection.info.transaction_status is TransactionStatus.IDLE


def _accept_in_pessimistic_create(
    connection,
    *,
    request_id: str,
    order_id: str,
):
    write_side = _build_write_side(
        connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )
    return write_side.create_order(
        request_id=request_id,
        order_id=order_id,
        amount=Decimal("100.00"),
    )


def test_pre_validation_block_stops_before_business_uow_and_admission(
    db_connection,
    monkeypatch,
):
    recorder = _CheckpointRecorder(
        idempotency_labels=["preliminary_idempotency_completed"],
        history_labels=["preliminary_history_observed"],
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.BLOCK,
        ),
    )

    result = write_side.create_order(
        request_id="pre-block-request",
        order_id="pre-block-order",
        amount=Decimal("100.00"),
    )

    assert recorder.events == [
        "preliminary_idempotency_completed",
        "preliminary_history_observed",
        "validation_completed",
    ]
    assert result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is None
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.BLOCK
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_pre_authoritative_replay_occurs_after_validation_and_business_uow(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    recorder = _CheckpointRecorder(
        idempotency_labels=[
            "preliminary_idempotency_completed",
            "authoritative_idempotency_completed",
        ],
        history_labels=["preliminary_history_observed"],
    )

    def accept_same_request_during_validation():
        with recorder.paused():
            concurrent_results.append(
                _accept_create(
                    concurrent_connection,
                    request_id="pre-authoritative-replay-request",
                    order_id="pre-authoritative-replay-order",
                )
            )

    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
            before_decision=accept_same_request_during_validation,
        ),
    )

    try:
        result = write_side.create_order(
            request_id="pre-authoritative-replay-request",
            order_id="pre-authoritative-replay-order",
            amount=Decimal("100.00"),
        )
    finally:
        concurrent_connection.close()

    assert recorder.events == [
        "preliminary_idempotency_completed",
        "preliminary_history_observed",
        "validation_completed",
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "rollback_acknowledged",
    ]
    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome == PostgresWriteSideOutcome.REPLAY
    assert result.idempotency_decision.verdict == IdempotencyVerdict.REPLAY
    assert result.accepted_event == concurrent_results[0].accepted_event
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.stream_admission_result is None
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_pre_authoritative_conflict_occurs_after_validation_and_business_uow(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    request_id = "pre-authoritative-conflict-request"
    order_id = "pre-authoritative-conflict-order"
    winning_amount = Decimal("999.00")
    losing_amount = Decimal("100.00")
    recorder = _CheckpointRecorder(
        idempotency_labels=[
            "preliminary_idempotency_completed",
            "authoritative_idempotency_completed",
        ],
        history_labels=["preliminary_history_observed"],
    )

    def accept_conflicting_request_during_validation():
        with recorder.paused():
            concurrent_results.append(
                _accept_create(
                    concurrent_connection,
                    request_id=request_id,
                    order_id=order_id,
                    amount=winning_amount,
                )
            )
            _assert_idle_and_reusable(concurrent_connection)

    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
            before_decision=accept_conflicting_request_during_validation,
        ),
    )

    try:
        result = write_side.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=losing_amount,
        )
    finally:
        concurrent_connection.close()

    assert db_connection.info.transaction_status is TransactionStatus.IDLE
    assert recorder.events == [
        "preliminary_idempotency_completed",
        "preliminary_history_observed",
        "validation_completed",
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "rollback_acknowledged",
    ]
    assert len(concurrent_results) == 1
    winning_result = concurrent_results[0]
    assert winning_result.outcome == PostgresWriteSideOutcome.ACCEPTED
    assert winning_result.accepted_event is not None
    assert winning_result.accepted_event.amount == winning_amount

    assert isinstance(result, PostgresWriteSideResult)
    assert result.outcome == PostgresWriteSideOutcome.CONFLICT
    assert result.idempotency_decision.verdict == IdempotencyVerdict.CONFLICT
    assert result.accepted_event is None
    assert result.idempotency_decision.record is not None
    assert (
        result.idempotency_decision.record.accepted_event
        == winning_result.accepted_event
    )
    assert result.idempotency_decision.record.signature.amount == winning_amount
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.stream_admission_result is None
    assert result.admission_result is None

    losing_candidate_id = (
        result.validation_decision.validation_result.candidate_event_id
    )
    with recorder.paused():
        durable_events = PostgresEventStore(db_connection).load(order_id)
        winning_replay = PostgresIdempotencyStore(db_connection).check(
            RequestSignature(
                request_id=request_id,
                command_type=CommandType.CREATE,
                order_id=order_id,
                amount=winning_amount,
            )
        )
        losing_conflict = PostgresIdempotencyStore(db_connection).check(
            RequestSignature(
                request_id=request_id,
                command_type=CommandType.CREATE,
                order_id=order_id,
                amount=losing_amount,
            )
        )

    assert durable_events == [winning_result.accepted_event]
    assert all(event.event_id != losing_candidate_id for event in durable_events)
    assert winning_replay.verdict == IdempotencyVerdict.REPLAY
    assert winning_replay.record is not None
    assert winning_replay.record.accepted_event == winning_result.accepted_event
    assert losing_conflict.verdict == IdempotencyVerdict.CONFLICT
    assert losing_conflict.record is not None
    assert losing_conflict.record.accepted_event == winning_result.accepted_event
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
    db_connection.rollback()
    _assert_idle_and_reusable(db_connection)


def test_pre_occ_conflict_stops_after_one_append_without_reload_or_retry(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    recorder = _CheckpointRecorder(
        idempotency_labels=[
            "preliminary_idempotency_completed",
            "authoritative_idempotency_completed",
        ],
        history_labels=["preliminary_history_observed"],
    )

    def accept_competing_create_after_optimistic_preparation():
        with recorder.paused():
            concurrent_results.append(
                _accept_create(
                    concurrent_connection,
                    request_id="competing-occ-request",
                    order_id="pre-occ-order",
                )
            )

    recorder._after_optimistic_preparation = (
        accept_competing_create_after_optimistic_preparation
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
        ),
    )

    try:
        result = write_side.create_order(
            request_id="pre-occ-request",
            order_id="pre-occ-order",
            amount=Decimal("100.00"),
        )
    finally:
        concurrent_connection.close()

    assert recorder.events == [
        "preliminary_idempotency_completed",
        "preliminary_history_observed",
        "validation_completed",
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "optimistic_preparation_completed",
        "append_admission_returned",
        "rollback_acknowledged",
    ]
    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict == AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict == AdmissionVerdict.STALE_WRITE
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_in_transaction_concrete_pessimistic_accepts_in_bounded_order(
    db_connection,
    monkeypatch,
):
    recorder = _CheckpointRecorder(
        idempotency_labels=["authoritative_idempotency_completed"],
        history_labels=["protected_history_observed"],
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    result = write_side.create_order(
        request_id="in-pessimistic-accepted-request",
        order_id="in-pessimistic-accepted-order",
        amount=Decimal("100.00"),
    )

    assert recorder.events == [
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "pessimistic_preparation_returned",
        "protected_history_observed",
        "validation_completed",
        "append_admission_returned",
        "idempotency_persistence_completed",
        "clean_commit_returned",
    ]
    assert result.outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict == AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict == AdmissionVerdict.ADMITTED
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_in_transaction_concrete_pessimistic_lock_non_acquisition_stops_early(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    order_id = "in-pessimistic-locked-order"
    locker_connection = db_connection_factory()
    locker_gate = PostgresPessimisticAdmissionGate(
        connection=locker_connection,
        event_store=PostgresEventStore(locker_connection),
    )
    locker_result = locker_gate.prepare_stream(order_id)
    assert locker_result.verdict == AdmissionVerdict.ADMITTED

    recorder = _CheckpointRecorder(
        idempotency_labels=["authoritative_idempotency_completed"],
        history_labels=[],
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_UnexpectedValidationRuntime(),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    try:
        result = write_side.create_order(
            request_id="in-pessimistic-locked-request",
            order_id=order_id,
            amount=Decimal("100.00"),
        )
    finally:
        locker_connection.rollback()
        locker_connection.close()

    assert recorder.events == [
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "pessimistic_preparation_returned",
        "rollback_acknowledged",
    ]
    assert result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict == AdmissionVerdict.LOCK_TIMEOUT
    assert result.validation_decision is None
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_in_transaction_concrete_pessimistic_validation_block_stops_before_append(
    db_connection,
    monkeypatch,
):
    recorder = _CheckpointRecorder(
        idempotency_labels=["authoritative_idempotency_completed"],
        history_labels=["protected_history_observed"],
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.BLOCK,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    result = write_side.create_order(
        request_id="in-pessimistic-block-request",
        order_id="in-pessimistic-block-order",
        amount=Decimal("100.00"),
    )

    assert recorder.events == [
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "pessimistic_preparation_returned",
        "protected_history_observed",
        "validation_completed",
        "rollback_acknowledged",
    ]
    assert result.outcome == PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict == AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.BLOCK
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 0
    assert count_rows(db_connection, "idempotency_records") == 0


def test_mixed_in_pessimistic_stale_after_pre_optimistic_commits_before_append(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    request_id = "mixed-in-stale-request"
    order_id = "mixed-in-stale-order"
    recorder = _CheckpointRecorder(
        idempotency_labels=["authoritative_idempotency_completed"],
        history_labels=["protected_history_observed"],
    )

    def accept_same_request_before_pessimistic_append():
        with recorder.paused():
            concurrent_results.append(
                _accept_create(
                    concurrent_connection,
                    request_id=request_id,
                    order_id=order_id,
                )
            )

    recorder._before_pessimistic_append = (
        accept_same_request_before_pessimistic_append
    )
    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_pessimistic_gate_factory,
    )

    try:
        result = write_side.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
    finally:
        concurrent_connection.close()

    assert recorder.events == [
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "pessimistic_preparation_returned",
        "protected_history_observed",
        "validation_completed",
        "append_admission_returned",
        "rollback_acknowledged",
    ]
    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome == PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.idempotency_decision.verdict == IdempotencyVerdict.MISS
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict == AdmissionVerdict.ADMITTED
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.admission_result is not None
    assert result.admission_result.verdict == AdmissionVerdict.STALE_WRITE
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_mixed_pre_authoritative_replay_after_in_pessimistic_commits_before_uow(
    db_connection,
    db_connection_factory,
    monkeypatch,
):
    concurrent_connection = db_connection_factory()
    concurrent_results = []
    request_id = "mixed-pre-replay-request"
    order_id = "mixed-pre-replay-order"
    recorder = _CheckpointRecorder(
        idempotency_labels=[
            "preliminary_idempotency_completed",
            "authoritative_idempotency_completed",
        ],
        history_labels=["preliminary_history_observed"],
    )

    def accept_same_request_after_pre_validation():
        with recorder.paused():
            concurrent_results.append(
                _accept_in_pessimistic_create(
                    concurrent_connection,
                    request_id=request_id,
                    order_id=order_id,
                )
            )

    recorder.install(monkeypatch)
    write_side = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=recorder,
            action=EnforcementAction.ALLOW,
            after_decision=accept_same_request_after_pre_validation,
        ),
    )

    try:
        result = write_side.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
    finally:
        concurrent_connection.close()

    assert recorder.events == [
        "preliminary_idempotency_completed",
        "preliminary_history_observed",
        "validation_completed",
        "business_uow_reached",
        "authoritative_idempotency_completed",
        "rollback_acknowledged",
    ]
    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome == PostgresWriteSideOutcome.ACCEPTED
    assert result.outcome == PostgresWriteSideOutcome.REPLAY
    assert result.idempotency_decision.verdict == IdempotencyVerdict.REPLAY
    assert result.accepted_event == concurrent_results[0].accepted_event
    assert result.validation_decision is not None
    assert result.validation_decision.action == EnforcementAction.ALLOW
    assert result.stream_admission_result is None
    assert result.admission_result is None
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_uncommitted_stream_position_commit_makes_waiting_writer_stale(
    db_connection,
    db_connection_factory,
):
    owner_connection = db_connection_factory()
    contender_connection = db_connection_factory()
    append_returned = Event()
    release_owner = Event()
    contender_thread: Thread | None = None
    contender_finished: Event | None = None

    _configure_read_committed(db_connection)
    _configure_read_committed(owner_connection)
    _configure_read_committed(contender_connection)

    order_id = "uncommitted-position-commit-order"
    owner_write_side = _build_write_side(
        owner_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_post_append_pause_gate_factory(
            append_returned=append_returned,
            release_owner=release_owner,
            rollback_after_release=False,
        ),
    )
    contender_write_side = _build_write_side(
        contender_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
    )

    owner_thread, owner_finished, owner_outcome = _start_create(
        owner_write_side,
        request_id="uncommitted-position-owner-request",
        order_id=order_id,
    )

    try:
        assert append_returned.wait(
            POLL_TIMEOUT_SECONDS
        ), "owner never reached the post-append uncommitted pause"

        observer_store = PostgresEventStore(db_connection)
        assert observer_store.load(order_id) == []

        contender_backend_pid = contender_connection.info.backend_pid
        contender_thread, contender_finished, contender_outcome = _start_create(
            contender_write_side,
            request_id="uncommitted-position-contender-request",
            order_id=order_id,
        )

        _wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=contender_finished,
        )
        assert not contender_finished.is_set()

        release_owner.set()

        observed_owner = _await_thread_outcome(
            owner_thread,
            owner_finished,
            owner_outcome,
        )
        observed_contender = _await_thread_outcome(
            contender_thread,
            contender_finished,
            contender_outcome,
        )

        assert isinstance(observed_owner, PostgresWriteSideResult)
        assert observed_owner.outcome == PostgresWriteSideOutcome.ACCEPTED

        assert isinstance(observed_contender, PostgresWriteSideResult)
        assert (
            observed_contender.outcome
            == PostgresWriteSideOutcome.ADMISSION_REJECTED
        )
        assert (
            observed_contender.idempotency_decision.verdict
            == IdempotencyVerdict.MISS
        )
        assert observed_contender.stream_admission_result is not None
        assert (
            observed_contender.stream_admission_result.verdict
            == AdmissionVerdict.ADMITTED
        )
        assert observed_contender.admission_result is not None
        assert (
            observed_contender.admission_result.verdict
            == AdmissionVerdict.STALE_WRITE
        )

        db_connection.rollback()
        committed_history = PostgresEventStore(db_connection).load(order_id)
        assert committed_history == [observed_owner.accepted_event]
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
    finally:
        release_owner.set()

        if owner_thread.is_alive():
            owner_finished.wait(POLL_TIMEOUT_SECONDS)
            owner_thread.join(timeout=1.0)

        if (
            contender_thread is not None
            and contender_finished is not None
            and contender_thread.is_alive()
        ):
            contender_finished.wait(POLL_TIMEOUT_SECONDS)
            contender_thread.join(timeout=1.0)

        owner_connection.rollback()
        owner_connection.close()
        contender_connection.rollback()
        contender_connection.close()



def test_uncommitted_stream_position_rollback_allows_waiting_writer_to_commit(
    db_connection,
    db_connection_factory,
):
    owner_connection = db_connection_factory()
    contender_connection = db_connection_factory()
    append_returned = Event()
    release_owner = Event()
    contender_thread: Thread | None = None
    contender_finished: Event | None = None

    _configure_read_committed(db_connection)
    _configure_read_committed(owner_connection)
    _configure_read_committed(contender_connection)

    order_id = "uncommitted-position-rollback-order"
    owner_write_side = _build_write_side(
        owner_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
        admission_gate_factory=_post_append_pause_gate_factory(
            append_returned=append_returned,
            release_owner=release_owner,
            rollback_after_release=True,
        ),
    )
    contender_write_side = _build_write_side(
        contender_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=_RecordingValidationRuntime(
            recorder=None,
            action=EnforcementAction.ALLOW,
        ),
    )

    owner_thread, owner_finished, owner_outcome = _start_create(
        owner_write_side,
        request_id="uncommitted-position-rollback-owner-request",
        order_id=order_id,
    )

    try:
        assert append_returned.wait(
            POLL_TIMEOUT_SECONDS
        ), "owner never reached the post-append uncommitted pause"

        observer_store = PostgresEventStore(db_connection)
        assert observer_store.load(order_id) == []

        contender_backend_pid = contender_connection.info.backend_pid
        contender_thread, contender_finished, contender_outcome = _start_create(
            contender_write_side,
            request_id="uncommitted-position-rollback-contender-request",
            order_id=order_id,
        )

        _wait_for_backend_lock(
            db_connection,
            backend_pid=contender_backend_pid,
            finished=contender_finished,
        )
        assert not contender_finished.is_set()

        release_owner.set()

        observed_owner = _await_thread_outcome(
            owner_thread,
            owner_finished,
            owner_outcome,
        )
        observed_contender = _await_thread_outcome(
            contender_thread,
            contender_finished,
            contender_outcome,
        )

        assert isinstance(observed_owner, _RollbackAfterAppend)

        assert isinstance(observed_contender, PostgresWriteSideResult)
        assert observed_contender.outcome == PostgresWriteSideOutcome.ACCEPTED
        assert (
            observed_contender.idempotency_decision.verdict
            == IdempotencyVerdict.MISS
        )
        assert observed_contender.stream_admission_result is not None
        assert (
            observed_contender.stream_admission_result.verdict
            == AdmissionVerdict.ADMITTED
        )
        assert observed_contender.admission_result is not None
        assert (
            observed_contender.admission_result.verdict
            == AdmissionVerdict.ADMITTED
        )

        db_connection.rollback()
        committed_history = PostgresEventStore(db_connection).load(order_id)
        assert committed_history == [observed_contender.accepted_event]
        assert count_rows(db_connection, "order_events") == 1
        assert count_rows(db_connection, "idempotency_records") == 1
    finally:
        release_owner.set()

        if owner_thread.is_alive():
            owner_finished.wait(POLL_TIMEOUT_SECONDS)
            owner_thread.join(timeout=1.0)

        if (
            contender_thread is not None
            and contender_finished is not None
            and contender_thread.is_alive()
        ):
            contender_finished.wait(POLL_TIMEOUT_SECONDS)
            contender_thread.join(timeout=1.0)

        owner_connection.rollback()
        owner_connection.close()
        contender_connection.rollback()
        contender_connection.close()
