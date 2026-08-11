"""Valid-only durable evidence for post-PR6 Layer-3 controls.

This experiment-owned module serializes the closed two-control model, verifies
one complete valid runtime result, atomically publishes exactly three files in
the Layer-3 namespace, and strictly reads them back with fresh validation and
aggregate recomputation. It never connects to PostgreSQL, executes a control,
interprets results, exposes a CLI, or modifies another evidence namespace.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from experiments.stage4b2.postgres_idempotency_read_lifecycle_characterization import (
    ALL_CONTROLS,
    RECORDED_ROUNDS,
    ControlAIdleRollbackAggregate,
    ControlAIdleRollbackSample,
    ControlBPreliminaryReadLifecycleAggregate,
    ControlBPreliminaryReadLifecycleSample,
    DescriptiveStatistics,
    IdempotencyVerdictIdentity,
    Layer3Aggregate,
    Layer3Control,
    Layer3Sample,
    RunValidity,
    TransactionStatusIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    schedule_control_counts,
    validate_run,
)
from experiments.stage4b2.postgres_idempotency_read_lifecycle_runtime import (
    Layer3RuntimeResult,
)


EVIDENCE_SCHEMA_VERSION = 1
SUPPLEMENTAL_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-read-lifecycle-layer3"
)
LAYER1_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-lifecycle-layer1"
)
LAYER2_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-check-layer2"
)
CANONICAL_PR6_EVIDENCE_NAMESPACE = "stage4b2-pr6-canonical-0bd2f51"
MANIFEST_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_read_lifecycle.layer3.manifest"
)
AGGREGATES_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_read_lifecycle.layer3.aggregates"
)
FIXED_SCHEDULE_IDENTITY = "CONTROL_A_THEN_CONTROL_B_30_ROUNDS_V1"
SAMPLES_PER_CONTROL = RECORDED_ROUNDS
TOTAL_PLANNED_SAMPLES = len(generate_recorded_schedule().samples)
CLOCK_IDENTITY = "time.perf_counter_ns"
VALIDATION_STATUS = "VALID"
PUBLICATION_RULE = (
    "validate_run=VALID; clean source required; invalid writes nothing; "
    "no retry, replacement, extension, or overwrite"
)
EVIDENCE_FILENAMES = frozenset(
    {"manifest.json", "samples.jsonl", "aggregates.json"}
)

PROJECT_ROOT = Path(__file__).parents[2]
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
    "token=",
    "secret=",
    "api_key=",
    "@",
    "localhost",
)


class Layer3EvidenceError(RuntimeError):
    """Report closed-schema or publication failure without repairing evidence.

    The error does not authorize retry, overwrite, live execution, or a result
    interpretation.
    """


@dataclass(frozen=True)
class Layer3EvidenceManifest:
    """Retain only authorized sanitized audit facts for one Layer-3 run.

    Construction enforces the closed manifest contract. A clean-source value
    of ``False`` may represent a rejected candidate but can never publish.
    The manifest contains no endpoint, credential, or execution policy.
    """

    schema_name: str
    schema_version: int
    run_id: str
    source_commit: str
    source_tree_clean_before_run: bool
    fixed_schedule_identity: str
    recorded_rounds: int
    samples_per_control: int
    total_planned_samples: int
    controls: tuple[str, ...]
    clock_identity: str
    postgresql_server_version: str
    validation_status: str
    publication_rule: str

    def __post_init__(self) -> None:
        if self.schema_name != MANIFEST_SCHEMA_NAME:
            raise ValueError("manifest schema_name is not supplemental Layer 3")
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("manifest schema_version is unsupported")
        _require_safe_run_id(self.run_id)
        if _FULL_COMMIT.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be one full lowercase Git identity")
        if type(self.source_tree_clean_before_run) is not bool:
            raise TypeError("source_tree_clean_before_run must be bool")
        if self.fixed_schedule_identity != FIXED_SCHEDULE_IDENTITY:
            raise ValueError("manifest fixed schedule identity changed")
        if self.recorded_rounds != RECORDED_ROUNDS:
            raise ValueError("manifest recorded_rounds must be 30")
        if self.samples_per_control != SAMPLES_PER_CONTROL:
            raise ValueError("manifest samples_per_control must be 30")
        if self.total_planned_samples != TOTAL_PLANNED_SAMPLES:
            raise ValueError("manifest total_planned_samples must be 60")
        if self.controls != tuple(control.value for control in ALL_CONTROLS):
            raise ValueError("manifest controls must be the exact Layer-3 controls")
        if self.clock_identity != CLOCK_IDENTITY:
            raise ValueError("manifest clock identity changed")
        _require_safe_server_version(self.postgresql_server_version)
        if self.validation_status != VALIDATION_STATUS:
            raise ValueError("manifest validation_status must be VALID")
        if self.publication_rule != PUBLICATION_RULE:
            raise ValueError("manifest publication rule changed")


@dataclass(frozen=True)
class EvidenceWriteResult:
    """Return exact paths only after complete atomic Layer-3 publication.

    The result is not a completion marker and carries no interpretation or
    authority to overwrite the immutable run directory.
    """

    directory: Path
    manifest_path: Path
    samples_path: Path
    aggregates_path: Path


@dataclass(frozen=True)
class PublishedLayer3Evidence:
    """Return one strictly parsed, revalidated, and recomputed evidence run.

    Reading is non-mutating and does not repair malformed or inconsistent
    artifacts.
    """

    manifest: Layer3EvidenceManifest
    samples: tuple[Layer3Sample, ...]
    aggregates: tuple[Layer3Aggregate, Layer3Aggregate]


def build_manifest(
    *,
    run_id: str,
    source_commit: str,
    source_tree_clean_before_run: bool,
    postgresql_server_version: str,
) -> Layer3EvidenceManifest:
    """Build the closed manifest without reading environment or connection data.

    The returned manifest is only a candidate; publication separately requires
    a clean source and a freshly valid runtime result. This function does not
    execute controls or inspect PostgreSQL.
    """

    return Layer3EvidenceManifest(
        schema_name=MANIFEST_SCHEMA_NAME,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        run_id=run_id,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        fixed_schedule_identity=FIXED_SCHEDULE_IDENTITY,
        recorded_rounds=RECORDED_ROUNDS,
        samples_per_control=SAMPLES_PER_CONTROL,
        total_planned_samples=TOTAL_PLANNED_SAMPLES,
        controls=tuple(control.value for control in ALL_CONTROLS),
        clock_identity=CLOCK_IDENTITY,
        postgresql_server_version=postgresql_server_version,
        validation_status=VALIDATION_STATUS,
        publication_rule=PUBLICATION_RULE,
    )


def manifest_to_dict(manifest: Layer3EvidenceManifest) -> dict[str, Any]:
    """Convert exactly the closed sanitized manifest into a JSON-ready map.

    No connection or environment field is synthesized by serialization.
    """

    return {
        "schema_name": manifest.schema_name,
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "source_commit": manifest.source_commit,
        "source_tree_clean_before_run": manifest.source_tree_clean_before_run,
        "fixed_schedule_identity": manifest.fixed_schedule_identity,
        "recorded_rounds": manifest.recorded_rounds,
        "samples_per_control": manifest.samples_per_control,
        "total_planned_samples": manifest.total_planned_samples,
        "controls": list(manifest.controls),
        "clock_identity": manifest.clock_identity,
        "postgresql_server_version": manifest.postgresql_server_version,
        "validation_status": manifest.validation_status,
        "publication_rule": manifest.publication_rule,
    }


def manifest_to_json(manifest: Layer3EvidenceManifest) -> str:
    """Serialize the closed manifest deterministically with no secret fields.

    This conversion neither validates a runtime result nor publishes files.
    """

    return json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"


def manifest_from_dict(raw: Mapping[str, Any]) -> Layer3EvidenceManifest:
    """Parse only the exact Layer-3 manifest keys and invariant values.

    Unknown fields are rejected rather than retained or interpreted.
    """

    _require_exact_keys(raw, _MANIFEST_KEYS, "manifest")
    return Layer3EvidenceManifest(
        schema_name=raw["schema_name"],
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        source_commit=raw["source_commit"],
        source_tree_clean_before_run=raw["source_tree_clean_before_run"],
        fixed_schedule_identity=raw["fixed_schedule_identity"],
        recorded_rounds=raw["recorded_rounds"],
        samples_per_control=raw["samples_per_control"],
        total_planned_samples=raw["total_planned_samples"],
        controls=tuple(raw["controls"]),
        clock_identity=raw["clock_identity"],
        postgresql_server_version=raw["postgresql_server_version"],
        validation_status=raw["validation_status"],
        publication_rule=raw["publication_rule"],
    )


def sample_to_dict(sample: Layer3Sample) -> dict[str, Any]:
    """Serialize one existing typed sample without expanding its closed fields.

    The map adds no run, request, order, component-sum, or execution identity.
    """

    if isinstance(sample, ControlAIdleRollbackSample):
        return {
            "control": sample.control.value,
            "sample_index": sample.sample_index,
            "round_index": sample.round_index,
            "status_before_cleanup": _optional_enum_value(
                sample.status_before_cleanup
            ),
            "cleanup_elapsed_ns": sample.cleanup_elapsed_ns,
            "status_after_cleanup": _optional_enum_value(
                sample.status_after_cleanup
            ),
            "exception_type": sample.exception_type,
        }
    if isinstance(sample, ControlBPreliminaryReadLifecycleSample):
        return {
            "control": sample.control.value,
            "sample_index": sample.sample_index,
            "round_index": sample.round_index,
            "returned_idempotency_verdict": _optional_enum_value(
                sample.returned_idempotency_verdict
            ),
            "history_count": sample.history_count,
            "idempotency_check_elapsed_ns": sample.idempotency_check_elapsed_ns,
            "accepted_history_load_elapsed_ns": (
                sample.accepted_history_load_elapsed_ns
            ),
            "cleanup_elapsed_ns": sample.cleanup_elapsed_ns,
            "lifecycle_elapsed_ns": sample.lifecycle_elapsed_ns,
            "status_before_check": _optional_enum_value(
                sample.status_before_check
            ),
            "status_after_check": _optional_enum_value(sample.status_after_check),
            "status_after_history": _optional_enum_value(
                sample.status_after_history
            ),
            "status_after_cleanup": _optional_enum_value(
                sample.status_after_cleanup
            ),
            "reuse_select_succeeded": sample.reuse_select_succeeded,
            "final_transaction_status": _optional_enum_value(
                sample.final_transaction_status
            ),
            "exception_type": sample.exception_type,
        }
    raise TypeError("sample must be one exact Layer-3 sample type")


def sample_from_dict(raw: Mapping[str, Any]) -> Layer3Sample:
    """Reconstruct one existing Layer-3 sample from its control-specific map.

    Exact key checks prevent schema expansion and do not repair invalid values.
    """

    if not isinstance(raw, Mapping):
        raise ValueError("sample must be one JSON object")
    control = Layer3Control(raw.get("control"))
    if control is Layer3Control.CONTROL_A_IDLE_ROLLBACK:
        _require_exact_keys(raw, _CONTROL_A_SAMPLE_KEYS, "Control-A sample")
        return ControlAIdleRollbackSample(
            control=control,
            sample_index=raw["sample_index"],
            round_index=raw["round_index"],
            status_before_cleanup=_optional_status(raw["status_before_cleanup"]),
            cleanup_elapsed_ns=raw["cleanup_elapsed_ns"],
            status_after_cleanup=_optional_status(raw["status_after_cleanup"]),
            exception_type=raw["exception_type"],
        )
    _require_exact_keys(raw, _CONTROL_B_SAMPLE_KEYS, "Control-B sample")
    return ControlBPreliminaryReadLifecycleSample(
        control=control,
        sample_index=raw["sample_index"],
        round_index=raw["round_index"],
        returned_idempotency_verdict=_optional_verdict(
            raw["returned_idempotency_verdict"]
        ),
        history_count=raw["history_count"],
        idempotency_check_elapsed_ns=raw["idempotency_check_elapsed_ns"],
        accepted_history_load_elapsed_ns=raw[
            "accepted_history_load_elapsed_ns"
        ],
        cleanup_elapsed_ns=raw["cleanup_elapsed_ns"],
        lifecycle_elapsed_ns=raw["lifecycle_elapsed_ns"],
        status_before_check=_optional_status(raw["status_before_check"]),
        status_after_check=_optional_status(raw["status_after_check"]),
        status_after_history=_optional_status(raw["status_after_history"]),
        status_after_cleanup=_optional_status(raw["status_after_cleanup"]),
        reuse_select_succeeded=raw["reuse_select_succeeded"],
        final_transaction_status=_optional_status(
            raw["final_transaction_status"]
        ),
        exception_type=raw["exception_type"],
    )


def samples_to_jsonl(samples: Iterable[Layer3Sample]) -> str:
    """Serialize deterministic JSONL in the supplied fixed schedule order.

    The function does not reorder, validate, or add identities to samples.
    """

    lines = [
        json.dumps(sample_to_dict(sample), sort_keys=True, separators=(",", ":"))
        for sample in samples
    ]
    return "" if not lines else "\n".join(lines) + "\n"


def samples_from_jsonl(payload: str) -> tuple[Layer3Sample, ...]:
    """Parse control-specific JSONL without accepting blank records.

    Parsing reconstructs typed samples but does not repair or publish them.
    """

    if not payload:
        return ()
    lines = payload.splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("samples JSONL must not contain blank records")
    return tuple(sample_from_dict(json.loads(line)) for line in lines)


def aggregates_to_dict(
    *,
    run_id: str,
    aggregates: Sequence[Layer3Aggregate],
) -> dict[str, Any]:
    """Serialize exactly two control-local aggregates without pooling.

    Existing model aggregates are accepted in exact control order. No timing
    field is summed, ranked, or reinterpreted.
    """

    _require_safe_run_id(run_id)
    _require_exact_aggregate_shape(aggregates)
    control_a, control_b = aggregates
    return {
        "schema_name": AGGREGATES_SCHEMA_NAME,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "groups": [
            {
                "control": control_a.control.value,
                "cleanup_elapsed_ns": _statistics_to_dict(
                    control_a.cleanup_elapsed_ns
                ),
            },
            {
                "control": control_b.control.value,
                "idempotency_check_elapsed_ns": _statistics_to_dict(
                    control_b.idempotency_check_elapsed_ns
                ),
                "accepted_history_load_elapsed_ns": _statistics_to_dict(
                    control_b.accepted_history_load_elapsed_ns
                ),
                "cleanup_elapsed_ns": _statistics_to_dict(
                    control_b.cleanup_elapsed_ns
                ),
                "lifecycle_elapsed_ns": _statistics_to_dict(
                    control_b.lifecycle_elapsed_ns
                ),
            },
        ],
    }


def aggregates_to_json(
    *,
    run_id: str,
    aggregates: Sequence[Layer3Aggregate],
) -> str:
    """Serialize the exact two-group aggregate envelope deterministically.

    Serialization adds no pooled score, p95, component sum, or interpretation.
    """

    return (
        json.dumps(
            aggregates_to_dict(run_id=run_id, aggregates=aggregates),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def aggregates_from_dict(raw: Mapping[str, Any]) -> tuple[Layer3Aggregate, ...]:
    """Parse exactly two control-local aggregates from the closed envelope.

    Unknown groups or fields are rejected and never normalized or repaired.
    """

    _require_exact_keys(raw, _AGGREGATE_ENVELOPE_KEYS, "aggregate envelope")
    if raw["schema_name"] != AGGREGATES_SCHEMA_NAME:
        raise ValueError("aggregate schema_name is not supplemental Layer 3")
    if raw["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("aggregate schema_version is unsupported")
    _require_safe_run_id(raw["run_id"])
    groups = raw["groups"]
    if not isinstance(groups, list) or len(groups) != len(ALL_CONTROLS):
        raise ValueError("aggregate groups must contain exactly two entries")
    raw_a, raw_b = groups
    _require_exact_keys(raw_a, _CONTROL_A_AGGREGATE_KEYS, "Control-A aggregate")
    _require_exact_keys(raw_b, _CONTROL_B_AGGREGATE_KEYS, "Control-B aggregate")
    if raw_a["control"] != Layer3Control.CONTROL_A_IDLE_ROLLBACK.value:
        raise ValueError("first aggregate must be exact Control A")
    if (
        raw_b["control"]
        != Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE.value
    ):
        raise ValueError("second aggregate must be exact Control B")
    aggregates: tuple[Layer3Aggregate, ...] = (
        ControlAIdleRollbackAggregate(
            control=Layer3Control.CONTROL_A_IDLE_ROLLBACK,
            cleanup_elapsed_ns=_statistics_from_dict(
                raw_a["cleanup_elapsed_ns"]
            ),
        ),
        ControlBPreliminaryReadLifecycleAggregate(
            control=Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE,
            idempotency_check_elapsed_ns=_statistics_from_dict(
                raw_b["idempotency_check_elapsed_ns"]
            ),
            accepted_history_load_elapsed_ns=_statistics_from_dict(
                raw_b["accepted_history_load_elapsed_ns"]
            ),
            cleanup_elapsed_ns=_statistics_from_dict(
                raw_b["cleanup_elapsed_ns"]
            ),
            lifecycle_elapsed_ns=_statistics_from_dict(
                raw_b["lifecycle_elapsed_ns"]
            ),
        ),
    )
    _require_exact_aggregate_shape(aggregates)
    return aggregates


def write_layer3_evidence_directory(
    *,
    output_root: Path,
    manifest: Layer3EvidenceManifest,
    result: Layer3RuntimeResult,
) -> EvidenceWriteResult | None:
    """Atomically publish three files only for one valid clean Layer-3 run.

    The exact schedule is freshly validated and aggregates are generated before
    filesystem publication. Invalid or dirty evidence returns ``None`` without
    creating the namespace. Existing final runs are immutable, and a failed
    partial write removes only this call's hidden staging directory. The writer
    neither executes PostgreSQL nor retries or interprets the run.
    """

    if not isinstance(result, Layer3RuntimeResult):
        raise TypeError("result must be Layer3RuntimeResult")
    schedule = generate_recorded_schedule()
    fresh_validation = validate_run(schedule, result.samples)
    if (
        result.schedule != schedule
        or fresh_validation.validity is not RunValidity.VALID
        or result.validation != fresh_validation
        or not manifest.source_tree_clean_before_run
    ):
        return None
    counts = schedule_control_counts(result.schedule)
    if counts != {control: SAMPLES_PER_CONTROL for control in ALL_CONTROLS}:
        return None

    aggregates = aggregate_recorded_samples(result.samples)
    _require_exact_aggregate_shape(aggregates)
    payloads = {
        "manifest.json": manifest_to_json(manifest),
        "samples.jsonl": samples_to_jsonl(result.samples),
        "aggregates.json": aggregates_to_json(
            run_id=manifest.run_id,
            aggregates=aggregates,
        ),
    }
    if set(payloads) != EVIDENCE_FILENAMES:
        raise Layer3EvidenceError("publication payload set is not exactly three files")

    _require_supplemental_output_root(output_root)
    final_directory = output_root / manifest.run_id
    if final_directory.exists():
        raise FileExistsError("refusing to overwrite an existing evidence run")
    output_root.mkdir(parents=True, exist_ok=True)
    if final_directory.exists():
        raise FileExistsError("refusing to overwrite an existing evidence run")

    staging_directory = Path(
        tempfile.mkdtemp(
            prefix=f".{manifest.run_id}.staging-",
            dir=output_root,
        )
    )
    try:
        for filename, payload in payloads.items():
            _write_complete_file(staging_directory / filename, payload)
        _fsync_directory(staging_directory)
        if final_directory.exists():
            raise FileExistsError("refusing to overwrite an existing evidence run")
        os.rename(staging_directory, final_directory)
        _fsync_directory(output_root)
    except BaseException:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
        raise

    return EvidenceWriteResult(
        directory=final_directory,
        manifest_path=final_directory / "manifest.json",
        samples_path=final_directory / "samples.jsonl",
        aggregates_path=final_directory / "aggregates.json",
    )


def read_layer3_evidence_directory(directory: Path) -> PublishedLayer3Evidence:
    """Strictly parse, revalidate, and recompute one three-file Layer-3 run.

    The directory must be in the exact Layer-3 namespace and contain no extra
    entries. Read-back never mutates, repairs, republishes, or interprets data.
    """

    if not isinstance(directory, Path):
        raise TypeError("directory must be pathlib.Path")
    _require_supplemental_output_root(directory.parent)
    entries = {path.name for path in directory.iterdir()}
    if entries != EVIDENCE_FILENAMES:
        raise Layer3EvidenceError("evidence directory must contain three files")
    manifest = manifest_from_dict(
        json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    )
    if directory.name != manifest.run_id:
        raise Layer3EvidenceError("directory run_id differs from manifest")
    if not manifest.source_tree_clean_before_run:
        raise Layer3EvidenceError("published manifest must retain clean source")
    samples = samples_from_jsonl(
        (directory / "samples.jsonl").read_text(encoding="utf-8")
    )
    schedule = generate_recorded_schedule()
    fresh_validation = validate_run(schedule, samples)
    if fresh_validation.validity is not RunValidity.VALID:
        raise Layer3EvidenceError("published samples do not freshly validate")
    raw_aggregates = json.loads(
        (directory / "aggregates.json").read_text(encoding="utf-8")
    )
    if raw_aggregates.get("run_id") != manifest.run_id:
        raise Layer3EvidenceError("aggregate run_id differs from manifest")
    aggregates = aggregates_from_dict(raw_aggregates)
    recomputed = aggregate_recorded_samples(samples)
    if aggregates != recomputed:
        raise Layer3EvidenceError("published aggregates differ from samples")
    return PublishedLayer3Evidence(
        manifest=manifest,
        samples=samples,
        aggregates=(aggregates[0], aggregates[1]),
    )


def _statistics_to_dict(result: DescriptiveStatistics) -> dict[str, Any]:
    if result.count != SAMPLES_PER_CONTROL:
        raise ValueError("each aggregate timing must contain 30 samples")
    return {
        "count": result.count,
        "minimum_ns": result.minimum_ns,
        "mean_ns": result.mean_ns,
        "median_ns": result.median_ns,
        "maximum_ns": result.maximum_ns,
    }


def _statistics_from_dict(raw: Mapping[str, Any]) -> DescriptiveStatistics:
    _require_exact_keys(raw, _STATISTICS_KEYS, "statistics")
    result = DescriptiveStatistics(
        count=raw["count"],
        minimum_ns=raw["minimum_ns"],
        mean_ns=raw["mean_ns"],
        median_ns=raw["median_ns"],
        maximum_ns=raw["maximum_ns"],
    )
    if result.count != SAMPLES_PER_CONTROL:
        raise ValueError("parsed aggregate timing must contain 30 samples")
    return result


def _require_exact_aggregate_shape(
    aggregates: Sequence[Layer3Aggregate],
) -> None:
    if len(aggregates) != len(ALL_CONTROLS):
        raise ValueError("aggregates must contain exactly two controls")
    control_a, control_b = aggregates
    if not isinstance(control_a, ControlAIdleRollbackAggregate) or (
        control_a.control is not Layer3Control.CONTROL_A_IDLE_ROLLBACK
    ):
        raise ValueError("first aggregate must be exact Control A")
    if not isinstance(control_b, ControlBPreliminaryReadLifecycleAggregate) or (
        control_b.control
        is not Layer3Control.CONTROL_B_PRELIMINARY_READ_LIFECYCLE
    ):
        raise ValueError("second aggregate must be exact Control B")
    for result in (
        control_a.cleanup_elapsed_ns,
        control_b.idempotency_check_elapsed_ns,
        control_b.accepted_history_load_elapsed_ns,
        control_b.cleanup_elapsed_ns,
        control_b.lifecycle_elapsed_ns,
    ):
        if result.count != SAMPLES_PER_CONTROL:
            raise ValueError("each aggregate timing must contain 30 samples")


def _optional_enum_value(value: Any) -> str | None:
    return None if value is None else value.value


def _optional_status(value: Any) -> TransactionStatusIdentity | None:
    return None if value is None else TransactionStatusIdentity(value)


def _optional_verdict(value: Any) -> IdempotencyVerdictIdentity | None:
    return None if value is None else IdempotencyVerdictIdentity(value)


def _require_safe_run_id(run_id: str) -> None:
    if (
        not isinstance(run_id, str)
        or run_id in {".", ".."}
        or _SAFE_RUN_ID.fullmatch(run_id) is None
    ):
        raise ValueError("run_id must be one path-safe identifier")


def _require_safe_server_version(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("PostgreSQL server version must be one short string")
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
        raise Layer3EvidenceError("output_root is not the Layer-3 namespace")
    protected = {
        LAYER1_EVIDENCE_NAMESPACE,
        LAYER2_EVIDENCE_NAMESPACE,
        CANONICAL_PR6_EVIDENCE_NAMESPACE,
    }
    if protected & set(output_root.resolve(strict=False).parts):
        raise Layer3EvidenceError("refusing protected evidence ancestry")


def _require_exact_keys(
    raw: Mapping[str, Any],
    expected: frozenset[str],
    label: str,
) -> None:
    if not isinstance(raw, Mapping) or set(raw) != expected:
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
        "recorded_rounds",
        "samples_per_control",
        "total_planned_samples",
        "controls",
        "clock_identity",
        "postgresql_server_version",
        "validation_status",
        "publication_rule",
    }
)
_CONTROL_A_SAMPLE_KEYS = frozenset(
    {
        "control",
        "sample_index",
        "round_index",
        "status_before_cleanup",
        "cleanup_elapsed_ns",
        "status_after_cleanup",
        "exception_type",
    }
)
_CONTROL_B_SAMPLE_KEYS = frozenset(
    {
        "control",
        "sample_index",
        "round_index",
        "returned_idempotency_verdict",
        "history_count",
        "idempotency_check_elapsed_ns",
        "accepted_history_load_elapsed_ns",
        "cleanup_elapsed_ns",
        "lifecycle_elapsed_ns",
        "status_before_check",
        "status_after_check",
        "status_after_history",
        "status_after_cleanup",
        "reuse_select_succeeded",
        "final_transaction_status",
        "exception_type",
    }
)
_STATISTICS_KEYS = frozenset(
    {"count", "minimum_ns", "mean_ns", "median_ns", "maximum_ns"}
)
_AGGREGATE_ENVELOPE_KEYS = frozenset(
    {"schema_name", "schema_version", "run_id", "groups"}
)
_CONTROL_A_AGGREGATE_KEYS = frozenset(
    {"control", "cleanup_elapsed_ns"}
)
_CONTROL_B_AGGREGATE_KEYS = frozenset(
    {
        "control",
        "idempotency_check_elapsed_ns",
        "accepted_history_load_elapsed_ns",
        "cleanup_elapsed_ns",
        "lifecycle_elapsed_ns",
    }
)
