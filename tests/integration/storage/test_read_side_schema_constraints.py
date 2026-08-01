from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import Connection
from psycopg import errors


def test_projection_states_accepts_valid_row(
    db_connection: Connection,
    clean_database: None,
) -> None:
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_states (
                order_id,
                status,
                total_amount,
                paid_amount,
                version,
                last_sequence
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                "order-001",
                "CREATED",
                Decimal("100.00"),
                Decimal("0.00"),
                1,
                1,
            ),
        )

    db_connection.commit()


def test_projection_states_rejects_empty_order_id(
    db_connection: Connection,
    clean_database: None,
) -> None:
    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_states (
                    order_id,
                    status,
                    total_amount,
                    paid_amount,
                    version,
                    last_sequence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    "   ",
                    "CREATED",
                    Decimal("100.00"),
                    Decimal("0.00"),
                    1,
                    1,
                ),
            )

    db_connection.rollback()


@pytest.mark.parametrize(
    ("status", "total_amount", "paid_amount", "version", "last_sequence"),
    [
        ("UNKNOWN", Decimal("100.00"), Decimal("0.00"), 1, 1),
        ("CREATED", Decimal("-1.00"), Decimal("0.00"), 1, 1),
        ("CREATED", Decimal("100.00"), Decimal("-1.00"), 1, 1),
        ("CREATED", Decimal("100.00"), Decimal("101.00"), 1, 1),
        ("CREATED", Decimal("100.00"), Decimal("0.00"), -1, 1),
        ("CREATED", Decimal("100.00"), Decimal("0.00"), 1, -1),
    ],
)
def test_projection_states_rejects_invalid_physical_shape(
    db_connection: Connection,
    clean_database: None,
    status: str,
    total_amount: Decimal,
    paid_amount: Decimal,
    version: int,
    last_sequence: int,
) -> None:
    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_states (
                    order_id,
                    status,
                    total_amount,
                    paid_amount,
                    version,
                    last_sequence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    "order-invalid-shape",
                    status,
                    total_amount,
                    paid_amount,
                    version,
                    last_sequence,
                ),
            )

    db_connection.rollback()


def test_projection_states_allows_physically_valid_but_semantically_suspicious_row(
    db_connection: Connection,
    clean_database: None,
) -> None:
    """
    PR1 only protects physical shape.

    A CREATED state with paid_amount > 0 may be semantically suspicious
    under the current simplified domain, but this should be a future
    Compass Layer 2 drift-detection case, not a PR1 database CHECK constraint.
    """
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_states (
                order_id,
                status,
                total_amount,
                paid_amount,
                version,
                last_sequence
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                "order-created-with-paid-amount",
                "CREATED",
                Decimal("100.00"),
                Decimal("100.00"),
                1,
                1,
            ),
        )

    db_connection.commit()


@pytest.mark.parametrize(
    ("worker_name", "cursor_kind", "cursor_value"),
    [
        ("projection-worker-unspecified", "UNSPECIFIED", ""),
        ("projection-worker-global-position", "GLOBAL_POSITION", "123"),
        (
            "projection-worker-event-id",
            "EVENT_ID",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        (
            "projection-worker-event-id-trimmed",
            "EVENT_ID",
            " 550e8400-e29b-41d4-a716-446655440000 ",
        ),
        (
            "projection-worker-appended-at",
            "APPENDED_AT",
            "2026-06-07T12:00:00+00:00",
        ),
    ],
)
def test_projection_checkpoints_accepts_valid_cursor_shapes(
    db_connection: Connection,
    clean_database: None,
    worker_name: str,
    cursor_kind: str,
    cursor_value: str,
) -> None:
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_checkpoints (
                worker_name,
                cursor_kind,
                cursor_value
            )
            VALUES (%s, %s, %s)
            """,
            (
                worker_name,
                cursor_kind,
                cursor_value,
            ),
        )

    db_connection.commit()


def test_projection_checkpoints_rejects_empty_worker_name(
    db_connection: Connection,
    clean_database: None,
) -> None:
    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_checkpoints (
                    worker_name,
                    cursor_kind,
                    cursor_value
                )
                VALUES (%s, %s, %s)
                """,
                (
                    "   ",
                    "UNSPECIFIED",
                    "",
                ),
            )

    db_connection.rollback()


