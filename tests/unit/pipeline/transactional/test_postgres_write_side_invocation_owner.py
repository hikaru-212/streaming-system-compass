from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from inspect import signature as inspect_signature
from threading import Barrier, Event, Lock
from typing import cast

import pytest

from src.compass.runtime.reinvocation_authority import (
    NoReinvocationAuthority,
    ReinvocationAuthorization,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideInvocationLifecycleError,
    PostgresWriteSideInvocationOwner,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


WAIT_SECONDS = 2.0


class _A2SentinelError(Exception):
    pass


class _SequencedWriteSide(PostgresTransactionalWriteSide):
    """Bounded public-writer subclass with deterministic invocation results."""

    def __init__(
        self,
        outcomes: list[PostgresWriteSideResult | BaseException],
        *,
        block_on_call: int | None = None,
    ) -> None:
        self._outcomes = outcomes
        self._block_on_call = block_on_call
        self._calls_lock = Lock()
        self.calls: list[tuple[CommandType, str, str, Decimal]] = []
        self.blocked_entry = Event()
        self.release_blocked_call = Event()

    def create_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._record_and_return(
            command_type=CommandType.CREATE,
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )

    def pay_order(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        return self._record_and_return(
            command_type=CommandType.PAY,
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )

    def _record_and_return(
        self,
        *,
        command_type: CommandType,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> PostgresWriteSideResult:
        with self._calls_lock:
            self.calls.append((command_type, request_id, order_id, amount))
            call_number = len(self.calls)

        if call_number > len(self._outcomes):
            raise AssertionError("unexpected public-writer entry")

        if call_number == self._block_on_call:
            self.blocked_entry.set()
            if not self.release_blocked_call.wait(WAIT_SECONDS):
                raise AssertionError(
                    "test did not release blocked writer call"
                )

        outcome = self._outcomes[call_number - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _signature(
    *, command_type: CommandType = CommandType.CREATE
) -> RequestSignature:
    return RequestSignature(
        request_id="stage4e-pr2-request",
        command_type=command_type,
        order_id="stage4e-pr2-order",
        amount=Decimal("100.00"),
    )


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="test-owned miss",
        record=None,
    )


def _positive_result(signature: RequestSignature) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason="test-owned preparation timeout",
            order_id=signature.order_id,
        ),
        validation_decision=None,
        validation_decision_evidence=None,
        admission_result=None,
    )


def _accepted_result(signature: RequestSignature) -> PostgresWriteSideResult:
    event = OrderAggregate(signature.order_id).create(
        signature.request_id,
        signature.amount,
    )
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ACCEPTED,
        accepted_event=event,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned stream admission",
            order_id=signature.order_id,
        ),
        validation_decision=_allowing_validation_decision(event.event_id),
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned append admission",
            candidate_event_id=event.event_id,
            accepted_event_id=event.event_id,
        ),
    )


def _allowing_validation_decision(
    candidate_event_id: str,
) -> ValidationDecision:
    return ValidationDecision(
        action=EnforcementAction.ALLOW,
        validation_result=ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="test-owned validation allowed",
            candidate_event_id=candidate_event_id,
            validator_name="stage4e-pr2-test",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
        ),
    )


def _owner(
    signature: RequestSignature,
    writer: PostgresTransactionalWriteSide,
) -> PostgresWriteSideInvocationOwner:
    return PostgresWriteSideInvocationOwner(
        request_signature=signature,
        writer=writer,
    )


@pytest.mark.parametrize(
    ("request_signature", "expected_message"),
    [
        pytest.param(object(), "request_signature must be RequestSignature"),
        pytest.param(
            replace(_signature(), request_id=object()),
            "request_signature.request_id must be str",
        ),
        pytest.param(
            replace(_signature(), command_type=object()),
            "request_signature.command_type must be CommandType",
        ),
        pytest.param(
            replace(_signature(), order_id=object()),
            "request_signature.order_id must be str",
        ),
        pytest.param(
            replace(_signature(), amount=object()),
            "request_signature.amount must be Decimal",
        ),
    ],
)
def test_constructor_requires_complete_structural_request_signature(
    request_signature,
    expected_message: str,
) -> None:
    writer = _SequencedWriteSide([])

    with pytest.raises(TypeError, match=expected_message):
        PostgresWriteSideInvocationOwner(
            request_signature=request_signature,
            writer=writer,
        )


