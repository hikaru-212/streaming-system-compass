"""Owner-backed tests for experiment-local controlled execution."""

from __future__ import annotations

from dataclasses import fields, replace
from decimal import Decimal

import pytest

import experiments.deterministic_autonomous_governance.executor as executor_module
from experiments.deterministic_autonomous_governance.executor import (
    ControlledExecutionRefused,
    ControlledExecutor,
)
from experiments.deterministic_autonomous_governance.model import (
    RecoveryActionKind,
    plan_recovery,
)
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
from src.core.order.enums import CommandType
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    AppendVersionMismatchEvidence,
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
    IdempotencyVerdict,
    RequestSignature,
)


CANDIDATE_EVENT_ID = "controlled-executor-candidate-001"


class _SequencedWriteSide(PostgresTransactionalWriteSide):
    """Return bounded predetermined results through the public writer surface."""

    def __init__(self, results: list[PostgresWriteSideResult]) -> None:
        self._results = results
        self.calls: list[tuple[CommandType, str, str, Decimal]] = []

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
        self.calls.append((command_type, request_id, order_id, amount))
        call_index = len(self.calls) - 1
        if call_index >= len(self._results):
            raise AssertionError("unexpected public-writer entry")
        return self._results[call_index]


def _signature(
    *,
    request_id: str = "controlled-executor-request-001",
    command_type: CommandType = CommandType.CREATE,
    order_id: str = "controlled-executor-order-001",
    amount: Decimal = Decimal("100.00"),
) -> RequestSignature:
    return RequestSignature(
        request_id=request_id,
        command_type=command_type,
        order_id=order_id,
        amount=amount,
    )


def _miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="test-owned idempotency miss",
        record=None,
    )


def _allowing_validation() -> ValidationDecision:
    return ValidationDecision(
        action=EnforcementAction.ALLOW,
        validation_result=ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="test-owned validation result",
            candidate_event_id=CANDIDATE_EVENT_ID,
            validator_name="controlled-executor-test-validator",
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=0.0,
        ),
    )


def _append_stale_a1(
    signature: RequestSignature,
    *,
    mismatch: AppendVersionMismatchEvidence | None,
) -> PostgresWriteSideResult:
    validation = _allowing_validation()
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned admitted stream",
            order_id=signature.order_id,
        ),
        validation_decision=validation,
        admission_result=AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="test-owned append staleness",
            candidate_event_id=(
                validation.validation_result.candidate_event_id
            ),
            append_version_mismatch_evidence=mismatch,
        ),
    )


def _typed_forward_a1(
    signature: RequestSignature,
) -> PostgresWriteSideResult:
    return _append_stale_a1(
        signature,
        mismatch=AppendVersionMismatchEvidence(
            expected_current_version=1,
            observed_current_version=2,
        ),
    )


def _generic_stale_a1(
    signature: RequestSignature,
) -> PostgresWriteSideResult:
    return _append_stale_a1(signature, mismatch=None)


def _a2_result(signature: RequestSignature) -> PostgresWriteSideResult:
    return PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED,
        accepted_event=None,
        idempotency_decision=_miss(),
        stream_admission_result=StreamAdmissionResult(
            verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
            reason="test-owned fresh A2 result",
            order_id=signature.order_id,
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


def test_independently_authorized_typed_forward_proposal_enters_one_a2() -> None:
    signature = _signature()
    a1_result = _typed_forward_a1(signature)
    a2_result = _a2_result(signature)
    writer = _SequencedWriteSide([a1_result, a2_result])
    owner = _owner(signature, writer)

    a1 = owner.invoke_initial()
    proposal = plan_recovery(request_signature=signature, result=a1)
    assessment = owner.evaluate_reinvocation_authority()
    assert proposal is not None
    assert type(assessment) is ReinvocationAuthorization

    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1,
        reinvocation_assessment=assessment,
    )
    returned_a2 = executor.execute(proposal)

    assert returned_a2 is a2_result
    expected_call = (
        signature.command_type,
        signature.request_id,
        signature.order_id,
        signature.amount,
    )
    assert writer.calls == [expected_call, expected_call]


