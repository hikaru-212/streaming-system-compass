from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from decimal import Decimal
from inspect import Parameter, signature
from typing import cast
from uuid import UUID

import pytest

import src.compass.runtime.read_side_decision_receipt_mapping as mapping_module
from src.compass.runtime.decision_receipt import (
    DecisionReceipt,
    DecisionReceiptActor,
    DecisionReceiptCorrelation,
    DecisionReceiptCostSummary,
    DecisionReceiptEvidenceSource,
    DecisionReceiptFlags,
    DecisionReceiptIdentitySource,
    DecisionReceiptSubjectType,
)
from src.compass.runtime.read_side_decision_receipt_mapping import (
    map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
    map_projection_snapshot_replay_validation_result_to_decision_receipt,
    map_replay_validation_result_to_decision_receipt,
)
from src.compass.runtime.semantic_outcome import (
    SemanticBoundary,
    SemanticOutcome,
    SemanticOutcomeCategory,
    SemanticOutcomeCode,
    SemanticReversibility,
    SemanticRiskLevel,
    SemanticSeverity,
)
from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)
from src.pipeline.projection.projection_snapshot_replay_validator import (
    ProjectionSnapshotReplayValidationResult,
    ProjectionSnapshotReplayValidationStatus,
)
from src.pipeline.projection.replay_validator import (
    ReplayValidationResult,
    ReplayValidationStatus,
)
from src.storage.postgres_projection_snapshot_store import ProjectionSnapshot


RECEIPT_ID = UUID("00000000-0000-0000-0000-000000000501")
OUTCOME_ID = UUID("00000000-0000-0000-0000-000000000502")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000503")
SECOND_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000504")
ORDER_ID = "order-001"


def make_order_state(
    *,
    status: OrderStatus = OrderStatus.CREATED,
    paid_amount: Decimal = Decimal("0.00"),
    version: int = 1,
) -> OrderState:
    return OrderState(
        order_id=ORDER_ID,
        status=status,
        total_amount=Decimal("100.00"),
        paid_amount=paid_amount,
        version=version,
    )


CREATED_STATE = make_order_state()
PAID_STATE = make_order_state(
    status=OrderStatus.PAID,
    paid_amount=Decimal("100.00"),
    version=2,
)
OTHER_ORDER_STATE = OrderState(
    order_id="order-002",
    status=OrderStatus.CREATED,
    total_amount=Decimal("100.00"),
    paid_amount=Decimal("0.00"),
    version=1,
)


@dataclass(frozen=True)
class ExpectedReceipt:
    ok: bool
    boundary: SemanticBoundary
    category: SemanticOutcomeCategory
    semantic_code: SemanticOutcomeCode
    severity: SemanticSeverity
    risk_level: SemanticRiskLevel
    reversibility: SemanticReversibility
    reason: str
    evidence_source: DecisionReceiptEvidenceSource
    subject_type: DecisionReceiptSubjectType
    subject_id: str | None
    order_id: str
    snapshot_id: UUID | None
    source_global_position: int | None
    identity_source: DecisionReceiptIdentitySource
    flags: DecisionReceiptFlags
    evidence_summary: dict[str, object]


def assert_receipt(
    receipt: DecisionReceipt,
    expected: ExpectedReceipt,
) -> None:
    assert receipt.receipt_id == RECEIPT_ID
    assert receipt.outcome_id == OUTCOME_ID
    assert receipt.ok is expected.ok
    assert receipt.boundary == expected.boundary
    assert receipt.category == expected.category
    assert receipt.semantic_code == expected.semantic_code
    assert receipt.severity == expected.severity
    assert receipt.risk_level == expected.risk_level
    assert receipt.reversibility == expected.reversibility
    assert receipt.reason == expected.reason
    assert receipt.evidence_source == expected.evidence_source
    assert receipt.subject.subject_type == expected.subject_type
    assert receipt.subject.subject_id == expected.subject_id
    assert receipt.correlation == DecisionReceiptCorrelation(
        order_id=expected.order_id,
        snapshot_id=expected.snapshot_id,
        source_global_position=expected.source_global_position,
        identity_source=expected.identity_source,
    )
    assert receipt.correlation.request_id is None
    assert receipt.correlation.candidate_event_id is None
    assert receipt.correlation.accepted_event_id is None
    assert receipt.flags == expected.flags
    assert receipt.flags == DecisionReceiptFlags()
    assert set(receipt.evidence_summary) == set(expected.evidence_summary)
    assert receipt.evidence_summary == expected.evidence_summary
    assert receipt.metadata == {}
    assert receipt.actor == DecisionReceiptActor()
    assert receipt.cost_summary == DecisionReceiptCostSummary()
    assert receipt.admission_evidence is None


