# ADR 0021: Projection Snapshots Are Optional for the Current Order Workload

[← Back to ADR Index](README.md)

## Status

Accepted

## Decision Scope

This ADR defines the current architectural importance of projection snapshots after:

- Stage 3.5D Snapshot Trust Contract work;
- the deferral of write-side aggregate snapshot rehydration;
- ADR 0020's move from global-position completeness assumptions to per-order
  exact-next projection progress;
- the later workload revalidation recorded in
  [Postmortem: From Snapshot Trust to Snapshot Necessity Revalidation](../postmortems/from_snapshot_trust_to_snapshot_necessity_revalidation.md).

This ADR does **not** reject snapshots as a general Event Sourcing technique.

It does **not** invalidate ADR 0013's trust rules.

It decides whether projection snapshots should be treated as required runtime
infrastructure for the **current Order workload**.

---

## Context

The project currently preserves:

```text
accepted history
= business authority

projection_states
= current derived read model

projection_order_progress
= durable per-order completeness/progress evidence

projection_snapshots
= optional derived reconstruction checkpoints
```

Stage 3.5D developed projection snapshots as a safer proving ground for the broader
Snapshot Trust Contract before considering the higher-risk write-side aggregate
snapshot path.

The write-side concern was:

```text
invalid aggregate snapshot
→ false aggregate state
→ incorrect command validation
→ incorrect candidate event
→ possible accepted-history admission risk
```

That trust problem remains real.

However, the current Order aggregate has a deliberately shallow lifecycle:

```text
INIT
→ CREATED
→ PAID
```

and therefore a very short accepted history:

```text
created but unpaid
→ 1 accepted event

paid
→ 2 accepted events
```

Write-side aggregate snapshot persistence and snapshot-assisted rehydration were
already deferred because this workload does not contain meaningful aggregate replay
debt.

Projection snapshots were retained longer because global event-stream growth and
projection checkpoint growth were previously treated as evidence that projection
replay/reconstruction cost would also grow.

ADR 0020 later corrected the projection execution model.

Projection completeness now uses:

```text
projection_name
+ projection_epoch
+ order_id
+ exact-next local sequence
```

and snapshot tails are reconstructed through:

```text
snapshot.source_event_sequence
+ same-order exact contiguous tail
```

`global_position` remains lineage and deterministic scheduling evidence.

It must not be interpreted as:

```text
a complete committed-history frontier
```

or as:

```text
a measure of one order's replay depth
```

The relevant snapshot performance question is therefore aggregate-local:

```text
How many events must one reconstruction unit replay,
and how expensive is that reconstruction?
```

For the current Order model, the answer is too small to justify projection snapshots
as required runtime acceleration.

---

## Problem

The project must avoid two incorrect conclusions.

### Incorrect conclusion A

```text
snapshot trust machinery is valid
→ snapshots must remain core runtime infrastructure
```

This does not follow.

A trust contract explains how an artifact may be used safely.

It does not prove that the artifact is operationally necessary.

### Incorrect conclusion B

```text
current Order workload does not need snapshots
→ Snapshot Trust Contract was architecturally wrong
```

This also does not follow.

If a future workload uses snapshot-assisted reconstruction, the same trust questions
remain:

```text
snapshot existence
≠ snapshot eligibility

snapshot eligibility
≠ semantic correctness

derived state
≠ accepted-history authority

snapshot-assisted path
must remain subordinate to authority
```

The project therefore needs a current stance that preserves reusable trust semantics
without continuing snapshot-specific expansion by default.

---

## Decision

For the current Order workload:

```text
Projection snapshots are optional derived reconstruction evidence.

They are not required for:
- business correctness;
- accepted-history authority;
- normal current-state reads;
- projection-worker restart;
- projection completeness;
- current-workload replay performance.
```

The project will treat the existing snapshot subsystem as:

```text
optional reference / trust-analysis infrastructure
```

rather than:

```text
mandatory production fast-path infrastructure
```

### Snapshot Trust Contract remains valid

ADR 0013 remains authoritative for this rule:

```text
If a snapshot is used by runtime,
it must not be trusted by existence alone.
```

The current decision changes snapshot **necessity**, not snapshot **trust semantics**.

### Global position is not a snapshot-necessity metric

