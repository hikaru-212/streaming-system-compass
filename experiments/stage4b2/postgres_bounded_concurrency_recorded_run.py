"""Human-operated one-shot canonical runner for Stage 4B.2 PR7.

Importing this module performs no Git query, environment read, PostgreSQL
access, experiment execution, or evidence publication. Only ``main()`` may
derive committed source lineage, consume one canonical execution authorization,
and delegate valid-only publication to the existing evidence boundary. Output
is sanitized experiment accounting and release-skew input for later human
review; it never selects a strategy or derives production policy.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import Any, TextIO

from experiments.stage4b2.postgres_bounded_concurrency_evidence import (
    CANONICAL_EXPECTED_BATCH_COUNT,
    CANONICAL_EXPECTED_INVOCATION_COUNT,
    CANONICAL_EXPECTED_OWNERSHIP_COUNT,
    CANONICAL_EXPECTED_RATE_GROUP_COUNT,
    build_canonical_manifest,
    canonical_evidence_root,
    write_canonical_evidence_directory,
)
from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    EXACT_CELL_COUNT,
    RECORDED_BATCHES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    RETAINED_WORKER_LEVELS,
    WARMUP_BATCHES_PER_CELL,
    EvidenceStatus,
    LevelRuntime,
    RecordedExecutionResult,
    RecordedScheduleExecutor,
    generate_fixed_schedule,
    open_postgres_level_runtime,
)


EXPECTED_BRANCH = "experiment/stage4b2-pr7-bounded-concurrency-characterization"
RUN_ID_PREFIX = "stage4b2-pr7-canonical-"
TEST_DATABASE_URL_ENVIRONMENT_VARIABLE = "TEST_DATABASE_URL"
EXPECTED_TOPOLOGY_LABEL = "guarded-test-postgresql"

EXIT_SUCCESS = 0
EXIT_PRE_EXECUTION_FAILURE = 2
EXIT_EXECUTION_FAILURE = 3
EXIT_POST_EXECUTION_FAILURE = 4
EXIT_PUBLICATION_FAILURE = 5

_FULL_LOWERCASE_HEAD = re.compile(r"[0-9a-f]{40}")


class _RunnerGateError(RuntimeError):
    """Stop one runner stage without retaining a sensitive failure message."""


@dataclass(frozen=True)
class _GitLineage:
    """Retain sanitized committed-source facts for the one-shot source gate."""

    repository_root: Path
    branch: str
    full_head: str
    source_tree_clean: bool

    def __post_init__(self) -> None:
        if not self.repository_root.is_absolute():
            raise ValueError("repository root must be absolute")
        if not self.branch:
            raise ValueError("branch must not be empty")
        if _FULL_LOWERCASE_HEAD.fullmatch(self.full_head) is None:
            raise ValueError("HEAD must be one full lowercase Git identity")
        if type(self.source_tree_clean) is not bool:
            raise TypeError("source_tree_clean must be a boolean fact")

    @property
    def run_id(self) -> str:
        """Derive the sole canonical run ID from the first seven HEAD chars."""

        return f"{RUN_ID_PREFIX}{self.full_head[:7]}"


@dataclass(frozen=True)
class _RuntimeFactSnapshot:
    """Retain only sanitized run-level facts observed from one opened level."""

    worker_level: int
    postgresql_server_version: str | None
    isolation_level: str
    autocommit: bool
    topology_label: str


@dataclass(frozen=True)
class _CanonicalRuntimeFacts:
    """Hold mutually consistent sanitized facts from the consumed execution."""

    postgresql_server_version: str
    isolation_level: str
    autocommit: bool
    topology_label: str


class _RuntimeFactCollector:
    """Observe facts from the one authorized execution without opening resources.

    The collector stores no connection, endpoint, role, database, or environment
    identity. It validates facts only after the canonical executor has returned
    and never authorizes retry, replacement, or a second runtime opening.
    """

    def __init__(self) -> None:
        self._snapshots: list[_RuntimeFactSnapshot] = []

    def observe(self, runtime: LevelRuntime) -> None:
        """Capture one level's existing sanitized runtime facts exactly once."""

        self._snapshots.append(
            _RuntimeFactSnapshot(
                worker_level=runtime.worker_level,
                postgresql_server_version=runtime.postgresql_server_version,
                isolation_level=runtime.isolation_level,
                autocommit=runtime.autocommit,
                topology_label=runtime.topology_label,
            )
        )

    def require_consistent(self) -> _CanonicalRuntimeFacts:
        """Return one run-level fact set or stop without authorizing a rerun."""

        levels = tuple(item.worker_level for item in self._snapshots)
        if len(levels) != len(RETAINED_WORKER_LEVELS) or set(levels) != set(
            RETAINED_WORKER_LEVELS
        ):
            raise _RunnerGateError
        if len(set(levels)) != len(levels):
            raise _RunnerGateError
        if any(
            item.postgresql_server_version is None
            or not item.postgresql_server_version
            or not item.isolation_level
            or type(item.autocommit) is not bool
            or item.topology_label != EXPECTED_TOPOLOGY_LABEL
            for item in self._snapshots
        ):
            raise _RunnerGateError
        versions = {item.postgresql_server_version for item in self._snapshots}
        isolations = {item.isolation_level for item in self._snapshots}
        autocommit_facts = {item.autocommit for item in self._snapshots}
        topology_labels = {item.topology_label for item in self._snapshots}
        if any(
            len(values) != 1
            for values in (
                versions,
                isolations,
                autocommit_facts,
                topology_labels,
            )
        ):
            raise _RunnerGateError
        server_version = next(iter(versions))
        if not isinstance(server_version, str):
            raise _RunnerGateError
        return _CanonicalRuntimeFacts(
            postgresql_server_version=server_version,
            isolation_level=next(iter(isolations)),
            autocommit=next(iter(autocommit_facts)),
            topology_label=next(iter(topology_labels)),
        )


