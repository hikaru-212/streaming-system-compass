"""Human-operated one-shot entry point for recorded Layer-2 evidence.

Importing this module performs no Git, environment, PostgreSQL, filesystem, or
experiment action. Execution occurs only through :func:`main` or the explicit
``python -m`` entry point. The runner derives source lineage and its run ID,
performs all pre-sample gates, invokes the existing fixed recorded runtime at
most once, validates with the existing model, publishes through the existing
valid-only writer, and immediately verifies the published evidence reader.

This module owns execution mechanics only. It does not interpret comparative
cost, select an architecture, implement retries, or define Layer 3 behavior.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, TextIO

from experiments.stage4b2.postgres_idempotency_check_characterization import (
    ALL_CELLS,
    CellAggregate,
    Layer2Sample,
    RECORDED_SAMPLES_PER_CELL,
    RunValidity,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_check_evidence import (
    DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT,
    EvidenceWriteResult,
    Layer2EvidenceManifest,
    PublishedLayer2Evidence,
    build_manifest,
    read_evidence_directory,
    write_evidence_directory,
)
from experiments.stage4b2.postgres_idempotency_check_runtime import (
    Layer2RuntimeResult,
    run_layer2_recorded,
)


EXPECTED_BRANCH = "experiment/stage4b2-post-pr6-idempotency-characterization"
RUN_ID_PREFIX = "stage4b2-post-pr6-idempotency-layer2-"
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


class OneShotRunFailure(RuntimeError):
    """Retain a sanitized failure stage and authorization-consumption fact."""

    def __init__(
        self,
        *,
        stage: str,
        error_type: str,
        authorization_consumed: bool,
    ) -> None:
        super().__init__(stage)
        self.stage = stage
        self.error_type = error_type
        self.authorization_consumed = authorization_consumed


@dataclass(frozen=True)
class GitLineage:
    """Retain source facts derived directly from the current Git worktree."""

    repository_root: Path
    branch: str
    full_head: str
    source_tree_clean_before_run: bool
    run_id: str


@dataclass(frozen=True)
class OneShotSummary:
    """Retain only sanitized descriptive facts after verified publication."""

    branch: str
    full_source_head: str
    run_id: str
    source_tree_clean_before_run: bool
    postgresql_server_version: str
    total_samples: int
    samples_per_cell: int
    validation: str
    exception_count: int
    reuse_success_count: int
    final_idle_count: int
    evidence_directory: str
    aggregates: tuple[CellAggregate, ...]


@dataclass(frozen=True)
class RunnerDependencies:
    """Provide deterministic seams without changing production experiment code."""

    git_output: Callable[[Sequence[str]], str]
    environment_value: Callable[[str], str | None]
    path_exists: Callable[[Path], bool]
    server_version_loader: Callable[[str], str]
    recorded_runner: Callable[..., Layer2RuntimeResult]
    manifest_builder: Callable[..., Layer2EvidenceManifest]
    evidence_writer: Callable[..., EvidenceWriteResult | None]
    evidence_reader: Callable[[Path], PublishedLayer2Evidence]


def default_dependencies() -> RunnerDependencies:
    """Build the live dependency boundary without performing any action."""

    return RunnerDependencies(
        git_output=_git_output,
        environment_value=os.environ.get,
        path_exists=lambda path: path.exists(),
        server_version_loader=_load_guarded_server_version,
        recorded_runner=run_layer2_recorded,
        manifest_builder=build_manifest,
        evidence_writer=write_evidence_directory,
        evidence_reader=read_evidence_directory,
    )


def run_one_shot(
    dependencies: RunnerDependencies | None = None,
) -> OneShotSummary:
    """Execute one gated fixed run and return its verified sanitized summary.

    All failures before ``recorded_runner`` are marked pre-sample. Once that
    callable is invoked, every failure is marked authorization-consumed and no
    code path invokes it again.
    """

    deps = default_dependencies() if dependencies is None else dependencies
    lineage = _pre_sample_lineage(deps)
    final_directory = DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT / lineage.run_id
    if deps.path_exists(final_directory):
        _fail("evidence_directory", "ExistingRunDirectory", False)

    database_url = deps.environment_value(TEST_DATABASE_URL_ENV)
    if not isinstance(database_url, str) or not database_url:
        _fail("database_configuration", "MissingTestDatabaseUrl", False)

    try:
        server_version = deps.server_version_loader(database_url)
        manifest = deps.manifest_builder(
            run_id=lineage.run_id,
            source_commit=lineage.full_head,
            source_tree_clean_before_run=lineage.source_tree_clean_before_run,
            postgresql_server_version=server_version,
            structural_smoke_validated=True,
        )
    except Exception as exc:
        _fail("guarded_server_metadata", type(exc).__name__, False)

    try:
        result = deps.recorded_runner(database_url, run_id=lineage.run_id)
    except Exception as exc:
        _fail("recorded_runtime", type(exc).__name__, True)

    try:
        _require_valid_runtime_result(result)
        publication = deps.evidence_writer(
            output_root=DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT,
            manifest=manifest,
            samples=result.samples,
        )
        if publication is None:
            _fail("publication", "WriterRefusedEvidence", True)
    except OneShotRunFailure:
        raise
    except Exception as exc:
        _fail("publication", type(exc).__name__, True)

    try:
        published = deps.evidence_reader(publication.directory)
        _require_valid_read_back(
            published=published,
            expected_manifest=manifest,
            expected_samples=result.samples,
            expected_directory=final_directory,
            publication=publication,
        )
        return _build_summary(
            lineage=lineage,
            server_version=server_version,
            published=published,
            evidence_directory=publication.directory,
        )
    except OneShotRunFailure:
        raise
    except Exception as exc:
        _fail("read_back", type(exc).__name__, True)


def print_summary(summary: OneShotSummary, *, stream: TextIO) -> None:
    """Print descriptive evidence without endpoint data or interpretation."""

    print("LAYER2_RECORDED_RUN=SUCCESS", file=stream)
    print(f"branch={summary.branch}", file=stream)
    print(f"source_head={summary.full_source_head}", file=stream)
    print(f"run_id={summary.run_id}", file=stream)
    print(
        "source_tree_clean_before_run="
        f"{str(summary.source_tree_clean_before_run).lower()}",
        file=stream,
    )
    print(
        f"postgresql_server_version={summary.postgresql_server_version}",
        file=stream,
    )
    print(f"samples={summary.total_samples}", file=stream)
    print(f"samples_per_cell={summary.samples_per_cell}", file=stream)
    print(f"validation={summary.validation}", file=stream)
    print(f"exceptions={summary.exception_count}", file=stream)
    print(
        f"reuse_select_succeeded={summary.reuse_success_count}/"
        f"{summary.total_samples}",
        file=stream,
    )
    print(
        f"final_idle={summary.final_idle_count}/{summary.total_samples}",
        file=stream,
    )
    print(f"evidence_directory={summary.evidence_directory}", file=stream)
    for aggregate in summary.aggregates:
        check = aggregate.check_elapsed_ns
        cleanup = aggregate.cleanup_elapsed_ns
        print(
            f"cell={aggregate.cell.identity} "
            "check_us["
            f"min={_microseconds(check.minimum_ns)},"
            f"mean={_microseconds(check.mean_ns)},"
            f"median={_microseconds(check.median_ns)},"
            f"max={_microseconds(check.maximum_ns)}] "
            "cleanup_us["
            f"min={_microseconds(cleanup.minimum_ns)},"
            f"mean={_microseconds(cleanup.mean_ns)},"
            f"median={_microseconds(cleanup.median_ns)},"
            f"max={_microseconds(cleanup.maximum_ns)}]",
            file=stream,
        )


def main(
    *,
    dependencies: RunnerDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the explicit one-shot CLI and suppress raw exception messages."""

    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        summary = run_one_shot(dependencies)
    except OneShotRunFailure as exc:
        consumed = "true" if exc.authorization_consumed else "false"
        print(
            "LAYER2_RECORDED_RUN=FAILED "
            f"stage={exc.stage} error_type={exc.error_type} "
            f"authorization_consumed={consumed}",
            file=err,
        )
        return 2
    except Exception as exc:
        print(
            "LAYER2_RECORDED_RUN=FAILED "
            f"stage=unknown error_type={type(exc).__name__} "
            "authorization_consumed=unknown",
            file=err,
        )
        return 2
    print_summary(summary, stream=out)
    return 0


