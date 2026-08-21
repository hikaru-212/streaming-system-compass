# Stage 4C Closeout

[← Back to Stage 4C](README.md)

## Status

```text
Stage 4C
= COMPLETE / CLOSED

PR1
= source-grounded implementation-entry boundary

PR2
= generic immutable RuntimeDecision contract
+ first Layer-1 PostgreSQL / Order write-side evaluation profile

Stage 4C.5
= bounded compatibility / documentation closeout
```

No additional Stage 4C production implementation is currently justified.

## Completion Statement

Stage 4C is complete and closed with one producer- and domain-neutral
current-response contract, one reviewed Layer-1 PostgreSQL / Order evaluation
profile, typed refusal outside that profile, and exact in-memory
source-feedback reviewability. The stage does not claim automatic production
caller wiring, strategy selection, same-request re-invocation authority, or
execution.

The bounded consumer experiment established that consuming a
`RuntimeDecision` can constrain caller handling of a completed producer result.
It did not establish the experimental runtime owner or its consequence model as
production architecture. Behavioral evidence and mechanism promotion remain
separate decisions.

## Delivery Map

### PR1 — Source-Grounded Implementation-Entry Boundary

PR1 established:

- the live, in-memory, caller-owned first design center;
- the first Layer-1 PostgreSQL / Order write-side profile;
- `PostgresWriteSideSemanticRuleFeedback` as the source-controlled first-profile
  input rather than a universal Stage 4C input contract;
- four reviewed current-response meanings;
- fail-closed treatment of unsupported and incoherent observations;
- the post-return invocation boundary outside write-side transaction and
  admission execution;
- explicit separation from Stage 4D strategy selection, Stage 4E same-request
  re-invocation authority, and execution.

### PR2 — Generic Contract and First Evaluation Profile

PR2 delivered:

- the immutable, producer- and domain-neutral `RuntimeDecision` contract;
- the closed `RuntimeDecisionResponse` vocabulary;
- evaluator-controlled construction with the exact consumed `SemanticOutcome`;
- the first Layer-1 PostgreSQL / Order write-side evaluator;
- the profile-specific read-only evaluation delivery retaining the exact source
  feedback;
- evaluator-specific typed refusal for unsupported or incoherent semantic
  observations;
- focused tests for contract shape, exact tuple mapping, refusal, source
  reviewability, terminal refinement, and dependency boundaries;
- an explicit callable capability with no automatic production caller wiring.

### Stage 4C.5 — Compatibility and Closeout

Stage 4C.5 records that existing Layer-1 and Layer-2 producer families already
share the producer-neutral `SemanticOutcome` structural contract. It closes the
stage through compatibility review and repository reconciliation rather than
new production behavior.

## Exact Production Source Map

PR2 production code is bounded to:

| Path | Responsibility |
|---|---|
| `src/compass/runtime/runtime_decision.py` | Defines the generic immutable `RuntimeDecision` and closed `RuntimeDecisionResponse` vocabulary. |
| `src/compass/runtime/write_side_runtime_decision.py` | Defines the first PostgreSQL / Order profile, its read-only source-feedback delivery, typed refusal, and the four reviewed tuple-to-response mappings. |
| `src/compass/runtime/__init__.py` | Exports the generic contract and first profile through the runtime package boundary. |

The implemented profile depends on previously delivered source boundaries:

| Path | Existing responsibility used by Stage 4C |
|---|---|
| `src/compass/runtime/semantic_outcome.py` | Defines the shared producer-neutral semantic structure used by Layer-1, Layer-2, and snapshot producer mappings. |
| `src/compass/runtime/write_side_rule_feedback.py` | Preserves one exact write-side `SemanticOutcome` plus terminally applicable exact Order-rule refinement. |
| `src/compass/runtime/write_side_outcome_mapping.py` | Maps PostgreSQL / Order write-side results into the shared `SemanticOutcome` contract. |
| `src/compass/runtime/read_side_outcome_mapping.py` | Maps read-side and snapshot observations into the same `SemanticOutcome` contract without creating Stage 4C policy. |

These supporting modules are not additional PR2 delivery claims.

## Exact Focused Test Map

PR2 focused tests are bounded to:

| Path | Proven boundary |
|---|---|
| `tests/unit/compass/runtime/test_runtime_decision.py` | Closed response vocabulary, exact outcome retention, immutability, controlled construction, structural validation, minimal fields, and absence of profile-specific dependencies. |
| `tests/unit/compass/runtime/test_write_side_runtime_decision.py` | Exact four-tuple mapping, explanation boundaries, typed refusal including `CONCURRENCY_UNCERTAIN`, refusal outside the first profile, exact source retention, terminal refinement, non-promotion of text or non-terminal evidence, and absence of writer, strategy, retry, or execution dependencies. |

