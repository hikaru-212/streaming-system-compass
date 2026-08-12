# Stage 4B.3 — Projection Trust Boundary and Continuation Closeout

[← Back to Implementation Notes](../README.md)

## Status

```text
Stage 4B.3
= CLOSED AS NOT CURRENTLY JUSTIFIED
```

The accepted architecture-necessity audit concluded that incremental
projection-trust continuation is not a current runtime correctness requirement.
The canonical decision is
[ADR 0026 — Projection Trust Continuation Is Not Currently Justified](../../adr/0026_projection_trust_continuation_is_not_currently_justified.md).

PR1 and PR2 remain complete historical/reference work. PR3 and later Stage
4B.3 implementation PRs will not proceed. The abandoned PR3 contract proposal
was never accepted, and this closeout adds no production source, tests,
migration, persistence, serializer, trust checkpoint, policy, strategy, or
retry behavior.

The current public documents are:

* [Projection Trust Boundary and Continuation](projection_trust_continuation_boundary.md) — PR1 responsibility authority;
* [PR Breakdown](pr_breakdown.md) — original evidence-first plan plus final delivery disposition;
* [Trust Mechanics Characterization](trust_mechanics_characterization.md) — PR2 executable current-mechanics evidence and limitations;
* [ADR 0026](../../adr/0026_projection_trust_continuation_is_not_currently_justified.md) — canonical closeout decision;
* [目前投影執行期正確性模型（中文說明）](projection_runtime_correctness_model.zh.md) — non-authoritative Chinese companion for maintainers.

The responsibility names used by these notes are conceptual. They do not freeze
future class, field, status, serialization, schema, or table names.

## Investigation Responsibility and Result

Accepted history is business authority. Projection state is derived mutable
state. Stage 4B.3 asked what evidence would be required to qualify one observed
order-local projection boundary and then evaluate whether trust can continue
across one exact-next committed projection advance.

PR1 bounded that question and PR2 characterized the actual mechanics before
implementation. The necessity audit then established that the supported normal
runtime already owns projection correctness through accepted-only exact-next
discovery, the canonical reducer, accepted-event progress lineage, atomic
state/progress persistence, database-role separation, and replay/rebuild.

No current production consumer needs an additional continuation conclusion, so
the stage closes without declaring projection state authoritative or absorbing
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

## Current Correctness Model

The accepted current model is:

```text
accepted order_events
= sole business authority

→ currently visible exact-next event
→ canonical reduce_order_event(...)
→ mutable projection state
+ durable projection_order_progress
→ worker-owned atomic commit

accepted-history replay
→ independent comparison / recovery
```

The write side rehydrates from accepted history and does not use projection
state as command authority. Under the Stage 3.5E role boundary,
`compass_projection_worker` is the intended normal runtime projection-state
writer; application, snapshot, and read-only roles cannot mutate
`projection_states`.

## Why Qualification Does Not Add Required Correctness

The proposed continuation relation was:

```text
previous replay consistency
+ one exact-next committed projection advance
→ continuing qualification
```

The advance is already protected by accepted-event eligibility, exact-next
per-order progress, same-order and exact-next reducer checks, current transition
and amount checks, accepted-event lineage revalidation, and atomic
state/progress commit. Qualification would repackage those guarantees as
additional governance/attestation vocabulary without strengthening the normal
materialization path.

It would also not prevent a privileged actor from changing a mutable projection
row after qualification. A fresh accepted-history replay or separately
justified independent integrity mechanism is still required to detect that
later content drift.

No current production consumer requires the additional vocabulary or takes an
action based on it.

## Delivery Disposition

```text
PR1
= responsibility / problem boundary
= COMPLETE / HISTORICAL REFERENCE

PR2
= executable mechanics characterization
= COMPLETE / HISTORICAL REFERENCE

PR3–PR7
= NOT PROCEEDING
```

The original PR sequence is retained in the
[PR breakdown](pr_breakdown.md) as historical planning context, with explicit
closeout dispositions. It is not an active implementation plan.

## Stage Boundaries

The closed Stage 4B.3 investigation remains distinct from:

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

The closeout does not select or create projection trust evidence contracts, a
state hash or fingerprint, reducer-version representation, trust checkpoint,
persistence table, migration, serializer, revalidation cadence, trust TTL,
scheduler, production runner, automatic rebuild, quarantine, fallback,
remediation, policy, strategy, retry behavior, or runtime action semantics.

## Re-entry Conditions

Projection trust continuation may be reconsidered only when a concrete consumer
can identify:

1. who consumes qualification;
2. what action depends on it;
3. which correctness property existing reducer, progress, lineage, permission,
   and transaction guarantees cannot provide;
4. why replay/rebuild is insufficient or too expensive;
5. restart and durability requirements;
6. how accepted history remains sole business authority;
7. how qualification avoids becoming a secondary business authority.

## Reusable Principle

> Additional qualification machinery is justified only when a concrete
> consumer needs evidence beyond accepted-history authority, producer
> invariants, durable processing lineage, atomic persistence, and replay-based
> recovery.
