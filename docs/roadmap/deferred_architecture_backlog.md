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

Completed Stage 3.5B, Stage 3.5C, Stage 3.5D, and Stage 3.5E work should be recorded in roadmaps, ADRs, postmortems, implementation notes, or PR history instead of staying here as deferred work.

Current foundation status after the Stage 4E PR0 boundary:

```text
Stage 4B.3 — Projection Trust Boundary and Continuation — COMPLETE / CLOSED AS NOT CURRENTLY JUSTIFIED
Stage 4B.5 — Order Correctness Contract V0 — COMPLETE / CLOSED
Stage 4C — Runtime Decision Authority — COMPLETE / CLOSED
Stage 4D — Strategy Selection Authority — RESPONSIBILITY RETAINED / IMPLEMENTATION DEFERRED
Stage 4E — Same-Request Re-Invocation Authority — PR0 BOUNDARY ESTABLISHED / PRODUCTION UNIMPLEMENTED
```

Stage 4B.3 PR1/PR2 remain investigation and reference evidence; ADR 0026 owns
re-entry and PR3+ intentionally do not proceed. No Projection Trust Continuation
mechanism was implemented. Stage 4B.5 defines 18 stable rules, while exactly six
FullProof `TRANSITION_TRUTH` rules currently have typed runtime producer
coverage.

Completed implementation details now live under:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)
- [Stage 4B Implementation Notes](../implementation_notes/stage_4b/)
- [Stage 4B.1 Implementation Notes](../implementation_notes/stage_4b_1/)
- [Stage 4B.2 Implementation Notes](../implementation_notes/stage_4b_2/)
- [Stage 4B.5 Implementation Notes](../implementation_notes/stage_4b_5/)
- [Stage 4C Implementation Notes](../implementation_notes/stage_4c/)
- [Stage 4E Implementation Notes](../implementation_notes/stage_4e/)

This backlog should now be used only for concerns intentionally deferred beyond the completed durable write-side, durable read-side, read-side snapshot trust, durable permission, Stage 4A SemanticOutcome, and Stage 4B DecisionReceipt baselines.

---

## Status Legend

```text
Completed Stage 4B.1 / trace design
→ implemented work belongs in Stage 4B.1 notes, not this backlog

Stage 4E / Same-Request Re-Invocation Authority
→ PR0 accepts preparation LOCK_TIMEOUT for one additional invocation of the
  same complete RequestSignature; broad retry classification, durable attempt
  evidence, and restart recovery remain unaccepted future candidates

Completed Stage 4B.5 / Order correctness contract
→ machine-readable correctness evidence is implemented; Stage 4C current-response authority and Stage 4E another-invocation authority remain separate

Stage 4 / connection-pool hardening
→ should wait until structured error modeling, connection lifecycle policy, or pooled database connections exist

Completed Stage 3.5E / actor-permission hardening
→ moved to implementation notes unless a later production-hardening concern remains

Later evaluation
→ should be revisited only when a concrete runtime, storage, or operational need appears

Later production hardening
→ useful, but not part of the current correctness baseline

Stage 5+ / later governance hardening
→ should wait until dual-dimension governance, action safety, and agent-facing tool boundaries become concrete
```

---

## 1. Projection Worker Lease / Checkpoint Row Locking

### Current Decision

Do not implement worker leasing, checkpoint row locking, `SELECT ... FOR UPDATE`, `SKIP LOCKED`, worker heartbeat, or distributed projection-worker coordination during the completed Stage 3.5C durable read-side baseline.

Stage 3.5C intentionally established a single-worker durable projection baseline.

The worker assumes:

```text
one active process per worker_name
```

### Why Not Now

The current read-side boundary is:

```text
accepted history + per-order progress
→ exact-next eligible event source
→ canonical reducer
→ projection state
→ per-order progress
```

with projection state and per-order progress persisted atomically. Under ADR
0020, `global_position` remains lineage and scheduling evidence rather than a
completeness cursor.

Adding worker leasing or checkpoint row locking would expand the baseline from deterministic durable read-side semantics into runtime coordination hardening.

That would mix two separate concerns:

```text
read-side atomicity
≠
distributed worker coordination
```

### Future Work

A later hardening pass may introduce:

- single active worker enforcement per `worker_name`
- checkpoint-row locking
- worker lease records
- heartbeat and lease expiry
- `SELECT ... FOR UPDATE`
- `SKIP LOCKED`
- partitioned projection workers
- recovery rules for crashed workers

### Architectural Consequence

This future work should preserve the current invariant:

```text
projection state
+
per-order progress
```

must remain atomic.

It should add runtime coordination around the worker boundary without moving projection semantics into storage.

### Current Classification

```text
Later production hardening
```

### Suggested Timing

After durable replay / rebuild validation exists and before any multi-worker or production deployment story depends on concurrent projection workers.

---

## 2. Order Domain Policy Contract v0 and Policy-Guided Recovery

> **Current qualification:** Stage 4B.5 completed the narrower identity-driven
> Order correctness contract and exact FullProof rule-evidence path. It did not
> implement recovery hints, retry policy, or the speculative policy schema
> below. Generic current-response authority belongs to Stage 4C. The first
> formal Stage 4E profile owns only one additional same-request invocation from
> preparation `LOCK_TIMEOUT`; reload, backoff, limits, budget, and lineage are
> unaccepted future candidates. None may be retroactively attributed to Stage
> 4B.5.

### Current Decision

Do not treat the completed Stage 4B.5 correctness contract as a general-purpose
policy framework or recovery contract.

The current position is:

- minimal actor / permission, `SemanticOutcome`, receipt, trace, measurement,
  and Order correctness foundations are complete
- Stage 4C Runtime Decision Authority is complete / closed
- Stage 4D Strategy Selection Authority is retained / implementation deferred
- Stage 4E Same-Request Re-Invocation Authority has a PR0 boundary / production
  contract unimplemented
- Stage 5 Action Safety is future

A concrete future consumer may justify a small domain-specific policy artifact
as a rule or evidence source within one of those authority boundaries. It is
not a mandatory Stage 4C intermediate.

This contract should be limited to the current minimal order/payment domain.

### Why Not Now

A full policy-fabric-like system would require:

- authored policy schema
- compiled execution plan
- policy version comparison
- validation reports
- replay reports
- release / promotion workflow
- cross-domain governance
- agent workflow integration

That would distract from the current correctness path.

The project does not need that much machinery to prove the Stage 4 governance loop.

### Future Work

If a concrete consumer justifies it, introduce a separately owned minimal
policy artifact such as:

```text
contracts/order_domain_policy_contract_v1.yaml
```

The first version may define:

- allowed order transitions
- forbidden order transitions
- amount rules
- full-payment semantics
- idempotent replay rule
- idempotency conflict rule
- stale-write recovery rule
- projection-drift rebuild / quarantine recovery hint
- snapshot-trust failure recovery hint

The following historical combined sketch preserved useful recovery questions,
but it must not become one Stage 4C contract:

```yaml
recovery_strategies:
  BLOCK:
    retryable: false
    human_required: false

  REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE:
    retryable: true
    max_attempts: 1
    required_action: reload_accepted_history

  ALLOW_REPLAY:
    retryable: false
    required_action: return_prior_accepted_result

  BLOCK_AND_ESCALATE:
    retryable: false
    human_required: true
```

Under ADR 0027, `BLOCK`, replay, rebuild, quarantine, and escalation may express
Stage 4C generic current responses. `retryable`, `max_attempts`, reload
requirements, retry timing, and other broad cross-attempt constraints remain
unaccepted future candidates outside the first formal Stage 4E profile. Stage
4D may choose how an already-authorized response or attempt is performed; it
cannot create action authority.

The earlier sketch also proposed extending `SemanticOutcome` with optional
policy linkage:

```python
@dataclass(frozen=True)
class PolicyRuleRef:
    contract_id: str
    rule_id: str
    version: int
```

Historical candidate optional `SemanticOutcome` fields:

```text
policy_ref
recovery_hint
retry_safety
intent_consistency
```

The implemented Stage 4A `SemanticOutcome` contract remains authoritative. Any
future attempt-specific fields require separate evidence and acceptance and
must not turn semantic observation into retry authorization.