Existing Stage 4A and Stage 4B.5 tests separately cover the shared
`SemanticOutcome` structure, Layer-1 and Layer-2 producer mappings, and the
write-side rule-feedback carrier. They corroborate compatibility but are not
reclassified as Stage 4C PR2 delivery.

## Stage 4C Invariants

```text
technical status
!= SemanticOutcome
!= exact rule refinement
!= diagnosis
!= RuntimeDecision
!= strategy selection
!= same-request re-invocation authorization
!= execution
```

The closed stage preserves these additional invariants:

- `RuntimeDecision` governs caller handling of one already-completed semantic
  outcome; it cannot retroactively authorize candidate append or transaction
  commit.
- The generic decision contains only a reviewed response, the exact consumed
  `SemanticOutcome`, and non-authoritative explanation text.
- Human text, generic context, and metadata are not parsed to recover policy or
  exact rule identity.
- Exact producer evidence may refine eligible policy input; it is not
  self-authorizing.
- Strategy selection, same-request re-invocation authority, and execution remain
  separately owned.
- A `DecisionReceipt` is governance evidence, not current action authority or
  permanent cross-process authorization.

## Stage 4C.5 Compatibility Disposition

The compatibility verdict is:

```text
Layer-1 producer mappings
+ Layer-2 / snapshot producer mappings
→ compatible producer-neutral SemanticOutcome structural contract

compatible semantic contract
!= identical producer evidence
!= identical RuntimeDecision policy
!= identical caller behavior
```

Layer-1 currently has one reviewed PostgreSQL / Order write-side
`RuntimeDecision` profile. Layer-2, read-side, and snapshot families currently
have no concrete production current-response caller, no guarded action requiring
Stage 4C authority, no reviewed response rules, and no demonstrated need for a
generic cross-layer evaluator.

Stage 4C.5 therefore does not add Layer-2 or snapshot `RuntimeDecision` policy,
rebuild, fallback, or quarantine policy, a universal evaluator, a generic
evidence envelope, automatic caller wiring, or a production consumer created
for symmetry.

## Current Consumer Boundary

The implemented evaluator is an explicit callable capability. The identified
production invocation boundary is after `PostgresTransactionalWriteSide` has
returned a terminal `PostgresWriteSideResult`; a future real caller would own
feedback mapping, evaluation, and handling at that post-return boundary. No
such production caller is currently wired.

The bounded experiment supplied behavioral evidence for this boundary:

```text
completed producer result
→ exact semantic feedback
→ RuntimeDecision or typed refusal
→ caller-visible consequence
```

The experiment did not approve its runtime owner, producer-specific consequence
types, provenance machinery, or orchestration shape for production.

## Refusal Semantics

The first profile issues authority only for its exact four reviewed Layer-1
semantic tuples. An unsupported boundary, unsupported category/code pairing,
otherwise coherent tuple outside the profile, `CONCURRENCY_UNCERTAIN`
observation, or incoherent rule refinement produces
`PostgresWriteSideRuntimeDecisionRefused`. A wrong Python input structure raises
`TypeError`, and source-feedback construction failures propagate.

```text
Stage 4C refusal
= no authoritative RuntimeDecision from this profile
!= BLOCK_CURRENT_CONTINUATION
!= USE_CURRENT_RESULT
!= Stage 4E authorization
!= Stage 4E refusal
```

Refusal is not a fifth positive response and never creates implicit authority.

## Evidence and Refinement Boundary

The first profile consumes one source-controlled
`PostgresWriteSideSemanticRuleFeedback`:

```text
exact SemanticOutcome
+ terminally applicable exact OrderRuleViolationEvidence when applicable
```

The generic decision retains the exact `SemanticOutcome`; the profile-specific
delivery retains the exact source feedback. This preserves reviewability
without copying Order evidence into the generic contract or inventing a generic
evidence bag.

Exact Order-rule refinement is eligible only when validation block is the
terminal write-side outcome. Earlier observations do not automatically become
the cause of a later accepted, replay, conflict, or admission result. Absence of
refinement is not success, permission, or proof that no rule was violated.

## Live, In-Memory and Durability Deferrals

The delivered profile is live and in memory. It does not require receipt
persistence before current-response evaluation. `DecisionReceipt` remains
durable-capable governance evidence, but evidence availability does not create
current action authority or authorize replay of an old action.

The following remain deferred until a concrete lifecycle consumer justifies
them:

- durable `RuntimeDecision` storage;
- independent decision identity and policy identity/versioning;
- automatic receipt materialization;
- cross-process decision reconstruction;
- restart-recovery governance and continuation;
- persistent same-request invocation lineage.

## Stage 4C / 4D / 4E Responsibility Relationship

