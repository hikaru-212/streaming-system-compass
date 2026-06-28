# Implementation Notes

[← Back to Docs Home](../README.md)

## Purpose

This folder contains stage-level and PR-level implementation notes for **Streaming System + Compass**.

Implementation notes are more concrete than roadmap documents, but broader than source-code comments.

They exist to keep the main roadmaps readable while preserving the implementation details needed to execute each stage safely.

---

## Why This Folder Exists

As the project grows, the main roadmap should not become a permanent archive of every completed PR's full scope, test matrix, schema draft, and non-goal list.

The roadmap should preserve:

- project sequencing
- stage dependencies
- current focus
- why one stage comes before another
- links to deeper implementation material

Implementation notes should preserve:

- PR breakdowns
- schema baselines
- store behavior
- validator behavior
- resolver behavior
- test plans
- implementation hazards
- stage-specific execution details
- deferral decisions that affect current stage scope

This keeps the roadmap useful as a roadmap instead of turning it into a long historical implementation log.

---

## What These Notes Are For

Use implementation notes for questions such as:

- What should this stage build?
- What PRs are expected inside this stage?
- What schema shape is currently proposed?
- What store behavior should be tested?
- What validator behavior should be implemented?
- What resolver behavior should be implemented?
- What collision, fallback, or retry policy should code preserve?
- What implementation hazards should be avoided?
- What should remain a non-goal for this PR?
- Which originally planned implementation items have been deferred?

---

## What These Notes Are NOT

Implementation notes are not meant to replace:

- roadmaps
- architecture notes
- boundary notes
- ADRs
- postmortems
- source-code comments
- test documentation

Those documents answer different questions:

```text
roadmap
= what should be built, in what order, and why this sequence matters

architecture notes
= how major subsystems are shaped and how they evolve

boundary notes
= what a module or cross-cutting boundary owns and does not own

ADRs
= why a specific decision was made

postmortems
= what was learned from a mistake, confusion, or design correction

implementation notes
= how a stage or PR should be executed without overloading the roadmap
```

---

## Current Notes

Stage 3.5D introduced the first implementation notes in this folder.

Current Stage 3.5D status:

```text
PR1   — General Snapshot Trust Contract Boundary
PR1.5 — CI / Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
```

Deferred Stage 3.5D work:

```text
Deferred PR6 — Aggregate Snapshot Schema / Store
Deferred PR7 — Snapshot-Assisted Write-Side Rehydration
```

| Document | Purpose |
|---|---|
| [Stage 3.5D PR Breakdown](stage_3_5d_pr_breakdown.md) | Defines the Stage 3.5D PR sequence, current closeout state, and deferred aggregate snapshot work. |
| [Snapshot Payload Hashing](snapshot_payload_hashing.md) | Defines deterministic canonical payload hashing for snapshot trust checks and future trust hardening. |
| [Snapshot Generation Policy](snapshot_generation_policy.md) | Defines when snapshot production may happen and keeps generation separate from trust validation. |
| [Projection Snapshot Schema Baseline](projection_snapshot_schema_baseline.md) | Records the PR2 physical schema baseline for projection snapshots, including source-boundary uniqueness rules. |
| [Postgres Projection Snapshot Store](postgres_projection_snapshot_store.md) | Defines the PR3 storage boundary, caller-owned transaction behavior, and collision handling for projection snapshots. |
| [Projection Snapshot-Assisted Replay Validator](projection_snapshot_assisted_replay_validator.md) | Defines the PR4 replay validation boundary for checking snapshot-assisted projection reconstruction against accepted-history replay, including accepted-history adapter and PostgreSQL wiring proof. |
| [Projection Snapshot-Assisted State Resolver](projection_snapshot_assisted_state_resolver.md) | Defines the PR4.5 read-side resolver primitive that consumes an externally qualified projection snapshot id and resolves projection state through snapshot + tail replay. |
| [Aggregate Snapshot Trust Boundary / Deferral Decision](aggregate_snapshot_trust_deferral.md) | Records the PR5 decision to defer aggregate snapshot schema, store, and snapshot-assisted write-side rehydration because write-side aggregate snapshots have stricter admission-path trust requirements. |

Future or deferred Stage 3.5D implementation notes may include:

| Document | Purpose |
|---|---|
| `aggregate_snapshot_schema_and_store.md` | Deferred. Would define the schema and store boundary for aggregate snapshots if write-side aggregate snapshot work is revived. |
| `snapshot_assisted_write_side_rehydration.md` | Deferred. Would define the write-side snapshot-assisted rehydration flow if aggregate snapshots become justified. |

---

## Current Stage 3.5D Interpretation

Stage 3.5D completed the read-side projection snapshot trust path.

```text
accepted history = authority
projection snapshot = derived state compression
PR4 validator = audit / validation evidence
PR4.5 resolver = read-side snapshot + tail replay primitive
```

PR5 records the decision not to implement write-side aggregate snapshots in this stage.

Reason:

```text
read-side projection snapshot
= derived-state integrity / replay-efficiency / runtime evidence

write-side aggregate snapshot
= admission-path safety concern
```

Write-side aggregate snapshot implementation is deferred until the trust contract, validation receipts, invalidation policy, fallback behavior, and strategy selection are mature enough.

---

## Relationship to the Roadmap

The implementation roadmap should stay concise.

When a stage requires detailed PR-level execution notes, those details should move here and the roadmap should link to the relevant implementation note.

A good rule of thumb:

```text
If it explains project order, keep it in the roadmap.
If it explains how one stage or PR should be built, move it to implementation notes.
```

This keeps the roadmap focused on sequencing and dependency logic while preserving implementation rigor in a dedicated place.

---

## Relationship to Architecture Notes

Architecture notes describe subsystem shape and long-term role.

Implementation notes describe concrete build steps for a stage or PR.

For example:

```text
architecture/snapshot_trust_contract.md
= how snapshot trust fits into the system

implementation_notes/stage_3_5d_pr_breakdown.md
= how Stage 3.5D should be split into PRs
```

---

## Relationship to Boundary Notes

Boundary notes define ownership and non-ownership rules.

Implementation notes turn those boundaries into concrete work plans.

For example:

```text
boundary_notes/snapshot_trust_contract_boundary.md
= what snapshot trust validation owns and does not own

implementation_notes/snapshot_payload_hashing.md
= how payload hashing should be implemented deterministically
```

---

## Relationship to Postmortems

Postmortems preserve lessons learned from confusion, mistakes, or design corrections.

Implementation notes convert those lessons into forward-looking execution constraints.

For example:

```text
postmortems/from_snapshot_as_fast_state_to_snapshot_trust_contract.md
= why treating snapshot as a simple cache is dangerous

implementation_notes/snapshot_generation_policy.md
= how snapshot production should remain separate from snapshot trust validation
```

---

## Documentation Principle

Implementation notes should stay concrete, but they should not silently expand stage scope.

A good implementation note should make clear:

- purpose
- scope
- non-goals
- assumptions
- required invariants
- validation plan
- relationship to other documentation

The goal is to preserve implementation discipline without turning the roadmap into a several-thousand-line archive.

In short:

```text
roadmap = navigation
implementation notes = execution detail
```
