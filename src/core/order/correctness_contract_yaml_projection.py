"""Deterministic YAML readability projection for Order correctness contracts.

The canonical Python :class:`OrderCorrectnessContract` remains the only
semantic authority. This module builds a detached, human-readable projection
from an admitted contract object and renders that projection with a deliberately
narrow YAML emitter. It does not define rules, load YAML, reconstruct contracts,
execute validation, select policy, persist data, or participate in runtime
request handling.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from enum import Enum
from typing import Iterable, cast

from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    CorrectnessCategory,
    OrderCorrectnessContract,
)
from src.core.order.enums import OrderStatus


ORDER_CORRECTNESS_CONTRACT_YAML_PROJECTION_VERSION = 1

_GENERATED_FILE_HEADER = (
    "# Generated readability projection.",
    "# Canonical Python Order Correctness Contract V0 is authoritative.",
    "# Do not edit manually or load as production runtime authority.",
)
_CATEGORY_ORDER = (
    CorrectnessCategory.COMMAND_LEGALITY,
    CorrectnessCategory.CANDIDATE_CONSTRUCTION,
    CorrectnessCategory.TRUSTED_APPLICATION,
    CorrectnessCategory.TRANSITION_TRUTH,
)
_STATUS_PRESENTATION_ORDER = (
    OrderStatus.INIT,
    OrderStatus.CREATED,
    OrderStatus.PAID,
)

__all__ = (
    "ORDER_CORRECTNESS_CONTRACT_YAML_PROJECTION_VERSION",
    "build_order_correctness_contract_yaml_projection",
    "render_order_correctness_contract_yaml",
)


def build_order_correctness_contract_yaml_projection(
    contract: OrderCorrectnessContract,
) -> dict[str, object]:
    """Build the exact source-derived structure owned by YAML projection v1.

    Args:
        contract: An admitted immutable Order correctness contract edition.

    Returns:
        A detached mapping with the exact projection v1 hierarchy. Every domain
        semantic value is read from ``contract``; only the projection-format
        version and structural key names are exporter-owned.

    Invariants:
        Categories use the explicit projection order, rules and relationships
        are sorted by stable rule identity, and frozenset vocabularies are
        sorted lexically by their enum string values. Decimal meaning is
        preserved as its exact string representation.

    Raises:
        TypeError: If ``contract`` or a projected scalar has an unsupported
            type.
        ValueError: If the supplied contract does not cover the closed category
            hierarchy owned by projection version 1.

    This function owns no transaction, concurrency, persistence, runtime
    loading, validation execution, policy, retry, or mutation behavior.
    """

    if not isinstance(contract, OrderCorrectnessContract):
        raise TypeError("contract must be OrderCorrectnessContract")

    category_names = tuple(
        _enum_string(category, "projection category")
        for category in _CATEGORY_ORDER
    )
    contract_category_names = frozenset(
        _enum_string(rule.category, "contract.rules.category")
        for rule in contract.rules
    )
    if contract_category_names != frozenset(category_names):
        raise ValueError(
            "contract rules must exactly cover YAML projection v1 categories"
        )

    projected_rules: dict[str, object] = {}
    for category, category_name in zip(
        _CATEGORY_ORDER,
        category_names,
        strict=True,
    ):
        rules = sorted(
            (rule for rule in contract.rules if rule.category is category),
            key=lambda rule: _enum_string(
                rule.rule_id,
                "contract.rules.rule_id",
            ),
        )
        projected_rules[category_name] = [
            {
                "rule_id": _enum_string(
                    rule.rule_id,
                    "contract.rules.rule_id",
                ),
                "semantic_proposition": _string(
                    rule.semantic_proposition,
                    "contract.rules.semantic_proposition",
                ),
                "subject": _enum_string(
                    rule.subject,
                    "contract.rules.subject",
                ),
            }
            for rule in rules
        ]

    projected_transitions = [
        {
            "rule_id": _enum_string(
                transition.legality_rule_id,
                "contract.allowed_transitions.legality_rule_id",
            ),
            "command": _enum_string(
                transition.command,
                "contract.allowed_transitions.command",
            ),
            "predecessor_status": _enum_string(
                transition.predecessor_status,
                "contract.allowed_transitions.predecessor_status",
            ),
            "candidate_event_type": _enum_string(
                transition.candidate_event_type,
                "contract.allowed_transitions.candidate_event_type",
            ),
            "resulting_status": _enum_string(
                transition.resulting_status,
                "contract.allowed_transitions.resulting_status",
            ),
        }
        for transition in sorted(
            contract.allowed_transitions,
            key=lambda transition: _enum_string(
                transition.legality_rule_id,
                "contract.allowed_transitions.legality_rule_id",
            ),
        )
    ]
    projected_amount_constraints = [
        {
            "rule_id": _enum_string(
                constraint.rule_id,
                "contract.amount_constraints.rule_id",
            ),
            "command": _enum_string(
                constraint.command,
                "contract.amount_constraints.command",
            ),
            "constraint": _enum_string(
                constraint.constraint,
                "contract.amount_constraints.constraint",
            ),
        }
        for constraint in sorted(
            contract.amount_constraints,
            key=lambda constraint: _enum_string(
                constraint.rule_id,
                "contract.amount_constraints.rule_id",
            ),
        )
    ]

    return {
        "projection_version": (
            ORDER_CORRECTNESS_CONTRACT_YAML_PROJECTION_VERSION
        ),
        "contract": {
            "id": _string(contract.contract_id, "contract.contract_id"),
            "version": _integer(
                contract.contract_version,
                "contract.contract_version",
            ),
            "vocabulary": {
                "statuses": _ordered_status_values(
                    contract.statuses,
                    "contract.statuses",
                ),
                "commands": _sorted_enum_values(
                    contract.commands,
                    "contract.commands",
                ),
                "event_types": _sorted_enum_values(
                    contract.event_types,
                    "contract.event_types",
                ),
            },
            "parameters": {
                "next_sequence_increment": _integer(
                    contract.next_sequence_increment,
                    "contract.next_sequence_increment",
                ),
                "normalization_quantum": _decimal_string(
                    contract.normalization_quantum,
                    "contract.normalization_quantum",
                ),
                "rounding_mode": _enum_string(
                    contract.rounding_mode,
                    "contract.rounding_mode",
                ),
            },
        },
        "rules": projected_rules,
        "relationships": {
            "allowed_transitions": projected_transitions,
            "amount_constraints": projected_amount_constraints,
        },
    }


def render_order_correctness_contract_yaml(
    contract: OrderCorrectnessContract,
) -> str:
    """Render one admitted contract as deterministic projection-v1 YAML text.

    Args:
        contract: The immutable canonical Python contract object to project.

    Returns:
        UTF-8-compatible text containing only LF line separators and exactly one
        terminal newline. String scalars are consistently double-quoted.

    Invariants:
        Rendering consumes only the exact structure produced by
        :func:`build_order_correctness_contract_yaml_projection`. It emits no
        timestamp, commit identity, filesystem path, environment field, YAML
        tag, anchor, alias, loader instruction, or runtime authority claim.

    Raises:
        TypeError: If the contract or a projected scalar/collection has an
            unsupported type.
        ValueError: If the projection hierarchy or key ordering differs from
            the exact version 1 schema.

    The renderer returns text only. It does not choose a destination, write a
    file, parse YAML, reconstruct a contract, execute rules, or own runtime,
    persistence, transaction, concurrency, policy, or retry behavior.
    """

    projection = build_order_correctness_contract_yaml_projection(contract)
    return _render_projection_v1(projection)


def _render_projection_v1(projection: dict[str, object]) -> str:
    """Render the exact projection-v1 hierarchy with fixed indentation."""

    root = _mapping(
        projection,
        (
            "projection_version",
            "contract",
            "rules",
            "relationships",
        ),
        "projection",
    )
    contract = _mapping(
        root["contract"],
        ("id", "version", "vocabulary", "parameters"),
        "projection.contract",
    )
    vocabulary = _mapping(
        contract["vocabulary"],
        ("statuses", "commands", "event_types"),
        "projection.contract.vocabulary",
    )
    parameters = _mapping(
        contract["parameters"],
        (
            "next_sequence_increment",
            "normalization_quantum",
            "rounding_mode",
        ),
        "projection.contract.parameters",
    )
    category_names = tuple(
        _enum_string(category, "projection category")
        for category in _CATEGORY_ORDER
    )
    rules = _mapping(root["rules"], category_names, "projection.rules")
    relationships = _mapping(
        root["relationships"],
        ("allowed_transitions", "amount_constraints"),
        "projection.relationships",
    )

    lines = [*_GENERATED_FILE_HEADER]
    lines.append(
        "projection_version: "
        + _yaml_integer(
            root["projection_version"],
            "projection.projection_version",
        )
    )
    lines.extend(
        (
            "",
            "contract:",
            "  id: " + _yaml_string(contract["id"], "projection.contract.id"),
            "  version: "
            + _yaml_integer(
                contract["version"],
                "projection.contract.version",
            ),
            "  vocabulary:",
        )
    )
    _append_string_sequence(
        lines,
        "statuses",
        vocabulary["statuses"],
        indent=4,
        field_name="projection.contract.vocabulary.statuses",
    )
    _append_string_sequence(
        lines,
        "commands",
        vocabulary["commands"],
        indent=4,
        field_name="projection.contract.vocabulary.commands",
    )
    _append_string_sequence(
        lines,
        "event_types",
        vocabulary["event_types"],
        indent=4,
        field_name="projection.contract.vocabulary.event_types",
    )
    lines.extend(
        (
            "  parameters:",
            "    next_sequence_increment: "
            + _yaml_integer(
                parameters["next_sequence_increment"],
                "projection.contract.parameters.next_sequence_increment",
            ),
            "    normalization_quantum: "
            + _yaml_string(
                parameters["normalization_quantum"],
                "projection.contract.parameters.normalization_quantum",
            ),
            "    rounding_mode: "
            + _yaml_string(
                parameters["rounding_mode"],
                "projection.contract.parameters.rounding_mode",
            ),
            "",
            "rules:",
        )
    )
    for category_name in category_names:
        lines.append(f"  {category_name}:")
        entries = _sequence(
            rules[category_name],
            f"projection.rules.{category_name}",
        )
        if not entries:
            raise ValueError(
                f"projection.rules.{category_name} must not be empty"
            )
        for index, value in enumerate(entries):
            entry = _mapping(
                value,
                ("rule_id", "semantic_proposition", "subject"),
                f"projection.rules.{category_name}[{index}]",
            )
            lines.extend(
                (
                    "    - rule_id: "
                    + _yaml_string(
                        entry["rule_id"],
                        f"projection.rules.{category_name}[{index}].rule_id",
                    ),
                    "      semantic_proposition: "
                    + _yaml_string(
                        entry["semantic_proposition"],
                        "projection.rules."
                        f"{category_name}[{index}].semantic_proposition",
                    ),
                    "      subject: "
                    + _yaml_string(
                        entry["subject"],
                        f"projection.rules.{category_name}[{index}].subject",
                    ),
                )
            )

    lines.extend(("", "relationships:"))
    transitions = _sequence(
        relationships["allowed_transitions"],
        "projection.relationships.allowed_transitions",
    )
    lines.append(
        "  allowed_transitions:"
        if transitions
        else "  allowed_transitions: []"
    )
    for index, value in enumerate(transitions):
        entry = _mapping(
            value,
            (
                "rule_id",
                "command",
                "predecessor_status",
                "candidate_event_type",
                "resulting_status",
            ),
            f"projection.relationships.allowed_transitions[{index}]",
        )
        lines.extend(
            (
                "    - rule_id: "
                + _yaml_string(
                    entry["rule_id"],
                    "projection.relationships."
                    f"allowed_transitions[{index}].rule_id",
                ),
                "      command: "
                + _yaml_string(
                    entry["command"],
                    "projection.relationships."
                    f"allowed_transitions[{index}].command",
                ),
                "      predecessor_status: "
                + _yaml_string(
                    entry["predecessor_status"],
                    "projection.relationships."
                    f"allowed_transitions[{index}].predecessor_status",
                ),
                "      candidate_event_type: "
                + _yaml_string(
                    entry["candidate_event_type"],
                    "projection.relationships."
                    f"allowed_transitions[{index}].candidate_event_type",
                ),
                "      resulting_status: "
                + _yaml_string(
                    entry["resulting_status"],
                    "projection.relationships."
                    f"allowed_transitions[{index}].resulting_status",
                ),
            )
        )

    amount_constraints = _sequence(
        relationships["amount_constraints"],
        "projection.relationships.amount_constraints",
    )
    lines.append(
        "  amount_constraints:"
        if amount_constraints
        else "  amount_constraints: []"
    )
    for index, value in enumerate(amount_constraints):
        entry = _mapping(
            value,
            ("rule_id", "command", "constraint"),
            f"projection.relationships.amount_constraints[{index}]",
        )
        lines.extend(
            (
                "    - rule_id: "
                + _yaml_string(
                    entry["rule_id"],
                    "projection.relationships."
                    f"amount_constraints[{index}].rule_id",
                ),
                "      command: "
                + _yaml_string(
                    entry["command"],
                    "projection.relationships."
                    f"amount_constraints[{index}].command",
                ),
                "      constraint: "
                + _yaml_string(
                    entry["constraint"],
                    "projection.relationships."
                    f"amount_constraints[{index}].constraint",
                ),
            )
        )

    return "\n".join(lines) + "\n"


def _append_string_sequence(
    lines: list[str],
    key: str,
    value: object,
    *,
    indent: int,
    field_name: str,
) -> None:
    """Append one owned block-style sequence of quoted string values."""

    prefix = " " * indent
    entries = _sequence(value, field_name)
    if not entries:
        lines.append(f"{prefix}{key}: []")
        return
    lines.append(f"{prefix}{key}:")
    for index, entry in enumerate(entries):
        lines.append(
            f"{prefix}  - "
            + _yaml_string(entry, f"{field_name}[{index}]")
        )


def _mapping(
    value: object,
    expected_keys: tuple[str, ...],
    field_name: str,
) -> dict[str, object]:
    """Require one exact ordered mapping owned by projection version 1."""

    if type(value) is not dict:
        raise TypeError(f"{field_name} must be dict")
    mapping = cast(dict[str, object], value)
    if tuple(mapping) != expected_keys:
        raise ValueError(
            f"{field_name} keys must be exactly {expected_keys!r} in order"
        )
    return mapping


def _sequence(value: object, field_name: str) -> list[object]:
    """Require one block-style sequence owned by projection version 1."""

    if type(value) is not list:
        raise TypeError(f"{field_name} must be list")
    return cast(list[object], value)


def _string(value: object, field_name: str) -> str:
    """Require a string scalar without applying semantic coercion."""

    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    return value


def _integer(value: object, field_name: str) -> int:
    """Require an integer scalar while keeping booleans distinct."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be int")
    return value


