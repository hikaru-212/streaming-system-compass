# Semantic Admission Glossary

[← Back to Semantic Admission Index](README.md)

This glossary defines the core vocabulary used in the Semantic Admission section of the Compass project.

The glossary is intentionally public-facing. It defines the conceptual language of the project, but it does not define complete implementation schemas, validator algorithms, or enforcement internals.

The terms are grouped into four layers:

1. **System Truth & Admission Core** — the base vocabulary for candidates, accepted facts, durable truth, and semantic admission.
2. **Technical & Semantic Concurrency Control** — the vocabulary for conflicts, ordering, stale reads, and meaning-preserving admission under concurrent proposals.
3. **Storage, Authority & Evidence Boundaries** — the vocabulary for CRUD integration, mutable state, destructive updates, authority checks, and admission evidence.
4. **Multi-Agent Semantic Contracts & Governance** — the vocabulary for shared context, shared contracts, agent claims, evidence freshness, and workflow-level correctness.

---

## 1. System Truth & Admission Core

### Candidate Artifact

A candidate artifact is any output, action, event, claim, plan, or generated object that has been proposed but not yet admitted as trusted system truth.

Examples include:

- candidate event
- candidate action
- candidate checkout
- candidate summary
- candidate tool call
- candidate agent plan

A candidate artifact may be useful, executable, or plausible.

That does not make it accepted truth.

### Candidate Action

A candidate action is an action proposed by an agent, workflow, API request, or automation process before the system has formally accepted it as valid.

A candidate action may be executable, but executability is not the same as admissibility.

Examples:

- `ALTER_COLUMN TableA.amount TO DECIMAL`
- `DROP_TABLE TableA`
- `UPDATE customer_id=123 status='approved'`
- `CreateOrder(product_id=A)`

A candidate action is not system truth.

### Candidate Event

A candidate event is a proposed event that has not yet entered accepted history.

In Compass, a candidate event must pass validation before it becomes part of durable accepted history.

### Accepted Fact

An accepted fact is a state change that the system has formally admitted and committed as durable truth.

The key point is not merely that the write succeeded.

The key point is that the system allowed the action to become trusted state.

### Accepted Business Fact

An accepted business fact is an accepted fact with business meaning.

Examples include:

- order accepted
- inventory reserved
- payment authorized
- refund issued
- product marked purchasable

An accepted business fact may be used by downstream systems, agents, projections, analytics, or audit processes.

### Accepted History

Accepted history is the durable sequence of events or facts the system treats as the source of truth.

Read models, projections, snapshots, analytics, downstream workflows, and future agent decisions may depend on accepted history.

Because of this, accepted history must be protected from semantically invalid candidate events.

### System Truth

System truth is the set of durable facts the system allows other components to rely on.

A tool call result, model output, or workflow step is not system truth by default.

### Semantic Admission

Semantic admission is the process of deciding whether a candidate action, event, claim, or artifact is allowed to become accepted system truth.

It asks:

> Should this candidate be allowed to mutate durable state or become trusted meaning?

Semantic admission is not the same as output evaluation.

It is a boundary decision before or during state mutation, public exposure, or durable admission.

### Admission Boundary

An admission boundary is the system boundary where candidate actions are accepted, rejected, escalated, transformed, or revalidated before they can mutate durable state or become trusted facts.

For state-changing agents, this boundary is critical because the agent may generate action paths dynamically.

### Semantic Correctness

Semantic correctness means that a system state or transformation preserves the intended business meaning, not merely that the code executed successfully.

A pipeline can finish, a schema can match, and a workflow can complete while still producing the wrong business meaning.

### Technical Success

Technical success means the system executed according to an operational signal:

- the tool returned success
- the database committed
- the job completed
- the workflow reached the end
- the final schema matched the expected shape

Technical success does not imply semantic correctness.

### Action Path

An action path is the sequence of operations used to reach a result.

The final state may look correct even when the action path was unsafe.

Example:

- Safe path: `ALTER_COLUMN`
- Unsafe path: `DROP_TABLE` followed by `CREATE_TABLE`

Both may lead to a table with the desired column type, but they do not preserve the same truth.

### Final-State Validation

