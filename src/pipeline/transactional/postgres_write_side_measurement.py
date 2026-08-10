"""Immutable Level-A measurement contract for PostgreSQL write execution.

This module defines execution-local evidence shapes only. It does not collect
time, instrument the write side, persist evidence, or change existing producer
APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideExecution,
    PostgresWriteSideResult,
)


class PostgresWriteSidePhaseMeasurementState(str, Enum):
    """Classify evidence availability for one bounded measurement phase.

    ``NOT_APPLICABLE`` means the phase does not belong to the selected concrete
    execution composition. ``NOT_REACHED`` means it belongs to that composition
    but normal execution returned before entering it. ``NOT_COLLECTED`` means
    execution reached the phase but retained no completed elapsed value.
    ``MEASURED`` means a non-negative integer nanosecond delta is present.

    The states describe measurement presence only. They do not establish a
    producer outcome, transaction result, retry decision, or policy judgment.
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REACHED = "NOT_REACHED"
    NOT_COLLECTED = "NOT_COLLECTED"
    MEASURED = "MEASURED"


@dataclass(frozen=True)
class PostgresWriteSidePhaseMeasurement:
    """Represent elapsed evidence for one bounded PostgreSQL write phase.

    Args:
        state: Explicit applicability, reach, and collection state.
        elapsed_ns: Completed monotonic elapsed delta in integer nanoseconds.

    Invariants:
        ``MEASURED`` requires an integer value greater than or equal to zero.
        Every other state requires ``None``. A measured zero is valid evidence
        and is never interpreted as missing.

    Failure behavior:
        Construction rejects an invalid state, non-integer elapsed value,
        negative delta, or state/value mismatch.

    Non-goals:
        This value does not store clock readings, wall-clock timestamps,
        topology, outcomes, additive cost buckets, or persistence metadata.
    """

    state: PostgresWriteSidePhaseMeasurementState
    elapsed_ns: int | None = None

    def __post_init__(self) -> None:
        """Validate the closed state/value representation."""
        if not isinstance(self.state, PostgresWriteSidePhaseMeasurementState):
            raise TypeError(
                "state must be PostgresWriteSidePhaseMeasurementState"
            )

        if self.state is PostgresWriteSidePhaseMeasurementState.MEASURED:
            if isinstance(self.elapsed_ns, bool) or not isinstance(
                self.elapsed_ns,
                int,
            ):
                raise TypeError(
                    "elapsed_ns must be int when state is MEASURED"
                )
            if self.elapsed_ns < 0:
                raise ValueError("elapsed_ns must be non-negative")
            return

        if self.elapsed_ns is not None:
            raise ValueError(
                "elapsed_ns must be None unless state is MEASURED"
            )


_MEASUREMENT_FIELD_NAMES = (
    "producer_write_invocation",
    "business_uow",
    "validation_runtime_call",
    "preliminary_idempotency_check",
    "preliminary_read_cleanup",
    "authoritative_idempotency_check",
    "accepted_history_load",
    "concurrency_preparation_call",
    "pessimistic_advisory_try_lock_call",
    "append_admission_call",
    "idempotency_record_call",
    "commit_finalization",
    "rollback_finalization",
)

_REACHED_STATES = frozenset(
    {
        PostgresWriteSidePhaseMeasurementState.NOT_COLLECTED,
        PostgresWriteSidePhaseMeasurementState.MEASURED,
    }
)


