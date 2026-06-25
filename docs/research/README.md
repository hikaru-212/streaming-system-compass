# Research Notes

[← Back to Docs Home](../README.md)

This folder records research notes, case observations, and architecture explorations related to the Streaming System + Compass project.

These documents are not implementation commitments.

They preserve ideas that may be useful later, especially when an external system behavior, AI failure case, product design pattern, or governance problem suggests a possible architecture lesson.

A note in this folder means:

```text
This idea is worth preserving,
but the project does not currently commit to implementing it.
```

## Scope

Research notes may include:

* observations from real-world system behavior
* AI governance failure patterns
* source-grounded generation ideas
* semantic admission extensions
* future runtime governance possibilities
* cost, latency, cache, or verification trade-offs
* architecture patterns that may or may not become part of Compass later

These notes should not be read as:

* current implementation scope
* accepted roadmap commitments
* Stage 3.5D requirements
* Stage 4 requirements
* production-ready designs

## Sections

* [AI Governance Research](./ai_governance/README.md)

## Relationship to the Main Project

The main Compass implementation remains in `src/`, `tests/`, ADRs, implementation notes, and roadmaps.

This folder is different.

It is a place to preserve reasoning before deciding whether an idea belongs in:

* an ADR
* an implementation note
* a roadmap item
* a postmortem
* or no implementation plan at all

Research notes are useful because some architecture ideas appear before the project is ready to implement them.
