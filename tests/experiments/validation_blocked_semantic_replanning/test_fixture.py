"""Executable witnesses for the experiment's governed configuration fixture."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal

import pytest

import experiments.validation_blocked_semantic_replanning.model as model
from experiments.validation_blocked_semantic_replanning.model import (
    AcceptedRateBudgetState,
    AcceptedSubmission,
    BlockedSubmission,
    ConfigurationAction,
    EnforcementAction,
    GovernedRateBudgetFixture,
    RateBudgetContract,
    RateBudgetProposal,
    RateBudgetRejectionEvidence,
    RateBudgetRuleId,
    RateBudgetTarget,
    RateBudgetValidationAllowed,
    RateUnitsPerSecond,
    ValidationVerdict,
    validate_rate_budget,
)


def _proposal(rate: int, request_id: str = "fixture-request-001") -> RateBudgetProposal:
    return RateBudgetProposal(
        request_id=request_id,
        action=ConfigurationAction.SET_RATE_BUDGET,
        target=RateBudgetTarget.FIXTURE_SERVICE,
        proposed_rate=RateUnitsPerSecond(rate),
    )


def _baseline() -> tuple[
    RateBudgetContract, AcceptedRateBudgetState, GovernedRateBudgetFixture
]:
    contract = RateBudgetContract(
        contract_id="experiment.rate_budget",
        contract_version=1,
        target=RateBudgetTarget.FIXTURE_SERVICE,
        maximum_rate=RateUnitsPerSecond(120),
    )
    initial = AcceptedRateBudgetState(
        target=RateBudgetTarget.FIXTURE_SERVICE,
        configured_rate=RateUnitsPerSecond(100),
    )
    return contract, initial, GovernedRateBudgetFixture(
        contract=contract, initial_state=initial
    )


def _record_validation(
    monkeypatch: pytest.MonkeyPatch, fixture: GovernedRateBudgetFixture
) -> list[
    tuple[AcceptedRateBudgetState, RateBudgetValidationAllowed | RateBudgetRejectionEvidence]
]:
    observed: list[
        tuple[AcceptedRateBudgetState, RateBudgetValidationAllowed | RateBudgetRejectionEvidence]
    ] = []
    real_validate = model.validate_rate_budget

    def record(
        proposal: RateBudgetProposal, *, contract: RateBudgetContract
    ) -> RateBudgetValidationAllowed | RateBudgetRejectionEvidence:
        before = fixture.accepted_state
        decision = real_validate(proposal, contract=contract)
        assert fixture.accepted_state is before
        observed.append((before, decision))
        return decision

    monkeypatch.setattr(model, "validate_rate_budget", record)
    return observed


@pytest.mark.parametrize(
    ("rate", "accepted"),
    [(120, True), (110, True), (0, True), (121, False), (200, False), (300, False)],
)
def test_submission_governs_exact_effect(
    rate: int, accepted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, before, fixture = _baseline()
    proposal = _proposal(rate)
    observed = _record_validation(monkeypatch, fixture)
    result = fixture.submit(proposal)

    assert len(observed) == 1
    assert observed[0][0] is before
    assert result.decision is observed[0][1]
    assert result.decision.proposal is proposal
    assert result.decision.contract is contract
    assert before.configured_rate.value == 100
    if accepted:
        assert type(result) is AcceptedSubmission
        assert type(result.decision) is RateBudgetValidationAllowed
        assert result.decision.verdict is ValidationVerdict.PASSED
        assert result.decision.enforcement_action is EnforcementAction.ALLOW
        assert result.accepted_state is fixture.accepted_state
        assert fixture.accepted_state is not before
        assert result.accepted_state.target is proposal.target
        assert result.accepted_state.configured_rate is proposal.proposed_rate
        assert fixture.accepted_state.configured_rate.value == rate
    else:
        assert type(result) is BlockedSubmission
        evidence = result.decision
        assert type(evidence) is RateBudgetRejectionEvidence
        assert evidence.verdict is ValidationVerdict.FAILED
        assert evidence.enforcement_action is EnforcementAction.BLOCK
        assert evidence.rule_id is RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM
        assert evidence.proposal.request_id == "fixture-request-001"
        assert evidence.proposal.action is ConfigurationAction.SET_RATE_BUDGET
        assert evidence.proposal.target is RateBudgetTarget.FIXTURE_SERVICE
        assert evidence.proposal.proposed_rate == RateUnitsPerSecond(rate)
        assert evidence.contract.contract_id == "experiment.rate_budget"
        assert evidence.contract.contract_version == 1
        assert evidence.contract.target is RateBudgetTarget.FIXTURE_SERVICE
        assert evidence.contract.maximum_rate == RateUnitsPerSecond(120)
        assert fixture.accepted_state is before
        assert fixture.accepted_state.configured_rate.value == 100


def test_pure_allow_has_no_effect_and_alternate_authority_cannot_be_injected() -> None:
    contract, before, fixture = _baseline()
    ordinary_allow = validate_rate_budget(_proposal(120), contract=contract)
    assert type(ordinary_allow) is RateBudgetValidationAllowed
    assert fixture.accepted_state is before

    proposal = _proposal(300)
    permissive = replace(
        contract, contract_version=2, maximum_rate=RateUnitsPerSecond(300)
    )
    unrelated_allow = validate_rate_budget(proposal, contract=permissive)
    assert type(unrelated_allow) is RateBudgetValidationAllowed
    assert unrelated_allow.proposal is proposal
    assert unrelated_allow.contract is permissive
    assert fixture.accepted_state is before

    with pytest.raises(TypeError, match="unexpected keyword argument 'decision'"):
        fixture.submit(proposal, decision=unrelated_allow)
    with pytest.raises(TypeError, match="unexpected keyword argument 'contract'"):
        fixture.submit(proposal, contract=permissive)
    with pytest.raises(TypeError, match="proposal must be exactly RateBudgetProposal"):
        fixture.submit(unrelated_allow)
    assert fixture.accepted_state is before

    result = fixture.submit(proposal)
    assert type(result) is BlockedSubmission
    assert result.decision.contract is contract
    assert result.decision.contract.maximum_rate.value == 120
    assert fixture.accepted_state is before


def test_every_submission_performs_fresh_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract, _, fixture = _baseline()
    observed = _record_validation(monkeypatch, fixture)
    proposal = _proposal(120)

    first = fixture.submit(proposal)
    second = fixture.submit(proposal)

    assert type(first) is AcceptedSubmission
    assert type(second) is AcceptedSubmission
    assert len(observed) == 2
    assert first.decision is observed[0][1]
    assert second.decision is observed[1][1]
    assert second.decision is not first.decision
    assert all(decision.proposal is proposal for _, decision in observed)
    assert all(decision.contract is contract for _, decision in observed)


class _CoercibleRate:
    def __int__(self) -> int:
        raise AssertionError("rate construction must not invoke coercion")


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (-1, ValueError),
        (True, TypeError),
        (120.0, TypeError),
        (Decimal("120"), TypeError),
        ("120", TypeError),
        (_CoercibleRate(), TypeError),
    ],
)
def test_rate_rejects_noncanonical_inputs(value: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        RateUnitsPerSecond(value)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"request_id": " \t"}, ValueError),
        ({"request_id": 1}, TypeError),
        ({"action": "SET_RATE_BUDGET"}, TypeError),
        ({"target": "FIXTURE_SERVICE"}, TypeError),
        ({"proposed_rate": 120}, TypeError),
    ],
)
def test_proposal_rejects_malformed_fields_before_semantic_validation(
    changes: dict[str, object], error: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, before, fixture = _baseline()
    observed = _record_validation(monkeypatch, fixture)
    with pytest.raises(error):
        fixture.submit(replace(_proposal(300), **changes))
    assert observed == []
    assert fixture.accepted_state is before


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"contract_id": " "}, ValueError),
        ({"contract_id": None}, TypeError),
        ({"contract_version": 0}, ValueError),
        ({"contract_version": -1}, ValueError),
        ({"contract_version": True}, TypeError),
        ({"contract_version": 1.0}, TypeError),
        ({"target": "another-service"}, TypeError),
        ({"maximum_rate": 120}, TypeError),
    ],
)
def test_contract_rejects_malformed_authority(
    changes: dict[str, object], error: type[Exception]
) -> None:
    contract, _, _ = _baseline()
    with pytest.raises(error):
        replace(contract, **changes)


def test_invalid_initial_state_is_a_setup_error() -> None:
    contract, initial, _ = _baseline()
    with pytest.raises(
        ValueError, match="initial configured rate must not exceed maximum"
    ):
        GovernedRateBudgetFixture(
            contract=contract,
            initial_state=replace(initial, configured_rate=RateUnitsPerSecond(121)),
        )
    with pytest.raises(TypeError, match="target must be exactly RateBudgetTarget"):
        replace(initial, target="another-service")
    with pytest.raises(
        TypeError, match="configured_rate must be exactly RateUnitsPerSecond"
    ):
        replace(initial, configured_rate=100)


def test_supported_targets_actions_and_rule_are_closed() -> None:
    assert list(ConfigurationAction) == [ConfigurationAction.SET_RATE_BUDGET]
    assert list(RateBudgetTarget) == [RateBudgetTarget.FIXTURE_SERVICE]
    assert list(RateBudgetRuleId) == [RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM]
    assert list(ValidationVerdict) == [ValidationVerdict.PASSED, ValidationVerdict.FAILED]
    assert list(EnforcementAction) == [EnforcementAction.ALLOW, EnforcementAction.BLOCK]
    with pytest.raises(ValueError):
        RateBudgetTarget("another-service")
    with pytest.raises(ValueError):
        ConfigurationAction("INCREMENT_RATE_BUDGET")


def test_complete_identity_is_explicit_and_public_contracts_are_immutable() -> None:
    contract, before, fixture = _baseline()
    proposal = _proposal(300)
    fresh_identity = replace(proposal, request_id="fixture-request-002")
    changed_value = replace(proposal, proposed_rate=RateUnitsPerSecond(200))
    assert fresh_identity != proposal
    assert fresh_identity.proposed_rate is proposal.proposed_rate
    assert changed_value != proposal
    assert changed_value.request_id == proposal.request_id
    assert [field.name for field in fields(RateBudgetProposal)] == [
        "request_id",
        "action",
        "target",
        "proposed_rate",
    ]

    blocked = fixture.submit(proposal)
    accepted = fixture.submit(_proposal(110, "fixture-request-003"))
    assert type(blocked) is BlockedSubmission
    assert type(accepted) is AcceptedSubmission
    for value in (
        proposal.proposed_rate,
        proposal,
        contract,
        before,
        blocked.decision,
        blocked,
        accepted.decision,
        accepted,
    ):
        name = fields(value)[0].name
        with pytest.raises(FrozenInstanceError):
            setattr(value, name, getattr(value, name))
    with pytest.raises(AttributeError):
        fixture.accepted_state = before
    assert fixture.accepted_state is accepted.accepted_state

    assert [field.name for field in fields(blocked.decision)] == ["proposal", "contract"]
    with pytest.raises(TypeError, match="unexpected keyword argument 'verdict'"):
        RateBudgetValidationAllowed(
            proposal=_proposal(120), contract=contract, verdict=ValidationVerdict.PASSED
        )
    with pytest.raises(TypeError, match="unexpected keyword argument 'rule_id'"):
        RateBudgetRejectionEvidence(
            proposal=proposal,
            contract=contract,
            rule_id=RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM,
        )


def test_submission_rejects_proposal_subclass() -> None:
    class UnsupportedProposal(RateBudgetProposal):
        pass

    _, before, fixture = _baseline()
    proposal = _proposal(120)
    unsupported = UnsupportedProposal(
        request_id=proposal.request_id,
        action=proposal.action,
        target=proposal.target,
        proposed_rate=proposal.proposed_rate,
    )
    with pytest.raises(TypeError, match="proposal must be exactly RateBudgetProposal"):
        fixture.submit(unsupported)
    assert fixture.accepted_state is before
