# Postmortem: From Snapshot Trust to Snapshot Necessity Revalidation

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-08-07

## Current Authority

This note records the historical reasoning path that led the project to re-evaluate
snapshot necessity.

It is intentionally historical and explanatory. Current architectural decisions
remain governed by accepted ADRs, especially:

- [ADR 0013 — Snapshot Runtime Eligibility and Validation Receipt Boundary](../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md)
- [ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md)
- [ADR 0021 — Projection Snapshots Are Optional for the Current Order Workload](../adr/0021_projection_snapshots_are_optional_for_current_order_workload.md)

This postmortem does **not** invalidate the Snapshot Trust Contract. It records why
the project now distinguishes a real trust problem from an absent workload need.

---

## 1. Purpose

The project implemented a substantial projection-snapshot subsystem:

```text
projection snapshot persistence
→ snapshot lineage and integrity evidence
→ authority-based replay validation
→ snapshot-assisted state resolution
→ SemanticOutcome mapping
→ DecisionReceipt mapping
→ planned ResolutionTrace work
```

The subsystem is technically meaningful and its trust boundaries remain useful.

However, later project evolution exposed a different question:

```text
Even if snapshots can be used safely,
does this system actually need snapshots?
```

This note records the full reasoning path behind that question.

The important correction is not:

```text
snapshot trust was a mistake
```

It is:

```text
snapshot trust problem = real

snapshot workload necessity
= must be proven separately
```

The project reached this conclusion through two separate premise revalidations:

1. write-side aggregate snapshots were deferred after the real Order workload was
   shown to have negligible aggregate-local replay depth;
2. projection snapshots were later re-opened for review after the projection worker
   moved away from global-position completeness assumptions toward durable
   per-order exact-next progress.

---

## 2. The Original High-Risk Concern Was Write-Side Snapshot Rehydration

The earliest written snapshot notes framed snapshots partly as replay-cost
optimization:

```text
event history grows
→ full replay becomes expensive
→ snapshot may reduce replay / rehydration cost
```

That was a real part of the early reasoning, but it was not the deepest correctness
concern that drove the Snapshot Trust Contract.

The higher-risk concern was the future write-side path:

```text
accepted history
→ aggregate snapshot
→ aggregate rehydration
→ command validation
→ candidate event
→ accepted history
```

If the snapshot were wrong but runtime treated it as current aggregate state:

```text
bad snapshot
→ false aggregate state
→ wrong command validation
→ wrong candidate event
→ possible pollution of future accepted history
```

This is qualitatively more dangerous than an incorrect read model.

A read-side error can produce:

```text
incorrect display
incorrect derived observation
incorrect diagnostic state
```

A write-side rehydration error can instead feed an authority-producing path:

```text
derived corruption
→ admission logic
→ new accepted fact
```

The Snapshot Trust Contract therefore had a real correctness motivation even before
any concrete snapshot optimization was proven necessary.

Later documentation makes this original high-risk concern explicit:

```text
invalid aggregate snapshot
→ false aggregate state
→ incorrect command validation
→ incorrect candidate event
→ possible accepted-history admission risk
```

The fact that this intent was not fully written down at the very beginning is itself
part of the historical record. The later boundary and ADR work preserve it more
clearly than the earliest performance-oriented wording.

---

## 3. Why the Project Implemented Read-Side Snapshot Trust First

The project did not begin by inserting snapshots directly into write-side aggregate
rehydration.

Instead, it chose projection snapshots as a lower-blast-radius proving ground:

```text
accepted history
→ projection reducer
→ projection state
→ projection snapshot
```

The engineering sequence was deliberate:

```text
high-risk target:
write-side aggregate snapshot trust

↓

lower-risk proving ground:
read-side projection snapshot trust

↓

prove:
lineage
integrity evidence
authority comparison
eligibility
tail replay
discardability
trust vocabulary

↓

only then decide whether the same contract
should enter write-side rehydration
```

This separation was valuable because the project could explore the trust machinery
without immediately allowing derived snapshot state to influence new accepted facts.

The resulting read-side work established several durable principles:

```text
accepted history = authority

snapshot = derived compression

snapshot existence ≠ snapshot trust

database validity ≠ semantic equivalence

eligibility ≠ authority proof

validator ≠ resolver

snapshot-assisted replay = candidate fast path

full accepted-history replay = authority path
```

Those principles remain valid even if the current workload ultimately does not need
snapshot acceleration.

---

## 4. First Premise Revalidation: Write-Side Snapshot Need Disappeared

After the read-side trust machinery was developed, the project returned to the
original higher-risk target:

```text
Aggregate Snapshot Schema / Store
Snapshot-Assisted Write-Side Rehydration
```

At that point the actual reference domain was examined more carefully.

The current Order lifecycle is deliberately small:

```text
INIT
→ CREATED
→ PAID
```

The accepted history is correspondingly shallow:

```text
created but unpaid order
→ 1 accepted event

paid order
→ 2 accepted events

current reference model
→ no legal third accepted event
```

