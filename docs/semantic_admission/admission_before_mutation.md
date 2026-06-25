# Admission Before Mutation

[← Back to Semantic Admission Index](README.md)

## Why Enterprise Agents Need an Admission Boundary

When AI becomes the operator, the risk model changes.

In traditional systems, a human operator usually has some natural friction:

- common sense
- hesitation before destructive actions
- manual review
- slower execution speed
- responsibility after the fact

But an AI agent can act much faster.

It can call tools, update records, trigger workflows, retry actions, and mutate enterprise state before a human even notices.

That changes the role of system design.

## Observation Is Necessary but Not Sufficient

Post-hoc observation is still important.

Logs matter. Audits matter. Dashboards matter. Evaluations matter.

But once a bad action has already mutated durable state, observation may only tell us that damage happened.

Worse, durable state does not stay local.

Once bad facts enter databases, logs, memories, or retrieval corpora, they can become evidence for future agents.

The failure is no longer just one bad action.

It becomes contaminated context for the next decision.

## The Missing Layer

Enterprise agents need something stronger than after-the-fact monitoring.

They need admission before mutation.

A useful distinction is:

- **candidate action**: what the agent proposes
- **accepted fact**: what the system allows to become committed state

This is not about blocking agents from acting.

It is about making agent-driven automation governable.

Human approval for every action does not scale.

Unbounded automation is unsafe.

The missing layer is contract-based admission.

## Contract-Based Admission

Contract-based admission defines:

- what actions are allowed
- what actions are blocked
- which entities can be touched
- which state changes require escalation
- which action paths are semantically unsafe
- which proofs are required before mutation

In this model, the agent can still move fast.

But it moves inside boundaries that are explicit, machine-readable, and enforceable before state mutation.

That is the role of a Compass-style guard.

## Core Principle

Evaluation improves the agent.

Admission protects the system.

The deeper question is not only:

> Did the agent successfully execute?

It is:

> Should this candidate action be allowed to become system truth?
