"""Evidence model for the Stage 4B.5 runtime-governance characterization.

This module is deliberately standard-library-only at import time. The recorded
runner imports it before selecting an A, B, or C worker; keeping production
modules out of this import graph is what lets the A subprocess install the
verified historical modules under their canonical names without current-source
contamination.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
import fcntl
import gc
import hashlib
import importlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import tempfile
import time
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 2
SCHEDULE_SEED = 4_500_617
BOOTSTRAP_SEED = 4_500_951
BOOTSTRAP_REPETITIONS = 2_000
MICRO_WARMUP_BLOCKS = 5
MICRO_RECORDED_BLOCKS = 30
MICRO_REPETITIONS_PER_PERMUTATION = 100
POSTGRES_WARMUP_CYCLES = 5
POSTGRES_RECORDED_BLOCKS = 30
POSTGRES_REPETITIONS_PER_PERMUTATION = 10
POSTGRES_P99_MINIMUM_POPULATION = 10_000
TIMER = "time.perf_counter_ns"
SCHEMA_LEVEL = "migrations-through-007"
HISTORICAL_SOURCE_COMMIT = "0bd2f515bcc49e8e1f0e9d2f9dba4a294adadd0d"
SEQUENCE_RULE_ID = "order.transition.sequence-matches-accepted-next-version"
HISTORICAL_MODULE_ORDER = (
    "src.compass.transition.validators",
    "src.compass.transition.runtime",
    "src.pipeline.transactional.postgres_write_side",
)

# Historical A executes the three pinned modules above while deliberately
# sharing these audited-unchanged transitive dependencies with the current
# checkout. This is a closed import surface, not a freeze on unrelated future
# files elsewhere under src/.
_A_CURRENT_TRANSITIVE_DEPENDENCIES = (
    ("src", "src/__init__.py"),
    ("src.compass", "src/compass/__init__.py"),
    ("src.compass.transition", "src/compass/transition/__init__.py"),
    ("src.compass.transition.types", "src/compass/transition/types.py"),
    ("src.core", "src/core/__init__.py"),
    ("src.core.common", "src/core/common/__init__.py"),
    ("src.core.common.ids", "src/core/common/ids.py"),
    ("src.core.common.money", "src/core/common/money.py"),
    ("src.core.order", "src/core/order/__init__.py"),
    ("src.core.order.aggregate", "src/core/order/aggregate.py"),
    ("src.core.order.enums", "src/core/order/enums.py"),
    ("src.core.order.events", "src/core/order/events.py"),
    ("src.core.order.proofs", "src/core/order/proofs.py"),
    ("src.pipeline", "src/pipeline/__init__.py"),
    ("src.pipeline.transactional", "src/pipeline/transactional/__init__.py"),
    (
        "src.pipeline.transactional.admission",
        "src/pipeline/transactional/admission.py",
    ),
    (
        "src.pipeline.transactional.postgres_admission",
        "src/pipeline/transactional/postgres_admission.py",
    ),
    (
        "src.pipeline.transactional.postgres_unit_of_work",
        "src/pipeline/transactional/postgres_unit_of_work.py",
    ),
    (
        "src.pipeline.transactional.postgres_write_side_config",
        "src/pipeline/transactional/postgres_write_side_config.py",
    ),
    (
        "src.pipeline.transactional.postgres_write_side_execution_trace",
        "src/pipeline/transactional/postgres_write_side_execution_trace.py",
    ),
    (
        "src.pipeline.transactional.postgres_write_side_measurement_instrumentation",
        "src/pipeline/transactional/postgres_write_side_measurement_instrumentation.py",
    ),
    ("src.storage", "src/storage/__init__.py"),
    ("src.storage.errors", "src/storage/errors.py"),
    ("src.storage.event_store", "src/storage/event_store.py"),
    ("src.storage.idempotency_store", "src/storage/idempotency_store.py"),
    ("src.storage.order_event_hydration", "src/storage/order_event_hydration.py"),
    ("src.storage.postgres_event_store", "src/storage/postgres_event_store.py"),
    (
        "src.storage.postgres_idempotency_store",
        "src/storage/postgres_idempotency_store.py",
    ),
)
_A_CURRENT_TRANSITIVE_DEPENDENCY_MODULES = frozenset(
    module_name for module_name, _ in _A_CURRENT_TRANSITIVE_DEPENDENCIES
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
A_SOURCE_PROVENANCE_PATH = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "stage4b5_runtime_governance_overhead"
    / "provenance.json"
)
A_REPLAY_REVIEW_PATH = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "stage4b5_runtime_governance_overhead"
    / "replay_review.json"
)
_A_HISTORICAL_SOURCE_DIFFERENCES_SHA256 = (
    "16a3050e5738a0d18911c61786dfd03f0dc25ec3fd2080a7e0061e7885347ee7"
)


class Layer(Enum):
    """Independent characterization layers."""

    MICRO = "MICRO"
    POSTGRES = "POSTGRES"


class Surface(Enum):
    """Matched A/B/C producer boundaries."""

    A = "A"
    B = "B"
    C = "C"


class AReplayStatus(Enum):
    """Availability of historical A against one reviewed current source state."""

    COMPATIBLE = "COMPATIBLE"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class AReplayCompatibility:
    """Retain one exact-state review result for historical A replay.

    This result describes only whether the hybrid historical-A loader may use
    the reviewed current transitive dependency bytes. It is not benchmark
    evidence, a performance conclusion, or runtime-governance authority.
    """

    status: AReplayStatus
    reason: str
    reviewed_current_source_commit: str


class AReplayReviewError(ValueError):
    """Raised when current protected source differs from its reviewed state."""


class Command(Enum):
    """Write commands represented in the fixed scenario matrix."""

    CREATE = "CREATE"
    PAY = "PAY"


class Terminal(Enum):
    """Terminal classes deliberately covered by this characterization."""

    ACCEPTED = "ACCEPTED"
    VALIDATION_BLOCKED = "VALIDATION_BLOCKED"


class Placement(Enum):
    """PostgreSQL validation placements; micro has no placement."""

    PRE_TRANSACTION = "PRE_TRANSACTION"
    IN_TRANSACTION = "IN_TRANSACTION"


@dataclass(frozen=True)
class Scenario:
    """One unpooled experiment cell."""

    name: str
    command: Command
    terminal: Terminal
    placement: Placement | None


@dataclass(frozen=True)
class Sample:
    """One externally timed observation."""

    schema_version: int
    run_id: str
    layer: str
    scenario: str
    surface: str
    block_index: int
    permutation_index: int
    repetition_index: int
    producer_elapsed_ns: int
    composition_elapsed_ns: int | None
    total_elapsed_ns: int
    producer_outcome: str
    rule_id: str | None

    @property
    def coordinate(self) -> tuple[str, int, int, int, str]:
        """Return this sample's exact fixed-schedule coordinate."""

        return (
            self.scenario,
            self.block_index,
            self.permutation_index,
            self.repetition_index,
            self.surface,
        )


