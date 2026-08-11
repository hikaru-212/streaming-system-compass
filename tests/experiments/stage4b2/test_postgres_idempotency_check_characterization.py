from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from experiments.stage4b2.postgres_idempotency_check_characterization import (
    ALL_CELLS,
    RECORDED_SAMPLES_PER_CELL,
    SCHEMA_VERSION,
    T_SETUP_SQL_IDENTITY,
    Layer2Cell,
    Layer2Context,
    Layer2Error,
    Layer2Sample,
    Layer2Schedule,
    Layer2StructuralSample,
    Layer2Verdict,
    RunValidity,
    ScheduleKind,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    generate_smoke_schedule,
    schedule_cell_counts,
    validate_run,
    validate_structural_run,
)


def _sample(plan, *, run_id="layer2-unit", elapsed_offset=0) -> Layer2Sample:
    return Layer2Sample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        sample_index=plan.sample_index,
        planned_context=plan.cell.context,
        planned_verdict=plan.cell.verdict,
        returned_verdict=plan.cell.verdict,
        check_elapsed_ns=100 + elapsed_offset,
        cleanup_elapsed_ns=20 + elapsed_offset,
        transaction_status_before_check=(
            TransactionStatusIdentity.INTRANS
            if plan.cell.context is Layer2Context.T
            else TransactionStatusIdentity.IDLE
        ),
        transaction_status_after_check=TransactionStatusIdentity.INTRANS,
        transaction_status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
    )


def _structural_sample(plan, *, identity="SELECT current check"):
    return Layer2StructuralSample(
        schema_version=SCHEMA_VERSION,
        run_id="layer2-structural-unit",
        sample_index=plan.sample_index,
        planned_context=plan.cell.context,
        planned_verdict=plan.cell.verdict,
        returned_verdict=plan.cell.verdict,
        transaction_status_before_check=(
            TransactionStatusIdentity.INTRANS
            if plan.cell.context is Layer2Context.T
            else TransactionStatusIdentity.IDLE
        ),
        transaction_status_after_check=TransactionStatusIdentity.INTRANS,
        transaction_status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
        check_sql_statement_count=1,
        normalized_check_sql_identities=(identity,),
        setup_sql_identity=(
            T_SETUP_SQL_IDENTITY
            if plan.cell.context is Layer2Context.T
            else None
        ),
    )


def test_context_identity_is_exactly_p_u_t() -> None:
    assert tuple(item.value for item in Layer2Context) == ("P", "U", "T")


def test_verdict_identity_is_exactly_miss_replay_conflict() -> None:
    assert tuple(item.value for item in Layer2Verdict) == (
        "MISS",
        "REPLAY",
        "CONFLICT",
    )


def test_factorial_contains_exactly_nine_cells_in_context_verdict_order() -> None:
    assert len(ALL_CELLS) == 9
    assert tuple(cell.identity for cell in ALL_CELLS) == (
        "P-MISS",
        "P-REPLAY",
        "P-CONFLICT",
        "U-MISS",
        "U-REPLAY",
        "U-CONFLICT",
        "T-MISS",
        "T-REPLAY",
        "T-CONFLICT",
    )


def test_smoke_schedule_is_exactly_one_sample_per_cell() -> None:
    schedule = generate_smoke_schedule()

    assert schedule.kind is ScheduleKind.SMOKE
    assert len(schedule.samples) == 9
    assert tuple(plan.cell for plan in schedule.samples) == ALL_CELLS
    assert set(schedule_cell_counts(schedule).values()) == {1}


def test_recorded_schedule_is_exactly_270_and_30_per_cell() -> None:
    schedule = generate_recorded_schedule()

    assert schedule.kind is ScheduleKind.RECORDED
    assert len(schedule.samples) == 270
    assert schedule_cell_counts(schedule) == {
        cell: RECORDED_SAMPLES_PER_CELL for cell in ALL_CELLS
    }


def test_recorded_schedule_order_is_deterministic_and_counterbalanced() -> None:
    first = generate_recorded_schedule()
    second = generate_recorded_schedule()

    assert first == second
    rounds = tuple(
        first.samples[offset : offset + len(ALL_CELLS)]
        for offset in range(0, len(first.samples), len(ALL_CELLS))
    )
    assert len(rounds) == 30
    assert all({plan.cell for plan in round_} == set(ALL_CELLS) for round_ in rounds)
    position_counts = {
        cell: Counter(
            position
            for round_ in rounds
            for position, plan in enumerate(round_)
            if plan.cell == cell
        )
        for cell in ALL_CELLS
    }
    assert all(
        set(counts.values()) <= {3, 4} and sum(counts.values()) == 30
        for counts in position_counts.values()
    )


def test_schedule_rejects_adaptive_extension_or_reordering() -> None:
    smoke = generate_smoke_schedule()

    with pytest.raises(ValueError, match="fixed Layer-2 plan"):
        Layer2Schedule(
            kind=ScheduleKind.SMOKE,
            samples=smoke.samples + (smoke.samples[0],),
        )

    with pytest.raises(ValueError, match="fixed Layer-2 plan"):
        Layer2Schedule(
            kind=ScheduleKind.SMOKE,
            samples=tuple(reversed(smoke.samples)),
        )


