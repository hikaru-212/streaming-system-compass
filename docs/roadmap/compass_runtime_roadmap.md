# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the **Compass runtime evolution path**.

It intentionally does not repeat the full implementation roadmap or preserve PR-level execution history.

For project-wide implementation sequencing, see:

- [Implementation Roadmap](implementation_roadmap.md)

For completed and current stage execution notes, see:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)
- [Stage 4B Implementation Notes](../implementation_notes/stage_4b/)
- [Stage 4B.3 Implementation Notes](../implementation_notes/stage_4b_3/)
- [Stage 4B.5 Implementation Notes](../implementation_notes/stage_4b_5/)
- [Stage 4C Implementation Notes and Closeout](../implementation_notes/stage_4c/)

This document focuses on a narrower question:

> How does Compass evolve from write-side semantic validation into runtime semantic validation, structured outcomes, runtime decisions, action safety, and dual-dimension governance?

In other words, this roadmap is about the semantic control layer, not the full project build plan.

---

## Scope Boundary

The implementation roadmap answers:

> What should be built, and in what order?

This Compass runtime roadmap answers:

> How does Compass become more capable as a runtime semantic control layer?

The two roadmaps overlap around Stage 3.5B, Stage 3.5C, Stage 3.5D, and Stage 4
because Compass builds on durable write-side, durable read-side, and completed
actor / permission boundaries. Stage 3.5D supplies optional snapshot reference
infrastructure; ADR 0021 confirms that the current Order workload and generic
Stage 4 governance do not depend on it.

However, this document avoids repeating detailed schema columns, migrations, store test matrices, and PR-level implementation history.

Those belong in the implementation roadmap and implementation notes.

This document instead tracks how those stages support the next Compass capabilities.

---

## Terminology Note: Compass Phases vs Project Stages

This document uses **Phase** to describe the focused evolution of Compass as a runtime semantic control layer.

The broader implementation roadmap uses **Stage** to describe project-wide build sequencing.

These two terms are intentionally related but not identical:

```text
Compass Phase = semantic-control capability progression
Project Stage = repository-wide implementation milestone
```

For example:

- Compass Phases 1–3 correspond to the current write-side validation and durable persistence dependencies across Stage 2, Stage 3, Stage 3.5B, and Stage 3.5C, with Stage 3.5D retained as optional replay-efficiency reference infrastructure.
- Stage 3.5E provides the completed minimal actor / permission boundary before broader runtime governance.
- Stage 4A provides the completed `SemanticOutcome` core for runtime semantic interpretation.
- Compass Phase 4 maps to Stage 4 runtime semantic governance.
- Compass Phase 5 maps to the Stage 5 action safety / dual-dimension governance demo.
- Compass Phase 6 maps to later production and agent-facing hardening.

The phase labels in this document should therefore be read as a Compass-specific capability path, not as a replacement for the project-wide Stage numbering in the implementation roadmap.

---

## Current Compass Position

Compass currently has a working Layer 1 baseline.

Layer 1 protects the write-side accepted-history boundary:

```text
candidate event
→ transition-truth validation
→ ALLOW / BLOCK
→ only allowed event can reach accepted history
```

The project has completed the durable baselines and optional replay-efficiency
reference infrastructure developed before Stage 4:

```text
Stage 3.5B = durable write-side baseline
Stage 3.5C = durable read-side baseline
Stage 3.5D = optional read-side snapshot trust / replay-efficiency baseline
```

This means Compass is already more than a passive checker.

It already has runtime control authority at the write-side boundary:

```text
invalid candidate event
→ blocked before accepted history
```

Stage 3.5B extended that authority into the durable PostgreSQL-backed write-side path:

```text
candidate event
→ Compass Layer 1 validation
→ append accepted event + record idempotency in one transaction
```

Stage 3.5C established the durable read-side target, and ADR 0020 repaired its completeness boundary:

```text
accepted history + per-order progress
→ exact-next eligible event source
→ canonical reducer
→ durable projection state
→ durable per-order progress
```

`global_position` remains lineage and deterministic scheduling evidence, not a
global completeness cursor.