def _pre_sample_lineage(deps: RunnerDependencies) -> GitLineage:
    try:
        repository_root = Path(deps.git_output(("rev-parse", "--show-toplevel")))
        branch = deps.git_output(("branch", "--show-current"))
        full_head = deps.git_output(("rev-parse", "HEAD"))
        status = deps.git_output(
            ("status", "--porcelain=v1", "--untracked-files=normal")
        )
    except Exception as exc:
        _fail("git_lineage", type(exc).__name__, False)

    if repository_root.resolve() != PROJECT_ROOT.resolve():
        _fail("repository_root", "UnexpectedRepositoryRoot", False)
    if branch != EXPECTED_BRANCH:
        _fail("branch", "UnexpectedBranch", False)
    if _FULL_COMMIT.fullmatch(full_head) is None:
        _fail("source_head", "InvalidGitHead", False)
    clean = status == ""
    if not clean:
        _fail("working_tree", "DirtyWorkingTree", False)
    return GitLineage(
        repository_root=repository_root,
        branch=branch,
        full_head=full_head,
        source_tree_clean_before_run=clean,
        run_id=f"{RUN_ID_PREFIX}{full_head[:7]}",
    )


def _git_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.rstrip("\n")


def _load_guarded_server_version(database_url: str) -> str:
    """Read only guarded server version metadata before any recorded sample."""

    from src.storage.postgres_connection import connect_postgres

    from experiments.stage4b2.postgres_idempotency_check_runtime import (
        _guard_test_connection,
    )

    connection = connect_postgres(database_url)
    try:
        _guard_test_connection(connection)
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version")
            row = cursor.fetchone()
        connection.rollback()
        if row is None or not isinstance(row[0], str) or not row[0]:
            raise ValueError("server version metadata is unavailable")
        return row[0]
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def _require_valid_runtime_result(result: Layer2RuntimeResult) -> None:
    schedule = generate_recorded_schedule()
    if result.schedule != schedule:
        _fail("recorded_validation", "ScheduleMismatch", True)
    validation = validate_run(schedule, result.samples)
    if (
        validation.validity is not RunValidity.VALID
        or result.validation.validity is not RunValidity.VALID
        or result.validation != validation
    ):
        _fail("recorded_validation", "InvalidRecordedRun", True)
    _require_exact_accounting(result.samples, consumed=True)


