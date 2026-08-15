"""Valid-only evidence persistence for post-PR6 Layer-1 characterization.

This experiment-owned module serializes the accepted Layer-1 typed model into
a distinct supplemental namespace. It writes no evidence unless the complete
fixed 80-sample run validates as ``VALID``. It never connects to PostgreSQL,
reruns a sample, modifies canonical PR6 evidence, or creates governance,
attempt, execution, retry, or strategy-selection identities.
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

from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
    AdmissionComposition,
    CONTAMINATED_D_E_TIMING_FIELDS,
    DescriptiveStatistics,
    DurableVerificationResult,
    IdempotencyLifecycleObservation,
    IdempotencyLifecyclePosition,
    IdempotencyVerdictIdentity,
    Layer1Path,
    Layer1Sample,
    MeasurementAvailability,
    PHASE_NAMES,
    PathAggregate,
    PhaseAggregate,
    PhaseRecord,
    PhaseState,
    ProducerOutcome,
    RECORDED_SAMPLES_PER_PATH,
    RunValidity,
    SCHEMA_VERSION,
    TimingEligibility,
    TransactionStatusIdentity,
    ValidationPlacementIdentity,
    aggregate_recorded_samples,
    generate_recorded_schedule,
    validate_run,
)


EVIDENCE_SCHEMA_VERSION = 1
SUPPLEMENTAL_EVIDENCE_NAMESPACE = (
    "stage4b2-post-pr6-idempotency-lifecycle-layer1"
)
MANIFEST_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_lifecycle.layer1.manifest"
)
SAMPLES_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_lifecycle.layer1.samples"
)
AGGREGATES_SCHEMA_NAME = (
    "stage4b2.post_pr6.postgres_idempotency_lifecycle.layer1.aggregates"
)
FIXED_SCHEDULE_IDENTITY = "A_TO_H_ROUND_ROBIN_10_EACH_V1"
FIXED_RECORDED_SAMPLE_COUNT = len(generate_recorded_schedule().samples)
TIMER_IDENTITY = "time.perf_counter_ns"
VALIDATION_STACK_IDENTITY = "ValidationRuntime(FullProofValidator,STRICT)"
PUBLICATION_RULE = (
    "validate_run=VALID; invalid writes nothing; no replacement or automatic rerun"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPPLEMENTAL_EVIDENCE_ROOT = (
    PROJECT_ROOT / "experiments/stage4b2/evidence" / SUPPLEMENTAL_EVIDENCE_NAMESPACE
)
CANONICAL_PR6_EVIDENCE_DIRECTORY = (
    PROJECT_ROOT
    / "experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51"
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


class Layer1EvidenceError(RuntimeError):
    """Report supplemental evidence construction or publication failures."""


@dataclass(frozen=True)
class Layer1EvidenceManifest:
    """Retain only sanitized reproducibility facts for one recorded run."""

    schema_name: str
    schema_version: int
    run_id: str
    source_commit: str
    source_tree_clean_before_run: bool
    fixed_schedule_identity: str
    recorded_sample_count: int
    samples_per_path: int
    paths: tuple[str, ...]
    timer_identity: str
    postgresql_server_version: str | None
    validation_stack_identity: str
    d_e_contamination_rule: tuple[str, ...]
    stop_publication_rule: str

    def __post_init__(self) -> None:
        if self.schema_name != MANIFEST_SCHEMA_NAME:
            raise ValueError("manifest schema_name is not supplemental Layer 1")
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise ValueError("manifest schema_version is unsupported")
        _require_safe_run_id(self.run_id)
        if _FULL_COMMIT.fullmatch(self.source_commit) is None:
            raise ValueError("source_commit must be one full lowercase Git identity")
        if type(self.source_tree_clean_before_run) is not bool:
            raise TypeError("source_tree_clean_before_run must be bool")
        if self.fixed_schedule_identity != FIXED_SCHEDULE_IDENTITY:
            raise ValueError("manifest fixed schedule identity changed")
        if self.recorded_sample_count != FIXED_RECORDED_SAMPLE_COUNT:
            raise ValueError("manifest recorded sample count must be 80")
        if self.samples_per_path != RECORDED_SAMPLES_PER_PATH:
            raise ValueError("manifest samples_per_path must be 10")
        if self.paths != tuple(path.value for path in Layer1Path):
            raise ValueError("manifest paths must be exactly A through H")
        if self.timer_identity != TIMER_IDENTITY:
            raise ValueError("manifest timer identity changed")
        if self.validation_stack_identity != VALIDATION_STACK_IDENTITY:
            raise ValueError("manifest validation stack identity changed")
        if self.d_e_contamination_rule != CONTAMINATED_D_E_TIMING_FIELDS:
            raise ValueError("manifest D/E contamination rule changed")
        if self.stop_publication_rule != PUBLICATION_RULE:
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
class PublishedLayer1Evidence:
    """Return a fully parsed supplemental evidence directory."""

    manifest: Layer1EvidenceManifest
    samples: tuple[Layer1Sample, ...]
    aggregates: tuple[PathAggregate, ...]


def build_manifest(
    *,
    run_id: str,
    source_commit: str,
    source_tree_clean_before_run: bool,
    postgresql_server_version: str | None,
) -> Layer1EvidenceManifest:
    """Build the fixed sanitized manifest without reading environment values."""

    return Layer1EvidenceManifest(
        schema_name=MANIFEST_SCHEMA_NAME,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        run_id=run_id,
        source_commit=source_commit,
        source_tree_clean_before_run=source_tree_clean_before_run,
        fixed_schedule_identity=FIXED_SCHEDULE_IDENTITY,
        recorded_sample_count=FIXED_RECORDED_SAMPLE_COUNT,
        samples_per_path=RECORDED_SAMPLES_PER_PATH,
        paths=tuple(path.value for path in Layer1Path),
        timer_identity=TIMER_IDENTITY,
        postgresql_server_version=postgresql_server_version,
        validation_stack_identity=VALIDATION_STACK_IDENTITY,
        d_e_contamination_rule=CONTAMINATED_D_E_TIMING_FIELDS,
        stop_publication_rule=PUBLICATION_RULE,
    )


def sample_to_dict(sample: Layer1Sample) -> dict[str, Any]:
    """Convert every Layer1Sample field into a deterministic JSON-ready map."""

    durable = sample.durable_verification
    return {
        "schema_name": SAMPLES_SCHEMA_NAME,
        "schema_version": sample.schema_version,
        "run_id": sample.run_id,
        "sample_index": sample.sample_index,
        "planned_path": sample.planned_path.value,
        "classified_path": (
            None if sample.classified_path is None else sample.classified_path.value
        ),
        "validation_placement": sample.validation_placement.value,
        "admission_composition": sample.admission_composition.value,
        "external_elapsed_ns": sample.external_elapsed_ns,
        "producer_outcome": (
            None if sample.producer_outcome is None else sample.producer_outcome.value
        ),
        "idempotency_observations": [
            {
                "position": observation.position.value,
                "verdict": observation.verdict.value,
            }
            for observation in sample.idempotency_observations
        ],
        "measurement_availability": (
            None
            if sample.measurement_availability is None
            else sample.measurement_availability.value
        ),
        "phases": (
            None
            if sample.phases is None
            else [
                {
                    "name": phase.name,
                    "state": phase.state.value,
                    "elapsed_ns": phase.elapsed_ns,
                }
                for phase in sample.phases
            ]
        ),
        "producer_return_transaction_status": (
            None
            if sample.producer_return_transaction_status is None
            else sample.producer_return_transaction_status.value
        ),
        "reuse_select_succeeded": sample.reuse_select_succeeded,
        "final_transaction_status": (
            None
            if sample.final_transaction_status is None
            else sample.final_transaction_status.value
        ),
        "durable_verification": {
            "verified": durable.verified,
            "event_count": durable.event_count,
            "idempotency_record_count": durable.idempotency_record_count,
            "preexisting_state_unchanged": durable.preexisting_state_unchanged,
            "winner_is_sole_event": durable.winner_is_sole_event,
            "result_references_winner": durable.result_references_winner,
            "losing_candidate_absent": durable.losing_candidate_absent,
        },
        "timing_eligibility": sample.timing_eligibility.value,
        "contaminated_timing_fields": list(sample.contaminated_timing_fields),
        "exception_type": sample.exception_type,
    }


def sample_from_dict(raw: Mapping[str, Any]) -> Layer1Sample:
    """Reconstruct one exact Layer1Sample from its serialized representation."""

    _require_exact_keys(raw, _SAMPLE_KEYS, "sample")
    if raw["schema_name"] != SAMPLES_SCHEMA_NAME:
        raise ValueError("sample schema_name is not supplemental Layer 1")
    raw_phases = raw["phases"]
    phases = None
    if raw_phases is not None:
        if not isinstance(raw_phases, list):
            raise ValueError("sample phases must be a list or null")
        phases = tuple(
            PhaseRecord(
                name=item["name"],
                state=PhaseState(item["state"]),
                elapsed_ns=item["elapsed_ns"],
            )
            for item in raw_phases
        )
    raw_observations = raw["idempotency_observations"]
    if not isinstance(raw_observations, list):
        raise ValueError("idempotency_observations must be a list")
    durable = raw["durable_verification"]
    if not isinstance(durable, Mapping):
        raise ValueError("durable_verification must be an object")
    _require_exact_keys(durable, _DURABLE_KEYS, "durable_verification")
    return Layer1Sample(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        sample_index=raw["sample_index"],
        planned_path=Layer1Path(raw["planned_path"]),
        classified_path=(
            None
            if raw["classified_path"] is None
            else Layer1Path(raw["classified_path"])
        ),
        validation_placement=ValidationPlacementIdentity(
            raw["validation_placement"]
        ),
        admission_composition=AdmissionComposition(raw["admission_composition"]),
        external_elapsed_ns=raw["external_elapsed_ns"],
        producer_outcome=(
            None
            if raw["producer_outcome"] is None
            else ProducerOutcome(raw["producer_outcome"])
        ),
        idempotency_observations=tuple(
            IdempotencyLifecycleObservation(
                position=IdempotencyLifecyclePosition(item["position"]),
                verdict=IdempotencyVerdictIdentity(item["verdict"]),
            )
            for item in raw_observations
        ),
        measurement_availability=(
            None
            if raw["measurement_availability"] is None
            else MeasurementAvailability(raw["measurement_availability"])
        ),
        phases=phases,
        producer_return_transaction_status=(
            None
            if raw["producer_return_transaction_status"] is None
            else TransactionStatusIdentity(
                raw["producer_return_transaction_status"]
            )
        ),
        reuse_select_succeeded=raw["reuse_select_succeeded"],
        final_transaction_status=(
            None
            if raw["final_transaction_status"] is None
            else TransactionStatusIdentity(raw["final_transaction_status"])
        ),
        durable_verification=DurableVerificationResult(
            verified=durable["verified"],
            event_count=durable["event_count"],
            idempotency_record_count=durable["idempotency_record_count"],
            preexisting_state_unchanged=durable[
                "preexisting_state_unchanged"
            ],
            winner_is_sole_event=durable["winner_is_sole_event"],
            result_references_winner=durable["result_references_winner"],
            losing_candidate_absent=durable["losing_candidate_absent"],
        ),
        timing_eligibility=TimingEligibility(raw["timing_eligibility"]),
        contaminated_timing_fields=tuple(raw["contaminated_timing_fields"]),
        exception_type=raw["exception_type"],
    )


def samples_to_jsonl(samples: Iterable[Layer1Sample]) -> str:
    """Serialize one deterministic compact JSON object per sample line."""

    lines = [
        json.dumps(sample_to_dict(sample), sort_keys=True, separators=(",", ":"))
        for sample in samples
    ]
    return "" if not lines else "\n".join(lines) + "\n"


def samples_from_jsonl(payload: str) -> tuple[Layer1Sample, ...]:
    """Parse deterministic sample JSONL without accepting blank records."""

    if not payload:
        return ()
    lines = payload.splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError("samples JSONL must not contain blank records")
    return tuple(sample_from_dict(json.loads(line)) for line in lines)


def manifest_to_dict(manifest: Layer1EvidenceManifest) -> dict[str, Any]:
    """Convert the closed sanitized manifest into a JSON-ready map."""

    return {
        "schema_name": manifest.schema_name,
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "source_commit": manifest.source_commit,
        "source_tree_clean_before_run": manifest.source_tree_clean_before_run,
        "fixed_schedule_identity": manifest.fixed_schedule_identity,
        "recorded_sample_count": manifest.recorded_sample_count,
        "samples_per_path": manifest.samples_per_path,
        "paths": list(manifest.paths),
        "timer_identity": manifest.timer_identity,
        "postgresql_server_version": manifest.postgresql_server_version,
        "validation_stack_identity": manifest.validation_stack_identity,
        "d_e_contamination_rule": list(manifest.d_e_contamination_rule),
        "stop_publication_rule": manifest.stop_publication_rule,
    }


def manifest_to_json(manifest: Layer1EvidenceManifest) -> str:
    """Serialize one deterministic human-readable sanitized manifest."""

    return json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"


def manifest_from_dict(raw: Mapping[str, Any]) -> Layer1EvidenceManifest:
    """Parse only the closed supplemental manifest schema."""

    _require_exact_keys(raw, _MANIFEST_KEYS, "manifest")
    return Layer1EvidenceManifest(
        schema_name=raw["schema_name"],
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        source_commit=raw["source_commit"],
        source_tree_clean_before_run=raw["source_tree_clean_before_run"],
        fixed_schedule_identity=raw["fixed_schedule_identity"],
        recorded_sample_count=raw["recorded_sample_count"],
        samples_per_path=raw["samples_per_path"],
        paths=tuple(raw["paths"]),
        timer_identity=raw["timer_identity"],
        postgresql_server_version=raw["postgresql_server_version"],
        validation_stack_identity=raw["validation_stack_identity"],
        d_e_contamination_rule=tuple(raw["d_e_contamination_rule"]),
        stop_publication_rule=raw["stop_publication_rule"],
    )


def aggregates_to_dict(
    *,
    run_id: str,
    aggregates: Sequence[PathAggregate],
) -> dict[str, Any]:
    """Serialize exactly eight path-local groups without contaminated fields."""

    _require_safe_run_id(run_id)
    if tuple(aggregate.path for aggregate in aggregates) != tuple(Layer1Path):
        raise ValueError("aggregates must contain exactly A through H")
    groups = []
    for aggregate in aggregates:
        group: dict[str, Any] = {
            "path": aggregate.path.value,
            "phases": [
                {
                    "phase_name": phase.phase_name,
                    "statistics": _statistics_to_dict(phase.statistics),
                }
                for phase in aggregate.phases
            ],
            "unavailable_timing_fields": list(
                aggregate.unavailable_timing_fields
            ),
        }
        if aggregate.external_elapsed is not None:
            group["external_elapsed"] = _statistics_to_dict(
                aggregate.external_elapsed
            )
        groups.append(group)
    return {
        "schema_name": AGGREGATES_SCHEMA_NAME,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "groups": groups,
    }


def aggregates_to_json(
    *,
    run_id: str,
    aggregates: Sequence[PathAggregate],
) -> str:
    """Serialize path-local aggregates deterministically without pooled scores."""

    return (
        json.dumps(
            aggregates_to_dict(run_id=run_id, aggregates=aggregates),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def aggregates_from_dict(raw: Mapping[str, Any]) -> tuple[PathAggregate, ...]:
    """Parse and validate the exact eight-group aggregate envelope."""

    _require_exact_keys(raw, _AGGREGATE_ENVELOPE_KEYS, "aggregate envelope")
    if raw["schema_name"] != AGGREGATES_SCHEMA_NAME:
        raise ValueError("aggregate schema_name is not supplemental Layer 1")
    if raw["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("aggregate schema_version is unsupported")
    _require_safe_run_id(raw["run_id"])
    groups = raw["groups"]
    if not isinstance(groups, list) or len(groups) != len(Layer1Path):
        raise ValueError("aggregate groups must contain exactly eight entries")
    aggregates: list[PathAggregate] = []
    for raw_group in groups:
        if not isinstance(raw_group, Mapping):
            raise ValueError("aggregate group must be an object")
        path = Layer1Path(raw_group["path"])
        allowed_keys = (
            _AGGREGATE_GROUP_KEYS_WITH_EXTERNAL
            if "external_elapsed" in raw_group
            else _AGGREGATE_GROUP_KEYS_WITHOUT_EXTERNAL
        )
        _require_exact_keys(raw_group, allowed_keys, "aggregate group")
        raw_phases = raw_group["phases"]
        if not isinstance(raw_phases, list):
            raise ValueError("aggregate phases must be a list")
        phases = tuple(
            PhaseAggregate(
                phase_name=item["phase_name"],
                statistics=_statistics_from_dict(item["statistics"]),
            )
            for item in raw_phases
        )
        external = (
            None
            if "external_elapsed" not in raw_group
            else _statistics_from_dict(raw_group["external_elapsed"])
        )
        aggregates.append(
            PathAggregate(
                path=path,
                external_elapsed=external,
                phases=phases,
                unavailable_timing_fields=tuple(
                    raw_group["unavailable_timing_fields"]
                ),
            )
        )
    parsed = tuple(aggregates)
    if tuple(aggregate.path for aggregate in parsed) != tuple(Layer1Path):
        raise ValueError("aggregate path order must be exactly A through H")
    for aggregate in parsed:
        if aggregate.path in {Layer1Path.D, Layer1Path.E}:
            if (
                aggregate.external_elapsed is not None
                or aggregate.unavailable_timing_fields
                != CONTAMINATED_D_E_TIMING_FIELDS
                or {
                    phase.phase_name for phase in aggregate.phases
                }
                & set(CONTAMINATED_D_E_TIMING_FIELDS)
            ):
                raise ValueError("D/E aggregate exposed contaminated timing")
    return parsed


def write_evidence_directory(
    *,
    output_root: Path,
    manifest: Layer1EvidenceManifest,
    samples: Sequence[Layer1Sample],
) -> EvidenceWriteResult | None:
    """Atomically publish three artifacts only for one valid fixed run.

    Invalid evidence returns ``None`` before any directory is created. Existing
    final directories are never overwritten. Every payload is completed in one
    hidden same-parent staging directory before one final directory rename.
    """

    schedule = generate_recorded_schedule()
    validation = validate_run(schedule, samples)
    if validation.validity is not RunValidity.VALID:
        return None
    _require_supplemental_output_root(output_root)
    if any(sample.run_id != manifest.run_id for sample in samples):
        raise Layer1EvidenceError("sample run_id differs from manifest run_id")

    aggregates = aggregate_recorded_samples(samples)
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


def read_evidence_directory(directory: Path) -> PublishedLayer1Evidence:
    """Parse a complete three-file supplemental evidence directory."""

    entries = {path.name for path in directory.iterdir()}
    if entries != {"manifest.json", "samples.jsonl", "aggregates.json"}:
        raise Layer1EvidenceError("evidence directory must contain three files")
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
        raise Layer1EvidenceError("aggregate run_id differs from manifest")
    if any(sample.run_id != manifest.run_id for sample in samples):
        raise Layer1EvidenceError("sample run_id differs from manifest")
    schedule = generate_recorded_schedule()
    if validate_run(schedule, samples).validity is not RunValidity.VALID:
        raise Layer1EvidenceError("published samples do not validate")
    aggregates = aggregates_from_dict(raw_aggregates)
    if aggregates != aggregate_recorded_samples(samples):
        raise Layer1EvidenceError("published aggregates differ from samples")
    return PublishedLayer1Evidence(
        manifest=manifest,
        samples=samples,
        aggregates=aggregates,
    )


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
        raise Layer1EvidenceError("output_root is not the supplemental namespace")
    resolved = output_root.resolve(strict=False)
    canonical = CANONICAL_PR6_EVIDENCE_DIRECTORY.resolve(strict=False)
    if resolved == canonical or canonical in resolved.parents:
        raise Layer1EvidenceError("refusing canonical PR6 evidence namespace")


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
        "recorded_sample_count",
        "samples_per_path",
        "paths",
        "timer_identity",
        "postgresql_server_version",
        "validation_stack_identity",
        "d_e_contamination_rule",
        "stop_publication_rule",
    }
)
_SAMPLE_KEYS = frozenset(
    {
        "schema_name",
        "schema_version",
        "run_id",
        "sample_index",
        "planned_path",
        "classified_path",
        "validation_placement",
        "admission_composition",
        "external_elapsed_ns",
        "producer_outcome",
        "idempotency_observations",
        "measurement_availability",
        "phases",
        "producer_return_transaction_status",
        "reuse_select_succeeded",
        "final_transaction_status",
        "durable_verification",
        "timing_eligibility",
        "contaminated_timing_fields",
        "exception_type",
    }
)
_DURABLE_KEYS = frozenset(
    {
        "verified",
        "event_count",
        "idempotency_record_count",
        "preexisting_state_unchanged",
        "winner_is_sole_event",
        "result_references_winner",
        "losing_candidate_absent",
    }
)
_STATISTICS_KEYS = frozenset(
    {"count", "min_ns", "mean_ns", "median_ns", "max_ns"}
)
_AGGREGATE_ENVELOPE_KEYS = frozenset(
    {"schema_name", "schema_version", "run_id", "groups"}
)
_AGGREGATE_GROUP_KEYS_WITH_EXTERNAL = frozenset(
    {"path", "external_elapsed", "phases", "unavailable_timing_fields"}
)
_AGGREGATE_GROUP_KEYS_WITHOUT_EXTERNAL = frozenset(
    {"path", "phases", "unavailable_timing_fields"}
)
