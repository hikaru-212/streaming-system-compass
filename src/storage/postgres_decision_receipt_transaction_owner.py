"""Commit-aware PostgreSQL transaction ownership for DecisionReceipt persistence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from psycopg import Connection
from psycopg.errors import IdleInTransactionSessionTimeout
from psycopg.pq import TransactionStatus

from src.compass.runtime.decision_receipt import DecisionReceipt
from src.storage.decision_receipt_store import (
    DecisionReceiptConflictError,
    DecisionReceiptInsertResult,
    DecisionReceiptMaterializationProvenance,
)
from src.storage.postgres_decision_receipt_store import (
    PostgresDecisionReceiptStore,
)


__all__ = [
    "PostgresDecisionReceiptConnectionFactory",
    "DecisionReceiptTransactionDurability",
    "DecisionReceiptRollbackDisposition",
    "DecisionReceiptConnectionDisposition",
    "DecisionReceiptTransactionFailureCategory",
    "DecisionReceiptCleanupFailureCategory",
    "PostgresDecisionReceiptTransactionResult",
    "PostgresDecisionReceiptTransactionOwner",
]


_IDLE_OWNER_TIMEOUT_SQLSTATE = "25P03"
_SET_LOCAL_IDLE_OWNER_TIMEOUT_SQL = """
    SELECT set_config(
        'idle_in_transaction_session_timeout',
        %s,
        true
    )
