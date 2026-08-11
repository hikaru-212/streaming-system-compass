from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
    AdmissionComposition,
    CONTAMINATED_D_E_TIMING_FIELDS,
    DurableVerificationResult,
    EXPECTED_CONFIGURATION,
    EXPECTED_LIFECYCLE,
    EXPECTED_PHASE_STATES,
    IdempotencyLifecyclePosition,
    IdempotencyVerdictIdentity,
    Layer1Error,
    Layer1Path,
    Layer1Sample,
    Layer1Schedule,
    MeasurementAvailability,
    PHASE_NAMES,
    PhaseRecord,
    PhaseState,
    ProducerOutcome,
    RECORDED_SAMPLES_PER_PATH,
    RunValidity,
    SCHEMA_VERSION,
    ScheduleKind,
    TimingEligibility,
    TransactionStatusIdentity,
    ValidationPlacementIdentity,
    aggregate_recorded_samples,
    classify_path,
    generate_recorded_schedule,
    generate_smoke_schedule,
    validate_run,
)


def _durable(path: Layer1Path) -> DurableVerificationResult:
    return DurableVerificationResult(
        verified=True,
        event_count=1,
        idempotency_record_count=1,
        preexisting_state_unchanged=(
            True
            if path in {Layer1Path.B, Layer1Path.C, Layer1Path.G, Layer1Path.H}
            else None
        ),
        winner_is_sole_event=(
            True if path in {Layer1Path.D, Layer1Path.E} else None
        ),
        result_references_winner=(
            True if path in {Layer1Path.D, Layer1Path.E} else None
        ),
        losing_candidate_absent=(True if path is Layer1Path.E else None),
    )


def _valid_sample(
    path: Layer1Path,
    sample_index: int,
    *,
    elapsed_ns: int = 100,
) -> Layer1Sample:
    placement, admission, outcome = EXPECTED_CONFIGURATION[path]
    phases = tuple(
        PhaseRecord(
            name=name,
            state=EXPECTED_PHASE_STATES[path][name],
            elapsed_ns=(
                elapsed_ns + phase_index
                if EXPECTED_PHASE_STATES[path][name] is PhaseState.MEASURED
                else None
            ),
        )
        for phase_index, name in enumerate(PHASE_NAMES)
    )
    contaminated = (
        CONTAMINATED_D_E_TIMING_FIELDS
        if path in {Layer1Path.D, Layer1Path.E}
        else ()
    )
    return Layer1Sample(
        schema_version=SCHEMA_VERSION,
        run_id="layer1-test-run",
        sample_index=sample_index,
        planned_path=path,
        classified_path=path,
        validation_placement=placement,
        admission_composition=admission,
        external_elapsed_ns=elapsed_ns,
        producer_outcome=outcome,
        idempotency_observations=EXPECTED_LIFECYCLE[path],
        measurement_availability=MeasurementAvailability.AVAILABLE,
        phases=phases,
        producer_return_transaction_status=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
        durable_verification=_durable(path),
        timing_eligibility=(
            TimingEligibility.STRUCTURAL_ONLY_COORDINATION_CONTAMINATED
            if contaminated
            else TimingEligibility.UNCONTAMINATED
        ),
        contaminated_timing_fields=contaminated,
    )


def _valid_samples_for(schedule) -> tuple[Layer1Sample, ...]:
    return tuple(
        _valid_sample(plan.path, plan.sample_index, elapsed_ns=plan.sample_index + 1)
        for plan in schedule.samples
    )


def test_exact_eight_path_identities_are_closed_and_ordered() -> None:
    assert tuple(path.value for path in Layer1Path) == tuple("ABCDEFGH")


def test_fixed_schedules_have_one_smoke_and_exactly_eighty_recorded_samples() -> None:
    smoke = generate_smoke_schedule()
    recorded = generate_recorded_schedule()

    assert smoke.kind is ScheduleKind.SMOKE
    assert tuple(plan.path for plan in smoke.samples) == tuple(Layer1Path)
    assert recorded.kind is ScheduleKind.RECORDED
    assert len(recorded.samples) == 80
    assert Counter(plan.path for plan in recorded.samples) == {
        path: RECORDED_SAMPLES_PER_PATH for path in Layer1Path
    }
    assert tuple(plan.sample_index for plan in recorded.samples) == tuple(range(80))


def test_schedule_rejects_adaptive_extension_or_reordering() -> None:
    recorded = generate_recorded_schedule()

    with pytest.raises(ValueError, match="fixed A--H plan"):
        Layer1Schedule(
            kind=ScheduleKind.RECORDED,
            samples=(*recorded.samples, recorded.samples[-1]),
        )
    with pytest.raises(ValueError, match="fixed A--H plan"):
        Layer1Schedule(
            kind=ScheduleKind.RECORDED,
            samples=tuple(reversed(recorded.samples)),
        )


