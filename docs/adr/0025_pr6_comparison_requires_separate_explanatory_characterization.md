# ADR 0025: PR6 Comparison Requires Separate Explanatory Characterization

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Stage 4B.2 PR6 is complete and remains frozen as the accepted Level-B PostgreSQL
strategy-comparison record.

The post-PR6 explanatory characterization currently has:

```text
Layer 1
= COMPLETE / VALID RECORDED EVIDENCE

Layer 2
= COMPLETE / 270-SAMPLE VALID RECORDED EVIDENCE

Layer 3
= COMPLETE / 60-SAMPLE VALID RECORDED EVIDENCE

Post-PR6 supplemental characterization
= COMPLETE / CLOSED

Counterfactual compositions
= DEFERRED / NOT REQUIRED FOR CLOSEOUT
```

The supplemental work does not reopen or replace PR6.

---

## Decision Scope

This decision governs how Stage 4B.2 interprets an unexpected empirical result
from the completed PR6 PostgreSQL comparison.

It defines why a separate post-PR6 explanatory characterization exists and what
that characterization may investigate.

It does not select a production validation placement, admission strategy,
connection policy, retry policy, or concurrency limit.

## Context

Stage 4B.2 PR6 compared the two current PostgreSQL write-side compositions:

```text
PRE_TRANSACTION
+ optimistic / OCC append-time admission

versus

IN_TRANSACTION
+ concrete PostgreSQL pessimistic admission
```

The comparison was intentionally performed on complete, correctness-preserving
production compositions rather than synthetic isolated functions.

The first accepted-path results showed an initially surprising ordering:

```text
PRE/OCC
= slightly higher observed end-to-end accepted-path latency

IN/pessimistic
= slightly lower observed end-to-end accepted-path latency
```

This result conflicted with a simple expectation that moving validation outside
the write-side business UOW should make the PRE composition appear cheaper.

However, that expectation collapsed several different cost dimensions into one
number.

PR6 changed multiple dimensions at the same time:

```text
validation placement

idempotency lifecycle

application-UOW topology

physical PostgreSQL transaction topology

admission mechanism

early-versus-late rejection behavior
```

Therefore the observed ordering could not establish which mechanism caused the
difference.

In particular:

```text
end-to-end producer latency
!= write-side business-UOW duration

write-side business-UOW duration
!= exact PostgreSQL physical transaction duration

physical transaction duration
!= lock occupancy

client-observed elapsed
!= server-side SQL execution time
```

A faster complete request therefore does not prove that its write-side
transactional region is shorter, and a slower complete request does not prove
that the architecture failed to move expensive work outside that region.

The unexpected PR6 result created a narrower question:

```text
Why is the current PRE/OCC accepted path externally slower,
and where is that additional cost actually paid?
```

Without a separate explanatory investigation, Stage 4B.2 would have had to
either stop at a descriptive ranking or over-interpret PR6 as causal evidence.

## Decision

PR6 remains complete historical Level-B evidence.

```text
PR6 canonical evidence
= preserved

post-PR6 explanatory characterization
= separate supplemental investigation
!= PR6 correction
!= PR6 replacement
!= strategy rerun
```

The unexpected accepted-path latency ordering must not be promoted directly into
an architecture decision.

The post-PR6 supplement instead decomposes current production behavior in three
bounded layers.

### Layer 1 — Production-Path Lifecycle Characterization

Layer 1 characterizes the current A–H production paths:

```text
A
PRE preliminary MISS
→ authoritative MISS
→ ACCEPTED

B
PRE preliminary REPLAY

C
PRE preliminary CONFLICT

D
PRE preliminary MISS
→ authoritative REPLAY

E
PRE preliminary MISS
→ authoritative CONFLICT

F
IN authoritative MISS
→ ACCEPTED

G
IN authoritative REPLAY

H
IN authoritative CONFLICT
```

The purpose is to establish which current operations are reached, which
measurement phases are available, where early termination occurs, and how the
existing transaction lifecycle differs across accepted, replay, and conflict
paths.

Layer 1 does not create a new write algorithm.

### Layer 2 — Exact Idempotency-Check Characterization

Layer 2 isolates the exact current production:

```text
PostgresIdempotencyStore.check(...)
```

under three transaction-lifecycle contexts:

```text
P
= direct check beginning from IDLE

U
= application UOW entered
  while the physical PostgreSQL transaction is still IDLE

T
= application UOW entered
  after one neutral setup statement has already moved the
  physical PostgreSQL transaction to INTRANS
```

Each context is crossed with:

```text
MISS
REPLAY
CONFLICT
```

