# Stage 4B.5 PR1 — Order Correctness Contract Boundary

## Status

```text
stage
= Stage 4B.5

bounded responsibility
= intended Order correctness

current deliverable
= PR1 boundary and design documentation only

implementation status
= not implemented
```

This document is a portable planning draft for the first Stage 4B.5 pull
request. It does not introduce the production contract, parity tests, runtime
consumption, serialization, persistence, or any change to the current Order
implementation.

Stage 4B.1 remains active and independent. This Stage 4B.5 boundary does not
change, depend on, or reinterpret Stage 4B.1 `DiagnosticTrace` work.

This document is not an accepted ADR and does not silently update the public
roadmap. It records the source-grounded boundary that must receive human review
before Stage 4B.5 implementation begins.

## 1. Purpose

Stage 4B.5 exists to provide a machine-readable semantic reference for intended
Order correctness.

That reference should eventually let downstream governance—including future
policy, retry governance, and agent consumers—distinguish:

```text
what happened
≠
what should have been true
≠
why the observed result violated intended domain semantics
```

The first Stage 4B.5 slice is intentionally narrower than a runtime policy
system. Its responsibility is:

```text
describe required Order-domain truth
```

not:

```text
authorize or execute a response
```

The governing separation is:

```text
the contract explains required truth
≠
the contract authorizes repair
```

The contract must not tell an agent or runtime component to mutate user intent,
change a payment amount, retry, rebuild, fall back, quarantine, or choose an
action or execution strategy.

## 2. Authority Model

Stage 4B.5 preserves the following source-grounded authority model:

```text
Order Domain v1 specification
= normative business meaning

OrderAggregate + shared Money implementation
= current executable domain authority

Order Correctness Contract v0
= immutable machine-readable description

Parity tests
= evidence that the declarative description remains aligned
```

The current normative business specification is:

```text
docs/domain/order_domain_v1_rules.md
```

The current executable domain authority is primarily:

```text
src/core/order/aggregate.py
src/core/common/money.py
src/core/order/enums.py
src/core/order/events.py
```

The future contract must describe that authority. It must not replace it,
execute it, or silently become a second runtime decision-maker.

The contract also must not silently supersede the normative domain
specification. If the specification, executable implementation, and proposed
contract disagree, Stage 4B.5 must surface the disagreement for review rather
than choosing a winner implicitly.

Parity has a deliberately limited meaning:

```text
parity
= evidence that two representations agree

parity
≠ independent proof that both representations are semantically correct
```

Human semantic review and the normative domain specification therefore remain
necessary even when every parity test passes.

## 3. V0 Responsibility Boundary

Order Correctness Contract v0 describes pure Order-domain correctness only.

It distinguishes three related but non-identical concerns:

```text
command legality
= whether the current aggregate may produce a candidate event

candidate construction
= what domain event a legal command proposes

trusted application
= how an already-trusted event changes aggregate state
```

This distinction is necessary because current command methods produce candidate
events without mutating the aggregate. Aggregate state changes only through
`apply(event)`.

`apply(event)` is a trusted state-mutation path. It is not a complete command
validator and must not be described as one.

## 4. V0 Vocabulary

The current closed vocabulary is:

| Vocabulary | Values |
|---|---|
| `OrderStatus` | `INIT`, `CREATED`, `PAID` |
| `CommandType` | `CREATE`, `PAY` |
| `EventType` | `CREATED`, `PAID` |

V0 describes only this minimal Order lifecycle. It does not imply that the
domain can never introduce later states, commands, or events. Such an addition
would be a semantic contract change and would require a new contract edition.

## 5. Initial Aggregate State

A new Order aggregate begins with:

| Field | Initial value |
|---|---|
| `status` | `INIT` |
| `current_version` | `0` |
| `total_amount` | `Decimal("0.00")` |
| `paid_amount` | `Decimal("0.00")` |
| `last_event_id` | `None` |

The aggregate already has its concrete `order_id` identity at `INIT`. Identity
exists independently of lifecycle status.

## 6. Closed-World Transition Semantics

The v0 transition graph is closed over the declared status and command
vocabularies.

