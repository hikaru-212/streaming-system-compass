from dataclasses import FrozenInstanceError
from decimal import Decimal
from types import MappingProxyType

import pytest

import src.core.order.correctness_contract as correctness_contract_module
from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    AllowedTransition,
    AmountConstraintKind,
    CommandAmountConstraint,
    CorrectnessCategory,
    CorrectnessRule,
    MoneyRoundingMode,
    OrderCorrectnessContract,
    OrderCorrectnessRuleId,
    RuleSubject,
)
from src.core.order.enums import CommandType, EventType, OrderStatus


EXPECTED_RULE_ID_VALUES = frozenset(
    (
        "order.command.create.allowed-from-init",
        "order.command.pay.allowed-from-created",
        "order.command.create.normalized-amount-positive",
        "order.command.pay.normalized-amount-positive",
        "order.command.pay.normalized-amount-equals-total",
        "order.candidate.sequence-is-next-aggregate-version",
        "order.candidate.proof-derived-from-aggregate-predecessor",
        "order.trusted-application.event-order-id-matches-aggregate",
        "order.trusted-application.event-sequence-is-next-version",
        "order.trusted-application.created-establishes-state",
        "order.trusted-application.paid-establishes-state",
        "order.trusted-application.updates-aggregate-history-head",
        "order.transition.sequence-matches-accepted-next-version",
        "order.transition.proof-prev-event-id-matches-accepted",
        "order.transition.proof-prev-version-matches-accepted",
        "order.transition.proof-prev-status-matches-accepted",
        "order.transition.candidate-event-type-supported",
        "order.transition.event-type-legal-from-accepted-status",
    )
)


