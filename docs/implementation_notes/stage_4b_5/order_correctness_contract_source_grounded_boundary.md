# Stage 4B.5 PR1 — Source-Grounded Order Correctness Boundary

## Status

```text
stage
= Stage 4B.5 — COMPLETE / CLOSED

PR
= PR1 — COMPLETE / MERGED

responsibility
= source-grounded correctness boundary and design documentation

PR1 documentation
= accepted source-grounded baseline

production contract and runtime evidence
= implemented in later Stage 4B.5 deliveries
```

This note records the PR1 source-grounded Stage 4B.5 boundary after a fresh
read-only audit of the Order domain, Compass Layer 1, write-side orchestration,
admission, and idempotency boundaries.

Later Stage 4B.5 deliveries implemented the 18-rule identity-driven contract,
six-rule FullProof evidence producer, same-invocation runtime and PostgreSQL
propagation, explicit terminal semantic refinement, deterministic YAML
projection, and bounded overhead characterization. The PR1 analysis below is
preserved as the source-grounded baseline rather than rewritten as closeout
chronology.

It supersedes the earlier planning assumption that Stage 4B.5 needs only a
data-only contract plus parity tests.

The historical file:

```text
order_correctness_contract_boundary.md
```

remains useful provenance but is not current architecture authority.

---

## 1. Why Stage 4B.5 Exists

Streaming System + Compass already prevents some invalid candidate actions from
becoming accepted history.

But a coarse rejection such as:

```text
VALIDATION_BLOCKED
```

does not by itself identify the exact intended correctness rule that was
violated.

Stage 4B.5 exists to close that gap.

Its target responsibility is:

```text
coarse correctness rejection
→ stable machine-readable correctness rule identity
```

The first concrete consumer motivation is live Agent feedback.

The goal is not to determine why an Agent reasoned incorrectly.

The goal is to let a live consumer know which correctness constraint the
candidate violated, so the next candidate space can be narrowed without parsing
free-text reasons.

Conceptually:

```text
Agent
→ current correctness enforcement
→ rejection
→ SemanticOutcome where available
→ RuleEvaluationEvidence where source-legitimate
→ live Agent feedback
→ Agent independently generates another candidate
→ correctness enforcement runs again
```

Stage 4B.5 does not authorize the next attempt and does not tell the Agent how
to repair its reasoning.

---

## 2. Current Authority Model

The current source-grounded authority model is:

```text
Order Domain v1 specification
= normative business meaning

OrderAggregate + shared Money
= executable authority for command/domain behavior

OrderEvent + Proof construction
= executable authority for candidate shape and claims

FullProofValidator
= executable authority for Compass Layer 1 transition-truth evaluation

Order Correctness Contract v0
= declarative machine-readable representation

Parity tests
= evidence of alignment, not independent semantic proof
```

The contract must describe current executable meaning without becoming another
runtime decision engine.

If normative specification, executable source, and proposed contract disagree,
Stage 4B.5 must surface the disagreement for human semantic review.

---

## 3. Current Execution Flow

### 3.1 Aggregate-local command path

Current command handling is approximately:

```text
aggregate construction
→ request identity validation
→ money parsing and cent normalization
→ normalized-positive check
→ command/state legality
→ full-payment equality for PAY
→ candidate sequence / predecessor proof construction
→ immutable candidate event
```

Important:

```text
successful command
→ candidate event

successful command
!= accepted event

candidate generation
!= aggregate mutation
```

Aggregate mutation occurs through trusted `apply(event)`.

### 3.2 Write-side path after candidate creation

After a candidate exists, current orchestration may continue through:

```text
Compass Layer 1 validation
→ concurrency / append admission
→ idempotency persistence
→ commit
→ accepted-history membership
```

The exact ordering differs between PRE_TRANSACTION and IN_TRANSACTION write
compositions, but that difference does not change Stage 4B.5 ownership.

---

## 4. Critical Distinction: Domain Rejection vs Compass BLOCK

The current repository proves:

```text
aggregate/domain command rejection
!=
Compass ValidationResult(FAILED)
→ validation-policy BLOCK
```

Domain command failures such as:

- CREATE from an illegal state;
- PAY from an illegal state;
- invalid normalized amount;
- full-payment mismatch;

occur before a candidate event is returned.

They currently surface as exceptions such as `ValueError` or
`MoneyValidationError`.

They do not currently produce:

```text
ValidationResult
PostgresWriteSideResult
SemanticOutcome
```

Therefore current live Agent rule feedback cannot truthfully claim coverage for
these failures without a separately approved typed domain-rejection producer.

By contrast, every Compass Layer 1 validation failure occurs after a candidate
exists.

---

## 5. Compass Layer 1 Transition-Truth Boundary

`FullProofValidator` evaluates an existing candidate against accepted-history-
derived context.

The current first-failure sequence checks:

1. candidate sequence against actual previous version + 1;
2. predecessor event identity;
3. predecessor version;
4. predecessor status;
5. supported candidate event type;
6. event-type legality from actual predecessor status.

A failed branch returns `ValidationResult(FAILED)`, and current validation policy
maps that result to BLOCK.

The validator knows which branch failed.

However, the returned `ValidationResult` currently contains:

- typed verdict;
- validation mode;
- validator identity;
- free-text reason;
- untyped metadata;

and no stable typed rule discriminator.

Therefore:

```text
producer-owned typed rule evidence
= feasible

downstream reason parsing
= forbidden
```

Stage 4B.5 must never infer `rule_id` by parsing exception strings, free-text
reasons, validator names, or incidental metadata shapes.

---

## 6. Correctness Categories

The source-grounded contract should not flatten all rules into a single
`DOMAIN_INVARIANT` category.

The first contract should preserve at least these conceptual categories.

### 6.1 Domain / command legality

Examples:

- CREATE legal only from INIT;
- PAY legal only from CREATED;
- normalized create amount > 0;
- normalized pay amount > 0;
- payment equals current total amount.

Executable owner:

```text
OrderAggregate + Money
```

### 6.2 Candidate construction semantics

Examples:

- candidate sequence is `current_version + 1`;
- candidate predecessor proof is constructed from aggregate state;
- candidate event identity may be allocated before acceptance.

Executable owner:

```text
OrderAggregate / OrderEvent / Proof
```

### 6.3 Trusted-application preconditions and effects

Examples:

- same-order application;
- exact-next supplied event;
- CREATED assigns/replaces `total_amount`;
- PAID assigns/replaces `paid_amount`;
- version and last-event identity advance.

Executable owner:

```text
OrderAggregate.apply(event)
```

Trusted apply is not a complete command validator.

### 6.4 Compass Layer 1 transition truth

Examples:

- candidate sequence matches accepted-context next version;
- predecessor identity matches accepted context;
- predecessor version matches accepted context;
- predecessor status matches accepted context;
- candidate event type is supported;
- candidate event type is legal from accepted-context status.

Executable owner:

```text
FullProofValidator
```

Including these rules declaratively does not transfer runtime ownership to the
contract.

---

## 7. Explicit First-Slice Deferrals

The initial contract must not silently absorb:

### Admission / accepted-history invariants

Examples:

- expected durable version still matches current stream;
- append candidate occupies the exact next durable position;
- accepted-history membership and commit durability.

These remain a later `ADMISSION_INVARIANT` sub-slice if explicitly approved.

### Idempotency semantics

Examples:

- MISS;
- same request + same semantic signature → replay;
- same request + different semantic signature → conflict;
- idempotency record ordering.

These remain a later `IDEMPOTENCY_SEMANTICS` sub-slice.

### Projection / snapshot trust

Owned by Stage 4B.3 and related read-side boundaries.

### Action / strategy / retry

Owned by Stage 4C / 4D / 4E.

---

## 8. Human Semantic Decisions Recorded by PR1

### 8.1 Event identity

```text
event_id
= identity that may be preallocated on a candidate

accepted-event status
= granted only by accepted-history membership
```

