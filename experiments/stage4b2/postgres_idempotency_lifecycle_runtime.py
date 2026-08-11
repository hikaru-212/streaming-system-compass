"""Real-PostgreSQL runtime for the post-PR6 Layer-1 A--H characterization.

The runtime invokes only current public producer APIs. Fixture construction,
database reset, connection/writer construction, durable verification, and
serialization remain outside the independent external timer. D/E use an
experiment-owned validation-runtime wrapper around the real FullProofValidator
STRICT stack; their coordination-contaminated outer and validation timings are
retained only as structural evidence and are excluded by the model aggregator.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter_ns
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
    AdmissionComposition,
    CONTAMINATED_D_E_TIMING_FIELDS,
    DurableVerificationResult,
    EXPECTED_CONFIGURATION,
    EXPECTED_LIFECYCLE,
    IdempotencyLifecycleObservation,
    IdempotencyVerdictIdentity,
    Layer1ClassificationError,
    Layer1Path,
    Layer1Sample,
    Layer1SamplePlan,
    Layer1Schedule,
    MeasurementAvailability,
    PHASE_NAMES,
    PhaseRecord,
    ProducerOutcome,
    RunValidationResult,
    SCHEMA_VERSION,
    TimingEligibility,
    TransactionStatusIdentity,
    ValidationPlacementIdentity,
    classify_path,
    generate_recorded_schedule,
    generate_smoke_schedule,
    validate_run,
)


CANONICAL_AMOUNT = Decimal("100.00")
CONFLICTING_AMOUNT = Decimal("999.00")


class Layer1RuntimeError(RuntimeError):
    """Report experiment-owned setup or verification failures."""


@dataclass(frozen=True)
class TimedProducerInvocation:
    """Retain one external timing and ordinary producer exception marker."""

    value: Any | None
    elapsed_ns: int
    exception_type: str | None = None

    def __post_init__(self) -> None:
        if type(self.elapsed_ns) is not int or self.elapsed_ns < 0:
            raise ValueError("elapsed_ns must be a non-negative integer")
        if self.exception_type is None and self.value is None:
            raise ValueError("normal timed invocation requires a value")
        if self.exception_type is not None:
            if not self.exception_type or self.value is not None:
                raise ValueError("exception timing must retain only a type name")


@dataclass(frozen=True)
class Layer1RuntimeResult:
    """Return a complete fixed schedule and its structural validation result."""

    schedule: Layer1Schedule
    samples: tuple[Layer1Sample, ...]
    validation: RunValidationResult


@dataclass(frozen=True)
class _Fixture:
    request_id: str
    order_id: str
    outer_amount: Decimal
    winner_amount: Decimal | None


@dataclass(frozen=True)
class _DurableSnapshot:
    events: tuple[tuple[Any, ...], ...]
    idempotency_records: tuple[tuple[Any, ...], ...]


class _CoordinatingValidationRuntime:
    """Delegate to FullProof STRICT, then run correctness-only D/E coordination."""

    def __init__(self, delegate: Any, after_decision: Callable[[], None]) -> None:
        self._delegate = delegate
        self._after_decision = after_decision

    def decide(self, candidate_event: Any, context: Any) -> Any:
        decision = self._delegate.decide(candidate_event, context)
        self._after_decision()
        return decision


def time_public_producer_invocation(
    invocation: Callable[[], Any],
    *,
    clock: Callable[[], int] = perf_counter_ns,
) -> TimedProducerInvocation:
    """Time exactly one public producer call and catch ordinary Exception only."""

    started_ns = _read_clock(clock)
    try:
        value = invocation()
    except Exception as exc:
        stopped_ns = _read_clock(clock)
        return TimedProducerInvocation(
            value=None,
            elapsed_ns=_elapsed(started_ns, stopped_ns),
            exception_type=type(exc).__name__,
        )
    stopped_ns = _read_clock(clock)
    return TimedProducerInvocation(
        value=value,
        elapsed_ns=_elapsed(started_ns, stopped_ns),
    )


def execute_fixed_schedule(
    schedule: Layer1Schedule,
    execute_one: Callable[[Layer1SamplePlan], Layer1Sample],
) -> tuple[Layer1Sample, ...]:
    """Execute each predeclared plan once, without retry or adaptive extension."""

    return tuple(execute_one(plan) for plan in schedule.samples)


def run_layer1_smoke(
    database_url: str,
    *,
    run_id: str,
    clock: Callable[[], int] = perf_counter_ns,
) -> Layer1RuntimeResult:
    """Run one non-canonical correctness smoke for every A--H path."""

    return _run_schedule(
        database_url=database_url,
        run_id=run_id,
        schedule=generate_smoke_schedule(),
        clock=clock,
    )


def run_layer1_recorded(
    database_url: str,
    *,
    run_id: str,
    clock: Callable[[], int] = perf_counter_ns,
) -> Layer1RuntimeResult:
    """Run the fixed 80-sample schedule when separately authorized."""

    return _run_schedule(
        database_url=database_url,
        run_id=run_id,
        schedule=generate_recorded_schedule(),
        clock=clock,
    )


def _run_schedule(
    *,
    database_url: str,
    run_id: str,
    schedule: Layer1Schedule,
    clock: Callable[[], int],
) -> Layer1RuntimeResult:
    if not isinstance(database_url, str) or not database_url:
        raise ValueError("database_url must be a non-empty string")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")

    from src.storage.postgres_connection import connect_postgres

    connections = tuple(connect_postgres(database_url) for _ in range(3))
    control, producer, competitor = connections
    try:
        for connection in connections:
            _guard_test_connection(connection)

        def execute(plan: Layer1SamplePlan) -> Layer1Sample:
            _reset_database(control, connections)
            fixture = _fixture(run_id, plan)
            return _execute_postgres_sample(
                run_id=run_id,
                plan=plan,
                fixture=fixture,
                control=control,
                producer=producer,
                competitor=competitor,
                clock=clock,
            )

        samples = execute_fixed_schedule(schedule, execute)
        return Layer1RuntimeResult(
            schedule=schedule,
            samples=samples,
            validation=validate_run(schedule, samples),
        )
    finally:
        for connection in connections:
            with suppress(Exception):
                connection.rollback()
            connection.close()


def _execute_postgres_sample(
    *,
    run_id: str,
    plan: Layer1SamplePlan,
    fixture: _Fixture,
    control: Any,
    producer: Any,
    competitor: Any,
    clock: Callable[[], int],
) -> Layer1Sample:
    path = plan.path
    placement, composition, _ = EXPECTED_CONFIGURATION[path]
    winner_results: list[Any] = []

    seed_writer = _build_writer(
        competitor,
        validation_placement=ValidationPlacementIdentity.PRE_TRANSACTION,
        admission_composition=AdmissionComposition.PRE_OCC,
        validation_runtime=_build_full_proof_strict_runtime(),
    )

    if path in {Layer1Path.B, Layer1Path.G}:
        winner_results.append(
            _seed_accepted(seed_writer, fixture, amount=CANONICAL_AMOUNT)
        )
        _require_idle_and_reusable(competitor)
    elif path in {Layer1Path.C, Layer1Path.H}:
        winner_results.append(
            _seed_accepted(seed_writer, fixture, amount=CONFLICTING_AMOUNT)
        )
        _require_idle_and_reusable(competitor)

    before = _read_durable_snapshot(control, fixture)
    outer_validation_runtime = _build_full_proof_strict_runtime()
    if path in {Layer1Path.D, Layer1Path.E}:
        winner_amount = (
            CANONICAL_AMOUNT if path is Layer1Path.D else CONFLICTING_AMOUNT
        )

        def commit_winner() -> None:
            if winner_results:
                raise Layer1RuntimeError("D/E winner coordination ran more than once")
            winner_results.append(
                _seed_accepted(seed_writer, fixture, amount=winner_amount)
            )
            _require_idle_and_reusable(competitor)

        outer_validation_runtime = _CoordinatingValidationRuntime(
            outer_validation_runtime,
            commit_winner,
        )

    writer = _build_writer(
        producer,
        validation_placement=placement,
        admission_composition=composition,
        validation_runtime=outer_validation_runtime,
    )

    timed = time_public_producer_invocation(
        lambda: writer.create_order_with_measurement(
            request_id=fixture.request_id,
            order_id=fixture.order_id,
            amount=fixture.outer_amount,
        ),
        clock=clock,
    )

    if timed.exception_type is not None:
        with suppress(Exception):
            producer.rollback()
        return Layer1Sample(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            sample_index=plan.sample_index,
            planned_path=path,
            classified_path=None,
            validation_placement=placement,
            admission_composition=composition,
            external_elapsed_ns=timed.elapsed_ns,
            producer_outcome=None,
            idempotency_observations=(),
            measurement_availability=None,
            phases=None,
            producer_return_transaction_status=None,
            reuse_select_succeeded=None,
            final_transaction_status=None,
            durable_verification=DurableVerificationResult(
                verified=False,
                event_count=None,
                idempotency_record_count=None,
            ),
            timing_eligibility=_timing_eligibility(path),
            contaminated_timing_fields=_contaminated_fields(path),
            exception_type=timed.exception_type,
        )

    delivery = timed.value
    availability, phases, result = _measurement_evidence(delivery)
    producer_outcome = ProducerOutcome(_enum_value(result.outcome))
    classified_path: Layer1Path | None = None
    observations: tuple[IdempotencyLifecycleObservation, ...] = ()
    if phases is not None:
        try:
            classified_path = classify_path(
                validation_placement=placement,
                admission_composition=composition,
                producer_outcome=producer_outcome,
                phases=phases,
            )
        except Layer1ClassificationError:
            classified_path = None
        if classified_path is not None:
            observations = _idempotency_observations(classified_path, result)

    producer_return_status, reuse_ok, final_status = _verify_connection_reuse(
        producer
    )
    after = _read_durable_snapshot(control, fixture)
    durable = _verify_durable_state(
        path=path,
        fixture=fixture,
        before=before,
        after=after,
        result=result,
        winner_results=winner_results,
    )
    return Layer1Sample(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        sample_index=plan.sample_index,
        planned_path=path,
        classified_path=classified_path,
        validation_placement=placement,
        admission_composition=composition,
        external_elapsed_ns=timed.elapsed_ns,
        producer_outcome=producer_outcome,
        idempotency_observations=observations,
        measurement_availability=availability,
        phases=phases,
        producer_return_transaction_status=producer_return_status,
        reuse_select_succeeded=reuse_ok,
        final_transaction_status=final_status,
        durable_verification=durable,
        timing_eligibility=_timing_eligibility(path),
        contaminated_timing_fields=_contaminated_fields(path),
    )


def _build_full_proof_strict_runtime() -> Any:
    from src.compass.transition.runtime import (
        ValidationDispatcher,
        ValidationPolicy,
        ValidationRuntime,
    )
    from src.compass.transition.types import ValidationMode
    from src.compass.transition.validators import FullProofValidator, NoOpValidator

    return ValidationRuntime(
        dispatcher=ValidationDispatcher(
            strict_validator=FullProofValidator(),
            off_validator=NoOpValidator(),
        ),
        policy=ValidationPolicy(),
        mode=ValidationMode.STRICT,
    )


def _build_writer(
    connection: Any,
    *,
    validation_placement: ValidationPlacementIdentity,
    admission_composition: AdmissionComposition,
    validation_runtime: Any,
) -> Any:
    from src.pipeline.transactional.postgres_admission import (
        PostgresOptimisticAdmissionGate,
        PostgresPessimisticAdmissionGate,
    )
    from src.pipeline.transactional.postgres_write_side import (
        PostgresTransactionalWriteSide,
    )
    from src.pipeline.transactional.postgres_write_side_config import (
        PostgresWriteSideConfig,
        ValidationPlacement,
    )

    if admission_composition is AdmissionComposition.PRE_OCC:
        def gate_factory(uow: Any) -> Any:
            return PostgresOptimisticAdmissionGate(uow.event_store)
    else:
        def gate_factory(uow: Any) -> Any:
            return PostgresPessimisticAdmissionGate(
                connection=uow.connection,
                event_store=uow.event_store,
            )

    placement = ValidationPlacement(validation_placement.value)
    return PostgresTransactionalWriteSide(
        connection=connection,
        validation_runtime=validation_runtime,
        admission_gate_factory=gate_factory,
        config=PostgresWriteSideConfig(validation_placement=placement),
    )


def _seed_accepted(writer: Any, fixture: _Fixture, *, amount: Decimal) -> Any:
    from src.pipeline.transactional.postgres_write_side import (
        PostgresWriteSideOutcome,
    )

    result = writer.create_order(
        request_id=fixture.request_id,
        order_id=fixture.order_id,
        amount=amount,
    )
    if result.outcome is not PostgresWriteSideOutcome.ACCEPTED:
        raise Layer1RuntimeError("fixture writer did not return ACCEPTED")
    return result


def _measurement_evidence(
    delivery: Any,
) -> tuple[MeasurementAvailability, tuple[PhaseRecord, ...] | None, Any]:
    availability = MeasurementAvailability(_enum_value(delivery.availability))
    measurement = delivery.measurement
    phases = None
    if availability is MeasurementAvailability.AVAILABLE:
        if measurement is None:
            raise Layer1RuntimeError("AVAILABLE delivery omitted measurement")
        phases = tuple(
            PhaseRecord(
                name=name,
                state=_phase_state(getattr(measurement, name).state),
                elapsed_ns=getattr(measurement, name).elapsed_ns,
            )
            for name in PHASE_NAMES
        )
    elif measurement is not None:
        raise Layer1RuntimeError("UNAVAILABLE delivery unexpectedly retained phases")
    return availability, phases, delivery.producer_value


def _idempotency_observations(
    classified_path: Layer1Path,
    result: Any,
) -> tuple[IdempotencyLifecycleObservation, ...]:
    """Combine source-proven reach order with the exact returned final verdict."""

    expected = EXPECTED_LIFECYCLE[classified_path]
    final_position = expected[-1].position
    raw_verdict = _enum_value(result.idempotency_decision.verdict).upper()
    try:
        final_verdict = IdempotencyVerdictIdentity(raw_verdict)
    except ValueError:
        return ()
    return (
        *expected[:-1],
        IdempotencyLifecycleObservation(final_position, final_verdict),
    )


def _verify_connection_reuse(
    connection: Any,
) -> tuple[TransactionStatusIdentity, bool, TransactionStatusIdentity]:
    producer_status = _transaction_status(connection)
    reuse_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            reuse_ok = cursor.fetchone() == (1,)
    except Exception:
        reuse_ok = False
    finally:
        with suppress(Exception):
            connection.rollback()
    return producer_status, reuse_ok, _transaction_status(connection)


def _require_idle_and_reusable(connection: Any) -> None:
    producer, reuse_ok, final = _verify_connection_reuse(connection)
    if (
        producer is not TransactionStatusIdentity.IDLE
        or not reuse_ok
        or final is not TransactionStatusIdentity.IDLE
    ):
        raise Layer1RuntimeError("fixture connection was not IDLE and reusable")


def _read_durable_snapshot(control: Any, fixture: _Fixture) -> _DurableSnapshot:
    try:
        with control.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    accepted_event_id,
                    request_id,
                    order_id,
                    sequence,
                    amount
                FROM order_events
                WHERE order_id = %s
                ORDER BY sequence
                """,
                (fixture.order_id,),
            )
            events = tuple(cursor.fetchall())
            cursor.execute(
                """
                SELECT
                    request_id,
                    order_id,
                    command_type,
                    amount,
                    accepted_event_id,
                    result_sequence,
                    status
                FROM idempotency_records
                WHERE request_id = %s
                """,
                (fixture.request_id,),
            )
            records = tuple(cursor.fetchall())
    finally:
        control.rollback()
    return _DurableSnapshot(events=events, idempotency_records=records)


