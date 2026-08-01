from typing import cast

import pytest
from psycopg import Connection

from src.pipeline.projection.order_projection_definition import (
    ORDER_STATE_PROJECTION_EPOCH,
    ORDER_STATE_PROJECTION_NAME,
    require_current_order_state_projection,
)
from src.pipeline.projection.postgres_worker import PostgresProjectionWorker
from src.storage.postgres_projection_eligible_event_source import (
    PostgresProjectionEligibleEventSource,
)
from src.storage.postgres_projection_progress_store import (
    PostgresProjectionProgressStore,
)
from src.storage.projection_progress_store import ProjectionOrderProgress


def _connection_without_database_access() -> Connection:
    return cast(Connection, object())


def test_postgres_worker_uses_only_current_projection_definition() -> None:
    worker = PostgresProjectionWorker(
        _connection_without_database_access(),
        worker_name="definition-test-worker",
    )

    assert worker.projection_name == ORDER_STATE_PROJECTION_NAME
    assert worker.projection_epoch == ORDER_STATE_PROJECTION_EPOCH


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("projection_name", "unsupported_projection"),
        ("projection_epoch", 2),
    ],
)
def test_postgres_worker_rejects_projection_definition_configuration(
    argument: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        PostgresProjectionWorker(
            _connection_without_database_access(),
            worker_name="definition-test-worker",
            **{argument: value},
        )


@pytest.mark.parametrize(
    ("projection_name", "projection_epoch", "expected_message"),
    [
        ("unsupported_projection", 1, "unsupported projection_name"),
        (ORDER_STATE_PROJECTION_NAME, 2, "unsupported projection_epoch"),
    ],
)
def test_definition_guard_rejects_unsupported_name_or_epoch(
    projection_name: str,
    projection_epoch: int,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        require_current_order_state_projection(
            projection_name=projection_name,
            projection_epoch=projection_epoch,
        )


@pytest.mark.parametrize(
    ("projection_name", "projection_epoch", "expected_message"),
    [
        ("unsupported_projection", 1, "unsupported projection_name"),
        (ORDER_STATE_PROJECTION_NAME, 2, "unsupported projection_epoch"),
    ],
)
def test_postgres_stores_reject_unsupported_name_or_epoch_before_sql(
    projection_name: str,
    projection_epoch: int,
    expected_message: str,
) -> None:
    connection = _connection_without_database_access()
    source = PostgresProjectionEligibleEventSource(connection)
    progress_store = PostgresProjectionProgressStore(connection)

    with pytest.raises(ValueError, match=expected_message):
        source.load_eligible(
            projection_name=projection_name,
            projection_epoch=projection_epoch,
            limit=1,
        )

    with pytest.raises(ValueError, match=expected_message):
        progress_store.load_progress(
            projection_name=projection_name,
            projection_epoch=projection_epoch,
            order_id="order-definition-test",
        )

    with pytest.raises(ValueError, match=expected_message):
        progress_store.advance_progress(
            ProjectionOrderProgress(
                projection_name=projection_name,
                projection_epoch=projection_epoch,
                order_id="order-definition-test",
                last_sequence=1,
                last_event_id="00000000-0000-0000-0000-000000000001",
                last_global_position=1,
            )
        )
