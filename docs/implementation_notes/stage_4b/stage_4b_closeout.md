# Stage 4B — DecisionReceipt Closeout

[← Back to Stage 4B](README.md)

## 1. Purpose

This note closes Stage 4B and records the final implemented architecture,
invariants, evidence boundaries, validation map, non-goals, and roadmap
transition. It is the completion record; the canonical cross-stage receipt
boundary remains the [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md).

## 2. Completion Statement

Stage 4B PR1–PR7 are complete. Stage 4B owns the `DecisionReceipt` boundary and
contract, generic and producer-specific mapping, tri-state flag boundary,
strict version-1 serialization, storage-neutral persistence envelopes,
migration 007, and caller-transaction-owned PostgreSQL persistence.

The completed architecture is explicit rather than automatic:

```text
technical producer result
→ SemanticOutcome
→ DecisionReceipt
→ strict serializer v1
→ explicit caller-owned persistence boundary
```

No mapper automatically invokes the store, and accepted history is not scanned
or reconciled into receipts.

## 3. Delivery Map

| Delivery unit | Completed responsibility | Primary record |
|---|---|---|
| PR1 | DecisionReceipt governance-evidence boundary | [PR1 design record](pr1_decision_receipt_boundary_design.md), [ADR 0016](../../adr/0016_decision_receipt_is_governance_evidence.md) |
| PR2 | Typed receipt, supporting contracts, JSON-safe evidence | [DecisionReceipt Runtime Contract](decision_receipt_contract.md) |
| Read-Side Canonical Context Interlude | Producer-owned read-side identity and lineage protection | [Stage 4B PR Breakdown](pr_breakdown.md) |
| PR3 | Generic `SemanticOutcome → DecisionReceipt` construction | [SemanticOutcome to DecisionReceipt](semantic_outcome_to_decision_receipt.md) |
| Flag Evaluation State Interlude | `TRUE`, `FALSE`, and `NOT_EVALUATED`; no producer evaluation authority | [Flag Evaluation State](decision_receipt_flag_evaluation_state.md), [ADR 0018](../../adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md) |
| PR4 | PostgreSQL write-side result mapping and admission fate | [Write-Side DecisionReceipt Mapping](write_side_decision_receipt_mapping.md) |
| PR5 | Read-side replay, snapshot-trust, and snapshot-assisted mapping | [Read-Side / Snapshot Mapping](read_side_snapshot_decision_receipt_mapping.md) |
| PR6 | Serializer v1, persistence envelopes, migration, PostgreSQL store | [Persistence Design](pr6_decision_receipt_persistence_design.md), [Durable Persistence](decision_receipt_persistence.md) |
| PR7 | Documentation ownership, current-state alignment, non-goals, transition | This closeout note |

## 4. Production Source Map

| Boundary | Production source |
|---|---|
| Semantic interpretation contract | `src/compass/runtime/semantic_outcome.py` |
| JSON-safe evidence helpers | `src/compass/runtime/json_types.py` |
| DecisionReceipt contract and supporting enums | `src/compass/runtime/decision_receipt.py` |
| Generic mapper | `src/compass/runtime/decision_receipt_mapping.py` |
| Write-side producer mapper | `src/compass/runtime/write_side_decision_receipt_mapping.py` |
| Read-side / snapshot producer mappers | `src/compass/runtime/read_side_decision_receipt_mapping.py` |
| Strict serializer v1 | `src/compass/runtime/decision_receipt_serialization.py` |
| Storage-neutral persistence envelopes | `src/storage/decision_receipt_store.py` |
| PostgreSQL receipt store | `src/storage/postgres_decision_receipt_store.py` |
| Durable schema | `db/migrations/007_create_decision_receipts.sql` |

Core contracts and the generic mapper are exported through
`src.compass.runtime`. Producer mappers, serializer v1, and storage contracts
are imported from their owning modules; Stage 4B does not add root exports only
for symmetry.

## 5. Contract and Mapping Invariants

- The complete `SemanticOutcome` tuple is preserved without reinterpretation.
- Receipt identity and evidence source are explicit inputs.
- Open-ended `SemanticOutcome.context` and `.evidence` are not copied.
- Flexible evidence is validated as bounded JSON-safe data and recursively frozen.
- Producer mappers validate typed result shapes and fail closed on contradictions.
- Mapping performs no persistence, policy evaluation, recovery, retry, or action.

## 6. Identity, Evidence-Source, and Admission Boundaries

Evidence path, identity provenance, and event admission fate are separate axes
under [ADR 0017](../../adr/0017_separate_evidence_path_identity_provenance_and_admission_fate.md).
Candidate identity does not prove accepted-history membership. Accepted-event
identity is present only where the typed producer evidence supports it.
Contradictory protected identity refuses normal receipt construction.

## 7. Flag-Evaluation Boundary

Every producer-created receipt uses:

```text
fallback_required = NOT_EVALUATED
rebuild_required = NOT_EVALUATED
operator_review_required = NOT_EVALUATED
retry_candidate = NOT_EVALUATED
```

`FALSE` means an authorized evaluator completed a negative evaluation; it is
not an omission default. Stage 4B has no authorized flag evaluator. Serializer
v1 and persistence preserve the tri-state values without changing them.

