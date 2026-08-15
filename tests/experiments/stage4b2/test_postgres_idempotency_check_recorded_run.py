from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import importlib
import inspect
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from experiments.stage4b2 import postgres_idempotency_check_recorded_run as runner
from experiments.stage4b2.postgres_idempotency_check_characterization import (
    ALL_CELLS,
    Layer2Context,
    Layer2Sample,
    RunValidity,
    SCHEMA_VERSION,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_check_evidence import (
    DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT,
    EvidenceWriteResult,
    PublishedLayer2Evidence,
    build_manifest,
    manifest_to_json,
)
from experiments.stage4b2.postgres_idempotency_check_recorded_run import (
    EXPECTED_BRANCH,
    PROJECT_ROOT,
    RUN_ID_PREFIX,
    OneShotRunFailure,
    RunnerDependencies,
    main,
    run_one_shot,
)
from experiments.stage4b2.postgres_idempotency_check_runtime import (
    Layer2RuntimeResult,
)


FULL_HEAD = "8cade928f54a272a19003991a3848e296dfb88e1"
RUN_ID = f"{RUN_ID_PREFIX}{FULL_HEAD[:7]}"
SECRET_DATABASE_URL = "postgresql://secret-marker.invalid/example"


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


def _runtime_result(
    samples: tuple[Layer2Sample, ...] | None = None,
) -> Layer2RuntimeResult:
    observed = _samples() if samples is None else samples
    schedule = generate_recorded_schedule()
    return Layer2RuntimeResult(
        schedule=schedule,
        samples=observed,
        validation=validate_run(schedule, observed),
    )


class _Harness:
    def __init__(self) -> None:
        self.branch = EXPECTED_BRANCH
        self.head = FULL_HEAD
        self.status = ""
        self.database_url = SECRET_DATABASE_URL
        self.run_directory_exists = False
        self.runtime_result = _runtime_result()
        self.git_calls = []
        self.events = []
        self.runtime_calls = 0
        self.writer_calls = 0
        self.reader_calls = 0
        self.captured_manifest = None
        self.captured_output_root = None
        self.captured_samples = None
        self.publication = None

    def git_output(self, arguments) -> str:
        arguments = tuple(arguments)
        self.git_calls.append(arguments)
        return {
            ("rev-parse", "--show-toplevel"): str(PROJECT_ROOT),
            ("branch", "--show-current"): self.branch,
            ("rev-parse", "HEAD"): self.head,
            ("status", "--porcelain=v1", "--untracked-files=normal"): self.status,
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
        return "16.3"

    def recorded_runner(self, database_url: str, *, run_id: str):
        assert database_url == self.database_url
        assert run_id == RUN_ID
        self.events.append("runtime")
        self.runtime_calls += 1
        return self.runtime_result

    def evidence_writer(self, *, output_root, manifest, samples):
        self.events.append("writer")
        self.writer_calls += 1
        self.captured_output_root = output_root
        self.captured_manifest = manifest
        self.captured_samples = tuple(samples)
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
        assert self.publication is not None
        assert directory == self.publication.directory
        return PublishedLayer2Evidence(
            manifest=self.captured_manifest,
            samples=self.captured_samples,
            aggregates=aggregate_recorded_samples(self.captured_samples),
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
    environment = dict(os.environ)
    environment.pop("TEST_DATABASE_URL", None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import experiments.stage4b2."
                "postgres_idempotency_check_recorded_run; print('IMPORTED')"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == "IMPORTED\n"
    assert completed.stderr == ""


def test_git_head_branch_root_and_clean_status_are_read_directly() -> None:
    harness = _Harness()

    summary = run_one_shot(harness.dependencies())

    assert summary.full_source_head == FULL_HEAD
    assert summary.branch == EXPECTED_BRANCH
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
        run_one_shot(harness.dependencies())

    assert captured.value.stage == expected_stage
    assert captured.value.authorization_consumed is False
    assert harness.runtime_calls == 0
    assert harness.writer_calls == 0


def test_run_id_is_exactly_first_seven_head_characters() -> None:
    harness = _Harness()

    summary = run_one_shot(harness.dependencies())

    assert summary.run_id == "stage4b2-post-pr6-idempotency-layer2-8cade92"
    assert not hasattr(summary, "alternate_run_id")
    assert "run_id" not in inspect.signature(run_one_shot).parameters


def test_metadata_failure_is_pre_sample_and_does_not_call_runtime() -> None:
    harness = _Harness()
    dependencies = replace(
        harness.dependencies(),
        server_version_loader=lambda _: (_ for _ in ()).throw(
            RuntimeError("raw endpoint details must remain hidden")
        ),
    )

    with pytest.raises(OneShotRunFailure) as captured:
        run_one_shot(dependencies)

    assert captured.value.stage == "guarded_server_metadata"
    assert captured.value.error_type == "RuntimeError"
    assert captured.value.authorization_consumed is False
    assert harness.runtime_calls == 0


def test_success_calls_recorded_runtime_exactly_once() -> None:
    harness = _Harness()

    summary = run_one_shot(harness.dependencies())

    assert summary.total_samples == 270
    assert harness.runtime_calls == 1
    assert harness.events == ["metadata", "runtime", "writer", "reader"]


def test_invalid_result_writes_no_evidence_and_does_not_retry() -> None:
    harness = _Harness()
    harness.runtime_result = _runtime_result(_samples()[:-1])

    with pytest.raises(OneShotRunFailure) as captured:
        run_one_shot(harness.dependencies())

    assert captured.value.stage == "recorded_validation"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 0


def test_runtime_exception_does_not_retry() -> None:
    harness = _Harness()

    def fail_runtime(*args, **kwargs):
        harness.runtime_calls += 1
        raise RuntimeError("raw database error must remain hidden")

    dependencies = replace(
        harness.dependencies(),
        recorded_runner=fail_runtime,
    )

    with pytest.raises(OneShotRunFailure) as captured:
        run_one_shot(dependencies)

    assert captured.value.stage == "recorded_runtime"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 0


def test_publication_failure_does_not_retry_runtime() -> None:
    harness = _Harness()

    def fail_publication(**kwargs):
        harness.writer_calls += 1
        raise OSError("raw path error must remain hidden")

    dependencies = replace(
        harness.dependencies(),
        evidence_writer=fail_publication,
    )

    with pytest.raises(OneShotRunFailure) as captured:
        run_one_shot(dependencies)

    assert captured.value.stage == "publication"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.writer_calls == 1


def test_read_back_failure_does_not_retry_runtime() -> None:
    harness = _Harness()

    def fail_read_back(_):
        harness.reader_calls += 1
        raise ValueError("raw evidence detail must remain hidden")

    dependencies = replace(
        harness.dependencies(),
        evidence_reader=fail_read_back,
    )

    with pytest.raises(OneShotRunFailure) as captured:
        run_one_shot(dependencies)

    assert captured.value.stage == "read_back"
    assert captured.value.authorization_consumed is True
    assert harness.runtime_calls == 1
    assert harness.reader_calls == 1


def test_valid_result_builds_exact_manifest_and_namespace() -> None:
    harness = _Harness()

    run_one_shot(harness.dependencies())

    manifest = harness.captured_manifest
    assert manifest.run_id == RUN_ID
    assert manifest.source_commit == FULL_HEAD
    assert manifest.source_tree_clean_before_run is True
    assert manifest.postgresql_server_version == "16.3"
    assert manifest.structural_smoke_validated is True
    assert harness.captured_output_root == DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT
    assert harness.publication.directory == (
        DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT / RUN_ID
    )


def test_valid_result_is_read_immediately_and_accounted_270_by_30() -> None:
    harness = _Harness()

    summary = run_one_shot(harness.dependencies())

    assert harness.events[-2:] == ["writer", "reader"]
    assert harness.reader_calls == 1
    assert summary.total_samples == 270
    assert summary.samples_per_cell == 30
    counts = {cell: 0 for cell in ALL_CELLS}
    for sample in harness.captured_samples:
        counts[sample.cell] += 1
    assert counts == {cell: 30 for cell in ALL_CELLS}
    assert len(summary.aggregates) == 9


def test_success_summary_is_sanitized_and_descriptive_only() -> None:
    harness = _Harness()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(
        dependencies=harness.dependencies(),
        stdout=stdout,
        stderr=stderr,
    )
    output = stdout.getvalue()

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert SECRET_DATABASE_URL not in output
    assert "secret-marker" not in output
    assert f"source_head={FULL_HEAD}" in output
    assert f"run_id={RUN_ID}" in output
    assert "samples=270" in output
    assert "samples_per_cell=30" in output
    assert "validation=VALID" in output
    assert "exceptions=0" in output
    assert "reuse_select_succeeded=270/270" in output
    assert "final_idle=270/270" in output
    assert sum(line.startswith("cell=") for line in output.splitlines()) == 9
    for forbidden in (
        "better",
        "superior",
        "capacity",
        "rate_limit",
        "caused",
        "database_name",
        "username",
        "password",
    ):
        assert forbidden not in output.lower()


def test_failure_summary_does_not_expose_environment_or_exception_message() -> None:
    harness = _Harness()
    stdout = StringIO()
    stderr = StringIO()

    def fail_runtime(*args, **kwargs):
        raise RuntimeError(f"endpoint={SECRET_DATABASE_URL}")

    exit_code = main(
        dependencies=replace(
            harness.dependencies(),
            recorded_runner=fail_runtime,
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code != 0
    assert stdout.getvalue() == ""
    assert "error_type=RuntimeError" in stderr.getvalue()
    assert "authorization_consumed=true" in stderr.getvalue()
    assert SECRET_DATABASE_URL not in stderr.getvalue()
    assert "endpoint=" not in stderr.getvalue()


def test_database_url_is_not_retained_in_manifest_or_summary() -> None:
    harness = _Harness()

    summary = run_one_shot(harness.dependencies())

    assert SECRET_DATABASE_URL not in manifest_to_json(harness.captured_manifest)
    assert SECRET_DATABASE_URL not in repr(summary)
    assert not hasattr(harness.captured_manifest, "database_url")


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
            return ("16.3",)

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
        lambda database_url: events.append(("connect", database_url)) or connection,
    )
    monkeypatch.setattr(
        runtime_module,
        "_guard_test_connection",
        lambda observed: events.append(("guard", observed)),
    )

    observed = runner._load_guarded_server_version(SECRET_DATABASE_URL)

    assert observed == "16.3"
    assert events == [
        ("connect", SECRET_DATABASE_URL),
        ("guard", connection),
        ("execute", "SHOW server_version"),
        "rollback",
        "rollback",
        "close",
    ]


def test_no_alternate_run_id_or_layer3_entry_point_exists() -> None:
    assert "run_id" not in inspect.signature(run_one_shot).parameters
    assert not hasattr(runner, "run_layer3")
    assert not hasattr(runner, "retry_recorded_run")
    assert not hasattr(runner, "alternate_run_id")
