# Persistent Storage Baseline

[← Back to Architectures Index](README.md)

## Purpose

This document defines the next major implementation target after the Stage 3 in-memory projection baseline.

The purpose of this stage is not merely to "put data into a database."

The real goal is to carry the current semantic boundaries into a durable runtime world without collapsing:

- accepted history semantics
- idempotency semantics
- projection-state semantics
- checkpoint progression semantics
- replay / rebuild equivalence

In other words, this stage asks:

> how can the current in-memory baseline become durable without losing the correctness properties that made the baseline meaningful in the first place?

---

## Current Position

The repository already has:

- a write-side transactional semantic baseline
- accepted-history replay baseline
- request-level idempotency with replay / conflict distinction
- Compass Layer 1 transition-truth validation
- a Stage 3 projection runtime baseline in deterministic in-memory form
- projection-state and checkpoint-store separation
- replay / rebuild through the same projection runtime path

What does **not yet** exist is durable persistence-backed execution.

This means the current system is still limited in important ways:

- accepted history does not yet survive process lifetime through a real database
- idempotency semantics are not yet durable across restart
- projection state is not yet persisted durably
- checkpoint progress is not yet persisted durably
- replay / rebuild equivalence has not yet been validated against persistence-backed state

---

## Why This Stage Comes Next

After the Stage 3 in-memory baseline, the next major problem is not DLQ, buffering, watermarking, or multi-worker coordination.

Those are real runtime concerns, but they should not be the next priority.

The next priority is durable persistence, because without it the system still lacks a strong answer to questions such as:

- what survives restart?
- what exactly is the durable source of truth?
- how is replay validated against stored runtime state?
- how does retry safety behave after process lifetime ends?
- how does checkpoint position remain trustworthy across restart?

This is why the next stage is best understood as:

## Stage 3.5 — Persistent Storage Baseline

---

## Core Goal

The core goal of this stage is:

> preserve the current semantic boundaries while replacing in-memory persistence with durable storage-backed implementations.

That means:

- do **not** redesign the semantic architecture
- do **not** collapse multiple stores into one ambiguous boundary
- do **not** introduce advanced runtime complexity prematurely
- do **not** treat persistence as a purely mechanical concern

Instead, persistence should be introduced carefully so that the meaning of each boundary remains stable.

---

## Recommended Order

The persistent storage baseline should be introduced in the following order.

### 1. Write-Side Durable Baseline

First strengthen:

- event store
- idempotency store

This is the correct first move because accepted history remains the source of truth, and idempotency semantics must survive restart if replay / conflict distinction is to remain meaningful.

### 2. Read-Side Durable Baseline

Then strengthen:

- projection store
- checkpoint store

This is the correct second move because projection state is derived from accepted history, and checkpoint trust depends on durable runtime progress.

### 3. Durable Replay / Rebuild Validation

After both write-side and read-side durable boundaries exist, validate:

- rebuild from durable accepted history
- consistency between replayed state and persisted projection state
- checkpoint correctness across restart

This is what turns the persistence baseline from "data saved in a DB" into a meaningful durable runtime baseline.

---

## Main Storage Targets

### `event_store`

Must evolve from in-memory accepted-history storage into a durable accepted-history boundary.

Its durable responsibilities include:

- append accepted event
- load accepted event history
- get last accepted event
- preserve append-only semantics
- preserve aggregate-local sequence continuity
- support deterministic replay

### `idempotency_store`

Must evolve from in-memory request replay tracking into a durable retry-safety boundary.

Its durable responsibilities include:

- persist request identity
- retrieve prior result for retry
- preserve replay / conflict distinction
- survive restart without losing semantic classification

### `projection_store`

Must evolve from in-memory projected-state storage into a durable read-side state boundary.

Its durable responsibilities include:

- persist projected state
- load projected state
- preserve current projected version
- support replay / rebuild comparison

### `checkpoint_store`

Must evolve from in-memory progress tracking into a durable projection progress boundary.

Its durable responsibilities include:

- persist last processed sequence / offset
- restore progress after restart
- remain semantically aligned with actual projection progress

---

## Persistent Storage Technology Choice

The recommended primary implementation target is:

## PostgreSQL

### Why PostgreSQL Fits This Stage Best

PostgreSQL is a strong fit because this project is not merely modeling cache behavior or transient coordination.

It is modeling:

- accepted-history durability
- replayability
- idempotency persistence
- projection-state persistence
- checkpoint semantics
- transactional consistency between related persistence updates

Those concerns are naturally aligned with PostgreSQL.

### Why Not Redis as the Primary Baseline

Redis may later be useful for auxiliary runtime concerns such as caching or coordination, but it is not the best primary storage baseline for this stage because the current priority is durable semantic state, not ephemeral speed-oriented infrastructure.

### Why Not SQLite as the Primary Baseline

SQLite can be useful for very small local experiments, but for a project whose explicit goal is production-inspired correctness under failure, PostgreSQL is a stronger long-term signal and a better fit for transaction semantics and durable runtime modeling.

---

## Transaction Boundary Concerns

This stage must pay special attention to multi-record semantic consistency.

### Write-Side Concern

If accepted event append and idempotency record persistence are split incorrectly, the system may produce semantically inconsistent persistence outcomes, for example:

- event persisted but idempotency record missing
- idempotency record persisted but event missing

That would damage retry semantics.

### Read-Side Concern

If projection state and checkpoint updates are split incorrectly, the system may produce runtime inconsistency, for example:

- state updated but checkpoint not advanced
- checkpoint advanced but state not updated

That would damage restart and replay trust.

This means persistent storage is not just about "saving rows."
It is also about preserving semantic consistency across related persistence operations.

---

## What This Stage Should Not Yet Do

The persistent storage baseline should **not yet** introduce:

- DLQ routing
- out-of-order buffering
- watermark semantics
- distributed multi-worker coordination
- production-scale observability claims
- operational SLI / SLO commitments
- governance layers richer than the current baseline

Those concerns are real, but they should come after durable baseline semantics are stable.

---

## Expected Deliverables

A successful persistent storage baseline should produce:

- durable accepted-history persistence
- durable idempotency persistence
- durable projection-state persistence
- durable checkpoint persistence
- replay / rebuild validation against persistence-backed runtime state
- tests proving that the durable world preserves the same core semantic boundaries established in the in-memory baseline

---

## Summary

The persistent storage baseline is the next stage because the current system already knows how to behave correctly in-memory.

The next challenge is to preserve that correctness when runtime state must survive process lifetime and restart.

This stage is therefore best understood as:

- not an infrastructure ornament
- not a database tutorial
- not an advanced streaming-runtime stage

but as the first durable-world extension of the project’s semantic baseline.
