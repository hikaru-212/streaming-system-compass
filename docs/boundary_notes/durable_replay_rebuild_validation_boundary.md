# Durable Replay / Rebuild Validation Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the boundary for **Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline**.

Stage 3.5C PR4 introduced the first PostgreSQL-backed projection worker baseline:

```text
order_events
→ PostgresProjectionEventSource
→ canonical reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore
```

PR4 proved that accepted events can be consumed through `GLOBAL_POSITION`, projected through the canonical reducer, and persisted together with checkpoint progress in one read-side transaction.

PR5 answers the next question:

> If accepted history is replayed from the durable event log, does it produce the same state as the durable projection table currently stores?

This PR does not make projection state the source of truth.

It validates projection state against accepted history.

---

## Status

Stage 3.5C PR5 is complete at the baseline level.

This boundary has been implemented through:

```text
ReplayValidationStatus
ReplayValidationResult
DurableReplayValidator
```

with integration coverage for:

```text
MATCH
MISSING_PROJECTION
DRIFT
NO_ACCEPTED_HISTORY
```

This completes the Stage 3.5C durable read-side baseline together with PR1 through PR4.

The next stage is:

```text
Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
```

---

## Core Boundary

The core PR5 boundary is:

```text
accepted history
→ replay through canonical reducer
→ expected derived state
→ compare with persisted projection state
```

The source-of-truth relationship remains:

```text
order_events
= accepted-history truth

projection_states
= derived runtime view

projection_checkpoints
= operational worker progress
```

PR5 does not change that relationship.

---

## Why This Boundary Exists

Stage 3.5C PR1 established durable read-side tables.

Stage 3.5C PR2 made `projection_states` usable through `PostgresProjectionStore`.

Stage 3.5C PR3 made `projection_checkpoints` usable through `PostgresCheckpointStore`.

Stage 3.5C PR4 connected accepted history, the canonical reducer, projection state, and checkpoint progress through a PostgreSQL-backed projection worker.

However, PR4 only proved that the worker can process accepted events incrementally.

PR5 proves that persisted read-side state can be independently checked by replaying accepted history.

That matters because projection state is derived.

A derived state can be stale, incomplete, corrupted, or inconsistent even if accepted history is valid.

---

## Validation Model

PR5 introduces a minimal validation model that compares:

```text
expected state from accepted-history replay
```

against:

```text
persisted state from projection_states
```

The baseline result model distinguishes:

```text
MATCH
MISSING_PROJECTION
DRIFT
NO_ACCEPTED_HISTORY
```

Where:

- `MATCH` means replay-derived state equals persisted projection state.
- `MISSING_PROJECTION` means accepted history exists but no durable projection state exists.
- `DRIFT` means both expected and persisted states exist, but they differ.
- `NO_ACCEPTED_HISTORY` means no accepted history exists for the target order.

This result model is intentionally smaller than Stage 4 `SemanticOutcome`.

It is a PR5 validation result, not the final governance model.

---

## Runtime Flow

The durable replay validation flow is:

```text
1. choose an order_id
2. load accepted events for that order from order_events
3. replay accepted events through the canonical reducer
4. produce expected OrderState
5. load persisted projection state from projection_states
6. compare expected state with persisted state
7. return a structured validation result
```

The important constraint is:

```text
replay must use the same canonical reducer path as incremental projection
```

PR5 does not create a second ad hoc reconstruction algorithm.

---

## Replay Ordering Boundary

For single-aggregate replay, accepted events must be replayed in aggregate-local causal order:

```text
ORDER BY sequence ASC
```

`GLOBAL_POSITION` is the worker-consumption cursor across accepted history.

`sequence` is the causal ordering boundary inside one aggregate stream.

Therefore, PR5 reuses the accepted-history loading path that returns one order's events ordered by `sequence ASC`, such as `PostgresEventStore.load(order_id)`.

This keeps PR5 aligned with the aggregate-local replay rule instead of accidentally replaying one order by a global worker cursor.

---

## Comparison Boundary

The PR5 comparison remains explicit and narrow.

It compares the replay-derived `OrderState` with the persisted projection `OrderState`.

The implementation avoids comparing unrelated operational metadata such as checkpoint progress, worker name, cursor kind, cursor value, or database timestamps.

The comparison preserves exact-value behavior for money-like fields.

For Decimal values, integration tests include database round-trip cases so that the project does not accidentally classify formatting or quantization differences as semantic drift.

---

## Rebuild Boundary

PR5 establishes the validation baseline only.

It does not perform automatic rebuild mutation.

The rebuild boundary remains future work:

```text
delete or reset projection state
→ replay accepted history
→ save rebuilt projection state
```

Future rebuild work must still preserve:

```text
accepted history = source of truth
projection state = derived state
```

Rebuild must not mutate accepted history.

Rebuild must not infer new business facts.

Rebuild must not advance a worker checkpoint unless the design explicitly defines that behavior.

If checkpoint behavior is included, it must be documented separately because checkpoint progress is operational metadata, not business correctness.

---

## What PR5 Proves

PR5 proves:

- accepted history can be replayed from PostgreSQL
- replay uses the canonical reducer
- replay-derived state can be compared with durable projection state
- matching projection state is recognized as valid
- missing projection state is detected
- drifted projection state is detected
- projection state ahead of accepted-history replay is detected as drift
- projection validation does not mutate accepted history
- projection validation does not silently advance checkpoint progress
- projection validation does not become Compass Layer 2 yet

---

## Non-goals

PR5 does not implement:

- Compass Layer 2 validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety
- Snapshot Trust Contract
- snapshot-assisted replay
- automatic repair policy
- production rebuild orchestration
- out-of-order buffering
- DLQ
- watermark semantics
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination
- durable history permission hardening
- append-only trigger enforcement

---

## Relationship to Compass Layer 2

PR5 prepares for Compass Layer 2, but it is not Layer 2 yet.

The distinction is:

```text
PR5:
replay accepted history
→ compare with durable projection state
→ return minimal validation result

Future Compass Layer 2:
classify projection drift semantically
→ produce structured outcome
→ connect to runtime decision policy
→ decide rebuild / quarantine / block / continue
```

PR5 produces the durable comparison substrate that Layer 2 can later use.

---

## Relationship to Stage 3.5D Snapshot Trust Contract

PR5 uses full accepted-history replay as the authority path.

Stage 3.5D is the next stage and may introduce snapshot-assisted replay as a fast path.

That future work must prove:

```text
snapshot-assisted replay
=
full accepted-history replay
```

PR5 does not depend on snapshots.

---

## Implementation Boundary

The baseline implementation introduces:

```text
src/pipeline/projection/replay_validator.py
tests/integration/pipeline/projection/test_durable_replay_validation.py
```

Core types:

```python
ReplayValidationStatus
ReplayValidationResult
DurableReplayValidator
```

The first version stays small and explicit.

It compares one `order_id` at a time before expanding into batch validation, rebuild orchestration, or Compass Layer 2 integration.

---

## Current Decision

Stage 3.5C PR5 implements a minimal durable replay / rebuild validation baseline.

It validates derived read-side state against accepted history without changing the source-of-truth model.

The core rule is:

```text
accepted history is truth
projection state is derived
replay result is the expected derived state
validation compares expected derived state with persisted derived state
```

This completes Stage 3.5C at the durable read-side baseline level.
