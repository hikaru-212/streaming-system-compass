"""Parity tests for the deterministic Order contract YAML projection.

These tests validate source-derived projection data before rendering and bind
the committed YAML bytes to a fresh canonical V0 render. They do not parse YAML,
load a contract, execute validation, or make YAML a production authority.
"""

from pathlib import Path
from typing import cast

import pytest

from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    CorrectnessCategory,
)
from src.core.order.correctness_contract_yaml_projection import (
    ORDER_CORRECTNESS_CONTRACT_YAML_PROJECTION_VERSION,
    build_order_correctness_contract_yaml_projection,
    render_order_correctness_contract_yaml,
)
from src.core.order.enums import OrderStatus


_CATEGORY_NAMES = (
    CorrectnessCategory.COMMAND_LEGALITY.value,
    CorrectnessCategory.CANDIDATE_CONSTRUCTION.value,
    CorrectnessCategory.TRUSTED_APPLICATION.value,
    CorrectnessCategory.TRANSITION_TRUTH.value,
)
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_COMMITTED_YAML_PATH = (
    _REPOSITORY_ROOT
    / "docs"
    / "implementation_notes"
    / "stage_4b_5"
    / "order_correctness_contract_v0.yaml"
)


def _mapping(value: object) -> dict[str, object]:
    """Narrow one test assertion to a projected mapping."""

    assert type(value) is dict
    return cast(dict[str, object], value)


def _sequence(value: object) -> list[object]:
    """Narrow one test assertion to a projected sequence."""

    assert type(value) is list
    return cast(list[object], value)


def _projection_sections() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    """Return the exact nested sections used by focused parity assertions."""

    projection = build_order_correctness_contract_yaml_projection(
        ORDER_CORRECTNESS_CONTRACT_V0
    )
    contract = _mapping(projection["contract"])
    vocabulary = _mapping(contract["vocabulary"])
    parameters = _mapping(contract["parameters"])
    rules = _mapping(projection["rules"])
    relationships = _mapping(projection["relationships"])
    return (
        projection,
        contract,
        vocabulary,
        parameters,
        rules,
        relationships,
    )


def _flatten_projected_rules() -> dict[str, tuple[str, str, str]]:
    """Recover category from its group key and index rules by stable identity."""

    rules = _projection_sections()[4]
    flattened: dict[str, tuple[str, str, str]] = {}
    for category_name in _CATEGORY_NAMES:
        for value in _sequence(rules[category_name]):
            entry = _mapping(value)
            rule_id = cast(str, entry["rule_id"])
            assert rule_id not in flattened
            flattened[rule_id] = (
                cast(str, entry["semantic_proposition"]),
                category_name,
                cast(str, entry["subject"]),
            )
    return flattened


def test_projection_schema_and_key_sets_are_exact() -> None:
    projection, contract, vocabulary, parameters, rules, relationships = (
        _projection_sections()
    )

    assert tuple(projection) == (
        "projection_version",
        "contract",
        "rules",
        "relationships",
    )
    assert tuple(contract) == ("id", "version", "vocabulary", "parameters")
    assert tuple(vocabulary) == ("statuses", "commands", "event_types")
    assert tuple(parameters) == (
        "next_sequence_increment",
        "normalization_quantum",
        "rounding_mode",
    )
    assert tuple(rules) == _CATEGORY_NAMES
    assert tuple(relationships) == (
        "allowed_transitions",
        "amount_constraints",
    )
    for category_name in _CATEGORY_NAMES:
        for value in _sequence(rules[category_name]):
            assert tuple(_mapping(value)) == (
                "rule_id",
                "semantic_proposition",
                "subject",
            )
    for value in _sequence(relationships["allowed_transitions"]):
        assert tuple(_mapping(value)) == (
            "rule_id",
            "command",
            "predecessor_status",
            "candidate_event_type",
            "resulting_status",
        )
    for value in _sequence(relationships["amount_constraints"]):
        assert tuple(_mapping(value)) == (
            "rule_id",
            "command",
            "constraint",
        )