# These fixtures mirror constructable producer results. They define only the
# approved PR5 receipt mappings and do not establish broader policy rules.
REPLAY_CASES = [
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MATCH,
            expected_state=CREATED_STATE,
            persisted_state=CREATED_STATE,
            reason="Projection matches accepted-history replay.",
        ),
        ExpectedReceipt(
            ok=True,
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            category=SemanticOutcomeCategory.VALID,
            semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
            severity=SemanticSeverity.INFO,
            risk_level=SemanticRiskLevel.LOW,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Projection matches accepted-history replay.",
            evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "MATCH",
                "expected_state_present": True,
                "persisted_state_present": True,
            },
        ),
        id="match",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MISSING_PROJECTION,
            expected_state=CREATED_STATE,
            persisted_state=None,
            reason="Projection is missing.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            category=SemanticOutcomeCategory.REBUILD_REQUIRED,
            semantic_code=SemanticOutcomeCode.REQUIRES_REBUILD,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.MEDIUM,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="Projection is missing.",
            evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "MISSING_PROJECTION",
                "expected_state_present": True,
                "persisted_state_present": False,
            },
        ),
        id="missing-projection",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.DRIFT,
            expected_state=PAID_STATE,
            persisted_state=CREATED_STATE,
            reason="Projection differs from accepted-history replay.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            category=SemanticOutcomeCategory.DRIFT,
            semantic_code=SemanticOutcomeCode.DRIFT_DETECTED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="Projection differs from accepted-history replay.",
            evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "DRIFT",
                "expected_state_present": True,
                "persisted_state_present": True,
            },
        ),
        id="drift",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
            expected_state=None,
            persisted_state=CREATED_STATE,
            reason="No accepted history exists for order.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            category=SemanticOutcomeCategory.UNRESOLVED,
            semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.UNKNOWN,
            reversibility=SemanticReversibility.UNKNOWN,
            reason="No accepted history exists for order.",
            evidence_source=DecisionReceiptEvidenceSource.READ_SIDE_PATH,
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "NO_ACCEPTED_HISTORY",
                "expected_state_present": False,
                "persisted_state_present": True,
            },
        ),
        id="no-accepted-history-with-persisted-projection",
    ),
]


@pytest.mark.parametrize(("result", "expected"), REPLAY_CASES)
def test_replay_status_mapping(
    result: ReplayValidationResult,
    expected: ExpectedReceipt,
) -> None:
    receipt = map_replay_validation_result_to_decision_receipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert_receipt(receipt, expected)


def test_no_accepted_history_without_persisted_projection_is_mappable() -> None:
    result = ReplayValidationResult(
        order_id=ORDER_ID,
        status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
        expected_state=None,
        persisted_state=None,
        reason="No accepted history or persisted projection exists for order.",
    )

    receipt = map_replay_validation_result_to_decision_receipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.ORDER
    assert receipt.subject.subject_id == ORDER_ID
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION
    )
    assert receipt.evidence_summary == {
        "technical_status": "NO_ACCEPTED_HISTORY",
        "expected_state_present": False,
        "persisted_state_present": False,
    }
    assert receipt.flags == DecisionReceiptFlags()


SNAPSHOT_REPLAY_CASES = [
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MATCH,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=PAID_STATE,
            authority_state=PAID_STATE,
            reason="Snapshot-assisted replay matches authority.",
        ),
        ExpectedReceipt(
            ok=True,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.VALID,
            semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
            severity=SemanticSeverity.INFO,
            risk_level=SemanticRiskLevel.LOW,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Snapshot-assisted replay matches authority.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(SNAPSHOT_ID),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "MATCH",
                "snapshot_artifact_present": True,
                "snapshot_assisted_state_present": True,
                "authority_state_present": True,
            },
        ),
        id="match",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            snapshot_assisted_state=None,
            authority_state=CREATED_STATE,
            reason="Projection snapshot is missing.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
            semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.MEDIUM,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Projection snapshot is missing.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=None,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "MISSING_SNAPSHOT",
                "snapshot_artifact_present": False,
                "snapshot_assisted_state_present": False,
                "authority_state_present": True,
            },
        ),
        id="missing-snapshot",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .INVALID_SNAPSHOT_BOUNDARY
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=None,
            authority_state=CREATED_STATE,
            reason="Snapshot boundary is invalid.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNTRUSTED,
            semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="Snapshot boundary is invalid.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(SNAPSHOT_ID),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "INVALID_SNAPSHOT_BOUNDARY",
                "snapshot_artifact_present": True,
                "snapshot_assisted_state_present": False,
                "authority_state_present": True,
            },
        ),
        id="invalid-snapshot-boundary",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=PAID_STATE,
            reason="Snapshot tail violated the order-local source contract.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNRESOLVED,
            semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.UNKNOWN,
            reason="Snapshot tail violated the order-local source contract.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.RUNTIME,
            subject_id=None,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION",
                "snapshot_artifact_present": True,
                "snapshot_assisted_state_present": True,
                "authority_state_present": True,
            },
        ),
        id="tail-source-contract-violation",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .SNAPSHOT_ASSISTED_DRIFT
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=PAID_STATE,
            reason="Snapshot-assisted replay differs from authority.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.DRIFT,
            semantic_code=SemanticOutcomeCode.DRIFT_DETECTED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="Snapshot-assisted replay differs from authority.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "SNAPSHOT_ASSISTED_DRIFT",
                "snapshot_artifact_present": True,
                "snapshot_assisted_state_present": True,
                "authority_state_present": True,
            },
        ),
        id="snapshot-assisted-drift",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .NO_ACCEPTED_HISTORY_FOR_ORDER
            ),
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            snapshot_assisted_state=None,
            authority_state=None,
            reason="No accepted history exists for order.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNRESOLVED,
            semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.UNKNOWN,
            reversibility=SemanticReversibility.UNKNOWN,
            reason="No accepted history exists for order.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_TRUST_PATH,
            subject_type=DecisionReceiptSubjectType.ORDER,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "NO_ACCEPTED_HISTORY_FOR_ORDER",
                "snapshot_artifact_present": False,
                "snapshot_assisted_state_present": False,
                "authority_state_present": False,
            },
        ),
        id="no-accepted-history-without-snapshot",
    ),
]


