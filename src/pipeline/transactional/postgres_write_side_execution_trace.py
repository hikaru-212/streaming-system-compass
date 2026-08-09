"""Immutable execution-topology evidence for the PostgreSQL write side."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.pipeline.transactional.postgres_write_side_config import (
    ValidationPlacement,
)


class PostgresWriteSideExecutionCheckpoint(str, Enum):
    """Identify one bounded write-side operation that returned normally.

    Checkpoints preserve execution topology only. A ``*_RETURNED`` value says
    that the named bounded operation returned normally; it does not assert that
    any returned result was favorable. In particular, concurrency preparation
    does not prove lock acquisition, and append admission does not prove event
    insertion or committed durability.

    ``IDEMPOTENCY_PERSISTENCE_RETURNED`` means only that
    ``PostgresIdempotencyStore.record(...)`` returned normally inside the
    current business transaction. It does not establish transaction commit,
    durable idempotency authority, cross-transaction visibility, or successful
    primary-result delivery.
    """

    PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED = (
        "PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED"
    )
    ACCEPTED_HISTORY_OBSERVED = "ACCEPTED_HISTORY_OBSERVED"
    VALIDATION_RETURNED = "VALIDATION_RETURNED"
    BUSINESS_UOW_REACHED = "BUSINESS_UOW_REACHED"
    AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED = (
        "AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED"
    )
    CONCURRENCY_PREPARATION_RETURNED = "CONCURRENCY_PREPARATION_RETURNED"
    APPEND_ADMISSION_RETURNED = "APPEND_ADMISSION_RETURNED"
    IDEMPOTENCY_PERSISTENCE_RETURNED = "IDEMPOTENCY_PERSISTENCE_RETURNED"


_PRE_TRANSACTION_CHECKPOINTS = (
    PostgresWriteSideExecutionCheckpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    PostgresWriteSideExecutionCheckpoint.ACCEPTED_HISTORY_OBSERVED,
    PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.BUSINESS_UOW_REACHED,
    PostgresWriteSideExecutionCheckpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    PostgresWriteSideExecutionCheckpoint.CONCURRENCY_PREPARATION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)

_IN_TRANSACTION_CHECKPOINTS = (
    PostgresWriteSideExecutionCheckpoint.BUSINESS_UOW_REACHED,
    PostgresWriteSideExecutionCheckpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    PostgresWriteSideExecutionCheckpoint.CONCURRENCY_PREPARATION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.ACCEPTED_HISTORY_OBSERVED,
    PostgresWriteSideExecutionCheckpoint.VALIDATION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.APPEND_ADMISSION_RETURNED,
    PostgresWriteSideExecutionCheckpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)


@dataclass(frozen=True)
class PostgresWriteSideExecutionTrace:
    """Preserve ordered topology for one PostgreSQL write-side execution.

    Args:
        validation_placement: Actual placement selected by write-side
            orchestration for this execution.
        checkpoints: Non-empty immutable prefix of the canonical checkpoint
            order for ``validation_placement``.

    Invariants:
        Every checkpoint is typed, appears at most once, and follows the
        canonical order for PRE_TRANSACTION or IN_TRANSACTION execution. The
        final tuple member is the derived terminal checkpoint.

    Failure behavior:
        Construction rejects invalid field types, empty or duplicate
        checkpoints, and checkpoint sequences that are not canonical prefixes.

    Non-goals:
        This trace does not preserve primary outcomes, verdicts, reasons,
        payloads, strategy or lock evidence, exception details, transaction
        durability, retry governance, policy, timing, or cost evidence. It also
        does not define result/trace delivery or coherence.
    """

    validation_placement: ValidationPlacement
    checkpoints: tuple[PostgresWriteSideExecutionCheckpoint, ...]

    def __post_init__(self) -> None:
        """Validate immutable structural evidence without result semantics."""
        if not isinstance(self.validation_placement, ValidationPlacement):
            raise TypeError("validation_placement must be ValidationPlacement")

        if type(self.checkpoints) is not tuple:
            raise TypeError("checkpoints must be tuple")
        if not self.checkpoints:
            raise ValueError("checkpoints must not be empty")
        if not all(
            isinstance(checkpoint, PostgresWriteSideExecutionCheckpoint)
            for checkpoint in self.checkpoints
        ):
            raise TypeError(
                "checkpoints must contain only "
                "PostgresWriteSideExecutionCheckpoint values"
            )
        if len(set(self.checkpoints)) != len(self.checkpoints):
            raise ValueError("checkpoints must not contain duplicates")

        canonical_checkpoints = _canonical_checkpoints_for(self.validation_placement)
        expected_prefix = canonical_checkpoints[: len(self.checkpoints)]
        if self.checkpoints != expected_prefix:
            raise ValueError(
                "checkpoints must be a canonical prefix for "
                f"{self.validation_placement.value}"
            )

    @property
    def terminal_checkpoint(self) -> PostgresWriteSideExecutionCheckpoint:
        """Return the final retained topology checkpoint in this trace.

        The value is derived from the non-empty checkpoint tuple and carries no
        independent primary-outcome or transaction-durability interpretation.
        It need not represent the physically final operation of the business
        transaction. On accepted paths, clean commit occurs after the final
        retained checkpoint and is owned by successful primary-result delivery.
        """
        return self.checkpoints[-1]


def _canonical_checkpoints_for(
    validation_placement: ValidationPlacement,
) -> tuple[PostgresWriteSideExecutionCheckpoint, ...]:
    if validation_placement is ValidationPlacement.PRE_TRANSACTION:
        return _PRE_TRANSACTION_CHECKPOINTS
    if validation_placement is ValidationPlacement.IN_TRANSACTION:
        return _IN_TRANSACTION_CHECKPOINTS
    raise ValueError(
        "unsupported validation placement: "
        f"{validation_placement.value}"
    )
