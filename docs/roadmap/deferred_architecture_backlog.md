# Deferred Architecture Backlog

[← Back to Roadmaps Index](README.md)

## Purpose

This document records architecture issues intentionally deferred from the current implementation scope.

The purpose of this backlog is not to expand the current implementation scope. Instead, it preserves design concerns that should be handled only when the system reaches the right implementation stage.

This backlog should not collect every possible cleanup idea.

An item should remain here only if it has at least one of the following:

- a plausible future trigger
- an architectural consequence
- a stage dependency
- a production-hardening reason
- a clear relationship to runtime evidence, governance, or durability

Pure naming preference, style cleanup, or already-completed implementation work should not remain in this backlog.

Completed Stage 3.5B work and completed Stage 3.5C PR0 schema-hardening work should be recorded in roadmaps, ADRs, postmortems, implementation notes, or PR history instead of staying here as deferred work.

Current focus:

```text
Stage 3.5C — Durable Read-Side Baseline
```

Recently completed baseline:

```text
Stage 3.5B — Durable Write-Side Baseline
```

Stage 3.5B now includes:

```text
PR1 Schema + Local PostgreSQL + Migration
PR2 PostgresEventStore
PR3 PostgresIdempotencyStore
PR4 Transactional Semantic Write-Side Boundary
PR5 PostgreSQL Concurrency Admission Boundary
PR6 Validation Placement Strategy Boundary / Stage 4 Prelude
```

Stage 3.5C PR0 has also completed durable order-event vocabulary hardening:

```text
event_type durable vocabulary normalization
proof_prev_status database CHECK constraint
order_events unique constraint rename
```

These completed items are no longer tracked as deferred backlog work.

This backlog should now be used only for concerns intentionally deferred beyond the durable write-side baseline and Stage 3.5C PR0 schema-hardening pass.

---

## Status Legend

```text
Stage 4 / evidence design
→ should wait for SemanticOutcome, runtime evidence, or governance work

Stage 4 / retry classification
→ should wait for SemanticOutcome / request-attempt evidence design

Stage 4 / connection-pool hardening
→ should wait until structured error modeling, connection lifecycle policy, or pooled database connections exist

Stage 3.5D / persistence optimization
→ should wait until durable write-side and durable read-side baselines exist, and replay / rebuild cost becomes meaningful

Stage 3.5D / snapshot trust contract
→ should wait until durable read-side baseline exists and snapshot-assisted replay is ready to be qualified for fast-path use

Stage 3.5E / durable history hardening
→ should wait until durable write-side, durable read-side, and replay-efficiency boundaries are clear enough to define database role authority

Later evaluation
→ should be revisited only when a concrete runtime, storage, or operational need appears

Later production hardening
→ useful, but not part of the current correctness baseline

Stage 5+ / later governance hardening
→ should wait until dual-dimension governance, action safety, and agent-facing tool boundaries become concrete
```

---

## 1. UUIDv7 / Time-Ordered UUID Evaluation

### Current Decision

Do not introduce UUIDv7 during Stage 3.5B or Stage 3.5C.

Current approach:

- keep UUIDv4
- centralize event ID generation
- preserve PostgreSQL UUID compatibility
- defer UUIDv7 / time-ordered UUID evaluation

### Why Not Now

UUIDv7 adoption may require:

- Python version compatibility review
- dependency decision
- migration strategy
- test updates
- decision on whether ordering should be represented by identity, sequence, or append time

### Existing Issue

```text
#7 Evaluate UUIDv7 for durable event identity generation
```

### Current Classification

```text
Later evaluation
```

### Suggested Timing

After Stage 3.5C or during later storage / operational hardening, unless storage locality or operational inspection becomes a real bottleneck.

---

## 2. Formal `EventStoreProtocol`

### Current Decision

Do not introduce a formal `Protocol` or abstract base class just because PostgreSQL persistence now exists.

The project currently relies on constructor injection and method-shape compatibility:

```python
append(candidate_event, expected_current_version)
load(order_id)
last_event(order_id)
```

### Why Not Now

A protocol should be introduced only when it clarifies coordination between multiple implementations or admission strategies.

Defining it too early may result in an abstraction shaped by incomplete information.

### Current Classification

```text
Later evaluation
```

### Future Work

Consider defining:

```python
class EventStoreProtocol(Protocol):
    def append(self, candidate_event: OrderEvent, expected_current_version: int) -> None: ...
    def load(self, order_id: str) -> list[OrderEvent]: ...
    def last_event(self, order_id: str) -> OrderEvent | None: ...
```

### Suggested Timing

Defer until multiple storage implementations or admission strategies require stricter type-level coordination.

---

## 3. Stored Event Record / JSONB Evidence Hydration

### Current Decision

