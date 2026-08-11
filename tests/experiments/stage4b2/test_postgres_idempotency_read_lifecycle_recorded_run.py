from __future__ import annotations

from collections import Counter
from dataclasses import replace
import importlib
import inspect
from io import StringIO
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.stage4b2 import (
    postgres_idempotency_read_lifecycle_recorded_run as runner,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleSample,
    IdempotencyVerdictIdentity,
    Layer3Control,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_evidence import (
    DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT,
    EVIDENCE_FILENAMES,
    EvidenceWriteResult,
    PublishedLayer3Evidence,
    build_manifest,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_recorded_run import (
    EXPECTED_BRANCH,
    PROJECT_ROOT,
    RUN_ID_PREFIX,
    OneShotRunFailure,
    RunnerDependencies,
    main,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime import (
    Layer3RuntimeResult,
)


FULL_HEAD = "6fea23a647e86759397cd5e0a89a68c2db5d76c5"
RUN_ID = f"{RUN_ID_PREFIX}{FULL_HEAD[:7]}"
SECRET_DATABASE_URL = "postgresql://secret-marker.invalid/example_test"


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


def _runtime_result(samples=None):
    observed = _samples() if samples is None else tuple(samples)
    schedule = generate_recorded_schedule()
    return Layer3RuntimeResult(
        schedule=schedule,
        samples=observed,
        validation=validate_run(schedule, observed),
    )


class _Harness:
    def __init__(self) -> None:
        self.repository_root = PROJECT_ROOT
        self.branch = EXPECTED_BRANCH
        self.head = FULL_HEAD
        self.status = ""
        self.database_url = SECRET_DATABASE_URL
        self.run_directory_exists = False
        self.runtime_result = _runtime_result()
        self.metadata_error = None
        self.runtime_error = None
        self.writer_error = None
        self.reader_error = None
        self.git_calls = []
        self.events = []
        self.runtime_calls = 0
        self.writer_calls = 0
        self.reader_calls = 0
        self.captured_manifest = None
        self.captured_output_root = None
        self.captured_result = None
        self.publication = None
        self.published_override = None

    def git_output(self, arguments) -> str:
        arguments = tuple(arguments)
        self.git_calls.append(arguments)
        return {
            ("rev-parse", "--show-toplevel"): str(self.repository_root),
            ("branch", "--show-current"): self.branch,
            ("rev-parse", "HEAD"): self.head,
            (
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
            ): self.status,
        }[arguments]

    def environment_value(self, name: str) -> str | None:
        assert name == "TEST_DATABASE_URL"
        return self.database_url

    def path_exists(self, path: Path) -> bool:
        assert path == DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT / RUN_ID
        return self.run_directory_exists

    def server_version_loader(self, database_url: str) -> str:
        assert database_url == self.database_url
        self.events.append("metadata")
        if self.metadata_error is not None:
            raise self.metadata_error
        return "PostgreSQL 16.3"

    def recorded_runner(self, database_url: str, *, run_id: str):
        assert database_url == self.database_url
        assert run_id == RUN_ID
        self.events.append("runtime")
        self.runtime_calls += 1
        if self.runtime_error is not None:
            raise self.runtime_error
        return self.runtime_result

    def evidence_writer(self, *, output_root, manifest, result):
        self.events.append("writer")
        self.writer_calls += 1
        if self.writer_error is not None:
            raise self.writer_error
        self.captured_output_root = output_root
        self.captured_manifest = manifest
        self.captured_result = result
        directory = output_root / manifest.run_id
        self.publication = EvidenceWriteResult(
            directory=directory,
            manifest_path=directory / "manifest.json",
            samples_path=directory / "samples.jsonl",
            aggregates_path=directory / "aggregates.json",
        )
        return self.publication

    def evidence_reader(self, directory: Path):
        self.events.append("reader")
        self.reader_calls += 1
        if self.reader_error is not None:
            raise self.reader_error
        assert self.publication is not None
        assert directory == self.publication.directory
        if self.published_override is not None:
            return self.published_override
        return PublishedLayer3Evidence(
            manifest=self.captured_manifest,
            samples=self.captured_result.samples,
            aggregates=aggregate_recorded_samples(self.captured_result.samples),
        )

    def dependencies(self) -> RunnerDependencies:
        return RunnerDependencies(
            git_output=self.git_output,
            environment_value=self.environment_value,
            path_exists=self.path_exists,
            server_version_loader=self.server_version_loader,
            recorded_runner=self.recorded_runner,
            manifest_builder=build_manifest,
            evidence_writer=self.evidence_writer,
            evidence_reader=self.evidence_reader,
        )


def test_import_performs_no_execution() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import experiments.stage4b2."
                "postgres_idempotency_read_lifecycle_recorded_run; "
                "print('IMPORTED')"
            ),
        ],
        cwd=PROJECT_ROOT,
        env={},
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == "IMPORTED\n"
    assert completed.stderr == ""


def test_git_root_branch_head_and_clean_state_are_derived_directly() -> None:
    harness = _Harness()

    summary = runner._run_one_shot(harness.dependencies())

    assert summary.branch == EXPECTED_BRANCH
    assert summary.full_source_head == FULL_HEAD
    assert summary.source_tree_clean_before_run is True
    assert harness.git_calls == [
        ("rev-parse", "--show-toplevel"),
        ("branch", "--show-current"),
        ("rev-parse", "HEAD"),
        ("status", "--porcelain=v1", "--untracked-files=normal"),
    ]


@pytest.mark.parametrize(
    ("attribute", "value", "expected_stage"),
    (
        ("status", "?? untracked-file", "working_tree"),
        ("branch", "different-branch", "branch"),
        ("database_url", "", "database_configuration"),
        ("database_url", None, "database_configuration"),
        ("run_directory_exists", True, "evidence_directory"),
        ("repository_root", PROJECT_ROOT / "unexpected", "repository_root"),
    ),
)
def test_pre_sample_gate_stops_before_runtime(
    attribute,
    value,
    expected_stage,
) -> None:
    harness = _Harness()
    setattr(harness, attribute, value)

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == expected_stage
    assert captured.value.authorization_consumed is False
    assert harness.runtime_calls == 0
    assert harness.writer_calls == 0
    assert harness.reader_calls == 0


def test_run_id_uses_exactly_the_first_seven_head_characters() -> None:
    harness = _Harness()

    summary = runner._run_one_shot(harness.dependencies())

    assert summary.run_id == "stage4b2-post-pr6-idempotency-layer3-6fea23a"
    assert "run_id" not in inspect.signature(runner._run_one_shot).parameters
    assert not hasattr(summary, "alternate_run_id")


def test_metadata_failure_is_pre_run_and_does_not_consume_authorization() -> None:
    harness = _Harness()
    harness.metadata_error = RuntimeError("sensitive endpoint details")

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == "guarded_server_metadata"
    assert captured.value.error_type == "RuntimeError"
    assert captured.value.authorization_consumed is False
    assert harness.runtime_calls == 0


def test_success_calls_the_recorded_runtime_exactly_once() -> None:
    harness = _Harness()

    summary = runner._run_one_shot(harness.dependencies())

    assert summary.total_samples == 60
    assert summary.control_a_samples == 30
    assert summary.control_b_samples == 30
    assert harness.runtime_calls == 1
    assert harness.events == ["metadata", "runtime", "writer", "reader"]


def test_runtime_exception_is_consumed_and_never_retried() -> None:
    harness = _Harness()
    harness.runtime_error = RuntimeError("sensitive database failure")

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == "recorded_runtime"
    assert captured.value.error_type == "RuntimeError"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 0


def test_invalid_runtime_result_does_not_publish() -> None:
    harness = _Harness()
    harness.runtime_result = _runtime_result(_samples()[:-1])

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == "recorded_validation"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 0


def test_lifecycle_invalidity_is_rejected_before_publication() -> None:
    harness = _Harness()
    samples = list(_samples())
    samples[1] = replace(
        samples[1],
        returned_idempotency_verdict=IdempotencyVerdictIdentity.REPLAY,
    )
    harness.runtime_result = _runtime_result(samples)

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == "recorded_validation"
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 0


@pytest.mark.parametrize("failure_stage", ("publication", "read_back"))
def test_post_runtime_failure_never_retries_the_runtime(failure_stage) -> None:
    harness = _Harness()
    if failure_stage == "publication":
        harness.writer_error = OSError("sensitive publication path")
    else:
        harness.reader_error = ValueError("sensitive read-back detail")

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == failure_stage
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 1
    assert harness.reader_calls == (1 if failure_stage == "read_back" else 0)


def test_valid_run_builds_exact_manifest_and_layer3_publication() -> None:
    harness = _Harness()

    summary = runner._run_one_shot(harness.dependencies())

    manifest = harness.captured_manifest
    assert manifest.run_id == RUN_ID
    assert manifest.source_commit == FULL_HEAD
    assert manifest.source_tree_clean_before_run is True
    assert manifest.postgresql_server_version == "PostgreSQL 16.3"
    assert harness.captured_output_root == DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT
    assert harness.publication.directory == (
        DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT / RUN_ID
    )
    assert summary.evidence_directory == (
        "experiments/stage4b2/evidence/"
        "stage4b2-post-pr6-idempotency-read-lifecycle-layer3/"
        f"{RUN_ID}"
    )


def test_read_back_checks_exact_three_files_and_recomputed_evidence() -> None:
    harness = _Harness()

    runner._run_one_shot(harness.dependencies())

    assert harness.reader_calls == 1
    paths = {
        harness.publication.manifest_path,
        harness.publication.samples_path,
        harness.publication.aggregates_path,
    }
    assert {path.name for path in paths} == EVIDENCE_FILENAMES
    assert Counter(sample.control for sample in harness.captured_result.samples) == {
        Layer3Control.CONTROL_A_IDLE_ROLLBACK: 30,
        Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE: 30,
    }


def test_read_back_sample_mismatch_never_retries_runtime() -> None:
    harness = _Harness()
    manifest = build_manifest(
        run_id=RUN_ID,
        source_commit=FULL_HEAD,
        source_tree_clean_before_run=True,
        postgresql_server_version="PostgreSQL 16.3",
    )
    samples = _samples()[:-1]
    harness.published_override = PublishedLayer3Evidence(
        manifest=manifest,
        samples=samples,
        aggregates=aggregate_recorded_samples(_samples()),
    )

    with pytest.raises(OneShotRunFailure) as captured:
        runner._run_one_shot(harness.dependencies())

    assert captured.value.stage == "read_back"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1


def test_success_summary_is_sanitized_and_has_independent_timing_groups() -> None:
    harness = _Harness()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        dependencies=harness.dependencies(),
        stdout=stdout,
        stderr=stderr,
    )

    output = stdout.getvalue()
    lowered = output.lower()
    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "samples=60" in output
    assert "control_a_samples=30" in output
    assert "control_b_samples=30" in output
    assert "validation=VALID" in output
    assert "exceptions=0" in output
    assert output.count(" timing=") == 5
    assert "timing=cleanup" in output
    assert "timing=idempotency_check" in output
    assert "timing=accepted_history_load" in output
    assert "timing=direct_lifecycle" in output
    assert SECRET_DATABASE_URL not in output
    for forbidden in (
        "component_sum",
        "database_total",
        "synthetic",
        "strategy_winner",
        "superior",
        "capacity",
        "rate_limit",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize(
    ("attribute", "failure_stage", "consumed"),
    (
        ("metadata_error", "guarded_server_metadata", "false"),
        ("runtime_error", "recorded_runtime", "true"),
    ),
)
def test_failure_summary_prints_only_stage_class_and_consumption(
    attribute,
    failure_stage,
    consumed,
) -> None:
    harness = _Harness()
    secret_message = f"do not print {SECRET_DATABASE_URL}"
    setattr(harness, attribute, RuntimeError(secret_message))
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        dependencies=harness.dependencies(),
        stdout=stdout,
        stderr=stderr,
    )

    failure = stderr.getvalue()
    assert exit_code != 0
    assert stdout.getvalue() == ""
    assert f"stage={failure_stage}" in failure
    assert "error_type=RuntimeError" in failure
    assert f"authorization_consumed={consumed}" in failure
    assert secret_message not in failure
    assert SECRET_DATABASE_URL not in failure


