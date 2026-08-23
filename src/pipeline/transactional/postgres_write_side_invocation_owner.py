"""Live one-shot owner for one PostgreSQL write-side request lifecycle."""

from __future__ import annotations

from decimal import Decimal
from threading import Lock

from src.compass.runtime.postgres_write_side_reinvocation_authority import (
    PostgresWriteSideReinvocationAuthorityEvaluation,
    evaluate_postgres_write_side_reinvocation_authority,
)
from src.compass.runtime.reinvocation_authority import (
    ReinvocationAuthorization,
)
from src.core.order.enums import CommandType
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideResult,
)
from src.storage.idempotency_store import RequestSignature


class PostgresWriteSideInvocationLifecycleError(RuntimeError):
    """Report invalid use of one PostgreSQL invocation-owner lifecycle.

    This exception represents owner-local execution-state misuse, such as
    duplicate A1 entry, evaluation before normal A1 completion, or unavailable
    one-shot authority. It is not Stage 4E semantic no-authority, retry policy,
    or a durable lifecycle status.
    """


class PostgresWriteSideInvocationOwner:
    """Own one live PostgreSQL A1 and at most one authorized A2 invocation.

    Args:
        request_signature: Complete immutable identity dispatched for both A1
            and any authorized A2.
        writer: Already-configured PostgreSQL public writer whose connection,
            validation runtime, configuration, and admission-gate factory are
            retained as the execution composition.

    The owner invokes A1 itself, retains the exact normally returned result,
    lazily evaluates and caches the existing Stage 4E PostgreSQL authority
    result, and atomically spends positive authority before A2 writer entry.
    One owner-scoped non-reentrant lock protects all mutable lifecycle
    publication, but is never held while the writer performs database work.

    Writer exceptions propagate unchanged. An A1 exception permanently uses
    the initial invocation without publishing a completed result. Every A2
    result or exception leaves authority spent. This in-process owner provides
    neither durable provenance nor retry scheduling, strategy selection,
    Stage 4C policy, restart recovery, distributed consumption, or A3.
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

        return result

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
            # point. It precedes A2 entry and is deliberately never reversed.
            self._authority_spent = True

        return self._dispatch_retained_request()

    def _require_completed_initial_result(self) -> PostgresWriteSideResult:
        """Return the published A1 result or refuse invalid lifecycle use."""

        if self._initial_result is None:
            raise PostgresWriteSideInvocationLifecycleError(
                "initial invocation has not completed normally"
            )
        return self._initial_result

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
    "PostgresWriteSideInvocationLifecycleError",
    "PostgresWriteSideInvocationOwner",
)
