# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, boundary notes, or postmortems.

Use roadmap documents to understand:

- what should be built first
- what depends on what
- which features are intentionally deferred
- how the project moves from durable truth toward runtime governance
- which Stage 3.5B and Stage 3.5C PR0 concerns are complete and which later concerns are intentionally deferred
- why Stage 3.5C is the current implementation focus after the durable write-side baseline
- why Stage 3.5D is kept as a later Snapshot Trust Contract / replay-efficiency stage
- why Stage 4 should classify retry reasons and intent consistency through `SemanticOutcome` / runtime evidence design
- why Stage 5+ may later evaluate isolated derived-state runtime / oblivious agent runtime as an agent-governance hardening direction

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, snapshot trust / replay efficiency, durable-history hardening, runtime semantic outcomes, runtime decision policy, action safety, Stage 5 dual-dimension governance, and later isolated derived-state runtime evaluation. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward durable runtime validation, snapshot-aware state validation, structured semantic outcomes, retry reason classification, runtime decisions, action safety, dual-dimension governance, and later agent-facing governance hardening. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred beyond the current implementation scope, including UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, Snapshot Trust Contract work, append-only hardening, retry classification, cleanup failure handling, isolated derived-state runtime, and later production / governance-hardening concerns. |

---

## Recommended Reading Order

1. [Implementation Roadmap](implementation_roadmap.md)
2. [Compass Runtime Roadmap](compass_runtime_roadmap.md)
3. [Deferred Architecture Backlog](deferred_architecture_backlog.md)

The implementation roadmap gives the global project sequence.

The Compass runtime roadmap gives a more focused view of how Compass should evolve from the current write-side baseline toward durable persistence, runtime semantic validation, structured semantic outcomes, runtime decision policy, action safety, and dual-dimension governance.

The deferred architecture backlog should be read after the main roadmaps. It does not expand the current implementation scope. It records known architecture concerns that have been intentionally postponed until the right stage.

---

## Current Roadmap Position

The project has already completed:

- Stage 1 — Transactional Semantic Core
- Stage 2 — Compass Layer 1 Write-side Validation
- Stage 3 — Projection Runtime Baseline
- Stage 3.5A — Decimal / Money Hardening
- Stage 3.5B PR1 — Schema + Docker PostgreSQL + Migration Skeleton
- Stage 3.5B PR2 — PostgresEventStore baseline
- Stage 3.5B PR3 — PostgresIdempotencyStore baseline
- Stage 3.5B PR4 — Transactional Semantic Write-side Boundary
- Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
- Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
- Stage 3.5C PR0 — Durable Order Event Vocabulary Hardening
- Stage 3.5C PR1 — Durable Read-Side Schema Baseline
- Stage 3.5C PR2 — PostgresProjectionStore
- Stage 3.5C PR3 — PostgresCheckpointStore
- Stage 3.5C PR4 — Global-Position Projection Worker Baseline

Stage 3.5B now forms a durable write-side baseline:

```text
durable accepted history
+ durable idempotency memory
+ transactional write-side execution
+ two-phase concurrency admission
+ validation placement strategy
```

The current major focus is:

```text
Stage 3.5C — Durable Read-Side Baseline
```

Stage 3.5C should stay focused on durable projection state, durable checkpoint state, and persistence-backed projection worker behavior. PR1 has established the durable read-side schema boundary, PR2 has made projection state durable through `PostgresProjectionStore`, PR3 has made checkpoint progress durable through `PostgresCheckpointStore`, and PR4 has introduced the first PostgreSQL-backed projection worker baseline using `GLOBAL_POSITION` as the accepted-history consumption cursor. The remaining Stage 3.5C work should implement durable replay / rebuild validation.

PR4 establishes:

```text
order_events.global_position = durable global event-log position
PostgresProjectionEventSource = accepted-history stream reader
PostgresProjectionWorker = PostgreSQL-backed read-side orchestration
PostgresProjectionStore + PostgresCheckpointStore = atomic read-side persistence pair
```

PR4 keeps the reducer storage-agnostic, stores checkpoint progress as `cursor_kind = GLOBAL_POSITION`, and assumes a single active worker process per `worker_name`. Worker leasing, checkpoint row locking, DLQ, watermark semantics, distributed multi-worker coordination, and Compass Layer 2 validation remain deferred.


Snapshot trust, retry classification, Layer 2 validation, and isolated agent-facing runtime work should remain deferred to their proper stages.

---

## Roadmap Principle

The project should evolve from semantic clarity toward runtime complexity:

```text
semantic truth
→ transactional execution
→ concurrency-safe admission
→ event truth validation
→ projection runtime
→ exact money hardening before durable persistence
→ durable write-side baseline
→ durable read-side baseline
→ snapshot trust qualification / replay efficiency
→ durable history and permission hardening
→ runtime semantic validation
→ structured semantic outcome
→ retry reason classification and intent consistency
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
→ later isolated derived-state runtime and adversarial hardening
```

The system should not attempt to solve chaos, broad governance, agent isolation, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are coherent.

