# Postmortems

[← Back to Docs Home](../README.md)

This directory contains postmortems for **Streaming System + Compass**.

Postmortems are used to preserve design mistakes, confusion points, debugging lessons, and architectural learning moments encountered during the project.

They are not ADRs.

A postmortem does not necessarily record a formal architecture decision. Instead, it explains what went wrong, why it was confusing, and what reusable lesson should be preserved.

---

## Postmortem Purpose

Postmortems help preserve:

- boundary misunderstandings
- scale mismatch in code reading
- mistaken ownership assumptions
- implementation confusion
- debugging lessons
- reusable design heuristics
- explicit differences between current project scope and enterprise-style documentation expectations
- key learning transitions between architecture stages
- transitions where a previously "natural" guarantee turns out to require explicit design
- reasoning bridges between current implementation and later roadmap stages
- distinctions between runtime behavior, durable evidence, and future governance signals

---

## Current Postmortems

## Current Postmortems

| Document | Purpose |
|---|---|
| [function_boundary_scale_mismatch](function_boundary_scale_mismatch.md) | Explains a recurring confusion caused by reading function parameters before identifying module roles, ownership boundaries, and architectural scale. |
| [from_projection_concerns_to_event_truth](from_projection_concerns_to_event_truth.md) | Records the design shift from focusing mainly on projection/runtime problems to treating event-source correctness and accepted-history entry as a more foundational concern. |
| [docs_vs_enterprise_design_docs](docs_vs_enterprise_design_docs.md) | Clarifies why the current repository documents emphasize semantic completeness and boundary clarity first, rather than pretending to already be a full enterprise operational design doc. |
| [from_in_memory_correctness_to_durable_consistency](from_in_memory_correctness_to_durable_consistency.md) | Explains why durable persistence is not just a backend replacement: once state must survive across time and restart, guarantees that felt natural in the in-memory world are no longer free. |
| [from_git_sync_to_db_immutability](from_git_sync_to_db_immutability.md) | Records how a Git local/remote synchronization confusion exposed a deeper distributed-systems lesson: Python-side guarantees such as `frozen=True` and append-only history must be explicitly re-declared at the database boundary. |
| [from_local_postgres_to_defense_in_depth](from_local_postgres_to_defense_in_depth.md) | Explains why local PostgreSQL setup, `.env`, least privilege, SQL migrations, Compass validation, and transactions protect different system boundaries instead of one mechanism protecting everything. |
| [from_runtime_behavior_to_durable_evidence](from_runtime_behavior_to_durable_evidence.md) | Explains why Python runtime behavior is not durable evidence unless selected facts are persisted into PostgreSQL, metadata fields, logs, metrics, traces, or audit records. |
| [from_exception_strings_to_governable_outcomes](from_exception_strings_to_governable_outcomes.md) | Explains why raw exception strings are not enough for semantic governance, and why structured semantic outcomes must later feed runtime decision policy, action safety, and layered trust. |

---

## How to Use These Notes

Use postmortems when you want to understand:

- why a previous implementation or interpretation was confusing
- how a boundary should be read in the future
- what design habit should be avoided
- what reusable reading or debugging method emerged from the mistake
- why the current repository intentionally documents some things in greater semantic depth while still deferring full enterprise-operational realism
- how one architectural stage exposed the need for the next stage
- why a future roadmap direction exists before its implementation begins

---

## Postmortem Principle

A good postmortem should not only say what happened.

It should identify the reusable lesson:

```text
confusion
→ root cause
→ corrected model
→ future rule
```

For roadmap bridge documents, the useful pattern is:

```text
current limitation
→ missing semantic boundary
→ corrected model
→ future implementation stage
```
