from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json

import pytest

from experiments.stage4b2 import (
    postgres_idempotency_read_lifecycle_evidence as evidence,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ALL_CONTROLS,
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleSample,
    IdempotencyVerdictIdentity,
    Layer3Control,
    RunValidationResult,
    RunValidity,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_evidence import (
    AGGREGATES_SCHEMA_NAME,
    CANONICAL_PR6_EVIDENCE_NAMESPACE,
    CLOCK_IDENTITY,
    EVIDENCE_FILENAMES,
    EVIDENCE_SCHEMA_VERSION,
    FIXED_SCHEDULE_IDENTITY,
    LAYER1_EVIDENCE_NAMESPACE,
    LAYER2_EVIDENCE_NAMESPACE,
    MANIFEST_SCHEMA_NAME,
    PUBLICATION_RULE,
    SAMPLES_PER_CONTROL,
    SUPPLEMENTAL_EVIDENCE_NAMESPACE,
    TOTAL_PLANNED_SAMPLES,
    VALIDATION_STATUS,
    Layer3EvidenceError,
    aggregates_from_dict,
    aggregates_to_dict,
    build_manifest,
    manifest_from_dict,
    manifest_to_dict,
    manifest_to_json,
    read_layer3_evidence_directory,
    sample_from_dict,
    sample_to_dict,
    samples_from_jsonl,
    samples_to_jsonl,
    write_layer3_evidence_directory,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime import (
    Layer3RuntimeResult,
)


RUN_ID = "stage4b2-layer3-evidence-test"
SOURCE_COMMIT = "a" * 40
SECRET_MARKER = "layer3-super-secret-marker"


def _sample(plan):
    if plan.control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
        return ControlAIdleRollbackSample(
            control=plan.control,
            sample_index=plan.sample_index,
            round_index=plan.round_index,
            status_before_cleanup=TransactionStatusIdentity.IDLE,
            cleanup_elapsed_ns=100 + plan.sample_index,
            status_after_cleanup=TransactionStatusIdentity.IDLE,
        )
    return ControlBPreliminaryReadLifecycleSample(
        control=plan.control,
        sample_index=plan.sample_index,
        round_index=plan.round_index,
        returned_idempotency_verdict=IdempotencyVerdictIdentity.MISS,
        history_count=0,
        idempotency_check_elapsed_ns=200 + plan.sample_index,
        accepted_history_load_elapsed_ns=300 + plan.sample_index,
        cleanup_elapsed_ns=400 + plan.sample_index,
        lifecycle_elapsed_ns=1_000 + plan.sample_index,
        status_before_check=TransactionStatusIdentity.IDLE,
        status_after_check=TransactionStatusIdentity.INTRANS,
        status_after_history=TransactionStatusIdentity.INTRANS,
        status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
    )


def _samples():
    return tuple(_sample(plan) for plan in generate_recorded_schedule().samples)


def _result(samples=None, validation=None):
    schedule = generate_recorded_schedule()
    retained_samples = _samples() if samples is None else tuple(samples)
    retained_validation = (
        validate_run(schedule, retained_samples)
        if validation is None
        else validation
    )
    return Layer3RuntimeResult(
        schedule=schedule,
        samples=retained_samples,
        validation=retained_validation,
    )


def _manifest(*, clean=True, server_version="PostgreSQL 16.3"):
    return build_manifest(
        run_id=RUN_ID,
        source_commit=SOURCE_COMMIT,
        source_tree_clean_before_run=clean,
        postgresql_server_version=server_version,
    )


def _output_root(tmp_path):
    return tmp_path / SUPPLEMENTAL_EVIDENCE_NAMESPACE


def test_evidence_namespace_is_exact_and_separate() -> None:
    assert SUPPLEMENTAL_EVIDENCE_NAMESPACE == (
        "stage4b2-post-pr6-idempotency-read-lifecycle-layer3"
    )
    assert SUPPLEMENTAL_EVIDENCE_NAMESPACE not in {
        LAYER1_EVIDENCE_NAMESPACE,
        LAYER2_EVIDENCE_NAMESPACE,
        CANONICAL_PR6_EVIDENCE_NAMESPACE,
    }
    assert evidence.DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT.name == (
        SUPPLEMENTAL_EVIDENCE_NAMESPACE
    )


def test_manifest_is_closed_sanitized_deterministic_and_round_trips() -> None:
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
        "recorded_rounds": 30,
        "samples_per_control": 30,
        "total_planned_samples": 60,
        "controls": [control.value for control in ALL_CONTROLS],
        "clock_identity": CLOCK_IDENTITY,
        "postgresql_server_version": "PostgreSQL 16.3",
        "validation_status": VALIDATION_STATUS,
        "publication_rule": PUBLICATION_RULE,
    }
    assert set(raw) == {
        "schema_name",
        "schema_version",
        "run_id",
        "source_commit",
        "source_tree_clean_before_run",
        "fixed_schedule_identity",
        "recorded_rounds",
        "samples_per_control",
        "total_planned_samples",
        "controls",
        "clock_identity",
        "postgresql_server_version",
        "validation_status",
        "publication_rule",
    }
    assert manifest_to_json(manifest) == payload
    assert manifest_from_dict(json.loads(payload)) == manifest


@pytest.mark.parametrize("source_commit", ("short", "A" * 40, "g" * 40))
def test_manifest_requires_full_lowercase_40_character_commit(
    source_commit,
) -> None:
    with pytest.raises(ValueError, match="full lowercase Git identity"):
        build_manifest(
            run_id=RUN_ID,
            source_commit=source_commit,
            source_tree_clean_before_run=True,
            postgresql_server_version="PostgreSQL 16.3",
        )


@pytest.mark.parametrize(
    "unsafe_version",
    (
        "postgresql://example.invalid/example_test",
        "host=localhost port=5433",
        f"PostgreSQL 16.3 password={SECRET_MARKER}",
        f"PostgreSQL 16.3 token={SECRET_MARKER}",
    ),
)
def test_manifest_rejects_connection_or_secret_shaped_server_version(
    unsafe_version,
) -> None:
    with pytest.raises(ValueError, match="connection data"):
        _manifest(server_version=unsafe_version)


def test_sample_jsonl_is_deterministic_exact_60_and_fixed_a_b_order() -> None:
    samples = _samples()
    first = samples_to_jsonl(samples)
    second = samples_to_jsonl(samples)
    parsed = samples_from_jsonl(first)

    assert first == second
    assert len(first.splitlines()) == TOTAL_PLANNED_SAMPLES == 60
    assert parsed == samples
    assert Counter(sample.control for sample in parsed) == {
        control: SAMPLES_PER_CONTROL for control in ALL_CONTROLS
    }
    assert tuple(sample.control for sample in parsed) == tuple(
        plan.control for plan in generate_recorded_schedule().samples
    )
    assert tuple(sample.sample_index for sample in parsed) == tuple(range(60))


def test_control_a_sample_serialization_is_exact_and_round_trips() -> None:
    sample = _samples()[0]
    raw = sample_to_dict(sample)

    assert raw == {
        "control": "CONTROL_A_IDLE_ROLLBACK",
        "sample_index": 0,
        "round_index": 0,
        "status_before_cleanup": "IDLE",
        "cleanup_elapsed_ns": 100,
        "status_after_cleanup": "IDLE",
        "exception_type": None,
    }
    assert sample_from_dict(raw) == sample


def test_control_b_sample_serialization_is_exact_and_round_trips() -> None:
    sample = _samples()[1]
    raw = sample_to_dict(sample)

    assert set(raw) == {
        "control",
        "sample_index",
        "round_index",
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
    }
    assert raw["returned_idempotency_verdict"] == "MISS"
    assert raw["history_count"] == 0
    assert sample_from_dict(raw) == sample


def test_samples_never_expand_to_identity_or_synthetic_timing_fields() -> None:
    serialized = samples_to_jsonl(_samples()).lower()

    for forbidden in (
        "request_id",
        "order_id",
        "database_time_ns",
        "component_sum_ns",
        "attempt_id",
        "execution_id",
        "exception_message",
    ):
        assert forbidden not in serialized


def test_aggregate_serialization_has_exact_two_unpooled_controls() -> None:
    aggregates = aggregate_recorded_samples(_samples())
    raw = aggregates_to_dict(run_id=RUN_ID, aggregates=aggregates)

    assert raw["schema_name"] == AGGREGATES_SCHEMA_NAME
    assert len(raw["groups"]) == 2
    assert raw["groups"][0]["control"] == (
        Layer3Control.CONTROL_A_IDLE_ROLLBACK.value
    )
    assert set(raw["groups"][0]) == {"control", "cleanup_elapsed_ns"}
    assert raw["groups"][1]["control"] == (
        Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE.value
    )
    assert set(raw["groups"][1]) == {
        "control",
        "idempotency_check_elapsed_ns",
        "accepted_history_load_elapsed_ns",
        "cleanup_elapsed_ns",
        "lifecycle_elapsed_ns",
    }
    for group in raw["groups"]:
        for field, value in group.items():
            if field != "control":
                assert value["count"] == 30
                assert set(value) == {
                    "count",
                    "minimum_ns",
                    "mean_ns",
                    "median_ns",
                    "maximum_ns",
                }
    serialized = json.dumps(raw, sort_keys=True).lower()
    for forbidden in (
        "p95",
        "pooled",
        "strategy",
        "ranking",
        "database_time",
        "component_sum",
    ):
        assert forbidden not in serialized
    assert aggregates_from_dict(raw) == aggregates


def test_dirty_source_writes_nothing_and_creates_no_namespace(tmp_path) -> None:
    output_root = _output_root(tmp_path)

    written = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=_manifest(clean=False),
        result=_result(),
    )

    assert written is None
    assert not output_root.exists()