Final-state validation checks whether the end result looks correct.

It is useful but incomplete.

A correct-looking final state does not prove that the action path was admissible.

### Compass Guard

A Compass Guard is a conceptual admission guard that evaluates whether a candidate action should be allowed to cross a semantic boundary.

It may consider action type, target meaning, required evidence, and escalation conditions.

This glossary defines the concept only. It does not define the full guard implementation.

### Admission Before Mutation

Admission before mutation means the system validates whether an action is allowed before it changes durable state.

This is different from observing the damage after the mutation has already happened.

### Durable State

Durable state is state that persists and may be trusted by future systems.

Examples include:

- database rows
- event logs
- workflow state
- agent memory
- retrieval corpora
- audit records
- snapshots

Durable state requires stronger protection than temporary output.

### Bad State as Future Context

Bad state becomes future context when an invalid fact is admitted into durable systems and later used as evidence by agents, analytics, retrieval, or downstream workflows.

This turns a single bad action into a continuing source of semantic contamination.

### Architectural Over-Trust

Architectural over-trust is the mistake of allowing probabilistic outputs or successful executions to mutate durable state without an explicit admission boundary.

It treats generated actions as if they were already validated facts.

---

## 2. Technical & Semantic Concurrency Control

### Technical Concurrency

Technical concurrency refers to conflicts over write ordering, version continuity, locks, transaction boundaries, or stale state.

Traditional concurrency control usually asks questions such as:

- Did the version change?
- Did another transaction commit first?
- Can this write acquire the lock?
- Is this update based on a stale read?

Technical concurrency control is necessary, but it does not fully determine whether a candidate action is semantically admissible.

### Semantic Concurrency

Semantic concurrency refers to conflicts between multiple candidate actions that may be technically valid but semantically incompatible.

It asks:

> Even if these actions can be ordered, should they all be allowed to become accepted facts?

Semantic concurrency is the admission problem that remains after technical concurrency has controlled write ordering.

### Semantic Conflict

A semantic conflict occurs when two or more candidate actions cannot all become accepted facts without violating business meaning, user intent, domain rules, or accepted-history consistency.

A semantic conflict may exist even when:

- all actions are individually executable
- all requests passed basic validation
- all actors read the same initial state
- the database can serialize the writes
- a lock can determine who writes first

The conflict is not only about timing.

It is about meaning.

### Same-State Different-Intent Collision

A same-state different-intent collision occurs when multiple agents, workflows, or requests observe the same state but propose different target meanings.

Example:

```text
Observed state:
status = CREATED
version = 1
amount = 100.00

Candidate actions:
A: PAY order
B: CANCEL order
C: CHANGE amount
```

From a technical perspective, these actions may all be based on the same version.

From a semantic perspective, they represent incompatible futures.

### Concurrency Admission

Concurrency admission is the boundary where the system decides whether a candidate action can still become the next accepted fact under the current accepted history.

Technical concurrency control protects write ordering.

Semantic admission protects meaning.

Concurrency admission sits between them:

```text
candidate action
→ semantic validation
→ concurrency admission
→ accepted fact
```

In Compass, this distinction matters because a candidate may be semantically valid against an earlier state but no longer admissible after another fact has been accepted.

---

## 3. Storage, Authority & Evidence Boundaries

### CRUD Request

A CRUD request is a request that attempts to create, read, update, or delete mutable state.

In Semantic Admission, a state-changing CRUD request may be treated as a candidate action.

### Request-as-Candidate Mapping

Request-as-candidate mapping is the conceptual step of treating a state-changing request as a candidate action before it mutates durable state.

This allows semantic admission to reason about CRUD-like systems without requiring the public note to prescribe a specific implementation pattern.

### Mutable State

Mutable state is state that can be changed in place.

A mutable row may show the latest value while hiding previous values unless additional audit or history mechanisms exist.

### Destructive State Update

A destructive state update is an in-place state change that overwrites prior state from the primary operational view.

The previous value may still exist in backups, logs, or audit systems, but it is no longer visible as first-class operational history.

### Current Row Is Not History

Current row is not history is the principle that the latest database row does not explain the full sequence of facts that produced it.

