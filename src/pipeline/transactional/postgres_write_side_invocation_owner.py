"""Live one-shot owner for one PostgreSQL write-side request lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from typing import TypeAlias
from uuid import UUID, uuid4

from src.compass.runtime.postgres_write_side_reinvocation_authority import (
    PostgresWriteSideReinvocationAuthorityEvaluation,
    evaluate_postgres_write_side_reinvocation_authority,
)
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.compass.runtime.runtime_decision import RuntimeDecisionResponse
from src.compass.runtime.write_side_rule_feedback import (
    PostgresWriteSideSemanticRuleFeedback,
    map_postgres_write_side_result_to_semantic_rule_feedback,
)
from src.compass.runtime.write_side_runtime_decision import (
    PostgresWriteSideRuntimeDecisionEvaluation,
    PostgresWriteSideRuntimeDecisionRefused,
    evaluate_postgres_write_side_runtime_decision,
)
from src.core.order.enums import CommandType
from src.core.order.events import OrderEvent
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.storage.idempotency_store import (
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


class PostgresWriteSideInvocationLifecycleError(RuntimeError):
    """Report invalid use of one PostgreSQL invocation-owner lifecycle.

    This exception represents owner-local execution-state misuse, such as
    duplicate A1 entry, evaluation before normal A1 completion, or unavailable
    one-shot authority. It is not Stage 4E semantic no-authority, retry policy,
    or a durable lifecycle status.
    """


@dataclass(frozen=True, init=False)
class PostgresWriteSideCurrentResponseEvaluation:
    """Deliver one decided Stage 4C response for the exact current result.

    The owner is the trusted in-process construction boundary. The delivery
    retains the exact producer result and existing profile evaluation. Its
    selected result is the exact current result, the exact producer-carried
    prior accepted event, or ``None`` when the decision does not select an
    ordinary caller result. It does not execute the response or establish
    durable provenance.
    """

    producer_result: PostgresWriteSideResult
    evaluation: PostgresWriteSideRuntimeDecisionEvaluation
    selected_result: PostgresWriteSideResult | OrderEvent | None

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Reject construction outside the invocation-owner flow."""

        raise TypeError(
            "PostgresWriteSideCurrentResponseEvaluation must be produced by "
            "PostgresWriteSideInvocationOwner"
        )

    @classmethod
    def _from_owner(
        cls,
        *,
        request_signature: RequestSignature,
        producer_result: PostgresWriteSideResult,
        evaluation: PostgresWriteSideRuntimeDecisionEvaluation,
    ) -> "PostgresWriteSideCurrentResponseEvaluation":
        """Build one coherent owner-bound decided delivery."""

        if not isinstance(request_signature, RequestSignature):
            raise TypeError("request_signature must be RequestSignature")
        if not isinstance(producer_result, PostgresWriteSideResult):
            raise TypeError("producer_result must be PostgresWriteSideResult")
        if not isinstance(
            evaluation,
            PostgresWriteSideRuntimeDecisionEvaluation,
        ):
            raise TypeError(
                "evaluation must be "
                "PostgresWriteSideRuntimeDecisionEvaluation"
            )

        response = evaluation.decision.response
        if response is RuntimeDecisionResponse.USE_CURRENT_RESULT:
            selected_result: PostgresWriteSideResult | OrderEvent | None = (
                producer_result
            )
        elif response is RuntimeDecisionResponse.RETURN_PRIOR_ACCEPTED_RESULT:
            selected_result = _exact_prior_accepted_event(
                request_signature=request_signature,
                producer_result=producer_result,
            )
        elif response in {
            RuntimeDecisionResponse.BLOCK_CURRENT_CONTINUATION,
            RuntimeDecisionResponse.REQUIRE_ESCALATION,
        }:
            selected_result = None
        else:
            raise AssertionError(
                f"unsupported RuntimeDecisionResponse: {response}"
            )

        instance = object.__new__(cls)
        object.__setattr__(instance, "producer_result", producer_result)
        object.__setattr__(instance, "evaluation", evaluation)
        object.__setattr__(instance, "selected_result", selected_result)
        return instance