---

## Stage 3.5B Reminder

Stage 3.5B completed six durable write-side checkpoints:

1. **PR1 — Schema + Docker + Migration**  
   Established `order_events`, `idempotency_records`, local PostgreSQL setup, and the durable schema contract.

2. **PR2 — PostgresEventStore**  
   Made accepted event history durable.

3. **PR3 — PostgresIdempotencyStore**  
   Made request-level idempotency durable.

4. **PR4 — Transactional Semantic Write-side Boundary**  
   Coordinated event append and idempotency record write in one database transaction, while preserving Compass Layer 1 validation before accepted-history mutation.

5. **PR5 — PostgreSQL Concurrency Admission Boundary**  
   Reintroduced durable optimistic / pessimistic admission so concurrent writers can be admitted or rejected through a stable application boundary rather than raw database errors. PR5 also recorded the two-phase admission decision in ADR 0012 and treats `autocommit=True` as incompatible with transaction-scoped pessimistic admission.

6. **PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude**  
   Separated `ValidationMode` from `ValidationPlacement`, preserved `IN_TRANSACTION` as the default write-side behavior, and added a minimal `PRE_TRANSACTION` orchestration path guarded by append-time admission. PR6 also recorded the pre-transaction read cleanup boundary required to keep the physical connection state aligned with the placement label.

---

## Stage 3.5C PR0 Reminder

Stage 3.5C PR0 completed durable order-event vocabulary hardening before durable read-side persistence begins.

It finalized selected write-side schema vocabulary so later projection and replay code can depend on stable stored event records:

```text
event_type: CREATED / PAID
proof_prev_status: INIT / CREATED / PAID
unique constraint: uq_order_events_order_id_sequence
```

`CommandType` remains lowercase because it represents request/action identity for idempotency records, not accepted event identity.

---

## Stage 3.5C Reminder

Stage 3.5C should move the read-side baseline from in-memory stores toward durable persistence-backed semantics.

The main goal is to add durable projection state and checkpoint state without redefining the source of truth.

```text
event log / order_events = accepted history truth
projection state = derived runtime state
checkpoint = operational progress metadata
```

Stage 3.5C should prepare the system for later Compass Layer 2 validation by making derived state durable enough to compare against replayed accepted history.


Stage 3.5C should be implemented as a staged durable read-side PR sequence:

```text
PR1 — Durable Read-Side Schema Baseline ✅
PR2 — PostgresProjectionStore ✅
PR3 — PostgresCheckpointStore ✅
PR4 — Global-Position Projection Worker Baseline ✅
PR5 — Durable Replay / Rebuild Validation
PR6 — Stage 3.5C Documentation and Completion Alignment
```

PR1 establishes:

```text
projection_states = derived runtime view
projection_checkpoints = worker progress metadata
order_events = accepted-history truth
```

It also records that database constraints should protect physical shape and checkpoint cursor consistency, while future Compass Layer 2 should detect semantic projection drift.

PR2 establishes:

```text
PostgresProjectionStore = PostgreSQL-backed projection state persistence
projection_states = durable derived state storage
OrderState.version = current source sequence reflected by the projection state
```

PR2 keeps the projection store narrow: it saves, loads, upserts, and clears derived projection state, but it does not own checkpoints, worker orchestration, semantic drift validation, or transaction commit / rollback.

PR3 establishes:

```text
PostgresCheckpointStore = PostgreSQL-backed checkpoint progress persistence
projection_checkpoints = durable worker progress metadata
cursor_kind + cursor_value = explicit worker progress bookmark
```

PR3 keeps the checkpoint store narrow: it saves, loads, upserts, and clears worker progress metadata, but it does not scan accepted history, run the projection worker, decide the final cursor strategy, or commit / rollback transactions.

The sequencing rule is:

```text
schema first
→ store implementations
→ worker orchestration
→ replay / rebuild proof
→ documentation alignment
```

This keeps the read-side baseline focused on durable derived state and checkpoint progress before later stages introduce Snapshot Trust Contract work, Layer 2 validation, SemanticOutcome, or database role hardening.

Stage 3.5C should not implement:

- aggregate snapshots
- Snapshot Trust Contract
- Layer 2 validation
- retry reason classification
- `SemanticOutcome` persistence
- isolated read-side DB / agent runtime isolation

---

## Stage 3.5D Reminder

Stage 3.5D should not be mixed into the Stage 3.5C durable read-side baseline.

It is reserved for **Snapshot Trust Contract and replay efficiency** after durable write-side and durable read-side baselines are both coherent.

Possible Stage 3.5D work includes:

- aggregate snapshots
- snapshot metadata and lineage
- snapshot validity rules
- lineage checks using aggregate / order identity, snapshot version, source event identity, and source event sequence
- tail continuity checks after the snapshot version
- snapshot schema version and reducer version tracking
- payload hash / checksum as a baseline integrity check
- invalid snapshot fallback to full accepted-history replay
- projection rebuild optimization
- replay cost measurement
- evidence hooks for future Stage 4 `SemanticOutcome`

