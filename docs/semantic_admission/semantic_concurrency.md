# Semantic Concurrency

[← Back to Semantic Admission Index](README.md)

## Why Traditional Concurrency Is Not Enough

Traditional concurrency control is necessary, but it is not the whole problem for state-changing agents.

Optimistic locking can detect that another write has already changed the version.

Pessimistic locking can serialize access so that only one transaction mutates a resource at a time.

Both mechanisms are useful.

But they mainly answer technical questions:

* Who writes first?
* Did the version change?
* Can this transaction acquire the lock?
* Is this update based on stale state?
* Can the database serialize these writes safely?

They do not fully answer the semantic question:

> Should this candidate action still be allowed to become accepted truth?

That question becomes especially important when agents generate state-changing actions dynamically.

## The Same-State Different-Intent Problem

Consider an order with the following state:

```text
order_id = order-001
status = CREATED
version = 1
amount = 100.00
```

Now imagine three agents or workflows observe the same state at roughly the same time.

They each propose a different candidate action:

```text
Agent A → PAY order
Agent B → CANCEL order
Agent C → CHANGE amount
```

From a technical perspective, all three candidates may be based on the same version.

From a semantic perspective, they represent different futures.

The system cannot blindly treat them as equivalent writes.

## What Optimistic Locking Can Do

With optimistic locking, the system may accept whichever candidate commits first.

For example:

```text
Agent A pays the order first.
status = PAID
version = 2
```

Then Agent B and Agent C may fail because their expected version was `1`, but the current version is now `2`.

This protects version continuity.

But it does not fully explain what should happen next.

Should Agent B retry cancellation against the paid order?

Should Agent C retry amount modification after payment?

Should both be rejected?

Should one be escalated?

Should the system check whether the original user intent is still valid?

Optimistic locking detects stale writes, but it does not classify the semantic relationship between the losing candidates and the newly accepted fact.

## What Pessimistic Locking Can Do

With pessimistic locking, the system may allow only one agent to hold the lock at a time.

This prevents simultaneous mutation.

But it does not eliminate semantic conflict.

It only serializes the conflict.

For example:

```text
Agent A acquires the lock and pays the order.
Agent B waits.
Agent C waits.
```

After Agent A commits, Agent B and Agent C still need to be interpreted against the new accepted history.

The system still has to decide whether their original candidate actions remain admissible.

The lock solved timing.

It did not solve meaning.

## Semantic Concurrency

Semantic concurrency is the problem of deciding whether multiple candidate actions are compatible as accepted facts.

It asks:

> Even if the system can order these actions technically, should they all be allowed to become durable truth?

This is different from ordinary write concurrency.

Technical concurrency control protects ordering, isolation, and version continuity.

Semantic concurrency control protects business meaning, accepted-history consistency, and intent validity.

## Candidate Validity Can Expire

A candidate action may be valid against the state it originally observed but invalid after another fact is accepted.

For example:

```text
At version 1:
CANCEL order may be valid.

After PAY is accepted at version 2:
CANCEL order may no longer be valid,
or it may require a different business process such as refund.
```

The candidate did not merely lose a race.

Its meaning changed.

This is why retrying a stale candidate blindly can be dangerous.

A retry should not mean:

```text
Try the same write again until it succeeds.
```

It should mean:

```text
Re-evaluate the candidate against the current accepted history.
```

## Semantic Admission Under Concurrency

Semantic admission is the boundary that decides whether a candidate action can become an accepted fact.

Under concurrency, admission must consider both:

```text
technical continuity
+
semantic compatibility
```

A candidate should not be admitted merely because it can still be written.

It should be admitted only if it still preserves the intended business meaning under the current accepted history.

## Possible Outcomes

When a candidate loses a technical race or observes stale history, the system may respond in several ways:

* reject the candidate
* retry after semantic revalidation
* transform the candidate into a new candidate action
* escalate for human or policy review
* block because the original intent no longer matches the current state
* admit only if a domain-specific compensation path exists

The important point is that the response should be explicit.

A stale candidate should not silently become a new accepted fact without semantic re-evaluation.

## Why This Matters for Agents

Agentic systems make this problem sharper.

An agent may generate actions quickly.

Multiple agents may act on the same entity.

A workflow may retry automatically.

A tool call may succeed even when the meaning of the action has become wrong.

Without semantic concurrency handling, the system may protect database consistency while still admitting the wrong business meaning.

This is the deeper failure mode:

```text
technically serialized
but semantically wrong
```

## Relationship to Compass

Compass already separates several boundaries:

```text
candidate event
→ semantic validation
→ concurrency admission
→ accepted history
```

Semantic concurrency extends this framing.

It says that concurrency is not only about whether a write is stale or whether a lock is held.

It is also about whether the candidate still deserves to become accepted truth after the world has changed.

In Compass terms:

```text
accepted history = authority
candidate action = not truth yet
concurrency admission = not only ordering, but meaning under current history
```

This makes semantic concurrency a natural part of semantic admission.

It belongs near the agent-governance framing because the central question is not only:

> Can the action be written?

It is:

> Should this action still be accepted?

```
```
