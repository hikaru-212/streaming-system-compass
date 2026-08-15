# Durable History and Permission Documentation Index

[← Back to Topic_Indexes Index](README.md)

## How to Use This Index

This is topic-based navigation across the reviewed Durable History and Permission documents. Existing `docs/` folders remain the source of each document's role and chronology. A document appears under multiple topics only when it makes a substantial contribution to each.

Permission enforcement protects durable artifacts but does not define their business meaning. Database roles are runtime responsibility identities, not business actors. Actor metadata is not authentication, authorization, or a DecisionReceipt. Later completed boundaries govern current interpretation when older planning documents retain stale status wording. Reasoning notes preserve derivations; postmortems reconstruct concrete episodes. Neither is a current contract by itself.

This index does not override ADRs, boundary notes, implementation records, or stage closeout documents, and it is not a source of architectural, security, identity, or governance authority.

## Durable History and Permission Reading Path

| Order | Document | Role | Why read here |
|---:|---|---|---|
| 1 | [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Start with the completed durable-history and permission-hardening baseline and its explicit limitations. |
| 2 | [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Establish why accepted history, idempotency evidence, projections, per-order progress, retained checkpoints, and snapshots require different mutation postures. |
| 3 | [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Translate the authority model into the current PostgreSQL responsibility-role and table-privilege matrix. |
| 4 | [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Understand why Stage 3.5E uses test-owner `SET ROLE` probes without claiming production identity wiring. |
| 5 | [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Separate mechanism, permission, and future governance-flow tests. |
| 6 | [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Inspect the completed projection, per-order progress, checkpoint, and snapshot privilege probes. |
| 7 | [Minimal Actor Metadata Boundary](../../boundary_notes/minimal_actor_metadata_boundary.md) | Boundary note | Separate database permission identity, producer metadata, and governance decision evidence. |
| 8 | [PR5 Minimal Actor Metadata implementation note](../../implementation_notes/stage_3_5e/minimal_actor_metadata_boundary.md) | Design/implementation note | Read the documentation-first PR5 decision and its explicit non-goals. |
| 9 | [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Review delivery chronology after the completed boundaries; its PR5 `Planned` label is stale historical wording. |
| 10 | [From Git Sync to Database Immutability](../../reasoning_notes/from_git_sync_to_db_immutability.md) | Reasoning note | Trace why in-memory immutability must be re-expressed at the database boundary. |
| 11 | [From Local PostgreSQL to Defense in Depth](../../reasoning_notes/from_local_postgres_to_defense_in_depth.md) | Reasoning note | Place least privilege among distinct configuration, schema, validation, and transaction boundaries. |
| 12 | [From Row-count Assertions to Evidence Assertions](../../postmortems/from_row_count_assertions_to_evidence_assertions.md) | Postmortem | See why exact returned evidence can reveal adapter and type drift hidden by row counts. |
| 13 | [From Protocol Satisfaction to Production Wiring Proof](../../postmortems/from_protocol_satisfaction_to_production_wiring_proof.md) | Postmortem | Preserve the distinction between bounded component proof and real adapter/assembly proof. |
| 14 | [From Runtime Behavior to Durable Evidence](../../reasoning_notes/from_runtime_behavior_to_durable_evidence.md) | Reasoning note | Understand why transient decisions are not durable governance evidence unless explicitly preserved. |
| 15 | [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md) | Canonical boundary note | Separate current governance evidence from accepted history, idempotency evidence, and business authority. |
| 16 | [DecisionReceipt Durable Persistence](../../implementation_notes/stage_4b/decision_receipt_persistence.md) | Implementation boundary | Learn the explicit storage-neutral and caller-owned PostgreSQL persistence contract. |
| 17 | [DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary](../../boundary_notes/decision_receipt_postgres_transaction_safety_and_liveness_boundary.md) | Specialized boundary note | Read the current backend-specific safety, transaction-ownership, and conditional-progress boundary. |
| 18 | [From Statement Success to Owner-Liveness](../../reasoning_notes/from_statement_success_to_owner_liveness.md) | Reasoning note | Follow the derivation from statement success to the missing owner-resolution premise. |

## Overview and Responsibility Map

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Start here | Summarizes the completed database-role, permission-test, actor-metadata, and closeout scope. | Navigation and maturity statement, not semantic authority. |
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Core | Defines mutation posture according to artifact authority and operational role. | Stage 3.5E PR1 conceptual boundary. |
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Core | Defines the current responsibility roles, artifact access, and sequence privileges. | Implemented PR2 baseline. |
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Core | Defines how mechanism, permission, and governance tests make different claims. | Current testing boundary; complete policy/action governance-flow proof remains future work. |
| [Minimal Actor Metadata Boundary](../../boundary_notes/minimal_actor_metadata_boundary.md) | Boundary note | Core | Prevents role identity, producer metadata, and decision evidence from being collapsed. | PR5 reusable conceptual boundary. |
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Records the PR1–PR6 delivery sequence. | Contains stale PR5 status wording; later closeout governs current interpretation. |

## Accepted-history Protection

Accepted event history is authoritative for admitted facts. Normal runtime roles may append through the controlled Write-side path where granted, but they may not arbitrarily update or delete accepted history. Database privilege does not establish semantic admission.

Normal runtime roles cannot rewrite accepted history. Emergency administrative repair, restoration, approval, and audit policy are not defined by Stage 3.5E. A high-privilege migration or test owner must not be presented as an already-defined production repair authority.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Start here | Defines accepted history as authority and distinguishes permission hardening from semantic admission and transaction atomicity. | PR1 boundary. |
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Core | Grants the app writer append access while withholding normal-runtime history update/delete authority. | Implemented PR2 baseline. |
| [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Core | Defines how the effective history privileges of each responsibility role are tested. | Accepted testing-scope decision. |
| [From Git Sync to Database Immutability](../../reasoning_notes/from_git_sync_to_db_immutability.md) | Reasoning note | Historical/supporting | Explains why Python immutability and append discipline do not automatically protect PostgreSQL rows. | Non-authoritative Stage 3.5B derivation, not the current role matrix. |

## Successful Idempotency Evidence

Successful `idempotency_records` entries are durable request-to-accepted-effect evidence. They are not complete retry-attempt history, rejected-candidate evidence, `SemanticOutcome`, DecisionReceipt, or business truth by themselves. Their transaction coupling with accepted-event append does not make the two artifacts semantically equivalent.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Start here | Defines successful idempotency records as insert-once, rewrite-restricted request-effect evidence. | Current successful-only schema interpretation. |
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Core | Grants app-writer read/insert access and withholds normal-runtime update/delete access. | Implemented PR2 baseline. |
| [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Core | Records PR3 verification and distinguishes current successful mappings from future attempt/governance records. | Completed stage summary. |
| [From Runtime Behavior to Durable Evidence](../../reasoning_notes/from_runtime_behavior_to_durable_evidence.md) | Reasoning note | Historical/supporting | Explains why runtime replay/conflict/block behavior is not preserved merely because the successful mapping is durable. | Non-authoritative evidence-model derivation. |

## DecisionReceipt Persistence and Transaction Ownership

Stage 3.5 durable history and permissions protect accepted events, idempotency evidence, and derived artifacts. Completed Stage 4B adds a separate `DecisionReceipt` governance-evidence boundary. Its mappings do not automatically invoke persistence. The PostgreSQL store uses an injected connection with autocommit disabled, and the caller owns commit and rollback; an `INSERTED` result is a statement-level observation, not proof of durability or external visibility.

The specialized transaction boundary establishes conflicting-receipt safety and conditional progress for tested owner commit, rollback, and connection-close schedules. It does not establish bounded abnormal-path liveness, a universal timeout, connection-pool cleanup, or deadlock recovery. The owner-liveness note preserves the derivation rather than owning current behavior.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md) | Canonical boundary note | Start here | Owns the current cross-stage receipt responsibility and non-goals. | DecisionReceipt remains distinct from accepted history and business authority. |
| [DecisionReceipt Durable Persistence](../../implementation_notes/stage_4b/decision_receipt_persistence.md) | Implementation boundary | Core | Defines strict serialization, persistence envelopes, explicit insert/load, and caller-owned transaction completion. | Completed Stage 4B PR6; no automatic materialization. |
| [DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary](../../boundary_notes/decision_receipt_postgres_transaction_safety_and_liveness_boundary.md) | Specialized boundary note | Deep dive | Defines current PostgreSQL safety, tested conditional-progress paths, and explicit liveness non-guarantees. | No bounded owner liveness, timeout policy, pool cleanup, or deadlock recovery. |
| [From Statement Success to Owner-Liveness](../../reasoning_notes/from_statement_success_to_owner_liveness.md) | Reasoning note | Historical/supporting | Derives the owner-resolution premise from statement success, transaction visibility, and uniqueness-conflicting waiters. | Non-authoritative; current facts belong to the specialized boundary and PR6 record. |

## Runtime Database Roles

The current roles express runtime or test responsibilities, not human, user, or business-actor identities:

- `compass_migration_owner` represents high-privilege schema and migration responsibility and is not a normal runtime role.
- `compass_user` / test owner provides setup, cleanup, fixture, migration, and ordinary mechanism-test authority; its privileges are not runtime-role proof.
- `compass_app_writer` may read and append accepted events, read and insert successful idempotency evidence, and consume the accepted-event sequence; it may not rewrite history or receipts or access derived tables by default.
- `compass_projection_worker` may read accepted history, mutate projection state and retained checkpoints, select/insert/update—but not delete—`projection_order_progress`, and read snapshots; it may not mutate history, receipts, or snapshots or consume the accepted-event sequence.
- `compass_snapshot_worker` may read accepted history, `projection_order_progress`, and required derived artifacts and may insert snapshots; it may not rewrite history, mutate projections/per-order progress/checkpoints, or update/delete snapshots.
- `compass_readonly` may observe allowed durable state but may not mutate it.

Readonly access may observe sequence state where explicitly granted, but it cannot consume or advance the accepted-event sequence. Sequence consumption remains reserved for the app-writer responsibility. Sequence `SELECT` must not be read as `nextval` authority.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Start here | Defines all current responsibility roles and their table/sequence privileges. | Implemented PR2 baseline. |
| [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Core | Summarizes the role migration and PR3/PR4 verification. | Completed stage summary. |
| [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Core | Clarifies that activated database roles are responsibility boundaries rather than production login identities. | Accepted testing-scope decision. |
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves the implemented role matrix and sequence-access chronology. | Read with the later baseline and closeout documents. |

## Permission Probing with SET ROLE

ADR 0015 governs the current probe mechanism. `SET ROLE` verifies effective PostgreSQL privileges for an activated responsibility role inside a controlled test context. A typical probe uses test-owner setup, activates one role, attempts an allowed or forbidden operation, asserts the evidence or permission rejection, resets role state, rolls back, and cleans up under test-owner authority.

It does not prove separate production login users, role-specific DSNs or connection pools, credential rotation, secret management, pooled-session role isolation, deployed service wiring, or business authorization.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Start here | Defines test-owner `SET ROLE` as the accepted Stage 3.5E mechanism and explicitly limits its proof claim. | Accepted and implemented for permission testing. |
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Core | Defines setup, role activation, allowed/denied operation, reset/rollback, and cleanup responsibilities. | Current permission-testing boundary. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Records the shared probe fixture and completed PR4 matrix. | Baseline isolated permission tests, not production simulation. |
| [From Protocol Satisfaction to Production Wiring Proof](../../postmortems/from_protocol_satisfaction_to_production_wiring_proof.md) | Postmortem | Historical/supporting | Warns that a bounded test or interface proof does not demonstrate real production assembly. | Historical reusable testing lesson. |

## Derived-state Mutation Boundaries

Projection state, `projection_order_progress`, retained `projection_checkpoints`, and projection snapshots are derived. `projection_order_progress` is current exact-next per-order completeness evidence under ADR 0020; `projection_checkpoints` are legacy/generic operational metadata, not the current worker completeness model. Rebuildability does not imply unrestricted mutation by any runtime role. Projection workers control projection-state/checkpoint mutation and may select/insert/update—but not delete—per-order progress. Snapshot workers may insert snapshots but do not normally rewrite or delete them. Broader cleanup, retention, quarantine, replacement, or rebuild authority remains separately undefined.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Start here | Defines derived-state mutability without transferring accepted authority. | PR1 conceptual boundary. |
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Core | Assigns table-specific derived-state privileges, including per-order progress, to projection, snapshot, and readonly responsibilities. | Implemented PR2 baseline with the ADR 0020 extension. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Records the completed PostgreSQL probes for projection state, per-order progress, checkpoints, and snapshots. | Completed baseline with the ADR 0020 progress probes. |
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Core | Separates storage cleanup capability from normal runtime authority to invoke it. | Maintenance/governance authority remains future work. |

## Projection, Progress, and Checkpoint Permissions

The projection worker may `SELECT`, `INSERT`, `UPDATE`, and `DELETE` projection state and retained checkpoints through controlled projection and rebuild flows. For `projection_order_progress`, it may `SELECT`, `INSERT`, and `UPDATE` but not `DELETE`; snapshot and readonly roles may `SELECT` it, while the app writer has no access. `projection_order_progress` is current per-order completeness evidence under ADR 0020. `projection_checkpoints` are retained legacy/generic operational metadata, not the current worker completeness model. Neither artifact proves semantic correctness.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Start here | Defines the projection/progress/checkpoint privilege matrix and recovery rationale. | Implemented PR2 baseline with the ADR 0020 progress extension. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Records allowed and rejected operations for every tested role. | Completed PR4 permission-test evidence. |
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Core | Explains why controlled mutability is necessary while command admission remains grounded in accepted history. | PR1 boundary. |
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves the PR4 implementation sequence and exact matrix. | Historical delivery record. |

## Snapshot Permissions

Projection snapshots are derived evidence. The snapshot worker may read and insert snapshot artifacts, while normal runtime roles may not rewrite or delete them. Snapshot existence, producer metadata, or successful insertion does not establish snapshot trust or runtime eligibility.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Start here | Defines snapshot-worker insertion and normal-runtime rewrite/delete restrictions. | Implemented PR2 baseline. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Verifies the role-specific snapshot privilege matrix. | Completed PR4 baseline. |
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Core | Separates storage cleanup helpers from normal snapshot-production authority. | Retention, reset, and repair authority remain undefined. |
| [From Row-count Assertions to Evidence Assertions](../../postmortems/from_row_count_assertions_to_evidence_assertions.md) | Postmortem | Historical/supporting | Records the UUID evidence mismatch exposed by exact snapshot permission assertions. | Historical PR4 testing lesson. |

## Layered Permission and Governance Testing

Keep these proof layers separate:

1. deterministic/unit tests prove component logic against controlled inputs or fakes;
2. store/mechanism integration tests prove storage and runtime mechanisms, often under test-owner authority;
3. permission-boundary tests prove effective PostgreSQL privileges for activated responsibility roles;
4. adapter tests prove real dependency implementations;
5. production-path/wiring tests prove real adapters assemble and execute together;
6. later governance-flow tests must prove semantic evidence and decisions across participating roles.

Permission tests prove only their bounded PostgreSQL privilege claims. Where returned identity, row shape, or driver type forms part of the proof, exact evidence assertions are stronger than row-count-only assertions. Protocol satisfaction and isolated permission probes do not prove production wiring.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Start here | Defines mechanism, permission, and later governance-flow test layers. | Current Stage 3.5E testing boundary; Stage 4B receipts do not complete policy/action governance flow. |
| [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Core | Bounds the permission-probe claim and defers production identity topology. | Accepted testing-scope decision. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Shows the completed isolated permission-test implementation and explicit chaos-test deferrals. | Completed PR4 baseline. |
| [From Row-count Assertions to Evidence Assertions](../../postmortems/from_row_count_assertions_to_evidence_assertions.md) | Postmortem | Historical/supporting | Demonstrates why exact evidence can reveal physical adapter/type drift. | Historical testing correction. |
| [From Protocol Satisfaction to Production Wiring Proof](../../postmortems/from_protocol_satisfaction_to_production_wiring_proof.md) | Postmortem | Historical/supporting | Separates unit proof, adapter proof, and real assembly proof. | Historical Stage 3.5D example with reusable review guidance. |

## Minimal Actor Metadata

Database role, authenticated principal, business actor, request caller, runtime component, and producer metadata are distinct concepts. `created_by` and similar fields provide narrow provenance only. They do not establish identity assurance, authentication, authorization, semantic correctness, policy approval, or DecisionReceipt identity semantics.

The Stage 3.5E README and closeout treat PR5 as completed. The older PR breakdown retains a stale `Planned` label and should be read as historical chronology. PR5 completed a documentation-first minimal actor-metadata boundary; it did not add an actor registry, authentication system, audit table, or DecisionReceipt persistence.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Minimal Actor Metadata Boundary](../../boundary_notes/minimal_actor_metadata_boundary.md) | Boundary note | Start here | Defines the reusable separation among permission identity, producer/trigger metadata, and governance decision evidence. | PR5 conceptual boundary. |
| [PR5 Minimal Actor Metadata implementation note](../../implementation_notes/stage_3_5e/minimal_actor_metadata_boundary.md) | Design/implementation note | Core | Records the documentation-first decision, narrow `created_by` interpretation, and Stage 4 handoff. | Completed at the documentation-boundary level. |
| [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Core | Treats PR5 and the stage closeout as completed. | Later maturity statement governs current navigation. |
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Contains detailed PR5 scope but retains the stale `Planned` label. | Historical chronology, not current maturity authority. |
| [From Runtime Behavior to Durable Evidence](../../reasoning_notes/from_runtime_behavior_to_durable_evidence.md) | Reasoning note | Historical/supporting | Explains why runtime attribution or judgment becomes durable evidence only when explicitly preserved. | Non-authoritative evidence-model derivation. |

## Physical Enforcement versus Semantic Governance

PostgreSQL allow/deny, append-only protection, derived-state mutation restriction, actor metadata, semantic admission, `SemanticOutcome`, DecisionReceipt, and runtime policy are separate concerns. SQL success or failure must not be mapped directly into business or governance meaning.

Database permission answers whether the active responsibility role can execute a physical operation. Semantic admission answers whether a candidate may become accepted history. Actor metadata identifies a producer narrowly. Stage 4B preserves bounded governance evidence in `DecisionReceipt`; policy, allowed action, and execution remain later contracts.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Start here | Separates permission enforcement from Compass Layer 1 and transaction atomicity. | PR1 conceptual boundary. |
| [Minimal Actor Metadata Boundary](../../boundary_notes/minimal_actor_metadata_boundary.md) | Boundary note | Core | Separates producer provenance from semantic decision evidence. | PR5 reusable boundary. |
| [Layered Testing Strategy](../../boundary_notes/layered_testing_strategy_for_permission_and_governance.md) | Boundary note | Core | Prevents permission tests from being presented as governance-flow proof. | Policy/action governance remains future after completed Stage 4B receipt evidence. |
| [From Local PostgreSQL to Defense in Depth](../../reasoning_notes/from_local_postgres_to_defense_in_depth.md) | Reasoning note | Historical/supporting | Explains why permissions, schema, validation, transactions, configuration, and secrets protect different boundaries. | Non-authoritative derivation. |
| [From Runtime Behavior to Durable Evidence](../../reasoning_notes/from_runtime_behavior_to_durable_evidence.md) | Reasoning note | Historical/supporting | Distinguishes runtime judgment from evidence deliberately persisted for later explanation. | Non-authoritative Stage 3.5B framing. |

## Stage 3.5E Baseline and Limitations

Stage 3.5E completed a durable-history and permission-hardening baseline. That stage did not implement `SemanticOutcome` or DecisionReceipt persistence; Stage 4A and Stage 4B later supplied those separate boundaries. The repository still does not implement complete production IAM, authentication, business authorization, service-specific production credentials and pools, secrets topology, pooled-session leakage testing, emergency repair governance, or complete audit/governance records.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5E README](../../implementation_notes/stage_3_5e/README.md) | Stage navigation/status | Start here | Records completed PR1–PR6 scope and the bounded completion criteria. | Current stage closeout. |
| [ADR 0015](../../adr/0015_permission_probing_with_set_role.md) | ADR | Core | Defines the production identity, pool, credential, and deployment questions outside the current proof. | Accepted Stage 3.5E testing decision. |
| [Database Role / Privilege Baseline](../../implementation_notes/stage_3_5e/database_role_privilege_baseline.md) | Design/implementation note | Core | Records the implemented minimum PostgreSQL role baseline and explicit non-goals. | PR2 baseline, not full RBAC. |
| [Derived-State Mutation Permission Tests](../../implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md) | Implementation boundary | Deep dive | Records completed permission-matrix proof and deferred concurrency/chaos scenarios. | PR4 baseline, not production simulation. |
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves the stage delivery sequence and broad non-goals. | PR5 status wording is stale relative to closeout. |

## Implementation History and Design Evolution

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5E PR Breakdown](../../implementation_notes/stage_3_5e/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR1–PR6 planning and delivery detail. | Use later completed boundaries for current interpretation. |
| [From Git Sync to Database Immutability](../../reasoning_notes/from_git_sync_to_db_immutability.md) | Reasoning note | Historical/supporting | Traces the realization that process-level immutability must be re-declared in PostgreSQL. | Non-authoritative Stage 3.5B precursor. |
| [From Local PostgreSQL to Defense in Depth](../../reasoning_notes/from_local_postgres_to_defense_in_depth.md) | Reasoning note | Historical/supporting | Traces the separation of local credentials, real secrets, least privilege, schema, validation, and transactions. | Non-authoritative design evolution. |
| [From Row-count Assertions to Evidence Assertions](../../postmortems/from_row_count_assertions_to_evidence_assertions.md) | Postmortem | Historical/supporting | Records the PR4 UUID assertion-fidelity lesson. | Historical test evolution; no production incident. |
| [From Protocol Satisfaction to Production Wiring Proof](../../postmortems/from_protocol_satisfaction_to_production_wiring_proof.md) | Postmortem | Historical/supporting | Records why isolated correctness does not prove real assembly. | Historical Stage 3.5D example. |
| [From Runtime Behavior to Durable Evidence](../../reasoning_notes/from_runtime_behavior_to_durable_evidence.md) | Reasoning note | Historical/supporting | Traces the distinction between transient behavior, durable facts, and later evidence channels. | Non-authoritative Stage 3.5B evidence-model precursor. |

## Open Questions and Important Reading Notes

- Production login and connection-pool identity topology remains future work.
- Emergency administrative repair/restoration authority and evidence remain undefined.
- Maintenance authority for derived-state cleanup, snapshot deletion, retention, quarantine, and rebuild replacement remains undefined.
- Later policy and action stages must define any additional actor, authorization, and evidence identity semantics they require.
- Narrower audit-read access may be needed for future governance evidence.
- Production wiring proof and pooled-session role-leak testing remain future work.
- Permission-probe results are test evidence and are not currently persisted as governance records.
- The duplicate actor-metadata filenames represent different roles: a reusable boundary and a PR5 implementation record.