def test_invalid_runtime_validation_writes_nothing(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    inconsistent = RunValidationResult(RunValidity.INVALID, ())

    written = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=_manifest(),
        result=_result(validation=inconsistent),
    )

    assert written is None
    assert not output_root.exists()


def test_missing_sample_writes_nothing(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    samples = _samples()[:-1]

    written = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=_manifest(),
        result=_result(samples=samples),
    )

    assert written is None
    assert not output_root.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "returned_idempotency_verdict",
            IdempotencyVerdictIdentity.REPLAY,
        ),
        ("history_count", 1),
        ("status_after_history", TransactionStatusIdentity.IDLE),
        ("reuse_select_succeeded", False),
        ("exception_type", "RuntimeError"),
    ),
)
def test_invalid_control_b_invariant_writes_nothing(tmp_path, field, value) -> None:
    output_root = _output_root(tmp_path)
    samples = list(_samples())
    samples[1] = replace(samples[1], **{field: value})

    written = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=_manifest(),
        result=_result(samples=samples),
    )

    assert written is None
    assert not output_root.exists()


def test_valid_run_atomically_publishes_exactly_three_files_and_reads_back(
    tmp_path,
) -> None:
    output_root = _output_root(tmp_path)
    result = _result()
    manifest = _manifest()

    written = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=manifest,
        result=result,
    )

    assert written is not None
    assert written.directory == output_root / RUN_ID
    assert {path.name for path in written.directory.iterdir()} == EVIDENCE_FILENAMES
    assert len(written.samples_path.read_text(encoding="utf-8").splitlines()) == 60
    assert not any(path.name.startswith(".") for path in output_root.iterdir())
    parsed = read_layer3_evidence_directory(written.directory)
    assert parsed.manifest == manifest
    assert parsed.samples == result.samples
    assert parsed.aggregates == aggregate_recorded_samples(result.samples)


