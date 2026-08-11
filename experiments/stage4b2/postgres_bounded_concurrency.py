"""Stage 4B.2 PR7 connection-budget preflight infrastructure.

This PR7-owned module performs pure connection accounting and one guarded,
read-only PostgreSQL capability inspection.  It does not run producer calls,
create a worker sweep, time PostgreSQL, publish Level-C evidence, choose final
worker levels, or change server configuration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any


PREFLIGHT_SCHEMA_NAME = "stage4b2-pr7-connection-budget-preflight"
PREFLIGHT_SCHEMA_VERSION = 1
LEVEL_C_SCHEMA_NAME = "stage4b2-pr7-bounded-concurrency"
LEVEL_C_SCHEMA_VERSION = 1
CANDIDATE_WORKER_LEVELS = (1, 2, 4, 8)

PREFLIGHT_CONTROLLER_CONNECTIONS = 1
RUNTIME_DEDICATED_CONTROLLER_CONNECTIONS = 0
RUNTIME_OBSERVER_CONNECTIONS = 0

CONNECTION_FORMULA = (
    "required_connections(N) = N worker connections + 0 dedicated "
    "controller/setup connections + 0 observer connections"
)

_FORBIDDEN_SERIALIZED_KEYS = frozenset(
    {
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
)
_FORBIDDEN_SERIALIZED_VALUE_FRAGMENTS = (
    "://",
    "credentials=",
    "database_name=",
    "dsn=",
    "host=",
    "hostname=",
    "password=",
    "port=",
    "test_database_url=",
    "user=",
    "username=",
)


class ConnectionBudgetPreflightError(RuntimeError):
    """Base error for authored PR7 budget-preflight failures."""


class ConnectionBudgetSafetyError(ConnectionBudgetPreflightError):
    """Reject unsafe database targeting before budget inspection continues."""


class InvalidConnectionBudgetError(ConnectionBudgetPreflightError):
    """Reject missing, malformed, or internally inconsistent budget facts."""


class BudgetStatus(str, Enum):
    """Distinguish reviewable raw feasibility from no feasible candidate."""

    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    INSUFFICIENT_BUDGET = "INSUFFICIENT_BUDGET"


class RoleConnectionAccess(str, Enum):
    """Describe which PostgreSQL connection slots the current role may use."""

    REGULAR = "REGULAR"
    RESERVED = "RESERVED"
    SUPERUSER = "SUPERUSER"


@dataclass(frozen=True)
class ConnectionBudgetFacts:
    """Hold sanitized live facts needed for point-in-time slot accounting.

    The current client-session count includes the one temporary PR7 preflight
    controller connection.  No identity or connection endpoint is retained.
    """

    server_version_num: str
    max_connections: int
    superuser_reserved_connections: int
    reserved_connections: int | None
    current_client_sessions: int
    current_role_is_superuser: bool
    current_role_can_use_reserved_connections: bool
    preflight_controller_connections: int = PREFLIGHT_CONTROLLER_CONNECTIONS

    def __post_init__(self) -> None:
        if (
            not isinstance(self.server_version_num, str)
            or not self.server_version_num.isdigit()
        ):
            raise InvalidConnectionBudgetError(
                "server_version_num must be a decimal digit string"
            )
        _require_positive_int(self.max_connections, "max_connections")
        _require_non_negative_int(
            self.superuser_reserved_connections,
            "superuser_reserved_connections",
        )
        if self.reserved_connections is not None:
            _require_non_negative_int(
                self.reserved_connections,
                "reserved_connections",
            )
        _require_positive_int(self.current_client_sessions, "current_client_sessions")
        _require_positive_int(
            self.preflight_controller_connections,
            "preflight_controller_connections",
        )
        if self.preflight_controller_connections != PREFLIGHT_CONTROLLER_CONNECTIONS:
            raise InvalidConnectionBudgetError(
                "PR7 budget preflight requires exactly one controller connection"
            )
        if self.current_client_sessions < self.preflight_controller_connections:
            raise InvalidConnectionBudgetError(
                "current client sessions cannot omit the preflight controller"
            )
        if self.current_client_sessions > self.max_connections:
            raise InvalidConnectionBudgetError(
                "current client sessions cannot exceed max_connections"
            )
        if type(self.current_role_is_superuser) is not bool:
            raise InvalidConnectionBudgetError(
                "current_role_is_superuser must be boolean"
            )
        if type(self.current_role_can_use_reserved_connections) is not bool:
            raise InvalidConnectionBudgetError(
                "current_role_can_use_reserved_connections must be boolean"
            )
        if (
            self.superuser_reserved_connections
            + self.reserved_connections_applied
            >= self.max_connections
        ):
            raise InvalidConnectionBudgetError(
                "reserved connection settings leave no regular connection slots"
            )

    @property
    def reserved_connections_applied(self) -> int:
        """Return zero when the live server does not expose the optional setting."""

        return self.reserved_connections or 0

    @property
    def role_connection_access(self) -> RoleConnectionAccess:
        """Classify the current role without retaining its identity."""

        if self.current_role_is_superuser:
            return RoleConnectionAccess.SUPERUSER
        if self.current_role_can_use_reserved_connections:
            return RoleConnectionAccess.RESERVED
        return RoleConnectionAccess.REGULAR

    @property
    def usable_connection_ceiling(self) -> int:
        """Calculate the live role-qualified ceiling before current occupancy."""

        if self.role_connection_access is RoleConnectionAccess.SUPERUSER:
            return self.max_connections
        if self.role_connection_access is RoleConnectionAccess.RESERVED:
            return self.max_connections - self.superuser_reserved_connections
        return (
            self.max_connections
            - self.superuser_reserved_connections
            - self.reserved_connections_applied
        )

    @property
    def other_client_sessions(self) -> int:
        """Exclude the temporary preflight controller from current occupancy."""

        return self.current_client_sessions - self.preflight_controller_connections

    @property
    def available_worker_connections_before_headroom(self) -> int:
        """Return raw future worker slots without inventing safety headroom."""

        return max(0, self.usable_connection_ceiling - self.other_client_sessions)


@dataclass(frozen=True)
class CandidateLevelAssessment:
    """Describe raw feasibility for one documented candidate worker level."""

    candidate_level: int
    required_connections: int
    available_worker_connections_before_headroom: int
    raw_slots_remaining_before_headroom: int
    feasible_before_headroom: bool

    def __post_init__(self) -> None:
        _require_positive_int(self.candidate_level, "candidate_level")
        _require_positive_int(self.required_connections, "required_connections")
        _require_non_negative_int(
            self.available_worker_connections_before_headroom,
            "available_worker_connections_before_headroom",
        )
        if self.required_connections != required_connections(self.candidate_level):
            raise InvalidConnectionBudgetError(
                "candidate requirement does not match the PR7 connection formula"
            )
        expected_remaining = (
            self.available_worker_connections_before_headroom
            - self.required_connections
        )
        if self.raw_slots_remaining_before_headroom != expected_remaining:
            raise InvalidConnectionBudgetError(
                "candidate remaining-slot accounting is inconsistent"
            )
        if type(self.feasible_before_headroom) is not bool:
            raise InvalidConnectionBudgetError(
                "feasible_before_headroom must be boolean"
            )
        if self.feasible_before_headroom is not (expected_remaining >= 0):
            raise InvalidConnectionBudgetError(
                "candidate feasibility does not match remaining slots"
            )


@dataclass(frozen=True)
class LevelSelection:
    """Keep candidates and proposals separate from human-retained levels."""

    candidate_levels: tuple[int, ...]
    proposed_levels_for_human_review: tuple[int, ...]
    retained_levels: tuple[int, ...] = ()
    human_review_required: bool = True

    def __post_init__(self) -> None:
        if self.candidate_levels != CANDIDATE_WORKER_LEVELS:
            raise InvalidConnectionBudgetError(
                "PR7 candidate levels must remain exactly 1, 2, 4, and 8"
            )
        if any(
            level not in self.candidate_levels
            for level in self.proposed_levels_for_human_review
        ):
            raise InvalidConnectionBudgetError(
                "proposed levels must be a subset of candidate levels"
            )
        if tuple(sorted(set(self.proposed_levels_for_human_review))) != (
            self.proposed_levels_for_human_review
        ):
            raise InvalidConnectionBudgetError(
                "proposed levels must be unique and ordered"
            )
        if self.retained_levels:
            raise InvalidConnectionBudgetError(
                "the preflight cannot retain levels before human headroom review"
            )
        if self.human_review_required is not True:
            raise InvalidConnectionBudgetError(
                "connection-budget preflight always requires human review"
            )

    @property
    def fewer_than_three_proposed_levels(self) -> bool:
        """Flag when raw feasibility cannot support three curve points."""

        return len(self.proposed_levels_for_human_review) < 3


@dataclass(frozen=True)
class ConnectionBudgetPreflightResult:
    """Return sanitized raw feasibility without selecting final worker levels."""

    facts: ConnectionBudgetFacts
    assessments: tuple[CandidateLevelAssessment, ...]
    selection: LevelSelection
    status: BudgetStatus

    def __post_init__(self) -> None:
        if tuple(item.candidate_level for item in self.assessments) != (
            self.selection.candidate_levels
        ):
            raise InvalidConnectionBudgetError(
                "candidate assessments do not match candidate levels"
            )
        proposed = tuple(
            item.candidate_level
            for item in self.assessments
            if item.feasible_before_headroom
        )
        if proposed != self.selection.proposed_levels_for_human_review:
            raise InvalidConnectionBudgetError(
                "proposed levels do not match raw candidate feasibility"
            )
        expected_status = (
            BudgetStatus.HUMAN_REVIEW_REQUIRED
            if proposed
            else BudgetStatus.INSUFFICIENT_BUDGET
        )
        if self.status is not expected_status:
            raise InvalidConnectionBudgetError(
                "preflight status does not match raw candidate feasibility"
            )


def required_connections(worker_level: int) -> int:
    """Return the exact future recorded-runtime connection requirement.

    One persistent connection belongs to each worker lane.  Setup and
    post-timing verification reuse a worker connection while no timed batch is
    active, so no dedicated controller or observer connection is added.
    """

    _require_positive_int(worker_level, "worker_level")
    return (
        worker_level
        + RUNTIME_DEDICATED_CONTROLLER_CONNECTIONS
        + RUNTIME_OBSERVER_CONNECTIONS
    )


def build_connection_budget_preflight(
    facts: ConnectionBudgetFacts,
) -> ConnectionBudgetPreflightResult:
    """Calculate candidate feasibility before environment-specific headroom.

    The result proposes raw-feasible candidates for human review.  It never
    freezes retained levels and does not infer capacity from the server ceiling.
    """

    available = facts.available_worker_connections_before_headroom
    assessments = tuple(
        CandidateLevelAssessment(
            candidate_level=level,
            required_connections=required_connections(level),
            available_worker_connections_before_headroom=available,
            raw_slots_remaining_before_headroom=(
                available - required_connections(level)
            ),
            feasible_before_headroom=required_connections(level) <= available,
        )
        for level in CANDIDATE_WORKER_LEVELS
    )
    proposed = tuple(
        item.candidate_level for item in assessments if item.feasible_before_headroom
    )
    selection = LevelSelection(
        candidate_levels=CANDIDATE_WORKER_LEVELS,
        proposed_levels_for_human_review=proposed,
    )
    status = (
        BudgetStatus.HUMAN_REVIEW_REQUIRED
        if proposed
        else BudgetStatus.INSUFFICIENT_BUDGET
    )
    return ConnectionBudgetPreflightResult(
        facts=facts,
        assessments=assessments,
        selection=selection,
        status=status,
    )


def connection_budget_preflight_to_dict(
    result: ConnectionBudgetPreflightResult,
) -> dict[str, Any]:
    """Build the stable sanitized PR7 preflight representation."""

    facts = result.facts
    payload: dict[str, Any] = {
        "schema_name": PREFLIGHT_SCHEMA_NAME,
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "status": result.status.value,
        "connection_formula": {
            "expression": CONNECTION_FORMULA,
            "worker_connections": "N",
            "dedicated_recorded_runtime_controller_connections": (
                RUNTIME_DEDICATED_CONTROLLER_CONNECTIONS
            ),
            "dedicated_observer_connections": RUNTIME_OBSERVER_CONNECTIONS,
            "preflight_controller_connections": PREFLIGHT_CONTROLLER_CONNECTIONS,
        },
        "live_budget": {
            "server_version_num": facts.server_version_num,
            "max_connections": facts.max_connections,
            "superuser_reserved_connections": (
                facts.superuser_reserved_connections
            ),
            "reserved_connections": facts.reserved_connections,
            "reserved_connections_applied": facts.reserved_connections_applied,
            "current_role_connection_access": facts.role_connection_access.value,
            "current_client_sessions_including_preflight_controller": (
                facts.current_client_sessions
            ),
            "preflight_controller_connections": (
                facts.preflight_controller_connections
            ),
            "other_client_sessions": facts.other_client_sessions,
            "usable_connection_ceiling": facts.usable_connection_ceiling,
            "available_worker_connections_before_headroom": (
                facts.available_worker_connections_before_headroom
            ),
        },
        "candidate_levels": list(result.selection.candidate_levels),
        "candidate_assessments": [
            {
                "candidate_level": item.candidate_level,
                "required_connections": item.required_connections,
                "available_worker_connections_before_headroom": (
                    item.available_worker_connections_before_headroom
                ),
                "raw_slots_remaining_before_headroom": (
                    item.raw_slots_remaining_before_headroom
                ),
                "feasible_before_headroom": item.feasible_before_headroom,
            }
            for item in result.assessments
        ],
        "proposed_levels_for_human_review": list(
            result.selection.proposed_levels_for_human_review
        ),
        "retained_levels": list(result.selection.retained_levels),
        "human_review_required": result.selection.human_review_required,
        "fewer_than_three_proposed_levels": (
            result.selection.fewer_than_three_proposed_levels
        ),
        "limitations": [
            "raw feasibility is calculated before human-selected safety headroom",
            "current session count is a point-in-time observation",
            "proposed levels are not retained levels or capacity claims",
            "no Level-C workload or timing executes in this preflight",
        ],
    }
    _reject_secret_shaped_payload(payload)
    return payload


def connection_budget_preflight_to_json(
    result: ConnectionBudgetPreflightResult,
) -> str:
    """Serialize one sanitized preflight with stable keys and a final newline."""

    return json.dumps(
        connection_budget_preflight_to_dict(result),
        indent=2,
        sort_keys=True,
    ) + "\n"


def run_postgres_connection_budget_preflight(
    database_url: str,
) -> ConnectionBudgetPreflightResult:
    """Inspect one guarded test server without writes, timing, or concurrency.

    The supplied URL is passed only to the existing connection constructor.  It
    is never retained, serialized, printed, or included in an exception.
    """

    if not isinstance(database_url, str) or not database_url:
        raise ConnectionBudgetSafetyError("test database configuration is absent")

    from src.storage.postgres_connection import connect_postgres

    connection = connect_postgres(database_url)
    try:
        _guard_test_database(connection)
        facts = _read_connection_budget_facts(connection)
        return build_connection_budget_preflight(facts)
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def run_postgres_connection_budget_preflight_from_environment(
) -> ConnectionBudgetPreflightResult:
    """Run the guarded preflight from inherited `TEST_DATABASE_URL` state."""

    import os

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise ConnectionBudgetSafetyError(
            "TEST_DATABASE_URL is not configured for the PR7 preflight"
        )
    return run_postgres_connection_budget_preflight(database_url)


def _guard_test_database(connection: Any) -> None:
    """Refuse inspection when the connected database lacks the `_test` suffix."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
    database_name = row[0] if row else None
    if not isinstance(database_name, str) or not database_name.endswith("_test"):
        raise ConnectionBudgetSafetyError(
            "connected database failed the required _test suffix guard"
        )


