"""Deterministic evidence tests: no writer, database, clock, or worker execution."""

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal

import pytest

from experiments.load_capacity_protection.model import (
    LoadAcknowledgement,
    LoadCellIdentity,
    LoadCellObservation,
    LoadDurableStatus,
    LoadDurableVerification,
    LoadFailureEvidence,
    LoadOuterPhase,
    LoadRequestObservation,
    LoadTiming,
    LoadWorkItem,
    LoadWriterOverlap,
    derive_accounting,
    derive_timing,
    derive_writer_overlap,
)
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.transactional.postgres_write_side import (
    PostgresWriteSideOutcome,
    PostgresWriteSideResult,
)
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement,
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurement,
    PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import (
    IdempotencyDecision,
    IdempotencyRecord,
    IdempotencyVerdict,
    RequestSignature,
)


def work_item(index=0):
    return LoadWorkItem(
        index,
        RequestSignature(
            f"request-{index}", CommandType.CREATE, f"order-{index}", Decimal("10.00")
        ),
    )


def cell_identity(concurrency=2):
    return LoadCellIdentity("run-a", "cell-a", 0, concurrency)


def event_for(item):
    return OrderEvent(
        f"event-{item.workload_index}", item.signature.request_id,
        item.signature.order_id, 1, EventType.CREATED, item.signature.amount,
        123, Proof(OrderStatus.INIT, 0, None),
    )


def accepted(index=0, *, lane=0, start=20, end=40, cell=None):
    item = work_item(index)
    result = PostgresWriteSideResult(
        PostgresWriteSideOutcome.ACCEPTED, event_for(item),
        IdempotencyDecision(IdempotencyVerdict.MISS, "fixture miss"),
    )
    return LoadRequestObservation(
        cell=cell or cell_identity(), item=item, lane_id=lane,
        offer_ns=0, dispatch_ns=10, writer_entry_ns=start, writer_exit_ns=end,
        terminal_observation_ns=end + 5, result=result,
        acknowledgement=LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED,
    )


def writer_failure():
    return LoadRequestObservation(
        cell_identity(), work_item(), lane_id=0,
        offer_ns=0, dispatch_ns=10, writer_entry_ns=20, writer_exit_ns=40,
        terminal_observation_ns=45,
        failure=LoadFailureEvidence(
            "psycopg.OperationalError", LoadOuterPhase.WRITER_CALL, True,
            LoadAcknowledgement.UNKNOWN, "08006",
        ),
    )


def cell_with(*observations, planned=None, identity=None):
    return LoadCellObservation(
        identity or observations[0].cell,
        planned if planned is not None else tuple(obs.item for obs in observations),
        tuple(observations),
    )


def test_completed_accepted_observation_retains_production_identity_and_is_frozen():
    observation = accepted()
    snapshot = cell_with(observation)
    counts = derive_accounting(snapshot)
    assert counts.planned == counts.offered == counts.dispatched == 1
    assert counts.writer_entered == counts.terminal == counts.acknowledged_accepted == 1
    assert counts.residual_workload_indices == ()
    assert snapshot.observations[0].result is observation.result
    assert snapshot.planned[0].signature is observation.item.signature
    with pytest.raises(FrozenInstanceError):
        observation.offer_ns = 99
    with pytest.raises(FrozenInstanceError):
        snapshot.observations = ()


def test_pre_entry_failure_is_terminal_without_writer_result_or_measurement():
    acknowledgement = LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
    observation = LoadRequestObservation(
        cell_identity(), work_item(), offer_ns=0, terminal_observation_ns=5,
        failure=LoadFailureEvidence(
            "builtins.RuntimeError", LoadOuterPhase.SCHEDULING, False, acknowledgement,
        ),
        acknowledgement=acknowledgement,
    )
    counts = derive_accounting(cell_with(observation))
    assert counts.terminal == 1
    assert counts.dispatched == counts.writer_entered == counts.acknowledged_accepted == 0
    assert observation.result is observation.measurement is None
    assert derive_timing(observation) == LoadTiming(None, None, None, None, 5)