@pytest.mark.parametrize("context", tuple(Layer2Context))
def test_valid_context_status_shape(context: Layer2Context) -> None:
    plan = next(
        plan
        for plan in generate_smoke_schedule().samples
        if plan.cell == Layer2Cell(context, Layer2Verdict.MISS)
    )
    sample = _sample(plan)

    assert validate_run(
        Layer2Schedule(ScheduleKind.SMOKE, generate_smoke_schedule().samples),
        tuple(
            sample if candidate == plan else _sample(candidate)
            for candidate in generate_smoke_schedule().samples
        ),
    ).validity is RunValidity.VALID


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "transaction_status_before_check",
            TransactionStatusIdentity.INERROR,
            "BEFORE_STATUS_MISMATCH",
        ),
        (
            "transaction_status_after_check",
            TransactionStatusIdentity.IDLE,
            "AFTER_CHECK_STATUS_MISMATCH",
        ),
        (
            "transaction_status_after_cleanup",
            TransactionStatusIdentity.INTRANS,
            "AFTER_CLEANUP_STATUS_MISMATCH",
        ),
        ("reuse_select_succeeded", False, "REUSE_SELECT_FAILED"),
        (
            "final_transaction_status",
            TransactionStatusIdentity.INTRANS,
            "FINAL_STATUS_MISMATCH",
        ),
    ),
)
def test_transaction_lifecycle_mismatch_invalidates_run(field, value, code) -> None:
    schedule = generate_smoke_schedule()
    samples = [_sample(plan) for plan in schedule.samples]
    samples[0] = replace(samples[0], **{field: value})

    validation = validate_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert code in {issue.code for issue in validation.issues}


def test_returned_verdict_mismatch_invalidates_run() -> None:
    schedule = generate_smoke_schedule()
    samples = [_sample(plan) for plan in schedule.samples]
    samples[0] = replace(samples[0], returned_verdict=Layer2Verdict.REPLAY)

    validation = validate_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert "VERDICT_MISMATCH" in {issue.code for issue in validation.issues}


def test_unexpected_exception_invalidates_without_replacement() -> None:
    schedule = generate_smoke_schedule()
    samples = [_sample(plan) for plan in schedule.samples]
    samples[2] = replace(
        samples[2],
        returned_verdict=None,
        exception_type="RuntimeError",
    )

    validation = validate_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert len(samples) == 9
    assert "UNEXPECTED_EXCEPTION" in {issue.code for issue in validation.issues}


def test_missing_or_extra_sample_invalidates_run() -> None:
    schedule = generate_smoke_schedule()
    samples = tuple(_sample(plan) for plan in schedule.samples)

    missing = validate_run(schedule, samples[:-1])
    extra = validate_run(schedule, samples + (samples[-1],))

    assert missing.validity is RunValidity.INVALID
    assert extra.validity is RunValidity.INVALID
    assert "SAMPLE_COUNT_MISMATCH" in {issue.code for issue in missing.issues}
    assert "SAMPLE_COUNT_MISMATCH" in {issue.code for issue in extra.issues}


def test_primary_sample_rejects_structural_observation() -> None:
    plan = generate_smoke_schedule().samples[0]

    with pytest.raises(ValueError, match="cannot retain SQL tracing"):
        replace(
            _sample(plan),
            structural_sql_observation_identity="observed SQL",
        )


def test_structural_run_requires_one_identical_check_statement_per_cell() -> None:
    schedule = generate_smoke_schedule()
    samples = tuple(_structural_sample(plan) for plan in schedule.samples)

    assert validate_structural_run(schedule, samples).validity is RunValidity.VALID

    mismatched = list(samples)
    mismatched[-1] = replace(
        mismatched[-1],
        normalized_check_sql_identities=("SELECT different check",),
    )
    validation = validate_structural_run(schedule, mismatched)
    assert validation.validity is RunValidity.INVALID
    assert "CHECK_SQL_IDENTITY_MISMATCH" in {
        issue.code for issue in validation.issues
    }


def test_structural_run_rejects_missing_check_statement() -> None:
    schedule = generate_smoke_schedule()
    samples = [_structural_sample(plan) for plan in schedule.samples]
    samples[0] = replace(
        samples[0],
        check_sql_statement_count=0,
        normalized_check_sql_identities=(),
    )

    validation = validate_structural_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert "CHECK_SQL_COUNT_MISMATCH" in {issue.code for issue in validation.issues}


def test_aggregate_returns_exactly_nine_unpooled_cells_without_p95() -> None:
    schedule = generate_recorded_schedule()
    samples = tuple(
        _sample(plan, elapsed_offset=plan.sample_index)
        for plan in schedule.samples
    )

    aggregates = aggregate_recorded_samples(samples)

    assert tuple(aggregate.cell for aggregate in aggregates) == ALL_CELLS
    assert len(aggregates) == 9
    assert all(
        aggregate.check_elapsed_ns.count == RECORDED_SAMPLES_PER_CELL
        and aggregate.cleanup_elapsed_ns.count == RECORDED_SAMPLES_PER_CELL
        for aggregate in aggregates
    )
    assert all(not hasattr(aggregate, "p95") for aggregate in aggregates)
    assert all(not hasattr(aggregate, "context_score") for aggregate in aggregates)
    assert all(not hasattr(aggregate, "verdict_score") for aggregate in aggregates)


def test_invalid_recorded_samples_cannot_be_aggregated() -> None:
    schedule = generate_recorded_schedule()
    samples = tuple(_sample(plan) for plan in schedule.samples[:-1])

    with pytest.raises(Layer2Error, match="invalid Layer-2"):
        aggregate_recorded_samples(samples)
