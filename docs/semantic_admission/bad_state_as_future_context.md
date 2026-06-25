# When Bad State Becomes Future Context

[← Back to Semantic Admission Index](README.md)

## Core Risk

In agentic systems, a bad action is not always a one-time failure.

If the system admits it into durable state, it can become context for the next decision.

That is the deeper risk.

## From Bad Action to Bad Evidence

An agent may propose the wrong action.

The system may accept it.

The database, log, memory, or retrieval corpus may then preserve it as if it were a valid fact.

Later, another agent may retrieve that same polluted fact and use it as evidence.

At that point, the failure is no longer only:

> The agent made a bad decision.

It becomes:

> The system taught future agents that the bad decision was part of reality.

## Why Accepted History Matters

A dirty accepted history does not stay local.

It can flow into:

- analytics
- dashboards
- memory
- retrieval
- fine-tuning data
- downstream workflows
- future agent decisions

Post-hoc observability can tell us that something happened.

But it may not prevent bad facts from becoming trusted context.

## Admission Protects Future Reasoning

This is why admission before mutation matters.

The goal is not to make agents perfect.

The goal is to prevent unvalidated agent output from becoming durable system truth.

Semantic correctness is not only about the current transaction.

It is also about protecting the future context that agents will reason from.

## Core Principle

Bad accepted state can become future context.

Therefore, agent governance must protect the boundary where candidate actions become accepted facts.
