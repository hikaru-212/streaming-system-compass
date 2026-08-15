"""Immutable declarative correctness contract for the minimal Order domain.

The contract in this module represents intended correctness as typed data. It
does not execute commands, normalize money, evaluate candidates, mutate an
aggregate, validate accepted-history truth, or select a runtime action.

Executable authority remains with the current Order, Money, and Compass
implementations. A later parity stage may compare those implementations with
the canonical data declared here without importing their executable helpers
into this module.

Candidate identity and acceptance remain separate authority concepts: a
candidate may carry an ``event_id`` before it becomes accepted history. That
architectural principle is intentionally not one of the stable rule-evaluation
identities in the V0 contract.

In current Order V1, ``current_version`` tracks the last applied aggregate-local
event sequence. That equality exists because every currently legal accepted
Order event changes business state. V0 does not assert semantic identity between
event sequence and a future separately modeled business-state version, and no
separate ``business_state_version`` exists in V0.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .enums import CommandType, EventType, OrderStatus


class CorrectnessCategory(str, Enum):
    """Semantic responsibility category for an Order correctness rule.

    Categories identify when and by which architectural responsibility a rule
    is evaluated. They do not identify technical status, runtime action,
    admission disposition, retry classification, or recovery strategy.
    """

    COMMAND_LEGALITY = "COMMAND_LEGALITY"
    CANDIDATE_CONSTRUCTION = "CANDIDATE_CONSTRUCTION"
    TRUSTED_APPLICATION = "TRUSTED_APPLICATION"
    TRANSITION_TRUTH = "TRANSITION_TRUTH"


class RuleSubject(str, Enum):
    """Closed vocabulary describing what a correctness proposition is about.

    A subject is independent from the rule category so that, for example,
    candidate-event propositions and predecessor-claim propositions remain
    distinguishable without introducing arbitrary subject strings.
    """

    AGGREGATE_COMMAND = "AGGREGATE_COMMAND"
    CANDIDATE_EVENT = "CANDIDATE_EVENT"
    PREDECESSOR_CLAIM = "PREDECESSOR_CLAIM"
    TRUSTED_EVENT_APPLICATION = "TRUSTED_EVENT_APPLICATION"
    ACCEPTED_CONTEXT_COMPARISON = "ACCEPTED_CONTEXT_COMPARISON"


class OrderCorrectnessRuleId(str, Enum):
    """Currently known stable semantic identities for Order correctness rules.

    A contract edition selects an explicit subset of this vocabulary. Adding a
    future known identity does not retroactively require an older contract
    edition to contain it. Identity remains separate from evaluation result,
    validator implementation, reason text, policy action, and retry behavior.
    """

    CREATE_ALLOWED_FROM_INIT = "order.command.create.allowed-from-init"
    PAY_ALLOWED_FROM_CREATED = "order.command.pay.allowed-from-created"
    CREATE_NORMALIZED_AMOUNT_POSITIVE = (
        "order.command.create.normalized-amount-positive"
    )
    PAY_NORMALIZED_AMOUNT_POSITIVE = "order.command.pay.normalized-amount-positive"
    PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL = (
        "order.command.pay.normalized-amount-equals-total"
    )

    CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION = (
        "order.candidate.sequence-is-next-aggregate-version"
    )
    CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR = (
        "order.candidate.proof-derived-from-aggregate-predecessor"
    )

    TRUSTED_APPLICATION_EVENT_ORDER_ID_MATCHES_AGGREGATE = (
        "order.trusted-application.event-order-id-matches-aggregate"
    )
    TRUSTED_APPLICATION_EVENT_SEQUENCE_IS_NEXT_VERSION = (
        "order.trusted-application.event-sequence-is-next-version"
    )
    TRUSTED_APPLICATION_CREATED_ESTABLISHES_STATE = (
        "order.trusted-application.created-establishes-state"
    )
    TRUSTED_APPLICATION_PAID_ESTABLISHES_STATE = (
        "order.trusted-application.paid-establishes-state"
    )
    TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD = (
        "order.trusted-application.updates-aggregate-history-head"
    )

    TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION = (
        "order.transition.sequence-matches-accepted-next-version"
    )
    TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED = (
        "order.transition.proof-prev-event-id-matches-accepted"
    )
    TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED = (
        "order.transition.proof-prev-version-matches-accepted"
    )
    TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED = (
        "order.transition.proof-prev-status-matches-accepted"
    )
    TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED = (
        "order.transition.candidate-event-type-supported"
    )
    TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS = (
        "order.transition.event-type-legal-from-accepted-status"
    )


class MoneyRoundingMode(str, Enum):
    """Closed declarative rounding vocabulary justified by the current contract.

    The vocabulary contains only rounding semantics that are source-grounded for
    an accepted contract edition. It contains no normalization behavior; current
    executable Money behavior remains outside this module.
    """

    ROUND_HALF_EVEN = "ROUND_HALF_EVEN"


class AmountConstraintKind(str, Enum):
    """Closed declarative vocabulary for V0 normalized-amount relationships.

    Values describe intended command-money semantics only. They do not parse,
    normalize, or compare runtime values.
    """

    NORMALIZED_VALUE_GREATER_THAN_ZERO = "NORMALIZED_VALUE_GREATER_THAN_ZERO"
    NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT = (
        "NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT"
    )


@dataclass(frozen=True)
class _RuleDefinition:
    """Private immutable semantic metadata owned by one stable rule identity."""

    semantic_proposition: str
    category: CorrectnessCategory
    subject: RuleSubject

    def __post_init__(self) -> None:
        if (
            not isinstance(self.semantic_proposition, str)
            or not self.semantic_proposition.strip()
            or self.semantic_proposition != self.semantic_proposition.strip()
        ):
            raise ValueError(
                "semantic_proposition must be a trimmed non-empty string"
            )
        if not isinstance(self.category, CorrectnessCategory):
            raise TypeError("category must be CorrectnessCategory")
        if not isinstance(self.subject, RuleSubject):
            raise TypeError("subject must be RuleSubject")


_RULE_DEFINITIONS: Mapping[OrderCorrectnessRuleId, _RuleDefinition] = (
    MappingProxyType(
        {
            OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT: _RuleDefinition(
                semantic_proposition=(
                    "A CREATE command is legal only when the aggregate status "
                    "is INIT."
                ),
                category=CorrectnessCategory.COMMAND_LEGALITY,
                subject=RuleSubject.AGGREGATE_COMMAND,
            ),
            OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED: _RuleDefinition(
                semantic_proposition=(
                    "A PAY command is legal only when the aggregate status is "
                    "CREATED."
                ),
                category=CorrectnessCategory.COMMAND_LEGALITY,
                subject=RuleSubject.AGGREGATE_COMMAND,
            ),
            OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE: (
                _RuleDefinition(
                    semantic_proposition=(
                        "The normalized CREATE amount is greater than zero."
                    ),
                    category=CorrectnessCategory.COMMAND_LEGALITY,
                    subject=RuleSubject.AGGREGATE_COMMAND,
                )
            ),
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE: (
                _RuleDefinition(
                    semantic_proposition=(
                        "The normalized PAY amount is greater than zero."
                    ),
                    category=CorrectnessCategory.COMMAND_LEGALITY,
                    subject=RuleSubject.AGGREGATE_COMMAND,
                )
            ),
            OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL: (
                _RuleDefinition(
                    semantic_proposition=(
                        "The normalized PAY amount equals the aggregate's current "
                        "total_amount."
                    ),
                    category=CorrectnessCategory.COMMAND_LEGALITY,
                    subject=RuleSubject.AGGREGATE_COMMAND,
                )
            ),
            OrderCorrectnessRuleId.CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate event's sequence equals the aggregate's "
                        "current_version plus next_sequence_increment."
                    ),
                    category=CorrectnessCategory.CANDIDATE_CONSTRUCTION,
                    subject=RuleSubject.CANDIDATE_EVENT,
                )
            ),
            OrderCorrectnessRuleId.CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate proof's prev_status, prev_version, and "
                        "prev_event_id are derived from the aggregate's current "
                        "status, current_version, and last_event_id."
                    ),
                    category=CorrectnessCategory.CANDIDATE_CONSTRUCTION,
                    subject=RuleSubject.PREDECESSOR_CLAIM,
                )
            ),
            (
                OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_ORDER_ID_MATCHES_AGGREGATE
            ): (
                _RuleDefinition(
                    semantic_proposition=(
                        "A trusted event's order_id equals the aggregate's order_id "
                        "before application."
                    ),
                    category=CorrectnessCategory.TRUSTED_APPLICATION,
                    subject=RuleSubject.TRUSTED_EVENT_APPLICATION,
                )
            ),
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_SEQUENCE_IS_NEXT_VERSION: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A trusted event's sequence equals the aggregate's "
                        "current_version plus next_sequence_increment before "
                        "application."
                    ),
                    category=CorrectnessCategory.TRUSTED_APPLICATION,
                    subject=RuleSubject.TRUSTED_EVENT_APPLICATION,
                )
            ),
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_CREATED_ESTABLISHES_STATE: (
                _RuleDefinition(
                    semantic_proposition=(
                        "Applying a trusted CREATED event sets status to CREATED "
                        "and replaces total_amount with event.amount."
                    ),
                    category=CorrectnessCategory.TRUSTED_APPLICATION,
                    subject=RuleSubject.TRUSTED_EVENT_APPLICATION,
                )
            ),
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_PAID_ESTABLISHES_STATE: (
                _RuleDefinition(
                    semantic_proposition=(
                        "Applying a trusted PAID event sets status to PAID and "
                        "replaces paid_amount with event.amount."
                    ),
                    category=CorrectnessCategory.TRUSTED_APPLICATION,
                    subject=RuleSubject.TRUSTED_EVENT_APPLICATION,
                )
            ),
            OrderCorrectnessRuleId.TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD: (
                _RuleDefinition(
                    semantic_proposition=(
                        "Applying a trusted event updates the aggregate's local "
                        "history head by setting current_version to event.sequence "
                        "and last_event_id to event.event_id."
                    ),
                    category=CorrectnessCategory.TRUSTED_APPLICATION,
                    subject=RuleSubject.TRUSTED_EVENT_APPLICATION,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate event's sequence equals the accepted context's "
                        "previous version plus next_sequence_increment."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate proof's prev_event_id equals the accepted "
                        "context's predecessor event identity."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate proof's prev_version equals the accepted "
                        "context's previous version."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate proof's prev_status equals the accepted "
                        "context's previous status."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate event's event_type belongs to the contract's "
                        "declared event_types."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.CANDIDATE_EVENT,
                )
            ),
            OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS: (
                _RuleDefinition(
                    semantic_proposition=(
                        "A candidate event's event_type is legal from the accepted "
                        "context's previous status according to the allowed "
                        "transition graph."
                    ),
                    category=CorrectnessCategory.TRANSITION_TRUTH,
                    subject=RuleSubject.ACCEPTED_CONTEXT_COMPARISON,
                )
            ),
        }
    )
)


@dataclass(frozen=True)
class _AllowedTransitionDefinition:
    """Private relationship owned by one command-legality rule identity."""

    command: CommandType
    predecessor_status: OrderStatus
    candidate_event_type: EventType
    resulting_status: OrderStatus


_ALLOWED_TRANSITION_DEFINITIONS: Mapping[
    OrderCorrectnessRuleId,
    _AllowedTransitionDefinition,
] = MappingProxyType(
    {
        OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT: (
            _AllowedTransitionDefinition(
                command=CommandType.CREATE,
                predecessor_status=OrderStatus.INIT,
                candidate_event_type=EventType.CREATED,
                resulting_status=OrderStatus.CREATED,
            )
        ),
        OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED: (
            _AllowedTransitionDefinition(
                command=CommandType.PAY,
                predecessor_status=OrderStatus.CREATED,
                candidate_event_type=EventType.PAID,
                resulting_status=OrderStatus.PAID,
            )
        ),
    }
)


@dataclass(frozen=True)
class _CommandAmountConstraintDefinition:
    """Private amount relationship owned by one command-legality rule ID."""

    command: CommandType
    constraint: AmountConstraintKind


_COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS: Mapping[
    OrderCorrectnessRuleId,
    _CommandAmountConstraintDefinition,
] = MappingProxyType(
    {
        OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE: (
            _CommandAmountConstraintDefinition(
                command=CommandType.CREATE,
                constraint=(
                    AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO
                ),
            )
        ),
        OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE: (
            _CommandAmountConstraintDefinition(
                command=CommandType.PAY,
                constraint=(
                    AmountConstraintKind.NORMALIZED_VALUE_GREATER_THAN_ZERO
                ),
            )
        ),
        OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL: (
            _CommandAmountConstraintDefinition(
                command=CommandType.PAY,
                constraint=(
                    AmountConstraintKind.NORMALIZED_VALUE_EQUALS_CURRENT_TOTAL_AMOUNT
                ),
            )
        ),
    }
)


@dataclass(frozen=True)
class _OrderCorrectnessContractDefinition:
    """Private immutable content selected by one stable contract identity."""

    statuses: frozenset[OrderStatus]
    commands: frozenset[CommandType]
    event_types: frozenset[EventType]
    next_sequence_increment: int
    normalization_quantum: Decimal
    rounding_mode: MoneyRoundingMode
    rule_ids: tuple[OrderCorrectnessRuleId, ...]
    transition_rule_ids: tuple[OrderCorrectnessRuleId, ...]
    amount_rule_ids: tuple[OrderCorrectnessRuleId, ...]


_ORDER_CORRECTNESS_CONTRACT_DEFINITIONS: Mapping[
    tuple[str, int],
    _OrderCorrectnessContractDefinition,
] = MappingProxyType(
    {
        (
            "order.correctness",
            0,
        ): _OrderCorrectnessContractDefinition(
            statuses=frozenset(
                (
                    OrderStatus.INIT,
                    OrderStatus.CREATED,
                    OrderStatus.PAID,
                )
            ),
            commands=frozenset((CommandType.CREATE, CommandType.PAY)),
            event_types=frozenset((EventType.CREATED, EventType.PAID)),
            next_sequence_increment=1,
            normalization_quantum=Decimal("0.01"),
            rounding_mode=MoneyRoundingMode.ROUND_HALF_EVEN,
            rule_ids=(
                OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
                OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
                OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
                OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
                OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
                (
                    OrderCorrectnessRuleId.CANDIDATE_SEQUENCE_IS_NEXT_AGGREGATE_VERSION
                ),
                (
                    OrderCorrectnessRuleId.CANDIDATE_PROOF_DERIVED_FROM_AGGREGATE_PREDECESSOR
                ),
                (
                    OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_ORDER_ID_MATCHES_AGGREGATE
                ),
                (
                    OrderCorrectnessRuleId.TRUSTED_APPLICATION_EVENT_SEQUENCE_IS_NEXT_VERSION
                ),
                (
                    OrderCorrectnessRuleId.TRUSTED_APPLICATION_CREATED_ESTABLISHES_STATE
                ),
                (
                    OrderCorrectnessRuleId.TRUSTED_APPLICATION_PAID_ESTABLISHES_STATE
                ),
                (
                    OrderCorrectnessRuleId.TRUSTED_APPLICATION_UPDATES_AGGREGATE_HISTORY_HEAD
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED
                ),
                (
                    OrderCorrectnessRuleId.TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS
                ),
            ),
            transition_rule_ids=(
                OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
                OrderCorrectnessRuleId.PAY_ALLOWED_FROM_CREATED,
            ),
            amount_rule_ids=(
                OrderCorrectnessRuleId.CREATE_NORMALIZED_AMOUNT_POSITIVE,
                OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_POSITIVE,
                OrderCorrectnessRuleId.PAY_NORMALIZED_AMOUNT_EQUALS_TOTAL,
            ),
        )
    }
)


@dataclass(frozen=True, init=False)
class CorrectnessRule:
    """Immutable materialization of one authoritative stable rule definition.

    Fields:
        rule_id: Stable typed identity selected by a contract edition.
        semantic_proposition: Human-readable immutable explanation of meaning.
        category: Architectural correctness responsibility for the rule.
        subject: Typed evaluation subject of the proposition.

    Use :meth:`from_rule_id` for construction. Callers cannot independently
    select proposition, category, or subject; the authoritative private registry
    determines those fields from ``rule_id``. The proposition is explanatory
    data, not a parser input, evaluator expression, or replacement for identity.
    """

    rule_id: OrderCorrectnessRuleId
    semantic_proposition: str
    category: CorrectnessCategory
    subject: RuleSubject

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "CorrectnessRule must be constructed with "
            "CorrectnessRule.from_rule_id()"
        )

    @classmethod
    def from_rule_id(
        cls,
        rule_id: OrderCorrectnessRuleId,
    ) -> "CorrectnessRule":
        """Materialize the one authoritative definition for ``rule_id``."""

        if not isinstance(rule_id, OrderCorrectnessRuleId):
            raise TypeError("rule_id must be OrderCorrectnessRuleId")

        try:
            definition = _RULE_DEFINITIONS[rule_id]
        except KeyError as exc:
            raise ValueError(
                "rule_id has no authoritative semantic definition"
            ) from exc

        rule = object.__new__(cls)
        object.__setattr__(rule, "rule_id", rule_id)
        object.__setattr__(
            rule,
            "semantic_proposition",
            definition.semantic_proposition,
        )
        object.__setattr__(rule, "category", definition.category)
        object.__setattr__(rule, "subject", definition.subject)
        return rule


@dataclass(frozen=True, init=False)
class AllowedTransition:
    """Immutable materialization of one authoritative transition edge.

    Fields identify the command-legality rule, predecessor status, candidate
    event type, and resulting status after trusted application. Absence from the
    closed allowed graph denotes a forbidden command/status combination; this
    record performs no runtime command evaluation or state mutation.

    Use :meth:`from_rule_id` for construction. The legality rule identity owns
    the complete relationship, so callers cannot independently combine it with
    command, status, or event values.
    """

    legality_rule_id: OrderCorrectnessRuleId
    command: CommandType
    predecessor_status: OrderStatus
    candidate_event_type: EventType
    resulting_status: OrderStatus

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "AllowedTransition must be constructed with "
            "AllowedTransition.from_rule_id()"
        )

    @classmethod
    def from_rule_id(
        cls,
        rule_id: OrderCorrectnessRuleId,
    ) -> "AllowedTransition":
        """Materialize the one transition relationship owned by ``rule_id``.

        Args:
            rule_id: Stable legality identity with a registered transition.

        Returns:
            An immutable relationship whose dependent fields come only from the
            authoritative transition registry.

        Raises:
            TypeError: If ``rule_id`` is not an Order correctness rule identity.
            ValueError: If the identity owns no transition definition.

        This method performs declarative materialization only; it does not
        evaluate a command or mutate an aggregate.
        """

        if not isinstance(rule_id, OrderCorrectnessRuleId):
            raise TypeError("rule_id must be OrderCorrectnessRuleId")

        try:
            definition = _ALLOWED_TRANSITION_DEFINITIONS[rule_id]
        except KeyError as exc:
            raise ValueError(
                "rule_id has no authoritative allowed-transition definition"
            ) from exc

        transition = object.__new__(cls)
        object.__setattr__(transition, "legality_rule_id", rule_id)
        object.__setattr__(transition, "command", definition.command)
        object.__setattr__(
            transition,
            "predecessor_status",
            definition.predecessor_status,
        )
        object.__setattr__(
            transition,
            "candidate_event_type",
            definition.candidate_event_type,
        )
        object.__setattr__(
            transition,
            "resulting_status",
            definition.resulting_status,
        )
        return transition


@dataclass(frozen=True, init=False)
class CommandAmountConstraint:
    """Immutable materialization of one authoritative amount relationship.

    The record associates a stable command-legality rule with a command and a
    typed constraint kind. It contains no Money parsing, normalization, runtime
    comparison, storage conversion, or rejection behavior.

    Use :meth:`from_rule_id` for construction. The rule identity owns the
    command and constraint, so callers cannot compose those fields separately.
    """

    rule_id: OrderCorrectnessRuleId
    command: CommandType
    constraint: AmountConstraintKind

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "CommandAmountConstraint must be constructed with "
            "CommandAmountConstraint.from_rule_id()"
        )

    @classmethod
    def from_rule_id(
        cls,
        rule_id: OrderCorrectnessRuleId,
    ) -> "CommandAmountConstraint":
        """Materialize the one amount relationship owned by ``rule_id``.

        Args:
            rule_id: Stable command-legality identity with a registered amount
                relationship.

        Returns:
            An immutable command/constraint relationship materialized from the
            authoritative amount registry.

        Raises:
            TypeError: If ``rule_id`` is not an Order correctness rule identity.
            ValueError: If the identity owns no amount definition.

        This method does not normalize, compare, or reject runtime money values.
        """

        if not isinstance(rule_id, OrderCorrectnessRuleId):
            raise TypeError("rule_id must be OrderCorrectnessRuleId")

        try:
            definition = _COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS[rule_id]
        except KeyError as exc:
            raise ValueError(
                "rule_id has no authoritative command-amount definition"
            ) from exc

        constraint = object.__new__(cls)
        object.__setattr__(constraint, "rule_id", rule_id)
        object.__setattr__(constraint, "command", definition.command)
        object.__setattr__(constraint, "constraint", definition.constraint)
        return constraint


@dataclass(frozen=True, init=False)
class OrderCorrectnessContract:
    """Immutable materialization of one registered Order contract edition.

    Fields:
        contract_id: Stable non-empty domain-scoped contract identity.
        contract_version: Non-negative semantic edition number.
        statuses: Closed statuses declared by this edition.
        commands: Closed commands declared by this edition.
        event_types: Closed event types declared by this edition.
        next_sequence_increment: Positive declared next-position increment.
        normalization_quantum: Positive finite Decimal normalization quantum.
        rounding_mode: Typed declarative decimal rounding mode.
        rules: Explicit stable rule definitions selected by this edition.
        allowed_transitions: Closed allowed command/status graph records.
        amount_constraints: Normalized command-amount constraint records.

    Use :meth:`from_identity` for construction. The registered identity selects
    every edition-wide parameter and all rule, transition, and amount-rule IDs.
    The specialized authoritative registries materialize the selected records;
    callers cannot independently compose content while claiming that identity.

    Construction validates declarative-definition coherence only: types,
    immutability, uniqueness, vocabulary membership, and referenced-rule
    relationships. It does not evaluate commands, events, or candidates.

    Unknown identities raise ``ValueError``. This object owns no transaction,
    concurrency, persistence, runtime evaluation, policy, retry, or mutation.
    """

    contract_id: str
    contract_version: int
    statuses: frozenset[OrderStatus]
    commands: frozenset[CommandType]
    event_types: frozenset[EventType]
    next_sequence_increment: int
    normalization_quantum: Decimal
    rounding_mode: MoneyRoundingMode
    rules: tuple[CorrectnessRule, ...]
    allowed_transitions: tuple[AllowedTransition, ...]
    amount_constraints: tuple[CommandAmountConstraint, ...]

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "OrderCorrectnessContract must be constructed with "
            "OrderCorrectnessContract.from_identity()"
        )

    @classmethod
    def from_identity(
        cls,
        contract_id: str,
        contract_version: int,
    ) -> "OrderCorrectnessContract":
        """Materialize the one registered edition for a stable identity.

        Args:
            contract_id: Stable, trimmed Order contract family identity.
            contract_version: Non-negative registered edition number.

        Returns:
            An immutable contract whose parameters and selected identities come
            only from the authoritative edition definition.

        Raises:
            TypeError: If the version is not an integer.
            ValueError: If either identity component is invalid or the complete
                identity is not registered.

        Materialization performs definition coherence checks only. It does not
        execute correctness rules or become an authority for runtime behavior.
        """

        _require_trimmed_non_empty_string(contract_id, "contract_id")
        _require_non_negative_int(contract_version, "contract_version")

        try:
            definition = _ORDER_CORRECTNESS_CONTRACT_DEFINITIONS[
                (contract_id, contract_version)
            ]
        except KeyError as exc:
            raise ValueError(
                "contract identity has no authoritative edition definition"
            ) from exc

        contract = object.__new__(cls)
        object.__setattr__(contract, "contract_id", contract_id)
        object.__setattr__(contract, "contract_version", contract_version)
        object.__setattr__(contract, "statuses", definition.statuses)
        object.__setattr__(contract, "commands", definition.commands)
        object.__setattr__(contract, "event_types", definition.event_types)
        object.__setattr__(
            contract,
            "next_sequence_increment",
            definition.next_sequence_increment,
        )
        object.__setattr__(
            contract,
            "normalization_quantum",
            definition.normalization_quantum,
        )
        object.__setattr__(contract, "rounding_mode", definition.rounding_mode)
        object.__setattr__(
            contract,
            "rules",
            tuple(
                CorrectnessRule.from_rule_id(rule_id)
                for rule_id in definition.rule_ids
            ),
        )
        object.__setattr__(
            contract,
            "allowed_transitions",
            tuple(
                AllowedTransition.from_rule_id(rule_id)
                for rule_id in definition.transition_rule_ids
            ),
        )
        object.__setattr__(
            contract,
            "amount_constraints",
            tuple(
                CommandAmountConstraint.from_rule_id(rule_id)
                for rule_id in definition.amount_rule_ids
            ),
        )
        contract._validate_structure()
        return contract

    def _validate_structure(self) -> None:
        """Validate materialized declarative coherence without evaluation."""

        _require_trimmed_non_empty_string(self.contract_id, "contract_id")
        _require_non_negative_int(self.contract_version, "contract_version")
        _require_positive_int(
            self.next_sequence_increment,
            "next_sequence_increment",
        )
        _require_positive_finite_decimal(
            self.normalization_quantum,
            "normalization_quantum",
        )
        _require_enum(self.rounding_mode, MoneyRoundingMode, "rounding_mode")

        _require_exact_frozenset(self.statuses, "statuses")
        _require_exact_frozenset(self.commands, "commands")
        _require_exact_frozenset(self.event_types, "event_types")
        _require_exact_tuple(self.rules, "rules")
        _require_exact_tuple(self.allowed_transitions, "allowed_transitions")
        _require_exact_tuple(self.amount_constraints, "amount_constraints")

        _require_enum_members(self.statuses, OrderStatus, "statuses")
        _require_enum_members(self.commands, CommandType, "commands")
        _require_enum_members(self.event_types, EventType, "event_types")
        _require_record_members(self.rules, CorrectnessRule, "rules")
        _require_record_members(
            self.allowed_transitions,
            AllowedTransition,
            "allowed_transitions",
        )
        _require_record_members(
            self.amount_constraints,
            CommandAmountConstraint,
            "amount_constraints",
        )

        rule_ids = tuple(rule.rule_id for rule in self.rules)
        if len(frozenset(rule_ids)) != len(rule_ids):
            raise ValueError("rules must contain unique rule IDs")

        transition_keys = tuple(
            (transition.command, transition.predecessor_status)
            for transition in self.allowed_transitions
        )
        if len(frozenset(self.allowed_transitions)) != len(
            self.allowed_transitions
        ):
            raise ValueError("allowed_transitions must not contain duplicates")
        if len(frozenset(transition_keys)) != len(transition_keys):
            raise ValueError(
                "allowed_transitions must not contain contradictory definitions "
                "for the same command and predecessor status"
            )

        for transition in self.allowed_transitions:
            if transition.command not in self.commands:
                raise ValueError(
                    "allowed transition command must belong to declared commands"
                )
            if transition.predecessor_status not in self.statuses:
                raise ValueError(
                    "allowed transition predecessor status must belong to "
                    "declared statuses"
                )
            if transition.candidate_event_type not in self.event_types:
                raise ValueError(
                    "allowed transition candidate event type must belong to "
                    "declared event_types"
                )
            if transition.resulting_status not in self.statuses:
                raise ValueError(
                    "allowed transition resulting status must belong to "
                    "declared statuses"
                )

            legality_rule = _resolve_rule(
                self.rules,
                transition.legality_rule_id,
                "allowed transition",
            )
            if (
                legality_rule.category is not CorrectnessCategory.COMMAND_LEGALITY
                or legality_rule.subject is not RuleSubject.AGGREGATE_COMMAND
            ):
                raise ValueError(
                    "allowed transition legality rule must be COMMAND_LEGALITY "
                    "with AGGREGATE_COMMAND subject"
                )

        if len(frozenset(self.amount_constraints)) != len(
            self.amount_constraints
        ):
            raise ValueError("amount_constraints must not contain duplicates")

        amount_constraint_keys = tuple(
            (constraint.command, constraint.constraint)
            for constraint in self.amount_constraints
        )
        if len(frozenset(amount_constraint_keys)) != len(amount_constraint_keys):
            raise ValueError(
                "amount_constraints must not contain conflicting definitions "
                "for the same command and constraint"
            )

        amount_rule_ids = tuple(
            constraint.rule_id for constraint in self.amount_constraints
        )
        if len(frozenset(amount_rule_ids)) != len(amount_rule_ids):
            raise ValueError(
                "amount_constraints must reference unique rule IDs"
            )

        for constraint in self.amount_constraints:
            if constraint.command not in self.commands:
                raise ValueError(
                    "amount constraint command must belong to declared commands"
                )

            amount_rule = _resolve_rule(
                self.rules,
                constraint.rule_id,
                "amount constraint",
            )
            if (
                amount_rule.category is not CorrectnessCategory.COMMAND_LEGALITY
                or amount_rule.subject is not RuleSubject.AGGREGATE_COMMAND
            ):
                raise ValueError(
                    "amount constraint rule must be COMMAND_LEGALITY with "
                    "AGGREGATE_COMMAND subject"
                )


def _require_trimmed_non_empty_string(value: object, field_name: str) -> None:
    """Reject values that are not non-empty strings without outer whitespace."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")


