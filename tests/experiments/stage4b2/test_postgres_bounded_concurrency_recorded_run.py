"""Deterministic tests for the human-operated PR7 canonical one-shot runner."""

from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import experiments.stage4b2.postgres_bounded_concurrency_evidence as evidence_module
import experiments.stage4b2.postgres_bounded_concurrency_runtime as runtime_module
from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    EvidenceStatus,
    RECORDED_SCHEDULE_SEED,
    RETAINED_WORKER_LEVELS,
    generate_fixed_schedule,
)


RUNNER_MODULE = (
    "experiments.stage4b2.postgres_bounded_concurrency_recorded_run"
)
EXPECTED_BRANCH = "experiment/stage4b2-pr7-bounded-concurrency-characterization"
FULL_HEAD = "1234567abcdef0123456789abcdef0123456789a"
SECRET_DATABASE_URL = (
    "postgresql://canonical-user:canonical-password@canonical-host/compass_test"
)


@pytest.fixture
def runner_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    module = importlib.import_module(RUNNER_MODULE)

    def unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("test crossed an unconfigured canonical boundary")

    monkeypatch.setattr(module, "RecordedScheduleExecutor", unexpected)
    monkeypatch.setattr(module, "open_postgres_level_runtime", unexpected)
    monkeypatch.setattr(module, "write_canonical_evidence_directory", unexpected)
    return module


