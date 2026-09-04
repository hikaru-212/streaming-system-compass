"""Deterministic experiment-local recovery proposal model.

This first slice converts one bounded completed write-side observation into a
proposal or no proposal.  The planner is intentionally more eager than the
current Stage 4E authority evaluator: both typed and evidence-less append
``STALE_WRITE`` results produce the same proposed consequence.

Proposal generation is not authority evaluation or execution.  This module has
no authority artifact, invocation owner, writer, persistence, retry-loop, or
runtime-decision responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.storage.idempotency_store import RequestSignature


class RecoveryActionKind(str, Enum):
    """Closed proposed-consequence vocabulary for the first experiment slice.

    The value describes planner intent.  It is not an execution command,
    authority flag, retry classification, or permission to invoke a writer.
    """

    ONE_FRESH_SAME_REQUEST_INVOCATION = "ONE_FRESH_SAME_REQUEST_INVOCATION"


@dataclass(frozen=True)
class RecoveryProposal:
    """Retain one experiment-local proposal and its exact live source objects.

    Args:
        request_signature: Complete request identity supplied to the planner.
        source_result: Exact completed write-side result supplied to the planner.
        action: Closed proposed consequence selected by the planner.

    Object identity here preserves live in-process experiment custody only.  It
    is not durable provenance, restart-safe identity, distributed authority
    binding, or evidence that the proposed consequence is authorized.
    """

    request_signature: RequestSignature
    source_result: PostgresWriteSideResult
    action: RecoveryActionKind

    def __post_init__(self) -> None:
        """Validate only the proposal's three top-level contract types."""

        _require_request_signature(self.request_signature)
        _require_result(self.source_result)
        if not isinstance(self.action, RecoveryActionKind):
            raise TypeError("action must be RecoveryActionKind")


def plan_recovery(
    *,
    request_signature: RequestSignature,
    result: PostgresWriteSideResult,
) -> RecoveryProposal | None:
    """Propose one fresh same-request invocation for coarse append staleness.

    Args:
        request_signature: Complete live request identity retained by the caller.
        result: Exact completed PostgreSQL write-side result.

    Returns:
        A proposal retaining the exact supplied objects when the completed result
        is an append-phase ``STALE_WRITE`` with no accepted event; otherwise
        ``None``.

    Raises:
        TypeError: If either top-level input has the wrong production type.

    The predicate deliberately does not inspect typed version-mismatch evidence,
    version direction, candidate or validation coherence, idempotency or stream
    profiles, or human reason text.  Those distinctions do not belong to this
    experimental proposal generator.  In particular, a returned proposal does
    not imply retryability, re-invocation authority, or permission to execute.
    """

    _require_request_signature(request_signature)
    _require_result(result)

    admission_result = result.admission_result
    if (
        result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        and result.accepted_event is None
        and admission_result is not None
        and admission_result.verdict is AdmissionVerdict.STALE_WRITE
    ):
        return RecoveryProposal(
            request_signature=request_signature,
            source_result=result,
            action=RecoveryActionKind.ONE_FRESH_SAME_REQUEST_INVOCATION,
        )

    return None


def _require_request_signature(value: object) -> None:
    """Reject a malformed top-level request identity without revalidating it."""

    if type(value) is not RequestSignature:
        raise TypeError("request_signature must be RequestSignature")


def _require_result(value: object) -> None:
    """Reject a malformed top-level result without revalidating producer fields."""

    if type(value) is not PostgresWriteSideResult:
        raise TypeError("result must be PostgresWriteSideResult")


__all__ = (
    "RecoveryActionKind",
    "RecoveryProposal",
    "plan_recovery",
)