EXPECTED_RULE_ASSOCIATIONS = frozenset(
    (
        (
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION,
            CorrectnessCategory.CANDIDATE_CONSTRUCTION,
            RuleSubject.CANDIDATE_EVENT,
        ),
        (
            OrderCorrectnessRuleId.CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR,
            CorrectnessCategory.CANDIDATE_CONSTRUCTION,
            RuleSubject.PREDECESSOR_CLAIM,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_ORDER_ID_MATCHES_AGGREGATE,
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_SEQUENCE_IS_NEXT_VERSION,
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_CREATED_ESTABLISHES_STATE,
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_PAID_ESTABLISHES_STATE,
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD,
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.CANDIDATE_EVENT,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS,
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
    )
)


def test_canonical_contract_identity_and_version_are_frozen() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    assert contract.contract_id == "order.correctness"
    assert contract.contract_version == 0


def test_correctness_category_vocabulary_is_exact() -> None:
    assert frozenset(category.value for category in CorrectnessCategory) == frozenset(
        (
            "COMMAND_LEGALITY",
            "CANDIDATE_CONSTRUCTION",
            "TRUSTED_APPLICATION",
            "TRANSITION_TRUTH",
        )
    )


def test_rule_subject_vocabulary_is_exact() -> None:
    assert frozenset(subject.value for subject in RuleSubject) == frozenset(
        (
            "AGGREGATE_COMMAND",
            "CANDIDATE_EVENT",
            "PREDECESSOR_CLAIM",
            "TRUSTED_EVENT_APPLICATION",
            "ACCEPTED_CONTEXT_COMPARISON",
        )
    )


def test_money_rounding_mode_vocabulary_is_exact() -> None:
    assert tuple(mode.value for mode in MoneyRoundingMode) == ("ROUND_HALF_EVEN",)


def test_amount_constraint_kind_vocabulary_is_exact() -> None:
    assert frozenset(
        constraint.value for constraint in AmountConstraintKind
    ) == frozenset(
        (
            "NORMALIZED_VALUE_GREATER_THAN_ZERO",
            "NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT",
        )
    )


def test_known_rule_id_vocabulary_is_exactly_the_approved_eighteen() -> None:
    known_values = frozenset(rule_id.value for rule_id in OrderCorrectnessRuleId)

    assert len(OrderCorrectnessRuleId) == 18
    assert known_values == EXPECTED_RULE_ID_VALUES
    assert "order.candidate.event-id-does-not-imply-acceptance" not in known_values


def test_authoritative_rule_registry_is_immutable_and_exactly_complete() -> None:
    definitions = correctness_contract_module._RULE_DEFINITIONS

    assert isinstance(definitions, MappingProxyType)
    assert len(definitions) == len(OrderCorrectnessRuleId)
    assert frozenset(definitions) == frozenset(OrderCorrectnessRuleId)

    with pytest.raises(TypeError):
        definitions[OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT] = definitions[
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED
        ]  # type: ignore[index]


def test_no_authoritative_definition_exists_for_unknown_rule_id() -> None:
    definitions = correctness_contract_module._RULE_DEFINITIONS

    with pytest.raises(KeyError):
        definitions["order.unknown"]  # type: ignore[index]

    with pytest.raises(TypeError, match="OrderCorrectnessRuleId"):
        CorrectnessRule.from_rule_id("order.unknown")  # type: ignore[arg-type]


def test_correctness_rule_public_construction_is_rule_id_driven() -> None:
    rule_id = OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT

    rule = CorrectnessRule.from_rule_id(rule_id)

    assert rule.rule_id is rule_id
    assert rule.semantic_proposition == (
        "A CREATE command is legal only when the aggregate status is INIT."
    )
    assert rule.category is CorrectnessCategory.COMMAND_LEGALITY
    assert rule.subject is RuleSubject.AGGREGATE_COMMAND


@pytest.mark.parametrize(
    ("rule_id", "proposition", "category", "subject"),
    (
        (
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
            "A CREATE command is legal only when the aggregate status is INIT.",
            CorrectnessCategory.COMMAND_LEGALITY,
            RuleSubject.AGGREGATE_COMMAND,
        ),
        (
            OrderCorrectnessRuleId.CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR,
            (
                "A candidate proof's prev_status, prev_version, and prev_event_id "
                "are derived from the aggregate's current status, "
                "current_version, and last_event_id."
            ),
            CorrectnessCategory.CANDIDATE_CONSTRUCTION,
            RuleSubject.PREDECESSOR_CLAIM,
        ),
        (
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD,
            (
                "Applying a trusted event updates the aggregate's local history "
                "head by setting current_version to event.sequence and "
                "last_event_id to event.event_id."
            ),
            CorrectnessCategory.TRUSTED_APPLICATION,
            RuleSubject.TRUSTED_EVENT_APPLICATION,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED,
            (
                "A candidate proof's prev_status equals the accepted context's "
                "previous status."
            ),
            CorrectnessCategory.TRANSITION_TRUTH,
            RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
        ),
    ),
)
def test_rule_id_uniquely_determines_semantic_metadata(
    rule_id: OrderCorrectnessRuleId,
    proposition: str,
    category: CorrectnessCategory,
    subject: RuleSubject,
) -> None:
    first = CorrectnessRule.from_rule_id(rule_id)
    second = CorrectnessRule.from_rule_id(rule_id)

    assert first == second
    assert (
        first.semantic_proposition,
        first.category,
        first.subject,
    ) == (proposition, category, subject)


def test_arbitrary_four_field_rule_construction_is_not_supported() -> None:
    with pytest.raises(TypeError, match="from_rule_id"):
        CorrectnessRule(
            rule_id=OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
            semantic_proposition="unrelated meaning",
            category=CorrectnessCategory.TRANSITION_TRUTH,
            subject=RuleSubject.PREDECESSOR_CLAIM,
        )


def test_canonical_contract_uses_each_approved_rule_id_once() -> None:
    rule_ids = tuple(rule.rule_id for rule in ORDER_CORRECTNESS_CONTRACT_V0.rules)

    assert len(rule_ids) == 18
    assert len(frozenset(rule_ids)) == 18
    assert frozenset(rule_id.value for rule_id in rule_ids) == EXPECTED_RULE_ID_VALUES


def test_canonical_rule_category_and_subject_associations_are_exact() -> None:
    actual = frozenset(
        (rule.rule_id, rule.category, rule.subject)
        for rule in ORDER_CORRECTNESS_CONTRACT_V0.rules
    )

    assert actual == EXPECTED_RULE_ASSOCIATIONS


def test_canonical_rules_materialize_authoritative_definitions() -> None:
    definitions = correctness_contract_module._RULE_DEFINITIONS

    for rule in ORDER_CORRECTNESS_CONTRACT_V0.rules:
        definition = definitions[rule.rule_id]
        assert (
            rule.semantic_proposition,
            rule.category,
            rule.subject,
        ) == (
            definition.semantic_proposition,
            definition.category,
            definition.subject,
        )


@pytest.mark.parametrize(
    ("record", "field_name", "new_value"),
    (
        (ORDER_CORRECTNESS_CONTRACT_V0, "contract_version", 1),
        (
            ORDER_CORRECTNESS_CONTRACT_V0.rules[0],
            "semantic_proposition",
            "changed",
        ),
        (
            ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions[0],
            "resulting_status",
            OrderStatus.PAID,
        ),
        (
            ORDER_CORRECTNESS_CONTRACT_V0.amount_constraints[0],
            "command",
            CommandType.PAY,
        ),
    ),
)
def test_public_dataclass_records_are_frozen(
    record: object,
    field_name: str,
    new_value: object,
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(record, field_name, new_value)


def test_contract_uses_only_tuple_and_frozenset_collections() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    assert type(contract.statuses) is frozenset
    assert type(contract.commands) is frozenset
    assert type(contract.event_types) is frozenset
    assert type(contract.rules) is tuple
    assert type(contract.allowed_transitions) is tuple
    assert type(contract.amount_constraints) is tuple

    with pytest.raises(AttributeError):
        contract.statuses.add(OrderStatus.INIT)  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        contract.rules.append(contract.rules[0])  # type: ignore[attr-defined]


def test_canonical_order_vocabularies_are_exact() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    assert contract.statuses == frozenset(
        (OrderStatus.INIT, OrderStatus.CREATED, OrderStatus.PAID)
    )
    assert contract.commands == frozenset((CommandType.CREATE, CommandType.PAY))
    assert contract.event_types == frozenset((EventType.CREATED, EventType.PAID))


def test_canonical_allowed_transition_graph_is_exact() -> None:
    assert ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions == (
        AllowedTransition.from_rule_id(
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT
        ),
        AllowedTransition.from_rule_id(
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED
        ),
    )


def test_forbidden_command_status_pairs_are_derived_from_closed_graph() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0
    all_pairs = frozenset(
        (status, command)
        for status in contract.statuses
        for command in contract.commands
    )
    allowed_pairs = frozenset(
        (transition.predecessor_status, transition.command)
        for transition in contract.allowed_transitions
    )

    assert all_pairs - allowed_pairs == frozenset(
        (
            (OrderStatus.INIT, CommandType.PAY),
            (OrderStatus.CREATED, CommandType.CREATE),
            (OrderStatus.PAID, CommandType.CREATE),
            (OrderStatus.PAID, CommandType.PAY),
        )
    )


def test_canonical_amount_constraints_are_exact() -> None:
    assert ORDER_CORRECTNESS_CONTRACT_V0.amount_constraints == (
        CommandAmountConstraint.from_rule_id(
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE
        ),
        CommandAmountConstraint.from_rule_id(
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE
        ),
        CommandAmountConstraint.from_rule_id(
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL
        ),
    )


def test_canonical_money_and_sequence_declarations_are_exact() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    assert contract.normalization_quantum == Decimal("0.01")
    assert contract.rounding_mode is MoneyRoundingMode.ROUND_HALF_EVEN
    assert contract.next_sequence_increment == 1


def test_all_canonical_rule_references_resolve() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0
    rule_ids = frozenset(rule.rule_id for rule in contract.rules)

    assert all(
        transition.legality_rule_id in rule_ids
        for transition in contract.allowed_transitions
    )
    assert all(
        constraint.rule_id in rule_ids
        for constraint in contract.amount_constraints
    )


def test_authoritative_rule_definitions_are_typed_and_trimmed() -> None:
    for definition in correctness_contract_module._RULE_DEFINITIONS.values():
        assert definition.semantic_proposition
        assert (
            definition.semantic_proposition
            == definition.semantic_proposition.strip()
        )
        assert isinstance(definition.category, CorrectnessCategory)
        assert isinstance(definition.subject, RuleSubject)


def test_authoritative_transition_registry_is_immutable_and_exact() -> None:
    definitions = correctness_contract_module._ALLOWED_TRANSITION_DEFINITIONS
    expected_ids = frozenset(
        (
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
        )
    )

    assert isinstance(definitions, MappingProxyType)
    assert frozenset(definitions) == expected_ids

    with pytest.raises(TypeError):
        definitions[OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT] = definitions[
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED
        ]  # type: ignore[index]


@pytest.mark.parametrize(
    ("rule_id", "relationship"),
    (
        (
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
            (
                CommandType.CREATE,
                OrderStatus.INIT,
                EventType.CREATED,
                OrderStatus.CREATED,
            ),
        ),
        (
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
            (
                CommandType.PAY,
                OrderStatus.CREATED,
                EventType.PAID,
                OrderStatus.PAID,
            ),
        ),
    ),
)
def test_transition_rule_id_uniquely_determines_complete_relationship(
    rule_id: OrderCorrectnessRuleId,
    relationship: tuple[CommandType, OrderStatus, EventType, OrderStatus],
) -> None:
    first = AllowedTransition.from_rule_id(rule_id)
    second = AllowedTransition.from_rule_id(rule_id)

    assert first == second
    assert first.legality_rule_id is rule_id
    assert (
        first.command,
        first.predecessor_status,
        first.candidate_event_type,
        first.resulting_status,
    ) == relationship


def test_arbitrary_transition_construction_is_not_supported() -> None:
    with pytest.raises(TypeError, match="from_rule_id"):
        AllowedTransition(
            legality_rule_id=OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
            command=CommandType.CREATE,
            predecessor_status=OrderStatus.INIT,
            candidate_event_type=EventType.CREATED,
            resulting_status=OrderStatus.CREATED,
        )


def test_non_transition_rule_cannot_materialize_allowed_transition() -> None:
    with pytest.raises(ValueError, match="allowed-transition definition"):
        AllowedTransition.from_rule_id(
            OrderCorrectnessRuleId.CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION
        )

    with pytest.raises(TypeError, match="OrderCorrectnessRuleId"):
        AllowedTransition.from_rule_id("order.unknown")  # type: ignore[arg-type]


def test_authoritative_amount_registry_is_immutable_and_exact() -> None:
    definitions = (
        correctness_contract_module._COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS
    )
    expected_ids = frozenset(
        (
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
        )
    )

    assert isinstance(definitions, MappingProxyType)
    assert frozenset(definitions) == expected_ids

    with pytest.raises(TypeError):
        definitions[
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE
        ] = definitions[
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE
        ]  # type: ignore[index]


@pytest.mark.parametrize(
    ("rule_id", "command", "constraint"),
    (
        (
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
            CommandType.CREATE,
            AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO,
        ),
        (
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
            CommandType.PAY,
            AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO,
        ),
        (
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
            CommandType.PAY,
            AmountConstraintKind.NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT,
        ),
    ),
)
def test_amount_rule_id_uniquely_determines_command_and_constraint(
    rule_id: OrderCorrectnessRuleId,
    command: CommandType,
    constraint: AmountConstraintKind,
) -> None:
    first = CommandAmountConstraint.from_rule_id(rule_id)
    second = CommandAmountConstraint.from_rule_id(rule_id)

    assert first == second
    assert first.rule_id is rule_id
    assert first.command is command
    assert first.constraint is constraint


def test_arbitrary_amount_constraint_construction_is_not_supported() -> None:
    with pytest.raises(TypeError, match="from_rule_id"):
        CommandAmountConstraint(
            rule_id=OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
            command=CommandType.CREATE,
            constraint=AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO,
        )


def test_non_amount_rule_cannot_materialize_amount_constraint() -> None:
    with pytest.raises(ValueError, match="command-amount definition"):
        CommandAmountConstraint.from_rule_id(
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT
        )

    with pytest.raises(TypeError, match="OrderCorrectnessRuleId"):
        CommandAmountConstraint.from_rule_id(  # type: ignore[arg-type]
            "order.unknown"
        )


def test_authoritative_contract_edition_registry_is_immutable_and_exact() -> None:
    definitions = (
        correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS
    )

    assert isinstance(definitions, MappingProxyType)
    assert tuple(definitions) == (("order.correctness", 0),)

    with pytest.raises(TypeError):
        definitions[("order.correctness", 1)] = definitions[
            ("order.correctness", 0)
        ]  # type: ignore[index]


def test_v0_identity_has_exactly_one_authoritative_definition() -> None:
    definitions = (
        correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS
    )
    definition = definitions[("order.correctness", 0)]

    assert len(definitions) == 1
    assert definition.statuses == frozenset(OrderStatus)
    assert definition.commands == frozenset(CommandType)
    assert definition.event_types == frozenset(EventType)
    assert definition.next_sequence_increment == 1
    assert definition.normalization_quantum == Decimal("0.01")
    assert definition.rounding_mode is MoneyRoundingMode.ROUND_HALF_EVEN
    assert len(definition.rule_ids) == 18
    assert len(definition.transition_rule_ids) == 2
    assert len(definition.amount_rule_ids) == 3


def test_contract_public_construction_is_edition_identity_driven() -> None:
    first = OrderCorrectnessContract.from_identity("order.correctness", 0)
    second = OrderCorrectnessContract.from_identity(
        contract_id="order.correctness",
        contract_version=0,
    )

    assert first == ORDER_CORRECTNESS_CONTRACT_V0
    assert second == ORDER_CORRECTNESS_CONTRACT_V0
    assert first is not ORDER_CORRECTNESS_CONTRACT_V0


def test_direct_contract_construction_cannot_forge_v0_quantum() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    with pytest.raises(TypeError, match="from_identity"):
        OrderCorrectnessContract(
            contract_id="order.correctness",
            contract_version=0,
            statuses=contract.statuses,
            commands=contract.commands,
            event_types=contract.event_types,
            next_sequence_increment=contract.next_sequence_increment,
            normalization_quantum=Decimal("0.05"),
            rounding_mode=contract.rounding_mode,
            rules=contract.rules,
            allowed_transitions=contract.allowed_transitions,
            amount_constraints=contract.amount_constraints,
        )


def test_direct_contract_construction_cannot_forge_v0_rule_subset() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    with pytest.raises(TypeError, match="from_identity"):
        OrderCorrectnessContract(
            contract_id="order.correctness",
            contract_version=0,
            statuses=contract.statuses,
            commands=contract.commands,
            event_types=contract.event_types,
            next_sequence_increment=contract.next_sequence_increment,
            normalization_quantum=contract.normalization_quantum,
            rounding_mode=contract.rounding_mode,
            rules=contract.rules[:-1],
            allowed_transitions=contract.allowed_transitions,
            amount_constraints=contract.amount_constraints,
        )


@pytest.mark.parametrize(
    ("contract_id", "contract_version", "expected_error"),
    (
        ("order.correctness", 1, ValueError),
        ("order.unknown", 0, ValueError),
        ("", 0, ValueError),
        ("order.correctness", -1, ValueError),
        ("order.correctness", True, TypeError),
    ),
)
def test_unknown_or_invalid_contract_identity_is_rejected(
    contract_id: str,
    contract_version: object,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        OrderCorrectnessContract.from_identity(
            contract_id,
            contract_version,  # type: ignore[arg-type]
        )


def test_v0_materializes_exact_reviewed_selection_counts() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0

    assert len(contract.rules) == 18
    assert len(contract.allowed_transitions) == 2
    assert len(contract.amount_constraints) == 3


def test_authoritative_definition_records_are_frozen() -> None:
    records_and_fields = (
        (
            next(iter(correctness_contract_module._RULE_DEFINITIONS.values())),
            "semantic_proposition",
            "changed",
        ),
        (
            next(
                iter(
                    correctness_contract_module._ALLOWED_TRANSITION_DEFINITIONS.values()
                )
            ),
            "command",
            CommandType.PAY,
        ),
        (
            next(
                iter(
                    correctness_contract_module._COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS.values()
                )
            ),
            "command",
            CommandType.PAY,
        ),
        (
            next(
                iter(
                    correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS.values()
                )
            ),
            "normalization_quantum",
            Decimal("0.05"),
        ),
    )

    for record, field_name, new_value in records_and_fields:
        with pytest.raises(FrozenInstanceError):
            setattr(record, field_name, new_value)


def test_specialized_registry_rules_have_required_metadata() -> None:
    rule_definitions = correctness_contract_module._RULE_DEFINITIONS
    specialized_rule_ids = frozenset(
        correctness_contract_module._ALLOWED_TRANSITION_DEFINITIONS
    ) | frozenset(
        correctness_contract_module._COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS
    )

    assert specialized_rule_ids.issubset(rule_definitions)
    for rule_id in specialized_rule_ids:
        definition = rule_definitions[rule_id]
        assert definition.category is CorrectnessCategory.COMMAND_LEGALITY
        assert definition.subject is RuleSubject.AGGREGATE_COMMAND


def test_v0_selections_are_duplicate_free_and_cross_registry_coherent() -> None:
    definition = correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS[
        ("order.correctness", 0)
    ]
    selections = (
        definition.rule_ids,
        definition.transition_rule_ids,
        definition.amount_rule_ids,
    )

    assert all(len(selection) == len(frozenset(selection)) for selection in selections)
    assert frozenset(definition.transition_rule_ids).issubset(
        definition.rule_ids
    )
    assert frozenset(definition.amount_rule_ids).issubset(definition.rule_ids)
    assert frozenset(definition.transition_rule_ids).issubset(
        correctness_contract_module._ALLOWED_TRANSITION_DEFINITIONS
    )
    assert frozenset(definition.amount_rule_ids).issubset(
        correctness_contract_module._COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS
    )


def test_v0_specialized_definitions_belong_to_edition_vocabularies() -> None:
    edition = correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS[
        ("order.correctness", 0)
    ]

    for rule_id in edition.transition_rule_ids:
        transition = (
            correctness_contract_module._ALLOWED_TRANSITION_DEFINITIONS[rule_id]
        )
        assert transition.command in edition.commands
        assert transition.predecessor_status in edition.statuses
        assert transition.candidate_event_type in edition.event_types
        assert transition.resulting_status in edition.statuses

    for rule_id in edition.amount_rule_ids:
        constraint = (
            correctness_contract_module._COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS[
                rule_id
            ]
        )
        assert constraint.command in edition.commands


def test_v0_materialized_records_match_all_authoritative_definitions() -> None:
    contract = ORDER_CORRECTNESS_CONTRACT_V0
    edition = correctness_contract_module._ORDER_CORRECTNESS_CONTRACT_DEFINITIONS[
        (contract.contract_id, contract.contract_version)
    ]

    assert tuple(rule.rule_id for rule in contract.rules) == edition.rule_ids
    assert tuple(
        transition.legality_rule_id
        for transition in contract.allowed_transitions
    ) == edition.transition_rule_ids
    assert tuple(
        constraint.rule_id for constraint in contract.amount_constraints
    ) == edition.amount_rule_ids
    assert contract.rules == tuple(
        CorrectnessRule.from_rule_id(rule_id) for rule_id in edition.rule_ids
    )
    assert contract.allowed_transitions == tuple(
        AllowedTransition.from_rule_id(rule_id)
        for rule_id in edition.transition_rule_ids
    )
    assert contract.amount_constraints == tuple(
        CommandAmountConstraint.from_rule_id(rule_id)
        for rule_id in edition.amount_rule_ids
    )


def test_authoritative_cross_registry_validator_accepts_current_definitions() -> None:
    assert correctness_contract_module._validate_authoritative_definitions() is None
