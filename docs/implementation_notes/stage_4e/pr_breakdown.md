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

### Responsibility

PR3 will use the invocation owner established by PR2 to consume the already-complete
Stage 4C current-response authority. It addresses:

- `outcome_id` ownership or generation;
- result plus `RuntimeDecision` or typed-refusal delivery;
- `USE_CURRENT_RESULT`;
- `RETURN_PRIOR_ACCEPTED_RESULT`;
- `BLOCK_CURRENT_CONTINUATION`;
- `REQUIRE_ESCALATION`;
- typed Stage 4C refusal transport;
- caller-visible continuation semantics.

PR3 must not change Stage 4E eligibility or lifecycle merely to consume Stage
4C authority.

## Later Work

Later work remains provisional and evidence-gated.

`STALE_WRITE` may re-enter only after production-owned evidence can prove the
required candidate, validation, append, and invocation provenance without the
experiment's observation wrappers or monkeypatches.

Stage 4D may re-enter only under the condition in
[ADR 0028](../../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md).

PR2 and PR3 are the bounded downstream responsibilities above. No additional
Stage 4E PR is planned merely to hold generic retry concerns.

## PR0 Promotion Table

| Experiment finding | Formal status | Production implication |
|---|---|---|
| Complete `RequestSignature` defines same request | Accepted requirement | Preserve all four fields. |
| Same `request_id` alone is insufficient | Accepted requirement | Refuse request-ID-only authorization. |
| Preparation `LOCK_TIMEOUT` | Accepted first profile | Consume producer-owned preparation evidence. |
| `STALE_WRITE` | Experimental evidence only | Defer pending a production evidence contract. |
| Stage 4C / 4E independence | Accepted architecture result | Do not require a Stage 4C decision. |
| One-shot / consume before entry | Accepted safety requirement | Atomic lifecycle guards A2 writer entry. |
| A2 outcome never restores authority | Accepted safety requirement | Spent is terminal. |
| No automatic A3 | Accepted boundary | No retry loop. |
| Same execution composition | Accepted behavioral requirement | Preserve the A1-owned `HOW`. |
| Exact writer identity and observation lifecycle | Experimental mechanism | Use only a source-grounded private owner seam. |
| `PublicWriterInvocationObservation` and wrappers | Experimental mechanism | Do not promote. |