def _read_connection_budget_facts(connection: Any) -> ConnectionBudgetFacts:
    """Read only sanitized settings, role capability, and client occupancy."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                current_setting('server_version_num'),
                current_setting('max_connections')::integer,
                current_setting('superuser_reserved_connections')::integer,
                current_setting('reserved_connections', true),
                role_record.rolsuper,
                CASE
                    WHEN to_regrole('pg_use_reserved_connections') IS NULL
                        THEN FALSE
                    ELSE pg_has_role(
                        current_user,
                        to_regrole('pg_use_reserved_connections'),
                        'MEMBER'
                    )
                END,
                (
                    SELECT count(*)::integer
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                )
            FROM pg_roles AS role_record
            WHERE role_record.rolname = current_user
            """
        )
        row = cursor.fetchone()
    if row is None or len(row) != 7:
        raise InvalidConnectionBudgetError(
            "live server did not return one complete budget row"
        )
    reserved_connections = _optional_setting_int(
        row[3],
        "reserved_connections",
    )
    return ConnectionBudgetFacts(
        server_version_num=row[0],
        max_connections=row[1],
        superuser_reserved_connections=row[2],
        reserved_connections=reserved_connections,
        current_role_is_superuser=row[4],
        current_role_can_use_reserved_connections=row[5],
        current_client_sessions=row[6],
    )