def test_projection_version_is_exporter_owned_and_equals_one() -> None:
    projection = _projection_sections()[0]

    assert ORDER_CORRECTNESS_CONTRACT_YAML_PROJECTION_VERSION == 1
    assert projection["projection_version"] == 1


def test_projected_contract_identity_matches_canonical_v0() -> None:
    contract = _projection_sections()[1]
    canonical = ORDER_CORRECTNESS_CONTRACT_V0

    assert contract["id"] == canonical.contract_id
    assert contract["version"] == canonical.contract_version


def test_projected_vocabularies_match_canonical_v0_exactly() -> None:
    vocabulary = _projection_sections()[2]
    canonical = ORDER_CORRECTNESS_CONTRACT_V0

    expected = {
        "statuses": [
            OrderStatus.INIT.value,
            OrderStatus.CREATED.value,
            OrderStatus.PAID.value,
        ],
        "commands": sorted(command.value for command in canonical.commands),
        "event_types": sorted(
            event_type.value for event_type in canonical.event_types
        ),
    }
    assert vocabulary == expected


def test_projected_parameters_match_canonical_v0_exactly() -> None:
    parameters = _projection_sections()[3]
    canonical = ORDER_CORRECTNESS_CONTRACT_V0

    assert parameters == {
        "next_sequence_increment": canonical.next_sequence_increment,
        "normalization_quantum": str(canonical.normalization_quantum),
        "rounding_mode": canonical.rounding_mode.value,
    }
    rendered = render_order_correctness_contract_yaml(canonical)
    assert (
        "normalization_quantum: "
        f'"{canonical.normalization_quantum}"'
    ) in rendered


def test_projected_rules_match_canonical_v0_exactly() -> None:
    projected = _flatten_projected_rules()
    canonical = ORDER_CORRECTNESS_CONTRACT_V0
    expected = {
        rule.rule_id.value: (
            rule.semantic_proposition,
            rule.category.value,
            rule.subject.value,
        )
        for rule in canonical.rules
    }

    assert len(projected) == len(canonical.rules) == 18
    assert frozenset(projected) == frozenset(expected)
    assert {
        rule_id: values[0] for rule_id, values in projected.items()
    } == {rule_id: values[0] for rule_id, values in expected.items()}
    assert {
        rule_id: values[1] for rule_id, values in projected.items()
    } == {rule_id: values[1] for rule_id, values in expected.items()}
    assert {
        rule_id: values[2] for rule_id, values in projected.items()
    } == {rule_id: values[2] for rule_id, values in expected.items()}
    assert projected == expected


def test_projected_transition_relationships_match_canonical_v0_exactly() -> None:
    relationships = _projection_sections()[5]
    projected = {
        cast(str, entry["rule_id"]): (
            entry["command"],
            entry["predecessor_status"],
            entry["candidate_event_type"],
            entry["resulting_status"],
        )
        for entry in (
            _mapping(value)
            for value in _sequence(relationships["allowed_transitions"])
        )
    }
    expected = {
        transition.legality_rule_id.value: (
            transition.command.value,
            transition.predecessor_status.value,
            transition.candidate_event_type.value,
            transition.resulting_status.value,
        )
        for transition in ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions
    }

    assert projected == expected


def test_projected_amount_relationships_match_canonical_v0_exactly() -> None:
    relationships = _projection_sections()[5]
    projected = {
        cast(str, entry["rule_id"]): (
            entry["command"],
            entry["constraint"],
        )
        for entry in (
            _mapping(value)
            for value in _sequence(relationships["amount_constraints"])
        )
    }
    expected = {
        constraint.rule_id.value: (
            constraint.command.value,
            constraint.constraint.value,
        )
        for constraint in ORDER_CORRECTNESS_CONTRACT_V0.amount_constraints
    }

    assert projected == expected