def test_constructor_requires_postgres_transactional_write_side() -> None:
    with pytest.raises(
        TypeError,
        match="writer must be PostgresTransactionalWriteSide",
    ):
        PostgresWriteSideInvocationOwner(
            request_signature=_signature(),
            writer=object(),
        )


@pytest.mark.parametrize("command_type", [CommandType.CREATE, CommandType.PAY])
def test_a1_and_a2_dispatch_exact_retained_fields_to_same_writer(
    command_type: CommandType,
) -> None:
    signature = _signature(command_type=command_type)
    initial_result = _positive_result(signature)
    a2_result = _accepted_result(signature)
    retained_writer = _SequencedWriteSide([initial_result, a2_result])
    unrelated_writer = _SequencedWriteSide([])
    owner = _owner(signature, retained_writer)

    assert owner.invoke_initial() is initial_result
    assert isinstance(
        owner.evaluate_reinvocation_authority(),
        ReinvocationAuthorization,
    )
    assert owner.invoke_authorized_reinvocation() is a2_result

    expected_call = (
        command_type,
        signature.request_id,
        signature.order_id,
        signature.amount,
    )
    assert retained_writer.calls == [expected_call, expected_call]
    assert unrelated_writer.calls == []
    assert list(
        inspect_signature(
            PostgresWriteSideInvocationOwner.invoke_authorized_reinvocation
        ).parameters
    ) == ["self"]


def test_invoke_initial_returns_and_retains_exact_result_once() -> None:
    signature = _signature()
    initial_result = _positive_result(signature)
    writer = _SequencedWriteSide([initial_result])
    owner = _owner(signature, writer)

    returned = owner.invoke_initial()

    assert returned is initial_result
    assert owner.__dict__["_initial_result"] is initial_result
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has already started",
    ):
        owner.invoke_initial()
    assert len(writer.calls) == 1


def test_concurrent_a1_allows_one_entry_and_publishes_after_return() -> None:
    signature = _signature()
    initial_result = _positive_result(signature)
    writer = _SequencedWriteSide([initial_result], block_on_call=1)
    owner = _owner(signature, writer)

    with ThreadPoolExecutor(max_workers=3) as executor:
        initial_future = executor.submit(owner.invoke_initial)
        assert writer.blocked_entry.wait(WAIT_SECONDS)

        duplicate_future = executor.submit(owner.invoke_initial)
        evaluation_future = executor.submit(
            owner.evaluate_reinvocation_authority
        )
        try:
            with pytest.raises(
                PostgresWriteSideInvocationLifecycleError,
                match="initial invocation has already started",
            ):
                duplicate_future.result(timeout=WAIT_SECONDS)
            with pytest.raises(
                PostgresWriteSideInvocationLifecycleError,
                match="initial invocation has not completed normally",
            ):
                evaluation_future.result(timeout=WAIT_SECONDS)
        finally:
            writer.release_blocked_call.set()

        assert initial_future.result(timeout=WAIT_SECONDS) is initial_result

    assert owner.__dict__["_initial_result"] is initial_result
    assert len(writer.calls) == 1


def test_a1_exception_is_identical_and_never_retried() -> None:
    signature = _signature()
    sentinel = _A2SentinelError("A1 sentinel")
    writer = _SequencedWriteSide([sentinel])
    owner = _owner(signature, writer)

    with pytest.raises(_A2SentinelError) as raised:
        owner.invoke_initial()
    assert raised.value is sentinel

    for operation in (
        owner.evaluate_reinvocation_authority,
        owner.invoke_authorized_reinvocation,
    ):
        with pytest.raises(
            PostgresWriteSideInvocationLifecycleError,
            match="initial invocation has not completed normally",
        ):
            operation()
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has already started",
    ):
        owner.invoke_initial()
    assert len(writer.calls) == 1