@pytest.mark.parametrize("path", tuple(Layer1Path))
def test_exact_expected_phase_matrix_has_all_thirteen_fields(path: Layer1Path) -> None:
    states = EXPECTED_PHASE_STATES[path]

    assert tuple(states) == PHASE_NAMES
    assert len(states) == 13


def test_exact_phase_reach_sets_match_accepted_method() -> None:
    measured = {
        path: {
            name
            for name, state in EXPECTED_PHASE_STATES[path].items()
            if state is PhaseState.MEASURED
        }
        for path in Layer1Path
    }
    assert measured == {
        Layer1Path.A: {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        },
        Layer1Path.B: {
            "producer_write_invocation",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        Layer1Path.C: {
            "producer_write_invocation",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        Layer1Path.D: {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "rollback_finalization",
        },
        Layer1Path.E: {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "rollback_finalization",
        },
        Layer1Path.F: {
            "producer_write_invocation",
            "business_uow",
            "validation_runtime_call",
            "authoritative_idempotency_check",
            "accepted_history_load",
            "concurrency_preparation_call",
            "pessimistic_advisory_try_lock_call",
            "append_admission_call",
            "idempotency_record_call",
            "commit_finalization",
        },
        Layer1Path.G: {
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "rollback_finalization",
        },
        Layer1Path.H: {
            "producer_write_invocation",
            "business_uow",
            "authoritative_idempotency_check",
            "rollback_finalization",
        },
    }


def test_exact_not_applicable_phase_sets_match_accepted_method() -> None:
    not_applicable = {
        path: {
            name
            for name, state in EXPECTED_PHASE_STATES[path].items()
            if state is PhaseState.NOT_APPLICABLE
        }
        for path in Layer1Path
    }

    assert not_applicable == {
        Layer1Path.A: {"pessimistic_advisory_try_lock_call"},
        Layer1Path.B: {"pessimistic_advisory_try_lock_call"},
        Layer1Path.C: {"pessimistic_advisory_try_lock_call"},
        Layer1Path.D: {"pessimistic_advisory_try_lock_call"},
        Layer1Path.E: {"pessimistic_advisory_try_lock_call"},
        Layer1Path.F: {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        Layer1Path.G: {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
        Layer1Path.H: {
            "preliminary_idempotency_check",
            "preliminary_read_cleanup",
        },
    }


def test_ordered_idempotency_lifecycle_is_exact_for_all_paths() -> None:
    assert EXPECTED_LIFECYCLE[Layer1Path.A][0].position is (
        IdempotencyLifecyclePosition.PRELIMINARY
    )
    assert EXPECTED_LIFECYCLE[Layer1Path.A][0].verdict is (
        IdempotencyVerdictIdentity.MISS
    )
    assert EXPECTED_LIFECYCLE[Layer1Path.D][-1].verdict is (
        IdempotencyVerdictIdentity.REPLAY
    )
    assert EXPECTED_LIFECYCLE[Layer1Path.E][-1].verdict is (
        IdempotencyVerdictIdentity.CONFLICT
    )
    assert EXPECTED_LIFECYCLE[Layer1Path.G][0].position is (
        IdempotencyLifecyclePosition.AUTHORITATIVE
    )
    assert all(EXPECTED_LIFECYCLE[path] for path in Layer1Path)


@pytest.mark.parametrize("path", tuple(Layer1Path))
def test_classifier_returns_exact_path(path: Layer1Path) -> None:
    sample = _valid_sample(path, 0)

    assert sample.phases is not None
    assert (
        classify_path(
            validation_placement=sample.validation_placement,
            admission_composition=sample.admission_composition,
            producer_outcome=sample.producer_outcome,
            phases=sample.phases,
        )
        is path
    )


def test_run_validation_rejects_outcome_or_classified_path_drift() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    samples[0] = replace(
        samples[0],
        classified_path=Layer1Path.B,
        producer_outcome=ProducerOutcome.REPLAY,
    )

    result = validate_run(schedule, samples)

    assert result.validity is RunValidity.INVALID
    assert {issue.code for issue in result.issues} >= {
        "OUTCOME_MISMATCH",
        "PATH_CLASSIFICATION_MISMATCH",
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "producer_return_transaction_status",
            TransactionStatusIdentity.INTRANS,
            "PRODUCER_RETURN_NOT_IDLE",
        ),
        ("reuse_select_succeeded", False, "CONNECTION_REUSE_FAILED"),
        (
            "final_transaction_status",
            TransactionStatusIdentity.INERROR,
            "FINAL_TRANSACTION_NOT_IDLE",
        ),
    ),
)
def test_transaction_status_and_reuse_failures_invalidate_run(
    field: str,
    value,
    code: str,
) -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    samples[0] = replace(samples[0], **{field: value})

    result = validate_run(schedule, samples)

    assert code in {issue.code for issue in result.issues}


def test_unavailable_measurement_is_retained_but_invalidates_run() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    samples[0] = replace(
        samples[0],
        measurement_availability=MeasurementAvailability.UNAVAILABLE,
        phases=None,
        classified_path=None,
        idempotency_observations=(),
    )

    result = validate_run(schedule, samples)

    assert result.validity is RunValidity.INVALID
    assert "MEASUREMENT_UNAVAILABLE" in {issue.code for issue in result.issues}


def test_one_wrong_phase_state_invalidates_without_reclassification() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    sample = samples[0]
    assert sample.phases is not None
    phases = list(sample.phases)
    phase_index = PHASE_NAMES.index("commit_finalization")
    phases[phase_index] = PhaseRecord(
        name="commit_finalization",
        state=PhaseState.NOT_REACHED,
        elapsed_ns=None,
    )
    samples[0] = replace(sample, phases=tuple(phases))

    result = validate_run(schedule, samples)

    assert "PHASE_STATE_MISMATCH" in {issue.code for issue in result.issues}


def test_exception_marker_invalidates_without_becoming_a_path_cohort() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    original = samples[0]
    samples[0] = Layer1Sample(
        schema_version=SCHEMA_VERSION,
        run_id=original.run_id,
        sample_index=original.sample_index,
        planned_path=original.planned_path,
        classified_path=None,
        validation_placement=original.validation_placement,
        admission_composition=original.admission_composition,
        external_elapsed_ns=17,
        producer_outcome=None,
        idempotency_observations=(),
        measurement_availability=None,
        phases=None,
        producer_return_transaction_status=None,
        reuse_select_succeeded=None,
        final_transaction_status=None,
        durable_verification=DurableVerificationResult(False, None, None),
        timing_eligibility=TimingEligibility.UNCONTAMINATED,
        contaminated_timing_fields=(),
        exception_type="UniqueViolation",
    )

    result = validate_run(schedule, samples)

    assert result.validity is RunValidity.INVALID
    assert any(
        issue.code == "UNEXPECTED_EXCEPTION" and issue.detail == "UniqueViolation"
        for issue in result.issues
    )


def test_missing_durable_verification_marker_invalidates_run() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    samples[0] = replace(
        samples[0],
        durable_verification=DurableVerificationResult(False, 1, 1),
    )

    result = validate_run(schedule, samples)

    assert "DURABLE_VERIFICATION_FAILED" in {
        issue.code for issue in result.issues
    }


def test_d_and_e_require_explicit_structural_only_contamination_markers() -> None:
    schedule = generate_smoke_schedule()
    samples = list(_valid_samples_for(schedule))
    d_index = next(
        index
        for index, plan in enumerate(schedule.samples)
        if plan.path is Layer1Path.D
    )
    samples[d_index] = replace(
        samples[d_index],
        timing_eligibility=TimingEligibility.UNCONTAMINATED,
        contaminated_timing_fields=(),
    )

    result = validate_run(schedule, samples)

    assert "TIMING_CONTAMINATION_MISMATCH" in {
        issue.code for issue in result.issues
    }


def test_aggregation_is_eight_path_local_cohorts_without_pooled_scores() -> None:
    schedule = generate_recorded_schedule()
    samples = _valid_samples_for(schedule)

    aggregates = aggregate_recorded_samples(samples)

    assert tuple(aggregate.path for aggregate in aggregates) == tuple(Layer1Path)
    assert aggregates[0].external_elapsed is not None
    assert aggregates[0].external_elapsed.count == 10
    assert aggregates[3].external_elapsed is None
    assert aggregates[4].external_elapsed is None
    assert aggregates[3].unavailable_timing_fields == (
        CONTAMINATED_D_E_TIMING_FIELDS
    )
    assert "producer_write_invocation" not in {
        phase.phase_name for phase in aggregates[3].phases
    }
    assert "validation_runtime_call" not in {
        phase.phase_name for phase in aggregates[4].phases
    }
    assert not hasattr(aggregates[0], "composition_score")


def test_invalid_fixed_run_cannot_be_aggregated_or_replaced() -> None:
    schedule = generate_recorded_schedule()
    samples = _valid_samples_for(schedule)[:-1]

    with pytest.raises(Layer1Error, match="invalid"):
        aggregate_recorded_samples(samples)


def test_configuration_is_exact_pre_occ_a_to_e_and_in_pessimistic_f_to_h() -> None:
    assert all(
        EXPECTED_CONFIGURATION[path][0]
        is ValidationPlacementIdentity.PRE_TRANSACTION
        and EXPECTED_CONFIGURATION[path][1] is AdmissionComposition.PRE_OCC
        for path in (
            Layer1Path.A,
            Layer1Path.B,
            Layer1Path.C,
            Layer1Path.D,
            Layer1Path.E,
        )
    )
    assert all(
        EXPECTED_CONFIGURATION[path][0]
        is ValidationPlacementIdentity.IN_TRANSACTION
        and EXPECTED_CONFIGURATION[path][1]
        is AdmissionComposition.IN_PESSIMISTIC
        for path in (Layer1Path.F, Layer1Path.G, Layer1Path.H)
    )
