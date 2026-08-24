"""Storage-level exceptions.

These exceptions describe persistence-boundary failures.

They are intentionally not Stage 4 SemanticOutcome objects.
They exist so infrastructure errors can be translated into stable storage or
admission-level meanings before they reach higher write-side orchestration.
"""


class StorageError(Exception):
    """Base class for storage-layer failures."""


class StorageConflictError(StorageError):
    """Base class for storage conflicts caused by concurrent or stale writes."""


class StaleWriteError(StorageConflictError):
    """Raised when a writer attempts to append from a stale expected version."""


class AppendVersionMismatchError(StaleWriteError, ValueError):
    """Transport one append-time expected/current version inequality.

    Args:
        expected_current_version: Version supplied by the append caller.
        observed_current_version: Authoritative version observed by storage.

    This source-specific storage failure preserves the existing ``ValueError``
    compatibility of ``PostgresEventStore.append`` while remaining within the
    storage-conflict hierarchy. The inheritance is a compatibility mechanism;
    it does not make generic ``StaleWriteError`` values equivalent to this
    characterized physical source.

    The exception is internal storage-to-admission transport. It does not
    express semantic interpretation, retry policy, re-invocation authority, or
    execution behavior.
    """

    expected_current_version: int
    observed_current_version: int

    def __init__(
        self,
        *,
        expected_current_version: int,
        observed_current_version: int,
    ) -> None:
        self.expected_current_version = expected_current_version
        self.observed_current_version = observed_current_version
        super().__init__(
            "Version conflict: "
            f"store_version={observed_current_version}, "
            f"expected_version={expected_current_version}"
        )


class AppendConflictError(StorageConflictError):
    """Raised when append-time sequence occupation conflicts with existing history.

    Typically caused by a UNIQUE constraint violation on the accepted-history
    stream position, such as (order_id, sequence).
    """


class StorageInfrastructureError(StorageError):
    """Raised when persistence fails for non-domain infrastructure reasons."""
