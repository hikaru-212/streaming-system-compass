from dataclasses import FrozenInstanceError, fields

import pytest

from src.pipeline.transactional.postgres_write_side_config import (
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
    PostgresWriteSideExecutionTrace,
)


Checkpoint = PostgresWriteSideExecutionCheckpoint

PRE_CHECKPOINTS = (
    Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.ACCEPTED_HISTORY_OBSERVED,
    Checkpoint.VALIDATION_RETURNED,
    Checkpoint.BUSINESS_UOW_REACHED,
    Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    Checkpoint.APPEND_ADMISSION_RETURNED,
    Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)

IN_CHECKPOINTS = (
    Checkpoint.BUSINESS_UOW_REACHED,
    Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
    Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
    Checkpoint.ACCEPTED_HISTORY_OBSERVED,
    Checkpoint.VALIDATION_RETURNED,
    Checkpoint.APPEND_ADMISSION_RETURNED,
    Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
)


def test_checkpoint_enum_has_exact_public_vocabulary_and_excludes_clean_commit():
    expected_vocabulary = [
        "PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED",
        "ACCEPTED_HISTORY_OBSERVED",
        "VALIDATION_RETURNED",
        "BUSINESS_UOW_REACHED",
        "AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED",
        "CONCURRENCY_PREPARATION_RETURNED",
        "APPEND_ADMISSION_RETURNED",
        "IDEMPOTENCY_PERSISTENCE_RETURNED",
    ]

    assert [checkpoint.name for checkpoint in Checkpoint] == expected_vocabulary
    assert [checkpoint.value for checkpoint in Checkpoint] == expected_vocabulary
    assert not hasattr(Checkpoint, "CLEAN_COMMIT_RETURNED")


def test_trace_has_exact_stored_field_surface_and_derived_terminal():
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:3],
    )

    assert tuple(field.name for field in fields(trace)) == (
        "validation_placement",
        "checkpoints",
    )
    assert trace.terminal_checkpoint is Checkpoint.VALIDATION_RETURNED


def test_trace_is_frozen_and_hashable():
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:1],
    )

    with pytest.raises(FrozenInstanceError):
        setattr(trace, "checkpoints", PRE_CHECKPOINTS[:2])

    assert isinstance(hash(trace), int)
    assert trace.checkpoints == (Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,)


def test_trace_rejects_wrong_validation_placement_type():
    with pytest.raises(TypeError):
        PostgresWriteSideExecutionTrace(
            validation_placement="PRE_TRANSACTION",  # type: ignore[arg-type]
            checkpoints=PRE_CHECKPOINTS[:1],
        )


def test_trace_rejects_mutable_checkpoint_list():
    with pytest.raises(TypeError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
            checkpoints=list(PRE_CHECKPOINTS[:1]),  # type: ignore[arg-type]
        )


def test_trace_rejects_empty_checkpoint_tuple():
    with pytest.raises(ValueError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
            checkpoints=(),
        )


def test_trace_rejects_non_checkpoint_member():
    with pytest.raises(TypeError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
            checkpoints=("VALIDATION_RETURNED",),  # type: ignore[arg-type]
        )


def test_trace_rejects_duplicate_checkpoint():
    with pytest.raises(ValueError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
            checkpoints=(
                Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
                Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
            ),
        )


@pytest.mark.parametrize("prefix_length", range(1, len(PRE_CHECKPOINTS) + 1))
def test_trace_accepts_every_non_empty_pre_transaction_prefix(prefix_length):
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.PRE_TRANSACTION,
        checkpoints=PRE_CHECKPOINTS[:prefix_length],
    )

    assert trace.checkpoints == PRE_CHECKPOINTS[:prefix_length]
    assert trace.terminal_checkpoint is PRE_CHECKPOINTS[prefix_length - 1]


