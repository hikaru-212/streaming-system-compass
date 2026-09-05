"""Witness changed proposal intent without transferring fixture authority."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, fields, replace

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
)
from experiments.validation_blocked_semantic_replanning.planner import (
    RateBudgetRepairPolicy,
    plan_rate_budget_repair,
)


def _proposal(rate: int, request_id: str = "fixture-request-001") -> RateBudgetProposal:
    return RateBudgetProposal(
        request_id=request_id,
        action=ConfigurationAction.SET_RATE_BUDGET,
        target=RateBudgetTarget.FIXTURE_SERVICE,
        proposed_rate=RateUnitsPerSecond(rate),
    )


def _baseline(initial: int = 100, maximum: int = 120):
    contract = RateBudgetContract(
        contract_id="experiment.rate_budget",
        contract_version=1,
        target=RateBudgetTarget.FIXTURE_SERVICE,
        maximum_rate=RateUnitsPerSecond(maximum),
    )
    state = AcceptedRateBudgetState(
        target=contract.target, configured_rate=RateUnitsPerSecond(initial)
    )
    return contract, state, GovernedRateBudgetFixture(
        contract=contract, initial_state=state
    )


def _record_governance(monkeypatch: pytest.MonkeyPatch, fixture):
    submissions = []
    validations = []
    real_submit = GovernedRateBudgetFixture.submit
    real_validate = model.validate_rate_budget

    def record_submit(owner, proposal):
        assert owner is fixture
        submissions.append(proposal)
        return real_submit(owner, proposal)

    def record_validate(proposal, *, contract):
        before = fixture.accepted_state
        decision = real_validate(proposal, contract=contract)
        assert fixture.accepted_state is before
        validations.append((before, decision))
        return decision

    # These observers preserve real submission and validation behavior.
    monkeypatch.setattr(GovernedRateBudgetFixture, "submit", record_submit)
    monkeypatch.setattr(model, "validate_rate_budget", record_validate)
    return submissions, validations


@pytest.mark.parametrize(
    ("policy", "new_id", "revised_rate"),
    [
        (RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM, "fixture-request-002", 120),
        (
            RateBudgetRepairPolicy.REDUCE_OBSERVED_RATE_BY_ONE_THIRD,
            "fixture-request-003",
            200,
        ),
    ],
    ids=["C1-valid-revision", "C2-invalid-revision"],
)
def test_a_b_and_independent_regoverned_revision(
    policy, new_id, revised_rate, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each case has its own equivalent baseline; C2 never follows C1's mutation.
    contract, initial, fixture = _baseline()
    original = _proposal(300)
    original_snapshot = replace(original)
    contract_snapshot = replace(contract)
    submissions, validations = _record_governance(monkeypatch, fixture)

    # A: the ordinary owner produces the real rejection and keeps state intact.
    blocked = fixture.submit(original)
    assert type(blocked) is BlockedSubmission
    evidence = blocked.decision
    evidence_snapshot = replace(evidence)
    assert type(evidence) is RateBudgetRejectionEvidence
    assert evidence is validations[0][1]
    assert evidence.proposal is original
    assert evidence.contract is contract
    assert evidence.verdict is ValidationVerdict.FAILED
    assert evidence.enforcement_action is EnforcementAction.BLOCK
    assert evidence.rule_id is RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM
    assert evidence.proposal.proposed_rate.value == 300
    assert evidence.contract.maximum_rate.value == 120
    assert fixture.accepted_state is initial
    assert initial.configured_rate.value == 100

    # B: planning creates intent without invoking either governance entry point.
    revised = plan_rate_budget_repair(
        blocked,
        original_proposal=original,
        new_request_id=new_id,
        policy=policy,
    )
    assert type(revised) is RateBudgetProposal
    assert revised is not original
    assert revised.request_id == new_id
    assert revised.request_id != original.request_id
    assert revised.proposed_rate.value == revised_rate
    assert revised.proposed_rate != original.proposed_rate
    assert revised.action is original.action
    assert revised.target is original.target
    assert original == original_snapshot
    assert contract == contract_snapshot
    assert blocked.decision is evidence
    assert evidence == evidence_snapshot
    assert evidence.proposal is original
    assert evidence.contract is contract
    assert fixture.accepted_state is initial
    assert submissions == [original]
    assert len(validations) == 1
    assert [field.name for field in fields(revised)] == [
        "request_id", "action", "target", "proposed_rate"
    ]
    with pytest.raises(FrozenInstanceError):
        revised.request_id = "mutated"
    with pytest.raises(FrozenInstanceError):
        revised.proposed_rate.value = 999

    # C1/C2: only this explicit submission may validate and change owner state.
    result = fixture.submit(revised)
    assert len(submissions) == 2
    assert submissions[0] is original
    assert submissions[1] is revised
    assert len(validations) == 2
    assert validations[0][0] is initial
    assert validations[1][0] is initial
    assert result.decision is validations[1][1]
    assert result.decision is not evidence
    assert result.decision.proposal is revised
    assert result.decision.contract is contract
    if policy is RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM:
        assert type(result) is AcceptedSubmission
        assert type(result.decision) is RateBudgetValidationAllowed
        assert result.decision.verdict is ValidationVerdict.PASSED
        assert result.decision.enforcement_action is EnforcementAction.ALLOW
        assert fixture.accepted_state is result.accepted_state
        assert result.accepted_state is not initial
        assert result.accepted_state.configured_rate is revised.proposed_rate
        assert result.accepted_state.configured_rate.value == 120
    else:
        assert type(result) is BlockedSubmission
        assert type(result.decision) is RateBudgetRejectionEvidence
        assert result.decision.verdict is ValidationVerdict.FAILED
        assert result.decision.enforcement_action is EnforcementAction.BLOCK
        assert result.decision.rule_id is RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM
        assert result.decision.proposal.proposed_rate.value == 200
        assert result.decision.contract.maximum_rate.value == 120
        assert fixture.accepted_state is initial
        assert fixture.accepted_state.configured_rate.value == 100
    assert original == original_snapshot
    assert contract == contract_snapshot
    assert evidence == evidence_snapshot


def test_same_live_evidence_supports_different_proposal_policies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract, initial, fixture = _baseline()
    original = _proposal(300)
    submissions, validations = _record_governance(monkeypatch, fixture)
    blocked = fixture.submit(original)
    evidence = blocked.decision
    snapshot = (replace(original), replace(contract), replace(evidence))

    at_maximum = plan_rate_budget_repair(
        blocked,
        original_proposal=original,
        new_request_id="fixture-request-002",
        policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
    )
    reduced = plan_rate_budget_repair(
        blocked,
        original_proposal=original,
        new_request_id="fixture-request-003",
        policy=RateBudgetRepairPolicy.REDUCE_OBSERVED_RATE_BY_ONE_THIRD,
    )
    assert at_maximum.proposed_rate.value == 120
    assert reduced.proposed_rate.value == 200
    assert at_maximum.request_id != reduced.request_id
    assert at_maximum.proposed_rate != reduced.proposed_rate
    assert blocked.decision is evidence
    assert evidence.proposal is original
    assert evidence.contract is contract
    assert (original, contract, evidence) == snapshot
    assert fixture.accepted_state is initial
    assert submissions == [original]
    assert len(validations) == 1


def test_maximum_policy_consumes_retained_operand_and_preserves_id_spelling() -> None:
    contract, initial, fixture = _baseline(initial=60, maximum=80)
    original = _proposal(150)
    blocked = fixture.submit(original)
    assert type(blocked) is BlockedSubmission
    revised = plan_rate_budget_repair(
        blocked,
        original_proposal=original,
        new_request_id="  caller-owned-002  ",
        policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
    )
    assert revised.proposed_rate is contract.maximum_rate
    assert revised.proposed_rate.value == 80
    assert revised.request_id == "  caller-owned-002  "
    assert fixture.accepted_state is initial


@pytest.mark.parametrize(
    ("initial", "maximum", "original_rate", "expected"),
    [(100, 120, 301, 200), (0, 0, 1, 0), (0, 0, 10**30 + 1, 666666666666666666666666666667)],
)
def test_reduction_uses_exact_integer_units_without_a_positive_rate_rule(
    initial, maximum, original_rate, expected
) -> None:
    _, before, fixture = _baseline(initial=initial, maximum=maximum)
    original = _proposal(original_rate)
    blocked = fixture.submit(original)
    revised = plan_rate_budget_repair(
        blocked,
        original_proposal=original,
        new_request_id="reduced-002",
        policy=RateBudgetRepairPolicy.REDUCE_OBSERVED_RATE_BY_ONE_THIRD,
    )
    assert revised.proposed_rate.value == expected
    assert revised.proposed_rate != original.proposed_rate
    assert fixture.accepted_state is before


@dataclass(frozen=True)
class _UnrelatedCarrier:
    decision: object


@pytest.mark.parametrize("shape", ["accepted", "allow", "evidence", "exception", "object", "dataclass", "subclass"])
def test_planner_rejects_unsupported_result_shapes(shape: str) -> None:
    _, _, fixture = _baseline()
    original = _proposal(300)
    blocked = fixture.submit(original)
    allowed = fixture.submit(_proposal(110, "accepted-request"))

    class UnsupportedBlockedSubmission(BlockedSubmission):
        pass

    unsupported = {
        "accepted": allowed,
        "allow": allowed.decision,
        "evidence": blocked.decision,
        "exception": ValueError("construction failed"),
        "object": object(),
        "dataclass": _UnrelatedCarrier(blocked.decision),
        "subclass": UnsupportedBlockedSubmission(blocked.decision),
    }[shape]
    before = fixture.accepted_state
    with pytest.raises(TypeError, match="blocked_submission must be exactly BlockedSubmission"):
        plan_rate_budget_repair(
            unsupported,
            original_proposal=original,
            new_request_id="new-request",
            policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
        )
    assert fixture.accepted_state is before


def test_planner_requires_exact_original_proposal_custody() -> None:
    _, initial, fixture = _baseline()
    original = _proposal(300)
    blocked = fixture.submit(original)
    reconstructed = replace(original)
    assert reconstructed == original
    assert reconstructed is not original
    with pytest.raises(ValueError, match="exact rejected proposal"):
        plan_rate_budget_repair(
            blocked,
            original_proposal=reconstructed,
            new_request_id="new-request",
            policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
        )
    assert fixture.accepted_state is initial


@pytest.mark.parametrize("rate", [110, 120])
def test_manually_constructed_rejection_requires_operand_coherence(rate: int) -> None:
    # Only a coherence-boundary negative: this is not an observed governed BLOCK.
    contract, initial, fixture = _baseline()
    original = _proposal(rate)
    unsupported = BlockedSubmission(
        RateBudgetRejectionEvidence(proposal=original, contract=contract)
    )
    with pytest.raises(ValueError, match="must exceed its retained maximum"):
        plan_rate_budget_repair(
            unsupported,
            original_proposal=original,
            new_request_id="new-request",
            policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
        )
    assert fixture.accepted_state is initial


@pytest.mark.parametrize(
    ("new_id", "error"),
    [("fixture-request-001", ValueError), (" \t", ValueError), (1, TypeError)],
)
def test_planner_rejects_reused_or_malformed_request_identity(new_id, error) -> None:
    _, initial, fixture = _baseline()
    original = _proposal(300)
    blocked = fixture.submit(original)
    with pytest.raises(error):
        plan_rate_budget_repair(
            blocked,
            original_proposal=original,
            new_request_id=new_id,
            policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
        )
    assert fixture.accepted_state is initial


def test_planner_rejects_other_unsupported_input_types() -> None:
    class UnsupportedProposal(RateBudgetProposal):
        pass

    class UnsupportedIdentity(str):
        pass

    _, initial, fixture = _baseline()
    original = _proposal(300)
    blocked = fixture.submit(original)
    inputs = dict(
        original_proposal=original,
        new_request_id="new-request",
        policy=RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
    )
    for replacement in (
        {"original_proposal": object()},
        {"original_proposal": UnsupportedProposal(
            original.request_id, original.action, original.target, original.proposed_rate
        )},
        {"new_request_id": UnsupportedIdentity("new-request")},
        {"policy": "USE_OBSERVED_MAXIMUM"},
        {"policy": object()},
    ):
        with pytest.raises(TypeError):
            plan_rate_budget_repair(blocked, **(inputs | replacement))
    assert list(RateBudgetRepairPolicy) == [
        RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM,
        RateBudgetRepairPolicy.REDUCE_OBSERVED_RATE_BY_ONE_THIRD,
    ]
    assert fixture.accepted_state is initial