"""


class PostgresDecisionReceiptConnectionFactory(Protocol):
    """Acquire one dedicated PostgreSQL governance connection per operation.

    Responsibility:
        Return a psycopg connection dedicated to one DecisionReceipt persistence
        operation. The transaction owner, not the factory caller, owns the
        returned connection's completion and close lifecycle.

    Guarantees:
        Each call supplies an independently owned connection rather than an
        accepted-event business transaction connection.

    Non-guarantees:
        This first-version protocol defines no pool lease, healthy release,
        invalidation, retry, configuration loading, or business orchestration.
    """

    def __call__(self) -> Connection[object]:
        """Return one dedicated connection and transfer its lifecycle.

        Returns:
            A psycopg connection intended exclusively for one receipt
            governance operation.

        Guarantees:
            A returned connection is owned by the transaction owner until it
            is closed or discarded.

        Non-guarantees:
            Acquisition does not begin, commit, or roll back a transaction and
            defines no pooling or retry behavior.
        """
        ...


class DecisionReceiptTransactionDurability(str, Enum):
    """Classify commit-aware durability for one receipt governance transaction.

    ``COMMITTED`` requires acknowledged commit. ``NOT_COMMITTED`` requires a
    known pre-commit failure or the characterized server-side idle-owner
    rollback. ``UNKNOWN`` preserves unacknowledged commit-phase ambiguity.
    These values describe technical persistence only and authorize no retry or
    semantic interpretation.
    """

    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    UNKNOWN = "UNKNOWN"


class DecisionReceiptRollbackDisposition(str, Enum):
    """Describe client rollback handling without implying transaction durability.

    ``NOT_REQUIRED`` means no rollback was needed, ``CONFIRMED`` means rollback
    returned successfully, ``FAILED`` preserves rollback cleanup failure, and
    ``NOT_POSSIBLE`` covers invalid-entry, terminated, or commit-ambiguous
    connections on which client rollback is not an authoritative cleanup step.
    """

    NOT_REQUIRED = "NOT_REQUIRED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    NOT_POSSIBLE = "NOT_POSSIBLE"


class DecisionReceiptConnectionDisposition(str, Enum):
    """Describe final handling of an acquired dedicated governance connection.

    ``CLOSED`` records normal healthy close, ``DISCARDED`` records close of a
    connection that must not be reused, and ``CLEANUP_FAILED`` records that the
    close attempt itself failed. This enum does not define pool semantics.
    """

    CLOSED = "CLOSED"
    DISCARDED = "DISCARDED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


class DecisionReceiptTransactionFailureCategory(str, Enum):
    """Provide stable technical failure phases for transaction-owner results.

    Categories identify acquisition, connection-entry, timeout-configuration,
    statement-store, typed conflict, commit, and characterized idle-owner
    failures. They do not duplicate receipt conflict categories, expose raw
    driver text, or imply semantic invalidity, retry, policy, or business
    failure.
    """

    CONNECTION_ACQUISITION_FAILED = "CONNECTION_ACQUISITION_FAILED"
    AUTOCOMMIT_ENABLED = "AUTOCOMMIT_ENABLED"
    TRANSACTION_NOT_IDLE = "TRANSACTION_NOT_IDLE"
    CONNECTION_STATE_UNAVAILABLE = "CONNECTION_STATE_UNAVAILABLE"
    TIMEOUT_CONFIGURATION_FAILED = "TIMEOUT_CONFIGURATION_FAILED"
    STORE_OPERATION_FAILED = "STORE_OPERATION_FAILED"
    CONFLICT = "CONFLICT"
    COMMIT_FAILED = "COMMIT_FAILED"
    IDLE_OWNER_TIMEOUT = "IDLE_OWNER_TIMEOUT"


class DecisionReceiptCleanupFailureCategory(str, Enum):
    """Preserve safe cleanup-failure evidence separately from durability.

    Rollback and connection-close failures are recorded without raw exception
    text. Cleanup evidence never changes an already established ``COMMITTED``,
    ``NOT_COMMITTED``, or ``UNKNOWN`` durability classification and carries no
    retry or semantic authority.
    """

    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    CONNECTION_CLOSE_FAILED = "CONNECTION_CLOSE_FAILED"


@dataclass(frozen=True)
class PostgresDecisionReceiptTransactionResult:
    """Return commit-aware technical evidence for one receipt transaction.

    Args:
        durability: Acknowledged, known non-committed, or unknown durability.
        rollback_disposition: How client rollback was handled.
        statement_result: Optional statement-only store evidence. Its presence
            never overrides ``durability``. For ``IDLE_OWNER_TIMEOUT``, presence
            asserts that the store statement completed before termination was
            observed; absence means no completed statement evidence is claimed.
        failure_category: Stable owner-phase failure classification, if any.
        conflict_error: Existing safe typed receipt-conflict evidence, if any.
        connection_disposition: Final handling of an acquired connection, or
            ``None`` when acquisition never succeeded.
        sqlstate: Safe PostgreSQL SQLSTATE metadata when available.
        cleanup_failures: Immutable rollback or close failure evidence.

    Guarantees:
        Typed conflict evidence remains separate from generic failure category,
        statement success becomes durable only after acknowledged commit, and
        cleanup failures do not rewrite primary durability.

    Non-guarantees:
        This result does not infer semantic validity, business-command success,
        retry candidacy, retry authorization, policy, operator action, fallback,
        reconciliation, trace evidence, or pool disposition.
    """

    durability: DecisionReceiptTransactionDurability
    rollback_disposition: DecisionReceiptRollbackDisposition
    statement_result: DecisionReceiptInsertResult | None = None
    failure_category: DecisionReceiptTransactionFailureCategory | None = None
    conflict_error: DecisionReceiptConflictError | None = None
    connection_disposition: DecisionReceiptConnectionDisposition | None = None
    sqlstate: str | None = None
    cleanup_failures: tuple[DecisionReceiptCleanupFailureCategory, ...] = ()

    def __post_init__(self) -> None:
        """Validate immutable technical evidence without adding policy meaning."""
        if not isinstance(
            self.durability,
            DecisionReceiptTransactionDurability,
        ):
            raise TypeError(
                "durability must be DecisionReceiptTransactionDurability"
            )
        if not isinstance(
            self.rollback_disposition,
            DecisionReceiptRollbackDisposition,
        ):
            raise TypeError(
                "rollback_disposition must be "
                "DecisionReceiptRollbackDisposition"
            )
        if self.statement_result is not None and not isinstance(
            self.statement_result,
            DecisionReceiptInsertResult,
        ):
            raise TypeError(
                "statement_result must be DecisionReceiptInsertResult or None"
            )
        if self.failure_category is not None and not isinstance(
            self.failure_category,
            DecisionReceiptTransactionFailureCategory,
        ):
            raise TypeError(
                "failure_category must be "
                "DecisionReceiptTransactionFailureCategory or None"
            )
        if self.conflict_error is not None and not isinstance(
            self.conflict_error,
            DecisionReceiptConflictError,
        ):
            raise TypeError(
                "conflict_error must be DecisionReceiptConflictError or None"
            )
        if self.connection_disposition is not None and not isinstance(
            self.connection_disposition,
            DecisionReceiptConnectionDisposition,
        ):
            raise TypeError(
                "connection_disposition must be "
                "DecisionReceiptConnectionDisposition or None"
            )
        if self.sqlstate is not None and not isinstance(self.sqlstate, str):
            raise TypeError("sqlstate must be str or None")
        if type(self.cleanup_failures) is not tuple or any(
            not isinstance(item, DecisionReceiptCleanupFailureCategory)
            for item in self.cleanup_failures
        ):
            raise TypeError(
                "cleanup_failures must be a tuple of "
                "DecisionReceiptCleanupFailureCategory values"
            )
        _validate_result_coherence(self)


def _validate_result_coherence(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Reject contradictory transaction, cleanup, and evidence combinations."""
    _validate_cleanup_coherence(result)

    acquisition_failure = (
        result.failure_category
        is DecisionReceiptTransactionFailureCategory
        .CONNECTION_ACQUISITION_FAILED
    )
    if result.connection_disposition is None and not acquisition_failure:
        raise ValueError(
            "connection_disposition may be None only for connection acquisition "
            "failure"
        )

    if acquisition_failure:
        _validate_acquisition_failure_result(result)
        return
    if result.durability is DecisionReceiptTransactionDurability.COMMITTED:
        _validate_committed_result(result)
        return
    if result.durability is DecisionReceiptTransactionDurability.UNKNOWN:
        _validate_unknown_result(result)
        return

    failure_category = result.failure_category
    if failure_category is DecisionReceiptTransactionFailureCategory.CONFLICT:
        _validate_conflict_result(result)
        return
    if failure_category is (
        DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
    ):
        _validate_idle_owner_timeout_result(result)
        return
    if failure_category in {
        DecisionReceiptTransactionFailureCategory.TIMEOUT_CONFIGURATION_FAILED,
        DecisionReceiptTransactionFailureCategory.STORE_OPERATION_FAILED,
    }:
        _validate_precommit_failure_result(result)
        return
    if failure_category is (
        DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
    ):
        _validate_autocommit_entry_failure_result(result)
        return
    if failure_category in {
        DecisionReceiptTransactionFailureCategory.TRANSACTION_NOT_IDLE,
        DecisionReceiptTransactionFailureCategory.CONNECTION_STATE_UNAVAILABLE,
    }:
        _validate_discarded_entry_failure_result(result)
        return

    raise ValueError(
        "NOT_COMMITTED durability requires a supported pre-commit failure "
        "category"
    )


