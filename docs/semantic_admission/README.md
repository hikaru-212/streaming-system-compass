# Semantic Admission

[← Back to Docs Home](../README.md)

This folder is the condensed AI governance entry point for the Streaming System + Compass project.

The full Compass project contains many distributed-systems implementation details: durable write-side storage, projections, checkpoints, replay validation, snapshot trust contracts, transaction boundaries, idempotency, concurrency, and failure recovery.

This section focuses on the higher-level problem framing:

> When an AI agent proposes a state-changing action, what makes that action eligible to become system truth?

Compass treats agent output as a candidate, not as truth.

A successful tool call, database write, or workflow completion may prove execution success, but it does not automatically prove semantic correctness.

---

## Disclosure Scope

This section is intended as a public conceptual entry point.

It defines the problem, vocabulary, and case-study framing for Semantic Admission.

It does not expose complete implementation internals, final contract schemas, validator algorithms, authority matrices, runtime policy tables, or production enforcement designs.

The goal is to make the architectural boundary understandable while preserving implementation flexibility and design ownership.

---

## Core Claim

A state-changing agent system needs a boundary between:

- **candidate action**: what the agent proposes
- **accepted fact**: what the system formally allows to become durable truth

This boundary is called **semantic admission**.

---

## Why This Matters for Agents

Traditional software systems usually execute paths written ahead of time by engineers.

Agentic systems may generate the action path dynamically.

That changes the risk model.

The system must not ask only:

> Did the action execute?

It must also ask:

> Should this candidate action have been allowed to change durable state?

This is especially important when multiple agents, workflows, or requests propose state changes at the same time.

Technical concurrency control can protect write ordering, but it does not fully decide whether competing candidate actions are semantically compatible.

---

## Why This Also Matters for Multi-Agent Workflows

A multi-agent system may share context, tools, sessions, and orchestration.

That is necessary, but not sufficient.

Shared context tells agents what was observed.

It does not automatically define what agents are allowed to claim, execute, or commit.

For commercial workflows, agents also need shared semantic contracts.

Example:

```text
Product A had stock at search time.
```

This does not automatically mean:

```text
Product A is purchasable at commit time.
```

A search result is not a purchase guarantee.

A recommendation is not a reservation.

A candidate checkout is not an accepted order.

---

## Why Bad State Can Become Future Context

In agentic systems, a bad action is not necessarily isolated.

If the system admits it into durable state, that action may become part of the environment future agents observe.

It can be stored, indexed, retrieved, summarized, reflected in analytics, or used by downstream workflows.

This creates a propagation risk:

```text
bad agent action
→ admitted durable state
→ future agent context
→ downstream decision
→ new state mutation
```

The goal of semantic admission is not to make agents perfect.

The goal is to prevent unvalidated outputs from becoming future context.

---

## Why Inferred Semantics Need Admission

Enterprise agents may infer business meaning from tables, dashboards, BI metrics, queries, semantic views, documentation, and usage patterns.

That can reduce human search burden.

But inferred meaning is not automatically accepted semantic truth.

```text
inferred semantic meaning ≠ accepted semantic contract
```

An agent may help propose a Compass layer, semantic contract, or business definition.

It should not authorize its own semantic truth.

A governed system should distinguish:

```text
semantic discovery
→ candidate semantic contract
→ evidence / lineage / conflict review
→ accepted semantic contract version
```

---

## Why Mutable State Is a Weak Boundary

Many early systems begin with CRUD because it is fast, familiar, and compatible with existing tools.

That is understandable.

However, agentic commerce introduces a stronger risk model.

When agents can dynamically call tools and mutate business state, the system must distinguish between:

```text
current mutable row
```

and:

```text
authoritative, auditable business fact
```

The current row may show what the state is now.

It may not explain who changed it, why it changed, what evidence supported the change, or whether the actor had business authority.

