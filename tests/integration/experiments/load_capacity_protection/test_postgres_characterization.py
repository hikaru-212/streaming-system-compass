"""Small real composition witness, not load characterization or performance evidence.

Execution requires explicit approval for TEST_DATABASE_URL and the scoped row
cleanup below. No shared clean_database fixture or PR7 reset is used. Reserve
these deterministic IDs for this witness and run without competing DB tests.
"""

from collections import Counter
from contextlib import ExitStack
from decimal import Decimal
from threading import Barrier

import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.model import (
    LoadAcknowledgement,
    LoadCellIdentity,
    LoadWorkItem,
    derive_accounting,
)
from experiments.load_capacity_protection.postgres_characterization import run_characterization
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from src.compass.transition.types import ValidationMode, ValidationVerdict
from src.core.order.enums import CommandType, EventType
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurementAvailability,
    PostgresWriteSideMeasurementDelivery,
    PostgresWriteSidePhaseMeasurementState,
)
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature
from src.storage.postgres_connection import connect_postgres
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from tests.integration.conftest import assert_test_database, get_test_database_url


@pytest.fixture
def prepared_workload():
    # K=3, N=2 is solely a composition/reuse witness, never a capacity setting.
    return tuple(
        LoadWorkItem(index, RequestSignature(
            f"pr1-composition-request-{index}", CommandType.CREATE,
            f"pr1-composition-order-{index}", Decimal("10.00"),
        ))
        for index in range(3)
    )


@pytest.fixture
def witness_connections(prepared_workload):
    """Open guarded retained connections; clean only previously absent witness rows.

Reuse repository URL/guard helpers but register close before checking identity:
the shared factory checks identity before returning its new connection. This
local ownership also closes a connection when an identity assertion fails.

No pre-run deletion is permitted. Existing rows matching either identity refuse
the witness. After all lane connections close, teardown deletes only paired
witness request/order IDs, idempotency first, without CASCADE or sequence reset.
"""
    database_url = get_test_database_url()  # Explicit TEST_DATABASE_URL, no fallback.
    configured_database = conninfo_to_dict(database_url).get("dbname")
    assert configured_database and configured_database.endswith("_test"), (
        "TEST_DATABASE_URL must explicitly name the approved _test database"
    )
    request_ids = [item.signature.request_id for item in prepared_workload]
    order_ids = [item.signature.order_id for item in prepared_workload]

    def open_guarded(stack):
        connection = connect_postgres(database_url)
        stack.callback(connection.close)
        assert_test_database(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == configured_database
        connection.rollback()  # End guard reads before composing any writer.
        assert not connection.autocommit
        assert connection.info.transaction_status is TransactionStatus.IDLE
        return connection

    with ExitStack() as control_cleanup:
        control = open_guarded(control_cleanup)
        with control.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM order_events "
                "WHERE request_id = ANY(%s) OR order_id = ANY(%s)",
                (request_ids, order_ids),
            )
            assert cursor.fetchone()[0] == 0, "witness event identities already exist"
            cursor.execute(
                "SELECT COUNT(*) FROM idempotency_records "
                "WHERE request_id = ANY(%s) OR order_id = ANY(%s)",
                (request_ids, order_ids),
            )
            assert cursor.fetchone()[0] == 0, "witness idempotency identities already exist"
        control.rollback()
        with ExitStack() as lane_cleanup:
            connections = tuple(open_guarded(lane_cleanup) for _ in range(2))
            try:
                yield control, connections
            finally:
                lane_cleanup.close()
                control.rollback()
                with control.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM idempotency_records "
                        "WHERE request_id = ANY(%s) AND order_id = ANY(%s)",
                        (request_ids, order_ids),
                    )
                    cursor.execute(
                        "DELETE FROM order_events "
                        "WHERE request_id = ANY(%s) AND order_id = ANY(%s)",
                        (request_ids, order_ids),
                    )
                control.commit()


