from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


@dataclass(frozen=True)
class RuntimeTechnicalStatusMapping:
    """
    Semantic mapping rule for one runtime technical status.

    This rule translates a raw technical status into semantic meaning.
    It does not decide runtime action, execution strategy, durable receipt
    persistence, or retry governance.
    """

    ok: bool
    category: SemanticOutcomeCategory
    semantic_code: SemanticOutcomeCode
    severity: SemanticSeverity
    risk_level: SemanticRiskLevel
    reversibility: SemanticReversibility


_STATUS_MAPPINGS: dict[str, RuntimeTechnicalStatusMapping] = {
    "MATCH": RuntimeTechnicalStatusMapping(
        ok=True,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "RESOLVED_FROM_SNAPSHOT": RuntimeTechnicalStatusMapping(
        ok=True,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "MISSING_SNAPSHOT": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
        semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "MISSING_PROJECTION": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.REBUILD_REQUIRED,
        semantic_code=SemanticOutcomeCode.REQUIRES_REBUILD,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "NO_ACCEPTED_HISTORY": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNRESOLVED,
        semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.UNKNOWN,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
    "NO_ACCEPTED_HISTORY_FOR_ORDER": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNRESOLVED,
        semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.UNKNOWN,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
    "INVALID_SNAPSHOT_BOUNDARY": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNTRUSTED,
        semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "INVALID_SNAPSHOT_PRECONDITION": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNTRUSTED,
        semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "INVALID_SNAPSHOT_COMPATIBILITY": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNTRUSTED,
        semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.UNRESOLVED,
        semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
    "TAIL_REPLAY_FAILED": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
        semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "DRIFT": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.DRIFT,
        semantic_code=SemanticOutcomeCode.DRIFT_DETECTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "SNAPSHOT_ASSISTED_DRIFT": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.DRIFT,
        semantic_code=SemanticOutcomeCode.DRIFT_DETECTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.REBUILDABLE,
    ),
    "WRITE_SIDE_ACCEPTED": RuntimeTechnicalStatusMapping(
        ok=True,
        category=SemanticOutcomeCategory.VALID,
        semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "COMPASS_VALIDATION_BLOCKED": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.BLOCK_REQUIRED,
        semantic_code=SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
    "CONCURRENT_STATE_STALENESS": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
        semantic_code=SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "WRITE_SIDE_INFRASTRUCTURE_ERROR": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.ESCALATION_REQUIRED,
        semantic_code=SemanticOutcomeCode.REQUIRES_OPERATOR_REVIEW,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
    "OCC_CONFLICT_AFTER_VALIDATION": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
        semantic_code=SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "LOCK_TIMEOUT": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.CONCURRENCY_UNCERTAIN,
        semantic_code=SemanticOutcomeCode.CONCURRENCY_UNCERTAIN,
        severity=SemanticSeverity.WARNING,
        risk_level=SemanticRiskLevel.MEDIUM,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "IDEMPOTENT_REPLAY": RuntimeTechnicalStatusMapping(
        ok=True,
        category=SemanticOutcomeCategory.RETRY_CLASSIFIED,
        semantic_code=SemanticOutcomeCode.IDEMPOTENT_REPLAY_ALLOWED,
        severity=SemanticSeverity.INFO,
        risk_level=SemanticRiskLevel.LOW,
        reversibility=SemanticReversibility.REVERSIBLE,
    ),
    "IDEMPOTENCY_CONFLICT": RuntimeTechnicalStatusMapping(
        ok=False,
        category=SemanticOutcomeCategory.BLOCK_REQUIRED,
        semantic_code=SemanticOutcomeCode.SEMANTIC_CONFLICT_DETECTED,
        severity=SemanticSeverity.ERROR,
        risk_level=SemanticRiskLevel.HIGH,
        reversibility=SemanticReversibility.UNKNOWN,
    ),
}


def map_runtime_technical_status(
    *,
    outcome_id: UUID,
    technical_status: str | Enum,
    boundary: SemanticBoundary,
    reason: str,
    context: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> SemanticOutcome:
    """
    Convert a raw runtime technical status into a SemanticOutcome.

    This mapper is intentionally generic. It maps a status name into semantic
    meaning, but it does not inspect projection validator result objects,
    write-side admission result objects, or retry attempt records.

    Adapter-specific mapping belongs in later PRs.
    """

    normalized_status = _normalize_technical_status(technical_status)
    mapping = _mapping_for_status(normalized_status)
    merged_evidence = _merge_technical_status_into_evidence(
        technical_status=normalized_status,
        evidence=evidence,
    )

    return SemanticOutcome(
        outcome_id=outcome_id,
        ok=mapping.ok,
        boundary=boundary,
        category=mapping.category,
        semantic_code=mapping.semantic_code,
        severity=mapping.severity,
        risk_level=mapping.risk_level,
        reversibility=mapping.reversibility,
        reason=reason,
        context=dict(context or {}),
        evidence=merged_evidence,
    )


def supported_runtime_technical_statuses() -> frozenset[str]:
    """
    Return the currently supported runtime technical status names.

    This exists for tests, documentation, and future adapter validation.
    """

    return frozenset(_STATUS_MAPPINGS)


def _mapping_for_status(status: str) -> RuntimeTechnicalStatusMapping:
    try:
        return _STATUS_MAPPINGS[status]
    except KeyError as exc:
        raise ValueError(f"Unsupported runtime technical status: {status}") from exc


def _normalize_technical_status(value: str | Enum) -> str:
    if isinstance(value, Enum):
        raw_value = value.value
        if isinstance(raw_value, str):
            return _require_non_empty_status(raw_value)
        return _require_non_empty_status(value.name)

    if isinstance(value, str):
        return _require_non_empty_status(value)

    raise TypeError("technical_status must be a string or Enum value")


def _require_non_empty_status(value: str) -> str:
    if not value.strip():
        raise ValueError("technical_status must be a non-empty string")
    return value


def _merge_technical_status_into_evidence(
    *,
    technical_status: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(evidence or {})

    existing = merged.get("technical_status")
    if existing is not None and existing != technical_status:
        raise ValueError(
            "evidence technical_status must match mapped technical_status"
        )

    merged["technical_status"] = technical_status
    return merged