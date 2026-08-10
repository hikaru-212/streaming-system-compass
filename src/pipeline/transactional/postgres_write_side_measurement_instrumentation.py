"""Stage 4B.2 production instrumentation for PostgreSQL write measurement.

The instrumentation is producer-specific and invocation-local. Existing
unmeasured APIs create no recorder, perform no clock reads, and construct no
measurement artifact. The shared write algorithm retains small recorder-
absence branches; their observer cost is deliberately left for later
experiment evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import time
from typing import TYPE_CHECKING, TypeVar

from psycopg import Connection

from src.pipeline.transactional.admission import ConcurrencyGate
from src.pipeline.transactional.postgres_admission import (
    PostgresPessimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)
from src.pipeline.transactional.postgres_write_side_config import (
    ValidationPlacement,
)
from src.storage.postgres_event_store import PostgresEventStore

if TYPE_CHECKING:
    from src.pipeline.transactional.postgres_write_side_measurement import (
        PostgresWriteSideMeasurementDelivery,
    )


class _PostgresWriteSideMeasurementPhase(str, Enum):
    """Name the exact PR3 fields owned by invocation-local collection."""

    PRODUCER_WRITE_INVOCATION = "producer_write_invocation"
    BUSINESS_UOW = "business_uow"
    VALIDATION_RUNTIME_CALL = "validation_runtime_call"
    PRELIMINARY_IDEMPOTENCY_CHECK = "preliminary_idempotency_check"
    PRELIMINARY_READ_CLEANUP = "preliminary_read_cleanup"
    AUTHORITATIVE_IDEMPOTENCY_CHECK = "authoritative_idempotency_check"
    ACCEPTED_HISTORY_LOAD = "accepted_history_load"
    CONCURRENCY_PREPARATION_CALL = "concurrency_preparation_call"
    PESSIMISTIC_ADVISORY_TRY_LOCK_CALL = (
        "pessimistic_advisory_try_lock_call"
    )
    APPEND_ADMISSION_CALL = "append_admission_call"
    IDEMPOTENCY_RECORD_CALL = "idempotency_record_call"
    COMMIT_FINALIZATION = "commit_finalization"
    ROLLBACK_FINALIZATION = "rollback_finalization"


@dataclass
class _PhaseReading:
    """Retain mutable collection state before immutable PR3 construction."""

    applicable: bool
    reached: bool = False
    elapsed_ns: int | None = None


_T = TypeVar("_T")


class _PostgresWriteSideMeasurementRecorder:
    """Collect one measured write invocation without owning business behavior.

    Clock exceptions, invalid types (including booleans), and backwards
    readings leave only the reached phase in ``NOT_COLLECTED`` form. The
    recorder never catches the operation supplied to ``measure_call``.

    If either whole-invocation clock read fails, normal business execution is
    still preserved. The required whole phase then cannot satisfy the frozen
    PR3 snapshot invariant, so post-return delivery becomes unavailable.
    """

    def __init__(
        self,
        *,
        validation_placement: ValidationPlacement,
        clock: Callable[[], int],
    ) -> None:
        if not isinstance(validation_placement, ValidationPlacement):
            raise TypeError("validation_placement must be ValidationPlacement")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._clock = clock
        self._readings = {
            phase: _PhaseReading(
                applicable=self._initial_applicability(
                    phase,
                    validation_placement=validation_placement,
                )
            )
            for phase in _PostgresWriteSideMeasurementPhase
        }

    def start(self, phase: _PostgresWriteSideMeasurementPhase) -> int | None:
        """Mark a phase reached and return a valid starting clock reading."""
        reading = self._reading(phase)
        reading.applicable = True
        reading.reached = True
        reading.elapsed_ns = None
        return self._read_clock()

    def finish(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
        started_ns: int | None,
    ) -> None:
        """Retain a completed non-negative delta or leave NOT_COLLECTED."""
        if started_ns is None:
            return

        stopped_ns = self._read_clock()
        if stopped_ns is None or stopped_ns < started_ns:
            return

        self._reading(phase).elapsed_ns = stopped_ns - started_ns

    def measure_call(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
        operation: Callable[[], _T],
    ) -> _T:
        """Measure only a normally returning operation without catching it."""
        started_ns = self.start(phase)
        result = operation()
        self.finish(phase, started_ns)
        return result

    def mark_applicable(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
    ) -> None:
        """Mark an unreached phase applicable to the concrete composition."""
        reading = self._reading(phase)
        if not reading.reached:
            reading.applicable = True

    def mark_not_applicable(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
    ) -> None:
        """Mark an unreached phase absent from the concrete composition."""
        reading = self._reading(phase)
        if not reading.reached:
            reading.applicable = False

    def build_delivery(
        self,
        producer_value: object,
    ) -> PostgresWriteSideMeasurementDelivery:
        """Build available evidence or preserve the value with unavailability.

        ADR 0023 makes ``Exception`` intentionally broad by ownership, while
        this block remains narrow by code location. It contains only translation
        of retained readings, immutable measurement construction, and AVAILABLE
        delivery construction after the existing producer returned normally.
        It contains no producer work, clock read, callback, I/O, transaction
        finalization, persistence, telemetry, or correctness-required logging.
        """
        from src.pipeline.transactional.postgres_write_side_measurement import (
            PostgresWriteSideMeasurementAvailability,
            PostgresWriteSideMeasurementDelivery,
        )

        # Every Exception owned by this pure post-return construction block is
        # measurement unavailability under ADR 0023, not a business failure.
        # The existing producer call is deliberately outside this try block.
        try:
            measurement = self._build_measurement()
            return PostgresWriteSideMeasurementDelivery(
                producer_value=producer_value,  # type: ignore[arg-type]
                availability=(
                    PostgresWriteSideMeasurementAvailability.AVAILABLE
                ),
                measurement=measurement,
            )
        except Exception:
            return PostgresWriteSideMeasurementDelivery(
                producer_value=producer_value,  # type: ignore[arg-type]
                availability=(
                    PostgresWriteSideMeasurementAvailability.UNAVAILABLE
                ),
                measurement=None,
            )

    def _build_measurement(self):
        """Construct the exact frozen PR3 snapshot from retained readings."""
        from src.pipeline.transactional.postgres_write_side_measurement import (
            PostgresWriteSideMeasurement,
        )

        phase = _PostgresWriteSideMeasurementPhase
        return PostgresWriteSideMeasurement(
            producer_write_invocation=self._phase_measurement(
                phase.PRODUCER_WRITE_INVOCATION
            ),
            business_uow=self._phase_measurement(phase.BUSINESS_UOW),
            validation_runtime_call=self._phase_measurement(
                phase.VALIDATION_RUNTIME_CALL
            ),
            preliminary_idempotency_check=self._phase_measurement(
                phase.PRELIMINARY_IDEMPOTENCY_CHECK
            ),
            preliminary_read_cleanup=self._phase_measurement(
                phase.PRELIMINARY_READ_CLEANUP
            ),
            authoritative_idempotency_check=self._phase_measurement(
                phase.AUTHORITATIVE_IDEMPOTENCY_CHECK
            ),
            accepted_history_load=self._phase_measurement(
                phase.ACCEPTED_HISTORY_LOAD
            ),
            concurrency_preparation_call=self._phase_measurement(
                phase.CONCURRENCY_PREPARATION_CALL
            ),
            pessimistic_advisory_try_lock_call=self._phase_measurement(
                phase.PESSIMISTIC_ADVISORY_TRY_LOCK_CALL
            ),
            append_admission_call=self._phase_measurement(
                phase.APPEND_ADMISSION_CALL
            ),
            idempotency_record_call=self._phase_measurement(
                phase.IDEMPOTENCY_RECORD_CALL
            ),
            commit_finalization=self._phase_measurement(
                phase.COMMIT_FINALIZATION
            ),
            rollback_finalization=self._phase_measurement(
                phase.ROLLBACK_FINALIZATION
            ),
        )

    def _phase_measurement(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
    ):
        """Translate one mutable reading into the frozen PR3 state model."""
        from src.pipeline.transactional.postgres_write_side_measurement import (
            PostgresWriteSidePhaseMeasurement,
            PostgresWriteSidePhaseMeasurementState,
        )

        reading = self._reading(phase)
        state = PostgresWriteSidePhaseMeasurementState
        if not reading.applicable:
            return PostgresWriteSidePhaseMeasurement(state=state.NOT_APPLICABLE)
        if not reading.reached:
            return PostgresWriteSidePhaseMeasurement(state=state.NOT_REACHED)
        if reading.elapsed_ns is None:
            return PostgresWriteSidePhaseMeasurement(state=state.NOT_COLLECTED)
        return PostgresWriteSidePhaseMeasurement(
            state=state.MEASURED,
            elapsed_ns=reading.elapsed_ns,
        )

    def _read_clock(self) -> int | None:
        """Return one safe integer reading without affecting business flow."""
        try:
            reading = self._clock()
        except Exception:
            return None

        if isinstance(reading, bool) or not isinstance(reading, int):
            return None
        return reading

    def _reading(
        self,
        phase: _PostgresWriteSideMeasurementPhase,
    ) -> _PhaseReading:
        if not isinstance(phase, _PostgresWriteSideMeasurementPhase):
            raise TypeError("phase must be _PostgresWriteSideMeasurementPhase")
        return self._readings[phase]

    @staticmethod
    def _initial_applicability(
        phase: _PostgresWriteSideMeasurementPhase,
        *,
        validation_placement: ValidationPlacement,
    ) -> bool:
        preliminary_phases = {
            _PostgresWriteSideMeasurementPhase
            .PRELIMINARY_IDEMPOTENCY_CHECK,
            _PostgresWriteSideMeasurementPhase.PRELIMINARY_READ_CLEANUP,
        }
        if phase in preliminary_phases:
            return validation_placement is ValidationPlacement.PRE_TRANSACTION

        if (
            phase
            is _PostgresWriteSideMeasurementPhase
            .PESSIMISTIC_ADVISORY_TRY_LOCK_CALL
        ):
            # Stage 4B.2's accepted IN composition uses the current concrete
            # pessimistic gate. If preparation is reached, the actual gate
            # instance below confirms or removes this applicability.
            return validation_placement is ValidationPlacement.IN_TRANSACTION

        return True


class _MeasuredPostgresWriteSideUnitOfWork(PostgresWriteSideUnitOfWork):
    """Time current UOW/finalization methods without changing their semantics."""

    def __init__(
        self,
        connection: Connection,
        recorder: _PostgresWriteSideMeasurementRecorder,
    ) -> None:
        super().__init__(connection)
        self._measurement_recorder = recorder
        self._business_uow_started_ns: int | None = None

    def __enter__(self) -> PostgresWriteSideUnitOfWork:
        self._business_uow_started_ns = self._measurement_recorder.start(
            _PostgresWriteSideMeasurementPhase.BUSINESS_UOW
        )
        return super().__enter__()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        result = super().__exit__(exc_type, exc, traceback)
        self._measurement_recorder.finish(
            _PostgresWriteSideMeasurementPhase.BUSINESS_UOW,
            self._business_uow_started_ns,
        )
        return result

    def commit(self) -> None:
        return self._measurement_recorder.measure_call(
            _PostgresWriteSideMeasurementPhase.COMMIT_FINALIZATION,
            super().commit,
        )

    def rollback(self) -> None:
        return self._measurement_recorder.measure_call(
            _PostgresWriteSideMeasurementPhase.ROLLBACK_FINALIZATION,
            super().rollback,
        )


class _MeasuredPostgresPessimisticAdmissionGate(
    PostgresPessimisticAdmissionGate
):
    """Measure the concrete try-lock while reusing current gate algorithms."""

    def __init__(
        self,
        *,
        connection: Connection,
        event_store: PostgresEventStore,
        recorder: _PostgresWriteSideMeasurementRecorder,
    ) -> None:
        super().__init__(
            connection=connection,
            event_store=event_store,
        )
        self._measurement_recorder = recorder

    def _try_lock_stream(self, order_id: str) -> bool:
        return self._measurement_recorder.measure_call(
            _PostgresWriteSideMeasurementPhase
            .PESSIMISTIC_ADVISORY_TRY_LOCK_CALL,
            lambda: super(
                _MeasuredPostgresPessimisticAdmissionGate,
                self,
            )._try_lock_stream(order_id),
        )


def _new_measurement_recorder(
    validation_placement: ValidationPlacement,
) -> _PostgresWriteSideMeasurementRecorder:
    """Create one recorder with the production monotonic nanosecond clock."""
    return _PostgresWriteSideMeasurementRecorder(
        validation_placement=validation_placement,
        clock=time.perf_counter_ns,
    )


def _new_measured_uow(
    connection: Connection,
    recorder: _PostgresWriteSideMeasurementRecorder,
) -> PostgresWriteSideUnitOfWork:
    """Create the measured UOW adapter only for an explicit measured call."""
    return _MeasuredPostgresWriteSideUnitOfWork(connection, recorder)


def _instrument_concrete_pessimistic_gate(
    gate: ConcurrencyGate,
    recorder: _PostgresWriteSideMeasurementRecorder,
) -> ConcurrencyGate:
    """Adapt only the current concrete pessimistic gate before preparation.

    The admission factory remains authoritative and is always invoked first.
    When it returns the exact current concrete pessimistic class, this seam
    creates the measured subclass from the gate's public constructor inputs.
    It neither copies private preparation state nor retains a bound private
    try-lock method. Factory-specific subclasses are left unchanged.
    """
    phase = (
        _PostgresWriteSideMeasurementPhase
        .PESSIMISTIC_ADVISORY_TRY_LOCK_CALL
    )
    if type(gate) is PostgresPessimisticAdmissionGate:
        recorder.mark_applicable(phase)
        return _MeasuredPostgresPessimisticAdmissionGate(
            connection=gate.connection,
            event_store=gate.event_store,
            recorder=recorder,
        )

    recorder.mark_not_applicable(phase)
    return gate
