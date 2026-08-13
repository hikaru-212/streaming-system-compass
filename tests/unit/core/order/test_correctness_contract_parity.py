"""Executable-authority parity for the canonical Order correctness contract.

These tests compare the declarative V0 contract with current Order, Money, and
Compass behavior. They do not make the contract executable and do not claim
that agreement between the two representations proves semantic correctness.
"""

from dataclasses import replace
from decimal import Decimal
from enum import Enum

import pytest

from src.compass.transition.types import ValidationContext, ValidationVerdict
from src.compass.transition.validators import FullProofValidator
from src.core.common.money import MoneyValidationError, normalize_money
from src.core.order.aggregate import OrderAggregate
from src.core.order.correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    AmountConstraintKind,
    CorrectnessCategory,
    MoneyRoundingMode,
    OrderCorrectnessRuleId,
    RuleSubject,
)
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof


class _ForeignEventType(Enum):
    """Test-local value for the validator's unsupported-type branch."""

    OBSERVED = "OBSERVED"


def _assert_rule_declared(
    rule_id: OrderCorrectnessRuleId,
    category: CorrectnessCategory,
    subject: RuleSubject,
) -> None:
    """Bind an executable parity scenario to one typed contract rule."""

    matches = tuple(
        rule
        for rule in ORDER_CORRECTNESS_CONTRACT_V0.rules
        if rule.rule_id is rule_id
    )
    assert len(matches) == 1
    assert matches[0].category is category
    assert matches[0].subject is subject


def _assert_amount_constraint(
    rule_id: OrderCorrectnessRuleId,
    command: CommandType,
    constraint: AmountConstraintKind,
) -> None:
    """Bind command behavior to its typed V0 amount relationship."""

    _assert_rule_declared(
        rule_id,
        CorrectnessCategory.COMMAND_LEGALITY,
        RuleSubject.AGGREGATE_COMMAND,
    )
    assert any(
        item.rule_id is rule_id
        and item.command is command
        and item.constraint is constraint
        for item in ORDER_CORRECTNESS_CONTRACT_V0.amount_constraints
    )


def _event(
    *,
    event_id: str,
    order_id: str = "order-parity",
    sequence: int,
    event_type: object,
    amount: Decimal,
    prev_status: OrderStatus,
    prev_version: int,
    prev_event_id: str | None,
) -> OrderEvent:
    """Build deterministic event-shaped test data without persistence."""

    return OrderEvent(
        event_id=event_id,
        request_id=f"request-{event_id}",
        order_id=order_id,
        sequence=sequence,
        event_type=event_type,  # type: ignore[arg-type]
        amount=amount,
        occurred_at_ms=0,
        proof=Proof(
            prev_status=prev_status,
            prev_version=prev_version,
            prev_event_id=prev_event_id,
        ),
    )


