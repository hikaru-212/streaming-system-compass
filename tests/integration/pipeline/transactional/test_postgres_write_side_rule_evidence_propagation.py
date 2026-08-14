"""Rule-evidence propagation through the real PostgreSQL write-side boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum

import pytest

from src.compass.transition.rule_evaluation_evidence import (
    FullProofValidationEvidence,
)
from src.compass.transition.runtime import (
    ValidationDecisionWithRuleEvidence,
    ValidationDispatcher,
    ValidationPolicy,
    ValidationRuntime,
)
from src.compass.transition.types import (
    EnforcementAction,
    ValidationContext,
    ValidationDecision,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType, OrderStatus
from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_admission import (
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideExecution,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurementDelivery,
)
from src.storage.idempotency_store import IdempotencyDecision, IdempotencyVerdict


class _Delivery(Enum):
    NORMAL = "normal"
    MEASUREMENT = "measurement"
    TRACE = "trace"
    TRACE_AND_MEASUREMENT = "trace-and-measurement"


class _RecordingPolicy(ValidationPolicy):
    def __init__(self) -> None:
        self.received: list[ValidationResult] = []

    def decide(self, result: ValidationResult) -> EnforcementAction:
        self.received.append(result)
        return super().decide(result)


class _RaisingPolicy(ValidationPolicy):
    def __init__(self) -> None:
        self.received: list[ValidationResult] = []

    def decide(self, result: ValidationResult) -> EnforcementAction:
        self.received.append(result)
        raise RuntimeError("policy failed")


class _SequencedFullProofValidator(FullProofValidator):
    """Drive pass/fail outcomes while retaining the actual candidate object."""

    def __init__(self, failures: tuple[bool, ...]) -> None:
        self._failures = failures
        self.evidence_calls = 0
        self.legacy_calls = 0
        self.produced: list[FullProofValidationEvidence] = []

    def validate(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("legacy validate must not run on the evidence path")

    def validate_with_rule_evidence(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> FullProofValidationEvidence:
        try:
            fails = self._failures[self.evidence_calls]
        except IndexError as exc:
            raise AssertionError("unexpected FullProof invocation") from exc

        self.evidence_calls += 1
        evaluated_context = (
            replace(
                context,
                actual_prev_version=context.actual_prev_version + 1,
            )
            if fails
            else context
        )
        evidence = super().validate_with_rule_evidence(
            candidate_event,
            evaluated_context,
        )
        self.produced.append(evidence)
        return evidence


class _RaisingFullProofValidator(FullProofValidator):
    def __init__(self) -> None:
        self.evidence_calls = 0
        self.legacy_calls = 0

    def validate(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("legacy validate must not run on the evidence path")

    def validate_with_rule_evidence(self, candidate_event, context):
        self.evidence_calls += 1
        raise RuntimeError("validator failed")


class _RecordingNoOpValidator(NoOpValidator):
    def __init__(self) -> None:
        self.calls = 0
        self.produced: list[ValidationResult] = []

    def validate(self, candidate_event, context) -> ValidationResult:
        self.calls += 1
        result = super().validate(candidate_event, context)
        self.produced.append(result)
        return result


class _RecordingValidationRuntime(ValidationRuntime):
    def __init__(self, *args, before_decision=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._before_decision = before_decision
        self.evidence_decide_calls = 0
        self.legacy_decide_calls = 0
        self.produced: list[ValidationDecisionWithRuleEvidence] = []

    def decide(self, candidate_event, context) -> ValidationDecision:
        self.legacy_decide_calls += 1
        return super().decide(candidate_event, context)

    def decide_with_rule_evidence(
        self,
        candidate_event,
        context,
    ) -> ValidationDecisionWithRuleEvidence:
        self.evidence_decide_calls += 1
        if self._before_decision is not None:
            self._before_decision()
        carrier = super().decide_with_rule_evidence(candidate_event, context)
        self.produced.append(carrier)
        return carrier


class _LegacyDecideOnlyRuntime:
    def __init__(self) -> None:
        self.calls = 0
        self.decisions: list[ValidationDecision] = []

    def decide(self, candidate_event, context) -> ValidationDecision:
        self.calls += 1
        decision = ValidationDecision(
            action=EnforcementAction.ALLOW,
            validation_result=ValidationResult(
                verdict=ValidationVerdict.PASSED,
                reason="legacy decide-only runtime allowed candidate",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=0.0,
                io_time_ms=0.0,
                total_time_ms=0.0,
                metadata={},
            ),
        )
        self.decisions.append(decision)
        return decision


class _RaisingEvidenceAwareRuntime:
    def __init__(self) -> None:
        self.evidence_calls = 0
        self.legacy_calls = 0

    def decide_with_rule_evidence(self, candidate_event, context):
        self.evidence_calls += 1
        raise AttributeError("runtime failed")

    def decide(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("legacy fallback must not follow runtime failure")


class _UnexpectedValidationRuntime:
    def __init__(self) -> None:
        self.evidence_calls = 0
        self.legacy_calls = 0

    def decide_with_rule_evidence(self, candidate_event, context):
        self.evidence_calls += 1
        raise AssertionError("validation must not be reached")

    def decide(self, candidate_event, context):
        self.legacy_calls += 1
        raise AssertionError("validation must not be reached")


class _PrepareRejectedGate:
    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return StreamAdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason="test-owned stream preparation rejection",
            order_id=order_id,
        )

    def append_if_admitted(self, candidate_event, expected_current_version):
        raise AssertionError("append must not follow preparation rejection")


class _AppendRejectedGate:
    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="test-owned stream preparation admission",
            order_id=order_id,
        )

    def append_if_admitted(
        self,
        candidate_event,
        expected_current_version,
    ) -> AdmissionResult:
        return AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="test-owned append admission rejection",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=None,
        )


@dataclass(frozen=True)
class _Invocation:
    result: PostgresWriteSideResult
    execution: PostgresWriteSideExecution | None
    measurement_delivery: PostgresWriteSideMeasurementDelivery | None


def _pessimistic_gate_factory(uow):
    return PostgresPessimisticAdmissionGate(
        connection=uow.connection,
        event_store=uow.event_store,
    )


def _prepare_rejected_gate_factory(uow):
    return _PrepareRejectedGate()


def _append_rejected_gate_factory(uow):
    return _AppendRejectedGate()


def _build_write_side(
    connection,
    *,
    placement: ValidationPlacement,
    validation_runtime,
    admission_gate_factory=None,
) -> PostgresTransactionalWriteSide:
    selected_gate_factory = admission_gate_factory
    if (
        selected_gate_factory is None
        and placement is ValidationPlacement.IN_TRANSACTION
    ):
        selected_gate_factory = _pessimistic_gate_factory

    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=selected_gate_factory,
        config=PostgresWriteSideConfig(validation_placement=placement),
    )


def _recording_runtime(
    *,
    validator,
    policy: ValidationPolicy,
    mode: ValidationMode = ValidationMode.STRICT,
    off_validator=None,
    before_decision=None,
) -> _RecordingValidationRuntime:
    return _RecordingValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=validator,
            off_validator=off_validator or NoOpValidator(),
        ),
        policy=policy,
        mode=mode,
        before_decision=before_decision,
    )


def _seed_order(connection, *, order_id: str) -> None:
    runtime = _LegacyDecideOnlyRuntime()
    result = _build_write_side(
        connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=runtime,
    ).create_order(
        request_id=f"seed-{order_id}",
        order_id=order_id,
        amount=Decimal("100.00"),
    )
    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert runtime.calls == 1


def _accept_create(
    connection,
    *,
    request_id: str,
    order_id: str,
    amount: Decimal,
) -> PostgresWriteSideResult:
    runtime = _LegacyDecideOnlyRuntime()
    result = _build_write_side(
        connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=runtime,
    ).create_order(
        request_id=request_id,
        order_id=order_id,
        amount=amount,
    )
    assert result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert runtime.calls == 1
    return result


def _invoke(
    write_side: PostgresTransactionalWriteSide,
    *,
    command: CommandType,
    delivery: _Delivery,
    request_id: str,
    order_id: str,
) -> _Invocation:
    method_name = {
        (CommandType.CREATE, _Delivery.NORMAL): "create_order",
        (CommandType.CREATE, _Delivery.MEASUREMENT): (
            "create_order_with_measurement"
        ),
        (CommandType.CREATE, _Delivery.TRACE): "create_order_with_trace",
        (CommandType.CREATE, _Delivery.TRACE_AND_MEASUREMENT): (
            "create_order_with_trace_and_measurement"
        ),
        (CommandType.PAY, _Delivery.NORMAL): "pay_order",
        (CommandType.PAY, _Delivery.MEASUREMENT): "pay_order_with_measurement",
        (CommandType.PAY, _Delivery.TRACE): "pay_order_with_trace",
        (CommandType.PAY, _Delivery.TRACE_AND_MEASUREMENT): (
            "pay_order_with_trace_and_measurement"
        ),
    }[(command, delivery)]
    value = getattr(write_side, method_name)(
        request_id=request_id,
        order_id=order_id,
        amount=Decimal("100.00"),
    )

    if delivery is _Delivery.NORMAL:
        assert isinstance(value, PostgresWriteSideResult)
        return _Invocation(value, None, None)

    if delivery is _Delivery.TRACE:
        assert isinstance(value, PostgresWriteSideExecution)
        result = value.result
        assert value.result is result
        return _Invocation(result, value, None)

    assert isinstance(value, PostgresWriteSideMeasurementDelivery)
    producer_value = value.producer_value
    if delivery is _Delivery.MEASUREMENT:
        assert isinstance(producer_value, PostgresWriteSideResult)
        assert value.producer_value is producer_value
        return _Invocation(producer_value, None, value)

    assert isinstance(producer_value, PostgresWriteSideExecution)
    result = producer_value.result
    assert value.producer_value is producer_value
    assert producer_value.result is result
    return _Invocation(result, producer_value, value)


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("command", tuple(CommandType))
@pytest.mark.parametrize("placement", tuple(ValidationPlacement))
@pytest.mark.parametrize("delivery", tuple(_Delivery))
def test_full_proof_failure_preserves_exact_evidence_across_all_topologies(
    db_connection,
    command: CommandType,
    placement: ValidationPlacement,
    delivery: _Delivery,
) -> None:
    order_id = f"failure-{command.value}-{placement.value}-{delivery.value}"
    if command is CommandType.PAY:
        _seed_order(db_connection, order_id=order_id)

    validator = _SequencedFullProofValidator((True,))
    policy = _RecordingPolicy()
    runtime = _recording_runtime(validator=validator, policy=policy)
    invocation = _invoke(
        _build_write_side(
            db_connection,
            placement=placement,
            validation_runtime=runtime,
        ),
        command=command,
        delivery=delivery,
        request_id=f"request-{order_id}",
        order_id=order_id,
    )
    carrier = runtime.produced[0]
    producer_evidence = validator.produced[0]

    assert invocation.result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED
    assert runtime.evidence_decide_calls == 1
    assert runtime.legacy_decide_calls == 0
    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == [producer_evidence.validation_result]
    assert policy.received[0] is producer_evidence.validation_result
    assert invocation.result.validation_decision_evidence is carrier
    assert invocation.result.validation_decision is carrier.decision
    assert carrier.decision.validation_result is producer_evidence.validation_result
    assert carrier.observed_violation is producer_evidence.observed_violation
    assert invocation.result.observed_rule_violation is carrier.observed_violation
    assert invocation.result.observed_rule_violation is not None


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("command", tuple(CommandType))
@pytest.mark.parametrize("placement", tuple(ValidationPlacement))
def test_full_proof_success_has_no_false_violation(
    db_connection,
    command: CommandType,
    placement: ValidationPlacement,
) -> None:
    order_id = f"success-{command.value}-{placement.value}"
    if command is CommandType.PAY:
        _seed_order(db_connection, order_id=order_id)

    validator = _SequencedFullProofValidator((False,))
    policy = _RecordingPolicy()
    runtime = _recording_runtime(validator=validator, policy=policy)
    invocation = _invoke(
        _build_write_side(
            db_connection,
            placement=placement,
            validation_runtime=runtime,
        ),
        command=command,
        delivery=_Delivery.NORMAL,
        request_id=f"request-{order_id}",
        order_id=order_id,
    )
    carrier = runtime.produced[0]

    assert invocation.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert invocation.result.validation_decision is carrier.decision
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert carrier.decision.validation_result.verdict is ValidationVerdict.PASSED
    assert carrier.observed_violation is None
    assert invocation.result.observed_rule_violation is None


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("placement", tuple(ValidationPlacement))
def test_off_mode_preserves_skipped_allow_without_violation(
    db_connection,
    placement: ValidationPlacement,
) -> None:
    off_validator = _RecordingNoOpValidator()
    policy = _RecordingPolicy()
    runtime = _recording_runtime(
        validator=FullProofValidator(),
        off_validator=off_validator,
        policy=policy,
        mode=ValidationMode.OFF,
    )
    invocation = _invoke(
        _build_write_side(
            db_connection,
            placement=placement,
            validation_runtime=runtime,
        ),
        command=CommandType.CREATE,
        delivery=_Delivery.NORMAL,
        request_id=f"off-{placement.value}",
        order_id=f"off-{placement.value}",
    )
    carrier = runtime.produced[0]

    assert off_validator.calls == 1
    assert invocation.result.validation_decision is carrier.decision
    assert carrier.decision.validation_result is off_validator.produced[0]
    assert carrier.decision.validation_result.verdict is ValidationVerdict.SKIPPED
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert invocation.result.observed_rule_violation is None


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("placement", tuple(ValidationPlacement))
def test_legacy_decide_only_runtime_uses_one_unchanged_call(
    db_connection,
    placement: ValidationPlacement,
) -> None:
    runtime = _LegacyDecideOnlyRuntime()
    invocation = _invoke(
        _build_write_side(
            db_connection,
            placement=placement,
            validation_runtime=runtime,
        ),
        command=CommandType.CREATE,
        delivery=_Delivery.NORMAL,
        request_id=f"legacy-{placement.value}",
        order_id=f"legacy-{placement.value}",
    )

    assert runtime.calls == 1
    assert invocation.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    assert invocation.result.validation_decision is runtime.decisions[0]
    assert invocation.result.validation_decision_evidence is None
    assert invocation.result.observed_rule_violation is None


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize(
    ("expected_outcome", "expected_verdict", "concurrent_amount"),
    (
        (
            PostgresWriteSideOutcome.REPLAY,
            IdempotencyVerdict.REPLAY,
            Decimal("100.00"),
        ),
        (
            PostgresWriteSideOutcome.CONFLICT,
            IdempotencyVerdict.CONFLICT,
            Decimal("999.00"),
        ),
    ),
    ids=("authoritative-replay", "authoritative-conflict"),
)
def test_pre_authoritative_idempotency_preserves_validation_carrier(
    db_connection,
    db_connection_factory,
    expected_outcome: PostgresWriteSideOutcome,
    expected_verdict: IdempotencyVerdict,
    concurrent_amount: Decimal,
) -> None:
    concurrent_connection = db_connection_factory()
    request_id = f"request-{expected_outcome.value}"
    order_id = f"order-{expected_outcome.value}"
    concurrent_results: list[PostgresWriteSideResult] = []

    def accept_during_validation() -> None:
        concurrent_results.append(
            _accept_create(
                concurrent_connection,
                request_id=request_id,
                order_id=order_id,
                amount=concurrent_amount,
            )
        )

    validator = _SequencedFullProofValidator((False,))
    policy = _RecordingPolicy()
    runtime = _recording_runtime(
        validator=validator,
        policy=policy,
        before_decision=accept_during_validation,
    )
    writer = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=runtime,
    )

    try:
        result = writer.create_order(
            request_id=request_id,
            order_id=order_id,
            amount=Decimal("100.00"),
        )
    finally:
        concurrent_connection.close()

    carrier = runtime.produced[0]
    producer_evidence = validator.produced[0]
    assert len(concurrent_results) == 1
    assert concurrent_results[0].outcome is PostgresWriteSideOutcome.ACCEPTED
    assert runtime.evidence_decide_calls == 1
    assert runtime.legacy_decide_calls == 0
    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == [producer_evidence.validation_result]
    assert policy.received[0] is producer_evidence.validation_result
    assert result.outcome is expected_outcome
    assert result.idempotency_decision.verdict is expected_verdict
    assert result.validation_decision is carrier.decision
    assert result.validation_decision_evidence is carrier
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert producer_evidence.validation_result.verdict is ValidationVerdict.PASSED
    assert carrier.decision.validation_result is producer_evidence.validation_result
    assert carrier.observed_violation is producer_evidence.observed_violation
    assert result.observed_rule_violation is carrier.observed_violation


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize(
    (
        "placement",
        "gate_factory",
        "expected_stream_verdict",
        "append_result_expected",
    ),
    (
        (
            ValidationPlacement.PRE_TRANSACTION,
            _prepare_rejected_gate_factory,
            AdmissionVerdict.LOCK_TIMEOUT,
            False,
        ),
        (
            ValidationPlacement.PRE_TRANSACTION,
            _append_rejected_gate_factory,
            AdmissionVerdict.ADMITTED,
            True,
        ),
        (
            ValidationPlacement.IN_TRANSACTION,
            _append_rejected_gate_factory,
            AdmissionVerdict.ADMITTED,
            True,
        ),
    ),
    ids=("pre-preparation", "pre-append", "in-append"),
)
def test_post_validation_admission_rejection_preserves_runtime_carrier(
    db_connection,
    placement: ValidationPlacement,
    gate_factory,
    expected_stream_verdict: AdmissionVerdict,
    append_result_expected: bool,
) -> None:
    validator = _SequencedFullProofValidator((False,))
    policy = _RecordingPolicy()
    runtime = _recording_runtime(validator=validator, policy=policy)
    result = _build_write_side(
        db_connection,
        placement=placement,
        validation_runtime=runtime,
        admission_gate_factory=gate_factory,
    ).create_order(
        request_id=f"admission-{placement.value}-{expected_stream_verdict.value}",
        order_id=f"admission-{placement.value}-{expected_stream_verdict.value}",
        amount=Decimal("100.00"),
    )

    carrier = runtime.produced[0]
    producer_evidence = validator.produced[0]
    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert runtime.evidence_decide_calls == 1
    assert runtime.legacy_decide_calls == 0
    assert validator.evidence_calls == 1
    assert validator.legacy_calls == 0
    assert policy.received == [producer_evidence.validation_result]
    assert policy.received[0] is producer_evidence.validation_result
    assert result.validation_decision is carrier.decision
    assert result.validation_decision_evidence is carrier
    assert carrier.decision.action is EnforcementAction.ALLOW
    assert producer_evidence.validation_result.verdict is ValidationVerdict.PASSED
    assert carrier.decision.validation_result is producer_evidence.validation_result
    assert carrier.observed_violation is producer_evidence.observed_violation
    assert result.observed_rule_violation is carrier.observed_violation
    assert result.stream_admission_result is not None
    assert result.stream_admission_result.verdict is expected_stream_verdict
    assert (result.admission_result is not None) is append_result_expected


@pytest.mark.usefixtures("clean_database")
def test_in_pre_validation_stream_rejection_has_no_validation_carrier(
    db_connection,
) -> None:
    runtime = _UnexpectedValidationRuntime()
    result = _build_write_side(
        db_connection,
        placement=ValidationPlacement.IN_TRANSACTION,
        validation_runtime=runtime,
        admission_gate_factory=_prepare_rejected_gate_factory,
    ).create_order(
        request_id="in-pre-validation-rejection",
        order_id="in-pre-validation-rejection",
        amount=Decimal("100.00"),
    )

    assert result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
    assert runtime.evidence_calls == 0
    assert runtime.legacy_calls == 0
    assert result.validation_decision is None
    assert result.validation_decision_evidence is None
    assert result.observed_rule_violation is None


def _failed_carrier(candidate_event: OrderEvent) -> ValidationDecisionWithRuleEvidence:
    validator = _SequencedFullProofValidator((True,))
    runtime = _recording_runtime(
        validator=validator,
        policy=_RecordingPolicy(),
    )
    context = ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=OrderStatus.INIT,
    )
    return runtime.decide_with_rule_evidence(candidate_event, context)


def _idempotency_miss() -> IdempotencyDecision:
    return IdempotencyDecision(
        verdict=IdempotencyVerdict.MISS,
        reason="test-owned miss",
    )


def test_result_rejects_equal_valued_but_distinct_decision() -> None:
    aggregate_candidate = _candidate("candidate-same-value")
    carrier = _failed_carrier(aggregate_candidate)
    distinct_decision = ValidationDecision(
        action=carrier.decision.action,
        validation_result=carrier.decision.validation_result,
    )

    assert distinct_decision == carrier.decision
    assert distinct_decision is not carrier.decision
    with pytest.raises(ValueError, match="identical decision"):
        PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            accepted_event=None,
            idempotency_decision=_idempotency_miss(),
            validation_decision=distinct_decision,
            validation_decision_evidence=carrier,
        )


@pytest.mark.parametrize("same_candidate_id", (False, True))
def test_result_rejects_carrier_from_another_invocation(
    same_candidate_id: bool,
) -> None:
    carrier_a = _failed_carrier(_candidate("candidate-a"))
    carrier_b = _failed_carrier(
        _candidate("candidate-a" if same_candidate_id else "candidate-b")
    )

    with pytest.raises(ValueError, match="identical decision"):
        PostgresWriteSideResult(
            outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
            accepted_event=None,
            idempotency_decision=_idempotency_miss(),
            validation_decision=carrier_b.decision,
            validation_decision_evidence=carrier_a,
        )


def test_optional_carrier_does_not_change_primary_result_equality() -> None:
    carrier = _failed_carrier(_candidate("candidate-equality"))
    without_carrier = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=_idempotency_miss(),
        validation_decision=carrier.decision,
    )
    with_carrier = PostgresWriteSideResult(
        outcome=PostgresWriteSideOutcome.VALIDATION_BLOCKED,
        accepted_event=None,
        idempotency_decision=without_carrier.idempotency_decision,
        validation_decision=carrier.decision,
        validation_decision_evidence=carrier,
    )

    assert with_carrier == without_carrier
    assert with_carrier.observed_rule_violation is carrier.observed_violation


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize(
    ("first_fails", "second_fails"),
    (
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ),
    ids=("failure-failure", "failure-success", "success-failure", "success-success"),
)
def test_write_side_evidence_is_invocation_local(
    db_connection,
    first_fails: bool,
    second_fails: bool,
) -> None:
    validator = _SequencedFullProofValidator((first_fails, second_fails))
    runtime = _recording_runtime(
        validator=validator,
        policy=_RecordingPolicy(),
    )
    writer = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=runtime,
    )
    order_id = f"temporal-{first_fails}-{second_fails}"

    first = _invoke(
        writer,
        command=CommandType.CREATE,
        delivery=_Delivery.NORMAL,
        request_id=f"first-{order_id}",
        order_id=order_id,
    ).result
    second_command = CommandType.CREATE if first_fails else CommandType.PAY
    second = _invoke(
        writer,
        command=second_command,
        delivery=_Delivery.NORMAL,
        request_id=f"second-{order_id}",
        order_id=order_id,
    ).result

    assert runtime.evidence_decide_calls == 2
    assert tuple(
        result.observed_rule_violation is not None for result in (first, second)
    ) == (first_fails, second_fails)
    for index, result in enumerate((first, second)):
        carrier = runtime.produced[index]
        assert result.validation_decision_evidence is carrier
        assert result.validation_decision is carrier.decision
        assert result.observed_rule_violation is carrier.observed_violation
    if first_fails and second_fails:
        assert first.observed_rule_violation is not second.observed_rule_violation


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("placement", tuple(ValidationPlacement))
def test_pre_validation_replay_has_no_runtime_carrier(
    db_connection,
    placement: ValidationPlacement,
) -> None:
    order_id = f"early-replay-{placement.value}"
    request_id = f"seed-{order_id}"
    _seed_order(db_connection, order_id=order_id)
    runtime = _UnexpectedValidationRuntime()

    replay = _invoke(
        _build_write_side(
            db_connection,
            placement=placement,
            validation_runtime=runtime,
        ),
        command=CommandType.CREATE,
        delivery=_Delivery.NORMAL,
        request_id=request_id,
        order_id=order_id,
    ).result

    assert replay.outcome is PostgresWriteSideOutcome.REPLAY
    assert runtime.evidence_calls == 0
    assert runtime.legacy_calls == 0
    assert replay.validation_decision is None
    assert replay.validation_decision_evidence is None
    assert replay.observed_rule_violation is None


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize("failure_source", ("validator", "policy", "runtime"))
def test_validation_failure_propagates_without_normal_delivery(
    db_connection,
    failure_source: str,
) -> None:
    if failure_source == "validator":
        validator = _RaisingFullProofValidator()
        policy = _RecordingPolicy()
        runtime = _recording_runtime(validator=validator, policy=policy)
    elif failure_source == "policy":
        validator = _SequencedFullProofValidator((False,))
        policy = _RaisingPolicy()
        runtime = _recording_runtime(validator=validator, policy=policy)
    else:
        validator = None
        policy = None
        runtime = _RaisingEvidenceAwareRuntime()

    writer = _build_write_side(
        db_connection,
        placement=ValidationPlacement.PRE_TRANSACTION,
        validation_runtime=runtime,
    )

    expected_exception = (
        AttributeError if failure_source == "runtime" else RuntimeError
    )
    with pytest.raises(expected_exception, match=f"{failure_source} failed"):
        _invoke(
            writer,
            command=CommandType.CREATE,
            delivery=_Delivery.TRACE_AND_MEASUREMENT,
            request_id=f"exception-{failure_source}",
            order_id=f"exception-{failure_source}",
        )

    if failure_source == "validator":
        assert validator is not None
        assert validator.evidence_calls == 1
        assert validator.legacy_calls == 0
        assert policy is not None
        assert policy.received == []
        assert runtime.produced == []
    elif failure_source == "policy":
        assert validator is not None
        assert validator.evidence_calls == 1
        assert policy is not None
        assert len(policy.received) == 1
        assert runtime.produced == []
    else:
        assert isinstance(runtime, _RaisingEvidenceAwareRuntime)
        assert runtime.evidence_calls == 1
        assert runtime.legacy_calls == 0


def _candidate(event_id: str) -> OrderEvent:
    candidate = OrderAggregate(f"order-{event_id}").create(
        request_id=f"request-{event_id}",
        total_amount=Decimal("100.00"),
    )
    return replace(candidate, event_id=event_id)
