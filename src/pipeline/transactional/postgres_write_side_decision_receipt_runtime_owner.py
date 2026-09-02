"""Compose PostgreSQL write invocation with live DecisionReceipt custody."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import TypeAlias
from uuid import UUID, uuid4

from src.compass.runtime.postgres_write_side_reinvocation_authority import (
    PostgresWriteSideReinvocationAuthorityEvaluation,
)
from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_materialization_owner,
    postgres_write_side_decision_receipt_persistence_composition_owner,
)
from src.pipeline.transactional.admission import (
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideCurrentResponseDelivery,
    PostgresWriteSideInvocationOwner,
)
from src.storage.idempotency_store import RequestSignature
from src.storage.postgres_decision_receipt_transaction_owner import (
    PostgresDecisionReceiptTransactionOwner,
)


__all__ = (
    "PostgresWriteSideDecisionReceiptCompletedInvocation",
    "PostgresWriteSideDecisionReceiptPersistenceEligibility",
    "PostgresWriteSideDecisionReceiptRuntimeDelivery",
    "PostgresWriteSideDecisionReceiptRuntimeLifecycleError",
    "PostgresWriteSideDecisionReceiptRuntimeOwner",
    "PostgresWriteSideDecisionReceiptRuntimeStatus",
    "evaluate_postgres_write_side_decision_receipt_persistence_eligibility",
)


_IdentityFactory: TypeAlias = Callable[[], UUID]
materialization = (
    postgres_write_side_decision_receipt_materialization_owner
)
persistence = (
    postgres_write_side_decision_receipt_persistence_composition_owner
)
_MaterializationOwner = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationOwner
)
_MaterializationStatus = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationStatus
)
_PersistenceCompositionDelivery = (
    persistence.PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery
)
_PersistenceCompositionOwner = (
    persistence.PostgresWriteSideDecisionReceiptPersistenceCompositionOwner
)


class PostgresWriteSideDecisionReceiptRuntimeLifecycleError(RuntimeError):
    """Report unavailable completed-invocation custody in one runtime owner."""


class PostgresWriteSideDecisionReceiptPersistenceEligibility(str, Enum):
    """Classify reviewed positive profiles and fail closed otherwise.

    Each eligible value identifies one source-reviewed producer profile. The
    single ineligible value deliberately covers both known unsafe technical
    profiles and future or structurally unreviewed profiles. It does not claim
    that the business result failed or that receipt persistence was attempted.
    """

    ELIGIBLE_ACCEPTED = "ELIGIBLE_ACCEPTED"
    ELIGIBLE_IDEMPOTENT_REPLAY = "ELIGIBLE_IDEMPOTENT_REPLAY"
    ELIGIBLE_IDEMPOTENCY_CONFLICT = "ELIGIBLE_IDEMPOTENCY_CONFLICT"
    ELIGIBLE_VALIDATION_BLOCKED = "ELIGIBLE_VALIDATION_BLOCKED"
    ELIGIBLE_PREPARATION_LOCK_TIMEOUT = (
        "ELIGIBLE_PREPARATION_LOCK_TIMEOUT"
    )
    INELIGIBLE = "INELIGIBLE"

    @property
    def is_eligible(self) -> bool:
        """Return whether this exact reviewed profile may reach persistence."""

        return self is not type(self).INELIGIBLE


def evaluate_postgres_write_side_decision_receipt_persistence_eligibility(
    result: PostgresWriteSideResult,
) -> PostgresWriteSideDecisionReceiptPersistenceEligibility:
    """Evaluate one live result against the closed receipt-safe allowlist.

    Args:
        result: Exact normal result returned through the retained PostgreSQL
            invocation owner.

    Returns:
        One reviewed positive profile or ``INELIGIBLE``. Unknown outcomes,
        append-time rejections, infrastructure failures, and other unmatched
        structures fail closed.

    The reviewed ordinary profiles use fixed or semantic producer reasons in
    the current source. Preparation ``LOCK_TIMEOUT`` is distinguished by typed
    lifecycle position: it has a ``StreamAdmissionResult`` and no append
    result.
    Current append rejection translations can retain exception-derived reason
    text, so none is positively eligible. This evaluator never parses reason
    strings and does not reinterpret business, durability, Stage 4C, or Stage
    4E evidence.

    Raises:
        TypeError: If ``result`` is not a ``PostgresWriteSideResult``.
    """

    if not isinstance(result, PostgresWriteSideResult):
        raise TypeError("result must be PostgresWriteSideResult")

    if result.outcome is PostgresWriteSideOutcome.ACCEPTED:
        return (
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_ACCEPTED
        )
    if result.outcome is PostgresWriteSideOutcome.REPLAY:
        return (
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_IDEMPOTENT_REPLAY
        )
    if result.outcome is PostgresWriteSideOutcome.CONFLICT:
        return (
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_IDEMPOTENCY_CONFLICT
        )
    if result.outcome is PostgresWriteSideOutcome.VALIDATION_BLOCKED:
        return (
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_VALIDATION_BLOCKED
        )

    stream_result = result.stream_admission_result
    if (
        result.outcome is PostgresWriteSideOutcome.ADMISSION_REJECTED
        and result.admission_result is None
        and isinstance(stream_result, StreamAdmissionResult)
        and stream_result.verdict is AdmissionVerdict.LOCK_TIMEOUT
    ):
        return (
            PostgresWriteSideDecisionReceiptPersistenceEligibility
            .ELIGIBLE_PREPARATION_LOCK_TIMEOUT
        )

    return PostgresWriteSideDecisionReceiptPersistenceEligibility.INELIGIBLE


_evaluate_persistence_eligibility = (
    evaluate_postgres_write_side_decision_receipt_persistence_eligibility
)


class PostgresWriteSideDecisionReceiptRuntimeStatus(str, Enum):
    """Classify terminal receipt composition independent of business truth."""

    PERSISTENCE_INELIGIBLE = "PERSISTENCE_INELIGIBLE"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"
    PERSISTENCE_COMPLETED = "PERSISTENCE_COMPLETED"
    UNEXPECTED_COMPOSITION_EXCEPTION = "UNEXPECTED_COMPOSITION_EXCEPTION"


@dataclass(frozen=True)
class PostgresWriteSideDecisionReceiptRuntimeDelivery:
    """Deliver exact business truth with terminal application receipt evidence.

    Args:
        business_result: Exact normal producer result retained by the completed
            invocation handle.
        persistence_eligibility: Exact fail-closed eligibility evaluation for
            that result.
        status: Terminal application receipt-composition classification.
        persistence_delivery: Exact PR2 delivery for recognized materialization
            failure or normally returned persistence evidence; otherwise
            ``None``.

    ``PERSISTENCE_INELIGIBLE`` means persistence was not reached and is
    distinct from PR2 ``NOT_COMMITTED`` or ``UNKNOWN``.
    ``MATERIALIZATION_FAILED`` carries the existing bounded PR1 failure through
    the exact PR2 delivery.
    ``PERSISTENCE_COMPLETED`` carries the exact existing transaction result
    without reinterpretation. ``UNEXPECTED_COMPOSITION_EXCEPTION`` is bounded
    live evidence only: no exception object or raw text is retained, and the
    completed handle will not re-enter PR2.

    This delivery does not persist diagnostics, authorize retry, change the
    business result, resolve durability, or create Stage 4C / Stage 4E policy.
    """

    business_result: PostgresWriteSideResult
    persistence_eligibility: (
        PostgresWriteSideDecisionReceiptPersistenceEligibility
    )
    status: PostgresWriteSideDecisionReceiptRuntimeStatus
    persistence_delivery: _PersistenceCompositionDelivery | None

    def __post_init__(self) -> None:
        """Reject application evidence that contradicts the retained result."""

        if not isinstance(self.business_result, PostgresWriteSideResult):
            raise TypeError("business_result must be PostgresWriteSideResult")
        if not isinstance(
            self.persistence_eligibility,
            PostgresWriteSideDecisionReceiptPersistenceEligibility,
        ):
            raise TypeError(
                "persistence_eligibility must be "
                "PostgresWriteSideDecisionReceiptPersistenceEligibility"
            )
        if not isinstance(
            self.status,
            PostgresWriteSideDecisionReceiptRuntimeStatus,
        ):
            raise TypeError(
                "status must be PostgresWriteSideDecisionReceiptRuntimeStatus"
            )

        if self.status is (
            PostgresWriteSideDecisionReceiptRuntimeStatus
            .PERSISTENCE_INELIGIBLE
        ):
            if self.persistence_eligibility.is_eligible:
                raise ValueError(
                    "PERSISTENCE_INELIGIBLE requires ineligible evidence"
                )
            if self.persistence_delivery is not None:
                raise ValueError(
                    "PERSISTENCE_INELIGIBLE cannot carry persistence delivery"
                )
            return

        if not self.persistence_eligibility.is_eligible:
            raise ValueError(
                "eligible receipt-composition status requires eligible "
                "evidence"
            )

        if self.status is (
            PostgresWriteSideDecisionReceiptRuntimeStatus
            .UNEXPECTED_COMPOSITION_EXCEPTION
        ):
            if self.persistence_delivery is not None:
                raise ValueError(
                    "unexpected composition cannot carry persistence delivery"
                )
            return

        delivery = self.persistence_delivery
        if not isinstance(delivery, _PersistenceCompositionDelivery):
            raise TypeError(
                "recognized composition status requires exact PR2 delivery"
            )
        if delivery.business_result is not self.business_result:
            raise ValueError(
                "business_result must be the exact PR2 business result"
            )

        materialization_failed = delivery.materialization_delivery.status is (
            _MaterializationStatus.MATERIALIZATION_FAILED
        )
        if self.status is (
            PostgresWriteSideDecisionReceiptRuntimeStatus
            .MATERIALIZATION_FAILED
        ):
            if not materialization_failed or delivery.persistence_reached:
                raise ValueError(
                    "MATERIALIZATION_FAILED requires PR2 materialization "
                    "failure"
                )
            return

        if materialization_failed or not delivery.persistence_reached:
            raise ValueError(
                "PERSISTENCE_COMPLETED requires reached PR2 persistence"
            )


@dataclass(frozen=True, init=False, eq=False)
class PostgresWriteSideDecisionReceiptCompletedInvocation:
    """Own the canonical live receipt graph for one normal invocation result.

    The runtime owner is the only construction boundary. The handle retains the
    exact business result and one exact PR1 materialization owner. Only a
    positively eligible profile retains one exact PR2 persistence-composition
    owner.
    Its first ``compose_receipt`` call publishes one terminal application
    delivery under an owner-local lock. Every later call returns that identical
    object, including after ``UNKNOWN`` or an unexpected exception.

    Unexpected receipt exceptions are reduced to a bounded live status without
    retaining raw text or the exception object. They never remove access to the
    business result and never create automatic receipt retry authority.

    This bounded handle has no attempt identity, durable lifecycle, collection,
    reconstruction API, Stage 4C identity, Stage 4E authority, or process-crash
    recovery responsibility.
    """

    business_result: PostgresWriteSideResult
    persistence_eligibility: (
        PostgresWriteSideDecisionReceiptPersistenceEligibility
    )
    _materialization_owner: _MaterializationOwner = field(
        repr=False,
        compare=False,
    )
    _persistence_owner: _PersistenceCompositionOwner | None = field(
        repr=False,
        compare=False,
    )
    _cached_receipt_delivery: (
        PostgresWriteSideDecisionReceiptRuntimeDelivery | None
    ) = field(repr=False, compare=False)
    _receipt_lock: Lock = field(repr=False, compare=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Reject construction outside the runtime-owner completion flow."""

        raise TypeError(
            "PostgresWriteSideDecisionReceiptCompletedInvocation must be "
            "produced by PostgresWriteSideDecisionReceiptRuntimeOwner"
        )

    @classmethod
    def _from_runtime_owner(
        cls,
        *,
        business_result: PostgresWriteSideResult,
        receipt_transaction_owner: PostgresDecisionReceiptTransactionOwner,
        receipt_id_factory: _IdentityFactory,
        outcome_id_factory: _IdentityFactory,
    ) -> "PostgresWriteSideDecisionReceiptCompletedInvocation":
        """Build one privately retained PR1/PR2 graph for a normal result."""

        eligibility = _evaluate_persistence_eligibility(business_result)
        materialization_owner = _MaterializationOwner(
            completed_result=business_result,
            receipt_id_factory=receipt_id_factory,
            outcome_id_factory=outcome_id_factory,
        )
        persistence_owner = (
            _PersistenceCompositionOwner(
                materialization_owner=materialization_owner,
                receipt_transaction_owner=receipt_transaction_owner,
            )
            if eligibility.is_eligible
            else None
        )

        instance = object.__new__(cls)
        object.__setattr__(instance, "business_result", business_result)
        object.__setattr__(instance, "persistence_eligibility", eligibility)
        object.__setattr__(
            instance,
            "_materialization_owner",
            materialization_owner,
        )
        object.__setattr__(instance, "_persistence_owner", persistence_owner)
        object.__setattr__(instance, "_cached_receipt_delivery", None)
        object.__setattr__(instance, "_receipt_lock", Lock())
        return instance

    def compose_receipt(
        self,
    ) -> PostgresWriteSideDecisionReceiptRuntimeDelivery:
        """Compose receipt evidence once and return one terminal live delivery.

        Returns:
            Exact business truth paired with ineligibility, bounded
            materialization failure, exact normally returned PR2 evidence, or a
            bounded unexpected-composition category.

        Eligible receipt work occurs only after the business result already
        exists. Receipt persistence remains a separate transaction. The method
        neither calls Stage 4C nor Stage 4E nor retries any terminal result.
        """

        with self._receipt_lock:
            cached_delivery = self._cached_receipt_delivery
            if cached_delivery is not None:
                return cached_delivery

            persistence_owner = self._persistence_owner
            if persistence_owner is None:
                delivery = PostgresWriteSideDecisionReceiptRuntimeDelivery(
                    business_result=self.business_result,
                    persistence_eligibility=self.persistence_eligibility,
                    status=(
                        PostgresWriteSideDecisionReceiptRuntimeStatus
                        .PERSISTENCE_INELIGIBLE
                    ),
                    persistence_delivery=None,
                )
            else:
                try:
                    persistence_delivery = persistence_owner.compose()
                    delivery = self._delivery_from_persistence(
                        persistence_delivery
                    )
                except Exception:
                    # The application boundary intentionally retains neither
                    # raw exception text nor automatic PR2 re-entry authority.
                    delivery = PostgresWriteSideDecisionReceiptRuntimeDelivery(
                        business_result=self.business_result,
                        persistence_eligibility=self.persistence_eligibility,
                        status=(
                            PostgresWriteSideDecisionReceiptRuntimeStatus
                            .UNEXPECTED_COMPOSITION_EXCEPTION
                        ),
                        persistence_delivery=None,
                    )

            object.__setattr__(self, "_cached_receipt_delivery", delivery)
            return delivery

    def _delivery_from_persistence(
        self,
        persistence_delivery: _PersistenceCompositionDelivery,
    ) -> PostgresWriteSideDecisionReceiptRuntimeDelivery:
        """Preserve one exact normal PR2 delivery under application status."""

        materialization_status = (
            persistence_delivery.materialization_delivery.status
        )
        status = (
            PostgresWriteSideDecisionReceiptRuntimeStatus
            .MATERIALIZATION_FAILED
            if materialization_status
            is _MaterializationStatus.MATERIALIZATION_FAILED
            else PostgresWriteSideDecisionReceiptRuntimeStatus
            .PERSISTENCE_COMPLETED
        )
        return PostgresWriteSideDecisionReceiptRuntimeDelivery(
            business_result=self.business_result,
            persistence_eligibility=self.persistence_eligibility,
            status=status,
            persistence_delivery=persistence_delivery,
        )