def test_generic_stale_proposal_with_no_authority_never_enters_a2() -> None:
    signature = _signature()
    a1_result = _generic_stale_a1(signature)
    writer = _SequencedWriteSide([a1_result])
    owner = _owner(signature, writer)

    a1 = owner.invoke_initial()
    proposal = plan_recovery(request_signature=signature, result=a1)
    assessment = owner.evaluate_reinvocation_authority()
    assert proposal is not None
    assert (
        proposal.action
        is RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
    )
    assert type(assessment) is NoReinvocationAuthority

    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1,
        reinvocation_assessment=assessment,
    )
    with pytest.raises(
        ControlledExecutionRefused,
        match="independent Stage 4E assessment issued no authority",
    ):
        executor.execute(proposal)

    assert len(writer.calls) == 1


def test_structurally_equal_different_source_result_is_refused() -> None:
    signature = _signature()
    retained_a1 = _typed_forward_a1(signature)
    equal_but_different_a1 = replace(retained_a1)
    writer = _SequencedWriteSide([retained_a1, _a2_result(signature)])
    owner = _owner(signature, writer)
    assert owner.invoke_initial() is retained_a1
    assessment = owner.evaluate_reinvocation_authority()
    assert type(assessment) is ReinvocationAuthorization
    assert equal_but_different_a1 == retained_a1
    assert equal_but_different_a1 is not retained_a1

    proposal = plan_recovery(
        request_signature=signature,
        result=equal_but_different_a1,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=retained_a1,
        reinvocation_assessment=assessment,
    )

    with pytest.raises(
        ControlledExecutionRefused,
        match="source_result is not the retained live A1 result",
    ):
        executor.execute(proposal)
    assert len(writer.calls) == 1


def test_complete_signature_mismatch_is_refused_before_owner_entry() -> None:
    expected_signature = _signature()
    different_signature = _signature(
        request_id=expected_signature.request_id,
        command_type=CommandType.PAY,
        order_id="different-order",
        amount=Decimal("101.00"),
    )
    a1_result = _typed_forward_a1(expected_signature)
    writer = _SequencedWriteSide([a1_result, _a2_result(expected_signature)])
    owner = _owner(expected_signature, writer)
    assert owner.invoke_initial() is a1_result
    assessment = owner.evaluate_reinvocation_authority()
    assert type(assessment) is ReinvocationAuthorization

    proposal = plan_recovery(
        request_signature=different_signature,
        result=a1_result,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner,
        expected_signature=expected_signature,
        retained_a1_result=a1_result,
        reinvocation_assessment=assessment,
    )

    with pytest.raises(
        ControlledExecutionRefused,
        match="request_signature does not equal expected_signature",
    ):
        executor.execute(proposal)
    assert len(writer.calls) == 1


def test_positive_authority_for_different_signature_is_refused() -> None:
    signature = _signature()
    a1_result = _typed_forward_a1(signature)
    writer = _SequencedWriteSide([a1_result, _a2_result(signature)])
    owner = _owner(signature, writer)
    assert owner.invoke_initial() is a1_result
    own_assessment = owner.evaluate_reinvocation_authority()
    assert type(own_assessment) is ReinvocationAuthorization

    other_signature = _signature(
        request_id="other-request",
        order_id="other-order",
    )
    other_a1 = _typed_forward_a1(other_signature)
    other_writer = _SequencedWriteSide([other_a1])
    other_owner = _owner(other_signature, other_writer)
    assert other_owner.invoke_initial() is other_a1
    other_assessment = other_owner.evaluate_reinvocation_authority()
    assert type(other_assessment) is ReinvocationAuthorization

    proposal = plan_recovery(
        request_signature=signature,
        result=a1_result,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1_result,
        reinvocation_assessment=other_assessment,
    )

    with pytest.raises(
        ControlledExecutionRefused,
        match="authorization request_signature does not match",
    ):
        executor.execute(proposal)
    assert len(writer.calls) == 1
    assert len(other_writer.calls) == 1