The project will not justify snapshot creation or snapshot-specific runtime expansion
using:

```text
global_position size
```

or:

```text
total global event count
```

alone.

Any future snapshot policy must reason about the actual reconstruction unit, for
example:

```text
aggregate-local event depth
reducer / hydration cost
reconstruction frequency
rebuild or recovery RTO
```

### Current projection paths remain snapshot-independent

The following remain sufficient without snapshots:

```text
accepted history
→ projection worker
→ projection_states
→ projection_order_progress
```

Normal current-state serving continues to use `projection_states`.

Authority reconstruction and drift validation may continue to use accepted-history
replay.

Projection completeness and safe continuation remain responsibilities of
per-order projection progress.

### Further snapshot-specific Stage 4 work is conditional

New snapshot-specific Stage 4 work requires a concrete justification.

At least one of the following should exist before snapshot work expands again:

```text
1. a production runtime caller that materially benefits from snapshot resolution;
2. materially deeper aggregate-local accepted history;
3. measured reconstruction cost that exceeds an explicit threshold;
4. a rebuild / recovery RTO that full replay cannot satisfy;
5. a concrete StrategySelector / TrustGate consumer;
6. an explicitly bounded reference-case objective.
```

Prior investment is not sufficient justification.

---

## Rationale

### 1. Projection state already serves normal reads

`projection_states` is the current materialized read model.

For ordinary reads:

```text
order_id
→ projection_states
```

is simpler than:

```text
snapshot
→ compatibility checks
→ hydrate
→ load tail
→ validate tail
→ replay
→ resolve state
```

Snapshot-assisted resolution therefore does not replace the normal read path.

---

### 2. Projection progress already owns restart/completeness semantics

After ADR 0020, safe projection continuation is aggregate-local.

The relevant boundary is:

```text
projection identity
+ epoch
+ order
+ exact-next sequence
```

Projection snapshots are not required to prove that the worker can resume safely.

---

### 3. The current Order history is too shallow to create replay debt

The current reference Order has no legal long-running stream of accepted
state-changing events.

A sequence-1 snapshot can eliminate replay of approximately one event.

A sequence-2 snapshot generally leaves no later Order event to replay in the current
domain.

That is not sufficient operational evidence for a dedicated runtime optimization.

---

### 4. Snapshot trust remains a reusable correctness pattern

The lack of current workload necessity does not erase the trust boundary.

A snapshot can still be:

```text
physically valid
but semantically wrong
```

and a future runtime that consumes it may still need:

```text
lineage
integrity evidence
version compatibility
authority validation
eligibility evidence
discardability
fallback
```

The existing subsystem therefore remains valuable as a concrete reference case for
derived-state governance.

---

### 5. Complexity must continue to pay for itself

The existing snapshot subsystem introduces:

```text
schema
store semantics
lineage
hashing
compatibility
validator statuses
resolver statuses
outcome mappings
receipt mappings
trace possibilities
future strategy possibilities
```

That complexity is acceptable only when attached to a real requirement or an
explicitly bounded reference goal.

The project will not expand the subsystem solely because it is already implemented.

---

## Alternatives Considered

### Option A — Continue treating projection snapshots as a core Stage 4 fast path

Under this option, future Stage 4 work would continue building snapshot-specific:

```text
ResolutionTrace
cost evidence
TrustGate
StrategySelector
runtime policy
```

#### Benefits

```text
- maximizes reuse of existing snapshot work
- provides a rich concrete case for Stage 4 abstractions
- prepares for future long-history workloads
```

#### Costs

```text
- current workload does not need the fast path
- increases maintenance and semantic surface
- risks allowing sunk cost to drive architecture
- distracts from write-side and projection-worker paths with current operational value
```

#### Decision

Rejected as the default direction.

Snapshot-specific work may continue only when independently justified.

---

### Option B — Remove the entire snapshot subsystem immediately

Under this option, the project would delete snapshot schema, stores, validator,
resolver, mappings, tests, and documentation.

#### Benefits

```text
- smallest current runtime surface
- removes maintenance burden
- eliminates ambiguity about snapshot importance
```

#### Costs

