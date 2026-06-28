# Postmortem: Local Correctness, Global Premise Drift

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-26

---

## 1. Purpose

This note records a stage-level reasoning correction discovered during Stage 3.5D.

The issue was not that the implemented code was wrong.

The issue was subtler:

```text
Each local PR could be technically correct,
while the stage-level premise had partially drifted.
```

This is especially important in AI-assisted engineering.

An agent loop can help make each implementation step more complete, more tested, and more internally consistent. But if the original reason for doing the work is not rechecked, the loop may continue optimizing a direction whose cost-benefit profile has changed.

In short:

```text
agent loop can be green,
but architectural intent can drift.
```

This mirrors the core Compass lesson:

```text
a pipeline can be green,
but business meaning can be wrong.
```

---

## 2. Context

Stage 3.5D was introduced as:

```text
Snapshot Trust Contract / Replay Efficiency
```

The original stage principle was:

```text
accepted history = authority
snapshot = derived state compression
fast path = snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

The initial motivation behind snapshot work seemed straightforward:

```text
event log grows over time
→ full replay becomes expensive
→ snapshot can reduce replay / rehydrate cost
```

However, snapshot support is not only a performance optimization.

If a runtime uses a snapshot as the starting point for reconstruction, then a stale, corrupted, incompatible, or incorrectly generated snapshot can produce false current state.

That false state may then affect downstream runtime behavior.

This led to the general Snapshot Trust Contract idea.

---

## 3. Original High-Risk Concern

The strongest original trust-boundary concern was write-side aggregate rehydration.

A write-side aggregate snapshot can influence:

```text
command validation
candidate event generation
Compass Layer 1 validation context
accepted-history admission
```

The dangerous chain is:

```text
invalid aggregate snapshot
→ false aggregate state
→ incorrect command validation
→ incorrect candidate event
→ polluted Compass Layer 1 validation context
→ possible accepted-history admission risk
```

This is a high-risk boundary because an incorrect write-side reconstruction can affect what becomes accepted history.

Therefore, write-side aggregate snapshots require stricter trust rules than read-side projection snapshots.

---

## 4. What Actually Happened

When Stage 3.5D implementation began, the work was intentionally applied to the read side first.

This made sense locally.

The read side already had durable projection state and checkpoint state. Projection snapshots were a safer place to implement the general trust-contract machinery first:

```text
snapshot lineage
source event boundary
source global position
snapshot schema version
reducer version
payload evidence
tail replay continuity
fallback to authority replay
```

The PR sequence developed into:

```text
PR1 — General Snapshot Trust Contract Boundary
PR2 — Projection Snapshot Schema Baseline
PR3 — PostgresProjectionSnapshotStore
PR4 — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
```

This was locally coherent.

PR4 introduced validation / audit evidence.

PR4.5 introduced a read-side resolver that can use trusted snapshot evidence to resolve projection state through:

```text
projection snapshot + tail replay
```

without doing full accepted-history replay on every normal read path.

However, this read-side work did not fully answer the original high-risk write-side concern.

It answered a related but different problem.

---

## 5. Mistaken Model 1: Global Log Cost vs Per-Aggregate Cost

One source of confusion was the cost model.

The original intuition treated write-side rehydration as if it might become expensive because the global event log grows over time:

```text
global_position grows
→ event log becomes large
→ write-side rehydration may need snapshot acceleration
```

But this was not the correct cost model for the current system.

The write side does not rehydrate an order by replaying the whole global event log.

The write side rehydrates an order by loading accepted events for that specific aggregate:

```text
command(order_id)
→ load accepted events for this order_id
→ replay this order's local history
→ validate command
→ create candidate event
→ Compass Layer 1
→ append-time admission
```

Therefore, the relevant cost is not:

```text
length of the global event log
```

The relevant cost is:

```text
event depth of one aggregate
```

In the current project, the order lifecycle is intentionally small:

```text
INIT → CREATED → PAID
```

That means most write-side rehydration paths only replay a few events.

In this project, write-side aggregate snapshot production code is not justified by replay cost yet.

---

## 6. Mistaken Model 2: Read-Side Trust vs Write-Side Admission Trust

A second source of confusion was treating read-side snapshot validation as if it had the same risk level as write-side admission trust.

This is not accurate.

Read-side projection state is derived state.

If read-side state is wrong, the system may show an incorrect view:

```text
wrong projection
wrong dashboard
wrong query result
wrong downstream observation
```

That is still important.

But it usually does not directly pollute accepted history.

The recovery path is usually:

```text
discard derived state
replay accepted history
rebuild projection
```

Write-side aggregate state is different.

If write-side reconstructed state is wrong, it can affect command validation and candidate event generation.

That means write-side snapshot failure can become an admission-path risk.

Therefore:

```text
read-side snapshot trust
= derived-state integrity / replay-efficiency / runtime evidence

write-side snapshot trust
= admission-path safety concern
```

These two concerns share a trust-contract vocabulary, but they should not be treated as the same risk class.

---

## 7. Corrected Interpretation of Read-Side Snapshot Work

The read-side snapshot work remains useful.

It should not be discarded.

However, its meaning should be reframed.

Read-side snapshot validation should be understood as:

```text
derived-state integrity evidence
projection replay-efficiency support
snapshot-assisted resolver evidence
future Compass Layer 2 input
```

It should not be described as directly protecting accepted history.

A projection snapshot can help answer:

```text
Can this read-side state be safely resolved from snapshot + tail replay?
```

It can also help detect:

```text
projection drift
snapshot boundary mismatch
tail discontinuity
schema / reducer incompatibility
payload evidence mismatch
```

These are valuable runtime signals.

But they are not the same as write-side admission safety.

---

## 8. Relationship to Compass Layer 2

The read-side snapshot validator does not replace Compass Layer 2.

It provides evidence for it.

The difference is:

```text
PR4 / PR4.5:
technical evidence about projection snapshot-assisted reconstruction

