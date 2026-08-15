from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import Any, cast
from uuid import uuid4

import pytest

from src.pipeline.projection.projection_snapshot_assisted_resolution_trace import (  # noqa: E501
    ProjectionSnapshotAssistedResolutionExecution,
    ProjectionSnapshotAssistedResolutionTerminalStage,
    ProjectionSnapshotAssistedResolutionTrace,
)
from src.pipeline.projection.projection_snapshot_assisted_state_resolver import (  # noqa: E501
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)
from tests.shared.order_states import make_order_state


def test_projection_snapshot_assisted_resolution_terminal_stage_values(
) -> None:
    assert {
        stage.value
        for stage in ProjectionSnapshotAssistedResolutionTerminalStage
    } == {
        "SNAPSHOT_PRECONDITION",
        "SNAPSHOT_LOOKUP",
        "SNAPSHOT_COMPATIBILITY",
        "SNAPSHOT_HYDRATION",
        "TAIL_SOURCE",
        "TAIL_REPLAY",
        "COMPLETED",
    }


def test_precondition_stage_trace_has_no_snapshot_or_tail_evidence() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_PRECONDITION
        )
    )

    assert trace.snapshot_source_event_sequence is None
    assert trace.last_validated_tail_event_sequence is None
    assert trace.last_successfully_replayed_tail_event_sequence is None
    assert trace.source_expected_event_sequence is None
    assert trace.observed_event_sequence is None
    assert trace.observed_order_id is None
    assert trace.observed_event_id is None


def test_missing_snapshot_lookup_stage_trace_has_no_snapshot_base() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_LOOKUP
        )
    )

    assert trace.snapshot_source_event_sequence is None


def test_compatibility_stage_trace_uses_conservative_snapshot_evidence(
) -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_COMPATIBILITY
        )
    )

    assert trace.snapshot_source_event_sequence is None


def test_hydration_stage_trace_requires_only_validated_snapshot_base() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_HYDRATION
        ),
        snapshot_source_event_sequence=3,
    )

    assert trace.snapshot_source_event_sequence == 3
    assert trace.last_validated_tail_event_sequence is None
    assert trace.last_successfully_replayed_tail_event_sequence is None


def test_tail_source_trace_preserves_validation_progress_without_replay(
) -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE
        ),
        snapshot_source_event_sequence=10,
        last_validated_tail_event_sequence=12,
        source_expected_event_sequence=13,
        observed_event_sequence=15,
        observed_order_id="order-001",
        observed_event_id="accepted-event-015",
    )

    assert trace.last_validated_tail_event_sequence == 12
    assert trace.last_successfully_replayed_tail_event_sequence is None
    assert trace.source_expected_event_sequence == 13
    assert trace.observed_event_id == "accepted-event-015"


def test_tail_source_trace_can_record_adapter_failure_without_observed_event(
) -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE
        ),
        snapshot_source_event_sequence=10,
        source_expected_event_sequence=11,
    )

    assert trace.last_validated_tail_event_sequence is None
    assert trace.observed_event_sequence is None


def test_tail_replay_trace_preserves_complete_validation_and_shorter_prefix(
) -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY
        ),
        snapshot_source_event_sequence=10,
        last_validated_tail_event_sequence=15,
        last_successfully_replayed_tail_event_sequence=12,
        observed_event_sequence=13,
        observed_order_id="order-001",
        observed_event_id="accepted-event-013",
    )

    assert trace.last_validated_tail_event_sequence == 15
    assert trace.last_successfully_replayed_tail_event_sequence == 12
    assert trace.observed_event_sequence == 13


def test_completed_trace_can_preserve_successful_tail_progress() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
        ),
        snapshot_source_event_sequence=10,
        last_validated_tail_event_sequence=12,
        last_successfully_replayed_tail_event_sequence=12,
    )

    assert trace.last_validated_tail_event_sequence == 12
    assert trace.last_successfully_replayed_tail_event_sequence == 12


def test_completed_snapshot_only_trace_has_null_tail_progress() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
        ),
        snapshot_source_event_sequence=10,
    )

    assert trace.last_validated_tail_event_sequence is None
    assert trace.last_successfully_replayed_tail_event_sequence is None


def test_trace_is_immutable() -> None:
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
        ),
        snapshot_source_event_sequence=10,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(
            trace,
            "terminal_stage",
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY,
        )


