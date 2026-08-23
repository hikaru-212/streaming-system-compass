"""Experimental PostgreSQL resolution-boundary characterizations.

These tests deliberately model A3 outside the production PR2 invocation owner.
They neither extend that owner nor introduce a production retry lifecycle.
"""

from __future__ import annotations

from decimal import Decimal
from queue import Empty, Queue
from threading import Event, Thread

import pytest
from psycopg.pq import TransactionStatus

from src.compass.runtime.postgres_write_side_reinvocation_authority import (
    evaluate_postgres_write_side_reinvocation_authority,
)
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    ConcurrencyGate,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresPessimisticAdmissionGate,
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
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideInvocationLifecycleError,
    PostgresWriteSideInvocationOwner,
)
from src.storage.idempotency_store import (
    IdempotencyVerdict,
    RequestSignature,
)
from src.storage.postgres_event_store import PostgresEventStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")

AMOUNT = Decimal("100.00")
WAIT_SECONDS = 5.0


class _CountingAllowValidationRuntime:
    """Return real writer-compatible allow decisions and count invocations."""

    def __init__(self) -> None:
        self.call_count = 0

    def decide(self, candidate_event, context) -> ValidationDecision:
        self.call_count += 1
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="Experimental resolution-boundary validation allowed",
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


class _PauseAfterPessimisticLockGate:
    """Pause B after the real transaction-scoped advisory lock is acquired."""

    def __init__(
        self,
        delegate: PostgresPessimisticAdmissionGate,
        *,
        acquired: Event,
        release: Event,
    ) -> None:
        self._delegate = delegate
        self._acquired = acquired
        self._release = release

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        result = self._delegate.prepare_stream(order_id)
        if result.verdict is not AdmissionVerdict.ADMITTED:
            raise AssertionError("B did not acquire the advisory lock")

        self._acquired.set()
        if not self._release.wait(WAIT_SECONDS):
            raise AssertionError("the experiment did not release B")
        return result

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version: int,
    ) -> AdmissionResult:
        return self._delegate.append_if_admitted(
            candidate_event,
            expected_current_version,
        )


def _pessimistic_gate_factory(uow) -> ConcurrencyGate:
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def _pausing_pessimistic_gate_factory(
    *,
    acquired: Event,
    release: Event,
):
    def factory(uow) -> ConcurrencyGate:
        return _PauseAfterPessimisticLockGate(
            PostgresPessimisticAdmissionGate(
                connection=uow.connection,
                event_store=uow.event_store,
            ),
            acquired=acquired,
            release=release,
        )

    return factory


def _writer(
    connection,
    validation_runtime: _CountingAllowValidationRuntime,
    *,
    admission_gate_factory=_pessimistic_gate_factory,
) -> PostgresTransactionalWriteSide:
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=admission_gate_factory,
        config=PostgresWriteSideConfig(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
        ),
    )


def _signature(name: str) -> RequestSignature:
    return RequestSignature(
        request_id=f"stage4e-successive-request-{name}",
        command_type=CommandType.CREATE,
        order_id=f"stage4e-successive-order-{name}",
        amount=AMOUNT,
    )


def _invoke_signature(
    writer: PostgresTransactionalWriteSide,
    signature: RequestSignature,
) -> PostgresWriteSideResult:
    if signature.command_type is CommandType.CREATE:
        return writer.create_order(
            request_id=signature.request_id,
            order_id=signature.order_id,
            amount=signature.amount,
        )
    if signature.command_type is CommandType.PAY:
        return writer.pay_order(
            request_id=signature.request_id,
            order_id=signature.order_id,
            amount=signature.amount,
        )
    raise AssertionError(
        f"unsupported experimental command type: {signature.command_type!r}"
    )


def _invoke_one_experimental_a3(
    writer: PostgresTransactionalWriteSide,
    fresh_a2_authority: ReinvocationAuthorization,
) -> PostgresWriteSideResult:
    """Schedule one A3 from A2-derived authority, without a retry loop."""

    return _invoke_signature(writer, fresh_a2_authority.request_signature)