Stage 3.5D added the snapshot trust / replay-efficiency substrate:

```text
projection snapshot
+ tail replay
→ validation against accepted-history replay
→ externally qualified snapshot-assisted state resolution
```

Stage 3.5E then added the durable permission and minimal actor boundary:

```text
accepted history permission hardening
+ derived-state controlled mutation
+ minimal producer metadata
→ cleaner Stage 4 receipt / governance foundation
```

Stage 4A then added the first Compass Layer 2 semantic interpretation boundary:

```text
technical runtime evidence
→ SemanticOutcome
```

Stage 4B then completed the DecisionReceipt contract, mappings, strict
serialization, and explicit PostgreSQL persistence foundation. Stage 4B.1 then
completed producer-specific diagnostic and resolution trace boundaries while
keeping traces separate from receipts. Stage 4B.2 then completed
producer-specific measurement, controlled comparison, explanatory
characterization, and bounded concurrency evidence. Stage 4B.3 is complete and
closed as not currently justified after PR1 responsibility-boundary work, PR2 executable
mechanics characterization, and an accepted architecture-necessity audit. PR3
and later Stage 4B.3 implementation work do not proceed. Stage 4B.5 is complete
after separately owned parallel work delivered the Order correctness
contract, exact FullProof evidence path, runtime/write-side propagation,
terminal semantic refinement, deterministic YAML projection, and bounded
overhead characterization. The Stage 4B.3 closeout did not move, redefine,
block, or sequence it.

Stage 4C is complete and closed. PR1 established the source-grounded
implementation-entry boundary; PR2 delivered the generic immutable
`RuntimeDecision` contract and first Layer-1 PostgreSQL / Order write-side
profile; Stage 4C.5 completed compatibility review and repository
reconciliation. Stage 4D retains a valid Strategy Selection Authority
responsibility, but implementation is deferred under ADR 0028. Stage 4E PR0
establishes Same-Request Re-Invocation Authority and accepts preparation
`LOCK_TIMEOUT` as the first formal positive profile; the production contract
remains unimplemented.

---

## Current Runtime-Decision Boundary

Compass implements one reviewed Runtime Decision Authority profile over live
Layer-1 PostgreSQL / Order semantic observations. It does not implement a
universal policy or a Layer-2 / snapshot profile.

The current evidence foundations cover bounded write-side observations,
read-side / derived-state observations, and source-applicable exact correctness
rule evidence. Stage 4A maps eligible observations into `SemanticOutcome`;
Stage 4B provides explicit durable governance-evidence foundations; and Stage
4B.5 provides terminal exact-rule refinement where supported.

The generic Stage 4C responsibility and output remain producer- and
domain-neutral. Its first concrete profile is live, in memory, caller-owned,
and Layer-1 PostgreSQL write-side:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ required live SemanticOutcome
+ source-applicable terminal exact OrderRuleViolationEvidence
→ evaluate_postgres_write_side_runtime_decision
→ RuntimeDecision or typed refusal
→ caller-owned current-response use
```

That implemented profile supports using a completed current result, returning
a prior accepted result, blocking current continuation, and requiring
escalation. `CONCURRENCY_UNCERTAIN` remains unsupported: it produces typed
refusal and never implicit allow.

Existing Layer-1 and Layer-2 producer families already share the
producer-neutral `SemanticOutcome` structural contract. Compatibility does not
mean identical producer evidence, `RuntimeDecision` policy, or caller behavior.
Layer-2 and snapshot families have no concrete production current-response
caller, guarded action requiring Stage 4C authority, reviewed response rules,
or demonstrated need for a generic cross-layer evaluator.

Projection mismatch, replay validation, and snapshot-assisted observations
remain valid read-side evidence families. They do not define the entire Stage
4C governance problem.

Stage 4B.2 answered the next bounded question after execution topology was
preserved:

> What did one current PostgreSQL write execution strategy cost, how do the two
> current correctness-preserving compositions compare under controlled work,
> and how does that comparison change under bounded contention?

That interpretation began in Stage 4A through `SemanticOutcome` mapping and
continued through the completed Stage 4B receipt foundation and Stage 4B.1
execution-topology evidence. Measurement remains descriptive. Strategy
Selection Authority, conditional Same-Request Re-Invocation Authority, rate
admission, and Stage 5 action safety remain separate work. Runtime Decision
Authority is complete and closed within its first reviewed profile.

---

## Snapshot Substrate Status

Stage 3.5D has completed the read-side projection snapshot trust substrate and explicitly deferred write-side aggregate snapshot implementation.

Under [ADR 0021](../adr/0021_projection_snapshots_are_optional_for_current_order_workload.md),
this remains bounded reference infrastructure rather than a current Order
workload or generic Stage 4 dependency. ADR 0026 keeps further snapshot-specific
continuation closed until a concrete workload or consumer justifies it.

Completed baseline:

```text
PR1   — Snapshot Trust Contract Boundary
PR1.5 — CI Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
```

The important boundary is:

```text
read-side projection snapshot
= derived state compression / replay-efficiency support