def test_default_server_version_loader_guards_and_closes_connection(
    monkeypatch,
) -> None:
    events = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, sql):
            events.append(("execute", sql))

        def fetchone(self):
            return ("PostgreSQL 16.3",)

    class _Connection:
        def cursor(self):
            return _Cursor()

        def rollback(self):
            events.append("rollback")

        def close(self):
            events.append("close")

    connection = _Connection()
    connection_module = importlib.import_module("src.storage.postgres_connection")
    runtime_module = importlib.import_module(
        "experiments.stage4b2.postgres_idempotency_check_runtime"
    )
    monkeypatch.setattr(
        connection_module,
        "connect_postgres",
        lambda database_url: (
            events.append(("connect", database_url)) or connection
        ),
    )
    monkeypatch.setattr(
        runtime_module,
        "_guard_test_connection",
        lambda observed: events.append(("guard", observed)),
    )

    observed = runner._load_guarded_server_version(SECRET_DATABASE_URL)

    assert observed == "PostgreSQL 16.3"
    assert events == [
        ("connect", SECRET_DATABASE_URL),
        ("guard", connection),
        ("execute", "SHOW server_version"),
        "rollback",
        "rollback",
        "close",
    ]


def test_runner_exposes_no_alternate_control_or_interpretation_surface() -> None:
    assert "run_id" not in inspect.signature(runner._run_one_shot).parameters
    assert not hasattr(runner, "retry_recorded_run")
    assert not hasattr(runner, "alternate_run_id")
    assert not hasattr(runner, "run_layer4")
    assert not hasattr(runner, "PRE_NO_PRELIMINARY")
    assert not hasattr(runner, "IN_OCC")
    assert not hasattr(runner, "StrategyWinner")
    assert not hasattr(runner, "component_sum")
    assert not hasattr(runner, "database_total")
