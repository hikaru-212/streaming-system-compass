# Stage 4E PR Breakdown

[← Back to Stage 4E](README.md)

## Purpose

This plan keeps the first formal Stage 4E delivery bounded to same-request
public-writer re-invocation authority. It promotes accepted experimental
behavioral findings without promoting experiment-only mechanisms.

The plan is not a commitment to generic retry governance, durable attempt
tracking, automatic execution, or a long Stage 4E roadmap.

## Authority Boundary

```text
Stage 4C
= current-response authority

Stage 4D
= HOW selection inside prior authorization

Stage 4E
= whether exactly one additional invocation of the same complete request is
  authorized

execution
= separate responsibility
```

The formal same-request identity is structural equality of the complete frozen
`RequestSignature`:

```text
request_id
+ command_type
+ order_id
+ amount
```

## PR0 — Architecture Boundary and Source Audit

### Status

Documented by this PR.

### Responsibility

PR0:

- promotes accepted experiment findings into formal repository reasoning;
- freezes Same-Request Re-Invocation Authority as the first Stage 4E
  responsibility;
- accepts preparation `LOCK_TIMEOUT` as the first formal positive profile;
- defers `STALE_WRITE` from the first production profile;
- identifies the minimum trustworthy production evidence;
- records the missing PostgreSQL invocation-owner/binding seam;
- distinguishes private composition retention from durable writer identity;
- records one-shot, consume-before-entry, spent-on-all-outcomes, and no-A3
  requirements;
- preserves typed refusal as absence of authority rather than fabricated
  denial;
- records Stage 4D implementation deferral in ADR 0028;
- reconciles only current navigation and roadmap language made stale by this
  boundary.

### Source-Audit Result

Current production source provides:

- the complete frozen `RequestSignature` contract;
- a typed `StreamAdmissionResult` owned by stream preparation;
- real preparation `LOCK_TIMEOUT` production in
  `PostgresPessimisticAdmissionGate.prepare_stream()`;
- `PostgresWriteSideResult` fields that preserve preparation evidence
  separately from append evidence;
- a public writer whose construction already fixes the execution composition.

Current production source does not provide:

- complete-signature retention on an A1 `LOCK_TIMEOUT` result;
- a PostgreSQL application/runtime owner above the public writer;
- a formal Stage 4E authorization/refusal contract;
- a one-shot issuance and consumption lifecycle;
- a consumption boundary that binds A2 to the A1-owned composition.

These are bounded missing seams, not reasons to reopen the accepted behavioral
findings.

### PR1 Entry Readiness

No separate production-code or characterization PR is required before PR1.
PR1 can establish the immutable contracts and source-specific evaluator from
existing production-owned typed evidence. It does not need an intermediate
writer-result mutation, test hook, owner, lifecycle, or experiment promotion.

### PR0 Non-Goals

PR0 does not change production code, tests, migrations, dependencies, writer
behavior, database state, or runtime wiring. It does not implement Stage 4E.

## PR1 — Immutable Authority Contract and First Evaluator

### Status

Implemented in Stage 4E PR1.

### Goal

Establish the minimum immutable, live/in-memory contract and evaluation needed
to represent:

- complete same-request identity;
- one eligible producer-owned A1 evidence profile;
- positive authority for one additional invocation of that complete request;
- typed refusal / no authority for unsupported or incoherent evidence.

PR1 does not implement authority ownership or consumption.

### Minimum Input Boundary

The evaluator consumes only:

```text
complete RequestSignature
+ exact A1 PostgresWriteSideResult
```

It should validate the accepted preparation profile through typed fields:

```text
outcome = ADMISSION_REJECTED
idempotency = MISS with no record
stream admission = LOCK_TIMEOUT for RequestSignature.order_id
validation = not reached
append admission = not reached
accepted event = absent
```

Human-readable reason text is not policy input.

### Minimum Output Boundary

