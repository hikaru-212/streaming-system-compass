# Semantic Admission

[← Back to Docs Home](../README.md)

This folder is the condensed AI governance entry point for the Streaming System + Compass project.

The full Compass project contains many distributed-systems implementation details: durable write-side storage, projections, checkpoints, replay validation, snapshot trust contracts, transaction boundaries, idempotency, concurrency, and failure recovery.

This section focuses on the higher-level problem framing:

> When an AI agent proposes a state-changing action, what makes that action eligible to become system truth?

Compass treats agent output as a candidate, not as truth. A successful tool call, database write, or workflow completion may prove execution success, but it does not automatically prove semantic correctness.

## Core Claim

A state-changing agent system needs a boundary between:

* **candidate action**: what the agent proposes
* **accepted fact**: what the system formally allows to become durable truth

This boundary is called **semantic admission**.

## Why This Matters for Agents

Traditional software systems usually execute paths written ahead of time by engineers.

Agentic systems may generate the action path dynamically.

That changes the risk model.

The system must not ask only:

> Did the action execute?

It must also ask:

> Should this candidate action have been allowed to change durable state?

This is especially important when multiple agents, workflows, or requests propose state changes at the same time. Technical concurrency control can protect write ordering, but it does not fully decide whether competing candidate actions are semantically compatible.

## Reading Order

Start with:

1. [manifesto.md](./manifesto.md)
2. [glossary.md](./glossary.md)
3. [candidate_actions_are_not_accepted_facts.md](./candidate_actions_are_not_accepted_facts.md)
4. [action_path_admission.md](./action_path_admission.md)
5. [admission_before_mutation.md](./admission_before_mutation.md)
6. [semantic_concurrency.md](./semantic_concurrency.md)
7. [bad_state_as_future_context.md](./bad_state_as_future_context.md)
8. [agent_action_as_hypothesis.md](./agent_action_as_hypothesis.md)

## Relationship to the Main Project

The main project implements the runtime evidence behind this framing.

In the full Compass system:

* candidate events are validated before entering accepted history
* accepted history is treated as the source of truth
* idempotency and concurrency are treated as separate boundaries
* projections are checked against accepted history
* snapshots are derived, discardable, traceable, and subordinate
* replay validation is used to detect read-side semantic drift

This folder does not replace the implementation notes or ADRs.

It provides the shortest path into the AI governance problem that the implementation is designed to test:

```text
candidate output
→ admission boundary
→ accepted fact
→ protected accepted history
→ safer future reasoning
```

## Related Research

Some related ideas are exploratory and are not part of the current implementation roadmap.

See:

* [`../research/ai_governance/`](../research/ai_governance/)