def _validate_cleanup_coherence(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Require cleanup categories and dispositions to agree bidirectionally."""
    rollback_failed = (
        result.rollback_disposition
        is DecisionReceiptRollbackDisposition.FAILED
    )
    has_rollback_failure = (
        DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED
        in result.cleanup_failures
    )
    if rollback_failed is not has_rollback_failure:
        raise ValueError(
            "rollback disposition FAILED and ROLLBACK_FAILED cleanup evidence "
            "must appear together"
        )

    connection_cleanup_failed = (
        result.connection_disposition
        is DecisionReceiptConnectionDisposition.CLEANUP_FAILED
    )
    has_close_failure = (
        DecisionReceiptCleanupFailureCategory.CONNECTION_CLOSE_FAILED
        in result.cleanup_failures
    )
    if connection_cleanup_failed is not has_close_failure:
        raise ValueError(
            "connection disposition CLEANUP_FAILED and CONNECTION_CLOSE_FAILED "
            "cleanup evidence must appear together"
        )


def _validate_acquisition_failure_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate the only result shape that has no acquired connection."""
    if result.durability is not DecisionReceiptTransactionDurability.NOT_COMMITTED:
        raise ValueError("connection acquisition failure must be NOT_COMMITTED")
    if result.statement_result is not None or result.conflict_error is not None:
        raise ValueError(
            "connection acquisition failure cannot contain statement or "
            "conflict evidence"
        )
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    ):
        raise ValueError(
            "connection acquisition failure requires rollback NOT_REQUIRED"
        )
    if result.connection_disposition is not None:
        raise ValueError(
            "connection acquisition failure cannot have connection disposition"
        )