`PostgresEventStore.load()` returns `list[OrderEvent]` and only hydrates fields required to reconstruct the domain event.

It does not currently hydrate:

- `payload_json`
- `proof_json`
- `metadata_json`
- `appended_at`
- `event_schema_version`

### Why Not Now

`OrderEvent` does not currently carry those fields.

Hydrating JSONB evidence into `OrderEvent` would blur the boundary between:

- domain event reconstruction
- durable audit / evidence record retrieval

### Future Work

Introduce a persistence-level record such as:

```python
@dataclass(frozen=True)
class StoredOrderEvent:
    event: OrderEvent
    payload_json: dict
    proof_json: dict
    metadata_json: dict
    appended_at: datetime
    event_schema_version: int
```

Then consider separate APIs:

```python
load(order_id) -> list[OrderEvent]
load_records(order_id) -> list[StoredOrderEvent]
```

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During audit, evidence, or SemanticOutcome persistence design.

---

## 4. Registry-Stage Timing in `metadata_json`

### Current Decision

Stage 3.5B did not implement durable timing collection.

`metadata_json` remains a reserved container for future runtime metadata.

### Future Metadata Candidates

Possible future timing fields:

- idempotency check duration
- aggregate rehydration duration
- validation context build duration
- candidate event creation duration
- Compass validation duration
- event append duration
- idempotency record write duration
- transaction total duration
- validation placement mode
- admission strategy identity

### Why Not Now

Stage 3.5B focused on correctness boundaries:

- durable accepted history
- durable idempotency
- transaction atomicity
- concurrency admission
- validation placement

Timing collection is meaningful, but it should not distract from correctness boundaries.

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During Stage 4 evidence / outcome persistence, or during a dedicated observability pass after durable read-side persistence exists.

---

## 5. Event Payload / Proof / Metadata JSON Shape

### Current Decision

Stage 3.5B uses minimal JSONB objects:

```python
payload_json = {}
proof_json = {
    "prev_event_id": ...,
    "prev_version": ...,
    "prev_status": ...,
}
metadata_json = {}
```

Stage 3.5C PR0 hardened selected durable vocabulary at the schema boundary, but it did not define a full JSONB event evidence model.

### Why Not Now

The project has not yet defined a full durable event payload schema or audit evidence model.

### Future Work

Clarify:

- whether `payload_json` should duplicate event domain fields
- whether `proof_json` is only a proof copy or a richer proof-carrying evidence container
- whether `metadata_json` should be restricted to runtime metadata
- how these fields relate to SemanticOutcome persistence

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

After durable read-side baseline, before or during SemanticOutcome persistence design.

---

## 6. Append-Only Database Hardening

### Current Decision

Stage 3.5B does not implement production-grade append-only hardening.

Current defenses are:

- application append logic
- `accepted_event_id` primary key
- `UNIQUE(order_id, sequence)`
- expected-version check in the store
- PR4 transaction boundary
- PR5 admission boundary
- Stage 3.5C PR0 durable vocabulary and proof-status schema hardening

These defenses protect the accepted-history write path, but they do not yet make `order_events` a database-level append-only log.

PostgreSQL rows remain mutable by default if a database role has `UPDATE` or `DELETE` authority.

### Why Not During Stage 3.5C PR1

Stage 3.5C PR1 should focus on durable read-side schema baseline work.

Database role boundaries should wait until the project knows the final baseline shape of:

- write-side runtime access
- projection worker access
- read-side store mutation requirements
- checkpoint update requirements
- rebuild / reset requirements

This matters because `order_events` should move toward append-only accepted history, while `projection_states` and `projection_checkpoints` must remain mutable enough to support upsert, resume, reset, and rebuild.

### Future Work

Evaluate during Stage 3.5E:

- database role boundary documentation
- migration owner vs runtime role separation
- write-side runtime role permissions
- projection worker role permissions
- read-only observer role permissions
- revoking runtime `UPDATE` / `DELETE` authority from `order_events`
- optional trigger-based rejection of `UPDATE` / `DELETE` on `order_events`
- tests proving runtime roles cannot rewrite accepted history
- documentation explaining why read-side tables remain mutable while accepted history is hardened

Possible role categories:

```text
migration_owner
write_side_runtime
projection_worker
read_only_observer
```

### Current Classification

```text
Stage 3.5E / durable history hardening
```

### Suggested Timing

During:

```text
Stage 3.5E — Durable History and Permission Hardening
```

after Stage 3.5C durable read-side baseline and Stage 3.5D replay-efficiency work make runtime storage authority clear enough to harden safely.

---

## 7. Integration Test Boundary and CI Strategy

### Current Decision

Stage 3.5B introduced or aligned:

- `TEST_DATABASE_URL`
- `compass_test`
- test database guardrails
- destructive DB test isolation
- CI test database creation
- migration against test database
- integration test directory reorganization
- transactional integration test README
- in-memory integration test README