| Command | Allowed predecessor | Candidate event | Result after trusted application |
|---|---|---|---|
| `CREATE` | `INIT` | `CREATED` | `CREATED` |
| `PAY` | `CREATED` | `PAID` | `PAID` |

Closed-world means that every other combination of the declared command and
status vocabularies is forbidden:

```text
CREATE from CREATED
CREATE from PAID
PAY from INIT
PAY from PAID
```

The contract should represent the allowed predecessor set as exhaustive. It
should not maintain a second, independently editable list of forbidden
transitions that can drift from the allowed graph.

The `PAY from PAID` prohibition is domain legality when a pay command reaches
the aggregate. Whether an incoming call is a new request or a replay of an
already accepted request belongs to idempotency and orchestration, not to this
transition rule.

## 7. Candidate Generation and State Mutation

A legal command produces a candidate event. Candidate generation does not
itself mutate aggregate state.

The current semantic sequence is:

```text
legal command
→ candidate OrderEvent
→ external validation and admission boundaries
→ trusted apply(event)
→ aggregate state mutation
```

The v0 contract describes only the domain portions of this sequence. It does
not assert that a candidate became accepted history, and it does not decide
whether external validation or admission should allow the candidate.

For an aggregate-produced candidate:

```text
candidate.sequence = aggregate.current_version + 1
```

This is a domain candidate-construction rule. It is distinct from checking the
candidate against current accepted history and distinct from append-time
expected-version admission.

## 8. Money and Amount Semantics

V0 uses the current shared Money semantics:

```text
representation
= Decimal-based exact money

normalization quantum
= Decimal("0.01")

rounding
= ROUND_HALF_EVEN
```

All v0 amount comparisons apply to normalized money values.

### Create

```text
normalized create amount > Decimal("0.00")
```

Applying the corresponding trusted `CREATED` event assigns:

```text
total_amount = event.amount
```

### Pay

```text
normalized pay amount > Decimal("0.00")

normalized pay amount = current total_amount
```

Applying the corresponding trusted `PAID` event assigns:

```text
paid_amount = event.amount
```

The assignment is replacement, not accumulation:

```text
paid_amount = event.amount

not

paid_amount += event.amount
```

This preserves the current meaning of `PAID` as full-payment completion. V0
does not introduce partial, split, or accumulated payments.

## 9. Trusted `apply(event)` Boundary

Trusted application requires:

```text
event.order_id = aggregate.order_id

event.sequence = aggregate.current_version + 1
```

These are local preconditions of the aggregate mutation path.

They do not assert that storage has guaranteed a valid accepted history. In
particular:

```text
apply requires an exact-next supplied event
≠
the Order contract guarantees accepted-history continuity
```

`apply(event)` assumes the event is already accepted or otherwise trusted by
its caller. It intentionally does not rerun all command preconditions.

Therefore arbitrary `apply(PAID)` is not a complete validation path. An
exact-next, same-order `PAID` event supplied directly to `apply(...)` does not
cause the aggregate to recheck:

- whether a `PAY` command was legal from the prior state;
- whether the amount is positive;
- whether the amount equals `total_amount`;
- whether predecessor proof matches accepted history;
- whether the event was actually admitted to accepted history.

V0 must model command legality, application effects, and trusted-application
preconditions as separate declarative concepts so this distinction remains
visible.

## 10. Explicit V0 Exclusions

The following responsibilities are outside Order Correctness Contract v0:

| Excluded concern | Owning or later boundary |
|---|---|
| Accepted-history membership and continuity guarantee | Event store, replay source, and admission boundaries |
| Candidate sequence compared with accepted version | Compass Layer 1 transition truth |
| Proof matched with accepted predecessor identity, version, or status | Compass Layer 1 transition truth |
| Expected durable version and append-position occupation | Persistence/concurrency admission |
| Idempotency replay, conflict, fingerprint, and recording order | Idempotency and transactional orchestration |
| Projection state or snapshot trust | Projection and read-side trust boundaries |
| Runtime technical or semantic outcome | Stage 4A and existing runtime result boundaries |
| `DecisionReceipt` linkage | Existing Stage 4B evidence boundary; no v0 linkage |
| Detailed execution path | Stage 4B.1 `DiagnosticTrace` |
| Timing and cost evidence | Stage 4B.2 |
| Permitted runtime action | Stage 4C |
| Execution strategy | Stage 4D |
| Retry and attempt governance | Stage 4E |
| Serialization or interoperability artifact | Future consumer-specific work |
| Persistence or database schema | Future separately authorized work |

