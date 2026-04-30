from typing import Optional, Tuple, List

from src.core.order.aggregate import OrderAggregate
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.storage.event_store import EventStore
from src.storage.idempotency_store import (
    IdempotencyProvider,
    RequestSignature,
    IdempotencyVerdict,
)
from src.compass.transition.types import (
    ValidationContext,
    EnforcementAction,
)
from src.compass.transition.runtime import ValidationRuntime
from .admission import ConcurrencyGate, AdmissionVerdict


class OrderRegistry:
    """
    Transactional orchestration boundary.

    Main flow:
    idempotency -> rehydrate aggregate -> produce candidate event
    -> semantic validation -> persistence admission -> local apply -> idempotency record

    Registry owns:
    - request replay / idempotency distinction
    - aggregate rehydration
    - validation context construction
    - calling validation runtime
    - calling admission gate

    Registry does NOT own:
    - aggregate business legality
    - validation semantics themselves
    - append-time continuity logic itself
    """

    def __init__(
        self,
        store: EventStore,
        idem: IdempotencyProvider,
        validation_runtime: ValidationRuntime,
        gate: ConcurrencyGate,
    ):
        self.store = store
        self.idem = idem
        self.validation_runtime = validation_runtime
        self.gate = gate

    def _rehydrate_aggregate(self, order_id: str) -> Tuple[OrderAggregate, List[OrderEvent]]:
        """
        Rebuild fresh aggregate execution state from accepted history.

        Replay rule:
        - accepted history must deterministically reconstruct aggregate state
        - replay and live apply share the same apply(event) mutation path
        """
        history = self.store.load(order_id)
        aggregate = OrderAggregate(order_id)

        for historical_event in history:
            aggregate.apply(historical_event)

        return aggregate, history



    def _build_validation_context(
        self,
        aggregate: OrderAggregate,
        actual_prev_event: Optional[OrderEvent],
        ) -> ValidationContext:
        """
        Build validation context from accepted history.

        Source of truth:
        - actual_prev_event comes from accepted event history
        - actual_prev_version comes from the rehydrated aggregate
        - actual_prev_status comes from the rehydrated aggregate

        Registry should not re-derive business status from event type.
        Aggregate.apply(event) is the single source of truth for state reconstruction.
        """
        return ValidationContext(
            actual_prev_event=actual_prev_event,
            actual_prev_version=aggregate.current_version,
            actual_prev_status=aggregate.status,
        )

    def _check_idempotency(self, signature: RequestSignature):
        """
        Request replay policy.

        Rules:
        - same request_id + same semantic payload -> replay
        - same request_id + different semantic payload -> conflict
        - unseen request_id -> continue normal processing
        """
        decision = self.idem.check(signature)

        if decision.verdict == IdempotencyVerdict.REPLAY:
            return decision.record.accepted_event

        if decision.verdict == IdempotencyVerdict.CONFLICT:
            return decision

        return None

    def handle_create(self, request_id: str, order_id: str, amount: float):
        """
        End-to-end write-side flow for create command.

        Side-effect ordering rule:
        - do not record idempotency before event admission succeeds
        - do not mutate accepted history before semantic validation passes
        """
        signature = RequestSignature(
            request_id=request_id,
            command_type=CommandType.CREATE,
            order_id=order_id,
            amount=amount,
        )

        # 1. Idempotency Check
        idempotency_outcome = self._check_idempotency(signature)
        if idempotency_outcome is not None:
            return idempotency_outcome

        # 2. Rehydrate and Context Building
        aggregate, history = self._rehydrate_aggregate(order_id)
        actual_prev_event = history[-1] if history else None
        validation_context = self._build_validation_context(aggregate, actual_prev_event)

        # 3. Decision Logic (Core)
        new_event = aggregate.create(request_id, amount)

        # 4. Compass Semantic Validation (Enabler)
        validation_decision = self.validation_runtime.decide(new_event, validation_context)
        if validation_decision.action != EnforcementAction.ALLOW:
            return validation_decision

        # 5. Concurrency Admission (Enabler)
        expected_current_version = aggregate.current_version
        admission_result = self.gate.admit(new_event, expected_current_version)
        if admission_result.verdict != AdmissionVerdict.ADMITTED:
            return admission_result

        # 6. Post-Commit Mutation & Recording
        aggregate.apply(new_event)
        self.idem.record(signature, new_event)

        return new_event

    def handle_pay(self, request_id: str, order_id: str, amount: float):
        """
        End-to-end write-side flow for pay command.
        """
        signature = RequestSignature(
            request_id=request_id,
            command_type=CommandType.PAY,
            order_id=order_id,
            amount=amount,
        )

        idempotency_outcome = self._check_idempotency(signature)
        if idempotency_outcome is not None:
            return idempotency_outcome

        aggregate, history = self._rehydrate_aggregate(order_id)
        actual_prev_event = history[-1] if history else None
        validation_context = self._build_validation_context(aggregate, actual_prev_event)

        new_event = aggregate.pay(request_id, amount)

        validation_decision = self.validation_runtime.decide(new_event, validation_context)
        if validation_decision.action != EnforcementAction.ALLOW:
            return validation_decision
        
        expected_current_version = aggregate.current_version
        admission_result = self.gate.admit(new_event, expected_current_version)
        if admission_result.verdict != AdmissionVerdict.ADMITTED:
            return admission_result

        aggregate.apply(new_event)
        self.idem.record(signature, new_event)

        return new_event