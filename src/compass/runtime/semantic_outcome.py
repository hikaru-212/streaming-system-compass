from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID


class SemanticOutcomeCategory(str, Enum):
    """
    Coarse semantic outcome family for runtime correctness.

    This category is intentionally broader than a technical validator status.
    It describes what kind of semantic condition was observed without deciding
    the runtime action, execution strategy, or retry policy.
    """

    VALID = "VALID"
    UNRESOLVED = "UNRESOLVED"
    UNTRUSTED = "UNTRUSTED"
    DRIFT = "DRIFT"
    FALLBACK_REQUIRED = "FALLBACK_REQUIRED"
    REBUILD_REQUIRED = "REBUILD_REQUIRED"
    BLOCK_REQUIRED = "BLOCK_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    CONCURRENCY_UNCERTAIN = "CONCURRENCY_UNCERTAIN"
    RETRY_CLASSIFIED = "RETRY_CLASSIFIED"
    INTENT_INCONSISTENT = "INTENT_INCONSISTENT"


class SemanticOutcomeCode(str, Enum):
    """
    Stable machine-readable semantic meaning.

    These codes should be produced from technical runtime evidence in later
    mapping PRs. They must not directly execute recovery, select strategy, or
    authorize retries.
    """

    SEMANTICALLY_VALID = "SEMANTICALLY_VALID"
    RUNTIME_UNRESOLVED = "RUNTIME_UNRESOLVED"
    DERIVED_STATE_UNTRUSTED = "DERIVED_STATE_UNTRUSTED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    FAST_PATH_UNAVAILABLE = "FAST_PATH_UNAVAILABLE"
    REQUIRES_AUTHORITY_FALLBACK = "REQUIRES_AUTHORITY_FALLBACK"
    REQUIRES_REBUILD = "REQUIRES_REBUILD"
    REQUIRES_OPERATOR_REVIEW = "REQUIRES_OPERATOR_REVIEW"
    REJECT_DOWNSTREAM_USAGE = "REJECT_DOWNSTREAM_USAGE"
    CONCURRENCY_UNCERTAIN = "CONCURRENCY_UNCERTAIN"
    IDEMPOTENT_REPLAY_ALLOWED = "IDEMPOTENT_REPLAY_ALLOWED"
    SEMANTIC_CONFLICT_DETECTED = "SEMANTIC_CONFLICT_DETECTED"
    INTENT_DRIFT_DETECTED = "INTENT_DRIFT_DETECTED"


class SemanticBoundary(str, Enum):
    """
    Runtime boundary where the semantic outcome was produced or applies.
    """

    LAYER_1_WRITE_SIDE = "LAYER_1_WRITE_SIDE"
    LAYER_2_READ_SIDE = "LAYER_2_READ_SIDE"
    SNAPSHOT_TRUST = "SNAPSHOT_TRUST"
    IDEMPOTENCY = "IDEMPOTENCY"
    CONCURRENCY_ADMISSION = "CONCURRENCY_ADMISSION"
    RUNTIME_GOVERNANCE = "RUNTIME_GOVERNANCE"


class SemanticSeverity(str, Enum):
    """
    Human-facing severity of the semantic condition.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SemanticRiskLevel(str, Enum):
    """
    Risk level carried with a semantic outcome.

    Risk is evidence for later policy and strategy layers. It is not itself a
    runtime decision.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class SemanticReversibility(str, Enum):
    """
    Whether the semantic condition is expected to be recoverable.
    """

    REVERSIBLE = "REVERSIBLE"
    REBUILDABLE = "REBUILDABLE"
    COMPENSABLE = "COMPENSABLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SemanticOutcome:
    """
    Semantic interpretation of runtime correctness evidence.

    This object answers:
    - what semantic condition was observed?
    - at which boundary was it observed?
    - how severe / risky / reversible is it?
    - what context and evidence support the interpretation?

    This object does NOT answer:
    - what runtime action should be executed?
    - which recovery path should be used?
    - which execution strategy is cheapest or healthiest?
    - whether retry is allowed?
    - whether a durable receipt has been written?

    Context and evidence are defensively copied and deeply frozen for common
    container types so that outcome evidence cannot be mutated through the
    original input objects after construction.
    """

    outcome_id: UUID
    ok: bool
    boundary: SemanticBoundary
    category: SemanticOutcomeCategory
    semantic_code: SemanticOutcomeCode
    severity: SemanticSeverity
    risk_level: SemanticRiskLevel
    reversibility: SemanticReversibility
    reason: str
    context: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_uuid(self.outcome_id, "outcome_id")
        _require_non_empty_string(self.reason, "reason")
        _require_enum(self.boundary, SemanticBoundary, "boundary")
        _require_enum(self.category, SemanticOutcomeCategory, "category")
        _require_enum(self.semantic_code, SemanticOutcomeCode, "semantic_code")
        _require_enum(self.severity, SemanticSeverity, "severity")
        _require_enum(self.risk_level, SemanticRiskLevel, "risk_level")
        _require_enum(
            self.reversibility,
            SemanticReversibility,
            "reversibility",
        )
        _require_mapping(self.context, "context")
        _require_mapping(self.evidence, "evidence")

        object.__setattr__(self, "context", _freeze_mapping(self.context))
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence))


def _require_uuid(value: object, field_name: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be UUID")


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


def _require_mapping(value: object, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {key: _freeze_value(item) for key, item in value.items()}
    )


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_freeze_value(item) for item in value)
    return value