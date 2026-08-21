# Architecture Notes

[← Back to Docs Home](../README.md)

This directory contains subsystem-level architecture notes for **Streaming System + Compass**.

Unlike ADRs, these documents do not primarily record one-time decisions. They
describe the role, boundary, intended evolution, and cross-system context of
major system components.

Use these documents to understand how the system is structured, why each
subsystem exists, and where a local design resembles—but does not reproduce—a
broader infrastructure pattern.

For the current Stage 4B route, read [High-Level Architecture](high_level_architecture.md),
[Projection Pipeline](projection_pipeline.md), [Snapshot Trust Contract](snapshot_trust_contract.md),
then the [Stage 4B closeout](../implementation_notes/stage_4b/stage_4b_closeout.md).
The older Stage 3 and initial global-checkpoint passages remain historical
design context; ADR 0020 owns current projection completeness.

---

## Architecture Document Index

| Document | Purpose |
|---|---|
| [High-Level Architecture](high_level_architecture.md) | Defines the top-level system structure and major layer responsibilities. |
| [Transactional Core](transactional_core.md) | Defines the write-side semantic baseline and transactional flow. |
| [Compass Layers](compass_layers.md) | Defines Compass as layered semantic validation and governance. |
| [Projection Pipeline](projection_pipeline.md) | Defines the evolution from a replay helper to a Stage 3 baseline projection runtime built around reducer, worker, state persistence, and progress advancement. |
| [Persistent Storage Baseline](persistent_storage_baseline.md) | Defines Stage 3.5 as the durable persistence extension of the current in-memory baseline, including write-side-first and read-side-second evolution. |
| [Write-Side Schema Baseline](write_side_schema_baseline.md) | Defines the first durable write-side schema baseline for `order_events` and `idempotency_records`, including semantic fingerprint evolution and transaction grouping rationale. |
| [Read-Side Schema Baseline](read_side_schema_baseline.md) | Defines the initial Stage 3.5C durable read-side schema baseline for `projection_states` and `projection_checkpoints`. Its original global-checkpoint model is historical context for the later per-order repair recorded by ADR 0020. |
| [Aggregate-Local Progress, Partition-Local Logs, and Commit-Consistent Boundaries](aggregate_local_progress_partition_logs_and_commit_boundaries.md) | Compares the repaired per-order PostgreSQL projection with Kafka partition-local offsets and WAL / LSN-based committed observation, including the shared boundary-scoping rule, where the analogy stops, current trade-offs, and future decision triggers. |
| [Snapshot Trust Contract](snapshot_trust_contract.md) | Defines how snapshots can support replay / rehydration efficiency while remaining derived, discardable, and subordinate to accepted history. |
| [Retry Reason Classification](retry_reason_classification.md) | Preserves historical/future candidate taxonomy for retry-like situations and why retry evidence should not live in `idempotency_records`; it is not the accepted first formal Stage 4E contract. |

---

## Recommended Reading Order

1. [High-Level Architecture](high_level_architecture.md)
2. [Transactional Core](transactional_core.md)
3. [Compass Layers](compass_layers.md)
4. [Projection Pipeline](projection_pipeline.md)
5. [Persistent Storage Baseline](persistent_storage_baseline.md)
6. [Write-Side Schema Baseline](write_side_schema_baseline.md)
7. [Read-Side Schema Baseline](read_side_schema_baseline.md)
8. [Aggregate-Local Progress, Partition-Local Logs, and Commit-Consistent Boundaries](aggregate_local_progress_partition_logs_and_commit_boundaries.md)
9. [Snapshot Trust Contract](snapshot_trust_contract.md)
10. [Retry Reason Classification](retry_reason_classification.md)

This order reflects the dependency structure and the later correction of the
original durable read-side progress model:

```text
top-level system structure
→ transactional truth
→ write-side transition-truth validation
→ projected runtime state
→ durable persistence evolution
→ durable write-side schema hardening
→ initial durable read-side schema baseline
→ repaired progress scope and external architecture comparison
→ Snapshot Trust Contract
→ retry / attempt evidence classification
→ later state-level runtime validation
```

---

## Architecture Notes vs ADRs

Architecture notes describe the shape, boundaries, and context of a subsystem.

ADRs explain why a specific repository decision was made.

For example:

- `high_level_architecture.md` explains how the major system layers relate to one another.
- `transactional_core.md` explains what the transactional core is.
- `compass_layers.md` explains what the layered Compass architecture is.
- `projection_pipeline.md` explains how projection evolved into a Stage 3 baseline runtime path.
- `persistent_storage_baseline.md` explains how the project should move from in-memory correctness into durable persistence-backed execution.
- `write_side_schema_baseline.md` explains how the durable write-side schema should be shaped before implementation grows larger.
- `read_side_schema_baseline.md` preserves the initial durable read-side schema and scalar-checkpoint baseline as historical architecture context.
- `aggregate_local_progress_partition_logs_and_commit_boundaries.md` explains how aggregate-local projection progress relates to Kafka partition-local consumption and WAL / LSN committed observation without claiming that the mechanisms are identical.
- `snapshot_trust_contract.md` explains how snapshot-assisted replay and rehydration can be introduced without letting snapshots replace accepted history.
- `retry_reason_classification.md` preserves historical/future candidate distinctions among idempotent replay, concurrency retry, infrastructure retry, semantic conflict, and agent intent drift without promoting them into the first formal Stage 4E profile.
- `adr/0003_concurrency_idempotency_and_retry_safety.md` explains a specific decision inside the transactional write-side path.
- `adr/0004_why_compass_split_into_two_layers.md` explains why Compass evolved from a single runtime-verification idea into two layers.
- `adr/0005_persistent_storage_baseline_strategy.md` explains why Stage 3.5 should prioritize PostgreSQL-backed durable persistence before more advanced runtime concerns.
- `adr/0006_use_decimal_for_money_values_before_durable_persistence.md` explains why exact decimal money representation should be introduced before durable persistence grows larger.
- `adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md` records the accepted decision to preserve globally unique event coordinates while replacing the unsafe global projection-completeness cursor with per-order exact-next progress and order-local snapshot tails.

Both are important, but they answer different questions.

---

## Architecture Documentation Principle

Every architecture note should make these boundaries clear:

- what this subsystem owns
- what this subsystem does not own
- what inputs it consumes
- what outputs it produces
- what invariants it must preserve
- what completeness claims its progress markers can actually prove
- which external architecture comparisons are structural analogies rather than
  identical mechanisms
- what future evolution is expected

A reusable rule for cursor, checkpoint, offset, snapshot, and progress design
is:

> Match durable progress to the narrowest ordering and completeness boundary
> required by the consumer and actually guaranteed by the source.
