from __future__ import annotations

from typing import Mapping
from uuid import UUID

from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptAdmissionEvidence,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlags,
    DecisionReceiptSubject,
    DecisionReceiptSubjectType,
)
from src.compass.runtime.semantic_outcome import SemanticOutcome


def map_semantic_outcome_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome: SemanticOutcome,
    evidence_source: DecisionReceiptEvidenceSource,
    subject: DecisionReceiptSubject | None = None,
    correlation: DecisionReceiptCorrelation | None = None,
    actor: DecisionReceiptActor | None = None,
    cost_summary: DecisionReceiptCostSummary | None = None,
    flags: DecisionReceiptFlags | None = None,
    admission_evidence: DecisionReceiptAdmissionEvidence | None = None,
    evidence_summary: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> DecisionReceipt:
    """
    Construct a DecisionReceipt from an existing SemanticOutcome.

    This mapper preserves the complete typed semantic tuple without performing
    another semantic interpretation.

    Receipt identity, evidence-path ownership, supporting contracts, and
    receipt-safe flexible evidence must be supplied explicitly by the caller or
    by later producer-specific adapters.

    Invariants:

    - SemanticOutcome.context and SemanticOutcome.evidence are never inspected
      or copied.
    - The typed semantic tuple is preserved one-to-one without remapping.
    - Supporting-contract type checks and JSON-safety validation are delegated
      to the DecisionReceipt contract.

    This mapper intentionally does not:

    - infer evidence source, subject, correlation, or identity provenance;
    - infer admission disposition or governance flags;
    - authorize retry, fallback, rebuild, or operator review;
    - serialize or persist the receipt.
    """

    return DecisionReceipt(
        receipt_id=receipt_id,
        outcome_id=outcome.outcome_id,
        ok=outcome.ok,
        boundary=outcome.boundary,
        category=outcome.category,
        semantic_code=outcome.semantic_code,
        severity=outcome.severity,
        risk_level=outcome.risk_level,
        reversibility=outcome.reversibility,
        reason=outcome.reason,
        evidence_source=evidence_source,
        subject=(
            subject
            if subject is not None
            else DecisionReceiptSubject(
                subject_type=DecisionReceiptSubjectType.UNKNOWN
            )
        ),
        correlation=(
            correlation
            if correlation is not None
            else DecisionReceiptCorrelation()
        ),
        actor=actor if actor is not None else DecisionReceiptActor(),
        cost_summary=(
            cost_summary
            if cost_summary is not None
            else DecisionReceiptCostSummary()
        ),
        flags=flags if flags is not None else DecisionReceiptFlags(),
        admission_evidence=admission_evidence,
        evidence_summary=(
            evidence_summary if evidence_summary is not None else {}
        ),
        metadata=metadata if metadata is not None else {},
    )