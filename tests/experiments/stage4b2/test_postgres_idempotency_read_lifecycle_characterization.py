from __future__ import annotations

from collections import Counter
from dataclasses import fields, replace

import pytest

from experiments.stage4b2 import (
    postgres_idempotency_read_lifecycle_characterization as layer3,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ALL_CONTROLS,
    RECORDED_ROUNDS,
    ControlAIdleRollbackAggregate,
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleAggregate,
    ControlBPreliminaryReadLifecycleSample,
    DescriptiveStatistics,
    IdempotencyVerdictIdentity,
    Layer3Control,
    Layer3Error,
    Layer3Schedule,
    RunValidity,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    schedule_control_counts,
    validate_run,
)


def _sample(plan, *, elapsed_offset=0):
    if plan.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
        return ControlAIdleRollbackSample(
            control=plan.control,
            sample_index=plan.sample_index,
            round_index=plan.round_index,
            status_before_cleanup=TransactionStatusIdentity.IDLE,
            cleanup_elapsed_ns=10 + elapsed_offset,
            status_after_cleanup=TransactionStatusIdentity.IDLE,
        )
    return ControlBPreliminaryReadLifecycleSample(
        control=plan.control,
        sample_index=plan.sample_index,
        round_index=plan.round_index,
        returned_idempotency_verdict=IdempotencyVerdictIdentity.MISS,
        history_count=0,
        idempotency_check_elapsed_ns=20 + elapsed_offset,
        accepted_history_load_elapsed_ns=30 + elapsed_offset,
        cleanup_elapsed_ns=40 + elapsed_offset,
        lifecycle_elapsed_ns=150 + elapsed_offset,
        status_before_check=TransactionStatusIdentity.IDLE,
        status_after_check=TransactionStatusIdentity.INTRANS,
        status_after_history=TransactionStatusIdentity.INTRANS,
        status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
    )


def _valid_samples():
    return tuple(_sample(plan) for plan in generate_recorded_schedule().samples)


def test_model_defines_exactly_two_controls() -> None:
    assert tuple(control.value for control in Layer3Control) == (
        "CONTROL_A_IDLE_ROLLBACK",
        "CONTROL_B_PRELIMINARY_READ_LIFECYCLE",
    )
    assert ALL_CONTROLS == tuple(Layer3Control)


def test_fixed_schedule_is_30_rounds_60_samples_and_30_per_control() -> None:
    schedule = generate_recorded_schedule()

    assert RECORDED_ROUNDS == 30
    assert len(schedule.samples) == 60
    assert schedule_control_counts(schedule) == {
        control: 30 for control in ALL_CONTROLS
    }
    assert Counter(plan.round_index for plan in schedule.samples) == {
        round_index: 2 for round_index in range(30)
    }


def test_fixed_schedule_order_is_deterministic_a_then_b_per_round() -> None:
    first = generate_recorded_schedule()
    second = generate_recorded_schedule()

    assert first == second
    assert tuple(plan.sample_index for plan in first.samples) == tuple(range(60))
    for round_index in range(30):
        plans = first.samples[round_index * 2 : (round_index + 1) * 2]
        assert tuple(plan.round_index for plan in plans) == (
            round_index,
            round_index,
        )
        assert tuple(plan.control for plan in plans) == ALL_CONTROLS


def test_schedule_rejects_extension_reordering_or_replacement() -> None:
    schedule = generate_recorded_schedule()

    with pytest.raises(ValueError, match="fixed Layer-3 plan"):
        Layer3Schedule(schedule.samples + (schedule.samples[0],))
    with pytest.raises(ValueError, match="fixed Layer-3 plan"):
        Layer3Schedule(tuple(reversed(schedule.samples)))
    with pytest.raises(ValueError, match="fixed Layer-3 plan"):
        Layer3Schedule(schedule.samples[:-1])


def test_control_a_sample_contract_contains_only_cleanup_lifecycle_fields() -> None:
    assert tuple(field.name for field in fields(ControlAIdleRollbackSample)) == (
        "control",
        "sample_index",
        "round_index",
        "status_before_cleanup",
        "cleanup_elapsed_ns",
        "status_after_cleanup",
        "exception_type",
    )


def test_control_b_contract_has_direct_lifecycle_without_synthetic_total() -> None:
    names = {field.name for field in fields(ControlBPreliminaryReadLifecycleSample)}

    assert {
        "returned_idempotency_verdict",
        "history_count",
        "idempotency_check_elapsed_ns",
        "accepted_history_load_elapsed_ns",
        "cleanup_elapsed_ns",
        "lifecycle_elapsed_ns",
        "status_before_check",
        "status_after_check",
        "status_after_history",
        "status_after_cleanup",
        "reuse_select_succeeded",
        "final_transaction_status",
        "exception_type",
    } <= names
    assert "database_time_ns" not in names
    assert "component_sum_ns" not in names


