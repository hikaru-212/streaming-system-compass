
import time

from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    OrderCorrectnessRuleId,
)
from src.core.order.enums import EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.rule_violation_evidence import OrderRuleViolationEvidence

from .rule_evaluation_evidence import FullProofValidationEvidence
from .types import (
    ValidationContext,
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)


class NoOpValidator:
    """
    Validation-off path.

    Used when runtime mode is OFF.

    This validator intentionally performs no semantic validation.
    It keeps the validation runtime interface stable when validation is disabled.
    """

    def validate(self, candidate_event: OrderEvent, context: ValidationContext) -> ValidationResult:
        start_total = time.perf_counter()
        end_total = time.perf_counter()

        return ValidationResult(
            verdict=ValidationVerdict.SKIPPED,
            reason="Validation skipped because validation mode is OFF",
            candidate_event_id=candidate_event.event_id,
            validator_name=self.__class__.__name__,
            validation_mode=ValidationMode.OFF,
            logic_validation_time_ms=0.0,
            io_time_ms=0.0,
            total_time_ms=(end_total - start_total) * 1000.0,
            metadata={},
        )


class FullProofValidator:
    """
    Full proof-based Layer 1 transition validator.

    This validator does not trust the event proof directly.
    The proof is treated as a semantic claim carried by the candidate event.

    Responsibility:
    - verify sequence continuity
    - verify predecessor event identity
    - verify predecessor version consistency
    - verify claimed predecessor status against accepted history
    - verify event-type-specific transition legality

    Important distinction:
    - event.proof.prev_status:
        The predecessor status claimed by the candidate event.

    - context.actual_prev_status:
        The actual predecessor status derived from accepted history.

    A valid event must satisfy both:
    1. its proof claim must match actual accepted history
    2. its event type must be legal from that predecessor status

    Example:
    - CREATED requires previous status INIT.
    - PAID requires previous status CREATED.
    """

    REQUIRED_PREV_STATUS_BY_EVENT_TYPE = {
        EventType.CREATED: OrderStatus.INIT,
        EventType.PAID: OrderStatus.CREATED,
    }

    def validate(self, candidate_event: OrderEvent, context: ValidationContext) -> ValidationResult:
        """Validate one candidate while preserving the legacy result API.

        Args:
            candidate_event: Event-shaped candidate to compare with accepted
                context.
            context: Accepted-history-derived predecessor facts.

        Returns:
            The existing primary semantic validation result.

        This view does not expose sibling rule evidence and retains the current
        ``TransitionValidator`` protocol signature and behavior.
        """

        validation_result, _ = self._validate(candidate_event, context)
        return validation_result

    def validate_with_rule_evidence(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> FullProofValidationEvidence:
        """Validate once and expose bounded sibling rule-violation evidence.

        Args:
            candidate_event: Event-shaped candidate to compare with accepted
                context.
            context: Accepted-history-derived predecessor facts.

        Returns:
            The primary ``ValidationResult`` plus the stable rule identity for
            the one failure branch observed before validation terminated. A
            passing result has no violation evidence.

        This method does not rank violations, collect all failures, select an
        action, authorize retry, or prescribe repair.
        """

        validation_result, violated_rule_id = self._validate(
            candidate_event,
            context,
        )
        observed_violation = (
            None
            if violated_rule_id is None
            else OrderRuleViolationEvidence(
                contract_id=ORDER_CORRECTNESS_CONTRACT_V0.contract_id,
                contract_version=(
                    ORDER_CORRECTNESS_CONTRACT_V0.contract_version
                ),
                rule_id=violated_rule_id,
                candidate_event_id=candidate_event.event_id,
            )
        )
        return FullProofValidationEvidence(
            validation_result=validation_result,
            observed_violation=observed_violation,
        )

    def _validate(
        self,
        candidate_event: OrderEvent,
        context: ValidationContext,
    ) -> tuple[ValidationResult, OrderCorrectnessRuleId | None]:
        """Run the single FullProof branch tree for both public result views."""

        start_total = time.perf_counter()
        io_time_ms = 0.0
        start_logic = time.perf_counter()

        expected_prev_version = context.actual_prev_version
        expected_prev_event_id = (
            None
            if context.actual_prev_event is None
            else context.actual_prev_event.event_id
        )
        expected_prev_status = context.actual_prev_status

        # 1. Sequence continuity:
        # If accepted history is at version N, the candidate event must be N + 1.
        if candidate_event.sequence != expected_prev_version + 1:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason=(
                    f"Sequence violation: got {candidate_event.sequence}, "
                    f"expected {expected_prev_version + 1}"
                ),
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "expected_prev_version": expected_prev_version,
                    "actual_sequence": candidate_event.sequence,
                    "expected_sequence": expected_prev_version + 1,
                    "expected_prev_event_id": expected_prev_event_id,
                    "expected_prev_status": expected_prev_status.value,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
            )

        # 2. Predecessor identity:
        # The event must point to the actual last accepted event.
        if candidate_event.proof.prev_event_id != expected_prev_event_id:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="Predecessor mismatch: prev_event_id does not match actual previous event",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "expected_prev_event_id": expected_prev_event_id,
                    "claimed_prev_event_id": candidate_event.proof.prev_event_id,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED,
            )

        # 3. Predecessor version:
        # The event's proof must claim the same previous version as accepted history.
        if candidate_event.proof.prev_version != expected_prev_version:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="Proof mismatch: prev_version does not match actual history",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "expected_prev_version": expected_prev_version,
                    "claimed_prev_version": candidate_event.proof.prev_version,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED,
            )

        # 4. Proof status must match actual history:
        # This checks whether the event's self-claimed predecessor status
        # agrees with the validator's view of accepted history.
        if candidate_event.proof.prev_status != expected_prev_status:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason="Proof mismatch: prev_status does not match actual history",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "actual_prev_status": expected_prev_status.value,
                    "claimed_prev_status": candidate_event.proof.prev_status.value,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED,
            )

        # 5. Event-type-specific transition legality:
        # Even if proof matches actual history, the event type itself must be
        # legal from that predecessor status.
        required_prev_status = self.REQUIRED_PREV_STATUS_BY_EVENT_TYPE.get(candidate_event.event_type)

        if required_prev_status is None:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason=f"Unsupported event type: {candidate_event.event_type.value}",
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "event_type": candidate_event.event_type.value,
                    "actual_prev_status": expected_prev_status.value,
                    "claimed_prev_status": candidate_event.proof.prev_status.value,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
            )

        if expected_prev_status != required_prev_status:
            end_logic = time.perf_counter()
            end_total = time.perf_counter()

            validation_result = ValidationResult(
                verdict=ValidationVerdict.FAILED,
                reason=(
                    f"Invalid transition: {candidate_event.event_type.value} requires "
                    f"prev_status={required_prev_status.value}, "
                    f"but actual_prev_status={expected_prev_status.value}"
                ),
                candidate_event_id=candidate_event.event_id,
                validator_name=self.__class__.__name__,
                validation_mode=ValidationMode.STRICT,
                logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
                io_time_ms=io_time_ms,
                total_time_ms=(end_total - start_total) * 1000.0,
                metadata={
                    "event_type": candidate_event.event_type.value,
                    "required_prev_status": required_prev_status.value,
                    "actual_prev_status": expected_prev_status.value,
                    "claimed_prev_status": candidate_event.proof.prev_status.value,
                },
            )
            return (
                validation_result,
                OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS,
            )

        end_logic = time.perf_counter()
        end_total = time.perf_counter()

        validation_result = ValidationResult(
            verdict=ValidationVerdict.PASSED,
            reason="Event passed full proof transition validation",
            candidate_event_id=candidate_event.event_id,
            validator_name=self.__class__.__name__,
            validation_mode=ValidationMode.STRICT,
            logic_validation_time_ms=(end_logic - start_logic) * 1000.0,
            io_time_ms=io_time_ms,
            total_time_ms=(end_total - start_total) * 1000.0,
            metadata={
                "event_type": candidate_event.event_type.value,
                "expected_prev_version": expected_prev_version,
                "expected_prev_event_id": expected_prev_event_id,
                "expected_prev_status": expected_prev_status.value,
                "claimed_prev_version": candidate_event.proof.prev_version,
                "claimed_prev_event_id": candidate_event.proof.prev_event_id,
                "claimed_prev_status": candidate_event.proof.prev_status.value,
            },
        )
        return validation_result, None