### Architectural Consequence

The current live-governance direction is:

```text
SemanticOutcome
+ applicable rule / correctness evidence
→ Runtime Decision Authority
```

A future policy artifact may supply versioned rules or evidence. It does not
own action authority, become a mandatory intermediate, or authorize another
attempt.

### Current Classification

```text
Deferred domain policy / rule-evidence artifact
```

### Suggested Timing

Only after:

```text
Stage 4A — SemanticOutcome Core (complete)
Stage 4B.5 — Order Correctness Contract v0 (complete)
```

and only when a concrete consumer inside separately reviewed governance work
requires a distinct versioned artifact:

```text
Stage 4C — Runtime Decision Authority
future evidence-gated governance beyond the first Stage 4E profile
```

This remaining recovery-policy work must not be treated as completed
Stage 4B.5 scope:

```text
Order correctness evidence
≠ recovery policy
≠ retry authorization
```

### Non-goals

This future item should not become:

- a full policy authoring platform
- a replacement for Compass validation
- a replacement for accepted-history admission
- a cross-domain governance framework
- a release-pack / promotion system
- an agent workflow orchestrator

The intended role is narrower:

```text
provide stable rule evidence for Stage 4C current-response decisions and later
Stage 4E attempt governance without collapsing their authority
```

---

## 3. UUIDv7 / Time-Ordered UUID Evaluation

### Current Decision

Do not introduce UUIDv7 during the completed durable write-side / read-side baseline work.

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
- decision on whether ordering should be represented by identity, sequence, global position, or append time

### Existing Issue

```text
#7 Evaluate UUIDv7 for durable event identity generation
```

### Current Classification

```text
Later evaluation
```

### Suggested Timing

During later storage / operational hardening, unless storage locality or operational inspection becomes a real bottleneck.

---

## 4. Formal `EventStoreProtocol`

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

## 5. Stored Event Record / JSONB Evidence Hydration

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

During audit, evidence, receipt, or `SemanticOutcome` persistence design.

---

## 6. Registry-Stage Timing in `metadata_json`

### Current Decision

The completed durable baselines did not implement durable timing collection.

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
- snapshot validation duration
- snapshot-assisted resolution duration

### Why Not Now

The completed durable baselines focused on correctness boundaries:

- durable accepted history
- durable idempotency
- transaction atomicity
- concurrency admission
- durable read-side state
- replay / rebuild validation
- snapshot trust substrate

Timing collection is meaningful, but it should not distract from correctness boundaries.

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During Stage 4 evidence / outcome persistence, or during a dedicated observability pass.

---

## 7. Event Payload / Proof / Metadata JSON Shape

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

Stage 3.5C hardened selected durable vocabulary at the schema boundary, but it did not define a full JSONB event evidence model.

### Why Not Now

The project has not yet defined a full durable event payload schema or audit evidence model.

### Future Work

Clarify:

- whether `payload_json` should duplicate event domain fields
- whether `proof_json` is only a proof copy or a richer proof-carrying evidence container
- whether `metadata_json` should be restricted to runtime metadata
- how these fields relate to `SemanticOutcome` / `DecisionReceipt` persistence

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

Before or during `SemanticOutcome` / receipt persistence design.

---

## 8. Projection State Version / Source Sequence Separation

### Current Decision

Do not rename or split `OrderState.version` during the completed durable read-side / snapshot trust baselines.

At the current projection model level:

```text
OrderState.version
= last aggregate-local accepted event sequence reflected by this projection state
```

Therefore `PostgresProjectionStore` intentionally persists:

```text
projection_states.last_sequence = state.version
```

Stage 3.5D keeps the physical projection snapshot rule future-safe:

```text
state_version <= source_event_sequence
```

while current resolver / validator compatibility may still require stricter runtime checks.

### Why Not Now

Changing this would turn a storage-boundary implementation into a projection model refactor.

It would require coordinated changes across:

- reducer logic
- worker sequencing logic
- projection tests
- snapshot trust validation
- future checkpoint / worker integration

The current order domain does not yet include non-state-changing accepted events.

### Future Work

