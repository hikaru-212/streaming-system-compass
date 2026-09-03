"""Experiment-local controlled execution over existing owner-held authority."""

from __future__ import annotations

from dataclasses import dataclass

from experiments.deterministic_autonomous_governance.model import (
    RecoveryActionKind,
    RecoveryProposal,
)
from src.compass.runtime.reinvocation_authority import (
    NoReinvocationAuthority,
    ReinvocationAuthorization,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideInvocationOwner,
)
from src.storage.idempotency_store import RequestSignature


class ControlledExecutionRefused(RuntimeError):
    """Report experiment-local proposal/authority incompatibility.

    This refusal is not a Stage 4E denial or an owner lifecycle failure. Once
    execution is delegated to the production invocation owner, owner and writer
    results or failures propagate unchanged.
    """


@dataclass(frozen=True)
class ControlledExecutor:
    """Bind one proposal check to independent assessment and live owner custody.

    Args:
        owner: Exact production owner retaining the writer and A1/A2 lifecycle.
        expected_signature: Complete request identity expected by this binding.
        retained_a1_result: Exact live A1 result expected as proposal source.
        reinvocation_assessment: Independently established Stage 4E result.

    The executor does not evaluate or mint authority, retain a writer, or own
    AVAILABLE/SPENT state. Its only execution path delegates to the existing
    owner's one-shot ``invoke_authorized_reinvocation`` boundary.
    """

    owner: PostgresWriteSideInvocationOwner
    expected_signature: RequestSignature
    retained_a1_result: PostgresWriteSideResult
    reinvocation_assessment: (
        ReinvocationAuthorization | NoReinvocationAuthority
    )

    def __post_init__(self) -> None:
        """Require the exact current experiment and production carriers."""

        if type(self.owner) is not PostgresWriteSideInvocationOwner:
            raise TypeError("owner must be PostgresWriteSideInvocationOwner")
        if type(self.expected_signature) is not RequestSignature:
            raise TypeError("expected_signature must be RequestSignature")
        if type(self.retained_a1_result) is not PostgresWriteSideResult:
            raise TypeError(
                "retained_a1_result must be PostgresWriteSideResult"
            )
        assessment_type = type(self.reinvocation_assessment)
        if assessment_type not in {
            ReinvocationAuthorization,
            NoReinvocationAuthority,
        }:
            raise TypeError(
                "reinvocation_assessment must be ReinvocationAuthorization "
                "or NoReinvocationAuthority"
            )

    def execute(self, proposal: RecoveryProposal) -> PostgresWriteSideResult:
        """Execute one compatible proposal through the retained live owner.

        Raises:
            ControlledExecutionRefused: If the proposal is unsupported, its
                source or complete request identity mismatches this binding, or
                the independently supplied Stage 4E assessment is non-authorizing
                or has a different complete request identity.
            PostgresWriteSideInvocationLifecycleError: Unchanged from the owner
                when its independently cached authority is unavailable or spent.
            Exception: Any owner or retained-writer failure, unchanged.

        No check here evaluates Stage 4E or establishes owner-local availability.
        """

        if type(proposal) is not RecoveryProposal:
            raise ControlledExecutionRefused(
                "proposal must be the exact RecoveryProposal type"
            )

        if (
            proposal.action
            is not RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION
        ):
            raise ControlledExecutionRefused(
                "proposal action is unsupported by ControlledExecutor"
            )

        if proposal.source_result is not self.retained_a1_result:
            raise ControlledExecutionRefused(
                "proposal source_result is not the retained live A1 result"
            )

        if proposal.request_signature != self.expected_signature:
            raise ControlledExecutionRefused(
                "proposal request_signature does not equal expected_signature"
            )

        assessment = self.reinvocation_assessment
        if type(assessment) is NoReinvocationAuthority:
            raise ControlledExecutionRefused(
                "independent Stage 4E assessment issued no authority"
            )

        if (
            assessment.request_signature != self.expected_signature
            or assessment.request_signature != proposal.request_signature
        ):
            raise ControlledExecutionRefused(
                "authorization request_signature does not match the complete "
                "expected and proposed request identity"
            )

        return self.owner.invoke_authorized_reinvocation()


__all__ = (
    "ControlledExecutionRefused",
    "ControlledExecutor",
)
