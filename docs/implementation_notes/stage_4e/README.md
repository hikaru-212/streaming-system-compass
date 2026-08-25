# Stage 4E — Same-Request Re-Invocation Authority

[← Back to Implementation Notes](../README.md)

## Status

PR0 architecture boundary established. PR1 contract and evaluator implemented.
PR2 invocation owner and one-shot lifecycle implemented.
PR3 live-owner Stage 4C current-response delivery implemented.
PR4 append version-mismatch evidence refinement implemented.
PR5 narrow append version-advance authority profile implemented.

PR1 implements the immutable authorization/no-authority contracts and first
source-specific evaluator. PR2 implements live PostgreSQL A1 custody, explicit
cached evaluation, and guarded one-shot A2 entry through the same configured
writer. PR3 adds explicit Stage 4C delivery for only the owner's currently
published normal result. It does not add application/bootstrap consumption or
enforcement. PR4 preserves one characterized physical append source as stable
typed evidence. PR5 promotes only its coherent forward-version consequence into
a second source-specific issuance profile. This document does not promote the
experiment's scaffolding into production APIs.

The stage position is:

```text
Stage 4C
= COMPLETE / CLOSED
= current-response authority

Stage 4D
= valid Strategy Selection Authority responsibility
= implementation deferred under ADR 0028

Stage 4E
= Same-Request Re-Invocation Authority
= PR1 contract and first evaluator implemented
= PR2 invocation owner and one-shot consumption implemented
= PR3 current-response delivery capability implemented in the same owner
= PR4 source-specific append version-mismatch evidence implemented
= PR5 coherent append version advance added as a second positive profile
```

## First Formal Responsibility

Stage 4E answers one narrow question:

> Given eligible evidence from one completed invocation, is exactly one
> additional public writer invocation of the same complete `RequestSignature`
> authorized?

This is another-invocation authority. It is not current-response authority,
strategy selection, or execution.

```text
RuntimeDecision
!= Strategy Selection
!= another-invocation authorization
!= execution

current invocation failure
!= another-invocation authority

authorization
!= execution
```

Stage 4C and Stage 4E are independent dimensions. A Stage 4C refusal neither
authorizes nor refuses Stage 4E, and a Stage 4E authorization does not alter the
Stage 4C result for A1.

The responsibilities do not form a mandatory runtime pipeline:

```text
one completed result
→ Stage 4C decision or refusal
→ caller handling

separately, when another same-request invocation is considered
→ Stage 4E authorization or refusal

if A2 is authorized
→ Stage 4D chooses HOW only if multiple eligible strategies exist
→ execution
→ fresh result
→ Stage 4C handling when applicable
```

## Same-Request Identity

The existing production contract in
`src/storage/idempotency_store.py` defines `RequestSignature` as a frozen
dataclass with exactly these fields:

```text
request_id
command_type
order_id
amount
```

The first formal identity rule is structural equality of that complete
contract:

```text
same complete RequestSignature
= same request

same request_id alone
!= same request

same Python object
!= required for same request
```

No `intent_id`, semantic fingerprint, request lineage identifier, attempt
identifier, or execution identifier is introduced by PR0.

## Production Source Audit

The source audit found the following current contracts and ownership seams.