A system may know what the state is now without knowing why it became that way.

### Admission Evidence

Admission evidence is the evidence used to decide whether a candidate can become an accepted fact.

Examples include:

- current accepted history
- source snapshot
- inventory observation
- user confirmation
- policy version
- actor identity
- external authority signal

Admission evidence should be trustworthy enough for the boundary it supports.

### Audit Evidence

Audit evidence is evidence preserved so the system can later explain why a candidate was admitted, blocked, retried, or escalated.

Audit evidence is important for root-cause analysis, governance, and trust.

### Immutable History

Immutable history is a durable record of state transitions that is append-only or otherwise protected from silent overwrite.

It provides a stronger evidence boundary than mutable current state alone.

### Truth Source

A truth source is the authority the system relies on for a specific class of facts.

Examples:

- inventory authority
- payment authority
- order authority
- pricing authority
- policy authority

A truth source should not be casually editable by agents whose task depends on that truth.

### Agent Observation Is Not Authority

Agent observation is not authority means that an agent seeing or recording a fact does not automatically make that fact authoritative.

An agent may observe:

```text
Product A had stock at T1.
```

That does not mean the agent can declare:

```text
Product A is purchasable at commit time.
```

### Tool Permission Is Not Business Authority

Tool permission is not business authority means that the technical ability to call a tool does not imply the semantic right to create or modify a business fact.

An actor may technically call an endpoint, but still lack authority to produce that kind of accepted fact.

### Business Authority

Business authority is the right to create, modify, or certify a specific class of business fact.

For example, an inventory authority may update stock, while a recommendation agent may only present candidate options.

### Authority-Aware Admission

Authority-aware admission is admission that checks not only whether a candidate action appears valid, but whether the actor has the semantic authority to produce that kind of fact.

### Truth-Source Tampering

Truth-source tampering occurs when an agent or workflow changes the source of truth that should have independently constrained its action.

The key risk is not only mutation.

The key risk is mutation of the evidence boundary itself.

### Source-of-Truth Contamination

Source-of-truth contamination occurs when a truth source is polluted by a candidate workflow, agent output, or unsupported action, and is later used as trusted evidence.

This can make invalid actions appear valid after the fact.

### Circular Evidence

Circular evidence occurs when a candidate action relies on evidence that was produced or modified by the same workflow that is trying to pass admission.

Circular evidence weakens independent validation.

### Self-Satisfying Candidate

A self-satisfying candidate is a candidate action that attempts to modify the evidence, precondition, or truth source required for its own admission.

Example:

```text
Product is out of stock.
Agent modifies or requests modification of stock.
Order candidate now appears admissible.
```

A self-satisfying candidate is a semantic admission risk.

### Task Completion Is Not Truth Preservation

Task completion is not truth preservation means that an agent completing its assigned task does not prove that the system preserved business truth.

An agent may complete a workflow by changing the conditions that made the workflow invalid.

### Mutable State Is Not Independent Evidence

Mutable state is not independent evidence means that a current mutable value should not automatically be trusted as independent proof if the candidate workflow may have influenced that value.

### State Mutation Requires Admission

State mutation requires admission means that any action changing durable business state should pass an explicit boundary before it becomes trusted system truth.

### Event-Driven Core

An event-driven core is a system design where important business state changes are represented as events or durable facts rather than only mutable current rows.

In Compass, this provides a natural place for semantic admission.

### CRUD Table as Projection

CRUD table as projection is the pattern of treating mutable tables as derived views of accepted facts rather than as the sole authority.

This can preserve compatibility with existing tools while keeping stronger trust boundaries behind the scenes.

---

## 4. Multi-Agent Semantic Contracts & Governance

### Shared Context

Shared context is the information made available across agents, workflows, or harnesses.

It may include:

- conversation history
- tool outputs
- intermediate observations
- session state
- workflow memory
- retrieved documents

Shared context helps agents coordinate.

It does not automatically define what agents are allowed to claim or commit.

### Shared Semantic Contract

A shared semantic contract defines what agents are allowed to claim, what evidence must be attached, what must be revalidated, and what can become an accepted business fact.

Shared semantic contract is not the same as shared context.

