"""Safety and subprocess-isolation tests for the Stage 4B.5 runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import experiments.stage4b5.runtime_governance_overhead_recorded_run as recorded_run
from experiments.stage4b5.runtime_governance_overhead import (
    MICRO_SCENARIOS,
    REPOSITORY_ROOT,
    SEQUENCE_RULE_ID,
    Surface,
    Terminal,
)
from experiments.stage4b5.runtime_governance_overhead_recorded_run import (
    CANONICAL_CONFIRMATION,
    RecordedRunError,
    _require_canonical_preconditions,
    _read_postgres_preflight_facts,
    _WorkerRuntime,
    require_test_database_name,
)


RUNNER = (
    REPOSITORY_ROOT
    / "experiments"
    / "stage4b5"
    / "runtime_governance_overhead_recorded_run.py"
)


class _FakeTransactionStatus:
    def __init__(self) -> None:
        self.name = "IDLE"


class _FakeConnectionInfo:
    def __init__(self) -> None:
        self.transaction_status = _FakeTransactionStatus()


class _FakePreflightCursor:
    def __init__(self, connection: "_FakePreflightConnection") -> None:
        self.connection = connection
        self.query = ""

    def __enter__(self) -> "_FakePreflightCursor":
        return self

    def __exit__(self, *unused: object) -> None:
        return None

    def execute(self, query: str) -> None:
        self.connection.statuses_before_query.append(
            self.connection.info.transaction_status.name
        )
        self.connection.info.transaction_status.name = "INTRANS"
        self.query = query

    def fetchone(self) -> tuple[object, ...]:
        if self.query.startswith("SELECT current_database"):
            return ("compass_test", 181689)
        if self.query == "SHOW server_version_num":
            return ("160014",)
        if self.query == "SHOW transaction_isolation":
            return ("read committed",)
        raise AssertionError(f"unexpected fetchone query: {self.query}")

    def fetchall(self) -> list[tuple[str]]:
        if not self.query.startswith("SELECT tablename FROM pg_tables"):
            raise AssertionError(f"unexpected fetchall query: {self.query}")
        return [("order_events",)]


class _FakePreflightConnection:
    def __init__(self, *, rollback_returns_idle: bool) -> None:
        self.autocommit = False
        self.info = _FakeConnectionInfo()
        self.rollback_returns_idle = rollback_returns_idle
        self.rollback_calls = 0
        self.statuses_before_query: list[str] = []

    def cursor(self) -> _FakePreflightCursor:
        return _FakePreflightCursor(self)

    def rollback(self) -> None:
        self.rollback_calls += 1
        if self.rollback_returns_idle:
            self.info.transaction_status.name = "IDLE"


def test_database_name_guard_is_suffix_exact() -> None:
    assert require_test_database_name("stage4b5_test") == "stage4b5_test"
    for unsafe in ("stage4b5", "stage4b5_testing", "", None):
        with pytest.raises(RecordedRunError, match="does not end in _test"):
            require_test_database_name(unsafe)


def test_postgres_preflight_rolls_back_read_transaction_to_idle() -> None:
    connection = _FakePreflightConnection(rollback_returns_idle=True)

    facts = _read_postgres_preflight_facts(connection)

    assert connection.autocommit is False
    assert connection.statuses_before_query == [
        "IDLE",
        "INTRANS",
        "INTRANS",
        "INTRANS",
    ]
    assert connection.rollback_calls == 1
    assert connection.info.transaction_status.name == "IDLE"
    assert facts == {
        "database_name": "compass_test",
        "database_oid": 181689,
        "postgres_version_num": "160014",
        "transaction_isolation": "read committed",
        "tables": {"order_events"},
    }


def test_postgres_preflight_fails_if_cleanup_does_not_return_to_idle() -> None:
    connection = _FakePreflightConnection(rollback_returns_idle=False)

    with pytest.raises(
        RecordedRunError,
        match="not IDLE after read-only PostgreSQL preflight rollback",
    ):
        _read_postgres_preflight_facts(connection)

    assert connection.rollback_calls == 1
    assert connection.info.transaction_status.name == "INTRANS"


def test_canonical_interpreter_precondition_accepts_hosted_python_toolchain(
    monkeypatch,
) -> None:
    source_identity = {"working_tree_clean": True}
    monkeypatch.setattr(
        recorded_run,
        "current_source_identity",
        lambda: source_identity,
    )
    monkeypatch.setattr(sys, "prefix", getattr(sys, "base_prefix", sys.prefix))
    monkeypatch.delattr(sys, "real_prefix", raising=False)

    assert _require_canonical_preconditions(CANONICAL_CONFIRMATION) is source_identity


def test_c_surface_records_same_invocation_composition_lap() -> None:
    worker = _WorkerRuntime(Surface.C)
    observation = worker.micro_batch(
        MICRO_SCENARIOS[0].name,
        1,
        "timing-shape",
    )[0]
    assert set(observation) == {
        "producer_elapsed_ns",
        "composition_elapsed_ns",
        "total_elapsed_ns",
        "producer_outcome",
        "rule_id",
    }
    assert observation["producer_elapsed_ns"] > 0
    assert observation["composition_elapsed_ns"] >= 0
    assert observation["total_elapsed_ns"] == (
        observation["producer_elapsed_ns"]
        + observation["composition_elapsed_ns"]
    )


def test_a_loader_fails_if_parent_import_introduces_current_child() -> None:
    script = """
