"""Deterministic vulnerable model for indirect authority composition.

This module implements only PR2 of the indirect-authority-escalation demo:

* a limited actor is denied the protected accepted-fact append directly;
* the same actor may submit a restock request through locally allowed edges;
* a privileged service deliberately promotes the resulting candidate without
  semantic authority-evidence admission; and
* the authoritative effect is recorded as accepted history.

The model is intentionally local, synchronous, in-memory, and domain-specific.
It contains no PR3 evidence authority, semantic admission, Compass production
integration, generic RBAC, retry, concurrency, persistence, or external I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import ClassVar, Mapping


class Component(str, Enum):
    """Closed identities that participate in the PR2 capability graph."""

    LIMITED_AGENT = "LIMITED_AGENT"
    RESTOCK_WORKFLOW = "RESTOCK_WORKFLOW"
    INVENTORY_AUTHORITY_SERVICE = "INVENTORY_AUTHORITY_SERVICE"
    AUTHORITATIVE_INVENTORY_STORE = "AUTHORITATIVE_INVENTORY_STORE"


class LocalOperation(str, Enum):
    """Closed local operations needed by the direct and composed paths."""

    SUBMIT_RESTOCK_REQUEST = "SUBMIT_RESTOCK_REQUEST"
    SUBMIT_REPLENISHMENT_CANDIDATE = "SUBMIT_REPLENISHMENT_CANDIDATE"
    APPEND_ACCEPTED_REPLENISHMENT = "APPEND_ACCEPTED_REPLENISHMENT"


class PermissionDecision(str, Enum):
    """Local capability decision; it does not express semantic authority."""

    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class LocalCapability:
    """Identify one caller, local operation, and target capability edge."""

    caller: Component
    operation: LocalOperation
    target: Component


@dataclass(frozen=True)
class CapabilityCheck:
    """Preserve the exact local edge and its deterministic permission decision."""

    capability: LocalCapability
    decision: PermissionDecision


_CAPABILITY_DECISIONS: Mapping[LocalCapability, PermissionDecision] = (
    MappingProxyType(
        {
            LocalCapability(
                caller=Component.LIMITED_AGENT,
                operation=LocalOperation.SUBMIT_RESTOCK_REQUEST,
                target=Component.RESTOCK_WORKFLOW,
            ): PermissionDecision.ALLOWED,
            LocalCapability(
                caller=Component.RESTOCK_WORKFLOW,
                operation=LocalOperation.SUBMIT_REPLENISHMENT_CANDIDATE,
                target=Component.INVENTORY_AUTHORITY_SERVICE,
            ): PermissionDecision.ALLOWED,
            LocalCapability(
                caller=Component.INVENTORY_AUTHORITY_SERVICE,
                operation=LocalOperation.APPEND_ACCEPTED_REPLENISHMENT,
                target=Component.AUTHORITATIVE_INVENTORY_STORE,
            ): PermissionDecision.ALLOWED,
            LocalCapability(
                caller=Component.LIMITED_AGENT,
                operation=LocalOperation.APPEND_ACCEPTED_REPLENISHMENT,
                target=Component.AUTHORITATIVE_INVENTORY_STORE,
            ): PermissionDecision.DENIED,
        }
    )
)


def decide_local_capability(
    *,
    caller: Component,
    operation: LocalOperation,
    target: Component,
) -> CapabilityCheck:
    """Evaluate one edge in the closed PR2 local capability model.

    Args:
        caller: Component attempting the operation.
        operation: Finite local operation being attempted.
        target: Component that owns the local operation boundary.

    Returns:
        The exact capability edge and its decision. The four experiment edges
        are declared explicitly; any other typed combination fails closed as
        ``DENIED``.

    This decision answers only whether the local call is permitted. It does not
    decide whether a candidate is semantically supported as an authoritative
    inventory fact.
    """

    capability = LocalCapability(
        caller=caller,
        operation=operation,
        target=target,
    )
    return CapabilityCheck(
        capability=capability,
        decision=_CAPABILITY_DECISIONS.get(
            capability,
            PermissionDecision.DENIED,
        ),
    )


def _validate_product_and_quantity(product_id: object, quantity: object) -> None:
    """Reject empty product identities and non-positive integer quantities."""

    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string")
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("quantity must be a positive int")


@dataclass(frozen=True)
class RestockRequest:
    """Represent a request for replenishment, not a replenishment fact."""

    product_id: str
    quantity: int

    def __post_init__(self) -> None:
        _validate_product_and_quantity(self.product_id, self.quantity)


@dataclass(frozen=True)
class CandidateStockReplenished:
    """Represent proposed replenishment before accepted-fact promotion."""

    product_id: str
    quantity: int

    def __post_init__(self) -> None:
        _validate_product_and_quantity(self.product_id, self.quantity)


@dataclass(frozen=True)
class AcceptedStockReplenished:
    """Represent replenishment admitted into authoritative accepted history."""

    product_id: str
    quantity: int

    def __post_init__(self) -> None:
        _validate_product_and_quantity(self.product_id, self.quantity)


PROTECTED_PRODUCT_ID = "product-a"
PROTECTED_QUANTITY = 10
PROTECTED_REPLENISHMENT = AcceptedStockReplenished(
    product_id=PROTECTED_PRODUCT_ID,
    quantity=PROTECTED_QUANTITY,
)


@dataclass(frozen=True)
class AppendResult:
    """Record one attempted accepted-fact append and its local outcome."""

    capability_check: CapabilityCheck
    attempted_fact: AcceptedStockReplenished
    appended_fact: AcceptedStockReplenished | None

    def __post_init__(self) -> None:
        if self.capability_check.decision is PermissionDecision.ALLOWED:
            if self.appended_fact != self.attempted_fact:
                raise ValueError(
                    "ALLOWED append must preserve the exact attempted fact"
                )
            return
        if self.appended_fact is not None:
            raise ValueError("DENIED append must not expose an appended fact")

    @property
    def fact_appended(self) -> bool:
        """Return whether the attempted fact entered accepted history."""

        return self.appended_fact is not None


@dataclass(frozen=True)
class CandidatePromotionResult:
    """Record vulnerable candidate submission and its privileged append result."""

    candidate_submission_check: CapabilityCheck
    candidate: CandidateStockReplenished
    append_result: AppendResult | None

    def __post_init__(self) -> None:
        allowed = (
            self.candidate_submission_check.decision
            is PermissionDecision.ALLOWED
        )
        if allowed != (self.append_result is not None):
            raise ValueError(
                "candidate submission decision and append presence must agree"
            )


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Record request admission, candidate production, and downstream result."""

    request_submission_check: CapabilityCheck
    candidate: CandidateStockReplenished | None
    promotion_result: CandidatePromotionResult | None

    def __post_init__(self) -> None:
        allowed = (
            self.request_submission_check.decision
            is PermissionDecision.ALLOWED
        )
        complete = self.candidate is not None and self.promotion_result is not None
        if allowed != complete:
            raise ValueError(
                "request decision, candidate, and promotion presence must agree"
            )


