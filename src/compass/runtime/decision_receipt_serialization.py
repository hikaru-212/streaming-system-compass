"""Versioned portable serialization for the shared DecisionReceipt contract.

This module owns the explicit version 1 semantic payload shape. It is not a
PostgreSQL row mapper, persistence envelope, store, orchestration boundary,
reconciler, policy engine, retry mechanism, or logging adapter.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, TypeVar, cast
from uuid import UUID

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlagState,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
    EventAdmissionDisposition,
)
from src.compass.runtime.json_types import JsonValue, ensure_json_object
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


DECISION_RECEIPT_SERIALIZATION_VERSION = 1

__all__ = [
    "DECISION_RECEIPT_SERIALIZATION_VERSION",
    "serialize_decision_receipt",
    "deserialize_decision_receipt",
]


_SIGNED_64_BIT_MIN = -(2**63)
_SIGNED_64_BIT_MAX = 2**63 - 1

_OUTER_KEYS = frozenset({"receipt_serialization_version", "receipt"})
_RECEIPT_KEYS = frozenset(
    {
        "receipt_id",
        "outcome_id",
        "ok",
        "boundary",
        "category",
        "semantic_code",
        "severity",
        "risk_level",
        "reversibility",
        "reason",
        "evidence_source",
        "subject",
        "correlation",
        "actor",
        "cost_summary",
        "flags",
        "admission_evidence",
        "evidence_summary",
        "metadata",
    }
)
_SUBJECT_KEYS = frozenset({"subject_type", "subject_id"})
_CORRELATION_KEYS = frozenset(
    {
        "order_id",
        "request_id",
        "candidate_event_id",
        "accepted_event_id",
        "snapshot_id",
        "source_global_position",
        "identity_source",
    }
)
_ACTOR_KEYS = frozenset({"actor_id", "actor_role", "runtime_role"})
_COST_SUMMARY_KEYS = frozenset(
    {
        "elapsed_ms",
        "validation_elapsed_ms",
        "replay_elapsed_ms",
        "transaction_elapsed_ms",
        "lock_wait_ms",
    }
)
_FLAGS_KEYS = frozenset(
    {
        "fallback_required",
        "rebuild_required",
        "operator_review_required",
        "retry_candidate",
    }
)
_ADMISSION_EVIDENCE_KEYS = frozenset({"disposition"})

_EnumT = TypeVar("_EnumT", bound=Enum)


def serialize_decision_receipt(
    receipt: DecisionReceipt,
) -> dict[str, JsonValue]:
    """Serialize one DecisionReceipt into the exact portable version 1 payload.

    Args:
        receipt: The validated shared semantic receipt to serialize.

    Returns:
        A detached mutable outer dictionary containing
        ``receipt_serialization_version`` and an explicitly field-owned
        ``receipt`` object. UUIDs are canonical strings, enums are stable value
        strings, optional fields remain present as ``None``, and flexible JSON
        objects are detached mutable dictionaries and lists.

    Invariants:
        Every current DecisionReceipt and supporting-contract field is owned
        explicitly. Every integer anywhere in the payload must fit the signed
        64-bit range; booleans are never treated as integers. Flexible JSON
        retains the shared finite-number, string-key, and depth requirements.
        The emitted serialization version is always exactly 1.

    Raises:
        TypeError: If ``receipt`` is not a DecisionReceipt or flexible evidence
            contains a non-JSON-safe value.
        ValueError: If flexible evidence violates JSON constraints or any
            integer falls outside the version 1 persistence range.

    Non-goals:
        This function does not map PostgreSQL rows, add persistence-envelope
        fields, persist data, manage transactions, orchestrate materialization,
        reconcile history, choose policy, authorize retry, or produce logs.
    """

    if not isinstance(receipt, DecisionReceipt):
        raise TypeError("receipt must be DecisionReceipt")

    receipt_body: dict[str, JsonValue] = {
        "receipt_id": str(receipt.receipt_id),
        "outcome_id": str(receipt.outcome_id),
        "ok": receipt.ok,
        "boundary": receipt.boundary.value,
        "category": receipt.category.value,
        "semantic_code": receipt.semantic_code.value,
        "severity": receipt.severity.value,
        "risk_level": receipt.risk_level.value,
        "reversibility": receipt.reversibility.value,
        "reason": receipt.reason,
        "evidence_source": receipt.evidence_source.value,
        "subject": cast(
            JsonValue,
            {
                "subject_type": receipt.subject.subject_type.value,
                "subject_id": receipt.subject.subject_id,
            },
        ),
        "correlation": cast(
            JsonValue,
            {
                "order_id": receipt.correlation.order_id,
                "request_id": receipt.correlation.request_id,
                "candidate_event_id": _serialize_optional_uuid(
                    receipt.correlation.candidate_event_id
                ),
                "accepted_event_id": _serialize_optional_uuid(
                    receipt.correlation.accepted_event_id
                ),
                "snapshot_id": _serialize_optional_uuid(
                    receipt.correlation.snapshot_id
                ),
                "source_global_position": _serialize_optional_int64(
                    receipt.correlation.source_global_position,
                    "receipt.correlation.source_global_position",
                ),
                "identity_source": receipt.correlation.identity_source.value,
            },
        ),
        "actor": cast(
            JsonValue,
            {
                "actor_id": receipt.actor.actor_id,
                "actor_role": receipt.actor.actor_role,
                "runtime_role": receipt.actor.runtime_role,
            },
        ),
        "cost_summary": cast(
            JsonValue,
            {
                "elapsed_ms": _serialize_optional_int64(
                    receipt.cost_summary.elapsed_ms,
                    "receipt.cost_summary.elapsed_ms",
                ),
                "validation_elapsed_ms": _serialize_optional_int64(
                    receipt.cost_summary.validation_elapsed_ms,
                    "receipt.cost_summary.validation_elapsed_ms",
                ),
                "replay_elapsed_ms": _serialize_optional_int64(
                    receipt.cost_summary.replay_elapsed_ms,
                    "receipt.cost_summary.replay_elapsed_ms",
                ),
                "transaction_elapsed_ms": _serialize_optional_int64(
                    receipt.cost_summary.transaction_elapsed_ms,
                    "receipt.cost_summary.transaction_elapsed_ms",
                ),
                "lock_wait_ms": _serialize_optional_int64(
                    receipt.cost_summary.lock_wait_ms,
                    "receipt.cost_summary.lock_wait_ms",
                ),
            },
        ),
        "flags": cast(
            JsonValue,
            {
                "fallback_required": receipt.flags.fallback_required.value,
                "rebuild_required": receipt.flags.rebuild_required.value,
                "operator_review_required": (
                    receipt.flags.operator_review_required.value
                ),
                "retry_candidate": receipt.flags.retry_candidate.value,
            },
        ),
        "admission_evidence": _serialize_admission_evidence(
            receipt.admission_evidence
        ),
        "evidence_summary": cast(
            JsonValue,
            _detach_json_object(
                receipt.evidence_summary,
                "receipt.evidence_summary",
            ),
        ),
        "metadata": cast(
            JsonValue,
            _detach_json_object(receipt.metadata, "receipt.metadata"),
        ),
    }

    return {
        "receipt_serialization_version": (
            DECISION_RECEIPT_SERIALIZATION_VERSION
        ),
        "receipt": cast(JsonValue, receipt_body),
    }


def deserialize_decision_receipt(
    payload: Mapping[str, object],
) -> DecisionReceipt:
    """Deserialize one exact version 1 payload into a validated DecisionReceipt.

    Args:
        payload: A mapping with exactly ``receipt_serialization_version`` and
            ``receipt`` keys. The receipt body and every supporting object must
            contain their complete exact version 1 key sets.

    Returns:
        A shared DecisionReceipt reconstructed with native UUID and enum types.
        Flexible evidence and metadata pass through the existing receipt
        contract and are therefore validated and frozen again.

    Invariants:
        Only serialization version 1 is accepted. No missing or unknown key is
        ignored, optional fields must be present and use ``None`` when absent,
        UUID and enum instances are rejected in favor of portable strings, and
        scalar values are never coerced. Every integer, including nested JSON
        evidence, must fit the signed 64-bit persistence range; booleans remain
        distinct. DecisionReceipt revalidates all semantic cross-field rules.

    Raises:
        TypeError: If an object or scalar has the wrong portable payload type.
        ValueError: If keys, version, UUIDs, enums, JSON values, integer ranges,
            or DecisionReceipt semantic invariants are invalid.

    Non-goals:
        This function does not read PostgreSQL rows, interpret persistence
        envelopes, access a store, manage transactions, orchestrate or reconcile
        receipts, select policy, authorize retry, or process diagnostics/logs.
    """

    outer = _require_mapping(payload, "payload")
    _require_exact_keys(outer, _OUTER_KEYS, "payload")

    version = _require_int64(
        outer["receipt_serialization_version"],
        "payload.receipt_serialization_version",
    )
    if version != DECISION_RECEIPT_SERIALIZATION_VERSION:
        raise ValueError(
            "payload.receipt_serialization_version is unsupported; expected 1"
        )

    receipt_body = _require_mapping(outer["receipt"], "payload.receipt")
    _require_exact_keys(receipt_body, _RECEIPT_KEYS, "payload.receipt")

    subject_body = _require_nested_mapping(
        receipt_body,
        "subject",
        _SUBJECT_KEYS,
    )
    correlation_body = _require_nested_mapping(
        receipt_body,
        "correlation",
        _CORRELATION_KEYS,
    )
    actor_body = _require_nested_mapping(
        receipt_body,
        "actor",
        _ACTOR_KEYS,
    )
    cost_summary_body = _require_nested_mapping(
        receipt_body,
        "cost_summary",
        _COST_SUMMARY_KEYS,
    )
    flags_body = _require_nested_mapping(
        receipt_body,
        "flags",
        _FLAGS_KEYS,
    )

    admission_evidence = _deserialize_admission_evidence(
        receipt_body["admission_evidence"]
    )

    return DecisionReceipt(
        receipt_id=_deserialize_uuid(
            receipt_body["receipt_id"],
            "payload.receipt.receipt_id",
        ),
        outcome_id=_deserialize_uuid(
            receipt_body["outcome_id"],
            "payload.receipt.outcome_id",
        ),
        ok=_require_bool(receipt_body["ok"], "payload.receipt.ok"),
        boundary=_deserialize_enum(
            receipt_body["boundary"],
            SemanticBoundary,
            "payload.receipt.boundary",
        ),
        category=_deserialize_enum(
            receipt_body["category"],
            SemanticOutcomeCategory,
            "payload.receipt.category",
        ),
        semantic_code=_deserialize_enum(
            receipt_body["semantic_code"],
            SemanticOutcomeCode,
            "payload.receipt.semantic_code",
        ),
        severity=_deserialize_enum(
            receipt_body["severity"],
            SemanticSeverity,
            "payload.receipt.severity",
        ),
        risk_level=_deserialize_enum(
            receipt_body["risk_level"],
            SemanticRiskLevel,
            "payload.receipt.risk_level",
        ),
        reversibility=_deserialize_enum(
            receipt_body["reversibility"],
            SemanticReversibility,
            "payload.receipt.reversibility",
        ),
        reason=_require_string(
            receipt_body["reason"],
            "payload.receipt.reason",
        ),
        evidence_source=_deserialize_enum(
            receipt_body["evidence_source"],
            DecisionReceiptEvidenceSource,
            "payload.receipt.evidence_source",
        ),
        subject=DecisionReceiptSubject(
            subject_type=_deserialize_enum(
                subject_body["subject_type"],
                DecisionReceiptSubjectType,
                "payload.receipt.subject.subject_type",
            ),
            subject_id=_deserialize_optional_string(
                subject_body["subject_id"],
                "payload.receipt.subject.subject_id",
            ),
        ),
        correlation=DecisionReceiptCorrelation(
            order_id=_deserialize_optional_string(
                correlation_body["order_id"],
                "payload.receipt.correlation.order_id",
            ),
            request_id=_deserialize_optional_string(
                correlation_body["request_id"],
                "payload.receipt.correlation.request_id",
            ),
            candidate_event_id=_deserialize_optional_uuid(
                correlation_body["candidate_event_id"],
                "payload.receipt.correlation.candidate_event_id",
            ),
            accepted_event_id=_deserialize_optional_uuid(
                correlation_body["accepted_event_id"],
                "payload.receipt.correlation.accepted_event_id",
            ),
            snapshot_id=_deserialize_optional_uuid(
                correlation_body["snapshot_id"],
                "payload.receipt.correlation.snapshot_id",
            ),
            source_global_position=_deserialize_optional_int64(
                correlation_body["source_global_position"],
                "payload.receipt.correlation.source_global_position",
            ),
            identity_source=_deserialize_enum(
                correlation_body["identity_source"],
                DecisionReceiptIdentitySource,
                "payload.receipt.correlation.identity_source",
            ),
        ),
        actor=DecisionReceiptActor(
            actor_id=_deserialize_optional_string(
                actor_body["actor_id"],
                "payload.receipt.actor.actor_id",
            ),
            actor_role=_deserialize_optional_string(
                actor_body["actor_role"],
                "payload.receipt.actor.actor_role",
            ),
            runtime_role=_deserialize_optional_string(
                actor_body["runtime_role"],
                "payload.receipt.actor.runtime_role",
            ),
        ),
        cost_summary=DecisionReceiptCostSummary(
            elapsed_ms=_deserialize_optional_int64(
                cost_summary_body["elapsed_ms"],
                "payload.receipt.cost_summary.elapsed_ms",
            ),
            validation_elapsed_ms=_deserialize_optional_int64(
                cost_summary_body["validation_elapsed_ms"],
                "payload.receipt.cost_summary.validation_elapsed_ms",
            ),
            replay_elapsed_ms=_deserialize_optional_int64(
                cost_summary_body["replay_elapsed_ms"],
                "payload.receipt.cost_summary.replay_elapsed_ms",
            ),
            transaction_elapsed_ms=_deserialize_optional_int64(
                cost_summary_body["transaction_elapsed_ms"],
                "payload.receipt.cost_summary.transaction_elapsed_ms",
            ),
            lock_wait_ms=_deserialize_optional_int64(
                cost_summary_body["lock_wait_ms"],
                "payload.receipt.cost_summary.lock_wait_ms",
            ),
        ),
        flags=DecisionReceiptFlags(
            fallback_required=_deserialize_enum(
                flags_body["fallback_required"],
                DecisionReceiptFlagState,
                "payload.receipt.flags.fallback_required",
            ),
            rebuild_required=_deserialize_enum(
                flags_body["rebuild_required"],
                DecisionReceiptFlagState,
                "payload.receipt.flags.rebuild_required",
            ),
            operator_review_required=_deserialize_enum(
                flags_body["operator_review_required"],
                DecisionReceiptFlagState,
                "payload.receipt.flags.operator_review_required",
            ),
            retry_candidate=_deserialize_enum(
                flags_body["retry_candidate"],
                DecisionReceiptFlagState,
                "payload.receipt.flags.retry_candidate",
            ),
        ),
        admission_evidence=admission_evidence,
        evidence_summary=_detach_json_object(
            _require_mapping(
                receipt_body["evidence_summary"],
                "payload.receipt.evidence_summary",
            ),
            "payload.receipt.evidence_summary",
        ),
        metadata=_detach_json_object(
            _require_mapping(
                receipt_body["metadata"],
                "payload.receipt.metadata",
            ),
            "payload.receipt.metadata",
        ),
    )


def _serialize_optional_uuid(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _serialize_optional_int64(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    return _require_int64(value, field_name)


def _serialize_admission_evidence(
    evidence: DecisionReceiptAdmissionEvidence | None,
) -> JsonValue:
    if evidence is None:
        return None
    return cast(JsonValue, {"disposition": evidence.disposition.value})


def _deserialize_admission_evidence(
    value: object,
) -> DecisionReceiptAdmissionEvidence | None:
    if value is None:
        return None

    body = _require_mapping(value, "payload.receipt.admission_evidence")
    _require_exact_keys(
        body,
        _ADMISSION_EVIDENCE_KEYS,
        "payload.receipt.admission_evidence",
    )
    return DecisionReceiptAdmissionEvidence(
        disposition=_deserialize_enum(
            body["disposition"],
            EventAdmissionDisposition,
            "payload.receipt.admission_evidence.disposition",
        )
    )


def _require_nested_mapping(
    receipt_body: Mapping[str, object],
    field_name: str,
    expected_keys: frozenset[str],
) -> Mapping[str, object]:
    path = f"payload.receipt.{field_name}"
    body = _require_mapping(receipt_body[field_name], path)
    _require_exact_keys(body, expected_keys, path)
    return body


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return value


def _require_exact_keys(
    value: Mapping[str, object],
    expected_keys: frozenset[str],
    field_name: str,
) -> None:
    actual_keys: set[str] = set()
    for key in value:
        if type(key) is not str:
            raise TypeError(f"{field_name} keys must be strings")
        actual_keys.add(key)

    missing = sorted(expected_keys - actual_keys)
    unknown = sorted(actual_keys - expected_keys)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown keys: {', '.join(unknown)}")
        raise ValueError(f"{field_name} has invalid keys ({'; '.join(details)})")


def _require_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be bool")
    return value


def _require_string(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    return value


def _deserialize_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)


def _deserialize_uuid(value: object, field_name: str) -> UUID:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a UUID string")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid UUID string") from exc


def _deserialize_optional_uuid(value: object, field_name: str) -> UUID | None:
    if value is None:
        return None
    return _deserialize_uuid(value, field_name)


def _deserialize_enum(
    value: object,
    enum_type: type[_EnumT],
    field_name: str,
) -> _EnumT:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a {enum_type.__name__} value string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} has an unknown {enum_type.__name__} value"
        ) from exc


def _deserialize_optional_int64(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _require_int64(value, field_name)


def _require_int64(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be int, not bool or another type")
    if value < _SIGNED_64_BIT_MIN or value > _SIGNED_64_BIT_MAX:
        raise ValueError(f"{field_name} must fit the signed 64-bit range")
    return value


def _detach_json_object(
    value: Mapping[str, object],
    field_name: str,
) -> dict[str, JsonValue]:
    validated = ensure_json_object(value, field_name=field_name)
    return {
        key: _detach_json_value(item, f"{field_name}.{key}")
        for key, item in validated.items()
    }


def _detach_json_value(value: JsonValue, field_name: str) -> JsonValue:
    if value is None or type(value) is str or type(value) is bool:
        return value
    if type(value) is int:
        return _require_int64(value, field_name)
    if type(value) is float:
        # ensure_json_object already enforces finiteness before this copy.
        return value
    if isinstance(value, Mapping):
        return cast(
            JsonValue,
            {
                key: _detach_json_value(item, f"{field_name}.{key}")
                for key, item in value.items()
            },
        )
    if isinstance(value, tuple):
        # Mutable lists are the portable JSON representation. JsonValue's
        # runtime contract accepts sequences but models frozen values as tuples,
        # so the cast documents this intentionally detached output boundary.
        return cast(
            JsonValue,
            [
                _detach_json_value(item, f"{field_name}[{index}]")
                for index, item in enumerate(value)
            ],
        )
    raise TypeError(f"{field_name} must be JSON-safe")