A candidate can have an `event_id` without being an accepted event.

### 8.2 Positive amount

The source-stable rule is:

```text
normalized monetary value > 0
```

not merely raw input > 0.

Money is normalized to the current monetary quantum before positivity is
checked.

### 8.3 Full-payment equality

The current normal command path enforces:

```text
payment amount = current total amount
```

before producing the PAY candidate.

Trusted `apply(PAID)` does not independently revalidate this equality.

Therefore full-payment correctness is a guarantee of the normal
command/candidate/admission trust chain, not an independently rechecked
arbitrary-apply invariant.

### 8.4 Multiple correctness categories

Stage 4B.5 v0 is not one flat list of domain invariants.

The contract must preserve each rule's evaluation subject and current executable
owner.

---

## 9. Rule Identity Boundary

Stable rule identity is now justified by a concrete consumer:

```text
live Agent constraint feedback
```

PR1 does not freeze actual rule IDs.

PR1 freezes naming principles.

Existing document-local Order Domain labels such as `ID1`, `S1`, `C3`, `P3`,
and `E5` are historical navigation labels within
`docs/domain/order_domain_v1_rules.md`. They are not automatically Stage 4B.5
stable rule identities.

Preserve:

```text
existing prose label
!=
future stable correctness rule identity
```

PR2 may adopt the same label only after explicitly reviewing and adopting the
same semantic identity. PR1 does not make that decision.

A valid rule identity should:

1. represent one source-grounded semantic assertion;
2. remain stable across implementation refactors that preserve meaning;
3. belong to an explicit contract identity and version;
4. identify its evaluation subject;
5. remain separate from technical outcome and policy vocabulary;
6. keep superficially similar sequence assertions separate when they belong to
   different owners or times;
7. not imply exhaustive evaluation or stable first-failure priority unless that
   priority is separately contracted.

Rule identity must remain distinct from:

```text
technical status
SemanticOutcomeCode
admission disposition
RuntimeAction
recovery strategy
retry classification
```

The complete ID vocabulary is a PR2 responsibility.

---

## 10. Contract Representation Direction

The preferred first implementation direction is:

```text
canonical immutable data-only typed Python
```

Reasons:

- fits the current Python runtime and stable enums;
- preserves Decimal / Money semantics;
- requires no new dependency;
- supports direct parity tests;
- avoids a second manually maintained JSON/YAML authority.

The contract must not contain:

- callbacks;
- executable predicates;
- evaluator methods;
- aggregate mutation;
- admission actions;
- policy methods;
- retry or recovery instructions;
- dependency-injected runtime behavior.

If an interoperability artifact is later required, it should be generated
deterministically from the canonical contract instead of maintained as a second
source of truth.

---

## 11. RuleEvaluationEvidence Direction

The smallest future rule-evaluation evidence concept is:

```text
contract identity
contract version
rule identity
evaluation result
```

A subject/correlation identity may also be necessary when evidence and outcome
travel independently.

### 11.1 Compass-first feasibility

`FullProofValidator` is the safest first producer because the producer branch
already owns:

- the exact check;
- the compared typed facts;
- the candidate identity;
- the validation verdict later interpreted by validation policy.

This can potentially produce sibling typed rule evidence without changing the
existing semantic allow/block decision.

### 11.2 Aggregate-domain limitation

Current aggregate command failures do not provide exact typed rule identity.

Examples include:

- illegal command state;
- invalid normalized amount;
- full-payment mismatch.

Adding a typed domain-rejection producer would change the current producer
surface and requires a separately approved architecture decision.

PR1–PR3 do not require that change.

---

## 12. Live SemanticOutcome Relationship

For supported Compass rejections, the intended first consumer direction is
same-process composition:

```text
SemanticOutcome
+
RuleEvaluationEvidence
```

These artifacts remain siblings with separate ownership.

PR1 does not add:

- `rule_id` to `SemanticOutcome`;
- a convenience wrapper;
- a generic Agent result envelope.