Eligible evidence should produce an immutable positive authority that retains
the complete signature.
The authorization artifact must not own or expose a writer, execution callable,
strategy, execution composition, mutable lifecycle state, retry policy, timing,
or persistence identity.

Mutable availability, spent state, and consumption belong to PR2 rather than
the authorization artifact.

Unsupported or incoherent evidence should produce a typed no-authority/refusal
result. It should not produce a universal negative policy decision.

```text
positive authority
or typed absence of authority

not

universal ALLOWED / DENIED policy
```

### Required Unit Characterization

PR1 should characterize at least:

- independently constructed but structurally equal complete signatures count
  as the same request;
- same `request_id` with a changed command, order, or amount is not the same
  request;
- the accepted production `LOCK_TIMEOUT` result shape authorizes;
- append-time `LOCK_TIMEOUT`, `STALE_WRITE`, accepted, replay, conflict,
  validation-blocked, infrastructure, and incoherent A1 shapes receive typed
  refusal in the first profile;
- Stage 4C decision or refusal is not an evaluator prerequisite;
- authorization exposes no execution, strategy, lifecycle, timing, count, or
  persistence capability.

The experiment already supplies behavioral evidence for these boundaries.
PR1 unit characterization targets only the formal source-owned evaluation
seam and does not reproduce its monkeypatch and observation framework.

### PR1 Evidence Exclusions

Do not require the following for the first evaluator:

- `SemanticOutcome`;
- Stage 4C `RuntimeDecision`;
- `DecisionReceipt`;
- diagnostic/execution trace;
- Measurement Evidence;
- exact Order correctness-rule evidence.

Do not create a generic evidence envelope merely to carry them.

### PR1 Non-Goals

PR1 must not introduce:

- `STALE_WRITE` authorization;
- retry taxonomy, backoff, jitter, timing, budget, or attempt-class policy;
- candidate regeneration or validation reuse;
- durable attempt records or lineage;
- restart recovery or distributed consumption;
- dynamic strategy selection;
- writer/strategy identity registries;
- an invocation owner, mutable lifecycle, synchronization, consumption API,
  writer entry, automatic A2 scheduling, retry loops, or A3;
- Stage 4C production consumption;
- Stage 5 action execution or safety policy.

## PR2 — Invocation Owner and One-Shot Consumption

### Status

Implemented in Stage 4E PR2.

### Responsibility

PR2 owns the live PostgreSQL invocation boundary required to make one issued
authorization consumable at most once:

- retain the complete signature, exact A1 result, and configured writer;
- provide one owner-scoped evaluation/issuance cache;
- protect that cache and `AVAILABLE → SPENT` with one synchronization boundary;
- mark authority spent before A2 public-writer entry;
- preserve spent state after every A2 result or exception;
- prevent writer/composition substitution;
- perform no automatic A3.

PR2 adds the real PostgreSQL characterization for preparation `LOCK_TIMEOUT`
followed by one guarded A2 entry. It does not change PR1 eligibility.

The implemented owner accepts only one complete `RequestSignature` and one
already-configured `PostgresTransactionalWriteSide`. It invokes A1 itself,
publishes the exact normal result under one owner-scoped lock, evaluates only
when explicitly requested, and caches the exact authorization or no-authority
object. Positive authority is spent under that same lock before A2 writer
entry; every A2 result or exception leaves it terminally spent. Writer execution
occurs outside the lock, and both invocations use the same retained request and
writer composition.

The PostgreSQL integration characterization uses the concrete
`IN_TRANSACTION` plus pessimistic composition. A real held advisory lock makes
A1 return the accepted early preparation `LOCK_TIMEOUT` shape without reaching
validation. After lock release, explicit one-shot consumption enters the same
writer composition and A2 returns `ACCEPTED`, with one validation call, one
accepted event row, one idempotency row, and no changes after a refused second
consumption.

## PR3 — Stage 4C Production Consumption

### Status

Implemented in Stage 4E PR3 as a production current-response delivery
capability. End-to-end application consumption remains outside this PR.

### Responsibility