| Production source | Current responsibility | Stage 4E relevance |
|---|---|---|
| `src/storage/idempotency_store.py` | Frozen `RequestSignature` and idempotency classification | Provides the complete same-request identity contract. |
| `src/pipeline/transactional/admission.py` | Typed stream-preparation and append-admission results | Keeps preparation evidence distinct from append evidence and retains source-specific append version-mismatch evidence. |
| `src/pipeline/transactional/postgres_admission.py` | PostgreSQL optimistic and pessimistic admission gates | `PostgresPessimisticAdmissionGate.prepare_stream()` produces the first positive `LOCK_TIMEOUT` evidence; append translation preserves characterized version-mismatch evidence without itself authorizing another invocation. |
| `src/storage/postgres_event_store.py` | PostgreSQL accepted-history append boundary | Owns the physical expected/observed current-version inequality and emits its typed internal transport. |
| `src/pipeline/transactional/postgres_write_side.py` | Public PostgreSQL writer, orchestration, result, and static composition ownership | Carries A1 producer evidence but accepts decomposed request arguments and does not retain the complete signature on a timeout result. |
| `src/pipeline/transactional/postgres_write_side_invocation_owner.py` | Live current-result custody, explicit Stage 4C delivery, cached Stage 4E evaluation, and atomic one-shot A2 entry | Retains the complete request and configured writer, keeps one stable outcome identity and delivery for the current normal result, invalidates that state at A2 start, and independently spends positive Stage 4E authority before A2 writer entry. |
| `src/pipeline/transactional/postgres_write_side_config.py` | Immutable validation-placement configuration | Confirms current strategy placement is a construction choice. |
| `src/compass/runtime/write_side_outcome_mapping.py` | Maps producer results to `SemanticOutcome` | Demonstrates why the semantic projection is too coarse to prove the first Stage 4E profile by itself. |
| `src/compass/runtime/write_side_runtime_decision.py` | Stage 4C current-response evaluation | Refuses `CONCURRENCY_UNCERTAIN`; it is not a Stage 4E prerequisite. |
| `src/bootstrap/build_transactional_runtime.py` and `src/pipeline/transactional/registry.py` | In-memory composition root and single-invocation registry | Provide ownership patterns but are not a PostgreSQL A1/A2 runtime owner. |

PR2 provides the PostgreSQL-specific live invocation owner across A1, explicit
Stage 4E evaluation, and a possible guarded A2 invocation. PR3 adds explicit
decided/refused Stage 4C delivery over only its current normal result. No
production application service, command handler, or PostgreSQL bootstrap is
wired to construct or enforce that delivery; application wiring remains
outside this PR.

No production source fact materially contradicts the accepted experimental
findings.

## RequestSignature Ownership Audit

`PostgresTransactionalWriteSide.create_order()` and `pay_order()` accept:

```text
request_id
order_id
amount
```

The selected public method supplies `command_type` internally. The writer then
constructs the complete `RequestSignature` privately inside its execution
path.

Before public writer entry, the caller legitimately knows every signature
field. No production PostgreSQL layer currently holds a complete
`RequestSignature` object at that boundary, because no such caller/owner is
wired and the public API receives decomposed arguments.

On a preparation `LOCK_TIMEOUT`, the returned `PostgresWriteSideResult` carries
an idempotency `MISS` with no `IdempotencyRecord`. It therefore does not retain
the complete incoming signature. In particular, same `request_id` alone cannot
reconstruct or prove the same request.

The Stage 4E invocation owner retains the complete signature separately and
binds it to the exact A1 producer result in the same trusted in-process flow.
Adding the signature to every production result is not required by the current
implementation.

## First Positive Profile

Preparation `LOCK_TIMEOUT` is the accepted first formal positive profile.

The production operation is:

```text
PostgresPessimisticAdmissionGate.prepare_stream(order_id)
→ StreamAdmissionResult(
     verdict=LOCK_TIMEOUT,
     reason=...,
     order_id=order_id,
   )
```

For the established `IN_TRANSACTION` plus pessimistic composition, the public
writer calls preparation after authoritative idempotency `MISS` and before
history loading, candidate construction, validation, or append admission. The
writer rolls back and returns the typed result.

The minimum trustworthy A1 producer shape is:

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
```

The evaluator must use typed fields and structural relationships. It must not
parse `reason` text.

Preparation `LOCK_TIMEOUT` is distinguishable from append-time `STALE_WRITE`:
the former is owned by `stream_admission_result` with no append result, while
the latter is owned by `admission_result` after admitted stream preparation and
an allowing validation decision.

For the first positive profile, no narrower production-owned Stage 4E source
result exists. The raw `PostgresWriteSideResult`, validated against the typed
shape above, is therefore sufficient for that profile. PR0 does not create a
generic evidence envelope.

## PR4 Append Version-Mismatch Evidence Refinement

PR4 is complete. It preserves one characterized physical append fact:

```text
PostgresEventStore.append(...)
observes:

