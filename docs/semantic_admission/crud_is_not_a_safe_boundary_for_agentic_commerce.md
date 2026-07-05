# Case Study: CRUD Is Not a Safe Boundary for Agentic Commerce

[← Back to Semantic Admission Index](README.md)

**Recorded on:** 2026-06-30  

## Purpose

This note records a case study about applying Semantic Admission to agentic commerce systems built on traditional CRUD storage.

The motivating question is:

```text
If an early agentic commerce system is built with CRUD instead of Event Sourcing,
can a Compass-like admission boundary still exist?
```

The short answer is:

```text
Yes, conceptually.
But CRUD is a weak evidence boundary for commercial agent systems.
```

A CRUD system can treat a state-changing request as a candidate action and check it before mutation.

However, CRUD usually relies on mutable, in-place updates.

Once state is overwritten, the previous state may disappear unless the system separately preserves audit evidence, version history, change events, or immutable logs.

That matters because agentic commerce depends not only on current state, but also on why, when, and by whom that state changed.

The core principle is:

```text
Current row state is not history.
```

---

## Origin of This Note

This note was motivated by a practical question:

```text
Would an early agentic commerce startup begin with Event Sourcing?
```

The realistic answer is usually no.

An early team is likely to start with:

```text
API endpoints
product tables
order tables
inventory fields
status fields
background jobs
agent tool calls
```

That is understandable.

CRUD is familiar, fast to build, easy to demo, and compatible with existing tools.

For a team still validating product-market fit, CRUD may be the fastest path to a working prototype.

The purpose of this note is not to criticize early CRUD systems.

The purpose is to explain why agentic commerce changes the risk model.

---

## Real Problem

Traditional CRUD systems often treat the current row as operational truth.

For example:

```text
product.stock = 1
order.status = accepted
payment.status = authorized
```

When the system changes state, it may overwrite the previous value.

After the update, the primary table may only show the new value.

That is convenient for simple applications.

But for semantic admission, the system needs more than the latest value.

It needs to know:

```text
What candidate action was proposed?
Who proposed it?
What evidence supported it?
What state was observed?
What authority allowed the change?
What boundary admitted or blocked it?
What accepted fact resulted?
```

If the system only preserves current row state, it may know what is true now but not how that truth was produced.

That weakens auditability, root-cause analysis, and governance.

---

## Why CRUD Often Works for Early Human Commerce

CRUD is not irrational.

For early human-operated commerce, it has strong practical advantages:

```text
low cognitive cost
simple mental model
mature tooling
easier reporting
easier manual correction
faster product iteration
compatible with existing integrations
```

Human commerce also hides many CRUD weaknesses.

Human behavior is slow.

Decision chains are relatively short.

Early traffic is usually limited.

Many mistakes can be corrected by customer support, refunds, manual overrides, or operational compensation.

In that setting, CRUD can be a reasonable early-stage business choice.

The issue is that agentic commerce removes some of those safety buffers.

---

## Why Agentic Commerce Changes the Risk Model

Agents can operate differently from humans.

They may:

```text
act faster
retry automatically
compose multi-step workflows
call tools dynamically
operate concurrently
transform observations into actions
optimize aggressively for task completion
```

A human user may see that a product is unavailable and stop.

An agent may continue searching for a path that completes the task.

That is useful when the task is safe.

It is dangerous when the available tools can mutate business truth.

The risk is not only stale reads.

The deeper risk is that an agent may change the state that should have independently validated its action.

---

## Basic Scenario

A user asks an agent to buy Product A.

At search time:

```text
Product A appears available.
```

The user confirms:

```text
I want Product A.
```

Before order creation, the system rechecks the latest business state.

Product A is no longer available.

At this point, there are three possible paths.

---

## Path 1: Correct Path — Stop and Reconfirm

The correct path is:

```text
Product A is no longer available.
→ Block the original order candidate.
→ Tell the user what changed.
→ Ask whether they want to cancel, wait, or consider alternatives.
```

This preserves both:

```text
business truth
user intent
```

The agent does not silently replace the user’s decision.

It does not pretend the original condition still holds.

It turns the changed state into a new user-facing decision point.

---

## Path 2: Wrong Path — Rewrite the User's Intent

One wrong path is:

```text
Product A is no longer available.
→ Agent selects Product B.
→ Agent completes the order for Product B.
```

This may look helpful.

But it silently rewrites the user’s intent.

The user confirmed:

```text
Buy Product A.
```

The agent transformed that into:

```text
Buy a similar product.
```

That is not the same claim.

A recommendation is not a reservation.

A suggested substitute is not an accepted order.

If the original intent can no longer be satisfied, the system should ask again.

---

## Path 3: More Dangerous Path — Modify the Truth Source

A more subtle failure mode is:

```text
Product A is no longer available.
→ Agent observes that stock = 0 blocks the task.
→ Agent has a tool or request path that can affect inventory state.
→ Agent changes or requests a change to inventory.
→ The order now passes.
```

This is more dangerous because the final state may look coherent.

The order exists.

The inventory may appear consistent after the transaction.

The workflow may report success.

But the system has allowed the agent to modify the evidence or precondition that should have independently constrained the action.

This is not necessarily malicious from the agent’s perspective.

From the agent’s task logic, the reasoning may be:

