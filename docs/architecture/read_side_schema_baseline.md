# Durable Read-Side Schema Baseline

[← Back to Architectures Index](README.md)

## Purpose

This document defines the first durable schema baseline for the read-side path in **Stage 3.5C PR1**.

Its purpose is to explain why the initial PostgreSQL schema for durable read-side state should be shaped the way it is before store and worker implementation grows larger.

This note focuses on two durable read-side boundaries:

- derived projection state
- projection worker checkpoint progress

It does **not** define the full PostgreSQL-backed projection worker.
It defines the schema-level reasoning that supports that later implementation.

---

## Stage 3.5C Completion Note

This document was originally written for Stage 3.5C PR1.

Stage 3.5C is now complete at the durable read-side baseline level:

```text
PR1 — Durable Read-Side Schema Baseline
PR2 — PostgresProjectionStore
PR3 — PostgresCheckpointStore
PR4 — Global-Position Projection Worker Baseline
PR5 — Durable Replay / Rebuild Validation Baseline
```

This architecture note should now be read as the schema foundation that enabled PR2–PR5.

The next stage is:

```text
Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
```

---

## Why This Note Exists

Stage 3 established a deterministic in-memory projection runtime baseline.

Stage 3.5B established durable write-side accepted history through PostgreSQL.

Stage 3.5C now begins moving the read-side baseline from in-memory stores toward durable persistence-backed semantics.

This move is not only a storage change.

It forces the project to clarify three different meanings:

```text
order_events = accepted-history source of truth
projection_states = derived runtime view
projection_checkpoints = worker progress metadata
```

The read-side schema must support durability without accidentally redefining business truth.

---

## Scope

This document covers the first durable read-side schema baseline for:

- `projection_states`
- `projection_checkpoints`

At PR1, this document did not yet cover the later implementation PRs.

Those later Stage 3.5C responsibilities are now complete:

```text
PR2 — PostgresProjectionStore
PR3 — PostgresCheckpointStore
PR4 — PostgreSQL-backed projection worker and GLOBAL_POSITION cursor
PR5 — Durable replay / rebuild validation
```

The following remain outside the completed Stage 3.5C schema baseline:

- snapshot trust
- snapshot-assisted replay optimization
- Compass Layer 2 validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety
- database role hardening
- append-only trigger enforcement

---

## Core Read-Side Principle

The durable read-side must preserve one core rule:

> Read-side state is derived state.  
> It is not the source of truth.

The durable source of truth remains accepted history in `order_events`.

Projection state exists to make the current derived view queryable and restart-safe.

Checkpoint state exists to make worker progress restart-safe.

Neither one should become a replacement for accepted history.

---

## Current Durable Read-Side Targets

The baseline read-side schema should support:

- durable latest projection state per order
- durable projection worker progress
- restart survival
- future PostgreSQL-backed projection store implementation
- future PostgreSQL-backed checkpoint store implementation
- future replay / rebuild from accepted history
- future Layer 2 comparison between replayed expected state and persisted projection state

The baseline schema should not force the final worker cursor strategy before the PostgreSQL-backed worker exists.

---

# Table 1: `projection_states`

## Purpose

The `projection_states` table stores the latest derived runtime view for each order.

It is the durable equivalent of the current in-memory projection state store.

It should be treated as rebuildable derived state.

If projection state becomes corrupted, stale, or inconsistent, the recovery path should be:

```text
accepted history
→ canonical projection reducer
→ rebuilt projection state
```

not:

```text
mutate accepted history to match projection state
```

---

## Proposed Core Columns

- `order_id`
- `status`
- `total_amount`
- `paid_amount`
- `version`
- `last_sequence`
- `updated_at`

---

## Why These Columns Exist

### `order_id`

The primary identity of the projected order view.

For the current domain, one order should have one latest derived projection state.

A future generalized projection framework may rename this concept, but Stage 3.5C should stay aligned with the current order domain.

### `status`

The latest derived order status.

