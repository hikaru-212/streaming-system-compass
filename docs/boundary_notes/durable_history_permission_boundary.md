# Durable History Permission Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the durable-history permission boundary introduced in:

```text
Stage 3.5E — Durable History and Permission Hardening
```

The boundary exists because not all durable tables have the same semantic authority.

Accepted history is the source of truth.

Derived runtime artifacts are not.

Therefore, the system should not treat all durable mutation paths as equivalent.

---

## Core Rule

```text
accepted history should be harder to mutate than derived runtime state
```

This rule follows from the project’s existing authority model:

```text
accepted history = authority
projection state = derived runtime view
checkpoint = operational progress metadata
snapshot = derived state compression
```

If these tables have different semantic authority, then their mutation boundaries should also differ.

---

## Why This Boundary Matters

A system can technically succeed while corrupting business meaning.

For earlier stages, the project focused on preventing invalid candidate events from entering accepted history and proving that derived state still matches accepted history.

Stage 3.5E adds another protection:

```text
even after durable persistence exists,
not every runtime actor should be able to mutate every durable table
```

This is not only a security concern.

It is a semantic correctness concern.

If accepted history can be updated, deleted, or rewritten through the same assumptions used for derived state, then the system weakens its own authority model.

---

## Table Authority Levels

### `order_events`

```text
authority level: accepted history
mutation posture: append-oriented / restricted
```

`order_events` stores accepted facts.

Once an event enters accepted history, downstream systems may depend on it:

```text
aggregate replay
projection runtime
rebuild validation
snapshot trust validation
analytics
future runtime governance
```

Therefore, accepted history should not be casually updated or deleted.

The intended direction is:

```text
candidate event
→ Compass Layer 1 admission
→ concurrency / idempotency boundary
→ append accepted event
```

Mutation paths outside the intended append flow should be restricted.

---

### `idempotency_records`

```text
authority level: request-effect memory
mutation posture: controlled write-side support
```

`idempotency_records` does not define business truth by itself.

However, it protects request-level effect semantics.

It helps distinguish:

```text
safe replay
vs
conflicting duplicate request
```

Its mutation rights should remain tied to the write-side transactional boundary.

It should not be treated like projection state.

---

### `projection_states`

```text
authority level: derived read-side state
mutation posture: controlled but mutable
```

`projection_states` stores derived read models.

Projection state is useful for runtime reads, but it is not authority.

It can drift.

It can be cleared.

It can be rebuilt.

It can be compared against accepted-history replay.

Therefore, Stage 3.5E should not make projection state append-only or impossible to update.

The correct boundary is:

```text
projection state is mutable through controlled projection runtime paths
but does not have accepted-history authority
```

---

### `projection_checkpoints`

```text
authority level: operational progress metadata
mutation posture: controlled but mutable
```

`projection_checkpoints` records worker progress.

A checkpoint tells the system how far a projection worker has processed.

It does not prove business correctness.

It is operational metadata.

Therefore, checkpoints must remain mutable by controlled worker / rebuild flows.

However, unrestricted mutation is still dangerous because a bad checkpoint may cause skipped replay, repeated replay, or confusing recovery behavior.

The correct boundary is:

```text
checkpoint mutation is allowed,
but only through intended operational roles / runtime paths
```

---

### `projection_snapshots`

```text
authority level: derived state compression
mutation posture: evidence-oriented insertion / controlled selection
```

`projection_snapshots` stores derived state-compression artifacts.

A snapshot may speed up replay, but it is not accepted history.

A snapshot can only participate in a fast path after trust qualification.

The important distinction is:

```text
latest persisted snapshot
≠
latest trusted snapshot
```

A snapshot table may allow insertion of new snapshot artifacts, but the system must not treat snapshot existence as proof of trust.

The permission boundary should protect snapshot evidence without making snapshots authoritative.

---

## Permission Boundary vs Semantic Admission

Stage 3.5E permission hardening is not the same as Compass Layer 1.

Compass Layer 1 asks:

```text
Should this candidate event be allowed to become accepted history?
```

Stage 3.5E asks:

```text
Is this actor / runtime component allowed to mutate this durable table through this path?
```

These two checks protect different failure modes.

A candidate event may be semantically valid but submitted through an unauthorized mutation path.

A runtime actor may have permission to use a path, but Compass may still reject the candidate event as semantically invalid.

The system needs both boundaries.

---

## Permission Boundary vs Transaction Atomicity

Transaction atomicity is not permission hardening.

A transaction can atomically commit the wrong mutation.

Stage 3.5E does not replace transactional consistency.

It adds a separate question:

```text
Should this component have the authority to perform this mutation at all?
```

This continues the project’s existing distinction between:

```text
technical success
and
semantic correctness
```

---

## Minimal Actor Model

Stage 3.5E may introduce a minimal actor vocabulary.

The purpose is not to model human users fully.

The purpose is to distinguish runtime responsibilities.

Possible actor categories:

```text
application writer
projection worker
snapshot worker
migration owner
read-only observer
future governance runtime
```

Possible metadata:

```text
actor_id
actor_type
actor_role
created_by
triggered_by
runtime_component
```

This metadata should remain minimal.

It exists to prepare for future Stage 4 concepts such as:

```text
DecisionReceipt
RuntimeDecisionPolicy
repair / rebuild / quarantine evidence
privileged runtime action records
```

---

## Non-goals

This boundary does not introduce:

```text
full RBAC
login
JWT
session management
multi-tenant auth
cloud IAM
secret manager integration
user account management
UI permissions
audit dashboard
Compass Layer 2
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
action safety gate
agent sandboxing
```

Those are later concerns.

Stage 3.5E only establishes the minimum durable mutation boundary needed before those later governance layers can be meaningful.

---

## Expected Invariants

Stage 3.5E should move the project toward these invariants:

```text
accepted history cannot be casually updated or deleted

accepted-history append paths remain explicit and controlled

projection state remains rebuildable

checkpoint progress remains operationally mutable

projection snapshots remain derived evidence, not authority

read-only actors cannot mutate durable state

runtime actors have narrower table-specific responsibilities

future receipts can identify who or what produced privileged evidence or action
```

---

## Summary

The durable-history permission boundary protects the project’s authority model.

It does not make the system a full auth platform.

It makes one thing explicit:

```text
the table that defines truth
must not have the same mutation posture
as tables that merely derive, compress, or track runtime state
```

That is the Stage 3.5E boundary.
