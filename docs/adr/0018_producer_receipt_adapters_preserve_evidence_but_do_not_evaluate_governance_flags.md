# ADR 0018: Producer Receipt Adapters Preserve Evidence but Do Not Evaluate Governance Flags

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Implemented for Stage 4B PR4 and PR5.

The PostgreSQL write-side adapter and all read-side / snapshot producer
adapters preserve typed evidence while leaving all four governance flags
`NOT_EVALUATED`. Stage 4B PR6 serializes and persists those tri-state values
without evaluating them.

Dedicated evaluators that may later produce `TRUE` or `FALSE` remain future
work.

---

## Context

`DecisionReceiptFlags` carries four governance propositions:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

Each proposition uses the tri-state `DecisionReceiptFlagState` vocabulary:

```text
TRUE
FALSE
NOT_EVALUATED
```

The shared contract requires `TRUE` and `FALSE` to represent completed
evaluations. `NOT_EVALUATED` preserves the absence of a completed evaluation
and must not be treated as `FALSE`.

Producer-specific receipt adapters possess detailed typed facts. For example,
the PostgreSQL write-side adapter can observe:

```text
STALE_WRITE
LOCK_TIMEOUT
INFRASTRUCTURE_ERROR
```

It can also preserve technical status, the existing semantic tuple, lifecycle
phase, subject, correlation, identity provenance, admission fate, and compact
typed evidence.

Those facts do not automatically grant authority to complete a governance
proposition.

The experimental PR4 mapping currently treats selected rejection verdicts as
positive flag evaluations:

```text
STALE_WRITE
→ retry_candidate = TRUE

LOCK_TIMEOUT
→ retry_candidate = TRUE

INFRASTRUCTURE_ERROR
→ operator_review_required = TRUE
```

Other outcomes, including `ACCEPTED` and `REPLAY`, remain
`NOT_EVALUATED`. Without an explicit evaluator contract that defines both
positive and negative authority, this creates an unresolved asymmetry:
selected technical facts become positive governance conclusions, while no
component is identified as having completed the corresponding negative
evaluations.

ADR 0017 separated evidence path, identity provenance, admission fate, and
flag state. The shared flag-state work defined the tri-state representation
but deliberately deferred concrete producer evaluator ownership to the PR4 and
PR5 audits.

---

## Decision

Producer-specific `DecisionReceipt` adapters preserve typed evidence but do not
evaluate governance flags.

Producer-specific adapters may:

- validate producer result shapes;
- reject malformed or contradictory evidence;
- map the existing semantic tuple;
- select evidence source;
- select subject;
- select correlation;
- select primary identity provenance;
- select admission fate;
- construct compact typed evidence summaries.

Producer-specific adapters must not complete these governance propositions:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

Therefore every producer-specific adapter supplies:

```text
fallback_required = DecisionReceiptFlagState.NOT_EVALUATED
rebuild_required = DecisionReceiptFlagState.NOT_EVALUATED
operator_review_required = DecisionReceiptFlagState.NOT_EVALUATED
retry_candidate = DecisionReceiptFlagState.NOT_EVALUATED
```

This rule applies to:

- the Stage 4B PR4 PostgreSQL write-side adapter;
- the Stage 4B PR5 read-side and snapshot adapters;
- future producer-specific receipt adapters.

Dedicated later evaluators own completed `TRUE` and `FALSE` conclusions.
Potential ownership areas include runtime decision policy, retry governance,
read-side or snapshot health evaluation, strategy selection, and
operator-review evaluation. This ADR does not prematurely choose the exact
future class or function names.

The durable state meanings are:

```text
TRUE
→ an authorized evaluator completed the proposition positively

FALSE
→ an authorized evaluator completed the proposition negatively

NOT_EVALUATED
→ no authorized completed evaluation exists
```

`FALSE` is never a default for omitted evaluation.

---

## Required Evaluator Contract

Any future component that produces `TRUE` or `FALSE` must define:

1. the exact proposition;
2. the evaluator owner;
3. the required inputs;
4. evidence sufficient for `TRUE`;
5. evidence sufficient for `FALSE`;
6. the `NOT_EVALUATED` condition;
7. the downstream consumer;
8. explicit non-goals.

A semantic code, semantic category, technical status, or producer verdict does
not itself grant evaluator authority. A later ADR or explicit contract must
adopt the complete evaluation rule before such evidence can produce `TRUE` or
`FALSE`.

The generic PR3 mapper remains pass-through only. It may preserve explicitly
supplied flag states from an authorized evaluator, but it must not infer them
from `SemanticOutcome`, producer evidence, or receipt fields.

---

## Rationale

### Typed facts are not governance conclusions

`STALE_WRITE`, `LOCK_TIMEOUT`, and `INFRASTRUCTURE_ERROR` are typed producer
facts. They remain available as technical status, semantic outcome, admission
disposition, lifecycle phase, and compact typed evidence.

They do not by themselves authorize:

```text
retry_candidate = TRUE
operator_review_required = TRUE
```

Retry candidacy may depend on intent consistency, commit certainty, attempt
history, policy, or other evidence. Operator review may depend on actor,
amount, risk, regulation, ambiguity, attempt history, or escalation policy.
Those inputs are not generally completed by a producer result.

### Positive-only evaluation is incomplete

A positive trigger table does not establish who owns the complete proposition.
The evaluator boundary must explain both positive and negative conclusions,
including when evidence remains insufficient.

This does not require every completed evaluator to produce both values for
every receipt. It requires the evaluator contract to define the authority and
evidence for both values rather than treating selected producer facts as
self-authorizing positive conclusions.

### Acceptance does not make every flag false

