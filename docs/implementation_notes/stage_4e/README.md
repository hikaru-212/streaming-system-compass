# Stage 4E — Same-Request Re-Invocation Authority

[← Back to Implementation Notes](../README.md)

## Status

PR0 architecture boundary established.

Production Stage 4E remains unimplemented. This document promotes accepted
behavioral findings from the completed Stage 4C-to-4E experiment into the first
formal Stage 4E responsibility. It does not promote the experiment's scaffolding
into production APIs.

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
= first formal production contract not yet implemented
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
| `src/pipeline/transactional/admission.py` | Typed stream-preparation and append-admission results | Keeps preparation evidence distinct from append evidence. |
| `src/pipeline/transactional/postgres_admission.py` | PostgreSQL optimistic and pessimistic admission gates | `PostgresPessimisticAdmissionGate.prepare_stream()` produces the first positive `LOCK_TIMEOUT` evidence. |
| `src/pipeline/transactional/postgres_write_side.py` | Public PostgreSQL writer, orchestration, result, and static composition ownership | Carries A1 producer evidence but accepts decomposed request arguments and does not retain the complete signature on a timeout result. |
| `src/pipeline/transactional/postgres_write_side_config.py` | Immutable validation-placement configuration | Confirms current strategy placement is a construction choice. |
| `src/compass/runtime/write_side_outcome_mapping.py` | Maps producer results to `SemanticOutcome` | Demonstrates why the semantic projection is too coarse to prove the first Stage 4E profile by itself. |
| `src/compass/runtime/write_side_runtime_decision.py` | Stage 4C current-response evaluation | Refuses `CONCURRENCY_UNCERTAIN`; it is not a Stage 4E prerequisite. |
| `src/bootstrap/build_transactional_runtime.py` and `src/pipeline/transactional/registry.py` | In-memory composition root and single-invocation registry | Provide ownership patterns but are not a PostgreSQL A1/A2 runtime owner. |

No production application service, command handler, runtime owner, or bootstrap
currently owns a `PostgresTransactionalWriteSide` across A1 authorization and a
possible A2 invocation. That absence is a repository fact, not an architecture
verdict against Stage 4E.

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

A future Stage 4E invocation owner must retain the complete signature
separately and bind it to the exact A1 producer result in the same trusted
in-process flow. Adding the signature to every production result is not
required by the current evidence.

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

No narrower production-owned Stage 4E source result currently exists. The raw
`PostgresWriteSideResult`, validated against the typed shape above, is therefore
sufficient for the first profile. PR0 does not create a generic evidence
envelope.

## Evidence Deliberately Not Required

| Existing evidence | Required? | Reason |
|---|---|---|
| `SemanticOutcome` | No | Both preparation and append concurrency cases map to `CONCURRENCY_UNCERTAIN`; the projection does not preserve enough phase-specific proof by itself. |
| Stage 4C `RuntimeDecision` | No | Stage 4C refuses the current `CONCURRENCY_UNCERTAIN` profile and is an independent current-response authority. |
| `DecisionReceipt` | No | It is derived durable governance evidence, not required for the live first-profile precondition or authorization lifecycle. |
| `DiagnosticTrace` / execution trace | No | Typed stream versus append result placement already proves the required production phase for this profile. |
| Measurement Evidence | No | Timing and cost do not prove authorization eligibility. |
| Order correctness-rule evidence | No | The accepted timeout occurs before candidate construction and validation in the established composition. |

The first profile therefore prefers the smallest trustworthy evidence set:

```text
complete RequestSignature
+ validated producer-owned preparation LOCK_TIMEOUT result
+ legitimate A1 invocation/composition ownership
→ Stage 4E evaluation
```

## Invocation and Composition Ownership

Stage 4E evaluates and issues authority; it does not execute A2. A legitimate
owner must be able to retain:

```text
complete RequestSignature
+ exact A1 PostgresWriteSideResult
+ the existing writer/composition
+ Stage 4E authorization or refusal
```

No such PostgreSQL owner exists in current production source. The smallest
required seam is a live, in-process command/runtime owner around the existing
public writer. Its responsibility is bounded:

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

The live invocation owner and authorization lifecycle must preserve all of the
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

The first profile supports:

```text
eligible preparation LOCK_TIMEOUT evidence
→ positive one-additional-invocation authorization

unsupported or incoherent evidence
→ typed NoStage4EAuthority / refusal
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
| `STALE_WRITE` positive profile | Experimental evidence only | Deferred until a production evidence contract exists. |
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
- `STALE_WRITE` authorization;
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

- `STALE_WRITE` authorization;
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

PR1 is proposed to establish the minimum immutable formal contract and the
small in-process ownership seam required to bind complete request identity,
eligible A1 evidence, one-shot consumption, and composition preservation. No
production mechanism beyond that bounded responsibility is accepted by PR0.