def _install_git(
    monkeypatch: pytest.MonkeyPatch,
    runner: Any,
    repository_root: Path,
    *,
    branch: str = EXPECTED_BRANCH,
    full_head: str = FULL_HEAD,
    dirty: bool = False,
) -> list[tuple[tuple[str, ...], Path | None]]:
    calls: list[tuple[tuple[str, ...], Path | None]] = []
    responses = {
        ("rev-parse", "--show-toplevel"): f"{repository_root}\n",
        ("branch", "--show-current"): f"{branch}\n",
        ("rev-parse", "HEAD"): f"{full_head}\n",
        ("status", "--porcelain", "--untracked-files=normal"): (
            " M protected-file\n" if dirty else ""
        ),
    }

    def fake_run(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert command[0] == "git"
        assert check is True
        assert capture_output is True
        assert text is True
        arguments = tuple(command[1:])
        calls.append((arguments, cwd))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=responses[arguments],
            stderr="",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return calls


def _fake_result(
    schedule: Any,
    *,
    status: EvidenceStatus = EvidenceStatus.VALID,
    invocation_count: int = 1_800,
    batch_count: int = 480,
    ownership_count: int = 15,
) -> Any:
    invocations = tuple(
        SimpleNamespace(
            worker_level=plan.cell.worker_level,
            exception_type=None,
        )
        for plan in schedule.recorded_batches
        for _lane_index in range(plan.cell.worker_level)
    )[:invocation_count]
    batches = tuple(
        SimpleNamespace(
            worker_level=plan.cell.worker_level,
            first_start_offset_ns=10,
            last_start_offset_ns=(
                10
                + plan.cell.worker_level * 100
                + plan.batch_index % 3
            ),
        )
        for plan in schedule.recorded_batches
    )[:batch_count]
    ownership = tuple(SimpleNamespace(slot=index) for index in range(15))[
        :ownership_count
    ]
    issues = () if status is EvidenceStatus.VALID else (
        SimpleNamespace(code="SYNTHETIC_INVALID"),
    )
    return SimpleNamespace(
        schedule=schedule,
        validation=SimpleNamespace(status=status, issues=issues),
        invocations=invocations,
        batches=batches,
        ownership=ownership,
    )


def _fake_readback(
    *,
    runner: Any,
    repository_root: Path,
    manifest: Any,
    result: Any,
    batch_rate_group_count: int = 16,
) -> Any:
    return SimpleNamespace(
        run_directory=(
            runner.canonical_evidence_root(repository_root) / manifest.run_id
        ),
        manifest=manifest,
        result=result,
        invocation_aggregates=(SimpleNamespace(),),
        batch_rate_aggregates=tuple(
            SimpleNamespace() for _ in range(batch_rate_group_count)
        ),
    )


def _configure_launch(
    *,
    monkeypatch: pytest.MonkeyPatch,
    runner: Any,
    repository_root: Path,
    result: Any | None = None,
    execution_exception: Exception | None = None,
    writer_exception: Exception | None = None,
    batch_rate_group_count: int = 16,
    fact_overrides: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repository_root.mkdir(parents=True, exist_ok=True)
    _install_git(monkeypatch, runner, repository_root)
    monkeypatch.setenv("TEST_DATABASE_URL", SECRET_DATABASE_URL)
    schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    state: dict[str, Any] = {
        "constructor_calls": [],
        "execute_calls": [],
        "open_calls": [],
        "writer_calls": [],
        "manifest_calls": [],
        "schedule": schedule,
    }

    @contextmanager
    def fake_open_postgres_level_runtime(
        *,
        database_url: str,
        worker_level: int,
    ) -> Any:
        state["open_calls"].append(
            {"database_url": database_url, "worker_level": worker_level}
        )
        values = {
            "postgresql_server_version": "160014",
            "isolation_level": "READ_COMMITTED",
            "autocommit": False,
            "topology_label": "guarded-test-postgresql",
        }
        values.update((fact_overrides or {}).get(worker_level, {}))
        yield SimpleNamespace(worker_level=worker_level, **values)

    class FakeRecordedScheduleExecutor:
        def __init__(self, *, open_level_runtime: Any) -> None:
            state["constructor_calls"].append(open_level_runtime)
            self._open_level_runtime = open_level_runtime

        def execute(self, *, run_id: str, schedule: Any) -> Any:
            state["execute_calls"].append(
                {"run_id": run_id, "schedule": schedule}
            )
            if execution_exception is not None:
                raise execution_exception
            level_order = tuple(
                dict.fromkeys(cell.worker_level for cell in schedule.cells)
            )
            for worker_level in level_order:
                with self._open_level_runtime(worker_level):
                    pass
            return result if result is not None else _fake_result(schedule)

    original_manifest_builder = runner.build_canonical_manifest

    def capture_manifest(**kwargs: Any) -> Any:
        state["manifest_calls"].append(kwargs)
        return original_manifest_builder(**kwargs)

    def fake_writer(
        *,
        repository_root: Path,
        manifest: Any,
        result: Any,
    ) -> Any:
        state["writer_calls"].append(
            {
                "repository_root": repository_root,
                "manifest": manifest,
                "result": result,
            }
        )
        if writer_exception is not None:
            raise writer_exception
        return _fake_readback(
            runner=runner,
            repository_root=repository_root,
            manifest=manifest,
            result=result,
            batch_rate_group_count=batch_rate_group_count,
        )

    monkeypatch.setattr(runner, "generate_fixed_schedule", lambda *, seed: schedule)
    monkeypatch.setattr(
        runner,
        "open_postgres_level_runtime",
        fake_open_postgres_level_runtime,
    )
    monkeypatch.setattr(
        runner,
        "RecordedScheduleExecutor",
        FakeRecordedScheduleExecutor,
    )
    monkeypatch.setattr(runner, "build_canonical_manifest", capture_manifest)
    monkeypatch.setattr(runner, "write_canonical_evidence_directory", fake_writer)
    return state


def _combined_output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def _assert_sanitized_failure(
    output: str,
    *,
    stage: str,
    exception_class: str,
    consumed: bool,
) -> None:
    assert output.splitlines() == [
        f"failure stage = {stage}",
        f"exception class = {exception_class}",
        f"authorization_consumed = {str(consumed).lower()}",
    ]
    assert SECRET_DATABASE_URL not in output
    assert "canonical-user" not in output
    assert "canonical-password" not in output
    assert "canonical-host" not in output


def test_importing_module_performs_no_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def unexpected(*_args: object, **_kwargs: object) -> None:
        calls.append("unexpected")
        raise AssertionError("import crossed an execution boundary")

    class ExplodingEnvironment(dict[str, str]):
        def get(self, *_args: object, **_kwargs: object) -> str:
            unexpected()
            return ""

    monkeypatch.setattr(subprocess, "run", unexpected)
    monkeypatch.setattr(os, "environ", ExplodingEnvironment())
    monkeypatch.setattr(runtime_module, "RecordedScheduleExecutor", unexpected)
    monkeypatch.setattr(runtime_module, "open_postgres_level_runtime", unexpected)
    monkeypatch.setattr(evidence_module, "build_canonical_manifest", unexpected)
    monkeypatch.setattr(
        evidence_module,
        "write_canonical_evidence_directory",
        unexpected,
    )
    sys.modules.pop(RUNNER_MODULE, None)

    imported = importlib.import_module(RUNNER_MODULE)

    assert imported.__name__ == RUNNER_MODULE
    assert calls == []
    sys.modules.pop(RUNNER_MODULE, None)


def test_git_lineage_and_run_id_are_derived_directly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner_module: Any,
) -> None:
    calls = _install_git(monkeypatch, runner_module, tmp_path)

    lineage = runner_module._derive_git_lineage()

    assert lineage.repository_root == tmp_path
    assert lineage.branch == EXPECTED_BRANCH
    assert lineage.full_head == FULL_HEAD
    assert lineage.source_tree_clean is True
    assert lineage.run_id == "stage4b2-pr7-canonical-1234567"
    assert calls == [
        (("rev-parse", "--show-toplevel"), None),
        (("branch", "--show-current"), tmp_path),
        (("rev-parse", "HEAD"), tmp_path),
        (
            ("status", "--porcelain", "--untracked-files=normal"),
            tmp_path,
        ),
    ]


@pytest.mark.parametrize(
    ("branch", "full_head", "dirty"),
    (
        ("wrong-branch", FULL_HEAD, False),
        (EXPECTED_BRANCH, FULL_HEAD, True),
        (EXPECTED_BRANCH, "1234567", False),
        (EXPECTED_BRANCH, "A" * 40, False),
    ),
)
def test_source_gate_stops_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
    branch: str,
    full_head: str,
    dirty: bool,
) -> None:
    _install_git(
        monkeypatch,
        runner_module,
        tmp_path,
        branch=branch,
        full_head=full_head,
        dirty=dirty,
    )
    monkeypatch.setenv("TEST_DATABASE_URL", SECRET_DATABASE_URL)

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_PRE_EXECUTION_FAILURE
    _assert_sanitized_failure(
        output,
        stage="SOURCE_GATE",
        exception_class="_RunnerGateError",
        consumed=False,
    )