@pytest.mark.parametrize(("result", "expected"), SNAPSHOT_REPLAY_CASES)
def test_snapshot_replay_status_mapping(
    result: ProjectionSnapshotReplayValidationResult,
    expected: ExpectedReceipt,
) -> None:
    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert_receipt(receipt, expected)


def test_snapshot_replay_reducer_failure_accepts_equal_exposed_states() -> None:
    # This shape mirrors the producer's reducer-failure drift branch: a
    # first-tail-event failure leaves the hydrated state equal to authority.
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus.SNAPSHOT_ASSISTED_DRIFT
        ),
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        snapshot_assisted_state=CREATED_STATE,
        authority_state=CREATED_STATE,
        reason="Snapshot-assisted tail replay failed.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert (
        receipt.ok,
        receipt.boundary,
        receipt.category,
        receipt.semantic_code,
        receipt.severity,
        receipt.risk_level,
        receipt.reversibility,
    ) == (
        False,
        SemanticBoundary.SNAPSHOT_TRUST,
        SemanticOutcomeCategory.DRIFT,
        SemanticOutcomeCode.DRIFT_DETECTED,
        SemanticSeverity.ERROR,
        SemanticRiskLevel.HIGH,
        SemanticReversibility.REBUILDABLE,
    )
    assert receipt.evidence_summary == {
        "technical_status": "SNAPSHOT_ASSISTED_DRIFT",
        "snapshot_artifact_present": True,
        "snapshot_assisted_state_present": True,
        "authority_state_present": True,
    }


def test_snapshot_tail_contract_violation_accepts_equal_exposed_states() -> None:
    # A different-order record or non-contiguous local sequence can violate
    # the producer tail contract before either exposed state diverges.
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
        ),
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        snapshot_assisted_state=CREATED_STATE,
        authority_state=CREATED_STATE,
        reason="Snapshot tail violated the order-local source contract.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.RUNTIME
    assert receipt.subject.subject_id is None
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
    )
    assert (
        receipt.category,
        receipt.semantic_code,
    ) == (
        SemanticOutcomeCategory.UNRESOLVED,
        SemanticOutcomeCode.RUNTIME_UNRESOLVED,
    )
    assert receipt.flags == DecisionReceiptFlags()


@pytest.mark.parametrize(
    ("mapper", "result"),
    [
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .INVALID_SNAPSHOT_BOUNDARY
                ),
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                snapshot_assisted_state=None,
                authority_state=CREATED_STATE,
                reason="Snapshot source position is not positive.",
            ),
            id="snapshot-trust-invalid-boundary",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .INVALID_SNAPSHOT_COMPATIBILITY
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                resolved_state=None,
                reason="Snapshot source position is not positive.",
            ),
            id="snapshot-assisted-invalid-compatibility",
        ),
    ],
)
def test_invalid_loaded_snapshot_can_preserve_zero_source_global_position(
    mapper: Callable[..., DecisionReceipt],
    result: object,
) -> None:
    receipt = mapper(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert receipt.correlation.snapshot_id == SNAPSHOT_ID
    assert receipt.correlation.source_global_position == 0
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
    )
    assert receipt.evidence_summary["snapshot_artifact_present"] is True


@pytest.mark.parametrize(
    ("mapper", "result"),
    [
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MATCH,
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                snapshot_assisted_state=CREATED_STATE,
                authority_state=CREATED_STATE,
                reason="Snapshot-assisted state matches authority state.",
            ),
            id="snapshot-replay-match",
        ),
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
                ),
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                snapshot_assisted_state=CREATED_STATE,
                authority_state=CREATED_STATE,
                reason=(
                    "Snapshot tail violated the order-local source contract."
                ),
            ),
            id="snapshot-replay-tail-source-contract-violation",
        ),
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus
                    .SNAPSHOT_ASSISTED_DRIFT
                ),
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                snapshot_assisted_state=CREATED_STATE,
                authority_state=PAID_STATE,
                reason="Snapshot-assisted state drifted from authority state.",
            ),
            id="snapshot-replay-snapshot-assisted-drift",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                resolved_state=CREATED_STATE,
                reason="Projection state resolved from snapshot.",
            ),
            id="snapshot-assisted-resolved-from-snapshot",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                resolved_state=None,
                reason=(
                    "Snapshot-assisted tail violated the order-local source "
                    "contract."
                ),
            ),
            id="snapshot-assisted-tail-source-contract-violation",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .TAIL_REPLAY_FAILED
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=0,
                resolved_state=None,
                reason="Snapshot-assisted tail replay failed.",
            ),
            id="snapshot-assisted-tail-replay-failed",
        ),
    ],
)
def test_post_validation_snapshot_status_rejects_zero_source_position(
    mapper: Callable[..., DecisionReceipt],
    result: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires source_global_position > 0",
    ):
        mapper(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


@pytest.mark.parametrize(
    ("source_global_position", "error_type", "message"),
    [
        pytest.param(
            -1,
            ValueError,
            "source_global_position must be non-negative",
            id="negative",
        ),
        pytest.param(
            cast(int, True),
            TypeError,
            "source_global_position must be int or None",
            id="bool",
        ),
    ],
)
def test_loaded_snapshot_source_position_uses_shared_contract_validation(
    source_global_position: int,
    error_type: type[Exception],
    message: str,
) -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .INVALID_SNAPSHOT_BOUNDARY
        ),
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=source_global_position,
        snapshot_assisted_state=None,
        authority_state=CREATED_STATE,
        reason="Snapshot boundary is invalid.",
    )

    with pytest.raises(error_type, match=message):
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_source_global_position_is_preserved_only_as_snapshot_lineage() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .INVALID_SNAPSHOT_BOUNDARY
        ),
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=23,
        snapshot_assisted_state=None,
        authority_state=CREATED_STATE,
        reason="Snapshot boundary is invalid.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert receipt.correlation.source_global_position == 23
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
    )
    assert receipt.evidence_summary == {
        "technical_status": "INVALID_SNAPSHOT_BOUNDARY",
        "snapshot_artifact_present": True,
        "snapshot_assisted_state_present": False,
        "authority_state_present": True,
    }
    assert "source_global_position" not in receipt.evidence_summary
    assert "source_global_position" not in receipt.metadata
    assert receipt.category == SemanticOutcomeCategory.UNTRUSTED
    assert receipt.semantic_code == SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED
    assert receipt.flags == DecisionReceiptFlags()