Candidate event identity may provide correlation when same-execution provenance
is guaranteed by the producer path.

The exact live composition is a later PR responsibility.

---

## 13. DecisionReceipt / Durability Relationship

`DecisionReceipt` remains compact durable governance evidence.

Stage 4B.5 v0 does not add `rule_id` to:

```text
DecisionReceipt.metadata
DecisionReceipt.evidence_summary
```

as an escape hatch.

Durable rule-level evidence may later support:

- cross-process recovery context;
- historical violated-rule counts;
- Agent/workflow quality analysis.

Those uses require explicit durable coverage, retention, completeness, and
version attribution.

They are future possibilities, not first-slice requirements.

---

## 14. Agent Feedback Boundary

Stage 4B.5 answers:

```text
Which intended correctness constraint was violated?
```

It does not answer:

```text
May another attempt occur?
How many attempts?
What backoff?
Should state be reloaded?
What fallback should run?
How should the Agent repair its reasoning?
```

A valid live flow is:

```text
candidate
→ current correctness enforcement
→ typed rule-level violation evidence
→ live Agent feedback
→ Agent independently generates another candidate
→ the same correctness/admission boundaries execute again
```

Rule feedback constrains candidate space.

It does not authorize retry.

---

## 15. PR1 Documentation Alignment Boundary

PR1 may perform narrow current-authority alignment for Stage 4B.5 status and
navigation.

Candidate files include:

```text
docs/roadmap/implementation_roadmap.md
docs/roadmap/compass_runtime_roadmap.md
docs/README.md
docs/roadmap/README.md
docs/implementation_notes/README.md
```

Historical Stage 4A / 4B / 4B.1 / 4B.2 closeouts must not be rewritten.

The historical Stage 4B.5 candidate draft must remain historical.

Normative domain wording in:

```text
docs/domain/order_domain_v1_rules.md
```

may receive only explicitly approved narrow corrections necessary to align:

- candidate identity versus accepted-event status;
- normalized-positive money semantics;
- full-payment trust-chain qualification;
- order identity enforcement placement.

No broader domain redesign is authorized.

---

## 16. Non-Goals

PR1 does not:

- implement the contract;
- implement stable rule IDs;
- implement rule evaluation;
- change `OrderAggregate`;
- change Money semantics;
- change Compass Layer 1 semantics;
- change `SemanticOutcome`;
- change `DecisionReceipt`;
- change `DiagnosticTrace`;
- change persistence/concurrency admission;
- change idempotency behavior;
- add a migration;
- add a dependency;
- implement retry or recovery;
- modify an Agent candidate;
- import Stage 4B.3 responsibility.

---

## 17. Stop Conditions

Stop and request human review if future work requires:

- changing current domain or Money behavior;
- changing Compass allow/block semantics;
- changing admission/idempotency behavior;
- changing SemanticOutcome / DecisionReceipt / DiagnosticTrace;
- parsing exception or reason strings for rule identity;
- treating untyped metadata shapes as stable rule identity;
- making the contract executable authority;
- a second hand-maintained JSON/YAML rule source;
- retry / recovery / policy ownership;
- automatic Agent correction;
- freezing IDs without a clear source-grounded subject;
- claiming parity while normative and executable meaning disagree.

PR2 must not begin until the PR1 semantic corrections and rule-identity
principles have received human review.

---

## 18. PR1 Completion Boundary

PR1 is complete when:

1. current enforcement ownership is explicitly documented;
2. domain command rejection and Compass BLOCK are clearly separated;
3. correctness categories are explicitly separated;
4. the four human semantic corrections are recorded;
5. the rule-identity principles are reviewable;
6. live Agent constraint feedback is recorded as a concrete consumer;
7. aggregate-domain live evidence limitations are explicit;
8. admission/idempotency/durability/policy/retry remain outside the first slice;
9. PR2–later sequencing is documented; and
10. no production behavior changed.

PR1 does not claim that a production Order Correctness Contract,
RuleEvaluationEvidence, or live Agent feedback path already exists.