def _decimal_string(value: object, field_name: str) -> str:
    """Preserve the exact finite Decimal representation as a string scalar."""

    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be Decimal")
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return str(value)


def _enum_string(value: object, field_name: str) -> str:
    """Project a typed enum only when its canonical value is a string."""

    if not isinstance(value, Enum):
        raise TypeError(f"{field_name} must be Enum")
    return _string(value.value, f"{field_name}.value")


def _sorted_enum_values(
    values: Iterable[Enum],
    field_name: str,
) -> list[str]:
    """Return explicitly lexical enum values for unordered vocabularies."""

    return sorted(
        _enum_string(value, f"{field_name} member") for value in values
    )


def _ordered_status_values(
    values: Iterable[OrderStatus],
    field_name: str,
) -> list[str]:
    """Return statuses in lifecycle order after exact vocabulary validation."""

    supplied = frozenset(values)
    expected = frozenset(_STATUS_PRESENTATION_ORDER)
    if supplied != expected:
        raise ValueError(
            f"{field_name} must exactly match projection v1 status vocabulary"
        )
    return [
        _enum_string(status, f"{field_name} member")
        for status in _STATUS_PRESENTATION_ORDER
    ]


def _yaml_string(value: object, field_name: str) -> str:
    """Render one supported YAML double-quoted string scalar."""

    return json.dumps(
        _string(value, field_name),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _yaml_integer(value: object, field_name: str) -> str:
    """Render one supported YAML integer scalar."""

    return str(_integer(value, field_name))


def _main() -> None:
    """Print canonical V0 without selecting or writing a destination path."""

    sys.stdout.write(
        render_order_correctness_contract_yaml(ORDER_CORRECTNESS_CONTRACT_V0)
    )


if __name__ == "__main__":
    _main()