Stage 3.5C PR0 also added PostgreSQL schema-constraint coverage for durable order-event vocabulary hardening.

These are sufficient for the current durable write-side baseline and PR0 schema-hardening pass.

### Remaining Future Work

Possible later follow-ups:

- pytest markers for DB-backed tests
- storage integration README
- integration root README
- performance / benchmark test separation
- optional test container lifecycle helpers

### Current Classification

```text
Later production hardening
```

### Suggested Timing

Revisit when the test matrix expands for Stage 3.5C durable read-side persistence or when CI runtime becomes difficult to manage.

---

## 8. Snapshot Trust Contract and Replay Efficiency

### Current Decision

Do not implement aggregate snapshots, snapshot trust, or projection rebuild optimization during Stage 3.5C.

Stage 3.5C should first complete the durable read-side baseline:

```text
durable projection state
durable checkpoint state
PostgresProjectionStore
PostgresCheckpointStore
persistence-backed projection worker tests
```

Snapshot and replay-efficiency mechanisms should be handled as a later persistence-optimization stage.

### Why Not Now

Stage 3.5C answers:

```text
Can the read-side become durable while preserving accepted history as the source of truth?
```

Snapshot work answers different questions:

```text
As accepted history grows, how can replay, rehydrate, and rebuild costs be reduced?
```

```text
When is a snapshot trustworthy enough to use on the normal fast path without full replay every time?
```

These concerns should not distract from the durable read-side correctness baseline.

### Future Work

Consider during Stage 3.5D:

- aggregate snapshot schema
- aggregate snapshot store
- rehydration from latest valid snapshot plus tail events
- projection rebuild optimization
- snapshot metadata and lineage
- snapshot validity rules
- replay cost measurement
- lineage checks:
  - aggregate_id / order_id
  - snapshot_version
  - source_event_id
  - source_event_sequence
- tail continuity checks
- snapshot_schema_version
- reducer_version
- payload_hash / checksum
- invalid snapshot fallback to full replay
- snapshot trust levels:
  - invalid / untrusted
  - fast-path eligible
  - high-confidence
  - recently audited
- hooks for future Stage 4 SemanticOutcome when snapshot trust checks fail

### Current Classification

```text
Stage 3.5D / snapshot trust contract
```

### Suggested Timing

During:

```text
Stage 3.5D — Persistence Optimization & Replay Efficiency
```

after Stage 3.5C durable read-side baseline is complete.

---

## 9. Pre-Transaction Cleanup Failure Handling

### Current Decision

Stage 3.5B PR6 introduced a simple cleanup boundary during the preliminary read phase for `PRE_TRANSACTION` validation:

```python
try:
    preliminary_idempotency_decision = read_idempotency_store.check(signature)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
        return PostgresWriteSideResult(...)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
        return PostgresWriteSideResult(...)

    history = read_event_store.load(order_id)
finally:
    connection.rollback()
```

This is required because read-only `SELECT` operations can still open an implicit transaction when the PostgreSQL connection is not in autocommit mode.

The current baseline ensures that CPU-side Compass validation does not accidentally run while the connection still carries an implicit read transaction.

### Deferred Concern

The current baseline does not yet implement structured handling for rollback failure itself.

Future production-like handling may need to distinguish:

```text
primary read / load failure
vs
cleanup rollback failure
```

This matters because rollback can itself fail if the connection is already closed, aborted, or physically broken.

There are two different failure cases:

```text
Case 1:
primary read failure happens
+
cleanup rollback failure also happens

Risk:
cleanup failure may mask the original read failure
```

```text
Case 2:
primary read succeeds
+
cleanup rollback fails

Risk:
the system may continue as if the connection were clean even though cleanup failed
```

The project should not silently swallow cleanup failures with a broad:

```python
except Exception:
    pass
```

That would avoid masking the primary error, but it could also hide connection-state corruption.

### Future Direction

When Stage 4 error modeling or connection pooling is introduced, consider a hardened cleanup model that can:

- preserve the primary error when cleanup also fails
- attach cleanup failure as diagnostic context
- map cleanup failure into a structured infrastructure error
- mark the connection as unsafe for reuse
- discard or invalidate broken pooled connections
- log cleanup failures with trace context
- expose cleanup failure as operational evidence

A possible future pattern is:

```text
if primary error exists:
    preserve primary error
    attach cleanup failure as diagnostic context

if no primary error exists:
    surface cleanup failure as infrastructure failure
```

This future work should be integrated with the Stage 4 error model instead of being implemented as ad hoc exception handling inside Stage 3.5B.

### Current Classification

```text
Stage 4 / connection-pool hardening
```

### Suggested Timing

Revisit when at least one of the following becomes true:

- Stage 4 error model work begins
- connection pooling is introduced
- infrastructure errors are mapped into structured runtime outcomes
- production-like observability is added
- cleanup failures need to become operational evidence

### Related Note

See:

- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

---

## 10. Retry Reason Classification and Intent Consistency

### Current Decision

Do not add `retry_reason` to `idempotency_records` during Stage 3.5C.

`idempotency_records` remain successful request-result memory:

```text
request_id
→ semantic_fingerprint
→ accepted_event_id / result
```

Retry reason is attempt-level evidence and belongs to Stage 4 SemanticOutcome / request-attempt evidence design.

### Why Not Now

Retry-like situations may come from different boundaries:

- idempotency replay
- idempotency conflict
- stale-write admission rejection
- lock timeout
- infrastructure failure
- projection / snapshot drift
- future agent intent drift

These should not be collapsed into a single `retry` field.

They also should not pollute `idempotency_records`, because idempotency records only represent successful accepted-event mappings.

### Future Work

During Stage 4, define:

```text
retry_class
retry_safety
intent_consistency
```

Candidate values may include:

```text
retry_class:
- IDEMPOTENT_REPLAY
- CONCURRENCY_RETRY
- INFRASTRUCTURE_RETRY
- SEMANTIC_CONFLICT
- SEMANTIC_DRIFT
- REBUILD_REQUIRED
- UNKNOWN

retry_safety:
- SAFE_TO_REPLAY
- SAFE_TO_RETRY_AFTER_RELOAD
- RETRY_WITH_BACKOFF
- REBUILD_REQUIRED
- NOT_RETRYABLE
- BLOCK_AND_ESCALATE
- UNKNOWN

intent_consistency:
- SAME_INTENT
- SAME_IDENTITY_DIFFERENT_MEANING
- NOT_AN_IDEMPOTENCY_REPLAY
- AGENT_INTENT_DRIFT
- NOT_APPLICABLE
- UNKNOWN
```

If durable evidence is needed, consider a separate table such as:

```text
request_attempts
semantic_outcomes
runtime_outcomes
```

### Current Classification

```text
Stage 4 / retry classification
```

### Suggested Timing

During Stage 4B SemanticOutcome / Error Model v1 and Stage 4C RuntimeDecisionPolicy design.

---

## 11. Isolated Derived-State Runtime / Oblivious Agent Runtime

### Current Decision

Do not implement isolated agent runtime or separate read-side DB during Stage 3.5C, Stage 3.5D, or Stage 4.

This is a Stage 5+ / later governance-hardening direction.

### Concept

Future versions of Compass may isolate untrusted agents from the sovereign event store.

The future model is:

```text
Sovereign Event Store
→ Projection Pipeline
→ Isolated Derived-State DB / controlled read boundary
→ Agent observes derived state
→ Agent proposes candidate action
→ Compass validates against accepted history
→ accepted event is appended only by the system kernel
```

### Why It Matters

This separates observation from authority.

Agents may observe derived state, but they should not directly read or write accepted history.

If the derived-state world is corrupted, it can be quarantined, discarded, and rebuilt from accepted history.

Compass remains the admission authority.

### Future Work

Evaluate:

- separate read-side projection DB
- controlled agent read API
- candidate action protocol
- Compass admission against sovereign event store
- rebuildable sandbox state
- HMAC / sealed snapshots for high-risk derived state
- hash chains / MMR only if stronger tamper evidence becomes necessary

### Current Classification

```text
Stage 5+ / later governance hardening
```

### Suggested Timing

Revisit after:

- Stage 5 dual-dimension governance demo is stable
- ActionSafetyGate exists
- Layer 2 projection validation exists
- SemanticOutcome / RuntimeDecisionPolicy are implemented
- agent-facing tool interface becomes concrete

---

## Summary

The deferred backlog should now be read with the following stage alignment:

| Item | Current Alignment |
|---|---|
| UUIDv7 | Later evaluation |
| EventStoreProtocol | Later evaluation |
| StoredEventRecord / JSONB hydration | Stage 4 / evidence design |
| Registry-stage timing | Stage 4 / evidence design |
| Payload/proof/metadata JSON shape | Stage 4 evidence / outcome persistence |
| Append-only DB hardening | Stage 3.5E / durable history hardening |
| Integration test boundary / CI strategy | Later production hardening |
| Snapshot trust contract and replay efficiency | Stage 3.5D / snapshot trust contract |
| Pre-transaction cleanup failure handling | Stage 4 / connection-pool hardening |
| Retry reason classification and intent consistency | Stage 4 / retry classification |
| Isolated derived-state runtime / oblivious agent runtime | Stage 5+ / later governance hardening |

The backlog remains a scope-control document.

It should not be used to pull every valid architecture concern into the current PR or stage.