The allowed status vocabulary follows the hardened domain-state vocabulary already used by Stage 3.5C PR0:

```text
INIT
CREATED
PAID
```

### `total_amount`

The total order amount derived from accepted history.

This value must preserve exact money semantics.

### `paid_amount`

The paid amount derived from accepted history.

This value should not exceed `total_amount` in the current domain baseline.

### `version`

The derived projection version for the order.

This should correspond to the aggregate-local event progress represented by accepted history for that order.

### `last_sequence`

The last aggregate-local sequence applied to this order's projection state.

This is intentionally local to one order.

It is valid for `projection_states` because each row represents one order.

It must not be confused with the worker-level checkpoint cursor.

### `updated_at`

The database update time for the derived projection row.

This is operational metadata for the projection view.

It is not the domain event occurrence time and not the accepted-history append time.

---

## Suggested Draft Shape

A first migration should look conceptually like:

```sql
CREATE TABLE IF NOT EXISTS projection_states (
    order_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    paid_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    version INTEGER NOT NULL,
    last_sequence INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_projection_states_order_id_not_empty
        CHECK (length(trim(order_id)) > 0),

    CONSTRAINT ck_projection_states_status
        CHECK (status IN ('INIT', 'CREATED', 'PAID')),

    CONSTRAINT ck_projection_states_total_amount_non_negative
        CHECK (total_amount >= 0),

    CONSTRAINT ck_projection_states_paid_amount_non_negative
        CHECK (paid_amount >= 0),

    CONSTRAINT ck_projection_states_paid_amount_not_exceed_total_amount
        CHECK (paid_amount <= total_amount),

    CONSTRAINT ck_projection_states_version_non_negative
        CHECK (version >= 0),

    CONSTRAINT ck_projection_states_last_sequence_non_negative
        CHECK (last_sequence >= 0)
);
```

---

## Baseline Role of `projection_states`

The `projection_states` table is:

- durable derived runtime state
- one latest view per order
- query-friendly
- restart-safe
- replaceable through rebuild
- future Layer 2 comparison target

It is **not**:

- accepted history
- the write-side source of truth
- a substitute for `order_events`
- a rejected-candidate audit table
- a runtime decision table
- a semantic outcome table
- a snapshot table

---

# Table 2: `projection_checkpoints`

## Purpose

The `projection_checkpoints` table stores durable projection worker progress.

It answers:

> where did this worker last stop scanning accepted history?

It does not answer:

> is the business state correct?

Checkpoint state is operational progress metadata.

It must not be treated as business truth.

---

## Why `last_processed_sequence` Is Not Used

The checkpoint table intentionally does **not** use:

```text
last_processed_sequence INTEGER
```

because `order_events.sequence` is aggregate-local.

The current accepted-history table protects stream order through:

```text
(order_id, sequence)
```

That means:

```text
Order A sequence 1, 2
Order B sequence 1, 2
Order C sequence 1, 2
```

This is correct for aggregate replay.

But it is not a global event-log cursor.

A background projection worker needs a cursor over the whole accepted-history stream, not only one order stream.

Therefore, this PR1 boundary rule is required:

> `projection_checkpoints` must not store `last_processed_sequence` as the worker checkpoint.

That name would incorrectly imply that `order_events.sequence` is a global worker offset.

---

## Proposed Core Columns

- `worker_name`
- `cursor_kind`
- `cursor_value`
- `updated_at`

---

## Why These Columns Exist

### `worker_name`

Identifies the projection worker or projection pipeline whose progress is being tracked.

For the first durable read-side baseline, this can be a stable logical worker name.

### `cursor_kind`

Declares what kind of cursor is stored in `cursor_value`.

This keeps the checkpoint schema honest about the fact that the final event-log scanning strategy is not decided in PR1.

Allowed baseline values:

```text
UNSPECIFIED
APPENDED_AT
EVENT_ID
GLOBAL_POSITION
```

### `cursor_value`

Stores the actual cursor token.