PR3 uses the invocation owner established by PR2 to deliver the already-complete
Stage 4C current-response authority for only its currently published normal
result. It implements:

- one stable owner-held `outcome_id` per current result;
- immutable result plus `RuntimeDecision` evaluation or typed-refusal delivery;
- `USE_CURRENT_RESULT`;
- `RETURN_PRIOR_ACCEPTED_RESULT`;
- `BLOCK_CURRENT_CONTINUATION`;
- `REQUIRE_ESCALATION`;
- typed Stage 4C refusal transport;
- exact replay event selection;
- atomic current-response invalidation at A2 start;
- fresh current-response publication after normal A2 completion.

The delivery is explicit and cached; refusal means no authoritative Stage 4C
decision exists and is not a block, denial, or escalation decision. PR3 does
not change Stage 4E eligibility or one-shot lifecycle, retain attempt history,
or add application/bootstrap enforcement.

## PR4 — Append Version-Mismatch Evidence Refinement

### Status

Implemented in Stage 4E PR4.

### Responsibility

PR4 preserves stable typed producer evidence for exactly one characterized
physical stale source:

```text
PostgresEventStore.append(...)
observed_current_version != expected_current_version
→ AppendVersionMismatchError
→ PostgreSQL admission
→ AdmissionResult.append_version_mismatch_evidence
→ PostgresWriteSideResult.admission_result
```

The retained evidence contains only `expected_current_version` and
`observed_current_version`. `AdmissionVerdict.STALE_WRITE` remains unchanged.
The internal storage exception preserves the observation across the storage
boundary but does not escape as the write-side control language.

The distinction is source-specific. Evidence remains absent for candidate
continuity mismatch, generic `ValueError`, generic `StaleWriteError`,
`AppendConflictError`, recognized stream-position `UniqueViolation`, and
manual/coarse `STALE_WRITE` construction.

The existing PostgreSQL experiment retains both deterministic schedules. Its
A1 results now identify the physical source through exact typed version
evidence—`expected=0, observed=1` and `expected=1, observed=2`—rather than
reason text. A1 has no durable accepted effect; a fresh full invocation either
observes the winning request as `REPLAY` or reloads changed authoritative state
and follows current domain reasoning.

### Consequence Boundary

PR4 does not change eligibility:

```text
technical outcome
!= physical evidence
!= semantic interpretation
!= authority
!= execution

completed invocation
+ AppendVersionMismatchEvidence
→ NoReinvocationAuthority
```

The preparation `LOCK_TIMEOUT` positive profile remains exactly as implemented
in PR1. PR4 adds no generic stale authorization, retry taxonomy, execution,
loop, A3, budget, backoff, scheduler, persistence, Stage 4A interpretation, or
Stage 4C behavior.

### PR5 Handoff at PR4 Closeout

PR5 was not implemented by PR4. Its handoff was limited to this open question:

> Given a completed prior invocation with exact characterized append
> version-mismatch evidence, under what additional invariants—if any—may
> exactly one fresh invocation of the same complete `RequestSignature` enter?

No possible additional invariant is an established PR4 rule.

## PR5 — Append Version-Advance Re-Invocation Authority

### Status

Implemented in Stage 4E PR5.

### Responsibility

PR5 adds a second explicit, source-specific positive predicate to the existing
evaluator. It leaves the PR1 preparation `LOCK_TIMEOUT` predicate unchanged and
does not introduce a generic supersession or retry abstraction.

The precise theorem is:

> A completed trusted write-side result showing a coherent append version
> advance, with no accepted A1 effect, may issue authority for exactly one
> fresh invocation of the invocation owner's retained complete
> `RequestSignature`.

Eligibility requires all of:

```text
outcome = ADMISSION_REJECTED
accepted_event = None
idempotency = MISS with no A1-carried record
stream admission = ADMITTED for RequestSignature.order_id
validation action = ALLOW
append admission = STALE_WRITE with no accepted_event_id
append evidence = AppendVersionMismatchEvidence
observed_current_version > expected_current_version
append candidate_event_id = validation candidate_event_id
```