def _require_non_negative_int(value: object, field_name: str) -> None:
    """Reject booleans, non-integers, and negative integer values."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be int")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _require_positive_int(value: object, field_name: str) -> None:
    """Reject booleans, non-integers, and non-positive integer values."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be int")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_positive_finite_decimal(value: object, field_name: str) -> None:
    """Reject values that are not positive finite Decimal instances."""

    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be Decimal")
    if not value.is_finite() or value <= Decimal("0"):
        raise ValueError(f"{field_name} must be a positive finite Decimal")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    """Reject a value that is not a member of the required enum type."""

    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be {enum_type.__name__}")


def _require_exact_frozenset(value: object, field_name: str) -> None:
    """Reject mutable or alternate collection types for frozenset fields."""

    if type(value) is not frozenset:
        raise TypeError(f"{field_name} must be frozenset")


def _require_exact_tuple(value: object, field_name: str) -> None:
    """Reject mutable or alternate collection types for tuple fields."""

    if type(value) is not tuple:
        raise TypeError(f"{field_name} must be tuple")


def _require_enum_members(
    values: frozenset[object],
    enum_type: type[Enum],
    field_name: str,
) -> None:
    """Reject a declared vocabulary containing values from another type."""

    for value in values:
        if not isinstance(value, enum_type):
            raise TypeError(
                f"{field_name} members must be {enum_type.__name__}"
            )