def _verify_durable_state(
    *,
    path: Layer1Path,
    fixture: _Fixture,
    before: _DurableSnapshot,
    after: _DurableSnapshot,
    result: Any,
    winner_results: list[Any],
) -> DurableVerificationResult:
    from src.compass.transition.types import ValidationMode

    event_count = len(after.events)
    record_count = len(after.idempotency_records)
    event_ids = {str(row[0]) for row in after.events}
    winner = winner_results[0] if len(winner_results) == 1 else None
    winner_event = None if winner is None else winner.accepted_event
    winner_event_id = None if winner_event is None else winner_event.event_id
    preexisting_unchanged = before == after
    winner_is_sole = (
        winner_event_id is not None
        and event_count == 1
        and event_ids == {winner_event_id}
    )
    record = result.idempotency_decision.record
    referenced_event = None if record is None else record.accepted_event
    result_references_winner = (
        winner_event is not None
        and (
            result.accepted_event == winner_event
            or referenced_event == winner_event
        )
    )
    validation = result.validation_decision
    validation_result = None if validation is None else validation.validation_result
    validation_reached = path in {
        Layer1Path.A,
        Layer1Path.D,
        Layer1Path.E,
        Layer1Path.F,
    }
    validation_ok = (
        validation_result is not None
        and validation_result.validator_name == "FullProofValidator"
        and validation_result.validation_mode is ValidationMode.STRICT
        if validation_reached
        else validation is None
    )
    losing_candidate_id = (
        None
        if validation_result is None
        else validation_result.candidate_event_id
    )
    losing_absent = (
        losing_candidate_id is not None and losing_candidate_id not in event_ids
    )

    if path in {Layer1Path.A, Layer1Path.F}:
        accepted = result.accepted_event
        verified = (
            validation_ok
            and event_count == 1
            and record_count == 1
            and accepted is not None
            and accepted.event_id in event_ids
        )
    elif path in {Layer1Path.B, Layer1Path.C, Layer1Path.G, Layer1Path.H}:
        verified = (
            validation_ok
            and preexisting_unchanged
            and event_count == 1
            and record_count == 1
            and winner is not None
        )
    else:
        verified = (
            validation_ok
            and event_count == 1
            and record_count == 1
            and winner_is_sole
            and result_references_winner
            and (path is not Layer1Path.E or losing_absent)
        )

    return DurableVerificationResult(
        verified=verified,
        event_count=event_count,
        idempotency_record_count=record_count,
        preexisting_state_unchanged=(
            preexisting_unchanged
            if path in {Layer1Path.B, Layer1Path.C, Layer1Path.G, Layer1Path.H}
            else None
        ),
        winner_is_sole_event=(
            winner_is_sole if path in {Layer1Path.D, Layer1Path.E} else None
        ),
        result_references_winner=(
            result_references_winner
            if path in {Layer1Path.D, Layer1Path.E}
            else None
        ),
        losing_candidate_absent=(losing_absent if path is Layer1Path.E else None),
    )


