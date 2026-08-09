from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .projection_snapshot_assisted_state_resolver import (
    ProjectionSnapshotAssistedResolutionResult,
    ProjectionSnapshotAssistedResolutionStatus,
)


class ProjectionSnapshotAssistedResolutionTerminalStage(str, Enum):
    """Terminal stage reached by one snapshot-assisted resolution execution.

    The values identify the bounded control-flow stage that produced an
    existing typed resolution result. They do not classify root cause,
    authorize retry or fallback, select policy or strategy, or describe runtime
    action.

    Constructor/configuration failures and currently propagating unexpected
    exceptions produce no execution envelope and therefore no terminal stage.
    """

    SNAPSHOT_PRECONDITION = "SNAPSHOT_PRECONDITION"
    SNAPSHOT_LOOKUP = "SNAPSHOT_LOOKUP"
    SNAPSHOT_COMPATIBILITY = "SNAPSHOT_COMPATIBILITY"
    SNAPSHOT_HYDRATION = "SNAPSHOT_HYDRATION"
    TAIL_SOURCE = "TAIL_SOURCE"
    TAIL_REPLAY = "TAIL_REPLAY"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ProjectionSnapshotAssistedResolutionTrace:
    """Preserve bounded scalar progress for one resolution execution.

    Responsibility:
    - identify the terminal execution stage;
    - preserve a validated snapshot base when that boundary was reached;
    - keep tail-source validation progress separate from tail-replay progress;
    - preserve bounded observed-event identity for source or replay failure.

    Sequence values are positive order-local coordinates. Snapshot sequence is
    an immutable base, not replay progress. Observed event identity remains the
    accepted record's existing string ``event_id`` and is never inferred from
    ``request_id`` or converted to UUID.

    Construction raises ``TypeError`` for invalid field types and
    ``ValueError`` for incoherent stage, presence, identity, or progress
    relationships. This in-memory object contains no result reason, exception
    text, domain state, event payload, persistence metadata, policy, strategy,
    fallback, retry, action, cost, or observability behavior.
    """

    terminal_stage: ProjectionSnapshotAssistedResolutionTerminalStage
    snapshot_source_event_sequence: int | None = None
    last_validated_tail_event_sequence: int | None = None
    last_successfully_replayed_tail_event_sequence: int | None = None
    source_expected_event_sequence: int | None = None
    observed_event_sequence: int | None = None
    observed_order_id: str | None = None
    observed_event_id: str | None = None

    def __post_init__(self) -> None:
        _require_enum(
            self.terminal_stage,
            ProjectionSnapshotAssistedResolutionTerminalStage,
            "terminal_stage",
        )
        _require_optional_positive_int(
            self.snapshot_source_event_sequence,
            "snapshot_source_event_sequence",
        )
        _require_optional_positive_int(
            self.last_validated_tail_event_sequence,
            "last_validated_tail_event_sequence",
        )
        _require_optional_positive_int(
            self.last_successfully_replayed_tail_event_sequence,
            "last_successfully_replayed_tail_event_sequence",
        )
        _require_optional_positive_int(
            self.source_expected_event_sequence,
            "source_expected_event_sequence",
        )
        _require_optional_positive_int(
            self.observed_event_sequence,
            "observed_event_sequence",
        )
        _require_optional_non_empty_string(
            self.observed_order_id,
            "observed_order_id",
        )
        _require_optional_non_empty_string(
            self.observed_event_id,
            "observed_event_id",
        )
        _validate_observed_event_presence(self)
        _validate_stage_presence(self)
        _validate_progress_coherence(self)


@dataclass(frozen=True)
class ProjectionSnapshotAssistedResolutionExecution:
    """Pair one existing primary resolution result with exactly one trace.

    ``result`` remains the authoritative producer result, including status,
    reason, snapshot lineage, and successful resolved state. ``trace`` owns
    only bounded execution-stage and progress evidence. The envelope validates
    their source-grounded status/stage relationship but does not reconstruct,
    reinterpret, or otherwise validate the existing result's contents.

    Construction raises ``TypeError`` for the wrong result or trace type and
    ``ValueError`` for a result-status/terminal-stage mismatch. The envelope is
    immutable, in memory, and provides no execution, persistence,
    serialization, policy, fallback, retry, strategy, action, cost, or
    observability behavior.
    """

    result: ProjectionSnapshotAssistedResolutionResult
    trace: ProjectionSnapshotAssistedResolutionTrace

    def __post_init__(self) -> None:
        _require_type(
            self.result,
            ProjectionSnapshotAssistedResolutionResult,
            "result",
        )
        _require_type(
            self.trace,
            ProjectionSnapshotAssistedResolutionTrace,
            "trace",
        )
        _validate_execution_coherence(self.result, self.trace)


