# Order Domain v1 Business Rules

[← Back to Domains Index](README.md)

## Scope: `INIT -> CREATED -> PAID`

This document defines the domain-level business rules for the current minimal write-side model.

The goal of this document is not to simulate a full commerce system yet.
Its purpose is to make the current v1 world explicit and internally coherent, especially around:

- domain legality
- amount semantics
- event/state alignment
- idempotency behavior ownership
- current scope boundaries and known future gaps

This document is intentionally different from:

- `docs/architecture/`, which describes system/module structure
- `docs/adr/`, which records architecture decisions
- `docs/roadmap/`, which records implementation milestones and sequencing

---

# 0. What This Document Defines

This document answers four questions:

1. What business actions are legal in the current minimal order model?
2. Which rules belong to the aggregate?
3. Which rules do **not** belong to the aggregate?
4. How should retry behavior be understood in relation to `request_id`?

---

# 1. Core Semantic Assumptions of v1

The current v1 world intentionally uses a very small semantic model.

In this model:

- `CREATED` means the order has been created
- `PAID` means the order has been **fully paid**
- `PAID` does **not** mean "one payment chunk was received"
- v1 does **not** support:
  - partial payment
  - split payment
  - payment accumulation
  - refund
  - reverse
  - cancel-after-paid
  - asynchronous external payment coordination
  - reconciliation workflows

This means the current model is **not** a full payment orchestration model.
It is only the first coherent transactional write-side baseline.

---

# 2. Identity and Request Concepts

## Rule ID1 — `order_id` is aggregate identity
`order_id` identifies the order aggregate / event stream.

It answers:
- which order this command/event belongs to
- which stream should be loaded and replayed

`order_id` is **not** derived from status.
It exists even when the aggregate is still at `INIT`.

---

## Rule ID2 — `request_id` is request identity
`request_id` identifies one command/request instance.

It answers:
- whether this request is a retry
- whether this request has already been processed
- which prior accepted result should be replayed, if any

`request_id` is **not** the same thing as:
- order identity
- product identity
- aggregate identity

---

## Rule ID3 — `event_id` is accepted-event identity
`event_id` identifies one accepted event.

A successfully processed request usually produces one accepted event.

Retrying the same request must not create a second new event.

---

# 3. Boundary of Responsibility

## 3.1 Aggregate is responsible for
The aggregate is responsible for:

- domain legality
- status transition legality
- amount-related business legality
- sequence decision for candidate events
- proof generation from current aggregate state

---

## 3.2 Aggregate is not responsible for
The aggregate is **not** responsible for:

- input schema validation
- external payload shape validation
- request retry detection
- request/result replay for idempotency
- transition-truth comparison against accepted history
- optimistic concurrency admission

---

## 3.3 Registry / orchestration layer is responsible for
The transactional orchestration layer is responsible for:

- idempotency lookup
- replay of prior accepted results when the same request is retried
- aggregate rehydration
- validation context construction
- calling validation runtime
- calling admission gate

---

## 3.4 Compass Layer 1 is responsible for
Compass Layer 1 is responsible for:

- predecessor identity truth
- previous version truth
- previous status truth
- stale candidate detection
- validation of whether a candidate event truthfully follows accepted history

---

## 3.5 Admission gate is responsible for
Admission gate / persistence boundary is responsible for:

- optimistic version checking
- append-time continuity protection
- conflict rejection when store version no longer matches expected version

---

## 3.6 Schema layer (Pandera / Pydantic / etc.) is responsible for
Schema validation layers may enforce:

- field existence
- type correctness
- basic value ranges
- cross-field data contract checks

However, schema layers do **not** define business legality by themselves.

---

# 4. Status Rules

## Rule S1 — The initial status must be `INIT`
A new aggregate instance must start with:

- `status = INIT`
- `current_version = 0`
- `total_amount = 0`
- `paid_amount = 0`
- `last_event_id = None`

This is the only valid initial state.

---

## Rule S2 — Aggregate identity exists even at `INIT`
Even before the order is created, the aggregate still has a concrete `order_id`.

This means:
- identity and state are separate concepts
- an `INIT` aggregate still represents a particular order stream coordinate

---

## Rule S3 — Only `INIT` may produce `CREATED`
Allowed:
- `INIT -> CREATED`

Not allowed:
- `CREATED -> CREATED`
- `PAID -> CREATED`

This prevents repeated order creation for the same aggregate.

---

## Rule S4 — Only `CREATED` may produce `PAID`
Allowed:
- `CREATED -> PAID`

Not allowed:
- `INIT -> PAID`
- `PAID -> PAID`

This keeps the `PAID` state dependent on a valid predecessor.

---

# 5. Create Rules

## Rule C1 — `order_id` must not be empty
A create command must carry a non-empty `order_id`.

---

## Rule C2 — `request_id` must not be empty
A create command must carry a non-empty `request_id`.

This is required for request-level retry safety.

---

## Rule C2.1 — Retried create requests must be treated as retries, not new creates
If the same create request is retried with the same `request_id`, the system should replay the prior accepted result rather than treat it as a fresh create attempt.

This rule belongs to the orchestration / idempotency layer, not to the aggregate.