write-side aggregate snapshot
= command admission path optimization / stricter trust problem
```

Projection snapshots can support read-side resolution when externally qualified.

Aggregate snapshot schema / store work and snapshot-assisted write-side rehydration remain deferred because stale or corrupted aggregate snapshots could influence future accepted-history admission.

Detailed Stage 3.5D execution notes live in:

- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)

---

## Compass Evolution Principle

Compass should evolve from stable truth and evidence foundations into separate
governance responsibilities:

```text
write-side event truth
→ durable accepted history
→ durable derived state
→ minimal actor / permission boundary
→ structured semantic outcomes

selected observations
→ DecisionReceipt / DiagnosticTrace / Measurement Evidence as applicable

live SemanticOutcome + applicable exact rule refinement
→ completed Stage 4C current-response decision or refusal
→ caller handling

eligible prior-invocation evidence
→ Stage 4E authorization or refusal when another invocation of the same complete RequestSignature is considered

if another invocation is authorized
→ Stage 4D selects HOW only if multiple eligible strategies exist
→ execution
→ fresh result
→ Stage 4C handling when applicable

optional snapshot trust / replay-efficiency infrastructure
= derived-state reference path, not accepted authority or a Stage 4 prerequisite
```

The key principle is:

> A semantic failure should not only be detected.  
> It should become explicit enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.

---

# Phase 1 — Layer 1 Write-Side Validation

## Goal

Protect accepted history before invalid facts enter the event log.

## Already Established

Compass Layer 1 checks whether a candidate event truthfully follows accepted history.

Examples:

```text
INIT → CREATED  allowed
CREATED → PAID  allowed
INIT → PAID     blocked
```

Layer 1 currently protects:

- transition truth
- claimed previous state
- claimed previous version
- candidate event consistency
- accepted-history entry

## Runtime Meaning

Layer 1 is already a runtime control boundary.

It does not merely record that an event is invalid.

It prevents invalid history from being written.

```text
invalid semantic transition
→ BLOCK
→ no accepted event
```

## Current Status

Implemented at baseline level.

Stage 3.5B preserves Layer 1 inside the PostgreSQL-backed transactional write-side flow.

---

# Phase 2 — Durable Write-Side Dependency

## Why Compass Needs This

Layer 1 protects accepted history, but accepted history must become durable before later runtime validation can be trusted across restart, retry, and partial failure.

Stage 3.5B provides this dependency.

Detailed PR-level execution history lives in:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)

## Compass-Relevant Outcomes

Stage 3.5B gives Compass:

- durable accepted history
- durable event identity
- durable replay source
- durable idempotency result memory
- transactionally coordinated event append and idempotency record write
- Compass Layer 1 preserved before durable accepted-history mutation
- clear candidate / accepted identity boundary
- PostgreSQL-backed two-phase concurrency admission
- validation placement strategy
- minimal `PRE_TRANSACTION` validation path guarded by append-time admission

## Current Status

Completed at the durable write-side baseline level.

---

# Phase 3 — Durable Read-Side Dependency

## Why Compass Needs This

Layer 2 validation requires a durable read-side target.

To detect projection drift, Compass needs to compare:

```text
expected state from accepted-history replay
vs
persisted projection state
```

If the projection state exists only in memory, the validation is useful but not yet durable enough for stronger runtime governance.

Stage 3.5C provides this dependency.

Detailed PR-level execution history lives in:

- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)

## Compass-Relevant Outcomes

Stage 3.5C originally gave Compass:

- durable projection state schema
- durable checkpoint state schema
- PostgreSQL-backed projection state store
- PostgreSQL-backed checkpoint store
- global-position accepted-history consumption
- PostgreSQL-backed projection worker orchestration
- projection-state and checkpoint-progress atomic persistence
- durable replay / rebuild validation

ADR 0020 supersedes the scalar completeness model for the current order-state
projection. The repaired worker discovers exact-next events from accepted
history plus `projection_order_progress` and commits state with per-order
progress atomically. Global position is lineage and scheduling evidence only.

## Runtime Meaning

Read-side state is not source of truth.

It is derived state.

Compass Layer 2 should eventually verify whether derived state remains faithful to accepted history.

```text
accepted history = truth source
projection state = derived runtime view
Layer 2 = truthfulness check for derived state
```

## Current Status

Completed at the durable read-side baseline level.

---

# Stage 3.5D Reference Infrastructure — Snapshot Trust Contract / Replay Efficiency

Stage 3.5D is complete at the read-side snapshot trust / replay-efficiency baseline level.

It does not implement Layer 2 validation itself.

Instead, it provides optional replay, rehydration, and recovery infrastructure.
The current Order workload does not require snapshots for business correctness,
reads, restart, completeness, or current replay performance.

Stage 3.5D treats snapshots as derived state-compression artifacts:

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
```

