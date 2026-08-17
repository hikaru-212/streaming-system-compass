# Write-side Documentation Index

[← Back to Topic_Indexes Index](README.md)

## How to Use This Index

This is an experimental, topic-based navigation layer for the reviewed Write-side documentation. The existing `docs/` folder structure remains the source for each document's type and development context.

A document may appear under more than one topic when it makes a substantial contribution to each subject. Repetition here indicates navigation value; it does not give the document a new authority level.

This index does not override domain specifications, architecture documents, ADRs, boundary notes, or implementation records. When an older planning document contains a superseded candidate design, later accepted ADRs govern the current interpretation. In particular, historical implementation examples must not be read as current configuration contracts when an accepted ADR says otherwise.

## Write-side Reading Path

| Order | Document | Role | Why read here |
|---:|---|---|---|
| 1 | [Stage 3.5B — Durable Write-Side Baseline](../../implementation_notes/stage_3_5b/README.md) | Stage navigation/status | Start with the completed baseline's scope and its four central responsibility distinctions. |
| 2 | [Aggregate Module](../../boundary_notes/aggregate_module.md) | Boundary note | Establish that the aggregate owns domain legality and candidate-event production, not infrastructure. |
| 3 | [Idempotency Module](../../boundary_notes/idempotency_module.md) | Boundary note | Establish request-level replay and conflict semantics before examining concurrency. |
| 4 | [Concurrency Module](../../boundary_notes/concurrency_boundary.md) | Boundary note | Establish why stale-write admission is separate from legality, validation, and idempotency. |
| 5 | [ADR 0003 — Concurrency Control, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | ADR | Connect request identity, accepted-state freshness, ambiguous-result recovery, and retry-safe classification. |
| 6 | [ADR 0008 — Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | ADR | Learn why a candidate can have an identity without being an accepted fact. |
| 7 | [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | ADR | Establish that all-or-nothing persistence and competing-writer admission answer different questions. |
| 8 | [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../adr/0011_validation_mode_vs_validation_placement.md) | ADR | Learn the current accepted validation-placement/admission configuration contract. |
| 9 | [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Learn why entering a protected stream section is distinct from final append-time admission. |
| 10 | [Write-Side Schema Baseline](../../architecture/write_side_schema_baseline.md) and [ADR 0009 — Write-Side Persistence Driver and Identity Generation Boundary](../../adr/0009_write_side_persistence_driver_and_identity_boundary.md) | Architecture and ADR | Finish with the durable schema, explicit persistence boundary, and identity-generation details. |
| 11 | [Write-side Admission Outcome Mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Completed Stage 4A mapping | Follow write-side evidence into typed `SemanticOutcome` without changing admission behavior. |
| 12 | [Write-side DecisionReceipt Mapping](../../implementation_notes/stage_4b/write_side_decision_receipt_mapping.md) | Completed Stage 4B mapping | Follow producer evidence into `DecisionReceipt` without automatic persistence or policy evaluation. |
| 13 | [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Confirm the completed mapping, serialization, explicit persistence, and later-stage non-goals. |

## Write-side Overview and Responsibility Map

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5B — Durable Write-Side Baseline](../../implementation_notes/stage_3_5b/README.md) | Stage navigation/status | Start here | Summarizes the completed durable baseline and its central authority, identity, atomicity, admission, and validation distinctions. | Stage 3.5B is stated to be complete at the durable Write-side baseline level; later hardening and broader governance remain outside its scope. |
| [High-Level Architecture](../../architecture/high_level_architecture.md) | Architecture | Core | Places the transactional core, accepted event history, projections, and Compass validation in the larger system. | Foundational architecture overview; it is not an implementation-completion record. |
| [Transactional Core](../../architecture/transactional_core.md) | Architecture | Core | Explains the command path and separates aggregate decisions, candidate validation, admission, persistence, and replay. | Foundational architecture; preserve its responsibility boundaries when reading later PostgreSQL material. |
| [Compass Layers](../../architecture/compass_layers.md) | Architecture | Deep dive | Distinguishes Layer 1 candidate-transition validation from later layers that operate on accepted history or derived state. | Layer descriptions do not make projections or checkpoints accepted history. |
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Domain specification | Core | Defines the order-domain states and legal transitions whose meaning the Write-side must preserve. | Domain specification; persistence and orchestration do not redefine these rules. |

## Aggregate and Domain Legality

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Aggregate Module](../../boundary_notes/aggregate_module.md) | Boundary note | Start here | Defines the aggregate as the owner of command legality, next transition, sequence progression, candidate production, and event application during replay. | Essential responsibility boundary; no formal ADR status is claimed. |
| [Order Domain v1 Rules](../../domain/order_domain_v1_rules.md) | Domain specification | Core | Supplies the domain states, commands, and legal transition rules applied by the aggregate. | Domain meaning comes from this specification and the core boundary. |
| [Transactional Core](../../architecture/transactional_core.md) | Architecture | Core | Places aggregate rehydration and command decision-making before candidate validation and admission. | Do not collapse aggregate legality into Compass validation or persistence checks. |
| [ADR 0003 — Concurrency Control, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | ADR | Deep dive | Shows that a legal domain decision can still fail freshness admission and must then be classified using latest accepted state. | Accepted; the concurrency and retry-safety baseline is implemented, but later Retry / Attempt Authorization remains separate. |

## Candidate Identity and Accepted History

There is one physical pre-allocated `event_id` for an event-shaped candidate.

Before successful append:

```text
candidate_event_id = event_id
accepted_event_id = None
```

After successful append:

```text
candidate_event_id = accepted_event_id = event_id
```

Accepted authority comes from accepted-history membership, not UUID existence. Cross-attempt candidate identity policy not yet defined.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0008 — Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](../../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | ADR | Start here | Defines the one-UUID lifecycle and the distinct candidate and accepted role names. | Accepted and implemented at baseline level; it does not define cross-attempt reuse or regeneration. |
| [Event Store Module](../../boundary_notes/event_store_module.md) | Boundary note | Core | Defines accepted event history as the append-only replay source and excludes rejected candidates from that history. | Essential authority boundary; no formal ADR status is claimed. |
| [Write-Side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Architecture | Core | Maps accepted identities to `order_events` and links successful idempotency results to accepted events. | Stage 3.5B schema baseline; it is not the first conceptual entry point. |
| [ADR 0009 — Write-Side Persistence Driver and Identity Generation Boundary](../../adr/0009_write_side_persistence_driver_and_identity_boundary.md) | ADR | Deep dive | Centralizes candidate identity generation and preserves UUID identity through explicit PostgreSQL persistence. | Accepted and implemented at baseline level; UUIDv7 remains deferred. |
| [Persistence Boundary](../../boundary_notes/persistence_boundary.md) | Boundary note | Deep dive | Explains that persistence preserves accepted facts without defining their business meaning. | Read with the foundation authority model; storage membership grants accepted status only after admission. |
| [Stage 3.5B Write-Side Schema Translation Note](../../boundary_notes/stage3.5B_write_side_schema_translation_note.md) | Planning-era implementation note | Historical/supporting | Preserves the reasoning that translated candidate/accepted identity and append-only expectations into database requirements. | Planning-era companion retained for rationale; later completed schema and accepted ADRs govern current interpretation. |

## Idempotency and Request Identity

The intended high-level order is:

```text
request normalization / semantic fingerprint
-> idempotency classification
-> if MISS, load accepted history
-> rehydrate aggregate
-> build candidate
-> validate
-> admission
-> append
-> atomically persist the successful idempotency result
```

Early classification avoids wasting history loading, replay, candidate construction, and validation on requests already known to be `REPLAY` or `CONFLICT`. It is a cost-saving classification step; durable uniqueness and atomic persistence of the successful result remain the final correctness guarantee.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Idempotency Module](../../boundary_notes/idempotency_module.md) | Boundary note | Start here | Defines request-level duplicate protection, payload-aware replay, and conflict when one request identity is reused with different semantic content. | Essential responsibility boundary; idempotency does not replace legality, validation, or stream continuity. |
| [ADR 0003 — Concurrency Control, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | ADR | Core | Separates request identity from competing-write freshness and covers result recovery after ambiguous completion. | Accepted; establishes the broad retry-safety baseline. |
| [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Core | Places idempotency classification before stream preparation, accepted-history loading, candidate construction, and validation. | Accepted; its ordering avoids unnecessary protected or expensive work. |
| [Write-Side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Architecture | Core | Defines durable successful request-to-accepted-event records, semantic fingerprints, fingerprint versions, and transactional coupling. | The baseline persists successful results; durable conflict-attempt history remains deferred. |
| [Stage 3.5B PR Breakdown](../../implementation_notes/stage_3_5b/pr_breakdown.md) | Implementation history | Historical/supporting | Records the PR3 durable store and PR4 atomic event/result implementation sequence. | Historical implementation detail; it does not replace the boundary note or accepted ADRs. |

## Semantic Validation

Aggregate legality and Compass Layer 1 validation are separate. The aggregate decides whether a command can produce a legal candidate; Layer 1 evaluates whether that candidate truthfully represents the claimed transition before accepted-history mutation.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Compass Layers](../../architecture/compass_layers.md) | Architecture | Start here | Defines Layer 1 candidate-transition validation and distinguishes it from later validation over accepted or derived state. | Foundational layer model; it does not define transaction placement. |
| [Transactional Core](../../architecture/transactional_core.md) | Architecture | Core | Places candidate construction, semantic validation, admission, and persistence as distinct Write-side steps. | Foundation for reading later placement and PostgreSQL decisions. |
| [Aggregate Module](../../boundary_notes/aggregate_module.md) | Boundary note | Core | Defines the domain-legality responsibility that Layer 1 must not absorb. | No formal status; essential conceptual boundary. |
| [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../adr/0011_validation_mode_vs_validation_placement.md) | ADR | Core | Separates validation strength from placement, atomicity, and admission strategy. | Accepted and implemented at baseline level. |
| [Validation Placement Strategy Boundary](../../boundary_notes/validation_placement_strategy_boundary.md) | Planning-era implementation note | Deep dive | Preserves PR6 implementation reasoning for in-transaction and pre-transaction validation paths. | Does not replace ADR 0011; its candidate flows must be read through the later accepted contract and current idempotency ordering. |

## Validation Placement and Admission Strategy

ADR 0011 governs the current configuration contract.

Supported:

- `PRE_TRANSACTION + OPTIMISTIC`
- `IN_TRANSACTION + PESSIMISTIC`

Unsupported:

- `IN_TRANSACTION + OPTIMISTIC`
- `PRE_TRANSACTION + PESSIMISTIC`

`IN_TRANSACTION + OPTIMISTIC` holds a transaction during validation while still allowing the validated basis to become stale before final optimistic admission. `PRE_TRANSACTION + PESSIMISTIC` acquires protection too late to protect the history basis that was already validated. Older candidate examples in implementation planning do not override ADR 0011, and mechanically constructible combinations are not necessarily supported configurations.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../adr/0011_validation_mode_vs_validation_placement.md) | ADR | Start here | Defines the accepted two-composition matrix and explains why the other compositions are unsupported. | Accepted; governs current configuration interpretation. |
| [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | ADR | Core | Establishes that moving validation inside a transaction does not itself provide competing-writer admission. | Accepted and implemented at baseline level. |
| [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Core | Supplies the early-lock and final-continuity mechanism needed by the accepted placement strategies. | Accepted and implemented at baseline level. |
| [Validation Placement Strategy Boundary](../../boundary_notes/validation_placement_strategy_boundary.md) | Planning-era implementation note | Deep dive | Describes the PR6 placement implementation intent and the requirement for append-time admission after pre-transaction validation. | Planning-era flows do not override ADR 0011 or the current early-idempotency ordering. |
| [Stage 3.5B PR Breakdown](../../implementation_notes/stage_3_5b/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR6 sequencing and contains an older candidate API example useful for understanding chronology. | Its `IN_TRANSACTION + OPTIMISTIC` candidate example is not a supported configuration under ADR 0011. |

## Concurrency Admission

Concurrency admission decides whether a writer may occupy the next accepted-history stream position. It does not decide domain legality, semantic trust, request identity, retry policy, or transaction atomicity.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Concurrency Module](../../boundary_notes/concurrency_boundary.md) | Boundary note | Start here | Defines the stale-write invariant and places accepted-state freshness at the persistence/admission boundary. | Conceptual boundary; optimistic version-based control is its baseline example. |
| [ADR 0003 — Concurrency Control, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | ADR | Core | Defines expected-version admission, latest-state reload, and result classification after conditional-write failure. | Accepted; later PostgreSQL ADRs refine the admission mechanism. |
| [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | ADR | Core | Conceptual core for why coordinated commit does not choose among competing writers. | Accepted and implemented at baseline level. |
| [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Core | Mechanism core: `prepare_stream(order_id)` controls entry to a protected section, while `append_if_admitted(...)` controls final stream-position occupation. | Accepted; append-time expected-version checking remains required under pessimistic locking. |
| [PostgreSQL Concurrency Admission Boundary](../../boundary_notes/postgres_concurrency_admission_boundary.md) | Planning-era implementation note | Deep dive | Explains translation from physical PostgreSQL conflicts to stable admission results such as stale write, lock timeout, or infrastructure failure. | PR5 planning language; later ADR and implementation history report the baseline completed. |
| [Event Store Module](../../boundary_notes/event_store_module.md) | Boundary note | Deep dive | Explains the durable stream-continuity boundary underneath admission. | Storage enforcement supplies physical evidence; upper admission vocabulary remains separate. |

## Transaction Atomicity

Transaction atomicity answers whether related durable writes commit or roll back together. It does not answer whether a candidate may occupy the next accepted-history position.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | ADR | Start here | Defines the conceptual split between the all-or-nothing consistency group and competing-writer admission. | Accepted and implemented at baseline level; conceptual core for this topic. |
| [Persistence Boundary](../../boundary_notes/persistence_boundary.md) | Boundary note | Core | Describes durable append and transaction responsibilities without assigning business meaning to storage. | No formal ADR status; read with the foundation authority model. |
| [Transactional Core](../../architecture/transactional_core.md) | Architecture | Core | Places transaction coordination around accepted append and successful idempotency-result persistence. | Foundational architecture; later PostgreSQL documents supply physical details. |
| [Write-Side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Architecture | Core | Defines the event append and successful idempotency result as one transactional consistency group. | Stage 3.5B schema baseline. |
| [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Deep dive | Explains why transaction-scoped pessimistic preparation must remain active through append and commit, while final admission remains separate. | Accepted; rejects `autocommit=True` for transaction-scoped pessimistic protection. |
| [Stage 3.5B PR Breakdown](../../implementation_notes/stage_3_5b/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR4 atomicity before PR5 admission, making the implementation chronology explicit. | Historical sequence; not a substitute for ADR 0010. |

## Durable Persistence and Schema

Successful admitted append grants accepted-history membership. Persistence preserves that accepted fact durably but does not define its business meaning.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Persistence Boundary](../../boundary_notes/persistence_boundary.md) | Boundary note | Start here | Defines what persistence preserves and what remains the responsibility of domain and semantic boundaries. | Essential boundary; avoids treating storage as the creator of business meaning. |
| [Write-Side Schema Baseline](../../architecture/write_side_schema_baseline.md) | Architecture | Core | Defines `order_events`, `idempotency_records`, stream uniqueness, exact money, evidence separation, and their transactional relationship. | Core schema reference, but not the first conceptual entry point. |
| [Event Store Module](../../boundary_notes/event_store_module.md) | Boundary note | Core | Defines accepted history as append-only, ordered, replayable, and distinct from projection or rejected-candidate state. | No formal ADR status; essential accepted-history boundary. |
| [ADR 0009 — Write-Side Persistence Driver and Identity Generation Boundary](../../adr/0009_write_side_persistence_driver_and_identity_boundary.md) | ADR | Deep dive | Records explicit `psycopg`/SQL persistence, centralized UUID generation, and type/evidence round-trip requirements. | Accepted and implemented at baseline level; not a general ban on other persistence tools. |
| [Stage 3.5B Write-Side Schema Translation Note](../../boundary_notes/stage3.5B_write_side_schema_translation_note.md) | Planning-era implementation note | Historical/supporting | Preserves the translation from Python immutability, exact money, and append-only semantics into database requirements. | Planning-era rationale; role hardening, triggers, and additional audit structures were deferred. |
| [Stage 3.5B PR Breakdown](../../implementation_notes/stage_3_5b/pr_breakdown.md) | Implementation history | Historical/supporting | Records the PR1 schema, PR2 event store, PR3 idempotency store, and PR4 transactional implementation sequence. | Completed implementation history; not architecture authority by itself. |

## Retry-safe Baseline and Failure Classification

**Retry-safe classification and durable replay baseline implemented.**

Stage 3.5B includes durable replay/conflict handling, ambiguous-result recovery, stale-write rejection, stable admission classification, and enough accepted-history and request evidence to avoid treating a stale candidate as accepted.

Retry / Attempt Authorization, retry budgets, backoff or jitter, Strategy
Selection Authority, irreversible-action retry policy, and durable attempt
lineage remain later-stage work. Stable admission results support those later
decisions but do not constitute the complete governed retry model.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0003 — Concurrency Control, Idempotency, and Retry Safety](../../adr/0003_concurrency_idempotency_and_retry_safety.md) | ADR | Start here | Defines request replay, ambiguous-result recovery, stale-write rejection, latest-state reload, and achieved/retryable/conflict classification. | Accepted; uses retry safety in the broad Stage 3.5B baseline sense. |
| [Idempotency Module](../../boundary_notes/idempotency_module.md) | Boundary note | Core | Distinguishes genuine same-request replay from reuse of a request identity with different semantic content. | Request-level retry safety does not replace concurrency or domain correctness. |
| [Concurrency Module](../../boundary_notes/concurrency_boundary.md) | Boundary note | Core | Explains why a stale candidate must not be blindly retried or admitted and why latest accepted state must be reloaded. | Conceptual boundary; automatic retry policy is outside its responsibility. |
| [PostgreSQL Concurrency Admission Boundary](../../boundary_notes/postgres_concurrency_admission_boundary.md) | Planning-era implementation note | Deep dive | Defines stable admission classifications that a future retry policy can consume. | Full retry policy and durable admission-attempt evidence are explicitly deferred. |
| [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md) | ADR | Deep dive | Distinguishes prepare-time lock failure, validation block, append-time stale write, and successful admission. | Accepted; retry policy, attempt persistence, and automatic strategy switching remain future work. |
| [Stage 3.5B — Durable Write-Side Baseline](../../implementation_notes/stage_3_5b/README.md) | Stage navigation/status | Core | Qualifies completion as a durable Write-side baseline rather than complete runtime governance. | Later Stage 4 work may refine retry decisions without making the existing broad baseline definition wrong. |

## Stage 4A / Stage 4B Write-side Mapping

Stage 4A maps bounded write-side admission evidence into typed `SemanticOutcome`. Stage 4B maps supported producer results into `DecisionReceipt`, preserves admission-fate and identity evidence, supports strict serializer v1, and provides explicit caller-owned PostgreSQL receipt persistence. The command/admission path does not automatically construct or persist a receipt, and mapper output does not select policy, retry, strategy, or action.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Write-side Admission Outcome Mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Start here | Defines the completed write-side `SemanticOutcome` adapter and protected identity context. | Stage 4A complete. |
| [Write-side DecisionReceipt Mapping](../../implementation_notes/stage_4b/write_side_decision_receipt_mapping.md) | Implementation boundary | Core | Defines completed producer-specific receipt construction and admission-fate evidence. | Stage 4B complete; mapping performs no persistence. |
| [DecisionReceipt Durable Persistence](../../implementation_notes/stage_4b/decision_receipt_persistence.md) | Implementation boundary | Deep dive | Defines strict serialization, storage-neutral envelopes, and caller-owned PostgreSQL transaction completion. | Explicit operation; no command-path auto-wiring. |
| [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Core | Confirms the completed receipt baseline and deferred runtime governance. | `DiagnosticTrace` / `ResolutionTrace`, policy, retry, strategy, and action remain later work. |

## Implementation History and Planning-era Material

These documents preserve how the Stage 3.5B implementation was planned and delivered. They are valuable for chronology, constraints, and rationale, but older candidate flows do not override later accepted ADRs.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5B — Durable Write-Side Baseline](../../implementation_notes/stage_3_5b/README.md) | Stage navigation/status | Start here | Gives the stage completion boundary and points to the detailed implementation history. | Complete at durable Write-side baseline level. |
| [Stage 3.5B PR Breakdown](../../implementation_notes/stage_3_5b/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves PR1 through PR6 scope, sequence, tests, and non-goals. | Contains older candidate examples; ADR 0011 governs the current placement/admission contract. |
| [Stage 3.5B Write-Side Schema Translation Note](../../boundary_notes/stage3.5B_write_side_schema_translation_note.md) | Planning-era implementation note | Historical/supporting | Records the preimplementation translation from in-memory guarantees to durable schema requirements. | Later completed schema and accepted ADRs provide current status. |
| [PostgreSQL Concurrency Admission Boundary](../../boundary_notes/postgres_concurrency_admission_boundary.md) | Planning-era implementation note | Historical/supporting | Records the intended PR5 vocabulary and physical-error translation boundary. | Uses future-oriented language; later ADRs and implementation history report completion. |
| [Validation Placement Strategy Boundary](../../boundary_notes/validation_placement_strategy_boundary.md) | Planning-era implementation note | Historical/supporting | Records the intended PR6 placement implementation and Stage 4 prelude. | Its late-idempotency `PRE_TRANSACTION` example and mechanically possible mode/placement examples do not override later accepted/current interpretations. |

## Open Questions and Deferred Clarifications

- Cross-attempt candidate identity reuse or regeneration is not yet defined.
- Stage 3.5B retry safety is a baseline; later Retry / Attempt Authorization must remain separate from completed Stage 4A/4B evidence mapping.
- Planning-era documents may retain older candidate flows and must be read together with later accepted ADRs.
