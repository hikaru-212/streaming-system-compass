"""Propose revised fixture intent without validation, submission, or authority.

Trusted composition supplies an observed blocked submission and retains its
original proposal. Exact object correlation and operand coherence do not
authenticate these publicly constructible carriers. This module owns only two
deterministic proposal policies, not accepted state or request memory.
"""

from __future__ import annotations

from enum import Enum

from experiments.validation_blocked_semantic_replanning.model import (
    BlockedSubmission,
    RateBudgetProposal,
    RateUnitsPerSecond,
)


class RateBudgetRepairPolicy(str, Enum):
    """Select a proposal transformation, never the revised admission outcome.

    The maximum policy chooses the observed bound. The reduction policy retains
    two-thirds of the rejected rate, rounded down in exact integer units, and
    does not clamp to the bound. Either output still requires fresh governance.
    """

    USE_OBSERVED_MAXIMUM = "USE_OBSERVED_MAXIMUM"
    REDUCE_OBSERVED_RATE_BY_ONE_THIRD = "REDUCE_OBSERVED_RATE_BY_ONE_THIRD"


def _require_exact(value: object, expected: type, name: str) -> None:
    """Reject unsupported types without coercion or subclass behavior."""

    if type(value) is not expected:
        raise TypeError(f"{name} must be exactly {expected.__name__}")


def plan_rate_budget_repair(
    blocked_submission: BlockedSubmission,
    *,
    original_proposal: RateBudgetProposal,
    new_request_id: str,
    policy: RateBudgetRepairPolicy,
) -> RateBudgetProposal:
    """Form one changed proposal from eligible live rejection evidence.

    Inputs are the exact observed BlockedSubmission, caller-retained original
    proposal, an explicit caller-owned new request ID, and one closed policy.
    Return only a new immutable RateBudgetProposal preserving action and target.
    No fixture, validator, submission, persistence, or authority is involved.

    Raise TypeError for unsupported exact input types. Raise ValueError for
    different source custody, incoherent rejection operands, reused request ID,
    or an unchanged semantic rate. Normal proposal construction rejects blank
    IDs and preserves their spelling. Freshness is relative to this original
    request only; the caller owns global identity and any subsequent submission.

    The coherence guard is not a second validation decision or authentication.
    Trusted composition must supply the actual live result: even coherent
    publicly constructed dataclasses do not prove governed rejection occurred.
    """

    _require_exact(blocked_submission, BlockedSubmission, "blocked_submission")
    _require_exact(original_proposal, RateBudgetProposal, "original_proposal")
    _require_exact(new_request_id, str, "new_request_id")
    _require_exact(policy, RateBudgetRepairPolicy, "policy")

    evidence = blocked_submission.decision
    if evidence.proposal is not original_proposal:
        raise ValueError("original_proposal must be the exact rejected proposal")

    original_rate = evidence.proposal.proposed_rate
    maximum_rate = evidence.contract.maximum_rate
    # Carrier construction checks types, not this failed comparison.
    if original_rate.value <= maximum_rate.value:
        raise ValueError("rejection proposed rate must exceed its retained maximum")
    if new_request_id == original_proposal.request_id:
        raise ValueError("new_request_id must differ from the original request ID")

    if policy is RateBudgetRepairPolicy.USE_OBSERVED_MAXIMUM:
        revised_rate = maximum_rate
    elif policy is RateBudgetRepairPolicy.REDUCE_OBSERVED_RATE_BY_ONE_THIRD:
        revised_rate = RateUnitsPerSecond((2 * original_rate.value) // 3)
    else:
        raise ValueError("unsupported repair policy")

    if revised_rate == original_rate:
        raise ValueError("repair must change the proposed rate")
    return RateBudgetProposal(
        request_id=new_request_id,
        action=original_proposal.action,
        target=original_proposal.target,
        proposed_rate=revised_rate,
    )
