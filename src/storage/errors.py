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


class AppendConflictError(StorageConflictError):
    """Raised when append-time sequence occupation conflicts with existing history.

    Typically caused by a UNIQUE constraint violation on the accepted-history
    stream position, such as (order_id, sequence).
    """


class StorageInfrastructureError(StorageError):
    """Raised when persistence fails for non-domain infrastructure reasons."""