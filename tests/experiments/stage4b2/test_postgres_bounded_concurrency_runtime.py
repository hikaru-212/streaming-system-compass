"""Deterministic fake-runtime tests for the Stage 4B.2 PR7 executor."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import fields, replace
from decimal import Decimal
import json
import threading
from types import SimpleNamespace
from typing import Any

import pytest

import experiments.stage4b2.postgres_bounded_concurrency as preflight_module
import experiments.stage4b2.postgres_bounded_concurrency_runtime as runtime_module
from experiments.stage4b2.postgres_bounded_concurrency import (
    LEVEL_C_SCHEMA_NAME,
    LEVEL_C_SCHEMA_VERSION,
)
from experiments.stage4b2.postgres_bounded_concurrency_runtime import (
    EXACT_CELL_COUNT,
    EXPECTED_PHASE_STATE_MATRICES,
    PR3_PHASE_NAMES,
    RECORDED_BATCHES_PER_CELL,
    RECORDED_SCHEDULE_SEED,
    RETAINED_WORKER_LEVELS,
    WARMUP_BATCHES_PER_CELL,
    BatchRecord,
    BoundedConcurrencyRuntimeError,
    Cohort,
    Composition,
    DescriptiveStatistics,
    EvidenceStatus,
    ExperimentSchedule,
    InvocationRecord,
    LaneRuntime,
    LevelRuntime,
    PhaseRecord,
    PhaseState,
    RecordedScheduleExecutor,
    RejectionStage,
    WorkloadFamily,
    _TimedObservation,
    _admission_gate_factory,
    _build_current_writer,
    _build_validation_runtime,
    aggregate_batch_rates,
    aggregate_invocations,
    batch_completion_rates,
    batch_record_to_dict,
    batch_records_to_jsonl,
    classify_cohort,
    generate_fixed_schedule,
    invocation_record_from_timed_observation,
    invocation_record_to_dict,
    invocation_records_to_jsonl,
    prepare_invocation_specs,
    validate_recorded_run,
)


class _FakeFailure(RuntimeError):
    pass


class _EnumValue:
    def __init__(self, value: str) -> None:
        self.value = value


class _Recorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def record(self, kind: str, **details: Any) -> int:
        with self._lock:
            sequence = len(self.events)
            self.events.append({"sequence": sequence, "kind": kind, **details})
            return sequence


class _FakeConnection:
    def __init__(self, *, worker_level: int, lane_index: int) -> None:
        self.worker_level = worker_level
        self.lane_index = lane_index


class _FakeWriter:
    def __init__(
        self,
        *,
        database: "_FakeDatabase",
        connection: _FakeConnection,
        composition: Composition,
    ) -> None:
        self.database = database
        self.connection = connection
        self.composition = composition

    def create_order_with_measurement(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> Any:
        return self.database.execute(
            connection=self.connection,
            composition=self.composition,
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )


class _FakeDatabase:
    def __init__(
        self,
        recorder: _Recorder,
        *,
        invalid_coordinate: tuple[int, int, int] | None = None,
        invalid_kind: str | None = None,
    ) -> None:
        self.recorder = recorder
        self.invalid_coordinate = invalid_coordinate
        self.invalid_kind = invalid_kind
        self._lock = threading.Lock()
        self.accepted_orders: set[str] = set()
        self.current_plan = None
        self.calls: list[dict[str, Any]] = []
        self.request_counts: Counter[str] = Counter()
        self.reset_count = 0

    def reset(self, worker_level: int) -> None:
        with self._lock:
            self.accepted_orders.clear()
            self.reset_count += 1
        self.recorder.record("reset", worker_level=worker_level)

    def prepare(self, plan: Any, specs: tuple[Any, ...]) -> None:
        with self._lock:
            self.current_plan = plan
            assert not self.accepted_orders.intersection(
                {spec.order_id for spec in specs}
            )
        self.recorder.record(
            "prepare",
            plan_index=plan.plan_index,
            cell_index=plan.cell.cell_index,
            batch_index=plan.batch_index,
            recorded=plan.recorded,
            worker_level=plan.cell.worker_level,
        )

    def execute(
        self,
        *,
        connection: _FakeConnection,
        composition: Composition,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> Any:
        plan = self.current_plan
        assert plan is not None
        assert amount == Decimal("100.00")
        coordinate = (
            plan.cell.cell_index,
            plan.batch_index,
            connection.lane_index,
        )
        self.recorder.record(
            "invoke",
            plan_index=plan.plan_index,
            lane_index=connection.lane_index,
            worker_level=connection.worker_level,
            composition=composition.value,
            thread_id=threading.get_ident(),
        )
        with self._lock:
            self.calls.append(
                {
                    "plan_index": plan.plan_index,
                    "recorded": plan.recorded,
                    "cell_index": plan.cell.cell_index,
                    "batch_index": plan.batch_index,
                    "lane_index": connection.lane_index,
                    "worker_level": connection.worker_level,
                    "request_id": request_id,
                    "order_id": order_id,
                    "thread_id": threading.get_ident(),
                }
            )
            self.request_counts[request_id] += 1
            is_target = (
                plan.recorded
                and self.invalid_coordinate is not None
                and coordinate == self.invalid_coordinate
            )
            if is_target and self.invalid_kind == "exception":
                raise _FakeFailure("message must never enter evidence")
            if is_target and self.invalid_kind == "unsupported":
                return _delivery("UNSUPPORTED", composition=composition)
            if is_target and self.invalid_kind == "unavailable":
                return _delivery(
                    "ACCEPTED",
                    composition=composition,
                    availability="UNAVAILABLE",
                )
            if is_target and self.invalid_kind == "missing_phase":
                return _delivery(
                    "ACCEPTED",
                    composition=composition,
                    missing_phase="business_uow",
                )

            if order_id not in self.accepted_orders:
                self.accepted_orders.add(order_id)
                return _delivery("ACCEPTED", composition=composition)
            if composition is Composition.PRE_OCC:
                return _delivery("STALE_WRITE", composition=composition)
            return _delivery("LOCK_TIMEOUT", composition=composition)


class _FakeTimingSource:
    def __init__(self, plan: Any, recorder: _Recorder) -> None:
        self.plan = plan
        self.recorder = recorder
        self.reference = plan.plan_index * 10_000 + 1_000

    def release_reference_ns(self) -> int:
        self.recorder.record(
            "release",
            plan_index=self.plan.plan_index,
            reference_ns=self.reference,
        )
        return self.reference

    def invocation_start_ns(self, lane_index: int) -> int:
        reading = self.reference + 10 + lane_index * 10
        self.recorder.record(
            "start",
            plan_index=self.plan.plan_index,
            lane_index=lane_index,
            reading=reading,
        )
        return reading

    def invocation_stop_ns(self, lane_index: int) -> int:
        reading = self.reference + 110 + lane_index * 13
        self.recorder.record(
            "stop",
            plan_index=self.plan.plan_index,
            lane_index=lane_index,
            reading=reading,
        )
        return reading


class _FakeRuntimeProvider:
    def __init__(
        self,
        *,
        invalid_coordinate: tuple[int, int, int] | None = None,
        invalid_kind: str | None = None,
    ) -> None:
        self.recorder = _Recorder()
        self.database = _FakeDatabase(
            self.recorder,
            invalid_coordinate=invalid_coordinate,
            invalid_kind=invalid_kind,
        )
        self.open_counts: Counter[int] = Counter()
        self.close_counts: Counter[int] = Counter()
        self.connection_count = 0

    @contextmanager
    def open(self, worker_level: int):
        self.open_counts[worker_level] += 1
        connections: list[_FakeConnection] = []
        for lane_index in range(worker_level):
            connection = _FakeConnection(
                worker_level=worker_level,
                lane_index=lane_index,
            )
            connections.append(connection)
            self.connection_count += 1
            self.recorder.record(
                "connection_constructed",
                worker_level=worker_level,
                lane_index=lane_index,
            )
        lanes = tuple(
            LaneRuntime(
                lane_index=lane_index,
                connection=connection,
                writers={
                    composition: _FakeWriter(
                        database=self.database,
                        connection=connection,
                        composition=composition,
                    )
                    for composition in Composition
                },
            )
            for lane_index, connection in enumerate(connections)
        )
        runtime = LevelRuntime(
            worker_level=worker_level,
            lanes=lanes,
            reset_database=lambda: self.database.reset(worker_level),
            prepare_batch=self.database.prepare,
            verify_observation=lambda connection, value, spec: self.recorder.record(
                "verify_observation",
                plan_index=spec.plan.plan_index,
                lane_index=spec.lane_index,
                worker_level=connection.worker_level,
            ),
            verify_connection=lambda connection: self.recorder.record(
                "verify_connection",
                plan_index=self.database.current_plan.plan_index,
                lane_index=connection.lane_index,
                worker_level=connection.worker_level,
            ),
            topology_label="deterministic-fake",
        )
        try:
            yield runtime
        finally:
            self.close_counts[worker_level] += 1
            self.recorder.record("connections_closed", worker_level=worker_level)

    def timing_source(self, plan: Any) -> _FakeTimingSource:
        return _FakeTimingSource(plan, self.recorder)


def _measurement(
    *,
    composition: Composition,
    cohort: Cohort,
    missing_phase: str | None = None,
    phase_state_overrides: dict[str, PhaseState] | None = None,
) -> Any:
    expected = EXPECTED_PHASE_STATE_MATRICES[(composition, cohort)]
    overrides = phase_state_overrides or {}
    values = {}
    for index, name in enumerate(PR3_PHASE_NAMES):
        if name == missing_phase:
            continue
        state = overrides.get(name, expected[name])
        values[name] = SimpleNamespace(
            state=_EnumValue(state.value),
            elapsed_ns=index + 1 if state is PhaseState.MEASURED else None,
        )
    return SimpleNamespace(**values)


def _delivery(
    kind: str,
    *,
    composition: Composition,
    availability: str = "AVAILABLE",
    missing_phase: str | None = None,
    phase_state_overrides: dict[str, PhaseState] | None = None,
) -> Any:
    if kind == "ACCEPTED":
        cohort = Cohort.ACCEPTED
        producer = SimpleNamespace(
            outcome=_EnumValue("ACCEPTED"),
            stream_admission_result=SimpleNamespace(
                verdict=_EnumValue("ADMITTED")
            ),
            admission_result=SimpleNamespace(verdict=_EnumValue("ADMITTED")),
        )
    elif kind == "STALE_WRITE":
        cohort = Cohort.APPEND_STALE_WRITE
        producer = SimpleNamespace(
            outcome=_EnumValue("ADMISSION_REJECTED"),
            stream_admission_result=SimpleNamespace(
                verdict=_EnumValue("ADMITTED")
            ),
            admission_result=SimpleNamespace(
                verdict=_EnumValue("STALE_WRITE")
            ),
        )
    elif kind == "LOCK_TIMEOUT":
        cohort = Cohort.PREPARE_LOCK_TIMEOUT
        producer = SimpleNamespace(
            outcome=_EnumValue("ADMISSION_REJECTED"),
            stream_admission_result=SimpleNamespace(
                verdict=_EnumValue("LOCK_TIMEOUT")
            ),
            admission_result=None,
        )
    else:
        cohort = Cohort.ACCEPTED
        producer = SimpleNamespace(
            outcome=_EnumValue("REPLAY"),
            stream_admission_result=None,
            admission_result=None,
        )
    return SimpleNamespace(
        availability=_EnumValue(availability),
        measurement=(
            _measurement(
                composition=composition,
                cohort=cohort,
                missing_phase=missing_phase,
                phase_state_overrides=phase_state_overrides,
            )
            if availability == "AVAILABLE"
            else None
        ),
        producer_value=producer,
    )


@pytest.fixture(scope="module")
def fixed_schedule() -> ExperimentSchedule:
    return generate_fixed_schedule()


@pytest.fixture(scope="module")
def valid_execution() -> tuple[_FakeRuntimeProvider, Any]:
    provider = _FakeRuntimeProvider()
    result = RecordedScheduleExecutor(
        open_level_runtime=provider.open,
        timing_source_factory=provider.timing_source,
    ).execute(
        run_id="pr7-deterministic-valid",
        schedule=generate_fixed_schedule(),
    )
    return provider, result


def _first_recorded_plan(schedule: ExperimentSchedule) -> Any:
    return next(plan for plan in schedule.batches if plan.recorded)


def _record_from_delivery(
    delivery: Any,
    *,
    family: WorkloadFamily = WorkloadFamily.SAME_ORDER_HOT_STREAM,
    composition: Composition = Composition.PRE_OCC,
) -> InvocationRecord:
    schedule = generate_fixed_schedule()
    original = next(
        plan
        for plan in schedule.recorded_batches
        if plan.cell.workload_family is family
        and plan.cell.composition is composition
    )
    spec = prepare_invocation_specs(run_id="unit-record", plan=original)[0]
    observation = _TimedObservation(
        value=delivery,
        invocation_start_ns=1_010,
        invocation_stop_ns=1_110,
    )
    return invocation_record_from_timed_observation(
        run_id="unit-record",
        invocation_index=0,
        spec=spec,
        observation=observation,
        release_reference_ns=1_000,
    )


_PHASE_MATRIX_CASES = (
    (
        Composition.PRE_OCC,
        "ACCEPTED",
        Cohort.ACCEPTED,
        frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "validation_runtime_call",
                "preliminary_idempotency_check",
                "preliminary_read_cleanup",
                "authoritative_idempotency_check",
                "accepted_history_load",
                "concurrency_preparation_call",
                "append_admission_call",
                "idempotency_record_call",
                "commit_finalization",
            }
        ),
        frozenset({"pessimistic_advisory_try_lock_call"}),
        frozenset({"rollback_finalization"}),
    ),
    (
        Composition.PRE_OCC,
        "STALE_WRITE",
        Cohort.APPEND_STALE_WRITE,
        frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "validation_runtime_call",
                "preliminary_idempotency_check",
                "preliminary_read_cleanup",
                "authoritative_idempotency_check",
                "accepted_history_load",
                "concurrency_preparation_call",
                "append_admission_call",
                "rollback_finalization",
            }
        ),
        frozenset({"pessimistic_advisory_try_lock_call"}),
        frozenset({"idempotency_record_call", "commit_finalization"}),
    ),
    (
        Composition.IN_PESSIMISTIC,
        "ACCEPTED",
        Cohort.ACCEPTED,
        frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "validation_runtime_call",
                "authoritative_idempotency_check",
                "accepted_history_load",
                "concurrency_preparation_call",
                "pessimistic_advisory_try_lock_call",
                "append_admission_call",
                "idempotency_record_call",
                "commit_finalization",
            }
        ),
        frozenset(
            {"preliminary_idempotency_check", "preliminary_read_cleanup"}
        ),
        frozenset({"rollback_finalization"}),
    ),
    (
        Composition.IN_PESSIMISTIC,
        "LOCK_TIMEOUT",
        Cohort.PREPARE_LOCK_TIMEOUT,
        frozenset(
            {
                "producer_write_invocation",
                "business_uow",
                "authoritative_idempotency_check",
                "concurrency_preparation_call",
                "pessimistic_advisory_try_lock_call",
                "rollback_finalization",
            }
        ),
        frozenset(
            {"preliminary_idempotency_check", "preliminary_read_cleanup"}
        ),
        frozenset(
            {
                "validation_runtime_call",
                "accepted_history_load",
                "append_admission_call",
                "idempotency_record_call",
                "commit_finalization",
            }
        ),
    ),
)


def test_constants_freeze_only_reviewed_pr7_scope() -> None:
    assert RETAINED_WORKER_LEVELS == (1, 2, 4, 8)
    assert not hasattr(runtime_module, "CANDIDATE_WORKER_LEVELS")
    assert tuple(Composition) == (
        Composition.PRE_OCC,
        Composition.IN_PESSIMISTIC,
    )
    assert tuple(WorkloadFamily) == (
        WorkloadFamily.SAME_ORDER_HOT_STREAM,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY,
    )
    assert WARMUP_BATCHES_PER_CELL == 3
    assert RECORDED_BATCHES_PER_CELL == 30
    assert RECORDED_SCHEDULE_SEED == 73
    assert set(EXPECTED_PHASE_STATE_MATRICES) == {
        (Composition.PRE_OCC, Cohort.ACCEPTED),
        (Composition.PRE_OCC, Cohort.APPEND_STALE_WRITE),
        (Composition.IN_PESSIMISTIC, Cohort.ACCEPTED),
        (Composition.IN_PESSIMISTIC, Cohort.PREPARE_LOCK_TIMEOUT),
    }


def test_schedule_generation_is_independent_of_preflight_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_schedule = generate_fixed_schedule()
    assert preflight_module.CANDIDATE_WORKER_LEVELS == (1, 2, 4, 8)

    # Candidate discovery belongs to preflight; the runtime consumes only the
    # already reviewed retained set, even if candidate planning later differs.
    monkeypatch.setattr(preflight_module, "CANDIDATE_WORKER_LEVELS", (1,))

    assert RETAINED_WORKER_LEVELS == (1, 2, 4, 8)
    assert generate_fixed_schedule() == reviewed_schedule


def test_fixed_schedule_has_exact_cells_and_batch_counts(
    fixed_schedule: ExperimentSchedule,
) -> None:
    assert len(fixed_schedule.cells) == EXACT_CELL_COUNT == 16
    assert len(fixed_schedule.batches) == 16 * (3 + 30) == 528
    assert len(fixed_schedule.recorded_batches) == 16 * 30 == 480
    assert Counter(
        (
            cell.worker_level,
            cell.workload_family,
            cell.composition,
        )
        for cell in fixed_schedule.cells
    ) == Counter(
        (level, family, composition)
        for level in RETAINED_WORKER_LEVELS
        for family in WorkloadFamily
        for composition in Composition
    )
    for cell in fixed_schedule.cells:
        cell_batches = [
            batch for batch in fixed_schedule.batches if batch.cell == cell
        ]
        assert sum(not batch.recorded for batch in cell_batches) == 3
        assert sum(batch.recorded for batch in cell_batches) == 30


def test_schedule_is_deterministic_and_has_one_exact_seeded_order(
    fixed_schedule: ExperimentSchedule,
) -> None:
    assert generate_fixed_schedule(seed=73) == fixed_schedule
    assert generate_fixed_schedule(seed=71) != fixed_schedule
    assert [
        (
            cell.worker_level,
            cell.workload_family.value,
            cell.composition.value,
        )
        for cell in fixed_schedule.cells
    ] == [
        (8, "SAME_ORDER_HOT_STREAM", "PRE_OCC"),
        (8, "SAME_ORDER_HOT_STREAM", "IN_PESSIMISTIC"),
        (8, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "IN_PESSIMISTIC"),
        (8, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "PRE_OCC"),
        (2, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "PRE_OCC"),
        (2, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "IN_PESSIMISTIC"),
        (2, "SAME_ORDER_HOT_STREAM", "IN_PESSIMISTIC"),
        (2, "SAME_ORDER_HOT_STREAM", "PRE_OCC"),
        (1, "SAME_ORDER_HOT_STREAM", "PRE_OCC"),
        (1, "SAME_ORDER_HOT_STREAM", "IN_PESSIMISTIC"),
        (1, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "IN_PESSIMISTIC"),
        (1, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "PRE_OCC"),
        (4, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "PRE_OCC"),
        (4, "DIFFERENT_ORDER_GENERAL_CONCURRENCY", "IN_PESSIMISTIC"),
        (4, "SAME_ORDER_HOT_STREAM", "IN_PESSIMISTIC"),
        (4, "SAME_ORDER_HOT_STREAM", "PRE_OCC"),
    ]


def test_schedule_balances_workload_and_composition_first_order(
    fixed_schedule: ExperimentSchedule,
) -> None:
    first_workload_by_level = {
        level: next(
            cell.workload_family
            for cell in fixed_schedule.cells
            if cell.worker_level == level
        )
        for level in RETAINED_WORKER_LEVELS
    }
    assert Counter(first_workload_by_level.values()) == {
        WorkloadFamily.SAME_ORDER_HOT_STREAM: 2,
        WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY: 2,
    }
    first_compositions = Counter(
        (cell.workload_family, cell.composition)
        for cell in fixed_schedule.cells
        if cell.composition_order_position == 0
    )
    for family in WorkloadFamily:
        assert first_compositions[(family, Composition.PRE_OCC)] == 2
        assert first_compositions[(family, Composition.IN_PESSIMISTIC)] == 2


def test_lane_identity_rotation_is_deterministic_and_balanced(
    fixed_schedule: ExperimentSchedule,
) -> None:
    for cell in fixed_schedule.cells:
        recorded = [
            plan
            for plan in fixed_schedule.recorded_batches
            if plan.cell == cell
        ]
        assignments: dict[int, list[int]] = defaultdict(list)
        for plan in recorded:
            for spec in prepare_invocation_specs(run_id="rotation", plan=plan):
                assignments[spec.lane_index].append(spec.identity_position)
        for values in assignments.values():
            counts = Counter(values)
            assert set(counts) == set(range(cell.worker_level))
            assert max(counts.values()) - min(counts.values()) <= 1


def test_workload_identity_rules_are_never_pooled(
    fixed_schedule: ExperimentSchedule,
) -> None:
    same = next(
        plan
        for plan in fixed_schedule.recorded_batches
        if plan.cell.worker_level == 8
        and plan.cell.workload_family is WorkloadFamily.SAME_ORDER_HOT_STREAM
    )
    different = next(
        plan
        for plan in fixed_schedule.recorded_batches
        if plan.cell.worker_level == 8
        and plan.cell.workload_family
        is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
    )
    same_specs = prepare_invocation_specs(run_id="identities", plan=same)
    different_specs = prepare_invocation_specs(run_id="identities", plan=different)
    assert len({spec.request_id for spec in same_specs}) == 8
    assert len({spec.order_id for spec in same_specs}) == 1
    assert len({spec.request_id for spec in different_specs}) == 8
    assert len({spec.order_id for spec in different_specs}) == 8


def test_level_runtime_requires_n_distinct_persistent_connections() -> None:
    connection = _FakeConnection(worker_level=2, lane_index=0)
    writers = {
        composition: _FakeWriter(
            database=_FakeDatabase(_Recorder()),
            connection=connection,
            composition=composition,
        )
        for composition in Composition
    }
    with pytest.raises(ValueError, match="exactly N"):
        LevelRuntime(
            worker_level=2,
            lanes=(LaneRuntime(0, connection, writers),),
            reset_database=lambda: None,
            prepare_batch=lambda plan, specs: None,
            verify_observation=lambda connection, value, spec: None,
            verify_connection=lambda connection: None,
        )
    with pytest.raises(ValueError, match="cannot share"):
        LevelRuntime(
            worker_level=2,
            lanes=(
                LaneRuntime(0, connection, writers),
                LaneRuntime(1, connection, writers),
            ),
            reset_database=lambda: None,
            prepare_batch=lambda plan, specs: None,
            verify_observation=lambda connection, value, spec: None,
            verify_connection=lambda connection: None,
        )


def test_valid_executor_consumes_exact_fixed_accounting(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    provider, result = valid_execution
    assert result.validation.status is EvidenceStatus.VALID
    assert result.validation.issues == ()
    assert len(result.invocations) == 1_800
    assert len(result.batches) == 480
    assert len(result.ownership) == sum(RETAINED_WORKER_LEVELS) == 15
    assert provider.open_counts == Counter({1: 1, 2: 1, 4: 1, 8: 1})
    assert provider.close_counts == provider.open_counts
    assert provider.connection_count == 15
    assert len(provider.database.calls) == 1_980
    assert set(provider.database.request_counts.values()) == {1}
    assert all(batch.completed_count == batch.worker_level for batch in result.batches)


def test_executor_uses_one_persistent_thread_and_connection_per_lane(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    provider, result = valid_execution
    ownership = {
        (item.worker_level, item.lane_index): item.thread_id
        for item in result.ownership
    }
    observed_threads: dict[tuple[int, int], set[int]] = defaultdict(set)
    for call in provider.database.calls:
        observed_threads[(call["worker_level"], call["lane_index"])].add(
            call["thread_id"]
        )
    assert set(observed_threads) == set(ownership)
    for key, thread_ids in observed_threads.items():
        assert thread_ids == {ownership[key]}
    assert all(
        record.connection_slot == record.lane_index
        for record in result.invocations
    )


def test_connections_are_constructed_before_warmup_and_never_in_timed_scope(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    provider, _result = valid_execution
    events = provider.recorder.events
    for level in RETAINED_WORKER_LEVELS:
        construction = [
            event
            for event in events
            if event["kind"] == "connection_constructed"
            and event["worker_level"] == level
        ]
        first_prepare = next(
            event
            for event in events
            if event["kind"] == "prepare" and event["worker_level"] == level
        )
        assert len(construction) == level
        assert max(event["sequence"] for event in construction) < first_prepare["sequence"]
    construction_sequences = {
        event["sequence"]
        for event in events
        if event["kind"] == "connection_constructed"
    }
    for release in (event for event in events if event["kind"] == "release"):
        last_stop = max(
            event["sequence"]
            for event in events
            if event["kind"] == "stop"
            and event["plan_index"] == release["plan_index"]
        )
        assert not any(
            release["sequence"] < sequence < last_stop
            for sequence in construction_sequences
        )


def test_barrier_timing_has_one_reference_offsets_and_last_completion(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    provider, result = valid_execution
    plan = _first_recorded_plan(result.schedule)
    batch = next(
        item
        for item in result.batches
        if item.cell_index == plan.cell.cell_index
        and item.batch_index == plan.batch_index
    )
    records = [
        record
        for record in result.invocations
        if record.cell_index == plan.cell.cell_index
        and record.batch_index == plan.batch_index
    ]
    plan_events = [
        event
        for event in provider.recorder.events
        if event.get("plan_index") == plan.plan_index
    ]
    assert [event["kind"] for event in plan_events].count("release") == 1
    release_sequence = next(
        event["sequence"] for event in plan_events if event["kind"] == "release"
    )
    assert all(
        release_sequence
        < next(
            event["sequence"]
            for event in plan_events
            if event["kind"] == "start" and event["lane_index"] == lane
        )
        < next(
            event["sequence"]
            for event in plan_events
            if event["kind"] == "invoke" and event["lane_index"] == lane
        )
        < next(
            event["sequence"]
            for event in plan_events
            if event["kind"] == "stop" and event["lane_index"] == lane
        )
        for lane in range(plan.cell.worker_level)
    )
    assert max(
        event["sequence"] for event in plan_events if event["kind"] == "stop"
    ) < min(
        event["sequence"]
        for event in plan_events
        if event["kind"].startswith("verify")
    )
    assert batch.release_reference_ns == plan.plan_index * 10_000 + 1_000
    assert [record.start_offset_ns for record in records] == [
        10 + lane * 10 for lane in range(plan.cell.worker_level)
    ]
    assert batch.first_start_offset_ns == 10
    assert batch.last_start_offset_ns == 10 + (plan.cell.worker_level - 1) * 10
    assert batch.batch_elapsed_ns == 110 + (plan.cell.worker_level - 1) * 13


def test_each_planned_batch_is_prepared_and_consumed_once(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    provider, result = valid_execution
    prepared = Counter(
        event["plan_index"]
        for event in provider.recorder.events
        if event["kind"] == "prepare"
    )
    assert prepared == Counter(plan.plan_index for plan in result.schedule.batches)
    assert set(prepared.values()) == {1}
    assert provider.database.reset_count == 32


@pytest.mark.parametrize(
    ("outcome", "stage", "stream", "append", "expected"),
    (
        ("ACCEPTED", None, "ADMITTED", "ADMITTED", Cohort.ACCEPTED),
        (
            "ADMISSION_REJECTED",
            RejectionStage.APPEND,
            "ADMITTED",
            "STALE_WRITE",
            Cohort.APPEND_STALE_WRITE,
        ),
        (
            "ADMISSION_REJECTED",
            RejectionStage.PREPARE_STREAM,
            "LOCK_TIMEOUT",
            None,
            Cohort.PREPARE_LOCK_TIMEOUT,
        ),
    ),
)
def test_exact_cohort_classifier(
    outcome: str,
    stage: RejectionStage | None,
    stream: str | None,
    append: str | None,
    expected: Cohort,
) -> None:
    assert classify_cohort(
        producer_outcome=outcome,
        rejection_stage=stage,
        stream_admission_verdict=stream,
        append_admission_verdict=append,
    ) is expected


def test_classifier_rejects_unsupported_normal_combination() -> None:
    with pytest.raises(BoundedConcurrencyRuntimeError):
        classify_cohort(
            producer_outcome="REPLAY",
            rejection_stage=None,
            stream_admission_verdict=None,
            append_admission_verdict=None,
        )


@pytest.mark.parametrize(
    ("composition", "kind", "cohort", "measured", "not_applicable", "not_reached"),
    _PHASE_MATRIX_CASES,
)
def test_supported_cohorts_preserve_exact_thirteen_phase_matrix(
    composition: Composition,
    kind: str,
    cohort: Cohort,
    measured: frozenset[str],
    not_applicable: frozenset[str],
    not_reached: frozenset[str],
) -> None:
    assert measured.isdisjoint(not_applicable)
    assert measured.isdisjoint(not_reached)
    assert not_applicable.isdisjoint(not_reached)
    assert measured | not_applicable | not_reached == set(PR3_PHASE_NAMES)
    expected = {
        name: (
            PhaseState.MEASURED
            if name in measured
            else (
                PhaseState.NOT_APPLICABLE
                if name in not_applicable
                else PhaseState.NOT_REACHED
            )
        )
        for name in PR3_PHASE_NAMES
    }
    assert dict(EXPECTED_PHASE_STATE_MATRICES[(composition, cohort)]) == expected

    record = _record_from_delivery(
        _delivery(kind, composition=composition),
        composition=composition,
    )
    assert record.cohort is cohort
    assert record.measurement_availability == "AVAILABLE"
    assert tuple(phase.name for phase in record.phases or ()) == PR3_PHASE_NAMES
    assert {phase.name: phase.state for phase in record.phases or ()} == expected
    for phase in record.phases or ():
        if phase.state is PhaseState.MEASURED:
            assert phase.elapsed_ns is not None
        else:
            assert phase.elapsed_ns is None


@pytest.mark.parametrize(
    ("composition", "cohort", "phase_name", "expected_state"),
    (
        (
            Composition.PRE_OCC,
            Cohort.ACCEPTED,
            "pessimistic_advisory_try_lock_call",
            PhaseState.NOT_APPLICABLE,
        ),
        (
            Composition.PRE_OCC,
            Cohort.APPEND_STALE_WRITE,
            "idempotency_record_call",
            PhaseState.NOT_REACHED,
        ),
        (
            Composition.IN_PESSIMISTIC,
            Cohort.ACCEPTED,
            "preliminary_idempotency_check",
            PhaseState.NOT_APPLICABLE,
        ),
        (
            Composition.IN_PESSIMISTIC,
            Cohort.PREPARE_LOCK_TIMEOUT,
            "validation_runtime_call",
            PhaseState.NOT_REACHED,
        ),
    ),
)
def test_unexpected_extra_measured_phase_invalidates_run(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
    composition: Composition,
    cohort: Cohort,
    phase_name: str,
    expected_state: PhaseState,
) -> None:
    _provider, result = valid_execution
    original = next(
        record
        for record in result.invocations
        if record.composition is composition and record.cohort is cohort
    )
    assert EXPECTED_PHASE_STATE_MATRICES[(composition, cohort)][phase_name] is (
        expected_state
    )
    altered_phases = tuple(
        PhaseRecord(
            name=phase.name,
            state=PhaseState.MEASURED,
            elapsed_ns=999,
        )
        if phase.name == phase_name
        else phase
        for phase in original.phases or ()
    )
    altered = replace(original, phases=altered_phases)
    invocations = tuple(
        altered if record is original else record for record in result.invocations
    )

    validation = validate_recorded_run(
        schedule=result.schedule,
        invocations=invocations,
        batches=result.batches,
        ownership=result.ownership,
    )

    assert validation.status is EvidenceStatus.INVALID_RUN
    matching = [
        issue
        for issue in validation.issues
        if issue.code == "PHASE_STATE_MISMATCH" and f"phase={phase_name}" in issue.detail
    ]
    assert len(matching) == 1
    assert f"cell={original.cell_index}" in matching[0].detail
    assert f"batch={original.batch_index}" in matching[0].detail
    assert f"lane={original.lane_index}" in matching[0].detail
    assert f"expected={expected_state.value}" in matching[0].detail
    assert "observed=MEASURED" in matching[0].detail


@pytest.mark.parametrize(
    ("invalid_kind", "issue_code"),
    (
        ("exception", "UNEXPECTED_EXCEPTION"),
        ("unsupported", "UNSUPPORTED_OUTCOME"),
        ("unavailable", "MEASUREMENT_UNAVAILABLE"),
        ("missing_phase", "MISSING_PHASE_RECORD"),
    ),
)
def test_invalid_observation_invalidates_without_retry_or_replacement(
    invalid_kind: str,
    issue_code: str,
) -> None:
    schedule = generate_fixed_schedule()
    target_plan = next(
        plan
        for plan in schedule.recorded_batches
        if plan.cell.workload_family
        is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
    )
    target = (target_plan.cell.cell_index, target_plan.batch_index, 0)
    provider = _FakeRuntimeProvider(
        invalid_coordinate=target,
        invalid_kind=invalid_kind,
    )
    result = RecordedScheduleExecutor(
        open_level_runtime=provider.open,
        timing_source_factory=provider.timing_source,
    ).execute(run_id=f"invalid-{invalid_kind}", schedule=schedule)
    assert result.validation.status is EvidenceStatus.INVALID_RUN
    assert issue_code in {issue.code for issue in result.validation.issues}
    assert len(result.invocations) == 1_800
    assert len(result.batches) == 480
    assert len(provider.database.calls) == 1_980
    assert set(provider.database.request_counts.values()) == {1}
    target_records = [
        record
        for record in result.invocations
        if (record.cell_index, record.batch_index, record.lane_index) == target
    ]
    assert len(target_records) == 1
    if invalid_kind == "exception":
        assert target_records[0].exception_type == "_FakeFailure"
        assert "message must never enter evidence" not in json.dumps(
            invocation_record_to_dict(target_records[0])
        )


def test_validation_detects_missing_duplicate_and_wrong_identity(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    missing = validate_recorded_run(
        schedule=result.schedule,
        invocations=result.invocations[:-1],
        batches=result.batches,
        ownership=result.ownership,
    )
    assert "MISSING_INVOCATION" in {issue.code for issue in missing.issues}

    duplicate = validate_recorded_run(
        schedule=result.schedule,
        invocations=(*result.invocations, result.invocations[0]),
        batches=result.batches,
        ownership=result.ownership,
    )
    assert "DUPLICATE_INVOCATION" in {issue.code for issue in duplicate.issues}

    wrong = replace(result.invocations[0], composition=Composition.IN_PESSIMISTIC)
    wrong_identity = validate_recorded_run(
        schedule=result.schedule,
        invocations=(wrong, *result.invocations[1:]),
        batches=result.batches,
        ownership=result.ownership,
    )
    assert "INVOCATION_PLAN_MISMATCH" in {
        issue.code for issue in wrong_identity.issues
    }


def test_validation_detects_completed_and_accepted_accounting(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    original = result.batches[0]
    assert original.worker_level == 8
    incomplete = replace(
        original,
        completed_count=7,
        accepted_count=min(original.accepted_count, 7),
        typed_outcome_counts=(
            replace(original.typed_outcome_counts[0], count=7),
        ),
    )
    invalid_completed = validate_recorded_run(
        schedule=result.schedule,
        invocations=result.invocations,
        batches=(incomplete, *result.batches[1:]),
        ownership=result.ownership,
    )
    assert "INCOMPLETE_BATCH" in {
        issue.code for issue in invalid_completed.issues
    }

    accepted_batch = next(
        batch
        for batch in result.batches
        if batch.workload_family
        is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
        and batch.accepted_count > 0
    )
    wrong_accepted = replace(
        accepted_batch,
        accepted_count=accepted_batch.accepted_count - 1,
    )
    batches = tuple(
        wrong_accepted if batch is accepted_batch else batch
        for batch in result.batches
    )
    invalid_accepted = validate_recorded_run(
        schedule=result.schedule,
        invocations=result.invocations,
        batches=batches,
        ownership=result.ownership,
    )
    assert "ACCEPTED_COUNT_MISMATCH" in {
        issue.code for issue in invalid_accepted.issues
    }


def test_executor_rejects_noncanonical_schedule_before_opening_resources(
    fixed_schedule: ExperimentSchedule,
) -> None:
    provider = _FakeRuntimeProvider()
    altered = replace(
        fixed_schedule,
        cells=tuple(reversed(fixed_schedule.cells)),
    )
    with pytest.raises(BoundedConcurrencyRuntimeError, match="exact deterministic"):
        RecordedScheduleExecutor(
            open_level_runtime=provider.open,
            timing_source_factory=provider.timing_source,
        ).execute(run_id="noncanonical", schedule=altered)
    assert provider.open_counts == Counter()
    assert provider.connection_count == 0


def test_validation_rejects_unplanned_adaptive_extension(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    extra = replace(
        result.invocations[-1],
        invocation_index=len(result.invocations),
        cell_index=99,
    )
    validation = validate_recorded_run(
        schedule=result.schedule,
        invocations=(*result.invocations, extra),
        batches=result.batches,
        ownership=result.ownership,
    )
    assert "UNPLANNED_INVOCATION" in {
        issue.code for issue in validation.issues
    }


def test_aggregation_keeps_exact_cohorts_and_workloads_separate(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    aggregates = aggregate_invocations(result.invocations)
    keys = [
        (
            item.worker_level,
            item.workload_family,
            item.composition,
            item.cohort,
        )
        for item in aggregates
    ]
    assert len(keys) == len(set(keys)) == 22
    assert any(key[-1] is Cohort.APPEND_STALE_WRITE for key in keys)
    assert any(key[-1] is Cohort.PREPARE_LOCK_TIMEOUT for key in keys)
    assert all(
        key[-1] is Cohort.ACCEPTED
        for key in keys
        if key[1] is WorkloadFamily.DIFFERENT_ORDER_GENERAL_CONCURRENCY
    )
    assert all(item.external_elapsed_ns.count > 0 for item in aggregates)


def test_batch_rates_are_protocol_qualified_and_group_to_16_cells(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    first = result.batches[0]
    rates = batch_completion_rates(first)
    assert rates.accepted_completion_rate_per_second == pytest.approx(
        first.accepted_count * 1_000_000_000 / first.batch_elapsed_ns
    )
    assert rates.all_completion_rate_per_second == pytest.approx(
        first.completed_count * 1_000_000_000 / first.batch_elapsed_ns
    )
    aggregates = aggregate_batch_rates(result.batches)
    assert len(aggregates) == 16
    assert all(
        item.accepted_completion_rate_per_second.count == 30
        and item.all_completion_rate_per_second.count == 30
        for item in aggregates
    )


def test_descriptive_model_omits_p95_and_rate_limit_derivation() -> None:
    statistic_fields = {item.name for item in fields(DescriptiveStatistics)}
    assert statistic_fields == {"count", "minimum", "maximum", "mean", "median"}
    assert "p95" not in statistic_fields
    assert not hasattr(runtime_module, "rate_limit")


def test_serialization_schema_is_stable_and_has_no_governance_ids(
    valid_execution: tuple[_FakeRuntimeProvider, Any],
) -> None:
    _provider, result = valid_execution
    invocation = invocation_record_to_dict(result.invocations[0])
    batch = batch_record_to_dict(result.batches[0])
    assert invocation["schema_name"] == LEVEL_C_SCHEMA_NAME
    assert invocation["schema_version"] == LEVEL_C_SCHEMA_VERSION
    assert batch["schema_name"] == LEVEL_C_SCHEMA_NAME
    assert batch["schema_version"] == LEVEL_C_SCHEMA_VERSION
    assert set(invocation) == {
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
    }
    assert "attempt_id" not in invocation
    assert "execution_id" not in invocation
    assert "attempt_id" not in batch
    assert "execution_id" not in batch
    invocation_jsonl = invocation_records_to_jsonl(result.invocations[:2])
    batch_jsonl = batch_records_to_jsonl(result.batches[:2])
    assert invocation_jsonl.endswith("\n")
    assert batch_jsonl.endswith("\n")
    assert len(invocation_jsonl.splitlines()) == 2
    assert len(batch_jsonl.splitlines()) == 2


def test_real_writer_factory_retains_fullproof_strict_pre_and_in_only() -> None:
    from src.compass.transition.types import ValidationMode
    from src.compass.transition.validators import FullProofValidator
    from src.pipeline.transactional.postgres_admission import (
        PostgresOptimisticAdmissionGate,
        PostgresPessimisticAdmissionGate,
    )
    from src.pipeline.transactional.postgres_write_side_config import (
        ValidationPlacement,
    )

    validation_runtime = _build_validation_runtime()
    assert type(validation_runtime.dispatcher.strict_validator) is FullProofValidator
    assert validation_runtime.mode is ValidationMode.STRICT

    connection = object()
    pre_writer = _build_current_writer(
        connection=connection,
        composition=Composition.PRE_OCC,
    )
    in_writer = _build_current_writer(
        connection=connection,
        composition=Composition.IN_PESSIMISTIC,
    )
    assert pre_writer._config.validation_placement is ValidationPlacement.PRE_TRANSACTION
    assert in_writer._config.validation_placement is ValidationPlacement.IN_TRANSACTION

    event_store = object()
    optimistic = _admission_gate_factory(Composition.PRE_OCC)(
        SimpleNamespace(event_store=event_store)
    )
    pessimistic = _admission_gate_factory(Composition.IN_PESSIMISTIC)(
        SimpleNamespace(connection=connection, event_store=event_store)
    )
    assert type(optimistic) is PostgresOptimisticAdmissionGate
    assert type(pessimistic) is PostgresPessimisticAdmissionGate
    assert optimistic.event_store is event_store
    assert pessimistic.connection is connection


def test_runtime_source_exposes_no_postgresql_execution_entry_point() -> None:
    assert not hasattr(runtime_module, "main")
    assert not hasattr(runtime_module, "write_evidence_directory")
    assert not hasattr(runtime_module, "run_canonical")
    assert not hasattr(runtime_module, "run_smoke")
    assert set(Composition) == {Composition.PRE_OCC, Composition.IN_PESSIMISTIC}
