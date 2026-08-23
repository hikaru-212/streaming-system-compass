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
→ one explicit cached Stage 4E evaluation
→ at most one authorized A2 public-writer entry
```

This is trusted live causal custody. It is not cryptographic, durable,
restart-safe, distributed, or hostile-code tamper-proof provenance.

## What the Owner Owns

The owner owns:

- private custody of the complete `RequestSignature`;
- the trusted live causal path into A1;
- private custody of the exact normally completed A1
  `PostgresWriteSideResult`;
- private custody of the configured writer and its existing execution
  composition;
- explicit, lazy Stage 4E evaluation;
- one owner-scoped cache for the exact positive or no-authority evaluation;
- owner-local one-shot spendability for positive authority;
- the atomic `AVAILABLE → SPENT` transition before A2 writer entry;
- guarded same-request, same-composition A2 dispatch; and
- terminal spent state after every A2 return or exception.

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
- evaluation-cache creation and publication; and
- the positive-authority `AVAILABLE → SPENT` transition.

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

## Failure Boundary

Structural input and result invalidity remains `TypeError`. Well-typed evidence
outside the Stage 4E profile remains `NoReinvocationAuthority` from the
existing evaluator.

`PostgresWriteSideInvocationLifecycleError` is reserved for owner-lifecycle
misuse, including duplicate A1 entry, evaluation without normal A1 completion,
consumption before explicit evaluation, consumption of cached no-authority,
already-spent authority, and unsupported retained command dispatch. It is not
a Stage 4E denial or generic retry-policy vocabulary.

An A1 writer exception propagates unchanged, publishes no completed result,
and permanently uses A1 admission for that owner. An A2 exception also
propagates unchanged, but authority was already spent before writer entry.

## What the Owner Does Not Own

The owner does not own:

- Stage 4E eligibility semantics or new positive profiles;
- Stage 4C current-response policy or caller continuation semantics;
- Stage 4D strategy selection;
- automatic retry, retry scheduling, backoff, jitter, or timing;
- retry budgets or attempt counting;
- durable attempt history, lineage, or identifiers;
- application or UI escalation;
- persistent authority or writer identity;
- distributed or restart-safe lifecycle state;
- schema, migration, bootstrap, or dependency changes; or
- a second re-invocation lifecycle or automatic A3.

Stage 4C current-response consumption is outside the current owner boundary.

If this same owner later acquires Stage 4C consumption responsibility, this
boundary note should be updated to record that additional ownership rather than
introducing a competing invocation-owner boundary.