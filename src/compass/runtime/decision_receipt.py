from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from uuid import UUID

from src.compass.runtime.json_types import ensure_json_object
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)


class DecisionReceiptEvidenceSource(str, Enum):
    """
    Runtime evidence path that produced the receipt.

    This vocabulary identifies where receipt evidence came from. It describes
    the evidence path, not the technical status, semantic outcome, runtime
    action, execution strategy, retry policy, persistence state, or validator
    operation.
    """

    WRITE_SIDE_ADMISSION = "WRITE_SIDE_ADMISSION"
    READ_SIDE_PATH = "READ_SIDE_PATH"
    SNAPSHOT_TRUST_PATH = "SNAPSHOT_TRUST_PATH"
    SNAPSHOT_ASSISTED_PATH = "SNAPSHOT_ASSISTED_PATH"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    UNKNOWN = "UNKNOWN"


class DecisionReceiptSubjectType(str, Enum):
    """
    Subject family for the receipt.

    The subject identifies what the receipt is about. It is not itself proof of
    accepted-history authority.
    """

    ORDER = "ORDER"
    REQUEST = "REQUEST"
    CANDIDATE_EVENT = "CANDIDATE_EVENT"
    ACCEPTED_EVENT = "ACCEPTED_EVENT"
    SNAPSHOT = "SNAPSHOT"
    PROJECTION = "PROJECTION"
    RUNTIME = "RUNTIME"
    UNKNOWN = "UNKNOWN"


class DecisionReceiptIdentitySource(str, Enum):
    """
    Source of identity / lineage evidence carried by the receipt.

    This distinction prevents candidate-derived correlation evidence from being
    mistaken for accepted-history identity.
    """

    ACCEPTED_HISTORY = "ACCEPTED_HISTORY"
    CANDIDATE_EVENT_IDENTITY = "CANDIDATE_EVENT_IDENTITY"
    WRITE_SIDE_CORRELATION = "WRITE_SIDE_CORRELATION"
    READ_SIDE_OBSERVATION = "READ_SIDE_OBSERVATION"
    SNAPSHOT_LINEAGE = "SNAPSHOT_LINEAGE"
    CALLER_CONTEXT = "CALLER_CONTEXT"
    UNKNOWN = "UNKNOWN"


class EventAdmissionDisposition(str, Enum):
    """Typed admission fate for an event attempt."""

    ADMITTED_TO_ACCEPTED_HISTORY = "ADMITTED_TO_ACCEPTED_HISTORY"
    MATCHED_EXISTING_ACCEPTED_EVENT = "MATCHED_EXISTING_ACCEPTED_EVENT"
    SEMANTIC_ADMISSION_REJECTED = "SEMANTIC_ADMISSION_REJECTED"
    APPEND_CONCURRENCY_CONFLICT = "APPEND_CONCURRENCY_CONFLICT"
    COMMIT_OUTCOME_UNRESOLVED = "COMMIT_OUTCOME_UNRESOLVED"
    ADMISSION_NOT_REACHED = "ADMISSION_NOT_REACHED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DecisionReceiptSubject:
    """
    Entity or runtime object that the receipt is about.

    The subject is intentionally separate from correlation evidence. A receipt
    may be about a candidate, an accepted event, a snapshot, a projection, or a
    runtime condition without collapsing those identities into one authority.
    """

    subject_type: DecisionReceiptSubjectType
    subject_id: str | None = None

    def __post_init__(self) -> None:
        _require_enum(
            self.subject_type,
            DecisionReceiptSubjectType,
            "subject_type",
        )
        _require_optional_non_empty_string(self.subject_id, "subject_id")


@dataclass(frozen=True)
class DecisionReceiptCorrelation:
    """
    Queryable identity / lineage correlation carried by the receipt.

    These fields are evidence for review and future governance. They must not
    be interpreted as accepted-history authority unless identity_source says so.

    The identity_source field is the primary source for this correlation block.
    It is not field-level provenance. If a future adapter needs to distinguish
    candidate_event_id, accepted_event_id, request_id, snapshot_id, and
    source_global_position by separate authority sources, Stage 4B can extend
    this contract with field-level identity provenance.
    """

    order_id: str | None = None
    request_id: str | None = None
    candidate_event_id: UUID | None = None
    accepted_event_id: UUID | None = None
    snapshot_id: UUID | None = None
    source_global_position: int | None = None
    identity_source: DecisionReceiptIdentitySource = (
        DecisionReceiptIdentitySource.UNKNOWN
    )

    def __post_init__(self) -> None:
        _require_optional_non_empty_string(self.order_id, "order_id")
        _require_optional_non_empty_string(self.request_id, "request_id")
        _require_optional_uuid(self.candidate_event_id, "candidate_event_id")
        _require_optional_uuid(self.accepted_event_id, "accepted_event_id")
        _require_optional_uuid(self.snapshot_id, "snapshot_id")
        _require_optional_non_negative_int(
            self.source_global_position,
            "source_global_position",
        )
        _require_enum(
            self.identity_source,
            DecisionReceiptIdentitySource,
            "identity_source",
        )