class AuthoritativeInventoryStore:
    """Own accepted inventory fact history and derive inventory from that history.

    The store enforces the local append capability and accepts only
    ``AcceptedStockReplenished`` values. It does not store an independently
    mutable inventory integer and it does not evaluate candidate evidence. In
    PR2 the privileged service remains responsible for, and deliberately fails
    at, the semantic promotion boundary.
    """

    component: ClassVar[Component] = Component.AUTHORITATIVE_INVENTORY_STORE

    def __init__(self) -> None:
        self._accepted_facts: list[AcceptedStockReplenished] = []

    def append_accepted_replenishment(
        self,
        *,
        caller: Component,
        fact: AcceptedStockReplenished,
    ) -> AppendResult:
        """Attempt to append one accepted replenishment through the local gate.

        Args:
            caller: Component invoking the store append boundary.
            fact: Accepted replenishment fact being attempted.

        Returns:
            An immutable result preserving the exact capability decision,
            attempted fact, and appended fact when allowed. A denied result does
            not mutate accepted history.

        Raises:
            TypeError: If ``fact`` is a request or candidate rather than an
                ``AcceptedStockReplenished`` value.
        """

        if not isinstance(fact, AcceptedStockReplenished):
            raise TypeError("fact must be AcceptedStockReplenished")

        capability_check = decide_local_capability(
            caller=caller,
            operation=LocalOperation.APPEND_ACCEPTED_REPLENISHMENT,
            target=self.component,
        )
        if capability_check.decision is PermissionDecision.DENIED:
            return AppendResult(
                capability_check=capability_check,
                attempted_fact=fact,
                appended_fact=None,
            )

        self._accepted_facts.append(fact)
        return AppendResult(
            capability_check=capability_check,
            attempted_fact=fact,
            appended_fact=fact,
        )

    @property
    def accepted_facts(self) -> tuple[AcceptedStockReplenished, ...]:
        """Return an immutable view of authoritative accepted fact history."""

        return tuple(self._accepted_facts)

    def inventory(self, product_id: str) -> int:
        """Fold accepted replenishment history into inventory for one product."""

        if not isinstance(product_id, str) or not product_id.strip():
            raise ValueError("product_id must be a non-empty string")
        return sum(
            fact.quantity
            for fact in self._accepted_facts
            if fact.product_id == product_id
        )


