# Snapshot Trust Documentation Index

[← Back to Topic_Indexes Index](README.md)

## How to Use This Index

This is topic-based navigation across the reviewed Snapshot Trust documents. The existing `docs/` folders remain the source of each document's role and chronology. A document appears under more than one topic only when it makes a substantial contribution to each.

Accepted event history remains the authority for admitted facts. Projection snapshots are durable, derived, rebuildable compression; persistence does not grant them accepted authority. Later completed implementation boundaries govern current implementation interpretation when earlier planning material describes incomplete or broader designs. Reasoning notes preserve derivations; postmortems reconstruct concrete episodes. Neither is a current contract by itself.

This index does not override architecture documents, ADRs, boundary notes, implementation records, or deferral decisions, and it is not a source of `SemanticOutcome`, DecisionReceipt, runtime policy, retry, or strategy semantics.

## Snapshot Trust Reading Path

| Order | Document | Role | Why read here |
|---:|---|---|---|
| 1 | [Stage 3.5D README](../../implementation_notes/stage_3_5d/README.md) | Stage navigation/status | Start with the completed Read-side projection-snapshot baseline and the explicit aggregate-snapshot deferral. |
| 2 | [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Establish the authority path, derived-state model, and trust responsibilities. Its stated baseline is after PR4, so read later completed boundaries as well. |
| 3 | [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Separate existence, validation evidence, context-specific use, and future receipt-backed reusable eligibility. |
| 4 | [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | See the implemented PR4 checks, explicit non-goals, and deferred trust checks. |
| 5 | [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Learn the durable evidence shape and the distinct local and global lineage coordinates. |
| 6 | [ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Establish that snapshot tails use exact-next order-local sequence while `source_global_position` remains lineage. |
| 7 | [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Understand authority comparison through snapshot-plus-tail reconstruction and full accepted-history replay. |
| 8 | [PR4.5 assisted-state resolver](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_state_resolver.md) | Implementation boundary | Understand fast-path resolution from an explicitly qualified snapshot without treating resolution as trust creation. |
| 9 | [Postgres projection snapshot store](../../implementation_notes/stage_3_5d/postgres_projection_snapshot_store.md) | Design/implementation note | Study insert-once persistence, exact/latest lookup, transaction ownership, and collision behavior. |
| 10 | [Snapshot payload hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Design/implementation note | Deepen the integrity model while preserving the limits of hash equality. |
| 11 | [Snapshot generation policy](../../implementation_notes/stage_3_5d/snapshot_generation_policy.md) | Design/implementation note | Separate safe generation premises from trust qualification and runtime use. |
| 12 | [Aggregate snapshot trust deferral](../../implementation_notes/stage_3_5d/aggregate_snapshot_trust_deferral.md) | Deferral decision | See why Stage 3.5D does not implement aggregate snapshots or Write-side rehydration. |
| 13 | [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Use after the current boundaries to understand the PR1–PR5 sequence and deferred PR6–PR7 work. |
| 14 | [From snapshot as fast state to Snapshot Trust Contract](../../postmortems/from_snapshot_as_fast_state_to_snapshot_trust_contract.md) | Postmortem | Trace the shift from cache-like snapshot thinking to explicit trust qualification. |
| 15 | [From generic validation to authority-based reasoning](../../postmortems/from_generic_validation_to_authority_based_reasoning.md) | Postmortem | Understand why accepted-history availability precedes snapshot classification; later Stage 4 discussion is not retroactive Stage 3.5D behavior. |
| 16 | [From per-order global position to global source boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Trace the correction that made per-order sequence local and accepted-source position global. |
| 17 | [Stage 3.5D local correctness and global premise drift](../../postmortems/stage_3_5d_local_correctness_global_premise_drift.md) | Postmortem | Understand the corrected cost/risk premise behind the projection-first baseline and aggregate deferral. |

## Snapshot Trust Overview and Responsibility Map

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5D README](../../implementation_notes/stage_3_5d/README.md) | Stage navigation/status | Start here | Defines the completed stage scope: Read-side projection snapshots plus an explicit aggregate-snapshot deferral decision. | Navigation and maturity statement, not semantic authority. |
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Core | Defines snapshots as traceable, checkable, rejectable, discardable, and rebuildable derived-state compression. | Describes the baseline after PR4 and predates completed PR4.5/PR5 boundaries. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | Defines the longer-term separation among local eligibility, authority validation, runtime use, and future durable receipts. | Accepted and partially implemented. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Records the current implemented checks and deferred hardening at the trust boundary. | Current first implementation after PR4. |
| [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Historical/supporting | Shows how schema, store, validation, resolution, and deferral were delivered. | Planning and closeout chronology must not override later completed boundaries. |

## Snapshot as Derived State

Accepted event history is the authority for admitted facts. A projection snapshot is durable, derived, rebuildable compression of projection state. It does not become authoritative merely because it exists, is stored, has a UUID, parses successfully, contains a nonempty hash field, or is the latest snapshot.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Start here | Establishes full accepted-history replay as the authority path and snapshot use as a subordinate acceleration path. | Baseline after PR4. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | Prevents durable snapshot evidence from being confused with accepted authority or permanent runtime eligibility. | Accepted; receipt-backed reuse remains future work. |
| [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Deep dive | Defines the durable physical artifact while stating that physical constraints do not establish trust. | PR2 persistence shape. |
| [From snapshot as fast state to Snapshot Trust Contract](../../postmortems/from_snapshot_as_fast_state_to_snapshot_trust_contract.md) | Postmortem | Historical/supporting | Explains why a cache-like model was replaced by explicit evidence and qualification boundaries. | Historical rationale, not a current contract by itself. |

## Snapshot Existence, Validity, Eligibility, and Trust

Keep the following qualification states distinct:

1. physical existence;
2. structural validity;
3. local eligibility and compatibility;
4. authority-comparison evidence;
5. runtime use in a specific context;
6. future reusable eligibility backed by a durable validation receipt.

These states must not be collapsed into a single `trusted` flag. PR4 `MATCH` establishes authority-comparison evidence for that validation context. It does not create permanent or universally reusable snapshot eligibility.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Start here | Defines the qualification ladder and distinguishes current evidence from future receipt-backed reuse. | Accepted and partially implemented. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Lists implemented validation checks and deferred lineage, hashing, compatibility, and governance checks. | PR4-era current boundary. |
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Core | Produces authority-comparison evidence by comparing assisted reconstruction with full replay. | Completed PR4; does not authorize future use by itself. |
| [PR4.5 assisted-state resolver](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_state_resolver.md) | Implementation boundary | Core | Consumes an explicitly selected and qualified snapshot, checks local compatibility, and attempts resolution. | Completed PR4.5; consumes trust rather than creating it. |
| [From generic validation to authority-based reasoning](../../postmortems/from_generic_validation_to_authority_based_reasoning.md) | Postmortem | Historical/supporting | Explains why accepted history must exist before snapshot absence, invalidity, or drift can be classified meaningfully. | Later governance examples do not redefine Stage 3.5D results. |

## Snapshot Generation Eligibility

Generation is separate from validation and runtime trust. A snapshot should be constructed only from trusted reconstruction, such as full accepted-history replay or another explicitly qualified canonical path. Automatic production remains deferred.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Snapshot generation policy](../../implementation_notes/stage_3_5d/snapshot_generation_policy.md) | Design/implementation note | Deep dive | Defines trusted generation sources, possible generation points, and the rule that snapshot-write failure must not invalidate accepted history. | Automatic triggers, scheduler behavior, retention, and concurrency policy are deferred. |
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Core | Separates builder, store, validator, and generation-policy responsibilities. | Baseline after PR4. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Deep dive | Places generated evidence within the wider runtime-eligibility model. | Broader reusable eligibility remains future work. |
| [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Historical/supporting | Shows that production generation automation was not required to close the completed baseline. | Historical implementation sequence. |

## Snapshot Schema and Lineage

Lineage coordinates have different scopes and must not be substituted for one another:

- per-order source sequence records aggregate-local causal progress;
- global accepted-source position records globally unique lineage and deterministic scheduling evidence, not completeness;
- source event identity names the claimed accepted boundary event;
- state version records reducer-applied local continuity;
- schema version identifies payload interpretation;
- reducer version identifies derivation logic.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Start here | Defines snapshot identity, order identity, source event identity, local sequence, global position, state, versions, hash, and provenance metadata. | PR2 single-active-version baseline. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Distinguishes implemented plausibility checks from deferred exact source-event and gap verification. | PR4-era boundary. |
| [Postgres projection snapshot store](../../implementation_notes/stage_3_5d/postgres_projection_snapshot_store.md) | Design/implementation note | Deep dive | Uses the complete source boundary for lookup and collision classification; orders latest snapshots by global position, not creation time. | PR3 persistence boundary. |
| [From per-order global position to global source boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Explains the correction from per-order scoping to globally unique accepted-source position. | Historical schema evolution. |
| [ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Core | Narrows `source_global_position` to lineage and defines exact-next order-local tail loading. | Current implemented tail/completeness authority. |

## Payload Hashing and Integrity

Hash equality proves equality of canonical bytes within the agreed hash scope. It does not prove business correctness, accepted-history alignment, source-lineage validity, runtime eligibility, authorship, or authorization. The store persists a caller-supplied hash; full canonical recomputation is not part of the completed PR4/PR4.5 contract.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Snapshot payload hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Design/implementation note | Deep dive | Defines canonical serialization guidance, SHA-256 evidence, candidate inclusions, and the limits of hash equality. | Trust-hardening design; exact scope and full validator enforcement remain unresolved. |
| [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Deep dive | Requires a stored nonempty hash without claiming that the database computed or validated it. | PR2 physical constraint. |
| [Postgres projection snapshot store](../../implementation_notes/stage_3_5d/postgres_projection_snapshot_store.md) | Design/implementation note | Deep dive | Persists and compares the supplied hash during idempotent-save/collision handling. | PR3 store does not compute trust. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Marks full hash recomputation as deferred from the completed PR4 checks. | PR4-era boundary. |

## Durable Snapshot Storage

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Postgres projection snapshot store](../../implementation_notes/stage_3_5d/postgres_projection_snapshot_store.md) | Design/implementation note | Deep dive | Defines insert-once persistence, caller-owned transactions, exact/latest lookup, idempotent duplicate handling, collision errors, and per-order clearing. | Completed PR3 store boundary; persistence does not establish trust. |
| [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Core | Defines uniqueness, source-boundary evidence, payload, compatibility versions, hash, and metadata. | PR2 single-active-version baseline. |
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Core | Keeps storage subordinate to builder, validator, and authority-path responsibilities. | Baseline after PR4. |
| [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Historical/supporting | Places the schema and store before validation and resolution in the implementation chronology. | Earlier plans do not override completed boundaries. |

## Snapshot Trust Validation

The PR4 validator consumes accepted history and a snapshot candidate, reconstructs snapshot plus tail, performs full accepted-history replay, compares final states, and produces authority-comparison evidence. It does not select policy or mutate accepted history, projection state, progress state, or snapshots. Stage 4A and Stage 4B later map this bounded evidence into `SemanticOutcome` and `DecisionReceipt` without changing those producer responsibilities.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Start here | Defines the completed comparison algorithm and structured results, including match, missing evidence, invalid boundary, tail-source violation, and drift. | Completed PR4 validation-only boundary. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Summarizes implemented checks and identifies deferred hash, lineage, compatibility, and global-gap checks. | Current first implementation after PR4. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | Locates PR4 evidence within the broader eligibility and future-receipt model. | Accepted and partially implemented. |
| [From generic validation to authority-based reasoning](../../postmortems/from_generic_validation_to_authority_based_reasoning.md) | Postmortem | Historical/supporting | Explains classification precedence: establish accepted-history authority before classifying snapshot evidence. | Historical reasoning; later Stage 4 mappings are separate. |

## Snapshot-assisted Replay

Snapshot-assisted replay hydrates snapshot state and applies accepted events for the same order whose sequence is exactly after the snapshot's `source_event_sequence`. It is a fast-path candidate subordinate to full accepted-history replay. `source_global_position` remains lineage and scheduling evidence; it does not own tail completeness.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Start here | Defines snapshot-plus-tail replay as an acceleration path that must remain comparable with and rejectable in favor of authority replay. | Baseline after PR4. |
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Core | Performs assisted reconstruction and full replay within one validation operation. | Completed PR4. |
| [Snapshot Trust boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Core | Defines boundary plausibility, strict tail advancement, and drift evidence. | Some exact lineage and gap checks remain deferred. |
| [ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Core | Defines same-order, exact-next local-sequence tail loading and preserves global position as lineage only. | Current implemented tail contract. |
| [From per-order global position to global source boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Preserves the distinct global uniqueness scope of the lineage coordinate. | Does not own the current tail-loading rule. |

## Snapshot-assisted State Resolution

The PR4.5 resolver consumes an explicitly selected and qualified snapshot, performs local eligibility and compatibility checks, replays the accepted tail, and returns resolved state or a structured unresolved result. It does not create trust, perform full authority comparison, automatically invoke fallback, or persist state.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [PR4.5 assisted-state resolver](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_state_resolver.md) | Implementation boundary | Start here | Defines exact-snapshot selection, local precondition/compatibility checks, strict tail replay, resolved output, and unresolved classifications. | Completed PR4.5; no partial state is returned on failure. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | States that the resolver consumes current trust evidence and that durable receipt-backed eligibility remains future work. | Accepted and partially implemented. |
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Core | Supplies the current authority-comparison context from which a qualified snapshot may be selected. | PR4 `MATCH` is contextual evidence, not permanent authorization. |
| [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Historical/supporting | Shows why resolver completion followed validation and did not expand into policy or automatic repair. | Implementation chronology. |

## Accepted-history Fallback and Drift Evidence

Full accepted-history replay remains the authority path. The architecture requires safe fallback to remain available, but PR4.5 does not own automatic fallback selection; caller or orchestrator ownership remains future work. A mismatch is evidence of derived-state or fast-path drift. It does not by itself prove accepted-history corruption or select severity, repair, quarantine, retry, or runtime policy.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Snapshot Trust architecture](../../architecture/snapshot_trust_contract.md) | Architecture | Start here | Requires the snapshot path to remain discardable in favor of full accepted-history replay. | Architecture-level fallback requirement. |
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Core | Produces match or drift evidence without selecting a response. | Completed PR4 validation boundary. |
| [PR4.5 assisted-state resolver](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_state_resolver.md) | Implementation boundary | Core | Returns structured unresolved evidence and deliberately leaves full-replay fallback to a caller. | Completed PR4.5 component boundary. |
| [From generic validation to authority-based reasoning](../../postmortems/from_generic_validation_to_authority_based_reasoning.md) | Postmortem | Historical/supporting | Explains why missing authority, missing snapshot, invalid evidence, and actual drift must remain distinct. | Historical rationale; not a runtime policy contract. |

## Projection Snapshot Baseline

Stage 3.5D completed the Read-side projection-snapshot baseline and the explicit aggregate-snapshot deferral decision. This is not complete production hardening and is not a completed aggregate-snapshot feature. ADR 0013 remains partially implemented because durable validation receipts, broader reusable eligibility, fuller hash/lineage enforcement, and aggregate snapshot use remain future work.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5D README](../../implementation_notes/stage_3_5d/README.md) | Stage navigation/status | Start here | States the completed projection-snapshot scope and aggregate deferral. | Stage completion statement, not production-hardening claim. |
| [Projection snapshot schema baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Design/implementation note | Core | Provides the durable Read-side snapshot evidence shape. | Completed PR2 baseline. |
| [Postgres projection snapshot store](../../implementation_notes/stage_3_5d/postgres_projection_snapshot_store.md) | Design/implementation note | Deep dive | Provides durable projection-snapshot persistence and collision handling. | Completed PR3 boundary. |
| [PR4 assisted-replay validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Core | Provides authority-comparison evidence for snapshot-assisted replay. | Completed PR4 boundary. |
| [PR4.5 assisted-state resolver](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_state_resolver.md) | Implementation boundary | Core | Provides qualified fast-path resolution. | Completed PR4.5 boundary. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | Distinguishes the implemented baseline from future durable trust and aggregate work. | Accepted and partially implemented. |

## Stage 4A / Stage 4B Snapshot Mapping

Stage 4A maps bounded snapshot-trust and snapshot-assisted evidence into typed `SemanticOutcome`. Stage 4B maps those producer results into `DecisionReceipt`, preserves tri-state governance flags as `NOT_EVALUATED`, and supports strict serialization and explicit caller-owned persistence. These mappings do not grant continuing snapshot trust, automatically materialize receipts, select fallback, rebuild state, or authorize action. `DiagnosticTrace` / `ResolutionTrace` remain Stage 4B.1 and are not implemented.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Read-side Outcome Mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Start here | Defines the completed snapshot-trust and assisted-resolution `SemanticOutcome` adapters. | Stage 4A complete. |
| [Read-side / Snapshot DecisionReceipt Mapping](../../implementation_notes/stage_4b/read_side_snapshot_decision_receipt_mapping.md) | Implementation boundary | Core | Defines completed producer-specific receipt construction and evidence checks. | Stage 4B complete; mapping performs no persistence or policy evaluation. |
| [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Core | Confirms the current receipt mapping, serialization, persistence, and non-goal baseline. | Stage 4B.1 trace work is next. |

## Aggregate Snapshot Deferral

No aggregate-snapshot schema, aggregate-snapshot store, builder, selector, Write-side rehydration integration, or admission-sensitive trust gate was implemented. Aggregate snapshots remain deferred pending measured benefit and stricter governance.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Aggregate snapshot trust deferral](../../implementation_notes/stage_3_5d/aggregate_snapshot_trust_deferral.md) | Deferral decision | Start here | Records the explicit non-implementation, shallow-history cost evidence, higher admission risk, and future revival conditions. | Completed PR5 deferral decision. |
| [ADR 0013](../../adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | ADR | Core | Keeps aggregate snapshot use within the longer-term trust and runtime-eligibility model. | Accepted; aggregate portion remains unimplemented. |
| [Snapshot generation policy](../../implementation_notes/stage_3_5d/snapshot_generation_policy.md) | Design/implementation note | Deep dive | Identifies aggregate generation as future and subordinate to trusted reconstruction. | No aggregate generation path implemented. |
| [Stage 3.5D local correctness and global premise drift](../../postmortems/stage_3_5d_local_correctness_global_premise_drift.md) | Postmortem | Historical/supporting | Explains why aggregate replay cost and risk assumptions were corrected before deferral. | Historical premise audit, not an implementation commitment. |

## Implementation History and Design Evolution

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5D PR breakdown](../../implementation_notes/stage_3_5d/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR1–PR5 completion and PR6–PR7 deferral. | Read with later completed boundaries when candidate designs differ. |
| [From snapshot as fast state to Snapshot Trust Contract](../../postmortems/from_snapshot_as_fast_state_to_snapshot_trust_contract.md) | Postmortem | Historical/supporting | Traces the move from performance cache to explicit evidence and trust qualification. | Evolution narrative, not current authority. |
| [From generic validation to authority-based reasoning](../../postmortems/from_generic_validation_to_authority_based_reasoning.md) | Postmortem | Historical/supporting | Traces authority-first classification and later evidence interpretation. | Later Stage 4 language must not be projected backward. |
| [From per-order global position to global source boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Records the correction of global-position scope and uniqueness. | The current schema/boundary documents state the operative model. |
| [Stage 3.5D local correctness and global premise drift](../../postmortems/stage_3_5d_local_correctness_global_premise_drift.md) | Postmortem | Historical/supporting | Records why the stage completed a projection baseline and deferred aggregate snapshots. | Historical premise correction, not a future-work commitment. |

## Open Questions and Important Reading Notes

- Exact canonical payload-hash scope remains undecided.
- Full mandatory lineage checks remain incomplete.
- Durable validation receipts and invalidation/version rules remain future work.
- Automatic full-replay fallback ownership is not yet assigned.
- Production generation triggers, retention, and concurrency policy remain deferred.
- Schema/reducer multi-version coexistence remains future work.
- Aggregate snapshots remain deferred.
- PR4 `MATCH` must not be broadened beyond its current evidence contract without an explicit later decision.