@dataclass(frozen=True)
class DecisionReceiptAdmissionEvidence:
    """Typed evidence describing an event's write-side admission fate.

    Event identifiers remain owned by DecisionReceiptCorrelation. This avoids
    duplicating candidate_event_id and accepted_event_id in two contract
    objects and prevents conflicting identity evidence.
    """

    disposition: EventAdmissionDisposition = EventAdmissionDisposition.UNKNOWN

    def __post_init__(self) -> None:
        _require_enum(
            self.disposition,
            EventAdmissionDisposition,
            "disposition",
        )


@dataclass(frozen=True)
class DecisionReceiptActor:
    """
    Actor / runtime role evidence associated with the receipt.

    Actor metadata is receipt-safe evidence only. It is not database permission
    authority and does not execute governance decisions.
    """

    actor_id: str | None = None
    actor_role: str | None = None
    runtime_role: str | None = None

    def __post_init__(self) -> None:
        _require_optional_non_empty_string(self.actor_id, "actor_id")
        _require_optional_non_empty_string(self.actor_role, "actor_role")
        _require_optional_non_empty_string(self.runtime_role, "runtime_role")


@dataclass(frozen=True)
class DecisionReceiptCostSummary:
    """
    Compact cost evidence extension point.

    Stage 4B records only narrow summary cost evidence. Measurement matrix
    semantics, benchmark suites, LLM token accounting, path-specific cost
    buckets, and routing policy belong to later stages.

    This contract intentionally does not include a generic `extra` field.
    Future Stage 4B.2 may introduce explicit path-cost fields or a dedicated
    cost evidence breakdown contract once the vocabulary is defined.
    """

    elapsed_ms: int | None = None
    validation_elapsed_ms: int | None = None
    replay_elapsed_ms: int | None = None
    transaction_elapsed_ms: int | None = None
    lock_wait_ms: int | None = None

    def __post_init__(self) -> None:
        _require_optional_non_negative_int(self.elapsed_ms, "elapsed_ms")
        _require_optional_non_negative_int(
            self.validation_elapsed_ms,
            "validation_elapsed_ms",
        )
        _require_optional_non_negative_int(
            self.replay_elapsed_ms,
            "replay_elapsed_ms",
        )
        _require_optional_non_negative_int(
            self.transaction_elapsed_ms,
            "transaction_elapsed_ms",
        )
        _require_optional_non_negative_int(self.lock_wait_ms, "lock_wait_ms")


@dataclass(frozen=True)
class DecisionReceiptFlags:
    """
    Governance-relevant flags carried as evidence.

    These flags do not execute operator review, fallback, rebuild, or retry.
    Later runtime policy / strategy / retry governance layers may consume them.
    """

    fallback_required: bool = False
    rebuild_required: bool = False
    operator_review_required: bool = False
    retry_candidate: bool = False

    def __post_init__(self) -> None:
        _require_bool(self.fallback_required, "fallback_required")
        _require_bool(self.rebuild_required, "rebuild_required")
        _require_bool(
            self.operator_review_required,
            "operator_review_required",
        )
        _require_bool(self.retry_candidate, "retry_candidate")


