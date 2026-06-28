# Postmortem: From Per-Order Global Position to Global Source Boundary

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-14

## Summary

This note records a schema-boundary correction discovered during **Stage 3.5D PR2 — Projection Snapshot Schema Baseline**.

The initial projection snapshot uniqueness model treated `source_global_position` as if it were scoped by `order_id`.

That was wrong.

The confusion came from reading all snapshot source-boundary fields as if they shared the same scope.

They do not.

The corrected model is:

```text
source_event_sequence
= order-local accepted event sequence
= unique together with order_id

source_global_position
= global accepted-history cursor
= globally unique

source_event_id
= accepted event identity
= globally unique
```

This postmortem exists to preserve the rule that database uniqueness scope must match the semantic scope of the boundary being stored.

---

## 1. Trigger Question

The trigger was a discomfort with this test shape:

```text
allows same global position for different orders
```

At first, the test looked like a normal companion to:

```text
allows same source sequence for different orders
```

But the two cases are not equivalent.

It is valid for two different orders to have the same local sequence:

```text
order-001, source_event_sequence = 1
order-002, source_event_sequence = 1
```

It is not valid for two different accepted events to have the same global position:

```text
order-001, source_global_position = 1
order-002, source_global_position = 1
```

The question was therefore:

> If `global_position` is a global event-log cursor, why would the snapshot table allow different orders to share the same value?

That question exposed the schema mistake.

---

## 2. The Deeper Realization

The deeper realization was that source-boundary fields can look similar in a table while representing different scopes.

The projection snapshot table stores:

```text
order_id
source_event_id
source_event_sequence
source_global_position
```

Because these fields sit next to each other, it was tempting to make both source-boundary uniqueness rules include `order_id`:

```text
UNIQUE(order_id, source_event_sequence)
UNIQUE(order_id, source_global_position)
```

Only the first rule is correct.

`source_event_sequence` is local to one order stream.

`source_global_position` is not.

It belongs to the global accepted event log.

The mistake was copying the local stream-boundary pattern onto a global cursor.

---

## 3. Why The Symmetry Was Misleading

The misleading symmetry was:

```text
order_id + source_event_sequence
order_id + source_global_position
```

This shape looks consistent, but it hides a semantic mismatch.

### Source sequence case

```text
source_event_sequence
```

answers:

> Which event number is this inside one order stream?

Therefore it needs the stream identity:

```text
order_id + source_event_sequence
```

### Global position case

```text
source_global_position
```

answers:

> Which event position is this inside the global accepted-history timeline?

Therefore it should not need `order_id` to be unique.

If two rows need different `order_id` values to disambiguate the same `source_global_position`, then the position is not really global.

---

## 4. What The Initial Schema Allowed

The initial schema shape allowed:

```text
order-001, source_global_position = 1
order-002, source_global_position = 1
```

That would imply one of two bad meanings:

1. `source_global_position` is not actually global.
2. two different accepted events can occupy the same global event-log position.

Both meanings violate the Stage 3.5C global-position projection worker model.

In that model, global position is the event-log cursor used to consume accepted events in one durable order.

A global position should point to one accepted-history boundary.

It should not become a per-order lineage number.

---

## 5. Corrected Schema Model

The corrected PR2 schema uses:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

This preserves three different identities.

| Field / Boundary | Scope | Database rule |
|---|---|---|
| `source_event_id` | accepted event identity | globally unique |
| `order_id + source_event_sequence` | order-local event boundary | composite unique |
| `source_global_position` | global accepted-history cursor | globally unique |

This means:

```text
same source_event_sequence across different orders
→ allowed

same source_global_position across different orders
→ rejected

same source_event_id across different rows
→ rejected
```

The corrected schema now matches the intended event-sourcing semantics.

---

## 6. Test Correction

The wrong test encoded the wrong mental model:

```text
test_projection_snapshot_allows_same_global_position_for_different_orders
```

That test was removed.

The corrected tests verify:

```text
duplicate source_global_position is rejected across orders
duplicate source_event_id is rejected across rows
same source_event_sequence is allowed across different orders
```

The tests now document the boundary directly:

```text
sequence is local
global_position is global
source_event_id is global
```

