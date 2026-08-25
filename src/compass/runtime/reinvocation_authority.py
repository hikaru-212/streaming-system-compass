"""Producer-neutral contracts for same-request re-invocation authority."""

from __future__ import annotations

from dataclasses import dataclass

from src.storage.idempotency_store import RequestSignature


@dataclass(frozen=True, init=False)
class ReinvocationAuthorization:
    """Represent issued authority for one additional invocation of one request.

    Args:
        request_signature: The complete request identity for which authority was
            issued. Equality follows the existing frozen ``RequestSignature``
            contract across request ID, command type, order ID, and amount.

    Instances are produced only through a reviewed Stage 4E evaluator. This
    limits accidental free construction in normal use; it is not an object-
    security or authenticity boundary.

    The contract records immutable issuance meaning only. It does not own
    consumption availability, mutable spent state, synchronization, a writer,
    an execution callable, strategy selection, composition, retry policy,
    timing, persistence, or execution identity.
    """

    request_signature: RequestSignature

    def __init__(self) -> None:
        """Reject direct construction outside a reviewed Stage 4E evaluator."""

        raise TypeError(
            "ReinvocationAuthorization must be produced by a reviewed "
            "Stage 4E evaluator"
        )

    @classmethod
    def _from_evaluation(
        cls,
        *,
        request_signature: RequestSignature,
    ) -> "ReinvocationAuthorization":
        """Construct immutable authority from one reviewed evaluation."""

        if not isinstance(request_signature, RequestSignature):
            raise TypeError("request_signature must be RequestSignature")

        instance = object.__new__(cls)
        object.__setattr__(instance, "request_signature", request_signature)
        return instance


@dataclass(frozen=True, init=False)
class NoReinvocationAuthority:
    """Represent typed absence of Stage 4E authority for assessed evidence.

    Args:
        request_signature: The complete request identity that was assessed.
        explanation: Non-empty review text describing why the first profile did
            not issue authority. It is not authoritative policy input.

    This result is neither a reviewed denial nor a permanent prohibition. It
    carries no execution instruction, generic evidence bag, retry-policy
    taxonomy, lifecycle state, or persistence responsibility.
    """

    request_signature: RequestSignature
    explanation: str

    def __init__(self) -> None:
        """Reject direct construction outside a reviewed Stage 4E evaluator."""

        raise TypeError(
            "NoReinvocationAuthority must be produced by a reviewed "
            "Stage 4E evaluator"
        )

    @classmethod
    def _from_evaluation(
        cls,
        *,
        request_signature: RequestSignature,
        explanation: str,
    ) -> "NoReinvocationAuthority":
        """Construct typed no-authority from one reviewed evaluation."""

        if not isinstance(request_signature, RequestSignature):
            raise TypeError("request_signature must be RequestSignature")
        if not isinstance(explanation, str):
            raise TypeError("explanation must be str")
        if not explanation.strip():
            raise ValueError("explanation must be a non-empty string")

        instance = object.__new__(cls)
        object.__setattr__(instance, "request_signature", request_signature)
        object.__setattr__(instance, "explanation", explanation)
        return instance


__all__ = (
    "NoReinvocationAuthority",
    "ReinvocationAuthorization",
)