The purpose is to reduce replay, rehydrate, and rebuild cost without allowing snapshots to replace accepted history.

The Stage 3.5D trust model is:

```text
fast path = externally qualified snapshot + tail replay
authority path = full accepted-history replay
```

Compass-relevant outcomes include:

- projection snapshot lineage back to accepted history
- projection snapshot support for read-side replay efficiency
- snapshot-assisted replay validation against accepted-history replay
- snapshot-assisted state resolution from an externally qualified snapshot id
- explicit aggregate snapshot deferral until write-side trust prerequisites are stronger
- fast-path vs authority-path distinction
- future replay cost measurement through receipts / runtime evidence records

Detailed execution notes live in:

- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)

Stage 3.5D should remain persistence / replay hardening.

It should not absorb structured semantic outcomes, Runtime Decision Authority,
action safety, or dual-dimension governance.

---

# Stage 3.5E Completed Dependency — Minimal Actor / Permission Boundary

Before Compass entered stronger runtime-governance work, the system established
a minimal actor / permission boundary.

```text
Stage 3.5E — Minimal Actor / Permission Boundary
```

At that checkpoint, this stage did not implement Layer 2 validation, structured
semantic outcomes, runtime decision policy, full RBAC, login/session handling,
or benchmarking.

Instead, it clarifies who or what is allowed to produce validation, snapshots, receipts, decisions, rebuilds, and privileged operations.

Compass depends on this distinction because later runtime governance will treat accepted history as durable evidence:

```text
accepted history = source of truth / durable evidence
projection state = derived runtime view
checkpoint = operational progress metadata
```

Stage 3.5E therefore defined minimal actor semantics before later Stage 4
evidence needed fields such as `created_by`, `validated_by`, `decision_by`,
`receipt_by`, or `triggered_by`.

Compass-relevant outcomes include:

- system / admin / operator / test actor semantics
- privileged operation boundary documentation
- created_by / future validated_by / decision_by metadata alignment
- optional database role boundary documentation
- accepted-history tables protected from casual `UPDATE` / `DELETE` where appropriate
- read-side tables left mutable for upsert, resume, reset, and rebuild
- stronger confidence that later Layer 2 receipts can identify who or what produced evidence

Stage 3.5E remains the completed minimal actor / permission hardening baseline.

It did not absorb Layer 2 validation, `SemanticOutcome`, runtime decision
policy, action safety, or dual-dimension governance.

---

# Phase 4 — Runtime Semantic Governance

## Goal

