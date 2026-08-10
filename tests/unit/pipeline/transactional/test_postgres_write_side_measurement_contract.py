from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from inspect import signature

import pytest

from src.core.order.aggregate import OrderAggregate
from src.pipeline.transactional.postgres_write_side import (
    PostgresTransactionalWriteSide,
    PostgresWriteSideExecution,
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_config import (
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_execution_trace import (
    PostgresWriteSideExecutionCheckpoint,
    PostgresWriteSideExecutionTrace,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSideMeasurementDelivery,
    PostgresWriteSidePhaseMeasurement,
    PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyVerdict,
)


State = PostgresWriteSidePhaseMeasurementState
Availability = PostgresWriteSideMeasurementAvailability

MEASUREMENT_FIELD_NAMES = (
    "producer_write_invocation",
    "business_uow",
    "validation_runtime_call",
    "preliminary_idempotency_check",
    "preliminary_read_cleanup",
    "authoritative_idempotency_check",
    "accepted_history_load",
    "concurrency_preparation_call",
    "pessimistic_advisory_try_lock_call",
    "append_admission_call",
    "idempotency_record_call",
    "commit_finalization",
    "rollback_finalization",
)


def _measured(elapsed_ns: int) -> PostgresWriteSidePhaseMeasurement:
    return PostgresWriteSidePhaseMeasurement(
        state=State.MEASURED,
        elapsed_ns=elapsed_ns,
    )


def _absent(state: State) -> PostgresWriteSidePhaseMeasurement:
    return PostgresWriteSidePhaseMeasurement(state=state)


def _early_pre_measurement(**overrides: object) -> PostgresWriteSideMeasurement:
    values: dict[str, object] = {
        "producer_write_invocation": _measured(10),
        "business_uow": _absent(State.NOT_REACHED),
        "validation_runtime_call": _absent(State.NOT_REACHED),
        "preliminary_idempotency_check": _measured(1),
        "preliminary_read_cleanup": _measured(1),
        "authoritative_idempotency_check": _absent(State.NOT_REACHED),
        "accepted_history_load": _absent(State.NOT_REACHED),
        "concurrency_preparation_call": _absent(State.NOT_REACHED),
        "pessimistic_advisory_try_lock_call": _absent(
            State.NOT_APPLICABLE
        ),
        "append_admission_call": _absent(State.NOT_REACHED),
        "idempotency_record_call": _absent(State.NOT_REACHED),
        "commit_finalization": _absent(State.NOT_REACHED),
        "rollback_finalization": _absent(State.NOT_REACHED),
    }
    values.update(overrides)
    return PostgresWriteSideMeasurement(**values)  # type: ignore[arg-type]


def _accepted_in_measurement() -> PostgresWriteSideMeasurement:
    return PostgresWriteSideMeasurement(
        producer_write_invocation=_measured(100),
        business_uow=_measured(80),
        validation_runtime_call=_measured(20),
        preliminary_idempotency_check=_absent(State.NOT_APPLICABLE),
        preliminary_read_cleanup=_absent(State.NOT_APPLICABLE),
        authoritative_idempotency_check=_measured(5),
        accepted_history_load=_measured(10),
        concurrency_preparation_call=_measured(8),
        pessimistic_advisory_try_lock_call=_measured(3),
        append_admission_call=_measured(12),
        idempotency_record_call=_measured(4),
        commit_finalization=_measured(6),
        rollback_finalization=_absent(State.NOT_APPLICABLE),
    )


def _normal_nonaccepted_in_measurement() -> PostgresWriteSideMeasurement:
    return PostgresWriteSideMeasurement(
        producer_write_invocation=_measured(20),
        business_uow=_measured(15),
        validation_runtime_call=_absent(State.NOT_REACHED),
        preliminary_idempotency_check=_absent(State.NOT_APPLICABLE),
        preliminary_read_cleanup=_absent(State.NOT_APPLICABLE),
        authoritative_idempotency_check=_measured(5),
        accepted_history_load=_absent(State.NOT_REACHED),
        concurrency_preparation_call=_absent(State.NOT_REACHED),
        pessimistic_advisory_try_lock_call=_absent(State.NOT_REACHED),
        append_admission_call=_absent(State.NOT_REACHED),
        idempotency_record_call=_absent(State.NOT_REACHED),
        commit_finalization=_absent(State.NOT_APPLICABLE),
        rollback_finalization=_measured(4),
    )


def _result(outcome: PostgresWriteSideOutcome) -> PostgresWriteSideResult:
    aggregate = OrderAggregate("measurement-contract-order")
    candidate_event = aggregate.create(
        request_id="measurement-contract-request",
        total_amount=Decimal("100.00"),
    )
    return PostgresWriteSideResult(
        outcome=outcome,
        accepted_event=(
            candidate_event
            if outcome is PostgresWriteSideOutcome.ACCEPTED
            else None
        ),
        idempotency_decision=IdempotencyDecision(
            verdict=IdempotencyVerdict.MISS,
            reason="Contract test idempotency evidence",
        ),
    )


def _accepted_execution() -> PostgresWriteSideExecution:
    checkpoint = PostgresWriteSideExecutionCheckpoint
    trace = PostgresWriteSideExecutionTrace(
        validation_placement=ValidationPlacement.IN_TRANSACTION,
        checkpoints=(
            checkpoint.BUSINESS_UOW_REACHED,
            checkpoint.AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED,
            checkpoint.CONCURRENCY_PREPARATION_RETURNED,
            checkpoint.ACCEPTED_HISTORY_OBSERVED,
            checkpoint.VALIDATION_RETURNED,
            checkpoint.APPEND_ADMISSION_RETURNED,
            checkpoint.IDEMPOTENCY_PERSISTENCE_RETURNED,
        ),
    )
    return PostgresWriteSideExecution(
        result=_result(PostgresWriteSideOutcome.ACCEPTED),
        trace=trace,
    )


def test_phase_state_has_exact_four_state_vocabulary() -> None:
    assert [state.value for state in State] == [
        "NOT_APPLICABLE",
        "NOT_REACHED",
        "NOT_COLLECTED",
        "MEASURED",
    ]


def test_phase_measurement_is_immutable_and_accepts_measured_zero() -> None:
    phase = _measured(0)

    assert phase.state is State.MEASURED
    assert phase.elapsed_ns == 0
    with pytest.raises(FrozenInstanceError):
        phase.elapsed_ns = 1  # type: ignore[misc]


def test_not_applicable_is_distinct_from_not_reached() -> None:
    not_applicable = _absent(State.NOT_APPLICABLE)
    not_reached = _absent(State.NOT_REACHED)

    assert not_applicable != not_reached
    assert not_applicable.elapsed_ns is None
    assert not_reached.elapsed_ns is None


def test_not_collected_is_distinct_from_measured_zero() -> None:
    not_collected = _absent(State.NOT_COLLECTED)
    measured_zero = _measured(0)

    assert not_collected != measured_zero
    assert not_collected.elapsed_ns is None
    assert measured_zero.elapsed_ns == 0


@pytest.mark.parametrize("elapsed_ns", [-1, -10])
def test_phase_measurement_rejects_negative_elapsed_values(elapsed_ns: int) -> None:
    with pytest.raises(ValueError, match="elapsed_ns must be non-negative"):
        _measured(elapsed_ns)


@pytest.mark.parametrize("elapsed_ns", [None, 1.5, True])
def test_measured_phase_requires_an_integer_elapsed_value(elapsed_ns: object) -> None:
    with pytest.raises(TypeError, match="elapsed_ns must be int"):
        PostgresWriteSidePhaseMeasurement(
            state=State.MEASURED,
            elapsed_ns=elapsed_ns,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "state",
    [State.NOT_APPLICABLE, State.NOT_REACHED, State.NOT_COLLECTED],
)
def test_unmeasured_phase_states_reject_numeric_values(state: State) -> None:
    with pytest.raises(ValueError, match="elapsed_ns must be None"):
        PostgresWriteSidePhaseMeasurement(state=state, elapsed_ns=0)


def test_measurement_has_exact_immutable_first_contract_surface() -> None:
    measurement = _accepted_in_measurement()

    assert tuple(field.name for field in fields(measurement)) == (
        MEASUREMENT_FIELD_NAMES
    )
    with pytest.raises(FrozenInstanceError):
        measurement.business_uow = _measured(1)  # type: ignore[misc]


def test_available_snapshot_requires_measured_producer_invocation() -> None:
    with pytest.raises(
        ValueError,
        match="producer_write_invocation must be MEASURED",
    ):
        _early_pre_measurement(
            producer_write_invocation=_absent(State.NOT_COLLECTED)
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "preliminary_read_cleanup": _absent(State.NOT_REACHED),
        },
        {
            "validation_runtime_call": _measured(1),
        },
        {
            "authoritative_idempotency_check": _measured(1),
        },
        {
            "concurrency_preparation_call": _measured(1),
        },
        {
            "pessimistic_advisory_try_lock_call": _measured(1),
        },
        {
            "append_admission_call": _measured(1),
        },
        {
            "idempotency_record_call": _measured(1),
        },
        {
            "business_uow": _measured(3),
        },
    ],
)
def test_snapshot_rejects_incomplete_reached_topology(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _early_pre_measurement(**overrides)


def test_snapshot_rejects_both_commit_and_rollback_finalization() -> None:
    with pytest.raises(ValueError, match="exactly one reached"):
        PostgresWriteSideMeasurement(
            producer_write_invocation=_measured(20),
            business_uow=_measured(15),
            validation_runtime_call=_absent(State.NOT_REACHED),
            preliminary_idempotency_check=_absent(State.NOT_APPLICABLE),
            preliminary_read_cleanup=_absent(State.NOT_APPLICABLE),
            authoritative_idempotency_check=_measured(2),
            accepted_history_load=_absent(State.NOT_REACHED),
            concurrency_preparation_call=_measured(2),
            pessimistic_advisory_try_lock_call=_absent(State.NOT_APPLICABLE),
            append_admission_call=_measured(2),
            idempotency_record_call=_measured(2),
            commit_finalization=_measured(2),
            rollback_finalization=_measured(2),
        )


def test_snapshot_allows_not_collected_for_a_reached_detail_phase() -> None:
    measurement = _early_pre_measurement(
        preliminary_idempotency_check=_absent(State.NOT_COLLECTED),
        preliminary_read_cleanup=_absent(State.NOT_COLLECTED),
    )

    assert measurement.preliminary_idempotency_check.state is State.NOT_COLLECTED
    assert measurement.preliminary_read_cleanup.elapsed_ns is None


def test_overlapping_children_are_not_summed_into_the_whole() -> None:
    measurement = _accepted_in_measurement()
    child_total = sum(
        phase.elapsed_ns
        for phase in (
            measurement.business_uow,
            measurement.validation_runtime_call,
            measurement.authoritative_idempotency_check,
            measurement.accepted_history_load,
            measurement.concurrency_preparation_call,
            measurement.pessimistic_advisory_try_lock_call,
            measurement.append_admission_call,
            measurement.idempotency_record_call,
            measurement.commit_finalization,
        )
        if phase.elapsed_ns is not None
    )

    assert child_total > measurement.producer_write_invocation.elapsed_ns


def test_available_delivery_requires_a_measurement() -> None:
    result = _result(PostgresWriteSideOutcome.ACCEPTED)
    measurement = _accepted_in_measurement()

    delivery = PostgresWriteSideMeasurementDelivery(
        producer_value=result,
        availability=Availability.AVAILABLE,
        measurement=measurement,
    )

    assert tuple(field.name for field in fields(delivery)) == (
        "producer_value",
        "availability",
        "measurement",
    )
    assert delivery.producer_value is result
    assert delivery.measurement is measurement

    with pytest.raises(FrozenInstanceError):
        delivery.measurement = None  # type: ignore[misc]


def test_availability_has_exact_two_state_vocabulary() -> None:
    assert [state.value for state in Availability] == [
        "AVAILABLE",
        "UNAVAILABLE",
    ]


def test_unavailable_delivery_requires_no_fabricated_phase_values() -> None:
    result = _result(PostgresWriteSideOutcome.ACCEPTED)

    delivery = PostgresWriteSideMeasurementDelivery(
        producer_value=result,
        availability=Availability.UNAVAILABLE,
        measurement=None,
    )

    assert delivery.producer_value is result
    assert delivery.measurement is None


def test_delivery_rejects_incoherent_availability_pairs() -> None:
    result = _result(PostgresWriteSideOutcome.ACCEPTED)

    with pytest.raises(TypeError, match="measurement must be"):
        PostgresWriteSideMeasurementDelivery(
            producer_value=result,
            availability=Availability.AVAILABLE,
            measurement=None,
        )

    with pytest.raises(ValueError, match="measurement must be None"):
        PostgresWriteSideMeasurementDelivery(
            producer_value=result,
            availability=Availability.UNAVAILABLE,
            measurement=_accepted_in_measurement(),
        )


def test_delivery_preserves_exact_legacy_producer_value() -> None:
    result = _result(PostgresWriteSideOutcome.ACCEPTED)

    delivery = PostgresWriteSideMeasurementDelivery(
        producer_value=result,
        availability=Availability.AVAILABLE,
        measurement=_accepted_in_measurement(),
    )

    assert type(delivery.producer_value) is PostgresWriteSideResult
    assert delivery.producer_value is result
    assert delivery.producer_value.accepted_event is result.accepted_event


def test_delivery_preserves_exact_traced_producer_value_and_trace() -> None:
    execution = _accepted_execution()
    original_trace = execution.trace

    delivery = PostgresWriteSideMeasurementDelivery(
        producer_value=execution,
        availability=Availability.AVAILABLE,
        measurement=_accepted_in_measurement(),
    )

    assert type(delivery.producer_value) is PostgresWriteSideExecution
    assert delivery.producer_value is execution
    assert delivery.producer_value.trace is original_trace
    assert tuple(field.name for field in fields(original_trace)) == (
        "validation_placement",
        "checkpoints",
    )
    assert not any(
        "time" in field.name or "elapsed" in field.name
        for field in fields(original_trace)
    )


def test_normal_typed_nonaccepted_result_has_available_measurement_shape() -> None:
    result = _result(PostgresWriteSideOutcome.REPLAY)
    measurement = _normal_nonaccepted_in_measurement()

    delivery = PostgresWriteSideMeasurementDelivery(
        producer_value=result,
        availability=Availability.AVAILABLE,
        measurement=measurement,
    )

    assert delivery.producer_value is result
    assert delivery.producer_value.outcome is PostgresWriteSideOutcome.REPLAY
    assert measurement.rollback_finalization.state is State.MEASURED
    assert measurement.commit_finalization.state is State.NOT_APPLICABLE


def test_contract_has_no_retry_attempt_receipt_or_persistence_surface() -> None:
    public_names = {
        *(state.name for state in State),
        *(field.name for field in fields(PostgresWriteSideMeasurement)),
        *(field.name for field in fields(PostgresWriteSideMeasurementDelivery)),
    }
    forbidden_terms = {
        "retry",
        "attempt",
        "receipt",
        "persist",
        "strategy",
        "rate_limit",
    }

    assert all(
        forbidden not in name.lower()
        for name in public_names
        for forbidden in forbidden_terms
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "create_order",
        "pay_order",
        "create_order_with_trace",
        "pay_order_with_trace",
    ],
)
def test_existing_unmeasured_apis_do_not_require_measurement(
    method_name: str,
) -> None:
    method = getattr(PostgresTransactionalWriteSide, method_name)
    parameter_names = set(signature(method).parameters)

    assert not any("measurement" in name for name in parameter_names)


def test_pr4_measured_methods_are_explicit_and_do_not_add_enable_flags() -> None:
    measured_methods = (
        "create_order_with_measurement",
        "create_order_with_trace_and_measurement",
        "pay_order_with_measurement",
        "pay_order_with_trace_and_measurement",
    )

    assert all(
        hasattr(PostgresTransactionalWriteSide, method_name)
        for method_name in measured_methods
    )
    for method_name in (
        "create_order",
        "create_order_with_trace",
        "pay_order",
        "pay_order_with_trace",
    ):
        assert "measurement_enabled" not in signature(
            getattr(PostgresTransactionalWriteSide, method_name)
        ).parameters
