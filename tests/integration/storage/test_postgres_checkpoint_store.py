import pytest
from psycopg import Connection
from psycopg import errors

from src.storage.postgres_checkpoint_store import CheckpointCursorKind
from src.storage.postgres_checkpoint_store import PostgresCheckpointStore
from src.storage.postgres_checkpoint_store import ProjectionCheckpoint


def make_checkpoint(
    *,
    worker_name: str,
    cursor_kind: CheckpointCursorKind,
    cursor_value: str,
) -> ProjectionCheckpoint:
    return ProjectionCheckpoint(
        worker_name=worker_name,
        cursor_kind=cursor_kind,
        cursor_value=cursor_value,
    )


def test_load_missing_checkpoint_returns_none(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    checkpoint = store.load_checkpoint("missing-worker")

    assert checkpoint is None


def test_save_and_load_unspecified_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    expected = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.UNSPECIFIED,
        cursor_value="",
    )

    store.save_checkpoint(expected)
    db_connection.commit()

    actual = store.load_checkpoint("projection-worker")

    assert actual == expected


def test_save_and_load_global_position_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    expected = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="123",
    )

    store.save_checkpoint(expected)
    db_connection.commit()

    actual = store.load_checkpoint("projection-worker")

    assert actual == expected


def test_save_and_load_event_id_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    expected = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.EVENT_ID,
        cursor_value="550e8400-e29b-41d4-a716-446655440000",
    )

    store.save_checkpoint(expected)
    db_connection.commit()

    actual = store.load_checkpoint("projection-worker")

    assert actual == expected


def test_save_and_load_appended_at_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    expected = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.APPENDED_AT,
        cursor_value="2026-06-07T12:00:00+00:00",
    )

    store.save_checkpoint(expected)
    db_connection.commit()

    actual = store.load_checkpoint("projection-worker")

    assert actual == expected


def test_save_checkpoint_upserts_existing_worker_checkpoint(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    first = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.UNSPECIFIED,
        cursor_value="",
    )
    second = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="456",
    )

    store.save_checkpoint(first)
    store.save_checkpoint(second)
    db_connection.commit()

    actual = store.load_checkpoint("projection-worker")

    assert actual == second

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM projection_checkpoints
            WHERE worker_name = %s
            """,
            ("projection-worker",),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 1


def test_multiple_workers_do_not_overwrite_each_other(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    worker_a = make_checkpoint(
        worker_name="worker-a",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="100",
    )
    worker_b = make_checkpoint(
        worker_name="worker-b",
        cursor_kind=CheckpointCursorKind.EVENT_ID,
        cursor_value="550e8400-e29b-41d4-a716-446655440000",
    )

    store.save_checkpoint(worker_a)
    store.save_checkpoint(worker_b)
    db_connection.commit()

    assert store.load_checkpoint("worker-a") == worker_a
    assert store.load_checkpoint("worker-b") == worker_b


def test_clear_removes_checkpoints(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    checkpoint = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="100",
    )

    store.save_checkpoint(checkpoint)
    db_connection.commit()

    assert store.load_checkpoint("projection-worker") is not None

    store.clear()
    db_connection.commit()

    assert store.load_checkpoint("projection-worker") is None


@pytest.mark.parametrize(
    ("cursor_kind", "cursor_value"),
    [
        (CheckpointCursorKind.UNSPECIFIED, "1"),
        (CheckpointCursorKind.GLOBAL_POSITION, "not-a-number"),
        (CheckpointCursorKind.EVENT_ID, "not-a-uuid"),
        (CheckpointCursorKind.APPENDED_AT, ""),
        (CheckpointCursorKind.APPENDED_AT, "   "),
    ],
)
def test_save_checkpoint_rejects_invalid_cursor_value_for_kind(
    db_connection: Connection,
    clean_database: None,
    cursor_kind: CheckpointCursorKind,
    cursor_value: str,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    checkpoint = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=cursor_kind,
        cursor_value=cursor_value,
    )

    with pytest.raises(errors.CheckViolation):
        store.save_checkpoint(checkpoint)

    db_connection.rollback()


def test_save_checkpoint_rejects_empty_worker_name(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    checkpoint = make_checkpoint(
        worker_name="   ",
        cursor_kind=CheckpointCursorKind.UNSPECIFIED,
        cursor_value="",
    )

    with pytest.raises(errors.CheckViolation):
        store.save_checkpoint(checkpoint)

    db_connection.rollback()


def test_save_checkpoint_does_not_commit_transaction(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresCheckpointStore(db_connection)

    checkpoint = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="100",
    )

    store.save_checkpoint(checkpoint)
    db_connection.rollback()

    assert store.load_checkpoint("projection-worker") is None


def test_connection_can_be_reused_after_constraint_error_and_rollback(
    db_connection: Connection,
    clean_database: None,
) -> None:
    """
    PostgreSQL marks the current transaction as failed after a constraint error.

    The store intentionally does not rollback by itself because transaction
    ownership belongs to the caller.

    After the caller rolls back, the same connection should be usable again.
    """
    store = PostgresCheckpointStore(db_connection)

    invalid_checkpoint = make_checkpoint(
        worker_name="projection-worker",
        cursor_kind=CheckpointCursorKind.GLOBAL_POSITION,
        cursor_value="not-a-number",
    )

    with pytest.raises(errors.CheckViolation):
        store.save_checkpoint(invalid_checkpoint)

    db_connection.rollback()

    assert store.load_checkpoint("projection-worker") is None