This is important because schema tests are not just regression tests.

In this project, they also preserve architectural meaning.

---

## 7. Deferred Versioned Boundary

PR2 intentionally keeps `source_event_id` and `source_global_position` globally unique.

This is appropriate for the current baseline:

```text
single active reducer version
single active snapshot schema version
one projection snapshot row per accepted event boundary
```

A future stage may support multiple reducer versions or multiple snapshot schema versions for the same accepted-history boundary.

If that happens, the schema may need to migrate from single-boundary uniqueness to a versioned-boundary model:

```text
UNIQUE(source_event_id, reducer_version, snapshot_schema_version)
UNIQUE(source_global_position, reducer_version, snapshot_schema_version)
UNIQUE(order_id, source_event_sequence, reducer_version, snapshot_schema_version)
```

That future model would allow more than one snapshot row for the same accepted event boundary, but only when the rows belong to different reducer or snapshot schema versions.

That is not part of PR2.

If implemented later, the migration must be paired with store and validator changes.

Snapshot loading must qualify the snapshot by supported runtime versions:

```text
WHERE reducer_version = supported reducer version
  AND snapshot_schema_version = supported schema version
```

Otherwise the runtime could load a snapshot produced by the wrong logic version.

---

## 8. Why This Was Caught Early

This mistake was caught before PR2 completion because the test names were semantically uncomfortable.

The key signal was not a failing test.

The key signal was a test that passed while describing an impossible event-log reality:

```text
same global position for different orders
```

This is a useful lesson.

Passing tests can still encode the wrong model.

A test should be reviewed not only for whether it passes, but for whether the world it describes is valid.

---

## 9. New Mental Model

The corrected mental model is:

```text
order-local boundary
→ must include order_id

global boundary
→ must not require order_id to be unique

accepted event identity
→ globally unique by definition
```

The word `global` should trigger a review question:

> Can two different accepted events legally have this same value?

For `source_event_sequence`, the answer is yes across different order streams.

For `source_global_position`, the answer is no.

For `source_event_id`, the answer is no.

---

## 10. Reusable Rule For Future Design

The reusable rule is:

> Do not infer uniqueness scope from column adjacency.
> Infer uniqueness scope from the semantic identity of the field.

A field can appear inside an order-specific table and still represent a global boundary.

For future schema design, especially around snapshots, checkpoints, replay cursors, and Layer 2 evidence, the review should ask:

1. Is this value local to one stream, worker, aggregate, or projection?
2. Is this value global across accepted history?
3. Does the database constraint preserve that exact scope?
4. Would this constraint allow two different accepted events to claim the same boundary?

This rule should be reused when designing:

- aggregate snapshots
- snapshot-assisted write-side rehydration
- replay evidence tables
- Layer 2 semantic outcome evidence
- future partitioned or sharded cursor models

---

## 11. What This Means For Snapshot Trust

Snapshot trust depends on lineage evidence.

Lineage evidence is only useful if its physical constraints preserve the same scope as the accepted-history boundary it claims to reference.

If `source_global_position` can be duplicated across different orders, then it no longer gives reliable global replay evidence.

If `source_event_id` can be duplicated across snapshot rows in the current single-version baseline, then the system can create competing snapshots for the same accepted event boundary.

The corrected schema keeps snapshot rows subordinate to accepted history by making their source-boundary evidence physically consistent with accepted history.

---

## 12. Final Postmortem Lesson

The final lesson is:

> A source-boundary field is not just metadata.
> It is a claim about where derived state came from.

If that claim says “global,” then the database must enforce it globally.

The corrected PR2 boundary is therefore:

```text
source_event_sequence is local
source_global_position is global
source_event_id is global
```

That sentence should be reused as the review rule for any future snapshot or replay-boundary schema.

---

## Suggested Follow-Up

Use this postmortem as a review reference for the rest of Stage 3.5D:

- PR3 `PostgresProjectionSnapshotStore` should preserve the corrected source-boundary model.
- PR4 snapshot-assisted replay validation should verify source-boundary evidence against accepted history.
- Future versioned snapshot coexistence should be introduced only through an explicit migration and version-aware store / validator behavior.
