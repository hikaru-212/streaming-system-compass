"""Pure deterministic tests for the Stage 4B.2 PR7 budget preflight."""

from __future__ import annotations

import json
from typing import Any

import pytest

import experiments.stage4b2.postgres_bounded_concurrency as preflight_module
from experiments.stage4b2.postgres_bounded_concurrency import (
    CANDIDATE_WORKER_LEVELS,
    CONNECTION_FORMULA,
    LEVEL_C_SCHEMA_NAME,
    LEVEL_C_SCHEMA_VERSION,
    PREFLIGHT_SCHEMA_NAME,
    PREFLIGHT_SCHEMA_VERSION,
    BudgetStatus,
    ConnectionBudgetFacts,
    ConnectionBudgetSafetyError,
    InvalidConnectionBudgetError,
    RoleConnectionAccess,
    build_connection_budget_preflight,
    connection_budget_preflight_to_dict,
    connection_budget_preflight_to_json,
    required_connections,
    run_postgres_connection_budget_preflight,
)


def _facts(
    *,
    max_connections: int = 20,
    superuser_reserved_connections: int = 2,
    reserved_connections: int | None = 1,
    current_client_sessions: int = 4,
    current_role_is_superuser: bool = False,
    current_role_can_use_reserved_connections: bool = False,
) -> ConnectionBudgetFacts:
    return ConnectionBudgetFacts(
        server_version_num="160014",
        max_connections=max_connections,
        superuser_reserved_connections=superuser_reserved_connections,
        reserved_connections=reserved_connections,
        current_client_sessions=current_client_sessions,
        current_role_is_superuser=current_role_is_superuser,
        current_role_can_use_reserved_connections=(
            current_role_can_use_reserved_connections
        ),
    )


def test_pr7_schema_names_are_separate_from_pr6_schema_v1() -> None:
    assert PREFLIGHT_SCHEMA_NAME == "stage4b2-pr7-connection-budget-preflight"
    assert PREFLIGHT_SCHEMA_VERSION == 1
    assert LEVEL_C_SCHEMA_NAME == "stage4b2-pr7-bounded-concurrency"
    assert LEVEL_C_SCHEMA_VERSION == 1


def test_candidates_are_proposed_but_never_retained_before_human_review() -> None:
    result = build_connection_budget_preflight(_facts())

    assert result.status is BudgetStatus.HUMAN_REVIEW_REQUIRED
    assert result.selection.candidate_levels == CANDIDATE_WORKER_LEVELS
    assert result.selection.proposed_levels_for_human_review == (1, 2, 4, 8)
    assert result.selection.retained_levels == ()
    assert result.selection.human_review_required is True
    assert result.selection.fewer_than_three_proposed_levels is False


def test_connection_requirement_is_exactly_one_persistent_connection_per_worker(
) -> None:
    assert CONNECTION_FORMULA == (
        "required_connections(N) = N worker connections + 0 dedicated "
        "controller/setup connections + 0 observer connections"
    )
    assert [required_connections(level) for level in CANDIDATE_WORKER_LEVELS] == [
        1,
        2,
        4,
        8,
    ]

    with pytest.raises(InvalidConnectionBudgetError, match="positive integer"):
        required_connections(0)


@pytest.mark.parametrize(
    ("is_superuser", "can_use_reserved", "expected_access", "expected_ceiling"),
    [
        (False, False, RoleConnectionAccess.REGULAR, 17),
        (False, True, RoleConnectionAccess.RESERVED, 18),
        (True, False, RoleConnectionAccess.SUPERUSER, 20),
    ],
)
def test_role_capability_changes_usable_ceiling_without_identity(
    is_superuser: bool,
    can_use_reserved: bool,
    expected_access: RoleConnectionAccess,
    expected_ceiling: int,
) -> None:
    facts = _facts(
        current_role_is_superuser=is_superuser,
        current_role_can_use_reserved_connections=can_use_reserved,
    )

    assert facts.role_connection_access is expected_access
    assert facts.usable_connection_ceiling == expected_ceiling
    assert facts.other_client_sessions == 3
    assert facts.available_worker_connections_before_headroom == expected_ceiling - 3


def test_unexposed_reserved_connections_setting_is_recorded_and_applied_as_zero(
) -> None:
    facts = _facts(reserved_connections=None)
    payload = connection_budget_preflight_to_dict(
        build_connection_budget_preflight(facts)
    )

    assert facts.reserved_connections_applied == 0
    assert facts.usable_connection_ceiling == 18
    assert payload["live_budget"]["reserved_connections"] is None
    assert payload["live_budget"]["reserved_connections_applied"] == 0


def test_candidate_assessment_reports_raw_slots_before_unselected_headroom() -> None:
    result = build_connection_budget_preflight(_facts())
    assessments = {item.candidate_level: item for item in result.assessments}

    assert result.facts.available_worker_connections_before_headroom == 14
    assert assessments[1].required_connections == 1
    assert assessments[1].raw_slots_remaining_before_headroom == 13
    assert assessments[8].required_connections == 8
    assert assessments[8].raw_slots_remaining_before_headroom == 6
    assert all(item.feasible_before_headroom for item in result.assessments)


def test_insufficient_budget_is_not_misreported_as_invalid_or_retained() -> None:
    result = build_connection_budget_preflight(
        _facts(
            max_connections=10,
            superuser_reserved_connections=3,
            reserved_connections=2,
            current_client_sessions=6,
        )
    )

    assert result.facts.usable_connection_ceiling == 5
    assert result.facts.other_client_sessions == 5
    assert result.facts.available_worker_connections_before_headroom == 0
    assert result.status is BudgetStatus.INSUFFICIENT_BUDGET
    assert result.selection.proposed_levels_for_human_review == ()
    assert result.selection.retained_levels == ()
    assert result.selection.fewer_than_three_proposed_levels is True