for exactly nine cells.

The T context is a transaction-lifecycle control.

It is not the current production IN composition and must not be interpreted as
one.

Layer 2 measures the exact production `check()` call and cleanup separately.
It does not copy, rewrite, or replace the production idempotency SQL.

### Layer 3 — Transaction and Cleanup Controls

Layer 3 separately characterizes:

```text
IDLE
→ rollback
```

and the actual PRE preliminary read bundle:

```text
IDLE
→ preliminary idempotency MISS
→ empty accepted-history load
→ rollback
→ IDLE
```

The purpose is to distinguish current lookup cost, read-transaction lifecycle,
and cleanup behavior without inventing one synthetic "database time" value.

### Counterfactual Compositions

Counterfactual compositions are not required for completion.

In particular:

```text
PRE_NO_PRELIMINARY
IN_OCC
```

remain optional.

They must not be introduced merely to make the comparison more symmetrical.

If Layers 1–3 sufficiently explain the observed PR6 behavior, the supplemental
investigation stops.

### Concurrency Ownership

This supplement answers:

```text
Where is the current single-execution cost paid?
```

It does not answer:

```text
How does that resource-placement trade-off behave
as bounded concurrent demand increases?
```

That separate question remains owned by Stage 4B.2 PR7.

## Rationale

PR6 was designed to compare complete production compositions.

That is useful for answering:

```text
What did the current strategies cost in this recorded environment?
```

It is not sufficient for answering:

```text
Which individual mechanism caused the observed difference?
```

Treating the PR6 end-to-end result as causal would conflate multiple changing
axes and could produce a false architecture conclusion.

The supplemental investigation preserves the original empirical result while
using narrower evidence to explain it.

This keeps two responsibilities separate:

```text
comparison
!= explanation
```

It also preserves the distinction between different resource dimensions.

A composition may rationally trade:

```text
slightly higher total request latency

for

a shorter write-side business-UOW interval

or

earlier REPLAY / CONFLICT termination
```

without either observation invalidating the other.

## Current Supporting Evidence

Layer 1 completed one fixed 80-sample recorded run:

```text
planned samples
= 80

observed samples
= 80

validation
= VALID

unexpected exceptions
= 0

connection IDLE / reuse verification
= 80 / 80

durable verification
= 80 / 80
```

For the uncontaminated accepted paths, the local recorded evidence observed:

```text
external latency median

PRE/OCC
≈ 3.315 ms

IN/pessimistic
≈ 3.103 ms
```

while the same run observed:

```text
write-side business-UOW median

PRE/OCC
≈ 1.969 ms

IN/pessimistic
≈ 3.055 ms
```

Therefore:

```text
higher PRE end-to-end latency
did not imply
a longer PRE write-side business UOW
```

This result supports the decision not to treat end-to-end latency ranking as a
complete architecture conclusion.

Layer 1 also showed that preliminary idempotency classification is not pure
overhead.

For already-known request identities, PRE may terminate before entering the
business UOW, while a fresh accepted MISS path pays the preliminary read
lifecycle before proceeding.

These observations are descriptive and environment-qualified.

They do not prove a complete causal decomposition.

Layer 2 completed its fixed 270-sample exact production idempotency-check
factorial: 30 samples in every P/U/T × MISS/REPLAY/CONFLICT cell, validation
`VALID`, no exceptions, reuse 270/270, and final IDLE 270/270. It established
the transaction-lifecycle shape:

```text
P
IDLE → INTRANS → IDLE

U
IDLE → INTRANS → IDLE

T
INTRANS → INTRANS → IDLE
```

across the MISS, REPLAY, and CONFLICT recorded cells.

A separate structural characterization confirmed that every Layer-2 cell emits
one check-attributable production SQL statement with the same normalized
identity.

P versus U check elapsed did not show one stable directional difference
sufficient to attribute the PR6 ordering to application-UOW entry itself. The
already-INTRANS T control had lower check medians than U for all three verdicts
in this recorded environment, but T is not the production IN composition and
does not isolate a universal physical-transaction-start cost.

Layer 3 completed its fixed 60-sample run: 30 IDLE rollback controls and 30
PRE-like preliminary read-lifecycle controls, validation `VALID`, no
exceptions, and all required lifecycle/reuse evidence satisfied. Its recorded
medians were:

```text
IDLE rollback baseline
= 3.167 µs

PRE-like idempotency check
= 719.854 µs

accepted-history load
= 319.1875 µs

active read cleanup
= 214.3335 µs

directly measured preliminary read lifecycle
= 1,263.6255 µs
```

The direct lifecycle was independently timed and is not a sum of the component
medians.