Phase 4 describes how Compass evolves from bounded write-side and read-side
semantic evidence into separately owned runtime governance responsibilities.

Stage 4A and Stage 4B provide semantic interpretation and durable evidence
foundations. Stage 4C now provides the closed generic current-response contract
and first reviewed Layer-1 PostgreSQL / Order profile. Stage 4E PR0 now defines
the first formal same-request boundary while production implementation remains
next; Stage 4D responsibility is retained and implementation is deferred.

The high-level flow is:

```text
technical evidence
→ SemanticOutcome

durable evidence path:
SemanticOutcome
→ DecisionReceipt as separately persisted durable governance evidence

generic live decision responsibility:
eligible current SemanticOutcome
→ completed Stage 4C current-response RuntimeDecision or refusal
→ caller handling

first concrete Layer-1 PostgreSQL / Order profile:
required SemanticOutcome
+ terminally applicable exact OrderRuleViolationEvidence when source-applicable
→ generic current-response RuntimeDecision meaning

when another invocation of the same complete RequestSignature is being considered:
eligible prior-invocation evidence
→ Stage 4E authorization or refusal

if another invocation is authorized:
→ Stage 4D selects HOW only if multiple eligible strategies exist
→ execution
→ fresh result
→ Stage 4C handling when applicable

DiagnosticTrace and measurement
= optional supporting evidence for concrete later consumers
```

---

## Core Boundary

Compass Phase 4 preserves four distinctions:

```text
technical status
≠
semantic outcome

semantic outcome
≠
runtime decision

runtime decision
≠
execution strategy

runtime decision
≠
retry authorization

retry authorization
≠
retry execution

retry attempt
≠
same intent
```

This prevents raw validator results, exception strings, retry counters, or fast-path health signals from being treated as complete governance decisions.

---

## Capability Path

Phase 4 roughly maps to Stage 4 in the implementation roadmap.

The capability path is:

1. define runtime semantic outcome vocabulary
2. record decision evidence at receipt level
3. preserve detailed failure diagnostics separately
4. make cost / timing evidence observable
5. close projection trust continuation when no additional correctness need or
   consumer is demonstrated, while keeping order correctness references as
   separately owned foundation work
6. convert eligible semantic outcomes into reviewed runtime decisions —
   complete for the first Layer-1 profile
7. confirm Layer-1 / Layer-2 structural compatibility and close Stage 4C —
   complete
8. retain strategy-selection responsibility and defer implementation until
   dynamic `HOW` selection is required
9. authorize and constrain another invocation of the same complete
   `RequestSignature` — PR0 boundary established / production unimplemented

Here, same request means structural equality of the complete
`RequestSignature`, including `request_id`, `command_type`, `order_id`, and
`amount`:

```text
same complete RequestSignature
= same request

same request_id alone
!= same request
```

Stage 4B.2 is complete and closed after producer-specific write-side
measurement semantics, controlled PostgreSQL strategy comparison, explanatory
characterization, and bounded concurrency evidence. Stage 4B.5 is also complete
and closed; its rule evidence does not authorize retry. Stage 4B.3 is complete
and closed as not currently justified under
[ADR 0026](../adr/0026_projection_trust_continuation_is_not_currently_justified.md):
PR1/PR2 remain reference evidence and PR3+ do not proceed. Stage 4B.5 completed
as separately owned parallel foundation work, independent from Stage 4B.3.
Stage 4B.2 and Stage 4B.5 did not implement policy, strategy selection, retry
governance, or rate admission.

Stage 4C is complete and closed. PR1 supplied the source-grounded entry
boundary; PR2 delivered the generic immutable contract and first Layer-1
PostgreSQL / Order profile; Stage 4C.5 confirmed compatibility through the
producer-neutral `SemanticOutcome` structure without adding Layer-2 or snapshot
policy.

Stage 4B.5 defines 18 stable correctness rules, but exactly six FullProof
`TRANSITION_TRUTH` rules currently have typed runtime producer coverage. Rule
identity and observed rule evidence do not authorize a runtime response or
retry.

