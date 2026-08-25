# Stage 4E Closeout — Same-Request Re-Invocation Authority

[← Back to Stage 4E](README.md)

## Status

```text
Stage 4E
= SAME-REQUEST RE-INVOCATION AUTHORITY
= COMPLETE / CLOSED

PR0–PR6
= complete
```

No additional Stage 4E production implementation is currently justified.
Broader retry, recovery, scheduling, and attempt-governance concerns are not
hidden Stage 4E follow-up work.

## Purpose

This note is the final Stage 4E completion authority. It records the implemented
responsibility, production source and ownership boundaries, reviewed positive
profiles, evidence and experiment disposition, validation map, non-goals, and
transition back to Stage 4 integration.

Stage 4E answers one bounded question:

> Given eligible evidence from one completed invocation and the owner-retained
> same complete `RequestSignature`, may exactly one fresh additional public-
> writer invocation enter?

Stage 4E is not a generic retry framework. Closing it does not assign every
retry-like concern to this stage.

## Final Responsibility

The completed responsibility is consequence-specific another-invocation
authority:

```text
eligible completed-invocation evidence
+ owner-retained complete RequestSignature
→ ReinvocationAuthorization
→ at most one fresh additional public-writer entry
```

Well-typed evidence outside the two reviewed positive profiles produces
`NoReinvocationAuthority`. That result is typed absence of authority, not a
universal or permanent denial.

The final responsibility preserves:

```text
technical status
!= semantic meaning
!= authority

evidence
!= authority

current-response authority
!= another-invocation authority

another-invocation authority
!= execution

fresh invocation
!= resume old attempt

same complete RequestSignature
!= same invocation

issued authority
!= reusable retry budget

Stage 4E
!= generic retry framework
```

## Completed Chronology

| Delivery | Completed responsibility |
|---|---|
| PR0 | Froze Same-Request Re-Invocation Authority as the Stage 4E responsibility and completed the production source audit. |
| PR1 | Implemented the immutable authority/no-authority contracts and the first production-positive preparation `LOCK_TIMEOUT` evaluator profile. |
| PR2 | Implemented `PostgresWriteSideInvocationOwner`, owner-scoped cached evaluation, and atomic one-shot `AVAILABLE → SPENT` before A2 entry. |
| Experiment 1 | Characterized the information value of successive fresh invocations across a competing transaction's resolution boundary without creating production A3 semantics. |
| PR3 | Added Stage 4C current-response custody and delivery through the same owner while preserving Stage 4C/Stage 4E independence. |
| Experiment 2 | Characterized fresh-observation information value after real append-time version mismatch and rollback. |
| PR4 | Preserved typed `AppendVersionMismatchEvidence` for one characterized physical append source without changing authority. |
| PR5 | Added the narrow coherent append-version-advance profile as a second source-specific path to `ReinvocationAuthorization`. |
| PR6 | Closes the stage through documentation reconciliation and responsibility freeze without runtime changes. |

The experiments supplied executable evidence. They did not become production
semantics merely because later production work used findings they supported.

## Final Production Source Map

| Production source | Final Stage 4E responsibility |
|---|---|
| `src/storage/idempotency_store.py` | Defines the frozen complete `RequestSignature`: request ID, command type, order ID, and amount. |
| `src/pipeline/transactional/postgres_write_side.py` | Provides the normal public PostgreSQL writer boundary and trusted completed result consumed by the evaluator. |
| `src/compass/runtime/reinvocation_authority.py` | Defines immutable `ReinvocationAuthorization` and typed `NoReinvocationAuthority`; neither artifact executes or owns lifecycle state. |
| `src/compass/runtime/postgres_write_side_reinvocation_authority.py` | Evaluates exactly the two reviewed source-specific positive profiles. |
| `src/pipeline/transactional/postgres_write_side_invocation_owner.py` | Retains the complete request and configured writer, owns A1 custody, caches evaluation, spends positive authority before A2 entry, and permits no replacement A2 arguments. |
| `src/pipeline/transactional/admission.py` | Defines typed stream/append results and source-specific `AppendVersionMismatchEvidence`. |
| `src/pipeline/transactional/postgres_admission.py` | Translates the characterized storage mismatch into typed admission evidence without parsing diagnostic text. |
| `src/storage/postgres_event_store.py` | Owns the physical expected/current append-version observation. |

No production scheduler, retry loop, attempt log, recovery planner, or dynamic
strategy selector is part of this map.

## Positive Profile 1 — Preparation LOCK_TIMEOUT

The first reviewed positive profile requires:

```text
PostgresWriteSideResult
├── outcome = ADMISSION_REJECTED
├── accepted_event = None
├── idempotency_decision.verdict = MISS
├── idempotency_decision.record = None
├── stream_admission_result.verdict = LOCK_TIMEOUT
├── stream_admission_result.order_id = RequestSignature.order_id
├── validation_decision = None
├── validation_decision_evidence = None
└── admission_result = None

→ ReinvocationAuthorization
```

