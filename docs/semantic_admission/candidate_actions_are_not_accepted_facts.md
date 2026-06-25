# Candidate Actions Are Not Accepted Facts

[← Back to Semantic Admission Index](README.md)

## Core Risk

One risk in agentic systems is easy to miss:

An AI agent can generate an action, call a tool, and receive a successful response.

But that still does not mean the action should become accepted system truth.

## The Missing Question

Evaluation often asks:

> Did the output look correct?

Enterprise systems need another question:

> Should this action be allowed to change the system?

An agent may successfully call a tool, update a record, trigger a workflow, or move data across systems.

From an execution perspective, everything may look fine:

- the tool call succeeded
- the database write succeeded
- the workflow completed

But the action may still be semantically wrong.

It may target the wrong entity. It may violate domain constraints. It may drift from the original user intent. It may create state that future systems will treat as truth.

## Candidate vs Accepted

A useful distinction is:

- **candidate action**: what the agent proposes
- **accepted fact**: what the system formally commits

Without this boundary, an agent workflow can look successful while quietly poisoning enterprise state.

A candidate action should not become an accepted fact merely because it was executable.

## Evaluation and Admission

Evaluation improves the agent.

Admission protects the system.

Evaluation may tell us whether the model tends to produce good outputs.

Admission decides whether this specific candidate action is allowed to become durable truth.

The key question is not only:

> Did the agent produce an output?

It is:

> Should this candidate action become system truth?

## Why This Matters

This is not a criticism of agents.

Agents are powerful precisely because they can turn intent into action.

But once agents begin touching enterprise state, systems need a clear boundary between proposed actions and committed facts.

That boundary is semantic admission.