def test_existing_run_directory_is_never_overwritten(tmp_path) -> None:
    output_root = _output_root(tmp_path)
    first = write_layer3_evidence_directory(
        output_root=output_root,
        manifest=_manifest(),
        result=_result(),
    )
    assert first is not None
    before = {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
        if path.is_file()
    }

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_layer3_evidence_directory(
            output_root=output_root,
            manifest=_manifest(),
            result=_result(),
        )

    after = {
        path.name: path.read_bytes()
        for path in first.directory.iterdir()
        if path.is_file()
    }
    assert after == before


def test_wrong_namespace_refuses_publication(tmp_path) -> None:
    with pytest.raises(Layer3EvidenceError, match="Layer-3 namespace"):
        write_layer3_evidence_directory(
            output_root=tmp_path / "wrong-evidence-namespace",
            manifest=_manifest(),
            result=_result(),
        )


@pytest.mark.parametrize(
    "protected_namespace",
    (
        LAYER1_EVIDENCE_NAMESPACE,
        LAYER2_EVIDENCE_NAMESPACE,
        CANONICAL_PR6_EVIDENCE_NAMESPACE,
    ),
)
def test_protected_evidence_ancestry_is_rejected(
    tmp_path,
    protected_namespace,
) -> None:
    output_root = (
        tmp_path / protected_namespace / SUPPLEMENTAL_EVIDENCE_NAMESPACE
    )

    with pytest.raises(Layer3EvidenceError, match="protected evidence ancestry"):
        write_layer3_evidence_directory(
            output_root=output_root,
            manifest=_manifest(),
            result=_result(),
        )

    assert not output_root.exists()


