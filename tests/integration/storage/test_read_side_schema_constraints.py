from decimal import Decimal

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