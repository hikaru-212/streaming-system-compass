from __future__ import annotations

from dataclasses import fields
import json

import pytest

from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
    CONTAMINATED_D_E_TIMING_FIELDS,
    DurableVerificationResult,
    EXPECTED_CONFIGURATION,
    EXPECTED_LIFECYCLE,
    EXPECTED_PHASE_STATES,
    Layer1Path,
    Layer1Sample,
    MeasurementAvailability,
    PHASE_NAMES,
    PhaseRecord,
    PhaseState,
    SCHEMA_VERSION,
    TimingEligibility,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
)
from experiments.stage4b2.postgres_idempotency_lifecycle_evidence import (
    AGGREGATES_SCHEMA_NAME,
    EVIDENCE_SCHEMA_VERSION,
    FIXED_RECORDED_SAMPLE_COUNT,
    FIXED_SCHEDULE_IDENTITY,
    MANIFEST_SCHEMA_NAME,
    PUBLICATION_RULE,
    SAMPLES_SCHEMA_NAME,
    SUPPLEMENTAL_EVIDENCE_NAMESPACE,
    TIMER_IDENTITY,
    VALIDATION_STACK_IDENTITY,
    Layer1EvidenceError,
    aggregates_to_dict,
    build_manifest,
    manifest_from_dict,
    manifest_to_dict,
    manifest_to_json,
    read_evidence_directory,
    sample_to_dict,
    samples_from_jsonl,
    samples_to_jsonl,
    write_evidence_directory,
)


RUN_ID = "stage4b2-layer1-evidence-test"
SOURCE_COMMIT = "a" * 40


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


def _sample(path: Layer1Path, sample_index: int) -> Layer1Sample:
    placement, admission, outcome = EXPECTED_CONFIGURATION[path]
    elapsed_ns = sample_index + 100
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
        run_id=RUN_ID,
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


def _samples() -> tuple[Layer1Sample, ...]:
    return tuple(
        _sample(plan.path, plan.sample_index)
        for plan in generate_recorded_schedule().samples
    )


def _manifest():
    return build_manifest(
        run_id=RUN_ID,
        source_commit=SOURCE_COMMIT,
        source_tree_clean_before_run=True,
        postgresql_server_version="16.3",
    )


def _output_root(tmp_path):
    return tmp_path / SUPPLEMENTAL_EVIDENCE_NAMESPACE


def test_sample_serialization_is_deterministic_and_round_trips_all_eighty() -> None:
    samples = _samples()

    first = samples_to_jsonl(samples)
    second = samples_to_jsonl(samples)

    assert first == second
    assert len(first.splitlines()) == FIXED_RECORDED_SAMPLE_COUNT == 80
    assert samples_from_jsonl(first) == samples
    first_raw = json.loads(first.splitlines()[0])
    assert first_raw["schema_name"] == SAMPLES_SCHEMA_NAME
    assert set(first_raw) == set(sample_to_dict(samples[0]))
    assert set(first_raw) == {
        "schema_name",
        *(field.name for field in fields(Layer1Sample)),
    }


def test_d_and_e_raw_contaminated_values_and_markers_are_preserved() -> None:
    raw_samples = [
        json.loads(line)
        for line in samples_to_jsonl(_samples()).splitlines()
    ]

    for path in (Layer1Path.D, Layer1Path.E):
        raw = next(item for item in raw_samples if item["planned_path"] == path.value)
        phases = {phase["name"]: phase for phase in raw["phases"]}
        assert isinstance(raw["external_elapsed_ns"], int)
        assert raw["timing_eligibility"] == (
            TimingEligibility.STRUCTURAL_ONLY_COORDINATION_CONTAMINATED.value
        )
        assert raw["contaminated_timing_fields"] == list(
            CONTAMINATED_D_E_TIMING_FIELDS
        )
        assert phases["producer_write_invocation"]["state"] == "MEASURED"
        assert isinstance(
            phases["producer_write_invocation"]["elapsed_ns"],
            int,
        )
        assert phases["validation_runtime_call"]["state"] == "MEASURED"
        assert isinstance(phases["validation_runtime_call"]["elapsed_ns"], int)


def test_aggregate_serialization_has_eight_paths_and_no_pooled_scores() -> None:
    samples = _samples()
    aggregates = aggregate_recorded_samples(samples)

    raw = aggregates_to_dict(run_id=RUN_ID, aggregates=aggregates)

    assert raw["schema_name"] == AGGREGATES_SCHEMA_NAME
    assert [group["path"] for group in raw["groups"]] == list("ABCDEFGH")
    assert len(raw["groups"]) == 8
    serialized = json.dumps(raw, sort_keys=True)
    assert "PRE score" not in serialized
    assert "IN score" not in serialized
    assert "p95" not in serialized
    assert "strategy_winner" not in serialized