def test_snapshot_match_remains_neutral_evidence() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MATCH,
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        snapshot_assisted_state=PAID_STATE,
        authority_state=PAID_STATE,
        reason="Snapshot-assisted replay matches authority.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )
    receipt_field_names = {field.name for field in fields(receipt)}

    assert receipt.flags == DecisionReceiptFlags()
    assert receipt.admission_evidence is None
    assert receipt_field_names.isdisjoint(
        {"runtime_action", "policy", "strategy"}
    )


def test_snapshot_no_history_with_loaded_lineage_uses_snapshot_lineage() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=(
            ProjectionSnapshotReplayValidationStatus
            .NO_ACCEPTED_HISTORY_FOR_ORDER
        ),
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        snapshot_assisted_state=None,
        authority_state=None,
        reason="No accepted history exists for order.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert receipt.subject.subject_type == DecisionReceiptSubjectType.ORDER
    assert receipt.subject.subject_id == ORDER_ID
    assert receipt.correlation.snapshot_id == SNAPSHOT_ID
    assert receipt.correlation.source_global_position == 10
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE
    )
    assert receipt.evidence_summary["snapshot_artifact_present"] is True


SNAPSHOT_ASSISTED_CASES = [
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .RESOLVED_FROM_SNAPSHOT
            ),
            resolved_state=PAID_STATE,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            reason="Projection resolved from snapshot and tail.",
        ),
        ExpectedReceipt(
            ok=True,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.VALID,
            semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
            severity=SemanticSeverity.INFO,
            risk_level=SemanticRiskLevel.LOW,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Projection resolved from snapshot and tail.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.PROJECTION,
            subject_id=ORDER_ID,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "RESOLVED_FROM_SNAPSHOT",
                "snapshot_artifact_present": True,
                "resolved_state_present": True,
            },
        ),
        id="resolved-from-snapshot",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
            resolved_state=None,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=None,
            reason="Requested snapshot was not found.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
            semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.MEDIUM,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Requested snapshot was not found.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(SNAPSHOT_ID),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "MISSING_SNAPSHOT",
                "snapshot_artifact_present": False,
                "resolved_state_present": False,
            },
        ),
        id="missing-snapshot-request-reference",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .INVALID_SNAPSHOT_PRECONDITION
            ),
            resolved_state=None,
            snapshot_id=None,
            source_global_position=None,
            reason="trusted_snapshot_id is required.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNTRUSTED,
            semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="trusted_snapshot_id is required.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.RUNTIME,
            subject_id=None,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            identity_source=DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "INVALID_SNAPSHOT_PRECONDITION",
                "snapshot_artifact_present": False,
                "resolved_state_present": False,
            },
        ),
        id="invalid-snapshot-precondition",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .INVALID_SNAPSHOT_COMPATIBILITY
            ),
            resolved_state=None,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            reason="Snapshot is incompatible with the resolver.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNTRUSTED,
            semantic_code=SemanticOutcomeCode.DERIVED_STATE_UNTRUSTED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.REBUILDABLE,
            reason="Snapshot is incompatible with the resolver.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.SNAPSHOT,
            subject_id=str(SNAPSHOT_ID),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "INVALID_SNAPSHOT_COMPATIBILITY",
                "snapshot_artifact_present": True,
                "resolved_state_present": False,
            },
        ),
        id="invalid-snapshot-compatibility",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
            ),
            resolved_state=None,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            reason=(
                "Snapshot-assisted tail violated the order-local source "
                "contract."
            ),
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.UNRESOLVED,
            semantic_code=SemanticOutcomeCode.RUNTIME_UNRESOLVED,
            severity=SemanticSeverity.ERROR,
            risk_level=SemanticRiskLevel.HIGH,
            reversibility=SemanticReversibility.UNKNOWN,
            reason=(
                "Snapshot-assisted tail violated the order-local source "
                "contract."
            ),
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.RUNTIME,
            subject_id=None,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION",
                "snapshot_artifact_present": True,
                "resolved_state_present": False,
            },
        ),
        id="tail-source-contract-violation",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
            resolved_state=None,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            reason="Snapshot-assisted tail replay failed.",
        ),
        ExpectedReceipt(
            ok=False,
            boundary=SemanticBoundary.SNAPSHOT_TRUST,
            category=SemanticOutcomeCategory.FALLBACK_REQUIRED,
            semantic_code=SemanticOutcomeCode.FAST_PATH_UNAVAILABLE,
            severity=SemanticSeverity.WARNING,
            risk_level=SemanticRiskLevel.MEDIUM,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason="Snapshot-assisted tail replay failed.",
            evidence_source=DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH,
            subject_type=DecisionReceiptSubjectType.RUNTIME,
            subject_id=None,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            identity_source=DecisionReceiptIdentitySource.SNAPSHOT_LINEAGE,
            flags=DecisionReceiptFlags(),
            evidence_summary={
                "technical_status": "TAIL_REPLAY_FAILED",
                "snapshot_artifact_present": True,
                "resolved_state_present": False,
            },
        ),
        id="tail-replay-failed",
    ),
]


