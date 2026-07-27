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
    """
    Typed governance evidence for an event attempt's admission fate.

    Admission fate is distinct from technical status and executes no runtime
    action. Candidate construction is also distinct from reaching candidate-
    level append admission: a pre-transaction path may construct a candidate
    before stream preparation prevents append_if_admitted(...) from being
    invoked.

    For an idempotency conflict, an accepted event identifies the prior
    accepted record that proves the conflict; it does not mean the current
    attempt was accepted. APPEND_TECHNICAL_FAILURE records a known technical
    append failure with no accepted event, while COMMIT_OUTCOME_UNRESOLVED
    remains reserved for an ambiguous commit result. A technical status such
    as LOCK_TIMEOUT does not by itself select APPEND_CONCURRENCY_CONFLICT.

    APPEND_ADMISSION_NOT_REACHED means append_if_admitted(...) was not invoked
    and no event from the current attempt entered accepted history. Its
    candidate identity is optional: preferred in-transaction pessimistic
    preparation rejects before candidate construction, while an explicitly
    selected non-default or custom composition may construct a candidate
    before prepare_stream(...) rejects. The disposition does not claim that
    idempotency, history loading, Compass validation, or stream preparation
    was skipped.
    """

    ADMITTED_TO_ACCEPTED_HISTORY = "ADMITTED_TO_ACCEPTED_HISTORY"
    MATCHED_EXISTING_ACCEPTED_EVENT = "MATCHED_EXISTING_ACCEPTED_EVENT"
    IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY = (
        "IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY"
    )
    SEMANTIC_ADMISSION_REJECTED = "SEMANTIC_ADMISSION_REJECTED"
    APPEND_CONCURRENCY_CONFLICT = "APPEND_CONCURRENCY_CONFLICT"
    APPEND_TECHNICAL_FAILURE = "APPEND_TECHNICAL_FAILURE"
    COMMIT_OUTCOME_UNRESOLVED = "COMMIT_OUTCOME_UNRESOLVED"
    APPEND_ADMISSION_NOT_REACHED = "APPEND_ADMISSION_NOT_REACHED"
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
    """Typed governance evidence describing write-side admission fate.

    Event identifiers remain owned by DecisionReceiptCorrelation. This avoids
    duplicating candidate_event_id and accepted_event_id in two contract
    objects and prevents conflicting identity evidence.

    Admission evidence is distinct from technical status, semantic outcome,
    and runtime action. It records what happened at the admission lifecycle
    boundary but does not execute recovery, retry, or any other action.
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


class DecisionReceiptFlagState(str, Enum):
    """
    Durable evaluation state for one DecisionReceipt flag proposition.

    TRUE and FALSE are completed, producer-owned evidence assertions.
    NOT_EVALUATED means the receipt contains no completed evaluation for the
    proposition. It is not a negative assertion and must not be treated as
    FALSE.

    The enum records governance evidence only. It does not authorize or execute
    fallback, rebuild, operator review, or retry.
    """

    TRUE = "TRUE"
    FALSE = "FALSE"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class DecisionReceiptFlags:
    """
    Producer-owned evaluation states carried as governance evidence.

    TRUE and FALSE require a completed evaluation by the evidence owner.
    NOT_EVALUATED is the default and preserves the absence of a completed
    evaluation without making an implicit negative assertion.

    These states do not execute operator review, fallback, rebuild, or retry.
    They do not authorize retry. Later policy, strategy, and retry-governance
    layers may consume them without treating NOT_EVALUATED as FALSE.
    """

    fallback_required: DecisionReceiptFlagState = (
        DecisionReceiptFlagState.NOT_EVALUATED
    )
    rebuild_required: DecisionReceiptFlagState = (
        DecisionReceiptFlagState.NOT_EVALUATED
    )
    operator_review_required: DecisionReceiptFlagState = (
        DecisionReceiptFlagState.NOT_EVALUATED
    )
    retry_candidate: DecisionReceiptFlagState = (
        DecisionReceiptFlagState.NOT_EVALUATED
    )

    def __post_init__(self) -> None:
        _require_enum(
            self.fallback_required,
            DecisionReceiptFlagState,
            "fallback_required",
        )
        _require_enum(
            self.rebuild_required,
            DecisionReceiptFlagState,
            "rebuild_required",
        )
        _require_enum(
            self.operator_review_required,
            DecisionReceiptFlagState,
            "operator_review_required",
        )
        _require_enum(
            self.retry_candidate,
            DecisionReceiptFlagState,
            "retry_candidate",
        )


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

    if (
        disposition
        == EventAdmissionDisposition.IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
    ):
        # This accepted ID belongs to the prior idempotency record. A current
        # candidate may exist, but its identity need not match the prior event.
        if accepted_event_id is None:
            raise ValueError(
                "accepted_event_id is required for an idempotency conflict "
                "with accepted history"
            )
        return

    if disposition in {
        EventAdmissionDisposition.SEMANTIC_ADMISSION_REJECTED,
        EventAdmissionDisposition.APPEND_CONCURRENCY_CONFLICT,
        EventAdmissionDisposition.APPEND_TECHNICAL_FAILURE,
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

    if disposition == EventAdmissionDisposition.APPEND_ADMISSION_NOT_REACHED:
        # Candidate construction may precede a rejecting prepare_stream(...)
        # call, so candidate presence does not prove append_if_admitted(...)
        # was invoked.
        if accepted_event_id is not None:
            raise ValueError(
                "accepted_event_id must be None when append admission was "
                "not reached"
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