def test_wrong_a1_result_type_is_not_published_or_retried() -> None:
    signature = _signature()
    wrong_result = cast(PostgresWriteSideResult, object())
    writer = _SequencedWriteSide([wrong_result])
    owner = _owner(signature, writer)

    with pytest.raises(
        TypeError,
        match="retained writer must return PostgresWriteSideResult",
    ):
        owner.invoke_initial()

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has not completed normally",
    ):
        owner.evaluate_reinvocation_authority()
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has already started",
    ):
        owner.invoke_initial()
    assert len(writer.calls) == 1


def test_evaluation_is_explicit_positive_and_does_not_enter_a2() -> None:
    signature = _signature()
    writer = _SequencedWriteSide(
        [_positive_result(signature), _accepted_result(signature)]
    )
    owner = _owner(signature, writer)

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="initial invocation has not completed normally",
    ):
        owner.evaluate_reinvocation_authority()

    owner.invoke_initial()
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="has not been explicitly evaluated",
    ):
        owner.invoke_authorized_reinvocation()

    evaluation = owner.evaluate_reinvocation_authority()

    assert isinstance(evaluation, ReinvocationAuthorization)
    assert len(writer.calls) == 1


def test_negative_evaluation_is_cached_and_cannot_enter_a2() -> None:
    signature = _signature()
    negative_result = replace(
        _positive_result(signature),
        stream_admission_result=None,
    )
    writer = _SequencedWriteSide([negative_result])
    owner = _owner(signature, writer)
    owner.invoke_initial()

    first = owner.evaluate_reinvocation_authority()
    second = owner.evaluate_reinvocation_authority()

    assert isinstance(first, NoReinvocationAuthority)
    assert second is first
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="issued no re-invocation authority",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 1


def test_concurrent_evaluation_returns_one_identical_cached_object() -> None:
    signature = _signature()
    writer = _SequencedWriteSide([_positive_result(signature)])
    owner = _owner(signature, writer)
    owner.invoke_initial()
    participant_count = 8
    barrier = Barrier(participant_count)

    def evaluate_after_barrier():
        barrier.wait(timeout=WAIT_SECONDS)
        return owner.evaluate_reinvocation_authority()

    with ThreadPoolExecutor(max_workers=participant_count) as executor:
        futures = [
            executor.submit(evaluate_after_barrier)
            for _ in range(participant_count)
        ]
        evaluations = [
            future.result(timeout=WAIT_SECONDS) for future in futures
        ]

    assert isinstance(evaluations[0], ReinvocationAuthorization)
    assert all(evaluation is evaluations[0] for evaluation in evaluations)
    assert len(writer.calls) == 1


def test_structural_evaluator_error_is_not_cached() -> None:
    signature = _signature()
    malformed_result = replace(
        _positive_result(signature),
        outcome=object(),
    )
    writer = _SequencedWriteSide([malformed_result])
    owner = _owner(signature, writer)
    owner.invoke_initial()

    for _ in range(2):
        with pytest.raises(
            TypeError,
            match="result.outcome must be PostgresWriteSideOutcome",
        ):
            owner.evaluate_reinvocation_authority()
        assert owner.__dict__["_cached_reinvocation_evaluation"] is None


def test_issued_authority_meaning_remains_cached_after_spend() -> None:
    signature = _signature()
    writer = _SequencedWriteSide(
        [_positive_result(signature), _accepted_result(signature)]
    )
    owner = _owner(signature, writer)
    owner.invoke_initial()
    issued_authority = owner.evaluate_reinvocation_authority()

    owner.invoke_authorized_reinvocation()

    assert owner.evaluate_reinvocation_authority() is issued_authority
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="already been spent",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 2


def test_concurrent_consumption_spends_before_a2_and_releases_lock() -> None:
    signature = _signature()
    a2_result = _accepted_result(signature)
    writer = _SequencedWriteSide(
        [_positive_result(signature), a2_result],
        block_on_call=2,
    )
    owner = _owner(signature, writer)
    owner.invoke_initial()
    issued_authority = owner.evaluate_reinvocation_authority()

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(owner.invoke_authorized_reinvocation)
        assert writer.blocked_entry.wait(WAIT_SECONDS)

        loser = executor.submit(owner.invoke_authorized_reinvocation)
        try:
            with pytest.raises(
                PostgresWriteSideInvocationLifecycleError,
                match="already been spent",
            ):
                loser.result(timeout=WAIT_SECONDS)
            assert owner.evaluate_reinvocation_authority() is issued_authority
        finally:
            writer.release_blocked_call.set()

        assert winner.result(timeout=WAIT_SECONDS) is a2_result

    assert len(writer.calls) == 2