It is text because the cursor token may later be:

- an ISO-8601 timestamp
- an accepted event id
- a global numeric position encoded as text
- another stable token selected by the PostgreSQL-backed worker design

### `updated_at`

The database update time for the worker checkpoint row.

This helps with operational inspection.

It is not a freshness guarantee by itself.

---

## Suggested Draft Shape

A first migration should look conceptually like:

```sql
CREATE TABLE IF NOT EXISTS projection_checkpoints (
    worker_name TEXT PRIMARY KEY,

    cursor_kind TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    cursor_value TEXT NOT NULL DEFAULT '',

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_projection_checkpoints_worker_name_not_empty
        CHECK (length(trim(worker_name)) > 0),

    CONSTRAINT ck_projection_checkpoints_cursor_kind
        CHECK (cursor_kind IN (
            'UNSPECIFIED',
            'APPENDED_AT',
            'EVENT_ID',
            'GLOBAL_POSITION'
        )),

    CONSTRAINT ck_projection_checkpoints_value_alignment
        CHECK (
            (cursor_kind = 'UNSPECIFIED' AND cursor_value = '') OR
            (cursor_kind = 'GLOBAL_POSITION' AND cursor_value ~ '^[0-9]+$') OR
            (
                cursor_kind = 'EVENT_ID'
                AND trim(cursor_value) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) OR
            (cursor_kind = 'APPENDED_AT' AND length(trim(cursor_value)) > 0)
        )
);
```

---

## Checkpoint Cursor Strategy

Stage 3.5C PR1 does not decide the final PostgreSQL worker scanning strategy.

It only creates a durable place to store the worker cursor.

Possible future strategies include:

### `APPENDED_AT`

The worker scans accepted history by database append time.

This avoids introducing a global position column, but it requires careful handling of:

- same-timestamp events
- transaction visibility
- late commits
- overlap scanning
- de-duplication by accepted event identity

### `GLOBAL_POSITION`

The worker scans accepted history by a global monotonic event-log position.

This would likely require a later write-side migration that adds a global event-log position to `order_events`.

This strategy is easier to reason about for deterministic replay, auditability, and Compass Layer 2 validation.

It introduces a global ordering point during insert, but it gives the read-side worker a simple and stable cursor.

### `EVENT_ID`

The worker uses event identity as a cursor or tie-breaker.

This may be useful as a secondary ordering component, but event identity alone should not be assumed to encode commit order unless the chosen identity policy explicitly supports that.

### CDC / WAL-Based Stream

A later production-grade system may use Change Data Capture or logical replication to consume committed database changes.

This is intentionally outside Stage 3.5C PR1.

---

## Preferred Future Direction

For this project's current goals, the preferred future direction is likely `GLOBAL_POSITION`.

Reason:

The project prioritizes:

- deterministic replay
- auditability
- semantic validation
- Compass Layer 2 drift detection
- action-safety reasoning

over maximum write throughput.

A global event-log position makes projection worker behavior easier to test, replay, resume, and explain.

PR1 deliberately avoided introducing `order_events.global_position`.

That decision was later made in Stage 3.5C PR4 when the PostgreSQL-backed projection worker was introduced.

---

# Constraint Philosophy

Database constraints in the read-side schema protect **minimum valid shape**.

They should reject impossible or malformed rows such as:

- empty projection identity
- unknown projection status
- negative money values
- paid amount greater than total amount
- negative projection version
- negative aggregate-local last sequence
- empty worker name
- unknown cursor kind
- cursor kind / cursor value mismatch

They do **not** prove that projection state is faithful to accepted history.

That belongs to future replay / rebuild checks and Compass Layer 2 validation.

---

# Deferred Projection State Semantic Constraints

Stage 3.5C PR1 intentionally does not add cross-field domain constraints such as:

```sql
status = 'PAID' implies paid_amount = total_amount
```

or:

```sql
status = 'CREATED' implies paid_amount = 0
```

