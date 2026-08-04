import pytest

from src.pipeline.transactional.postgres_unit_of_work import (
    PostgresWriteSideUnitOfWork,
)


class FakeConnection:
    def __init__(self, *, autocommit: bool):
        self.autocommit = autocommit
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


class SentinelError(Exception):
    pass


def test_enter_rejects_autocommit_before_body_executes():
    connection = FakeConnection(autocommit=True)
    uow = PostgresWriteSideUnitOfWork(connection)
    body_executed = False

    with pytest.raises(
        RuntimeError,
        match="requires connection.autocommit=False",
    ):
        with uow:
            body_executed = True

    assert body_executed is False
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 0


def test_enter_rechecks_autocommit_after_construction():
    connection = FakeConnection(autocommit=False)
    uow = PostgresWriteSideUnitOfWork(connection)
    connection.autocommit = True

    with pytest.raises(
        RuntimeError,
        match="requires connection.autocommit=False",
    ):
        with uow:
            pass

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 0


def test_clean_exit_commits_once_without_rollback():
    connection = FakeConnection(autocommit=False)
    body_executed = False

    with PostgresWriteSideUnitOfWork(connection):
        body_executed = True

    assert body_executed is True
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0


def test_exceptional_exit_rolls_back_once_and_preserves_original_exception():
    connection = FakeConnection(autocommit=False)

    with pytest.raises(SentinelError, match="sentinel failure"):
        with PostgresWriteSideUnitOfWork(connection):
            raise SentinelError("sentinel failure")

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