Revisit only if the domain introduces accepted events that do not change business state, or if future reducer / projection versioning requires separating:

```text
business_version
last_processed_sequence
source_global_position
reducer_version
projection_schema_version
```

### Current Classification

```text
Later evaluation
```

### Suggested Timing

Only when non-state-changing accepted events, reducer migration, or projection schema migration requires it.

---

## 9. Append-Only Database Hardening

### Current Decision

The completed durable write-side baseline does not implement production-grade append-only hardening.

Current defenses are:

- application append logic
- `accepted_event_id` primary key
- `UNIQUE(order_id, sequence)`
- expected-version check in the store
- transactional write-side boundary
- two-phase concurrency admission
- durable vocabulary and proof-status schema hardening

These defenses protect the accepted-history write path, but they do not yet make `order_events` a database-level append-only log.

PostgreSQL rows remain mutable by default if a database role has `UPDATE` or `DELETE` authority.

### Why Not Now

Stage 3.5E completed the bounded database-role and minimal actor / permission
baseline. The remaining item is production-grade append-only enforcement and
its operational governance, not the previously missing actor boundary.

This matters because `order_events` should move toward append-only accepted history, while `projection_states` and `projection_checkpoints` must remain mutable enough to support upsert, resume, reset, and rebuild.

### Future Work