def test_missing_database_url_stops_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _install_git(monkeypatch, runner_module, tmp_path)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_PRE_EXECUTION_FAILURE
    _assert_sanitized_failure(
        output,
        stage="DATABASE_CONFIGURATION_GATE",
        exception_class="_RunnerGateError",
        consumed=False,
    )


def test_existing_canonical_directory_stops_before_runtime_and_environment_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _install_git(monkeypatch, runner_module, tmp_path)
    final_directory = (
        runner_module.canonical_evidence_root(tmp_path)
        / "stage4b2-pr7-canonical-1234567"
    )
    final_directory.mkdir(parents=True)

    class ExplodingEnvironment(dict[str, str]):
        def get(self, *_args: object, **_kwargs: object) -> str:
            raise AssertionError("existing evidence must stop before environment read")

    monkeypatch.setattr(runner_module.os, "environ", ExplodingEnvironment())

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_PRE_EXECUTION_FAILURE
    _assert_sanitized_failure(
        output,
        stage="EVIDENCE_DIRECTORY_GATE",
        exception_class="_RunnerGateError",
        consumed=False,
    )


def test_valid_launch_uses_exact_schedule_executor_and_runtime_seams_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_SUCCESS
    assert len(state["constructor_calls"]) == 1
    assert state["execute_calls"] == [
        {
            "run_id": "stage4b2-pr7-canonical-1234567",
            "schedule": state["schedule"],
        }
    ]
    supplied = state["execute_calls"][0]["schedule"]
    assert supplied.seed == 73
    assert supplied.retained_worker_levels == (1, 2, 4, 8)
    assert supplied.warmup_batches_per_cell == 3
    assert supplied.recorded_batches_per_cell == 30
    assert len(supplied.cells) == 16
    assert len(supplied.recorded_batches) == 480
    assert [item["worker_level"] for item in state["open_calls"]] == [8, 2, 1, 4]
    assert all(
        item["database_url"] == SECRET_DATABASE_URL
        for item in state["open_calls"]
    )
    assert SECRET_DATABASE_URL not in output