def test_fewer_than_three_raw_feasible_levels_requires_curve_review() -> None:
    result = build_connection_budget_preflight(
        _facts(
            max_connections=10,
            superuser_reserved_connections=3,
            reserved_connections=2,
            current_client_sessions=4,
        )
    )

    assert result.facts.available_worker_connections_before_headroom == 2
    assert result.selection.proposed_levels_for_human_review == (1, 2)
    assert result.selection.retained_levels == ()
    assert result.selection.fewer_than_three_proposed_levels is True


@pytest.mark.parametrize(
    "facts_kwargs",
    [
        {"max_connections": 0},
        {"superuser_reserved_connections": -1},
        {"reserved_connections": -1},
        {
            "max_connections": 5,
            "superuser_reserved_connections": 3,
            "reserved_connections": 2,
        },
        {"current_client_sessions": 0},
        {"max_connections": 5, "current_client_sessions": 6},
    ],
)
def test_invalid_budget_facts_fail_closed(facts_kwargs: dict[str, Any]) -> None:
    with pytest.raises(InvalidConnectionBudgetError):
        _facts(**facts_kwargs)


def test_serialized_preflight_contains_only_sanitized_budget_metadata() -> None:
    result = build_connection_budget_preflight(_facts())
    payload = connection_budget_preflight_to_dict(result)
    serialized = connection_budget_preflight_to_json(result)

    assert payload["schema_name"] == PREFLIGHT_SCHEMA_NAME
    assert payload["retained_levels"] == []
    assert payload["human_review_required"] is True
    assert payload["connection_formula"]["preflight_controller_connections"] == 1
    assert "://" not in serialized
    forbidden_keys = {
        "credentials",
        "database_name",
        "dsn",
        "environment_variable_values",
        "host",
        "hostname",
        "password",
        "port",
        "test_database_url",
        "username",
    }
    assert forbidden_keys.isdisjoint(_recursive_keys(json.loads(serialized)))


def test_secret_shaped_payload_is_rejected_before_serialization() -> None:
    with pytest.raises(
        InvalidConnectionBudgetError,
        match="forbidden metadata key",
    ):
        preflight_module._reject_secret_shaped_payload(
            {"safe": {"database_name": "must-not-serialize"}}
        )

    with pytest.raises(
        InvalidConnectionBudgetError,
        match="secret-shaped metadata value",
    ):
        preflight_module._reject_secret_shaped_payload(
            {"safe": "postgresql://must-not-serialize"}
        )


class _FakeCursor:
    def __init__(self, connection: "_FakeConnection") -> None:
        self._connection = connection
        self._row: tuple[Any, ...] | None = None

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        normalized = " ".join(statement.split())
        self._connection.statements.append(normalized)
        if "current_database()" in normalized:
            self._row = (self._connection.database_name,)
        else:
            self._row = self._connection.budget_row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class _FakeConnection:
    def __init__(
        self,
        *,
        database_name: str = "compass_test",
        budget_row: tuple[Any, ...] = (
            "160014",
            100,
            3,
            "0",
            False,
            False,
            5,
        ),
    ) -> None:
        self.database_name = database_name
        self.budget_row = budget_row
        self.statements: list[str] = []
        self.rollback_count = 0
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.closed = True


def test_guarded_live_capability_is_read_only_and_does_not_retain_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeConnection()
    supplied_urls: list[str] = []

    def connect(database_url: str) -> _FakeConnection:
        supplied_urls.append(database_url)
        return connection

    from src.storage import postgres_connection

    monkeypatch.setattr(postgres_connection, "connect_postgres", connect)
    secret_url = "postgresql://secret-user:secret-password@secret-host/compass_test"

    result = run_postgres_connection_budget_preflight(secret_url)
    serialized = connection_budget_preflight_to_json(result)

    assert supplied_urls == [secret_url]
    assert secret_url not in serialized
    assert "secret-user" not in serialized
    assert "secret-password" not in serialized
    assert "secret-host" not in serialized
    assert len(connection.statements) == 2
    assert all(statement.startswith("SELECT") for statement in connection.statements)
    assert connection.rollback_count == 1
    assert connection.closed is True


def test_non_test_database_guard_hides_database_and_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _FakeConnection(database_name="sensitive_production_name")

    from src.storage import postgres_connection

    monkeypatch.setattr(
        postgres_connection,
        "connect_postgres",
        lambda _database_url: connection,
    )
    secret_url = "postgresql://secret@secret/sensitive_production_name"

    with pytest.raises(ConnectionBudgetSafetyError) as raised:
        run_postgres_connection_budget_preflight(secret_url)

    message = str(raised.value)
    assert "sensitive_production_name" not in message
    assert secret_url not in message
    assert connection.rollback_count == 1
    assert connection.closed is True


def test_cli_refuses_any_level_c_execution_surface() -> None:
    with pytest.raises(SystemExit, match="Level-C execution is not implemented"):
        preflight_module.main([])


def test_cli_retains_only_exception_type_for_unknown_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise RuntimeError("arbitrary secret detail must remain hidden")

    monkeypatch.setattr(
        preflight_module,
        "run_postgres_connection_budget_preflight_from_environment",
        fail,
    )

    with pytest.raises(SystemExit) as raised:
        preflight_module.main(["--preflight"])

    assert str(raised.value) == (
        "PR7 connection-budget preflight failed: RuntimeError"
    )


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(key).lower() for key in value),
            *(
                nested_key
                for nested in value.values()
                for nested_key in _recursive_keys(nested)
            ),
        }
    if isinstance(value, list):
        return {
            nested_key
            for nested in value
            for nested_key in _recursive_keys(nested)
        }
    return set()