@pytest.mark.parametrize(
    ("cursor_kind", "cursor_value"),
    [
        ("UNKNOWN", ""),
        ("UNSPECIFIED", "123"),
        ("GLOBAL_POSITION", "abc"),
        ("EVENT_ID", "not-a-uuid"),
        ("APPENDED_AT", ""),
        ("APPENDED_AT", "   "),
    ],
)
def test_projection_checkpoints_rejects_invalid_cursor_shapes(
    db_connection: Connection,
    clean_database: None,
    cursor_kind: str,
    cursor_value: str,
) -> None:
    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_checkpoints (
                    worker_name,
                    cursor_kind,
                    cursor_value
                )
                VALUES (%s, %s, %s)
                """,
                (
                    "projection-worker-invalid-cursor",
                    cursor_kind,
                    cursor_value,
                ),
            )

    db_connection.rollback()


def _insert_progress_lineage_event(
    connection: Connection,
    *,
    order_id: str,
) -> tuple[str, int]:
    event_id = str(uuid4())
    request_id = f"request-{uuid4()}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO order_events (
                accepted_event_id,
                order_id,
                sequence,
                event_type,
                request_id,
                amount,
                occurred_at_ms,
                proof_prev_event_id,
                proof_prev_version,
                proof_prev_status
            )
            VALUES (%s, %s, 1, 'CREATED', %s, 100.00, 1, NULL, 0, 'INIT')
            RETURNING global_position
            """,
            (event_id, order_id, request_id),
        )
        global_position = int(cursor.fetchone()[0])
    connection.commit()
    return event_id, global_position


def test_projection_order_progress_accepts_valid_initial_lineage(
    db_connection: Connection,
    clean_database: None,
) -> None:
    order_id = "order-progress-schema"
    event_id, global_position = _insert_progress_lineage_event(
        db_connection,
        order_id=order_id,
    )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_order_progress (
                projection_name,
                projection_epoch,
                order_id,
                last_sequence,
                last_event_id,
                last_global_position
            )
            VALUES ('order_state_projection', 1, %s, 1, %s, %s)
            """,
            (order_id, event_id, global_position),
        )
    db_connection.commit()


@pytest.mark.parametrize(
    ("projection_name", "projection_epoch", "order_id", "last_sequence"),
    [
        ("   ", 1, "order-progress-invalid", 1),
        ("order_state_projection", 0, "order-progress-invalid", 1),
        ("order_state_projection", 1, "   ", 1),
        ("order_state_projection", 1, "order-progress-invalid", 0),
    ],
)
def test_projection_order_progress_rejects_invalid_physical_identity(
    db_connection: Connection,
    clean_database: None,
    projection_name: str,
    projection_epoch: int,
    order_id: str,
    last_sequence: int,
) -> None:
    event_order_id = "order-progress-valid-lineage"
    event_id, global_position = _insert_progress_lineage_event(
        db_connection,
        order_id=event_order_id,
    )

    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_order_progress (
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    last_event_id,
                    last_global_position
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    event_id,
                    global_position,
                ),
            )
    db_connection.rollback()


def test_projection_order_progress_rejects_mismatched_event_lineage(
    db_connection: Connection,
    clean_database: None,
) -> None:
    first_event_id, _ = _insert_progress_lineage_event(
        db_connection,
        order_id="order-progress-first",
    )
    _, second_global_position = _insert_progress_lineage_event(
        db_connection,
        order_id="order-progress-second",
    )

    with pytest.raises(errors.ForeignKeyViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projection_order_progress (
                    projection_name,
                    projection_epoch,
                    order_id,
                    last_sequence,
                    last_event_id,
                    last_global_position
                )
                VALUES (
                    'order_state_projection',
                    1,
                    'order-progress-first',
                    1,
                    %s,
                    %s
                )
                """,
                (first_event_id, second_global_position),
            )
    db_connection.rollback()


@pytest.mark.parametrize("next_sequence", [1, 3])
def test_projection_order_progress_rejects_regression_or_skip(
    db_connection: Connection,
    clean_database: None,
    next_sequence: int,
) -> None:
    order_id = "order-progress-exact-next"
    event_id, global_position = _insert_progress_lineage_event(
        db_connection,
        order_id=order_id,
    )
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO projection_order_progress (
                projection_name,
                projection_epoch,
                order_id,
                last_sequence,
                last_event_id,
                last_global_position
            )
            VALUES ('order_state_projection', 1, %s, 1, %s, %s)
            """,
            (order_id, event_id, global_position),
        )
    db_connection.commit()

    with pytest.raises(errors.CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE projection_order_progress
                SET last_sequence = %s
                WHERE projection_name = 'order_state_projection'
                  AND projection_epoch = 1
                  AND order_id = %s
                """,
                (next_sequence, order_id),
            )
    db_connection.rollback()
