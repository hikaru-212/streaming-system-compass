"""PostgreSQL-backed admission gates.

Admission decides whether a writer may enter an aggregate-stream critical
section and whether a candidate event may occupy the next accepted-history
stream position.

This module does not own:
- domain legality
- Compass validation truth
- idempotency replay / conflict classification
- transaction commit / rollback orchestration
- Stage 4 SemanticOutcome mapping
"""

from __future__ import annotations

from psycopg import Connection
from psycopg.errors import LockNotAvailable, UniqueViolation

from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    StreamAdmissionResult,
)
from src.storage.errors import (
    AppendConflictError,
    StaleWriteError,
    StorageInfrastructureError,
)
from src.storage.postgres_event_store import PostgresEventStore


class PostgresOptimisticAdmissionGate:
    """PostgreSQL-backed optimistic admission strategy.

    Strategy:
    - do not pre-lock the stream
    - use prepare_stream as a no-op
    - do not pre-read current version in the gate
    - attempt append through PostgresEventStore
    - translate append-time persistence conflicts into stable AdmissionResult values
    """

    def __init__(self, event_store: PostgresEventStore):
        self.event_store = event_store

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        return StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="PostgreSQL optimistic admission does not pre-lock stream",
            order_id=order_id,
        )

    def admit(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        return _append_with_translation(
            event_store=self.event_store,
            candidate_event=candidate_event,
            expected_current_version=expected_current_version,
            gate_name="PostgreSQL optimistic admission gate",
        )


class PostgresPessimisticAdmissionGate:
    """PostgreSQL-backed pessimistic admission strategy.

    Strategy:
    - acquire a transaction-scoped advisory lock during stream preparation
    - only append after the stream lock has been acquired
    - return LOCK_TIMEOUT if the stream lock cannot be acquired immediately
    - translate append-time persistence conflicts into stable AdmissionResult values

    The advisory lock is transaction-scoped. It is released by PostgreSQL when
    the surrounding transaction commits or rolls back.

    This gate does not commit or roll back the transaction. Transaction
    lifecycle remains owned by the write-side unit of work / caller.
    """

    def __init__(
        self,
        *,
        connection: Connection,
        event_store: PostgresEventStore,
    ):
        self.connection = connection
        self.event_store = event_store
        self._prepared_order_ids: set[str] = set()

    def prepare_stream(self, order_id: str) -> StreamAdmissionResult:
        if self.connection.autocommit:
            return StreamAdmissionResult(
                verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                reason=(
                    "PostgreSQL pessimistic admission gate requires a "
                    "transaction-scoped connection, but connection.autocommit "
                    "is enabled"
                ),
                order_id=order_id,
            )

        lock_acquired = self._try_lock_stream(order_id)

        if not lock_acquired:
            return StreamAdmissionResult(
                verdict=AdmissionVerdict.LOCK_TIMEOUT,
                reason=(
                    "Stream lock was not available for PostgreSQL pessimistic "
                    f"admission gate: order_id={order_id}"
                ),
                order_id=order_id,
            )

        self._prepared_order_ids.add(order_id)

        return StreamAdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason=(
                "Stream lock acquired by PostgreSQL pessimistic admission gate: "
                f"order_id={order_id}"
            ),
            order_id=order_id,
        )

    def admit(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        if candidate_event.order_id not in self._prepared_order_ids:
            return AdmissionResult(
                verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                reason=(
                    "PostgreSQL pessimistic admission gate requires "
                    "prepare_stream(order_id) before append-time admission: "
                    f"order_id={candidate_event.order_id}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )

        return _append_with_translation(
            event_store=self.event_store,
            candidate_event=candidate_event,
            expected_current_version=expected_current_version,
            gate_name="PostgreSQL pessimistic admission gate",
        )

    def _try_lock_stream(self, order_id: str) -> bool:
        """Try to acquire a transaction-scoped advisory lock for one stream.

        The two-argument advisory lock form creates a namespace-like key:

        - first hash: lock namespace for order event streams
        - second hash: aggregate stream identity

        This keeps different order_id streams from blocking each other while
        making writers for the same order_id compete for the same lock.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_try_advisory_xact_lock(
                    hashtext(%s),
                    hashtext(%s)
                )
                """,
                ("order_events_stream", order_id),
            )
            result = cursor.fetchone()

        return bool(result[0])


def _append_with_translation(
    *,
    event_store: PostgresEventStore,
    candidate_event: OrderEvent,
    expected_current_version: int,
    gate_name: str,
) -> AdmissionResult:
    try:
        event_store.append(
            candidate_event,
            expected_current_version=expected_current_version,
        )
    except (ValueError, StaleWriteError, AppendConflictError) as exc:
        return AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason=f"Stale write rejected by {gate_name}: {exc}",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=None,
        )
    except UniqueViolation as exc:
        if _is_stream_position_conflict(exc):
            return AdmissionResult(
                verdict=AdmissionVerdict.STALE_WRITE,
                reason=(
                    "Append-time stream position conflict rejected by "
                    f"{gate_name}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )

        return AdmissionResult(
            verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
            reason=(
                "Unexpected unique constraint violation during "
                f"{gate_name}: {exc}"
            ),
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=None,
        )
    except LockNotAvailable as exc:
        return AdmissionResult(
            verdict=AdmissionVerdict.LOCK_TIMEOUT,
            reason=f"Lock was not available during {gate_name}: {exc}",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=None,
        )
    except StorageInfrastructureError as exc:
        return AdmissionResult(
            verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
            reason=f"Storage infrastructure failure during {gate_name}: {exc}",
            candidate_event_id=candidate_event.event_id,
            accepted_event_id=None,
        )

    return AdmissionResult(
        verdict=AdmissionVerdict.ADMITTED,
        reason=f"Event admitted by {gate_name}",
        candidate_event_id=candidate_event.event_id,
        accepted_event_id=candidate_event.event_id,
    )


def _is_stream_position_conflict(exc: UniqueViolation) -> bool:
    """Return whether a UniqueViolation represents stream position occupation.

    PostgreSQL reports many different unique constraint failures through the
    same exception class.

    Only the accepted-history stream-position constraint should be translated
    into STALE_WRITE. Other unique failures may represent identity bugs,
    schema issues, or unrelated persistence problems.
    """

    constraint_name = getattr(exc.diag, "constraint_name", None)

    if constraint_name is None:
        return False

    known_stream_position_constraints = {
        # Explicit constraint name from db/migrations/001_create_write_side_tables.sql
        "uq_order_events_order_sequence",
        # Common PostgreSQL auto-generated or future explicit alternatives.
        "order_events_order_id_sequence_key",
        "uq_order_events_order_id_sequence",
    }

    return constraint_name in known_stream_position_constraints