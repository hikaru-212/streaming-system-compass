"""Deterministic admission proofs using real public writer boundaries and fake I/O."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event, Lock
from unittest.mock import Mock

import pytest
from psycopg import OperationalError

from src.bootstrap.build_postgres_write_side_decision_receipt_runtime import (
    build_postgres_write_side_decision_receipt_runtime,
)
from src.compass.runtime.reinvocation_authority import ReinvocationAuthorization
from src.compass.transition.types import EnforcementAction
from src.core.order.enums import CommandType
from src.pipeline.transactional import postgres_write_side as writer_module
from src.pipeline.transactional.postgres_write_side import PostgresTransactionalWriteSide
from src.pipeline.transactional.postgres_write_side_config import ValidationPlacement
from src.pipeline.transactional.postgres_write_side_invocation_owner import (
    PostgresWriteSideInvocationLifecycleError,
    PostgresWriteSideInvocationOwner,
)
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityRefused
from src.storage.idempotency_store import IdempotencyVerdict
from tests.unit.pipeline.transactional.test_postgres_write_side_invocation_owner import (
    _accepted_result, _conflict_result, _positive_result, _replay_result, _signature,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_characterization import (
    _CommitFailure, _FakeConnection, _ManualClock, _Probe, _ProducerFailure,
    _RollbackFailure, _Scenario,
)
from tests.unit.pipeline.transactional.test_postgres_write_side_measurement_instrumentation import (
    _build_preview_writer, _install_preview_boundaries,
)


DEADLINE = 5  # Failure guard only; events/barriers establish every causal ordering.
METHODS = tuple(
    f'{command}_order{suffix}'
    for command in ('create', 'pay')
    for suffix in ('', '_with_trace', '_with_measurement', '_with_trace_and_measurement')
)
ARGS = dict(request_id='capacity-request', order_id='capacity-order', amount=Decimal('10.00'))


def writer(admission=None):
    return PostgresTransactionalWriteSide(
        connection=Mock(), validation_runtime=Mock(), capacity_admission=admission,
    )


@pytest.mark.parametrize('bound', [True, False, None, 1.5, '8'])
def test_noninteger_bound_is_rejected(bound):
    with pytest.raises(TypeError):
        BoundedWriterAdmission(bound)


@pytest.mark.parametrize('bound', [0, -1])
def test_nonpositive_bound_is_rejected(bound):
    with pytest.raises(ValueError):
        BoundedWriterAdmission(bound)


def test_invalid_injected_object_is_rejected():
    with pytest.raises(TypeError, match='capacity_admission'):
        writer(object())


@pytest.mark.parametrize('method_name', METHODS)
def test_refusal_precedes_all_public_writer_work(monkeypatch, method_name):
    admission = BoundedWriterAdmission(1)
    target = writer(admission)
    forbidden = Mock(side_effect=AssertionError('refused call must not execute'))
    monkeypatch.setattr(target, '_execute_command', forbidden)
    monkeypatch.setattr(target, '_execute_command_with_measurement', forbidden)
    monkeypatch.setattr(writer_module, '_PostgresWriteSideTraceCollector', forbidden)
    monkeypatch.setattr(writer_module, '_new_measurement_recorder', forbidden)

    def offer_excess():
        with pytest.raises(WriterCapacityRefused) as raised:
            getattr(target, method_name)(**ARGS)
        assert type(raised.value) is WriterCapacityRefused
        assert vars(raised.value) == {}  # No producer evidence or authority carrier.

    admission.run(offer_excess)
    forbidden.assert_not_called()
    assert target._connection.mock_calls == []
    assert target._validation_runtime.mock_calls == []
    assert admission.run(lambda: 'subsequent') == 'subsequent'


@pytest.mark.parametrize('method_name', METHODS)
@pytest.mark.parametrize('result_factory', [_accepted_result, _replay_result, _conflict_result, _positive_result])
def test_public_variants_release_and_preserve_exact_normal_value(monkeypatch, method_name, result_factory):
    admission = BoundedWriterAdmission(1)
    target = writer(admission)
    result = result_factory(_signature())
    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        with pytest.raises(WriterCapacityRefused):
            admission.run(lambda: pytest.fail('capacity must remain held'))
        return result

    monkeypatch.setattr(target, '_execute_command', execute)
    monkeypatch.setattr(target, '_execute_command_with_measurement', execute)
    assert getattr(target, method_name)(**ARGS) is result
    assert len(calls) == 1
    assert admission.run(lambda: result) is result


@pytest.mark.parametrize('method_name', METHODS)
@pytest.mark.parametrize('error', [RuntimeError('ordinary'), OperationalError('postgres'), KeyboardInterrupt()])
def test_exception_identity_and_release(monkeypatch, method_name, error):
    admission = BoundedWriterAdmission(1)
    target = writer(admission)
    fail = Mock(side_effect=error)
    monkeypatch.setattr(target, '_execute_command', fail)
    monkeypatch.setattr(target, '_execute_command_with_measurement', fail)
    with pytest.raises(type(error)) as raised:
        getattr(target, method_name)(**ARGS)
    assert raised.value is error
    assert admission.run(lambda: 'released') == 'released'


def test_five_offered_callers_share_bound_two_across_five_writers(monkeypatch):
    admission = BoundedWriterAdmission(2)
    targets = [writer(admission) for _ in range(5)]
    entered = Barrier(3)
    release = Event()
    excess_ready = Barrier(4)
    lock = Lock()
    active = peak = 0
    entries = []
    result = _accepted_result(_signature())

    def execute(**kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            entries.append(kwargs)
        try:
            entered.wait(DEADLINE)
            assert release.wait(DEADLINE)
            return result
        finally:
            with lock:
                active -= 1

    for target in targets:
        monkeypatch.setattr(target, '_execute_command', execute)

    def offer_excess(target):
        excess_ready.wait(DEADLINE)
        with pytest.raises(WriterCapacityRefused):
            target.create_order(**ARGS)
        return 'refused'

    with ThreadPoolExecutor(max_workers=5) as pool:
        holders = [pool.submit(t.create_order, **ARGS) for t in targets[:2]]
        try:
            entered.wait(DEADLINE)
            excess = [pool.submit(offer_excess, t) for t in targets[2:]]
            excess_ready.wait(DEADLINE)
            assert [f.result(DEADLINE) for f in excess] == ['refused'] * 3
            assert active == peak == len(entries) == 2
        finally:
            release.set()
        assert [f.result(DEADLINE) for f in holders] == [result, result]
    assert active == 0 and peak == 2
    monkeypatch.setattr(targets[2], '_execute_command', lambda **kw: result)
    assert targets[2].create_order(**ARGS) is result


@pytest.mark.parametrize('method_name', METHODS)
def test_absent_protection_preserves_execution(monkeypatch, method_name):
    target = writer()
    value = object()
    execute = Mock(return_value=value)
    monkeypatch.setattr(target, '_execute_command', execute)
    monkeypatch.setattr(target, '_execute_command_with_measurement', execute)
    assert getattr(target, method_name)(**ARGS) is value
    execute.assert_called_once()


@pytest.mark.parametrize('case', ['accepted', 'replay', 'validation', 'occ', 'producer', 'commit', 'rollback'])
def test_real_writer_algorithm_and_final_delivery_are_inside_permit(monkeypatch, case):
    pre = ValidationPlacement.PRE_TRANSACTION
    inside = ValidationPlacement.IN_TRANSACTION
    miss, replay = IdempotencyVerdict.MISS, IdempotencyVerdict.REPLAY
    scenarios = {
        'accepted': _Scenario(pre, (miss, miss)),
        'replay': _Scenario(pre, (replay,)),
        'validation': _Scenario(pre, (miss,), validation_action=EnforcementAction.BLOCK),
        'occ': _Scenario(pre, (miss, miss), append_admitted=False),
        'producer': _Scenario(pre, (miss,), validation_raises=True),
        'commit': _Scenario(pre, (miss, miss), commit_raises=True),
        'rollback': _Scenario(inside, (replay,), pessimistic=True, rollback_raises=True),
    }
    _install_preview_boundaries(monkeypatch)
    connection = _FakeConnection(scenarios[case], _Probe(_ManualClock()))
    unprotected = _build_preview_writer(connection)
    admission = BoundedWriterAdmission(1)
    target = PostgresTransactionalWriteSide(
        connection, unprotected._validation_runtime, unprotected._admission_gate_factory,
        unprotected._config, capacity_admission=admission,
    )
    recorder_type = writer_module._PostgresWriteSideMeasurementRecorder
    original = recorder_type.build_delivery
    delivered = []

    def build_delivery(recorder, value):
        with pytest.raises(WriterCapacityRefused):
            admission.run(lambda: None)
        delivered.append(value)
        return original(recorder, value)

    monkeypatch.setattr(recorder_type, 'build_delivery', build_delivery)
    errors = {'producer': _ProducerFailure, 'commit': _CommitFailure, 'rollback': _RollbackFailure}
    if case in errors:
        with pytest.raises(errors[case]):
            target.create_order_with_measurement(**ARGS)
        assert not delivered
    else:
        result = target.create_order_with_measurement(**ARGS)
        assert result.producer_value is delivered[0]
        expected = {'accepted': 'ACCEPTED', 'replay': 'REPLAY', 'validation': 'VALIDATION_BLOCKED', 'occ': 'ADMISSION_REJECTED'}
        assert result.producer_value.outcome.value == expected[case]
    assert admission.run(lambda: 'after public return') == 'after public return'


@pytest.mark.parametrize('command_type', [CommandType.CREATE, CommandType.PAY])
@pytest.mark.parametrize('outer_runtime', [False, True])
def test_a2_uses_same_capacity_boundary_without_refunding_or_fabricating(monkeypatch, command_type, outer_runtime):
    admission = BoundedWriterAdmission(1)
    signature = _signature(command_type=command_type)
    if outer_runtime:
        owner = build_postgres_write_side_decision_receipt_runtime(
            request_signature=signature, business_connection=Mock(), validation_runtime=Mock(),
            receipt_connection_factory=Mock(), receipt_idle_in_transaction_session_timeout_ms=5000,
            capacity_admission=admission,
        )
        target = owner._invocation_owner._writer
    else:
        target = writer(admission)
        owner = PostgresWriteSideInvocationOwner(request_signature=signature, writer=target)
    execute = Mock(return_value=_positive_result(signature))
    monkeypatch.setattr(target, '_execute_command', execute)
    owner.invoke_initial()
    assert isinstance(owner.evaluate_reinvocation_authority(), ReinvocationAuthorization)

    def excess_a2():
        with pytest.raises(WriterCapacityRefused):
            owner.invoke_authorized_reinvocation()

    admission.run(excess_a2)
    assert execute.call_count == 1
    with pytest.raises(PostgresWriteSideInvocationLifecycleError, match='spent'):
        owner.invoke_authorized_reinvocation()
    with pytest.raises(PostgresWriteSideInvocationLifecycleError, match='no normally completed'):
        owner.evaluate_current_response()
    if outer_runtime:
        assert owner._authorized_reinvocation_completion is None
    assert admission.run(lambda: 'released') == 'released'


def test_builder_shares_explicit_object_and_a1_refusal_has_no_completion(monkeypatch):
    admission = BoundedWriterAdmission(1)
    runtimes = [build_postgres_write_side_decision_receipt_runtime(
        request_signature=_signature(), business_connection=Mock(), validation_runtime=Mock(),
        receipt_connection_factory=Mock(), receipt_idle_in_transaction_session_timeout_ms=5000,
        capacity_admission=admission,
    ) for _ in range(2)]
    writers = [r._invocation_owner._writer for r in runtimes]
    assert writers[0] is not writers[1]
    assert all(w._capacity_admission is admission for w in writers)

    def inside_first(**kwargs):
        with pytest.raises(WriterCapacityRefused):
            runtimes[1].invoke_initial()
        return _accepted_result(_signature())

    monkeypatch.setattr(writers[0], '_execute_command', inside_first)
    runtimes[0].invoke_initial()
    refused = runtimes[1]
    assert refused._initial_completion is None
    with pytest.raises(PostgresWriteSideInvocationLifecycleError, match='not completed'):
        refused.evaluate_reinvocation_authority()
    assert writers[1]._connection.mock_calls == []


@pytest.mark.parametrize('command_type', [CommandType.CREATE, CommandType.PAY])
def test_admitted_a2_releases_before_owner_publishes_completion(monkeypatch, command_type):
    admission = BoundedWriterAdmission(1)
    signature = _signature(command_type=command_type)
    owner = build_postgres_write_side_decision_receipt_runtime(
        request_signature=signature, business_connection=Mock(), validation_runtime=Mock(),
        receipt_connection_factory=Mock(), receipt_idle_in_transaction_session_timeout_ms=5000,
        capacity_admission=admission,
    )
    target = owner._invocation_owner._writer
    outcomes = iter([_positive_result(signature), _accepted_result(signature)])

    def execute(**kwargs):
        assert kwargs['command_type'] is command_type
        with pytest.raises(WriterCapacityRefused):
            admission.run(lambda: None)
        return next(outcomes)

    monkeypatch.setattr(target, '_execute_command', execute)
    original_publish = owner._new_completed_invocation
    publications = []

    def publish(result):
        publications.append(admission.run(lambda: result))
        return original_publish(result)

    monkeypatch.setattr(owner, '_new_completed_invocation', publish)
    owner.invoke_initial()
    owner.evaluate_reinvocation_authority()
    completed = owner.invoke_authorized_reinvocation()
    assert completed is owner.authorized_reinvocation_completion
    assert len(publications) == 2
    with pytest.raises(PostgresWriteSideInvocationLifecycleError, match='spent'):
        owner.invoke_authorized_reinvocation()