## 8. Serialization and Persistence Boundary

Serializer v1 owns one exact portable payload and rejects unknown, missing,
malformed, non-finite, or out-of-range values. Persistence envelopes keep
semantic receipt data separate from row materialization provenance and
database-generated time.

The PostgreSQL store inserts and loads receipts through an existing connection.
It does not map producer results, choose receipt identity, serialize arbitrary
objects, reconcile accepted history, or acknowledge a later transaction
commit.

## 9. Transaction, Concurrency, and Permission Boundary

The caller owns transaction start, commit, and rollback. Insert results are
statement-level observations inside that transaction. Identical duplicate
receipts are idempotent; conflicting content for the same receipt identity
fails closed; and conflicting reuse of an admitted-producer identity for an
accepted event fails closed. Schema constraints and runtime-role permissions
protect the durable boundary. Stage 4B does not define connection-pool policy,
deadlock recovery, or bounded liveness.

## 10. Projection and Snapshot Dependencies

Accepted history remains authority. Projection state and snapshots remain
derived evidence. Under [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md),
projection completeness uses exact-next per-order progress and snapshot tails
use contiguous order-local sequence. `global_position` remains lineage and
deterministic scheduling evidence, not a global completeness cursor.

PR5 maps point-in-time replay and snapshot results. A receipt does not grant
continuing snapshot trust, repair a projection, rebuild state, or authorize
fallback.

## 11. Validation-Evidence Map

The following files preserve scoped historical verification from the PRs that
introduced each boundary; PR7 does not claim a fresh aggregate test count:

| Boundary | Focused evidence |
|---|---|
| SemanticOutcome and DecisionReceipt contracts | `tests/unit/compass/runtime/test_semantic_outcome.py`, `tests/unit/compass/runtime/test_decision_receipt.py` |
| Generic mapper | `tests/unit/compass/runtime/test_decision_receipt_mapping.py` |
| Write-side mapper and mapper-produced round trips | `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py` |
| Read-side / snapshot mappers and mapper-produced round trips | `tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py` |
| Strict serialization | `tests/unit/compass/runtime/test_decision_receipt_serialization.py` |
| Storage-neutral envelopes | `tests/unit/storage/test_decision_receipt_store.py` |
| Migration and schema constraints | `tests/integration/storage/test_decision_receipt_schema_constraints.py` |
| PostgreSQL insert/load, transaction ownership, concurrency, and isolation | `tests/integration/storage/test_postgres_decision_receipt_store.py` |
| Runtime-role permissions | `tests/integration/security/test_decision_receipt_permissions.py` |

The projection-progress and snapshot dependencies have their own focused unit,
integration, schema, and permission coverage. Those tests validate upstream
read-side correctness; they are not counted as Stage 4B receipt tests.

## 12. Documentation Ownership

- ADRs own why an architectural decision was selected.
- `docs/boundary_notes/decision_receipt_boundary.md` owns current canonical cross-stage receipt behavior.
- PR-specific implementation notes preserve design, implementation, and scoped validation history.
- Roadmaps own sequencing and deferred work.
- This closeout note owns final Stage 4B completion, invariants, non-goals, and transition.

The renamed PR1 boundary note is intentionally historical and does not require
synchronized maintenance with the canonical boundary note.

## 13. Known Limitations

- No automatic mapper-to-store orchestration exists.
- No accepted-history receipt reconciliation exists.
- No publication outbox or publication cursor exists.
- Materialization provenance includes future reconciliation vocabulary but does not implement it.
- Producer flags remain unevaluated.
- Receipt persistence does not prove transaction commit outside the caller boundary.
- Projection execution remains single-active-worker for the supported definition and epoch.
- The orphan-projection vocabulary gap remains deferred post-Stage-4B hardening.

## 14. Final Non-Goals

Stage 4B does not implement DiagnosticTrace, ResolutionTrace, measurement
matrices, cost policy, domain policy, runtime decisions, strategy selection,
retry governance, automatic materialization, accepted-history reconciliation,
outbox publication, a publication cursor, multi-worker projection,
observability infrastructure, production deployment, connection-pool policy,
bounded liveness, deadlock handling, fallback, rebuild, quarantine, operator
workflow, or action execution.

## 15. Follow-Up Stages

```text
Stage 4B.1 = DiagnosticTrace / ResolutionTrace
Stage 4B.2 = Measurement Matrix / Cost Evidence
Stage 4B.5 = Order Domain Policy Contract
Stage 4C   = RuntimeDecisionPolicy
Stage 4C.5 = Layer 1 / Layer 2 Outcome Alignment
Stage 4D   = StrategySelector / Fast-Path Health
Stage 4E   = RetryGovernance / Attempt Classification
```

Action safety and execution remain later than these Stage 4 governance layers.

## 16. Roadmap Transition

Stage 4B is closed after PR7. Roadmaps and indexes should now identify Stage
4B.1 as the next stage while preserving PR1–PR6 implementation notes as
historical delivery records. Deferred semantic hardening and production
hardening remain backlog items rather than hidden Stage 4B scope.
