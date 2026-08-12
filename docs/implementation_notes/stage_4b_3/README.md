# Stage 4B.3 — Projection Trust Boundary and Continuation

[← Back to Implementation Notes](../README.md)

## Status

Stage 4B.3 is in documentation-first design. PR1 establishes responsibility,
evidence boundaries, limitations, and sequencing. It authorizes no production
code, test, migration, persistence, or runtime-policy change.

The current public documents are:

* [Projection Trust Boundary and Continuation](projection_trust_continuation_boundary.md) — PR1 responsibility authority;
* [PR Breakdown](pr_breakdown.md) — evidence-first delivery sequence.

The responsibility names used by these notes are conceptual. They do not freeze
future class, field, status, serialization, schema, or table names.

## Stage Responsibility

Accepted history is business authority. Projection state is derived mutable
state. Stage 4B.3 asks what evidence would be required to qualify one observed
order-local projection boundary and then evaluate whether trust can continue
across one exact-next committed projection advance.

It does not declare current projection state trusted. It also does not own
domain correctness, freshness policy, runtime action selection, retry,
remediation, snapshot trust, or global catch-up.

## Current Baseline

| Current evidence or identity | Supported meaning | Explicit limit |
| --- | --- | --- |
| `ReplayValidationResult.MATCH` | Point-in-time equality between replay-derived and persisted `OrderState` within one repeatable-read, read-only observation | Not a continuation-capable validated boundary |
| Worker result with `action="applied"` | One exact-next accepted event was reduced and projection state plus per-order progress committed before the result reached the caller | Not continuing trust |
| `order_state_projection`, epoch `1`, and `order_id` | Current durable per-order progress identity | Not complete mutable projection-state identity |
| `projection_epoch = 1` | Repaired per-order progress lineage | Not reducer version |
| `worker_name` | Operational identity | Not durable progress or projection-state identity |
| Projection state plus per-order progress | Current worker-owned atomic unit | No trust checkpoint participates today |

These statements are grounded in the current projection definition, worker,
validator, stores, and migrations. The detailed responsibility authority links
those sources.

## Required Qualification Gap

Neither current result is sufficient continuation evidence:

```text
MATCH
= point-in-time state-consistency observation
!= continuation-capable validated projection boundary

APPLIED
= one committed exact-next projection advance
!= continuing trust
```

A future design must establish how boundary evidence binds accepted-event
lineage, durable progress, the observed projection-state content, source
observation, and projection logic. Sequence or version equality alone is not
sufficient state-content binding.

## Open Architecture Decisions

PR1 deliberately leaves these questions unresolved:

* the representation used to bind projection-state content;
* an authoritative identity for live projection logic;
* how a read-only replay observation can be qualified and later materialized
  without losing its observation boundary;
* whether a future durable trust checkpoint is committed with state and
  progress (Model A) or materialized separately (Model B);
* whether durable trust checkpoints are needed at all after earlier evidence
  work is complete.

Snapshot `payload_hash` and snapshot reducer-version metadata are not selected
as answers. Projection epoch is not reducer version.

## Stage Boundaries

Stage 4B.3 remains distinct from:

* Stage 4B.1 `DiagnosticTrace`;
* Stage 4B.2 measurement evidence;
* Stage 4B.5 Order Correctness Contract;
* Stage 4C runtime decision policy;
* Stage 4D strategy selection;
* Stage 4E retry and attempt governance;
* snapshot trust and global projection catch-up.

No adjacent evidence type becomes trust authority merely because it is durable
or structurally similar.

## Non-Goals

PR1 does not select or create a state hash or fingerprint, reducer-version
representation, trust-checkpoint schema, persistence table, migration,
revalidation cadence, trust TTL, scheduler, production runner, automatic
rebuild, quarantine, fallback, remediation, or runtime action semantics.

## Reusable Principle

> Equality observed once and a committed update observed once are evidence
> about different boundaries. Continuing trust requires explicit qualification
> of both boundaries and of the lineage that connects them.
