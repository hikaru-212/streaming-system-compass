# Mathematical Structure Documentation Index

## How to Use This Index

This index is an optional cross-document mathematical reading lens for the Streaming System + Compass documentation. It identifies both explicit mathematical reasoning and strong structural correspondences that clarify concrete engineering consequences.

It does not imply mathematical authorial intent unless a source document says so. It does not turn an analogy into an accepted architecture contract, prove that Compass is a formal mathematical system, or replace the professional-topic indexes. Existing document folders and the Write-side, Read-side, Snapshot Trust, Durable History / Permission, and SemanticOutcome indexes remain the primary engineering navigation.

Documents without a meaningful mathematical classification are intentionally omitted from the main tables. The labels used here are:

- **Explicit mathematical reasoning** — the document explicitly depends on a formal rule, invariant, order, exact representation, deterministic mapping, or other technically meaningful mathematical property.
- **Strong structural correspondence** — the documented engineering structure has a precise and useful mathematical correspondence even though the document does not necessarily name it mathematically.
- **Weak analogy — rejected** — the comparison is suggestive but lacks the objects, operation or relation, required property, or engineering consequence needed for the strong map.

Mathematical vocabulary should clarify an engineering consequence rather than decorate it. Every strong correspondence below identifies its objects, relation or operation, required property, value, and practical limitation.

## Section 1 — Mathematical Area Overview