def test_execution_envelope_is_immutable_and_preserves_existing_result(
) -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=(
            ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT
        ),
        resolved_state=make_order_state(),
        snapshot_id=uuid4(),
        source_global_position=20,
        reason="Projection state resolved from snapshot and tail replay.",
    )
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
        ),
        snapshot_source_event_sequence=1,
    )

    execution = ProjectionSnapshotAssistedResolutionExecution(
        result=result,
        trace=trace,
    )

    assert execution.result is result
    assert execution.trace is trace
    with pytest.raises(FrozenInstanceError):
        setattr(execution, "trace", trace)


@pytest.mark.parametrize(
    ("status", "terminal_stage"),
    [
        (
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_PRECONDITION,
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_PRECONDITION,
        ),
        (
            ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
            ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_LOOKUP,
        ),
        (
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_COMPATIBILITY,
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_COMPATIBILITY,
        ),
        (
            ProjectionSnapshotAssistedResolutionStatus
            .INVALID_SNAPSHOT_COMPATIBILITY,
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_HYDRATION,
        ),
    ],
)
def test_execution_envelope_accepts_source_grounded_result_stage_pairs(
    status: ProjectionSnapshotAssistedResolutionStatus,
    terminal_stage: ProjectionSnapshotAssistedResolutionTerminalStage,
) -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=status,
    )
    trace_kwargs: dict[str, Any] = {"terminal_stage": terminal_stage}
    if (
        terminal_stage
        == ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_HYDRATION
    ):
        trace_kwargs["snapshot_source_event_sequence"] = 1
    trace = ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)

    execution = ProjectionSnapshotAssistedResolutionExecution(
        result=result,
        trace=trace,
    )

    assert execution.result.status == status
    assert execution.trace.terminal_stage == terminal_stage


@pytest.mark.parametrize(
    "field_name",
    [
        "snapshot_source_event_sequence",
        "last_validated_tail_event_sequence",
        "last_successfully_replayed_tail_event_sequence",
        "source_expected_event_sequence",
        "observed_event_sequence",
    ],
)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_trace_rejects_non_positive_sequence_fields(
    field_name: str,
    invalid_value: int,
) -> None:
    trace_kwargs = _valid_tail_replay_trace_kwargs()
    trace_kwargs[field_name] = invalid_value

    with pytest.raises(ValueError, match=f"{field_name} must be positive"):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


@pytest.mark.parametrize("invalid_value", [True, "1"])
def test_trace_rejects_invalid_sequence_field_types(
    invalid_value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="snapshot_source_event_sequence must be int or None",
    ):
        ProjectionSnapshotAssistedResolutionTrace(
            terminal_stage=(
                ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
            ),
            snapshot_source_event_sequence=cast(Any, invalid_value),
        )


@pytest.mark.parametrize(
    "field_name",
    ["observed_order_id", "observed_event_id"],
)
@pytest.mark.parametrize("invalid_value", ["", "   "])
def test_trace_rejects_empty_observed_identifiers(
    field_name: str,
    invalid_value: str,
) -> None:
    trace_kwargs = _valid_tail_source_trace_kwargs()
    trace_kwargs[field_name] = invalid_value

    with pytest.raises(
        ValueError,
        match=f"{field_name} must be a non-empty string",
    ):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


@pytest.mark.parametrize(
    "missing_field",
    ["observed_event_sequence", "observed_order_id", "observed_event_id"],
)
def test_trace_rejects_partial_observed_event_identity(
    missing_field: str,
) -> None:
    trace_kwargs = _valid_tail_source_trace_kwargs()
    trace_kwargs[missing_field] = None

    with pytest.raises(ValueError, match="must be all present or all absent"):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


def test_trace_rejects_replay_progress_greater_than_validation_progress(
) -> None:
    trace_kwargs = _valid_tail_replay_trace_kwargs()
    trace_kwargs["last_validated_tail_event_sequence"] = 12
    trace_kwargs["last_successfully_replayed_tail_event_sequence"] = 13

    with pytest.raises(ValueError, match="must not exceed"):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


def test_trace_rejects_tail_progress_at_pre_snapshot_stage() -> None:
    with pytest.raises(ValueError, match="requires absent tail evidence"):
        ProjectionSnapshotAssistedResolutionTrace(
            terminal_stage=(
                ProjectionSnapshotAssistedResolutionTerminalStage
                .SNAPSHOT_PRECONDITION
            ),
            last_validated_tail_event_sequence=1,
        )