def _aggregate_at_status(status: OrderStatus) -> OrderAggregate:
    """Create isolated aggregate state for command/apply parity scenarios."""

    aggregate = OrderAggregate("order-parity")
    if status is OrderStatus.INIT:
        return aggregate

    created = _event(
        event_id="accepted-created",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("10.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )
    aggregate.apply(created)
    if status is OrderStatus.CREATED:
        return aggregate

    paid = _event(
        event_id="accepted-paid",
        sequence=2,
        event_type=EventType.PAID,
        amount=Decimal("10.00"),
        prev_status=OrderStatus.CREATED,
        prev_version=1,
        prev_event_id=created.event_id,
    )
    aggregate.apply(paid)
    return aggregate


def _aggregate_state(aggregate: OrderAggregate) -> tuple[object, ...]:
    """Capture every current aggregate field relevant to mutation parity."""

    return (
        aggregate.order_id,
        aggregate.current_version,
        aggregate.status,
        aggregate.total_amount,
        aggregate.paid_amount,
        aggregate.last_event_id,
    )


def _context_at_status(status: OrderStatus) -> ValidationContext:
    """Build accepted-context facts independently of validator mappings."""

    if status is OrderStatus.INIT:
        return ValidationContext(
            actual_prev_event=None,
            actual_prev_version=0,
            actual_prev_status=OrderStatus.INIT,
        )

    if status is OrderStatus.CREATED:
        previous = _event(
            event_id="accepted-created",
            sequence=1,
            event_type=EventType.CREATED,
            amount=Decimal("10.00"),
            prev_status=OrderStatus.INIT,
            prev_version=0,
            prev_event_id=None,
        )
        return ValidationContext(
            actual_prev_event=previous,
            actual_prev_version=1,
            actual_prev_status=OrderStatus.CREATED,
        )

    previous = _event(
        event_id="accepted-paid",
        sequence=2,
        event_type=EventType.PAID,
        amount=Decimal("10.00"),
        prev_status=OrderStatus.CREATED,
        prev_version=1,
        prev_event_id="accepted-created",
    )
    return ValidationContext(
        actual_prev_event=previous,
        actual_prev_version=2,
        actual_prev_status=OrderStatus.PAID,
    )


def _candidate_for_context(
    event_type: object,
    context: ValidationContext,
) -> OrderEvent:
    """Build a candidate whose earlier transition-truth facts are valid."""

    previous_event_id = (
        None
        if context.actual_prev_event is None
        else context.actual_prev_event.event_id
    )
    return _event(
        event_id=f"candidate-{getattr(event_type, 'value', 'unknown').lower()}",
        sequence=(
            context.actual_prev_version
            + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment
        ),
        event_type=event_type,
        amount=Decimal("10.00"),
        prev_status=context.actual_prev_status,
        prev_version=context.actual_prev_version,
        prev_event_id=previous_event_id,
    )


# Command / Money parity


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    (
        (Decimal("1.234"), Decimal("1.23")),
        (Decimal("1.236"), Decimal("1.24")),
        (Decimal("10.005"), Decimal("10.00")),
        (Decimal("10.015"), Decimal("10.02")),
        (Decimal("0.004"), Decimal("0.00")),
        (Decimal("0.005"), Decimal("0.00")),
        (Decimal("0.006"), Decimal("0.01")),
    ),
)
def test_executable_money_normalization_matches_v0_quantum_and_rounding(
    raw_value: Decimal,
    expected: Decimal,
) -> None:
    assert ORDER_CORRECTNESS_CONTRACT_V0.normalization_quantum == Decimal("0.01")
    assert (
        ORDER_CORRECTNESS_CONTRACT_V0.rounding_mode
        is MoneyRoundingMode.ROUND_HALF_EVEN
    )
    assert normalize_money(raw_value) == expected


def test_create_normalized_positive_rule_matches_command_behavior() -> None:
    _assert_amount_constraint(
        OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
        CommandType.CREATE,
        AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO,
    )

    for rejected in (Decimal("0.004"), Decimal("0.005")):
        with pytest.raises(MoneyValidationError):
            OrderAggregate("order-parity").create("create", rejected)

    candidate = OrderAggregate("order-parity").create(
        "create",
        Decimal("0.006"),
    )
    assert candidate.amount == Decimal("0.01")


def test_pay_normalized_positive_rule_matches_command_behavior() -> None:
    _assert_amount_constraint(
        OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
        CommandType.PAY,
        AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO,
    )

    for rejected in (Decimal("0.004"), Decimal("0.005")):
        aggregate = OrderAggregate("order-parity")
        created = aggregate.create("create", Decimal("0.006"))
        aggregate.apply(created)
        with pytest.raises(MoneyValidationError):
            aggregate.pay("pay", rejected)

    aggregate = OrderAggregate("order-parity")
    created = aggregate.create("create", Decimal("0.006"))
    aggregate.apply(created)
    candidate = aggregate.pay("pay", Decimal("0.006"))
    assert candidate.amount == Decimal("0.01")


def test_pay_full_payment_rule_uses_normalized_amount() -> None:
    _assert_amount_constraint(
        OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
        CommandType.PAY,
        AmountConstraintKind.NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT,
    )

    aggregate = OrderAggregate("order-parity")
    created = aggregate.create("create", Decimal("10.015"))
    aggregate.apply(created)
    assert aggregate.total_amount == Decimal("10.02")

    accepted_candidate = aggregate.pay("pay-equal", Decimal("10.016"))
    assert accepted_candidate.amount == aggregate.total_amount

    with pytest.raises(ValueError):
        aggregate.pay("pay-unequal", Decimal("10.014"))


@pytest.mark.parametrize(
    ("status", "command"),
    tuple(
        (status, command)
        for status in OrderStatus
        for command in CommandType
    ),
)
def test_aggregate_command_legality_matches_allowed_graph(
    status: OrderStatus,
    command: CommandType,
) -> None:
    edges = tuple(
        edge
        for edge in ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions
        if edge.predecessor_status is status and edge.command is command
    )
    rule_id_by_command = {
        edge.command: edge.legality_rule_id
        for edge in ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions
    }
    _assert_rule_declared(
        rule_id_by_command[command],
        CorrectnessCategory.COMMAND_LEGALITY,
        RuleSubject.AGGREGATE_COMMAND,
    )

    aggregate = _aggregate_at_status(status)
    if not edges:
        with pytest.raises(ValueError):
            if command is CommandType.CREATE:
                aggregate.create("create", Decimal("10.00"))
            else:
                aggregate.pay("pay", Decimal("10.00"))
        return

    edge = edges[0]
    if command is CommandType.CREATE:
        candidate = aggregate.create("create", Decimal("10.00"))
    else:
        candidate = aggregate.pay("pay", Decimal("10.00"))
    assert candidate.event_type is edge.candidate_event_type


# Candidate-construction parity


def test_candidate_sequence_matches_declared_increment() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION,
        CorrectnessCategory.CANDIDATE_CONSTRUCTION,
        RuleSubject.CANDIDATE_EVENT,
    )
    aggregate = OrderAggregate("order-parity")

    before_create = aggregate.current_version
    created = aggregate.create("create", Decimal("10.00"))
    assert created.sequence == (
        before_create + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment
    )

    aggregate.apply(created)
    before_pay = aggregate.current_version
    paid = aggregate.pay("pay", Decimal("10.00"))
    assert paid.sequence == (
        before_pay + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment
    )