def test_real_measured_create_retains_lane_resources_and_durable_identity(
    prepared_workload, witness_connections,
):
    control, connections = witness_connections
    lanes = tuple(
        PostgresLoadLane(index, connection) for index, connection in enumerate(connections)
    )
    assert len({id(lane.connection) for lane in lanes}) == 2
    assert len({lane.connection.info.backend_pid for lane in lanes}) == 2
    assert len({connection.info.backend_pid for connection in (control, *connections)}) == 3
    assert len({id(lane.writer) for lane in lanes}) == 2
    first_calls = Barrier(2)

    # Recording and first-call rendezvous prove resource use, not performance.
    # Only the first call waits; this is not a replenishment/batch barrier.
    class RecordingLane:
        def __init__(self, lane):
            self.lane = lane
            self.calls = []

        def __call__(self, item):
            if not self.calls:
                first_calls.wait(timeout=10)  # Test failure deadline only.
            connection, writer = self.lane.connection, self.lane.writer
            delivery = self.lane(item)
            self.calls.append((item, connection, writer, delivery))
            return delivery

    recording_lanes = tuple(RecordingLane(lane) for lane in lanes)
    result = run_characterization(
        LoadCellIdentity("pr1-composition", "independent-create", 0, 2),
        prepared_workload, recording_lanes,
    )
    counts = derive_accounting(result)
    assert counts.planned == counts.offered == counts.dispatched == 3
    assert counts.writer_entered == counts.terminal == counts.acknowledged_accepted == 3
    assert counts.residual_workload_indices == ()
    all_calls = [call for lane in recording_lanes for call in lane.calls]
    assert Counter(call[0] for call in all_calls) == Counter(prepared_workload)
    assert sorted(len(lane.calls) for lane in recording_lanes) == [1, 2]
    for recording in recording_lanes:
        for _, connection, writer, _ in recording.calls:
            assert connection is recording.lane.connection
            assert writer is recording.lane.writer
        assert not recording.lane.connection.closed
        assert recording.lane.connection.info.transaction_status is TransactionStatus.IDLE

    # The scheduler has joined every worker. Verification uses a different
    # connection and a fresh read transaction, outside all workload timestamps.
    control.rollback()
    events = PostgresEventStore(control)
    idempotency = PostgresIdempotencyStore(control)
    accepted_ids = set()
    for observation in result.observations:
        assert observation.acknowledgement is LoadAcknowledgement.ACKNOWLEDGED_ACCEPTED
        assert observation.result.outcome is PostgresWriteSideOutcome.ACCEPTED
        delivery, = (
            call[3] for call in recording_lanes[observation.lane_id].calls
            if call[0] == observation.item
        )
        assert type(delivery) is PostgresWriteSideMeasurementDelivery
        assert observation.result is delivery.producer_value
        assert observation.measurement is delivery.measurement
        assert observation.measurement_availability is delivery.availability
        assert delivery.availability is PostgresWriteSideMeasurementAvailability.AVAILABLE
        for phase in (
            delivery.measurement.producer_write_invocation,
            delivery.measurement.preliminary_idempotency_check,
            delivery.measurement.commit_finalization,
        ):
            assert phase.state is PostgresWriteSidePhaseMeasurementState.MEASURED
        assert (
            delivery.measurement.pessimistic_advisory_try_lock_call.state
            is PostgresWriteSidePhaseMeasurementState.NOT_APPLICABLE
        )
        validation = observation.result.validation_decision.validation_result
        assert validation.validation_mode is ValidationMode.STRICT
        assert validation.validator_name == "FullProofValidator"
        assert validation.verdict is ValidationVerdict.PASSED
        assert observation.result.validation_decision_evidence is not None

        signature = observation.item.signature
        history = events.load(signature.order_id)
        assert len(history) == 1
        event, = history
        assert event == observation.result.accepted_event
        assert event.event_type is EventType.CREATED
        assert event.sequence == 1
        assert (event.request_id, event.order_id, event.amount) == (
            signature.request_id, signature.order_id, signature.amount,
        )
        decision = idempotency.check(signature)  # Read only, not another writer invocation.
        assert decision.verdict is IdempotencyVerdict.REPLAY
        assert decision.record.signature == signature
        assert decision.record.accepted_event == event
        accepted_ids.add(event.event_id)
        with control.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM order_events WHERE request_id = %s",
                (signature.request_id,),
            )
            assert cursor.fetchone()[0] == 1
    assert len(accepted_ids) == 3