For one completed result:

```text
current evidence
→ Stage 4C current-response decision or refusal
→ caller handling
```

When another same-request invocation is considered:

```text
eligible prior-invocation evidence
→ Stage 4E authorization or refusal

if another invocation is authorized:
→ Stage 4D selects HOW only if multiple eligible strategies exist
→ execution
→ fresh result
→ Stage 4C handling when applicable
```

Therefore:

```text
Stage 4C refusal
!= Stage 4E authorization
!= Stage 4E refusal

C → D → E
!= mandatory runtime pipeline
```

Stage 4C current-response authority is not a prerequisite for Stage 4E to
evaluate the separate another-invocation question.

## Stage 4D Disposition

```text
Stage 4D responsibility
= valid

Stage 4D implementation
= deferred
```

The deferral is based on observable architecture, not merely consumer absence:

- current write-side strategy composition is statically selected;
- no authorized operation currently has multiple dynamically eligible
  execution strategies;
- no reviewed runtime selection rule exists;
- adding a selector would not change observable behavior.

Stage 4D re-enters implementation only when an authorized operation has
multiple eligible strategies and reviewed evidence and rules can select `HOW`
without creating the underlying authority.

## Stage 4E Transition Direction

Stage 4E is the next formal implementation direction. Experimental evidence
supports bounded same-request public-writer re-invocation authority, but the
first formal slice must be narrower than the experiment.

Preparation `LOCK_TIMEOUT` is the most portable first candidate because the
existing producer-owned result and admission evidence is largely sufficient to
identify the prior invocation condition without promoting experiment-owned
observation lifecycle or writer identity machinery.

This transition does not promote the experimental:

- `PublicWriterInvocationObservation`;
- candidate monkeypatch;
- observation wrappers;
- exact Python writer identity;
- mutable observation-owned lifecycle;
- one-shot consumer;
- `STALE_WRITE` authorization profile.

The first formal Stage 4E profile must independently freeze its eligible
prior-invocation evidence, authorization/refusal meanings, invocation count and
constraints, intent and request-signature continuity, authority refresh rules,
and separation from execution. None of that behavior is implemented by this
closeout.

## Explicit Non-Goals

Stage 4C and this closeout do not introduce:

- Layer-2, read-side, or snapshot `RuntimeDecision` policy;
- snapshot fallback, rebuild, quarantine, or trust-selection policy;
- a universal evaluator or generic evidence envelope;
- automatic caller wiring or a production consumer created for symmetry;
- Stage 4D strategy selection;
- Stage 4E same-request re-invocation authorization or refusal;
- retry execution, backoff, budgets, limits, candidate regeneration, or repair;
- a policy engine, DSL, registry, hot reload, or configuration store;
- durable `RuntimeDecision` or invocation-lineage persistence;
- restart-recovery implementation;
- new producer evidence, correctness-rule coverage, migrations, dependencies,
  writer behavior, or tests;
- promotion of an experimental runtime owner into production architecture.

## Known Limitations

- The only reviewed production evaluation profile covers four Layer-1
  PostgreSQL / Order semantic tuples.
- `CONCURRENCY_UNCERTAIN` and every Layer-2 or snapshot tuple are refused by the
  first profile.
- No production caller currently consumes the decision or handles refusal.
- The generic contract has no independent decision identity, policy version,
  persistence contract, or cross-process provenance.
- Exact Order-rule refinement is limited to terminally applicable evidence from
  the existing six-rule FullProof producer coverage.
- The consumer and same-request re-invocation experiments are evidence, not
  production mechanism approval.

## Downstream Re-Entry Conditions

Stage 4C re-entry requires a concrete current-response demand not covered by the
closed profile. A proposal must identify the producer observation, guarded
caller action, eligible typed evidence, reviewed response rules, refusal
behavior, and exact reason the existing profile or shared `SemanticOutcome`
contract is insufficient.

Layer-2 or snapshot policy additionally requires a concrete production caller
and guarded action. A generic cross-layer evaluator or evidence envelope
requires a demonstrated multi-producer consumer whose shared policy cannot be
expressed through separate reviewed profiles.

Stage 4D and Stage 4E retain their own independent re-entry gates. Closing Stage
4C does not authorize either implementation by sequence alone.

## Final Stage Transition

```text
Stage 4C
= COMPLETE / CLOSED

Stage 4D
= responsibility retained
= implementation deferred
= no current dynamic HOW-selection requirement

Stage 4E
= next formal implementation direction
= bounded same-request public-writer re-invocation authority
= preparation LOCK_TIMEOUT as the most portable first candidate
= formal first slice narrower than the experiment
```

Stage 4C closes without additional production code. Stage 4E remains
unimplemented by this transition record.
