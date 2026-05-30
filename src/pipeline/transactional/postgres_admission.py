"""PostgreSQL-backed admission gates.

Admission decides whether a candidate event may occupy the next
accepted-history stream position.

This module does not own:
- domain legality
- Compass validation truth
- idempotency replay / conflict classification
- transaction commit / rollback orchestration
- Stage 4 SemanticOutcome mapping
"""

from __future__ import annotations

from psycopg.errors import LockNotAvailable, UniqueViolation

from src.core.order.events import OrderEvent
from src.pipeline.transactional.admission import AdmissionResult, AdmissionVerdict
from src.storage.errors import (
    AppendConflictError,
    StaleWriteError,
    StorageInfrastructureError,
)
from src.storage.postgres_event_store import PostgresEventStore


class PostgresOptimisticAdmissionGate:
    """PostgreSQL-backed optimistic admission strategy.

    Strategy:
    - do not lock first
    - do not pre-read current version in the gate
    - attempt append through PostgresEventStore
    - translate append-time persistence conflicts into stable AdmissionResult values
    """

    def __init__(self, event_store: PostgresEventStore):
        self.event_store = event_store

    def admit(
        self,
        candidate_event: OrderEvent,
        expected_current_version: int,
    ) -> AdmissionResult:
        try:
            self.event_store.append(
                candidate_event,
                expected_current_version=expected_current_version,
            )
        except (ValueError, StaleWriteError, AppendConflictError) as exc:
            return AdmissionResult(
                verdict=AdmissionVerdict.STALE_WRITE,
                reason=(
                    "Stale write rejected by PostgreSQL optimistic admission gate: "
                    f"{exc}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )
        except UniqueViolation as exc:
            if _is_stream_position_conflict(exc):
                return AdmissionResult(
                    verdict=AdmissionVerdict.STALE_WRITE,
                    reason=(
                        "Append-time stream position conflict rejected by "
                        "PostgreSQL optimistic admission gate"
                    ),
                    candidate_event_id=candidate_event.event_id,
                    accepted_event_id=None,
                )

            return AdmissionResult(
                verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                reason=(
                    "Unexpected unique constraint violation during PostgreSQL "
                    f"optimistic admission: {exc}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )
        except LockNotAvailable as exc:
            return AdmissionResult(
                verdict=AdmissionVerdict.LOCK_TIMEOUT,
                reason=(
                    "Lock was not available during PostgreSQL optimistic admission: "
                    f"{exc}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )
        except StorageInfrastructureError as exc:
            return AdmissionResult(
                verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
                reason=(
                    "Storage infrastructure failure during PostgreSQL "
                    f"optimistic admission: {exc}"
                ),
                candidate_event_id=candidate_event.event_id,
                accepted_event_id=None,
            )

        return AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="Event admitted by PostgreSQL optimistic admission gate",
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

    if constraint_name in known_stream_position_constraints:
        return True

    return (
        "order" in constraint_name
        and "sequence" in constraint_name
    )