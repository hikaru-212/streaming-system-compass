from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from psycopg import Connection

from tests.integration.security.helpers import (
    assert_role_can_execute,
    assert_role_cannot_execute,
)


def _decision_receipt_insert_statement() -> tuple[str, tuple[object, ...], UUID]:
    receipt_id = uuid4()
    return (
        """
        INSERT INTO decision_receipts (
            receipt_id,
            receipt_serialization_version,
            outcome_id,
            ok,
            boundary,
            category,
            semantic_code,
            severity,
            risk_level,
            reversibility,
            reason,
            evidence_source,
            subject_type,
            identity_source,
            fallback_required,
            rebuild_required,
            operator_review_required,
            retry_candidate,
            evidence_summary,
            metadata,
            materialization_provenance
        )
        VALUES (
            %s,
            1,
            %s,
            TRUE,
            'RUNTIME_GOVERNANCE',
            'VALID',
            'SEMANTICALLY_VALID',
            'INFO',
            'LOW',
            'REVERSIBLE',
            'Runtime evidence is semantically valid.',
            'RUNTIME_OBSERVATION',
            'UNKNOWN',
            'UNKNOWN',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            'NOT_EVALUATED',
            '{}'::jsonb,
            '{}'::jsonb,
            'LIVE_RESULT'
        )
        RETURNING receipt_id
        """,
        (receipt_id, uuid4()),
        receipt_id,
    )


def _insert_decision_receipt_as_test_owner(
    connection: Connection[Any],
) -> UUID:
    statement, params, receipt_id = _decision_receipt_insert_statement()
    connection.execute(statement, params)
    connection.commit()
    return receipt_id


@pytest.mark.parametrize("role", ["compass_app_writer", "compass_readonly"])
def test_authorized_roles_can_select_decision_receipts(
    connection: Connection[Any],
    role: str,
) -> None:
    receipt_id = _insert_decision_receipt_as_test_owner(connection)

    rows = assert_role_can_execute(
        connection,
        role=role,
        statement="SELECT receipt_id FROM decision_receipts",
    )

    assert rows == [(receipt_id,)]


@pytest.mark.parametrize(
    "role",
    ["compass_projection_worker", "compass_snapshot_worker"],
)
def test_worker_roles_cannot_select_decision_receipts(
    connection: Connection[Any],
    role: str,
) -> None:
    _insert_decision_receipt_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role=role,
        statement="SELECT receipt_id FROM decision_receipts",
    )


def test_app_writer_can_insert_decision_receipts(
    connection: Connection[Any],
) -> None:
    statement, params, receipt_id = _decision_receipt_insert_statement()

    rows = assert_role_can_execute(
        connection,
        role="compass_app_writer",
        statement=statement,
        params=params,
    )

    assert rows == [(receipt_id,)]


@pytest.mark.parametrize(
    "role",
    [
        "compass_readonly",
        "compass_projection_worker",
        "compass_snapshot_worker",
    ],
)
def test_unauthorized_roles_cannot_insert_decision_receipts(
    connection: Connection[Any],
    role: str,
) -> None:
    statement, params, _receipt_id = _decision_receipt_insert_statement()

    assert_role_cannot_execute(
        connection,
        role=role,
        statement=statement,
        params=params,
    )


@pytest.mark.parametrize(
    "role",
    [
        "compass_app_writer",
        "compass_readonly",
        "compass_projection_worker",
        "compass_snapshot_worker",
    ],
)
def test_runtime_roles_cannot_update_decision_receipts(
    connection: Connection[Any],
    role: str,
) -> None:
    receipt_id = _insert_decision_receipt_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role=role,
        statement="""
            UPDATE decision_receipts
            SET reason = 'Replacement is not allowed.'
            WHERE receipt_id = %s
        """,
        params=(receipt_id,),
    )


@pytest.mark.parametrize(
    "role",
    [
        "compass_app_writer",
        "compass_readonly",
        "compass_projection_worker",
        "compass_snapshot_worker",
    ],
)
def test_runtime_roles_cannot_delete_decision_receipts(
    connection: Connection[Any],
    role: str,
) -> None:
    receipt_id = _insert_decision_receipt_as_test_owner(connection)

    assert_role_cannot_execute(
        connection,
        role=role,
        statement="DELETE FROM decision_receipts WHERE receipt_id = %s",
        params=(receipt_id,),
    )
