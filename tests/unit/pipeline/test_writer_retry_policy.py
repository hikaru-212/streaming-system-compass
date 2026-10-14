"""Deterministic configuration checks; all numerical values are test fixtures."""

from dataclasses import FrozenInstanceError

import pytest

from src.pipeline.writer_retry_policy import WriterRetryPolicy


@pytest.mark.parametrize("maximum", [True, False, None, 2.0, "2"])
def test_attempt_limit_requires_integer(maximum):
    with pytest.raises(TypeError):
        WriterRetryPolicy(maximum, ())


@pytest.mark.parametrize("maximum", [0, -1])
def test_attempt_limit_includes_initial_attempt(maximum):
    with pytest.raises(ValueError):
        WriterRetryPolicy(maximum, ())


@pytest.mark.parametrize("delays", [[], [0.25], None, iter([0.25])])
def test_schedule_must_be_immutable_and_finite(delays):
    with pytest.raises(TypeError):
        WriterRetryPolicy(2, delays)


@pytest.mark.parametrize("delays", [(), (0.25, 0.5)])
def test_schedule_covers_exactly_additional_attempts(delays):
    with pytest.raises(ValueError):
        WriterRetryPolicy(2, delays)


@pytest.mark.parametrize("delay", [True, 1, "0.25", None])
def test_delay_type_is_explicit_seconds(delay):
    with pytest.raises(TypeError):
        WriterRetryPolicy(2, (delay,))


@pytest.mark.parametrize("delay", [0.0, -0.25, float("inf"), float("-inf"), float("nan")])
def test_delay_requires_positive_finite_value(delay):
    with pytest.raises(ValueError):
        WriterRetryPolicy(2, (delay,))


def test_schedule_is_explicit_without_mandatory_shape_or_jitter():
    policy = WriterRetryPolicy(4, (0.25, 0.25, 0.75))
    assert [policy.delay_before_retry(i) for i in (1, 2, 3)] == [0.25, 0.25, 0.75]
    assert policy.max_delay_seconds == 0.75
    assert WriterRetryPolicy(1, ()).max_delay_seconds is None
    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 100
    for index in (0, 4, -1):
        with pytest.raises(ValueError):
            policy.delay_before_retry(index)
    with pytest.raises(TypeError):
        policy.delay_before_retry(True)


def test_no_enabled_numerical_defaults():
    with pytest.raises(TypeError):
        WriterRetryPolicy()