def test_exact_30_30_valid_accounting_is_valid() -> None:
    validation = validate_run(generate_recorded_schedule(), _valid_samples())

    assert validation.validity is RunValidity.VALID
    assert validation.issues == ()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "status_before_cleanup",
            TransactionStatusIdentity.INTRANS,
            "CONTROL_A_BEFORE_STATUS_MISMATCH",
        ),
        ("cleanup_elapsed_ns", None, "MISSING_OR_INVALID_TIMING"),
        ("cleanup_elapsed_ns", -1, "MISSING_OR_INVALID_TIMING"),
        (
            "status_after_cleanup",
            TransactionStatusIdentity.INTRANS,
            "CONTROL_A_AFTER_STATUS_MISMATCH",
        ),
        ("exception_type", "RuntimeError", "UNEXPECTED_EXCEPTION"),
    ),
)
def test_control_a_invalid_evidence_invalidates_run(field, value, code) -> None:
    schedule = generate_recorded_schedule()
    samples = list(_valid_samples())
    samples[0] = replace(samples[0], **{field: value})

    validation = validate_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert code in {issue.code for issue in validation.issues}


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "returned_idempotency_verdict",
            IdempotencyVerdictIdentity.REPLAY,
            "CONTROL_B_VERDICT_MISMATCH",
        ),
        ("history_count", 1, "CONTROL_B_HISTORY_NOT_EMPTY"),
        (
            "status_before_check",
            TransactionStatusIdentity.INTRANS,
            "CONTROL_B_BEFORE_STATUS_MISMATCH",
        ),
        (
            "status_after_check",
            TransactionStatusIdentity.IDLE,
            "CONTROL_B_AFTER_CHECK_STATUS_MISMATCH",
        ),
        (
            "status_after_history",
            TransactionStatusIdentity.IDLE,
            "CONTROL_B_AFTER_HISTORY_STATUS_MISMATCH",
        ),
        (
            "status_after_cleanup",
            TransactionStatusIdentity.INTRANS,
            "CONTROL_B_AFTER_CLEANUP_STATUS_MISMATCH",
        ),
        ("reuse_select_succeeded", False, "CONTROL_B_REUSE_FAILED"),
        (
            "final_transaction_status",
            TransactionStatusIdentity.INTRANS,
            "CONTROL_B_FINAL_STATUS_MISMATCH",
        ),
        ("idempotency_check_elapsed_ns", None, "MISSING_OR_INVALID_TIMING"),
        ("accepted_history_load_elapsed_ns", -1, "MISSING_OR_INVALID_TIMING"),
        ("cleanup_elapsed_ns", None, "MISSING_OR_INVALID_TIMING"),
        ("lifecycle_elapsed_ns", -1, "MISSING_OR_INVALID_TIMING"),
        ("exception_type", "ValueError", "UNEXPECTED_EXCEPTION"),
    ),
)
def test_control_b_invalid_evidence_invalidates_run(field, value, code) -> None:
    schedule = generate_recorded_schedule()
    samples = list(_valid_samples())
    samples[1] = replace(samples[1], **{field: value})

    validation = validate_run(schedule, samples)

    assert validation.validity is RunValidity.INVALID
    assert code in {issue.code for issue in validation.issues}


def test_missing_duplicate_unplanned_and_reordered_samples_are_invalid() -> None:
    schedule = generate_recorded_schedule()
    samples = list(_valid_samples())

    missing = validate_run(schedule, samples[:-1])
    duplicate_samples = samples[:-1] + [samples[0]]
    duplicate = validate_run(schedule, duplicate_samples)
    unplanned_samples = samples.copy()
    unplanned_samples[-1] = replace(
        unplanned_samples[-1],
        sample_index=60,
        round_index=30,
    )
    unplanned = validate_run(schedule, unplanned_samples)
    reordered_samples = samples.copy()
    reordered_samples[0], reordered_samples[1] = (
        reordered_samples[1],
        reordered_samples[0],
    )
    reordered = validate_run(schedule, reordered_samples)

    assert "MISSING_SAMPLE_COORDINATE" in {
        issue.code for issue in missing.issues
    }
    assert "DUPLICATE_SAMPLE_COORDINATE" in {
        issue.code for issue in duplicate.issues
    }
    assert "UNPLANNED_SAMPLE_COORDINATE" in {
        issue.code for issue in unplanned.issues
    }
    assert "SAMPLE_ORDER_MISMATCH" in {
        issue.code for issue in reordered.issues
    }


def test_aggregates_remain_two_controls_with_independent_accepted_fields() -> None:
    schedule = generate_recorded_schedule()
    samples = tuple(
        _sample(plan, elapsed_offset=plan.round_index)
        for plan in schedule.samples
    )

    control_a, control_b = aggregate_recorded_samples(samples)

    assert isinstance(control_a, ControlAIdleRollbackAggregate)
    assert isinstance(control_b, ControlBPreliminaryReadLifecycleAggregate)
    assert control_a.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK
    assert (
        control_b.control
        is Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE
    )
    assert control_a.cleanup_elapsed_ns.count == 30
    assert control_b.idempotency_check_elapsed_ns.count == 30
    assert control_b.accepted_history_load_elapsed_ns.count == 30
    assert control_b.cleanup_elapsed_ns.count == 30
    assert control_b.lifecycle_elapsed_ns.count == 30
    assert tuple(field.name for field in fields(DescriptiveStatistics)) == (
        "count",
        "minimum_ns",
        "mean_ns",
        "median_ns",
        "maximum_ns",
    )
    assert not hasattr(control_a, "p95")
    assert not hasattr(control_b, "p95")
    assert not hasattr(control_b, "database_time_ns")
    assert not hasattr(control_b, "component_sum_ns")
    assert not hasattr(control_a, "pooled_score")
    assert not hasattr(control_b, "strategy_winner")


def test_invalid_recorded_samples_cannot_be_aggregated() -> None:
    with pytest.raises(Layer3Error, match="invalid Layer-3"):
        aggregate_recorded_samples(_valid_samples()[:-1])


def test_model_has_no_counterfactual_or_strategy_selection_identity() -> None:
    assert not hasattr(layer3, "PRE_NO_PRELIMINARY")
    assert not hasattr(layer3, "IN_OCC")
    assert not hasattr(layer3, "Strategy")
    assert not hasattr(layer3, "StrategyWinner")