def _optional_setting_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise InvalidConnectionBudgetError(
                f"{name} must be an integer when exposed"
            ) from exc
    else:
        raise InvalidConnectionBudgetError(
            f"{name} must be an integer when exposed"
        )
    _require_non_negative_int(parsed, name)
    return parsed


def _reject_secret_shaped_payload(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered_key = str(key).lower()
            if lowered_key in _FORBIDDEN_SERIALIZED_KEYS:
                raise InvalidConnectionBudgetError(
                    "preflight payload contains a forbidden metadata key"
                )
            _reject_secret_shaped_payload(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            _reject_secret_shaped_payload(nested)
        return
    if isinstance(value, str):
        lowered_value = value.lower()
        if any(
            fragment in lowered_value
            for fragment in _FORBIDDEN_SERIALIZED_VALUE_FRAGMENTS
        ):
            raise InvalidConnectionBudgetError(
                "preflight payload contains a secret-shaped metadata value"
            )


def _require_non_negative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise InvalidConnectionBudgetError(
            f"{name} must be a non-negative integer"
        )


def _require_positive_int(value: object, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise InvalidConnectionBudgetError(f"{name} must be a positive integer")


def main(argv: Sequence[str] | None = None) -> None:
    """Expose only the guarded read-only budget preflight."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Stage 4B.2 PR7 connection-budget preflight"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="inspect only sanitized PostgreSQL connection-budget facts",
    )
    args = parser.parse_args(argv)
    if not args.preflight:
        raise SystemExit(
            "PR7 Level-C execution is not implemented; pass --preflight only for "
            "the guarded read-only connection-budget inspection."
        )
    try:
        result = run_postgres_connection_budget_preflight_from_environment()
    except ConnectionBudgetPreflightError as exc:
        raise SystemExit(f"PR7 connection-budget preflight failed: {exc}") from None
    except Exception as exc:
        raise SystemExit(
            "PR7 connection-budget preflight failed: "
            f"{type(exc).__name__}"
        ) from None
    print(connection_budget_preflight_to_json(result), end="")


if __name__ == "__main__":
    main()
