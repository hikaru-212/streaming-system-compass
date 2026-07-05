# Case Study: Shared Context Is Not Shared Contract

[← Back to Semantic Admission Index](README.md)

**Recorded on:** 2026-06-30  

## Purpose

This note records a case study about extending Semantic Admission from single candidate actions into multi-agent workflows.

The motivating question is:

```text
If multiple agents share context, tools, and workflow memory,
is that enough to make their combined actions safe for commercial systems?
```

The answer is no.

Shared context helps agents coordinate what they have seen.

But commercial workflows require another layer:

```text
shared semantic contract
```

A shared semantic contract defines what agents are allowed to claim, what evidence is required, what must be revalidated, and what can become an accepted business fact.

The core principle is:

```text
Shared context is not shared contract.
```

---

## Origin of This Note

This note was triggered by public discussion around agentic commerce.

The specific product or team was not the important part.

The important architectural question was:

```text
If I were building an agentic commerce system,
where would the real correctness boundary be?
```

The obvious first answers are:

```text
agents need shared context
agents need orchestration
agents need tool access
agents need workflow memory
```

Those are all necessary.

But commercial workflows require more than coordination.

Agents eventually produce claims and actions that affect real business state:

```text
what can be shown
what can be recommended
what can be purchased
what can be charged
what can become an accepted order
```

That makes the problem close to the existing Compass principle:

```text
candidate action is not an accepted fact
```

The difference is that the candidate is no longer only a single event.

In a multi-agent workflow, the candidate may be a chain of claims and actions produced across a DAG.

This note treats agentic commerce as a case study for extending Compass from single-event admission into shared semantic contracts.

---

## Real Problem

In a multi-agent commerce workflow, agents do not only exchange information.

They transform observations into claims, and claims into actions.

For example:

```text
Search Agent observes Product A.
Inventory Agent reports Product A had stock.
Recommendation Agent shows Product A to the user.
Checkout Agent starts a purchase candidate.
Order Agent attempts to create an accepted order.
```

Each step may be locally reasonable.

But the whole workflow can still become semantically wrong if a weak observation is silently upgraded into a stronger business claim.

A shared context may say:

```text
Product A had stock = 1 at time T1.
```

That does not automatically mean:

```text
Product A is purchasable now.
```

And it definitely does not mean:

```text
Create accepted order for Product A.
```

This is the gap between shared context and shared contract.

---

## Motivating Scenario

A user asks:

```text
Find me a black hoodie under $100.
```

A possible agent workflow is:

```text
User Intent
   ↓
Search Agent
   ↓
Inventory Agent
   ↓
Recommendation Agent
   ↓
Checkout Agent
   ↓
Payment Agent
   ↓
Order Agent
```

At first glance, the workflow looks reasonable.

The Search Agent finds matching products.

The Inventory Agent checks stock.

The Recommendation Agent shows products to the user.

The Checkout Agent starts the purchase flow.

The Payment Agent attempts payment.

The Order Agent attempts to create the order.

The hidden risk is that the meaning of the claim changes as it moves through the workflow.

---

## Failure Mode: Search-Time Evidence Becomes Commit-Time Truth

Suppose the Inventory Agent observes:

```text
Product A stock = 1 at T1.
```

The Recommendation Agent shows Product A to the user.

The user chooses Product A.

At T2, the Checkout Agent attempts to place the order.

Between T1 and T2, another purchase may have consumed the final unit.

The original observation may have been true:

```text
Product A had stock at T1.
```

But the later claim may be false:

```text
Product A is purchasable at T2.
```

The unsafe semantic path is:

```text
stock = 1 at T1
   ↓
Product A is available
   ↓
Product A can be purchased
   ↓
Create accepted order
```

Each transition may look small.

Together, they produce semantic escalation.

---

## Semantic Escalation

Semantic escalation happens when a later step turns a weaker observation into a stronger business claim without the required evidence or revalidation.

Example:

```text
Observation:
Product A had stock at time T1.

Claim:
Product A is available.

Stronger claim:
Product A is purchasable now.

Accepted fact:
An order for Product A has been created.
```

The problem is not that the first observation was wrong.

The problem is that the workflow upgraded the observation without proving that the stronger claim was still valid.

This is especially dangerous because many commerce facts are time-sensitive:

```text
inventory
price
discount
shipping eligibility
payment authorization
reservation state
user eligibility
```

Therefore:

```text
search-time evidence ≠ commit-time truth
visible product ≠ purchasable product
recommendation ≠ reservation
candidate checkout ≠ accepted order
shared context ≠ shared contract
```

---

## Corrected Framing

The system should distinguish between different semantic levels.

```text
Search result:
Product A matched the user query.

Inventory observation:
Product A had stock = 1 at T1.

Recommendation:
Product A may be shown as a candidate option.

Checkout candidate:
The user wants to buy Product A.

Commit-time admission:
Product A still has inventory, and the order can be accepted.
```

The important boundary is the transition from candidate to accepted fact.

A product being visible to an agent does not make it purchasable.

A recommendation does not reserve inventory.

A checkout candidate does not become an accepted order until commit-time admission succeeds.

---

## Shared Compass Layer

A Shared Compass Layer is a semantic contract layer for multi-agent workflows.

Its role is not merely to store context or orchestrate agents.