### Shared Context Is Not Shared Contract

Shared context is not shared contract means that agents seeing the same information does not guarantee that they share the same rules for using it.

Shared context tells agents what was observed.

Shared contract defines what may be safely claimed, executed, or admitted.

### Shared Compass Layer

A Shared Compass Layer is a conceptual semantic contract layer for multi-agent workflows.

It protects the transition from agent-generated claims and actions into accepted business facts.

### Agent Observation

An agent observation is information an agent reads, retrieves, receives, or infers during a workflow.

An observation may support a claim, but it is not automatically an accepted fact.

### Structured Claim

A structured claim is a machine-readable representation of a semantic assertion.

For example:

```json
{
  "subject": "Product A",
  "predicate": "had_stock",
  "value": 1,
  "observed_at": "T1"
}
```

Structured claims are easier to verify, route, audit, and convert into runtime decisions than free-form text.

### Claim Strength

Claim strength refers to how strong a statement is relative to its evidence.

Example progression:

```text
Product A was observed.
Product A had stock at T1.
Product A is available.
Product A is purchasable now.
Order for Product A is accepted.
```

Each step requires stronger evidence and stronger admission.

### Semantic Escalation

Semantic escalation happens when a later step turns a weaker observation into a stronger business claim without the required evidence or revalidation.

Example:

```text
Product A had stock at T1.
→ Product A is purchasable now.
```

### Evidence Boundary

An evidence boundary checks whether an output, claim, or action is supported by sufficient evidence.

### Claim Boundary

A claim boundary checks whether an agent’s claim exceeds the evidence available to it.

### Candidate Action Boundary

A candidate action boundary checks whether an agent-generated action may become a candidate for state mutation.

### Commit-Time Admission Boundary

A commit-time admission boundary checks whether a candidate action can become an accepted business fact under the latest relevant authority.

### Runtime Revalidation Boundary

A runtime revalidation boundary checks whether changed state invalidates an earlier assumption.

### Search-Time Evidence

Search-time evidence is evidence observed when a product, option, document, or candidate is first found.

Search-time evidence may become stale before commit time.

### Commit-Time Truth

Commit-time truth is the latest relevant truth required when an action is about to become an accepted fact.

Search-time evidence is not commit-time truth.

### Evidence Freshness

Evidence freshness describes whether evidence is recent enough to support the claim or action being admitted.

Freshness requirements depend on risk and domain.

### Purchasable

Purchasable is a semantic claim that a product can be bought under current relevant business facts.

It should not be treated as a simple synonym for visible, searchable, or previously observed.

### Recommendation Is Not Reservation

Recommendation is not reservation means that showing or suggesting an item does not reserve it, guarantee it, or authorize purchase.

Cf. Shared Context Is Not Shared Contract.

### Intent Drift

Intent drift occurs when an agent transforms the user’s confirmed intent into a different action without renewed confirmation.

Example:

```text
User selected Product A.
Product A is unavailable.
Agent buys Product B without asking.
```

### Workflow-Level Semantic Drift

Workflow-level semantic drift occurs when a multi-step workflow gradually moves away from the original business meaning even though each local step appears reasonable.

### Local Correctness

Local correctness means one agent, function, or step appears correct in isolation.

Local correctness does not guarantee workflow-level correctness.

### Workflow-Level Correctness

Workflow-level correctness means the full chain of agents, claims, evidence, and actions preserves the intended business meaning.

### Agent-Generated Possibility

An agent-generated possibility is an option, plan, candidate, or claim produced by an agent before admission.

An agent-generated possibility may become useful input, but it is not an accepted fact.

### Accepted Public-Facing Meaning

Accepted public-facing meaning is generated meaning that the system allows users or external parties to rely on.

This term is useful for generated summaries, AI overviews, recommendations, and public claims.

---

## Reusable Principles

```text
A candidate artifact is not an accepted fact.

Technical success does not imply semantic correctness.

Shared context is not shared contract.

Search-time evidence is not commit-time truth.

A recommendation is not a reservation.

Tool permission is not business authority.

Task completion is not truth preservation.

Current row state is not history.

Mutable state is not independent evidence.

Agent observation is not authority.
```
