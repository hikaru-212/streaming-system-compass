"""Human-operated one-shot entry point for recorded Layer-3 evidence.

Importing this experiment-owned module performs no Git inspection, environment
access, filesystem mutation, PostgreSQL work, or recorded execution. Execution
occurs only through :func:`main` or the explicit ``python -m`` entry point.

The runner derives source lineage and a fixed run ID, gates all pre-sample
requirements, invokes the existing 60-sample runtime at most once, validates
with the existing model, publishes through the existing valid-only writer, and
immediately verifies the strict evidence reader. It does not interpret costs,
compare strategies, retry, define another control, or alter production code.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import TextIO

from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ALL_CONTROLS,
    RECORDED_ROUNDS,
    ControlAIdleRollbackAggregate,
    ControlBPreliminaryReadLifecycleAggregate,
    Layer3Aggregate,
    Layer3Control,
    Layer3Sample,
    RunValidity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_evidence import (
    DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT,
    EVIDENCE_FILENAMES,
    EvidenceWriteResult,
    Layer3EvidenceManifest,
    PublishedLayer3Evidence,
    build_manifest,
    read_layer3_evidence_directory,
    write_layer3_evidence_directory,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime import (
    Layer3RuntimeResult,
    run_layer3_recorded,
)


EXPECTED_BRANCH = "experiment/stage4b2-post-pr6-idempotency-characterization"
RUN_ID_PREFIX = "stage4b2-post-pr6-idempotency-layer3-"
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOTAL_RECORDED_SAMPLES = len(generate_recorded_schedule().samples)
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


class OneShotRunFailure(RuntimeError):
    """Retain only a sanitized stage, class, and consumption fact.

    The failure carries no exception message, connection configuration, retry
    authority, or interpretation.
    """

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
    """Retain source facts derived directly from the current Git worktree.

    The lineage is not user-configurable and supplies no alternate run identity.
    """

    repository_root: Path
    branch: str
    full_head: str
    source_tree_clean_before_run: bool
    run_id: str


@dataclass(frozen=True)
class OneShotSummary:
    """Retain only sanitized descriptive facts after verified publication.

    Timing groups remain control-local and independent. The summary has no
    component sum, strategy comparison, causal claim, or database endpoint.
    """

    branch: str
    full_source_head: str
    run_id: str
    source_tree_clean_before_run: bool
    postgresql_server_version: str
    total_samples: int
    control_a_samples: int
    control_b_samples: int
    validation: str
    exception_count: int
    evidence_directory: str
    aggregates: tuple[Layer3Aggregate, Layer3Aggregate]


@dataclass(frozen=True)
class RunnerDependencies:
    """Provide deterministic runner seams without changing Layer-3 modules.

    Construction performs no work. The seams support human execution and fake
    deterministic tests; they do not authorize retry or alternate identities.
    """

    git_output: Callable[[Sequence[str]], str]
    environment_value: Callable[[str], str | None]
    path_exists: Callable[[Path], bool]
    server_version_loader: Callable[[str], str]
    recorded_runner: Callable[..., Layer3RuntimeResult]
    manifest_builder: Callable[..., Layer3EvidenceManifest]
    evidence_writer: Callable[..., EvidenceWriteResult | None]
    evidence_reader: Callable[[Path], PublishedLayer3Evidence]


def _default_dependencies() -> RunnerDependencies:
    """Build the live dependency boundary without performing any action.

    Git, environment, filesystem, and PostgreSQL access remain deferred until
    :func:`main` is explicitly called.
    """

    return RunnerDependencies(
        git_output=_git_output,
        environment_value=os.environ.get,
        path_exists=lambda path: path.exists(),
        server_version_loader=_load_guarded_server_version,
        recorded_runner=run_layer3_recorded,
        manifest_builder=build_manifest,
        evidence_writer=write_layer3_evidence_directory,
        evidence_reader=read_layer3_evidence_directory,
    )


def _run_one_shot(
    dependencies: RunnerDependencies | None = None,
) -> OneShotSummary:
    """Execute one gated fixed run and return verified sanitized evidence.

    Failures before ``recorded_runner`` are marked unconsumed. Immediately
    before that callable is invoked, authorization becomes consumed; every
    later failure stops without any second invocation, retry, or replacement.
    """

    deps = _default_dependencies() if dependencies is None else dependencies
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
            source_tree_clean_before_run=(
                lineage.source_tree_clean_before_run
            ),
            postgresql_server_version=server_version,
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
            result=result,
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
            expected_result=result,
            expected_directory=final_directory,
            publication=publication,
        )
        return _build_summary(
            lineage=lineage,
            published=published,
            evidence_directory=publication.directory,
        )
    except OneShotRunFailure:
        raise
    except Exception as exc:
        _fail("read_back", type(exc).__name__, True)


def print_summary(summary: OneShotSummary, *, stream: TextIO) -> None:
    """Print sanitized control-local descriptive evidence in microseconds.

    The output omits connection data, component sums, comparative judgments,
    architecture preferences, capacity claims, and retry policy.
    """

    print("LAYER3_RECORDED_RUN=SUCCESS", file=stream)
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
    print(f"control_a_samples={summary.control_a_samples}", file=stream)
    print(f"control_b_samples={summary.control_b_samples}", file=stream)
    print(f"validation={summary.validation}", file=stream)
    print(f"exceptions={summary.exception_count}", file=stream)
    print(f"evidence_directory={summary.evidence_directory}", file=stream)

    control_a, control_b = summary.aggregates
    _print_timing(
        stream=stream,
        control=control_a.control,
        timing="cleanup",
        statistics=control_a.cleanup_elapsed_ns,
    )
    for timing, statistics in (
        ("idempotency_check", control_b.idempotency_check_elapsed_ns),
        ("accepted_history_load", control_b.accepted_history_load_elapsed_ns),
        ("cleanup", control_b.cleanup_elapsed_ns),
        ("direct_lifecycle", control_b.lifecycle_elapsed_ns),
    ):
        _print_timing(
            stream=stream,
            control=control_b.control,
            timing=timing,
            statistics=statistics,
        )


def main(
    *,
    dependencies: RunnerDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the explicit one-shot CLI and suppress raw exception messages.

    The success path prints descriptive evidence only. Failure output retains
    only stage, exception class, and authorization-consumption state.
    """

    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        summary = _run_one_shot(dependencies)
    except OneShotRunFailure as exc:
        consumed = "true" if exc.authorization_consumed else "false"
        print(
            "LAYER3_RECORDED_RUN=FAILED "
            f"stage={exc.stage} error_type={exc.error_type} "
            f"authorization_consumed={consumed}",
            file=err,
        )
        return 2
    except Exception as exc:
        print(
            "LAYER3_RECORDED_RUN=FAILED "
            f"stage=unknown error_type={type(exc).__name__} "
            "authorization_consumed=false",
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


def _require_valid_runtime_result(result: Layer3RuntimeResult) -> None:
    schedule = generate_recorded_schedule()
    if not isinstance(result, Layer3RuntimeResult):
        _fail("recorded_validation", "UnexpectedRuntimeResult", True)
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
    published: PublishedLayer3Evidence,
    expected_manifest: Layer3EvidenceManifest,
    expected_result: Layer3RuntimeResult,
    expected_directory: Path,
    publication: EvidenceWriteResult,
) -> None:
    if publication.directory != expected_directory:
        _fail("read_back", "EvidenceDirectoryMismatch", True)
    publication_paths = {
        publication.manifest_path,
        publication.samples_path,
        publication.aggregates_path,
    }
    if (
        {path.parent for path in publication_paths} != {publication.directory}
        or {path.name for path in publication_paths} != EVIDENCE_FILENAMES
    ):
        _fail("read_back", "EvidenceFileSetMismatch", True)
    if published.manifest != expected_manifest:
        _fail("read_back", "ManifestMismatch", True)
    if published.samples != expected_result.samples:
        _fail("read_back", "SampleMismatch", True)
    _require_exact_accounting(published.samples, consumed=True)
    validation = validate_run(generate_recorded_schedule(), published.samples)
    if validation.validity is not RunValidity.VALID:
        _fail("read_back", "InvalidPublishedSamples", True)
    if len(published.aggregates) != len(ALL_CONTROLS):
        _fail("read_back", "AggregateCountMismatch", True)
    if published.aggregates != aggregate_recorded_samples(published.samples):
        _fail("read_back", "AggregateRecomputationMismatch", True)


