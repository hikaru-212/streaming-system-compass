"""Rule-evaluation evidence invariants for the FullProof producer."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from enum import Enum
from itertools import cycle

import pytest

import src.compass.transition.validators as validators_module
from src.compass.transition.rule_evaluation_evidence import (
    FULL_PROOF_SUPPORTED_RULE_IDS,
    FullProofValidationEvidence,
)
from src.compass.transition.types import (
    ValidationContext,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)
from src.compass.transition.validators import FullProofValidator
from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    OrderCorrectnessRuleId,
)
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.core.order.rule_violation_evidence import OrderRuleViolationEvidence


class _ForeignEventType(Enum):
    """Test-local event type for the existing unsupported-type branch."""

    OBSERVED = "OBSERVED"


EXPECTED_FULL_PROOF_RULE_IDS = frozenset(
    (
        (
            OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED
        ),
        OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
        (
            OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS
        ),
    )
)


def _event(
    *,
    event_id: str,
    sequence: int,
    event_type: object,
    prev_status: OrderStatus,
    prev_version: int,
    prev_event_id: str | None,
) -> OrderEvent:
    """Build deterministic candidate-shaped data without persistence."""

    return OrderEvent(
        event_id=event_id,
        request_id=f"request-{event_id}",
        order_id="order-evidence",
        sequence=sequence,
        event_type=event_type,  # type: ignore[arg-type]
        amount=Decimal("10.00"),
        occurred_at_ms=0,
        proof=Proof(
            prev_status=prev_status,
            prev_version=prev_version,
            prev_event_id=prev_event_id,
        ),
    )


def _accepted_created_event() -> OrderEvent:
    """Build accepted-predecessor-shaped data for CREATED history context."""

    return _event(
        event_id="accepted-created",
        sequence=1,
        event_type=EventType.CREATED,
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )


def _init_context() -> ValidationContext:
    """Return accepted empty-history facts."""

    return ValidationContext(
        actual_prev_event=None,
        actual_prev_version=0,
        actual_prev_status=OrderStatus.INIT,
    )


def _created_context() -> ValidationContext:
    """Return accepted facts after one CREATED event."""

    accepted_created = _accepted_created_event()
    return ValidationContext(
        actual_prev_event=accepted_created,
        actual_prev_version=1,
        actual_prev_status=OrderStatus.CREATED,
    )


def _valid_created_candidate() -> OrderEvent:
    """Return a candidate satisfying every FullProof branch."""

    return _event(
        event_id="candidate-created",
        sequence=1,
        event_type=EventType.CREATED,
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )


def _valid_paid_candidate() -> OrderEvent:
    """Return a PAY candidate following the deterministic accepted predecessor."""

    return _event(
        event_id="candidate-paid",
        sequence=2,
        event_type=EventType.PAID,
        prev_status=OrderStatus.CREATED,
        prev_version=1,
        prev_event_id="accepted-created",
    )


def _validation_result(
    verdict: ValidationVerdict,
    *,
    candidate_event_id: str = "candidate-evidence",
) -> ValidationResult:
    """Build a minimal primary result for evidence-structure tests."""

    return ValidationResult(
        verdict=verdict,
        reason="result",
        candidate_event_id=candidate_event_id,
        validator_name="FullProofValidator",
        validation_mode=ValidationMode.STRICT,
        logic_validation_time_ms=0.0,
        io_time_ms=0.0,
        total_time_ms=0.0,
        metadata={},
    )


def _violation(
    rule_id: OrderCorrectnessRuleId,
    *,
    candidate_event_id: str = "candidate-evidence",
) -> OrderRuleViolationEvidence:
    """Build canonical V0 sibling evidence for structural tests."""

    return OrderRuleViolationEvidence(
        contract_id=ORDER_CORRECTNESS_CONTRACT_V0.contract_id,
        contract_version=ORDER_CORRECTNESS_CONTRACT_V0.contract_version,
        rule_id=rule_id,
        candidate_event_id=candidate_event_id,
    )


def _assert_observed_rule(
    candidate: OrderEvent,
    context: ValidationContext,
    expected_rule_id: OrderCorrectnessRuleId,
) -> None:
    """Assert exact typed evidence without interpreting reason or metadata."""

    result = FullProofValidator().validate_with_rule_evidence(candidate, context)

    assert result.validation_result.verdict is ValidationVerdict.FAILED
    assert result.observed_violation is not None
    assert result.observed_violation.rule_id is expected_rule_id
    assert result.observed_violation.candidate_event_id == candidate.event_id
    assert result.observed_violation.contract_id == "order.correctness"
    assert result.observed_violation.contract_version == 0


def test_order_rule_violation_evidence_is_frozen() -> None:
    evidence = _violation(
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
    )

    with pytest.raises(FrozenInstanceError):
        evidence.rule_id = (  # type: ignore[misc]
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED
        )


def test_full_proof_validation_evidence_is_frozen() -> None:
    evidence = FullProofValidationEvidence(
        validation_result=_validation_result(ValidationVerdict.PASSED),
        observed_violation=None,
    )

    with pytest.raises(FrozenInstanceError):
        evidence.observed_violation = _violation(  # type: ignore[misc]
            OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
        )


def test_passed_result_rejects_observed_violation() -> None:
    with pytest.raises(ValueError, match="PASSED"):
        FullProofValidationEvidence(
            validation_result=_validation_result(ValidationVerdict.PASSED),
            observed_violation=_violation(
                OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
            ),
        )


def test_failed_result_requires_observed_violation() -> None:
    with pytest.raises(ValueError, match="FAILED"):
        FullProofValidationEvidence(
            validation_result=_validation_result(ValidationVerdict.FAILED),
            observed_violation=None,
        )


def test_full_proof_supported_rule_set_is_exact_and_immutable() -> None:
    assert type(FULL_PROOF_SUPPORTED_RULE_IDS) is frozenset
    assert FULL_PROOF_SUPPORTED_RULE_IDS == EXPECTED_FULL_PROOF_RULE_IDS
    assert len(FULL_PROOF_SUPPORTED_RULE_IDS) == 6

    with pytest.raises(AttributeError):
        FULL_PROOF_SUPPORTED_RULE_IDS.add(  # type: ignore[attr-defined]
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT
        )


@pytest.mark.parametrize("rule_id", tuple(OrderCorrectnessRuleId))
def test_failed_wrapper_accepts_exactly_the_six_supported_rule_ids(
    rule_id: OrderCorrectnessRuleId,
) -> None:
    result = _validation_result(ValidationVerdict.FAILED)
    evidence = _violation(rule_id)

    if rule_id in EXPECTED_FULL_PROOF_RULE_IDS:
        wrapped = FullProofValidationEvidence(
            validation_result=result,
            observed_violation=evidence,
        )
        assert wrapped.observed_violation is evidence
        return

    with pytest.raises(ValueError, match="not supported"):
        FullProofValidationEvidence(
            validation_result=result,
            observed_violation=evidence,
        )


@pytest.mark.parametrize("candidate_event_id", ("", "   ", None))
def test_candidate_event_id_must_be_non_empty(
    candidate_event_id: object,
) -> None:
    with pytest.raises(ValueError, match="candidate_event_id"):
        OrderRuleViolationEvidence(
            contract_id="order.correctness",
            contract_version=0,
            rule_id=(
                OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
            ),
            candidate_event_id=candidate_event_id,  # type: ignore[arg-type]
        )


def test_candidate_event_id_does_not_require_uuid_shape() -> None:
    evidence = _violation(
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
        candidate_event_id="candidate-local-identity",
    )

    assert evidence.candidate_event_id == "candidate-local-identity"


def test_failed_wrapper_rejects_mismatched_candidate_identity() -> None:
    with pytest.raises(ValueError, match="same candidate"):
        FullProofValidationEvidence(
            validation_result=_validation_result(
                ValidationVerdict.FAILED,
                candidate_event_id="candidate-result",
            ),
            observed_violation=_violation(
                OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
                candidate_event_id="candidate-evidence",
            ),
        )


def test_full_proof_wrapper_rejects_skipped_result() -> None:
    with pytest.raises(ValueError, match="PASSED or FAILED"):
        FullProofValidationEvidence(
            validation_result=_validation_result(ValidationVerdict.SKIPPED),
            observed_violation=None,
        )


@pytest.mark.parametrize(
    ("contract_id", "contract_version", "expected_error"),
    (
        ("another.contract", 0, ValueError),
        ("order.correctness", 1, ValueError),
        ("order.correctness", True, TypeError),
    ),
)
def test_violation_evidence_rejects_non_v0_contract_identity(
    contract_id: str,
    contract_version: object,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        OrderRuleViolationEvidence(
            contract_id=contract_id,
            contract_version=contract_version,  # type: ignore[arg-type]
            rule_id=(
                OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
            ),
            candidate_event_id="candidate-evidence",
        )


def test_valid_candidate_preserves_primary_result_semantics_without_violation() -> None:
    candidate = _valid_created_candidate()
    context = _init_context()
    legacy = FullProofValidator().validate(candidate, context)
    evidence_result = FullProofValidator().validate_with_rule_evidence(
        candidate,
        context,
    )

    assert evidence_result.validation_result.verdict is legacy.verdict
    assert evidence_result.validation_result.reason == legacy.reason
    assert (
        evidence_result.validation_result.candidate_event_id
        == legacy.candidate_event_id
        == candidate.event_id
    )
    assert evidence_result.validation_result.validator_name == legacy.validator_name
    assert evidence_result.validation_result.validation_mode is legacy.validation_mode
    assert evidence_result.validation_result.metadata == legacy.metadata
    assert evidence_result.observed_violation is None


def test_wrong_candidate_sequence_maps_to_sequence_rule() -> None:
    candidate = replace(_valid_created_candidate(), sequence=2)

    _assert_observed_rule(
        candidate,
        _init_context(),
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
    )


def test_wrong_proof_prev_event_id_maps_to_predecessor_identity_rule() -> None:
    valid = _valid_paid_candidate()
    candidate = replace(
        valid,
        proof=replace(valid.proof, prev_event_id="another-accepted-event"),
    )

    _assert_observed_rule(
        candidate,
        _created_context(),
        OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED,
    )


def test_wrong_proof_prev_version_maps_to_predecessor_version_rule() -> None:
    valid = _valid_paid_candidate()
    candidate = replace(
        valid,
        proof=replace(valid.proof, prev_version=99),
    )

    _assert_observed_rule(
        candidate,
        _created_context(),
        OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED,
    )


def test_wrong_proof_prev_status_maps_to_predecessor_status_rule() -> None:
    valid = _valid_paid_candidate()
    candidate = replace(
        valid,
        proof=replace(valid.proof, prev_status=OrderStatus.INIT),
    )

    _assert_observed_rule(
        candidate,
        _created_context(),
        OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED,
    )


def test_unsupported_event_type_maps_to_supported_vocabulary_rule() -> None:
    candidate = replace(
        _valid_created_candidate(),
        event_type=_ForeignEventType.OBSERVED,  # type: ignore[arg-type]
    )

    _assert_observed_rule(
        candidate,
        _init_context(),
        OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
    )


def test_illegal_event_type_from_status_maps_to_transition_legality_rule() -> None:
    candidate = _event(
        event_id="candidate-illegal-paid",
        sequence=1,
        event_type=EventType.PAID,
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )

    _assert_observed_rule(
        candidate,
        _init_context(),
        (
            OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS
        ),
    )


@pytest.mark.parametrize(
    ("candidate", "context"),
    (
        (_valid_created_candidate(), _init_context()),
        (
            replace(_valid_created_candidate(), sequence=2),
            _init_context(),
        ),
    ),
)
def test_legacy_and_evidence_views_use_equal_shared_path_results(
    candidate: OrderEvent,
    context: ValidationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = cycle((1.0, 2.0, 3.0, 4.0))
    monkeypatch.setattr(
        validators_module.time,
        "perf_counter",
        lambda: next(clock),
    )
    validator = FullProofValidator()

    legacy = validator.validate(candidate, context)
    evidence_result = validator.validate_with_rule_evidence(candidate, context)

    assert evidence_result.validation_result == legacy



