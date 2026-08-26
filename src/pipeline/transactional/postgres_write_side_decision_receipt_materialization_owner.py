"""Own one live DecisionReceipt materialization for one completed write result."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import TypeAlias
from uuid import UUID, uuid4

from src.compass.runtime.decision_receipt import DecisionReceipt
from src.compass.runtime.write_side_decision_receipt_mapping import (
    map_postgres_write_side_result_to_decision_receipt,
)
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideResult


__all__ = (
    "PostgresWriteSideDecisionReceiptMaterializationDelivery",
    "PostgresWriteSideDecisionReceiptMaterializationFailureCategory",
    "PostgresWriteSideDecisionReceiptMaterializationOwner",
    "PostgresWriteSideDecisionReceiptMaterializationStatus",
)


_IdentityFactory: TypeAlias = Callable[[], UUID]


class PostgresWriteSideDecisionReceiptMaterializationStatus(str, Enum):
    """Classify the live materialization result without changing business truth."""

    MATERIALIZED = "MATERIALIZED"
    MATERIALIZATION_FAILED = "MATERIALIZATION_FAILED"


class PostgresWriteSideDecisionReceiptMaterializationFailureCategory(str, Enum):
    """Bound expected mapper contract failures without retaining raw error text."""

    TYPE_ERROR = "TYPE_ERROR"
    VALUE_ERROR = "VALUE_ERROR"


@dataclass(frozen=True)
class PostgresWriteSideDecisionReceiptMaterializationDelivery:
    """Deliver one exact business result with its live receipt materialization.

    Args:
        business_result: Exact normally completed producer result retained by the
            owner. Receipt materialization never reconstructs or reclassifies it.
        status: Whether the existing receipt mapper produced a receipt or raised
            a recognized contract failure.
        receipt: Exact materialized receipt when ``status`` is ``MATERIALIZED``;
            otherwise ``None``.
        failure_category: Bounded live mapper-failure evidence when ``status`` is
            ``MATERIALIZATION_FAILED``; otherwise ``None``.

    Invariants:
        A materialized delivery carries exactly one ``DecisionReceipt`` and no
        failure category. A failed delivery carries no receipt and exactly one
        recognized failure category. The business result remains independent of
        either materialization state.

    Non-goals:
        This delivery does not persist a receipt, report transaction durability,
        authorize retry, retain raw exception text, or represent business
        acceptance, Stage 4C current-response identity, or Stage 4E authority.
    """

    business_result: PostgresWriteSideResult
    status: PostgresWriteSideDecisionReceiptMaterializationStatus
    receipt: DecisionReceipt | None
    failure_category: (
        PostgresWriteSideDecisionReceiptMaterializationFailureCategory | None
    )

    def __post_init__(self) -> None:
        """Validate exact materialized-versus-failed delivery coherence."""

        if not isinstance(self.business_result, PostgresWriteSideResult):
            raise TypeError("business_result must be PostgresWriteSideResult")
        if not isinstance(
            self.status,
            PostgresWriteSideDecisionReceiptMaterializationStatus,
        ):
            raise TypeError(
                "status must be "
                "PostgresWriteSideDecisionReceiptMaterializationStatus"
            )

        if (
            self.status
            is PostgresWriteSideDecisionReceiptMaterializationStatus.MATERIALIZED
        ):
            if not isinstance(self.receipt, DecisionReceipt):
                raise TypeError(
                    "receipt must be DecisionReceipt when status is MATERIALIZED"
                )
            if self.failure_category is not None:
                raise ValueError(
                    "failure_category must be None when status is MATERIALIZED"
                )
            return

        if self.receipt is not None:
            raise ValueError(
                "receipt must be None when status is MATERIALIZATION_FAILED"
            )
        if not isinstance(
            self.failure_category,
            PostgresWriteSideDecisionReceiptMaterializationFailureCategory,
        ):
            raise TypeError(
                "failure_category must be "
                "PostgresWriteSideDecisionReceiptMaterializationFailureCategory "
                "when status is MATERIALIZATION_FAILED"
            )


class PostgresWriteSideDecisionReceiptMaterializationOwner:
    """Own one live receipt-materialization lifecycle for one completed result.

    Args:
        completed_result: Exact normally completed ``PostgresWriteSideResult`` to
            retain for this owner's entire lifetime.
        receipt_id_factory: Callable that lazily supplies the receipt UUID for
            this lifecycle. The default uses ``uuid4``.
        outcome_id_factory: Callable that lazily supplies the receipt-path
            ``SemanticOutcome`` UUID for this lifecycle. It is independent of
            Stage 4C current-response identity. The default uses ``uuid4``.

    The first ``materialize`` call allocates both identities and invokes the
    authoritative write-side receipt mapper. A successful mapping or bounded
    ``TypeError`` / ``ValueError`` failure is cached, and every later call
    returns that identical delivery object. One owner-scoped lock makes the
    identity allocation, mapping, and cache publication one live operation.

    Failure behavior:
        Invalid owner construction and invalid identity-factory behavior raise
        directly as programmer-contract errors. Only ``TypeError`` and
        ``ValueError`` raised by the existing receipt mapper become cached live
        materialization failures. Other exceptions propagate unchanged.

    Non-goals:
        This owner does not execute business work, change the retained result,
        persist receipts, resolve unknown durability, retry mapping, reconcile
        history, record attempts, or participate in Stage 4C or Stage 4E.
    """

    def __init__(
        self,
        *,
        completed_result: PostgresWriteSideResult,
        receipt_id_factory: _IdentityFactory = uuid4,
        outcome_id_factory: _IdentityFactory = uuid4,
    ) -> None:
        """Validate and retain one exact result and two lazy identity factories."""

        if not isinstance(completed_result, PostgresWriteSideResult):
            raise TypeError("completed_result must be PostgresWriteSideResult")
        if not callable(receipt_id_factory):
            raise TypeError("receipt_id_factory must be callable")
        if not callable(outcome_id_factory):
            raise TypeError("outcome_id_factory must be callable")

        self._completed_result = completed_result
        self._receipt_id_factory = receipt_id_factory
        self._outcome_id_factory = outcome_id_factory
        self._receipt_id: UUID | None = None
        self._outcome_id: UUID | None = None
        self._cached_delivery: (
            PostgresWriteSideDecisionReceiptMaterializationDelivery | None
        ) = None
        self._lifecycle_lock = Lock()

    def materialize(
        self,
    ) -> PostgresWriteSideDecisionReceiptMaterializationDelivery:
        """Materialize once and return the identical cached live delivery.

        Returns:
            A materialized delivery containing the exact receipt, or a failed
            delivery containing bounded mapper-contract failure evidence. Both
            forms retain the exact original business result.

        Raises:
            TypeError: If an identity factory returns a non-UUID value.
            Exception: Any mapper exception other than ``TypeError`` or
                ``ValueError`` propagates unchanged and is not cached.

        Identity allocation occurs once after valid identity factories return.
        Successful mapping and recognized mapping failure are terminal for this
        live owner. An unexpected mapper exception propagates and is not
        converted into a delivery or retry policy.
        """

        with self._lifecycle_lock:
            if self._cached_delivery is not None:
                return self._cached_delivery

            receipt_id, outcome_id = self._require_materialization_identities()

            try:
                receipt = map_postgres_write_side_result_to_decision_receipt(
                    receipt_id=receipt_id,
                    outcome_id=outcome_id,
                    result=self._completed_result,
                )
            except TypeError:
                delivery = self._failed_delivery(
                    PostgresWriteSideDecisionReceiptMaterializationFailureCategory
                    .TYPE_ERROR
                )
            except ValueError:
                delivery = self._failed_delivery(
                    PostgresWriteSideDecisionReceiptMaterializationFailureCategory
                    .VALUE_ERROR
                )
            else:
                delivery = (
                    PostgresWriteSideDecisionReceiptMaterializationDelivery(
                        business_result=self._completed_result,
                        status=(
                            PostgresWriteSideDecisionReceiptMaterializationStatus
                            .MATERIALIZED
                        ),
                        receipt=receipt,
                        failure_category=None,
                    )
                )

            self._cached_delivery = delivery
            return delivery

    def _require_materialization_identities(self) -> tuple[UUID, UUID]:
        """Allocate both receipt-local identities once and return them."""

        if self._receipt_id is None and self._outcome_id is None:
            receipt_id = _identity_from_factory(
                self._receipt_id_factory,
                "receipt_id_factory",
            )
            outcome_id = _identity_from_factory(
                self._outcome_id_factory,
                "outcome_id_factory",
            )
            self._receipt_id = receipt_id
            self._outcome_id = outcome_id

        if self._receipt_id is None or self._outcome_id is None:
            raise AssertionError("materialization identities must be coherent")
        return self._receipt_id, self._outcome_id

    def _failed_delivery(
        self,
        failure_category: (
            PostgresWriteSideDecisionReceiptMaterializationFailureCategory
        ),
    ) -> PostgresWriteSideDecisionReceiptMaterializationDelivery:
        """Build a failed live delivery without changing the business result."""

        return PostgresWriteSideDecisionReceiptMaterializationDelivery(
            business_result=self._completed_result,
            status=(
                PostgresWriteSideDecisionReceiptMaterializationStatus
                .MATERIALIZATION_FAILED
            ),
            receipt=None,
            failure_category=failure_category,
        )


def _identity_from_factory(
    factory: _IdentityFactory,
    factory_name: str,
) -> UUID:
    """Return one native UUID or reject an invalid identity-factory contract."""

    identity = factory()
    if not isinstance(identity, UUID):
        raise TypeError(f"{factory_name} must return UUID")
    return identity
