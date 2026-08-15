from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json

import pytest

from experiments.stage4b2 import postgres_idempotency_check_evidence as evidence
from experiments.stage4b2.postgres_idempotency_check_characterization import (
    ALL_CELLS,
    Layer2Context,
    Layer2Sample,
    RECORDED_SAMPLES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    SCHEMA_VERSION,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
)
from experiments.stage4b2.postgres_idempotency_check_evidence import (
    AGGREGATES_SCHEMA_NAME,
    CANONICAL_PR6_EVIDENCE_NAMESPACE,
    EVIDENCE_SCHEMA_VERSION,
    FIXED_RECORDED_SAMPLE_COUNT,
    FIXED_SCHEDULE_IDENTITY,
    LAYER1_EVIDENCE_NAMESPACE,
    MANIFEST_SCHEMA_NAME,
    PUBLICATION_RULE,
    SAMPLES_SCHEMA_NAME,
    SUPPLEMENTAL_EVIDENCE_NAMESPACE,
    TIMER_IDENTITY,
    VALIDATION_STATUS,
    Layer2EvidenceError,
    aggregates_from_dict,
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


RUN_ID = "stage4b2-layer2-evidence-test"
SOURCE_COMMIT = "a" * 40


def _sample(plan) -> Layer2Sample:
    before = (
        TransactionStatusIdentity.INTRANS
        if plan.cell.context is Layer2Context.T
        else TransactionStatusIdentity.IDLE
    )
    return Layer2Sample(
        schema_version=SCHEMA_VERSION,
        run_id=RUN_ID,
        sample_index=plan.sample_index,
        planned_context=plan.cell.context,
        planned_verdict=plan.cell.verdict,
        returned_verdict=plan.cell.verdict,
        check_elapsed_ns=1_000 + plan.sample_index,
        cleanup_elapsed_ns=200 + plan.sample_index,
        transaction_status_before_check=before,
        transaction_status_after_check=TransactionStatusIdentity.INTRANS,
        transaction_status_after_cleanup=TransactionStatusIdentity.IDLE,
        reuse_select_succeeded=True,
        final_transaction_status=TransactionStatusIdentity.IDLE,
    )


def _samples() -> tuple[Layer2Sample, ...]:
    return tuple(_sample(plan) for plan in generate_recorded_schedule().samples)


def _manifest(*, clean: bool = True):
    return build_manifest(
        run_id=RUN_ID,
        source_commit=SOURCE_COMMIT,
        source_tree_clean_before_run=clean,
        postgresql_server_version="16.3",
        structural_smoke_validated=True,
    )


def _output_root(tmp_path):
    return tmp_path / SUPPLEMENTAL_EVIDENCE_NAMESPACE


def test_evidence_namespace_is_exact_and_separate() -> None:
    assert SUPPLEMENTAL_EVIDENCE_NAMESPACE == (
        "stage4b2-post-pr6-idempotency-check-layer2"
    )
    assert SUPPLEMENTAL_EVIDENCE_NAMESPACE != LAYER1_EVIDENCE_NAMESPACE
    assert SUPPLEMENTAL_EVIDENCE_NAMESPACE != CANONICAL_PR6_EVIDENCE_NAMESPACE
    assert evidence.DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT.name == (
        SUPPLEMENTAL_EVIDENCE_NAMESPACE
    )


def test_sample_serialization_is_deterministic_and_round_trips_270() -> None:
    samples = _samples()

    first = samples_to_jsonl(samples)
    second = samples_to_jsonl(samples)

    assert first == second
    assert len(first.splitlines()) == FIXED_RECORDED_SAMPLE_COUNT == 270
    assert samples_from_jsonl(first) == samples
    raw = json.loads(first.splitlines()[0])
    assert raw["schema_name"] == SAMPLES_SCHEMA_NAME
    assert set(raw) == set(sample_to_dict(samples[0])) == {
        "schema_name",
        "schema_version",
        "run_id",
        "sample_index",
        "planned_context",
        "planned_verdict",
        "returned_verdict",
        "check_elapsed_ns",
        "cleanup_elapsed_ns",
        "transaction_status_before_check",
        "transaction_status_after_check",
        "transaction_status_after_cleanup",
        "reuse_select_succeeded",
        "final_transaction_status",
        "exception_type",
    }
    assert "structural_sql_observation_identity" not in raw
    assert "exception_message" not in raw


def test_serialized_samples_retain_exactly_30_per_cell() -> None:
    parsed = samples_from_jsonl(samples_to_jsonl(_samples()))

    counts = Counter(sample.cell for sample in parsed)

    assert counts == {
        cell: RECORDED_SAMPLES_PER_CELL for cell in ALL_CELLS
    }


def test_aggregate_serialization_has_nine_cells_and_no_pooling() -> None:
    aggregates = aggregate_recorded_samples(_samples())

    raw = aggregates_to_dict(run_id=RUN_ID, aggregates=aggregates)

    assert raw["schema_name"] == AGGREGATES_SCHEMA_NAME
    assert [
        (group["context"], group["verdict"]) for group in raw["groups"]
    ] == [
        (cell.context.value, cell.verdict.value) for cell in ALL_CELLS
    ]
    assert len(raw["groups"]) == 9
    for group in raw["groups"]:
        assert set(group) == {
            "context",
            "verdict",
            "check_elapsed_ns",
            "cleanup_elapsed_ns",
        }
        for field in ("check_elapsed_ns", "cleanup_elapsed_ns"):
            assert group[field]["count"] == RECORDED_SAMPLES_PER_CELL
            assert set(group[field]) == {
                "count",
                "min_ns",
                "mean_ns",
                "median_ns",
                "max_ns",
            }
    serialized = json.dumps(raw, sort_keys=True).lower()
    for forbidden in (
        "p95",
        "pooled",
        "strategy_winner",
        "database_time",
        "context_score",
        "verdict_score",
    ):
        assert forbidden not in serialized
    assert aggregates_from_dict(raw) == aggregates


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
        "fixed_recorded_schedule_seed": RECORDED_SCHEDULE_SEED,
        "planned_sample_count": 270,
        "samples_per_cell": 30,
        "cells": [cell.identity for cell in ALL_CELLS],
        "clock_identity": TIMER_IDENTITY,
        "postgresql_server_version": "16.3",
        "validation_status": VALIDATION_STATUS,
        "structural_smoke_validated": True,
        "publication_rule": PUBLICATION_RULE,
    }
    assert manifest_to_json(manifest) == payload
    assert manifest_from_dict(json.loads(payload)) == manifest
    lowered = payload.lower()
    for forbidden in (
        "test_database_url",
        "dsn",
        '"host"',
        '"port"',
        "database_name",
        "username",
        "password",
        "environment_variable",
        "postgresql://",
        "localhost",
        "compass_test",
        "compass_user",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize(
    "unsafe_version",
    (
        "postgresql://example.invalid/test",
        "host=localhost port=5433",
        "16.3\ndatabase=example_test",
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
            structural_smoke_validated=True,
        )


def test_manifest_requires_known_commit_and_valid_structural_smoke() -> None:
    with pytest.raises(ValueError, match="full lowercase Git identity"):
        build_manifest(
            run_id=RUN_ID,
            source_commit="short",
            source_tree_clean_before_run=True,
            postgresql_server_version="16.3",
            structural_smoke_validated=True,
        )
    with pytest.raises(ValueError, match="structural smoke"):
        build_manifest(
            run_id=RUN_ID,
            source_commit=SOURCE_COMMIT,
            source_tree_clean_before_run=True,
            postgresql_server_version="16.3",
            structural_smoke_validated=False,
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


def test_dirty_source_writes_nothing_and_does_not_create_namespace(tmp_path) -> None:
    output_root = _output_root(tmp_path)

    result = write_evidence_directory(
        output_root=output_root,
        manifest=_manifest(clean=False),
        samples=_samples(),
    )

    assert result is None
    assert not output_root.exists()


def test_valid_run_publishes_three_files_and_round_trips(tmp_path) -> None:
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
    assert len(result.samples_path.read_text(encoding="utf-8").splitlines()) == 270
    assert not any(path.name.startswith(".") for path in output_root.iterdir())
    parsed = read_evidence_directory(result.directory)
    assert parsed.manifest == manifest
    assert parsed.samples == samples
    assert parsed.aggregates == aggregate_recorded_samples(samples)


def test_existing_run_directory_is_never_overwritten(tmp_path) -> None:
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


def test_wrong_namespace_refuses_publication(tmp_path) -> None:
    with pytest.raises(Layer2EvidenceError, match="Layer-2 namespace"):
        write_evidence_directory(
            output_root=tmp_path / "wrong-evidence-namespace",
            manifest=_manifest(),
            samples=_samples(),
        )


@pytest.mark.parametrize(
    "protected_namespace",
    (LAYER1_EVIDENCE_NAMESPACE, CANONICAL_PR6_EVIDENCE_NAMESPACE),
)
def test_protected_evidence_namespace_cannot_be_overwritten(
    tmp_path,
    protected_namespace: str,
) -> None:
    output_root = (
        tmp_path / protected_namespace / SUPPLEMENTAL_EVIDENCE_NAMESPACE
    )

    with pytest.raises(Layer2EvidenceError, match="protected evidence"):
        write_evidence_directory(
            output_root=output_root,
            manifest=_manifest(),
            samples=_samples(),
        )

    assert not output_root.exists()


def test_partial_publication_never_becomes_visible(tmp_path, monkeypatch) -> None:
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
        write_evidence_directory(
            output_root=output_root,
            manifest=_manifest(),
            samples=_samples(),
        )

    assert not (output_root / RUN_ID).exists()
    assert all(path.name.startswith(".") for path in output_root.iterdir())


def test_published_payload_contains_no_connection_or_secret_data(tmp_path) -> None:
    result = write_evidence_directory(
        output_root=_output_root(tmp_path),
        manifest=_manifest(),
        samples=_samples(),
    )
    assert result is not None
    payload = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            result.manifest_path,
            result.samples_path,
            result.aggregates_path,
        )
    ).lower()

    for forbidden in (
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
        "compass_test",
        "compass_user",
    ):
        assert forbidden not in payload