def _validate_committed_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate acknowledged commit evidence and its cleanup disposition."""
    if result.statement_result is None:
        raise ValueError("COMMITTED durability requires statement_result")
    if result.failure_category is not None or result.conflict_error is not None:
        raise ValueError(
            "COMMITTED durability cannot contain failure or conflict evidence"
        )
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    ):
        raise ValueError(
            "COMMITTED durability requires rollback disposition NOT_REQUIRED"
        )
    if result.connection_disposition not in {
        DecisionReceiptConnectionDisposition.CLOSED,
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
    }:
        raise ValueError(
            "COMMITTED durability requires connection CLOSED or CLEANUP_FAILED"
        )


def _validate_unknown_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate conservative unacknowledged commit-phase evidence."""
    if result.statement_result is None:
        raise ValueError("UNKNOWN durability requires statement_result")
    if result.failure_category is not (
        DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
    ):
        raise ValueError("UNKNOWN durability requires failure category COMMIT_FAILED")
    if result.conflict_error is not None:
        raise ValueError("UNKNOWN durability cannot contain conflict evidence")
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    ):
        raise ValueError(
            "UNKNOWN durability requires rollback disposition NOT_POSSIBLE"
        )
    if result.connection_disposition not in {
        DecisionReceiptConnectionDisposition.DISCARDED,
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
    }:
        raise ValueError(
            "UNKNOWN durability requires connection DISCARDED or CLEANUP_FAILED"
        )


def _validate_conflict_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate typed conflict evidence without adding semantic authority."""
    if result.durability is not DecisionReceiptTransactionDurability.NOT_COMMITTED:
        raise ValueError("CONFLICT requires NOT_COMMITTED durability")
    if result.conflict_error is None:
        raise ValueError("CONFLICT requires conflict_error")
    if result.statement_result is not None:
        raise ValueError("CONFLICT cannot contain statement_result")
    _validate_rolled_back_acquired_result(result, failure_name="CONFLICT")


def _validate_idle_owner_timeout_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate characterized server-side idle-owner rollback evidence."""
    if result.durability is not DecisionReceiptTransactionDurability.NOT_COMMITTED:
        raise ValueError("IDLE_OWNER_TIMEOUT requires NOT_COMMITTED durability")
    if result.conflict_error is not None:
        raise ValueError("IDLE_OWNER_TIMEOUT cannot contain conflict evidence")
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    ):
        raise ValueError("IDLE_OWNER_TIMEOUT requires rollback NOT_POSSIBLE")
    if result.connection_disposition not in {
        DecisionReceiptConnectionDisposition.DISCARDED,
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
    }:
        raise ValueError(
            "IDLE_OWNER_TIMEOUT requires connection DISCARDED or CLEANUP_FAILED"
        )