@dataclass(frozen=True, init=False)
class PostgresWriteSideCurrentResponseRefusal:
    """Deliver typed absence of Stage 4C current-response authority.

    This artifact retains the exact current producer result, exact mapped
    feedback, and exact evaluator refusal. It deliberately has no
    ``RuntimeDecision`` or selected-result field. Refusal is not block, denial,
    escalation, permission to continue, or a Stage 4E result.
    """

    producer_result: PostgresWriteSideResult
    source_feedback: PostgresWriteSideSemanticRuleFeedback
    refusal: PostgresWriteSideRuntimeDecisionRefused

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Reject construction outside the invocation-owner flow."""

        raise TypeError(
            "PostgresWriteSideCurrentResponseRefusal must be produced by "
            "PostgresWriteSideInvocationOwner"
        )

    @classmethod
    def _from_owner(
        cls,
        *,
        producer_result: PostgresWriteSideResult,
        source_feedback: PostgresWriteSideSemanticRuleFeedback,
        refusal: PostgresWriteSideRuntimeDecisionRefused,
    ) -> "PostgresWriteSideCurrentResponseRefusal":
        """Build one coherent owner-bound refused delivery."""

        if not isinstance(producer_result, PostgresWriteSideResult):
            raise TypeError("producer_result must be PostgresWriteSideResult")
        if not isinstance(
            source_feedback,
            PostgresWriteSideSemanticRuleFeedback,
        ):
            raise TypeError(
                "source_feedback must be "
                "PostgresWriteSideSemanticRuleFeedback"
            )
        if not isinstance(refusal, PostgresWriteSideRuntimeDecisionRefused):
            raise TypeError(
                "refusal must be PostgresWriteSideRuntimeDecisionRefused"
            )

        instance = object.__new__(cls)
        object.__setattr__(instance, "producer_result", producer_result)
        object.__setattr__(instance, "source_feedback", source_feedback)
        object.__setattr__(instance, "refusal", refusal)
        return instance


PostgresWriteSideCurrentResponseDelivery: TypeAlias = (
    PostgresWriteSideCurrentResponseEvaluation
    | PostgresWriteSideCurrentResponseRefusal
)


class PostgresWriteSideInvocationOwner:
    """Own one live PostgreSQL A1 and at most one authorized A2 invocation.

    Args:
        request_signature: Complete immutable identity dispatched for both A1
            and any authorized A2.
        writer: Already-configured PostgreSQL public writer whose connection,
            validation runtime, configuration, and admission-gate factory are
            retained as the execution composition.

    The owner invokes A1 itself, retains the exact normally returned result for
    Stage 4E, and publishes the latest normal invocation result for explicit
    Stage 4C current-response evaluation. One stable outcome identity and one
    decided or refused delivery are cached for only that current result. The
    owner also lazily evaluates and caches the existing Stage 4E PostgreSQL
    authority result and atomically spends positive authority before A2 writer
    entry. One owner-scoped non-reentrant lock protects all mutable lifecycle
    publication, but is never held while the writer performs database work.

    Writer exceptions propagate unchanged. An A1 exception permanently uses
    the initial invocation without publishing a completed result. Every A2
    result or exception leaves authority spent. This in-process owner provides
    neither durable provenance nor application continuation enforcement,
    attempt history, retry scheduling, strategy selection, new Stage 4C policy,
    restart recovery, distributed consumption, or A3.
    """

    def __init__(
        self,
        *,
        request_signature: RequestSignature,
        writer: PostgresTransactionalWriteSide,
    ) -> None:
        """Validate and retain one complete request and configured writer."""

        _validate_request_signature(request_signature)
        if not isinstance(writer, PostgresTransactionalWriteSide):
            raise TypeError("writer must be PostgresTransactionalWriteSide")

        self._request_signature = request_signature
        self._writer = writer
        self._initial_invocation_started = False
        self._initial_result: PostgresWriteSideResult | None = None
        self._cached_reinvocation_evaluation: (
            PostgresWriteSideReinvocationAuthorityEvaluation | None
        ) = None
        self._authority_spent = False
        self._current_response_result: PostgresWriteSideResult | None = None
        self._current_response_outcome_id: UUID | None = None
        self._cached_current_response_delivery: (
            PostgresWriteSideCurrentResponseDelivery | None
        ) = None
        self._lifecycle_lock = Lock()

    def invoke_initial(self) -> PostgresWriteSideResult:
        """Invoke A1 once and publish its exact normal result under the lock.

        Returns:
            The exact ``PostgresWriteSideResult`` returned by the retained
            public writer.

        Raises:
            PostgresWriteSideInvocationLifecycleError: If A1 was already
                started by any caller.
            TypeError: If the retained writer returns the wrong result type.
            Exception: The identical exception raised by the retained writer.

        Admission is marked before writer entry. The lifecycle lock is released
        during writer execution and reacquired to publish normal completion.
        Failure never restores initial-invocation availability.
        """

        with self._lifecycle_lock:
            if self._initial_invocation_started:
                raise PostgresWriteSideInvocationLifecycleError(
                    "initial invocation has already started"
                )
            self._initial_invocation_started = True

        result = self._dispatch_retained_request()

        with self._lifecycle_lock:
            self._initial_result = result
            self._publish_current_response_result(result)

        return result

    def evaluate_current_response(
        self,
    ) -> PostgresWriteSideCurrentResponseDelivery:
        """Explicitly evaluate Stage 4C for the current normal result.

        Returns:
            The identical cached decided or refused delivery for the currently
            published normal producer result.

        Raises:
            PostgresWriteSideInvocationLifecycleError: If no normal invocation
                result is currently published.
            Exception: Structural mapping or evaluation failures propagate and
                are not cached.

        The first call for one current result mints and retains its stable
        ``outcome_id`` before mapping. A structural failure leaves that identity
        available for a later evaluation of the same result. Typed Stage 4C
        refusal is a completed cached delivery, not a block decision. This
        method performs no writer I/O, Stage 4E evaluation, or application
        response execution.
        """

        with self._lifecycle_lock:
            current_result = self._require_current_response_result()
            cached_delivery = self._cached_current_response_delivery
            if cached_delivery is not None:
                return cached_delivery

            outcome_id = self._current_response_outcome_id
            if outcome_id is None:
                outcome_id = uuid4()
                # Identity belongs to the current producer-result lifecycle,
                # not to a successful delivery. Retain it before mapping so a
                # later call cannot mint a second identity after failure.
                self._current_response_outcome_id = outcome_id

            feedback = map_postgres_write_side_result_to_semantic_rule_feedback(
                outcome_id=outcome_id,
                result=current_result,
            )
            try:
                evaluation = evaluate_postgres_write_side_runtime_decision(
                    feedback
                )
            except PostgresWriteSideRuntimeDecisionRefused as refusal:
                delivery: PostgresWriteSideCurrentResponseDelivery = (
                    PostgresWriteSideCurrentResponseRefusal._from_owner(
                        producer_result=current_result,
                        source_feedback=feedback,
                        refusal=refusal,
                    )
                )
            else:
                delivery = PostgresWriteSideCurrentResponseEvaluation._from_owner(
                    request_signature=self._request_signature,
                    producer_result=current_result,
                    evaluation=evaluation,
                )

            self._cached_current_response_delivery = delivery
            return delivery

    def evaluate_reinvocation_authority(
        self,
    ) -> PostgresWriteSideReinvocationAuthorityEvaluation:
        """Explicitly evaluate Stage 4E once and return the cached object.

        Returns:
            The identical cached ``ReinvocationAuthorization`` or
            ``NoReinvocationAuthority`` for this owner-held A1 context.

        Raises:
            PostgresWriteSideInvocationLifecycleError: If A1 has not completed
                normally.
            TypeError: If the retained result is structurally invalid for the
                existing evaluator. Such failure is not cached.

        Evaluation is a bounded in-memory operation performed while holding the
        single lifecycle lock. It neither invokes A1 nor enters A2. A cached
        authorization remains the immutable record of issuance after its
        separate owner-local spendability has become terminally spent.
        """

        with self._lifecycle_lock:
            initial_result = self._require_completed_initial_result()
            cached_evaluation = self._cached_reinvocation_evaluation
            if cached_evaluation is not None:
                return cached_evaluation

            evaluation = evaluate_postgres_write_side_reinvocation_authority(
                request_signature=self._request_signature,
                result=initial_result,
            )
            self._cached_reinvocation_evaluation = evaluation
            return evaluation

    def invoke_authorized_reinvocation(self) -> PostgresWriteSideResult:
        """Atomically spend cached positive authority and invoke A2 once.

        Returns:
            The exact ``PostgresWriteSideResult`` returned by the retained
            public writer for A2.

        Raises:
            PostgresWriteSideInvocationLifecycleError: If A1 did not complete,
                evaluation was not explicitly requested, no authority was
                issued, or the authority was already spent.
            TypeError: If the retained writer returns the wrong result type.
            Exception: The identical exception raised by the retained writer.

        Setting ``_authority_spent`` under the lifecycle lock is the
        AVAILABLE-to-SPENT linearization point. The lock is then released
        before public-writer entry. No return value or exception restores
        availability, and this method never evaluates implicitly or creates an
        A3 lifecycle.
        """

        with self._lifecycle_lock:
            self._require_completed_initial_result()
            evaluation = self._cached_reinvocation_evaluation
            if evaluation is None:
                raise PostgresWriteSideInvocationLifecycleError(
                    "re-invocation authority has not been explicitly evaluated"
                )
            if not isinstance(evaluation, ReinvocationAuthorization):
                raise PostgresWriteSideInvocationLifecycleError(
                    "the cached Stage 4E evaluation issued no re-invocation "
                    "authority"
                )
            if self._authority_spent:
                raise PostgresWriteSideInvocationLifecycleError(
                    "re-invocation authority has already been spent"
                )

            # This owner-local write is the one-shot consumption linearization
            # point. The same critical section invalidates A1 as the current
            # response source before A2 entry. Neither transition is reversed.
            self._authority_spent = True
            self._clear_current_response_state()

        result = self._dispatch_retained_request()

        with self._lifecycle_lock:
            self._publish_current_response_result(result)

        return result

    def _require_completed_initial_result(self) -> PostgresWriteSideResult:
        """Return the published A1 result or refuse invalid lifecycle use."""

        if self._initial_result is None:
            raise PostgresWriteSideInvocationLifecycleError(
                "initial invocation has not completed normally"
            )
        return self._initial_result

    def _require_current_response_result(self) -> PostgresWriteSideResult:
        """Return the current normal result or refuse unavailable lifecycle use."""

        if self._current_response_result is None:
            raise PostgresWriteSideInvocationLifecycleError(
                "no normally completed current-response result is available"
            )
        return self._current_response_result

    def _clear_current_response_state(self) -> None:
        """Invalidate the complete current-result identity/cache lifecycle."""

        self._current_response_result = None
        self._current_response_outcome_id = None
        self._cached_current_response_delivery = None

    def _publish_current_response_result(
        self,
        result: PostgresWriteSideResult,
    ) -> None:
        """Publish one exact normal result with a fresh empty Stage 4C state."""

        self._current_response_result = result
        self._current_response_outcome_id = None
        self._cached_current_response_delivery = None

    def _dispatch_retained_request(self) -> PostgresWriteSideResult:
        """Dispatch only the privately retained signature and writer."""

        signature = self._request_signature
        if signature.command_type is CommandType.CREATE:
            result = self._writer.create_order(
                request_id=signature.request_id,
                order_id=signature.order_id,
                amount=signature.amount,
            )
        elif signature.command_type is CommandType.PAY:
            result = self._writer.pay_order(
                request_id=signature.request_id,
                order_id=signature.order_id,
                amount=signature.amount,
            )
        else:
            raise PostgresWriteSideInvocationLifecycleError(
                "retained command type is unsupported by the PostgreSQL "
                f"invocation owner: {signature.command_type!r}"
            )

        if not isinstance(result, PostgresWriteSideResult):
            raise TypeError(
                "retained writer must return PostgresWriteSideResult"
            )
        return result


def _exact_prior_accepted_event(
    *,
    request_signature: RequestSignature,
    producer_result: PostgresWriteSideResult,
) -> OrderEvent:
    """Return the exact replay event after validating owner-held relationships."""

    if producer_result.outcome is not PostgresWriteSideOutcome.REPLAY:
        raise ValueError(
            "RETURN_PRIOR_ACCEPTED_RESULT requires a REPLAY producer result"
        )

    idempotency_decision = producer_result.idempotency_decision
    if idempotency_decision.verdict is not IdempotencyVerdict.REPLAY:
        raise ValueError(
            "REPLAY producer result requires a REPLAY idempotency decision"
        )
    record = idempotency_decision.record
    if not isinstance(record, IdempotencyRecord):
        raise ValueError("REPLAY producer result requires an idempotency record")
    if record.signature != request_signature:
        raise ValueError(
            "REPLAY idempotency record signature must equal the retained "
            "RequestSignature"
        )

    prior_accepted_event = producer_result.accepted_event
    if not isinstance(prior_accepted_event, OrderEvent):
        raise ValueError(
            "REPLAY producer result requires a producer-carried accepted event"
        )
    if prior_accepted_event is not record.accepted_event:
        raise ValueError(
            "REPLAY producer result and idempotency record must carry the exact "
            "same accepted event"
        )
    return prior_accepted_event


def _validate_request_signature(request_signature: RequestSignature) -> None:
    """Validate only structural owner inputs, without new domain policy."""

    if not isinstance(request_signature, RequestSignature):
        raise TypeError("request_signature must be RequestSignature")
    if not isinstance(request_signature.request_id, str):
        raise TypeError("request_signature.request_id must be str")
    if not isinstance(request_signature.command_type, CommandType):
        raise TypeError("request_signature.command_type must be CommandType")
    if not isinstance(request_signature.order_id, str):
        raise TypeError("request_signature.order_id must be str")
    if not isinstance(request_signature.amount, Decimal):
        raise TypeError("request_signature.amount must be Decimal")


__all__ = (
    "PostgresWriteSideCurrentResponseDelivery",
    "PostgresWriteSideCurrentResponseEvaluation",
    "PostgresWriteSideCurrentResponseRefusal",
    "PostgresWriteSideInvocationLifecycleError",
    "PostgresWriteSideInvocationOwner",
)