observed_current_version != expected_current_version
```

The stable retained payload is exactly:

```text
AppendVersionMismatchEvidence(
  expected_current_version,
  observed_current_version,
)
```

The production ownership and retention chain is:

```text
PostgresEventStore
→ AppendVersionMismatchError as typed internal transport
→ PostgreSQL admission translation
→ AdmissionResult.append_version_mismatch_evidence
→ PostgresWriteSideResult.admission_result
```

The storage exception does not escape as the upper control language, and the
admission gate does not parse human-readable text. The experiment's two real
PostgreSQL schedules observe exact version transitions `0 → 1` and `1 → 2`.
In both, A1 has no durable accepted effect and the complete fresh invocation
obtains information from newly authoritative history rather than retrying the
old append or reusing the old candidate or validation.

This evidence is deliberately source-specific. It remains absent for:

- candidate continuity mismatch;
- generic `ValueError` and generic `StaleWriteError`;
- `AppendConflictError`;
- recognized stream-position `UniqueViolation`;
- manually constructed or otherwise coarse `STALE_WRITE`.

The technical verdict remains `AdmissionVerdict.STALE_WRITE`. Stage 4A may
continue to apply its existing coarse interpretation for its current
responsibility; that shared projection does not establish global consequence
equivalence among physical stale sources. PR4 did not change Stage 4C,
`DecisionReceipt`, or the Stage 4E evaluator.

```text
technical outcome
!= physical evidence
!= semantic interpretation
!= authority
!= execution

at the PR4 closeout:

completed invocation
+ append version-mismatch evidence
→ NoReinvocationAuthority
```

PR4 evidence availability alone is not Stage 4E
`ReinvocationAuthorization`. PR5 separately reviews the additional result and
custody invariants required for one consequence.

## PR5 Append Version-Advance Authority Profile

PR5 adds one explicit positive predicate beside the unchanged preparation
`LOCK_TIMEOUT` predicate. Its theorem is:

> A completed trusted write-side result showing a coherent append version
> advance, with no accepted A1 effect, may issue authority for exactly one
> fresh invocation of the invocation owner's retained complete
> `RequestSignature`.

The evaluator requires this exact structural profile:

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
    │   ├── observed_current_version > expected_current_version
    │   └── typed AppendVersionMismatchEvidence
    └── candidate_event_id
        = validation_decision.validation_result.candidate_event_id
```

PR4's evidence contract continues to accept either direction of physical
inequality. PR5 deliberately requires `observed_current_version >
expected_current_version`: accepted history observed at append has advanced
beyond the version A1 expected. A contract-valid reverse inequality remains
`NoReinvocationAuthority`. Generic or coarse `STALE_WRITE`, including stale
results without the typed mismatch payload, also remains non-authorizing.

The mismatch payload alone does not prove absence of an A1 effect. PR5 requires
the coherent completed result with `ADMISSION_REJECTED`, no top-level accepted
event, no append accepted-event identity, and A1-carried idempotency `MISS` with
no record. In the trusted write-side control flow, version mismatch occurs
before insert, the rejection branch rolls back, and idempotency persistence
occurs only after admitted append. The carried `MISS` describes A1's execution;
it is not a claim about current database contents after a competing commit.

The evaluator does not independently prove complete A1 request identity, and
`PostgresWriteSideResult` does not reconstruct all four request fields. Same-
request identity is preserved by invocation-owner custody:

```text
owner-retained complete RequestSignature
→ A1 dispatched from that signature
→ evaluator receives that retained signature and exact A1 result
→ A2 accepts no replacement request arguments
→ A2 dispatches from the same retained signature
```

PR5 therefore relies on the trusted producer result, source-specific typed
evidence, structural coherence, known write-side control flow, and existing
owner custody. The evidence dataclasses are not an arbitrary serialized proof
protocol, and no request fields are added to `PostgresWriteSideResult`.

`ReinvocationAuthorization` means permission to re-enter the complete normal
invocation boundary once so current authoritative state can be observed. It is
not permission for any candidate to become accepted history. A2 still performs
normal idempotency, history reconstruction, domain reasoning, validation,
stream admission, append, and commit as applicable:

```text
A2 authority
!= A2 success
!= A2 replay
!= candidate acceptance
```

The two real schedules demonstrate the distinction: the same-request winner
leads fresh A2 to `REPLAY`, while a different request's accepted PAY leads fresh
A2 to current domain rejection. Neither outcome is predicted by issuance.
Stage 4C remains unchanged and may still refuse the A1 current response while
Stage 4E independently issues this one-shot another-invocation authority.

## Evidence Deliberately Not Required