Its role is to protect the boundary between:

```text
agent-generated candidates
```

and:

```text
accepted business facts
```

In a single-event Compass model, the question is:

```text
Can this candidate event enter accepted history?
```

In a multi-agent workflow, the question becomes:

```text
Can this chain of agent-generated claims and actions preserve business meaning
before any irreversible or durable fact is accepted?
```

This note intentionally does not prescribe a concrete implementation.

The reusable point is the boundary:

```text
Agents may coordinate through shared context,
but their claims and actions still require semantic admission.
```

---

## Example: Purchasable Product

In agentic commerce, `purchasable` should not be treated as a simple field.

It is a semantic claim.

A product may be purchasable only when the relevant business facts still support that claim.

At minimum, this may involve:

```text
product existence
valid price
available inventory
fresh enough evidence
purchase eligibility
shipping feasibility
valid payment path
no conflicting reservation
commit-time validation
```

The public lesson is not a specific contract schema.

The public lesson is:

```text
Purchasable is not merely observed.
Purchasable must be admitted.
```

---

## Boundary Types

A multi-agent workflow may need several conceptual boundaries.

### Evidence Boundary

Checks whether an agent output is supported by evidence.

### Claim Boundary

Checks whether an agent's claim exceeds the available evidence.

### Candidate Action Boundary

Checks whether an agent-generated action is allowed to become a candidate for state mutation.

### Commit-Time Admission Boundary

Checks whether the candidate action can become an accepted business fact under current authority.

### Runtime Revalidation Boundary

Checks whether changed state invalidates an earlier assumption.

These are conceptual boundary types.

This note does not define their final API, schema, enum set, or runtime implementation.

---

## Relationship to Current Compass Project

The current Streaming System + Compass project already contains the core principle:

```text
candidate action is not an accepted fact
accepted history is authority
technical success does not imply semantic correctness
```

The multi-agent extension applies the same principle at workflow level.

Current Compass Layer 1 asks:

```text
Is this candidate event acceptable?
```

A Shared Compass Layer asks:

```text
Is this multi-agent workflow preserving the meaning required
for an acceptable business outcome?
```

This does not replace the current project.

It extends the same philosophy from event admission into agentic workflow governance.

---

## Relationship to Snapshot and Runtime Validation

The project’s snapshot trust work contains a similar principle:

```text
snapshot ≠ authority
```

A snapshot is useful, but it is derived, traceable, and subordinate to accepted history.

The same pattern applies to agent observations:

```text
agent observation ≠ accepted business fact
```

An inventory result, search result, or recommendation is evidence observed at a time.

It should not become commit-time truth unless the required contract and admission boundary allow it.

The reusable principle is:

```text
Derived or intermediate state must not be promoted into authority without validation.
```

---

## Relationship to Agent Orchestration Systems

Agent orchestration systems may provide:

```text
shared context
shared tools
shared sessions
shared control
workflow coordination
governance hooks
```

These are important.

However, commercial workflows require another question:

```text
What are agents allowed to claim or commit?
```

A shared context layer may answer:

```text
What did the agents observe?
```

A shared control layer may answer:

```text
Which agent can call which tool?
```

A shared semantic contract answers:

```text
What does this claim mean?
What evidence supports it?
What must be revalidated?
What may become an accepted business fact?
```

Compass is therefore not another harness.

It is a semantic admission layer for agent-generated claims and actions.

---

## Core Principles

```text
Shared context is not shared contract.

A search result is not a purchase guarantee.

Search-time evidence is not commit-time truth.

A recommendation is not a reservation.

A candidate checkout is not an accepted order.

A locally valid agent output is not workflow-level correctness.

An agent-generated action is not an accepted business fact.

Derived or intermediate state must not be promoted into authority without validation.
```

---

## Why This Matters for Commercialization

A multi-agent demo can succeed even when its business semantics are unsafe.

A demo may show:

```text
The agent finds a product.
The user selects it.
The agent places an order.
The workflow completes successfully.
```

But a commercial system must ensure:

```text
the product was actually purchasable
the inventory was still available
the price was still valid
the payment was authorized correctly
the order was not duplicated
the accepted order reflects commit-time truth
```

Without a shared semantic contract, the system may fail under:

```text
concurrency
stale data
retry
partial failure
conflicting reservations
unsupported claims
tool inconsistency
state drift
```

The point is not that orchestration is unimportant.

The point is that orchestration alone does not define business truth.

---

## Future Role in the Repository

This note belongs in the Semantic Admission section as a public case study.

It does not define the final implementation API.

It does not define the final contract schema.

It does not claim that the current implementation already supports multi-agent commerce.

It records why the existing Compass principle may generalize from event admission into commercial multi-agent workflows.

A future private or implementation-facing note may define more concrete designs.

---

## Summary

This note records one architectural realization:

```text
Multi-agent systems do not only need shared context.
They need shared semantic contracts.
```

For agentic commerce, this means agents must share enforceable definitions of:

```text
available
purchasable
reserved
paid
accepted
blocked
refunded
cancelled
```

The long-term role of Compass is therefore not only to validate events.

It is to protect business meaning as candidate claims and actions move through distributed, agent-generated workflows.

Compass protects the transition from:

```text
agent-generated possibility
```

to:

```text
accepted business fact
```
