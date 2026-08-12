"""Deterministic tests for the PR7 canonical evidence persistence boundary."""

from __future__ import annotations

from collections import Counter
from dataclasses import FrozenInstanceError, fields, replace
import json
from pathlib import Path
from typing import Any

import pytest

import experiments.stage4b2.postgres_bounded_concurrency_evidence as evidence_module
from experiments.stage4b2.postgres_bounded_concurrency import (
    LEVEL_C_SCHEMA_NAME,
    LEVEL_C_SCHEMA_VERSION,
)
from experiments.stage4b2.postgres_bounded_concurrency_evidence import (
    ACCEPTED_SMOKE_RELEASE_SKEW_REVIEW,
    ACCEPTED_SMOKE_RUN_ID,
    ACCEPTED_SMOKE_SOURCE_COMMIT,
    CANONICAL_EVIDENCE_FILENAMES,
    CANONICAL_EVIDENCE_RELATIVE_ROOT,
    CANONICAL_EVIDENCE_SCHEMA_NAME,
    CANONICAL_EVIDENCE_SCHEMA_VERSION,
    CANONICAL_EXPECTED_BATCH_COUNT,
    CANONICAL_EXPECTED_INVOCATION_COUNT,
    CANONICAL_EXPECTED_OWNERSHIP_COUNT,
    CANONICAL_EXPECTED_RATE_GROUP_COUNT,
    CANONICAL_PUBLICATION_RULE,
    CanonicalEvidencePublicationError,
    CanonicalEvidenceValidationError,
    build_canonical_manifest,
    canonical_evidence_root,
    read_canonical_evidence_directory,
    write_canonical_evidence_directory,
)
from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    EXPECTED_PHASE_STATE_MATRICES,
    PR3_PHASE_NAMES,
    RECORDED_BATCHES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    RETAINED_WORKER_LEVELS,
    BatchRecord,
    Cohort,
    Composition,
    EvidenceStatus,
    InvocationRecord,
    LaneOwnershipRecord,
    PhaseRecord,
    PhaseState,
    RecordedExecutionResult,
    RejectionStage,
    RunValidationResult,
    TypedOutcomeCount,
    ValidationIssue,
    WorkloadFamily,
    aggregate_batch_rates,
    aggregate_invocations,
    generate_fixed_schedule,
    validate_recorded_run,
)


RUN_ID = "stage4b2-pr7-canonical-test"
SOURCE_COMMIT = "c6bcad7c1f4b74f8d0669688520ab2588efceaf2"


def _manifest(
    *,
    run_id: str = RUN_ID,
    source_commit: str = SOURCE_COMMIT,
    source_tree_clean_before_run: bool = True,
    postgresql_server_version: str = "160014",
) -> Any:
    return build_canonical_manifest(
        run_id=run_id,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        postgresql_server_version=postgresql_server_version,
        transaction_isolation="READ_COMMITTED",
        autocommit=False,
        topology_label="guarded-test-postgresql",
    )


def _cohort_for(plan: Any, lane_index: int) -> Cohort:
    if (
        plan.cell.workload_family
        is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
        or lane_index == 0
    ):
        return Cohort.ACCEPTED
    if plan.cell.composition is Composition.PRE_OCC:
        return Cohort.APPEND_STALE_WRITE
    return Cohort.PREPARE_LOCK_TIMEOUT


def _producer_fields(
    cohort: Cohort,
) -> tuple[str, RejectionStage | None, str | None, str | None]:
    if cohort is Cohort.ACCEPTED:
        return "ACCEPTED", None, "ADMITTED", "ADMITTED"
    if cohort is Cohort.APPEND_STALE_WRITE:
        return "ADMISSION_REJECTED", RejectionStage.APPEND, "ADMITTED", "STALE_WRITE"
    return (
        "ADMISSION_REJECTED",
        RejectionStage.PREPARE_STREAM,
        "LOCK_TIMEOUT",
        None,
    )