def _fixture(run_id: str, plan: Layer1SamplePlan) -> _Fixture:
    token = f"{run_id}:{plan.sample_index}:{plan.path.value}"
    request_id = str(uuid5(NAMESPACE_URL, f"{token}:request"))
    order_id = str(uuid5(NAMESPACE_URL, f"{token}:order"))
    winner_amount = None
    if plan.path in {Layer1Path.B, Layer1Path.D, Layer1Path.G}:
        winner_amount = CANONICAL_AMOUNT
    elif plan.path in {Layer1Path.C, Layer1Path.E, Layer1Path.H}:
        winner_amount = CONFLICTING_AMOUNT
    return _Fixture(
        request_id=request_id,
        order_id=order_id,
        outer_amount=CANONICAL_AMOUNT,
        winner_amount=winner_amount,
    )


def _guard_test_connection(connection: Any) -> None:
    if connection.autocommit:
        raise Layer1RuntimeError("Layer 1 requires autocommit disabled")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
    finally:
        connection.rollback()
    if row is None or not isinstance(row[0], str) or not row[0].endswith("_test"):
        raise Layer1RuntimeError("refusing Layer 1 outside a database ending _test")
    _require_idle_and_reusable(connection)


def _reset_database(control: Any, all_connections: tuple[Any, ...]) -> None:
    for connection in all_connections:
        _require_idle_and_reusable(connection)
    with control.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE
                decision_receipts,
                projection_snapshots,
                projection_order_progress,
                projection_checkpoints,
                projection_states,
                idempotency_records,
                order_events
            RESTART IDENTITY CASCADE
            """
        )
    control.commit()
    for connection in all_connections:
        _require_idle_and_reusable(connection)


def _phase_state(value: Any):
    from experiments.stage4b2.postgres_idempotency_lifecycle_characterization import (
        PhaseState,
    )

    return PhaseState(_enum_value(value))


def _transaction_status(connection: Any) -> TransactionStatusIdentity:
    name = getattr(connection.info.transaction_status, "name", None)
    try:
        return TransactionStatusIdentity(name)
    except ValueError:
        return TransactionStatusIdentity.UNKNOWN


def _timing_eligibility(path: Layer1Path) -> TimingEligibility:
    return (
        TimingEligibility.STRUCTURAL_ONLY_COORDINATION_CONTAMINATED
        if path in {Layer1Path.D, Layer1Path.E}
        else TimingEligibility.UNCONTAMINATED
    )


def _contaminated_fields(path: Layer1Path) -> tuple[str, ...]:
    return (
        CONTAMINATED_D_E_TIMING_FIELDS
        if path in {Layer1Path.D, Layer1Path.E}
        else ()
    )


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        raise Layer1RuntimeError("runtime evidence contained an invalid enum value")
    return raw


def _read_clock(clock: Callable[[], int]) -> int:
    reading = clock()
    if type(reading) is not int:
        raise TypeError("external clock must return integer nanoseconds")
    return reading


def _elapsed(started_ns: int, stopped_ns: int) -> int:
    elapsed_ns = stopped_ns - started_ns
    if elapsed_ns < 0:
        raise Layer1RuntimeError("external clock moved backwards")
    return elapsed_ns
