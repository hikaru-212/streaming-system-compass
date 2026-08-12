"""Deterministic specifications for the human-operated PR7 smoke runner.

These tests replace Git, environment, and PostgreSQL boundaries with fakes.
They are intentionally not an authorization to run the tests or live smoke.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, cast

import pytest

import experiments.stage4b2.postgres_bounded_concurrency_runtime as runtime_module
from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    SMOKE_EVIDENCE_KIND,
    SmokeExecutionResult,
    SmokeStatus,
    Composition,
    WorkloadFamily,
)


RUNNER_MODULE = (
    "experiments.stage4b2.postgres_bounded_concurrency_smoke_run"
)
EXPECTED_BRANCH = "experiment/stage4b2-pr7-bounded-concurrency-characterization"
FULL_HEAD = "1234567abcdef0123456789abcdef0123456789a"
SECRET_DATABASE_URL = (
    "postgresql://secret-user:secret-password@secret-host/compass_test"
)

_CELL_COORDINATES = (
    (8, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.PRE_OCC),
    (8, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.IN_PESSIMISTIC),
    (
        8,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.IN_PESSIMISTIC,
    ),
    (
        8,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.PRE_OCC,
    ),
    (
        2,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.PRE_OCC,
    ),
    (
        2,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.IN_PESSIMISTIC,
    ),
    (2, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.IN_PESSIMISTIC),
    (2, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.PRE_OCC),
    (1, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.PRE_OCC),
    (1, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.IN_PESSIMISTIC),
    (
        1,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.IN_PESSIMISTIC,
    ),
    (
        1,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.PRE_OCC,
    ),
    (
        4,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.PRE_OCC,
    ),
    (
        4,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
        Composition.IN_PESSIMISTIC,
    ),
    (4, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.IN_PESSIMISTIC),
    (4, WorkloadFamily.SAME_ORDER_HOT_STREAM, Composition.PRE_OCC),
)


@pytest.fixture
def runner_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    module = importlib.import_module(RUNNER_MODULE)

    def unexpected_smoke(**_kwargs: object) -> None:
        raise AssertionError("test did not explicitly authorize the fake smoke")

    monkeypatch.setattr(module, "run_postgres_smoke", unexpected_smoke)
    return module


def _install_git(
    monkeypatch: pytest.MonkeyPatch,
    runner: Any,
    *,
    branch: str = EXPECTED_BRANCH,
    full_head: str = FULL_HEAD,
    dirty: bool = False,
) -> list[tuple[tuple[str, ...], Path | None]]:
    calls: list[tuple[tuple[str, ...], Path | None]] = []
    responses = {
        ("rev-parse", "--show-toplevel"): "/workspace/pr7\n",
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


def _fake_runtime_facts(
    levels: tuple[int, ...] = (8, 2, 1, 4),
) -> tuple[SimpleNamespace, ...]:
    return tuple(
        SimpleNamespace(
            worker_level=level,
            lane_count=level,
            thread_count=level,
            connection_count=level,
            topology_label="guarded-test-postgresql",
            postgresql_server_version="160014",
            isolation_level="READ_COMMITTED",
            autocommit=False,
        )
        for level in levels
    )


def _typed_counts(
    *,
    cell_index: int,
    worker_level: int,
) -> tuple[SimpleNamespace, ...]:
    if cell_index == 0:
        return (
            SimpleNamespace(outcome="ACCEPTED", count=1),
            SimpleNamespace(
                outcome="ADMISSION_REJECTED_APPEND_STALE_WRITE",
                count=worker_level - 1,
            ),
        )
    if cell_index == 1:
        return (
            SimpleNamespace(outcome="ACCEPTED", count=1),
            SimpleNamespace(
                outcome="ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT",
                count=worker_level - 1,
            ),
        )
    return (SimpleNamespace(outcome="ACCEPTED", count=worker_level),)


def _fake_smoke_result(
    *,
    status: SmokeStatus = SmokeStatus.STRUCTURALLY_VALID,
    completed_cells: int = 16,
    failed_cell_index: int | None = None,
) -> SmokeExecutionResult:
    batches: list[SimpleNamespace] = []
    invocations: list[SimpleNamespace] = []
    for cell_index, (worker_level, family, composition) in enumerate(
        _CELL_COORDINATES[:completed_cells]
    ):
        elapsed_values = [10 * (lane + 1) for lane in range(worker_level)]
        invocations.extend(
            SimpleNamespace(
                smoke_cell_index=cell_index,
                record=SimpleNamespace(external_elapsed_ns=elapsed_ns),
            )
            for elapsed_ns in elapsed_values
        )
        typed_counts = _typed_counts(
            cell_index=cell_index,
            worker_level=worker_level,
        )
        batches.append(
            SimpleNamespace(
                smoke_cell_index=cell_index,
                release_skew_ns=worker_level - 1,
                record=SimpleNamespace(
                    worker_level=worker_level,
                    workload_family=family,
                    composition=composition,
                    completed_count=worker_level,
                    accepted_count=(
                        1 if cell_index in (0, 1) else worker_level
                    ),
                    typed_outcome_counts=typed_counts,
                    first_start_offset_ns=10,
                    last_start_offset_ns=10 + worker_level - 1,
                    batch_elapsed_ns=100 + worker_level,
                ),
            )
        )
    issues = (
        ()
        if status is SmokeStatus.STRUCTURALLY_VALID
        else (
            SimpleNamespace(
                code="PHASE_STATE_MISMATCH",
                detail=f"cell={failed_cell_index}; lane=0; phase=business_uow",
            ),
        )
    )
    failed_extent = 0 if failed_cell_index is None else failed_cell_index + 1
    visited_coordinates = _CELL_COORDINATES[: max(completed_cells, failed_extent)]
    visited_levels = tuple(
        dict.fromkeys(level for level, _family, _composition in visited_coordinates)
    )
    return cast(
        SmokeExecutionResult,
        SimpleNamespace(
            evidence_kind=SMOKE_EVIDENCE_KIND,
            status=status,
            batches=tuple(batches),
            invocations=tuple(invocations),
            failed_cell_index=failed_cell_index,
            release_skew_human_review_required=True,
            runtime_facts=_fake_runtime_facts(visited_levels),
            issues=issues,
        ),
    )


def _launch_valid_fake(
    *,
    monkeypatch: pytest.MonkeyPatch,
    runner: Any,
    result: SmokeExecutionResult | None = None,
) -> tuple[int, list[dict[str, str]]]:
    _install_git(monkeypatch, runner)
    monkeypatch.setenv("TEST_DATABASE_URL", SECRET_DATABASE_URL)
    calls: list[dict[str, str]] = []

    def fake_smoke(*, database_url: str, run_id: str) -> Any:
        calls.append({"database_url": database_url, "run_id": run_id})
        return result if result is not None else _fake_smoke_result()

    monkeypatch.setattr(runner, "run_postgres_smoke", fake_smoke)
    return runner.main(), calls


def test_importing_runner_performs_no_git_environment_or_smoke_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def unexpected(*_args: object, **_kwargs: object) -> None:
        calls.append("unexpected")
        raise AssertionError("import crossed an execution boundary")

    monkeypatch.setattr(runtime_module, "run_postgres_smoke", unexpected)
    monkeypatch.setattr(subprocess, "run", unexpected)
    sys.modules.pop(RUNNER_MODULE, None)

    imported = importlib.import_module(RUNNER_MODULE)

    assert imported.__name__ == RUNNER_MODULE
    assert calls == []


def test_git_branch_and_full_head_are_derived_directly(
    monkeypatch: pytest.MonkeyPatch,
    runner_module: Any,
) -> None:
    calls = _install_git(monkeypatch, runner_module)

    lineage = runner_module._derive_git_lineage()

    assert lineage.repository_root == Path("/workspace/pr7")
    assert lineage.branch == EXPECTED_BRANCH
    assert lineage.full_head == FULL_HEAD
    assert lineage.source_tree_clean is True
    assert calls == [
        (("rev-parse", "--show-toplevel"), None),
        (("branch", "--show-current"), Path("/workspace/pr7")),
        (("rev-parse", "HEAD"), Path("/workspace/pr7")),
        (
            ("status", "--porcelain", "--untracked-files=normal"),
            Path("/workspace/pr7"),
        ),
    ]


def test_run_id_uses_first_seven_characters_of_derived_head(
    monkeypatch: pytest.MonkeyPatch,
    runner_module: Any,
) -> None:
    _install_git(
        monkeypatch,
        runner_module,
        full_head="ABCDEF7" + "0" * 33,
    )

    lineage = runner_module._derive_git_lineage()

    assert lineage.run_id == "stage4b2-pr7-postgres-smoke-abcdef7"


def test_runner_rejects_user_supplied_run_id_or_other_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    smoke_calls: list[object] = []
    monkeypatch.setattr(
        runner_module,
        "run_postgres_smoke",
        lambda **kwargs: smoke_calls.append(kwargs),
    )

    exit_code = runner_module.main(("--run-id", "alternate"))
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert exit_code == runner_module.EXIT_PRE_SMOKE_FAILURE
    assert smoke_calls == []
    assert "reason = COMMAND_ARGUMENTS_NOT_ACCEPTED" in combined
    assert "run_postgres_smoke = NOT CALLED" in combined


@pytest.mark.parametrize(
    ("branch", "dirty", "reason"),
    (
        ("wrong-branch", False, "WRONG_GIT_BRANCH"),
        (EXPECTED_BRANCH, True, "DIRTY_SOURCE_TREE"),
    ),
)
def test_wrong_branch_or_dirty_tree_prevents_smoke_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
    branch: str,
    dirty: bool,
    reason: str,
) -> None:
    _install_git(monkeypatch, runner_module, branch=branch, dirty=dirty)
    monkeypatch.setenv("TEST_DATABASE_URL", SECRET_DATABASE_URL)
    smoke_calls: list[object] = []
    monkeypatch.setattr(
        runner_module,
        "run_postgres_smoke",
        lambda **kwargs: smoke_calls.append(kwargs),
    )

    exit_code = runner_module.main()
    output = capsys.readouterr()
    combined = output.out + output.err

    assert exit_code == runner_module.EXIT_PRE_SMOKE_FAILURE
    assert smoke_calls == []
    assert f"reason = {reason}" in combined
    assert "run_postgres_smoke = NOT CALLED" in combined
    assert "smoke authorization consumed = false" in combined
    assert "protected-file" not in combined


def test_missing_database_url_prevents_smoke_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _install_git(monkeypatch, runner_module)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    smoke_calls: list[object] = []
    monkeypatch.setattr(
        runner_module,
        "run_postgres_smoke",
        lambda **kwargs: smoke_calls.append(kwargs),
    )

    exit_code = runner_module.main()
    output = capsys.readouterr()
    combined = output.out + output.err

    assert exit_code == runner_module.EXIT_PRE_SMOKE_FAILURE
    assert smoke_calls == []
    assert "reason = TEST_DATABASE_URL_MISSING" in combined
    assert "run_postgres_smoke = NOT CALLED" in combined


def test_valid_launch_passes_secret_once_without_printing_it(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr()
    combined = output.out + output.err

    assert exit_code == runner_module.EXIT_SUCCESS
    assert calls == [
        {
            "database_url": SECRET_DATABASE_URL,
            "run_id": "stage4b2-pr7-postgres-smoke-1234567",
        }
    ]
    assert SECRET_DATABASE_URL not in combined
    assert "secret-user" not in combined
    assert "secret-password" not in combined
    assert "secret-host" not in combined


def test_structurally_valid_requires_human_skew_review_and_denies_canonical(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, _calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_SUCCESS
    assert "smoke status = STRUCTURALLY_VALID" in output
    assert "release skew human review = REQUIRED" in output
    assert "canonical Level-C execution = NOT AUTHORIZED" in output
    assert "canonical VALID" not in output


def test_success_prints_exact_accounting_and_sanitized_runtime_facts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, _calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_SUCCESS
    assert f"branch = {EXPECTED_BRANCH}" in output
    assert f"full source HEAD = {FULL_HEAD}" in output
    assert "run ID = stage4b2-pr7-postgres-smoke-1234567" in output
    assert "source tree clean = true" in output
    assert f"evidence kind = {SMOKE_EVIDENCE_KIND}" in output
    assert "total planned cells = 16" in output
    assert "observed completed cells = 16" in output
    assert "total planned invocations = 60" in output
    assert "observed invocations = 60" in output
    assert "failed cell index = NONE" in output
    assert "release-skew human review required = true" in output
    assert output.count("topology label = guarded-test-postgresql") == 4
    assert "PostgreSQL server version = 160014" in output
    assert "isolation level = READ_COMMITTED" in output
    assert "autocommit = false" in output


def test_cell_diagnostics_keep_typed_outcomes_and_skew_separate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, _calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_SUCCESS
    assert output.count("smoke cell index = ") == 16
    assert "typed outcome count ACCEPTED = 1" in output
    assert "typed outcome count ADMISSION_REJECTED_APPEND_STALE_WRITE = 7" in output
    assert (
        "typed outcome count ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT = 7"
        in output
    )
    assert "generic rejected" not in output.lower()
    assert "first start offset ns = 10" in output
    assert "last start offset ns = 17" in output
    assert "release skew ns = 7" in output
    assert "batch elapsed ns = 108" in output


def test_invocation_elapsed_diagnostics_use_min_mean_median_and_max(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, _calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_SUCCESS
    assert "invocation elapsed ns minimum = 10" in output
    assert "invocation elapsed ns mean = 45.0" in output
    assert "invocation elapsed ns median = 45.0" in output
    assert "invocation elapsed ns maximum = 80" in output
    assert "p95" not in output.lower()


def test_invalid_smoke_returns_nonzero_and_never_calls_again(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    result = _fake_smoke_result(
        status=SmokeStatus.INVALID_SMOKE,
        completed_cells=2,
        failed_cell_index=2,
    )
    exit_code, calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
        result=result,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_INVALID_SMOKE
    assert len(calls) == 1
    assert "status = INVALID_SMOKE" in output
    assert "first failed cell index = 2" in output
    assert "issue code = PHASE_STATE_MISMATCH" in output
    assert "issue detail = cell=2; lane=0; phase=business_uow" in output
    assert "cells completed before stop = 2" in output
    assert "invocations retained before stop = 16" in output
    assert "canonical Level-C execution = NOT AUTHORIZED" in output


def test_runtime_exception_consumes_once_without_message_or_retry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    _install_git(monkeypatch, runner_module)
    monkeypatch.setenv("TEST_DATABASE_URL", SECRET_DATABASE_URL)
    calls: list[int] = []

    class SecretFailure(RuntimeError):
        pass

    def fail_once(**_kwargs: object) -> None:
        calls.append(1)
        raise SecretFailure(
            "postgresql://exception-user:exception-password@exception-host/db"
        )

    monkeypatch.setattr(runner_module, "run_postgres_smoke", fail_once)

    exit_code = runner_module.main()
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert exit_code == runner_module.EXIT_SMOKE_RUNTIME_FAILURE
    assert calls == [1]
    assert "exception type = SecretFailure" in combined
    assert "run_postgres_smoke = CALLED ONCE" in combined
    assert "smoke authorization consumed = true" in combined
    assert "retry or replacement = NOT AUTHORIZED" in combined
    assert "exception-user" not in combined
    assert "exception-password" not in combined
    assert "exception-host" not in combined
    assert SECRET_DATABASE_URL not in combined


def test_runner_invokes_no_canonical_aggregate_or_persistence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("canonical or persistence boundary was invoked")

    monkeypatch.setattr(runtime_module, "aggregate_invocations", forbidden)
    monkeypatch.setattr(runtime_module, "aggregate_batch_rates", forbidden)
    exit_code, calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out

    assert exit_code == runner_module.EXIT_SUCCESS
    assert len(calls) == 1
    assert not hasattr(runner_module, "write_evidence_directory")
    assert not hasattr(runner_module, "invocation_records_to_jsonl")
    assert not hasattr(runner_module, "batch_records_to_jsonl")
    assert "evidence directory" not in output.lower()


def test_runner_introduces_no_rate_capacity_or_attempt_policy(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runner_module: Any,
) -> None:
    exit_code, calls = _launch_valid_fake(
        monkeypatch=monkeypatch,
        runner=runner_module,
    )
    output = capsys.readouterr().out.lower()

    assert exit_code == runner_module.EXIT_SUCCESS
    assert len(calls) == 1
    for forbidden in (
        "throughput",
        "rate limit",
        "safe concurrency",
        "capacity",
        "saturation",
        "connection-pool recommendation",
        "strategy winner",
        "attempt_id",
        "execution_id",
        "layer 3",
    ):
        assert forbidden not in output
    assert not hasattr(runner_module, "rate_limit")
    assert not hasattr(runner_module, "retry")
    assert not hasattr(runner_module, "attempt_id")