@dataclass(frozen=True)
class BatchSummary:
    """Summarize one surface's repetitions in one block/permutation unit."""

    schema_version: int
    run_id: str
    layer: str
    scenario: str
    surface: str
    block_index: int
    permutation_index: int
    repetition_count: int
    producer_median_ns: int
    composition_median_ns: int | None
    total_median_ns: int


@dataclass(frozen=True)
class BatchComparison:
    """One block/permutation comparison or directly observed C composition lap."""

    schema_version: int
    run_id: str
    layer: str
    scenario: str
    comparison: str
    role: str
    experimental_unit: str
    block_index: int
    permutation_index: int
    estimate_metric: str
    estimate_ns: int
    relative_reference_metric: str
    relative_reference_summary_ns: int
    relative_estimate_percent: float
    estimation_method: str


@dataclass(frozen=True)
class ScheduleConfig:
    """Fixed, non-adaptive schedule parameters."""

    layer: Layer
    warmups: int
    recorded_blocks: int
    repetitions_per_permutation: int
    schedule_seed: int = SCHEDULE_SEED


MICRO_CONFIG = ScheduleConfig(
    layer=Layer.MICRO,
    warmups=MICRO_WARMUP_BLOCKS,
    recorded_blocks=MICRO_RECORDED_BLOCKS,
    repetitions_per_permutation=MICRO_REPETITIONS_PER_PERMUTATION,
)
POSTGRES_CONFIG = ScheduleConfig(
    layer=Layer.POSTGRES,
    warmups=POSTGRES_WARMUP_CYCLES,
    recorded_blocks=POSTGRES_RECORDED_BLOCKS,
    repetitions_per_permutation=POSTGRES_REPETITIONS_PER_PERMUTATION,
)


MICRO_SCENARIOS = tuple(
    Scenario(
        name=f"{command.value}_{terminal.value}",
        command=command,
        terminal=terminal,
        placement=None,
    )
    for command in Command
    for terminal in Terminal
)
POSTGRES_SCENARIOS = tuple(
    Scenario(
        name=f"{command.value}_{placement.value}_{terminal.value}",
        command=command,
        terminal=terminal,
        placement=placement,
    )
    for command in Command
    for placement in Placement
    for terminal in Terminal
)


def fixed_surface_permutations(
    seed: int = SCHEDULE_SEED,
) -> tuple[tuple[Surface, ...], ...]:
    """Return all six A/B/C orders in one fixed seeded order."""

    permutations = list(itertools.permutations(tuple(Surface)))
    random.Random(seed).shuffle(permutations)
    return tuple(permutations)


def expected_sample_count(
    *,
    scenarios: Sequence[Scenario],
    config: ScheduleConfig,
) -> int:
    """Return the exact fixed recorded population across A/B/C."""

    return (
        len(scenarios)
        * config.recorded_blocks
        * math.factorial(len(Surface))
        * len(Surface)
        * config.repetitions_per_permutation
    )


def _git(*args: str, binary: bool = False) -> str | bytes:
    """Run one read-only local Git query against the repository."""

    completed = subprocess.run(
        ("git", *args),
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
    )
    return completed.stdout if binary else completed.stdout.strip()


