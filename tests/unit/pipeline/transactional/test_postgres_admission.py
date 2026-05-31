from dataclasses import dataclass

from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
    PostgresPessimisticAdmissionGate,
    _is_stream_position_conflict,
)
from src.storage.errors import (
    AppendConflictError,
    StaleWriteError,
    StorageInfrastructureError,
)


@dataclass(frozen=True)
class FakeEvent:
    event_id: str = "candidate-event-1"
    order_id: str = "order-1"


class FakeEventStore:
    def __init__(self, exc=None):
        self.exc = exc
        self.append_calls = []

    def append(self, candidate_event, expected_current_version):
        self.append_calls.append(
            {
                "candidate_event": candidate_event,
                "expected_current_version": expected_current_version,
            }
        )

        if self.exc is not None:
            raise self.exc


class FakeConnection:
    def __init__(self, autocommit=False):
        self.autocommit = autocommit


class FakeDiag:
    def __init__(self, constraint_name):
        self.constraint_name = constraint_name


class FakeUniqueViolation:
    def __init__(self, constraint_name):
        self.diag = FakeDiag(constraint_name)


def test_postgres_optimistic_prepare_stream_is_noop_admitted():
    gate = PostgresOptimisticAdmissionGate(FakeEventStore())

    result = gate.prepare_stream("order-1")

    assert result.verdict == AdmissionVerdict.ADMITTED
    assert result.admitted is True
    assert result.order_id == "order-1"


def test_postgres_optimistic_admit_appends_candidate_event():
    event_store = FakeEventStore()
    gate = PostgresOptimisticAdmissionGate(event_store)
    candidate_event = FakeEvent()

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.ADMITTED
    assert result.admitted is True
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id == candidate_event.event_id
    assert event_store.append_calls == [
        {
            "candidate_event": candidate_event,
            "expected_current_version": 1,
        }
    ]


def test_postgres_optimistic_admit_translates_value_error_to_stale_write():
    gate = PostgresOptimisticAdmissionGate(
        FakeEventStore(exc=ValueError("version conflict"))
    )
    candidate_event = FakeEvent()

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.STALE_WRITE
    assert result.admitted is False
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id is None
    assert "version conflict" in result.reason


def test_postgres_optimistic_admit_translates_stale_write_error_to_stale_write():
    gate = PostgresOptimisticAdmissionGate(
        FakeEventStore(exc=StaleWriteError("stale writer"))
    )
    candidate_event = FakeEvent()

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.STALE_WRITE
    assert result.admitted is False
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id is None
    assert "stale writer" in result.reason


def test_postgres_optimistic_admit_translates_append_conflict_to_stale_write():
    gate = PostgresOptimisticAdmissionGate(
        FakeEventStore(exc=AppendConflictError("stream position occupied"))
    )
    candidate_event = FakeEvent()

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.STALE_WRITE
    assert result.admitted is False
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id is None
    assert "stream position occupied" in result.reason


def test_postgres_optimistic_admit_translates_storage_infrastructure_error():
    gate = PostgresOptimisticAdmissionGate(
        FakeEventStore(exc=StorageInfrastructureError("database unavailable"))
    )
    candidate_event = FakeEvent()

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.INFRASTRUCTURE_ERROR
    assert result.admitted is False
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id is None
    assert "database unavailable" in result.reason


def test_postgres_pessimistic_admit_requires_prepare_stream_first():
    gate = PostgresPessimisticAdmissionGate(
        connection=FakeConnection(autocommit=False),
        event_store=FakeEventStore(),
    )
    candidate_event = FakeEvent(order_id="order-1")

    result = gate.append_if_admitted(candidate_event, expected_current_version=1)

    assert result.verdict == AdmissionVerdict.INFRASTRUCTURE_ERROR
    assert result.admitted is False
    assert result.candidate_event_id == candidate_event.event_id
    assert result.accepted_event_id is None
    assert "prepare_stream(order_id)" in result.reason


def test_is_stream_position_conflict_returns_true_for_current_migration_constraint():
    exc = FakeUniqueViolation("uq_order_events_order_sequence")

    assert _is_stream_position_conflict(exc) is True


def test_is_stream_position_conflict_returns_true_for_future_explicit_constraint():
    exc = FakeUniqueViolation("uq_order_events_order_id_sequence")

    assert _is_stream_position_conflict(exc) is True


def test_is_stream_position_conflict_returns_true_for_postgres_default_constraint():
    exc = FakeUniqueViolation("order_events_order_id_sequence_key")

    assert _is_stream_position_conflict(exc) is True


def test_is_stream_position_conflict_returns_false_for_unknown_constraint():
    exc = FakeUniqueViolation("uq_order_events_accepted_event_id")

    assert _is_stream_position_conflict(exc) is False


def test_is_stream_position_conflict_returns_false_when_constraint_name_missing():
    exc = FakeUniqueViolation(None)

    assert _is_stream_position_conflict(exc) is False