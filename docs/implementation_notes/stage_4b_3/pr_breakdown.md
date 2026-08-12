# Stage 4B.3 PR Breakdown

[← Back to Stage 4B.3](README.md)

## Status and Sequencing Rule

```text
Stage 4B.3
= CLOSED AS NOT CURRENTLY JUSTIFIED
```

The canonical closeout decision is
[ADR 0026 — Projection Trust Continuation Is Not Currently Justified](../../adr/0026_projection_trust_continuation_is_not_currently_justified.md).

This file preserves the original evidence-first planning sequence as historical
context. It is no longer an active implementation plan. PR1 and PR2 completed
the investigation needed to decide necessity; PR3 and later Stage 4B.3
implementation PRs are not proceeding.

Concepts such as a validated projection boundary or projection-advance evidence
are responsibility labels in this plan. PR1 does not freeze future class, field,
status, serializer, schema, or table names.

The original sequence was:

```text
PR1  documentation / responsibility boundary
PR2  trust-mechanics characterization
PR3  immutable projection trust evidence contracts
PR4  base observation qualification
PR5  projection advance evidence integration
PR6  trust continuation evaluator
PR7  durable trust checkpoint integration — CONDITIONAL
final Stage 4B.3 closeout
```

Characterization preceded the necessity decision. That evidence established
that contracts and later integration are not currently justified, so the
sequence stops after PR2.

## PR1 — Documentation / Responsibility Boundary

Disposition: **COMPLETE / RETAINED AS HISTORICAL REFERENCE**.

Purpose:

* establish the exact current meanings of replay `MATCH` and worker `APPLIED`;
* establish the current projection identity and transaction boundary;
* make the missing qualification evidence explicit;
* record unresolved choices and non-goals;
* align current-authority projection documentation.

Deliverables are limited to this Stage 4B.3 index, the responsibility authority,
the PR sequence, and narrow current-authority documentation corrections.

PR1 must not create code, tests, migrations, schemas, persistence, or runtime
behavior. It must not choose state-binding, live-logic identity, or checkpoint
atomicity representations.

## PR2 — Trust-Mechanics Characterization

Disposition: **COMPLETE / RETAINED AS HISTORICAL REFERENCE**.

Purpose: turn the source assumptions that matter to continuation into focused,
executable evidence before immutable contracts are designed.

Status: focused characterization tests are implemented for replay `MATCH`
without repaired progress, repeatable-read observation stability, independent
same-version projection-state mutation, state-ahead sequence failure,
commit-correlated worker delivery, and continuation under a replacement worker
name. Human execution of the real-PostgreSQL scenarios remains pending. See
[Trust Mechanics Characterization](trust_mechanics_characterization.md).

Characterization should cover only mechanics required by the PR1 boundary,
including:

* replay-observation consistency and what lineage is visible in that
  observation;
* caller-visible worker completion relative to transaction commit and rollback;
* exact-next progress and accepted-event lineage behavior;
* independently mutable state/progress behavior relevant to state binding;
* the observation/materialization race that a later design must address.

PR2 does not define trust contracts, select representations, or add durable
trust state.

## PR3 — Immutable Projection Trust Evidence Contracts

Disposition: **NOT PROCEEDING**.

The abandoned PR3 WIP was never accepted. No contract implementation is part of
the Stage 4B.3 closeout.

Purpose: define the smallest producer-specific immutable evidence contracts
justified by PR1 and PR2.

The contracts must keep these concerns distinct:

* point-in-time replay observation;
* qualification of an order-local base boundary;
* one committed exact-next projection advance;
* evaluation of continuation.

They must make missing or unqualified evidence representable without implying
trust. Exact names and field representations are decisions for this PR, not PR1.
No PostgreSQL table, migration, runtime policy, or durable checkpoint belongs in
PR3.

## PR4 — Base Observation Qualification

Disposition: **NOT PROCEEDING**.

Purpose: qualify a replay observation as a continuation-capable order-local base
only when the required identity, accepted-event lineage, progress qualification,
state-content binding, source observation, and applicable logic qualification
are established.

PR4 must preserve:

```text
raw MATCH
!= qualified base boundary
```

It must explicitly address the read-only observation/materialization gap. It
must not silently convert a later read into evidence about the original
repeatable-read observation. Durable checkpoint persistence remains out of scope
unless separately authorized after the atomicity decision.

## PR5 — Projection Advance Evidence Integration

Disposition: **NOT PROCEEDING**.

Purpose: produce or qualify the evidence needed to describe one worker-owned,
exact-next committed projection step.

The integration must be grounded in the current state-plus-progress transaction
and accepted-event lineage. It must not infer continuing trust from the current
human-readable worker result alone. Evidence that is absent today—including
prior boundary binding, state-content bindings, durable progress identity, and
applicable live-logic identity—must be supplied or explicitly remain
unqualified.

PR5 does not establish global catch-up, freshness, domain correctness, or
runtime action authority.

## PR6 — Trust Continuation Evaluator

Disposition: **NOT PROCEEDING**.

Purpose: evaluate whether a qualified order-local base at sequence `N` can
continue across qualified evidence for the exact-next committed advance at
`N + 1`.

The evaluator must remain pure governance interpretation. It must reject or
leave unresolved missing identity, lineage, state binding, logic qualification,
non-exact-next sequencing, or uncorrelated completion. It does not run the
worker, validate the domain, select an action or strategy, retry, rebuild, or
remediate.

## PR7 — Durable Trust Checkpoint Integration — CONDITIONAL

Disposition: **NOT PROCEEDING**.

PR7 exists only if earlier PRs demonstrate that a reusable durable checkpoint
is required and repository authority separately resolves its atomicity and
materialization model.

Before PR7 begins, the following must be accepted:

* whether Model A or Model B owns checkpoint materialization;
* the state-content and live-logic qualification representations;
* rollback, crash-gap, race, stale-checkpoint, and reconciliation semantics;
* the minimum durable identity and evidence contract;
* whether a migration and new persistence surface are justified.

PR7 must not be used to decide those questions implicitly through schema design.
If durable materialization is unnecessary, PR7 is omitted and closeout records
that conclusion.

## Final PR — Stage 4B.3 Closeout

Disposition: **THIS DOCUMENTATION-ONLY CLOSEOUT**.

The closeout records:

* PR1 responsibility and problem-boundary work as complete reference material;
* PR2 executable mechanics characterization as complete reference material;
* the current accepted-history, reducer, progress, transaction, permission, and
  replay correctness model;
* that no current consumer or missing runtime correctness property justifies
  incremental qualification;
* PR3–PR7 as not proceeding;
* explicit re-entry conditions for any future reconsideration.

No Stage 4B.3 type, table, evaluator, producer integration, or persistence
surface is implemented. Stage 4B.5, 4C, 4D, and 4E remain separately owned.

## Stage-Wide Exclusions

The sequence does not authorize domain correctness, runtime action or strategy
selection, retry or attempt governance, DiagnosticTrace or measurement-evidence
redesign, snapshot trust redesign, global catch-up, global validated frontiers,
history-completeness proof, trust TTL or lease policy, automatic rebuild,
quarantine, fallback, or remediation.
