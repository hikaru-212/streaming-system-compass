"""Govern one experiment-local rate-budget configuration without a planner.

Proposals carry intent, while trusted setup supplies independent authority.
Pure validation cannot change accepted state; only the synchronous fixture owner
can install the exact evaluated effect after ALLOW. This trusted in-process model
has no traffic semantics, persistence, request memory, or concurrency guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


def _require_exact(value: object, expected: type, name: str) -> None:
    """Reject unsupported contract types without coercion or subclass behavior."""

    if type(value) is not expected:
        raise TypeError(f"{name} must be exactly {expected.__name__}")


def _require_nonblank(value: object, name: str) -> None:
    """Require an explicit string identity, preserving its supplied spelling."""

    _require_exact(value, str, name)
    if not value.strip():
        raise ValueError(f"{name} must be nonblank")


@dataclass(frozen=True)
class RateUnitsPerSecond:
    """Store a nonnegative exact integer in fixed abstract fixture units/sec.

    Construction raises TypeError for non-integers, including bool, and
    ValueError for negative integers. No coercion, rounding, or unit conversion
    occurs. Zero is valid and claims no real-world traffic behavior.
    """

    value: int

    def __post_init__(self) -> None:
        """Enforce the canonical quantity representation, not a semantic maximum."""

        _require_exact(self.value, int, "value")
        if self.value < 0:
            raise ValueError("value must be nonnegative")


class ConfigurationAction(str, Enum):
    """The sole proposed operation replaces the configured rate-budget value."""

    SET_RATE_BUDGET = "SET_RATE_BUDGET"


class RateBudgetTarget(str, Enum):
    """The single synthetic service configuration slot supported by the fixture."""

    FIXTURE_SERVICE = "FIXTURE_SERVICE"


@dataclass(frozen=True)
class RateBudgetProposal:
    """Retain complete request identity and a structurally valid proposed effect.

    The caller supplies a nonblank request ID, the supported action and target,
    and a canonical rate. Construction checks only those structural contracts;
    it never obtains authority or compares the rate with a governing maximum.
    Fresh IDs are caller-owned; this model does not track prior requests.
    """

    request_id: str
    action: ConfigurationAction
    target: RateBudgetTarget
    proposed_rate: RateUnitsPerSecond

    def __post_init__(self) -> None:
        """Reject malformed request fields with TypeError or ValueError."""

        _require_nonblank(self.request_id, "request_id")
        _require_exact(self.action, ConfigurationAction, "action")
        _require_exact(self.target, RateBudgetTarget, "target")
        _require_exact(self.proposed_rate, RateUnitsPerSecond, "proposed_rate")


@dataclass(frozen=True)
class RateBudgetContract:
    """Retain independently supplied authority for one target and contract edition.

    Trusted setup owns the nonblank identity, positive exact integer version,
    target, and canonical maximum. This immutable value is not a proposal field,
    an executable policy registry, or a preferred configuration value.
    """

    contract_id: str
    contract_version: int
    target: RateBudgetTarget
    maximum_rate: RateUnitsPerSecond

    def __post_init__(self) -> None:
        """Reject malformed authority fields with TypeError or ValueError."""

        _require_nonblank(self.contract_id, "contract_id")
        _require_exact(self.contract_version, int, "contract_version")
        if self.contract_version <= 0:
            raise ValueError("contract_version must be positive")
        _require_exact(self.target, RateBudgetTarget, "target")
        _require_exact(self.maximum_rate, RateUnitsPerSecond, "maximum_rate")


@dataclass(frozen=True)
class AcceptedRateBudgetState:
    """Expose an immutable configured value for the fixture's single target.

    The fixture owner establishes acceptance; constructing this value alone
    changes no owner state. It carries no revision, history, or durable identity.
    """

    target: RateBudgetTarget
    configured_rate: RateUnitsPerSecond

    def __post_init__(self) -> None:
        """Require the closed target and canonical quantity representation."""

        _require_exact(self.target, RateBudgetTarget, "target")
        _require_exact(self.configured_rate, RateUnitsPerSecond, "configured_rate")


class ValidationVerdict(str, Enum):
    """Report whether the proposed effect satisfies fixture semantic validation."""

    PASSED = "PASSED"
    FAILED = "FAILED"


class EnforcementAction(str, Enum):
    """Describe whether validation permits proceeding toward an accepted effect."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class RateBudgetRuleId(str, Enum):
    """Identify the inclusive maximum rule for the contract's supported target."""

    RATE_BUDGET_WITHIN_MAXIMUM = "RATE_BUDGET_WITHIN_MAXIMUM"


@dataclass(frozen=True)
class RateBudgetValidationAllowed:
    """Retain exact live inputs of a successful validation without applying them.

    The validator produces this carrier; its type checks are not a second
    semantic evaluation. Neither construction nor possession authorizes a caller
    to mutate the fixture, which accepts proposals and performs its own validation.
    """

    proposal: RateBudgetProposal
    contract: RateBudgetContract

    def __post_init__(self) -> None:
        """Require exact immutable source contracts."""

        _require_exact(self.proposal, RateBudgetProposal, "proposal")
        _require_exact(self.contract, RateBudgetContract, "contract")

    @property
    def verdict(self) -> ValidationVerdict:
        """Report the fixed successful semantic verdict."""

        return ValidationVerdict.PASSED

    @property
    def enforcement_action(self) -> EnforcementAction:
        """Permit owner-controlled application without claiming an accepted effect."""

        return EnforcementAction.ALLOW