Compass Layer 2:
semantic runtime decision based on evidence
```

For example, PR4 / PR4.5 can produce or consume evidence such as:

```text
snapshot exists
snapshot boundary is valid
snapshot schema is supported
tail replay is continuous
snapshot-assisted state matches authority replay
snapshot-assisted state drifts from authority replay
```

Compass Layer 2 can later decide:

```text
fallback
quarantine
mark uncertain
reject downstream decision
emit SemanticOutcome
notify operator
prevent agent-visible usage
```

Therefore, read-side snapshot work should be positioned as an evidence mechanism, not as the complete runtime semantic policy.

---

## 9. Corrected PR Direction

The corrected direction is:

```text
PR1 — General Snapshot Trust Contract Boundary
PR2 — Projection Snapshot Schema Baseline
PR3 — PostgresProjectionSnapshotStore
PR4 — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5 — Aggregate Snapshot Trust Boundary and Deferral
```

PR5 should still exist.

But its purpose should change.

Instead of acting as a direct bridge into immediate aggregate snapshot production code, PR5 should record:

```text
why write-side aggregate snapshots are stricter
why the original high-risk concern still matters
why current aggregate event depth does not justify implementation
why read-side projection snapshots cannot be inverted into aggregate state
when future PR6 / PR7 should be revived
```

The previous PR6 / PR7 work should be deferred:

```text
PR6 — Aggregate Snapshot Schema / Store
PR7 — Snapshot-Assisted Write-Side Rehydration
```

These remain valid future optimizations, but they are not necessary for the current project stage.

---

## 10. Why This Is Not a Failure

This is not a failure of the snapshot work.

It is a stage-level correction.

The implemented read-side work is still useful.

The correction is about scope, risk class, and cost-benefit alignment.

The main lesson is:

```text
A technically valid architecture concern does not automatically justify immediate production implementation.
```

A concern can be real in general, while still not being urgent in the current system.

For this project:

```text
write-side aggregate snapshot risk is real
but current aggregate replay depth is too small
so production implementation is deferred
```

At the same time:

```text
read-side snapshot work is useful
but it should be framed as derived-state evidence
not as accepted-history protection
```

---

## 11. AI-Assisted Engineering Lesson

This issue also reveals a broader lesson about AI-assisted development.

A coding agent or assistant can help make every local step more rigorous:

```text
better schema
better tests
better validators
better result models
better documentation
better edge-case coverage
```

But local rigor does not guarantee global alignment.

If the premise is not periodically rechecked, the system can continue to move forward while solving a slightly different problem than the one that originally justified the work.

This is a form of premise drift.

```text
local correctness
does not imply
global premise alignment
```

In agent-assisted engineering, a loop may keep improving the current path unless the harness includes explicit checks such as:

```text
What was the original stage problem?
What problem is the current PR actually solving?
Are they still aligned?
What authority boundary is being protected?
Is this source-of-truth safety, derived-state integrity, or runtime evidence?
What measurable risk justifies the next PR?
Should the next PR proceed, shrink, or defer?
```

Without those checks, an agent loop can produce a sequence of locally correct PRs while the stage-level architectural intent drifts.

---

## 12. Reusable Lesson

For future stages, each major PR sequence should include a premise audit.

A useful audit template is:

```text
1. Original premise:
   Why did this stage exist?

2. Current implementation:
   What are we actually building?

3. Boundary classification:
   Are we protecting source of truth, derived state, runtime evidence, or operator visibility?

4. Cost-benefit check:
   Is the next planned implementation justified by current system risk or cost?

5. Drift check:
   Has the work shifted from the original problem to a related but different problem?

6. Deferral option:
   Should the next PR proceed, shrink, or move to future work?
```

This should be applied especially when a project uses AI assistance heavily.

The goal is not to slow down implementation.

The goal is to prevent a locally coherent loop from silently drifting away from the stage-level reason for existing.

---

## 13. Human Intent Drift vs Agent Objective Drift

In this case, the drift was human intent drift.

I had an original architectural concern: write-side aggregate snapshot trust. But as implementation moved into read-side projection snapshot work, the local PR sequence became coherent enough that the original concern was partially diluted.

For agents, the same outward pattern may appear, but the mechanism is different. An agent does not have intent in the human sense. It follows prompts, tool feedback, tests, and evaluators. When those feedback signals capture only local correctness, the agent may continue optimizing a proxy objective while the global premise drifts.

Therefore, for AI-assisted engineering, the safer term is proxy-objective drift or apparent intent drift.

The practical lesson is the same:

local feedback loops must be paired with periodic premise audits.

---

## 14. Final Decision

Current decision:

```text
read-side projection snapshot work:
keep and complete as derived-state integrity / resolver evidence

write-side aggregate snapshot production code:
defer for now

PR5:
keep as Aggregate Snapshot Trust Boundary and Deferral

PR6 / PR7:
move to future optimization until aggregate replay depth justifies them
```

This preserves the original Snapshot Trust Contract insight while avoiding unnecessary production complexity in the current domain.

The final lesson is:

```text
A green PR sequence does not prove that the stage premise is still aligned.
```

Or, in the language of the project:

```text
agent loop can be green,
but the architectural premise can drift.
```