def test_escaping_writer_failure_keeps_unknown_acknowledgement_and_safe_evidence():
    observation = writer_failure()
    assert observation.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert observation.result is observation.measurement is None
    assert observation.failure.sqlstate == "08006"
    assert derive_timing(observation).external_writer_call_ns == 20
    assert derive_accounting(cell_with(observation)).acknowledged_accepted == 0


def test_later_durable_effect_does_not_upgrade_ambiguous_acknowledgement():
    observation = writer_failure()
    event = event_for(observation.item)
    decision = IdempotencyDecision(
        IdempotencyVerdict.REPLAY, "fixture replay",
        IdempotencyRecord(observation.item.signature, event),
    )
    verified = replace(observation, verification=LoadDurableVerification(
        LoadDurableStatus.PRESENT, (event,), decision,
    ))
    assert verified.verification.idempotency_decision is decision
    assert verified.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert derive_accounting(cell_with(verified)).acknowledged_accepted == 0
    assert observation.verification is None


def test_durable_mismatch_evidence_is_retained_for_future_correctness_checks():
    observation = accepted()
    events = (event_for(observation.item), event_for(work_item(1)))
    verified = replace(observation, verification=LoadDurableVerification(
        LoadDurableStatus.PRESENT, events,
    ))
    assert verified.verification.accepted_events == events
    assert verified.verification.idempotency_decision is None
    missing = replace(observation, verification=LoadDurableVerification(
        LoadDurableStatus.ABSENT,
    ))
    assert missing.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED


def test_missing_boundaries_and_unknown_verification_remain_absent():
    observation = LoadRequestObservation(cell_identity(), work_item())
    assert derive_timing(observation) == LoadTiming(None, None, None, None, None)
    assert observation.verification is None
    assert LoadDurableVerification(LoadDurableStatus.UNKNOWN).accepted_events == ()
    with_missing_dispatch = replace(accepted(), dispatch_ns=None)
    assert derive_timing(with_missing_dispatch).scheduler_queue_wait_ns is None
    assert derive_timing(with_missing_dispatch).external_writer_call_ns == 20


@pytest.mark.parametrize("change", [
    {"offer_ns": 11}, {"dispatch_ns": 21}, {"writer_entry_ns": 41},
    {"writer_exit_ns": 46}, {"terminal_observation_ns": 39},
    {"dispatch_ns": None, "offer_ns": 21},
])
def test_timestamp_ordering_is_rejected_without_clamping(change):
    with pytest.raises(ValueError, match="timestamps must be ordered"):
        replace(accepted(), **change)


@pytest.mark.parametrize("value, error", [(-1, ValueError), (True, TypeError), (1.5, TypeError)])
def test_timestamp_values_must_be_nonnegative_integers(value, error):
    with pytest.raises(error):
        LoadRequestObservation(cell_identity(), work_item(), offer_ns=value)


def test_writer_exit_without_entry_is_rejected():
    with pytest.raises(ValueError, match="writer exit requires writer entry"):
        LoadRequestObservation(cell_identity(), work_item(), writer_exit_ns=40)


def test_normal_result_and_escaping_failure_are_rejected():
    with pytest.raises(ValueError, match="exclusive"):
        replace(accepted(), failure=writer_failure().failure)


@pytest.mark.parametrize("observation", [
    LoadRequestObservation(cell_identity(), work_item()), writer_failure(),
])
def test_accepted_acknowledgement_cannot_be_invented(observation):
    with pytest.raises(ValueError, match="acknowledgement"):
        replace(observation, acknowledgement=LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED)


