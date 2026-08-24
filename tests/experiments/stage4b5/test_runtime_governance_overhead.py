"""Unit tests for Stage 4B.5 overhead evidence and statistics."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import experiments.stage4b5.runtime_governance_overhead as overhead
from experiments.stage4b5.runtime_governance_overhead import (
    AReplayReviewError,
    AReplayStatus,
    HISTORICAL_SOURCE_COMMIT,
    MICRO_CONFIG,
    MICRO_SCENARIOS,
    POSTGRES_CONFIG,
    POSTGRES_SCENARIOS,
    SCHEMA_VERSION,
    Layer,
    Sample,
    ScheduleConfig,
    Surface,
    aggregate_evidence,
    assert_secret_free,
    block_bootstrap_median_ci,
    compute_batch_comparisons,
    compute_batch_summaries,
    expected_sample_count,
    evaluate_a_current_replay_compatibility,
    fixed_surface_permutations,
    load_and_verify_historical_a_source_provenance,
    nearest_rank,
    validate_recorded_population,
    validate_run_id,
    write_immutable_evidence,
)


def _sample(
    *,
    surface: Surface,
    producer_elapsed_ns: int,
    composition_elapsed_ns: int | None = None,
    block: int = 0,
    permutation: int = 0,
    repetition: int = 0,
) -> Sample:
    if surface is Surface.C:
        if composition_elapsed_ns is None:
            composition_elapsed_ns = 20
        total_elapsed_ns = producer_elapsed_ns + composition_elapsed_ns
    else:
        if composition_elapsed_ns is not None:
            raise ValueError("A/B test samples cannot carry composition laps")
        total_elapsed_ns = producer_elapsed_ns
    return Sample(
        schema_version=SCHEMA_VERSION,
        run_id="unit-run",
        layer=Layer.MICRO.value,
        scenario=MICRO_SCENARIOS[0].name,
        surface=surface.value,
        block_index=block,
        permutation_index=permutation,
        repetition_index=repetition,
        producer_elapsed_ns=producer_elapsed_ns,
        composition_elapsed_ns=composition_elapsed_ns,
        total_elapsed_ns=total_elapsed_ns,
        producer_outcome=MICRO_SCENARIOS[0].terminal.value,
        rule_id=None,
    )


def test_fixed_matrices_and_schedule_population() -> None:
    assert len(MICRO_SCENARIOS) == 4
    assert len(POSTGRES_SCENARIOS) == 8
    permutations = fixed_surface_permutations()
    assert len(permutations) == 6
    assert len(set(permutations)) == 6
    assert all(set(permutation) == set(Surface) for permutation in permutations)
    assert expected_sample_count(
        scenarios=MICRO_SCENARIOS,
        config=MICRO_CONFIG,
    ) == 216_000
    assert expected_sample_count(
        scenarios=POSTGRES_SCENARIOS,
        config=POSTGRES_CONFIG,
    ) == 43_200


def test_a_provenance_resolves_exact_commit_blobs_and_digests() -> None:
    provenance = load_and_verify_historical_a_source_provenance()
    assert provenance["source_commit"] == HISTORICAL_SOURCE_COMMIT
    assert [entry["module"] for entry in provenance["modules"]] == [
        "src.compass.transition.validators",
        "src.compass.transition.runtime",
        "src.pipeline.transactional.postgres_write_side",
    ]


def test_a_provenance_pins_historical_audit_time_source_differences() -> None:
    document = json.loads(
        overhead.A_SOURCE_PROVENANCE_PATH.read_text(encoding="utf-8")
    )
    historical_differences = json.dumps(
        document["allowed_current_source_differences"],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")

    # This digest freezes historical audit metadata only. Current drift remains
    # scoped independently to A's explicit transitive dependency surface.
    assert hashlib.sha256(historical_differences).hexdigest() == (
        "16a3050e5738a0d18911c61786dfd03f0dc25ec3fd2080a7e0061e7885347ee7"
    )


def test_a_replay_review_is_separate_exact_state_metadata() -> None:
    document = json.loads(
        overhead.A_REPLAY_REVIEW_PATH.read_text(encoding="utf-8")
    )

    assert set(document) == {
        "schema",
        "schema_version",
        "historical_a_source_commit",
        "reviewed_current_source_commit",
        "replay_status",
        "reason",
        "protected_current_dependencies",
    }
    assert document["schema"] == (
        "stage4b5-runtime-governance-a-replay-review"
    )
    assert document["schema_version"] == 1
    assert document["historical_a_source_commit"] == HISTORICAL_SOURCE_COMMIT
    assert document["replay_status"] == "REFUSED"
    assert [
        (entry["module"], entry["path"])
        for entry in document["protected_current_dependencies"]
    ] == list(overhead._A_CURRENT_TRANSITIVE_DEPENDENCIES)
    assert all(
        len(entry["sha256"]) == 64
        for entry in document["protected_current_dependencies"]
    )


def test_a_replay_review_exact_committed_state_is_reviewed_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The checked-in review is based on committed bytes. The repository may
    # carry unrelated protected working-tree work while this maintenance commit
    # is validated, so this test deliberately supplies the reviewed HEAD bytes.
    monkeypatch.setattr(
        overhead,
        "_read_working_tree_protected_source",
        overhead._read_head_protected_source,
    )

    replay = evaluate_a_current_replay_compatibility()

    assert replay.status is AReplayStatus.REFUSED
    assert replay.reviewed_current_source_commit == (
        "0563657b186b1e5948b8d80bb3d4071cd49ac08b"
    )
    assert "no performance-equivalence review" in replay.reason


def test_a_replay_review_rejects_future_committed_protected_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_head_source = overhead._read_head_protected_source

    def changed_head_source(source_path: str) -> bytes:
        if source_path == "src/core/order/events.py":
            return b"future reviewed-surface change"
        return real_head_source(source_path)

    monkeypatch.setattr(overhead, "_read_head_protected_source", changed_head_source)
    monkeypatch.setattr(
        overhead,
        "_read_working_tree_protected_source",
        changed_head_source,
    )

    with pytest.raises(
        AReplayReviewError,
        match="unreviewed current A protected dependency drift: HEAD=.*events.py",
    ):
        evaluate_a_current_replay_compatibility()


def test_a_replay_review_identity_tampering_is_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document = json.loads(
        overhead.A_REPLAY_REVIEW_PATH.read_text(encoding="utf-8")
    )
    document["protected_current_dependencies"][0]["sha256"] = "0" * 64
    tampered_review = tmp_path / "replay_review.json"
    tampered_review.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(overhead, "A_REPLAY_REVIEW_PATH", tampered_review)

    with pytest.raises(
        AReplayReviewError,
        match="does not match its reviewed commit",
    ):
        evaluate_a_current_replay_compatibility()


def test_a_replay_review_rejects_protected_working_tree_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_head_source = overhead._read_head_protected_source

    def changed_working_tree_source(source_path: str) -> bytes:
        if source_path == "src/storage/postgres_event_store.py":
            return b"uncommitted protected source"
        return real_head_source(source_path)

    monkeypatch.setattr(
        overhead,
        "_read_working_tree_protected_source",
        changed_working_tree_source,
    )

    with pytest.raises(
        AReplayReviewError,
        match="working-tree=.*postgres_event_store.py",
    ):
        evaluate_a_current_replay_compatibility()


def test_a_replay_review_ignores_unrelated_working_tree_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    unrelated_source = tmp_path / "unrelated_current_source.py"
    unrelated_source.write_text("unrelated = True\n", encoding="utf-8")
    monkeypatch.setattr(
        overhead,
        "_read_working_tree_protected_source",
        overhead._read_head_protected_source,
    )

    replay = evaluate_a_current_replay_compatibility()

    assert unrelated_source.exists()
    assert replay.status is AReplayStatus.REFUSED


@pytest.mark.parametrize(
    ("tamper", "message"),
    (
        ("schema", "unexpected A source provenance schema"),
        ("commit", "does not match the pinned"),
        ("module_order", "retain the audited dependency order"),
        ("blob", "Git blob mismatch"),
        ("digest", "SHA-256 mismatch"),
        ("audit_metadata", "audit-time differences changed"),
    ),
)
def test_historical_a_provenance_tampering_remains_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tamper: str,
    message: str,
) -> None:
    document = json.loads(
        overhead.A_SOURCE_PROVENANCE_PATH.read_text(encoding="utf-8")
    )
    if tamper == "schema":
        document["schema"] = "tampered"
    elif tamper == "commit":
        document["source_commit"] = "0" * 40
    elif tamper == "module_order":
        document["modules"][0], document["modules"][1] = (
            document["modules"][1],
            document["modules"][0],
        )
    elif tamper == "blob":
        document["modules"][0]["git_blob"] = "0" * 40
    elif tamper == "digest":
        document["modules"][0]["sha256"] = "0" * 64
    else:
        document["allowed_current_source_differences"].append(
            "src/unreviewed.py"
        )
    tampered_provenance = tmp_path / "provenance.json"
    tampered_provenance.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        overhead,
        "A_SOURCE_PROVENANCE_PATH",
        tampered_provenance,
    )

    with pytest.raises(ValueError, match=message):
        load_and_verify_historical_a_source_provenance()


def test_nearest_rank_is_empirical_and_non_interpolating() -> None:
    values = [1, 2, 3, 4, 100]
    assert nearest_rank(values, 50) == 3
    assert nearest_rank(values, 95) == 100
    assert nearest_rank(values, 99) == 100


def test_cluster_bootstrap_targets_pooled_unit_median_not_block_medians() -> None:
    values_by_block = {
        block: (
            [0] * 10
            if block < 14
            else [0] * 4 + [100] * 6
        )
        for block in range(30)
    }
    pooled_values = [
        value
        for block in values_by_block.values()
        for value in block
    ]
    block_medians = [
        nearest_rank(block, 50) for block in values_by_block.values()
    ]
    assert nearest_rank(pooled_values, 50) == 0
    assert nearest_rank(block_medians, 50) == 100

    interval = block_bootstrap_median_ci(
        values_by_block,
        seed=7,
        repetitions=500,
    )

    assert interval["lower"] == 0
    assert interval["upper"] == 0
    assert interval["block_count"] == 30
    assert interval["units_per_block"] == 10
    assert interval["bootstrap_population_size"] == 300
    assert interval["statistic"] == "empirical nearest-rank median of pooled units"
    assert interval["within_block_units"] == "retained in full"


def test_comparisons_use_batch_units_and_direct_c_composition_lap() -> None:
    config = ScheduleConfig(
        layer=Layer.MICRO,
        warmups=0,
        recorded_blocks=1,
        repetitions_per_permutation=2,
    )
    samples = [
        _sample(surface=Surface.A, producer_elapsed_ns=100, repetition=0),
        _sample(surface=Surface.A, producer_elapsed_ns=1_000, repetition=1),
        _sample(surface=Surface.B, producer_elapsed_ns=130, repetition=0),
        _sample(surface=Surface.B, producer_elapsed_ns=900, repetition=1),
        _sample(
            surface=Surface.C,
            producer_elapsed_ns=120,
            composition_elapsed_ns=20,
            repetition=0,
        ),
        _sample(
            surface=Surface.C,
            producer_elapsed_ns=920,
            composition_elapsed_ns=40,
            repetition=1,
        ),
    ]
    summaries = compute_batch_summaries(samples, config=config)
    comparisons = compute_batch_comparisons(summaries)
    estimates = {
        comparison.comparison: comparison.estimate_ns
        for comparison in comparisons
    }
    assert estimates == {
        "B-A_END_TO_END": 30,
        "C-B_COMPOSITION_LAP": 20,
        "C-A_END_TO_END": 40,
        "C-B_TOTAL_SECONDARY": 10,
    }
    composition = next(
        comparison
        for comparison in comparisons
        if comparison.comparison == "C-B_COMPOSITION_LAP"
    )
    assert composition.experimental_unit == "recorded block/permutation batch"
    assert composition.role == "PRIMARY"
    assert composition.estimation_method.startswith("direct same-invocation")
    assert composition.relative_reference_metric == "A.total_median_ns"
    assert composition.relative_reference_summary_ns == 100
    assert composition.relative_estimate_percent == 20.0
    assert not hasattr(composition, "repetition_index")


def test_postgres_p99_is_withheld_for_fixed_population() -> None:
    config = ScheduleConfig(
        layer=Layer.POSTGRES,
        warmups=0,
        recorded_blocks=1,
        repetitions_per_permutation=1,
    )
    samples = [
        replace(
            _sample(surface=surface, producer_elapsed_ns=100 + index),
            layer=Layer.POSTGRES.value,
        )
        for index, surface in enumerate(Surface)
    ]
    summaries = compute_batch_summaries(samples, config=config)
    comparisons = compute_batch_comparisons(summaries)
    aggregates = aggregate_evidence(
        samples,
        summaries,
        comparisons,
        layer=Layer.POSTGRES,
        bootstrap_repetitions=10,
    )
    assert all(
        metric["p99"] is None
        for group in aggregates["absolute"].values()
        for metric in group["invocation_metrics"].values()
    )
    assert all(
        group["estimate_ns"]["p99"] is None
        for group in aggregates["batch_comparisons"].values()
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("block_index", 1),
        ("permutation_index", len(fixed_surface_permutations())),
        ("repetition_index", 1),
        ("scenario", "UNKNOWN_SCENARIO"),
        ("surface", "UNKNOWN_SURFACE"),
    ),
)
def test_population_validation_requires_every_unpooled_coordinate(
    field: str,
    invalid_value: int | str,
) -> None:
    config = ScheduleConfig(
        layer=Layer.MICRO,
        warmups=0,
        recorded_blocks=1,
        repetitions_per_permutation=1,
    )
    scenario = MICRO_SCENARIOS[0]
    samples = [
        replace(
            _sample(
                surface=surface,
                producer_elapsed_ns=100,
                permutation=permutation_index,
            ),
            scenario=scenario.name,
        )
        for permutation_index, _ in enumerate(fixed_surface_permutations())
        for surface in Surface
    ]
    validate_recorded_population(
        samples=samples,
        scenarios=(scenario,),
        config=config,
        run_id="unit-run",
    )
    with pytest.raises(ValueError, match="sample population mismatch"):
        validate_recorded_population(
            samples=samples[:-1],
            scenarios=(scenario,),
            config=config,
            run_id="unit-run",
        )

    duplicate_population = list(samples)
    duplicate_population[-1] = duplicate_population[0]
    with pytest.raises(ValueError, match="duplicate coordinates"):
        validate_recorded_population(
            samples=duplicate_population,
            scenarios=(scenario,),
            config=config,
            run_id="unit-run",
        )

    out_of_range_population = list(samples)
    out_of_range_population[-1] = replace(
        out_of_range_population[-1],
        **{field: invalid_value},
    )
    with pytest.raises(ValueError, match="coordinate universe mismatch"):
        validate_recorded_population(
            samples=out_of_range_population,
            scenarios=(scenario,),
            config=config,
            run_id="unit-run",
        )


def test_evidence_namespace_is_secret_free_and_immutable(tmp_path: Path) -> None:
    config = ScheduleConfig(
        layer=Layer.MICRO,
        warmups=0,
        recorded_blocks=1,
        repetitions_per_permutation=1,
    )
    samples = [
        _sample(surface=surface, producer_elapsed_ns=100)
        for surface in Surface
    ]
    summaries = compute_batch_summaries(samples, config=config)
    comparisons = compute_batch_comparisons(summaries)
    aggregates = aggregate_evidence(
        samples,
        summaries,
        comparisons,
        layer=Layer.MICRO,
        bootstrap_repetitions=10,
    )
    destination = write_immutable_evidence(
        output_root=tmp_path,
        run_id="unit-run",
        manifest={"run_id": "unit-run"},
        samples=samples,
        batch_summaries=summaries,
        batch_comparisons=comparisons,
        aggregates=aggregates,
    )
    assert {path.name for path in destination.iterdir()} == {
        "manifest.json",
        "samples.jsonl",
        "batch_summaries.jsonl",
        "batch_comparisons.jsonl",
        "aggregates.json",
    }
    with pytest.raises(FileExistsError):
        write_immutable_evidence(
            output_root=tmp_path,
            run_id="unit-run",
            manifest={"run_id": "unit-run"},
            samples=samples,
            batch_summaries=summaries,
            batch_comparisons=comparisons,
            aggregates=aggregates,
        )
    with pytest.raises(ValueError, match="forbidden secret marker"):
        assert_secret_free({"connection": "postgresql://secret"})
    for unsafe_run_id in (".", "..", "../escape", ".staging-private"):
        with pytest.raises(ValueError, match="run_id"):
            validate_run_id(unsafe_run_id)