def _require_valid_read_back(
    *,
    published: PublishedLayer2Evidence,
    expected_manifest: Layer2EvidenceManifest,
    expected_samples: Sequence[Layer2Sample],
    expected_directory: Path,
    publication: EvidenceWriteResult,
) -> None:
    if publication.directory != expected_directory:
        _fail("read_back", "EvidenceDirectoryMismatch", True)
    if published.manifest != expected_manifest:
        _fail("read_back", "ManifestMismatch", True)
    if published.samples != tuple(expected_samples):
        _fail("read_back", "SampleMismatch", True)
    _require_exact_accounting(published.samples, consumed=True)
    if len(published.aggregates) != len(ALL_CELLS):
        _fail("read_back", "AggregateCountMismatch", True)
    if published.aggregates != aggregate_recorded_samples(published.samples):
        _fail("read_back", "AggregateRecomputationMismatch", True)


def _require_exact_accounting(
    samples: Sequence[Layer2Sample],
    *,
    consumed: bool,
) -> None:
    schedule = generate_recorded_schedule()
    if len(samples) != len(schedule.samples):
        _fail("recorded_validation", "SampleCountMismatch", consumed)
    counts = Counter(sample.cell for sample in samples)
    if counts != {cell: RECORDED_SAMPLES_PER_CELL for cell in ALL_CELLS}:
        _fail("recorded_validation", "CellCountMismatch", consumed)
    if any(sample.exception_type is not None for sample in samples):
        _fail("recorded_validation", "UnexpectedSampleException", consumed)


def _build_summary(
    *,
    lineage: GitLineage,
    server_version: str,
    published: PublishedLayer2Evidence,
    evidence_directory: Path,
) -> OneShotSummary:
    samples = published.samples
    return OneShotSummary(
        branch=lineage.branch,
        full_source_head=lineage.full_head,
        run_id=lineage.run_id,
        source_tree_clean_before_run=lineage.source_tree_clean_before_run,
        postgresql_server_version=server_version,
        total_samples=len(samples),
        samples_per_cell=RECORDED_SAMPLES_PER_CELL,
        validation=RunValidity.VALID.value,
        exception_count=sum(
            sample.exception_type is not None for sample in samples
        ),
        reuse_success_count=sum(
            sample.reuse_select_succeeded is True for sample in samples
        ),
        final_idle_count=sum(
            sample.final_transaction_status is TransactionStatusIdentity.IDLE
            for sample in samples
        ),
        evidence_directory=evidence_directory.relative_to(PROJECT_ROOT).as_posix(),
        aggregates=published.aggregates,
    )


def _microseconds(value_ns: int | float) -> str:
    return f"{value_ns / 1_000:.3f}"


def _fail(stage: str, error_type: str, consumed: bool) -> None:
    raise OneShotRunFailure(
        stage=stage,
        error_type=error_type,
        authorization_consumed=consumed,
    ) from None


if __name__ == "__main__":
    raise SystemExit(main())
