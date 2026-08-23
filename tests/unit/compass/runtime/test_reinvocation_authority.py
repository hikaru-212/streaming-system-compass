from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal

import pytest

import src.compass.runtime.reinvocation_authority as authority_module
from src.compass.runtime.reinvocation_authority import (
    NoReinvocationAuthority,
    ReinvocationAuthorization,
)
from src.core.order.enums import CommandType
from src.storage.idempotency_store import RequestSignature


def _signature() -> RequestSignature:
    return RequestSignature(
        request_id="stage4e-request-001",
        command_type=CommandType.CREATE,
        order_id="stage4e-order-001",
        amount=Decimal("100.00"),
    )


def _authorization() -> ReinvocationAuthorization:
    return ReinvocationAuthorization._from_evaluation(
        request_signature=_signature(),
    )


def _no_authority() -> NoReinvocationAuthority:
    return NoReinvocationAuthority._from_evaluation(
        request_signature=_signature(),
        explanation="The first Stage 4E profile did not issue authority.",
    )


def test_complete_request_signature_uses_structural_equality() -> None:
    original = _signature()
    independently_constructed = _signature()

    assert independently_constructed is not original
    assert independently_constructed == original


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        pytest.param("command_type", CommandType.PAY, id="command-type"),
        pytest.param("order_id", "stage4e-order-002", id="order-id"),
        pytest.param("amount", Decimal("101.00"), id="amount"),
    ],
)
def test_same_request_id_with_changed_semantic_component_is_not_same_request(
    field_name: str,
    changed_value: object,
) -> None:
    original = _signature()
    changed = replace(original, **{field_name: changed_value})

    assert changed.request_id == original.request_id
    assert changed != original


def test_authorization_retains_exact_complete_signature_and_is_frozen() -> None:
    signature = _signature()
    authorization = ReinvocationAuthorization._from_evaluation(
        request_signature=signature,
    )

    assert authorization.request_signature is signature
    with pytest.raises(FrozenInstanceError):
        authorization.request_signature = _signature()  # type: ignore[misc]


def test_no_authority_is_distinct_typed_immutable_review_result() -> None:
    signature = _signature()
    result = NoReinvocationAuthority._from_evaluation(
        request_signature=signature,
        explanation="Unsupported evidence does not issue Stage 4E authority.",
    )

    assert result.request_signature is signature
    assert result.explanation == (
        "Unsupported evidence does not issue Stage 4E authority."
    )
    assert not isinstance(result, ReinvocationAuthorization)
    with pytest.raises(FrozenInstanceError):
        result.explanation = "changed"  # type: ignore[misc]


def test_contracts_reject_direct_construction() -> None:
    with pytest.raises(TypeError, match="reviewed Stage 4E evaluator"):
        ReinvocationAuthorization()
    with pytest.raises(TypeError, match="reviewed Stage 4E evaluator"):
        NoReinvocationAuthority()


def test_authorization_has_only_immutable_issuance_meaning() -> None:
    authorization = _authorization()

    assert {field.name for field in fields(ReinvocationAuthorization)} == {
        "request_signature"
    }
    assert not callable(authorization)
    for forbidden_name in {
        "writer",
        "execute",
        "execution_callable",
        "strategy",
        "composition",
        "available",
        "spent",
        "consume",
        "try_consume",
        "retry_count",
        "attempt_count",
        "backoff",
        "timing",
        "authorization_id",
        "persistence_id",
    }:
        assert not hasattr(authorization, forbidden_name)


def test_no_authority_is_not_a_universal_policy_or_evidence_bag() -> None:
    result = _no_authority()

    assert {field.name for field in fields(NoReinvocationAuthority)} == {
        "request_signature",
        "explanation",
    }
    for forbidden_name in {
        "allowed",
        "denied",
        "policy",
        "instruction",
        "metadata",
        "evidence",
    }:
        assert not hasattr(result, forbidden_name)


def test_generic_contract_module_has_no_producer_execution_or_lifecycle_dependency() -> None:
    forbidden_symbols = {
        "PostgresWriteSideResult",
        "PostgresTransactionalWriteSide",
        "RuntimeDecision",
        "SemanticOutcome",
        "Thread",
        "Lock",
    }

    assert forbidden_symbols.isdisjoint(authority_module.__dict__)