class InventoryAuthorityService:
    """Own privileged accepted-fact mutation for the deliberately vulnerable path.

    The service verifies that the candidate arrived through the permitted
    workflow edge, then promotes it directly into an accepted replenishment and
    invokes the store through its legitimate append capability. PR2
    deliberately contains no semantic authority-evidence sufficiency gate.
    """

    component: ClassVar[Component] = Component.INVENTORY_AUTHORITY_SERVICE

    def __init__(self, store: AuthoritativeInventoryStore) -> None:
        self._store = store

    def promote_candidate_without_semantic_authority_admission(
        self,
        *,
        caller: Component,
        candidate: CandidateStockReplenished,
    ) -> CandidatePromotionResult:
        """Promote a permitted-workflow candidate without PR3 authority evidence.

        Args:
            caller: Component submitting the replenishment candidate.
            candidate: Candidate produced by the restock workflow.

        Returns:
            The candidate-submission capability decision and, when locally
            allowed, the privileged accepted-fact append result.

        The missing semantic authority-admission step is the deliberate PR2
        vulnerability. Local capability checks remain active both here and at
        the store; this method does not bypass a denied permission.
        """

        if not isinstance(candidate, CandidateStockReplenished):
            raise TypeError("candidate must be CandidateStockReplenished")

        submission_check = decide_local_capability(
            caller=caller,
            operation=LocalOperation.SUBMIT_REPLENISHMENT_CANDIDATE,
            target=self.component,
        )
        if submission_check.decision is PermissionDecision.DENIED:
            return CandidatePromotionResult(
                candidate_submission_check=submission_check,
                candidate=candidate,
                append_result=None,
            )

        # Deliberate PR2 failure: permitted workflow arrival is treated as
        # sufficient for promotion from candidate to accepted inventory fact.
        accepted_fact = AcceptedStockReplenished(
            product_id=candidate.product_id,
            quantity=candidate.quantity,
        )
        append_result = self._store.append_accepted_replenishment(
            caller=self.component,
            fact=accepted_fact,
        )
        return CandidatePromotionResult(
            candidate_submission_check=submission_check,
            candidate=candidate,
            append_result=append_result,
        )


class RestockWorkflow:
    """Convert an allowed restock request into a candidate for the service."""

    component: ClassVar[Component] = Component.RESTOCK_WORKFLOW

    def __init__(self, authority_service: InventoryAuthorityService) -> None:
        self._authority_service = authority_service

    def handle_restock_request(
        self,
        *,
        caller: Component,
        request: RestockRequest,
    ) -> WorkflowExecutionResult:
        """Check request permission, create a candidate, and submit it downstream.

        Args:
            caller: Component submitting the restock request.
            request: Requested product and quantity.

        Returns:
            The exact request-edge decision and, when allowed, the distinct
            candidate plus the authority service's vulnerable promotion result.
        """

        if not isinstance(request, RestockRequest):
            raise TypeError("request must be RestockRequest")

        request_check = decide_local_capability(
            caller=caller,
            operation=LocalOperation.SUBMIT_RESTOCK_REQUEST,
            target=self.component,
        )
        if request_check.decision is PermissionDecision.DENIED:
            return WorkflowExecutionResult(
                request_submission_check=request_check,
                candidate=None,
                promotion_result=None,
            )

        candidate = CandidateStockReplenished(
            product_id=request.product_id,
            quantity=request.quantity,
        )
        promotion_result = (
            self._authority_service
            .promote_candidate_without_semantic_authority_admission(
                caller=self.component,
                candidate=candidate,
            )
        )
        return WorkflowExecutionResult(
            request_submission_check=request_check,
            candidate=candidate,
            promotion_result=promotion_result,
        )


class LimitedAgent:
    """Exercise the limited actor's direct and allowed-workflow paths."""

    component: ClassVar[Component] = Component.LIMITED_AGENT

    def attempt_direct_append(
        self,
        *,
        store: AuthoritativeInventoryStore,
        fact: AcceptedStockReplenished,
    ) -> AppendResult:
        """Attempt the protected accepted-fact append as the limited actor."""

        return store.append_accepted_replenishment(
            caller=self.component,
            fact=fact,
        )

    def submit_restock_request(
        self,
        *,
        workflow: RestockWorkflow,
        request: RestockRequest,
    ) -> WorkflowExecutionResult:
        """Submit one request through the actor's allowed workflow edge."""

        return workflow.handle_restock_request(
            caller=self.component,
            request=request,
        )


__all__ = (
    "AcceptedStockReplenished",
    "AppendResult",
    "AuthoritativeInventoryStore",
    "CandidatePromotionResult",
    "CandidateStockReplenished",
    "CapabilityCheck",
    "Component",
    "InventoryAuthorityService",
    "LimitedAgent",
    "LocalCapability",
    "LocalOperation",
    "PROTECTED_PRODUCT_ID",
    "PROTECTED_QUANTITY",
    "PROTECTED_REPLENISHMENT",
    "PermissionDecision",
    "RestockRequest",
    "RestockWorkflow",
    "WorkflowExecutionResult",
    "decide_local_capability",
)