_PRE_SNAPSHOT_BASE_STAGES = frozenset(
    {
        (
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_PRECONDITION
        ),
        ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_LOOKUP,
        (
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_COMPATIBILITY
        ),
    }
)

_PRE_TAIL_STAGES = _PRE_SNAPSHOT_BASE_STAGES | {
    ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_HYDRATION,
}

_RESULT_STATUS_TO_TERMINAL_STAGES = {
    ProjectionSnapshotAssistedResolutionStatus.INVALID_SNAPSHOT_PRECONDITION: (
        (
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_PRECONDITION
        ),
    ),
    ProjectionSnapshotAssistedResolutionStatus.MISSING_SNAPSHOT: (
        ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_LOOKUP,
    ),
    (
        ProjectionSnapshotAssistedResolutionStatus
        .INVALID_SNAPSHOT_COMPATIBILITY
    ): (
        (
            ProjectionSnapshotAssistedResolutionTerminalStage
            .SNAPSHOT_COMPATIBILITY
        ),
        ProjectionSnapshotAssistedResolutionTerminalStage.SNAPSHOT_HYDRATION,
    ),
    (
        ProjectionSnapshotAssistedResolutionStatus
        .TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
    ): (
        ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE,
    ),
    ProjectionSnapshotAssistedResolutionStatus.TAIL_REPLAY_FAILED: (
        ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY,
    ),
    ProjectionSnapshotAssistedResolutionStatus.RESOLVED_FROM_SNAPSHOT: (
        ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED,
    ),
}


def _validate_observed_event_presence(
    trace: ProjectionSnapshotAssistedResolutionTrace,
) -> None:
    observed_presence = (
        trace.observed_event_sequence is not None,
        trace.observed_order_id is not None,
        trace.observed_event_id is not None,
    )
    if any(observed_presence) and not all(observed_presence):
        raise ValueError(
            "observed_event_sequence, observed_order_id, and "
            "observed_event_id must be all present or all absent"
        )


def _validate_stage_presence(
    trace: ProjectionSnapshotAssistedResolutionTrace,
) -> None:
    stage = trace.terminal_stage
    if stage in _PRE_SNAPSHOT_BASE_STAGES:
        if trace.snapshot_source_event_sequence is not None:
            raise ValueError(
                f"{stage.value} requires absent snapshot_source_event_sequence"
            )
    elif trace.snapshot_source_event_sequence is None:
        raise ValueError(
            f"{stage.value} requires snapshot_source_event_sequence"
        )

    if stage in _PRE_TAIL_STAGES:
        _require_absent_tail_evidence(trace)
        return

    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE:
        if trace.source_expected_event_sequence is None:
            raise ValueError(
                "TAIL_SOURCE requires source_expected_event_sequence"
            )
        if trace.last_successfully_replayed_tail_event_sequence is not None:
            raise ValueError(
                "TAIL_SOURCE requires absent replay progress"
            )
        return

    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY:
        if trace.last_validated_tail_event_sequence is None:
            raise ValueError(
                "TAIL_REPLAY requires last_validated_tail_event_sequence"
            )
        if trace.source_expected_event_sequence is not None:
            raise ValueError(
                "TAIL_REPLAY requires absent source_expected_event_sequence"
            )
        if trace.observed_event_sequence is None:
            raise ValueError("TAIL_REPLAY requires observed event evidence")
        return

    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED:
        if trace.source_expected_event_sequence is not None:
            raise ValueError(
                "COMPLETED requires absent source_expected_event_sequence"
            )
        if trace.observed_event_sequence is not None:
            raise ValueError(
                "COMPLETED requires absent observed event evidence"
            )
        return

    raise ValueError(f"Unsupported terminal_stage: {stage}")


