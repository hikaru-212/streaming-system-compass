import uuid

import pytest
from psycopg.errors import CheckViolation


def test_order_events_rejects_lowercase_event_type(db_connection, clean_database):
    with pytest.raises(CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_events (
                    accepted_event_id,
                    event_schema_version,
                    order_id,
                    sequence,
                    event_type,
                    request_id,
                    amount,
                    occurred_at_ms,
                    proof_prev_event_id,
                    proof_prev_version,
                    proof_prev_status,
                    payload_json,
                    proof_json,
                    metadata_json
                )
                VALUES (
                    %s, 1, %s, 1, 'created', %s, 100.00, 1234567890,
                    NULL, 0, 'INIT',
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb
                )
                """,
                (
                    uuid.uuid4(),
                    f"order-{uuid.uuid4()}",
                    f"request-{uuid.uuid4()}",
                ),
            )

    db_connection.rollback()


def test_order_events_rejects_invalid_proof_prev_status(db_connection, clean_database):
    with pytest.raises(CheckViolation):
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_events (
                    accepted_event_id,
                    event_schema_version,
                    order_id,
                    sequence,
                    event_type,
                    request_id,
                    amount,
                    occurred_at_ms,
                    proof_prev_event_id,
                    proof_prev_version,
                    proof_prev_status,
                    payload_json,
                    proof_json,
                    metadata_json
                )
                VALUES (
                    %s, 1, %s, 1, 'CREATED', %s, 100.00, 1234567890,
                    NULL, 0, 'UNKNOWN',
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb
                )
                """,
                (
                    uuid.uuid4(),
                    f"order-{uuid.uuid4()}",
                    f"request-{uuid.uuid4()}",
                ),
            )

    db_connection.rollback()