def _validate_precommit_failure_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate timeout-configuration and statement-store failure evidence."""
    if result.durability is not DecisionReceiptTransactionDurability.NOT_COMMITTED:
        raise ValueError("pre-commit failure requires NOT_COMMITTED durability")
    if result.statement_result is not None or result.conflict_error is not None:
        raise ValueError(
            "pre-commit failure cannot contain statement or conflict evidence"
        )
    _validate_rolled_back_acquired_result(
        result,
        failure_name="pre-commit failure",
    )


def _validate_rolled_back_acquired_result(
    result: PostgresDecisionReceiptTransactionResult,
    *,
    failure_name: str,
) -> None:
    """Require a rollback attempt and final disposition after acquisition."""
    if result.rollback_disposition not in {
        DecisionReceiptRollbackDisposition.CONFIRMED,
        DecisionReceiptRollbackDisposition.FAILED,
    }:
        raise ValueError(
            f"{failure_name} requires rollback CONFIRMED or FAILED"
        )
    if result.connection_disposition is None:
        raise ValueError(f"{failure_name} requires connection disposition")
    if (
        result.rollback_disposition
        is DecisionReceiptRollbackDisposition.CONFIRMED
        and result.connection_disposition
        not in {
            DecisionReceiptConnectionDisposition.CLOSED,
            DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
        }
    ):
        raise ValueError(
            f"{failure_name} with confirmed rollback requires connection "
            "CLOSED or CLEANUP_FAILED"
        )
    if (
        result.rollback_disposition is DecisionReceiptRollbackDisposition.FAILED
        and result.connection_disposition
        not in {
            DecisionReceiptConnectionDisposition.DISCARDED,
            DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
        }
    ):
        raise ValueError(
            f"{failure_name} with failed rollback requires connection "
            "DISCARDED or CLEANUP_FAILED"
        )


def _validate_autocommit_entry_failure_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate clean close of an acquired autocommit connection."""
    _validate_entry_failure_common(result, failure_name="AUTOCOMMIT_ENABLED")
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_REQUIRED
    ):
        raise ValueError("AUTOCOMMIT_ENABLED requires rollback NOT_REQUIRED")
    if result.connection_disposition not in {
        DecisionReceiptConnectionDisposition.CLOSED,
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
    }:
        raise ValueError(
            "AUTOCOMMIT_ENABLED requires connection CLOSED or CLEANUP_FAILED"
        )


def _validate_discarded_entry_failure_result(
    result: PostgresDecisionReceiptTransactionResult,
) -> None:
    """Validate discard of a non-idle or uninspectable acquired connection."""
    _validate_entry_failure_common(result, failure_name="entry-state failure")
    if result.rollback_disposition is not (
        DecisionReceiptRollbackDisposition.NOT_POSSIBLE
    ):
        raise ValueError("entry-state failure requires rollback NOT_POSSIBLE")
    if result.connection_disposition not in {
        DecisionReceiptConnectionDisposition.DISCARDED,
        DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
    }:
        raise ValueError(
            "entry-state failure requires connection DISCARDED or CLEANUP_FAILED"
        )


def _validate_entry_failure_common(
    result: PostgresDecisionReceiptTransactionResult,
    *,
    failure_name: str,
) -> None:
    """Validate evidence shared by dedicated-connection entry failures."""
    if result.durability is not DecisionReceiptTransactionDurability.NOT_COMMITTED:
        raise ValueError(f"{failure_name} requires NOT_COMMITTED durability")
    if result.statement_result is not None or result.conflict_error is not None:
        raise ValueError(
            f"{failure_name} cannot contain statement or conflict evidence"
        )