def _git_output(arguments: tuple[str, ...], *, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise _RunnerGateError from None
    return completed.stdout.strip()


def _derive_git_lineage() -> _GitLineage:
    repository_root_text = _git_output(("rev-parse", "--show-toplevel"))
    if not repository_root_text:
        raise _RunnerGateError
    repository_root = Path(repository_root_text)
    try:
        return _GitLineage(
            repository_root=repository_root,
            branch=_git_output(("branch", "--show-current"), cwd=repository_root),
            full_head=_git_output(("rev-parse", "HEAD"), cwd=repository_root),
            source_tree_clean=not _git_output(
                ("status", "--porcelain", "--untracked-files=normal"),
                cwd=repository_root,
            ),
        )
    except (TypeError, ValueError):
        raise _RunnerGateError from None


def _require_source_gate(lineage: _GitLineage) -> None:
    if lineage.branch != EXPECTED_BRANCH or not lineage.source_tree_clean:
        raise _RunnerGateError


def _require_new_run_directory(lineage: _GitLineage) -> Path:
    final_directory = canonical_evidence_root(lineage.repository_root) / lineage.run_id
    if os.path.lexists(final_directory):
        raise _RunnerGateError
    return final_directory


def _require_exact_schedule(schedule: Any) -> None:
    if schedule.seed != RECORDED_SCHEDULE_SEED:
        raise _RunnerGateError
    if schedule.retained_worker_levels != RETAINED_WORKER_LEVELS:
        raise _RunnerGateError
    if schedule.warmup_batches_per_cell != WARMUP_BATCHES_PER_CELL:
        raise _RunnerGateError
    if schedule.recorded_batches_per_cell != RECORDED_BATCHES_PER_CELL:
        raise _RunnerGateError
    if len(schedule.cells) != EXACT_CELL_COUNT:
        raise _RunnerGateError
    if len(schedule.recorded_batches) != CANONICAL_EXPECTED_BATCH_COUNT:
        raise _RunnerGateError
    planned_invocations = sum(
        plan.cell.worker_level for plan in schedule.recorded_batches
    )
    if planned_invocations != CANONICAL_EXPECTED_INVOCATION_COUNT:
        raise _RunnerGateError
    if sum(RETAINED_WORKER_LEVELS) != CANONICAL_EXPECTED_OWNERSHIP_COUNT:
        raise _RunnerGateError


def _require_valid_result(
    result: RecordedExecutionResult,
    *,
    exact_schedule: Any,
) -> None:
    if result.schedule != exact_schedule:
        raise _RunnerGateError
    if (
        result.validation.status is not EvidenceStatus.VALID
        or result.validation.issues
    ):
        raise _RunnerGateError
    if len(result.invocations) != CANONICAL_EXPECTED_INVOCATION_COUNT:
        raise _RunnerGateError
    if len(result.batches) != CANONICAL_EXPECTED_BATCH_COUNT:
        raise _RunnerGateError
    if len(result.ownership) != CANONICAL_EXPECTED_OWNERSHIP_COUNT:
        raise _RunnerGateError
    if any(item.exception_type is not None for item in result.invocations):
        raise _RunnerGateError


def _require_valid_readback(
    readback: Any,
    *,
    manifest: Any,
    final_directory: Path,
) -> None:
    if readback.manifest != manifest or readback.run_directory != final_directory:
        raise _RunnerGateError
    result = readback.result
    if (
        result.validation.status is not EvidenceStatus.VALID
        or result.validation.issues
        or len(result.invocations) != CANONICAL_EXPECTED_INVOCATION_COUNT
        or len(result.batches) != CANONICAL_EXPECTED_BATCH_COUNT
        or len(result.ownership) != CANONICAL_EXPECTED_OWNERSHIP_COUNT
    ):
        raise _RunnerGateError
    if len(readback.batch_rate_aggregates) != CANONICAL_EXPECTED_RATE_GROUP_COUNT:
        raise _RunnerGateError


def _print_failure(
    *,
    stage: str,
    exception_type: str,
    authorization_consumed: bool,
    output: TextIO,
) -> None:
    print(f"failure stage = {stage}", file=output)
    print(f"exception class = {exception_type}", file=output)
    print(
        "authorization_consumed = "
        f"{str(authorization_consumed).lower()}",
        file=output,
    )


def _release_skew_by_level(
    result: RecordedExecutionResult,
) -> dict[int, tuple[int, ...]]:
    grouped: dict[int, list[int]] = defaultdict(list)
    for batch in result.batches:
        grouped[batch.worker_level].append(
            batch.last_start_offset_ns - batch.first_start_offset_ns
        )
    if set(grouped) != set(RETAINED_WORKER_LEVELS):
        raise _RunnerGateError
    return {level: tuple(grouped[level]) for level in RETAINED_WORKER_LEVELS}


def _print_success(
    *,
    lineage: _GitLineage,
    facts: _CanonicalRuntimeFacts,
    readback: Any,
    output: TextIO,
) -> None:
    result = readback.result
    skews = _release_skew_by_level(result)
    print(f"source branch = {lineage.branch}", file=output)
    print(f"full source HEAD = {lineage.full_head}", file=output)
    print(f"run ID = {lineage.run_id}", file=output)
    print("clean source = true", file=output)
    print(f"schedule seed = {RECORDED_SCHEDULE_SEED}", file=output)
    print("worker levels = 1,2,4,8", file=output)
    print(f"exact cells = {EXACT_CELL_COUNT}", file=output)
    print(f"warmup batches / cell = {WARMUP_BATCHES_PER_CELL}", file=output)
    print(f"recorded batches / cell = {RECORDED_BATCHES_PER_CELL}", file=output)
    print(f"recorded batches = {len(result.batches)}", file=output)
    print(f"recorded invocations = {len(result.invocations)}", file=output)
    print(f"ownership records = {len(result.ownership)}", file=output)
    print("validation = VALID", file=output)
    print("unexpected exceptions = 0", file=output)
    print(
        f"PostgreSQL server version = {facts.postgresql_server_version}",
        file=output,
    )
    print(f"transaction isolation = {facts.isolation_level}", file=output)
    print(f"autocommit = {str(facts.autocommit).lower()}", file=output)
    print(f"topology label = {facts.topology_label}", file=output)
    print(f"evidence directory = {readback.run_directory}", file=output)
    print(
        "release-skew diagnostics = HUMAN-REVIEW INPUT ONLY",
        file=output,
    )

    invocations_by_level = _count_by_worker_level(result.invocations)
    batches_by_level = _count_by_worker_level(result.batches)
    for worker_level in RETAINED_WORKER_LEVELS:
        values = skews[worker_level]
        print(f"worker level = {worker_level}", file=output)
        print(
            f"recorded batch count = {batches_by_level[worker_level]}",
            file=output,
        )
        print(
            f"invocation count = {invocations_by_level[worker_level]}",
            file=output,
        )
        print(f"release skew ns minimum = {min(values)}", file=output)
        print(
            f"release skew ns median = {statistics.median(values)}",
            file=output,
        )
        print(f"release skew ns maximum = {max(values)}", file=output)
    print("release-skew interpretation = HUMAN REVIEW REQUIRED", file=output)
    print("release-skew acceptance threshold = NOT DEFINED", file=output)


def _count_by_worker_level(records: Sequence[Any]) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for record in records:
        counts[record.worker_level] += 1
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    """Consume at most one human-authorized canonical Level-C execution.

    The function applies Git, branch, clean-tree, run-directory, schedule, and
    database-configuration gates before setting its one-shot authorization as
    consumed. It delegates runtime work and evidence publication to the
    existing canonical components, clears its database URL reference after the
    call, and prints only sanitized success facts or stage/class/consumption on
    failure. It never retries, runs smoke, selects a strategy, or derives
    capacity, SLO, admission, concurrency, or rate-limit policy.
    """

    authorization_consumed = False
    if argv:
        _print_failure(
            stage="COMMAND_GATE",
            exception_type=_RunnerGateError.__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE

    try:
        lineage = _derive_git_lineage()
        _require_source_gate(lineage)
    except Exception as exc:
        _print_failure(
            stage="SOURCE_GATE",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE

    try:
        final_directory = _require_new_run_directory(lineage)
    except Exception as exc:
        _print_failure(
            stage="EVIDENCE_DIRECTORY_GATE",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE

    try:
        exact_schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
        _require_exact_schedule(exact_schedule)
    except Exception as exc:
        _print_failure(
            stage="SCHEDULE_GATE",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE

    database_url = os.environ.get(TEST_DATABASE_URL_ENVIRONMENT_VARIABLE)
    if not database_url or not database_url.strip():
        database_url = None
        _print_failure(
            stage="DATABASE_CONFIGURATION_GATE",
            exception_type=_RunnerGateError.__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE

    facts = _RuntimeFactCollector()

    @contextmanager
    def open_authorized_level(worker_level: int) -> Iterator[LevelRuntime]:
        if database_url is None:
            raise _RunnerGateError
        with open_postgres_level_runtime(
            database_url=database_url,
            worker_level=worker_level,
        ) as runtime:
            facts.observe(runtime)
            yield runtime

    try:
        executor = RecordedScheduleExecutor(
            open_level_runtime=open_authorized_level
        )
    except Exception as exc:
        database_url = None
        _print_failure(
            stage="EXECUTOR_CONSTRUCTION_GATE",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PRE_EXECUTION_FAILURE
    try:
        authorization_consumed = True
        result = executor.execute(run_id=lineage.run_id, schedule=exact_schedule)
    except Exception as exc:
        _print_failure(
            stage="CANONICAL_EXECUTION",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_EXECUTION_FAILURE
    finally:
        database_url = None

    try:
        _require_valid_result(result, exact_schedule=exact_schedule)
    except Exception as exc:
        _print_failure(
            stage="RUNTIME_VALIDATION",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_POST_EXECUTION_FAILURE

    try:
        consistent_facts = facts.require_consistent()
    except Exception as exc:
        _print_failure(
            stage="RUNTIME_FACT_VALIDATION",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_POST_EXECUTION_FAILURE

    try:
        manifest = build_canonical_manifest(
            run_id=lineage.run_id,
            source_commit=lineage.full_head,
            source_tree_clean_before_run=True,
            postgresql_server_version=(
                consistent_facts.postgresql_server_version
            ),
            transaction_isolation=consistent_facts.isolation_level,
            autocommit=consistent_facts.autocommit,
            topology_label=consistent_facts.topology_label,
        )
    except Exception as exc:
        _print_failure(
            stage="MANIFEST_CONSTRUCTION",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_POST_EXECUTION_FAILURE

    try:
        readback = write_canonical_evidence_directory(
            repository_root=lineage.repository_root,
            manifest=manifest,
            result=result,
        )
        _require_valid_readback(
            readback,
            manifest=manifest,
            final_directory=final_directory,
        )
    except Exception as exc:
        _print_failure(
            stage="EVIDENCE_PUBLICATION_READBACK",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_PUBLICATION_FAILURE

    try:
        _print_success(
            lineage=lineage,
            facts=consistent_facts,
            readback=readback,
            output=sys.stdout,
        )
    except Exception as exc:
        _print_failure(
            stage="SUCCESS_SUMMARY",
            exception_type=type(exc).__name__,
            authorization_consumed=authorization_consumed,
            output=sys.stderr,
        )
        return EXIT_POST_EXECUTION_FAILURE
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