@pytest.mark.parametrize(("result", "expected"), SNAPSHOT_ASSISTED_CASES)
def test_snapshot_assisted_status_mapping(
    result: ProjectionSnapshotAssistedResolutionResult,
    expected: ExpectedReceipt,
) -> None:
    receipt = (
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert_receipt(receipt, expected)


def test_resolved_from_snapshot_remains_neutral_evidence() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id=ORDER_ID,
        status=(
            ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
        ),
        resolved_state=PAID_STATE,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        reason="Projection resolved from snapshot and order-local tail.",
    )

    receipt = (
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )
    receipt_field_names = {field.name for field in fields(receipt)}

    assert receipt.flags == DecisionReceiptFlags()
    assert receipt.admission_evidence is None
    assert (
        receipt.evidence_source
        == DecisionReceiptEvidenceSource.SNAPSHOT_ASSISTED_PATH
    )
    assert receipt.subject.subject_type == DecisionReceiptSubjectType.PROJECTION
    assert receipt.subject.subject_id == ORDER_ID
    assert receipt_field_names.isdisjoint(
        {"runtime_action", "policy", "strategy"}
    )


def test_status_case_ownership_tracks_every_current_producer_status() -> None:
    assert {
        cast(ReplayValidationResult, parameter.values[0]).status
        for parameter in REPLAY_CASES
    } == set(ReplayValidationStatus)
    assert {
        cast(
            ProjectionSnapshotReplayValidationResult,
            parameter.values[0],
        ).status
        for parameter in SNAPSHOT_REPLAY_CASES
    } == set(ProjectionSnapshotReplayValidationStatus)
    assert {
        cast(
            ProjectionSnapshotAssistedResolutionResult,
            parameter.values[0],
        ).status
        for parameter in SNAPSHOT_ASSISTED_CASES
    } == set(ProjectionSnapshotAssistedResolutionStatus)


def test_mapped_producer_result_field_ownership_is_explicit() -> None:
    assert {field.name for field in fields(ReplayValidationResult)} == {
        "order_id",
        "status",
        "expected_state",
        "persisted_state",
        "reason",
    }
    assert {
        field.name for field in fields(ProjectionSnapshotReplayValidationResult)
    } == {
        "status",
        "order_id",
        "snapshot_id",
        "source_global_position",
        "snapshot_assisted_state",
        "authority_state",
        "reason",
    }
    assert {
        field.name
        for field in fields(ProjectionSnapshotAssistedResolutionResult)
    } == {
        "order_id",
        "status",
        "resolved_state",
        "snapshot_id",
        "source_global_position",
        "reason",
    }

    unowned_fields = {
        "source_event_id",
        "source_event_sequence",
        "projection_name",
        "projection_epoch",
    }
    for result_type in (
        ReplayValidationResult,
        ProjectionSnapshotReplayValidationResult,
        ProjectionSnapshotAssistedResolutionResult,
    ):
        assert {
            field.name for field in fields(result_type)
        }.isdisjoint(unowned_fields)


def test_public_wrapper_signatures_are_narrow_and_keyword_only() -> None:
    wrappers = (
        map_replay_validation_result_to_decision_receipt,
        map_projection_snapshot_replay_validation_result_to_decision_receipt,
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
    )

    for wrapper in wrappers:
        parameters = signature(wrapper).parameters
        assert tuple(parameters) == ("receipt_id", "outcome_id", "result")
        assert all(
            parameter.kind == Parameter.KEYWORD_ONLY
            for parameter in parameters.values()
        )


def test_receipt_summary_is_reconstructed_without_outcome_payload_copying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = ReplayValidationResult(
        order_id=ORDER_ID,
        status=ReplayValidationStatus.MATCH,
        expected_state=CREATED_STATE,
        persisted_state=CREATED_STATE,
        reason="Projection matches.",
    )

    def fake_stage_4a_adapter(
        *,
        outcome_id: UUID,
        result: ReplayValidationResult,
    ) -> SemanticOutcome:
        return SemanticOutcome(
            outcome_id=outcome_id,
            ok=True,
            boundary=SemanticBoundary.LAYER_2_READ_SIDE,
            category=SemanticOutcomeCategory.VALID,
            semantic_code=SemanticOutcomeCode.SEMANTICALLY_VALID,
            severity=SemanticSeverity.INFO,
            risk_level=SemanticRiskLevel.LOW,
            reversibility=SemanticReversibility.REVERSIBLE,
            reason=result.reason,
            context={
                "snapshot_object": object(),
                "order_id": "caller-overridden-order",
            },
            evidence={
                "result_type": "CallerOverride",
                "expected_state_present": False,
                "persisted_state_present": False,
                "state_object": result.expected_state,
            },
        )

    monkeypatch.setattr(
        mapping_module,
        "map_replay_validation_result_to_semantic_outcome",
        fake_stage_4a_adapter,
    )

    receipt = map_replay_validation_result_to_decision_receipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )

    assert receipt.correlation.order_id == ORDER_ID
    assert receipt.evidence_summary == {
        "technical_status": "MATCH",
        "expected_state_present": True,
        "persisted_state_present": True,
    }
    assert "result_type" not in receipt.evidence_summary
    assert "state_object" not in receipt.evidence_summary
    assert receipt.metadata == {}


