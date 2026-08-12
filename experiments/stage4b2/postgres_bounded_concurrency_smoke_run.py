"""Human-operated entry point for the Stage 4B.2 PR7 PostgreSQL smoke.

Importing this module performs no Git inspection, environment inspection, or
PostgreSQL work.  Only ``main()`` derives committed source lineage, applies the
pre-smoke gates, and calls the already-authoritative ``run_postgres_smoke``
runtime once.  Output is an in-memory correctness/topology diagnostic for human
release-skew review; it is not canonical evidence or performance policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import TextIO

from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    SMOKE_EVIDENCE_KIND,
    SMOKE_EXACT_CELL_COUNT,
    SMOKE_TOTAL_PLANNED_INVOCATIONS,
    SmokeExecutionResult,
    SmokeStatus,
    run_postgres_smoke,
)


EXPECTED_BRANCH = "experiment/stage4b2-pr7-bounded-concurrency-characterization"
RUN_ID_PREFIX = "stage4b2-pr7-postgres-smoke-"
TEST_DATABASE_URL_ENVIRONMENT_VARIABLE = "TEST_DATABASE_URL"

EXIT_SUCCESS = 0
EXIT_PRE_SMOKE_FAILURE = 2
EXIT_INVALID_SMOKE = 3
EXIT_SMOKE_RUNTIME_FAILURE = 4

_GIT_HEAD = re.compile(r"[0-9a-fA-F]{7,}")


@dataclass(frozen=True)
class _GitLineage:
    """Retain only sanitized committed-source facts needed by the smoke gate."""

    repository_root: Path
    branch: str
    full_head: str
    source_tree_clean: bool

    def __post_init__(self) -> None:
        if not self.repository_root.is_absolute():
            raise ValueError("Git repository root must be absolute")
        if not self.branch:
            raise ValueError("Git branch must not be empty")
        if _GIT_HEAD.fullmatch(self.full_head) is None:
            raise ValueError("Git HEAD must be a full hexadecimal commit identity")
        if type(self.source_tree_clean) is not bool:
            raise TypeError("source_tree_clean must be bool")

    @property
    def run_id(self) -> str:
        """Derive the only accepted smoke run identity from committed source."""

        return f"{RUN_ID_PREFIX}{self.full_head[:7].lower()}"


class _PreSmokeFailure(RuntimeError):
    """Stop before the one-shot smoke authorization is consumed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _git_output(arguments: tuple[str, ...], *, cwd: Path | None = None) -> str:
    """Run one read-only Git query and return stripped stdout only."""

    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise _PreSmokeFailure("GIT_LINEAGE_UNAVAILABLE") from exc
    return completed.stdout.strip()


def _derive_git_lineage() -> _GitLineage:
    """Derive repository root, branch, HEAD, and cleanliness directly from Git."""

    repository_root_text = _git_output(("rev-parse", "--show-toplevel"))
    if not repository_root_text:
        raise _PreSmokeFailure("GIT_ROOT_UNAVAILABLE")
    repository_root = Path(repository_root_text)
    try:
        branch = _git_output(("branch", "--show-current"), cwd=repository_root)
        full_head = _git_output(("rev-parse", "HEAD"), cwd=repository_root)
        porcelain = _git_output(
            ("status", "--porcelain", "--untracked-files=normal"),
            cwd=repository_root,
        )
        return _GitLineage(
            repository_root=repository_root,
            branch=branch,
            full_head=full_head,
            source_tree_clean=not porcelain,
        )
    except (TypeError, ValueError) as exc:
        raise _PreSmokeFailure("GIT_LINEAGE_INVALID") from exc


def _print_pre_smoke_failure(
    *,
    reason: str,
    output: TextIO,
    lineage: _GitLineage | None = None,
) -> None:
    """Report that no live smoke call occurred and authorization remains unused."""

    print("PRE-SMOKE FAILURE", file=output)
    print(f"reason = {reason}", file=output)
    if lineage is not None:
        print(f"repository root = {lineage.repository_root}", file=output)
        print(f"branch = {lineage.branch}", file=output)
        print(f"full source HEAD = {lineage.full_head}", file=output)
        print(f"source tree clean = {str(lineage.source_tree_clean).lower()}", file=output)
    print("run_postgres_smoke = NOT CALLED", file=output)
    print("smoke authorization consumed = false", file=output)
    print("canonical Level-C execution = NOT AUTHORIZED", file=output)