Together, the three layers support a bounded explanation: the current PRE/OCC
accepted path performs an additional durable idempotency lookup,
accepted-history load, and read-transaction cleanup before its business UOW.
Those boundaries have non-negligible client-observed elapsed, while moving
that work and validation outside the write-side application business UOW keeps
PRE's business-UOW interval materially shorter. Slightly higher PRE external
elapsed and shorter PRE business-UOW elapsed are therefore coherent rather
than contradictory observations.

The final values, evidence lineage, limitations, and closeout are recorded in
the [supplemental report](../implementation_notes/stage_4b_2/postgres_idempotency_transaction_lifecycle_report.md).
No concrete contradiction requires another control, so the supplement is
complete and closed. `PRE_NO_PRELIMINARY` and `IN_OCC` are not required for
closeout.

## Alternatives Considered

### Treat the lower PR6 end-to-end latency as the architecture winner

Rejected. PR6 changed multiple dimensions simultaneously and did not isolate
causal ownership of the observed difference.

### Re-run or modify PR6 until the original expectation appears

Rejected. The canonical PR6 evidence is accepted historical evidence. Changing
the workload after observing the result would mix comparison with
outcome-driven experiment redesign.

### Immediately remove the preliminary PRE idempotency check

Rejected. The existing evidence shows that preliminary classification can also
enable early REPLAY and CONFLICT termination. Its cost and benefit must be
characterized before any redesign decision.

### Immediately add IN/OCC for a cleaner factorial comparison

Rejected. Experimental symmetry alone does not justify adding a new composition
to the production-oriented investigation.

### Sum measured phases into one total database-cost number

Rejected. The current phase intervals may overlap and do not represent one
disjoint server-side cost decomposition.

## Consequences

### Positive

- PR6 remains an immutable historical empirical record.
- Unexpected evidence produces a narrower investigation rather than an
  immediate architecture reversal.
- End-to-end latency and write-side business-UOW duration remain separate cost
  dimensions.
- Existing PRE and IN production paths can be explained without first creating
  counterfactual algorithms.
- Preliminary idempotency cost and early-exit value can be evaluated separately.
- PR7 remains free to evaluate bounded concurrency behavior without absorbing
  single-execution causal decomposition.

### Negative

- Stage 4B.2 requires additional experiment code, PostgreSQL runs, and evidence
  review after PR6 itself was already complete.
- Some late REPLAY / CONFLICT outer timing is intentionally unusable because
  deterministic coordination contaminates the external and validation timing
  boundaries.
- The investigation finishes with a bounded mechanism explanation rather than
  one single causal number.

### Neutral but Important

This decision does not require PRE/OCC to become faster than IN/pessimistic.

The purpose is to explain where the current costs are paid and which resource
dimension each composition changes.

A valid outcome may therefore remain:

```text
PRE/OCC
= slightly slower end-to-end

while

PRE/OCC
= shorter write-side business UOW
```

without contradiction.

## Non-Goals

This ADR does not introduce or decide:

- a preferred production validation placement;
- a preferred production admission strategy;
- removal of preliminary idempotency;
- `IN_OCC`;
- `PRE_NO_PRELIMINARY`;
- strategy selection or automatic switching;
- retry or AttemptLog policy;
- connection-pool sizing;
- production concurrency limits;
- rate limiting;
- autoscaling;
- SLOs;
- production capacity or saturation thresholds;
- persistence changes;
- migrations; or
- generic telemetry infrastructure.

## Relationship to Existing Decisions

- ADR 0023 establishes that measurement availability does not govern business
  truth. This ADR preserves the same separation between observed execution cost
  and the producer's business result.
- ADR 0024 establishes detailed PostgreSQL write measurement as an explicit
  capability. PR6 and the supplemental characterization use that capability for
  controlled empirical work without making detailed measurement mandatory for
  every production execution.
- PR6 remains the accepted Level-B complete-composition comparison.
- PR7 owns the separate Level-C bounded concurrency / contention question.

## Current Decision Summary

```text
unexpected PR6 latency ordering
!= architecture winner

PR6 comparison
= preserved historical evidence

post-PR6 supplement
= COMPLETE / CLOSED
  with a bounded explanation of where current cost is paid

Layer 1
= COMPLETE / VALID production-path evidence

Layer 2
= COMPLETE / VALID exact idempotency-check evidence

Layer 3
= COMPLETE / VALID transaction / cleanup controls

counterfactual compositions
= DEFERRED / NOT REQUIRED FOR CLOSEOUT

PR7
= separate bounded-concurrency responsibility
```