Although these rules may match the current simplified order domain, they would turn the durable read-side table into a partial domain validator.

At PR1, the database protects the physical shape of derived projection state and checkpoint cursor consistency.

Projection semantic correctness belongs to the canonical reducer path and, later, Compass Layer 2 validation.

This leaves room for future tests where a reducer bug produces a physically valid but semantically wrong projection state.

For example:

```text
status = CREATED
paid_amount = 100
total_amount = 100
```

This row is physically valid under PR1 shape constraints, but it may be semantically wrong under the current domain model.

Such cases should become future Compass Layer 2 drift-detection cases rather than being hidden by a database CHECK constraint.

---

# Rebuild Rule

Projection state must remain rebuildable.

If projection state is lost, stale, or inconsistent, the authoritative recovery path is:

```text
order_events
→ canonical projection reducer
→ rebuilt projection_states
```

The `projection_states` table should be treated as a durable cache of derived truth, not as sovereign truth.

---

# Relation to Replay Validation and Future Layer 2

Stage 3.5C PR1 created the durable target that later validation can inspect.

Stage 3.5C PR5 now compares:

```text
accepted-history replay result
vs
persisted projection state
```

to detect:

- matching projection state
- missing projection state
- projection drift
- no accepted history for the target order

Future Compass Layer 2 may build on that evidence to classify semantic severity and connect drift detection to runtime decisions.

PR1 created the durable read-side shape required before that validation became meaningful.

---

# Current Design Decisions

At the current stage, the following are directionally accepted:

- `projection_states` stores latest derived state per order
- `projection_states.last_sequence` is aggregate-local progress
- `projection_checkpoints` stores worker-level scan cursor state
- `projection_checkpoints` must not use aggregate-local `sequence` as a global worker offset
- final cursor strategy is deferred until the PostgreSQL-backed worker exists
- `cursor_kind` and `cursor_value` preserve cursor flexibility without lying about current event-log shape
- future `GLOBAL_POSITION` is likely preferred if the project continues to prioritize deterministic replay and auditability
- read-side state remains derived and rebuildable

---

# Resolved and Deferred Questions

Stage 3.5C resolved the following questions:

- Stage 3.5C PR4 introduced `order_events.global_position`.
- PR4 chose `GLOBAL_POSITION` as the first PostgreSQL-backed projection worker cursor strategy.
- PR4 coordinated projection state and checkpoint progress in one read-side transaction.
- PR5 added durable replay / rebuild validation against accepted history.

The following remain deferred:

- whether `APPENDED_AT` polling is ever needed for a different workload
- whether `accepted_event_id` should be used as a tie-breaker for future cursor strategies
- whether checkpoint rows should eventually include heartbeat / freshness fields
- whether one worker checkpoint is sufficient for multiple future projection pipelines
- whether rebuild should reset checkpoints or use a separate rebuild cursor
- how snapshot-assisted replay should be trusted in Stage 3.5D

---

# Summary

The first durable read-side schema baseline should not merely create tables.

It should preserve:

- source-of-truth separation
- derived state semantics
- worker checkpoint semantics
- restart survival
- future replay / rebuild ability
- future Layer 2 comparability

That is why the initial durable read-side schema separates:

```text
projection_states
= derived per-order runtime view

projection_checkpoints
= worker-level scan cursor metadata
```

The most important PR1 checkpoint decision is negative:

> Do not store `last_processed_sequence` as the worker checkpoint.

`order_events.sequence` is aggregate-local.

The worker cursor must remain a separate concept.

---

## Closing Rule

The most important reminder preserved from Stage 3.5C PR1 is:

> Do not let durable read-side state redefine accepted history.

If the read-side currently depends on:

- pure reducer logic
- checkpoint-aware worker progress
- replay / rebuild ability
- projection state as derived view

then those guarantees must now be translated into:

- schema shape
- constraint choices
- checkpoint cursor vocabulary
- tests
- documentation

That is the real work of Stage 3.5C PR1.