| Existing evidence | Required? | Reason |
|---|---|---|
| `SemanticOutcome` | No | Both preparation and append concurrency cases map to `CONCURRENCY_UNCERTAIN`; the projection does not preserve enough phase-specific proof by itself. |
| Stage 4C `RuntimeDecision` | No | Stage 4C refuses the current `CONCURRENCY_UNCERTAIN` profile and is an independent current-response authority. |
| `DecisionReceipt` | No | It is derived durable governance evidence, not required for the live first-profile precondition or authorization lifecycle. |
| `DiagnosticTrace` / execution trace | No | Typed stream versus append result placement already proves the required production phase for this profile. |
| Measurement Evidence | No | Timing and cost do not prove authorization eligibility. |
| Order correctness-rule evidence | No | PR1 terminates before validation. PR5 requires the retained `ValidationDecision` to be `ALLOW` with coherent validation/admission candidate identity, but it does not require the optional rule-evidence carrier. |

The first profile therefore prefers the smallest trustworthy evidence set:

```text
complete RequestSignature
+ validated producer-owned preparation LOCK_TIMEOUT result
+ legitimate A1 invocation/composition ownership
→ Stage 4E evaluation
```

## Invocation and Composition Ownership

The Compass Stage 4E evaluator evaluates and issues authority; it does not
execute A2. The transactional invocation owner retains:

```text
complete RequestSignature
+ exact A1 PostgresWriteSideResult
+ the existing writer/composition
+ Stage 4E authorization or refusal
```

PR2 implements that seam as the PostgreSQL-specific, live, in-process
`PostgresWriteSideInvocationOwner` around the existing public writer. Its
responsibility is bounded:

- receive or construct the complete signature before A1;
- invoke the normal public writer with the decomposed fields;
- retain the exact A1 result and signature as one invocation-local fact;
- retain the already-configured writer composition;
- request Stage 4E evaluation;
- consume a positive authority before any A2 public-writer entry;
- make at most that one explicitly authorized A2 call.

This is not a general workflow engine or retry loop.

For the current in-process design, privately retaining the exact configured
writer instance is sufficient to preserve the composition transitively. The
writer already owns its connection, validation runtime, immutable placement
config, and admission-gate factory. Each invocation may correctly receive a
fresh per-command gate from the same retained factory.

```text
same writer instance as a private ownership mechanism
!= writer identity as a durable semantic contract
```

PR0 does not introduce `WriterIdentity`, `WriterFingerprint`,
`StrategyFingerprint`, `ExecutionPlanIdentity`, a topology registry, or a
policy/strategy registry.

## One-Shot Lifecycle

The formal safety property is:

```text
one A1 authorization
→ at most one later A2 public-writer entry
```

The live invocation owner and authorization lifecycle preserve all of the
following:

- consumption is atomic and thread-safe;
- authority is consumed before A2 public-writer entry;
- A2 `ACCEPTED`, `REPLAY`, rejection, timeout, or exception leaves it spent;
- a consumed authority never becomes available again;
- an issued but unused authority performs no invocation and may disappear with
  its live owner;
- no automatic A3 is created;
- process restart recovery and distributed consumption are not provided.

Repeated or concurrent evaluation of the same owner-held eligible A1 invocation
context within one trusted live in-process flow must not mint independent
spendable authorities. The formal requirement is one owner-scoped, in-memory
issuance/consumption lifecycle. Structurally equivalent independently
reconstructed `PostgresWriteSideResult` values do not establish the same
historical A1 execution or join that lifecycle. Reusing the exact same
in-process authorization object is the smallest possible realization, but
Python object identity is not promoted as durable or semantic authorization
identity.

Evaluation may be semantically idempotent; consumption is deliberately not.
After the first successful consumption transition, every later consumption
attempt must be refused before writer entry.

## Authorization and Refusal Vocabulary

The two reviewed profiles support:

```text
eligible preparation LOCK_TIMEOUT evidence
→ positive one-additional-invocation authorization

eligible coherent append version-advance evidence
→ positive one-additional-invocation authorization

unsupported or incoherent evidence
→ typed absence of re-invocation authority / refusal
```

Typed absence of authority is not a reviewed denial:

```text
unsupported
!= reviewed denial

absence of authority
!= permanent prohibition
```