V0 therefore contains no:

- `SemanticOutcomeCode`;
- `DecisionReceipt` field or metadata convention;
- runtime action;
- retryability or attempt limit;
- fallback, rebuild, quarantine, or escalation instruction;
- strategy or policy selection;
- timing or cost field;
- diagnostic trace;
- serializer;
- JSON or YAML artifact;
- persistence model or migration;
- evaluator;
- callback, predicate function, or dependency-injected executable behavior.

## 11. Rule Identity Boundary

V0 does not introduce stable public rule IDs.

For current parity use:

```text
v0 structural contract identity
= sufficient
```

The contract can be compared structurally through its declared vocabulary,
transition records, amount constraints, assignment effects, and sequence
semantics. No current runtime producer or consumer requires a separately stable
rule identifier.

Stable rule identities may become necessary later when a concrete typed
evidence consumer exists:

```text
Order Correctness Contract
→ specific intended assertion
→ RuleEvaluationEvidence
→ SemanticOutcome / later Stage 4C reasoning
```

That future direction would let runtime policy or agents understand why an
observed result violated intended domain truth instead of reacting only to a
coarse status or semantic classification.

Future rule identity must remain distinct from:

```text
technical status
SemanticOutcomeCode
admission disposition
RuntimeAction
execution strategy
retry classification
```

Stage 4B.5 PR1 does not define `RuleEvaluationEvidence`, an evaluator, or a rule
identifier vocabulary. It also does not place rule IDs into
`DecisionReceipt.metadata` or `DecisionReceipt.evidence_summary` as an escape
hatch.

## 12. Preferred Contract Representation

The preferred v0 implementation direction is:

```text
immutable, data-only typed Python
```

The future PR2 representation should conceptually use:

- frozen dataclasses;
- tuples and frozensets rather than mutable collections;
- existing `OrderStatus`, `CommandType`, and `EventType` values;
- `Decimal`-based money semantics;
- explicit data describing transitions, constraints, assignments, and sequence
  behavior.

It must not contain:

- callbacks;
- executable predicate functions;
- evaluator methods;
- aggregate mutation methods;
- policy methods;
- dependency injection;
- runtime service ownership.

PR1 does not create that production representation.

The first implementation should have one declarative source. This avoids:

```text
hand-maintained Python rules
+
hand-maintained JSON or YAML rules
→ competing declarative authorities
```

Generated interoperability artifacts may be reconsidered only after a concrete
Stage 4C or external-tool consumer exists. If such an artifact is later
justified, it should be generated deterministically from the typed declarative
source rather than maintained independently.

## 13. Contract Identity and Version Direction

The provisional smallest contract identity is:

```text
contract_id = "order.correctness"
contract_version = 0
```

`contract_version` identifies an edition of represented intended domain
semantics.

It should change when the represented semantic contract changes, including:

- state vocabulary;
- command or event vocabulary;
- transition meaning;
- amount or payment semantics;
- application effects;
- sequence semantics;
- the public structural rule surface.

It should not change merely because of:

- an implementation refactor that preserves behavior;
- test additions or test reorganization;
- a Stage number;
- a database migration unrelated to represented domain meaning;
- documentation wording that preserves semantics.

V0 does not implement version negotiation, compatibility ranges, promotion,
effective dates, schema-version machinery, or migration behavior.

## 14. Relationship to Later Governance

The intended ownership chain is:

| Boundary | Responsibility |
|---|---|
| Stage 4B.5 | What intended Order correctness is |
| Future typed `RuleEvaluationEvidence` | Which intended assertion was satisfied or violated |
| `SemanticOutcome` / `DecisionReceipt` | What happened and what it means semantically |
| Stage 4C | What action is permitted |
| Stage 4D | Which permitted execution strategy is selected |
| Stage 4E | Retry and attempt governance |

An intended rule violation is evidence for later reasoning. It is not an action
authorization.

For example:

```text
payment amount violates full-payment semantics
→ the contract explains the violated intended truth

payment amount violates full-payment semantics
≠ the contract authorizes changing the payment amount
```

Likewise, a rule violation does not automatically authorize retry, fallback,
rebuild, quarantine, escalation, or mutation of user intent.

## 15. Parity Boundary

PR3 should add pure parity tests that answer:

```text
Does Order Correctness Contract v0 still describe current
OrderAggregate and shared Money behavior?
```

The parity surface should cover:

- vocabulary and initial state;
- valid create and pay candidate generation;
- all forbidden command/status combinations under closed-world semantics;
- normalized positive amount requirements;
- partial and overpayment rejection;
- full-payment and non-accumulation semantics;
- candidate exact-next sequence;
- trusted same-order exact-next application;
- correct application, sequence gaps, and sequence duplication.

Parity should compare semantic behavior, not exception-message wording.

PR3 should remain pure and require no database, admission gate, idempotency
store, projection runtime, `SemanticOutcome`, `DecisionReceipt`, or
`DiagnosticTrace` fixture.

## 16. Smallest Justified PR Sequence

The currently justified Stage 4B.5 sequence is:

```text
PR1
→ boundary and design documentation

PR2
→ immutable typed, data-only Order Correctness Contract v0
→ structural and immutability tests only

PR3
→ pure parity tests against current OrderAggregate and Money authority
```

No fourth PR is currently justified.

Admission, idempotency, `RuleEvaluationEvidence`, serialization, and runtime
consumption require separate future authorization and a concrete consumer.

## 17. Non-Goals

Stage 4B.5 v0 does not:

- modify or replace `OrderAggregate`;
- modify shared Money behavior;
- generate production events or mutate aggregate state;
- decide whether a candidate is admitted;
- validate candidate proof against accepted history;
- guarantee accepted-history continuity;
- classify idempotency replay or conflict;
- validate projection or snapshot trust;
- produce `SemanticOutcome` or `DecisionReceipt`;
- evaluate a named rule at runtime;
- authorize a runtime action;
- choose an execution strategy;
- authorize or schedule retry;
- preserve timing, cost, or diagnostic traces;
- serialize or persist the contract;
- create a general policy-authoring platform;
- provide an agent workflow or repair instruction.

## 18. Stop Conditions

Stop future Stage 4B.5 v0 implementation and request architectural review if it
would require changing:

- `OrderAggregate`;
- shared Money behavior;
- Compass Layer 1;
- `SemanticOutcome`;
- `DecisionReceipt`;
- persistence or concurrency admission;
- idempotency behavior;
- projection or snapshot behavior;
- retry, policy, or strategy behavior;
- database schema or migrations;
- project dependencies.

Also stop if:

- a proposed rule cannot be grounded in current normative domain meaning and
  executable behavior;
- trusted `apply(event)` is being treated as a complete command validator;
- accepted-history, admission, or idempotency truth is being recast as a pure
  domain rule;
- the aggregate or a runtime validator would import and execute the contract;
- a manually maintained JSON or YAML rule source is proposed beside Python;
- stable public rule IDs are requested without a typed evaluator and concrete
  consumer;
- parity exposes a real contradiction between the normative Order Domain v1
  specification and executable authority.

When parity exposes such a contradiction, Stage 4B.5 must not make both sides
appear aligned by weakening the test or silently rewriting historical meaning.
The contradiction requires explicit human semantic review.

## 19. Current Source References

This boundary is grounded in the current tracked sources:

- `docs/domain/order_domain_v1_rules.md`
- `docs/domain/decision_note_transition_first_then_domain_invariants.md`
- `docs/boundary_notes/aggregate_module.md`
- `docs/boundary_notes/compass_layer_boundary.md`
- `docs/boundary_notes/event_store_module.md`
- `docs/boundary_notes/idempotency_module.md`
- `src/core/order/aggregate.py`
- `src/core/order/enums.py`
- `src/core/order/events.py`
- `src/core/order/proofs.py`
- `src/core/common/money.py`
- `src/compass/transition/validators.py`
- `src/storage/event_store.py`
- `src/storage/idempotency_store.py`

These references identify the current planning basis. They do not make this
draft an authority over those sources.