Revisit for later production hardening:

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
Later production append-only hardening; bounded Stage 3.5E baseline complete
```

### Suggested Timing

When a concrete production deployment, threat model, or repair-governance need
justifies stronger database-level enforcement.

---

## 10. Integration Test Boundary and CI Strategy

### Current Decision

The project should keep PostgreSQL-backed tests explicit and isolated from the development database.

The current baseline already separates destructive integration tests through `TEST_DATABASE_URL`.

### Remaining Future Work

- clearer test markers for unit vs integration vs destructive PostgreSQL tests
- possible CI matrix split if test runtime grows
- optional database fixture hardening
- optional local developer guide cleanup
- optional smoke-test profile

### Current Classification

```text
Later production hardening
```

### Suggested Timing

When test runtime, CI cost, or local development friction becomes a meaningful bottleneck.

---

## 10A. Class-Based Test Organization after Stage 4 Governance Boundaries Stabilize

### Current Decision

Do not perform broad class-based test reorganization as part of the completed
Stage 4B closeout.

Stage 4 Interlude PR0 already completed the intended pre-Stage-4B test helper consolidation. That cleanup moved stable repeated builders and small PostgreSQL helpers into `tests/shared/` while preserving:

```text
same test names
same assertions
same behavior
less duplicated setup
```

Class-based grouping remains deferred test-maintainability work. Completed
Stage 4B.1, Stage 4B.2, and Stage 4B.5 already establish the current trace,
measurement, and exact-rule evidence surfaces. Stage 4C, Stage 4D, and Stage 4E
may still reshape downstream governance-test organization.

### Why Not Now

Class grouping can improve readability after the semantic boundaries are stable, but doing it too early may hide the evolving distinctions between:

```text
DecisionReceipt construction
DecisionReceipt evidence extraction
DiagnosticTrace lineage
Measurement / cost evidence
Runtime Decision Authority
Strategy Selection Authority
Retry / Attempt Authorization
```

The current priority is to preserve the explicit Stage 4B test evidence while
later governance contracts are still emerging.

The project should not reorganize tests around classes merely for aesthetic grouping.

### Future Work

As production Stage 4C, Stage 4D, and Stage 4E boundaries become concrete,
revisit class-based organization when a specific high-density test surface has
stable semantic responsibilities and a real maintainability need.

Potential future grouping examples:

```text
TestDecisionReceiptConstruction
TestDecisionReceiptEvidence
TestDecisionReceiptIdentityLineage
TestDiagnosticTraceLineage
runtime-decision-authority test group
strategy-selection test group
retry-attempt-authorization test group
TestPostgresWriteSideCreateFlow
TestPostgresWriteSideReplayAndConflict
```

Existing transition validator tests already provide a useful reference style because they group by semantic failure class, for example:

```text
TestPredecessorMismatchCases
TestPrevStatusMismatchCases
TestPrevVersionMismatchCases
TestStaleCandidateCases
```

Future class grouping should follow the same principle:

```text
semantic responsibility first
not visual grouping for its own sake
```

### Guardrails

Future class-based cleanup should preserve:

```text
same test intent
same assertions
same behavior
explicit semantic evidence
explicit identity lineage
explicit boundary conditions
```

It should not introduce:

```text
scenario DSL
opaque broad fixtures
hidden semantic setup
hidden transaction or lock behavior
hidden identity contradiction setup
production-readiness behavior
```

### Current Classification

```text
Later evaluation / post-Stage-4 governance test organization
```

### Suggested Timing

Revisit after at least one of the following is true:

```text
a completed Stage 4B.x evidence surface or a later Stage 4C, Stage 4D, or
Stage 4E governance surface develops concrete maintainability pressure
public-release test readability review begins
```

Do not treat this as a Stage 4B deliverable. It remains optional later
maintainability work, and any grouping should continue to follow semantic
responsibilities rather than visual uniformity.

---

## 11. Aggregate Snapshot Schema / Store and Write-Side Rehydration

### Current Decision

Do not implement durable aggregate snapshots or snapshot-assisted write-side rehydration during Stage 3.5D.

Stage 3.5D completed the read-side projection snapshot trust path and explicitly deferred write-side aggregate snapshot implementation.

### Why This Boundary Exists

Read-side projection snapshots are derived runtime compression artifacts.

They can be rejected, bypassed, rebuilt, or compared against accepted history.

Write-side aggregate snapshots are stricter because they may influence command validation and accepted-history admission.

A stale or corrupted aggregate snapshot could cause the system to validate a candidate event against the wrong aggregate state.

### Deferred Work

- `aggregate_snapshots` schema
- `AggregateSnapshot` model
- `PostgresAggregateSnapshotStore`
- aggregate snapshot collision policy
- snapshot-assisted write-side aggregate rehydration
- fallback to full accepted-history replay when aggregate snapshot trust fails
- command admission tests for snapshot fast path and fallback path

### Future Trigger Conditions

Revisit only when at least one condition is true:

- aggregate replay depth becomes meaningfully expensive
- command admission latency needs a fast path
- durable validation receipts exist
- snapshot trust gate / selector infrastructure exists
- invalidation and fallback policy are explicit
- benchmark data shows the optimization is worth the added trust risk

### Current Classification

```text
Later evaluation
```

### Suggested Timing

After Stage 4 receipts / runtime governance exist, or when aggregate replay cost becomes a concrete bottleneck.

---

## 12. Pre-Transaction Cleanup Failure Handling

### Current Decision

The minimal `PRE_TRANSACTION` validation path should clean up implicit PostgreSQL read transactions before CPU-side validation begins.

The completed baseline records the boundary, but does not introduce advanced cleanup-failure governance.

### Deferred Concern

Future code may need to classify cleanup failure separately from:

- validation block
- idempotency conflict
- concurrency admission rejection
- infrastructure failure
- runtime decision failure

A cleanup failure can be operationally important because it affects whether the physical connection can safely continue.

### Future Direction

Introduce structured outcome / error classification for cleanup failure, such as:

```text
PRE_TRANSACTION_CLEANUP_FAILED
CONNECTION_UNSAFE_AFTER_CLEANUP_FAILURE
```

Then decide whether the runtime should:

- retry with a new connection
- discard the connection
- block the request
- raise infrastructure error
- emit an operational alert

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During structured outcome / runtime evidence design.

### Related Note

- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

---

## 13. Retry Reason Classification and Intent Consistency

### Current Decision

Do not treat retry as a single generic category.

The first formal Stage 4E profile owns only whether preparation `LOCK_TIMEOUT`
evidence authorizes one additional public-writer invocation of the same
complete `RequestSignature`. The broad taxonomy below does not own or imply
authority.

### Why Not Now

The completed baselines already distinguish:

- idempotent replay
- idempotency conflict
- stale write
- validation block
- infrastructure failure
- projection drift
- snapshot-assisted replay mismatch
- snapshot trust failure

`SemanticOutcome` is complete for its bounded producer families. The production
Stage 4E contract remains unimplemented; unified request-attempt evidence and
broader classification remain unaccepted future candidates.

### Future Work

The following historical candidate distinctions remain useful input to
separately justified future governance:

```text
same request_id + same semantic_fingerprint
→ IDEMPOTENT_REPLAY / SAFE_TO_REPLAY / SAME_INTENT