class PostgresWriteSideDecisionReceiptRuntimeOwner:
    """Own PostgreSQL invocation plus bounded live DecisionReceipt custody.

    Args:
        request_signature: Complete immutable identity retained for A1 and any
            Stage 4E-authorized A2.
        writer: Configured public PostgreSQL writer retained inside one exact
            ``PostgresWriteSideInvocationOwner``.
        receipt_transaction_owner: Existing owner of separate receipt
            transactions, retained as the dependency for eligible completion
            graphs.
        receipt_id_factory: Lazy receipt identity source passed to each exact
            PR1 owner. The default is ``uuid4``.
        receipt_outcome_id_factory: Lazy receipt-path semantic identity source
            passed to each PR1 owner. It remains independent of Stage 4C. The
            default is ``uuid4``.

    Lifecycle:
        ``invoke_initial`` delegates A1 and binds its exact normal result to
        one canonical completed-invocation handle before returning. Explicit
        Stage 4E evaluation remains delegated unchanged. A normally returned
        authorized A2 binds one distinct second handle while A1 custody remains
        retained. Read-only accessors return the identical bounded handles.

    One runtime-owner lock serializes application entry, delegation, and handle
    publication. Receipt composition is separately synchronized per completed
    handle, so A1 evidence remains usable after the invocation owner's current
    response moves to A2.

    This owner does not expose an API that accepts raw completed results, enter
    receipt work before business completion, invoke Stage 4C implicitly, mint
    or bypass Stage 4E authority, create A3, retain an attempt list, establish
    global uniqueness, or recover live state after process failure.
    """

    def __init__(
        self,
        *,
        request_signature: RequestSignature,
        writer: PostgresTransactionalWriteSide,
        receipt_transaction_owner: PostgresDecisionReceiptTransactionOwner,
        receipt_id_factory: _IdentityFactory = uuid4,
        receipt_outcome_id_factory: _IdentityFactory = uuid4,
    ) -> None:
        """Validate dependencies and create the private invocation owner."""

        if not isinstance(
            receipt_transaction_owner,
            PostgresDecisionReceiptTransactionOwner,
        ):
            raise TypeError(
                "receipt_transaction_owner must be "
                "PostgresDecisionReceiptTransactionOwner"
            )
        if not callable(receipt_id_factory):
            raise TypeError("receipt_id_factory must be callable")
        if not callable(receipt_outcome_id_factory):
            raise TypeError("receipt_outcome_id_factory must be callable")

        self._invocation_owner = PostgresWriteSideInvocationOwner(
            request_signature=request_signature,
            writer=writer,
        )
        self._receipt_transaction_owner = receipt_transaction_owner
        self._receipt_id_factory = receipt_id_factory
        self._receipt_outcome_id_factory = receipt_outcome_id_factory
        self._initial_completion: (
            PostgresWriteSideDecisionReceiptCompletedInvocation | None
        ) = None
        self._authorized_reinvocation_completion: (
            PostgresWriteSideDecisionReceiptCompletedInvocation | None
        ) = None
        self._lifecycle_lock = Lock()

    @property
    def initial_completion(
        self,
    ) -> PostgresWriteSideDecisionReceiptCompletedInvocation:
        """Return the identical retained A1 handle after normal completion."""

        with self._lifecycle_lock:
            completion = self._initial_completion
            if completion is None:
                raise PostgresWriteSideDecisionReceiptRuntimeLifecycleError(
                    "initial invocation has not completed normally"
                )
            return completion

    @property
    def authorized_reinvocation_completion(
        self,
    ) -> PostgresWriteSideDecisionReceiptCompletedInvocation:
        """Return the identical retained A2 handle after normal completion."""

        with self._lifecycle_lock:
            completion = self._authorized_reinvocation_completion
            if completion is None:
                raise PostgresWriteSideDecisionReceiptRuntimeLifecycleError(
                    "authorized re-invocation has not completed normally"
                )
            return completion

    def invoke_initial(
        self,
    ) -> PostgresWriteSideDecisionReceiptCompletedInvocation:
        """Invoke A1, then bind its exact normal result to one retained graph.

        Writer exceptions propagate unchanged and publish no completion handle.
        The business writer has fully returned before any receipt owner is
        constructed, and no receipt materialization or persistence is attempted
        by this method.
        """

        with self._lifecycle_lock:
            result = self._invocation_owner.invoke_initial()
            completion = self._new_completed_invocation(result)
            if self._initial_completion is not None:
                raise AssertionError("initial completion must publish once")
            self._initial_completion = completion
            return completion

    def evaluate_current_response(
        self,
    ) -> PostgresWriteSideCurrentResponseDelivery:
        """Delegate explicit Stage 4C evaluation for the current result."""

        with self._lifecycle_lock:
            return self._invocation_owner.evaluate_current_response()

    def evaluate_reinvocation_authority(
        self,
    ) -> PostgresWriteSideReinvocationAuthorityEvaluation:
        """Delegate explicit Stage 4E evaluation without changing authority."""

        with self._lifecycle_lock:
            return self._invocation_owner.evaluate_reinvocation_authority()

    def invoke_authorized_reinvocation(
        self,
    ) -> PostgresWriteSideDecisionReceiptCompletedInvocation:
        """Delegate one authorized A2 and retain its distinct normal handle.

        Stage 4E remains the only authority issuer and spend owner. An A2
        exception propagates after authority is spent and publishes no A2
        completion. Normal A2 completion starts its receipt lifecycle only
        after the writer returns.
        """

        with self._lifecycle_lock:
            result = self._invocation_owner.invoke_authorized_reinvocation()
            completion = self._new_completed_invocation(result)
            if self._authorized_reinvocation_completion is not None:
                raise AssertionError(
                    "authorized re-invocation completion must publish once"
                )
            self._authorized_reinvocation_completion = completion
            return completion

    def _new_completed_invocation(
        self,
        result: PostgresWriteSideResult,
    ) -> PostgresWriteSideDecisionReceiptCompletedInvocation:
        """Create the sole canonical owner graph for one normal completion."""

        completion_type = PostgresWriteSideDecisionReceiptCompletedInvocation
        return completion_type._from_runtime_owner(
            business_result=result,
            receipt_transaction_owner=self._receipt_transaction_owner,
            receipt_id_factory=self._receipt_id_factory,
            outcome_id_factory=self._receipt_outcome_id_factory,
        )