No explicit negative policy is justified by the first formal profile. PR0 does
not add a universal `ALLOWED`/`DENIED` policy vocabulary.

## Experiment-to-Formal Promotion

| Experiment finding | Formal status | Production implication |
|---|---|---|
| Complete `RequestSignature` defines same request | Accepted requirement | Formal contract preserves the full signature. |
| Same `request_id` alone is insufficient | Accepted requirement | No request-ID-only authorization. |
| Preparation `LOCK_TIMEOUT` positive profile | Accepted first profile | Producer-owned timeout evidence is required. |
| Coherent append current-version advance | Accepted second profile in PR5 | Typed PR4 evidence plus the exact completed-result coherence predicate may issue one-shot authority. |
| Generic `STALE_WRITE` positive profile | Not accepted | Other physical stale sources remain coarse and no generic authorization exists. |
| Stage 4C / Stage 4E independence | Accepted architecture result | No mandatory C→E dependency. |
| One-shot authorization | Accepted safety requirement | At most one later writer entry. |
| Consume before writer entry | Accepted safety requirement | A2 failure cannot restore authority. |
| No automatic A3 | Accepted first-slice boundary | No retry loop. |
| Same execution composition | Accepted behavioral requirement | Stage 4E cannot silently change `HOW`. |
| Exact Python writer identity | Experimental mechanism | Do not promote it as public semantic identity. |
| Mutable experimental lifecycle | Experimental mechanism | Production lifecycle ownership must be source-grounded. |
| `PublicWriterInvocationObservation` | Experimental carrier | Do not promote it as a production API. |

## Experimental Mechanisms Not Promoted

The following remain executable proof scaffolding:

- `PublicWriterInvocationObservation`;
- candidate-construction monkeypatches;
- validation and append observation wrappers;
- exact Python writer identity as public semantic identity;
- mutable observation-owned lifecycle;
- `ExperimentalOneShotReinvocationConsumer`;
- generic `STALE_WRITE` authorization;
- experiment-only PostgreSQL checkpoint hooks.

The behavioral properties they demonstrated remain accepted even though these
mechanisms do not become production architecture.

## Stage 4D Disposition

[ADR 0028](../../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md)
retains Stage 4D as the owner of dynamic `HOW` selection and defers its
implementation until one already-authorized operation has multiple dynamically
eligible paths, reviewed selection evidence, and observable value from the
choice.

Stage 4E preserves the current composition. It does not select a new one.

## First-Slice Non-Goals

The first formal Stage 4E slice does not design or implement:

- generic or coarse `STALE_WRITE` authorization;
- generic retry taxonomy;
- backoff, jitter, or general retry timing;
- retry budgets or attempt-class limits;
- candidate-regeneration policy;
- semantic-drift or agent-intent-drift retry;
- general retry planning;
- durable `AttemptLog`, `request_attempts`, `attempt_id`, or `execution_id`;
- persistent cross-attempt lineage;
- restart recovery;
- distributed authorization lifecycle;
- Stage 4D `StrategySelector`;
- automatic A2 execution, retry loops, or automatic A3;
- Stage 5 `ActionSafetyGate`;
- generic workflow orchestration or a general policy engine.

These broader concerns remain unaccepted future candidates. They require their
own concrete evidence before promotion.

## PR Direction

The bounded PR plan is maintained in [PR Breakdown](pr_breakdown.md).

PR1 establishes the immutable formal contracts and source-specific preparation
`LOCK_TIMEOUT` evaluator. PR2 implements invocation ownership, synchronized
result publication, exact evaluation caching, and one-shot A2 consumption. Its
real PostgreSQL characterization covers preparation `LOCK_TIMEOUT`, explicit
authority, release of the competing lock, one accepted A2, and terminal refusal
without extra rows. PR3 adds the current-result Stage 4C delivery capability to
that same owner, including stable outcome identity, typed refusal transport,
atomic invalidation at A2 start, and a fresh A2 current-response lifecycle. It
does not provide application-level enforcement or attempt history. PR4 retains
the characterized append current-version inequality through the real
PostgreSQL write-side result. PR5 adds its separately reviewed, coherent
forward-version profile to the evaluator and reuses the existing authority and
unchanged owner lifecycle. It adds no generic stale authorization, automatic
A2 execution, or outcome prediction.