def test_receipt_flexible_evidence_contains_no_state_or_snapshot_objects() -> None:
    result = ProjectionSnapshotReplayValidationResult(
        status=ProjectionSnapshotReplayValidationStatus.MATCH,
        order_id=ORDER_ID,
        snapshot_id=SNAPSHOT_ID,
        source_global_position=10,
        snapshot_assisted_state=CREATED_STATE,
        authority_state=CREATED_STATE,
        reason="Snapshot-assisted replay matches authority.",
    )

    receipt = (
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert not any(
        isinstance(value, (OrderState, ProjectionSnapshot))
        for value in receipt.evidence_summary.values()
    )
    assert receipt.metadata == {}


def test_pr5_receipt_adds_no_action_policy_retry_or_persistence_contract() -> None:
    result = ReplayValidationResult(
        order_id=ORDER_ID,
        status=ReplayValidationStatus.MATCH,
        expected_state=CREATED_STATE,
        persisted_state=CREATED_STATE,
        reason="Projection matches.",
    )
    receipt = map_replay_validation_result_to_decision_receipt(
        receipt_id=RECEIPT_ID,
        outcome_id=OUTCOME_ID,
        result=result,
    )
    field_names = {field.name for field in fields(receipt)}

    assert field_names.isdisjoint(
        {
            "runtime_action",
            "policy",
            "strategy",
            "retry_allowed",
            "serializer",
            "persisted",
            "store",
            "transaction",
        }
    )


@pytest.mark.parametrize("order_id", ["", " \t "], ids=["blank", "whitespace"])
def test_all_producer_mappings_reject_blank_order_id(order_id: str) -> None:
    # This is receipt-contract admission validation. The generic producer
    # result dataclasses remain directly constructable with these values.
    cases: tuple[tuple[Callable[..., DecisionReceipt], object], ...] = (
        (
            map_replay_validation_result_to_decision_receipt,
            ReplayValidationResult(
                order_id=order_id,
                status=ReplayValidationStatus.MATCH,
                expected_state=CREATED_STATE,
                persisted_state=CREATED_STATE,
                reason="invalid",
            ),
        ),
        (
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MATCH,
                order_id=order_id,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                snapshot_assisted_state=CREATED_STATE,
                authority_state=CREATED_STATE,
                reason="invalid",
            ),
        ),
        (
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=order_id,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                resolved_state=CREATED_STATE,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                reason="invalid",
            ),
        ),
    )

    for mapper, result in cases:
        typed_mapper = cast(Callable[..., DecisionReceipt], mapper)

        with pytest.raises(
            ValueError,
            match="order_id must be a non-empty string",
        ):
            typed_mapper(
                receipt_id=RECEIPT_ID,
                outcome_id=OUTCOME_ID,
                result=result,
            )


def test_all_producer_mappings_reject_foreign_status_enum() -> None:
    # Cross-family enum values are deliberately synthetic and prove that the
    # wrappers validate producer ownership rather than matching status text.
    cases: tuple[
        tuple[Callable[..., DecisionReceipt], object, str],
        ...,
    ] = (
        (
            map_replay_validation_result_to_decision_receipt,
            ReplayValidationResult(
                order_id=ORDER_ID,
                status=cast(
                    ReplayValidationStatus,
                    ProjectionSnapshotReplayValidationStatus.MATCH,
                ),
                expected_state=CREATED_STATE,
                persisted_state=CREATED_STATE,
                reason="invalid",
            ),
            "ReplayValidationResult.status must be ReplayValidationStatus",
        ),
        (
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=cast(
                    ProjectionSnapshotReplayValidationStatus,
                    ReplayValidationStatus.MATCH,
                ),
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                snapshot_assisted_state=CREATED_STATE,
                authority_state=CREATED_STATE,
                reason="invalid",
            ),
            "ProjectionSnapshotReplayValidationResult.status must be "
            "ProjectionSnapshotReplayValidationStatus",
        ),
        (
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=cast(
                    ProjectionSnapshotAssistedResolutionStatus,
                    ProjectionSnapshotReplayValidationStatus.MATCH,
                ),
                resolved_state=CREATED_STATE,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                reason="invalid",
            ),
            "ProjectionSnapshotAssistedResolutionResult.status must be "
            "ProjectionSnapshotAssistedResolutionStatus",
        ),
    )

    for mapper, result, message in cases:
        typed_mapper = cast(Callable[..., DecisionReceipt], mapper)

        with pytest.raises(ValueError, match=message):
            typed_mapper(
                receipt_id=RECEIPT_ID,
                outcome_id=OUTCOME_ID,
                result=result,
            )