```text
- removes a well-developed derived-state trust reference implementation
- destroys useful evidence about authority-vs-fast-path reasoning
- creates a large mechanical cleanup unrelated to current correctness needs
- may prematurely discard reusable work before the Stage 4 reprioritization is complete
```

#### Decision

Rejected for now.

No current correctness requirement forces immediate removal.

---

### Option C — Retain snapshots as optional reference infrastructure

Under this option:

```text
existing snapshot subsystem remains

but

snapshot-specific expansion stops unless a real consumer or workload justifies it
```

#### Benefits

```text
- preserves Snapshot Trust Contract evidence
- avoids unnecessary deletion work
- prevents snapshot from dominating future Stage 4
- permits future reuse if the workload changes
- makes current architectural priority explicit
```

#### Costs

```text
- some optional code and documentation remain
- future readers must understand that implementation does not imply recommendation
- snapshot-specific stale documentation still requires careful supersession notes
```

#### Decision

Accepted as the current direction.

---

## Consequences

### Positive Consequences

The project gains a clearer separation between:

```text
correctness requirement
performance optimization
reference implementation
```

Stage 4 can prioritize paths with stronger current operational importance:

```text
write-side command execution
validation placement
concurrency admission
transaction ownership
commit evidence
projection-worker progress
runtime decision policy
strategy selection
retry governance
```

The project also gains an explicit architectural rule:

> A global stream can grow without increasing the replay debt of any individual
> aggregate.

---

### Negative Consequences

Some snapshot-specific code remains more elaborate than the current workload
requires.

Existing documents may still contain historical wording that overstates the
importance of global-position-based replay or snapshot acceleration.

Those documents should be superseded carefully rather than silently rewritten as if
the project had always used the current model.

The project must also avoid accidentally treating snapshot-specific Stage 4
artifacts as mandatory dependencies merely because they already exist.

---

## Relationship to ADR 0013

ADR 0013 remains valid.

It answers:

```text
If runtime wants to use a snapshot,
what evidence or precondition is required?
```

This ADR answers a different question:

```text
Does the current Order workload require runtime to use projection snapshots at all?
```

The answers are:

```text
ADR 0013:
snapshot trust must be explicit

ADR 0021:
snapshot use is optional for the current workload
```

There is no conflict.

---

## Relationship to ADR 0020

ADR 0020 remains authoritative for projection progress and snapshot-tail mechanics.

This ADR adopts its consequence:

```text
global_position
= lineage / scheduling evidence

not
= committed-history completeness proof
```

Snapshot necessity must therefore be evaluated using order-local reconstruction
cost, not global-position growth.

---

## Relationship to Stage 4

Generic Stage 4 concepts do not depend on snapshots.

In particular:

```text
SemanticOutcome
DecisionReceipt
ResolutionTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
```

may all be exercised by non-snapshot producers.

Snapshot-specific adapters remain one concrete family of producers, not the
foundation of these abstractions.

This ADR supplies the workload-necessity decision; the Stage 4B.1 PR breakdown
owns producer sequencing. The accompanying reprioritization records that the PR2
snapshot trace contract remains the final bounded reference case, runtime traced
resolver integration is deferred before implementation, and projection-worker
`DiagnosticTrace` is not planned for current Stage 4B.1.

---

## Revisit Conditions

Revisit this ADR if one or more of the following becomes true:

```text
1. Order gains materially longer aggregate-local event histories.
2. A different aggregate with deep history is introduced.
3. Full replay exceeds an explicit latency or recovery target.
4. Projection rebuild becomes operationally expensive.
5. A production StrategySelector selects snapshot-assisted reconstruction.
6. Persisted trust evidence makes snapshot fast-path reuse operationally valuable.
7. A recovery / audit workflow requires historical derived checkpoints.
```

At that point, snapshots may move from:

```text
optional reference infrastructure
```

to:

```text
operationally justified runtime optimization
```

without changing accepted history as authority.

---

## Decision Summary

For the current Order workload:

```text
snapshot trust problem
= real

snapshot implementation
= valid reference machinery

snapshot correctness necessity
= none

snapshot operational necessity
= none demonstrated

snapshot performance necessity
= none demonstrated

future snapshot expansion
= evidence-gated
```

The project will preserve the existing trust reasoning while refusing to let prior
investment alone justify additional snapshot complexity.