def test_projection_has_no_missing_or_additional_semantic_identities() -> None:
    rules = frozenset(_flatten_projected_rules())
    relationships = _projection_sections()[5]
    transition_ids = frozenset(
        cast(str, _mapping(value)["rule_id"])
        for value in _sequence(relationships["allowed_transitions"])
    )
    amount_ids = frozenset(
        cast(str, _mapping(value)["rule_id"])
        for value in _sequence(relationships["amount_constraints"])
    )
    canonical = ORDER_CORRECTNESS_CONTRACT_V0

    assert rules == frozenset(rule.rule_id.value for rule in canonical.rules)
    assert transition_ids == frozenset(
        transition.legality_rule_id.value
        for transition in canonical.allowed_transitions
    )
    assert amount_ids == frozenset(
        constraint.rule_id.value
        for constraint in canonical.amount_constraints
    )
    assert transition_ids | amount_ids <= rules


def test_projection_uses_explicit_deterministic_ordering() -> None:
    _, _, vocabulary, _, rules, relationships = _projection_sections()

    assert _sequence(vocabulary["statuses"]) == [
        OrderStatus.INIT.value,
        OrderStatus.CREATED.value,
        OrderStatus.PAID.value,
    ]
    for vocabulary_name in ("commands", "event_types"):
        sequence = _sequence(vocabulary[vocabulary_name])
        assert sequence == sorted(sequence)
    for category_name in _CATEGORY_NAMES:
        rule_ids = [
            _mapping(value)["rule_id"]
            for value in _sequence(rules[category_name])
        ]
        assert rule_ids == sorted(rule_ids)
    for relationship_name in (
        "allowed_transitions",
        "amount_constraints",
    ):
        rule_ids = [
            _mapping(value)["rule_id"]
            for value in _sequence(relationships[relationship_name])
        ]
        assert rule_ids == sorted(rule_ids)


def test_two_consecutive_renders_are_byte_identical() -> None:
    first = render_order_correctness_contract_yaml(
        ORDER_CORRECTNESS_CONTRACT_V0
    ).encode("utf-8")
    second = render_order_correctness_contract_yaml(
        ORDER_CORRECTNESS_CONTRACT_V0
    ).encode("utf-8")

    assert first == second


def test_render_uses_lf_only_and_exactly_one_terminal_newline() -> None:
    rendered = render_order_correctness_contract_yaml(
        ORDER_CORRECTNESS_CONTRACT_V0
    )

    assert "\r" not in rendered
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    assert rendered.encode("utf-8").decode("utf-8") == rendered


def test_render_double_quotes_representative_semantic_string_scalars() -> None:
    rendered = render_order_correctness_contract_yaml(
        ORDER_CORRECTNESS_CONTRACT_V0
    )

    assert 'id: "order.correctness"' in rendered
    assert '- "create"' in rendered
    assert 'rule_id: "order.command.create.allowed-from-init"' in rendered
    assert 'subject: "AGGREGATE_COMMAND"' in rendered
    assert 'constraint: "NORMALIZED_VALUE_GREATER_THAN_ZERO"' in rendered


def test_committed_yaml_bytes_equal_fresh_canonical_v0_render() -> None:
    expected = render_order_correctness_contract_yaml(
        ORDER_CORRECTNESS_CONTRACT_V0
    ).encode("utf-8")

    assert _COMMITTED_YAML_PATH.read_bytes() == expected


def test_projection_rejects_non_contract_input() -> None:
    with pytest.raises(TypeError, match="OrderCorrectnessContract"):
        build_order_correctness_contract_yaml_projection(  # type: ignore[arg-type]
            object()
        )

    with pytest.raises(TypeError, match="OrderCorrectnessContract"):
        render_order_correctness_contract_yaml(object())  # type: ignore[arg-type]