same request_id + different semantic_fingerprint
→ SEMANTIC_CONFLICT

stale write caused by concurrent accepted-history advancement
→ REFRESH_HISTORY_AND_RETRY_IF_SAME_INTENT

transient infrastructure error
→ RETRYABLE_INFRASTRUCTURE_FAILURE

projection drift
→ REBUILD_DERIVED_STATE_BEFORE_CONTINUING

snapshot mismatch
→ FALLBACK_TO_AUTHORITY_REPLAY_OR_REQUALIFY_SNAPSHOT

agent retry with changed intended action
→ INTENT_DRIFT / NOT_SAFE_TO_RETRY
```

Suggested future fields:

```text
retry_class
retry_safety
intent_consistency
attempt_id
request_id
semantic_fingerprint
```

### Current Classification

```text
Historical / future candidate taxonomy — not accepted first-slice Stage 4E scope
```

### Suggested Timing

When a concrete consumer, evidence boundary, and reviewed authority rule beyond
the first Stage 4E profile are approved.

---

## 14. Isolated Derived-State Runtime / Oblivious Agent Runtime

### Current Decision

Do not isolate the read-side runtime or build an agent-facing sandbox during Stage 3.5E or the first Stage 4 passes.

### Concept

A later version may separate:

```text
accepted history authority
derived runtime state
agent-visible state
```

so that agents cannot directly observe or mutate authority tables.

### Why It Matters

If future agents act on derived state, the system may need stronger isolation so the agent sees an admitted, governed, and possibly delayed view rather than raw authority or unstable runtime internals.

### Future Work

- isolated read-side database
- agent-facing derived-state API
- governed state publication
- read-side admission receipts
- policy-controlled context exposure
- action safety gate integration

### Current Classification

```text
Stage 5+ / later governance hardening
```

### Suggested Timing

After Stage 5 dual-dimension governance makes semantic correctness and operational freshness explicit.

---

## Capacity Pressure Evidence Checkpoint

### Current Decision

Do not introduce a capacity mechanism or a new semantic status now.

Concurrency control protects correctness under shared-state contention.
Capacity controls protect availability and resource usage under load. Locks
and optimistic concurrency control are therefore not rate limiting.

### Future Evidence and Mechanisms

A future design should follow observed baseline, load, stress, soak, and fault
evidence. Possible mechanisms include rate limiting, bounded concurrency,
queues, per-key admission, and backpressure.

Overload must not be mapped directly to semantic invalidity. Capacity pressure
is operational evidence that later governance may interpret; it is not proof
that the underlying domain action is semantically invalid.

### Current Classification

```text
Later production hardening
```

---

## Summary

This backlog is not a second roadmap.

It only preserves intentionally deferred architecture concerns whose timing depends on future evidence, governance, production-hardening, or runtime-complexity needs.

Completed implementation work belongs in implementation notes, not here.

---

## Production-Like Chaos and Concurrency Hardening after Stage 4 Governance

**Status:** Deferred to Stage 4 late phase / Stage 5 production-hardening work.

Stage 3.5E permission tests verify the baseline PostgreSQL role / privilege matrix through isolated permission probes.

They do not prove production-like behavior under:

```text
concurrent workers
independent runtime connections
connection-pool reuse
rollback failure
worker crash windows
snapshot write races
checkpoint advancement races
derived-state corruption recovery
permission bypass attempts during active workflows
```

Those scenarios should be revisited after Stage 4 establishes structured
semantic outcomes, applicable durable evidence, Runtime Decision Authority,
Strategy Selection Authority, and conditional Retry / Attempt Authorization.

The reason is sequencing: chaos tests are most useful after the system can
classify what happened, preserve durable evidence when required, authorize a
current response, and distinguish operational failure from semantic risk.