@dataclass(frozen=True)
class PostgresWriteSideMeasurement:
    """Preserve complete Level-A phase state for one normal producer return.

    Args:
        producer_write_invocation: Existing producer API entry through its
            normal return after current UOW finalization. Its ``elapsed_ns``
            excludes final measurement construction and delivery overhead.
        business_uow: Application UOW entry through normal context exit. This
            is not exact physical PostgreSQL transaction lifetime.
        validation_runtime_call: Full ``ValidationRuntime.decide(...)`` call.
            It is distinct from validator-local
            ``ValidationResult.total_time_ms``.
        preliminary_idempotency_check: PRE preliminary idempotency lookup.
        preliminary_read_cleanup: PRE read-transaction rollback/cleanup call.
        authoritative_idempotency_check: Business-UOW idempotency lookup.
        accepted_history_load: Current event-store history load call.
        concurrency_preparation_call: Current ``prepare_stream(...)`` call.
        pessimistic_advisory_try_lock_call: Concrete nonblocking advisory
            try-lock call, not lock-wait time.
        append_admission_call: Current ``append_if_admitted(...)`` call, not
            pure OCC or pure INSERT cost.
        idempotency_record_call: Current transaction-local record call.
        commit_finalization: Current UOW commit call through normal return.
        rollback_finalization: Current UOW rollback call through normal return.

    Invariants:
        All thirteen fields are typed phase measurements. The whole producer
        invocation is measured. Reached-state relationships match the current
        normal-return PRE and IN source topology, including exactly one reached
        finalization for a reached business UOW.

    Failure behavior:
        Construction rejects incomplete or wrongly typed snapshots and the
        source-incompatible reach relationships explicitly owned by this contract. Final construction belongs after
        the existing producer has returned and must not govern business truth.

    Non-goals:
        Detailed intervals overlap. This contract neither sums them into a
        total nor infers positional containment from elapsed deltas. It does not
        own result semantics, traces, persistence, policy, retry, attempts,
        strategy selection, rate limiting, or aggregate statistics.
    """

    producer_write_invocation: PostgresWriteSidePhaseMeasurement
    business_uow: PostgresWriteSidePhaseMeasurement
    validation_runtime_call: PostgresWriteSidePhaseMeasurement
    preliminary_idempotency_check: PostgresWriteSidePhaseMeasurement
    preliminary_read_cleanup: PostgresWriteSidePhaseMeasurement
    authoritative_idempotency_check: PostgresWriteSidePhaseMeasurement
    accepted_history_load: PostgresWriteSidePhaseMeasurement
    concurrency_preparation_call: PostgresWriteSidePhaseMeasurement
    pessimistic_advisory_try_lock_call: PostgresWriteSidePhaseMeasurement
    append_admission_call: PostgresWriteSidePhaseMeasurement
    idempotency_record_call: PostgresWriteSidePhaseMeasurement
    commit_finalization: PostgresWriteSidePhaseMeasurement
    rollback_finalization: PostgresWriteSidePhaseMeasurement

    def __post_init__(self) -> None:
        """Validate field types and current normal-return reach topology."""
        for field_name in _MEASUREMENT_FIELD_NAMES:
            value = getattr(self, field_name)
            if not isinstance(value, PostgresWriteSidePhaseMeasurement):
                raise TypeError(
                    f"{field_name} must be PostgresWriteSidePhaseMeasurement"
                )

        if (
            self.producer_write_invocation.state
            is not PostgresWriteSidePhaseMeasurementState.MEASURED
        ):
            raise ValueError(
                "producer_write_invocation must be MEASURED for an available "
                "normal-return snapshot"
            )

        self._require_same_reach(
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        )
        self._require_parent_reached(
            "validation_runtime_call",
            "accepted_history_load",
        )
        self._require_parent_reached(
            "authoritative_idempotency_check",
            "business_uow",
        )
        self._require_parent_reached(
            "concurrency_preparation_call",
            "authoritative_idempotency_check",
        )
        self._require_parent_reached(
            "pessimistic_advisory_try_lock_call",
            "concurrency_preparation_call",
        )
        self._require_parent_reached(
            "append_admission_call",
            "concurrency_preparation_call",
        )
        self._require_parent_reached(
            "idempotency_record_call",
            "append_admission_call",
        )
        self._require_parent_reached(
            "commit_finalization",
            "idempotency_record_call",
        )
        self._require_parent_reached(
            "rollback_finalization",
            "business_uow",
        )

        uow_reached = _was_reached(self.business_uow)
        finalization_count = sum(
            (
                _was_reached(self.commit_finalization),
                _was_reached(self.rollback_finalization),
            )
        )
        if uow_reached and finalization_count != 1:
            raise ValueError(
                "a reached business_uow requires exactly one reached "
                "commit_finalization or rollback_finalization"
            )
        if not uow_reached and finalization_count != 0:
            raise ValueError(
                "finalization cannot be reached when business_uow was not "
                "reached"
            )

    def _require_same_reach(self, left_name: str, right_name: str) -> None:
        """Require two current normal-return phases to share reached state."""
        left = getattr(self, left_name)
        right = getattr(self, right_name)
        if _was_reached(left) is not _was_reached(right):
            raise ValueError(
                f"{left_name} and {right_name} must have compatible reached "
                "state"
            )

    def _require_parent_reached(
        self,
        child_name: str,
        parent_name: str,
    ) -> None:
        """Reject a reached child whose current source parent was not reached."""
        child = getattr(self, child_name)
        parent = getattr(self, parent_name)
        if _was_reached(child) and not _was_reached(parent):
            raise ValueError(
                f"{child_name} cannot be reached unless {parent_name} was "
                "reached"
            )


