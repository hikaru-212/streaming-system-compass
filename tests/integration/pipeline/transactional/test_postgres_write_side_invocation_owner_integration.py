from __future__ import annotations

from decimal import Decimal

import pytest

from src.compass.runtime.runtime_decision import RuntimeDecisionResponse
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.compass.runtime.semantic_outcome import SemanticOutcomeCategory
from src.compass.runtime.write_side_runtime_decision import (
    PostgresWriteSideRuntimeDecisionRefused,
)
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
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideCurrentResponseEvaluation,
    PostgresWriteSideCurrentResponseRefusal,
    PostgresWriteSideInvocationLifecycleError,
    PostgresWriteSideInvocationOwner,
)
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.postgres_event_store import PostgresEventStore
from tests.shared.postgres import count_rows


pytestmark = pytest.mark.usefixtures("clean_database")


class _CountingAllowValidationRuntime:
    def __init__(self) -> None:
        self.call_count = 0

    def decide(self, candidate_event, context) -> ValidationDecision:
        self.call_count += 1
        return ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="Stage 4E PR2 integration validation allowed",
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


def _pessimistic_gate_factory(uow) -> PostgresPessimisticAdmissionGate:
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def test_real_lock_timeout_supports_independent_stage4c_delivery_and_one_a2(
    db_connection,
    db_connection_factory,
) -> None:
    signature = RequestSignature(
        request_id="stage4e-pr2-integration-request",
        command_type=CommandType.CREATE,
        order_id="stage4e-pr2-integration-order",
        amount=Decimal("100.00"),
    )
    validation_runtime = _CountingAllowValidationRuntime()
    writer = PostgresTransactionalWriteSide(
        connection=db_connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=_pessimistic_gate_factory,
        config=PostgresWriteSideConfig(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
        ),
    )
    owner = PostgresWriteSideInvocationOwner(
        request_signature=signature,
        writer=writer,
    )

    lock_holder = db_connection_factory()
    holder_gate = PostgresPessimisticAdmissionGate(
        connection=lock_holder,
        event_store=PostgresEventStore(lock_holder),
    )
    try:
        holder_result = holder_gate.prepare_stream(signature.order_id)
        assert holder_result.verdict is AdmissionVerdict.ADMITTED

        initial_result = owner.invoke_initial()
    finally:
        lock_holder.rollback()
        lock_holder.close()

    assert (
        initial_result.outcome
        is PostgresWriteSideOutcome.ADMISSION_REJECTED
    )
    assert initial_result.accepted_event is None
    assert (
        initial_result.idempotency_decision.verdict
        is IdempotencyVerdict.MISS
    )
    assert initial_result.idempotency_decision.record is None
    assert initial_result.stream_admission_result is not None
    assert (
        initial_result.stream_admission_result.verdict
        is AdmissionVerdict.LOCK_TIMEOUT
    )
    assert (
        initial_result.stream_admission_result.order_id
        == signature.order_id
    )
    assert initial_result.validation_decision is None
    assert initial_result.validation_decision_evidence is None
    assert initial_result.admission_result is None
    assert validation_runtime.call_count == 0

    initial_delivery = owner.evaluate_current_response()
    assert isinstance(
        initial_delivery,
        PostgresWriteSideCurrentResponseRefusal,
    )
    assert initial_delivery.producer_result is initial_result
    assert initial_delivery.source_feedback.semantic_outcome.category is (
        SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN
    )
    assert isinstance(
        initial_delivery.refusal,
        PostgresWriteSideRuntimeDecisionRefused,
    )
    assert not hasattr(initial_delivery, "decision")
    assert not hasattr(initial_delivery, "selected_result")

    authority = owner.evaluate_reinvocation_authority()
    assert isinstance(authority, ReinvocationAuthorization)
    assert authority.request_signature is signature

    second_result = owner.invoke_authorized_reinvocation()

    assert second_result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert second_result.accepted_event is not None
    assert (
        second_result.idempotency_decision.verdict
        is IdempotencyVerdict.MISS
    )
    assert second_result.stream_admission_result is not None
    assert (
        second_result.stream_admission_result.verdict
        is AdmissionVerdict.ADMITTED
    )
    assert second_result.validation_decision is not None
    assert second_result.validation_decision.action is EnforcementAction.ALLOW
    assert second_result.admission_result is not None
    assert second_result.admission_result.verdict is AdmissionVerdict.ADMITTED
    second_delivery = owner.evaluate_current_response()
    assert isinstance(
        second_delivery,
        PostgresWriteSideCurrentResponseEvaluation,
    )
    assert second_delivery.producer_result is second_result
    assert (
        second_delivery.evaluation.decision.response
        is RuntimeDecisionResponse.USE_CURRENT_RESULT
    )
    assert second_delivery.selected_result is second_result
    assert validation_runtime.call_count == 1
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1

    with pytest.raises(
        PostgresWriteSideInvocationLifecycleError,
        match="already been spent",
    ):
        owner.invoke_authorized_reinvocation()

    assert validation_runtime.call_count == 1
    assert count_rows(db_connection, "order_events") == 1
    assert count_rows(db_connection, "idempotency_records") == 1