The source-of-truth rule remains unchanged:

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
```

The important Stage 3.5D distinction is:

```text
fast path:
snapshot + tail replay + trust checks

authority path:
full accepted-history replay for audit, rebuild, suspicious cases, reducer upgrades, or high-risk verification
```

---

## Stage 3.5E Reminder

Stage 3.5E is reserved for durable history and permission hardening after durable write-side, durable read-side, and replay-efficiency boundaries are clear.

The first hardening target is accepted history:

```text
order_events = accepted history / source of truth
```

Stage 3.5E should evaluate:

- database role boundary documentation
- migration owner vs runtime role separation
- write-side runtime permission baseline
- projection worker permission baseline
- read-only observer permission baseline
- revoking runtime `UPDATE` / `DELETE` authority from `order_events`
- optional trigger-based rejection of `UPDATE` / `DELETE` on `order_events`

If Stage 3.5D introduces snapshot tables, Stage 3.5E may also evaluate snapshot table permissions or append-only derived-artifact discipline.

However, projection state and checkpoint tables must remain mutable enough to support:

- upsert
- resume
- reset
- rebuild

---

## Deferred Architecture Backlog Reminder

Some architecture issues are known but intentionally deferred to avoid scope creep.

Examples include:

- UUIDv7 / time-ordered UUID evaluation
- formal `EventStoreProtocol`
- stored event record / JSONB evidence hydration
- registry-stage timing in `metadata_json`
- payload / proof / metadata JSON shape
- append-only database hardening
- Snapshot Trust Contract and replay-efficiency optimization
- retry reason classification and intent consistency
- pre-transaction cleanup failure handling after Stage 4 error model or connection-pool hardening exists
- isolated derived-state runtime / oblivious agent runtime
- integration-test follow-ups as the durable read-side test matrix expands

These are tracked in:

- [Deferred Architecture Backlog](deferred_architecture_backlog.md)

They should be converted into GitHub Issues only when their suggested timing becomes active.

---

## Stage 4 Reminder

Stage 4 is not only error classification.

It evolves Compass into:

```text
Layer 2 validation
→ SemanticOutcome
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

This reflects the core principle:

> Error semantics should not only be observed.  
> They should help the runtime decide whether to continue, replay, retry, reload, rebuild, block, quarantine, stop, or escalate.

Stage 4 should not be used as a dumping ground for durable persistence cleanup or replay optimization.

Completed schema-hardening work, such as Stage 3.5C PR0 durable event vocabulary normalization and `proof_prev_status` constraint enforcement, should remain recorded in implementation notes, PR history, and roadmaps rather than in the active deferred backlog.

Replay-efficiency work belongs to Stage 3.5D, not Stage 4 Error Model work.

### Retry Reason Classification

Stage 4 should explicitly classify retry-like situations through `SemanticOutcome` / request-attempt evidence design.

Retry is not a single category.

Examples:

```text
same request_id + same semantic_fingerprint
→ idempotent replay / safe physical retry

same request_id + different semantic_fingerprint
→ semantic conflict / same identity carrying different meaning

stale expected_version
→ concurrency retry / retry after reload

transient database or connection failure
→ infrastructure retry / retry with backoff or escalate

projection or snapshot drift
→ rebuild-oriented retry / quarantine derived state

future same intent_id + different intent_fingerprint
→ agent intent drift / block and escalate
```

This classification should not be stored directly in `idempotency_records`.

```text
idempotency_records = successful request-result memory
SemanticOutcome / request_attempts = retry reason and governance evidence
```

---

## Stage 5 Reminder

Stage 5 packages the final governance demo around:

```text
semantic correctness × operational freshness → action safety
```

The key matrix is:

|  | Operational Fresh | Operational Stale |
|---|---|---|
| Semantic Correct | Safe to act | Semantically correct but stale |
| Semantic Incorrect | Operationally healthy but semantically unsafe | Unsafe / stop / escalate |

This final demo should show that:

- operational freshness is not semantic correctness
- semantic correctness is not operational freshness
- action safety requires both dimensions

Snapshot / projection trust can contribute to the semantic correctness signal.

For example, a state may be operationally fresh but semantically unsafe if:

- projection differs from accepted-history replay
- snapshot trust checks fail
- reducer version is untrusted
- checkpoint and projection state disagree

---

## Stage 5+ Reminder

Stage 5+ may later evaluate isolated derived-state runtime / oblivious agent runtime.

This is a future governance-hardening direction, not a current implementation requirement.

The long-term model is:

```text
Sovereign Event Store
→ Projection Pipeline
→ Isolated Derived-State DB / controlled read boundary
→ Agent observes derived state
→ Agent submits candidate action
→ Compass validates against accepted history
→ accepted event is appended only by the trusted system boundary
```

The key principle is:

```text
Agent observes derived state.
Agent does not own truth mutation.
Compass owns admission.
Event log owns truth.
```

This should be revisited only after Stage 5 dual-dimension governance, `ActionSafetyGate`, and a concrete agent-facing tool boundary exist.