---

## Rule C3 — Create amount must be positive
`create(amount)` must satisfy:

- `amount > 0`

Not allowed:
- negative amount
- zero amount

In v1, zero-amount orders are intentionally not modeled.

---

## Rule C3.1 — Monetary values must not rely on floating-point semantics in final production design
Money should ultimately use:

- `Decimal`
- or smallest-unit integer representation (for example cents)

Using `float` is acceptable only as a temporary simplification during the skeleton phase.

If `float` is used in v1 code, that should be treated as an explicit technical debt, not as the intended long-term semantic representation.

---

## Rule C4 — `CREATED.amount` defines `total_amount`
In v1, the `amount` carried by the `CREATED` event is the order's `total_amount`.

This keeps the model intentionally small and avoids introducing broader pricing logic.

---

# 6. Pay Rules

## Rule P1 — `request_id` must not be empty
A pay command must carry a non-empty `request_id`.

---

## Rule P1.1 — Retried pay requests must be treated as retries, not new payments
If the same pay request is retried with the same `request_id`, the system should replay the prior accepted result rather than treat it as a fresh payment attempt.

This rule belongs to the orchestration / idempotency layer, not to the aggregate.

---

## Rule P1.2 — A different `request_id` means a new business action
If the same order receives a pay command with a **different** `request_id`, that request must be treated as a new business action.

If the order is already `PAID`, this new request should fail under current v1 rules.

This prevents confusion between:
- a retry of the same intent
- a new command that happens to target the same order

---

## Rule P1.3 — Idempotent replay requires payload consistency
A prior accepted result may be replayed **only if** the retried request is semantically identical to the original request associated with the same `request_id`.

If the same `request_id` is reused with a different payload, the system must reject the request as an idempotency conflict rather than blindly replay the prior result.

This rule belongs to the orchestration / idempotency layer, not to the aggregate.

### Why this rule exists
Without this rule, a malformed or tampered retry such as:

- first request: `pay(request_id="A1", amount=100)` -> accepted
- second request: `pay(request_id="A1", amount=10)` -> replayed as success

could cause client-side semantic confusion.

The aggregate state would still remain correct, but the request/result contract seen by the caller would become misleading.

---

## Rule P2 — Pay amount must be positive
`pay(amount)` must satisfy:

- `amount > 0`

Not allowed:
- negative amount
- zero amount

---

## Rule P3 — In v1, pay amount must equal `total_amount`
In the current v1 model:

- `pay(amount) == total_amount`

Not allowed:
- underpayment
- overpayment
- split payment
- accumulated payment

This rule defines `PAID` as **full payment completion**, not as a generic payment ledger entry.

---

## Rule P4 — A paid order cannot be paid again
If the aggregate is already `PAID`, a new pay command must not produce another `PAID` event.

### Important note
A retry of the **same** `request_id` should not reach aggregate legality evaluation in the first place.
That case should already be intercepted by the idempotency/orchestration layer.

This rule is therefore about **new** payment attempts, not request retries.

---

# 7. Event and State Alignment Rules

## Rule E1 — `sequence` must be decided by the aggregate
Event sequence must be derived from:

- `current_version + 1`

External callers must not arbitrarily decide event sequence.

---

## Rule E2 — `proof` must be generated from current aggregate state
`proof.prev_status`, `proof.prev_version`, and `proof.prev_event_id` must come from the current aggregate state at candidate-event creation time.

Proof must not be arbitrarily injected by outside callers.

---

## Rule E3 — Applying `CREATED` sets `total_amount`
After applying a `CREATED` event:

- `status = CREATED`
- `total_amount = event.amount`

---

## Rule E4 — Applying `PAID` sets `paid_amount = event.amount`
After applying a `PAID` event:

- `status = PAID`
- `paid_amount = event.amount`

This should **not** be modeled as:

- `paid_amount += event.amount`

because that would implicitly introduce partial-payment semantics that v1 does not support.

---

## Rule E5 — `PAID` implies `paid_amount == total_amount`
Once the order reaches `PAID`, the following must hold:

- `paid_amount == total_amount`

This is the semantic meaning of `PAID` in v1.

---

## Rule E6 — All state mutation must happen through `apply(event)`
Both:
- live accepted events
- replayed historical events

must go through the same `apply(event)` path.

This preserves single source of truth for aggregate state mutation.

### Command / Event clarification
Business legality checks happen when handling commands and producing candidate events.

`apply(event)` must be treated as trusted state mutation for accepted/replayed events.
It should not re-run command-level legality logic during replay.

This separation keeps rehydration deterministic and simple.

---

# 8. Replay / Rehydration Rules

## Rule R1 — Accepted history must be deterministically replayable
Given valid accepted history, replay must reconstruct the same aggregate state every time.

---

## Rule R2 — Replay and live apply must share the same state-mutation logic
There must not be:
- one mutation logic for live processing
- another mutation logic for replay

Otherwise deterministic replay breaks.

---

# 9. Idempotency Behavior Rules

## Rule I1 — Same `request_id` means request-level retry
If the same `request_id` is seen again, the system must treat it as a retry of the same request intent, not as a fresh business action.