The forward inequality is consequence-specific. PR4 retains physical
`observed != expected` evidence, while PR5 refuses a contract-valid
`observed < expected` shape. Coarse `STALE_WRITE` without the typed evidence
also remains non-authorizing.

This is not a self-contained serialized proof protocol. PR5 relies on the exact
trusted producer result, source-specific evidence, the structural checks above,
and known write-side control flow. The result does not reconstruct every
request field or independently prove that the supplied signature belongs to
A1. Same-request identity comes from the unchanged invocation owner: it retains
the complete signature, dispatches A1 from it, evaluates the exact A1 result
with it, accepts no replacement A2 arguments, and dispatches A2 from it.

### Consequence Boundary

The existing `ReinvocationAuthorization` represents permission to re-enter the
full normal invocation boundary once and observe current authoritative state.
It does not authorize reuse of A1's candidate or validation, retry of A1's
append, acceptance, replay, success, or any other business outcome. A fresh A2
still follows normal idempotency, history reconstruction, domain reasoning,
validation, stream admission, append, and commit as applicable.

The unchanged owner continues to own cached evaluation, `AVAILABLE → SPENT`
before A2 entry, same retained signature and writer composition, spent state
after an A2 exception, and no automatic A3. Stage 4C remains independent and
unchanged: the same A1 may receive a typed current-response refusal and a
separate Stage 4E authorization.

### Production and Executable Scope

PR5 changes only the Stage 4E evaluator in production. Focused unit coverage
characterizes the exact positive shape, forward inequality, candidate and
order continuity, no-A1-effect fields, A1-carried idempotency shape, malformed
nested structures, PR1 preservation, and unrelated negative profiles. The two
existing PostgreSQL schedules now apply the production evaluator to their real
A1 results before preserving their existing fresh outcomes: schedule A
resolves as `REPLAY`; schedule B raises the current
`ValueError("Order is already paid")` domain rejection.

No owner, public contract, producer, Stage 4A, Stage 4C, Stage 4D, schema,
migration, or Stage 4B.5 protected replay artifact changes.

## Later Work

Later work remains provisional and evidence-gated.

Generic `STALE_WRITE` authorization remains outside the accepted boundary.
Only the coherent forward-version profile over the characterized evidence has
been accepted in PR5; the technical verdict by itself remains non-authorizing.

Stage 4D may re-enter only under the condition in
[ADR 0028](../../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md).

PR2 through PR5 are the bounded downstream responsibilities above. No
additional Stage 4E PR is planned merely to hold generic retry concerns.

## PR0 Promotion Table

| Experiment finding | Formal status | Production implication |
|---|---|---|
| Complete `RequestSignature` defines same request | Accepted requirement | Preserve all four fields. |
| Same `request_id` alone is insufficient | Accepted requirement | Refuse request-ID-only authorization. |
| Preparation `LOCK_TIMEOUT` | Accepted first profile | Consume producer-owned preparation evidence. |
| Coherent append current-version advance | Accepted second profile in PR5 | Typed PR4 evidence plus exact completed-result coherence may issue one-shot authority. |
| Generic `STALE_WRITE` | Not accepted as a positive profile | Other physical stale sources remain coarse. |
| Stage 4C / 4E independence | Accepted architecture result | Do not require a Stage 4C decision. |
| One-shot / consume before entry | Accepted safety requirement | Atomic lifecycle guards A2 writer entry. |
| A2 outcome never restores authority | Accepted safety requirement | Spent is terminal. |
| No automatic A3 | Accepted boundary | No retry loop. |
| Same execution composition | Accepted behavioral requirement | Preserve the A1-owned `HOW`. |
| Exact writer identity and observation lifecycle | Experimental mechanism | Use only a source-grounded private owner seam. |
| `PublicWriterInvocationObservation` and wrappers | Experimental mechanism | Do not promote. |