def _phases(composition: Composition, cohort: Cohort) -> tuple[PhaseRecord, ...]:
    matrix = EXPECTED_PHASE_STATE_MATRICES[(composition, cohort)]
    return tuple(
        PhaseRecord(
            name=name,
            state=matrix[name],
            elapsed_ns=(100 + index if matrix[name] is PhaseState.MEASURED else None),
        )
        for index, name in enumerate(PR3_PHASE_NAMES)
    )


def _typed_counts(
    records: tuple[InvocationRecord, ...],
) -> tuple[TypedOutcomeCount, ...]:
    counts = Counter(record.cohort.value for record in records if record.cohort)
    return tuple(
        TypedOutcomeCount(outcome=outcome, count=count)
        for outcome, count in sorted(counts.items())
    )


def _valid_result(*, run_id: str = RUN_ID) -> RecordedExecutionResult:
    schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    invocations: list[InvocationRecord] = []
    batches: list[BatchRecord] = []
    invocation_index = 0
    batch_record_index = 0
    for plan in schedule.recorded_batches:
        batch_invocations: list[InvocationRecord] = []
        for lane_index in range(plan.cell.worker_level):
            cohort = _cohort_for(plan, lane_index)
            producer, rejection, stream, append = _producer_fields(cohort)
            record = InvocationRecord(
                schema_name=LEVEL_C_SCHEMA_NAME,
                schema_version=LEVEL_C_SCHEMA_VERSION,
                run_id=run_id,
                invocation_index=invocation_index,
                cell_index=plan.cell.cell_index,
                batch_index=plan.batch_index,
                lane_index=lane_index,
                connection_slot=lane_index,
                worker_level=plan.cell.worker_level,
                workload_family=plan.cell.workload_family,
                composition=plan.cell.composition,
                external_elapsed_ns=1_000 + lane_index,
                start_offset_ns=lane_index * 10,
                producer_outcome=producer,
                rejection_stage=rejection,
                stream_admission_verdict=stream,
                append_admission_verdict=append,
                cohort=cohort,
                measurement_availability="AVAILABLE",
                phases=_phases(plan.cell.composition, cohort),
                exception_type=None,
            )
            invocations.append(record)
            batch_invocations.append(record)
            invocation_index += 1
        records = tuple(batch_invocations)
        batches.append(
            BatchRecord(
                schema_name=LEVEL_C_SCHEMA_NAME,
                schema_version=LEVEL_C_SCHEMA_VERSION,
                run_id=run_id,
                batch_record_index=batch_record_index,
                cell_index=plan.cell.cell_index,
                batch_index=plan.batch_index,
                worker_level=plan.cell.worker_level,
                workload_family=plan.cell.workload_family,
                composition=plan.cell.composition,
                release_reference_ns=1_000_000 + batch_record_index * 10_000,
                first_start_offset_ns=min(item.start_offset_ns for item in records),
                last_start_offset_ns=max(item.start_offset_ns for item in records),
                batch_elapsed_ns=max(
                    item.start_offset_ns + item.external_elapsed_ns
                    for item in records
                ),
                completed_count=len(records),
                accepted_count=sum(item.cohort is Cohort.ACCEPTED for item in records),
                typed_outcome_counts=_typed_counts(records),
            )
        )
        batch_record_index += 1
    ownership = tuple(
        LaneOwnershipRecord(
            worker_level=worker_level,
            lane_index=lane_index,
            connection_slot=lane_index,
            thread_id=worker_level * 1_000 + lane_index + 1,
        )
        for worker_level in RETAINED_WORKER_LEVELS
        for lane_index in range(worker_level)
    )
    validation = validate_recorded_run(
        schedule=schedule,
        invocations=invocations,
        batches=batches,
        ownership=ownership,
    )
    return RecordedExecutionResult(
        schedule=schedule,
        invocations=tuple(invocations),
        batches=tuple(batches),
        ownership=ownership,
        validation=validation,
    )


@pytest.fixture(scope="module")
def valid_result() -> RecordedExecutionResult:
    result = _valid_result()
    assert result.validation.status is EvidenceStatus.VALID
    assert result.validation.issues == ()
    return result


