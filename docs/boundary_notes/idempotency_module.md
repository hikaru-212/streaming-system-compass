# Boundary Note: Idempotency Module

## Purpose

This module defines the boundary for request-level duplicate protection.

Its purpose is to ensure that repeated processing of the same request does not create repeated semantic effects.

Typical examples include:
- duplicate payment request
- retry after timeout
- client resubmission of the same command
- replay of already-processed external input

---

## Responsible For

This module is responsible for:

- checking whether a request has already been processed
- retrieving the previous result of that request
- storing request-to-result mappings
- protecting write-side execution from duplicate semantic effects
- request payload identity / fingerprint comparison for safe replay
- rejecting reuse of the same `request_id` when the payload is inconsistent

This usually means:
- `request_id` lookup
- `request_id` recording
- previous result retrieval
- payload equality or fingerprint check before replay

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether a command is legal
- deciding sequence progression
- validating transition truth
- replacing event-store continuity checks
- acting as the projection deduplication system

Those belong to:
- aggregate
- Compass transition validator
- event store
- projection layer

---

## Design Principle

Idempotency should be treated as a **request-level safety boundary**, not as a replacement for domain correctness.

This means:
- the aggregate still owns business legality
- the event store still owns persistence continuity checks
- Compass still owns semantic validation
- idempotency prevents the same request from causing repeated effects

In addition, safe idempotent replay requires not only request identity reuse, but also payload consistency.

A prior accepted result may be replayed only when the retried request is semantically the same request, not merely a request carrying the same key.

---

## Relationship to Transactional Flow

Idempotency is usually one of the earliest checks in the transactional path.

A typical order is:

1. receive request
2. check idempotency
3. if already processed, return prior result
4. otherwise continue transactional flow

This makes idempotency a front-line safety layer for retries and duplicate submissions.

---

## Relationship to Event Store

Idempotency and event store continuity are related, but not identical.

### Event store continuity asks:
- does this event fit the expected history progression?

### Idempotency asks:
- has this request already been processed before?

So even if event-store checks exist, idempotency still serves a distinct purpose at the request boundary.

---

## Relationship to Aggregate

The aggregate does not own duplicate-request memory.

The aggregate decides whether a transition is legal given current state.

Idempotency instead protects the system from creating the same semantic effect multiple times due to repeated external requests.

The aggregate should not be forced to remember prior request identities merely to support retry-safe request replay.

---

## Relationship to Projection

Idempotency at the write-side request boundary is different from deduplication inside projection.

Write-side idempotency protects command execution.  
Projection deduplication protects read-side consumption.

They are related ideas, but not the same module.

---

## Payload Consistency and Safe Replay

Request-level replay must not rely on `request_id` alone.

If the same `request_id` is retried, the system may safely replay the prior accepted result only when the retried payload is semantically identical to the original request payload.

If the same `request_id` is reused with a different payload, the request should be rejected as an idempotency conflict rather than blindly replaying the previous result.

This protects the request boundary from semantic confusion at the API / orchestration layer.

Important note:
- this does not replace aggregate legality
- this does not change accepted history
- this protects request/result consistency for retries

---

## Relationship to API / Orchestration Semantics

A replayed result is safe only when the caller is retrying the same logical request.

Examples:

### Safe replay
- first request: `pay(request_id="A1", amount=100)`
- retry request: `pay(request_id="A1", amount=100)`

This is the same request intent retried after timeout or response loss.

### Idempotency conflict
- first request: `pay(request_id="A1", amount=100)`
- later request: `pay(request_id="A1", amount=10)`

This is **not** a safe retry of the same request intent.  
Even if the system has already accepted the first request, blindly replaying the prior result here would create request/result semantic confusion for the caller.

So the module must distinguish:

- same `request_id` + same payload → safe replay
- same `request_id` + different payload → idempotency conflict

---

## Practical Warning

If idempotency is treated as the only duplicate protection mechanism, the system becomes too weak.

If idempotency is missing entirely, retries can easily become duplicate business effects.

If idempotent replay ignores payload consistency, the system may preserve internal state correctness while still producing misleading request/result semantics at the API boundary.

The right balance is:
- request-level idempotency at the write boundary
- payload consistency checks for safe replay
- continuity checks at the event-store boundary
- separate duplicate strategy for projection/runtime consumption

---

## Summary

The idempotency module protects the system from repeated semantic effects caused by repeated requests.

It does not define domain legality.  
It defines a retry-safe request boundary around the transactional core.

A correct idempotency boundary must distinguish between:

- a genuine retry of the same request
- reuse of the same `request_id` with a semantically different payload

Only the first case is safe for replay.