@pytest.mark.parametrize(
    "checkpoints",
    [
        (Checkpoint.BUSINESS_UOW_REACHED,),
        (
            Checkpoint.ACCEPTED_HISTORY_OBSERVED,
            Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
            Checkpoint.VALIDATION_RETURNED,
        ),
        (
            Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
            Checkpoint.ACCEPTED_HISTORY_OBSERVED,
            Checkpoint.BUSINESS_UOW_REACHED,
        ),
        (
            Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,
            Checkpoint.ACCEPTED_HISTORY_OBSERVED,
            Checkpoint.VALIDATION_RETURNED,
            Checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
        ),
        (
            *PRE_CHECKPOINTS[:5],
            Checkpoint.APPEND_ADMISSION_RETURNED,
        ),
    ],
)
def test_trace_rejects_noncanonical_pre_transaction_sequences(checkpoints):
    with pytest.raises(ValueError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
            checkpoints=checkpoints,
        )


@pytest.mark.parametrize("prefix_length", range(1, len(IN_CHECKPOINTS) + 1))
def test_trace_accepts_every_non_empty_in_transaction_prefix(prefix_length):
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=IN_CHECKPOINTS[:prefix_length],
    )

    assert trace.checkpoints == IN_CHECKPOINTS[:prefix_length]
    assert trace.terminal_checkpoint is IN_CHECKPOINTS[prefix_length - 1]


@pytest.mark.parametrize(
    ("validation_placement", "checkpoints"),
    [
        (ValidationPlacement.PRE_TRANSACTION, PRE_CHECKPOINTS),
        (ValidationPlacement.IN_TRANSACTION, IN_CHECKPOINTS),
    ],
)
def test_full_canonical_prefix_ends_at_idempotency_persistence(
    validation_placement,
    checkpoints,
):
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=validation_placement,
        checkpoints=checkpoints,
    )

    assert (
        trace.terminal_checkpoint
        is Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED
    )


@pytest.mark.parametrize(
    "checkpoints",
    [
        (Checkpoint.PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED,),
        (
            Checkpoint.BUSINESS_UOW_REACHED,
            Checkpoint.CONCURRENCY_PREPARATION_RETURNED,
        ),
        (
            *IN_CHECKPOINTS[:3],
            Checkpoint.VALIDATION_RETURNED,
        ),
        (
            *IN_CHECKPOINTS[:3],
            Checkpoint.VALIDATION_RETURNED,
            Checkpoint.ACCEPTED_HISTORY_OBSERVED,
        ),
        (
            *IN_CHECKPOINTS[:4],
            Checkpoint.APPEND_ADMISSION_RETURNED,
        ),
        (
            *IN_CHECKPOINTS[:4],
            Checkpoint.APPEND_ADMISSION_RETURNED,
            Checkpoint.VALIDATION_RETURNED,
        ),
        (
            *IN_CHECKPOINTS[:5],
            Checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
        ),
    ],
)
def test_trace_rejects_noncanonical_in_transaction_sequences(checkpoints):
    with pytest.raises(ValueError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
            checkpoints=checkpoints,
        )


def test_trace_excludes_result_policy_strategy_and_cost_responsibilities():
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=IN_CHECKPOINTS[:3],
    )
    forbidden_attributes = {
        "outcome",
        "verdict",
        "reason",
        "exception",
        "request_id",
        "candidate_event_id",
        "accepted_event_id",
        "source_global_position",
        "validation_mode",
        "strategy",
        "gate_class",
        "lock_attempted",
        "lock_acquired",
        "metadata",
        "decision_receipt",
        "semantic_outcome",
        "receipt_id",
        "outcome_id",
        "retry",
        "attempt",
        "attempt_number",
        "fallback",
        "policy",
        "action",
        "cost",
        "timing",
        "durability",
        "rollback",
        "rollback_disposition",
        "connection_disposition",
    }

    assert all(not hasattr(trace, name) for name in forbidden_attributes)


def test_trace_rejects_arbitrary_metadata():
    with pytest.raises(TypeError):
        PostgresWriteSideExecutionTrace(
            validation_placement=ValidationPlacement.IN_TRANSACTION,
            checkpoints=IN_CHECKPOINTS[:1],
            metadata={},  # type: ignore[call-arg]
        )