def _print_lineage(
    *,
    lineage: _GitLineage,
    output: TextIO,
) -> None:
    """Print the sanitized committed-source identity for one consumed smoke."""

    print(f"repository root = {lineage.repository_root}", file=output)
    print(f"branch = {lineage.branch}", file=output)
    print(f"full source HEAD = {lineage.full_head}", file=output)
    print(f"run ID = {lineage.run_id}", file=output)
    print("source tree clean = true", file=output)


def _print_runtime_facts(
    *,
    result: SmokeExecutionResult,
    output: TextIO,
) -> None:
    """Print only existing sanitized level-scoped runtime facts."""

    print("sanitized runtime facts:", file=output)
    for facts in result.runtime_facts:
        print(f"worker level = {facts.worker_level}", file=output)
        print(f"lane count = {facts.lane_count}", file=output)
        print(f"thread count = {facts.thread_count}", file=output)
        print(f"connection count = {facts.connection_count}", file=output)
        print(f"topology label = {facts.topology_label}", file=output)
        server_version = facts.postgresql_server_version or "UNAVAILABLE"
        print(f"PostgreSQL server version = {server_version}", file=output)
        print(f"isolation level = {facts.isolation_level}", file=output)
        print(f"autocommit = {str(facts.autocommit).lower()}", file=output)


def _print_completed_cells(
    *,
    result: SmokeExecutionResult,
    output: TextIO,
) -> None:
    """Print per-cell smoke diagnostics without benchmark interpretation."""

    print("completed smoke cell diagnostics:", file=output)
    invocations_by_cell: dict[int, list[int]] = {}
    for invocation in result.invocations:
        invocations_by_cell.setdefault(invocation.smoke_cell_index, []).append(
            invocation.record.external_elapsed_ns
        )

    for observed_batch in result.batches:
        cell_index = observed_batch.smoke_cell_index
        batch = observed_batch.record
        elapsed_values = invocations_by_cell.get(cell_index, [])
        if not elapsed_values:
            raise ValueError("completed smoke cell omitted invocation diagnostics")
        print(f"smoke cell index = {cell_index}", file=output)
        print(f"worker level = {batch.worker_level}", file=output)
        print(f"workload family = {batch.workload_family.value}", file=output)
        print(f"composition = {batch.composition.value}", file=output)
        print(f"completed count = {batch.completed_count}", file=output)
        print(f"accepted count = {batch.accepted_count}", file=output)
        for typed_count in batch.typed_outcome_counts:
            print(
                f"typed outcome count {typed_count.outcome} = {typed_count.count}",
                file=output,
            )
        print(
            f"first start offset ns = {batch.first_start_offset_ns}",
            file=output,
        )
        print(
            f"last start offset ns = {batch.last_start_offset_ns}",
            file=output,
        )
        print(f"release skew ns = {observed_batch.release_skew_ns}", file=output)
        print(f"batch elapsed ns = {batch.batch_elapsed_ns}", file=output)
        print(
            f"invocation elapsed ns minimum = {min(elapsed_values)}",
            file=output,
        )
        print(
            "invocation elapsed ns mean = "
            f"{statistics.fmean(elapsed_values)}",
            file=output,
        )
        print(
            "invocation elapsed ns median = "
            f"{statistics.median(elapsed_values)}",
            file=output,
        )
        print(
            f"invocation elapsed ns maximum = {max(elapsed_values)}",
            file=output,
        )