This is early preparation evidence. Validation and append were not reached, and
A1 produced no accepted effect. Human-readable `reason` text is not policy
input.

## Positive Profile 2 — Coherent Append Version Advance

The second reviewed positive profile requires:

```text
PostgresWriteSideResult
├── outcome = ADMISSION_REJECTED
├── accepted_event = None
├── idempotency_decision.verdict = MISS
├── idempotency_decision.record = None
├── stream_admission_result.verdict = ADMITTED
├── stream_admission_result.order_id = RequestSignature.order_id
├── validation_decision.action = ALLOW
└── admission_result
    ├── verdict = STALE_WRITE
    ├── accepted_event_id = None
    ├── append_version_mismatch_evidence
    │   └── observed_current_version > expected_current_version
    └── candidate_event_id
        = validation_decision.validation_result.candidate_event_id

→ ReinvocationAuthorization
```

Coarse `STALE_WRITE`, missing typed evidence, reverse version inequality,
candidate discontinuity, accepted A1 effects, or otherwise incoherent structure
remains non-authorizing.

## PR4 Evidence and PR5 Authority

PR4 and PR5 own different decisions:

```text
PR4
= retain one physical append fact
= observed_current_version != expected_current_version

PR4 evidence availability
!= ReinvocationAuthorization

PR5
= review one consequence over a coherent completed result
= require observed_current_version > expected_current_version
→ ReinvocationAuthorization
```

The mismatch payload alone does not prove absence of an A1 effect, request
identity, candidate coherence, or authority. PR5 consumes the exact trusted
completed result together with owner-retained request custody and known
write-side control flow.

## RequestSignature Custody

Same-request identity is structural equality of the complete frozen signature:

```text
request_id
+ command_type
+ order_id
+ amount
= complete RequestSignature
```

Same `request_id` alone is insufficient. The evaluator does not reconstruct the
complete request from `PostgresWriteSideResult`.

The owner preserves the binding:

```text
owner retains complete RequestSignature
→ owner dispatches A1 from that signature
→ owner retains the exact A1 result
→ evaluator receives that signature and result
→ A2 accepts no replacement request arguments
→ owner dispatches A2 from the retained signature
```

The same complete request may cross the public writer boundary more than once.
That does not make A1 and A2 the same invocation.

## One-Shot Owner Lifecycle

The completed lifecycle property is:

```text
one A1-derived ReinvocationAuthorization
→ at most one later A2 public-writer entry
```

`PostgresWriteSideInvocationOwner` owns one synchronized in-process lifecycle:

- A1 is invoked once;
- its exact normal result is published and retained;
- Stage 4E evaluation is explicit and cached;
- positive authority is spent atomically before A2 writer entry;
- A2 uses the retained request and writer composition;
- A2 return or exception leaves authority terminally spent;
- no A2 outcome restores availability;
- no automatic A3 lifecycle is created.

The immutable authorization continues to record that authority was issued after
its owner-local spendability becomes spent:

```text
issued authority meaning
!= current spendability
```

## Stage 4C and Stage 4E Independence

Stage 4C owns the current response to one completed result. Stage 4E owns the
separate question of whether another invocation may enter.

```text
Stage 4C refusal
!= Stage 4E authorization
!= Stage 4E refusal

Stage 4E authorization
!= change to A1's current-response result
```

The same A1 may receive a typed Stage 4C refusal and a separately valid Stage 4E
authorization. Neither evaluation is a prerequisite for the other.

The responsibilities do not form a mandatory linear pipeline. When a fresh A2
completes, its result begins a new current-response lifecycle when applicable.

## Fresh Invocation Boundary

`ReinvocationAuthorization` permits one entry through the complete normal public
writer boundary so current authoritative state can be observed.

It does not authorize:

- resuming A1;
- retrying A1's append;
- reusing A1's candidate;
- reusing A1's validation result;
- replay, success, acceptance, or any other business outcome;
- accepted-history mutation outside normal write-side admission.

A2 performs normal idempotency, authoritative-history reconstruction, domain
reasoning, validation, admission, append, and commit as applicable.

## PostgreSQL Characterization

The real PostgreSQL characterizations establish bounded information value:

- after a competing transaction resolves, a later fresh invocation may observe
  authoritative state unavailable to earlier invocations;
- after coherent append version advance, a fresh same-request invocation may
  resolve as real `REPLAY` or may recompute current domain legality and reject;
- neither result is predicted or authorized by issuance itself.

Experiment 1's A3 remains experiment-only. It demonstrates that a fresh later
observation can add information; it does not establish retry count, timing,
polling, or a production A3 lifecycle.

## Mixed-Topology Advisory-Lock Boundary

Topology affects which physical evidence is likely to arise:

```text
PRE_TRANSACTION + optimistic append admission
→ naturally exposed to append version advance

cooperating IN_TRANSACTION + pessimistic writers
→ normally serialize at prepare_stream()
→ contention normally appears as preparation LOCK_TIMEOUT

IN_TRANSACTION + pessimistic A
+ non-cooperating PRE_TRANSACTION + optimistic B
→ B does not honor A's advisory-lock protocol
→ B may advance accepted history
→ A may later observe append version mismatch
```

The mixed-topology characterization does not claim that ordinary cooperating
pessimistic writers normally produce append-time `STALE_WRITE`. PostgreSQL
advisory locks serialize participants that honor the same protocol; they do not
exclude a writer using another composition.

Stage 4E consequence evaluation consumes the reviewed evidence shape, not a
topology label.

## Evidence, Experiment, and Production Semantics

The experiments remain evidence sources and falsifiable characterizations.
Experiment-only wrappers, barriers, observations, monkeypatches, and A3
scheduling do not become production contracts.

```text
experiment observation
!= production evidence contract
!= production authority
```

PR4 promoted only typed physical evidence. PR5 separately promoted one reviewed
consequence over the full coherent production result. No experiment promotes
generic `STALE_WRITE`, exact Python writer identity as a semantic contract, or a
general retry manager.

## Stage 4D Disposition

```text
Stage 4D
= Strategy Selection Authority
= responsibility retained
= implementation deferred under ADR 0028
```

Stage 4E preserves A1's configured composition for A2. It does not select a
different `HOW` and cannot become an implicit dynamic selector.

Stage 4D re-enters only when one already-authorized operation has multiple
dynamically eligible strategies, reviewed selection evidence and rules, and
observable value from choosing among them.

## Limitations and Non-Goals

Stage 4E does not implement or claim:

- generic retry classification or a generic retry framework;
- automatic A2 or A3 scheduling;
- retry loops;
- backoff, jitter, or general retry timing;
- retry budgets or attempt-class limits;
- durable `AttemptLog`, `request_attempts`, `attempt_id`, or `execution_id`;
- candidate-regeneration or semantic-drift policy;
- recovery or reconciliation planning;
- an AI planner;
- restart recovery or cross-process continuation;
- distributed authorization consumption;
- Stage 4D `StrategySelector`;
- application/bootstrap continuation enforcement;
- a general workflow or policy engine.

Any future proposal for those concerns requires its own concrete evidence,
responsibility review, and independently authorized scope.

## Validation

Stage 4E production delivery is protected by focused unit and PostgreSQL
integration coverage for:

- immutable authority and typed no-authority contracts;
- exact preparation `LOCK_TIMEOUT` eligibility and negative shapes;
- exact coherent forward-version eligibility and malformed/incoherent shapes;
- Stage 4C/Stage 4E independence;
- invocation-owner caching, synchronization, and one-shot consumption;
- authority spent before writer entry and terminal spent state after exception;
- real PostgreSQL preparation-time and append-time evidence;
- same-request replay, changed-state rejection, and mixed-topology append
  version advance.

PR6 changes documentation only. Final validation used the original repository
Python environment and established:

- all 490 local Markdown targets found across the 21 authorized files resolve
  inside the workspace;
- remaining stale-language matches are historical, already correct, or
  unrelated rather than current Stage 4E status claims;
- `git diff --check` passes, with the untracked closeout checked separately for
  trailing whitespace;
- the focused Stage 4E authority, owner, append-stale, and real lock-timeout
  integration set passes: 86 tests;
- the full repository test suite passes: 2694 tests.

## Final Stage 4E Invariants

```text
technical status != semantic meaning
semantic meaning != authority
evidence != authority

current-response authority != another-invocation authority
another-invocation authority != execution

fresh invocation != resume old attempt
same complete RequestSignature != same invocation
issued authority != reusable retry budget

Stage 4E != generic retry framework
Stage 4D implementation = deferred
```

## Stage 4 Integration Transition

PR6 merge closes Stage 4E. It does not itself merge Stage 4 to `main`.

The exact integration sequence is:

```text
PR6 merge
→ Stage 4E = CLOSED

feat/stage4e-same-request-reinvocation-authority
→ feat/stage4-runtime-retry-governance

→ final Stage 4 integration validation

feat/stage4-runtime-retry-governance
→ main
```

Only after the updated Stage 4 baseline is in `main` may the separate
post-Stage-4 documentation sequence begin:

```text
create a separate clean documentation branch
→ ADR 0029
→ autonomous-governance experiment
```

ADR 0029 is not created, indexed, promoted, accepted, or merged by Stage 4E
PR6.

## Completion Statement

Stage 4E is complete and closed with two reviewed source-specific positive
profiles, one owner-retained complete-request boundary, and one synchronized
one-shot additional-invocation lifecycle. Evidence remains separate from
authority, authority remains separate from execution, Stage 4C remains
independent, Stage 4D remains deferred, and broader retry/recovery governance
remains outside the closed responsibility.