This section therefore treats mutable CRUD state as an important case study for Semantic Admission.

The public principle is:

```text
Current row state is not history.
Mutable state is not independent evidence.
Tool permission is not business authority.
Task completion is not truth preservation.
```

---

## Reading Order

Start with:

1. [manifesto.md](./manifesto.md)
2. [glossary.md](./glossary.md)
3. [candidate_actions_are_not_accepted_facts.md](./candidate_actions_are_not_accepted_facts.md)
4. [action_path_admission.md](./action_path_admission.md)
5. [admission_before_mutation.md](./admission_before_mutation.md)
6. [semantic_concurrency.md](./semantic_concurrency.md)
7. [bad_state_as_future_context.md](./bad_state_as_future_context.md)
8. [Agent Pipelines as a Stochastic Process](./agent_pipelines_as_stochastic_process.md)
9. [agent_action_as_hypothesis.md](./agent_action_as_hypothesis.md)
10. [retry_is_not_intent_preservation.md](./retry_is_not_intent_preservation.md)
11. [shared_context_is_not_shared_contract.md](./shared_context_is_not_shared_contract.md)
12. [crud_is_not_a_safe_boundary_for_agentic_commerce.md](./crud_is_not_a_safe_boundary_for_agentic_commerce.md)
13. [Agent-Assisted Compass Layer Construction](./agent_assisted_compass_layer_construction.md)
14. [input_guardrail_vs_admission_boundary_origin.public](./input_guardrail_vs_admission_boundary_origin.public.md)

---

## Glossary Structure

The glossary is grouped into four areas:

1. **System Truth & Admission Core**  
   Defines candidate artifacts, accepted facts, semantic admission, admission boundaries, durable state, and core correctness language.

2. **Technical & Semantic Concurrency Control**  
   Separates write-ordering problems from meaning-level conflicts between candidate actions.

3. **Storage, Authority & Evidence Boundaries**  
   Defines why mutable state, CRUD requests, truth sources, business authority, and audit evidence matter for agentic systems.

4. **Multi-Agent Semantic Contracts & Governance**  
   Defines shared context, shared semantic contracts, semantic escalation, commit-time truth, intent drift, and workflow-level correctness.

---

## Relationship to the Main Project

The main project implements the runtime evidence behind this framing.

In the full Compass system:

- candidate events are validated before entering accepted history
- accepted history is treated as the source of truth
- idempotency and concurrency are treated as separate boundaries
- projections are checked against accepted history
- snapshots are derived, discardable, traceable, and subordinate
- replay validation is used to detect read-side semantic drift
- retry-like situations are classified by semantic meaning, not collapsed into one generic retry category

This folder does not replace the implementation notes or ADRs.

It provides the shortest path into the AI governance problem that the implementation is designed to test:

```text
candidate output
→ admission boundary
→ accepted fact
→ protected accepted history
→ safer future reasoning
```

---

## Relationship to Research Notes

Some related ideas are exploratory and are not part of the current implementation roadmap.

See:

- [`../research/ai_governance/`](../research/ai_governance/)

The research notes include adjacent ideas such as source-grounded generation, overview cache admission, and multi-pass answer review.

Those notes are related to semantic admission, but they are intentionally separated from this public conceptual entry point.

---

## Summary

Semantic Admission is the boundary between agent-generated possibility and accepted system truth.

The central claim is:

```text
A candidate action is not an accepted fact.
```

The propagation extension adds:

```text
Bad state can become future context.
```

The multi-agent extension adds:

```text
Shared context is not shared contract.
```

The mutable-state case study adds:

```text
Current row state is not history.
Task completion is not truth preservation.
Tool permission is not business authority.
```

The semantic-contract extension adds:

```text
Inferred semantic meaning is not an accepted semantic contract.
```

Together, these principles describe why commercial agent systems need more than execution success, shared context, and CRUD state mutation.

They need explicit admission boundaries for business meaning.