An `ACCEPTED` result may give a later retry evaluator enough evidence to
conclude that the completed business attempt is not a retry candidate. PR4
does not own that evaluator and therefore still records
`retry_candidate = NOT_EVALUATED`.

Acceptance cannot universally prove:

```text
operator_review_required = FALSE
```

Human-review policy may depend on evidence outside the write-side result.
Producer adapters must not turn successful admission into an implicit negative
governance assertion.

### No producer evidence is lost

Leaving flags `NOT_EVALUATED` does not discard the facts needed by later
evaluators. The receipt continues to preserve, where available:

- technical status;
- semantic classification;
- lifecycle phase;
- typed stream or append verdicts;
- evidence source;
- subject;
- correlation;
- primary identity provenance;
- admission fate.

Later evaluators can combine those durable facts with the policy, health,
attempt, actor, risk, or regulatory inputs that they own.

### One rule must apply across producers

Applying the same boundary to PR4, PR5, and future adapters avoids assigning
governance authority merely because a component has producer-specific mapping
knowledge. Producer mappers remain deterministic evidence adapters; later
governance layers remain responsible for conclusions.

---

## Alternatives Considered

### Alternative 1: Keep the experimental positive-only PR4 mapping

Rejected.

This would keep selected `TRUE` mappings while leaving `ACCEPTED`, `REPLAY`,
and other outcomes unevaluated. It does not define negative-evaluation
authority and would force PR5 to invent a parallel standard.

### Alternative 2: Let each producer adapter define its own complete flag table

Rejected for the current architecture.

Producer evidence remains valuable, but adapter-local tables would mix
evidence normalization with governance evaluation and could assign different
meanings to the same shared flag across producers. A later ADR may authorize a
specific evaluator only after it defines the complete evaluator contract.

### Alternative 3: Infer flags from semantic category, code, or technical status

Rejected.

Semantic interpretation and governance evaluation are separate axes. The PR3
generic mapper must remain producer-agnostic and must not convert semantic
classification into flag authority.

### Alternative 4: Default non-triggered flags to `FALSE`

Rejected.

Absence of a positive producer fact does not prove that an authorized evaluator
completed the proposition negatively. This would collapse `FALSE` and
`NOT_EVALUATED`, reversing the purpose of the tri-state contract.

---

## Consequences

### Positive

- Evidence and governance conclusions remain cleanly separated.
- PR4 and PR5 follow one consistent ownership rule.
- Producer adapters perform no selective positive-only inference.
- Later policy and retry layers receive the original typed evidence.
- The `TRUE` / `FALSE` / `NOT_EVALUATED` meanings remain stable.
- Producer mappers remain deterministic evidence adapters.
- New producers do not acquire governance authority implicitly.

### Negative

- Receipts created directly by producer adapters initially contain no
  completed flags.
- Downstream consumers cannot rely on producer-created `TRUE` or `FALSE`
  states.
- Dedicated evaluator design and implementation are still required.
- Some immediately intuitive conclusions are deliberately deferred.
- Consumers must combine receipt evidence with evaluator-owned inputs before
  obtaining governance conclusions.

### Neutral but Important

The shared tri-state contract remains necessary. Dedicated evaluators may
later produce `TRUE` or `FALSE`; producer adapters simply are not those
evaluators.

Flags remain governance evidence and do not execute fallback, rebuild,
operator review, or retry.

---

## Relationship to Existing Decisions

### Shared flag-state contract

The `DecisionReceiptFlagState` tri-state contract remains valid and necessary.
This ADR resolves evaluator ownership; it does not change the enum, field
names, defaults, validation, or durable state meanings.

### ADR 0017

ADR 0017 separates evidence path, identity provenance, admission fate, and
flag state. It does not authorize producer-specific flag evaluation. This ADR
extends that separation by assigning completed governance evaluation outside
producer receipt adapters.

### Stage 4B flag-state work

The shared flag-state work established that only an evidence owner with a
completed evaluation may assert `TRUE` or `FALSE`, then deferred concrete PR4
and PR5 evaluator ownership. This ADR resolves that deferred question.

### ADR 0019

ADR 0019 addresses receipt persistence, reconstruction, and accepted versus
non-accepted materialization. Those concerns are orthogonal to flag evaluator
ownership. This decision neither modifies nor depends on ADR 0019.

---

## Implementation Implications

The completed PR4 follow-up removed positive flag inference from the write-side
adapter and aligned its tests and documentation. PR5 began with all four flags
`NOT_EVALUATED`, and PR6 preserves the values unchanged through serialization
and persistence. A dedicated evaluator may later supply completed states
through an explicitly defined boundary.

---

## Explicit Non-Goals

This ADR does not:

- modify production code or tests;
- define exact future evaluator class or function names;
- implement runtime decision policy;
- implement retry classification, safety, authorization, or execution;
- implement fallback, rebuild, or operator-review actions;
- change semantic mappings, admission dispositions, or evidence summaries;
- change receipt serialization, persistence, reconstruction, or schema;
- modify ADR 0017 or ADR 0019.

---

## Future Trigger Conditions

Revisit this decision only when a concrete evaluator and consumer require a
completed flag and can define the full evaluator contract adopted above.

Evidence availability alone is not a trigger. The proposal must establish
authority, positive and negative evidence, uncertainty handling, downstream
consumption, and non-goals.

---

## Final Principle

```text
producer-specific DecisionReceipt adapters
= preserve typed evidence
≠ evaluate governance flags

dedicated authorized evaluators
= complete governance propositions
```

Until an authorized evaluator completes a proposition:

```text
DecisionReceiptFlagState.NOT_EVALUATED
```