def _print_smoke_result(
    *,
    lineage: _GitLineage,
    result: SmokeExecutionResult,
    output: TextIO,
) -> int:
    """Print one consumed smoke result and return its process exit code."""

    print("SMOKE EXECUTION RESULT", file=output)
    _print_lineage(lineage=lineage, output=output)
    print(f"evidence kind = {result.evidence_kind}", file=output)
    print(f"smoke status = {result.status.value}", file=output)
    print(f"total planned cells = {SMOKE_EXACT_CELL_COUNT}", file=output)
    print(f"observed completed cells = {len(result.batches)}", file=output)
    print(
        f"total planned invocations = {SMOKE_TOTAL_PLANNED_INVOCATIONS}",
        file=output,
    )
    print(f"observed invocations = {len(result.invocations)}", file=output)
    failed_cell = (
        "NONE" if result.failed_cell_index is None else result.failed_cell_index
    )
    print(f"failed cell index = {failed_cell}", file=output)
    print(
        "release-skew human review required = "
        f"{str(result.release_skew_human_review_required).lower()}",
        file=output,
    )
    _print_runtime_facts(result=result, output=output)
    _print_completed_cells(result=result, output=output)

    if result.status is SmokeStatus.STRUCTURALLY_VALID:
        print("STRUCTURALLY_VALID", file=output)
        print("release skew human review = REQUIRED", file=output)
        print("canonical Level-C execution = NOT AUTHORIZED", file=output)
        print("smoke diagnostics only = true", file=output)
        return EXIT_SUCCESS

    if result.status is SmokeStatus.INVALID_SMOKE:
        print("status = INVALID_SMOKE", file=output)
        print(f"first failed cell index = {result.failed_cell_index}", file=output)
        for issue in result.issues:
            print(f"issue code = {issue.code}", file=output)
            print(f"issue detail = {issue.detail}", file=output)
        print(f"cells completed before stop = {len(result.batches)}", file=output)
        print(
            f"invocations retained before stop = {len(result.invocations)}",
            file=output,
        )
        print("canonical Level-C execution = NOT AUTHORIZED", file=output)
        return EXIT_INVALID_SMOKE

    print("status = UNRECOGNIZED_SMOKE_RESULT", file=output)
    print("canonical Level-C execution = NOT AUTHORIZED", file=output)
    return EXIT_SMOKE_RUNTIME_FAILURE


def _print_consumed_runtime_failure(
    *,
    lineage: _GitLineage,
    exception_type: str,
    output: TextIO,
) -> None:
    """Report only the exception class after the one-shot call has begun."""

    print("SMOKE EXECUTION RESULT", file=output)
    _print_lineage(lineage=lineage, output=output)
    print("smoke status = SMOKE_RUNTIME_FAILURE", file=output)
    print(f"exception type = {exception_type}", file=output)
    print("run_postgres_smoke = CALLED ONCE", file=output)
    print("smoke authorization consumed = true", file=output)
    print("retry or replacement = NOT AUTHORIZED", file=output)
    print("canonical Level-C execution = NOT AUTHORIZED", file=output)


def main(argv: Sequence[str] | None = None) -> int:
    """Apply pre-smoke gates and consume at most one live smoke authorization."""

    if argv:
        _print_pre_smoke_failure(
            reason="COMMAND_ARGUMENTS_NOT_ACCEPTED",
            output=sys.stderr,
        )
        return EXIT_PRE_SMOKE_FAILURE

    try:
        lineage = _derive_git_lineage()
    except _PreSmokeFailure as exc:
        _print_pre_smoke_failure(reason=exc.code, output=sys.stderr)
        return EXIT_PRE_SMOKE_FAILURE

    if lineage.branch != EXPECTED_BRANCH:
        _print_pre_smoke_failure(
            reason="WRONG_GIT_BRANCH",
            output=sys.stderr,
            lineage=lineage,
        )
        return EXIT_PRE_SMOKE_FAILURE
    if not lineage.source_tree_clean:
        _print_pre_smoke_failure(
            reason="DIRTY_SOURCE_TREE",
            output=sys.stderr,
            lineage=lineage,
        )
        return EXIT_PRE_SMOKE_FAILURE

    database_url = os.environ.get(TEST_DATABASE_URL_ENVIRONMENT_VARIABLE)
    if not database_url or not database_url.strip():
        database_url = None
        _print_pre_smoke_failure(
            reason="TEST_DATABASE_URL_MISSING",
            output=sys.stderr,
            lineage=lineage,
        )
        return EXIT_PRE_SMOKE_FAILURE

    try:
        try:
            result = run_postgres_smoke(
                database_url=database_url,
                run_id=lineage.run_id,
            )
        finally:
            database_url = None
    except Exception as exc:
        _print_consumed_runtime_failure(
            lineage=lineage,
            exception_type=type(exc).__name__,
            output=sys.stderr,
        )
        return EXIT_SMOKE_RUNTIME_FAILURE

    try:
        if result.evidence_kind != SMOKE_EVIDENCE_KIND:
            raise ValueError("smoke result evidence kind is not experiment-local")
        if result.release_skew_human_review_required is not True:
            raise ValueError("smoke result cannot waive release-skew human review")
        return _print_smoke_result(lineage=lineage, result=result, output=sys.stdout)
    except Exception as exc:
        _print_consumed_runtime_failure(
            lineage=lineage,
            exception_type=type(exc).__name__,
            output=sys.stderr,
        )
        return EXIT_SMOKE_RUNTIME_FAILURE


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
