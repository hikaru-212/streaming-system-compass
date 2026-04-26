# Boundary Note: Checkpoint Module

[← Back to Boundary Notes Index](README.md)

## Purpose

This module defines the persistence boundary for runtime processing progress.

Its purpose is to record how far a projection or consumer has progressed, so that processing can resume consistently after interruption or restart.

Typical checkpoint information may include:
- last processed sequence
- last consumed offset
- last successful projection position
- replay restart boundary

---

## Responsible For

This module is responsible for:

- storing processing progress
- loading processing progress during restart
- helping projection workers resume from a known boundary
- supporting replay / rebuild decisions
- enabling runtime progress consistency checks

---

## Not Responsible For

This module is **not** responsible for:

- deciding domain legality
- deciding event admission
- storing the full source-of-truth event history
- deriving projection state by itself
- replacing Compass state validation

Those belong to:
- aggregate
- event store
- projection layer
- Compass state layer

---

## Design Principle

A checkpoint should be treated as a **progress marker**, not as the source of semantic truth.

This means:

- event history remains the source of truth
- projection state remains derived state
- checkpoint only records how far processing has gone

In short:
- event store answers: what happened?
- projection store answers: what state has been derived?
- checkpoint store answers: how far has processing progressed?

---

## Relationship to Projection

Checkpointing belongs mainly to the projection runtime.

A projection worker typically needs to know:
- which events have already been consumed
- where to resume after a restart
- whether replay is needed from a certain boundary

Without checkpoints, a runtime projection worker cannot recover efficiently or consistently.

---

## Relationship to Replay

Checkpointing and replay are closely related.

Checkpoint says:
- "resume from here"

Replay says:
- "rebuild from there"

The system may use checkpoints to reduce full replay cost, but checkpoints do not replace replayability as a correctness principle.

---

## Relationship to Compass

Checkpoint semantics are especially important for the **state-level Compass layer**.

Compass may later ask questions such as:
- does the checkpoint position match the actual projection state?
- has the system advanced farther than its state indicates?
- is replay from checkpoint consistent with fully replayed history?

This means checkpoint correctness is not only operational, but also semantically important.

---

## Current Relevance

At the current stage of the project, checkpointing is not the first implementation priority.

It becomes significantly more important once:
- projection evolves into a real runtime worker
- incremental processing replaces pure replay demos
- crash recovery becomes a design concern

So this module can be defined early as a boundary note, even if its full implementation comes later.

---

## Practical Warning

If checkpoint is treated as source of truth, the system becomes fragile.

If checkpoint is missing from a real projection runtime, restart and recovery become inefficient or unsafe.

The right balance is:
- event history remains authoritative
- checkpoint records progress
- Compass later validates whether progress and derived state remain aligned

---

## Summary

The checkpoint module records runtime progress, not semantic truth.

It becomes critical once projection becomes a real processing pipeline rather than only a replay helper.