def test_candidate_predecessor_claim_matches_pre_command_aggregate_state() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR,
        CorrectnessCategory.CANDIDATE_CONSTRUCTION,
        RuleSubject.PREDECESSOR_CLAIM,
    )
    aggregate = OrderAggregate("order-parity")
    created = aggregate.create("create", Decimal("10.00"))
    aggregate.apply(created)

    predecessor = (
        aggregate.status,
        aggregate.current_version,
        aggregate.last_event_id,
    )
    paid = aggregate.pay("pay", Decimal("10.00"))

    assert (
        paid.proof.prev_status,
        paid.proof.prev_version,
        paid.proof.prev_event_id,
    ) == predecessor


# Trusted-application parity


def test_apply_rejects_mismatched_order_id_without_mutation() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_ORDER_ID_MATCHES_AGGREGATE,
        CorrectnessCategory.TRUSTED_APPLICATION,
        RuleSubject.TRUSTED_EVENT_APPLICATION,
    )
    aggregate = OrderAggregate("order-parity")
    event = _event(
        event_id="wrong-order",
        order_id="another-order",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("10.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )
    before = _aggregate_state(aggregate)

    with pytest.raises(ValueError):
        aggregate.apply(event)

    assert _aggregate_state(aggregate) == before


def test_apply_rejects_non_next_sequence_without_mutation() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_SEQUENCE_IS_NEXT_VERSION,
        CorrectnessCategory.TRUSTED_APPLICATION,
        RuleSubject.TRUSTED_EVENT_APPLICATION,
    )
    aggregate = OrderAggregate("order-parity")
    event = _event(
        event_id="discontinuous",
        sequence=1 + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment,
        event_type=EventType.CREATED,
        amount=Decimal("10.00"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )
    before = _aggregate_state(aggregate)

    with pytest.raises(ValueError):
        aggregate.apply(event)

    assert _aggregate_state(aggregate) == before


def test_apply_created_establishes_declared_state() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRUSTED_APPLICATION_CREATED_ESTABLISHES_STATE,
        CorrectnessCategory.TRUSTED_APPLICATION,
        RuleSubject.TRUSTED_EVENT_APPLICATION,
    )
    aggregate = OrderAggregate("order-parity")
    event = _event(
        event_id="trusted-created",
        sequence=1,
        event_type=EventType.CREATED,
        amount=Decimal("12.34"),
        prev_status=OrderStatus.INIT,
        prev_version=0,
        prev_event_id=None,
    )

    aggregate.apply(event)

    assert aggregate.status is OrderStatus.CREATED
    assert aggregate.total_amount == event.amount
    assert aggregate.paid_amount == Decimal("0.00")


def test_apply_paid_replaces_state_without_command_revalidation() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRUSTED_APPLICATION_PAID_ESTABLISHES_STATE,
        CorrectnessCategory.TRUSTED_APPLICATION,
        RuleSubject.TRUSTED_EVENT_APPLICATION,
    )
    aggregate = _aggregate_at_status(OrderStatus.CREATED)
    first = _event(
        event_id="trusted-paid-one",
        sequence=2,
        event_type=EventType.PAID,
        amount=Decimal("4.00"),
        prev_status=OrderStatus.CREATED,
        prev_version=1,
        prev_event_id="accepted-created",
    )
    second = _event(
        event_id="trusted-paid-two",
        sequence=3,
        event_type=EventType.PAID,
        amount=Decimal("3.00"),
        prev_status=OrderStatus.PAID,
        prev_version=2,
        prev_event_id=first.event_id,
    )

    aggregate.apply(first)
    assert aggregate.total_amount == Decimal("10.00")
    assert aggregate.paid_amount == Decimal("4.00")

    aggregate.apply(second)
    assert aggregate.status is OrderStatus.PAID
    assert aggregate.total_amount == Decimal("10.00")
    assert aggregate.paid_amount == Decimal("3.00")


