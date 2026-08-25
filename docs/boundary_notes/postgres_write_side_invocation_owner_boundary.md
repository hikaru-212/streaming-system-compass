# PostgreSQL Write-Side Invocation Owner Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the stable production boundary for
`PostgresWriteSideInvocationOwner`.

The owner governs one live, in-process lifecycle:

```text
one complete RequestSignature
+ one configured PostgresTransactionalWriteSide
→ one owner-invoked A1
→ one currently published normal PostgresWriteSideResult
→ optional explicit cached Stage 4C current-response delivery

the retained A1 result
→ one explicit cached Stage 4E evaluation
→ at most one authorized A2 public-writer entry
```

Stage 4C current-response delivery and Stage 4E another-invocation authority
remain independent responsibilities over owner-held live state. Neither one
implicitly evaluates, authorizes, consumes, or executes the other.

This is trusted live causal custody. It is not cryptographic, durable,
restart-safe, distributed, or hostile-code tamper-proof provenance.

## What the Owner Owns

The owner owns:

- private custody of the complete `RequestSignature`;
- the trusted live causal path into A1;
- private custody of the exact normally completed A1
  `PostgresWriteSideResult`;
- private custody of the currently published normal producer result, initially
  A1 and later A2 only after normal A2 completion;
- one stable owner-minted `outcome_id` for that currently published result once
  current-response evaluation is first requested;
- explicit Stage 4A / Stage 4C mapping of only that current result;
- one owner-scoped cache for the exact decided or refused current-response
  delivery;
- exact current-result selection for `USE_CURRENT_RESULT` and exact
  producer-and-record event selection for `RETURN_PRIOR_ACCEPTED_RESULT`;
- private custody of the configured writer and its existing execution
  composition;
- explicit, lazy Stage 4E evaluation;
- one owner-scoped cache for the exact positive or no-authority evaluation;
- owner-local one-shot spendability for positive authority;
- the atomic `AVAILABLE → SPENT` transition before A2 writer entry;
- guarded same-request, same-composition A2 dispatch; and
- terminal spent state after every A2 return or exception;
- atomic invalidation of all current-response state when A2 consumption begins;
  and
- a fresh empty current-response identity/cache lifecycle when A2 completes
  normally.

The retained writer preserves its already-configured connection, validation
runtime, `PostgresWriteSideConfig`, and admission-gate factory. Each invocation
may construct a fresh gate from that same retained factory.

```text
same retained execution composition
!= same per-invocation gate object

private writer custody
!= public or durable writer identity
```

## Synchronization and One-Shot Consumption

One owner-scoped non-reentrant lock protects all mutable lifecycle publication:

- A1 admission;
- exact completed A1-result publication;
- current-result publication;
- current `outcome_id` and delivery-cache creation and publication;
- the Stage 4E evaluation cache;
- the positive-authority `AVAILABLE → SPENT` transition; and
- the same-critical-section invalidation of current result, current
  `outcome_id`, and cached current-response delivery before A2 entry.

The lock is never held during PostgreSQL writer execution. The private spent
assignment under that lock is the consumption linearization point. It occurs
before A2 public-writer entry and is never reversed.

The immutable `ReinvocationAuthorization` continues to mean that authority was
issued after consumption. Spendability is separate owner-local lifecycle state:

```text
issued authority meaning
!= current spendability
```

Consequently, evaluation after consumption returns the same cached authority
object, while every further consumption attempt is refused before writer
entry. No A2 result or exception creates availability, and no A3 is automatic.

When A2 consumption wins the lock, A1 immediately ceases to be the current
response source. The owner clears the current producer result, current
`outcome_id`, and current-response delivery cache in the same critical section
that spends Stage 4E authority. An A2 exception leaves that state empty. A
normal A2 completion publishes the exact A2 result with no outcome identity or
delivery yet; later explicit evaluation starts its fresh current-response
lifecycle.

## Stage 4C Current-Response Delivery

`evaluate_current_response()` accepts no caller-supplied inputs. It operates
only on the current normal producer result published by this owner. The first
evaluation request mints and retains one `outcome_id` before mapping begins.
Repeated or concurrent evaluation of that same current result reuses the same
identity and returns the identical cached delivery after evaluation completes.

A structural mapping or evaluation failure propagates and is not cached. The
already-minted `outcome_id` remains retained, so a later evaluation of the same
current result cannot silently acquire a different semantic identity.

A decided delivery retains the exact producer result and exact existing
`PostgresWriteSideRuntimeDecisionEvaluation`. Its selected result is:

- the exact producer result for `USE_CURRENT_RESULT`;
- the exact prior accepted event already carried identically by the `REPLAY`
  result and its idempotency record for `RETURN_PRIOR_ACCEPTED_RESULT`; or
- absent for `BLOCK_CURRENT_CONTINUATION` and `REQUIRE_ESCALATION`.

Replay selection additionally requires the record's complete signature to
equal the owner's retained `RequestSignature`. No event is reconstructed.

A refused delivery retains the exact producer result, exact
`PostgresWriteSideSemanticRuleFeedback`, and exact
`PostgresWriteSideRuntimeDecisionRefused`. It has no `RuntimeDecision` and no
selected result. Its only meaning is that no authoritative Stage 4C
current-response decision is available:

```text
Stage 4C refusal
!= BLOCK_CURRENT_CONTINUATION
!= denial
!= escalation
!= permission to continue
!= Stage 4E authorization or refusal
```

This owner exposes a production current-response delivery capability. It does
not own the absent application/bootstrap continuation that would enforce or
execute a returned decision.

The current-response slot is not attempt history. A1 may cease to be current
without ever being evaluated when A2 begins, and the owner keeps no A1/A2
delivery collection or historical retrieval API.

## Failure Boundary

Structural input and result invalidity remains `TypeError`. Well-typed evidence
outside the Stage 4E profile remains `NoReinvocationAuthority` from the
existing evaluator.

Stage 4C structural mapper/evaluator failures propagate without a delivery.
Typed `PostgresWriteSideRuntimeDecisionRefused` instead becomes a cached refused
delivery without fabricating a `RuntimeDecision`.

`PostgresWriteSideInvocationLifecycleError` is reserved for owner-lifecycle
misuse, including duplicate A1 entry, evaluation without normal A1 completion,
consumption before explicit evaluation, consumption of cached no-authority,
already-spent authority, and unsupported retained command dispatch. It is not
a Stage 4E denial or generic retry-policy vocabulary.

An A1 writer exception propagates unchanged, publishes no completed result,
publishes no current-response state, and permanently uses A1 admission for that
owner. An A2 exception also propagates unchanged, but authority was already
spent before writer entry and the invalidated A1 current-response state is not
restored.

## What the Owner Does Not Own

The owner does not own:

- Stage 4E eligibility semantics or new positive profiles;
- new Stage 4C policy or semantic profiles;
- automatic Stage 4C evaluation;
- end-to-end application consumption, enforcement, or continuation;
- Stage 4D strategy selection;
- automatic retry, retry scheduling, backoff, jitter, or timing;
- retry budgets or attempt counting;
- current or durable attempt history, lineage, or identifiers;
- application or UI escalation;
- persistent authority or writer identity;
- distributed or restart-safe lifecycle state;
- schema, migration, bootstrap, or dependency changes; or
- a second re-invocation lifecycle or automatic A3.