@dataclass(frozen=True)
class RateBudgetRejectionEvidence:
    """Retain exact live inputs of the validator's failed maximum comparison.

    The proposal and contract expose typed operands, units, scope, and identities.
    Fixed properties identify the rule, failure, and block. This carrier neither
    re-evaluates its sources nor prescribes repair, retry, or submission policy.
    Live object custody is not durable provenance or hostile-code authenticity.
    """

    proposal: RateBudgetProposal
    contract: RateBudgetContract

    def __post_init__(self) -> None:
        """Require exact immutable source contracts."""

        _require_exact(self.proposal, RateBudgetProposal, "proposal")
        _require_exact(self.contract, RateBudgetContract, "contract")

    @property
    def rule_id(self) -> RateBudgetRuleId:
        """Identify the failed inclusive upper-bound constraint."""

        return RateBudgetRuleId.RATE_BUDGET_WITHIN_MAXIMUM

    @property
    def verdict(self) -> ValidationVerdict:
        """Report the fixed failed semantic verdict."""

        return ValidationVerdict.FAILED

    @property
    def enforcement_action(self) -> EnforcementAction:
        """Block this evaluated proposal from proceeding to an accepted effect."""

        return EnforcementAction.BLOCK


def validate_rate_budget(
    proposal: RateBudgetProposal,
    *,
    contract: RateBudgetContract,
) -> RateBudgetValidationAllowed | RateBudgetRejectionEvidence:
    """Compare a proposed rate against independently supplied target authority.

    Return an immutable ALLOW or BLOCK carrier retaining the exact input objects.
    The inclusive bound admits zero and every other canonical rate at or below
    the maximum. This function receives no owner and performs no state mutation.

    Raise TypeError for unsupported input types. Target mismatch is an invalid
    composition (ValueError), unreachable through the current single-member
    target enum; it is not a second semantic rule or maximum-violation evidence.
    """

    _require_exact(proposal, RateBudgetProposal, "proposal")
    _require_exact(contract, RateBudgetContract, "contract")
    if proposal.target is not contract.target:
        raise ValueError("proposal target must match contract target")
    if proposal.proposed_rate.value <= contract.maximum_rate.value:
        return RateBudgetValidationAllowed(proposal=proposal, contract=contract)
    return RateBudgetRejectionEvidence(proposal=proposal, contract=contract)


@dataclass(frozen=True)
class AcceptedSubmission:
    """Retain the owner's allowing decision and exact installed immutable state.

    This completed submission result is an observation, not an execution input.
    Its state must describe precisely the evaluated proposal's target and rate.
    """

    decision: RateBudgetValidationAllowed
    accepted_state: AcceptedRateBudgetState

    def __post_init__(self) -> None:
        """Reject unsupported result fields or a different proposed effect."""

        _require_exact(self.decision, RateBudgetValidationAllowed, "decision")
        _require_exact(self.accepted_state, AcceptedRateBudgetState, "accepted_state")
        proposal = self.decision.proposal
        if (
            self.accepted_state.target is not proposal.target
            or self.accepted_state.configured_rate != proposal.proposed_rate
        ):
            raise ValueError("accepted state must match the evaluated proposal")


@dataclass(frozen=True)
class BlockedSubmission:
    """Retain the exact rejection evidence from a submission with no state effect."""

    decision: RateBudgetRejectionEvidence

    def __post_init__(self) -> None:
        """Require the exact experiment-local rejection evidence type."""

        _require_exact(self.decision, RateBudgetRejectionEvidence, "decision")


class GovernedRateBudgetFixture:
    """Own independent authority and one synchronous in-memory configuration.

    Trusted setup supplies the contract and an admissible initial state. Only
    submit replaces accepted state; observations are immutable. There is no
    contract override, externally supplied decision, request memory, or public
    application method. Encapsulation assumes ordinary trusted Python use, not
    hostile reflection, concurrent calls, restart recovery, or durable effects.
    """

    __slots__ = ("_contract", "_accepted_state")

    def __init__(
        self,
        *,
        contract: RateBudgetContract,
        initial_state: AcceptedRateBudgetState,
    ) -> None:
        """Retain valid setup or raise TypeError/ValueError before initialization.

        An out-of-contract baseline is a setup error, not a proposal rejection.
        Target mismatch is unrepresentable through the current closed enum.
        """

        _require_exact(contract, RateBudgetContract, "contract")
        _require_exact(initial_state, AcceptedRateBudgetState, "initial_state")
        if initial_state.target is not contract.target:
            raise ValueError("initial state target must match contract target")
        if initial_state.configured_rate.value > contract.maximum_rate.value:
            raise ValueError("initial configured rate must not exceed maximum")
        self._contract = contract
        self._accepted_state = initial_state

    @property
    def accepted_state(self) -> AcceptedRateBudgetState:
        """Return the exact current immutable accepted-state observation."""

        return self._accepted_state

    def submit(
        self, proposal: RateBudgetProposal
    ) -> AcceptedSubmission | BlockedSubmission:
        """Freshly validate one proposal and apply its exact effect only on ALLOW.

        BLOCK returns the exact rejection evidence without replacing state.
        ALLOW constructs the next state and complete result before the single
        owner-local replacement. Structural or validation exceptions propagate
        before mutation. Earlier decisions are never accepted as submission input.
        """

        _require_exact(proposal, RateBudgetProposal, "proposal")
        decision = validate_rate_budget(proposal, contract=self._contract)
        if type(decision) is RateBudgetRejectionEvidence:
            return BlockedSubmission(decision=decision)

        # Apply from the retained evaluated proposal, with no second value input.
        next_state = AcceptedRateBudgetState(
            target=decision.proposal.target,
            configured_rate=decision.proposal.proposed_rate,
        )
        result = AcceptedSubmission(decision=decision, accepted_state=next_state)
        # All fallible construction precedes this sole submission-state mutation.
        self._accepted_state = next_state
        return result
