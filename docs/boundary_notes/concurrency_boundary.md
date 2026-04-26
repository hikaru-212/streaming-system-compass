# Boundary Note: Concurrency module

[← Back to Boundary Notes Index](README.md)

## Purpose

This note clarifies where concurrency-related responsibilities belong in the transactional write-side path.

The goal is to prevent concurrency control, idempotency, semantic validation, and domain decision logic from collapsing into one ambiguous module.

This note is a practical boundary companion to [ADR 0003: Concurrency Control, Idempotency, and Retry Safety](../adr/0003_concurrency_idempotency_and_retry_safety.md).

---

## Core Boundary Statement

Concurrency control answers this question:

> Can this operation still write based on the current authoritative state?

It does **not** answer:

- whether the domain transition is meaningful
- whether the candidate event is semantically trustworthy
- whether the same request has already been processed
- whether downstream side effects have been delivered

Those belong to different boundaries.

---

## What the Concurrency Boundary Owns

The concurrency boundary owns the admission rule that prevents stale writes from becoming accepted writes.

In the baseline design, this means:

- compare the worker's expected version/status against authoritative storage
- allow the write only if the expected state still matches
- reject or fail the write if the entity has already moved forward
- force the caller to reload latest authoritative state after a failed conditional write

The central invariant is:

> A stale read may happen, but a stale write must not succeed.

---

## What the Concurrency Boundary Does NOT Own

The concurrency boundary does **not** own:

- domain transition rules
- event schema design
- proof/provenance meaning
- Compass validation semantics
- request retry identity
- downstream side-effect delivery
- projection state correctness

These belong elsewhere.

---

## Responsibility Split

| Component | Responsibility |
|---|---|
| Aggregate | Decides whether a domain transition is legal from its current reconstructed state. |
| Compass Transition Validator | Decides whether a candidate event truthfully represents the transition it claims. |
| Idempotency Store | Decides whether the same external request has already been processed. |
| Registry | Orchestrates the flow, but should not become the source of concurrency truth. |
| Event Store / Persistence Boundary | Owns expected-version checking or conditional append/write. |
| Projection | Consumes accepted history; it should not decide write-side admission. |
| Outbox | Future boundary for reliable downstream side-effect publication. |

---

## Relationship to Registry

The registry coordinates the write-side flow:

1. receive command
2. check idempotency
3. load or rehydrate aggregate
4. ask aggregate to produce candidate event
5. run Compass transition validation
6. ask persistence boundary to admit the event conditionally
7. handle success or failed admission

The registry may call the concurrency mechanism, but it should not treat its own local memory as authoritative truth.

A stateless registry aligns with this principle because it treats in-memory aggregate objects as short-lived execution objects rather than durable truth.

---

## Relationship to Event Store

For an event-sourced implementation, the event store is the natural concurrency boundary.

It can enforce:

```text
append event only if current stream version == expected_version
```

or in relational form:

```sql
UNIQUE(order_id, version)
```

The key rule is:

> only one event can become the next accepted version for a given aggregate stream.

---

## Relationship to Idempotency

Idempotency and concurrency are related in runtime, but they answer different questions.

Idempotency asks:

> Is this the same external operation being retried or redelivered?

Concurrency asks:

> Can this operation still write against the current authoritative state?

Therefore:

```text
same request_id
= retry / redelivery safety
= idempotency
```

```text
different request_id competing over same order
= concurrency control
```

The idempotency store should not decide competing write conflicts.  
The concurrency boundary should not decide whether two messages are the same external request.

---

## Relationship to Compass

Compass validation and concurrency admission are separate.

Compass answers:

> Is this candidate event semantically trustworthy?

Concurrency answers:

> Can this candidate event still be written as the next accepted fact?

A candidate event may pass Compass validation but still fail persistence admission if another event has already advanced the stream.

This distinction is important:

```text
semantic validity
≠
write admission freshness
```

---

## Failed Admission Flow

When conditional admission fails, the system should not blindly retry from the stale state.

The caller should:

1. reload latest authoritative state
2. classify the result
3. decide whether the command is:
   - already achieved
   - retryable under latest state
   - conflicting / rejected

This keeps failed writes explainable rather than treating every failure as a generic error.

---

## Future Strategy Options

The baseline strategy is optimistic version-based concurrency control.

If contention becomes high, future strategies may include:

- pessimistic locking for hot entities
- single-writer / actor-style processing per entity key
- partitioning or sharding by entity ID for higher overall throughput
- retry backoff and jitter to reduce retry storms

These are strategy options, not current semantic requirements.

They do not change the central invariant:

> stale writes must not become accepted writes.

---

## Summary

The concurrency boundary protects the accepted write-side history from stale writes.

It should remain separate from:

- domain decision logic
- Compass semantic validation
- request idempotency
- projection processing
- side-effect delivery

The clean mental model is:

```text
Aggregate decides domain legality.
Compass decides semantic trust.
Persistence decides admission freshness.
Idempotency decides retry identity.
```