def _require_record_members(
    values: tuple[object, ...],
    record_type: type[object],
    field_name: str,
) -> None:
    """Reject a record collection containing values from another type."""

    for value in values:
        if not isinstance(value, record_type):
            raise TypeError(
                f"{field_name} members must be {record_type.__name__}"
            )


def _resolve_rule(
    rules: tuple[CorrectnessRule, ...],
    rule_id: OrderCorrectnessRuleId,
    reference_owner: str,
) -> CorrectnessRule:
    """Resolve a structurally referenced rule without executing its proposition."""

    matches = tuple(rule for rule in rules if rule.rule_id is rule_id)
    if not matches:
        raise ValueError(
            f"{reference_owner} references a rule ID absent from contract.rules"
        )
    return matches[0]


def _definition_invariant(condition: bool, message: str) -> None:
    """Fail module initialization when authoritative declarations drift."""

    if not condition:
        raise RuntimeError(message)


def _validate_authoritative_definitions() -> None:
    """Validate cross-registry coherence without evaluating runtime facts."""

    known_rule_ids = frozenset(OrderCorrectnessRuleId)
    _definition_invariant(
        frozenset(_RULE_DEFINITIONS) == known_rule_ids,
        "authoritative rule definitions must exactly cover known rule IDs",
    )

    transition_keys: list[tuple[CommandType, OrderStatus]] = []
    for rule_id, definition in _ALLOWED_TRANSITION_DEFINITIONS.items():
        _definition_invariant(
            rule_id in _RULE_DEFINITIONS,
            "allowed-transition definition must reference a known rule",
        )
        rule_definition = _RULE_DEFINITIONS[rule_id]
        _definition_invariant(
            rule_definition.category is CorrectnessCategory.COMMAND_LEGALITY
            and rule_definition.subject is RuleSubject.AGGREGATE_COMMAND,
            "allowed-transition rule must be COMMAND_LEGALITY with "
            "AGGREGATE_COMMAND subject",
        )
        _definition_invariant(
            isinstance(definition.command, CommandType)
            and isinstance(definition.predecessor_status, OrderStatus)
            and isinstance(definition.candidate_event_type, EventType)
            and isinstance(definition.resulting_status, OrderStatus),
            "allowed-transition definition must use typed relationship values",
        )
        transition_keys.append(
            (definition.command, definition.predecessor_status)
        )
    _definition_invariant(
        len(frozenset(transition_keys)) == len(transition_keys),
        "allowed-transition definitions must not contradict one graph key",
    )

    amount_keys: list[tuple[CommandType, AmountConstraintKind]] = []
    for rule_id, definition in (
        _COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS.items()
    ):
        _definition_invariant(
            rule_id in _RULE_DEFINITIONS,
            "command-amount definition must reference a known rule",
        )
        rule_definition = _RULE_DEFINITIONS[rule_id]
        _definition_invariant(
            rule_definition.category is CorrectnessCategory.COMMAND_LEGALITY
            and rule_definition.subject is RuleSubject.AGGREGATE_COMMAND,
            "command-amount rule must be COMMAND_LEGALITY with "
            "AGGREGATE_COMMAND subject",
        )
        _definition_invariant(
            isinstance(definition.command, CommandType)
            and isinstance(definition.constraint, AmountConstraintKind),
            "command-amount definition must use typed relationship values",
        )
        amount_keys.append((definition.command, definition.constraint))
    _definition_invariant(
        len(frozenset(amount_keys)) == len(amount_keys),
        "command-amount definitions must not duplicate one relationship",
    )

    for identity, definition in (
        _ORDER_CORRECTNESS_CONTRACT_DEFINITIONS.items()
    ):
        _definition_invariant(
            type(identity) is tuple and len(identity) == 2,
            "contract-edition registry keys must be identity tuples",
        )
        contract_id, contract_version = identity
        _definition_invariant(
            isinstance(contract_id, str)
            and bool(contract_id.strip())
            and contract_id == contract_id.strip(),
            "contract-edition contract_id must be a trimmed non-empty string",
        )
        _definition_invariant(
            type(contract_version) is int and contract_version >= 0,
            "contract-edition version must be a non-negative int",
        )
        _definition_invariant(
            type(definition.statuses) is frozenset
            and all(
                isinstance(status, OrderStatus)
                for status in definition.statuses
            ),
            "contract-edition statuses must be a typed frozenset",
        )
        _definition_invariant(
            type(definition.commands) is frozenset
            and all(
                isinstance(command, CommandType)
                for command in definition.commands
            ),
            "contract-edition commands must be a typed frozenset",
        )
        _definition_invariant(
            type(definition.event_types) is frozenset
            and all(
                isinstance(event_type, EventType)
                for event_type in definition.event_types
            ),
            "contract-edition event_types must be a typed frozenset",
        )
        _definition_invariant(
            type(definition.next_sequence_increment) is int
            and definition.next_sequence_increment > 0,
            "contract-edition next_sequence_increment must be positive",
        )
        _definition_invariant(
            isinstance(definition.normalization_quantum, Decimal)
            and definition.normalization_quantum.is_finite()
            and definition.normalization_quantum > Decimal("0"),
            "contract-edition normalization_quantum must be positive and finite",
        )
        _definition_invariant(
            isinstance(definition.rounding_mode, MoneyRoundingMode),
            "contract-edition rounding_mode must be typed",
        )

        selections = (
            ("rules", definition.rule_ids),
            ("transitions", definition.transition_rule_ids),
            ("amount constraints", definition.amount_rule_ids),
        )
        for selection_name, selected_ids in selections:
            _definition_invariant(
                type(selected_ids) is tuple,
                f"contract-edition {selection_name} selection must be a tuple",
            )
            _definition_invariant(
                all(
                    isinstance(rule_id, OrderCorrectnessRuleId)
                    for rule_id in selected_ids
                ),
                f"contract-edition {selection_name} must select typed rule IDs",
            )
            _definition_invariant(
                len(frozenset(selected_ids)) == len(selected_ids),
                f"contract-edition {selection_name} must not contain duplicates",
            )

        selected_rule_ids = frozenset(definition.rule_ids)
        selected_transition_ids = frozenset(definition.transition_rule_ids)
        selected_amount_ids = frozenset(definition.amount_rule_ids)
        _definition_invariant(
            selected_rule_ids.issubset(known_rule_ids),
            "contract edition must select only known rule IDs",
        )
        _definition_invariant(
            selected_transition_ids.issubset(
                _ALLOWED_TRANSITION_DEFINITIONS
            ),
            "selected transition rule must have an authoritative definition",
        )
        _definition_invariant(
            selected_amount_ids.issubset(
                _COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS
            ),
            "selected amount rule must have an authoritative definition",
        )
        _definition_invariant(
            selected_transition_ids.issubset(selected_rule_ids)
            and selected_amount_ids.issubset(selected_rule_ids),
            "selected transition and amount rules must be selected edition rules",
        )

        for rule_id in definition.transition_rule_ids:
            transition = _ALLOWED_TRANSITION_DEFINITIONS[rule_id]
            _definition_invariant(
                transition.command in definition.commands
                and transition.predecessor_status in definition.statuses
                and transition.candidate_event_type in definition.event_types
                and transition.resulting_status in definition.statuses,
                "selected transition values must belong to edition vocabularies",
            )
        for rule_id in definition.amount_rule_ids:
            constraint = _COMMAND_AMOUNT_CONSTRAINT_DEFINITIONS[rule_id]
            _definition_invariant(
                constraint.command in definition.commands,
                "selected amount command must belong to edition commands",
            )


_validate_authoritative_definitions()


ORDER_CORRECTNESS_CONTRACT_V0 = OrderCorrectnessContract.from_identity(
    contract_id="order.correctness",
    contract_version=0,
)


__all__ = (
    "AllowedTransition",
    "AmountConstraintKind",
    "CommandAmountConstraint",
    "CorrectnessCategory",
    "CorrectnessRule",
    "MoneyRoundingMode",
    "ORDER_CORRECTNESS_CONTRACT_V0",
    "OrderCorrectnessContract",
    "OrderCorrectnessRuleId",
    "RuleSubject",
)
