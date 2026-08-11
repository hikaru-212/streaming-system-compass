"""Deterministic orchestration tests for the Stage 4B.2 PR6 runtime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
import inspect
import json
from pathlib import Path
import re
import threading
from types import SimpleNamespace
from typing import Any

import pytest

import experiments.stage4b2.postgres_strategy_comparison_runtime as runtime_module
from experiments.stage4b2.postgres_strategy_comparison import (
    PR3_PHASE_NAMES,
    Cohort,
    Composition,
    EvidenceStatus,
    ExperimentSchedule,
    ProtocolConfig,
    Scenario,
    Surface,
    TimedInvocation,
    build_environment_manifest,
    deterministic_sample_token,
    generate_recorded_schedule,
    samples_from_jsonl,
)
from experiments.stage4b2.postgres_strategy_comparison_runtime import (
    ConcurrentLaneRuntime,
    LockNonAcquisitionRuntime,
    RecordedRuntimeError,
    RecordedScheduleExecutor,
    RuntimeTopology,
    SequentialCompositionRuntime,
    _BatchStartReference,
    _OffsetClock,
    build_recorded_run_manifest,
    sample_from_timed_invocation,
    write_evidence_directory,
)


class _LateDomainError(RuntimeError):
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


class _Clock:
    def __init__(self, recorder: _Recorder) -> None:
        self._lock = threading.Lock()
        self._reading = 0
        self._recorder = recorder

    def __call__(self) -> int:
        with self._lock:
            self._reading += 10
            reading = self._reading
        self._recorder.record(
            "clock",
            reading=reading,
            thread_id=threading.get_ident(),
        )
        return reading


@dataclass
class _FakeConnection:
    name: str


class _FakeDatabase:
    def __init__(
        self,
        recorder: _Recorder,
        *,
        force_concurrent_accepted: bool = False,
    ) -> None:
        self.recorder = recorder
        self.force_concurrent_accepted = force_concurrent_accepted
        self._lock = threading.Lock()
        self.accepted: dict[str, Any] = {}
        self.locked_orders: set[str] = set()
        self.calls: list[dict[str, Any]] = []
        self.attempts: dict[str, int] = {}
        self.fail_requests: set[str] = set()
        self.reset_count = 0

    def reset(self) -> None:
        with self._lock:
            self.accepted.clear()
            self.locked_orders.clear()
            self.reset_count += 1
        self.recorder.record("reset")

    def execute(
        self,
        *,
        writer_name: str,
        composition: Composition,
        connection: _FakeConnection,
        method: str,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> Any:
        call = {
            "writer": writer_name,
            "composition": composition,
            "connection": connection.name,
            "method": method,
            "request_id": request_id,
            "order_id": order_id,
            "amount": amount,
            "thread_id": threading.get_ident(),
        }
        call["sequence"] = self.recorder.record("invoke", **call)
        with self._lock:
            self.calls.append(call)
            self.attempts[request_id] = self.attempts.get(request_id, 0) + 1
            if request_id in self.fail_requests:
                raise _LateDomainError("message must not enter evidence")
            locked = order_id in self.locked_orders
            prior_event = self.accepted.get(order_id)
            if locked:
                result = _producer_result("LOCK_TIMEOUT", request_id, order_id)
            elif prior_event is None:
                event = SimpleNamespace(
                    request_id=request_id,
                    order_id=order_id,
                    sequence=1,
                    amount=amount,
                )
                self.accepted[order_id] = event
                result = _producer_result("ACCEPTED", request_id, order_id, event)
            elif self.force_concurrent_accepted:
                event = SimpleNamespace(
                    request_id=request_id,
                    order_id=order_id,
                    sequence=1,
                    amount=amount,
                )
                result = _producer_result("ACCEPTED", request_id, order_id, event)
            elif composition is Composition.PRE_OCC:
                result = _producer_result("STALE_WRITE", request_id, order_id)
            else:
                result = _producer_result("LOCK_TIMEOUT", request_id, order_id)

        if method == "create_order_with_measurement":
            return _delivery(result)
        return result


class _FakeWriter:
    def __init__(
        self,
        *,
        name: str,
        composition: Composition,
        connection: _FakeConnection,
        database: _FakeDatabase,
    ) -> None:
        self.name = name
        self.composition = composition
        self.connection = connection
        self.database = database

    def create_order(self, *, request_id: str, order_id: str, amount: Decimal) -> Any:
        return self.database.execute(
            writer_name=self.name,
            composition=self.composition,
            connection=self.connection,
            method="create_order",
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )

    def create_order_with_measurement(
        self,
        *,
        request_id: str,
        order_id: str,
        amount: Decimal,
    ) -> Any:
        return self.database.execute(
            writer_name=self.name,
            composition=self.composition,
            connection=self.connection,
            method="create_order_with_measurement",
            request_id=request_id,
            order_id=order_id,
            amount=amount,
        )


def _producer_result(
    kind: str,
    request_id: str,
    order_id: str,
    event: Any | None = None,
) -> Any:
    if kind == "ACCEPTED":
        outcome = "ACCEPTED"
        stream = "ADMITTED"
        append = "ADMITTED"
    elif kind == "STALE_WRITE":
        outcome = "ADMISSION_REJECTED"
        stream = "ADMITTED"
        append = "STALE_WRITE"
    else:
        outcome = "ADMISSION_REJECTED"
        stream = "LOCK_TIMEOUT"
        append = None
    validation_decision = None
    if kind in {"ACCEPTED", "STALE_WRITE"}:
        validation_decision = SimpleNamespace(
            validation_result=SimpleNamespace(
                validator_name="FullProofValidator",
                validation_mode=SimpleNamespace(value="strict"),
            )
        )
    return SimpleNamespace(
        outcome=_EnumValue(outcome),
        accepted_event=event,
        stream_admission_result=SimpleNamespace(verdict=_EnumValue(stream)),
        admission_result=(
            None if append is None else SimpleNamespace(verdict=_EnumValue(append))
        ),
        validation_decision=validation_decision,
        request_id=request_id,
        order_id=order_id,
    )


def _delivery(
    result: Any,
    *,
    states: dict[str, tuple[str, int | None]] | None = None,
    availability: str = "AVAILABLE",
) -> Any:
    measurement = None
    if availability == "AVAILABLE":
        phases = {}
        for index, name in enumerate(PR3_PHASE_NAMES):
            state, elapsed = (
                states[name] if states is not None else ("MEASURED", index)
            )
            phases[name] = SimpleNamespace(
                state=_EnumValue(state),
                elapsed_ns=elapsed,
            )
        measurement = SimpleNamespace(**phases)
    return SimpleNamespace(
        producer_value=result,
        availability=_EnumValue(availability),
        measurement=measurement,
    )


def _small_protocol(
    *,
    b_batches: int = 1,
    b_minimum: int = 1,
) -> ProtocolConfig:
    return ProtocolConfig(
        sequential_warmup_cycles=1,
        concurrent_warmup_batches_per_composition=1,
        observer_schedule_repetitions=1,
        scenario_a_samples_per_surface_per_composition=6,
        scenario_b_batches_per_composition=b_batches,
        scenario_c_batches_per_composition=1,
        scenario_e_samples=1,
        scenario_b_core_cohort_minimum=b_minimum,
    )


@dataclass
class _ExecutionFixture:
    recorder: _Recorder
    clock: _Clock
    database: _FakeDatabase
    topology: RuntimeTopology
    schedule: ExperimentSchedule
    protocol: ProtocolConfig
    result: Any


def _fake_execution(
    *,
    force_concurrent_accepted: bool = False,
    fail_plan_index: int | None = None,
) -> _ExecutionFixture:
    recorder = _Recorder()
    clock = _Clock(recorder)
    database = _FakeDatabase(
        recorder,
        force_concurrent_accepted=force_concurrent_accepted,
    )
    protocol = _small_protocol()
    schedule = generate_recorded_schedule(protocol=protocol, seed=17)
    if fail_plan_index is not None:
        plan = schedule.samples[fail_plan_index]
        database.fail_requests.add(_request_id("runtime-test", plan))
    topology = _fake_topology(database)
    result = RecordedScheduleExecutor(topology=topology, clock=clock).execute(
        run_id="runtime-test",
        schedule=schedule,
        protocol=protocol,
    )
    return _ExecutionFixture(
        recorder=recorder,
        clock=clock,
        database=database,
        topology=topology,
        schedule=schedule,
        protocol=protocol,
        result=result,
    )


def _fake_topology(database: _FakeDatabase) -> RuntimeTopology:
    sequential: dict[Composition, SequentialCompositionRuntime] = {}
    for composition in Composition:
        connection = _FakeConnection(f"a-{composition.value}")
        sequential[composition] = SequentialCompositionRuntime(
            connection=connection,
            current_writer=_FakeWriter(
                name=f"current-{composition.value}",
                composition=composition,
                connection=connection,
                database=database,
            ),
            frozen_writer=_FakeWriter(
                name=f"frozen-{composition.value}",
                composition=composition,
                connection=connection,
                database=database,
            ),
        )
    lanes = []
    for slot in (0, 1):
        connection = _FakeConnection(f"lane-{slot}")
        lanes.append(
            ConcurrentLaneRuntime(
                connection_slot=slot,
                connection=connection,
                current_writers={
                    composition: _FakeWriter(
                        name=f"lane-{slot}-{composition.value}",
                        composition=composition,
                        connection=connection,
                        database=database,
                    )
                    for composition in Composition
                },
            )
        )
    measured_connection = _FakeConnection("scenario-e-measured")
    locker_connection = _FakeConnection("scenario-e-locker")

    def verify_connection(connection: _FakeConnection) -> None:
        database.recorder.record("idle_reuse", connection=connection.name)

    def verify_observation(
        connection: _FakeConnection,
        value: Any,
        surface: Surface,
        request_id: str,
        order_id: str,
    ) -> None:
        database.recorder.record(
            "verify_observation",
            connection=connection.name,
            surface=surface.value,
            request_id=request_id,
            order_id=order_id,
        )

    def acquire_lock(connection: _FakeConnection, order_id: str) -> None:
        database.recorder.record(
            "lock_acquire",
            connection=connection.name,
            order_id=order_id,
        )
        with database._lock:
            database.locked_orders.add(order_id)

    def release_lock(connection: _FakeConnection) -> None:
        database.recorder.record("lock_release", connection=connection.name)
        with database._lock:
            database.locked_orders.clear()

    return RuntimeTopology(
        sequential=sequential,
        concurrent_lanes=(lanes[0], lanes[1]),
        lock_non_acquisition=LockNonAcquisitionRuntime(
            measured_connection=measured_connection,
            measured_writer=_FakeWriter(
                name="scenario-e-IN_PESSIMISTIC",
                composition=Composition.IN_PESSIMISTIC,
                connection=measured_connection,
                database=database,
            ),
            locker_connection=locker_connection,
        ),
        reset_database=database.reset,
        verify_connection=verify_connection,
        verify_observation=verify_observation,
        acquire_lock=acquire_lock,
        release_lock=release_lock,
        postgresql_server_version="160003",
        isolation_level="READ_COMMITTED",
        autocommit=False,
    )


def _request_id(run_id: str, plan: Any) -> str:
    token = deterministic_sample_token(
        run_id=run_id,
        sample_index=plan.sample_index,
        lane_index=plan.lane_index,
        purpose="request",
    )
    return f"pr6-request-{token}"


def _call_by_request(execution: _ExecutionFixture, request_id: str) -> dict[str, Any]:
    calls = [call for call in execution.database.calls if call["request_id"] == request_id]
    assert len(calls) == 1
    return calls[0]


def _manifest(protocol: ProtocolConfig, schedule: ExperimentSchedule) -> Any:
    return build_environment_manifest(
        source_commit="a" * 40,
        source_tree_clean_before_run=True,
        topology_label="guarded-test-postgresql",
        schema_or_migration_identity="migrations-through-007",
        isolation_level="READ_COMMITTED",
        autocommit=False,
        connection_arrangement="fixed sanitized six-connection arrangement",
        schedule_seed=schedule.seed,
        protocol=protocol,
        postgresql_server_version="160003",
        psycopg_version="3.test",
        python_implementation="CPython",
        python_version="3.test",
        platform="test-platform",
        architecture="test-architecture",
    )


@pytest.fixture(scope="module")
def valid_execution() -> _ExecutionFixture:
    execution = _fake_execution()
    assert execution.result.validation.status is EvidenceStatus.VALID
    return execution


def test_scenario_a_executes_every_plan_exactly_once(
    valid_execution: _ExecutionFixture,
) -> None:
    plans = [
        plan
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.A_UNCONTENDED
    ]
    assert {
        sample.sample_index
        for sample in valid_execution.result.samples
        if sample.scenario is Scenario.A_UNCONTENDED
    } == {plan.sample_index for plan in plans}
    assert all(
        valid_execution.database.attempts[_request_id("runtime-test", plan)] == 1
        for plan in plans
    )


def test_scenario_a_surface_selects_frozen_current_and_measured_methods(
    valid_execution: _ExecutionFixture,
) -> None:
    for plan in valid_execution.schedule.samples:
        if plan.scenario is not Scenario.A_UNCONTENDED:
            continue
        call = _call_by_request(
            valid_execution,
            _request_id("runtime-test", plan),
        )
        expected_prefix = (
            "frozen" if plan.surface is Surface.FROZEN_BASELINE else "current"
        )
        assert call["writer"] == f"{expected_prefix}-{plan.composition.value}"
        assert call["method"] == (
            "create_order_with_measurement"
            if plan.surface is Surface.CURRENT_MEASURED
            else "create_order"
        )


def test_current_measured_conversion_copies_all_thirteen_states_and_values() -> None:
    protocol = _small_protocol()
    plan = next(
        plan
        for plan in generate_recorded_schedule(protocol=protocol, seed=1).samples
        if plan.surface is Surface.CURRENT_MEASURED
    )
    state_names = ("MEASURED", "NOT_APPLICABLE", "NOT_REACHED", "NOT_COLLECTED")
    states = {
        name: (
            state_names[index % len(state_names)],
            index if state_names[index % len(state_names)] == "MEASURED" else None,
        )
        for index, name in enumerate(PR3_PHASE_NAMES)
    }
    result = _producer_result(
        "ACCEPTED",
        "request",
        "order",
        SimpleNamespace(
            request_id="request",
            order_id="order",
            sequence=1,
            amount=Decimal("100.00"),
        ),
    )
    sample = sample_from_timed_invocation(
        run_id="copy-phases",
        plan=plan,
        timed=TimedInvocation(value=_delivery(result, states=states), elapsed_ns=41),
        start_offset_ns=None,
    )
    assert sample.phases is not None
    assert len(sample.phases) == 13
    assert tuple(
        (phase.name, phase.state.value, phase.elapsed_ns) for phase in sample.phases
    ) == tuple((name, *states[name]) for name in PR3_PHASE_NAMES)


def test_unavailable_measured_delivery_is_retained_without_fabricated_phases() -> None:
    plan = next(
        plan
        for plan in generate_recorded_schedule(
            protocol=_small_protocol(),
            seed=4,
        ).samples
        if plan.surface is Surface.CURRENT_MEASURED
    )
    result = _producer_result(
        "ACCEPTED",
        "request",
        "order",
        SimpleNamespace(
            request_id="request",
            order_id="order",
            sequence=1,
            amount=Decimal("100.00"),
        ),
    )
    sample = sample_from_timed_invocation(
        run_id="unavailable-measurement",
        plan=plan,
        timed=TimedInvocation(
            value=_delivery(result, availability="UNAVAILABLE"),
            elapsed_ns=11,
        ),
        start_offset_ns=None,
    )
    assert sample.measurement_availability == "UNAVAILABLE"
    assert sample.phases is None


@pytest.mark.parametrize(
    "surface",
    [Surface.FROZEN_BASELINE, Surface.CURRENT_UNMEASURED],
)
def test_unmeasured_and_frozen_conversion_retain_null_measurement(
    surface: Surface,
) -> None:
    plan = replace(
        generate_recorded_schedule(protocol=_small_protocol(), seed=2).samples[0],
        surface=surface,
    )
    result = _producer_result(
        "ACCEPTED",
        "request",
        "order",
        SimpleNamespace(
            request_id="request",
            order_id="order",
            sequence=1,
            amount=Decimal("100.00"),
        ),
    )
    sample = sample_from_timed_invocation(
        run_id="null-measurement",
        plan=plan,
        timed=TimedInvocation(value=result, elapsed_ns=7),
        start_offset_ns=None,
    )
    assert sample.measurement_availability is None
    assert sample.phases is None


def test_exception_conversion_retains_only_type_and_external_elapsed() -> None:
    plan = generate_recorded_schedule(protocol=_small_protocol(), seed=3).samples[0]
    sample = sample_from_timed_invocation(
        run_id="exception-conversion",
        plan=plan,
        timed=TimedInvocation(value=None, elapsed_ns=73, exception_type="LateDomainError"),
        start_offset_ns=None,
    )
    assert sample.external_elapsed_ns == 73
    assert sample.exception_type == "LateDomainError"
    assert sample.producer_outcome is None
    assert sample.cohort is None
    assert sample.measurement_availability is None
    assert sample.phases is None


def test_connection_idle_and_reuse_checks_occur_outside_timing(
    valid_execution: _ExecutionFixture,
) -> None:
    plan = next(
        plan
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.A_UNCONTENDED
    )
    call = _call_by_request(valid_execution, _request_id("runtime-test", plan))
    verification = next(
        event
        for event in valid_execution.recorder.events
        if event["kind"] == "verify_observation"
        and event["request_id"] == call["request_id"]
    )
    reuse = next(
        event
        for event in valid_execution.recorder.events[verification["sequence"] + 1 :]
        if event["kind"] == "idle_reuse"
        and event["connection"] == call["connection"]
    )
    clocks = [
        event
        for event in valid_execution.recorder.events
        if event["kind"] == "clock"
        and call["sequence"] < event["sequence"] < verification["sequence"]
    ]
    assert len(clocks) == 1
    assert call["sequence"] < clocks[0]["sequence"] < verification["sequence"]
    assert verification["sequence"] < reuse["sequence"]


def test_scenario_b_uses_exactly_two_persistent_lane_threads_and_connections(
    valid_execution: _ExecutionFixture,
) -> None:
    calls = [
        _call_by_request(valid_execution, _request_id("runtime-test", plan))
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.B_SAME_ORDER
    ]
    assert {call["connection"] for call in calls} == {"lane-0", "lane-1"}
    assert len({call["thread_id"] for call in calls}) == 2
    by_connection: dict[str, set[int]] = {}
    for call in calls:
        by_connection.setdefault(call["connection"], set()).add(call["thread_id"])
    assert all(len(thread_ids) == 1 for thread_ids in by_connection.values())


def test_concurrent_barrier_releases_before_both_external_timers() -> None:
    recorder = _Recorder()
    clock = _Clock(recorder)
    reference = _BatchStartReference(clock)
    barrier = threading.Barrier(2, action=reference.mark_release)
    offset_clocks = [
        _OffsetClock(clock=clock, reference=reference),
        _OffsetClock(clock=clock, reference=reference),
    ]
    invoked: list[int] = []

    def worker(lane: int) -> None:
        runtime_module.time_after_start_gate(
            wait_for_start=barrier.wait,
            invocation=lambda: invoked.append(lane) or lane,
            clock=offset_clocks[lane],
        )

    threads = [threading.Thread(target=worker, args=(lane,)) for lane in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert reference.reference_ns == 10
    assert all(clock_value.start_offset_ns is not None for clock_value in offset_clocks)
    assert invoked == [0, 1] or invoked == [1, 0]


def test_scenario_b_lanes_share_order_and_use_distinct_request_ids(
    valid_execution: _ExecutionFixture,
) -> None:
    for batch_index in {
        plan.batch_index
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.B_SAME_ORDER
    }:
        plans = [
            plan
            for plan in valid_execution.schedule.samples
            if plan.scenario is Scenario.B_SAME_ORDER
            and plan.batch_index == batch_index
        ]
        calls = [
            _call_by_request(valid_execution, _request_id("runtime-test", plan))
            for plan in plans
        ]
        assert len({call["order_id"] for call in calls}) == 1
        assert len({call["request_id"] for call in calls}) == 2


def test_scenario_b_never_retries_a_lane(
    valid_execution: _ExecutionFixture,
) -> None:
    request_ids = [
        _request_id("runtime-test", plan)
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.B_SAME_ORDER
    ]
    assert all(valid_execution.database.attempts[request_id] == 1 for request_id in request_ids)


def test_scenario_b_pre_naturally_classifies_stale_write(
    valid_execution: _ExecutionFixture,
) -> None:
    cohorts = {
        sample.cohort
        for sample in valid_execution.result.samples
        if sample.scenario is Scenario.B_SAME_ORDER
        and sample.composition is Composition.PRE_OCC
    }
    assert cohorts == {Cohort.ACCEPTED, Cohort.APPEND_STALE_WRITE}


def test_scenario_b_in_naturally_classifies_lock_timeout(
    valid_execution: _ExecutionFixture,
) -> None:
    cohorts = {
        sample.cohort
        for sample in valid_execution.result.samples
        if sample.scenario is Scenario.B_SAME_ORDER
        and sample.composition is Composition.IN_PESSIMISTIC
    }
    assert cohorts == {Cohort.ACCEPTED, Cohort.PREPARE_LOCK_TIMEOUT}


def test_scenario_c_uses_distinct_orders(
    valid_execution: _ExecutionFixture,
) -> None:
    for batch_index in {
        plan.batch_index
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.C_DIFFERENT_ORDER
    }:
        plans = [
            plan
            for plan in valid_execution.schedule.samples
            if plan.scenario is Scenario.C_DIFFERENT_ORDER
            and plan.batch_index == batch_index
        ]
        calls = [
            _call_by_request(valid_execution, _request_id("runtime-test", plan))
            for plan in plans
        ]
        assert len({call["order_id"] for call in calls}) == 2


def test_scenario_c_retains_only_accepted_cohort(
    valid_execution: _ExecutionFixture,
) -> None:
    assert {
        sample.cohort
        for sample in valid_execution.result.samples
        if sample.scenario is Scenario.C_DIFFERENT_ORDER
    } == {Cohort.ACCEPTED}


def test_lane_to_connection_assignment_follows_each_sample_plan(
    valid_execution: _ExecutionFixture,
) -> None:
    for plan in valid_execution.schedule.samples:
        if plan.scenario not in {Scenario.B_SAME_ORDER, Scenario.C_DIFFERENT_ORDER}:
            continue
        call = _call_by_request(valid_execution, _request_id("runtime-test", plan))
        assert call["connection"] == f"lane-{plan.connection_slot}"


def test_scenario_e_lock_setup_occurs_before_external_timer(
    valid_execution: _ExecutionFixture,
) -> None:
    plan = next(
        plan
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.E_LOCK_NON_ACQUISITION
    )
    call = _call_by_request(valid_execution, _request_id("runtime-test", plan))
    acquire = max(
        event["sequence"]
        for event in valid_execution.recorder.events[: call["sequence"]]
        if event["kind"] == "lock_acquire"
    )
    clocks = [
        event["sequence"]
        for event in valid_execution.recorder.events
        if event["kind"] == "clock"
        and acquire < event["sequence"] < call["sequence"]
    ]
    assert len(clocks) == 1
    assert acquire < clocks[0] < call["sequence"]


def test_scenario_e_lock_cleanup_occurs_after_external_timer(
    valid_execution: _ExecutionFixture,
) -> None:
    plan = next(
        plan
        for plan in valid_execution.schedule.samples
        if plan.scenario is Scenario.E_LOCK_NON_ACQUISITION
    )
    call = _call_by_request(valid_execution, _request_id("runtime-test", plan))
    release = next(
        event["sequence"]
        for event in valid_execution.recorder.events[call["sequence"] + 1 :]
        if event["kind"] == "lock_release"
    )
    stop_clock = max(
        event["sequence"]
        for event in valid_execution.recorder.events
        if event["kind"] == "clock" and call["sequence"] < event["sequence"] < release
    )
    assert call["sequence"] < stop_clock < release


def test_scenario_d_has_no_enum_member_or_executor_surface() -> None:
    assert "D" not in {scenario.name.split("_")[0] for scenario in Scenario}
    assert not hasattr(RecordedScheduleExecutor, "_execute_scenario_d")


def test_warmup_uses_preconstructed_objects_but_generates_no_samples(
    valid_execution: _ExecutionFixture,
) -> None:
    warmup_calls = [
        call
        for call in valid_execution.database.calls
        if call["request_id"].startswith("pr6-warmup-request-")
    ]
    assert len(warmup_calls) == 6 + 4
    assert valid_execution.database.reset_count == 2
    assert len(valid_execution.result.samples) == len(valid_execution.schedule.samples)
    assert all(sample.sample_index >= 0 for sample in valid_execution.result.samples)


def test_recorded_schedule_is_fixed_and_rejects_runtime_mutation() -> None:
    protocol = ProtocolConfig()
    canonical = generate_recorded_schedule(protocol=protocol, seed=19)
    assert len(canonical.samples) == 180 + 120 + 120 + 30 == 450

    small = _small_protocol()
    schedule = generate_recorded_schedule(protocol=small, seed=19)
    mutated = replace(schedule, samples=schedule.samples[:-1])
    topology = _fake_topology(_FakeDatabase(_Recorder()))
    with pytest.raises(RecordedRuntimeError, match="exact deterministic"):
        RecordedScheduleExecutor(topology=topology).execute(
            run_id="mutated-schedule",
            schedule=mutated,
            protocol=small,
        )


def test_insufficient_evidence_does_not_extend_or_rerun_schedule() -> None:
    execution = _fake_execution(force_concurrent_accepted=True)
    assert execution.result.validation.status is EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert len(execution.result.samples) == len(execution.schedule.samples)
    recorded_requests = [_request_id("runtime-test", plan) for plan in execution.schedule.samples]
    assert all(execution.database.attempts[request_id] == 1 for request_id in recorded_requests)


def test_exception_sample_does_not_trigger_a_replacement() -> None:
    execution = _fake_execution(fail_plan_index=0)
    sample = execution.result.samples[0]
    assert execution.result.validation.status is EvidenceStatus.INVALID_RUN
    assert sample.exception_type == "_LateDomainError"
    assert len(execution.result.samples) == len(execution.schedule.samples)
    assert execution.database.attempts[_request_id("runtime-test", execution.schedule.samples[0])] == 1


def test_evidence_output_round_trips_valid_raw_samples_and_aggregates(
    tmp_path: Path,
    valid_execution: _ExecutionFixture,
) -> None:
    output = write_evidence_directory(
        output_root=tmp_path,
        run_id="runtime-test",
        manifest=_manifest(valid_execution.protocol, valid_execution.schedule),
        execution=valid_execution.result,
        schedule=valid_execution.schedule,
        protocol=valid_execution.protocol,
    )
    assert output is not None
    assert sorted(path.name for path in output.directory.iterdir()) == [
        "aggregates.json",
        "manifest.json",
        "samples.jsonl",
    ]
    assert samples_from_jsonl(output.samples_path.read_text(encoding="utf-8")) == (
        valid_execution.result.samples
    )
    aggregates = json.loads(output.aggregates_path.read_text(encoding="utf-8"))
    assert aggregates["schema_version"] == 1
    assert aggregates["aggregates"]


def test_interrupted_evidence_publish_never_leaves_complete_looking_run(
    tmp_path: Path,
    valid_execution: _ExecutionFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_replace = runtime_module.os.replace
    final_directory = tmp_path / "atomic-failure"

    def fail_final_replace(source: Any, destination: Any) -> None:
        if Path(destination) == final_directory:
            raise OSError("simulated directory publication interruption")
        real_replace(source, destination)

    monkeypatch.setattr(runtime_module.os, "replace", fail_final_replace)
    with pytest.raises(OSError, match="publication interruption"):
        write_evidence_directory(
            output_root=tmp_path,
            run_id="atomic-failure",
            manifest=_manifest(valid_execution.protocol, valid_execution.schedule),
            execution=replace(
                valid_execution.result,
                samples=tuple(
                    replace(sample, run_id="atomic-failure")
                    for sample in valid_execution.result.samples
                ),
            ),
            schedule=valid_execution.schedule,
            protocol=valid_execution.protocol,
        )
    assert not final_directory.exists()
    assert not (final_directory / "aggregates.json").exists()
    assert any(path.name.startswith(".atomic-failure.staging-") for path in tmp_path.iterdir())


def test_invalid_run_emits_no_evidence_or_aggregates(tmp_path: Path) -> None:
    execution = _fake_execution(fail_plan_index=0)
    output = write_evidence_directory(
        output_root=tmp_path / "invalid-root",
        run_id="runtime-test",
        manifest=_manifest(execution.protocol, execution.schedule),
        execution=execution.result,
        schedule=execution.schedule,
        protocol=execution.protocol,
    )
    assert output is None
    assert not (tmp_path / "invalid-root").exists()


def test_insufficient_run_emits_no_evidence_or_aggregates(tmp_path: Path) -> None:
    execution = _fake_execution(force_concurrent_accepted=True)
    output = write_evidence_directory(
        output_root=tmp_path / "insufficient-root",
        run_id="runtime-test",
        manifest=_manifest(execution.protocol, execution.schedule),
        execution=execution.result,
        schedule=execution.schedule,
        protocol=execution.protocol,
    )
    assert output is None
    assert not (tmp_path / "insufficient-root").exists()


def test_runtime_manifest_captures_source_state_without_secret_metadata(
    valid_execution: _ExecutionFixture,
) -> None:
    manifest = build_recorded_run_manifest(
        topology=valid_execution.topology,
        schedule=valid_execution.schedule,
        protocol=valid_execution.protocol,
    )
    payload = json.loads(runtime_module.manifest_to_json(manifest))
    assert re.fullmatch(r"[0-9a-f]{40}", payload["source_commit"])
    assert type(payload["source_tree_clean_before_run"]) is bool
    assert payload["worker_count"] == 2
    assert payload["postgresql_server_version"] == "160003"
    forbidden_keys = {
        "dsn",
        "database_name",
        "host",
        "port",
        "username",
        "password",
        "hostname",
        "credentials",
        "test_database_url",
    }
    assert forbidden_keys.isdisjoint(key.lower() for key in payload)
    assert "://" not in json.dumps(payload).lower()


def test_runtime_exposes_no_worker_count_sweep_api() -> None:
    assert "worker_count" not in inspect.signature(RecordedScheduleExecutor).parameters
    assert "worker_count" not in inspect.signature(runtime_module.open_postgres_runtime).parameters
    assert len(_fake_topology(_FakeDatabase(_Recorder())).concurrent_lanes) == 2