def _start_holder(
    writer: PostgresTransactionalWriteSide,
    signature: RequestSignature,
) -> tuple[Thread, Event, Queue[object]]:
    finished = Event()
    outcome: Queue[object] = Queue(maxsize=1)

    def run() -> None:
        try:
            outcome.put(_invoke_signature(writer, signature))
        except BaseException as error:
            outcome.put(error)
        finally:
            finished.set()

    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread, finished, outcome


def _await_holder(
    thread: Thread,
    finished: Event,
    outcome: Queue[object],
) -> PostgresWriteSideResult:
    assert finished.wait(WAIT_SECONDS), "B did not finish after release"
    thread.join(timeout=WAIT_SECONDS)
    assert not thread.is_alive(), "B thread remained alive after completion"
    try:
        observed = outcome.get_nowait()
    except Empty as error:
        raise AssertionError("B produced no outcome") from error
    if isinstance(observed, BaseException):
        raise observed
    assert isinstance(observed, PostgresWriteSideResult)
    return observed


def _assert_preparation_lock_timeout(
    result: PostgresWriteSideResult,
    signature: RequestSignature,
) -> None:
    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert result.accepted_event is None
    assert result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert result.idempotency_decision.record is None
    assert result.stream_admission_result is not None
    assert (
        result.stream_admission_result.verdict
        is AdmissionVerdict.LOCK_TIMEOUT
    )
    assert result.stream_admission_result.order_id == signature.order_id
    assert result.validation_decision is None
    assert result.validation_decision_evidence is None
    assert result.admission_result is None


def _assert_fresh_a2_authority(
    *,
    signature: RequestSignature,
    a1_authority: ReinvocationAuthorization,
    a2_result: PostgresWriteSideResult,
) -> ReinvocationAuthorization:
    a2_authority = evaluate_postgres_write_side_reinvocation_authority(
        request_signature=signature,
        result=a2_result,
    )
    assert isinstance(a2_authority, ReinvocationAuthorization)
    assert a2_authority is not a1_authority
    assert a2_authority.request_signature is signature
    return a2_authority


def test_a3_after_holder_rollback_observes_fresh_accepted_state(
    db_connection,
    db_connection_factory,
) -> None:
    """A3 crosses confirmed B rollback and follows the normal accepted path."""

    signature = _signature("rollback")
    actor_validation = _CountingAllowValidationRuntime()
    actor_writer = _writer(db_connection, actor_validation)
    actor_owner = PostgresWriteSideInvocationOwner(
        request_signature=signature,
        writer=actor_writer,
    )
    holder_connection = db_connection_factory()
    holder_gate = PostgresPessimisticAdmissionGate(
        connection=holder_connection,
        event_store=PostgresEventStore(holder_connection),
    )

    try:
        holder_preparation = holder_gate.prepare_stream(signature.order_id)
        assert holder_preparation.verdict is AdmissionVerdict.ADMITTED
        assert (
            holder_connection.info.transaction_status
            is TransactionStatus.INTRANS
        )

        # A1 executes only after B's lock acquisition is confirmed.
        a1_result = actor_owner.invoke_initial()
        _assert_preparation_lock_timeout(a1_result, signature)
        assert (
            holder_connection.info.transaction_status
            is TransactionStatus.INTRANS
        )

        a1_authority = actor_owner.evaluate_reinvocation_authority()
        assert isinstance(a1_authority, ReinvocationAuthorization)
        assert a1_authority.request_signature is signature

        # A2 spends only A1-derived authority while B remains unresolved.
        a2_result = actor_owner.invoke_authorized_reinvocation()
        _assert_preparation_lock_timeout(a2_result, signature)
        assert (
            holder_connection.info.transaction_status
            is TransactionStatus.INTRANS
        )

        # The possible A3 authority is independently derived from fresh A2.
        a2_authority = _assert_fresh_a2_authority(
            signature=signature,
            a1_authority=a1_authority,
            a2_result=a2_result,
        )
        with pytest.raises(
            PostgresWriteSideInvocationLifecycleError,
            match="already been spent",
        ):
            actor_owner.invoke_authorized_reinvocation()

        # B is synchronously rolled back and confirmed terminated before A3.
        holder_connection.rollback()
        assert (
            holder_connection.info.transaction_status
            is TransactionStatus.IDLE
        )

        a3_result = _invoke_one_experimental_a3(actor_writer, a2_authority)
    finally:
        holder_connection.rollback()
        holder_connection.close()

    assert a3_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert a3_result.accepted_event is not None
    assert a3_result.idempotency_decision.verdict is IdempotencyVerdict.MISS
    assert a3_result.stream_admission_result is not None
    assert (
        a3_result.stream_admission_result.verdict
        is AdmissionVerdict.ADMITTED
    )
    assert a3_result.validation_decision is not None
    assert a3_result.validation_decision.action is EnforcementAction.ALLOW
    assert a3_result.admission_result is not None
    assert a3_result.admission_result.verdict is AdmissionVerdict.ADMITTED
    assert actor_validation.call_count == 1
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1