def _require_exact_accounting(
    samples: Sequence[Layer3Sample],
    *,
    consumed: bool,
) -> None:
    schedule = generate_recorded_schedule()
    if len(samples) != TOTAL_RECORDED_SAMPLES:
        _fail("recorded_validation", "SampleCountMismatch", consumed)
    counts = Counter(sample.control for sample in samples)
    if counts != {control: RECORDED_ROUNDS for control in ALL_CONTROLS}:
        _fail("recorded_validation", "ControlCountMismatch", consumed)
    observed_coordinates = tuple(sample.coordinate for sample in samples)
    planned_coordinates = tuple(plan.coordinate for plan in schedule.samples)
    if observed_coordinates != planned_coordinates:
        _fail("recorded_validation", "SampleOrderMismatch", consumed)
    if any(sample.exception_type is not None for sample in samples):
        _fail("recorded_validation", "UnexpectedSampleException", consumed)


def _build_summary(
    *,
    lineage: GitLineage,
    published: PublishedLayer3Evidence,
    evidence_directory: Path,
) -> OneShotSummary:
    counts = Counter(sample.control for sample in published.samples)
    aggregates = published.aggregates
    if not isinstance(aggregates[0], ControlAIdleRollbackAggregate) or not isinstance(
        aggregates[1], ControlBPreliminaryReadLifecycleAggregate
    ):
        _fail("read_back", "AggregateTypeMismatch", True)
    return OneShotSummary(
        branch=lineage.branch,
        full_source_head=lineage.full_head,
        run_id=lineage.run_id,
        source_tree_clean_before_run=lineage.source_tree_clean_before_run,
        postgresql_server_version=(
            published.manifest.postgresql_server_version
        ),
        total_samples=len(published.samples),
        control_a_samples=counts[Layer3Control.CONTROL_A_IDLE_ROLLBACK],
        control_b_samples=counts[
            Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE
        ],
        validation=RunValidity.VALID.value,
        exception_count=sum(
            sample.exception_type is not None for sample in published.samples
        ),
        evidence_directory=evidence_directory.relative_to(PROJECT_ROOT).as_posix(),
        aggregates=(aggregates[0], aggregates[1]),
    )


def _print_timing(*, stream: TextIO, control, timing: str, statistics) -> None:
    print(
        f"control={control.value} timing={timing} "
        "microseconds["
        f"min={_microseconds(statistics.minimum_ns)},"
        f"mean={_microseconds(statistics.mean_ns)},"
        f"median={_microseconds(statistics.median_ns)},"
        f"max={_microseconds(statistics.maximum_ns)}]",
        file=stream,
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