def load_and_verify_historical_a_source_provenance() -> dict[str, Any]:
    """Verify immutable historical A provenance independently of replay.

    This verification owns the audit-time fixture, pinned commit, protected
    historical module order, Git blob identities, and byte digests. Current
    transitive dependency compatibility is deliberately evaluated elsewhere so
    later production evolution cannot make recorded historical truth appear
    corrupt.
    """

    document = json.loads(A_SOURCE_PROVENANCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("A source provenance must be a JSON object")
    if document.get("schema") != "stage4b5-runtime-governance-a-source-provenance":
        raise ValueError("unexpected A source provenance schema")
    if document.get("schema_version") != 1:
        raise ValueError("unexpected A source provenance version")
    if document.get("source_commit") != HISTORICAL_SOURCE_COMMIT:
        raise ValueError(
            "A source commit does not match the pinned canonical PR6 commit"
        )
    resolved_commit = _git("rev-parse", f"{HISTORICAL_SOURCE_COMMIT}^{{commit}}")
    if resolved_commit != HISTORICAL_SOURCE_COMMIT:
        raise ValueError("canonical A commit did not resolve to its pinned identity")

    modules = document.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("A source provenance must name at least one module")
    if not all(isinstance(entry, dict) for entry in modules):
        raise ValueError("A source module provenance must be a JSON object")
    if tuple(entry.get("module") for entry in modules) != HISTORICAL_MODULE_ORDER:
        raise ValueError("A source modules must retain the audited dependency order")
    allowed_differences = document.get("allowed_current_source_differences")
    if not isinstance(allowed_differences, list) or not allowed_differences:
        raise ValueError("A source provenance must freeze current source differences")
    historical_differences = json.dumps(
        allowed_differences,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        hashlib.sha256(historical_differences).hexdigest()
        != _A_HISTORICAL_SOURCE_DIFFERENCES_SHA256
    ):
        raise ValueError("A source provenance audit-time differences changed")

    for entry in modules:
        if not all(
            isinstance(entry.get(field), str)
            for field in ("module", "path", "git_blob", "sha256")
        ):
            raise ValueError("A source module provenance fields must be strings")
        expected_blob = entry["git_blob"]
        actual_blob = _git(
            "rev-parse",
            f"{HISTORICAL_SOURCE_COMMIT}:{entry['path']}",
        )
        if actual_blob != expected_blob:
            raise ValueError(f"Git blob mismatch for {entry['path']}")
        source = _git("cat-file", "blob", expected_blob, binary=True)
        if hashlib.sha256(source).hexdigest() != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {entry['path']}")
    return document


def load_and_verify_a_source_provenance() -> dict[str, Any]:
    """Return verified historical A provenance without evaluating replay."""

    return load_and_verify_historical_a_source_provenance()


def _load_and_verify_a_replay_review() -> dict[str, Any]:
    """Load the additive exact-state review for current historical-A replay."""

    document = json.loads(A_REPLAY_REVIEW_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AReplayReviewError("A replay review must be a JSON object")
    if document.get("schema") != "stage4b5-runtime-governance-a-replay-review":
        raise AReplayReviewError("unexpected A replay review schema")
    if document.get("schema_version") != 1:
        raise AReplayReviewError("unexpected A replay review version")
    if document.get("historical_a_source_commit") != HISTORICAL_SOURCE_COMMIT:
        raise AReplayReviewError(
            "A replay review does not match the historical A source commit"
        )

    reviewed_current_source_commit = document.get("reviewed_current_source_commit")
    if not isinstance(reviewed_current_source_commit, str):
        raise AReplayReviewError(
            "A replay review must identify its reviewed current source commit"
        )
    resolved_review_commit = _git(
        "rev-parse",
        f"{reviewed_current_source_commit}^{{commit}}",
    )
    if resolved_review_commit != reviewed_current_source_commit:
        raise AReplayReviewError(
            "A replay review commit did not resolve to its recorded identity"
        )

    try:
        status = AReplayStatus(document.get("replay_status"))
    except ValueError as exc:
        raise AReplayReviewError("unexpected A replay review status") from exc
    reason = document.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AReplayReviewError("A replay review must include a reason")

    dependencies = document.get("protected_current_dependencies")
    if not isinstance(dependencies, list):
        raise AReplayReviewError(
            "A replay review must identify protected current dependencies"
        )
    reviewed_order = tuple(
        (entry.get("module"), entry.get("path"))
        for entry in dependencies
        if isinstance(entry, dict)
    )
    if reviewed_order != _A_CURRENT_TRANSITIVE_DEPENDENCIES:
        raise AReplayReviewError(
            "A replay review must retain the protected dependency order"
        )
    for entry in dependencies:
        digest = entry.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise AReplayReviewError(
                "A replay review dependency SHA-256 identities are invalid"
            )
        reviewed_source = _git(
            "show",
            f"{reviewed_current_source_commit}:{entry['path']}",
            binary=True,
        )
        assert isinstance(reviewed_source, bytes)
        if hashlib.sha256(reviewed_source).hexdigest() != digest:
            raise AReplayReviewError(
                "A replay review dependency identity does not match its "
                f"reviewed commit: {entry['path']}"
            )

    # Parsing the status here prevents a syntactically valid but unsupported
    # status from being treated as a generic replay refusal.
    assert status in {AReplayStatus.COMPATIBLE, AReplayStatus.REFUSED}
    return document


def _read_head_protected_source(source_path: str) -> bytes:
    """Return the exact committed bytes for one protected current dependency."""

    source = _git("show", f"HEAD:{source_path}", binary=True)
    assert isinstance(source, bytes)
    return source


def _read_working_tree_protected_source(source_path: str) -> bytes:
    """Return the exact bytes that a current historical-A worker would import."""

    return (REPOSITORY_ROOT / source_path).read_bytes()


def evaluate_a_current_replay_compatibility() -> AReplayCompatibility:
    """Evaluate current historical-A replay against one exact reviewed state.

    Both committed ``HEAD`` bytes and working-tree bytes must match the review
    artifact. Matching a reviewed ``REFUSED`` state returns that status. Any
    mismatch is unreviewed protected dependency drift and raises instead of
    silently becoming another refusal.
    """

    document = _load_and_verify_a_replay_review()
    committed_drift: list[str] = []
    working_tree_drift: list[str] = []
    for entry in document["protected_current_dependencies"]:
        source_path = entry["path"]
        expected_digest = entry["sha256"]
        committed_digest = hashlib.sha256(
            _read_head_protected_source(source_path)
        ).hexdigest()
        working_tree_digest = hashlib.sha256(
            _read_working_tree_protected_source(source_path)
        ).hexdigest()
        if committed_digest != expected_digest:
            committed_drift.append(source_path)
        if working_tree_digest != expected_digest:
            working_tree_drift.append(source_path)

    if committed_drift or working_tree_drift:
        details: list[str] = []
        if committed_drift:
            details.append("HEAD=" + ", ".join(committed_drift))
        if working_tree_drift:
            details.append("working-tree=" + ", ".join(working_tree_drift))
        raise AReplayReviewError(
            "unreviewed current A protected dependency drift: "
            + "; ".join(details)
        )

    return AReplayCompatibility(
        status=AReplayStatus(document["replay_status"]),
        reason=document["reason"],
        reviewed_current_source_commit=document["reviewed_current_source_commit"],
    )


def install_verified_historical_modules() -> dict[str, Any]:
    """Install A's verified modules under canonical names in a fresh process.

    The caller must invoke this before any of the three canonical module names
    have been imported. Unchanged transitive dependencies continue to come from
    the current checkout; the source audit determined that the semantic delta is
    bounded by these three pinned modules. The process boundary prevents the B/C
    versions of those modules from coexisting with A.
    """

    document = load_and_verify_historical_a_source_provenance()
    replay = evaluate_a_current_replay_compatibility()
    if replay.status is not AReplayStatus.COMPATIBLE:
        raise AReplayReviewError(
            f"historical A replay status {replay.status.value}: {replay.reason}"
        )
    entries = document["modules"]
    module_names = {entry["module"] for entry in entries}

    def assert_children_absent(*, installed: set[str]) -> None:
        forbidden = module_names - installed
        contaminated = sorted(forbidden.intersection(sys.modules))
        attached: list[str] = []
        for entry in entries:
            name = entry["module"]
            if name in installed:
                continue
            parent_name, _, child_name = name.rpartition(".")
            parent = sys.modules.get(parent_name)
            if parent is not None and child_name in vars(parent):
                attached.append(name)
        if contaminated or attached:
            introduced = sorted(set(contaminated).union(attached))
            raise RuntimeError(
                "A parent import introduced protected current modules: "
                + ", ".join(introduced)
            )

    assert_children_absent(installed=set())
    parent_names = tuple(
        dict.fromkeys(entry["module"].rpartition(".")[0] for entry in entries)
    )
    for parent_name in parent_names:
        importlib.import_module(parent_name)
        assert_children_absent(installed=set())

    installed: set[str] = set()
    for entry in entries:
        name = entry["module"]
        parent_name, _, child_name = name.rpartition(".")
        assert_children_absent(installed=installed)
        parent = sys.modules[parent_name]
        source = _git("cat-file", "blob", entry["git_blob"], binary=True)
        module = ModuleType(name)
        module.__file__ = f"git:{HISTORICAL_SOURCE_COMMIT}:{entry['path']}"
        module.__package__ = parent_name
        module.__loader__ = None
        sys.modules[name] = module
        setattr(parent, child_name, module)
        try:
            exec(compile(source, module.__file__, "exec"), module.__dict__)
        except BaseException:
            sys.modules.pop(name, None)
            if getattr(parent, child_name, None) is module:
                delattr(parent, child_name)
            raise
        installed.add(name)
        assert_children_absent(installed=installed)

    allowed_source_modules = (
        _A_CURRENT_TRANSITIVE_DEPENDENCY_MODULES.union(module_names)
    )
    unexpected_source_modules = sorted(
        name
        for name in sys.modules
        if (name == "src" or name.startswith("src."))
        and name not in allowed_source_modules
    )
    if unexpected_source_modules:
        raise RuntimeError(
            "A import closure introduced unaudited current modules: "
            + ", ".join(unexpected_source_modules)
        )
    return document


def current_source_identity() -> dict[str, Any]:
    """Return current B/C Git identity without mutating repository state."""

    return {
        "commit": _git("rev-parse", "HEAD"),
        "production_src_tree": _git("rev-parse", "HEAD:src"),
        "harness_blobs": {
            path: _git("rev-parse", f"HEAD:{path}")
            for path in (
                "experiments/stage4b5/runtime_governance_overhead.py",
                "experiments/stage4b5/runtime_governance_overhead_recorded_run.py",
            )
        },
        "branch": _git("branch", "--show-current"),
        "working_tree_clean": not bool(_git("status", "--porcelain")),
    }


def nearest_rank(values: Sequence[float | int], percentile: float) -> float | int:
    """Return an empirical percentile using the nearest-rank convention."""

    if not values:
        raise ValueError("nearest_rank requires at least one value")
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(ordered))
    return ordered[rank - 1]


def distribution_summary(
    values: Sequence[float | int],
    *,
    include_p99: bool,
) -> dict[str, Any]:
    """Summarize a fixed empirical population without parametric assumptions."""

    if not values:
        raise ValueError("distribution summary requires at least one value")
    median = nearest_rank(values, 50)
    absolute_deviations = [abs(value - median) for value in values]
    summary: dict[str, Any] = {
        "count": len(values),
        "min": min(values),
        "p25": nearest_rank(values, 25),
        "p50": median,
        "p75": nearest_rank(values, 75),
        "p95": nearest_rank(values, 95),
        "max": max(values),
        "iqr": nearest_rank(values, 75) - nearest_rank(values, 25),
        "mad": nearest_rank(absolute_deviations, 50),
    }
    summary["p99"] = nearest_rank(values, 99) if include_p99 else None
    return summary


def _block_variation(
    values_by_block: Mapping[int, Sequence[float | int]],
) -> dict[str, Any]:
    """Summarize variation among per-block medians."""

    block_medians = {
        str(block): nearest_rank(values, 50)
        for block, values in sorted(values_by_block.items())
    }
    return {
        "block_medians": block_medians,
        "median_summary": distribution_summary(
            list(block_medians.values()),
            include_p99=False,
        ),
    }


def block_bootstrap_median_ci(
    values_by_block: Mapping[int, Sequence[float | int]],
    *,
    seed: int = BOOTSTRAP_SEED,
    repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, Any]:
    """Return a block-cluster bootstrap 95% CI for the pooled median.

    Recorded blocks are sampled with replacement. Every observation belonging
    to a selected block is retained, so each bootstrap replicate estimates the
    median over the same declared unit population as the reported empirical
    median. Histogram accumulation represents that complete resampled multiset
    without independently resampling within-block observations.
    """

    if repetitions <= 0:
        raise ValueError("bootstrap repetitions must be positive")
    blocks = [tuple(values) for _, values in sorted(values_by_block.items())]
    if not blocks or any(not block for block in blocks):
        raise ValueError("block bootstrap requires non-empty blocks")
    units_per_block = len(blocks[0])
    if any(len(block) != units_per_block for block in blocks):
        raise ValueError("block bootstrap requires equal fixed-population blocks")

    unique_values = sorted({value for block in blocks for value in block})
    value_indexes = {
        value: index for index, value in enumerate(unique_values)
    }
    block_histograms = [
        tuple(
            (value_indexes[value], count)
            for value, count in Counter(block).items()
        )
        for block in blocks
    ]
    bootstrap_population_size = len(blocks) * units_per_block
    median_rank = math.ceil(bootstrap_population_size * 0.5)
    rng = random.Random(seed)
    bootstrap_medians: list[float | int] = []
    for _ in range(repetitions):
        selected_multiplicities = [0] * len(blocks)
        for _ in blocks:
            selected_multiplicities[rng.randrange(len(blocks))] += 1

        # This histogram is the exact multiset formed by concatenating every
        # observation from each selected block, including repeated blocks.
        resampled_counts = [0] * len(unique_values)
        for multiplicity, histogram in zip(
            selected_multiplicities,
            block_histograms,
            strict=True,
        ):
            if not multiplicity:
                continue
            for value_index, count in histogram:
                resampled_counts[value_index] += multiplicity * count

        cumulative = 0
        for value, count in zip(unique_values, resampled_counts, strict=True):
            cumulative += count
            if cumulative >= median_rank:
                bootstrap_medians.append(value)
                break
        else:  # pragma: no cover - guarded by the complete block histograms
            raise AssertionError("cluster bootstrap population was incomplete")
    return {
        "method": (
            "fixed-seed recorded-block cluster bootstrap of pooled median"
        ),
        "statistic": "empirical nearest-rank median of pooled units",
        "resampling_unit": "recorded block",
        "within_block_units": "retained in full",
        "block_count": len(blocks),
        "units_per_block": units_per_block,
        "bootstrap_population_size": bootstrap_population_size,
        "confidence": 0.95,
        "seed": seed,
        "repetitions": repetitions,
        "lower": nearest_rank(bootstrap_medians, 2.5),
        "upper": nearest_rank(bootstrap_medians, 97.5),
    }


def compute_batch_summaries(
    samples: Sequence[Sample],
    *,
    config: ScheduleConfig,
) -> list[BatchSummary]:
    """Collapse repetitions into block/permutation experimental units."""

    groups: dict[
        tuple[str, str, str, int, int, str],
        list[Sample],
    ] = defaultdict(list)
    for sample in samples:
        key = (
            sample.run_id,
            sample.layer,
            sample.scenario,
            sample.block_index,
            sample.permutation_index,
            sample.surface,
        )
        groups[key].append(sample)

    summaries: list[BatchSummary] = []
    for key, group in sorted(groups.items()):
        run_id, layer, scenario, block, permutation, surface_value = key
        if len(group) != config.repetitions_per_permutation:
            raise ValueError(f"batch repetition population mismatch for {key}")
        repetitions = {sample.repetition_index for sample in group}
        expected_repetitions = set(
            range(config.repetitions_per_permutation)
        )
        if repetitions != expected_repetitions:
            raise ValueError(f"batch repetition coordinates mismatch for {key}")

        surface = Surface(surface_value)
        composition_values = [
            sample.composition_elapsed_ns
            for sample in group
            if sample.composition_elapsed_ns is not None
        ]
        if surface is Surface.C:
            if len(composition_values) != len(group):
                raise ValueError("C batch is missing composition lap observations")
            composition_median = int(nearest_rank(composition_values, 50))
        else:
            if composition_values:
                raise ValueError("A/B batch unexpectedly contains composition laps")
            composition_median = None

        summaries.append(
            BatchSummary(
                schema_version=SCHEMA_VERSION,
                run_id=run_id,
                layer=layer,
                scenario=scenario,
                surface=surface_value,
                block_index=block,
                permutation_index=permutation,
                repetition_count=len(group),
                producer_median_ns=int(
                    nearest_rank(
                        [sample.producer_elapsed_ns for sample in group],
                        50,
                    )
                ),
                composition_median_ns=composition_median,
                total_median_ns=int(
                    nearest_rank(
                        [sample.total_elapsed_ns for sample in group],
                        50,
                    )
                ),
            )
        )
    return summaries


def compute_batch_comparisons(
    summaries: Sequence[BatchSummary],
) -> list[BatchComparison]:
    """Compare surfaces only at the matched block/permutation batch unit."""

    groups: dict[
        tuple[str, str, str, int, int],
        dict[Surface, BatchSummary],
    ] = defaultdict(dict)
    for summary in summaries:
        key = (
            summary.run_id,
            summary.layer,
            summary.scenario,
            summary.block_index,
            summary.permutation_index,
        )
        surface = Surface(summary.surface)
        if surface in groups[key]:
            raise ValueError(f"duplicate batch surface for {key}")
        groups[key][surface] = summary

    comparisons: list[BatchComparison] = []
    for key, surfaces in sorted(groups.items()):
        if set(surfaces) != set(Surface):
            raise ValueError(f"incomplete A/B/C batch unit {key}")
        run_id, layer, scenario, block, permutation = key
        a = surfaces[Surface.A]
        b = surfaces[Surface.B]
        c = surfaces[Surface.C]
        if c.composition_median_ns is None:
            raise ValueError("C batch requires a composition median")

        definitions = (
            (
                "B-A_END_TO_END",
                "PRIMARY",
                "B.total_median_ns - A.total_median_ns",
                b.total_median_ns - a.total_median_ns,
                "difference of matched block/permutation batch medians",
            ),
            (
                "C-B_COMPOSITION_LAP",
                "PRIMARY",
                "C.composition_median_ns",
                c.composition_median_ns,
                "direct same-invocation composition lap summarized by batch median",
            ),
            (
                "C-A_END_TO_END",
                "PRIMARY",
                "C.total_median_ns - A.total_median_ns",
                c.total_median_ns - a.total_median_ns,
                "difference of matched block/permutation batch medians",
            ),
            (
                "C-B_TOTAL_SECONDARY",
                "SECONDARY_NOISE_SENSITIVE",
                "C.total_median_ns - B.total_median_ns",
                c.total_median_ns - b.total_median_ns,
                "independent full-path batch-median difference; not primary composition estimate",
            ),
        )
        for (
            comparison,
            role,
            estimate_metric,
            estimate_ns,
            method,
        ) in definitions:
            if a.total_median_ns <= 0:
                raise ValueError("batch comparison A reference must be positive")
            comparisons.append(
                BatchComparison(
                    schema_version=SCHEMA_VERSION,
                    run_id=run_id,
                    layer=layer,
                    scenario=scenario,
                    comparison=comparison,
                    role=role,
                    experimental_unit="recorded block/permutation batch",
                    block_index=block,
                    permutation_index=permutation,
                    estimate_metric=estimate_metric,
                    estimate_ns=estimate_ns,
                    relative_reference_metric="A.total_median_ns",
                    relative_reference_summary_ns=a.total_median_ns,
                    relative_estimate_percent=(
                        estimate_ns / a.total_median_ns
                    )
                    * 100.0,
                    estimation_method=method,
                )
            )
    return comparisons


def aggregate_evidence(
    samples: Sequence[Sample],
    batch_summaries: Sequence[BatchSummary],
    batch_comparisons: Sequence[BatchComparison],
    *,
    layer: Layer,
    bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict[str, Any]:
    """Aggregate raw absolutes and block/permutation comparison estimates."""

    include_p99 = layer is Layer.MICRO
    absolute_groups: dict[tuple[str, str], list[Sample]] = defaultdict(list)
    for sample in samples:
        absolute_groups[(sample.scenario, sample.surface)].append(sample)

    absolute: dict[str, Any] = {}
    for (scenario, surface), group in sorted(absolute_groups.items()):
        total_by_block: dict[int, list[int]] = defaultdict(list)
        for sample in group:
            total_by_block[sample.block_index].append(sample.total_elapsed_ns)
        key = f"{scenario}/{surface}"
        metrics = {
            "producer_elapsed_ns": distribution_summary(
                [sample.producer_elapsed_ns for sample in group],
                include_p99=include_p99,
            ),
            "total_elapsed_ns": distribution_summary(
                [sample.total_elapsed_ns for sample in group],
                include_p99=include_p99,
            ),
        }
        composition_values = [
            sample.composition_elapsed_ns
            for sample in group
            if sample.composition_elapsed_ns is not None
        ]
        if composition_values:
            metrics["composition_elapsed_ns"] = distribution_summary(
                composition_values,
                include_p99=include_p99,
            )
        absolute[key] = {
            "invocation_metrics": metrics,
            "total_elapsed_block_variation": _block_variation(total_by_block),
            "total_elapsed_median_bootstrap_ci_ns": block_bootstrap_median_ci(
                total_by_block,
                repetitions=bootstrap_repetitions,
            ),
        }
        if layer is Layer.POSTGRES:
            for metric in metrics.values():
                metric["p99_status"] = (
                    "withheld: fixed per-cell population below credibility "
                    f"threshold {POSTGRES_P99_MINIMUM_POPULATION}"
                )

    comparison_groups: dict[
        tuple[str, str],
        list[BatchComparison],
    ] = defaultdict(list)
    for comparison in batch_comparisons:
        comparison_groups[(comparison.scenario, comparison.comparison)].append(
            comparison
        )

    comparison_aggregates: dict[str, Any] = {}
    for (scenario, comparison), group in sorted(comparison_groups.items()):
        by_block: dict[int, list[int]] = defaultdict(list)
        for estimate in group:
            by_block[estimate.block_index].append(estimate.estimate_ns)
        key = f"{scenario}/{comparison}"
        comparison_aggregates[key] = {
            "role": group[0].role,
            "experimental_unit": group[0].experimental_unit,
            "estimation_method": group[0].estimation_method,
            "relative_reference_metric": group[0].relative_reference_metric,
            "estimate_ns": distribution_summary(
                [estimate.estimate_ns for estimate in group],
                include_p99=False,
            ),
            "relative_estimate_percent": distribution_summary(
                [estimate.relative_estimate_percent for estimate in group],
                include_p99=False,
            ),
            "block_variation": _block_variation(by_block),
            "median_bootstrap_ci_ns": block_bootstrap_median_ci(
                by_block,
                repetitions=bootstrap_repetitions,
            ),
            "p99_status": (
                "withheld for the 180 block/permutation comparison units; "
                "micro p99 applies to raw absolute and C composition-lap samples"
            ),
        }

    return {
        "schema": "stage4b5-runtime-governance-overhead-aggregates",
        "schema_version": SCHEMA_VERSION,
        "layer": layer.value,
        "percentile_method": "empirical-nearest-rank",
        "comparison_unit": "recorded block/permutation batch median",
        "comparison_rule": (
            "A/B and A/C compare batch medians; C-B primary uses the directly "
            "timed same-invocation C composition lap"
        ),
        "absolute": absolute,
        "batch_summary_count": len(batch_summaries),
        "batch_comparisons": comparison_aggregates,
    }


def environment_facts() -> dict[str, Any]:
    """Collect non-secret local runtime facts available without external access."""

    clock = time.get_clock_info("perf_counter")
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "platform_processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "timer": TIMER,
        "timer_implementation": clock.implementation,
        "timer_monotonic": clock.monotonic,
        "timer_adjustable": clock.adjustable,
        "timer_resolution_seconds": clock.resolution,
        "garbage_collection_enabled": gc.isenabled(),
    }


_SENSITIVE_MARKERS = (
    "TEST_DATABASE_URL",
    "DATABASE_URL",
    "postgresql://",
    "postgres://",
    "password=",
)


def assert_secret_free(document: Any) -> None:
    """Reject known connection-secret markers before evidence persistence."""

    serialized = json.dumps(
        document,
        sort_keys=True,
        default=(
            lambda value: asdict(value)
            if hasattr(value, "__dataclass_fields__")
            else str(value)
        ),
    )
    lowered = serialized.lower()
    for marker in _SENSITIVE_MARKERS:
        if marker.lower() in lowered:
            raise ValueError("evidence document contains a forbidden secret marker")


def _write_json(path: Path, document: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_jsonl(path: Path, records: Iterable[Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for record in records:
            document = (
                asdict(record)
                if hasattr(record, "__dataclass_fields__")
                else record
            )
            stream.write(json.dumps(document, sort_keys=True, separators=(",", ":")))
            stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_run_id(run_id: str) -> str:
    """Validate one filesystem-safe immutable evidence namespace identity."""

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    if (
        not run_id
        or run_id in {".", ".."}
        or run_id.startswith(".staging-")
        or any(character not in allowed for character in run_id)
    ):
        raise ValueError(
            "run_id must use only letters, digits, dot, dash, or underscore"
        )
    return run_id


def write_immutable_evidence(
    *,
    output_root: Path,
    run_id: str,
    manifest: Mapping[str, Any],
    samples: Sequence[Sample],
    batch_summaries: Sequence[BatchSummary],
    batch_comparisons: Sequence[BatchComparison],
    aggregates: Mapping[str, Any],
) -> Path:
    """Write one validated evidence namespace, refusing every overwrite."""

    validate_run_id(run_id)
    destination = output_root / run_id

    documents = (
        manifest,
        samples,
        batch_summaries,
        batch_comparisons,
        aggregates,
    )
    for document in documents:
        assert_secret_free(document)

    output_root.mkdir(parents=True, exist_ok=True)
    root_descriptor = os.open(output_root, os.O_RDONLY)
    try:
        fcntl.flock(root_descriptor, fcntl.LOCK_EX)
        if destination.exists():
            raise FileExistsError(
                f"evidence namespace already exists: {destination}"
            )
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".staging-{run_id}-",
                dir=output_root,
            )
        )
        _write_json(staging / "manifest.json", dict(manifest))
        _write_jsonl(staging / "samples.jsonl", samples)
        _write_jsonl(staging / "batch_summaries.jsonl", batch_summaries)
        _write_jsonl(staging / "batch_comparisons.jsonl", batch_comparisons)
        _write_json(staging / "aggregates.json", dict(aggregates))
        staging_descriptor = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(staging_descriptor)
        finally:
            os.close(staging_descriptor)
        os.rename(staging, destination)
        os.fsync(root_descriptor)
    finally:
        fcntl.flock(root_descriptor, fcntl.LOCK_UN)
        os.close(root_descriptor)
    return destination


def validate_recorded_population(
    *,
    samples: Sequence[Sample],
    scenarios: Sequence[Scenario],
    config: ScheduleConfig,
    run_id: str,
) -> None:
    """Fail closed unless samples exactly fill the fixed unpooled schedule."""

    permutation_count = len(fixed_surface_permutations(config.schedule_seed))
    expected_coordinates = {
        (
            scenario.name,
            block,
            permutation,
            repetition,
            surface.value,
        )
        for scenario in scenarios
        for block in range(config.recorded_blocks)
        for permutation in range(permutation_count)
        for repetition in range(config.repetitions_per_permutation)
        for surface in Surface
    }
    expected = len(expected_coordinates)
    if expected != expected_sample_count(scenarios=scenarios, config=config):
        raise ValueError("fixed schedule count and coordinate universe disagree")
    if len(samples) != expected:
        raise ValueError(
            f"sample population mismatch: expected {expected}, got {len(samples)}"
        )

    actual_coordinates = [sample.coordinate for sample in samples]
    if len(set(actual_coordinates)) != len(actual_coordinates):
        raise ValueError("recorded schedule contains duplicate coordinates")
    actual_coordinate_set = set(actual_coordinates)
    if actual_coordinate_set != expected_coordinates:
        missing = len(expected_coordinates - actual_coordinate_set)
        additional = len(actual_coordinate_set - expected_coordinates)
        raise ValueError(
            "recorded schedule coordinate universe mismatch: "
            f"missing={missing}, additional={additional}"
        )

    scenario_terminals = {
        scenario.name: scenario.terminal for scenario in scenarios
    }
    for sample in samples:
        if sample.schema_version != SCHEMA_VERSION:
            raise ValueError("sample schema version mismatch")
        if sample.run_id != run_id:
            raise ValueError("sample run identity mismatch")
        if sample.layer != config.layer.value:
            raise ValueError("sample layer mismatch")
        if (
            type(sample.producer_elapsed_ns) is not int
            or sample.producer_elapsed_ns <= 0
        ):
            raise ValueError("producer_elapsed_ns must be a positive int")
        if (
            type(sample.total_elapsed_ns) is not int
            or sample.total_elapsed_ns <= 0
        ):
            raise ValueError("total_elapsed_ns must be a positive int")
        surface = Surface(sample.surface)
        if surface is Surface.C:
            if (
                type(sample.composition_elapsed_ns) is not int
                or sample.composition_elapsed_ns < 0
            ):
                raise ValueError(
                    "C composition_elapsed_ns must be a non-negative int"
                )
            if sample.total_elapsed_ns != (
                sample.producer_elapsed_ns + sample.composition_elapsed_ns
            ):
                raise ValueError("C timing laps do not sum to total elapsed")
        else:
            if sample.composition_elapsed_ns is not None:
                raise ValueError("A/B must not report a composition lap")
            if sample.total_elapsed_ns != sample.producer_elapsed_ns:
                raise ValueError("A/B total must equal producer elapsed")

        terminal = scenario_terminals[sample.scenario]
        if sample.producer_outcome != terminal.value:
            raise ValueError("producer outcome does not match scenario")
        if surface is Surface.A and sample.rule_id is not None:
            raise ValueError("A must not claim Stage 4B.5 typed rule evidence")
        if surface in {Surface.B, Surface.C}:
            expected_rule = (
                SEQUENCE_RULE_ID
                if terminal is Terminal.VALIDATION_BLOCKED
                else None
            )
            if sample.rule_id != expected_rule:
                raise ValueError("B/C typed rule evidence does not match scenario")


def scenario_by_name(layer: Layer, name: str) -> Scenario:
    """Resolve a scenario without pooling across experiment cells."""

    scenarios = MICRO_SCENARIOS if layer is Layer.MICRO else POSTGRES_SCENARIOS
    for scenario in scenarios:
        if scenario.name == name:
            return scenario
    raise ValueError(f"unknown {layer.value} scenario: {name}")


__all__ = (
    "A_REPLAY_REVIEW_PATH",
    "A_SOURCE_PROVENANCE_PATH",
    "AReplayCompatibility",
    "AReplayReviewError",
    "AReplayStatus",
    "BOOTSTRAP_REPETITIONS",
    "BatchComparison",
    "BatchSummary",
    "Command",
    "HISTORICAL_SOURCE_COMMIT",
    "HISTORICAL_MODULE_ORDER",
    "Layer",
    "MICRO_CONFIG",
    "MICRO_SCENARIOS",
    "POSTGRES_CONFIG",
    "POSTGRES_SCENARIOS",
    "Placement",
    "REPOSITORY_ROOT",
    "SCHEMA_LEVEL",
    "SCHEMA_VERSION",
    "SEQUENCE_RULE_ID",
    "Sample",
    "Scenario",
    "ScheduleConfig",
    "Surface",
    "TIMER",
    "Terminal",
    "aggregate_evidence",
    "assert_secret_free",
    "block_bootstrap_median_ci",
    "compute_batch_comparisons",
    "compute_batch_summaries",
    "current_source_identity",
    "distribution_summary",
    "environment_facts",
    "evaluate_a_current_replay_compatibility",
    "expected_sample_count",
    "fixed_surface_permutations",
    "install_verified_historical_modules",
    "load_and_verify_a_source_provenance",
    "load_and_verify_historical_a_source_provenance",
    "nearest_rank",
    "scenario_by_name",
    "validate_recorded_population",
    "validate_run_id",
    "write_immutable_evidence",
)