[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md)
defines Stage 4C as current-response authority, Stage 4D as strategy selection
inside prior authorization, and Stage 4E as separately owned another-invocation
authority. [ADR 0028](../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md)
retains Stage 4D responsibility while deferring implementation. The accepted
first formal Stage 4E boundary narrows another-invocation authority to one
additional public writer invocation of the same complete
`RequestSignature`. Actual execution remains separate. The completed Stage 4C
delivery is live/in-memory first. Its generic decision responsibility remains
producer- and domain-neutral; the first concrete Layer-1 PostgreSQL / Order
profile requires `SemanticOutcome` and may consume terminally applicable exact
rule refinement. `DecisionReceipt` remains durable governance evidence but is
not required for the live hot path; restart recovery remains a distinct
deferred consumer.

Stage 4D implementation is deferred because current strategy composition is
static, no authorized operation has multiple dynamically eligible strategies,
no reviewed runtime selection rule exists, and a selector would not change
observable behavior. Stage 4E PR0 accepts preparation `LOCK_TIMEOUT` as the
first formal positive profile governing one additional invocation of the same
complete `RequestSignature`. The source audit and bounded PR direction are in
the [Stage 4E implementation notes](../implementation_notes/stage_4e/README.md);
the production contract remains unimplemented.

---

## Runtime Meaning

This phase asks:

> Given a live semantic observation, what generic current response is
> semantically permitted, required, or denied?

Eligible evidence may come from write-side observations, read-side /
derived-state observations, or source-applicable exact correctness-rule
evidence. Projection drift, replay mismatch, and derived-state trust remain
valid examples within the read-side family; they do not define the whole Stage
4C problem.

The generic live decision responsibility remains:

```text
live SemanticOutcome
+ source-applicable terminal exact rule refinement
→ Runtime Decision Authority
```

The implemented production profile is limited to the reviewed Layer-1
PostgreSQL / Order write-side tuples. Read-side and snapshot observations do not
acquire `RuntimeDecision` policy merely because they share this generic
responsibility description.

---

## Public Non-goals

Phase 4 does not claim to complete:

- full production benchmarking
- full observability platform
- full authorization system
- general policy platform
- agent workflow orchestration
- projection delivery layer
- final action safety demo

Those concerns belong to later hardening or Stage 5.

---

# Phase 5 — Action Safety / Dual-Dimension Governance Demo

## Goal

Phase 5 demonstrates how Compass governance can guard externally meaningful actions.

The key relationship is:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

Stage 4 establishes semantic meaning and evidence foundations, then separates
Runtime Decision Authority, Strategy Selection Authority, and conditional Retry
/ Attempt Authorization.

Stage 5 uses those outputs to decide whether an action should execute.

---

## Runtime Meaning

A green technical path is not enough.

An action may still be unsafe if:

- derived state is stale
- projection drift has not been resolved
- snapshot trust is unavailable
- the retry changed semantic intent
- the policy boundary requires escalation
- operational freshness is insufficient for the requested action

---

## Demonstration Direction

The demo should show the matrix:

```text
semantic correct + operational fresh
semantic correct + operational stale
semantic incorrect + operational fresh
semantic incorrect + operational stale
```

This makes visible why technical liveness and semantic correctness are different dimensions.

---

# Phase 6 — Later Governance and Production Hardening

## Goal

Later phases can harden the runtime around production concerns once the semantic governance model is stable.

Possible directions include:

- benchmark suite
- cost-aware admission strategy
- evidence retention policy
- production observability integration
- projection delivery layer if needed
- isolated derived-state runtime
- agent-facing governance boundaries
- broader domain expansion

---

## Final Summary

Compass evolves through the following capability path:

| Phase | Capability |
|---|---|
| 1 | Write-side transition-truth validation |
| 2 | Durable write-side accepted-history protection |
| 3 | Durable read-side plus optional snapshot trust reference infrastructure |
| 4 | Runtime semantic governance |
| 5 | Action safety / dual-dimension governance demo |
| 6 | Later production and agent-facing hardening |

The core principle remains:

```text
accepted history is authority
derived state is useful but subordinate
technical success is not semantic correctness
runtime governance should preserve meaning before optimizing execution
```