@pytest.mark.parametrize(
    ("mapper", "result", "message"),
    [
        pytest.param(
            map_replay_validation_result_to_decision_receipt,
            ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.MATCH,
                expected_state=cast(OrderState, "not-an-order-state"),
                persisted_state=CREATED_STATE,
                reason="invalid",
            ),
            "ReplayValidationResult.expected_state must be OrderState",
            id="replay-expected-state-wrong-type",
        ),
        pytest.param(
            map_replay_validation_result_to_decision_receipt,
            ReplayValidationResult(
                order_id=ORDER_ID,
                status=ReplayValidationStatus.MATCH,
                expected_state=CREATED_STATE,
                persisted_state=OTHER_ORDER_STATE,
                reason="invalid",
            ),
            "ReplayValidationResult.persisted_state order_id mismatch",
            id="replay-persisted-state-wrong-order",
        ),
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=ProjectionSnapshotReplayValidationStatus.MATCH,
                order_id=ORDER_ID,
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                snapshot_assisted_state=cast(
                    OrderState,
                    "not-an-order-state",
                ),
                authority_state=CREATED_STATE,
                reason="invalid",
            ),
            "ProjectionSnapshotReplayValidationResult.snapshot_assisted_state "
            "must be OrderState",
            id="snapshot-assisted-state-wrong-type",
        ),
        pytest.param(
            map_projection_snapshot_replay_validation_result_to_decision_receipt,
            ProjectionSnapshotReplayValidationResult(
                status=(
                    ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT
                ),
                order_id=ORDER_ID,
                snapshot_id=None,
                source_global_position=None,
                snapshot_assisted_state=None,
                authority_state=OTHER_ORDER_STATE,
                reason="invalid",
            ),
            "ProjectionSnapshotReplayValidationResult.authority_state "
            "order_id mismatch",
            id="snapshot-authority-state-wrong-order",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                resolved_state=cast(OrderState, "not-an-order-state"),
                reason="invalid",
            ),
            "ProjectionSnapshotAssistedResolutionResult.resolved_state "
            "must be OrderState",
            id="resolution-state-wrong-type",
        ),
        pytest.param(
            map_projection_snapshot_assisted_resolution_result_to_decision_receipt,
            ProjectionSnapshotAssistedResolutionResult(
                order_id=ORDER_ID,
                status=(
                    ProjectionSnapshotAssistedResolutionStatus
                    .RESOLVED_FROM_SNAPSHOT
                ),
                snapshot_id=SNAPSHOT_ID,
                source_global_position=10,
                resolved_state=OTHER_ORDER_STATE,
                reason="invalid",
            ),
            "ProjectionSnapshotAssistedResolutionResult.resolved_state "
            "order_id mismatch",
            id="resolution-state-wrong-order",
        ),
    ],
)
def test_present_state_requires_order_state_for_result_order(
    mapper: Callable[..., DecisionReceipt],
    result: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        mapper(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


INVALID_REPLAY_RESULTS = [
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MATCH,
            expected_state=None,
            persisted_state=CREATED_STATE,
            reason="invalid",
        ),
        "MATCH requires expected_state and persisted_state",
        id="match-missing-state",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MATCH,
            expected_state=PAID_STATE,
            persisted_state=CREATED_STATE,
            reason="invalid",
        ),
        "MATCH requires equal states",
        id="match-unequal",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MISSING_PROJECTION,
            expected_state=None,
            persisted_state=None,
            reason="invalid",
        ),
        "requires accepted-history replay state",
        id="missing-projection-no-expected-state",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.MISSING_PROJECTION,
            expected_state=CREATED_STATE,
            persisted_state=CREATED_STATE,
            reason="invalid",
        ),
        "requires persisted projection to be absent",
        id="missing-projection-has-persisted-state",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.DRIFT,
            expected_state=None,
            persisted_state=CREATED_STATE,
            reason="invalid",
        ),
        "DRIFT requires expected_state and persisted_state",
        id="drift-missing-state",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.DRIFT,
            expected_state=CREATED_STATE,
            persisted_state=CREATED_STATE,
            reason="invalid",
        ),
        "DRIFT requires unequal states",
        id="drift-equal",
    ),
    pytest.param(
        ReplayValidationResult(
            order_id=ORDER_ID,
            status=ReplayValidationStatus.NO_ACCEPTED_HISTORY,
            expected_state=CREATED_STATE,
            persisted_state=None,
            reason="invalid",
        ),
        "NO_ACCEPTED_HISTORY requires absent expected_state",
        id="no-history-has-expected-state",
    ),
]