def _terminal_a2_results(
    signature: RequestSignature,
) -> list[tuple[str, PostgresWriteSideResult]]:
    accepted = _accepted_result(signature)
    assert accepted.accepted_event is not None
    record = IdempotencyRecord(
        signature=signature,
        accepted_event=accepted.accepted_event,
    )
    validation = _allowing_validation_decision(
        accepted.accepted_event.event_id
    )
    admitted_stream = StreamAdmissionResult(
        verdict=AdmissionVerdict.ADMITTED,
        reason="test-owned admitted stream",
        order_id=signature.order_id,
    )

    return [
        ("accepted", accepted),
        ("preparation-lock-timeout", _positive_result(signature)),
        (
            "replay",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.REPLAY,
                accepted_event=record.accepted_event,
                idempotency_decision=IdempotencyDecision(
                    verdict=IdempotencyVerdict.REPLAY,
                    reason="test-owned replay",
                    record=record,
                ),
            ),
        ),
        (
            "conflict",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.CONFLICT,
                accepted_event=None,
                idempotency_decision=IdempotencyDecision(
                    verdict=IdempotencyVerdict.CONFLICT,
                    reason="test-owned conflict",
                    record=record,
                ),
            ),
        ),
        (
            "validation-blocked",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
                accepted_event=None,
                idempotency_decision=_miss(),
                stream_admission_result=admitted_stream,
                validation_decision=replace(
                    validation,
                    action=EnforcementAction.BLOCK,
                ),
            ),
        ),
        (
            "append-lock-timeout",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                accepted_event=None,
                idempotency_decision=_miss(),
                stream_admission_result=admitted_stream,
                validation_decision=validation,
                admission_result=AdmissionResult(
                    verdict=AdmissionVerdict.LOCK_TIMEOUT,
                    reason="test-owned append lock timeout",
                    candidate_event_id=accepted.accepted_event.event_id,
                ),
            ),
        ),
        (
            "append-stale-write",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                accepted_event=None,
                idempotency_decision=_miss(),
                stream_admission_result=admitted_stream,
                validation_decision=validation,
                admission_result=AdmissionResult(
                    verdict=AdmissionVerdict.STALE_WRITE,
                    reason="test-owned append stale write",
                    candidate_event_id=accepted.accepted_event.event_id,
                ),
            ),
        ),
        (
            "infrastructure",
            PostgresWriteSideResult(
                outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
                accepted_event=None,
                idempotency_decision=_miss(),
                stream_admission_result=StreamAdmissionResult(
                    verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                    reason="test-owned infrastructure result",
                    order_id=signature.order_id,
                ),
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("result_name", "a2_result"),
    _terminal_a2_results(_signature()),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_every_normal_a2_result_leaves_authority_terminally_spent(
    result_name: str,
    a2_result: PostgresWriteSideResult,
) -> None:
    del result_name
    signature = _signature()
    writer = _SequencedWriteSide([_positive_result(signature), a2_result])
    owner = _owner(signature, writer)
    owner.invoke_initial()
    owner.evaluate_reinvocation_authority()

    assert owner.invoke_authorized_reinvocation() is a2_result
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="already been spent",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 2


def test_a2_exception_propagates_identically_and_leaves_spent() -> None:
    signature = _signature()
    sentinel = _A2SentinelError("A2 sentinel")
    writer = _SequencedWriteSide([_positive_result(signature), sentinel])
    owner = _owner(signature, writer)
    owner.invoke_initial()
    owner.evaluate_reinvocation_authority()

    with pytest.raises(_A2SentinelError) as raised:
        owner.invoke_authorized_reinvocation()
    assert raised.value is sentinel

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="already been spent",
    ):
        owner.invoke_authorized_reinvocation()
    assert len(writer.calls) == 2
