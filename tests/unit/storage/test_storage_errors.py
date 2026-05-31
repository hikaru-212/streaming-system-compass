from src.storage.errors import (
    AppendConflictError,
    StaleWriteError,
    StorageConflictError,
    StorageError,
    StorageInfrastructureError,
)


def test_stale_write_error_is_storage_conflict_error():
    error = StaleWriteError("stale write")

    assert isinstance(error, StorageConflictError)
    assert isinstance(error, StorageError)


def test_append_conflict_error_is_storage_conflict_error():
    error = AppendConflictError("append conflict")

    assert isinstance(error, StorageConflictError)
    assert isinstance(error, StorageError)


def test_storage_infrastructure_error_is_storage_error():
    error = StorageInfrastructureError("database unavailable")

    assert isinstance(error, StorageError)