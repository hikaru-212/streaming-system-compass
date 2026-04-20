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

This usually means:
- request_id lookup
- request_id recording
- previous result retrieval

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

---

## Relationship to Projection

Idempotency at the write-side request boundary is different from deduplication inside projection.

Write-side idempotency protects command execution.  
Projection deduplication protects read-side consumption.

They are related ideas, but not the same module.

---

## Practical Warning

If idempotency is treated as the only duplicate protection mechanism, the system becomes too weak.

If idempotency is missing entirely, retries can easily become duplicate business effects.

The right balance is:
- request-level idempotency at the write boundary
- continuity checks at the event-store boundary
- separate duplicate strategy for projection/runtime consumption

---

## Summary

The idempotency module protects the system from repeated semantic effects caused by repeated requests.

It does not define domain legality.  
It defines a retry-safe request boundary around the transactional core.