def _require_absent_tail_evidence(
    trace: ProjectionSnapshotAssistedResolutionTrace,
) -> None:
    tail_evidence = {
        "last_validated_tail_event_sequence": (
            trace.last_validated_tail_event_sequence
        ),
        "last_successfully_replayed_tail_event_sequence": (
            trace.last_successfully_replayed_tail_event_sequence
        ),
        "source_expected_event_sequence": trace.source_expected_event_sequence,
        "observed_event_sequence": trace.observed_event_sequence,
    }
    present_fields = [
        field_name
        for field_name, field_value in tail_evidence.items()
        if field_value is not None
    ]
    if present_fields:
        raise ValueError(
            f"{trace.terminal_stage.value} requires absent tail evidence: "
            f"{', '.join(present_fields)}"
        )


def _validate_progress_coherence(
    trace: ProjectionSnapshotAssistedResolutionTrace,
) -> None:
    base_sequence = trace.snapshot_source_event_sequence
    validated_sequence = trace.last_validated_tail_event_sequence
    replayed_sequence = trace.last_successfully_replayed_tail_event_sequence

    if validated_sequence is not None:
        if base_sequence is None or validated_sequence <= base_sequence:
            raise ValueError(
                "last_validated_tail_event_sequence must be after "
                "snapshot_source_event_sequence"
            )

    if replayed_sequence is not None:
        if base_sequence is None or replayed_sequence <= base_sequence:
            raise ValueError(
                "last_successfully_replayed_tail_event_sequence must be after "
                "snapshot_source_event_sequence"
            )
        if (
            validated_sequence is None
            or replayed_sequence > validated_sequence
        ):
            raise ValueError(
                "last_successfully_replayed_tail_event_sequence must not "
                "exceed last_validated_tail_event_sequence"
            )

    stage = trace.terminal_stage
    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_SOURCE:
        if base_sequence is None:
            raise ValueError(
                "TAIL_SOURCE requires snapshot_source_event_sequence"
            )

        source_boundary = (
            validated_sequence
            if validated_sequence is not None
            else base_sequence
        )

        if trace.source_expected_event_sequence != source_boundary + 1:
            raise ValueError(
                "source_expected_event_sequence must be the next sequence "
                "after the validated tail boundary"
            )

    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.TAIL_REPLAY:
        observed_event_sequence = trace.observed_event_sequence

        if base_sequence is None:
            raise ValueError(
                "TAIL_REPLAY requires snapshot_source_event_sequence"
            )
        if validated_sequence is None:
            raise ValueError(
                "TAIL_REPLAY requires last_validated_tail_event_sequence"
            )
        if observed_event_sequence is None:
            raise ValueError(
                "TAIL_REPLAY requires observed event evidence"
            )

        replay_boundary = (
            replayed_sequence
            if replayed_sequence is not None
            else base_sequence
        )

        if observed_event_sequence != replay_boundary + 1:
            raise ValueError(
                "TAIL_REPLAY observed_event_sequence must be the next "
                "sequence after the successful replay boundary"
            )

        if validated_sequence < observed_event_sequence:
            raise ValueError(
                "TAIL_REPLAY observed_event_sequence must be within the "
                "complete validated tail"
            )

    if stage == ProjectionSnapshotAssistedResolutionTerminalStage.COMPLETED:
        progress_presence = (
            validated_sequence is not None,
            replayed_sequence is not None,
        )
        if progress_presence[0] != progress_presence[1]:
            raise ValueError(
                "COMPLETED requires validation and replay progress to be both "
                "present or both absent"
            )
        if validated_sequence != replayed_sequence:
            raise ValueError(
                "COMPLETED validation and replay progress must be equal"
            )


def _validate_execution_coherence(
    result: ProjectionSnapshotAssistedResolutionResult,
    trace: ProjectionSnapshotAssistedResolutionTrace,
) -> None:
    status = result.status
    if not isinstance(status, ProjectionSnapshotAssistedResolutionStatus):
        raise TypeError(
            "result.status must be ProjectionSnapshotAssistedResolutionStatus"
        )

    permitted_stages = _RESULT_STATUS_TO_TERMINAL_STAGES[status]
    if trace.terminal_stage not in permitted_stages:
        raise ValueError(
            f"result status {status.value} is incoherent with terminal stage "
            f"{trace.terminal_stage.value}"
        )


def _require_optional_positive_int(value: object, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be int or None")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_optional_non_empty_string(value: object, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str or None")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


def _require_type(
    value: object,
    expected_type: type[object],
    field_name: str,
) -> None:
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be {expected_type.__name__}")
