"""Canonical evidence persistence for the Stage 4B.2 PR7 experiment.

This module serializes only the already-defined canonical Level-C records,
publishes one fully valid run through an immutable atomic directory boundary,
and immediately reads the directory back for typed validation and aggregate
recomputation. It does not execute PostgreSQL or the canonical runtime, expose
a command-line entry point, choose a strategy, or derive capacity, admission,
SLO, saturation, or rate-limit policy.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    EXACT_CELL_COUNT,
    PR3_PHASE_NAMES,
    RECORDED_BATCHES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    RETAINED_WORKER_LEVELS,
    WARMUP_BATCHES_PER_CELL,
    BatchRateAggregate,
    BatchRecord,
    Cohort,
    Composition,
    DescriptiveStatistics,
    EvidenceStatus,
    InvocationAggregate,
    InvocationRecord,
    LaneOwnershipRecord,
    PhaseAggregate,
    PhaseRecord,
    PhaseState,
    RecordedExecutionResult,
    RejectionStage,
    RunValidationResult,
    TypedOutcomeCount,
    WorkloadFamily,
    aggregate_batch_rates,
    aggregate_invocations,
    batch_record_to_dict,
    classify_cohort,
    generate_fixed_schedule,
    invocation_record_to_dict,
    validate_recorded_run,
)


CANONICAL_EVIDENCE_RELATIVE_ROOT = Path(
    "experiments/stage4b2/evidence/stage4b2-pr7-canonical-levelc"
)
CANONICAL_EVIDENCE_SCHEMA_NAME = "stage4b2-pr7-canonical-levelc-evidence"
CANONICAL_EVIDENCE_SCHEMA_VERSION = 1
CANONICAL_SCHEDULE_IDENTITY = (
    "stage4b2-pr7-seed73-levels1-2-4-8-cells16-warmup3-recorded30"
)
CANONICAL_CLOCK_IDENTITY = "time.perf_counter_ns"
CANONICAL_EXPECTED_BATCH_COUNT = 480
CANONICAL_EXPECTED_INVOCATION_COUNT = 1800
CANONICAL_EXPECTED_OWNERSHIP_COUNT = 15
CANONICAL_EXPECTED_RATE_GROUP_COUNT = 16
ACCEPTED_SMOKE_SOURCE_COMMIT = "8dcfbdc1e1bc4cca8a8e7c48a73126a40ec9c958"
ACCEPTED_SMOKE_RUN_ID = "stage4b2-pr7-postgres-smoke-8dcfbdc"
ACCEPTED_SMOKE_RELEASE_SKEW_REVIEW = "ACCEPTED"
CANONICAL_PUBLICATION_RULE = "VALID_ONLY_ATOMIC_IMMUTABLE_DIRECTORY"

CANONICAL_EVIDENCE_FILENAMES = (
    "manifest.json",
    "invocations.jsonl",
    "batches.jsonl",
    "ownership.json",
    "invocation_aggregates.json",
    "batch_rate_aggregates.json",
)

_MANIFEST_FIELDS = (
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
)
_INVOCATION_FIELDS = (
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
)
_PHASE_FIELDS = ("name", "state", "elapsed_ns")
_BATCH_FIELDS = (
    "schema_name",
    "schema_version",
    "run_id",
    "batch_record_index",
    "cell_index",
    "batch_index",
    "worker_level",
    "workload_family",
    "composition",
    "release_reference_ns",
    "first_start_offset_ns",
    "last_start_offset_ns",
    "batch_elapsed_ns",
    "completed_count",
    "accepted_count",
    "typed_outcome_counts",
)
_TYPED_OUTCOME_FIELDS = ("outcome", "count")
_OWNERSHIP_FIELDS = ("worker_level", "lane_index", "connection_slot", "thread_id")
_STATISTICS_FIELDS = ("count", "minimum", "maximum", "mean", "median")
_PHASE_AGGREGATE_FIELDS = ("phase_name", "statistics_ns")
_INVOCATION_AGGREGATE_FIELDS = (
    "run_id",
    "worker_level",
    "workload_family",
    "composition",
    "cohort",
    "external_elapsed_ns",
    "phases",
)
_BATCH_RATE_AGGREGATE_FIELDS = (
    "run_id",
    "worker_level",
    "workload_family",
    "composition",
    "accepted_completion_rate_per_second",
    "all_completion_rate_per_second",
)

_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_FULL_SOURCE_COMMIT = re.compile(r"[0-9a-f]{40}")
_SANITIZED_FACT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,127}")
_FORBIDDEN_VALUE_MARKERS = (
    "test_database_url",
    "postgresql://",
    "postgres://",
    "password",
    "credential",
    "secret",
    "access_token",
    "api_key",
    "private_key",
    "endpoint",
    "hostname",
    "database_name",
    "host=",
    "port=",
    "dbname=",
    "database=",
    "username=",
    "user=",
    "dsn=",
)
_EVIDENCE_ANCESTRY = ("experiments", "stage4b2", "evidence")


class CanonicalEvidenceError(RuntimeError):
    """Report a sanitized PR7 evidence-boundary failure.

    The exception communicates only experiment-local validation or publication
    status. It must not retain producer exception messages, connection values,
    credentials, or endpoint identity, and it never authorizes another run.
    """


class CanonicalEvidenceValidationError(CanonicalEvidenceError):
    """Reject evidence that cannot satisfy the closed canonical contract.

    Validation happens before publication whenever possible. This exception
    does not imply that PostgreSQL work should be retried or replaced.
    """


class CanonicalEvidencePublicationError(CanonicalEvidenceError):
    """Report failure of immutable atomic directory publication.

    The writer cleans only its own hidden staging directory before publication.
    It never repairs or overwrites an existing final run directory.
    """


@dataclass(frozen=True)
class CanonicalEvidenceManifest:
    """Hold the exact sanitized manifest for one publishable canonical run.

    The model freezes schedule, count, clock, smoke-lineage, validation, and
    publication facts while accepting only the run/source identities and four
    sanitized PostgreSQL topology observations supplied by a future authorized
    workflow. It carries no endpoint, credential, execution authority, or
    production policy meaning.
    """

    schema_name: str
    schema_version: int
    run_id: str
    source_commit: str
    source_tree_clean_before_run: bool
    schedule_identity: str
    recorded_schedule_seed: int
    retained_worker_levels: tuple[int, ...]
    exact_cell_count: int
    warmup_batches_per_exact_cell: int
    recorded_batches_per_exact_cell: int
    expected_recorded_batch_count: int
    expected_recorded_invocation_count: int
    expected_ownership_count: int
    clock_identity: str
    postgresql_server_version: str
    transaction_isolation: str
    autocommit: bool
    topology_label: str
    validation_status: str
    smoke_source_commit: str
    smoke_run_id: str
    smoke_release_skew_review: str
    publication_rule: str

    def __post_init__(self) -> None:
        integer_fields = (
            "schema_version",
            "recorded_schedule_seed",
            "exact_cell_count",
            "warmup_batches_per_exact_cell",
            "recorded_batches_per_exact_cell",
            "expected_recorded_batch_count",
            "expected_recorded_invocation_count",
            "expected_ownership_count",
        )
        if any(type(getattr(self, name)) is not int for name in integer_fields):
            raise TypeError("manifest numeric contract fields must be integers")
        if any(type(level) is not int for level in self.retained_worker_levels):
            raise TypeError("manifest retained worker levels must be integers")
        string_fields = (
            "schema_name",
            "run_id",
            "source_commit",
            "schedule_identity",
            "clock_identity",
            "postgresql_server_version",
            "transaction_isolation",
            "topology_label",
            "validation_status",
            "smoke_source_commit",
            "smoke_run_id",
            "smoke_release_skew_review",
            "publication_rule",
        )
        if any(type(getattr(self, name)) is not str for name in string_fields):
            raise TypeError("manifest identity fields must be strings")
        expected = {
            "schema_name": CANONICAL_EVIDENCE_SCHEMA_NAME,
            "schema_version": CANONICAL_EVIDENCE_SCHEMA_VERSION,
            "schedule_identity": CANONICAL_SCHEDULE_IDENTITY,
            "recorded_schedule_seed": RECORDED_SCHEDULE_SEED,
            "retained_worker_levels": RETAINED_WORKER_LEVELS,
            "exact_cell_count": EXACT_CELL_COUNT,
            "warmup_batches_per_exact_cell": WARMUP_BATCHES_PER_CELL,
            "recorded_batches_per_exact_cell": RECORDED_BATCHES_PER_CELL,
            "expected_recorded_batch_count": CANONICAL_EXPECTED_BATCH_COUNT,
            "expected_recorded_invocation_count": (
                CANONICAL_EXPECTED_INVOCATION_COUNT
            ),
            "expected_ownership_count": CANONICAL_EXPECTED_OWNERSHIP_COUNT,
            "clock_identity": CANONICAL_CLOCK_IDENTITY,
            "validation_status": EvidenceStatus.VALID.value,
            "smoke_source_commit": ACCEPTED_SMOKE_SOURCE_COMMIT,
            "smoke_run_id": ACCEPTED_SMOKE_RUN_ID,
            "smoke_release_skew_review": (
                ACCEPTED_SMOKE_RELEASE_SKEW_REVIEW
            ),
            "publication_rule": CANONICAL_PUBLICATION_RULE,
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"manifest {name} differs from the contract")
        _require_safe_run_id(self.run_id)
        if _FULL_SOURCE_COMMIT.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be one full lowercase Git identity")
        if self.source_tree_clean_before_run is not True:
            raise ValueError("canonical publication requires a clean source tree")
        if type(self.autocommit) is not bool:
            raise TypeError("autocommit must be a boolean fact")
        for name in (
            "postgresql_server_version",
            "transaction_isolation",
            "topology_label",
        ):
            _require_sanitized_fact(name, getattr(self, name))


@dataclass(frozen=True)
class CanonicalEvidenceReadback:
    """Return one fully read-back and recomputed canonical evidence directory.

    Construction is possible only after exact-file parsing, fresh runtime
    validation, run-lineage checks, and aggregate equality. It is an
    experiment-local persistence result, not execution authorization,
    performance interpretation, or production policy.
    """

    run_directory: Path
    manifest: CanonicalEvidenceManifest
    result: RecordedExecutionResult
    invocation_aggregates: tuple[InvocationAggregate, ...]
    batch_rate_aggregates: tuple[BatchRateAggregate, ...]


def build_canonical_manifest(
    *,
    run_id: str,
    source_commit: str,
    source_tree_clean_before_run: bool,
    postgresql_server_version: str,
    transaction_isolation: str,
    autocommit: bool,
    topology_label: str,
) -> CanonicalEvidenceManifest:
    """Build the one closed manifest shape accepted for future publication.

    Only source/run identity and sanitized PostgreSQL facts are caller-owned;
    every methodological and smoke-lineage value is frozen here. The function
    neither inspects Git or PostgreSQL nor executes, publishes, or authorizes a
    canonical run.
    """

    return CanonicalEvidenceManifest(
        schema_name=CANONICAL_EVIDENCE_SCHEMA_NAME,
        schema_version=CANONICAL_EVIDENCE_SCHEMA_VERSION,
        run_id=run_id,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        schedule_identity=CANONICAL_SCHEDULE_IDENTITY,
        recorded_schedule_seed=RECORDED_SCHEDULE_SEED,
        retained_worker_levels=RETAINED_WORKER_LEVELS,
        exact_cell_count=EXACT_CELL_COUNT,
        warmup_batches_per_exact_cell=WARMUP_BATCHES_PER_CELL,
        recorded_batches_per_exact_cell=RECORDED_BATCHES_PER_CELL,
        expected_recorded_batch_count=CANONICAL_EXPECTED_BATCH_COUNT,
        expected_recorded_invocation_count=CANONICAL_EXPECTED_INVOCATION_COUNT,
        expected_ownership_count=CANONICAL_EXPECTED_OWNERSHIP_COUNT,
        clock_identity=CANONICAL_CLOCK_IDENTITY,
        postgresql_server_version=postgresql_server_version,
        transaction_isolation=transaction_isolation,
        autocommit=autocommit,
        topology_label=topology_label,
        validation_status=EvidenceStatus.VALID.value,
        smoke_source_commit=ACCEPTED_SMOKE_SOURCE_COMMIT,
        smoke_run_id=ACCEPTED_SMOKE_RUN_ID,
        smoke_release_skew_review=ACCEPTED_SMOKE_RELEASE_SKEW_REVIEW,
        publication_rule=CANONICAL_PUBLICATION_RULE,
    )


def canonical_evidence_root(repository_root: os.PathLike[str] | str) -> Path:
    """Derive the sole PR7 canonical namespace beneath a repository root.

    The function rejects evidence namespaces masquerading as repository roots
    and never accepts an alternate evidence destination. It performs no
    filesystem mutation and conveys no permission to publish or execute work.
    """

    root = _require_repository_root(repository_root)
    return root / CANONICAL_EVIDENCE_RELATIVE_ROOT


def write_canonical_evidence_directory(
    *,
    repository_root: os.PathLike[str] | str,
    manifest: CanonicalEvidenceManifest,
    result: RecordedExecutionResult,
) -> CanonicalEvidenceReadback:
    """Validate, atomically publish, and immediately read back one valid run.

    All six deterministic payloads are constructed and semantically validated
    before any namespace is created. Publication uses one hidden same-parent
    staging directory, exclusive file creation, file/directory fsync, and an
    immutable final rename. Existing runs are never overwritten, and failure
    never authorizes PostgreSQL execution, retry, replacement, or policy.
    """

    payloads = _construct_payloads(manifest=manifest, result=result)
    evidence_root = canonical_evidence_root(repository_root)
    _prepare_canonical_root(evidence_root)
    final_directory = evidence_root / manifest.run_id
    if os.path.lexists(final_directory):
        raise CanonicalEvidencePublicationError(
            "canonical run directory already exists and is immutable"
        )

    try:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=f".{manifest.run_id}.", dir=evidence_root)
        )
    except OSError:
        raise CanonicalEvidencePublicationError(
            "canonical evidence staging directory could not be created"
        ) from None
    renamed = False
    try:
        for filename in CANONICAL_EVIDENCE_FILENAMES:
            _write_payload_file(staging_directory / filename, payloads[filename])
        _fsync_directory(staging_directory)
        root_fd = os.open(evidence_root, os.O_RDONLY)
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX)
            if os.path.lexists(final_directory):
                raise CanonicalEvidencePublicationError(
                    "canonical run directory already exists and is immutable"
                )
            os.rename(staging_directory, final_directory)
            renamed = True
            try:
                os.fsync(root_fd)
            except OSError:
                os.rename(final_directory, staging_directory)
                renamed = False
                os.fsync(root_fd)
                raise
        finally:
            fcntl.flock(root_fd, fcntl.LOCK_UN)
            os.close(root_fd)
    except CanonicalEvidenceError:
        if not renamed:
            _cleanup_staging_directory(staging_directory)
        raise
    except (OSError, ValueError):
        if not renamed:
            _cleanup_staging_directory(staging_directory)
        raise CanonicalEvidencePublicationError(
            "canonical evidence atomic publication failed"
        ) from None

    readback = read_canonical_evidence_directory(
        repository_root=repository_root,
        run_directory=final_directory,
    )
    if readback.manifest != manifest:
        raise CanonicalEvidenceValidationError(
            "read-back manifest differs from the in-memory publication manifest"
        )
    return readback


def read_canonical_evidence_directory(
    *,
    repository_root: os.PathLike[str] | str,
    run_directory: os.PathLike[str] | str,
) -> CanonicalEvidenceReadback:
    """Read, validate, and recompute one exact immutable canonical directory.

    The reader accepts only a direct child of the fixed PR7 namespace with the
    exact six filenames. It reconstructs typed runtime evidence, invokes the
    existing validator and aggregators, and rejects any mismatch or secret
    marker. It never repairs evidence, runs PostgreSQL, or authorizes a rerun.
    """

    repository = _require_repository_root(repository_root)
    evidence_root = repository / CANONICAL_EVIDENCE_RELATIVE_ROOT
    _require_no_symlink_chain(repository, evidence_root)
    directory = _absolute_path(run_directory)
    if directory.parent != evidence_root or not _is_safe_run_id(directory.name):
        raise CanonicalEvidenceValidationError(
            "run directory is outside the fixed canonical namespace"
        )
    if directory.is_symlink() or not directory.is_dir():
        raise CanonicalEvidenceValidationError(
            "canonical run directory is absent or not a real directory"
        )
    entries = tuple(directory.iterdir())
    names = {entry.name for entry in entries}
    if names != set(CANONICAL_EVIDENCE_FILENAMES) or len(entries) != len(
        CANONICAL_EVIDENCE_FILENAMES
    ):
        raise CanonicalEvidenceValidationError(
            "canonical directory must contain exactly the six contract files"
        )
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise CanonicalEvidenceValidationError(
            "canonical contract entries must be regular files"
        )

    texts: dict[str, str] = {}
    try:
        for filename in CANONICAL_EVIDENCE_FILENAMES:
            texts[filename] = (directory / filename).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise CanonicalEvidenceValidationError(
            "canonical evidence files could not be read as UTF-8"
        ) from None
    _require_payloads_sanitized(texts)

    manifest = _manifest_from_json(texts["manifest.json"])
    if manifest.run_id != directory.name:
        raise CanonicalEvidenceValidationError(
            "manifest run identity does not match its immutable directory"
        )
    invocations = _invocations_from_jsonl(texts["invocations.jsonl"])
    batches = _batches_from_jsonl(texts["batches.jsonl"])
    ownership = _ownership_from_json(texts["ownership.json"])
    published_invocation_aggregates = _invocation_aggregates_from_json(
        texts["invocation_aggregates.json"]
    )
    published_batch_rate_aggregates = _batch_rate_aggregates_from_json(
        texts["batch_rate_aggregates.json"]
    )

    schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    fresh_validation = validate_recorded_run(
        schedule=schedule,
        invocations=invocations,
        batches=batches,
        ownership=ownership,
    )
    reconstructed = RecordedExecutionResult(
        schedule=schedule,
        invocations=invocations,
        batches=batches,
        ownership=ownership,
        validation=fresh_validation,
    )
    recomputed_invocation_aggregates, recomputed_batch_rate_aggregates = (
        _validate_canonical_result(manifest=manifest, result=reconstructed)
    )
    if published_invocation_aggregates != recomputed_invocation_aggregates:
        raise CanonicalEvidenceValidationError(
            "published invocation aggregates differ from raw recomputation"
        )
    if published_batch_rate_aggregates != recomputed_batch_rate_aggregates:
        raise CanonicalEvidenceValidationError(
            "published batch-rate aggregates differ from raw recomputation"
        )

    return CanonicalEvidenceReadback(
        run_directory=directory,
        manifest=manifest,
        result=reconstructed,
        invocation_aggregates=published_invocation_aggregates,
        batch_rate_aggregates=published_batch_rate_aggregates,
    )


def _construct_payloads(
    *,
    manifest: CanonicalEvidenceManifest,
    result: RecordedExecutionResult,
) -> dict[str, str]:
    invocation_aggregates, batch_rate_aggregates = _validate_canonical_result(
        manifest=manifest,
        result=result,
    )
    invocations = tuple(
        sorted(result.invocations, key=lambda item: item.invocation_index)
    )
    batches = tuple(sorted(result.batches, key=lambda item: item.batch_record_index))
    ownership = tuple(
        sorted(
            result.ownership,
            key=lambda item: (
                item.worker_level,
                item.lane_index,
                item.connection_slot,
                item.thread_id,
            ),
        )
    )
    payloads = {
        "manifest.json": _json_document(_manifest_to_dict(manifest)),
        "invocations.jsonl": _jsonl_document(
            invocation_record_to_dict(record) for record in invocations
        ),
        "batches.jsonl": _jsonl_document(
            batch_record_to_dict(batch) for batch in batches
        ),
        "ownership.json": _json_document(
            [_ownership_to_dict(item) for item in ownership]
        ),
        "invocation_aggregates.json": _json_document(
            [_invocation_aggregate_to_dict(item) for item in invocation_aggregates]
        ),
        "batch_rate_aggregates.json": _json_document(
            [_batch_rate_aggregate_to_dict(item) for item in batch_rate_aggregates]
        ),
    }
    if tuple(payloads) != CANONICAL_EVIDENCE_FILENAMES:
        raise CanonicalEvidenceValidationError(
            "canonical payload construction did not produce exactly six files"
        )
    _require_payloads_sanitized(payloads)
    return payloads


def _validate_canonical_result(
    *,
    manifest: CanonicalEvidenceManifest,
    result: RecordedExecutionResult,
) -> tuple[tuple[InvocationAggregate, ...], tuple[BatchRateAggregate, ...]]:
    if not isinstance(manifest, CanonicalEvidenceManifest):
        raise CanonicalEvidenceValidationError("manifest is not the closed PR7 type")
    if not isinstance(result, RecordedExecutionResult):
        raise CanonicalEvidenceValidationError(
            "result is not the canonical runtime result type"
        )
    if not isinstance(result.validation, RunValidationResult):
        raise CanonicalEvidenceValidationError(
            "result validation is not the canonical runtime validation type"
        )
    if any(not isinstance(item, InvocationRecord) for item in result.invocations):
        raise CanonicalEvidenceValidationError(
            "canonical invocations must use the frozen runtime record type"
        )
    if any(not isinstance(item, BatchRecord) for item in result.batches):
        raise CanonicalEvidenceValidationError(
            "canonical batches must use the frozen runtime record type"
        )
    if any(not isinstance(item, LaneOwnershipRecord) for item in result.ownership):
        raise CanonicalEvidenceValidationError(
            "canonical ownership must use the frozen runtime record type"
        )
    exact_schedule = generate_fixed_schedule(seed=RECORDED_SCHEDULE_SEED)
    if result.schedule != exact_schedule:
        raise CanonicalEvidenceValidationError("result schedule is not exact seed-73")
    if (
        result.validation.status is not EvidenceStatus.VALID
        or result.validation.issues
    ):
        raise CanonicalEvidenceValidationError("runtime result is not VALID")
    if len(result.invocations) != CANONICAL_EXPECTED_INVOCATION_COUNT:
        raise CanonicalEvidenceValidationError(
            "canonical run requires exactly 1800 invocations"
        )
    if len(result.batches) != CANONICAL_EXPECTED_BATCH_COUNT:
        raise CanonicalEvidenceValidationError(
            "canonical run requires exactly 480 batches"
        )
    if len(result.ownership) != CANONICAL_EXPECTED_OWNERSHIP_COUNT:
        raise CanonicalEvidenceValidationError(
            "canonical run requires exactly 15 ownership records"
        )
    if any(record.run_id != manifest.run_id for record in result.invocations):
        raise CanonicalEvidenceValidationError("invocation run identity mismatch")
    if any(batch.run_id != manifest.run_id for batch in result.batches):
        raise CanonicalEvidenceValidationError("batch run identity mismatch")
    if any(record.exception_type is not None for record in result.invocations):
        raise CanonicalEvidenceValidationError(
            "canonical publication requires zero unexpected exceptions"
        )
    for record in result.invocations:
        if tuple(phase.name for phase in record.phases or ()) != PR3_PHASE_NAMES:
            raise CanonicalEvidenceValidationError(
                "invocation phases are not in the frozen thirteen-phase order"
            )
        try:
            classified = classify_cohort(
                producer_outcome=record.producer_outcome or "",
                rejection_stage=record.rejection_stage,
                stream_admission_verdict=record.stream_admission_verdict,
                append_admission_verdict=record.append_admission_verdict,
            )
        except Exception:
            raise CanonicalEvidenceValidationError(
                "invocation does not retain an exact supported cohort"
            ) from None
        if classified is not record.cohort:
            raise CanonicalEvidenceValidationError(
                "invocation cohort differs from existing runtime classification"
            )

    fresh = validate_recorded_run(
        schedule=result.schedule,
        invocations=result.invocations,
        batches=result.batches,
        ownership=result.ownership,
    )
    if fresh.status is not EvidenceStatus.VALID or fresh.issues:
        raise CanonicalEvidenceValidationError(
            "fresh canonical runtime validation is not VALID"
        )
    try:
        invocation_aggregates = aggregate_invocations(result.invocations)
        batch_rate_aggregates = aggregate_batch_rates(result.batches)
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "canonical aggregate generation failed"
        ) from None
    if len(batch_rate_aggregates) != CANONICAL_EXPECTED_RATE_GROUP_COUNT:
        raise CanonicalEvidenceValidationError(
            "canonical evidence requires exactly 16 batch-rate groups"
        )
    if any(
        item.accepted_completion_rate_per_second.count
        != RECORDED_BATCHES_PER_CELL
        or item.all_completion_rate_per_second.count
        != RECORDED_BATCHES_PER_CELL
        for item in batch_rate_aggregates
    ):
        raise CanonicalEvidenceValidationError(
            "every batch-rate group requires exactly 30 observations"
        )
    if any(item.run_id != manifest.run_id for item in invocation_aggregates):
        raise CanonicalEvidenceValidationError(
            "invocation aggregate run identity mismatch"
        )
    if any(item.run_id != manifest.run_id for item in batch_rate_aggregates):
        raise CanonicalEvidenceValidationError(
            "batch-rate aggregate run identity mismatch"
        )
    return invocation_aggregates, batch_rate_aggregates


def _manifest_to_dict(manifest: CanonicalEvidenceManifest) -> dict[str, Any]:
    return {
        "schema_name": manifest.schema_name,
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "source_commit": manifest.source_commit,
        "source_tree_clean_before_run": manifest.source_tree_clean_before_run,
        "schedule_identity": manifest.schedule_identity,
        "recorded_schedule_seed": manifest.recorded_schedule_seed,
        "retained_worker_levels": list(manifest.retained_worker_levels),
        "exact_cell_count": manifest.exact_cell_count,
        "warmup_batches_per_exact_cell": manifest.warmup_batches_per_exact_cell,
        "recorded_batches_per_exact_cell": manifest.recorded_batches_per_exact_cell,
        "expected_recorded_batch_count": manifest.expected_recorded_batch_count,
        "expected_recorded_invocation_count": (
            manifest.expected_recorded_invocation_count
        ),
        "expected_ownership_count": manifest.expected_ownership_count,
        "clock_identity": manifest.clock_identity,
        "postgresql_server_version": manifest.postgresql_server_version,
        "transaction_isolation": manifest.transaction_isolation,
        "autocommit": manifest.autocommit,
        "topology_label": manifest.topology_label,
        "validation_status": manifest.validation_status,
        "smoke_source_commit": manifest.smoke_source_commit,
        "smoke_run_id": manifest.smoke_run_id,
        "smoke_release_skew_review": manifest.smoke_release_skew_review,
        "publication_rule": manifest.publication_rule,
    }


def _manifest_from_json(text: str) -> CanonicalEvidenceManifest:
    value = _parse_json(text, "manifest")
    data = _require_closed_object(value, _MANIFEST_FIELDS, "manifest")
    try:
        levels = data["retained_worker_levels"]
        if not isinstance(levels, list):
            raise TypeError
        return CanonicalEvidenceManifest(
            **{
                **data,
                "retained_worker_levels": tuple(levels),
            }
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "manifest values do not satisfy the closed contract"
        ) from None


def _invocations_from_jsonl(text: str) -> tuple[InvocationRecord, ...]:
    values = _parse_jsonl(text, "invocations")
    if len(values) != CANONICAL_EXPECTED_INVOCATION_COUNT:
        raise CanonicalEvidenceValidationError(
            "invocations.jsonl must contain exactly 1800 lines"
        )
    records = tuple(_invocation_from_dict(value) for value in values)
    if tuple(item.invocation_index for item in records) != tuple(
        range(CANONICAL_EXPECTED_INVOCATION_COUNT)
    ):
        raise CanonicalEvidenceValidationError(
            "invocation JSONL order must match deterministic invocation indexes"
        )
    return records


def _invocation_from_dict(value: Any) -> InvocationRecord:
    data = _require_closed_object(value, _INVOCATION_FIELDS, "invocation")
    try:
        phases_value = data["phases"]
        phases = None
        if phases_value is not None:
            if not isinstance(phases_value, list):
                raise TypeError
            phases = tuple(_phase_from_dict(item) for item in phases_value)
        rejection = data["rejection_stage"]
        cohort = data["cohort"]
        return InvocationRecord(
            **{
                **data,
                "workload_family": WorkloadFamily(data["workload_family"]),
                "composition": Composition(data["composition"]),
                "rejection_stage": (
                    None if rejection is None else RejectionStage(rejection)
                ),
                "cohort": None if cohort is None else Cohort(cohort),
                "phases": phases,
            }
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "invocation values do not satisfy the frozen schema"
        ) from None


def _phase_from_dict(value: Any) -> PhaseRecord:
    data = _require_closed_object(value, _PHASE_FIELDS, "phase")
    try:
        return PhaseRecord(
            name=data["name"],
            state=PhaseState(data["state"]),
            elapsed_ns=data["elapsed_ns"],
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "phase values do not satisfy the frozen schema"
        ) from None


def _batches_from_jsonl(text: str) -> tuple[BatchRecord, ...]:
    values = _parse_jsonl(text, "batches")
    if len(values) != CANONICAL_EXPECTED_BATCH_COUNT:
        raise CanonicalEvidenceValidationError(
            "batches.jsonl must contain exactly 480 lines"
        )
    records = tuple(_batch_from_dict(value) for value in values)
    if tuple(item.batch_record_index for item in records) != tuple(
        range(CANONICAL_EXPECTED_BATCH_COUNT)
    ):
        raise CanonicalEvidenceValidationError(
            "batch JSONL order must match deterministic batch indexes"
        )
    return records


def _batch_from_dict(value: Any) -> BatchRecord:
    data = _require_closed_object(value, _BATCH_FIELDS, "batch")
    try:
        counts = data["typed_outcome_counts"]
        if not isinstance(counts, list):
            raise TypeError
        return BatchRecord(
            **{
                **data,
                "workload_family": WorkloadFamily(data["workload_family"]),
                "composition": Composition(data["composition"]),
                "typed_outcome_counts": tuple(
                    _typed_outcome_from_dict(item) for item in counts
                ),
            }
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "batch values do not satisfy the frozen schema"
        ) from None


def _typed_outcome_from_dict(value: Any) -> TypedOutcomeCount:
    data = _require_closed_object(value, _TYPED_OUTCOME_FIELDS, "typed outcome")
    try:
        return TypedOutcomeCount(outcome=data["outcome"], count=data["count"])
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "typed outcome values do not satisfy the frozen schema"
        ) from None


def _ownership_to_dict(record: LaneOwnershipRecord) -> dict[str, int]:
    return {
        "worker_level": record.worker_level,
        "lane_index": record.lane_index,
        "connection_slot": record.connection_slot,
        "thread_id": record.thread_id,
    }


def _ownership_from_json(text: str) -> tuple[LaneOwnershipRecord, ...]:
    value = _parse_json(text, "ownership")
    if not isinstance(value, list) or len(value) != CANONICAL_EXPECTED_OWNERSHIP_COUNT:
        raise CanonicalEvidenceValidationError(
            "ownership.json must contain exactly 15 entries"
        )
    try:
        records = tuple(
            LaneOwnershipRecord(
                **_require_closed_object(item, _OWNERSHIP_FIELDS, "ownership")
            )
            for item in value
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "ownership values do not satisfy the frozen schema"
        ) from None
    expected_order = tuple(
        sorted(
            records,
            key=lambda item: (
                item.worker_level,
                item.lane_index,
                item.connection_slot,
                item.thread_id,
            ),
        )
    )
    if records != expected_order:
        raise CanonicalEvidenceValidationError(
            "ownership entries are not in deterministic order"
        )
    return records


def _statistics_to_dict(statistics: DescriptiveStatistics) -> dict[str, Any]:
    return {
        "count": statistics.count,
        "minimum": statistics.minimum,
        "maximum": statistics.maximum,
        "mean": statistics.mean,
        "median": statistics.median,
    }


def _statistics_from_dict(value: Any) -> DescriptiveStatistics:
    data = _require_closed_object(value, _STATISTICS_FIELDS, "statistics")
    count = data["count"]
    numbers = tuple(data[name] for name in _STATISTICS_FIELDS[1:])
    if type(count) is not int or count <= 0 or any(
        type(item) not in (int, float) or not math.isfinite(item) for item in numbers
    ):
        raise CanonicalEvidenceValidationError(
            "descriptive statistics contain invalid values"
        )
    minimum, maximum, mean, median = (float(item) for item in numbers)
    if minimum > maximum or not (
        minimum <= mean <= maximum and minimum <= median <= maximum
    ):
        raise CanonicalEvidenceValidationError(
            "descriptive statistics violate min/max bounds"
        )
    return DescriptiveStatistics(
        count=count,
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        median=median,
    )


def _invocation_aggregate_to_dict(item: InvocationAggregate) -> dict[str, Any]:
    return {
        "run_id": item.run_id,
        "worker_level": item.worker_level,
        "workload_family": item.workload_family.value,
        "composition": item.composition.value,
        "cohort": item.cohort.value,
        "external_elapsed_ns": _statistics_to_dict(item.external_elapsed_ns),
        "phases": [
            {
                "phase_name": phase.phase_name,
                "statistics_ns": _statistics_to_dict(phase.statistics_ns),
            }
            for phase in item.phases
        ],
    }


def _invocation_aggregates_from_json(text: str) -> tuple[InvocationAggregate, ...]:
    value = _parse_json(text, "invocation aggregates")
    if not isinstance(value, list):
        raise CanonicalEvidenceValidationError(
            "invocation aggregates must be one closed array"
        )
    return tuple(_invocation_aggregate_from_dict(item) for item in value)


def _invocation_aggregate_from_dict(value: Any) -> InvocationAggregate:
    data = _require_closed_object(
        value,
        _INVOCATION_AGGREGATE_FIELDS,
        "invocation aggregate",
    )
    phases = data["phases"]
    if not isinstance(phases, list):
        raise CanonicalEvidenceValidationError(
            "invocation aggregate phases must be an array"
        )
    _require_aggregate_identity(data)
    try:
        aggregate = InvocationAggregate(
            run_id=data["run_id"],
            worker_level=data["worker_level"],
            workload_family=WorkloadFamily(data["workload_family"]),
            composition=Composition(data["composition"]),
            cohort=Cohort(data["cohort"]),
            external_elapsed_ns=_statistics_from_dict(
                data["external_elapsed_ns"]
            ),
            phases=tuple(_phase_aggregate_from_dict(item) for item in phases),
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "invocation aggregate values do not satisfy the closed schema"
        ) from None
    phase_names = tuple(item.phase_name for item in aggregate.phases)
    expected_phase_names = tuple(
        name for name in PR3_PHASE_NAMES if name in set(phase_names)
    )
    if phase_names != expected_phase_names:
        raise CanonicalEvidenceValidationError(
            "invocation aggregate phases are not unique PR3 ordered phases"
        )
    return aggregate


def _phase_aggregate_from_dict(value: Any) -> PhaseAggregate:
    data = _require_closed_object(
        value,
        _PHASE_AGGREGATE_FIELDS,
        "phase aggregate",
    )
    if data["phase_name"] not in PR3_PHASE_NAMES:
        raise CanonicalEvidenceValidationError("aggregate contains an unknown phase")
    return PhaseAggregate(
        phase_name=data["phase_name"],
        statistics_ns=_statistics_from_dict(data["statistics_ns"]),
    )


def _batch_rate_aggregate_to_dict(item: BatchRateAggregate) -> dict[str, Any]:
    return {
        "run_id": item.run_id,
        "worker_level": item.worker_level,
        "workload_family": item.workload_family.value,
        "composition": item.composition.value,
        "accepted_completion_rate_per_second": _statistics_to_dict(
            item.accepted_completion_rate_per_second
        ),
        "all_completion_rate_per_second": _statistics_to_dict(
            item.all_completion_rate_per_second
        ),
    }


def _batch_rate_aggregates_from_json(text: str) -> tuple[BatchRateAggregate, ...]:
    value = _parse_json(text, "batch-rate aggregates")
    if not isinstance(value, list) or len(value) != CANONICAL_EXPECTED_RATE_GROUP_COUNT:
        raise CanonicalEvidenceValidationError(
            "batch-rate aggregates must contain exactly 16 groups"
        )
    records = tuple(_batch_rate_aggregate_from_dict(item) for item in value)
    if any(
        item.accepted_completion_rate_per_second.count
        != RECORDED_BATCHES_PER_CELL
        or item.all_completion_rate_per_second.count
        != RECORDED_BATCHES_PER_CELL
        for item in records
    ):
        raise CanonicalEvidenceValidationError(
            "each batch-rate group must contain exactly 30 observations"
        )
    return records


def _batch_rate_aggregate_from_dict(value: Any) -> BatchRateAggregate:
    data = _require_closed_object(
        value,
        _BATCH_RATE_AGGREGATE_FIELDS,
        "batch-rate aggregate",
    )
    _require_aggregate_identity(data)
    try:
        return BatchRateAggregate(
            run_id=data["run_id"],
            worker_level=data["worker_level"],
            workload_family=WorkloadFamily(data["workload_family"]),
            composition=Composition(data["composition"]),
            accepted_completion_rate_per_second=_statistics_from_dict(
                data["accepted_completion_rate_per_second"]
            ),
            all_completion_rate_per_second=_statistics_from_dict(
                data["all_completion_rate_per_second"]
            ),
        )
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "batch-rate aggregate values do not satisfy the closed schema"
        ) from None


def _require_aggregate_identity(data: Mapping[str, Any]) -> None:
    if not _is_safe_run_id(data.get("run_id")):
        raise CanonicalEvidenceValidationError(
            "aggregate run identity is not a safe experiment-local token"
        )
    worker_level = data.get("worker_level")
    if type(worker_level) is not int or worker_level not in RETAINED_WORKER_LEVELS:
        raise CanonicalEvidenceValidationError(
            "aggregate worker level is not one exact retained integer"
        )


def _json_document(value: Any) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
    except (TypeError, ValueError):
        raise CanonicalEvidenceValidationError(
            "canonical payload is not deterministic JSON"
        ) from None


def _jsonl_document(values: Iterable[Any]) -> str:
    return "".join(_json_document(value) for value in values)


def _parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise CanonicalEvidenceValidationError(
            f"{label} is not valid JSON"
        ) from None


def _parse_jsonl(text: str, label: str) -> tuple[Any, ...]:
    lines = text.splitlines()
    if not lines or any(not line for line in lines):
        raise CanonicalEvidenceValidationError(f"{label} JSONL is empty or sparse")
    return tuple(_parse_json(line, label) for line in lines)


def _require_closed_object(
    value: Any,
    fields: Sequence[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields) or len(value) != len(
        fields
    ):
        raise CanonicalEvidenceValidationError(
            f"{label} does not match its exact closed field set"
        )
    return value


def _require_payloads_sanitized(payloads: Mapping[str, str]) -> None:
    combined = "\n".join(payloads.values()).casefold()
    if any(marker in combined for marker in _FORBIDDEN_VALUE_MARKERS):
        raise CanonicalEvidenceValidationError(
            "canonical payload contains a forbidden secret or endpoint marker"
        )


def _require_sanitized_fact(name: str, value: Any) -> None:
    if type(value) is not str or _SANITIZED_FACT.fullmatch(value) is None:
        raise ValueError(f"{name} must be a short sanitized identity")
    lowered = value.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_VALUE_MARKERS):
        raise ValueError(f"{name} contains a forbidden connection or secret marker")


def _require_safe_run_id(run_id: Any) -> None:
    if not _is_safe_run_id(run_id):
        raise ValueError("run_id must be one safe experiment-local token")
    lowered = run_id.casefold()
    if any(marker in lowered for marker in _FORBIDDEN_VALUE_MARKERS):
        raise ValueError("run_id contains a forbidden secret marker")


def _is_safe_run_id(run_id: Any) -> bool:
    return (
        type(run_id) is str
        and len(run_id) <= 128
        and _SAFE_RUN_ID.fullmatch(run_id) is not None
    )


def _absolute_path(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_repository_root(path: os.PathLike[str] | str) -> Path:
    root = _absolute_path(path)
    if root.is_symlink() or not root.is_dir():
        raise CanonicalEvidenceValidationError(
            "repository root must be an existing non-symlink directory"
        )
    parts = root.parts
    for index in range(len(parts) - len(_EVIDENCE_ANCESTRY) + 1):
        if tuple(parts[index : index + len(_EVIDENCE_ANCESTRY)]) == (
            _EVIDENCE_ANCESTRY
        ):
            raise CanonicalEvidenceValidationError(
                "an evidence namespace cannot be used as repository ancestry"
            )
    return root


def _prepare_canonical_root(evidence_root: Path) -> None:
    repository_root = evidence_root.parents[3]
    _require_no_symlink_chain(repository_root, evidence_root)
    try:
        evidence_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise CanonicalEvidencePublicationError(
            "canonical evidence namespace could not be created"
        ) from None
    _require_no_symlink_chain(repository_root, evidence_root)


def _require_no_symlink_chain(repository_root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(repository_root)
    except ValueError:
        raise CanonicalEvidenceValidationError(
            "canonical evidence path escaped the repository root"
        ) from None
    current = repository_root
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current) and (
            current.is_symlink() or not current.is_dir()
        ):
            raise CanonicalEvidenceValidationError(
                "canonical evidence ancestry must contain only real directories"
            )


def _write_payload_file(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _cleanup_staging_directory(path: Path) -> None:
    if not path.exists():
        return
    try:
        for filename in CANONICAL_EVIDENCE_FILENAMES:
            candidate = path / filename
            if candidate.is_symlink() or candidate.is_file():
                candidate.unlink()
        path.rmdir()
    except OSError:
        raise CanonicalEvidencePublicationError(
            "writer could not clean its own hidden staging directory"
        ) from None
