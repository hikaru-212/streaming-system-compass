"""Deterministic, non-PostgreSQL tests for Stage 4B.2 PR6 infrastructure."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

import experiments.stage4b2.postgres_strategy_comparison as comparison_module
from experiments.stage4b2.postgres_strategy_comparison import (
    BASELINE_PROVENANCE_PATH,
    BASELINE_SOURCE_PATH,
    DEFAULT_BASELINE_MODULE_NAME,
    EXPECTED_BASELINE_GIT_BLOB,
    EXPECTED_BASELINE_SHA256,
    FIXED_PR6_WORKER_COUNT,
    PR3_PHASE_NAMES,
    AggregateResult,
    BaselineIntegrityError,
    Cohort,
    Composition,
    EvidenceStatus,
    ExperimentSample,
    ExperimentSchedule,
    PhaseRecord,
    PhaseState,
    PostgresPreflightResult,
    PreflightError,
    PreflightCellResult,
    ProtocolConfig,
    RejectionStage,
    SamplePlan,
    Scenario,
    Surface,
    UnsupportedCohortError,
    aggregate_paired_differences,
    aggregate_samples,
    aggregates_to_json,
    build_environment_manifest,
    classify_cohort,
    deterministic_sample_token,
    format_postgres_preflight,
    generate_concurrent_batch_schedule,
    generate_recorded_schedule,
    generate_sequential_observer_schedule,
    is_derived_scenario_d,
    load_frozen_baseline,
    manifest_to_dict,
    manifest_to_json,
    preflight_surface_order,
    sample_from_dict,
    sample_to_dict,
    samples_from_jsonl,
    samples_to_jsonl,
    time_after_start_gate,
    time_public_invocation,
    unload_frozen_baseline,
    validate_recorded_run,
    verify_baseline_fixture,
    _require_strict_full_proof_validation,
)
from src.compass.transition.types import (
    ValidationMode,
    ValidationResult,
    ValidationVerdict,
)


def _small_protocol(*, b_batches: int = 2, b_minimum: int = 1) -> ProtocolConfig:
    return ProtocolConfig(
        sequential_warmup_cycles=1,
        concurrent_warmup_batches_per_composition=1,
        observer_schedule_repetitions=1,
        scenario_a_samples_per_surface_per_composition=6,
        scenario_b_batches_per_composition=b_batches,
        scenario_c_batches_per_composition=1,
        scenario_e_samples=1,
        scenario_b_core_cohort_minimum=b_minimum,
    )


def _validation_result(
    *,
    mode: ValidationMode = ValidationMode.STRICT,
    validator_name: str = "FullProofValidator",
) -> ValidationResult:
    return ValidationResult(
        verdict=ValidationVerdict.PASSED,
        reason="Event passed full proof transition validation",
        candidate_event_id="preflight-candidate",
        validator_name=validator_name,
        validation_mode=mode,
        logic_validation_time_ms=0.0,
        io_time_ms=0.0,
        total_time_ms=0.0,
        metadata={},
    )


def test_preflight_strict_validation_uses_enum_identity_not_uppercase_value() -> None:
    assert ValidationMode.STRICT.value == "strict"

    _require_strict_full_proof_validation(_validation_result())


def test_preflight_strict_validation_rejects_non_strict_mode() -> None:
    with pytest.raises(PreflightError, match=r"ValidationMode\.STRICT"):
        _require_strict_full_proof_validation(
            _validation_result(mode=ValidationMode.OFF)
        )


def test_preflight_strict_validation_rejects_wrong_validator_name() -> None:
    with pytest.raises(PreflightError, match="FullProofValidator"):
        _require_strict_full_proof_validation(
            _validation_result(validator_name="NoOpValidator")
        )


def test_cli_reports_only_authored_preflight_error_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_preflight() -> PostgresPreflightResult:
        raise PreflightError("preflight CREATE did not use ValidationMode.STRICT")

    monkeypatch.setattr(
        comparison_module,
        "run_postgres_preflight_from_environment",
        fail_preflight,
    )

    with pytest.raises(SystemExit) as raised:
        comparison_module.main(["--preflight"])

    assert str(raised.value) == (
        "PR6 untimed preflight failed: "
        "preflight CREATE did not use ValidationMode.STRICT"
    )


def test_cli_retains_only_type_for_unknown_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_preflight() -> PostgresPreflightResult:
        raise RuntimeError("arbitrary exception detail must remain hidden")

    monkeypatch.setattr(
        comparison_module,
        "run_postgres_preflight_from_environment",
        fail_preflight,
    )

    with pytest.raises(
        SystemExit,
        match="PR6 untimed preflight failed: RuntimeError",
    ):
        comparison_module.main(["--preflight"])


def _phases(*, not_collected: str | None = None) -> tuple[PhaseRecord, ...]:
    return tuple(
        PhaseRecord(
            name=name,
            state=(
                PhaseState.NOT_COLLECTED
                if name == not_collected
                else PhaseState.MEASURED
            ),
            elapsed_ns=None if name == not_collected else index,
        )
        for index, name in enumerate(PR3_PHASE_NAMES)
    )


def _outcome_for_plan(
    plan: SamplePlan,
    *,
    force_b_accepted: bool = False,
) -> tuple[str, RejectionStage | None, str | None, str | None, Cohort | None]:
    if plan.scenario is Scenario.E_LOCK_NON_ACQUISITION:
        return (
            "ADMISSION_REJECTED",
            RejectionStage.PREPARE_STREAM,
            "LOCK_TIMEOUT",
            None,
            Cohort.PREPARE_LOCK_TIMEOUT,
        )
    if plan.scenario is Scenario.B_SAME_ORDER and plan.lane_index == 1:
        if force_b_accepted:
            return "ACCEPTED", None, "ADMITTED", "ADMITTED", Cohort.ACCEPTED
        if plan.composition is Composition.PRE_OCC:
            return (
                "ADMISSION_REJECTED",
                RejectionStage.APPEND,
                "ADMITTED",
                "STALE_WRITE",
                Cohort.APPEND_STALE_WRITE,
            )
        return (
            "ADMISSION_REJECTED",
            RejectionStage.PREPARE_STREAM,
            "LOCK_TIMEOUT",
            None,
            Cohort.PREPARE_LOCK_TIMEOUT,
        )
    return "ACCEPTED", None, "ADMITTED", "ADMITTED", Cohort.ACCEPTED


def _sample_for_plan(
    plan: SamplePlan,
    *,
    force_b_accepted: bool = False,
    not_collected: str | None = None,
) -> ExperimentSample:
    outcome, stage, stream_verdict, append_verdict, cohort = _outcome_for_plan(
        plan,
        force_b_accepted=force_b_accepted,
    )
    measured = plan.surface is Surface.CURRENT_MEASURED
    return ExperimentSample(
        schema_version=1,
        run_id="unit-run",
        sample_index=plan.sample_index,
        block_index=plan.block_index,
        batch_index=plan.batch_index,
        lane_index=plan.lane_index,
        scenario=plan.scenario,
        composition=plan.composition,
        surface=plan.surface,
        command="CREATE",
        history_depth=0,
        expected_sequence=1,
        producer_outcome=outcome,
        rejection_stage=stage,
        stream_admission_verdict=stream_verdict,
        append_admission_verdict=append_verdict,
        cohort=cohort,
        measurement_availability="AVAILABLE" if measured else None,
        external_elapsed_ns=100 + plan.sample_index,
        start_offset_ns=(plan.lane_index if plan.scenario in {
            Scenario.B_SAME_ORDER,
            Scenario.C_DIFFERENT_ORDER,
        } else None),
        phases=_phases(not_collected=not_collected) if measured else None,
    )


def _exception_sample_for_plan(
    plan: SamplePlan,
    *,
    elapsed_ns: int = 25,
    exception_type: str = "RuntimeError",
) -> ExperimentSample:
    return ExperimentSample(
        schema_version=1,
        run_id="exception-run",
        sample_index=plan.sample_index,
        block_index=plan.block_index,
        batch_index=plan.batch_index,
        lane_index=plan.lane_index,
        scenario=plan.scenario,
        composition=plan.composition,
        surface=plan.surface,
        command="CREATE",
        history_depth=0,
        expected_sequence=1,
        producer_outcome=None,
        rejection_stage=None,
        stream_admission_verdict=None,
        append_admission_verdict=None,
        cohort=None,
        measurement_availability=None,
        external_elapsed_ns=elapsed_ns,
        start_offset_ns=(
            plan.lane_index
            if plan.scenario in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}
            else None
        ),
        phases=None,
        exception_type=exception_type,
    )


def _complete_run(
    protocol: ProtocolConfig,
    *,
    seed: int = 7,
    force_b_accepted: bool = False,
) -> tuple[ExperimentSchedule, list[ExperimentSample]]:
    schedule = generate_recorded_schedule(protocol=protocol, seed=seed)
    return schedule, [
        _sample_for_plan(plan, force_b_accepted=force_b_accepted)
        for plan in schedule.samples
    ]


def _accepted_sample(
    *,
    sample_index: int,
    batch_index: int,
    composition: Composition,
    elapsed_ns: int,
    surface: Surface = Surface.CURRENT_UNMEASURED,
) -> ExperimentSample:
    measured = surface is Surface.CURRENT_MEASURED
    return ExperimentSample(
        schema_version=1,
        run_id="aggregate-run",
        sample_index=sample_index,
        block_index=0,
        batch_index=batch_index,
        lane_index=0,
        scenario=Scenario.A_UNCONTENDED,
        composition=composition,
        surface=surface,
        command="CREATE",
        history_depth=0,
        expected_sequence=1,
        producer_outcome="ACCEPTED",
        rejection_stage=None,
        stream_admission_verdict="ADMITTED",
        append_admission_verdict="ADMITTED",
        cohort=Cohort.ACCEPTED,
        measurement_availability="AVAILABLE" if measured else None,
        external_elapsed_ns=elapsed_ns,
        start_offset_ns=None,
        phases=_phases() if measured else None,
    )


def test_sequential_schedule_is_seeded_reproducible_and_balanced() -> None:
    first = generate_sequential_observer_schedule(seed=19)
    second = generate_sequential_observer_schedule(seed=19)
    different = generate_sequential_observer_schedule(seed=20)

    assert first == second
    assert first != different
    assert len(first) == 5 * 6 * 3 * 2
    counts = Counter((plan.surface, plan.composition) for plan in first)
    assert set(counts.values()) == {30}


def test_all_six_observer_permutations_appear_once_per_repetition() -> None:
    schedule = generate_sequential_observer_schedule(seed=23, repetitions=1)
    observed_orders = []
    for batch_index in range(6):
        plans = [plan for plan in schedule if plan.batch_index == batch_index]
        observed_orders.append(
            tuple(dict.fromkeys(plan.surface for plan in plans))
        )

    assert len(set(observed_orders)) == 6
    assert all(len(order) == 3 for order in observed_orders)


def test_sequential_composition_first_order_is_balanced() -> None:
    schedule = generate_sequential_observer_schedule(seed=29)
    first_by_round_surface = []
    for batch_index in range(30):
        for surface in Surface:
            plans = [
                plan
                for plan in schedule
                if plan.batch_index == batch_index and plan.surface is surface
            ]
            first_by_round_surface.append(plans[0].composition)

    assert Counter(first_by_round_surface) == {
        Composition.PRE_OCC: 45,
        Composition.IN_PESSIMISTIC: 45,
    }


@pytest.mark.parametrize(
    "scenario",
    [Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER],
)
def test_concurrent_schedule_alternates_compositions_and_lane_connections(
    scenario: Scenario,
) -> None:
    schedule = generate_concurrent_batch_schedule(
        scenario=scenario,
        batches_per_composition=4,
    )
    batch_compositions = []
    lane_assignments = []
    for batch_index in range(8):
        plans = [plan for plan in schedule if plan.batch_index == batch_index]
        batch_compositions.append(plans[0].composition)
        lane_assignments.append(
            tuple(plan.connection_slot for plan in sorted(plans, key=lambda p: p.lane_index))
        )
        assert {plan.lane_index for plan in plans} == {0, 1}

    assert batch_compositions == [
        Composition.PRE_OCC,
        Composition.IN_PESSIMISTIC,
        Composition.IN_PESSIMISTIC,
        Composition.PRE_OCC,
        Composition.PRE_OCC,
        Composition.IN_PESSIMISTIC,
        Composition.IN_PESSIMISTIC,
        Composition.PRE_OCC,
    ]
    assert lane_assignments == [(0, 1), (1, 0)] * 4


def test_worker_count_is_fixed_at_two_and_no_sweep_is_configurable() -> None:
    assert ProtocolConfig().worker_count == FIXED_PR6_WORKER_COUNT == 2
    with pytest.raises(ValueError, match="fixed at 2"):
        ProtocolConfig(worker_count=3)


def test_recorded_schedule_has_unique_deterministic_sample_indexes() -> None:
    protocol = ProtocolConfig()
    schedule = generate_recorded_schedule(protocol=protocol, seed=31)
    indexes = [plan.sample_index for plan in schedule.samples]

    assert indexes == list(range(len(indexes)))
    assert len(indexes) == 180 + 120 + 120 + 30
    assert deterministic_sample_token(
        run_id="run-1", sample_index=7, lane_index=1, purpose="order"
    ) == deterministic_sample_token(
        run_id="run-1", sample_index=7, lane_index=1, purpose="order"
    )


def test_preflight_surface_order_proves_both_connection_reuse_directions() -> None:
    assert preflight_surface_order(Composition.PRE_OCC) == (
        Surface.FROZEN_BASELINE,
        Surface.CURRENT_UNMEASURED,
        Surface.CURRENT_MEASURED,
    )
    assert preflight_surface_order(Composition.IN_PESSIMISTIC) == (
        Surface.CURRENT_UNMEASURED,
        Surface.CURRENT_MEASURED,
        Surface.FROZEN_BASELINE,
    )


def test_preflight_result_contains_six_structural_cells_and_no_latency() -> None:
    cells = tuple(
        PreflightCellResult(
            surface=surface,
            composition=composition,
            accepted=True,
            expected_sequence_one=True,
            event_persisted=True,
            connection_idle=True,
            connection_reusable=True,
            measurement_available=(
                True if surface is Surface.CURRENT_MEASURED else None
            ),
            baseline_verified=(
                True if surface is Surface.FROZEN_BASELINE else None
            ),
        )
        for composition in Composition
        for surface in preflight_surface_order(composition)
    )
    result = PostgresPreflightResult(
        cells=cells,
        same_connection_sequential_reuse=True,
        frozen_current_compatible=True,
        canonical_pre_compatible=True,
        canonical_in_pessimistic_compatible=True,
        current_measured_available=True,
    )
    formatted = format_postgres_preflight(result)

    assert len(result.cells) == 6
    assert "elapsed" not in formatted.lower()
    assert "latency" not in formatted.lower()
    assert "recorded_comparison=NOT_STARTED" in formatted


def test_cohort_classifier_separates_accepted_stale_and_lock_timeout() -> None:
    assert classify_cohort(
        producer_outcome="ACCEPTED",
        rejection_stage=None,
        stream_admission_verdict="ADMITTED",
        append_admission_verdict="ADMITTED",
    ) is Cohort.ACCEPTED
    assert classify_cohort(
        producer_outcome="ADMISSION_REJECTED",
        rejection_stage=RejectionStage.APPEND,
        stream_admission_verdict="ADMITTED",
        append_admission_verdict="STALE_WRITE",
    ) is Cohort.APPEND_STALE_WRITE
    assert classify_cohort(
        producer_outcome="ADMISSION_REJECTED",
        rejection_stage=RejectionStage.PREPARE_STREAM,
        stream_admission_verdict="LOCK_TIMEOUT",
        append_admission_verdict=None,
    ) is Cohort.PREPARE_LOCK_TIMEOUT


@pytest.mark.parametrize(
    ("outcome", "stage", "stream_verdict", "append_verdict"),
    [
        ("REPLAY", None, None, None),
        ("CONFLICT", None, None, None),
        ("VALIDATION_BLOCKED", None, None, None),
        ("ACCEPTED", None, "LOCK_TIMEOUT", "ADMITTED"),
        ("ADMISSION_REJECTED", RejectionStage.APPEND, None, "STALE_WRITE"),
    ],
)
def test_unsupported_or_inconsistent_outcomes_do_not_become_latency_cohorts(
    outcome: str,
    stage: RejectionStage | None,
    stream_verdict: str | None,
    append_verdict: str | None,
) -> None:
    with pytest.raises(UnsupportedCohortError, match="not a retained"):
        classify_cohort(
            producer_outcome=outcome,
            rejection_stage=stage,
            stream_admission_verdict=stream_verdict,
            append_admission_verdict=append_verdict,
        )


def test_d_is_only_a_natural_pre_stale_interpretation_of_scenario_b() -> None:
    assert "D" not in {scenario.name for scenario in Scenario}
    plan = SamplePlan(
        sample_index=0,
        block_index=0,
        batch_index=0,
        lane_index=1,
        connection_slot=1,
        scenario=Scenario.B_SAME_ORDER,
        composition=Composition.PRE_OCC,
        surface=Surface.CURRENT_MEASURED,
    )
    stale = _sample_for_plan(plan)
    assert is_derived_scenario_d(stale)
    assert not is_derived_scenario_d(replace(stale, scenario=Scenario.A_UNCONTENDED))


def test_phase_and_sample_serialization_round_trip_preserves_null_rule() -> None:
    measured = _accepted_sample(
        sample_index=0,
        batch_index=0,
        composition=Composition.PRE_OCC,
        elapsed_ns=100,
        surface=Surface.CURRENT_MEASURED,
    )
    frozen = _accepted_sample(
        sample_index=1,
        batch_index=1,
        composition=Composition.PRE_OCC,
        elapsed_ns=90,
        surface=Surface.FROZEN_BASELINE,
    )
    payload = samples_to_jsonl([measured, frozen])

    assert len(payload.splitlines()) == 2
    assert samples_from_jsonl(payload) == (measured, frozen)
    assert sample_from_dict(sample_to_dict(measured)) == measured
    assert sample_to_dict(frozen)["phases"] is None
    assert sample_to_dict(frozen)["measurement_availability"] is None


def test_exception_sample_serializes_null_result_and_measurement_evidence() -> None:
    plan = SamplePlan(
        sample_index=0,
        block_index=0,
        batch_index=0,
        lane_index=0,
        connection_slot=0,
        scenario=Scenario.A_UNCONTENDED,
        composition=Composition.PRE_OCC,
        surface=Surface.CURRENT_MEASURED,
    )
    sample = _exception_sample_for_plan(plan, exception_type="RuntimeError")
    payload = samples_to_jsonl([sample])
    raw = json.loads(payload)

    assert raw["producer_outcome"] is None
    assert raw["cohort"] is None
    assert raw["measurement_availability"] is None
    assert raw["phases"] is None
    assert raw["exception_type"] == "RuntimeError"
    assert "message must not become evidence" not in payload
    assert samples_from_jsonl(payload) == (sample,)

    with pytest.raises(ValueError, match="invalid or unsupported"):
        aggregate_samples([sample])


def test_exception_sample_rejects_normal_result_or_measurement_claims() -> None:
    plan = SamplePlan(
        sample_index=0,
        block_index=0,
        batch_index=0,
        lane_index=0,
        connection_slot=0,
        scenario=Scenario.A_UNCONTENDED,
        composition=Composition.PRE_OCC,
        surface=Surface.CURRENT_MEASURED,
    )
    sample = _exception_sample_for_plan(plan)

    with pytest.raises(ValueError, match="null producer outcome"):
        replace(sample, producer_outcome="ACCEPTED")
    with pytest.raises(ValueError, match="no normal result or measurement"):
        replace(sample, measurement_availability="UNAVAILABLE")


def test_aggregation_retains_default_statistics_and_independent_phases() -> None:
    samples = [
        _accepted_sample(
            sample_index=index,
            batch_index=index,
            composition=Composition.PRE_OCC,
            elapsed_ns=value,
            surface=Surface.CURRENT_MEASURED,
        )
        for index, value in enumerate([10, 20, 30, 40])
    ]
    aggregates = aggregate_samples(samples)

    assert len(aggregates) == 1
    result: AggregateResult = aggregates[0]
    assert result.external_elapsed.count == 4
    assert result.external_elapsed.minimum_ns == 10
    assert result.external_elapsed.maximum_ns == 40
    assert result.external_elapsed.mean_ns == 25.0
    assert result.external_elapsed.median_ns == 25.0
    assert len(result.phases) == len(PR3_PHASE_NAMES)
    encoded = json.loads(aggregates_to_json(aggregates))
    assert "p95" not in json.dumps(encoded).lower()


def test_aggregation_never_pools_different_cohorts() -> None:
    accepted = _accepted_sample(
        sample_index=0,
        batch_index=0,
        composition=Composition.PRE_OCC,
        elapsed_ns=100,
        surface=Surface.CURRENT_MEASURED,
    )
    stale_plan = SamplePlan(
        sample_index=1,
        block_index=0,
        batch_index=1,
        lane_index=1,
        connection_slot=1,
        scenario=Scenario.B_SAME_ORDER,
        composition=Composition.PRE_OCC,
        surface=Surface.CURRENT_MEASURED,
    )
    stale = _sample_for_plan(stale_plan)

    assert len(aggregate_samples([accepted, stale])) == 2


def test_aggregation_never_pools_runs_or_expected_sequences() -> None:
    first = _accepted_sample(
        sample_index=0,
        batch_index=0,
        composition=Composition.PRE_OCC,
        elapsed_ns=100,
    )
    second_run = replace(first, sample_index=1, run_id="aggregate-run-2")
    second_sequence = replace(
        first,
        sample_index=2,
        expected_sequence=2,
    )

    aggregates = aggregate_samples([first, second_run, second_sequence])

    assert len(aggregates) == 3
    assert {result.run_id for result in aggregates} == {
        "aggregate-run",
        "aggregate-run-2",
    }
    assert {result.expected_sequence for result in aggregates} == {1, 2}


def test_paired_difference_aggregation_is_explicitly_in_minus_pre() -> None:
    samples = [
        _accepted_sample(
            sample_index=0,
            batch_index=0,
            composition=Composition.PRE_OCC,
            elapsed_ns=10,
        ),
        _accepted_sample(
            sample_index=1,
            batch_index=0,
            composition=Composition.IN_PESSIMISTIC,
            elapsed_ns=14,
        ),
        _accepted_sample(
            sample_index=2,
            batch_index=1,
            composition=Composition.PRE_OCC,
            elapsed_ns=20,
        ),
        _accepted_sample(
            sample_index=3,
            batch_index=1,
            composition=Composition.IN_PESSIMISTIC,
            elapsed_ns=30,
        ),
    ]
    result = aggregate_paired_differences(samples)[0]

    assert result.count == 2
    assert result.mean_in_minus_pre_ns == 7.0
    assert result.median_in_minus_pre_ns == 7.0


def test_complete_fixed_run_validates_without_adaptive_sampling() -> None:
    protocol = _small_protocol(b_batches=2, b_minimum=1)
    schedule, samples = _complete_run(protocol)

    result = validate_recorded_run(
        samples=samples,
        schedule=schedule,
        protocol=protocol,
    )
    assert result.status is EvidenceStatus.VALID
    assert result.issues == ()


def test_missing_sample_and_incomplete_block_are_invalid() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    samples.pop(0)

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    codes = {issue.code for issue in result.issues}
    assert result.status is EvidenceStatus.INVALID_RUN
    assert {"MISSING_SAMPLE", "INCOMPLETE_MATCHED_BLOCK"} <= codes


def test_duplicate_sample_is_invalid() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    samples.append(samples[0])

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert result.status is EvidenceStatus.INVALID_RUN
    assert "DUPLICATE_SAMPLE" in {issue.code for issue in result.issues}


def test_measurement_unavailable_and_required_not_collected_are_invalid() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    measured_index = next(
        index
        for index, sample in enumerate(samples)
        if sample.surface is Surface.CURRENT_MEASURED
        and sample.composition is Composition.PRE_OCC
        and sample.cohort is Cohort.ACCEPTED
    )
    unavailable = replace(
        samples[measured_index],
        measurement_availability="UNAVAILABLE",
        phases=None,
    )
    samples[measured_index] = unavailable
    unavailable_result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert "MEASUREMENT_UNAVAILABLE" in {
        issue.code for issue in unavailable_result.issues
    }

    schedule, samples = _complete_run(protocol)
    original = samples[measured_index]
    samples[measured_index] = replace(
        original,
        phases=_phases(not_collected="producer_write_invocation"),
    )
    not_collected_result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert "REQUIRED_PHASE_NOT_COLLECTED" in {
        issue.code for issue in not_collected_result.issues
    }


def test_unexpected_exception_marker_invalidates_run() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    samples[0] = _exception_sample_for_plan(
        schedule.samples[0],
        exception_type="ValueError",
    )

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert result.status is EvidenceStatus.INVALID_RUN
    codes = {issue.code for issue in result.issues}
    assert "UNEXPECTED_EXCEPTION" in codes
    assert "MEASUREMENT_UNAVAILABLE" not in codes


def test_scenario_specific_cohort_is_enforced() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    c_index = next(
        index
        for index, sample in enumerate(samples)
        if sample.scenario is Scenario.C_DIFFERENT_ORDER
        and sample.composition is Composition.IN_PESSIMISTIC
    )
    samples[c_index] = replace(
        samples[c_index],
        producer_outcome="ADMISSION_REJECTED",
        rejection_stage=RejectionStage.PREPARE_STREAM,
        stream_admission_verdict="LOCK_TIMEOUT",
        append_admission_verdict=None,
        cohort=Cohort.PREPARE_LOCK_TIMEOUT,
    )

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )

    assert result.status is EvidenceStatus.INVALID_RUN
    assert "UNEXPECTED_SCENARIO_COHORT" in {
        issue.code for issue in result.issues
    }


def test_fixed_run_insufficiency_does_not_extend_schedule() -> None:
    protocol = _small_protocol(b_batches=2, b_minimum=2)
    schedule, samples = _complete_run(protocol, force_b_accepted=True)
    planned_count = len(schedule.samples)

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert result.status is EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert len(schedule.samples) == planned_count
    assert "SCENARIO_B_COHORT_INSUFFICIENT" in {
        issue.code for issue in result.issues
    }


def test_unplanned_extra_sample_is_adaptive_extension_and_invalid() -> None:
    protocol = _small_protocol()
    schedule, samples = _complete_run(protocol)
    samples.append(replace(samples[-1], sample_index=len(schedule.samples)))

    result = validate_recorded_run(
        samples=samples, schedule=schedule, protocol=protocol
    )
    assert result.status is EvidenceStatus.INVALID_RUN
    assert "RECORDED_COUNT_EXCEEDED" in {issue.code for issue in result.issues}


def test_invalid_worker_count_and_unbalanced_schedule_are_detected() -> None:
    protocol = _small_protocol()
    schedule = generate_recorded_schedule(protocol=protocol, seed=5)
    malformed = ExperimentSchedule(
        seed=schedule.seed,
        worker_count=3,
        samples=schedule.samples[:-1],
    )
    samples = [_sample_for_plan(plan) for plan in malformed.samples]

    result = validate_recorded_run(
        samples=samples, schedule=malformed, protocol=protocol
    )
    codes = {issue.code for issue in result.issues}
    assert result.status is EvidenceStatus.INVALID_RUN
    assert "INVALID_WORKER_COUNT" in codes
    assert "UNBALANCED_COMPOSITION_SCHEDULE" in codes


def test_external_timer_excludes_setup_and_classification_callbacks() -> None:
    events: list[str] = []
    readings = iter([100, 145])

    def setup() -> None:
        events.append("setup")

    def clock() -> int:
        events.append("clock")
        return next(readings)

    def invocation() -> str:
        events.append("invoke")
        return "producer-value"

    setup()
    timed = time_public_invocation(invocation, clock=clock)
    events.append("classify")

    assert timed.value == "producer-value"
    assert timed.elapsed_ns == 45
    assert timed.exception_type is None
    assert events == ["setup", "clock", "invoke", "clock", "classify"]


def test_ordinary_exception_reads_stop_clock_and_retains_only_type() -> None:
    events: list[str] = []
    readings = iter([200, 260])

    def invocation() -> object:
        events.append("invoke")
        raise RuntimeError("message must not become evidence")

    timed = time_public_invocation(
        invocation,
        clock=lambda: events.append("clock") or next(readings),
    )

    assert timed.value is None
    assert timed.elapsed_ns == 60
    assert timed.exception_type == "RuntimeError"
    assert events == ["clock", "invoke", "clock"]


@pytest.mark.parametrize(
    "process_control_exception",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_process_control_base_exceptions_are_not_swallowed(
    process_control_exception: type[BaseException],
) -> None:
    events: list[str] = []
    readings = iter([10, 20])

    def invocation() -> object:
        events.append("invoke")
        raise process_control_exception()

    with pytest.raises(process_control_exception):
        time_public_invocation(
            invocation,
            clock=lambda: events.append("clock") or next(readings),
        )

    assert events == ["clock", "invoke"]


def test_start_gate_wait_occurs_before_external_timer() -> None:
    events: list[str] = []
    readings = iter([10, 20])

    timed = time_after_start_gate(
        wait_for_start=lambda: events.append("barrier"),
        invocation=lambda: events.append("invoke") or "ok",
        clock=lambda: events.append("clock") or next(readings),
    )

    assert timed.elapsed_ns == 10
    assert events == ["barrier", "clock", "invoke", "clock"]


def test_exception_after_start_gate_still_times_only_the_invocation() -> None:
    events: list[str] = []
    readings = iter([50, 75])

    def invocation() -> object:
        events.append("invoke")
        raise ValueError("not serialized")

    timed = time_after_start_gate(
        wait_for_start=lambda: events.append("barrier"),
        invocation=invocation,
        clock=lambda: events.append("clock") or next(readings),
    )

    assert timed.exception_type == "ValueError"
    assert timed.elapsed_ns == 25
    assert events == ["barrier", "clock", "invoke", "clock"]


def test_baseline_hash_and_historical_provenance_match() -> None:
    provenance = verify_baseline_fixture()

    assert provenance.sha256 == EXPECTED_BASELINE_SHA256
    assert provenance.git_blob == EXPECTED_BASELINE_GIT_BLOB
    assert BASELINE_SOURCE_PATH.suffix == ".source"


def test_baseline_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    changed_source = tmp_path / BASELINE_SOURCE_PATH.name
    changed_source.write_bytes(BASELINE_SOURCE_PATH.read_bytes() + b"\n# changed\n")

    with pytest.raises(BaselineIntegrityError, match="SHA-256"):
        verify_baseline_fixture(
            source_path=changed_source,
            provenance_path=BASELINE_PROVENANCE_PATH,
        )


def test_baseline_loads_in_isolated_nonproduction_namespace() -> None:
    module_name = f"{DEFAULT_BASELINE_MODULE_NAME}_unit_test"
    loaded = load_frozen_baseline(module_name=module_name)
    try:
        assert loaded.module_name == module_name
        assert module_name in sys.modules
        assert loaded.module.PostgresTransactionalWriteSide.__module__ == module_name
        assert loaded.module_name != "src.pipeline.transactional.postgres_write_side"
    finally:
        unload_frozen_baseline(loaded)
    assert module_name not in sys.modules


def test_manifest_is_sanitized_and_preserves_before_run_clean_semantics() -> None:
    manifest = build_environment_manifest(
        source_commit="a" * 40,
        source_tree_clean_before_run=True,
        topology_label="dedicated_local_test",
        schema_or_migration_identity="migrations-through-005",
        isolation_level="READ_COMMITTED",
        autocommit=False,
        connection_arrangement="one lane-owned connection per fixed worker",
        schedule_seed=41,
        protocol=_small_protocol(),
        postgresql_server_version=None,
        psycopg_version="3.test",
        python_implementation="CPython",
        python_version="3.test",
        platform="TestOS",
        architecture="test-arch",
    )
    payload = manifest_to_dict(manifest)
    encoded = manifest_to_json(manifest)

    assert payload["source_tree_clean_before_run"] is True
    assert "clean_tree" not in payload
    assert payload["postgresql_server_version"] is None
    assert payload["worker_count"] == 2
    forbidden_keys = {
        "dsn", "test_database_url", "database_name", "host", "port",
        "username", "password", "hostname", "credentials",
    }
    assert forbidden_keys.isdisjoint(payload)
    assert not any(token in encoded.lower() for token in ["postgresql://", "password="])


def test_manifest_rejects_secret_shaped_metadata() -> None:
    with pytest.raises(ValueError, match="secret-shaped"):
        build_environment_manifest(
            source_commit="a" * 40,
            source_tree_clean_before_run=True,
            topology_label="postgresql://private-host/test",
            schema_or_migration_identity="migrations-through-005",
            isolation_level="READ_COMMITTED",
            autocommit=False,
            connection_arrangement="fixed lanes",
            schedule_seed=43,
            protocol=_small_protocol(),
            psycopg_version="3.test",
        )