import sys
from types import ModuleType
import experiments.stage4b5.runtime_governance_overhead as module

real_import = module.importlib.import_module

def injecting_import(name):
    parent = real_import(name)
    if name == "src.compass.transition":
        child_name = "src.compass.transition.validators"
        child = ModuleType(child_name)
        sys.modules[child_name] = child
        setattr(parent, "validators", child)
    return parent

module.importlib.import_module = injecting_import
try:
    module.install_verified_historical_modules()
except RuntimeError as exc:
    if "parent import introduced protected current modules" not in str(exc):
        raise
else:
    raise AssertionError("parent-import contamination was not rejected")
"""
    subprocess.run(
        (sys.executable, "-c", script),
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_micro_smoke_uses_isolated_a_b_c_and_discards_timings() -> None:
    completed = subprocess.run(
        (sys.executable, str(RUNNER), "smoke-micro"),
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    document = json.loads(completed.stdout)
    assert document["status"] == "smoke-only; timings discarded; no benchmark result"
    assert set(document["verification"]) == {
        scenario.name for scenario in MICRO_SCENARIOS
    }
    for scenario in MICRO_SCENARIOS:
        observations = document["verification"][scenario.name]
        assert set(observations) == {surface.value for surface in Surface}
        assert observations["A"]["rule_id"] is None
        if scenario.terminal is Terminal.VALIDATION_BLOCKED:
            assert observations["B"]["rule_id"] == SEQUENCE_RULE_ID
            assert observations["C"]["rule_id"] == SEQUENCE_RULE_ID
        else:
            assert observations["B"]["rule_id"] is None
            assert observations["C"]["rule_id"] is None


def test_canonical_cli_refuses_wrong_confirmation_without_writing() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            str(RUNNER),
            "micro",
            "--run-id",
            "must-not-exist",
            "--confirm",
            f"not-{CANONICAL_CONFIRMATION}",
        ),
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert completed.returncode == 2
    assert "recorded run refused" in completed.stderr
    assert "must-not-exist" not in {
        path.name
        for path in (REPOSITORY_ROOT / "experiments" / "stage4b5").glob("**/*")
    }


def test_postgres_worker_refuses_missing_test_database_environment() -> None:
    environment = os.environ.copy()
    environment.pop("TEST_DATABASE_URL", None)
    process = subprocess.Popen(
        (
            sys.executable,
            str(RUNNER),
            "_worker",
            "--surface",
            "B",
        ),
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write('{"operation":"postgres_open"}\n')
    process.stdin.flush()
    response = json.loads(process.stdout.readline())
    assert response == {
        "ok": False,
        "error_type": "RecordedRunError",
        "error": "worker operation failed without exposing exception text",
    }
    process.stdin.write('{"operation":"close"}\n')
    process.stdin.flush()
    assert json.loads(process.stdout.readline())["ok"] is True
    assert process.wait(timeout=10) == 0
