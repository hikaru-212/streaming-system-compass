from src.storage.errors import (
    AppendConflictError,
    AppendVersionMismatchError,
    StaleWriteError,
    StorageConflictError,
    StorageError,
    StorageInfrastructureError,
)


def test_append_version_mismatch_error_preserves_typed_versions_and_compatibility():
    error = AppendVersionMismatchError(
        expected_current_version=1,
        observed_current_version=2,
    )

    assert type(error) is AppendVersionMismatchError
    assert error.expected_current_version == 1
    assert error.observed_current_version == 2
    assert str(error) == (
        "Version conflict: store_version=2, expected_version=1"
    )
    assert isinstance(error, StaleWriteError)
    assert isinstance(error, StorageConflictError)
    assert isinstance(error, StorageError)
    assert isinstance(error, ValueError)


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
