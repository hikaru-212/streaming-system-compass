"""Compose one live write-side receipt materialization with persistence."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from src.pipeline.transactional import (
    postgres_write_side_decision_receipt_materialization_owner as materialization,
)
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideResult,
)
from src.storage.decision_receipt_store import (
    DecisionReceiptMaterializationProvenance,
)
from src.storage.postgres_decision_receipt_transaction_owner import (
    PostgresDecisionReceiptTransactionOwner,
    PostgresDecisionReceiptTransactionResult,
)


__all__ = (
    "PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery",
    "PostgresWriteSideDecisionReceiptPersistenceCompositionOwner",
)


_MaterializationDelivery = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationDelivery
)
_MaterializationOwner = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationOwner
)
_MaterializationStatus = (
    materialization.PostgresWriteSideDecisionReceiptMaterializationStatus
)


@dataclass(frozen=True)
class PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery:
    """Deliver separate business, materialization, and persistence evidence.

    Args:
        business_result: Exact completed write-side result retained by the PR1
            materialization delivery.
        materialization_delivery: Exact cached delivery returned by the retained
            PR1 materialization owner.
        persistence_reached: Whether the separate receipt transaction owner was
            invoked after successful materialization.
        persistence_result: Exact existing commit-aware transaction result when
            persistence was reached; otherwise ``None``.

    Invariants:
        The business result is the same object retained by the materialization
        delivery. Failed materialization is explicitly persistence-not-reached
        and cannot carry a persistence result. Successful materialization is
        persistence-reached and carries one existing transaction result.

    Non-goals:
        This delivery does not merge business, materialization, or persistence
        meanings; copy transaction durability into a parallel status; authorize
        retry; resolve unknown durability; or perform reconciliation.
    """

    business_result: PostgresWriteSideResult
    materialization_delivery: _MaterializationDelivery
    persistence_reached: bool
    persistence_result: PostgresDecisionReceiptTransactionResult | None

    def __post_init__(self) -> None:
        """Reject compound states that contradict the retained PR1 delivery."""

        if not isinstance(self.business_result, PostgresWriteSideResult):
            raise TypeError("business_result must be PostgresWriteSideResult")
        if not isinstance(
            self.materialization_delivery,
            _MaterializationDelivery,
        ):
            raise TypeError(
                "materialization_delivery must be "
                "PostgresWriteSideDecisionReceiptMaterializationDelivery"
            )
        if (
            self.business_result
            is not self.materialization_delivery.business_result
        ):
            raise ValueError(
                "business_result must be the exact materialization business "
                "result"
            )
        if type(self.persistence_reached) is not bool:
            raise TypeError("persistence_reached must be bool")

        if self.materialization_delivery.status is (
            _MaterializationStatus.MATERIALIZATION_FAILED
        ):
            if self.persistence_reached:
                raise ValueError(
                    "failed materialization cannot reach persistence"
                )
            if self.persistence_result is not None:
                raise ValueError(
                    "failed materialization cannot carry persistence_result"
                )
            return

        if not self.persistence_reached:
            raise ValueError(
                "materialized delivery must reach receipt persistence"
            )
        if not isinstance(
            self.persistence_result,
            PostgresDecisionReceiptTransactionResult,
        ):
            raise TypeError(
                "persistence_result must be "
                "PostgresDecisionReceiptTransactionResult when persistence "
                "is reached"
            )


class PostgresWriteSideDecisionReceiptPersistenceCompositionOwner:
    """Own one materialize-once and persist-once live composition lifecycle.

    Args:
        materialization_owner: One exact PR1 owner whose cached materialization
            identity and payload remain in custody for this lifecycle.
        receipt_transaction_owner: Existing owner of the separate PostgreSQL
            DecisionReceipt transaction invoked at most once.

    Lifecycle:
        The first ``compose`` call asks the retained PR1 owner to materialize.
        A failed materialization produces explicit persistence-not-reached
        evidence. A successful materialization passes that exact receipt object
        to the retained transaction owner with ``LIVE_RESULT`` provenance.
        The compound delivery is cached, including ``NOT_COMMITTED`` and
        ``UNKNOWN`` evidence, and every later caller receives that same object.
        One lock owns the complete materialize, persist, and cache publication
        sequence for concurrent callers.

    Failure behavior:
        Construction rejects owners outside the established contracts.
        Unexpected exceptions propagated by either retained owner are not
        reclassified as business, materialization, or persistence evidence.

    Non-goals:
        This owner does not execute business work, own the business transaction,
        select production eligibility, rebuild receipts, allocate identities,
        retry, resolve unknown durability, reconcile history, or participate in
        Stage 4C, Stage 4E, or normal production invocation wiring.
    """

    def __init__(
        self,
        *,
        materialization_owner: _MaterializationOwner,
        receipt_transaction_owner: PostgresDecisionReceiptTransactionOwner,
    ) -> None:
        """Retain the exact PR1 and receipt-transaction owner lifecycles."""

        if not isinstance(
            materialization_owner,
            _MaterializationOwner,
        ):
            raise TypeError(
                "materialization_owner must be "
                "PostgresWriteSideDecisionReceiptMaterializationOwner"
            )
        if not isinstance(
            receipt_transaction_owner,
            PostgresDecisionReceiptTransactionOwner,
        ):
            raise TypeError(
                "receipt_transaction_owner must be "
                "PostgresDecisionReceiptTransactionOwner"
            )

        self._materialization_owner = materialization_owner
        self._receipt_transaction_owner = receipt_transaction_owner
        self._cached_delivery: (
            PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery
            | None
        ) = None
        self._lifecycle_lock = Lock()

    def compose(
        self,
    ) -> PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery:
        """Materialize and persist once, then return one cached delivery.

        Returns:
            A compound delivery retaining the exact business result and PR1
            delivery. Failed materialization carries explicit
            persistence-not-reached evidence; successful materialization carries
            the exact existing commit-aware persistence result.

        Guarantees:
            Receipt persistence uses a separate transaction owned by the
            retained transaction owner, receives the exact PR1 receipt object,
            and is invoked no more than once for a normally returned delivery.
            Concurrent callers receive the identical cached delivery.

        Non-guarantees:
            This method does not reinterpret durability, authorize retry,
            resolve ``UNKNOWN``, or change the exact business result.
        """

        with self._lifecycle_lock:
            if self._cached_delivery is not None:
                return self._cached_delivery

            materialization_delivery = self._materialization_owner.materialize()
            if materialization_delivery.status is (
                _MaterializationStatus.MATERIALIZATION_FAILED
            ):
                delivery = (
                    PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery(
                        business_result=(
                            materialization_delivery.business_result
                        ),
                        materialization_delivery=materialization_delivery,
                        persistence_reached=False,
                        persistence_result=None,
                    )
                )
            else:
                receipt = materialization_delivery.receipt
                if receipt is None:
                    raise AssertionError(
                        "materialized delivery must retain its exact receipt"
                    )
                persistence_result = self._receipt_transaction_owner.persist(
                    receipt,
                    materialization_provenance=(
                        DecisionReceiptMaterializationProvenance.LIVE_RESULT
                    ),
                )
                delivery = (
                    PostgresWriteSideDecisionReceiptPersistenceCompositionDelivery(
                        business_result=(
                            materialization_delivery.business_result
                        ),
                        materialization_delivery=materialization_delivery,
                        persistence_reached=True,
                        persistence_result=persistence_result,
                    )
                )

            self._cached_delivery = delivery
            return delivery