@dataclass(frozen=True)
class DecisionReceipt:
    """
    Durable governance evidence contract for a SemanticOutcome.

    A DecisionReceipt preserves selected semantic governance evidence in a
    compact, reviewable, machine-readable shape.

    This object answers:
    - which semantic outcome was preserved?
    - which boundary produced or owns the semantic meaning?
    - which receipt-safe evidence supports the conclusion?
    - which identity / lineage correlation can be queried later?
    - what write-side admission fate was preserved, when applicable?
    - which summary flags may later policy consume?

    This object does NOT answer:
    - what runtime action should be executed?
    - which recovery path should be used?
    - which execution strategy is cheapest or healthiest?
    - whether retry is allowed?
    - whether the receipt has been persisted?
    - what detailed diagnostic trace was observed?
    """

    receipt_id: UUID
    outcome_id: UUID
    ok: bool
    boundary: SemanticBoundary
    category: SemanticOutcomeCategory
    semantic_code: SemanticOutcomeCode
    severity: SemanticSeverity
    risk_level: SemanticRiskLevel
    reversibility: SemanticReversibility
    reason: str
    evidence_source: DecisionReceiptEvidenceSource
    subject: DecisionReceiptSubject = field(
        default_factory=lambda: DecisionReceiptSubject(
            subject_type=DecisionReceiptSubjectType.UNKNOWN
        )
    )
    correlation: DecisionReceiptCorrelation = field(
        default_factory=DecisionReceiptCorrelation
    )
    actor: DecisionReceiptActor = field(default_factory=DecisionReceiptActor)
    cost_summary: DecisionReceiptCostSummary = field(
        default_factory=DecisionReceiptCostSummary
    )
    flags: DecisionReceiptFlags = field(default_factory=DecisionReceiptFlags)
    admission_evidence: DecisionReceiptAdmissionEvidence | None = None
    evidence_summary: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_uuid(self.receipt_id, "receipt_id")
        _require_uuid(self.outcome_id, "outcome_id")
        _require_bool(self.ok, "ok")
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
        _require_non_empty_string(self.reason, "reason")
        _require_enum(
            self.evidence_source,
            DecisionReceiptEvidenceSource,
            "evidence_source",
        )
        _require_type(self.subject, DecisionReceiptSubject, "subject")
        _require_type(
            self.correlation,
            DecisionReceiptCorrelation,
            "correlation",
        )
        _require_type(self.actor, DecisionReceiptActor, "actor")
        _require_type(
            self.cost_summary,
            DecisionReceiptCostSummary,
            "cost_summary",
        )
        _require_type(self.flags, DecisionReceiptFlags, "flags")

        if self.admission_evidence is not None:
            _require_type(
                self.admission_evidence,
                DecisionReceiptAdmissionEvidence,
                "admission_evidence",
            )
            _validate_admission_evidence(
                admission_evidence=self.admission_evidence,
                correlation=self.correlation,
            )

        object.__setattr__(
            self,
            "evidence_summary",
            ensure_json_object(
                self.evidence_summary,
                field_name="evidence_summary",
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            ensure_json_object(self.metadata, field_name="metadata"),
        )

    @property
    def is_valid(self) -> bool:
        return self.category == SemanticOutcomeCategory.VALID

    @property
    def requires_operator_review(self) -> bool:
        return self.flags.operator_review_required

    @property
    def requires_rebuild(self) -> bool:
        return self.flags.rebuild_required

    @property
    def requires_fallback(self) -> bool:
        return self.flags.fallback_required



def _validate_admission_evidence(
    *,
    admission_evidence: DecisionReceiptAdmissionEvidence,
    correlation: DecisionReceiptCorrelation,
) -> None:
    disposition = admission_evidence.disposition
    candidate_event_id = correlation.candidate_event_id
    accepted_event_id = correlation.accepted_event_id

    if disposition == EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY:
        if candidate_event_id is None:
            raise ValueError(
                "candidate_event_id is required when an event is admitted"
            )
        if accepted_event_id is None:
            raise ValueError(
                "accepted_event_id is required when an event is admitted"
            )
        if candidate_event_id != accepted_event_id:
            raise ValueError(
                "candidate_event_id and accepted_event_id must match when the "
                "same event identity is admitted to accepted history"
            )
        return

    if disposition == EventAdmissionDisposition.MATCHED_EXISTING_ACCEPTED_EVENT:
        if accepted_event_id is None:
            raise ValueError(
                "accepted_event_id is required for an idempotent replay match"
            )
        return

    if disposition in {
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.COMMIT_OUTCOME_UNRESOLVED,
    }:
        if candidate_event_id is None:
            raise ValueError(
                "candidate_event_id is required after a candidate event exists"
            )
        if accepted_event_id is not None:
            raise ValueError(
                "accepted_event_id must be None without authoritative "
                "accepted-history evidence"
            )
        return

    if disposition == EventAdmissionDisposition.ADMISSION_NOT_REACHED:
        if candidate_event_id is not None:
            raise ValueError(
                "candidate_event_id must be None when admission was not reached"
            )
        if accepted_event_id is not None:
            raise ValueError(
                "accepted_event_id must be None when admission was not reached"
            )
        return


def _require_uuid(value: object, field_name: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be UUID")


def _require_optional_uuid(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, UUID):
        raise TypeError(f"{field_name} must be UUID or None")


def _require_bool(value: object, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be bool")


def _require_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_optional_non_empty_string(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return
    _require_non_empty_string(value, field_name)


def _require_optional_non_negative_int(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be int or None")

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


def _require_type(value: object, expected_type: type[object], field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be {expected_type.__name__}")