class PostgresDecisionReceiptTransactionOwner:
    """Own one dedicated PostgreSQL DecisionReceipt governance transaction.

    Responsibility:
        Validate mandatory idle-owner configuration, acquire one dedicated
        connection, require a clean entry state, apply transaction-local
        live-but-idle protection, construct the statement-only store, complete
        commit or rollback, close or discard the connection, and return
        commit-aware technical evidence.

    Args:
        connection_factory: Purpose-specific callable that transfers ownership
            of one dedicated connection per persistence operation.
        idle_in_transaction_session_timeout_ms: Mandatory positive integer
            milliseconds applied transaction-locally before receipt insertion.

    Transaction semantics:
        The first transaction-local statement may open the psycopg transaction.
        ``INSERTED`` and ``ALREADY_PRESENT`` remain statement evidence until
        commit returns. Characterized idle-owner termination is known
        ``NOT_COMMITTED``; every other unacknowledged commit failure is
        ``UNKNOWN``.

    Non-guarantees:
        The owner does not construct or map receipts, allocate identities, call
        the accepted-event transaction, authorize retry, create traces or
        attempt logs, reconcile history, implement pooling, choose a production
        timeout, or change schema, migration, policy, or business outcomes.
    """

    def __init__(
        self,
        connection_factory: PostgresDecisionReceiptConnectionFactory,
        *,
        idle_in_transaction_session_timeout_ms: int,
    ) -> None:
        """Create an owner with a dedicated factory and validated timeout input.

        Validation occurs without acquiring a connection. Boolean and
        non-integer timeout values raise ``TypeError``; zero and negative values
        raise ``ValueError``. No default or application-side maximum is applied.
        The factory is retained for one call per later persistence operation.
        """
        if not callable(connection_factory):
            raise TypeError("connection_factory must be callable")
        if type(idle_in_transaction_session_timeout_ms) is not int:
            raise TypeError(
                "idle_in_transaction_session_timeout_ms must be int"
            )
        if idle_in_transaction_session_timeout_ms <= 0:
            raise ValueError(
                "idle_in_transaction_session_timeout_ms must be greater than zero"
            )

        self._connection_factory = connection_factory
        self._idle_in_transaction_session_timeout_ms = (
            idle_in_transaction_session_timeout_ms
        )

    def persist(
        self,
        receipt: DecisionReceipt,
        *,
        materialization_provenance: DecisionReceiptMaterializationProvenance,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Persist an already-complete receipt in one governance transaction.

        Args:
            receipt: Complete semantic receipt constructed by an authorized
                producer outside this owner.
            materialization_provenance: Required persistence-envelope evidence
                passed unchanged to the statement-only store.

        Returns:
            Commit-aware technical evidence containing optional inner statement
            evidence, conflict evidence, rollback and connection dispositions,
            safe SQLSTATE, and cleanup failures.

        Guarantees:
            The owner acquires its own dedicated connection, applies the timeout
            before receipt insertion, never reports ``COMMITTED`` before commit
            acknowledgement, and never reuses a terminated or ambiguous
            connection.

        Non-guarantees:
            This method does not accept a caller-owned connection, map semantic
            evidence, authorize retry, change a business outcome, implement
            reconciliation, or create trace, attempt-log, or policy artifacts.
        """
        if not isinstance(receipt, DecisionReceipt):
            raise TypeError("receipt must be DecisionReceipt")
        if not isinstance(
            materialization_provenance,
            DecisionReceiptMaterializationProvenance,
        ):
            raise TypeError(
                "materialization_provenance must be "
                "DecisionReceiptMaterializationProvenance"
            )

        try:
            connection = self._connection_factory()
        except Exception as error:
            return PostgresDecisionReceiptTransactionResult(
                durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
                rollback_disposition=(
                    DecisionReceiptRollbackDisposition.NOT_REQUIRED
                ),
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_ACQUISITION_FAILED
                ),
                sqlstate=_safe_sqlstate(error),
            )

        entry_failure = self._validate_connection_entry(connection)
        if entry_failure is not None:
            return entry_failure

        statement_result: DecisionReceiptInsertResult | None = None
        try:
            self._apply_transaction_local_timeout(connection)
        except Exception as error:
            if _is_characterized_idle_owner_timeout(error):
                return self._idle_owner_timeout_result(
                    connection,
                    error,
                    statement_result=None,
                )
            return self._precommit_failure_result(
                connection,
                error,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .TIMEOUT_CONFIGURATION_FAILED
                ),
            )

        try:
            store = self._build_store(connection)
            statement_result = store.insert(
                receipt,
                materialization_provenance=materialization_provenance,
            )
        except DecisionReceiptConflictError as error:
            return self._precommit_failure_result(
                connection,
                error,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory.CONFLICT
                ),
                conflict_error=error,
            )
        except Exception as error:
            if _is_characterized_idle_owner_timeout(error):
                return self._idle_owner_timeout_result(
                    connection,
                    error,
                    statement_result=None,
                )
            return self._precommit_failure_result(
                connection,
                error,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .STORE_OPERATION_FAILED
                ),
            )

        try:
            connection.commit()
        except Exception as error:
            if _is_characterized_idle_owner_timeout(error):
                return self._idle_owner_timeout_result(
                    connection,
                    error,
                    statement_result=statement_result,
                )
            return self._commit_ambiguous_result(
                connection,
                error,
                statement_result=statement_result,
            )

        return self._committed_result(connection, statement_result)

    def _build_store(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptStore:
        """Construct the statement-only store through a narrow test seam."""
        return PostgresDecisionReceiptStore(connection)

    def _apply_transaction_local_timeout(
        self,
        connection: Connection[object],
    ) -> None:
        """Apply the mandatory millisecond value to the current transaction."""
        connection.execute(
            _SET_LOCAL_IDLE_OWNER_TIMEOUT_SQL,
            (f"{self._idle_in_transaction_session_timeout_ms}ms",),
        )

    def _validate_connection_entry(
        self,
        connection: Connection[object],
    ) -> PostgresDecisionReceiptTransactionResult | None:
        """Fail closed when the dedicated connection violates entry invariants."""
        try:
            autocommit = connection.autocommit
        except Exception as error:
            return self._connection_invariant_failure_result(
                connection,
                error,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_STATE_UNAVAILABLE
                ),
                discard=True,
            )

        if autocommit:
            return self._connection_invariant_failure_result(
                connection,
                None,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory.AUTOCOMMIT_ENABLED
                ),
                discard=False,
            )

        try:
            transaction_status = connection.info.transaction_status
        except Exception as error:
            return self._connection_invariant_failure_result(
                connection,
                error,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .CONNECTION_STATE_UNAVAILABLE
                ),
                discard=True,
            )

        if transaction_status is not TransactionStatus.IDLE:
            return self._connection_invariant_failure_result(
                connection,
                None,
                failure_category=(
                    DecisionReceiptTransactionFailureCategory
                    .TRANSACTION_NOT_IDLE
                ),
                discard=True,
            )

        return None

    def _connection_invariant_failure_result(
        self,
        connection: Connection[object],
        error: Exception | None,
        *,
        failure_category: DecisionReceiptTransactionFailureCategory,
        discard: bool,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Close or discard an invalid acquired connection without using it."""
        success_disposition = (
            DecisionReceiptConnectionDisposition.DISCARDED
            if discard
            else DecisionReceiptConnectionDisposition.CLOSED
        )
        disposition, cleanup_failures, cleanup_sqlstate = _close_connection(
            connection,
            success_disposition=success_disposition,
        )
        primary_sqlstate = _safe_sqlstate(error) if error is not None else None
        return PostgresDecisionReceiptTransactionResult(
            durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
            rollback_disposition=(
                DecisionReceiptRollbackDisposition.NOT_POSSIBLE
                if discard
                else DecisionReceiptRollbackDisposition.NOT_REQUIRED
            ),
            failure_category=failure_category,
            connection_disposition=disposition,
            sqlstate=primary_sqlstate or cleanup_sqlstate,
            cleanup_failures=cleanup_failures,
        )

    def _precommit_failure_result(
        self,
        connection: Connection[object],
        error: Exception,
        *,
        failure_category: DecisionReceiptTransactionFailureCategory,
        conflict_error: DecisionReceiptConflictError | None = None,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Roll back known pre-commit failure and preserve cleanup evidence."""
        primary_sqlstate = _safe_sqlstate(error)
        try:
            connection.rollback()
        except Exception as rollback_error:
            disposition, close_failures, close_sqlstate = _close_connection(
                connection,
                success_disposition=(
                    DecisionReceiptConnectionDisposition.DISCARDED
                ),
            )
            return PostgresDecisionReceiptTransactionResult(
                durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
                rollback_disposition=(
                    DecisionReceiptRollbackDisposition.FAILED
                ),
                failure_category=failure_category,
                conflict_error=conflict_error,
                connection_disposition=disposition,
                sqlstate=(
                    primary_sqlstate
                    or _safe_sqlstate(rollback_error)
                    or close_sqlstate
                ),
                cleanup_failures=(
                    DecisionReceiptCleanupFailureCategory.ROLLBACK_FAILED,
                    *close_failures,
                ),
            )

        disposition, cleanup_failures, cleanup_sqlstate = _close_connection(
            connection,
            success_disposition=DecisionReceiptConnectionDisposition.CLOSED,
        )
        return PostgresDecisionReceiptTransactionResult(
            durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
            rollback_disposition=DecisionReceiptRollbackDisposition.CONFIRMED,
            failure_category=failure_category,
            conflict_error=conflict_error,
            connection_disposition=disposition,
            sqlstate=primary_sqlstate or cleanup_sqlstate,
            cleanup_failures=cleanup_failures,
        )

    def _idle_owner_timeout_result(
        self,
        connection: Connection[object],
        error: Exception,
        *,
        statement_result: DecisionReceiptInsertResult | None,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Preserve characterized server rollback without client rollback."""
        disposition, cleanup_failures, cleanup_sqlstate = _close_connection(
            connection,
            success_disposition=DecisionReceiptConnectionDisposition.DISCARDED,
        )
        return PostgresDecisionReceiptTransactionResult(
            durability=DecisionReceiptTransactionDurability.NOT_COMMITTED,
            rollback_disposition=(
                DecisionReceiptRollbackDisposition.NOT_POSSIBLE
            ),
            statement_result=statement_result,
            failure_category=(
                DecisionReceiptTransactionFailureCategory.IDLE_OWNER_TIMEOUT
            ),
            connection_disposition=disposition,
            sqlstate=_safe_sqlstate(error) or cleanup_sqlstate,
            cleanup_failures=cleanup_failures,
        )

    def _commit_ambiguous_result(
        self,
        connection: Connection[object],
        error: Exception,
        *,
        statement_result: DecisionReceiptInsertResult,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Preserve unknown durability after unacknowledged commit invocation."""
        disposition, cleanup_failures, cleanup_sqlstate = _close_connection(
            connection,
            success_disposition=DecisionReceiptConnectionDisposition.DISCARDED,
        )
        return PostgresDecisionReceiptTransactionResult(
            durability=DecisionReceiptTransactionDurability.UNKNOWN,
            rollback_disposition=(
                DecisionReceiptRollbackDisposition.NOT_POSSIBLE
            ),
            statement_result=statement_result,
            failure_category=(
                DecisionReceiptTransactionFailureCategory.COMMIT_FAILED
            ),
            connection_disposition=disposition,
            sqlstate=_safe_sqlstate(error) or cleanup_sqlstate,
            cleanup_failures=cleanup_failures,
        )

    def _committed_result(
        self,
        connection: Connection[object],
        statement_result: DecisionReceiptInsertResult,
    ) -> PostgresDecisionReceiptTransactionResult:
        """Close after acknowledged commit without allowing cleanup downgrade."""
        disposition, cleanup_failures, cleanup_sqlstate = _close_connection(
            connection,
            success_disposition=DecisionReceiptConnectionDisposition.CLOSED,
        )
        return PostgresDecisionReceiptTransactionResult(
            durability=DecisionReceiptTransactionDurability.COMMITTED,
            rollback_disposition=(
                DecisionReceiptRollbackDisposition.NOT_REQUIRED
            ),
            statement_result=statement_result,
            connection_disposition=disposition,
            sqlstate=cleanup_sqlstate,
            cleanup_failures=cleanup_failures,
        )


def _safe_sqlstate(error: BaseException) -> str | None:
    """Return safe SQLSTATE metadata without exposing raw driver diagnostics."""
    sqlstate = getattr(error, "sqlstate", None)
    return sqlstate if isinstance(sqlstate, str) else None


def _is_characterized_idle_owner_timeout(error: BaseException) -> bool:
    """Recognize the exact Level 1 timeout class or its stable SQLSTATE."""
    return isinstance(error, IdleInTransactionSessionTimeout) or (
        _safe_sqlstate(error) == _IDLE_OWNER_TIMEOUT_SQLSTATE
    )


def _close_connection(
    connection: Connection[object],
    *,
    success_disposition: DecisionReceiptConnectionDisposition,
) -> tuple[
    DecisionReceiptConnectionDisposition,
    tuple[DecisionReceiptCleanupFailureCategory, ...],
    str | None,
]:
    """Close or discard one dedicated connection and preserve close failure."""
    try:
        connection.close()
    except Exception as error:
        return (
            DecisionReceiptConnectionDisposition.CLEANUP_FAILED,
            (
                DecisionReceiptCleanupFailureCategory
                .CONNECTION_CLOSE_FAILED,
            ),
            _safe_sqlstate(error),
        )
    return success_disposition, (), None