@pytest.mark.parametrize("outcome", [
    PostgresWriteSideOutcome.REPLAY, PostgresWriteSideOutcome.CONFLICT,
    PostgresWriteSideOutcome.VALIDATION_BLOCKED,
    PostgresWriteSideOutcome.ADMISSION_REJECTED,
])
def test_normal_nonaccepted_returns_are_completions_but_not_useful_writes(outcome):
    observation = accepted()
    observation = replace(
        observation, result=replace(observation.result, outcome=outcome),
        acknowledgement=LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE,
    )
    counts = derive_accounting(cell_with(observation))
    assert counts.terminal == 1
    assert counts.acknowledged_accepted == 0


@pytest.mark.parametrize("duplicate", ["index", "request", "order"])
def test_duplicate_independent_identities_are_rejected(duplicate):
    first, second = work_item(0), work_item(1)
    if duplicate == "index":
        second = replace(second, workload_index=first.workload_index)
    else:
        name = f"{duplicate}_id"
        second = replace(second, signature=replace(
            second.signature, **{name: getattr(first.signature, name)},
        ))
    with pytest.raises(ValueError, match="duplicate independent"):
        LoadCellObservation(cell_identity(), (first, second))


def test_observations_must_match_plan_once_and_cell_identity():
    observation = accepted()
    with pytest.raises(ValueError, match="duplicate request observation"):
        cell_with(observation, observation, planned=(observation.item,))
    with pytest.raises(ValueError, match="planned item"):
        cell_with(observation, planned=(work_item(1),))
    with pytest.raises(ValueError, match="another cell"):
        cell_with(observation, identity=replace(observation.cell, repetition=1))
    with pytest.raises(ValueError, match="planned item"):
        cell_with(observation, planned=(replace(
            observation.item, signature=replace(observation.item.signature, amount=Decimal("20")),
        ),))


def test_partial_run_reconciles_all_planned_work_without_inventing_completions():
    completed = accepted()
    queued = LoadRequestObservation(cell_identity(), work_item(1), offer_ns=0)
    running = LoadRequestObservation(
        cell_identity(), work_item(2), lane_id=1, offer_ns=0,
        dispatch_ns=10, writer_entry_ns=20,
    )
    planned = tuple(work_item(index) for index in range(4))
    cell = cell_with(completed, queued, running, planned=planned)
    counts = derive_accounting(cell)
    assert (
        counts.planned, counts.offered, counts.dispatched, counts.writer_entered,
    ) == (4, 3, 2, 2)
    assert counts.terminal == counts.acknowledged_accepted == 1
    assert counts.residual_workload_indices == (1, 2, 3)
    assert counts.terminal + len(counts.residual_workload_indices) == counts.planned
    assert derive_writer_overlap(cell) == LoadWriterOverlap(1, 1, 1)


def test_timing_derives_each_outer_interval_and_keeps_measured_zero():
    assert derive_timing(accepted()) == LoadTiming(10, 10, 20, 5, 45)
    observation = replace(accepted(), dispatch_ns=0, writer_entry_ns=0)
    assert derive_timing(observation) == LoadTiming(0, 0, 40, 5, 45)


@pytest.mark.parametrize("intervals, expected", [
    (((20, 30), (40, 50)), 1),
    (((20, 40), (30, 50)), 2),
    (((20, 30), (30, 40)), 1),
    (((20, 20), (20, 20)), 0),
    (((20, 50), (20, 50)), 2),
])
def test_maximum_overlap_uses_half_open_writer_intervals(intervals, expected):
    observations = tuple(
        accepted(index, lane=index, start=start, end=end)
        for index, (start, end) in enumerate(intervals)
    )
    assert derive_writer_overlap(cell_with(*observations)) == LoadWriterOverlap(expected, 2, 0)


def test_configured_worker_count_cannot_manufacture_observed_overlap():
    identity = cell_identity(concurrency=16)
    empty = LoadCellObservation(identity, (work_item(),))
    assert derive_writer_overlap(empty) == LoadWriterOverlap(0, 0, 0)
    overlap = derive_writer_overlap(cell_with(accepted(cell=identity)))
    assert overlap.maximum_complete_interval_overlap == 1