def test_executor_never_evaluates_stage4e_implicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signature = _signature()
    a1_result = _typed_forward_a1(signature)
    a2_result = _a2_result(signature)
    writer = _SequencedWriteSide([a1_result, a2_result])
    owner = _owner(signature, writer)
    assert owner.invoke_initial() is a1_result
    assessment = owner.evaluate_reinvocation_authority()
    assert type(assessment) is ReinvocationAuthorization

    def fail_if_evaluated(_owner: PostgresWriteSideInvocationOwner) -> None:
        raise AssertionError("executor must not evaluate Stage 4E")

    monkeypatch.setattr(
        PostgresWriteSideInvocationOwner,
        "evaluate_reinvocation_authority",
        fail_if_evaluated,
    )
    proposal = plan_recovery(
        request_signature=signature,
        result=a1_result,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1_result,
        reinvocation_assessment=assessment,
    )

    assert executor.execute(proposal) is a2_result
    assert len(writer.calls) == 2


def test_free_standing_authorization_cannot_supply_owner_availability() -> None:
    signature = _signature()

    owner_b_a1 = _typed_forward_a1(signature)
    owner_b_writer = _SequencedWriteSide([owner_b_a1])
    owner_b = _owner(signature, owner_b_writer)
    assert owner_b.invoke_initial() is owner_b_a1
    owner_b_authorization = owner_b.evaluate_reinvocation_authority()
    assert type(owner_b_authorization) is ReinvocationAuthorization

    owner_a_a1 = _typed_forward_a1(signature)
    owner_a_writer = _SequencedWriteSide([owner_a_a1])
    owner_a = _owner(signature, owner_a_writer)
    assert owner_a.invoke_initial() is owner_a_a1
    proposal = plan_recovery(
        request_signature=signature,
        result=owner_a_a1,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner_a,
        expected_signature=signature,
        retained_a1_result=owner_a_a1,
        reinvocation_assessment=owner_b_authorization,
    )

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="authority has not been explicitly evaluated",
    ):
        executor.execute(proposal)
    assert len(owner_a_writer.calls) == 1
    assert len(owner_b_writer.calls) == 1


def test_second_execution_propagates_owner_spent_state_failure() -> None:
    signature = _signature()
    a1_result = _typed_forward_a1(signature)
    a2_result = _a2_result(signature)
    writer = _SequencedWriteSide([a1_result, a2_result])
    owner = _owner(signature, writer)
    assert owner.invoke_initial() is a1_result
    assessment = owner.evaluate_reinvocation_authority()
    assert type(assessment) is ReinvocationAuthorization
    proposal = plan_recovery(
        request_signature=signature,
        result=a1_result,
    )
    assert proposal is not None
    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1_result,
        reinvocation_assessment=assessment,
    )

    assert executor.execute(proposal) is a2_result
    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="authority has already been spent",
    ):
        executor.execute(proposal)
    assert len(writer.calls) == 2


def test_executor_surface_has_no_authority_or_execution_substitutes() -> None:
    forbidden_symbols = {
        "evaluate_postgres_write_side_reinvocation_authority",
        "RuntimeDecision",
        "DecisionReceipt",
        "PostgresTransactionalWriteSide",
        "evaluate_postgres_write_side_runtime_decision",
        "Stage4DSelector",
    }

    assert [field.name for field in fields(ControlledExecutor)] == [
        "owner",
        "expected_signature",
        "retained_a1_result",
        "reinvocation_assessment",
    ]
    assert forbidden_symbols.isdisjoint(executor_module.__dict__)


def test_executor_rejects_malformed_binding_and_proposal_types() -> None:
    signature = _signature()
    a1_result = _typed_forward_a1(signature)
    writer = _SequencedWriteSide([a1_result])
    owner = _owner(signature, writer)
    assert owner.invoke_initial() is a1_result
    assessment = owner.evaluate_reinvocation_authority()
    assert type(assessment) is ReinvocationAuthorization

    with pytest.raises(
        TypeError,
        match="owner must be PostgresWriteSideInvocationOwner",
    ):
        ControlledExecutor(
            owner=object(),  # type: ignore[arg-type]
            expected_signature=signature,
            retained_a1_result=a1_result,
            reinvocation_assessment=assessment,
        )

    executor = ControlledExecutor(
        owner=owner,
        expected_signature=signature,
        retained_a1_result=a1_result,
        reinvocation_assessment=assessment,
    )
    with pytest.raises(
        ControlledExecutionRefused,
        match="exact RecoveryProposal type",
    ):
        executor.execute(object())  # type: ignore[arg-type]

    assert len(writer.calls) == 1