@pytest.mark.parametrize(("result", "message"), INVALID_REPLAY_RESULTS)
def test_replay_mapping_rejects_contradictory_shapes(
    result: ReplayValidationResult,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        map_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


INVALID_SNAPSHOT_REPLAY_RESULTS = [
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MATCH,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=None,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "both present or both absent",
        id="unpaired-lineage",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MATCH,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "MATCH requires loaded snapshot lineage",
        id="match-no-lineage",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MATCH,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=PAID_STATE,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "MATCH requires equal states",
        id="match-unequal",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=None,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "MISSING_SNAPSHOT requires absent snapshot lineage",
        id="missing-snapshot-has-lineage",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=ProjectionSnapshotReplayValidationStatus.MISSING_SNAPSHOT,
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            snapshot_assisted_state=None,
            authority_state=None,
            reason="invalid",
        ),
        "MISSING_SNAPSHOT requires absent snapshot_assisted_state and present "
        "authority_state",
        id="missing-snapshot-no-authority",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .INVALID_SNAPSHOT_BOUNDARY
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "INVALID_SNAPSHOT_BOUNDARY requires absent "
        "snapshot_assisted_state and present authority_state",
        id="invalid-boundary-has-snapshot-state",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=None,
            authority_state=CREATED_STATE,
            reason="invalid",
        ),
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION requires "
        "snapshot_assisted_state and authority_state",
        id="tail-source-missing-snapshot-state",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .SNAPSHOT_ASSISTED_DRIFT
            ),
            order_id=ORDER_ID,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=None,
            reason="invalid",
        ),
        "SNAPSHOT_ASSISTED_DRIFT requires snapshot_assisted_state "
        "and authority_state",
        id="drift-missing-authority",
    ),
    pytest.param(
        ProjectionSnapshotReplayValidationResult(
            status=(
                ProjectionSnapshotReplayValidationStatus
                .NO_ACCEPTED_HISTORY_FOR_ORDER
            ),
            order_id=ORDER_ID,
            snapshot_id=None,
            source_global_position=None,
            snapshot_assisted_state=CREATED_STATE,
            authority_state=None,
            reason="invalid",
        ),
        "NO_ACCEPTED_HISTORY_FOR_ORDER requires absent comparison states",
        id="no-history-has-comparison-state",
    ),
]


@pytest.mark.parametrize(
    ("result", "message"),
    INVALID_SNAPSHOT_REPLAY_RESULTS,
)
def test_snapshot_replay_mapping_rejects_contradictory_shapes(
    result: ProjectionSnapshotReplayValidationResult,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        map_projection_snapshot_replay_validation_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


INVALID_SNAPSHOT_ASSISTED_RESULTS = [
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .INVALID_SNAPSHOT_PRECONDITION
            ),
            snapshot_id=SNAPSHOT_ID,
            source_global_position=None,
            resolved_state=None,
            reason="invalid",
        ),
        "INVALID_SNAPSHOT_PRECONDITION requires absent snapshot reference",
        id="precondition-has-snapshot-reference",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
            snapshot_id=None,
            source_global_position=None,
            resolved_state=None,
            reason="invalid",
        ),
        "MISSING_SNAPSHOT requires requested snapshot_id",
        id="missing-snapshot-no-request-reference",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            resolved_state=None,
            reason="invalid",
        ),
        "MISSING_SNAPSHOT requires requested snapshot_id, absent "
        "source_global_position",
        id="missing-snapshot-has-position",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .RESOLVED_FROM_SNAPSHOT
            ),
            snapshot_id=SNAPSHOT_ID,
            source_global_position=None,
            resolved_state=CREATED_STATE,
            reason="invalid",
        ),
        "RESOLVED_FROM_SNAPSHOT requires loaded snapshot lineage",
        id="resolved-missing-position",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .RESOLVED_FROM_SNAPSHOT
            ),
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            resolved_state=None,
            reason="invalid",
        ),
        "RESOLVED_FROM_SNAPSHOT requires resolved_state",
        id="resolved-missing-state",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .INVALID_SNAPSHOT_COMPATIBILITY
            ),
            snapshot_id=None,
            source_global_position=None,
            resolved_state=None,
            reason="invalid",
        ),
        "INVALID_SNAPSHOT_COMPATIBILITY requires loaded snapshot lineage",
        id="compatibility-no-lineage",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=(
                ProjectionSnapshotAssistedResolutionStatus
                .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
            ),
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            resolved_state=CREATED_STATE,
            reason="invalid",
        ),
        "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION requires absent resolved_state",
        id="tail-source-has-resolved-state",
    ),
    pytest.param(
        ProjectionSnapshotAssistedResolutionResult(
            order_id=ORDER_ID,
            status=ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED,
            snapshot_id=SNAPSHOT_ID,
            source_global_position=10,
            resolved_state=CREATED_STATE,
            reason="invalid",
        ),
        "TAIL_REPLAY_FAILED requires absent resolved_state",
        id="tail-replay-has-resolved-state",
    ),
]


@pytest.mark.parametrize(
    ("result", "message"),
    INVALID_SNAPSHOT_ASSISTED_RESULTS,
)
def test_snapshot_assisted_mapping_rejects_contradictory_shapes(
    result: ProjectionSnapshotAssistedResolutionResult,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )


def test_missing_snapshot_preserves_requested_reference_without_loaded_lineage() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id=ORDER_ID,
        status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
        snapshot_id=SECOND_SNAPSHOT_ID,
        source_global_position=None,
        resolved_state=None,
        reason="Requested snapshot was not found.",
    )

    receipt = (
        map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
            receipt_id=RECEIPT_ID,
            outcome_id=OUTCOME_ID,
            result=result,
        )
    )

    assert receipt.subject.subject_id == str(SECOND_SNAPSHOT_ID)
    assert receipt.correlation.snapshot_id == SECOND_SNAPSHOT_ID
    assert receipt.correlation.source_global_position is None
    assert (
        receipt.correlation.identity_source
        == DecisionReceiptIdentitySource.READ_SIDE_OBSERVATION
    )


def test_public_surface_is_exact() -> None:
    assert set(mapping_module.__all__) == {
        "map_replay_validation_result_to_decision_receipt",
        "map_projection_snapshot_replay_validation_result_to_decision_receipt",
        "map_projection_snapshot_assisted_resolution_result_to_decision_receipt",
    }