@pytest.mark.parametrize(
    "failure_evidence",
    [
        {"source_expected_event_sequence": 2},
        {
            "observed_event_sequence": 2,
            "observed_order_id": "order-001",
            "observed_event_id": "accepted-event-002",
        },
    ],
)
def test_completed_trace_rejects_failure_only_evidence(
    failure_evidence: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="COMPLETED requires absent"):
        ProjectionSnapshotAssistedResolutionTrace(
            terminal_stage=(
                ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
            ),
            snapshot_source_event_sequence=1,
            **failure_evidence,
        )


def test_completed_trace_rejects_unpaired_validation_progress() -> None:
    with pytest.raises(ValueError, match="both present or both absent"):
        ProjectionSnapshotAssistedResolutionTrace(
            terminal_stage=(
                ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED
            ),
            snapshot_source_event_sequence=1,
            last_validated_tail_event_sequence=2,
        )


def test_tail_source_trace_rejects_incoherent_expected_sequence() -> None:
    trace_kwargs = _valid_tail_source_trace_kwargs()
    trace_kwargs["source_expected_event_sequence"] = 14

    with pytest.raises(ValueError, match="must be the next sequence"):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


def test_tail_replay_trace_rejects_event_outside_validated_tail() -> None:
    trace_kwargs = _valid_tail_replay_trace_kwargs()
    trace_kwargs["last_validated_tail_event_sequence"] = 12

    with pytest.raises(ValueError, match="must be within"):
        ProjectionSnapshotAssistedResolutionTrace(**trace_kwargs)


def test_execution_envelope_rejects_result_stage_mismatch() -> None:
    result = ProjectionSnapshotAssistedResolutionResult(
        order_id="order-001",
        status=ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT,
    )
    trace = ProjectionSnapshotAssistedResolutionTrace(
        terminal_stage=(
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_PRECONDITION
        )
    )

    with pytest.raises(ValueError, match="is incoherent with terminal stage"):
        ProjectionSnapshotAssistedResolutionExecution(
            result=result,
            trace=trace,
        )


def test_trace_and_execution_contracts_expose_only_approved_fields() -> None:
    assert {
        field.name
        for field in fields(ProjectionSnapshotAssistedResolutionTrace)
    } == {
        "terminal_stage",
        "snapshot_source_event_sequence",
        "last_validated_tail_event_sequence",
        "last_successfully_replayed_tail_event_sequence",
        "source_expected_event_sequence",
        "observed_event_sequence",
        "observed_order_id",
        "observed_event_id",
    }
    assert {
        field.name
        for field in fields(ProjectionSnapshotAssistedResolutionExecution)
    } == {"result", "trace"}


def test_trace_contract_excludes_state_and_deferred_responsibilities() -> None:
    field_names = {
        field.name
        for field in fields(ProjectionSnapshotAssistedResolutionTrace)
    }
    forbidden_field_names = {
        "resolved_state",
        "partial_state",
        "order_state",
        "reason",
        "exception",
        "exception_text",
        "request_id",
        "source_global_position",
        "snapshot_id",
        "result_status",
        "decision_receipt",
        "trace_id",
        "metadata",
        "retry",
        "fallback",
        "policy",
        "strategy",
        "action",
        "cost",
        "persistence",
        "replay_expected_event_sequence",
    }

    assert field_names.isdisjoint(forbidden_field_names)


def _valid_tail_source_trace_kwargs() -> dict[str, Any]:
    return {
        "terminal_stage": (
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE
        ),
        "snapshot_source_event_sequence": 10,
        "last_validated_tail_event_sequence": 12,
        "source_expected_event_sequence": 13,
        "observed_event_sequence": 15,
        "observed_order_id": "order-001",
        "observed_event_id": "accepted-event-015",
    }


def _valid_tail_replay_trace_kwargs() -> dict[str, Any]:
    return {
        "terminal_stage": (
            ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY
        ),
        "snapshot_source_event_sequence": 10,
        "last_validated_tail_event_sequence": 15,
        "last_successfully_replayed_tail_event_sequence": 12,
        "observed_event_sequence": 13,
        "observed_order_id": "order-001",
        "observed_event_id": "accepted-event-013",
    }
