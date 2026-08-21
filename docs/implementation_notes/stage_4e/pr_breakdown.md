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
The smallest missing invocation-owner/binding seam and the focused concurrent
one-shot characterization belong inside PR1's proposed responsibility. PR0
does not need an intermediate writer-result mutation, test hook, or experiment
promotion to make PR1 ready.

### PR0 Non-Goals

PR0 does not change production code, tests, migrations, dependencies, writer
behavior, database state, or runtime wiring. It does not implement Stage 4E.

## PR1 — Minimum Formal Same-Request Authority Contract

### Status

Proposed next responsibility. Not implemented by PR0.

### Goal

Establish the minimum immutable, live/in-memory contract needed to represent:

- complete same-request identity;
- one eligible producer-owned A1 evidence profile;
- positive authority for one additional public-writer entry;
- typed refusal / no authority for unsupported evidence;
- one shared one-shot issuance and consumption lifecycle;
- consumption before public-writer entry;
- private preservation of the A1 execution composition.

PR1 should not freeze module or class names until its source-level design is
reviewed. The following descriptions are responsibilities, not API names.

### Minimum Input Boundary

The evaluator needs one trusted in-process composition of:

```text
complete RequestSignature
+ exact A1 PostgresWriteSideResult
+ owner-held configured writer/composition
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
the complete signature and its bounded one-shot issuance/consumption state.
The authorization artifact must not own or expose a writer, execution callable,
replacement strategy, or execution-composition capability.

The invocation owner may privately retain the complete signature, exact A1
result, configured writer/composition, and positive authorization. Actual
writer/composition custody belongs to that owner, not to the authorization.

Unsupported or incoherent evidence should produce a typed no-authority/refusal
result. It should not produce a universal negative policy decision.

```text
positive authority
or typed absence of authority

not

universal ALLOWED / DENIED policy
```

### Minimum Lifecycle Boundary

PR1 must preserve:

- at most one A2 public-writer entry per A1 authorization;
- atomic, thread-safe consumption;
- consumption before A2 writer entry;
- no restoration after A2 acceptance, replay, rejection, timeout, or exception;
- no independent authorities minted by repeated or concurrent evaluation of
  the same owner-held A1 invocation context within one trusted live in-process
  flow;
- no automatic A3;
- no persistence or restart recovery.

Exact Python authorization-object reuse may be the smallest in-process
implementation, but the semantic requirement is one shared issuance and
consumption lifecycle, not public Python identity.

Structurally equivalent independently reconstructed
`PostgresWriteSideResult` values do not establish the same historical A1
execution and must not join that owner-scoped lifecycle.

### Minimum Invocation-Owner Seam

Current source has no PostgreSQL owner above
`PostgresTransactionalWriteSide`. PR1 therefore needs the smallest owner seam
that can:

- retain the complete signature before A1;
- bind that signature to the exact A1 result;
- retain the already-configured writer privately;
- request evaluation;
- consume a positive authority before any A2 call;
- perform at most the explicitly authorized normal public-writer entry.

This owner must not accept a replacement writer, signature, validation
decision, candidate, or strategy at consumption time.

The owner is not a workflow engine, scheduler, retry loop, or Stage 4D selector.

### Required Characterization

PR1 should characterize at least:

- independently constructed but structurally equal complete signatures count
  as the same request;
- same `request_id` with a changed command, order, or amount cannot consume the
  authority;
- the accepted production `LOCK_TIMEOUT` result shape authorizes once;
- append-time `LOCK_TIMEOUT`, `STALE_WRITE`, accepted, replay, conflict,
  validation-blocked, infrastructure, and exceptional A1 shapes receive typed
  refusal in the first profile;
- Stage 4C decision or refusal is not an evaluator prerequisite;
- writer/composition substitution is impossible at consumption;
- repeated and concurrent evaluation of the same owner-held A1 invocation
  context within one trusted live in-process flow cannot mint multiple
  spendable authorities;
- concurrent consumers yield at most one public-writer entry;
- authority is already spent when the writer is entered;
- accepted, replayed, rejected, timed-out, and exceptional A2 outcomes all
  leave it spent;
- no automatic A3 occurs.

The experiment already supplies behavioral evidence for these boundaries.
Production characterization should target only the formal source-owned seam,
not reproduce its monkeypatch and observation framework.

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
- automatic A2 scheduling, retry loops, or A3;
- Stage 5 action execution or safety policy.

## Later Work

Later work remains provisional and evidence-gated.

`STALE_WRITE` may re-enter only after production-owned evidence can prove the
required candidate, validation, append, and invocation provenance without the
experiment's observation wrappers or monkeypatches.

Stage 4D may re-enter only under the condition in
[ADR 0028](../../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md).

No additional Stage 4E PR is planned merely to hold generic retry concerns.

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
