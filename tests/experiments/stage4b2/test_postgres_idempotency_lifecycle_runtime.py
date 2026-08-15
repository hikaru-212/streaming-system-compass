from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
    EXPECTED_LIFECYCLE,
    IdempotencyVerdictIdentity,
    Layer1Path,
    generate_smoke_schedule,
)
from experiments.stage4b2.postgres_idempotency_lifecycle_runtime import (
    _CoordinatingValidationRuntime,
    _idempotency_observations,
    execute_fixed_schedule,
    time_public_producer_invocation,
)


class _ProcessControlSignal(BaseException):
    pass


def test_external_timer_wraps_one_normal_public_invocation() -> None:
    readings = iter((100, 145))
    calls = []

    observed = time_public_producer_invocation(
        lambda: calls.append("called") or "producer-value",
        clock=lambda: next(readings),
    )

    assert calls == ["called"]
    assert observed.value == "producer-value"
    assert observed.elapsed_ns == 45
    assert observed.exception_type is None


def test_external_timer_retains_only_ordinary_exception_type() -> None:
    readings = iter((10, 18))

    def fail() -> None:
        raise ValueError("message must not enter evidence")

    observed = time_public_producer_invocation(
        fail,
        clock=lambda: next(readings),
    )

    assert observed.value is None
    assert observed.elapsed_ns == 8
    assert observed.exception_type == "ValueError"
    assert not hasattr(observed, "exception_message")


def test_external_timer_does_not_catch_process_control_baseexception() -> None:
    def stop() -> None:
        raise _ProcessControlSignal()

    with pytest.raises(_ProcessControlSignal):
        time_public_producer_invocation(stop, clock=lambda: 1)


def test_fixed_executor_invokes_each_smoke_plan_once_without_retry() -> None:
    schedule = generate_smoke_schedule()
    calls = []

    observed = execute_fixed_schedule(
        schedule,
        lambda plan: calls.append((plan.sample_index, plan.path)) or plan,
    )

    assert tuple(calls) == tuple(
        (plan.sample_index, plan.path) for plan in schedule.samples
    )
    assert observed == schedule.samples
    assert len(calls) == len(Layer1Path)


def test_fixed_executor_stops_without_replacement_after_failure() -> None:
    schedule = generate_smoke_schedule()
    calls = []

    def execute(plan):
        calls.append(plan.path)
        if plan.path is Layer1Path.C:
            raise RuntimeError("structural failure")
        return plan

    with pytest.raises(RuntimeError, match="structural failure"):
        execute_fixed_schedule(schedule, execute)

    assert calls == [Layer1Path.A, Layer1Path.B, Layer1Path.C]


@dataclass(frozen=True)
class _Decision:
    marker: str


class _Delegate:
    def __init__(self, events) -> None:
        self.events = events

    def decide(self, candidate_event, context):
        self.events.append(("delegate", candidate_event, context))
        return _Decision("full-proof-result")


def test_d_e_coordination_runs_after_delegate_decision_before_return() -> None:
    events = []
    runtime = _CoordinatingValidationRuntime(
        _Delegate(events),
        lambda: events.append(("coordination",)),
    )

    decision = runtime.decide("candidate", "context")

    assert decision == _Decision("full-proof-result")
    assert events == [
        ("delegate", "candidate", "context"),
        ("coordination",),
    ]


@pytest.mark.parametrize("path", tuple(Layer1Path))
def test_lifecycle_observation_retains_exact_returned_final_verdict(
    path: Layer1Path,
) -> None:
    expected = EXPECTED_LIFECYCLE[path]
    result = SimpleNamespace(
        idempotency_decision=SimpleNamespace(
            verdict=expected[-1].verdict.value.lower(),
        )
    )

    assert _idempotency_observations(path, result) == expected


def test_lifecycle_observation_does_not_hide_wrong_returned_final_verdict() -> None:
    result = SimpleNamespace(
        idempotency_decision=SimpleNamespace(verdict="conflict")
    )

    observed = _idempotency_observations(Layer1Path.A, result)

    assert observed != EXPECTED_LIFECYCLE[Layer1Path.A]
    assert observed[-1].verdict is IdempotencyVerdictIdentity.CONFLICT