def _publish(
    repository_root: Path,
    result: RecordedExecutionResult,
    *,
    manifest: Any | None = None,
) -> Any:
    repository_root.mkdir(parents=True, exist_ok=True)
    return write_canonical_evidence_directory(
        repository_root=repository_root,
        manifest=_manifest() if manifest is None else manifest,
        result=result,
    )


def _invalid_result(
    result: RecordedExecutionResult,
    **changes: Any,
) -> RecordedExecutionResult:
    return replace(result, **changes)


def _assert_no_publication(
    repository_root: Path,
    result: RecordedExecutionResult,
) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(CanonicalEvidenceValidationError):
        write_canonical_evidence_directory(
            repository_root=repository_root,
            manifest=_manifest(),
            result=result,
        )
    assert not canonical_evidence_root(repository_root).exists()


def _all_json_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested
            for child in value.values()
            for nested in _all_json_keys(child)
        }
    if isinstance(value, list):
        return {
            nested
            for child in value
            for nested in _all_json_keys(child)
        }
    return set()


def test_canonical_namespace_is_exact(tmp_path: Path) -> None:
    assert canonical_evidence_root(tmp_path) == (
        tmp_path / CANONICAL_EVIDENCE_RELATIVE_ROOT
    )
    assert str(CANONICAL_EVIDENCE_RELATIVE_ROOT) == (
        "experiments/stage4b2/evidence/stage4b2-pr7-canonical-levelc"
    )


def test_manifest_is_frozen_and_has_exact_closed_keys() -> None:
    manifest = _manifest()
    assert manifest.schema_name == CANONICAL_EVIDENCE_SCHEMA_NAME
    assert manifest.schema_version == CANONICAL_EVIDENCE_SCHEMA_VERSION
    assert {item.name for item in fields(manifest)} == {
        "schema_name",
        "schema_version",
        "run_id",
        "source_commit",
        "source_tree_clean_before_run",
        "schedule_identity",
        "recorded_schedule_seed",
        "retained_worker_levels",
        "exact_cell_count",
        "warmup_batches_per_exact_cell",
        "recorded_batches_per_exact_cell",
        "expected_recorded_batch_count",
        "expected_recorded_invocation_count",
        "expected_ownership_count",
        "clock_identity",
        "postgresql_server_version",
        "transaction_isolation",
        "autocommit",
        "topology_label",
        "validation_status",
        "smoke_source_commit",
        "smoke_run_id",
        "smoke_release_skew_review",
        "publication_rule",
    }
    with pytest.raises(FrozenInstanceError):
        manifest.run_id = "changed"  # type: ignore[misc]


def test_manifest_freezes_schedule_counts_and_smoke_lineage() -> None:
    manifest = _manifest()
    assert manifest.recorded_schedule_seed == 73
    assert manifest.schedule_identity == (
        "stage4b2-pr7-seed73-levels1-2-4-8-cells16-warmup3-recorded30"
    )
    assert manifest.retained_worker_levels == (1, 2, 4, 8)
    assert manifest.exact_cell_count == 16
    assert manifest.warmup_batches_per_exact_cell == 3
    assert manifest.recorded_batches_per_exact_cell == 30
    assert manifest.expected_recorded_batch_count == 480
    assert manifest.expected_recorded_invocation_count == 1_800
    assert manifest.expected_ownership_count == 15
    assert manifest.clock_identity == "time.perf_counter_ns"
    assert manifest.validation_status == "VALID"
    assert manifest.smoke_source_commit == ACCEPTED_SMOKE_SOURCE_COMMIT
    assert manifest.smoke_run_id == ACCEPTED_SMOKE_RUN_ID
    assert manifest.smoke_release_skew_review == ACCEPTED_SMOKE_RELEASE_SKEW_REVIEW
    assert manifest.publication_rule == CANONICAL_PUBLICATION_RULE


