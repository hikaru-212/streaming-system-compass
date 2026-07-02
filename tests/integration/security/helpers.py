from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

import pytest
from psycopg import Connection, sql
from psycopg.errors import InsufficientPrivilege


RUNTIME_ROLES: frozenset[str] = frozenset(
    {
        "compass_app_writer",
        "compass_projection_worker",
        "compass_snapshot_worker",
        "compass_readonly",
    }
)


class UnknownRuntimeRoleError(ValueError):
    pass


def _validate_runtime_role(role: str) -> None:
    if role not in RUNTIME_ROLES:
        raise UnknownRuntimeRoleError(
            f"Unknown runtime role: {role!r}. "
            f"Expected one of: {sorted(RUNTIME_ROLES)!r}"
        )


def grant_runtime_roles_to_current_user(connection: Connection[Any]) -> None:
    """Allow the test owner connection to use SET ROLE for runtime-role tests.

    Stage 3.5E runtime roles are responsibility boundaries, not login users.
    Permission-boundary tests therefore connect as the test owner and switch
    into the runtime role with SET ROLE.

    This helper is intentionally test setup, not production authorization logic.
    """

    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        current_user = cursor.fetchone()[0]

        for role in sorted(RUNTIME_ROLES):
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(
                    sql.Identifier(role),
                    sql.Identifier(current_user),
                )
            )

    connection.commit()


@contextmanager
def runtime_role(connection: Connection[Any], role: str):
    """Temporarily execute one permission probe as a runtime role.

    The connection remains physically owned by the test owner. The session role
    is switched only for the duration of the context.

    This helper is for Layer 2 permission-boundary probes. It always rolls back
    before RESET ROLE, even after successful statements. That is intentional:

    - successful allowed statements should not leak fixture data into later
      permission probes;
    - denied statements leave the transaction in an aborted state, and RESET
      ROLE cannot run safely until the transaction is rolled back;
    - expected failures wrapped by pytest.raises are swallowed by pytest, so the
      cleanup path cannot rely on seeing an exception escape the context.

    This helper intentionally owns the connection transaction state during the
    probe. Callers must not enter it with uncommitted setup work that they
    expect to preserve. The helper may roll back before the probe and will roll
    back again before RESET ROLE during cleanup.

    This helper also assumes exclusive, linear use of the connection. SET ROLE
    is session-level state, so this helper must not be used with a connection
    that is shared across concurrent tests, async tasks, background workers, or
    connection-pool borrowers.

    Do not use this helper for Layer 3 causal / multi-role flow tests where one
    role's committed write must be observed by another role. Those tests should
    use a separate committed-flow helper.

    Do not use this helper as a production role-switching abstraction. A real
    runtime deployment should prefer role-specific database users or
    role-specific connection pools rather than ad-hoc SET ROLE on a shared
    session.
    """

    _validate_runtime_role(role)

    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))

    try:
        yield
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
        connection.commit()


def execute_statement(
    connection: Connection[Any],
    statement: str,
    params: Sequence[Any] | None = None,
) -> list[tuple[Any, ...]] | None:
    """Execute one SQL statement and return rows only if PostgreSQL returns a result set.

    A returned result set does not imply that the statement was read-only.
    PostgreSQL statements such as INSERT ... RETURNING, UPDATE ... RETURNING,
    DELETE ... RETURNING, or functions with side effects may also return rows.

    Permission tests should therefore express the intended operation through the
    SQL statement itself and rely on PostgreSQL privileges for enforcement. This
    helper only normalizes execution and result fetching.
    """

    with connection.cursor() as cursor:
        cursor.execute(statement, params or ())
        if cursor.description is None:
            return None
        return cursor.fetchall()


def assert_role_can_execute(
    connection: Connection[Any],
    *,
    role: str,
    statement: str,
    params: Sequence[Any] | None = None,
) -> list[tuple[Any, ...]] | None:
    """Assert that a runtime role is allowed to execute one isolated statement.

    The statement is rolled back after the assertion. This helper proves that a
    role has permission to execute the statement; it does not persist successful
    writes for later assertions.
    """

    with runtime_role(connection, role):
        return execute_statement(connection, statement, params)


def assert_role_cannot_execute(
    connection: Connection[Any],
    *,
    role: str,
    statement: str,
    params: Sequence[Any] | None = None,
    error_type: type[Exception] = InsufficientPrivilege,
) -> None:
    """Assert that a runtime role is rejected by PostgreSQL permissions.

    Use this helper only for statements that are otherwise syntactically and
    structurally valid. The expected failure should come from privilege checks,
    not from missing rows, invalid input, or domain constraints.
    """

    with runtime_role(connection, role):
        with pytest.raises(error_type):
            execute_statement(connection, statement, params)