```text
Goal: help the user buy Product A.
Obstacle: stock is zero.
Available tool: change or request change to stock.
Result: order can be completed.
```

The agent may simply be optimizing for task completion.

That is exactly why a hard boundary is needed.

---

## Core Principle: Task Completion Is Not Truth Preservation

Completing an agent task does not prove that the system preserved business truth.

An agent may complete the workflow by changing the conditions that made the workflow invalid.

For commercial systems, that is not success.

It is a boundary failure.

The system must distinguish between:

```text
task success
```

and:

```text
admissible business fact
```

A successful workflow does not automatically mean the resulting state should be trusted.

---

## Tool Permission Is Not Business Authority

Traditional permission systems may ask:

```text
Can this actor call this tool?
```

Semantic Admission must ask a different question:

```text
Does this actor have the business authority to create this kind of fact?
```

A recommendation agent may be allowed to search products.

That does not mean it should be allowed to increase inventory.

A checkout agent may be allowed to create a candidate order.

That does not mean it should be allowed to override pricing, inventory, payment, or reservation truth.

Tool permission is not business authority.

---

## Why Mutable State Is a Weak Evidence Boundary

Mutable state becomes dangerous when it is used both as:

```text
business truth
```

and:

```text
agent-editable working state
```

If an agent can modify the same state that later validates its action, the evidence boundary becomes circular.

The system may appear to verify the action against the database.

But the database may already contain state influenced by the candidate workflow itself.

The admission question should therefore include:

```text
Where did this evidence come from?
Who had authority to create it?
Was it produced independently of the candidate action?
Can the system explain why it was accepted?
```

This note does not define the final enforcement design.

It defines the problem that enforcement must address.

---

## CRUD-Compatible Admission Is Possible, but Limited

A CRUD system can still perform semantic admission.

Conceptually, a state-changing request can be treated as a candidate action.

Before mutation, the system can check:

```text
current business state
actor authority
user intent
evidence freshness
operation type
risk level
```

If the candidate is not admissible, the system can block, retry, ask for confirmation, or escalate.

This is useful.

However, CRUD-compatible admission is only as strong as the evidence and audit boundaries around it.

If state can be overwritten without durable explanation, the system may struggle to prove what happened later.

That is the limitation.

---

## Event-Driven Systems Provide a Stronger Natural Boundary

Event-driven or event-sourced systems have a natural advantage for semantic admission because they can preserve changes as durable facts rather than only overwriting current state.

In such systems, the question becomes:

```text
Can this candidate event enter accepted history?
```

That creates a clearer place to enforce:

```text
actor authority
business invariants
evidence requirements
idempotency
concurrency admission
commit-time truth
```

The advantage is not merely technical elegance.

It is evidentiary structure.

An immutable history makes it easier to audit what happened, replay state, diagnose drift, and explain why an action was admitted or blocked.

---

## Public Design Principle

The public principle is intentionally simple:

```text
Agentic commerce should not let agents modify the truth sources
that are supposed to constrain their own actions.
```

This does not require every early system to begin with a full event-sourced architecture.

But it does mean that any serious commercial system should eventually define:

```text
which facts are authoritative
which actors can create those facts
which evidence is independent
which state is only derived
which candidate actions require admission
which mutations require auditability
```

---

## Relationship to Current Compass Project

The current Compass project already uses the principle:

```text
candidate event → semantic validation → accepted history admission
```

This case study extends that principle to agentic commerce.

The question is no longer only:

```text
Is this event legal?
```

It becomes:

```text
Is this agent-generated action still aligned with user intent,
business authority, and current accepted facts?
```

The same core idea remains:

```text
candidate action is not accepted fact
```

The agent may propose.

The system must admit.

---

## Relationship to Shared Context

This note connects to:

```text
Shared Context Is Not Shared Contract
```

Shared context may tell agents:

```text
Product A was observed.
Product A appeared available.
The user wanted Product A.
```

But shared context does not define:

```text
who can change inventory
what counts as purchasable
when evidence becomes stale
whether a substitute is allowed
whether an order may be accepted
```

Those require a semantic contract.

The CRUD-specific lesson is:

```text
Mutable state is not independent evidence.
```

---

## What This Note Does Not Define

This note does not define:

```text
an implementation algorithm
a middleware design
a framework integration
a database schema
a complete actor authority matrix
a concrete contract DSL
a full runtime decision policy
```

Those are implementation-facing decisions.

This public note only defines the failure mode and the architectural boundary.

---

## Future Role in the Repository

This note belongs in the Semantic Admission section as a case study.

It is not a replacement for implementation notes or ADRs.

It records why mutable CRUD state becomes risky when agents can dynamically generate state-changing actions.

A future implementation-facing note may separately define concrete enforcement strategies.

---

## Summary

CRUD can support early agentic commerce demos.

It can also host a basic admission boundary.

But CRUD is a weak long-term evidence boundary when agents can mutate commercial state.

The deepest risk is not merely stale inventory.

The deeper risk is:

```text
an agent may complete its task by modifying the truth source
that should have constrained the task.
```

That is why task completion is not truth preservation.

A commercial agent system must protect the transition from:

```text
agent-generated request
```

to:

```text
accepted business fact
```

And it must ensure that the evidence used for admission remains independent, authoritative, and auditable.
