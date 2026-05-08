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

---

## Current Postmortems

| Document | Purpose |
|---|---|
| [function_boundary_scale_mismatch](function_boundary_scale_mismatch.md) | Explains a recurring confusion caused by reading function parameters before identifying module roles, ownership boundaries, and architectural scale. |
| [from_projection_concerns_to_event_truth](from_projection_concerns_to_event_truth.md) | Records the design shift from focusing mainly on projection/runtime problems to treating event-source correctness and accepted-history entry as a more foundational concern. |
| [docs_vs_enterprise_design_docs](docs_vs_enterprise_design_docs.md) | Clarifies why the current repository documents emphasize semantic completeness and boundary clarity first, rather than pretending to already be a full enterprise operational design doc. |

---

## How to Use These Notes

Use postmortems when you want to understand:

- why a previous implementation or interpretation was confusing
- how a boundary should be read in the future
- what design habit should be avoided
- what reusable reading or debugging method emerged from the mistake
- why the current repository intentionally documents some things in greater semantic depth while still deferring full enterprise-operational realism

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