| Mathematical area | Support level | Main Compass areas | Representative documents | Main caution |
|---|---|---|---|---|
| Logic and formal specification | Strong | Foundations, Write-side, Snapshot Trust, permissions | [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md); [Transition-first Decision Note](../../domain/decision_note_transition_first_then_domain_invariants.md); [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | Separate business legality, transition truth, admission, and physical enforcement predicates. |
| State-transition systems | Strong | Aggregate, replay, projection, Semantic Admission | [Transactional Core](../../architecture/transactional_core.md); [Aggregate Boundary](../../boundary_notes/aggregate_module.md); [Action Path Admission](../../semantic_admission/action_path_admission.md) | The repository defines useful states and transitions, not a complete formal automaton. |
| Order theory and ordered histories | Strong | Accepted history, Read-side, snapshots | [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md); [Read-side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Aggregate-local sequence owns current exact-next completeness; global accepted-source position is distinct lineage/scheduling evidence. |
| Deterministic replay and algebraic reduction | Strong structural correspondence | Aggregate, projection, rebuild, snapshots | [Projection Pipeline](../../architecture/projection_pipeline.md); [Durable Replay Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Replay corresponds to a fold; the documents do not define a state monoid or homomorphism. |
| Concurrency, causality, and admission | Strong | Write-side, Semantic Admission | [ADR 0010](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md); [ADR 0012](../../adr/0012_two_phase_concurrency_admission.md); [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md) | The current relations are stream- and database-boundary specific, not a universal distributed happens-before relation. |
| Identity, membership, and semantic partitioning | Strong | Candidate/accepted lifecycle, idempotency, Stage 4A | [ADR 0008](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md); [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Identifier equality, accepted membership, observation boundary, and governance identity must not be collapsed. |
| Numerical representation and exact arithmetic | Strong | Domain, Write-side persistence | [ADR 0006](../../adr/0006_use_decimal_for_money_values_before_durable_persistence.md); [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Exact Decimal representation is not a complete numerical-analysis, currency, or rounding model. |
| Canonicalization and integrity functions | Strong | Snapshot Trust | [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Digest equality is bounded integrity evidence, not semantic correctness or authority. |
| Temporal safety properties | Strong structural correspondence | Admission, append-only history, checkpoints, permissions | [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md); [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | These are safety correspondences, not a formal LTL/CTL specification or liveness proof. |
| Evidence-to-meaning classification | Strong | Stage 4A / Stage 4B | [Runtime Technical-status Mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md); [DecisionReceipt Runtime Contract](../../implementation_notes/stage_4b/decision_receipt_contract.md) | Mappings cover supported evidence; receipt construction and persistence remain explicit rather than automatic. |
| Decision/control separation — structural only | Limited but useful | Stage 4A / Stage 4B and future governance | [Runtime SemanticOutcome Boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md); [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md) | Observation, meaning, governance evidence, and action are separated, but no formal controller or optimization problem exists. |
| Stochastic-agent reasoning — analogy only | Weak analogy — rejected | Semantic Admission | [Agent Pipelines as a Stochastic Process](../../semantic_admission/agent_pipelines_as_stochastic_process.md) | The essay explicitly offers an analogy and defines no random variables, index set, transition distribution, or dependence model. |
| **Unsupported group: linear algebra; category theory; formal stochastic processes; information theory; lattices; fixed-point convergence; formal control systems** | **Insufficient repository evidence** | — | — | These are not missing project features. The reviewed documents simply do not supply the structures required for these classifications. |

## Section 2 — Strong Mathematical Document Map

Weak analogies are excluded from this table.

| Document | Document role | Engineering area | Mathematical lens | Classification | Mathematical structure | Engineering value |
|---|---|---|---|---|---|---|
| [Compass Quotient Model v1](../../research/semantic_models/compass_quotient_model_v1.md) | Non-authoritative research model | Stage 4 / semantic compression | Many-sorted contextual equivalence, quotient construction, and open configurations | Candidate mathematical / semantic research model | Distinguishes implementation labels from semantic classes while proposing semantic-state quotients and a separate open-configuration carrier; adequacy, congruence, minimality, and conformance remain unproved. | Provides an optional compression lens without becoming an architecture or protocol authority. |
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Domain specification | Foundations / Write-side | Predicates, invariants, state transitions, exact arithmetic | Explicit mathematical reasoning | Order states and events; command and amount predicates; deterministic `apply`; required invariants. The rules do not enumerate a complete formal automaton. | Supplies concrete legality and replay proof obligations. |
| [Transition-first Decision Note](../../domain/decision_note_transition_first_then_domain_invariants.md) | Domain decision note | Foundations / Write-side | Necessary and sufficient conditions | Explicit mathematical reasoning | Transition truth is necessary but not sufficient; domain legality, admission continuity, and retry safety remain separate predicates. | Prevents one satisfied condition from being mistaken for complete admissibility. |
| [ADR 0006 — Decimal Money](../../adr/0006_use_decimal_for_money_values_before_durable_persistence.md) | Accepted ADR | Write-side | Exact arithmetic | Explicit mathematical reasoning | Exact decimal values and equality replace binary floating-point approximation; canonical representation remains bounded by documented policy. | Stabilizes equality, replay, fingerprints, and durable representation. |
| [Transactional Core](../../architecture/transactional_core.md) | Architecture | Foundations / Write-side | State transition and fold | Strong structural correspondence | State, ordered accepted events, and deterministic event application correspond to a left fold; no state-state operation is defined. | Clarifies rehydration and shared live/replay mutation logic. |
| [Aggregate Boundary](../../boundary_notes/aggregate_module.md) | Boundary note | Write-side | Reachable states and deterministic transition | Strong structural correspondence | Commands decide candidate transitions; accepted/replayed events deterministically evolve aggregate state. | Separates candidate legality from reconstruction. |
| [ADR 0003 — Concurrency, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | Accepted ADR | Write-side | Scoped idempotence and version order | Explicit mathematical reasoning | Repeating the same request identity and fingerprint returns one accepted result without another append; other retries are excluded. | Defines the exact idempotent system boundary. |
| [Idempotency Boundary](../../boundary_notes/idempotency_module.md) | Boundary note | Write-side | Equivalence classification | Explicit mathematical reasoning | Request identity and semantic fingerprint partition evidence into `MISS`, `REPLAY`, or `CONFLICT`. | Avoids treating every repeated attempt as equivalent. |
| [ADR 0008 — Candidate and Accepted Identity](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Accepted ADR | Foundations / Write-side | Identity and set membership | Explicit mathematical reasoning | A UUID may exist before admission; membership in accepted history grants accepted-event status. | Separates physical identity from authority. |
| [Write-side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Architecture / schema baseline | Write-side | Ordered coordinates and constraints | Explicit mathematical reasoning | Stream-local versions, uniqueness, numeric constraints, and identity relations preserve physical evidence without defining business legality. | Makes durable invariant violations detectable. |
| [ADR 0010 — Atomicity versus Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | Accepted ADR | Write-side | Independent predicates | Explicit mathematical reasoning | All-or-nothing transaction behavior and entitlement to the next stream position are distinct properties; neither implies the other. | Prevents atomic writes from being misread as concurrency-safe admission. |
| [ADR 0011 — Validation Placement](../../adr/0011_validation_mode_vs_validation_placement.md) | Accepted ADR | Write-side | Restricted product and temporal reasoning | Explicit mathematical reasoning | Validation placement × admission strategy has an accepted subset of two timing-coherent pairs; constructibility does not imply support. | Defines valid configuration composition. |
| [ADR 0012 — Two-phase Admission](../../adr/0012_two_phase_concurrency_admission.md) | Accepted ADR | Write-side | Causality and final admission point | Strong structural correspondence | Stream preparation constrains the validation basis; final append-time checking determines accepted membership. | Explains why preparation cannot replace final continuity admission. |
| [Concurrency Boundary](../../boundary_notes/concurrency_boundary.md) | Boundary note | Write-side | Prefix and stale-version relation | Strong structural correspondence | Expected and current versions identify whether a candidate was derived from the current accepted prefix. | Gives stale-write rejection its precise scope. |
| [PostgreSQL Concurrency Admission Boundary](../../boundary_notes/postgres_concurrency_admission_boundary.md) | Boundary note | Write-side | Serialization and linearization | Strong structural correspondence | A lock-protected critical section or optimistic compare-and-append permits one next accepted position. | Connects database behavior to the abstract continuity invariant. |
| [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md) | Public conceptual note | Semantic Admission | Competing transitions and history-relative validity | Strong structural correspondence | Candidates derived from one state can become incompatible after a competing fact changes the history prefix. | Shows why technical serialization alone does not preserve meaning. |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Architecture | Read-side | Deterministic reduction | Strong structural correspondence | Ordered accepted events are reduced into derived projection state; orchestration details are outside the reducer relation. | Supports deterministic replay and rebuild reasoning. |
| [Projection Module Boundary](../../boundary_notes/projection_module.md) | Boundary note | Read-side | State-transition function | Strong structural correspondence | Reducer state plus accepted event yields next derived state; storage and checkpoints are excluded. | Keeps projection derivation deterministic and testable. |
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Read-side / Snapshot | Partial order and per-key progress | Explicit mathematical reasoning | `(order_id, sequence)` gives local causal order and exact-next completeness; `global_position` is a distinct globally unique lineage and scheduling coordinate. | Prevents a visible higher allocation from being mistaken for a complete committed prefix. |
| [Global-position Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Read-side | Earlier scalar progress model | Explicit mathematical reasoning | Preserves the earlier global-position cursor model that ADR 0020 replaced for current completeness. | Makes the superseded completeness assumption reviewable without treating it as current. |
| [Read-side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Read-side | Coordinate scope and constraints | Explicit mathematical reasoning | Local sequence and the legacy global checkpoint cursor have different domains and durable invariants. | Preserves chronology; ADR 0020 governs current restart completeness. |
| [Durable Replay / Rebuild Validation Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Boundary note | Read-side | Ordered fold and equality predicate | Explicit mathematical reasoning | Aggregate-local accepted history is replayed deterministically and compared with persisted derived state. | Defines match, absence, and drift evidence without transferring authority. |
| [Global-source Boundary Postmortem](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Read-side / Snapshot | Local versus global uniqueness | Explicit mathematical reasoning | `(order_id, sequence)` is locally unique; `global_position` must be globally unique under the current source model. | Demonstrates the cost of confusing coordinate scopes. |
| [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md) | Architecture | Snapshot Trust | Prefix decomposition and qualification predicates | Strong structural correspondence | Accepted history is viewed as prefix plus tail; a snapshot claims derived state at the prefix boundary and requires qualification. | Explains acceleration without replacing the authority path. |
| [Snapshot Trust Boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Boundary note | Snapshot Trust | Validity, eligibility, and authority comparison | Explicit mathematical reasoning | Existence, structural validity, compatibility, authority-comparison evidence, and runtime use are distinct predicates. | Prevents a single overloaded `trusted` boolean. |
| [Projection Snapshot Schema Baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Implementation boundary | Snapshot Trust | Lineage coordinate tuple | Explicit mathematical reasoning | Local sequence, global position, event identity, schema version, and reducer version carry different scopes and uniqueness rules. | Makes false lineage claims mechanically visible. |
| [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Design / implementation note | Snapshot Trust | Canonicalization and digest function | Explicit mathematical reasoning | Payload is canonicalized to bytes and hashed; equality is meaningful only inside the selected canonical scope. | Bounds integrity evidence without claiming semantic truth. |
| [Snapshot-assisted Replay Validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Implementation boundary | Snapshot Trust | Prefix/tail reconstruction and equality | Strong structural correspondence | Snapshot-plus-tail reconstruction is compared with full accepted-history replay at the same authority boundary. | Produces comparison evidence without permanent authorization. |
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Boundary note | Permission / history | Allow/deny relation and safety invariant | Explicit mathematical reasoning | Role × artifact × operation determines physical permission; forbidden normal-runtime history rewrites remain excluded. | Frames database permissions as bounded enforcement rather than business authority. |
| [Action Path Admission](../../semantic_admission/action_path_admission.md) | Public conceptual note | Semantic Admission | Trace-sensitive predicate | Strong structural correspondence | Two action sequences may reach equivalent terminal state while only one satisfies the path-admission predicate. | Shows why terminal-state validation is insufficient. |
| [Retry Reason Classification](../../architecture/retry_reason_classification.md) | Future architecture note | Later Stage 4 | Product classification | Explicit mathematical reasoning | Identity/fingerprint cases map across retry class, retry safety, and intent-consistency dimensions. The vocabulary remains planning-stage. | Makes retry-like cases reviewable without collapsing them. |
| [Retry Is Not Intent Preservation](../../semantic_admission/retry_is_not_intent_preservation.md) | Public conceptual note | Semantic Admission | Equivalence cases | Explicit mathematical reasoning | Same/different request identity crossed with same/different meaning yields distinct runtime cases. | Prevents repetition from being assumed to preserve intent. |
| [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Stage 4A | Product-like typed classification | Strong structural correspondence | Category, code, boundary, severity, risk, reversibility, reason, context, and evidence remain distinct coordinates; they are not a vector. | Preserves multiple semantic dimensions without collapsing them into `ok`. |
| [Runtime Technical-status Mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation mapping | Stage 4A | Partial deterministic mapping | Explicit mathematical reasoning | Supported normalized statuses map to stable semantic tuples while caller-supplied boundary and evidence remain explicit. | Makes mapping gaps and contradictions auditable. |
| [Read-side Outcome Mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation mapping | Stage 4A | Many-to-one mapping with provenance | Explicit mathematical reasoning | Several adapter statuses may share a code while boundary, reason, and evidence preserve different assurance histories. | Avoids treating equal codes as identical observations. |
| [Write-side Admission Outcome Mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation mapping | Stage 4A | Case partition and mapping | Explicit mathematical reasoning | Accepted, validation-blocked, stale, timeout, infrastructure, replay, and conflict evidence map into distinct semantic meanings. | Keeps admission evidence classes separate. |
| [Semantic Mapping Stability Note](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Governance / stability note | Stage 4A | Mapping invariance and compatibility | Explicit mathematical reasoning | Mapping revisions must remain explicit and test-visible; adapter changes must not silently change semantic meaning. | Treats interpretation as a protected contract. |
| [Runtime SemanticOutcome Boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Stage 4A | Observation-to-meaning separation | Strong structural correspondence | Technical evidence is mapped to semantic interpretation; later policy maps meaning toward action. No controller dynamics are defined. | Prevents interpretation from becoming executable authorization. |
| [ADR 0007 — Semantic Correctness versus Operational Trust](../../adr/0007_separate_semantic_correctness_from_operational_trust.md) | Proposed ADR | Later trust governance | Finite product of trust dimensions | Strong structural correspondence | Semantic, history, projection, operational, and action-safety classifications form separate axes in a proposed evaluator. | Avoids a single `trusted` boolean while preserving proposed status. |
| [Drift Validation Cost Boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Design / implementation note | Stage 4A | Observation versus decision variables | Strong structural correspondence | Counts, timing, scope, and snapshot use are descriptive evidence; no objective or policy function is supplied. | Prevents measured cost from silently selecting runtime behavior. |

## Section 3 — Logic, Predicates, and Proof Obligations

| Document | Core mathematical idea | Concrete predicate or rule | Engineering consequence | Reading level |
|---|---|---|---|---|
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Invariant and legality predicates | Positive amounts; `pay(amount) == total_amount`; `PAID` implies `paid_amount == total_amount`; deterministic replay | Illegal business candidates must be rejected before admission | Start here |
| [Transition-first Decision Note](../../domain/decision_note_transition_first_then_domain_invariants.md) | Necessary versus sufficient conditions | Transition consistency is necessary but does not imply business legality | Domain, Layer 1, admission, and retry proofs remain separate | Core |
| [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | Allowed relation over configuration pairs | Only `PRE_TRANSACTION + OPTIMISTIC` and `IN_TRANSACTION + PESSIMISTIC` are supported | A mechanically constructible pair is not necessarily a valid configuration | Core |
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Allow/deny predicate | Normal runtime roles cannot arbitrarily update/delete accepted history | Physical enforcement protects authority without defining business meaning | Core |
| [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md) | Conjunction of qualification predicates | Existence alone does not imply compatibility, authority alignment, or runtime eligibility | Snapshot use requires evidence appropriate to the requested context | Core |
| [Snapshot Trust Boundary](../../boundary_notes/snapshot_trust_contract_boundary.md) | Separation of necessary conditions | Structural validity, local eligibility, lineage, and authority comparison remain distinct | Avoids collapsing qualification into one `trusted` flag | Deep dive |

## Section 4 — State-transition Systems

| Document | State space or state object | Transition relation/function | Preserved invariant | Limitation |
|---|---|---|---|---|
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Order aggregate state including status, amount, version, and predecessor identity | Commands produce legal candidate events; `apply(event)` mutates state | Legal status progression, amount invariants, sequence continuity, deterministic replay | Not a complete formal automaton or proof of every unreachable state |
| [Transactional Core](../../architecture/transactional_core.md) | Rehydrated aggregate state | Sequential application of accepted events followed by candidate decision | Candidate events are not accepted facts; replay and live application share semantics | Persistence and admission are separate boundaries |
| [Aggregate Boundary](../../boundary_notes/aggregate_module.md) | Aggregate state | Command handling chooses a candidate; accepted-event application evolves state | Business legality remains inside the domain boundary | Does not validate transition truth against durable accepted history by itself |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Derived projection state | Reducer applies an accepted event to prior projection state | Deterministic derived state from ordered accepted history | Projection state is not accepted history |
| [Action Path Admission](../../semantic_admission/action_path_admission.md) | External system state plus action trace | Each proposed operation changes the state along a trace | The path must preserve intent and protected data, not merely reach a matching terminal state | No complete action language or trace calculus is defined |

## Section 5 — Ordering, Causality, and Concurrency

| Document | Ordered objects | Order or causal relation | Scope | Why it matters | Limitation |
|---|---|---|---|---|---|
| [Global-position Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Accepted events in the historical Stage 3.5C model | Increasing `global_position` | Earlier global accepted-source consumption | Preserves the former scalar scan/restart model for chronology | Superseded for current completeness by ADR 0020 |
| [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Events within one order and durable per-order progress | Exact-next `(order_id, sequence)` progress; `global_position` only as lineage/scheduling evidence | Local aggregate completeness versus global coordinate | Prevents allocation order from being used as a committed-history frontier | One active worker only; no global committed watermark or multi-worker protocol |
| [Global-source Boundary Postmortem](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Snapshot lineage coordinates | Local composite uniqueness versus global uniqueness | Snapshot/source lineage | Corrects a false per-order interpretation of a global coordinate | Historical explanation, not independent architecture authority |
| [Concurrency Boundary](../../boundary_notes/concurrency_boundary.md) | Candidate attempts and accepted stream versions | Candidate basis precedes current version or matches current prefix | One aggregate stream | Detects stale candidates and competing next-position claims | Does not decide business compatibility |
| [ADR 0012](../../adr/0012_two_phase_concurrency_admission.md) | Stream basis, prepared critical section, candidate append | Prepare before expensive validation; final continuity check at append | One Write-side stream and transaction path | Preserves a valid basis while retaining final admission | Not a universal distributed linearizability proof |
| [PostgreSQL Concurrency Admission Boundary](../../boundary_notes/postgres_concurrency_admission_boundary.md) | Competing database transactions | Lock serialization or optimistic expected-version comparison | PostgreSQL-backed admission | Gives successful append a definite next stream position | Database ordering does not establish semantic validity |
| [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md) | Competing candidate actions | Validity is evaluated relative to the current accepted-history prefix | Business meaning under concurrency | A technically ordered candidate may still become semantically obsolete | Conceptual semantic boundary, not a database protocol |

No reviewed document defines a universal distributed happens-before relation across all services, agents, and storage systems.

## Section 6 — Replay, Reduction, and Fold Structure

Replay has a strong correspondence to a deterministic left fold over an ordered accepted-event sequence.

| Document | Initial state | Ordered input | Transition/reducer | Result | Mathematical classification |
|---|---|---|---|---|---|
| [Transactional Core](../../architecture/transactional_core.md) | Empty/new aggregate state | Aggregate-local accepted events | Aggregate `apply(event)` | Rehydrated aggregate | Strong structural correspondence |
| [Aggregate Boundary](../../boundary_notes/aggregate_module.md) | Current aggregate state | One accepted/replayed event at a time | Deterministic aggregate mutation | Next aggregate state | Strong structural correspondence |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Empty or prior projection state | Eligible accepted events, respecting exact-next local continuity | Canonical projection reducer | Derived read model | Strong structural correspondence |
| [Projection Module Boundary](../../boundary_notes/projection_module.md) | Prior projection state | Accepted event | Storage-independent reducer | Next projection state | Strong structural correspondence |
| [Durable Replay Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Empty projection state | One order's accepted events ordered by local sequence | Canonical reducer | Expected state for comparison | Explicit mathematical reasoning |
| [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md) | Qualified snapshot state at a claimed prefix | Accepted tail after the snapshot boundary | Canonical reducer | Snapshot-assisted resolved state | Strong structural correspondence |
| [Snapshot-assisted Replay Validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Snapshot state and full-replay initial state | Accepted tail and complete accepted history | Same canonical reducer on two reconstruction paths | Comparison evidence | Strong structural correspondence |

The reviewed documents do not define a binary composition operation on states, so this index does not claim a state monoid or a homomorphism. Finite deterministic replay is also not convergence to a fixed point.

## Section 7 — Idempotency and Equivalence Classes

| Document | Equivalence evidence | Repeated operation | Idempotent effect | Excluded cases |
|---|---|---|---|---|
| [ADR 0003](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | Same `request_id` and same semantic fingerprint | Repeat request classification and result lookup | Return prior accepted result; create no new accepted event | Changed payload/fingerprint, different request identity, general retry policy |
| [Idempotency Boundary](../../boundary_notes/idempotency_module.md) | Durable stored request/fingerprint evidence | Classify an incoming normalized request | `REPLAY` is stable for the same logical request | `MISS`, `CONFLICT`, stale write, technical persistence failure |
| [Retry Reason Classification](../../architecture/retry_reason_classification.md) | Request identity, semantic fingerprint, and attempt evidence | Classify a retry-like situation | Separates safe replay from reload/retry/escalation cases | Future architecture; not a completed universal retry contract |
| [Retry Is Not Intent Preservation](../../semantic_admission/retry_is_not_intent_preservation.md) | Same/different identity crossed with same/different meaning | Regenerate or repeat an attempted action | Only matching identity/meaning supports the narrow replay interpretation | Agent proxy-objective drift, infrastructure retry, rebuild, changed intent |

Idempotent replay is scoped to one request identity and matching semantic fingerprint. It is not arbitrary mathematical idempotence across all side effects, general retry permission, or proof that a regenerated agent action preserves intent.

## Section 8 — Identity, Set Membership, and Authority

| Document | Identity object | Membership or lifecycle relation | Authority consequence | Unresolved boundary |
|---|---|---|---|---|
| [ADR 0008](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Physical `event_id`; candidate and accepted references | Before append: candidate reference exists and accepted reference is absent; successful admitted append places the event in accepted history | Accepted-history membership establishes accepted-event status; UUID equality alone does not | Cross-attempt reuse or regeneration after rejected candidate reconstruction |
| [Write-side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Event, request, order, stream-version identities | Unique and foreign-key-like durable relations preserve accepted evidence | Schema preserves identity evidence but does not define business truth | Later identity evolution and broader actor/governance identity |
| [Idempotency Boundary](../../boundary_notes/idempotency_module.md) | `request_id` and semantic fingerprint | Durable mapping from one successful logical request to accepted result | Supports request-result replay, not accepted truth independently | Attempt lineage and rejected-candidate history |
| [Projection Snapshot Schema Baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Snapshot, source event, order, local sequence, global position, versions | Snapshot claims lineage to a particular derived-state boundary | Lineage supports qualification; snapshot identity does not grant authority | Full mandatory lineage enforcement remains incomplete |
| [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | `outcome_id` | Identifies one semantic interpretation result | Does not identify an event, request, receipt, or accepted fact | External API compatibility and Stage 4B.1 trace lineage remain separate boundaries |
| [DecisionReceipt Runtime Contract](../../implementation_notes/stage_4b/decision_receipt_contract.md) | `receipt_id`, `outcome_id`, subject and correlation coordinates | A typed record preserves selected SemanticOutcome-derived identity/evidence; Stage 4B mappings, serializer v1, and explicit persistence are complete | Correlation evidence is not accepted-history authority | Automatic materialization, policy, trace, retry, and action remain unimplemented |

Different identity coordinates have different semantic roles. This index does not decide the unresolved cross-attempt candidate-event identity policy.

## Section 9 — Exact Arithmetic and Canonical Representation

| Document | Numerical/representation concern | Required property | Rejected representation | Engineering consequence |
|---|---|---|---|---|
| [ADR 0006](../../adr/0006_use_decimal_for_money_values_before_durable_persistence.md) | Money equality before durable persistence | Exact decimal meaning in domain values, serialization, and SQL numeric columns | Binary floating-point money baseline | Stable replay, equality, persistence, and fingerprint inputs |
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Positive and equal payment amounts | `Decimal`, positive amount, full-payment equality in v1 | Negative/zero amounts and approximate money semantics | Domain legality can depend on exact comparisons |
| [Write-side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Durable numeric representation | Exact SQL numeric values and physical constraints | Floating-point durable money | Persistence preserves exact accepted evidence |
| [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Stable payload bytes and Decimal scale | Deterministic canonical primitive conversion and encoding | Decimal-to-float conversion and arbitrary serializer output | Equal logical payloads inside the declared scope can produce stable digests |

These rules do not constitute a complete numerical-analysis, currency, rounding, or error-propagation model.

## Section 10 — Snapshot Prefix Decomposition and Integrity

### Prefix decomposition

Accepted history can be viewed structurally as a prefix plus a tail. A snapshot claims derived state at a particular prefix boundary; accepted tail events are then replayed through the canonical reducer. Where authority-comparison evidence is required, the result is compared with full accepted-history replay.

### Integrity function

Snapshot hashing composes canonicalization with SHA-256 over a selected scope. Equality therefore concerns canonical bytes and their digest—not business correctness, authority, authorship, or universal eligibility.

| Document | Mathematical object/function | What is established | What is not established |
|---|---|---|---|
| [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md) | History decomposition `prefix + tail`; derived state at prefix boundary | A qualified snapshot may accelerate replay while full history remains the authority fallback | Snapshot is not accepted history or a universally sufficient summary |
| [Projection Snapshot Schema Baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md) | Boundary-coordinate tuple | Local/global lineage and version coordinates identify the claimed prefix context | Complete future multi-version compatibility and every mandatory lineage check |
| [Snapshot-assisted Replay Validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Two deterministic reconstruction paths and equality comparison | Snapshot-plus-tail can be compared with full replay for the validation context | A `MATCH` is not permanent authorization or a durable validation receipt |
| [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | `payload → canonical bytes → SHA-256 digest` | Same canonical bytes yield the same digest; scoped changes should affect the digest | Semantic correctness, accepted-history alignment, authorization, or collision impossibility |

A snapshot is not proven to be a sufficient statistic. Snapshot compression is not Shannon information theory. Hash equality is not semantic correctness.

## Section 11 — Semantic Classification as Partial Mapping

| Document | Mapping domain | Mapping codomain | Total or partial? | Preserved evidence | Known gap |
|---|---|---|---|---|---|
| [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Bounded runtime correctness evidence | SemanticOutcome fields: category, code, boundary, severity, risk, reversibility, reason, context, evidence | Contract defines the codomain; individual adapters remain bounded | Observation boundary, reason, context, and evidence | Public/JSON schema and all future vocabulary evolution |
| [Runtime Technical-status Mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Supported normalized generic statuses | Stable semantic tuple plus caller-supplied boundary/reason/evidence | Partial over explicitly supported statuses | Original normalized `technical_status` | Unsupported dependency/adapter statuses require explicit decisions |
| [Read-side Outcome Mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Read-side replay and Snapshot-assisted evidence statuses | SemanticOutcome | Partial adapter mapping | Technical status, boundary, assurance-specific evidence | Unsupported future producer statuses still require explicit mapping |
| [Write-side Admission Outcome Mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Accepted, blocked, stale, timeout, infrastructure, replay, conflict evidence | SemanticOutcome | Partial to the documented admission cases | Admission result, reason, request/concurrency evidence | No separate explicit domain-rejection mapping in the reviewed Stage 4A batch |
| [Semantic Mapping Stability Note](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Existing and proposed mapping revisions | Reviewable compatible mapping contract | Evolution is allowed but must be explicit | Test-visible semantic behavior and boundary meaning | General versioning, deprecation, and compatibility policy remains undefined |

`MISSING_PROJECTION` maps to `REBUILD_REQUIRED / REQUIRES_REBUILD`; that semantic classification does not authorize or execute a rebuild. Stage 4B producer mappings preserve bounded evidence in `DecisionReceipt`, and serialization/persistence remain separate explicit responsibilities.

## Section 12 — Temporal Safety and Trace-sensitive Admission

| Document | Temporal property | Required ordering | Forbidden trace | Formality level |
|---|---|---|---|---|
| [Action Path Admission](../../semantic_admission/action_path_admission.md) | Path admissibility, not terminal-state equality alone | Validate a destructive candidate before execution | Drop/recreate data and later arrive at a superficially matching schema | Strong structural temporal-safety correspondence |
| [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | Validation basis must be protected or rechecked at admission | Validate before optimistic append, or acquire pessimistic lock before protected validation | Validate first and acquire a lock too late; hold a transaction without protecting the basis | Explicit timing reasoning; not formal temporal logic |
| [ADR 0012](../../adr/0012_two_phase_concurrency_admission.md) | Preparation precedes expensive work; final admission follows validation | Prepare/load/validate before final append-time continuity check | Treat stream preparation as if it already granted accepted membership | Strong structural temporal-safety correspondence |
| [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Per-order progress advancement follows durably coordinated projection mutation | Select an exact-next local event, reduce, persist projection and per-order progress, then commit together | Advance one order past a missing or uncommitted local predecessor | Explicit transaction-order and local-continuity invariant |
| [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Accepted history is append-only for normal runtime roles | Controlled admitted append before durable membership | Arbitrary runtime update/delete of accepted history | Structural safety property backed by physical permissions |
| [ADR 0008](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Candidate precedes accepted membership | Allocate identity, validate/admit, then append | Treat pre-allocated UUID existence as an accepted fact | Explicit lifecycle relation |
| [From Statement Success to Owner-Liveness](../../reasoning_notes/from_statement_success_to_owner_liveness.md) | Safety and liveness require different premises | Preserve conflicting-fact exclusion; require owner resolution before claiming contender progress | Infer bounded liveness from statement success or lock arbitration alone | Non-authoritative derivation; tested conditional progress is not a liveness proof |

These are structural temporal-safety correspondences: they express that certain bad events or traces must never occur. The repository does not provide a formal LTL/CTL specification or a liveness proof.

## Section 13 — Decision and Control Separation

| Document | Observation/evidence | Interpretation | Later decision/action | Why this is not yet a formal control system |
|---|---|---|---|---|
| [Runtime SemanticOutcome Boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Technical or adapter evidence | SemanticOutcome meaning | Completed explicit DecisionReceipt mapping, then later policy, strategy, retry, fallback, or mutation | No plant, feedback signal, controller dynamics, or stability criterion |
| [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Bounded context and evidence | Typed semantic category/code and related dimensions | Later consumers may decide what to do | The contract explicitly stops before executable authorization |
| [Drift Validation Cost Boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Replay counts, validation timing, snapshot use, and scope | Descriptive cost evidence | Future frequency, sampling, fallback, or strategy decisions | No optimization objective, constraints, or selected policy function |
| [ADR 0007](../../adr/0007_separate_semantic_correctness_from_operational_trust.md) | Proposed semantic and operational signals | Proposed layered trust verdict | Proposed action-safety outcome | The ADR is future/proposed and defines no feedback law or formal controller |

This separation resembles decision/control architecture structurally. It is not a formal control system: no plant, feedback law, objective function, stability criterion, or controller is implemented.

## Section 14 — Rejected Mathematical Analogies

| Rejected analogy | Why tempting | Missing required structure | Better engineering description |
|---|---|---|---|
| Vector space / orthogonal decomposition | Semantic and trust records contain multiple independent-looking dimensions | Scalars, vector addition, scalar multiplication, basis, inner product | Typed product record; separation of responsibility |
| Category theory / functor | Architecture uses objects, arrows, pipelines, and mappings | Defined category, identity morphisms, closed composition, preservation or commutative law | Ordinary function and pipeline composition |
| Markov process | Agent outputs affect future states and context | Random variables, time index, transition kernel, Markov property | History-dependent propagation and feedback-risk analogy |
| Sufficient statistic | Snapshot compresses an accepted-history prefix | Inferential target and conditional-information sufficiency property | Versioned derived-state checkpoint with authority fallback |
| Information theory | Snapshots compress and hashes shorten payloads | Entropy, mutual information, channel, coding or uncertainty model | State compression and cryptographic integrity digest |
| Lattice | Trust and status vocabularies contain multiple values | Meet/join operations and lattice laws | Finite classifications or product of classifications |
| Fixed-point convergence | Replay repeatedly applies a reducer and reaches a stable result | Iterative limit process, metric/order, fixed-point equation, convergence proof | Finite deterministic fold |
| Formal control system | Stage 4 separates observations, interpretation, policy, and action | Plant, controller, feedback law, objective and stability analysis | Governance pipeline with decision boundaries |
| Projection as linear projection | The Read-side uses the word `projection` | Vector space, linear map, subspace, idempotent linear operator | Derived read-model reducer |

## Section 15 — Mathematical Reading Paths

### Path 1 — State, Transition, and Invariants

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Predicates and invariants | Initial state, legal commands, amount rules, `PAID` invariant, replay |
| 2 | [Transition-first Decision Note](../../domain/decision_note_transition_first_then_domain_invariants.md) | Necessary versus sufficient | Domain legality versus transition truth and admission continuity |
| 3 | [Transactional Core](../../architecture/transactional_core.md) | State-transition system | Rehydration, candidate creation, accepted application |
| 4 | [Aggregate Boundary](../../boundary_notes/aggregate_module.md) | Reachable state | Command decision versus deterministic `apply` |
| 5 | [Action Path Admission](../../semantic_admission/action_path_admission.md) | Trace predicate | Why equal terminal states need not have equal admissibility |

### Path 2 — Ordering, Concurrency, and Causality

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [ADR 0010](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | Independent properties | Atomicity versus next-position admission |
| 2 | [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | Restricted product | Supported and unsupported timing combinations |
| 3 | [ADR 0012](../../adr/0012_two_phase_concurrency_admission.md) | Causal sequence | Stream preparation versus final append |
| 4 | [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Partial order / per-key progress | Aggregate-local exact-next completeness versus global lineage/scheduling coordinate |
| 5 | [Global-source Boundary Postmortem](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Coordinate scope | Global uniqueness versus local composite uniqueness |
| 6 | [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md) | History-relative validity | Why a technically serializable action may be semantically obsolete |

### Path 3 — Replay, Reduction, and Reconstruction

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [Projection Pipeline](../../architecture/projection_pipeline.md) | Deterministic fold | Ordered accepted events and canonical reducer |
| 2 | [Projection Module Boundary](../../boundary_notes/projection_module.md) | Transition-function boundary | Reducer versus worker/storage responsibility |
| 3 | [Durable Replay Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Fold and equality | Expected replayed state versus persisted projection |
| 4 | [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md) | Prefix decomposition | Snapshot state plus accepted tail |
| 5 | [Snapshot-assisted Replay Validator](../../implementation_notes/stage_3_5d/projection_snapshot_assisted_replay_validator.md) | Dual reconstruction | Snapshot-assisted result versus full replay |

### Path 4 — Evidence, Classification, and Formal Logic

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Product-like classification | Separate semantic dimensions and evidence |
| 2 | [Runtime Technical-status Mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Partial deterministic function | Supported status domain and mapping families |
| 3 | [Read-side Outcome Mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Many-to-one mapping | Shared semantic code with distinct evidence boundaries |
| 4 | [Write-side Outcome Mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Case partition | Admission evidence classes |
| 5 | [Semantic Mapping Stability Note](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Mapping invariance | Reviewable semantic evolution |
| 6 | [Retry Reason Classification](../../architecture/retry_reason_classification.md) | Product classification | Retry class, safety, and intent consistency; preserve planning status |

### Path 5 — Exact Representation and Integrity

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [ADR 0006](../../adr/0006_use_decimal_for_money_values_before_durable_persistence.md) | Exact decimal arithmetic | Why float is rejected before durable persistence |
| 2 | [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Exact domain equality | Positive amount and full-payment predicates |
| 3 | [Write-side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Durable numeric constraints | SQL numeric representation and physical evidence |
| 4 | [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Canonicalization function | Decimal scale, canonical JSON, hash scope, bounded digest meaning |

### Path 6 — Agent Uncertainty and Governance — analogy-aware

| Order | Document | Mathematical lens | What to inspect |
|---:|---|---|---|
| 1 | [Agent Pipelines as a Stochastic Process](../../semantic_admission/agent_pipelines_as_stochastic_process.md) | Weak propagation analogy | The explicit caveat and missing stochastic-process primitives |
| 2 | [Retry Is Not Intent Preservation](../../semantic_admission/retry_is_not_intent_preservation.md) | Identity/meaning equivalence | Why repeated attempts may change semantic intent |
| 3 | [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md) | History-dependent validity | How a candidate changes meaning after competing acceptance |
| 4 | [ADR 0007](../../adr/0007_separate_semantic_correctness_from_operational_trust.md) | Proposed multi-axis evaluator | Why trust dimensions are not vectors |
| 5 | [Runtime SemanticOutcome Boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Observation versus action | Why interpretation must precede policy |
| 6 | [Drift Validation Cost Boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Evidence versus optimization | Why cost measurements do not select behavior |

## Section 16 — Mathematical Lens by Engineering Area

| Engineering area | Strongest mathematical structures | Representative documents | Learning value |
|---|---|---|---|
| Foundations and Authority Model | Predicates, transition functions, accepted-set membership, ordered history | [Transactional Core](../../architecture/transactional_core.md); [Order Domain Rules](../../domain/order_domain_v1_rules.md); [ADR 0008](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Separates candidate identity, transition meaning, and accepted authority. |
| Write-side | State transitions, exact arithmetic, idempotency, version order, restricted configuration relation | [ADR 0003](../../adr/0003_concurrency_idempotency_and_retry_safety.md); [ADR 0006](../../adr/0006_use_decimal_for_money_values_before_durable_persistence.md); [ADR 0011](../../adr/0011_validation_mode_vs_validation_placement.md) | Shows that domain legality, retry identity, validation, concurrency, and transaction atomicity are distinct obligations. |
| Read-side / Projection | Deterministic fold, partial order, per-key exact-next progress, equality validation | [Projection Pipeline](../../architecture/projection_pipeline.md); [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md); [Durable Replay Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Explains durable derived state without granting it accepted authority or claiming a global committed prefix. |
| Snapshot Trust | Prefix decomposition, lineage tuple, canonicalization, comparison predicate | [Snapshot Trust Contract](../../architecture/snapshot_trust_contract.md); [Snapshot Schema Baseline](../../implementation_notes/stage_3_5d/projection_snapshot_schema_baseline.md); [Snapshot Payload Hashing](../../implementation_notes/stage_3_5d/snapshot_payload_hashing.md) | Clarifies acceleration and integrity without sufficient-statistic or information-theory claims. |
| Durable History / Permission | Allow/deny relation and temporal append-only safety | [Durable History Permission Boundary](../../boundary_notes/durable_history_permission_boundary.md) | Separates physical mutation enforcement from semantic admission and business authorization. |
| Stage 4A | Product-like semantic contract, partial mappings, mapping invariance, observation/action separation | [SemanticOutcome Result Contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md); [Runtime Technical-status Mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md); [Mapping Stability Note](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Supports completeness and compatibility review without turning outcomes into action. |
| Stage 4B | Typed governance-evidence record, identity/correlation coordinates, path-level classification, strict representation | [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md); [DecisionReceipt Runtime Contract](../../implementation_notes/stage_4b/decision_receipt_contract.md); [DecisionReceipt Persistence](../../implementation_notes/stage_4b/decision_receipt_persistence.md) | Completed receipt mapping, serializer v1, and explicit persistence preserve bounded evidence without automatic materialization, policy, trace, retry, or action. |
| Semantic Admission | Trace predicates, competing transitions, identity/meaning cases, propagation analogy | [Action Path Admission](../../semantic_admission/action_path_admission.md); [Semantic Concurrency](../../semantic_admission/semantic_concurrency.md); [Retry Is Not Intent Preservation](../../semantic_admission/retry_is_not_intent_preservation.md) | Makes final-state insufficiency, history-relative validity, and retry meaning explicit while rejecting unsupported stochastic formalization. |

## Section 17 — Open Questions and Important Reading Notes

- Should state-transition and fold vocabulary become explicit project terminology, or remain an optional explanatory lens?
- Should aggregate-local order and the distinct global lineage/scheduling coordinate receive additional formal order terminology beyond ADR 0020?
- Should Stage 4A mappings later be versioned explicitly as partial functions over supported evidence domains?
- Should action-path admission receive a formal trace semantics?
- Is the stochastic-agent material only a metaphor, or a seed for a future probabilistic model with explicit random variables, time index, and dependence assumptions?
- Should Snapshot Trust use prefix-decomposition notation to clarify snapshot-plus-tail replay?
- Should any current correspondence become a tested formal invariant rather than remain explanatory navigation?
- Which mathematical vocabulary belongs in public-facing documents without obscuring the engineering boundary?
- Which additional Stage 4B invariants, if any, warrant a future bounded mathematical treatment without turning navigation into contract authority?

These questions do not create mathematical or architectural commitments. Any formalization remains subject to explicit project-owner review.