@pytest.mark.parametrize("source_commit", ("c6bcad7", "G" * 40, "a" * 39, "A" * 40))
def test_manifest_rejects_invalid_source_commit(source_commit: str) -> None:
    with pytest.raises(ValueError, match="full lowercase"):
        _manifest(source_commit=source_commit)


def test_dirty_source_cannot_construct_publishable_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="clean source"):
        _manifest(source_tree_clean_before_run=False)
    assert not (tmp_path / CANONICAL_EVIDENCE_RELATIVE_ROOT).exists()


def test_manifest_rejects_connection_shaped_runtime_fact() -> None:
    with pytest.raises(ValueError, match="sanitized"):
        _manifest(
            postgresql_server_version=(
                "postgresql://user:password@host.example/database"
            )
        )


def test_valid_publication_contains_exactly_six_files(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    assert readback.run_directory == canonical_evidence_root(tmp_path) / RUN_ID
    assert {item.name for item in readback.run_directory.iterdir()} == set(
        CANONICAL_EVIDENCE_FILENAMES
    )
    assert len(tuple(readback.run_directory.iterdir())) == 6


def test_manifest_json_has_exact_closed_keys(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    payload = json.loads((readback.run_directory / "manifest.json").read_text())
    assert set(payload) == {item.name for item in fields(readback.manifest)}
    assert payload["smoke_source_commit"] == ACCEPTED_SMOKE_SOURCE_COMMIT
    assert payload["smoke_run_id"] == ACCEPTED_SMOKE_RUN_ID
    assert payload["smoke_release_skew_review"] == "ACCEPTED"


def test_serialization_is_deterministic_across_repository_roots(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    first = _publish(tmp_path / "first", valid_result)
    second = _publish(tmp_path / "second", valid_result)
    assert {
        name: (first.run_directory / name).read_bytes()
        for name in CANONICAL_EVIDENCE_FILENAMES
    } == {
        name: (second.run_directory / name).read_bytes()
        for name in CANONICAL_EVIDENCE_FILENAMES
    }


def test_invocation_jsonl_round_trips_exact_frozen_records(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    lines = (readback.run_directory / "invocations.jsonl").read_text().splitlines()
    assert len(lines) == CANONICAL_EXPECTED_INVOCATION_COUNT == 1_800
    assert readback.result.invocations == valid_result.invocations
    first = json.loads(lines[0])
    assert set(first) == {
        "schema_name",
        "schema_version",
        "run_id",
        "invocation_index",
        "cell_index",
        "batch_index",
        "lane_index",
        "connection_slot",
        "worker_level",
        "workload_family",
        "composition",
        "external_elapsed_ns",
        "start_offset_ns",
        "producer_outcome",
        "rejection_stage",
        "stream_admission_verdict",
        "append_admission_verdict",
        "cohort",
        "measurement_availability",
        "phases",
        "exception_type",
    }
    assert len(first["phases"]) == 13
    assert [phase["name"] for phase in first["phases"]] == list(PR3_PHASE_NAMES)
    assert first["exception_type"] is None
    assert {"request_id", "order_id", "attempt_id", "execution_id"}.isdisjoint(first)


def test_batch_jsonl_round_trips_exact_frozen_records(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    lines = (readback.run_directory / "batches.jsonl").read_text().splitlines()
    assert len(lines) == CANONICAL_EXPECTED_BATCH_COUNT == 480
    assert readback.result.batches == valid_result.batches
    assert "release_skew_ns" not in json.loads(lines[0])


def test_ownership_round_trips_in_deterministic_order(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    payload = json.loads((readback.run_directory / "ownership.json").read_text())
    assert len(payload) == CANONICAL_EXPECTED_OWNERSHIP_COUNT == 15
    assert all(
        set(item) == {"worker_level", "lane_index", "connection_slot", "thread_id"}
        for item in payload
    )
    assert readback.result.ownership == tuple(
        sorted(
            valid_result.ownership,
            key=lambda item: (
                item.worker_level,
                item.lane_index,
                item.connection_slot,
                item.thread_id,
            ),
        )
    )


def test_invocation_aggregates_are_existing_exact_nonpooled_aggregation(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    expected = aggregate_invocations(valid_result.invocations)
    assert readback.invocation_aggregates == expected
    keys = {
        (
            item.worker_level,
            item.workload_family,
            item.composition,
            item.cohort,
        )
        for item in readback.invocation_aggregates
    }
    assert len(keys) == len(readback.invocation_aggregates)
    assert any(item[-1] is Cohort.APPEND_STALE_WRITE for item in keys)
    assert any(item[-1] is Cohort.PREPARE_LOCK_TIMEOUT for item in keys)
    payload = json.loads(
        (readback.run_directory / "invocation_aggregates.json").read_text()
    )
    statistics_keys = set(payload[0]["external_elapsed_ns"])
    assert statistics_keys == {"count", "minimum", "maximum", "mean", "median"}
    assert "p95" not in _all_json_keys(payload)
    assert "summed_phase" not in _all_json_keys(payload)
    assert {"pre_score", "in_score", "strategy_score"}.isdisjoint(
        _all_json_keys(payload)
    )


def test_batch_rate_aggregates_are_existing_exact_synchronized_burst_groups(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    assert readback.batch_rate_aggregates == aggregate_batch_rates(
        valid_result.batches
    )
    assert len(readback.batch_rate_aggregates) == CANONICAL_EXPECTED_RATE_GROUP_COUNT
    assert all(
        item.accepted_completion_rate_per_second.count
        == RECORDED_BATCHES_PER_CELL
        and item.all_completion_rate_per_second.count
        == RECORDED_BATCHES_PER_CELL
        for item in readback.batch_rate_aggregates
    )
    payload = json.loads(
        (readback.run_directory / "batch_rate_aggregates.json").read_text()
    )
    assert all(
        set(item) == {
            "run_id",
            "worker_level",
            "workload_family",
            "composition",
            "accepted_completion_rate_per_second",
            "all_completion_rate_per_second",
        }
        for item in payload
    )


def test_invalid_runtime_status_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    invalid = _invalid_result(
        valid_result,
        validation=RunValidationResult(
            status=EvidenceStatus.INVALID_RUN,
            issues=(ValidationIssue("TEST_INVALID", "sanitized"),),
        ),
    )
    _assert_no_publication(tmp_path, invalid)


def test_noncanonical_schedule_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    altered_schedule = replace(
        valid_result.schedule,
        cells=tuple(reversed(valid_result.schedule.cells)),
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, schedule=altered_schedule),
    )


@pytest.mark.parametrize("missing_kind", ("invocation", "batch", "ownership"))
def test_missing_exact_accounting_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    missing_kind: str,
) -> None:
    changes = {
        "invocation": {"invocations": valid_result.invocations[:-1]},
        "batch": {"batches": valid_result.batches[:-1]},
        "ownership": {"ownership": valid_result.ownership[:-1]},
    }[missing_kind]
    _assert_no_publication(tmp_path, _invalid_result(valid_result, **changes))


def test_wrong_phase_state_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    original = next(
        item
        for item in valid_result.invocations
        if item.composition is Composition.PRE_OCC and item.cohort is Cohort.ACCEPTED
    )
    phases = tuple(
        PhaseRecord(phase.name, PhaseState.MEASURED, 999)
        if phase.name == "pessimistic_advisory_try_lock_call"
        else phase
        for phase in original.phases or ()
    )
    altered = replace(original, phases=phases)
    invocations = tuple(
        altered if item is original else item for item in valid_result.invocations
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, invocations=invocations),
    )


def test_wrong_phase_order_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    original = valid_result.invocations[0]
    altered = replace(original, phases=tuple(reversed(original.phases or ())))
    invocations = tuple(
        altered if item is original else item for item in valid_result.invocations
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, invocations=invocations),
    )


def test_unsupported_cohort_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    original = valid_result.invocations[0]
    altered = replace(original, cohort=Cohort.PREPARE_LOCK_TIMEOUT)
    invocations = tuple(
        altered if item is original else item for item in valid_result.invocations
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, invocations=invocations),
    )


def test_different_order_nonaccepted_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    original = next(
        item
        for item in valid_result.invocations
        if item.workload_family is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
        and item.composition is Composition.PRE_OCC
    )
    altered = replace(
        original,
        producer_outcome="ADMISSION_REJECTED",
        rejection_stage=RejectionStage.APPEND,
        stream_admission_verdict="ADMITTED",
        append_admission_verdict="STALE_WRITE",
        cohort=Cohort.APPEND_STALE_WRITE,
        phases=_phases(Composition.PRE_OCC, Cohort.APPEND_STALE_WRITE),
    )
    invocations = tuple(
        altered if item is original else item for item in valid_result.invocations
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, invocations=invocations),
    )


def test_runtime_exception_evidence_writes_nothing(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    original = valid_result.invocations[0]
    altered = replace(
        original,
        producer_outcome=None,
        rejection_stage=None,
        stream_admission_verdict=None,
        append_admission_verdict=None,
        cohort=None,
        measurement_availability=None,
        phases=None,
        exception_type="SanitizedFailure",
    )
    invocations = tuple(
        altered if item is original else item for item in valid_result.invocations
    )
    _assert_no_publication(
        tmp_path,
        _invalid_result(valid_result, invocations=invocations),
    )


def test_existing_final_run_is_never_overwritten(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    first = _publish(tmp_path, valid_result)
    before = {
        name: (first.run_directory / name).read_bytes()
        for name in CANONICAL_EVIDENCE_FILENAMES
    }
    with pytest.raises(CanonicalEvidencePublicationError, match="immutable"):
        write_canonical_evidence_directory(
            repository_root=tmp_path,
            manifest=_manifest(),
            result=valid_result,
        )
    assert before == {
        name: (first.run_directory / name).read_bytes()
        for name in CANONICAL_EVIDENCE_FILENAMES
    }


def test_writer_requires_readback_manifest_equality(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = evidence_module.read_canonical_evidence_directory

    def substitute_manifest(**kwargs: Any) -> Any:
        readback = original(**kwargs)
        return replace(
            readback,
            manifest=replace(readback.manifest, source_commit="a" * 40),
        )

    monkeypatch.setattr(
        evidence_module,
        "read_canonical_evidence_directory",
        substitute_manifest,
    )
    with pytest.raises(CanonicalEvidenceValidationError, match="in-memory"):
        write_canonical_evidence_directory(
            repository_root=tmp_path,
            manifest=_manifest(),
            result=valid_result,
        )
    assert (canonical_evidence_root(tmp_path) / RUN_ID).is_dir()


def test_reader_rejects_wrong_namespace(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    wrong = tmp_path / "experiments/stage4b2/evidence/stage4b2-pr6" / RUN_ID
    with pytest.raises(CanonicalEvidenceValidationError, match="fixed canonical"):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=wrong,
        )
    assert readback.run_directory.is_dir()


@pytest.mark.parametrize(
    "protected_namespace",
    (
        "stage4b2-pr6-canonical-protected",
        "stage4b2-post-pr6-supplemental-protected",
        "stage4b2-pr7-postgres-smoke-protected",
    ),
)
def test_protected_evidence_ancestry_cannot_masquerade_as_repository_root(
    tmp_path: Path,
    protected_namespace: str,
) -> None:
    protected = (
        tmp_path
        / "experiments/stage4b2/evidence"
        / protected_namespace
    )
    protected.mkdir(parents=True)
    with pytest.raises(CanonicalEvidenceValidationError, match="ancestry"):
        canonical_evidence_root(protected)


def test_partial_write_failure_leaves_no_visible_final_or_staging_directory(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = evidence_module._write_payload_file
    calls = 0

    def fail_on_third_file(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("synthetic failure")
        original(path, content)

    monkeypatch.setattr(evidence_module, "_write_payload_file", fail_on_third_file)
    with pytest.raises(CanonicalEvidencePublicationError, match="atomic publication"):
        write_canonical_evidence_directory(
            repository_root=tmp_path,
            manifest=_manifest(),
            result=valid_result,
        )
    root = canonical_evidence_root(tmp_path)
    assert not (root / RUN_ID).exists()
    assert tuple(root.iterdir()) == ()


def test_publication_fsyncs_six_files_staging_directory_and_evidence_root(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fsync_descriptors: list[int] = []
    monkeypatch.setattr(
        evidence_module.os,
        "fsync",
        lambda descriptor: fsync_descriptors.append(descriptor),
    )
    _publish(tmp_path, valid_result)
    assert len(fsync_descriptors) == 8


@pytest.mark.parametrize("missing_name", CANONICAL_EVIDENCE_FILENAMES)
def test_readback_requires_every_exact_file(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    missing_name: str,
) -> None:
    readback = _publish(tmp_path, valid_result)
    (readback.run_directory / missing_name).unlink()
    with pytest.raises(CanonicalEvidenceValidationError, match="exactly the six"):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


def test_readback_rejects_extra_file(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    (readback.run_directory / "seventh.json").write_text("{}\n")
    with pytest.raises(CanonicalEvidenceValidationError, match="exactly the six"):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


def test_readback_rejects_run_id_mismatch(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    path = readback.run_directory / "invocations.jsonl"
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["run_id"] = "different-run"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(CanonicalEvidenceValidationError):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    (("invocations.jsonl", "1800"), ("batches.jsonl", "480")),
)
def test_readback_requires_exact_invocation_and_batch_counts(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
    filename: str,
    expected_count: str,
) -> None:
    readback = _publish(tmp_path, valid_result)
    path = readback.run_directory / filename
    path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(CanonicalEvidenceValidationError, match=expected_count):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


def test_readback_recomputes_invocation_aggregates_exactly(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    path = readback.run_directory / "invocation_aggregates.json"
    payload = json.loads(path.read_text())
    for name in ("minimum", "maximum", "mean", "median"):
        payload[0]["external_elapsed_ns"][name] += 1
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(CanonicalEvidenceValidationError, match="recomputation"):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


def test_readback_recomputes_batch_rate_aggregates_exactly(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    path = readback.run_directory / "batch_rate_aggregates.json"
    payload = json.loads(path.read_text())
    for name in ("minimum", "maximum", "mean", "median"):
        payload[0]["all_completion_rate_per_second"][name] += 1
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(CanonicalEvidenceValidationError, match="recomputation"):
        read_canonical_evidence_directory(
            repository_root=tmp_path,
            run_directory=readback.run_directory,
        )


def test_readback_reconstructs_fresh_valid_runtime_result(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    assert readback.result.validation.status is EvidenceStatus.VALID
    assert readback.result.validation.issues == ()
    assert len(readback.result.invocations) == 1_800
    assert len(readback.result.batches) == 480
    assert len(readback.result.ownership) == 15


def test_serialized_output_excludes_secret_endpoint_and_smoke_timing_markers(
    tmp_path: Path,
    valid_result: RecordedExecutionResult,
) -> None:
    readback = _publish(tmp_path, valid_result)
    combined = "\n".join(
        (readback.run_directory / name).read_text().casefold()
        for name in CANONICAL_EVIDENCE_FILENAMES
    )
    for marker in (
        "test_database_url",
        "postgresql://",
        "dsn=",
        "password",
        "credential",
        "hostname",
        "database_name",
        "smoke_cell_index",
        "smoke_invocation_elapsed",
        "smoke_batch_elapsed",
    ):
        assert marker not in combined


def test_module_exposes_no_runner_persistence_side_effect_or_policy() -> None:
    assert not hasattr(evidence_module, "main")
    assert not hasattr(evidence_module, "run_canonical")
    assert not hasattr(evidence_module, "run_postgres")
    assert not hasattr(evidence_module, "rate_limit")
    assert not hasattr(evidence_module, "safe_concurrency")
    assert not hasattr(evidence_module, "capacity")
    assert not hasattr(evidence_module, "saturation_point")
