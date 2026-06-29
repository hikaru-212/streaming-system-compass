# ADR 0014: Defer Projection Events as a Separate Delivery Layer

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted as a deferral decision.

No separate durable `projection_events` stream, projection-event table, projection delivery log, or first-class projection event model is introduced in the current baseline.

The current implementation continues to treat accepted history as the authoritative event source.

Read-side projection records, event-source envelopes, checkpoint records, and snapshot-assisted resolver inputs are derived consumption artifacts, not a second event-truth layer.

This decision is implemented by omission and boundary preservation across Stage 3.5C and Stage 3.5D.

Related implementation notes that preserve this boundary:

- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

Future work may revisit this decision only if the project needs a separate projection-delivery layer, durable read-side delivery log, multi-projection fanout coordination, projection DLQ, durable worker-attempt evidence, or production-grade projection retry auditing.

---

## Context


The current system uses accepted history as the authority log.

```text
order_events = accepted history / source of truth
```

Projection replay currently reads accepted events directly from `order_events` by `global_position`.

```text
order_events
→ PostgresProjectionEventSource.load_after(global_position)
→ projection reducer / snapshot-assisted resolver
```

This means the current projection event source is not a separate `projection_events` table. It is a read-side adapter over the accepted event log.

At this stage, this is intentional.

The system already has:

```text
accepted history
global_position cursor
projection replay
projection checkpoints
projection snapshots
snapshot-assisted replay validation
snapshot-assisted state resolution
```

These are sufficient for Stage 3.5D’s goal:

```text
accepted history = authority
snapshot = derived state compression
snapshot + tail replay = read-side fast path
validator = evidence against authority
resolver = safe read-side resolution primitive
```

A separate `projection_events` table or projection delivery log could be introduced later, but it would not create new business truth. It would create a delivery / fanout / worker-governance layer.

---

## Decision

Do not introduce a separate `projection_events` table in Stage 3.5D.

Continue using `order_events` as the projection replay source for now.

```text
order_events
→ projection tail source
→ reducer / validator / resolver
```

If a projection delivery layer is introduced later, it must be treated as a derived delivery artifact, not as semantic authority.

The source of truth remains:

```text
order_events / accepted history
```

A future projection delivery layer may be represented as one of:

```text
projection_dispatch_records
projection_inbox
projection_delivery_log
projection_work_items
```

The naming should make clear that it is a delivery mechanism, not a second event truth.

---

## Rationale

A separate projection delivery layer is not required for the current architecture.

The current system has a single durable event log with global ordering. This allows projection workers, validators, and resolvers to replay accepted events directly.

Adding a `projection_events` table now would introduce a new correctness surface before the system needs it.

It would require answers to questions such as:

```text
What happens if order_events exists but projection_events is missing?
What happens if projection_events exists but order_events is missing?
What happens if projection_events payload differs from order_events?
How are duplicate delivery records handled?
How are out-of-order delivery records handled?
How are worker retry attempts tracked?
How are poison events handled?
How is projection lag measured?
How is delivery reconciliation performed?
```

These are real production concerns, but they belong to a delivery / worker-governance layer, not to the Stage 3.5D snapshot trust contract.

---

## Source of Truth Boundary

A future projection delivery layer must not become a second source of truth.

The boundary is:

```text
order_events
= accepted facts
= authority
= what happened

projection_events / projection_dispatch_records
= delivery records
= worker inbox
= what needs to be processed or retried

projection_states
= derived read model
= what the read side currently shows

projection_snapshots
= derived state compression
= optimization, not authority
```

If there is any conflict, `order_events` wins.

Examples:

```text
order_events has an event, projection_events is missing it
→ delivery gap; regenerate delivery record from accepted history

projection_events has an event, order_events does not
→ invalid delivery artifact; reject or quarantine

projection_events payload differs from order_events
→ delivery corruption; rebuild from accepted history

projection_events is behind order_events
→ projection delivery lag; monitor and catch up
```

The system must never repair accepted history from projection delivery records.

The repair direction is always:

```text
accepted history
→ delivery layer
→ derived read model
```

---

## Consequences

### Positive Consequences

The current architecture remains simpler.

Stage 3.5D can stay focused on snapshot trust, replay validation, and read-side resolution without introducing worker delivery correctness.

The source of truth remains unambiguous:

```text
accepted history is authority
```

Projection replay can still be deterministic because `order_events` already provides a global-position-ordered event source.

The system avoids prematurely introducing:

```text
delivery gaps
delivery retries
dispatch records
dead-letter handling
worker attempt logs
projection delivery reconciliation
```

### Negative Consequences

The current design does not yet provide first-class delivery tracking for multiple projection consumers.

It does not yet record per-consumer worker attempts, delivery retries, or dead-letter state.

If the system grows to support many independent projections, direct replay from `order_events` may become operationally less convenient.

The system may eventually need a separate delivery layer for fanout, backpressure, retry governance, and observability.

---

## Future Trigger Conditions

Revisit this decision when one or more of the following become true:

```text
1. Multiple independent projection consumers exist.
2. Each projection requires independent delivery status.
3. Worker retry attempts must be tracked durably.
4. Dead-letter handling becomes necessary.
5. Projection lag needs first-class observability.
6. Projection delivery must cross service or database boundaries.
7. Direct reads from order_events become too expensive or operationally unsafe.
8. Runtime policy needs to disable, retry, or reroute specific projection consumers.
9. Stage 4 DecisionReceipt / RetryGovernance requires durable worker attempt evidence.
```

At that point, introduce a projection delivery layer as an Enabler, not as Core authority.

---

## Relationship to Compass

In Compass terms:

```text
order_events / accepted history
= Core authority

projection delivery layer
= Enabler / worker-governance substrate

projection_states
= derived read-side state

projection_snapshots
= derived state compression

validator
= checks derived state against authority

resolver
= attempts safe read-side resolution from trusted snapshot + tail
```

A projection delivery layer may later support:

```text
DecisionReceipt
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
worker health policy
projection lag observability
```

This makes it closer to Stage 4 / Stage 5 work than Stage 3.5D.

---

## Current Decision Summary

Do not add `projection_events` in Stage 3.5D.

Current model:

```text
event_log = truth
projection source = adapter over event_log
projection state = derived result
snapshot = derived compression
```

Future model, if needed:

```text
event_log = truth
projection delivery layer = worker control / fanout / retry substrate
projection state = derived result
snapshot = derived compression
```

The decision can be revisited when delivery complexity becomes real enough to justify a separate delivery layer.
