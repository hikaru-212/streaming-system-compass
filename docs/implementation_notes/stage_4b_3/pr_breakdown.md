# Stage 4B.3 PR Breakdown

[← Back to Stage 4B.3](README.md)

## Status and Sequencing Rule

This is a planning sequence, not implementation authority. Each PR must remain
within the decisions established by accepted earlier work and must stop when
the next step would require an unresolved semantic or persistence choice.

Concepts such as a validated projection boundary or projection-advance evidence
are responsibility labels in this plan. PR1 does not freeze future class, field,
status, serializer, schema, or table names.

The sequence is evidence-first:

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

Characterization precedes contracts; contracts precede integration; durable
persistence remains conditional on evidence that it is necessary and on a
separately accepted atomicity decision.

## PR1 — Documentation / Responsibility Boundary

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

Purpose: turn the source assumptions that matter to continuation into focused,
executable evidence before immutable contracts are designed.

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

Purpose: evaluate whether a qualified order-local base at sequence `N` can
continue across qualified evidence for the exact-next committed advance at
`N + 1`.

The evaluator must remain pure governance interpretation. It must reject or
leave unresolved missing identity, lineage, state binding, logic qualification,
non-exact-next sequencing, or uncorrelated completion. It does not run the
worker, validate the domain, select an action or strategy, retry, rebuild, or
remediate.

## PR7 — Durable Trust Checkpoint Integration — CONDITIONAL

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

The closeout records:

* implemented responsibility and evidence boundaries;
* accepted architecture decisions and their rationale;
* executable validation results;
* whether conditional PR7 occurred;
* limitations and explicit non-goals;
* deferred work and ownership by later stages.

Stage 4B.3 is not complete merely because types or tables exist. Completion
requires source and executable evidence that the accepted continuation boundary
is implemented without absorbing Stage 4B.5, 4C, 4D, or 4E responsibilities.

## Stage-Wide Exclusions

The sequence does not authorize domain correctness, runtime action or strategy
selection, retry or attempt governance, DiagnosticTrace or measurement-evidence
redesign, snapshot trust redesign, global catch-up, global validated frontiers,
history-completeness proof, trust TTL or lease policy, automatic rebuild,
quarantine, fallback, or remediation.