def test_a3_after_same_request_holder_commit_observes_real_replay(
    db_connection,
    db_connection_factory,
) -> None:
    """A3 crosses confirmed B commit and resolves through real idempotency."""

    signature = _signature("same-request-commit")
    acquired = Event()
    release = Event()
    holder_validation = _CountingAllowValidationRuntime()
    actor_validation = _CountingAllowValidationRuntime()
    holder_connection = db_connection_factory()
    holder_writer = _writer(
        holder_connection,
        holder_validation,
        admission_gate_factory=_pausing_pessimistic_gate_factory(
            acquired=acquired,
            release=release,
        ),
    )
    actor_writer = _writer(db_connection, actor_validation)
    actor_owner = PostgresWriteSideInvocationOwner(
        request_signature=signature,
        writer=actor_writer,
    )
    holder_thread, holder_finished, holder_outcome = _start_holder(
        holder_writer,
        signature,
    )

    try:
        assert acquired.wait(WAIT_SECONDS), "B never acquired the real lock"
        assert not release.is_set()
        assert not holder_finished.is_set()

        # B is paused after lock acquisition throughout both early attempts.
        a1_result = actor_owner.invoke_initial()
        _assert_preparation_lock_timeout(a1_result, signature)
        assert not release.is_set()
        assert not holder_finished.is_set()

        a1_authority = actor_owner.evaluate_reinvocation_authority()
        assert isinstance(a1_authority, ReinvocationAuthorization)
        assert a1_authority.request_signature is signature

        a2_result = actor_owner.invoke_authorized_reinvocation()
        _assert_preparation_lock_timeout(a2_result, signature)
        assert not release.is_set()
        assert not holder_finished.is_set()

        a2_authority = _assert_fresh_a2_authority(
            signature=signature,
            a1_authority=a1_authority,
            a2_result=a2_result,
        )
        assert actor_validation.call_count == 0

        # B is explicitly released and its real commit completes before A3.
        release.set()
        holder_result = _await_holder(
            holder_thread,
            holder_finished,
            holder_outcome,
        )
        assert holder_result.outcome is PostgresWriteSideOutcome.ACCEPTED
        assert holder_result.accepted_event is not None
        assert (
            holder_connection.info.transaction_status
            is TransactionStatus.IDLE
        )

        a3_result = _invoke_one_experimental_a3(actor_writer, a2_authority)
    finally:
        release.set()
        if holder_thread.is_alive():
            holder_finished.wait(WAIT_SECONDS)
            holder_thread.join(timeout=WAIT_SECONDS)
        holder_connection.rollback()
        holder_connection.close()

    assert a3_result.outcome is PostgresWriteSideOutcome.REPLAY
    assert a3_result.idempotency_decision.verdict is IdempotencyVerdict.REPLAY
    replay_record = a3_result.idempotency_decision.record
    assert replay_record is not None
    assert replay_record.signature == signature
    assert replay_record.accepted_event == holder_result.accepted_event
    assert a3_result.accepted_event == holder_result.accepted_event
    assert a3_result.stream_admission_result is None
    assert a3_result.validation_decision is None
    assert a3_result.admission_result is None
    assert holder_validation.call_count == 1
    assert actor_validation.call_count == 0
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