def test_d_and_e_aggregate_omits_exact_contaminated_timing_fields() -> None:
    raw = aggregates_to_dict(
        run_id=RUN_ID,
        aggregates=aggregate_recorded_samples(_samples()),
    )

    for path in ("D", "E"):
        group = next(group for group in raw["groups"] if group["path"] == path)
        phase_names = {phase["phase_name"] for phase in group["phases"]}
        assert "external_elapsed" not in group
        assert group["unavailable_timing_fields"] == list(
            CONTAMINATED_D_E_TIMING_FIELDS
        )
        assert "producer_write_invocation" not in phase_names
        assert "validation_runtime_call" not in phase_names


def test_manifest_is_closed_sanitized_and_deterministic() -> None:
    manifest = _manifest()

    raw = manifest_to_dict(manifest)
    payload = manifest_to_json(manifest)

    assert raw == {
        "schema_name": MANIFEST_SCHEMA_NAME,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "source_tree_clean_before_run": True,
        "fixed_schedule_identity": FIXED_SCHEDULE_IDENTITY,
        "recorded_sample_count": 80,
        "samples_per_path": 10,
        "paths": list("ABCDEFGH"),
        "timer_identity": TIMER_IDENTITY,
        "postgresql_server_version": "16.3",
        "validation_stack_identity": VALIDATION_STACK_IDENTITY,
        "d_e_contamination_rule": list(CONTAMINATED_D_E_TIMING_FIELDS),
        "stop_publication_rule": PUBLICATION_RULE,
    }
    assert manifest_to_json(manifest) == payload
    assert manifest_from_dict(json.loads(payload)) == manifest
    lowered = payload.lower()
    for forbidden in (
        "dsn",
        "host",
        "port",
        "database_name",
        "username",
        "password",
        "postgresql://",
        "localhost",
        "compass_test",
        "compass_user",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize(
    "unsafe_version",
    (
        "postgresql://user:password@example/test",
        "host=localhost port=5433",
        "16.3\ndatabase=compass_test",
    ),
)
def test_manifest_rejects_connection_data_in_server_version(
    unsafe_version: str,
) -> None:
    with pytest.raises(ValueError, match="connection data"):
        build_manifest(
            run_id=RUN_ID,
            source_commit=SOURCE_COMMIT,
            source_tree_clean_before_run=True,
            postgresql_server_version=unsafe_version,
        )


def test_invalid_run_writes_nothing_and_does_not_create_namespace(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    invalid_samples = _samples()[:-1]

    result = write_evidence_directory(
        output_root=output_root,
        manifest=_manifest(),
        samples=invalid_samples,
    )

    assert result is None
    assert not output_root.exists()


def test_valid_run_publishes_exactly_three_files_and_round_trips(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    samples = _samples()
    manifest = _manifest()

    result = write_evidence_directory(
        output_root=output_root,
        manifest=manifest,
        samples=samples,
    )

    assert result is not None
    assert result.directory == output_root / RUN_ID
    assert {path.name for path in result.directory.iterdir()} == {
        "manifest.json",
        "samples.jsonl",
        "aggregates.json",
    }
    assert not any(path.name.startswith(".") for path in output_root.iterdir())
    parsed = read_evidence_directory(result.directory)
    assert parsed.manifest == manifest
    assert parsed.samples == samples
    assert parsed.aggregates == aggregate_recorded_samples(samples)


def test_existing_final_directory_is_never_overwritten(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    samples = _samples()
    manifest = _manifest()
    first = write_evidence_directory(
        output_root=output_root,
        manifest=manifest,
        samples=samples,
    )
    assert first is not None
    before = {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
        if path.is_file()
    }

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_evidence_directory(
            output_root=output_root,
            manifest=manifest,
            samples=samples,
        )

    after = {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
        if path.is_file()
    }
    assert after == before


def test_writer_refuses_non_supplemental_namespace(tmp_path) -> None:
    with pytest.raises(Layer1EvidenceError, match="supplemental namespace"):
        write_evidence_directory(
            output_root=tmp_path / "stage4b2-pr6-canonical-0bd2f51",
            manifest=_manifest(),
            samples=_samples(),
        )