def test_partial_write_failure_leaves_no_visible_or_staging_directory(
    tmp_path,
    monkeypatch,
) -> None:
    output_root = _output_root(tmp_path)
    original = evidence._write_complete_file
    calls = 0

    def fail_after_one_file(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("deterministic partial-write failure")
        original(path, payload)

    monkeypatch.setattr(evidence, "_write_complete_file", fail_after_one_file)

    with pytest.raises(OSError, match="partial-write failure"):
        write_layer3_evidence_directory(
            output_root=output_root,
            manifest=_manifest(),
            result=_result(),
        )

    assert not (output_root / RUN_ID).exists()
    assert list(output_root.iterdir()) == []


def test_read_back_rejects_extra_file(tmp_path) -> None:
    written = write_layer3_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        result=_result(),
    )
    assert written is not None
    (written.directory / "extra.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(Layer3EvidenceError, match="three files"):
        read_layer3_evidence_directory(written.directory)


def test_read_back_requires_directory_and_manifest_run_id_consistency(
    tmp_path,
) -> None:
    written = write_layer3_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        result=_result(),
    )
    assert written is not None
    raw = json.loads(written.manifest_path.read_text(encoding="utf-8"))
    raw["run_id"] = "different-safe-run-id"
    written.manifest_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Layer3EvidenceError, match="directory run_id"):
        read_layer3_evidence_directory(written.directory)


def test_read_back_fresh_validation_rejects_tampered_sample(tmp_path) -> None:
    written = write_layer3_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        result=_result(),
    )
    assert written is not None
    lines = written.samples_path.read_text(encoding="utf-8").splitlines()
    raw = json.loads(lines[1])
    raw["reuse_select_succeeded"] = False
    lines[1] = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    written.samples_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(Layer3EvidenceError, match="freshly validate"):
        read_layer3_evidence_directory(written.directory)


def test_read_back_recomputes_and_rejects_tampered_aggregates(tmp_path) -> None:
    written = write_layer3_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        result=_result(),
    )
    assert written is not None
    raw = json.loads(written.aggregates_path.read_text(encoding="utf-8"))
    raw["groups"][0]["cleanup_elapsed_ns"]["mean_ns"] += 1
    written.aggregates_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Layer3EvidenceError, match="differ from samples"):
        read_layer3_evidence_directory(written.directory)


def test_published_payload_excludes_secret_and_connection_shapes(tmp_path) -> None:
    written = write_layer3_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        result=_result(),
    )
    assert written is not None
    payload = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            written.manifest_path,
            written.samples_path,
            written.aggregates_path,
        )
    ).lower()

    for forbidden in (
        SECRET_MARKER,
        "test_database_url",
        '"dsn"',
        '"host"',
        '"port"',
        "database_name",
        "username",
        "password",
        "environment_variable",
        "postgresql://",
        "localhost",
        "request_id",
        "order_id",
    ):
        assert forbidden not in payload


def test_evidence_module_has_no_runner_counterfactual_or_policy_surface() -> None:
    assert not hasattr(evidence, "run_layer3_recorded")
    assert not hasattr(evidence, "main")
    assert not hasattr(evidence, "PRE_NO_PRELIMINARY")
    assert not hasattr(evidence, "IN_OCC")
    assert not hasattr(evidence, "StrategyWinner")
    assert not hasattr(evidence, "rate_limit")
    assert not hasattr(evidence, "capacity")
