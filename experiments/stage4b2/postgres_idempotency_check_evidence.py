"""Valid-only evidence persistence for post-PR6 Layer-2 characterization.

This experiment-owned module serializes the exact nine-cell primary-cost
model into a distinct supplemental namespace. It writes nothing unless the
fixed 270-sample schedule validates as ``VALID``. It never connects to
PostgreSQL, executes a sample, persists structural SQL tracing, or modifies
Layer-1 or canonical PR6 evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from experiments.stage4b2.postgres_idempotency_check_characterization import (
    ALL_CELLS,
    CellAggregate,
    DescriptiveStatistics,
    Layer2Context,
    Layer2Sample,
    Layer2Verdict,
    RECORDED_SAMPLES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    RunValidity,
    SCHEMA_VERSION,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)


EVIDENCE_SCHEMA_VERSION = 1
SUPPLEMENTAL_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-check-layer2"
)
LAYER1_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-lifecycle-layer1"
)
CANONICAL_PR6_EVIDENCE_NAMESPACE = "stage4b2-pr6-canonical-0bd2f51"
MANIFEST_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_check.layer2.manifest"
)
SAMPLES_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_check.layer2.samples"
)
AGGREGATES_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_check.layer2.aggregates"
)
FIXED_SCHEDULE_IDENTITY = (
    "P_U_T_X_MISS_REPLAY_CONFLICT_COUNTERBALANCED_30_EACH_V1"
)
FIXED_RECORDED_SAMPLE_COUNT = len(generate_recorded_schedule().samples)
TIMER_IDENTITY = "time.perf_counter_ns"
VALIDATION_STATUS = "VALID"
PUBLICATION_RULE = (
    "validate_run=VALID; clean source required; invalid writes nothing; "
    "no replacement, retry, or extension"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT = (
    PROJECT_ROOT / "experiments/stage4b2/evidence" / SUPPLEMENTAL_EVIDENCE_NAMESPACE
)

_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
_FORBIDDEN_SERVER_VERSION_FRAGMENTS = (
    "postgresql://",
    "postgres://",
    "host=",
    "port=",
    "dbname=",
    "database=",
    "user=",
    "username=",
    "password=",
    "@",
    "localhost",
)


class Layer2EvidenceError(RuntimeError):
    """Report Layer-2 evidence construction or publication failures."""


@dataclass(frozen=True)
class Layer2EvidenceManifest:
    """Retain only sanitized audit facts for one fixed recorded run."""

    schema_name: str
    schema_version: int
    run_id: str
    source_commit: str
    source_tree_clean_before_run: bool
    fixed_schedule_identity: str
    fixed_recorded_schedule_seed: int
    planned_sample_count: int
    samples_per_cell: int
    cells: tuple[str, ...]
    clock_identity: str
    postgresql_server_version: str | None
    validation_status: str
    structural_smoke_validated: bool
    publication_rule: str

    def __post_init__(self) -> None:
        if self.schema_name != MANIFEST_SCHEMA_NAME:
            raise ValueError("manifest schema_name is not supplemental Layer 2")
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("manifest schema_version is unsupported")
        _require_safe_run_id(self.run_id)
        if _FULL_COMMIT.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be one full lowercase Git identity")
        if type(self.source_tree_clean_before_run) is not bool:
            raise TypeError("source_tree_clean_before_run must be bool")
        if self.fixed_schedule_identity != FIXED_SCHEDULE_IDENTITY:
            raise ValueError("manifest fixed schedule identity changed")
        if self.fixed_recorded_schedule_seed != RECORDED_SCHEDULE_SEED:
            raise ValueError("manifest recorded schedule seed changed")
        if self.planned_sample_count != FIXED_RECORDED_SAMPLE_COUNT:
            raise ValueError("manifest planned sample count must be 270")
        if self.samples_per_cell != RECORDED_SAMPLES_PER_CELL:
            raise ValueError("manifest samples_per_cell must be 30")
        if self.cells != tuple(cell.identity for cell in ALL_CELLS):
            raise ValueError("manifest cells must be the exact nine Layer-2 cells")
        if self.clock_identity != TIMER_IDENTITY:
            raise ValueError("manifest clock identity changed")
        if self.validation_status != VALIDATION_STATUS:
            raise ValueError("manifest validation status must be VALID")
        if self.structural_smoke_validated is not True:
            raise ValueError("structural smoke must already be separately valid")
        if self.publication_rule != PUBLICATION_RULE:
            raise ValueError("manifest publication rule changed")
        _require_safe_server_version(self.postgresql_server_version)


@dataclass(frozen=True)
class EvidenceWriteResult:
    """Return exact paths only after complete atomic directory publication."""

    directory: Path
    manifest_path: Path
    samples_path: Path
    aggregates_path: Path


@dataclass(frozen=True)
class PublishedLayer2Evidence:
    """Return a fully parsed and recomputed Layer-2 evidence directory."""

    manifest: Layer2EvidenceManifest
    samples: tuple[Layer2Sample, ...]
    aggregates: tuple[CellAggregate, ...]


def build_manifest(
    *,
    run_id: str,
    source_commit: str,
    source_tree_clean_before_run: bool,
    postgresql_server_version: str | None,
    structural_smoke_validated: bool,
) -> Layer2EvidenceManifest:
    """Build the fixed manifest without reading environment or connection data."""

    return Layer2EvidenceManifest(
        schema_name=MANIFEST_SCHEMA_NAME,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        run_id=run_id,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        fixed_schedule_identity=FIXED_SCHEDULE_IDENTITY,
        fixed_recorded_schedule_seed=RECORDED_SCHEDULE_SEED,
        planned_sample_count=FIXED_RECORDED_SAMPLE_COUNT,
        samples_per_cell=RECORDED_SAMPLES_PER_CELL,
        cells=tuple(cell.identity for cell in ALL_CELLS),
        clock_identity=TIMER_IDENTITY,
        postgresql_server_version=postgresql_server_version,
        validation_status=VALIDATION_STATUS,
        structural_smoke_validated=structural_smoke_validated,
        publication_rule=PUBLICATION_RULE,
    )


def sample_to_dict(sample: Layer2Sample) -> dict[str, Any]:
    """Serialize every primary sample field without SQL structural tracing."""

    if sample.structural_sql_observation_identity is not None:
        raise Layer2EvidenceError("primary sample unexpectedly retained SQL tracing")
    return {
        "schema_name": SAMPLES_SCHEMA_NAME,
        "schema_version": sample.schema_version,
        "run_id": sample.run_id,
        "sample_index": sample.sample_index,
        "planned_context": sample.planned_context.value,
        "planned_verdict": sample.planned_verdict.value,
        "returned_verdict": (
            None if sample.returned_verdict is None else sample.returned_verdict.value
        ),
        "check_elapsed_ns": sample.check_elapsed_ns,
        "cleanup_elapsed_ns": sample.cleanup_elapsed_ns,
        "transaction_status_before_check": _optional_enum_value(
            sample.transaction_status_before_check
        ),
        "transaction_status_after_check": _optional_enum_value(
            sample.transaction_status_after_check
        ),
        "transaction_status_after_cleanup": _optional_enum_value(
            sample.transaction_status_after_cleanup
        ),
        "reuse_select_succeeded": sample.reuse_select_succeeded,
        "final_transaction_status": _optional_enum_value(
            sample.final_transaction_status
        ),
        "exception_type": sample.exception_type,
    }


def sample_from_dict(raw: Mapping[str, Any]) -> Layer2Sample:
    """Reconstruct one exact primary sample from its closed evidence schema."""

    _require_exact_keys(raw, _SAMPLE_KEYS, "sample")
    if raw["schema_name"] != SAMPLES_SCHEMA_NAME:
        raise ValueError("sample schema_name is not supplemental Layer 2")
    return Layer2Sample(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        sample_index=raw["sample_index"],
        planned_context=Layer2Context(raw["planned_context"]),
        planned_verdict=Layer2Verdict(raw["planned_verdict"]),
        returned_verdict=(
            None
            if raw["returned_verdict"] is None
            else Layer2Verdict(raw["returned_verdict"])
        ),
        check_elapsed_ns=raw["check_elapsed_ns"],
        cleanup_elapsed_ns=raw["cleanup_elapsed_ns"],
        transaction_status_before_check=_optional_status(
            raw["transaction_status_before_check"]
        ),
        transaction_status_after_check=_optional_status(
            raw["transaction_status_after_check"]
        ),
        transaction_status_after_cleanup=_optional_status(
            raw["transaction_status_after_cleanup"]
        ),
        reuse_select_succeeded=raw["reuse_select_succeeded"],
        final_transaction_status=_optional_status(
            raw["final_transaction_status"]
        ),
        exception_type=raw["exception_type"],
    )


def samples_to_jsonl(samples: Iterable[Layer2Sample]) -> str:
    """Serialize deterministic compact JSONL with one record per sample."""

    lines = [
        json.dumps(sample_to_dict(sample), sort_keys=True, separators=(",", ":"))
        for sample in samples
    ]
    return "" if not lines else "\n".join(lines) + "\n"


def samples_from_jsonl(payload: str) -> tuple[Layer2Sample, ...]:
    """Parse sample JSONL without accepting blank records."""

    if not payload:
        return ()
    lines = payload.splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("samples JSONL must not contain blank records")
    return tuple(sample_from_dict(json.loads(line)) for line in lines)


def manifest_to_dict(manifest: Layer2EvidenceManifest) -> dict[str, Any]:
    """Convert the closed sanitized manifest into a JSON-ready map."""

    return {
        "schema_name": manifest.schema_name,
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "source_commit": manifest.source_commit,
        "source_tree_clean_before_run": manifest.source_tree_clean_before_run,
        "fixed_schedule_identity": manifest.fixed_schedule_identity,
        "fixed_recorded_schedule_seed": manifest.fixed_recorded_schedule_seed,
        "planned_sample_count": manifest.planned_sample_count,
        "samples_per_cell": manifest.samples_per_cell,
        "cells": list(manifest.cells),
        "clock_identity": manifest.clock_identity,
        "postgresql_server_version": manifest.postgresql_server_version,
        "validation_status": manifest.validation_status,
        "structural_smoke_validated": manifest.structural_smoke_validated,
        "publication_rule": manifest.publication_rule,
    }


def manifest_to_json(manifest: Layer2EvidenceManifest) -> str:
    """Serialize one deterministic human-readable sanitized manifest."""

    return json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"


def manifest_from_dict(raw: Mapping[str, Any]) -> Layer2EvidenceManifest:
    """Parse only the exact supplemental Layer-2 manifest schema."""

    _require_exact_keys(raw, _MANIFEST_KEYS, "manifest")
    return Layer2EvidenceManifest(
        schema_name=raw["schema_name"],
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        source_commit=raw["source_commit"],
        source_tree_clean_before_run=raw["source_tree_clean_before_run"],
        fixed_schedule_identity=raw["fixed_schedule_identity"],
        fixed_recorded_schedule_seed=raw["fixed_recorded_schedule_seed"],
        planned_sample_count=raw["planned_sample_count"],
        samples_per_cell=raw["samples_per_cell"],
        cells=tuple(raw["cells"]),
        clock_identity=raw["clock_identity"],
        postgresql_server_version=raw["postgresql_server_version"],
        validation_status=raw["validation_status"],
        structural_smoke_validated=raw["structural_smoke_validated"],
        publication_rule=raw["publication_rule"],
    )


def aggregates_to_dict(
    *,
    run_id: str,
    aggregates: Sequence[CellAggregate],
) -> dict[str, Any]:
    """Serialize exactly nine independent cell aggregates without pooling."""

    _require_safe_run_id(run_id)
    if tuple(aggregate.cell for aggregate in aggregates) != ALL_CELLS:
        raise ValueError("aggregates must contain the exact nine Layer-2 cells")
    groups = []
    for aggregate in aggregates:
        if (
            aggregate.check_elapsed_ns.count != RECORDED_SAMPLES_PER_CELL
            or aggregate.cleanup_elapsed_ns.count != RECORDED_SAMPLES_PER_CELL
        ):
            raise ValueError("each aggregate field must contain 30 samples")
        groups.append(
            {
                "context": aggregate.cell.context.value,
                "verdict": aggregate.cell.verdict.value,
                "check_elapsed_ns": _statistics_to_dict(
                    aggregate.check_elapsed_ns
                ),
                "cleanup_elapsed_ns": _statistics_to_dict(
                    aggregate.cleanup_elapsed_ns
                ),
            }
        )
    return {
        "schema_name": AGGREGATES_SCHEMA_NAME,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "groups": groups,
    }


def aggregates_to_json(
    *,
    run_id: str,
    aggregates: Sequence[CellAggregate],
) -> str:
    """Serialize exact-cell aggregates deterministically."""

    return (
        json.dumps(
            aggregates_to_dict(run_id=run_id, aggregates=aggregates),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def aggregates_from_dict(raw: Mapping[str, Any]) -> tuple[CellAggregate, ...]:
    """Parse and validate the exact nine-group aggregate envelope."""

    _require_exact_keys(raw, _AGGREGATE_ENVELOPE_KEYS, "aggregate envelope")
    if raw["schema_name"] != AGGREGATES_SCHEMA_NAME:
        raise ValueError("aggregate schema_name is not supplemental Layer 2")
    if raw["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("aggregate schema_version is unsupported")
    _require_safe_run_id(raw["run_id"])
    groups = raw["groups"]
    if not isinstance(groups, list) or len(groups) != len(ALL_CELLS):
        raise ValueError("aggregate groups must contain exactly nine entries")
    aggregates = tuple(
        CellAggregate(
            cell=ALL_CELLS[index],
            check_elapsed_ns=_statistics_from_dict(
                raw_group["check_elapsed_ns"]
            ),
            cleanup_elapsed_ns=_statistics_from_dict(
                raw_group["cleanup_elapsed_ns"]
            ),
        )
        for index, raw_group in enumerate(groups)
        if _validated_group_identity(raw_group, ALL_CELLS[index])
    )
    if tuple(aggregate.cell for aggregate in aggregates) != ALL_CELLS:
        raise ValueError("aggregate cell order must match the exact nine cells")
    for aggregate in aggregates:
        if (
            aggregate.check_elapsed_ns.count != RECORDED_SAMPLES_PER_CELL
            or aggregate.cleanup_elapsed_ns.count != RECORDED_SAMPLES_PER_CELL
        ):
            raise ValueError("parsed aggregate fields must contain 30 samples")
    return aggregates


def write_evidence_directory(
    *,
    output_root: Path,
    manifest: Layer2EvidenceManifest,
    samples: Sequence[Layer2Sample],
) -> EvidenceWriteResult | None:
    """Atomically publish three artifacts only for one valid clean fixed run.

    Invalid samples or a dirty pre-run source return ``None`` before any
    namespace is created. Existing run directories are never overwritten.
    Every file is completed in a hidden same-parent staging directory before
    one final atomic directory rename.
    """

    schedule = generate_recorded_schedule()
    validation = validate_run(schedule, samples)
    if (
        validation.validity is not RunValidity.VALID
        or not manifest.source_tree_clean_before_run
    ):
        return None
    _require_supplemental_output_root(output_root)
    if any(sample.run_id != manifest.run_id for sample in samples):
        raise Layer2EvidenceError("sample run_id differs from manifest run_id")

    aggregates = aggregate_recorded_samples(samples)
    if tuple(aggregate.cell for aggregate in aggregates) != ALL_CELLS:
        raise Layer2EvidenceError("aggregation did not retain exactly nine cells")
    payloads = {
        "manifest.json": manifest_to_json(manifest),
        "samples.jsonl": samples_to_jsonl(samples),
        "aggregates.json": aggregates_to_json(
            run_id=manifest.run_id,
            aggregates=aggregates,
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    final_directory = output_root / manifest.run_id
    if final_directory.exists():
        raise FileExistsError("refusing to overwrite an existing evidence run")
    staging_directory = Path(
        tempfile.mkdtemp(
            prefix=f".{manifest.run_id}.staging-",
            dir=output_root,
        )
    )
    for filename, payload in payloads.items():
        _write_complete_file(staging_directory / filename, payload)
    _fsync_directory(staging_directory)
    os.replace(staging_directory, final_directory)
    _fsync_directory(output_root)
    return EvidenceWriteResult(
        directory=final_directory,
        manifest_path=final_directory / "manifest.json",
        samples_path=final_directory / "samples.jsonl",
        aggregates_path=final_directory / "aggregates.json",
    )


def read_evidence_directory(directory: Path) -> PublishedLayer2Evidence:
    """Parse, validate, and recompute a complete three-file directory."""

    entries = {path.name for path in directory.iterdir()}
    if entries != {"manifest.json", "samples.jsonl", "aggregates.json"}:
        raise Layer2EvidenceError("evidence directory must contain three files")
    manifest = manifest_from_dict(
        json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    )
    samples = samples_from_jsonl(
        (directory / "samples.jsonl").read_text(encoding="utf-8")
    )
    raw_aggregates = json.loads(
        (directory / "aggregates.json").read_text(encoding="utf-8")
    )
    if raw_aggregates.get("run_id") != manifest.run_id:
        raise Layer2EvidenceError("aggregate run_id differs from manifest")
    if any(sample.run_id != manifest.run_id for sample in samples):
        raise Layer2EvidenceError("sample run_id differs from manifest")
    schedule = generate_recorded_schedule()
    if validate_run(schedule, samples).validity is not RunValidity.VALID:
        raise Layer2EvidenceError("published samples do not validate")
    aggregates = aggregates_from_dict(raw_aggregates)
    if aggregates != aggregate_recorded_samples(samples):
        raise Layer2EvidenceError("published aggregates differ from samples")
    return PublishedLayer2Evidence(manifest, samples, aggregates)


def _statistics_to_dict(result: DescriptiveStatistics) -> dict[str, Any]:
    return {
        "count": result.count,
        "min_ns": result.minimum_ns,
        "mean_ns": result.mean_ns,
        "median_ns": result.median_ns,
        "max_ns": result.maximum_ns,
    }


def _statistics_from_dict(raw: Mapping[str, Any]) -> DescriptiveStatistics:
    _require_exact_keys(raw, _STATISTICS_KEYS, "statistics")
    return DescriptiveStatistics(
        count=raw["count"],
        minimum_ns=raw["min_ns"],
        mean_ns=raw["mean_ns"],
        median_ns=raw["median_ns"],
        maximum_ns=raw["max_ns"],
    )


def _validated_group_identity(raw: Any, expected: Any) -> bool:
    if not isinstance(raw, Mapping):
        raise ValueError("aggregate group must be an object")
    _require_exact_keys(raw, _AGGREGATE_GROUP_KEYS, "aggregate group")
    if (
        raw["context"] != expected.context.value
        or raw["verdict"] != expected.verdict.value
    ):
        raise ValueError("aggregate group identity or order changed")
    return True


def _optional_enum_value(value: Any) -> str | None:
    return None if value is None else value.value


def _optional_status(value: Any) -> TransactionStatusIdentity | None:
    return None if value is None else TransactionStatusIdentity(value)


def _require_safe_run_id(run_id: str) -> None:
    if (
        not isinstance(run_id, str)
        or run_id in {".", ".."}
        or _SAFE_RUN_ID.fullmatch(run_id) is None
    ):
        raise ValueError("run_id must be one path-safe identifier")


def _require_safe_server_version(value: str | None) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("PostgreSQL server version must be a short string or null")
    lowered = value.lower()
    if (
        "\n" in value
        or "\r" in value
        or any(fragment in lowered for fragment in _FORBIDDEN_SERVER_VERSION_FRAGMENTS)
    ):
        raise ValueError("PostgreSQL server version contains connection data")


def _require_supplemental_output_root(output_root: Path) -> None:
    if not isinstance(output_root, Path):
        raise TypeError("output_root must be pathlib.Path")
    if output_root.name != SUPPLEMENTAL_EVIDENCE_NAMESPACE:
        raise Layer2EvidenceError("output_root is not the Layer-2 namespace")
    protected = {
        LAYER1_EVIDENCE_NAMESPACE,
        CANONICAL_PR6_EVIDENCE_NAMESPACE,
    }
    if protected & set(output_root.resolve(strict=False).parts):
        raise Layer2EvidenceError("refusing protected evidence namespace")


def _require_exact_keys(
    raw: Mapping[str, Any],
    expected: frozenset[str],
    label: str,
) -> None:
    if set(raw) != expected:
        raise ValueError(f"{label} keys differ from the closed evidence schema")


def _write_complete_file(path: Path, payload: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


_MANIFEST_KEYS = frozenset(
    {
        "schema_name",
        "schema_version",
        "run_id",
        "source_commit",
        "source_tree_clean_before_run",
        "fixed_schedule_identity",
        "fixed_recorded_schedule_seed",
        "planned_sample_count",
        "samples_per_cell",
        "cells",
        "clock_identity",
        "postgresql_server_version",
        "validation_status",
        "structural_smoke_validated",
        "publication_rule",
    }
)
_SAMPLE_KEYS = frozenset(
    {
        "schema_name",
        "schema_version",
        "run_id",
        "sample_index",
        "planned_context",
        "planned_verdict",
        "returned_verdict",
        "check_elapsed_ns",
        "cleanup_elapsed_ns",
        "transaction_status_before_check",
        "transaction_status_after_check",
        "transaction_status_after_cleanup",
        "reuse_select_succeeded",
        "final_transaction_status",
        "exception_type",
    }
)
_STATISTICS_KEYS = frozenset(
    {"count", "min_ns", "mean_ns", "median_ns", "max_ns"}
)
_AGGREGATE_ENVELOPE_KEYS = frozenset(
    {"schema_name", "schema_version", "run_id", "groups"}
)
_AGGREGATE_GROUP_KEYS = frozenset(
    {"context", "verdict", "check_elapsed_ns", "cleanup_elapsed_ns"}
)