def test_lane_assignment_and_known_same_lane_overlap_are_validated():
    with pytest.raises(ValueError, match="lane assignment"):
        replace(accepted(), lane_id=None)
    with pytest.raises(ValueError, match="lane range"):
        replace(accepted(), lane_id=2)
    with pytest.raises(ValueError, match="overlapping writer calls on one lane"):
        cell_with(accepted(0), accepted(1, start=30, end=50))
    assert derive_writer_overlap(cell_with(
        accepted(0), accepted(1, start=45, end=55),
    )).maximum_complete_interval_overlap == 1


def test_failure_writer_entry_and_acknowledgement_must_agree():
    observation = writer_failure()
    with pytest.raises(ValueError, match="writer-entered"):
        replace(observation, failure=replace(
            observation.failure, writer_entered=False, phase=LoadOuterPhase.SCHEDULING,
        ))
    with pytest.raises(ValueError, match="acknowledgement"):
        replace(observation, failure=replace(
            observation.failure,
            acknowledgement=LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE,
        ))


@pytest.mark.parametrize("phase, entered", [
    (LoadOuterPhase.CONNECTION_PREPARATION, True),
    (LoadOuterPhase.SCHEDULING, True),
    (LoadOuterPhase.DISPATCHED, True),
    (LoadOuterPhase.WRITER_CALL, False),
])
def test_failure_phase_cannot_contradict_writer_entry(phase, entered):
    with pytest.raises(ValueError, match="phase"):
        replace(writer_failure().failure, phase=phase, writer_entered=entered)


@pytest.mark.parametrize("change", [
    {"sqlstate": "password=secret"}, {"sqlstate": "0800"},
    {"exception_class": "failure: connection details"},
])
def test_failure_fields_reject_diagnostic_text(change):
    with pytest.raises(ValueError):
        replace(writer_failure().failure, **change)


def test_production_measurement_is_optional_and_reused_without_phase_reinterpretation():
    measured = PostgresWriteSidePhaseMeasurement(PostgresWriteSidePhaseMeasurementState.MEASURED, 1)
    phases = {field.name: measured for field in fields(PostgresWriteSideMeasurement)}
    phases["rollback_finalization"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_REACHED,
    )
    phases["pessimistic_advisory_try_lock_call"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_APPLICABLE,
    )
    phases["validation_runtime_call"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_COLLECTED,
    )
    measurement = PostgresWriteSideMeasurement(**phases)
    observation = replace(
        accepted(), measurement=measurement,
        measurement_availability=PostgresWriteSideMeasurementAvailability.AVAILABLE,
    )
    assert observation.measurement is measurement
    unavailable = replace(
        accepted(), measurement_availability=PostgresWriteSideMeasurementAvailability.UNAVAILABLE,
    )
    assert unavailable.measurement is None
    assert unavailable.result.outcome is PostgresWriteSideOutcome.ACCEPTED
    with pytest.raises(ValueError, match="delivery availability"):
        replace(accepted(), measurement=measurement)
    with pytest.raises(ValueError, match="normal writer result"):
        replace(
            writer_failure(),
            measurement_availability=PostgresWriteSideMeasurementAvailability.UNAVAILABLE,
        )


def test_collection_inputs_must_be_immutable():
    with pytest.raises(TypeError, match="tuple"):
        LoadCellObservation(cell_identity(), [work_item()])
    with pytest.raises(TypeError, match="tuple"):
        LoadDurableVerification(LoadDurableStatus.PRESENT, [event_for(work_item())])


def test_terminal_observation_cannot_invent_a_result_or_an_exit():
    with pytest.raises(ValueError, match="result or failure"):
        LoadRequestObservation(cell_identity(), work_item(), terminal_observation_ns=5)
    with pytest.raises(ValueError, match="requires writer exit"):
        replace(writer_failure(), writer_exit_ns=None)