def test_runtime_exception_consumes_once_never_retries_and_sanitizes_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    class SecretRuntimeFailure(RuntimeError):
        pass

    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
        execution_exception=SecretRuntimeFailure(SECRET_DATABASE_URL),
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_EXECUTION_FAILURE
    assert len(state["execute_calls"]) == 1
    assert state["writer_calls"] == []
    _assert_sanitized_failure(
        output,
        stage="CANONICAL_EXECUTION",
        exception_class="SecretRuntimeFailure",
        consumed=True,
    )


def test_invalid_result_never_publishes_or_retries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    result = _fake_result(schedule, status=EvidenceStatus.INVALID_RUN)
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
        result=result,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_POST_EXECUTION_FAILURE
    assert len(state["execute_calls"]) == 1
    assert state["writer_calls"] == []
    _assert_sanitized_failure(
        output,
        stage="RUNTIME_VALIDATION",
        exception_class="_RunnerGateError",
        consumed=True,
    )


@pytest.mark.parametrize(
    ("invocations", "batches", "ownership"),
    ((1_799, 480, 15), (1_800, 479, 15), (1_800, 480, 14)),
)
def test_exact_runtime_accounting_is_required_before_publication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
    invocations: int,
    batches: int,
    ownership: int,
) -> None:
    schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    result = _fake_result(
        schedule,
        invocation_count=invocations,
        batch_count=batches,
        ownership_count=ownership,
    )
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
        result=result,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_POST_EXECUTION_FAILURE
    assert len(state["execute_calls"]) == 1
    assert state["writer_calls"] == []
    _assert_sanitized_failure(
        output,
        stage="RUNTIME_VALIDATION",
        exception_class="_RunnerGateError",
        consumed=True,
    )


def test_runtime_facts_are_captured_and_manifest_uses_exact_sanitized_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
    )

    exit_code = runner_module.main()
    _combined_output(capsys)

    assert exit_code == runner_module.EXIT_SUCCESS
    assert len(state["manifest_calls"]) == 1
    assert state["manifest_calls"][0] == {
        "run_id": "stage4b2-pr7-canonical-1234567",
        "source_commit": FULL_HEAD,
        "source_tree_clean_before_run": True,
        "postgresql_server_version": "160014",
        "transaction_isolation": "READ_COMMITTED",
        "autocommit": False,
        "topology_label": "guarded-test-postgresql",
    }
    assert len(state["writer_calls"]) == 1
    manifest = state["writer_calls"][0]["manifest"]
    assert manifest.smoke_source_commit == (
        "8dcfbdc1e1bc4cca8a8e7c48a73126a40ec9c958"
    )
    assert manifest.smoke_run_id == "stage4b2-pr7-postgres-smoke-8dcfbdc"
    assert manifest.smoke_release_skew_review == "ACCEPTED"


@pytest.mark.parametrize(
    "fact_overrides",
    (
        {4: {"postgresql_server_version": "160015"}},
        {4: {"isolation_level": "SERIALIZABLE"}},
        {4: {"autocommit": True}},
        {4: {"topology_label": "unexpected-topology"}},
        {4: {"postgresql_server_version": None}},
    ),
)
def test_inconsistent_or_missing_runtime_facts_stop_after_consumption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
    fact_overrides: dict[int, dict[str, Any]],
) -> None:
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
        fact_overrides=fact_overrides,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_POST_EXECUTION_FAILURE
    assert len(state["execute_calls"]) == 1
    assert state["writer_calls"] == []
    _assert_sanitized_failure(
        output,
        stage="RUNTIME_FACT_VALIDATION",
        exception_class="_RunnerGateError",
        consumed=True,
    )


