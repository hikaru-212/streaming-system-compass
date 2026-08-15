# Drift Validation Cost Boundary

[← Back to Stage 4A](README.md)

## Purpose

This note records the cost boundary between different drift and validation paths discussed during Stage 4A PR3.

It exists to prevent the project from treating all replay-based validation as the same kind of cost.

The core distinction is:

```text
projection_state drift validation
≠
snapshot trust validation
≠
global projection consistency validation
```

They may all compare derived state against accepted history, but they do not have the same replay scope or runtime purpose.

---

## Core Authority Model

The authority model remains:

```text
accepted history = authority
projection state = derived runtime view
snapshot = derived state compression
checkpoint = operational progress metadata
```

A drift signal exists because derived state can diverge from authority.

The existence of `DRIFT` does not mean the system must check drift on every read request.

It means that when divergence is detected, the system has a stable semantic name for the condition.

---

## Order Identity Boundary

For the current order/payment model:

```text
order_id = order aggregate identity
```

It is not a product identifier.

The same `order_id` may appear multiple times in `order_events` because a single order has multiple events.

Different users buying the same product should produce different `order_id` values.

A product identifier, if introduced later, should be separate from `order_id`.

This matters because order-scoped validation should replay only events for one aggregate:

```text
order_events where order_id = ?
```

not the entire global event log.

---

## Projection State Drift Validation

Projection state drift validation compares:

```text
accepted-history replay for one order_id
vs
projection_states[order_id]
```

For the current domain, an order usually has only a few events, such as:

```text
ORDER_CREATED
PAYMENT_RECORDED
```

Therefore the validation cost is usually:

```text
O(number_of_events_for_this_order_id)
```

not:

```text
O(total_global_event_log_size)
```

This means order-scoped projection drift validation is relatively cheap in the current project.

It may still be used as a validation, audit, diagnostic, or repair path rather than as a mandatory step before every read.

---

## Projection Drift Example

Accepted history for one order:

```text
order-001 event 1: ORDER_CREATED(total_amount=100)
order-001 event 2: PAYMENT_RECORDED(paid_amount=100)
```

Authority replay produces:

```text
status = PAID
paid_amount = 100
state_version = 2
```

Persisted projection state contains:

```text
status = CREATED
paid_amount = 0
state_version = 1
```

The projection state differs from the accepted-history replay result.

This is projection state drift:

```text
technical_status = DRIFT
boundary = LAYER_2_READ_SIDE
semantic_code = DRIFT_DETECTED
```

This may indicate that the projection worker missed an event, advanced a checkpoint incorrectly, applied a reducer bug, or had its derived state mutated incorrectly.

---

## Snapshot-Assisted Drift Validation

Snapshot-assisted drift validation compares:

```text
snapshot + tail replay
vs
full accepted-history replay
```

This path is useful for proving whether a snapshot-assisted reconstruction matches authority.

However, if it is run before every runtime request, it can defeat the purpose of the snapshot fast path.

The expensive demonstration path is:

```text
full accepted-history replay
+ snapshot load
+ tail replay
+ comparison
```

This is different from replaying a small number of events for one order-scoped projection check.

Snapshot trust validation should therefore be treated as:

```text
trust bootstrap
audit / revalidation
suspicious-path validation
receipt-producing validation in future stages
```

not as the steady-state path for every request.

---

## Snapshot-Assisted Drift Example

Accepted history for one order:

```text
order-001 event 1: ORDER_CREATED(total_amount=100)
order-001 event 2: PAYMENT_RECORDED(paid_amount=100)
```

Full accepted-history replay produces:

```text
status = PAID
paid_amount = 100
state_version = 2
```

A snapshot claims to represent the state after event 1:

```text
source_event_sequence = 1
status = CREATED
paid_amount = 20
state_version = 1
```

But after event 1, paid amount should be 0.

If snapshot-assisted replay applies event 2 to the corrupted snapshot, it may produce:

```text
status = PAID
paid_amount = 120
state_version = 2
```

That differs from authority replay.

This is snapshot-assisted drift:

```text
technical_status = SNAPSHOT_ASSISTED_DRIFT
boundary = SNAPSHOT_TRUST
semantic_code = DRIFT_DETECTED
```

---

## Global Projection Consistency Validation

Global projection consistency validation is different again.

It may check whether a projection worker processed a global range of accepted events without gaps, corruption, or checkpoint inconsistency.

Its replay scope may be:

```text
many orders
large global_position range
entire projection partition
```

This can be expensive.

It should not be confused with order-scoped projection drift validation.

Global consistency checks belong closer to future diagnostic, measurement, repair, or operational governance work.

---

## Cost Comparison

| Validation path | Replay scope | Current expected cost | Steady-state path? |
|---|---|---:|---|
| Write-side aggregate replay | one `order_id` | low | yes, acceptable |
| Projection state drift check | one `order_id` | low in current domain | audit / diagnostic / optional check |
| Snapshot trust validation | snapshot boundary + authority comparison | higher | no, should not run every request |
| Global projection consistency | global event range / many orders | high | no, governance / diagnostic path |

The important rule is:

```text
Do not treat every replay as full global event-log replay.
```

For order-scoped validation, replay should be scoped by aggregate identity.

---

## Why DRIFT Still Matters

The system still needs `DRIFT` because derived state can diverge from accepted history.

The goal is not to check drift on every read.

The goal is to make detected divergence machine-readable and governable.

When projection state does not match authority, the system should not emit only a raw exception or string mismatch.

It should be able to produce:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
boundary = LAYER_2_READ_SIDE
```

When snapshot-assisted reconstruction does not match authority, the system should be able to produce:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
boundary = SNAPSHOT_TRUST
```

The same semantic code can appear under different boundaries because the recovery path may differ later.

---

## Design Rules

```text
Projection drift validation may be cheap when scoped by aggregate identity.

Snapshot trust validation should not be repeated before every fast-path request.

Global consistency validation should not be confused with order-scoped drift validation.

DRIFT is a semantic name for detected derived-state divergence, not a requirement to full replay on every read.

Stage 4A describes the semantic meaning.
Stage 4B may preserve receipts.
Stage 4D may decide when validation or fast-path use is cost-appropriate.
```

---

## Relationship to Stage 4B.2

This note is not a benchmark matrix.

It is a precursor to Stage 4B.2 measurement vocabulary.

Later measurement work may record fields such as:

```text
authority_replay_ms
snapshot_replay_validation_ms
resolver_elapsed_ms
accepted_event_count
tail_event_count
snapshot_used
receipt_used
fallback_used
```

At Stage 4A, the goal is only to preserve the conceptual cost boundary so future measurement and strategy selection do not confuse semantically different validation paths.