@pytest.mark.parametrize(
    "status_before",
    (OrderStatus.INIT, OrderStatus.CREATED),
)
def test_apply_updates_aggregate_history_head(
    status_before: OrderStatus,
) -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD,
        CorrectnessCategory.TRUSTED_APPLICATION,
        RuleSubject.TRUSTED_EVENT_APPLICATION,
    )
    aggregate = _aggregate_at_status(status_before)
    event_type = (
        EventType.CREATED
        if status_before is OrderStatus.INIT
        else EventType.PAID
    )
    event = _event(
        event_id=f"history-head-{event_type.value.lower()}",
        sequence=(
            aggregate.current_version
            + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment
        ),
        event_type=event_type,
        amount=Decimal("10.00"),
        prev_status=aggregate.status,
        prev_version=aggregate.current_version,
        prev_event_id=aggregate.last_event_id,
    )

    aggregate.apply(event)

    assert aggregate.current_version == event.sequence
    assert aggregate.last_event_id == event.event_id


# Compass transition-truth parity


def test_validator_sequence_truth_matches_declared_increment() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION,
        CorrectnessCategory.TRANSITION_TRUTH,
        RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
    )
    validator = FullProofValidator()
    context = _context_at_status(OrderStatus.CREATED)
    candidate = _candidate_for_context(EventType.PAID, context)

    assert validator.validate(candidate, context).verdict is ValidationVerdict.PASSED

    wrong_sequence = replace(
        candidate,
        sequence=(
            candidate.sequence
            + ORDER_CORRECTNESS_CONTRACT_V0.next_sequence_increment
        ),
    )
    assert (
        validator.validate(wrong_sequence, context).verdict
        is ValidationVerdict.FAILED
    )


@pytest.mark.parametrize(
    ("rule_id", "proof_field", "wrong_value"),
    (
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED,
            "prev_event_id",
            "another-accepted-event",
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED,
            "prev_version",
            99,
        ),
        (
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED,
            "prev_status",
            OrderStatus.INIT,
        ),
    ),
)
def test_validator_predecessor_claims_match_accepted_context(
    rule_id: OrderCorrectnessRuleId,
    proof_field: str,
    wrong_value: object,
) -> None:
    _assert_rule_declared(
        rule_id,
        CorrectnessCategory.TRANSITION_TRUTH,
        RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
    )
    validator = FullProofValidator()
    context = _context_at_status(OrderStatus.CREATED)
    candidate = _candidate_for_context(EventType.PAID, context)
    changed_proof = replace(candidate.proof, **{proof_field: wrong_value})
    changed_candidate = replace(candidate, proof=changed_proof)

    assert (
        validator.validate(changed_candidate, context).verdict
        is ValidationVerdict.FAILED
    )


def test_validator_supported_event_types_match_declared_vocabulary() -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED,
        CorrectnessCategory.TRANSITION_TRUTH,
        RuleSubject.CANDIDATE_EVENT,
    )
    validator = FullProofValidator()

    assert (
        frozenset(validator.REQUIRED_PREV_STATUS_BY_EVENT_TYPE)
        == ORDER_CORRECTNESS_CONTRACT_V0.event_types
    )
    for edge in ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions:
        context = _context_at_status(edge.predecessor_status)
        candidate = _candidate_for_context(edge.candidate_event_type, context)
        assert (
            validator.validate(candidate, context).verdict
            is ValidationVerdict.PASSED
        )

    context = _context_at_status(OrderStatus.INIT)
    unsupported = _candidate_for_context(_ForeignEventType.OBSERVED, context)
    assert (
        validator.validate(unsupported, context).verdict
        is ValidationVerdict.FAILED
    )


@pytest.mark.parametrize(
    ("status", "event_type"),
    tuple(
        (status, event_type)
        for status in OrderStatus
        for event_type in EventType
    ),
)
def test_validator_event_type_legality_matches_allowed_graph(
    status: OrderStatus,
    event_type: EventType,
) -> None:
    _assert_rule_declared(
        OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS,
        CorrectnessCategory.TRANSITION_TRUTH,
        RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
    )
    legal_pairs = frozenset(
        (edge.predecessor_status, edge.candidate_event_type)
        for edge in ORDER_CORRECTNESS_CONTRACT_V0.allowed_transitions
    )
    context = _context_at_status(status)
    candidate = _candidate_for_context(event_type, context)

    result = FullProofValidator().validate(candidate, context)

    expected_verdict = (
        ValidationVerdict.PASSED
        if (status, event_type) in legal_pairs
        else ValidationVerdict.FAILED
    )
    assert result.verdict is expected_verdict