@pytest.mark.parametrize("failure_kind", ("publication", "readback"))
def test_publication_or_readback_failure_never_retries_postgresql(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
    failure_kind: str,
) -> None:
    class SecretPublicationFailure(RuntimeError):
        pass

    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
        writer_exception=(
            SecretPublicationFailure(SECRET_DATABASE_URL)
            if failure_kind == "publication"
            else None
        ),
        batch_rate_group_count=(15 if failure_kind == "readback" else 16),
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_PUBLICATION_FAILURE
    assert len(state["execute_calls"]) == 1
    assert len(state["writer_calls"]) == 1
    _assert_sanitized_failure(
        output,
        stage="EVIDENCE_PUBLICATION_READBACK",
        exception_class=(
            "SecretPublicationFailure"
            if failure_kind == "publication"
            else "_RunnerGateError"
        ),
        consumed=True,
    )


def test_success_prints_exact_sanitized_accounting_and_evidence_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    state = _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_SUCCESS
    assert f"source branch = {EXPECTED_BRANCH}" in output
    assert f"full source HEAD = {FULL_HEAD}" in output
    assert "run ID = stage4b2-pr7-canonical-1234567" in output
    assert "clean source = true" in output
    assert "schedule seed = 73" in output
    assert "worker levels = 1,2,4,8" in output
    assert "exact cells = 16" in output
    assert "warmup batches / cell = 3" in output
    assert "recorded batches / cell = 30" in output
    assert "recorded batches = 480" in output
    assert "recorded invocations = 1800" in output
    assert "ownership records = 15" in output
    assert "validation = VALID" in output
    assert "unexpected exceptions = 0" in output
    assert "PostgreSQL server version = 160014" in output
    assert "transaction isolation = READ_COMMITTED" in output
    assert "autocommit = false" in output
    assert "topology label = guarded-test-postgresql" in output
    expected_directory = (
        runner_module.canonical_evidence_root(tmp_path)
        / "stage4b2-pr7-canonical-1234567"
    )
    assert f"evidence directory = {expected_directory}" in output
    assert len(state["writer_calls"]) == 1
    assert SECRET_DATABASE_URL not in output


def test_release_skew_output_is_worker_grouped_human_review_input_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_SUCCESS
    assert output.count("worker level = ") == 4
    assert output.count("recorded batch count = 120") == 4
    assert "worker level = 1" in output
    assert "invocation count = 120" in output
    assert "release skew ns minimum = 100" in output
    assert "release skew ns median = 101.0" in output
    assert "release skew ns maximum = 102" in output
    assert "worker level = 8" in output
    assert "invocation count = 960" in output
    assert "release skew ns minimum = 800" in output
    assert "release skew ns median = 801.0" in output
    assert "release skew ns maximum = 802" in output
    assert "release skew ns mean" not in output
    assert "release-skew diagnostics = HUMAN-REVIEW INPUT ONLY" in output
    assert "release-skew interpretation = HUMAN REVIEW REQUIRED" in output
    assert "release-skew acceptance threshold = NOT DEFINED" in output
    assert "release-skew acceptance threshold = 0" not in output


def test_runner_introduces_no_pooling_strategy_capacity_or_smoke_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _configure_launch(
        monkeypatch=monkeypatch,
        runner=runner_module,
        repository_root=tmp_path,
    )

    exit_code = runner_module.main()
    output = _combined_output(capsys).lower()

    assert exit_code == runner_module.EXIT_SUCCESS
    for forbidden in (
        "same_order_hot_stream",
        "different_order_general_concurrency",
        "pre_occ",
        "in_pessimistic",
        "in_occ",
        "pre_no_preliminary",
        "pre wins",
        "in wins",
        "strategy ranking",
        "capacity",
        "saturation",
        "safe concurrency",
        "production throughput",
        "slo",
        "rate limit",
        "connection-pool recommendation",
    ):
        assert forbidden not in output
    assert not hasattr(runner_module, "run_postgres_smoke")
    assert not hasattr(runner_module, "rate_limit")
    assert not hasattr(runner_module, "retry")
    assert not hasattr(runner_module, "attempt_id")
    assert not hasattr(runner_module, "execution_id")


def test_user_arguments_cannot_supply_alternate_run_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code = runner_module.main(("--run-id", "alternate"))
    output = _combined_output(capsys)

    assert exit_code == runner_module.EXIT_PRE_EXECUTION_FAILURE
    _assert_sanitized_failure(
        output,
        stage="COMMAND_GATE",
        exception_class="_RunnerGateError",
        consumed=False,
    )