That changed the workload analysis.

The relevant replay cost on the write side is not:

```text
total events in the database
```

It is:

```text
accepted events for this aggregate
```

For the current Order model:

```text
aggregate-local replay depth ≈ 1–2 events
```

There was therefore no demonstrated write-side reconstruction debt for snapshots to
solve.

The project stopped before implementing write-side aggregate snapshot persistence
and snapshot-assisted write-side rehydration.

This was the first snapshot stop-loss decision:

```text
write-side trust hazard
= real

write-side snapshot mechanism
= technically possible

current write-side workload need
= absent

therefore
→ defer implementation
```

The decision did not reject aggregate snapshots as a general Event Sourcing pattern.
It rejected spending current complexity budget on a workload that did not exist.

---

## 5. Why Read-Side Projection Snapshots Survived the First Revalidation

The write-side deferral did not immediately eliminate projection snapshots.

At the time, the project still carried a different mental model for projection
processing.

The working intuition was approximately:

```text
global accepted history keeps growing
→ projection checkpoint moves farther through the stream
→ projection replay / reconstruction burden appears to grow
→ projection snapshot still appears useful
```

Under that model, the project could consistently hold two different conclusions:

```text
write side:
per-order history is shallow
→ snapshot not needed

read side:
global stream keeps growing
→ projection snapshot may still reduce replay cost
```

The important point is that this was not merely:

```text
the code already exists
→ keep it
```

The read-side snapshot path still appeared to have a separate performance premise.

That premise was not fully re-evaluated until the projection worker itself was later
repaired and understood more precisely.

---

## 6. Projection Worker Repair Changed the Cost Model

The old projection mechanics relied on a scalar global-position cursor.

Conceptually:

```text
checkpoint = global_position N

load event where global_position > N
→ apply
→ advance checkpoint
```

That model contained a PostgreSQL commit-visibility defect.

A lower global position can be allocated by one transaction and commit after a
higher global position allocated by another transaction:

```text
T1 allocates P1
T1 remains uncommitted

T2 allocates P2
T2 commits

worker observes P2
worker advances global checkpoint to P2

T1 commits P1 later
```

A correctness rule based on:

```text
global_position > checkpoint
```

can then exclude P1 forever.

ADR 0020 repaired the model by moving projection completeness to an aggregate-local
boundary:

```text
projection_name
+ projection_epoch
+ order_id
+ exact-next local sequence
```

The current projection worker therefore reasons about:

```text
this order's durable progress
→ next accepted local sequence
```

rather than treating global position as a committed-history completeness frontier.

`global_position` remains useful as lineage and deterministic cross-order scheduling
evidence, but it no longer proves:

```text
everything before this global position has been safely processed
```

The snapshot-tail mechanism was repaired for the same reason:

```text
snapshot.source_event_sequence
+ same-order exact contiguous tail
```

now defines reconstruction progress.

---

## 7. Second Premise Revalidation: Global Stream Growth Is Not Local Replay Debt

Once the worker execution model became explicit, a previously hidden assumption
became visible.

The project had partially conflated:

```text
global stream growth
```

with:

```text
projection reconstruction cost
```

Those quantities live at different scopes.

For example:

```text
500,000 orders
× 2 accepted events per order
≈ 1,000,000 global accepted events
```

The global stream is large.

But for one order:

```text
full replay(order-A)
≈ 2 events
```

Therefore:

```text
global event count
≠ aggregate-local replay depth
```

Similarly:

```text
large global_position
≠ normal incremental worker replay cost
```

Normal projection processing does not mean:

```text
restart
→ replay every event from global position 0
```

It means resuming from durable projection progress and processing currently eligible
exact-next work.

The question that should drive snapshot policy is therefore not:

```text
How large is global_position?
```

It is:

```text
How much work must one reconstruction unit replay?
```

For snapshots, the relevant cost dimension is approximately:

```text
aggregate-local event count
× reducer / hydration cost
× frequency of reconstruction
```

The current Order domain performs poorly as a justification for snapshot
acceleration because its aggregate-local history is intentionally tiny.

This was the second snapshot stop-loss decision:

```text
read-side trust path
= technically valid

global-position growth
= not replay-cost evidence

current projection workload
= no demonstrated snapshot necessity

therefore
→ re-evaluate further snapshot-specific expansion
```

---

## 8. Checkpoint, Progress, and Snapshot Must Remain Separate Concepts

This revalidation exposed three concepts that should never be collapsed again.

### Global lineage coordinate

```text
global_position
```

Meaning:

```text
global allocation / lineage / scheduling coordinate
```

It does not prove aggregate-local replay depth or committed-history completeness.

### Projection progress

```text
projection_name
+ projection_epoch
+ order_id
+ last_sequence
```

Meaning:

```text
durable exact-next processing evidence
for one projection and one order
```

It supports safe incremental worker continuation.

### Snapshot

```text
order-local derived state
captured at source_event_sequence N
```