class PostgresWriteSideMeasurementAvailability(str, Enum):
    """Classify final Level-A artifact availability after normal producer return.

    ``AVAILABLE`` requires one valid immutable measurement snapshot.
    ``UNAVAILABLE`` is reserved for narrowly measurement-owned final
    construction failure after the exact producer value and transaction
    finalization are already established.

    This state does not classify existing producer exceptions, commit
    ambiguity, persistence, or business success.
    """

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class PostgresWriteSideMeasurementDelivery:
    """Deliver an exact producer value before its measurement availability.

    Args:
        producer_value: Exact object returned normally by an existing legacy or
            traced PostgreSQL write API.
        availability: Whether final Level-A construction succeeded.
        measurement: Immutable snapshot when available; otherwise ``None``.

    Invariants:
        ``producer_value`` is a ``PostgresWriteSideResult`` or
        ``PostgresWriteSideExecution``. ``AVAILABLE`` pairs with a valid
        snapshot, while ``UNAVAILABLE`` pairs with ``None``.

    Failure behavior:
        Construction rejects invalid producer types and incoherent availability
        pairs. A future measured API must keep this final construction inside
        the narrow post-producer measurement-owned boundary.

    Non-goals:
        The envelope does not reinterpret, copy, or validate nested producer
        semantics. It does not convert existing exceptions into unavailable
        measurement, persist evidence, or change trace behavior.
    """

    producer_value: PostgresWriteSideResult | PostgresWriteSideExecution
    availability: PostgresWriteSideMeasurementAvailability
    measurement: PostgresWriteSideMeasurement | None

    def __post_init__(self) -> None:
        """Validate result-first type and availability coherence."""
        if not isinstance(
            self.producer_value,
            (PostgresWriteSideResult, PostgresWriteSideExecution),
        ):
            raise TypeError(
                "producer_value must be PostgresWriteSideResult or "
                "PostgresWriteSideExecution"
            )
        if not isinstance(
            self.availability,
            PostgresWriteSideMeasurementAvailability,
        ):
            raise TypeError(
                "availability must be PostgresWriteSideMeasurementAvailability"
            )

        if (
            self.availability
            is PostgresWriteSideMeasurementAvailability.AVAILABLE
        ):
            if not isinstance(self.measurement, PostgresWriteSideMeasurement):
                raise TypeError(
                    "measurement must be PostgresWriteSideMeasurement when "
                    "availability is AVAILABLE"
                )
            return

        if self.measurement is not None:
            raise ValueError(
                "measurement must be None when availability is UNAVAILABLE"
            )


def _was_reached(measurement: PostgresWriteSidePhaseMeasurement) -> bool:
    """Return whether execution reached the represented bounded phase."""
    return measurement.state in _REACHED_STATES