This rule belongs to the orchestration/idempotency layer.

---

## Rule I1.1 — Idempotent replay requires payload identity
A prior accepted result may be replayed only if the retried request payload is semantically identical to the original request payload associated with that `request_id`.

If payload differs, the request must be rejected as an idempotency conflict.

This avoids replaying a prior result into a semantically different caller context.

---

## Rule I2 — Idempotency ownership belongs outside the aggregate
The aggregate does not own duplicate-request memory.

Retry detection and prior-result replay belong to:
- registry
- command handler
- idempotency store

not to the aggregate itself.

---

## Rule I3 — Different `request_id` means a new request
Even if:
- `order_id` is the same
- payload looks similar

a different `request_id` must be treated as a new request.

The system must then decide legality based on current domain state.

---

## Rule I4 — Idempotency is not equivalent to "status-based skipping"
The system must not treat every later request as safe to skip merely because the order is already `PAID`.

The correct distinction is:

- same `request_id` -> retry -> replay accepted result
- different `request_id` -> new business action -> re-evaluate legality

Status alone is not sufficient to distinguish these cases.

---

# 10. Rules Explicitly Outside Aggregate Scope

## Not Aggregate A — Input/data schema validation
Examples:
- missing fields
- type mismatch
- malformed payload shape
- dataframe schema mismatch

These belong to:
- Pandera
- Pydantic
- API schema validation
- equivalent input-contract tooling

---

## Not Aggregate B — Transition truth against accepted history
Examples:
- whether `prev_event_id` matches actual last accepted event
- whether `prev_version` matches accepted history
- whether a candidate is stale

These belong to:
- Compass Layer 1

---

## Not Aggregate C — Optimistic persistence admission
Examples:
- expected version no longer matches store version
- append-time continuity rejection

These belong to:
- admission gate / event-store boundary

---

## Not Aggregate D — Retry replay policy
Examples:
- whether a request has already been processed
- whether the same `request_id` should replay prior accepted result
- whether payload identity matches prior request payload

These belong to:
- idempotency / orchestration layer

---

# 11. Known Limitation Outside Current v1 Scope

## Known Limitation K1 — External payment success may diverge from local accepted history
This v1 model protects internal write-side semantic correctness.

It does **not** yet solve the case where:

1. an external payment provider succeeds
2. local system confirmation is delayed, lost, or not durably recorded
3. local order state remains `CREATED`
4. the user later initiates another payment attempt

In such a case, external payment truth and local accepted history may diverge.

### Why this is out of scope for v1
v1 intentionally focuses on:

- internal domain legality
- Layer 1 semantic validation
- optimistic admission
- deterministic replay of accepted history

It does not yet model:

- asynchronous payment-finalization workflows
- in-flight `PAYING` state
- external payment reconciliation
- compensation/refund handling for divergence

### Future evolution direction
Possible later directions include:

- introducing a `PAYING` state
- blocking new payment attempts while payment outcome is unresolved
- reconciliation against provider settlement truth
- compensation workflows for external/local mismatch

This limitation is recorded explicitly to show that the gap is known, not ignored.

---

# 12. Minimal v1 Rule Summary

If reduced to the most essential v1 rules, the current model depends on these:

1. initial aggregate state must be `INIT`
2. `order_id` is aggregate identity and exists independently of status
3. only `INIT` may create
4. only `CREATED` may pay
5. `create(amount)` requires `amount > 0`
6. `pay(amount)` requires `amount > 0`
7. in v1, `pay(amount)` requires `amount == total_amount`
8. `PAID` implies `paid_amount == total_amount`
9. all state mutation must happen through `apply(event)`
10. same `request_id` means retry
11. different `request_id` means new business action
12. same `request_id` may replay prior result only if payload remains semantically identical
13. status alone cannot replace idempotency distinction
14. external payment/local state divergence is known but intentionally out of scope for v1

---

# 13. Suggested Tests

## Aggregate business legality tests
- create with empty `order_id` -> fail
- create with empty `request_id` -> fail
- create with negative amount -> fail
- create with zero amount -> fail
- create after `CREATED` -> fail
- pay with empty `request_id` -> fail
- pay with negative amount -> fail
- pay with zero amount -> fail
- pay with amount != total_amount -> fail
- pay after `PAID` with a new `request_id` -> fail

---

## Idempotency / orchestration tests
- same create `request_id` retry -> replay prior accepted result
- same pay `request_id` retry -> replay prior accepted result
- same `request_id` with different payload -> reject as idempotency conflict
- different `request_id` after `PAID` -> reject as illegal new action

---

## Replay consistency tests
- create then replay -> `total_amount` correct
- create + pay then replay -> `paid_amount` correct
- replayed state equals live-applied state

---

# 14. Final Summary

In the current v1 world, the write-side must protect not only:

- state transition order
- predecessor proof consistency
- append-time continuity

but also:

- amount reasonableness
- the semantic meaning of `PAID`
- the distinction between retried request and new request
- payload consistency for idempotent replay
- the legal cleanliness of accepted history

Without these rules, the system may remain formally continuous while still accepting semantically invalid business behavior.
