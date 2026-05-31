from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Protocol

from src.core.order.events import OrderEvent
from src.core.order.enums import OrderStatus


class ValidationMode(Enum):
    """
    Runtime validation mode selector for Compass Layer 1.
    """
    STRICT = "strict"
    OFF = "off"


class ValidationVerdict(Enum):
    """
    Semantic truth outcome produced by a transition validator.

    Important:
    - this is NOT the same as runtime enforcement action
    - validation truth and system response are intentionally separated
    """
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnforcementAction(Enum):
    """
    Runtime response chosen after semantic validation.

    Current minimal Phase 1 mapping:
    - PASSED -> ALLOW
    - SKIPPED -> ALLOW
    - FAILED -> BLOCK
    """
    ALLOW = "allow"
    BLOCK = "block"


@dataclass
class ValidationResult:
    """
    Detailed semantic-validation result for one candidate event.

    This object answers:
    - did semantic transition validation pass or fail?
    - why?
    - which validator made the decision?
    - how much time did validation take?
    """
    verdict: ValidationVerdict
    reason: str
    candidate_event_id: str
    validator_name: str
    validation_mode: ValidationMode
    logic_validation_time_ms: float
    io_time_ms: float
    total_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationDecision:
    """
    Final runtime-facing decision returned to registry.

    Important separation:
    - validation_result = semantic truth outcome
    - action = runtime enforcement behavior
    """
    action: EnforcementAction
    validation_result: ValidationResult


@dataclass(frozen=True)
class ValidationContext:
    """
    Accepted-history truth context supplied to transition validators.

    Field meaning:
    - actual_prev_event: actual last accepted event
    - actual_prev_version: actual current stream version
    - actual_prev_status: predecessor business status implied by accepted history
    """
    actual_prev_event: Optional[OrderEvent]
    actual_prev_version: int
    actual_prev_status: OrderStatus


class TransitionValidator(Protocol):
    """
    Protocol for Compass Layer 1 transition validators.
    """
    def validate(self, candidate_event: OrderEvent, context: ValidationContext) -> ValidationResult:
        ...