Meaning:

```text
optional reconstruction checkpoint
for a particular derived-state path
```

It may reduce reconstruction work when aggregate-local histories are materially
deep.

A snapshot is not a substitute for projection progress.

Projection progress is not a snapshot.

Global position is not either one.

---

## 9. What Was Wrong and What Was Not Wrong

The project should not rewrite history as though every snapshot decision had been
correct.

There were real mistakes and overengineering.

### What was wrong

The project spent significant implementation and documentation effort on a snapshot
subsystem before the actual workload need had been demonstrated.

The read-side performance story also retained too much dependence on a
global-stream-growth intuition that later became inappropriate after the projection
worker repair.

The general lesson is:

```text
do not choose an optimization substrate
before verifying that the expensive operation
grows in the same scope as the quantity being measured
```

For this project:

```text
global stream scope
≠ aggregate reconstruction scope
```

### What was not wrong

The Snapshot Trust problem itself was real.

If any future runtime uses derived snapshot state—especially on an
authority-producing write path—the system still needs to answer:

```text
Why is this derived state safe enough to use?
```

The following principles remain useful:

```text
derived evidence ≠ authority

physical validity ≠ semantic correctness

snapshot existence ≠ runtime eligibility

runtime eligibility ≠ authority-validated trust

validation evidence ≠ authorization

fast path must remain discardable

authority replay must remain able to supersede derived state
```

The project therefore does not need to pretend the snapshot subsystem is a current
production necessity in order to preserve the value of the trust analysis.

---

## 10. Current Architectural Assessment

The current assessment is:

| Dimension | Current assessment |
| --- | --- |
| Snapshot trust problem | Real and reusable |
| Write-side snapshot need | Not demonstrated for the current Order workload |
| Projection snapshot need | Not demonstrated for the current Order workload |
| Correctness dependency on snapshots | None |
| Normal current-state read dependency | None |
| Projection restart/progress dependency | None; per-order progress owns this |
| Current performance justification | None demonstrated |
| Architecture / research value | High as a derived-state trust reference case |
| Future value | Conditional on a real snapshot consumer or materially deeper aggregate-local histories |

The current snapshot subsystem should therefore be understood as:

```text
technically implemented
+
semantically analyzed
+
not currently required
```

rather than:

```text
core runtime infrastructure that must keep expanding
```

---

## 11. Relationship to Stage 4

Stage 4 has already extracted useful generic boundaries from the snapshot work.

Snapshot-specific producers have helped exercise:

```text
technical result
→ SemanticOutcome
→ DecisionReceipt
```

and the distinction between:

```text
primary result
semantic meaning
durable governance evidence
diagnostic detail
runtime decision
strategy
retry authorization
```

Those generic abstractions do not depend on snapshots.

Therefore:

```text
snapshot-specific Stage 4 work
```

must no longer expand merely because earlier stages already invested in snapshots.

Further snapshot-specific work should require at least one of:

```text
1. a real production caller;
2. materially deeper aggregate-local history;
3. measured reconstruction cost;
4. an explicit rebuild / recovery requirement;
5. a concrete trust-gated strategy consumer;
6. a reference-case goal that is intentionally bounded and documented as such.
```

Absent such evidence, Stage 4 should prioritize paths with current operational
importance, especially:

```text
write-side authoritative mutation
projection worker correctness
validation placement
concurrency
transaction evidence
runtime policy
strategy selection
retry governance
```

---

## 12. Reusable Engineering Lesson

The most reusable lesson is not:

```text
snapshots are unnecessary
```

Snapshots are valuable for workloads where one reconstruction unit accumulates
large event histories or where reconstruction itself is expensive.

The reusable lesson is:

```text
Optimization necessity must be scoped to the expensive operation.
```

More concretely:

```text
global stream growth
does not imply
aggregate-local replay growth

global lineage
does not imply
projection completeness

technical correctness
does not imply
workload necessity

implemented successfully
does not imply
continued expansion is justified
```

A better review sequence for future optimizations is:

```text
1. Identify the expensive operation.
2. Identify its true unit of work.
3. Measure or bound how that unit grows.
4. Separate correctness requirements from performance requirements.
5. Add optimization machinery only when the workload justifies its complexity.
6. Revalidate old assumptions after the execution model changes.
```

---

## 13. Final Takeaway

The project first asked:

```text
How can snapshots be used safely?
```

It later asked the equally important question:

```text
Should this system be using snapshots at all?
```

The answers are compatible:

```text
Snapshot Trust Contract
= a valid solution to a real derived-state trust problem

Current Order snapshot requirement
= not demonstrated
```

The resulting architecture lesson is:

> A mechanism can be correctly designed for a real class of problems and still be
> unnecessary for the workload currently in front of the system.

The correct response is not to defend prior complexity because it already exists.

The correct response is to preserve the reusable reasoning, stop expanding the
unjustified path, and redirect engineering effort toward the boundaries that
currently carry authority and operational risk.
