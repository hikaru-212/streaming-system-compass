# DecisionReceipt Boundary

[← Back to Boundary Notes](README.md)

> **Authority:** This is the current canonical cross-stage `DecisionReceipt`
> boundary. PR-specific implementation notes preserve delivery history and do
> not override this note, the accepted ADRs, or current source contracts.

The specialized current boundary for caller-owned PostgreSQL transaction
safety, conditional progress, and explicit liveness non-guarantees is the
[DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary](decision_receipt_postgres_transaction_safety_and_liveness_boundary.md).
That specialized note does not replace this cross-stage owner.

## Purpose

This note defines the conceptual boundary for Stage 4B `DecisionReceipt`.

Stage 4A introduced `SemanticOutcome` as the semantic interpretation of technical runtime evidence.
Stage 4B introduces `DecisionReceipt` as the durable governance evidence record for selected semantic outcomes.

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

The purpose of this note is to clarify what a receipt is responsible for, what it must not absorb, and why durable governance evidence is narrower than ordinary logging.

---

## Core Boundary

A `SemanticOutcome` answers:

```text
What does this technical result mean semantically?
```

A `DecisionReceipt` answers:

```text
What selected summary evidence should be preserved so future governance can review, query, and act on that semantic meaning?
```

Therefore:

```text
SemanticOutcome
= semantic interpretation

DecisionReceipt
= durable governance evidence record for selected semantic interpretation
```

A live system may consume `SemanticOutcome` directly for immediate runtime
classification and current-response authority. Under
[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md),
the first live Runtime Decision Authority and Retry / Attempt Authorization
paths do not require a `DecisionReceipt` or prior receipt persistence.

A consumer that needs durable auditability, reviewability, operator
investigation, delayed reconciliation, restart/recovery, or governance
continuation may require receipts for that durable purpose. Strategy selection
and retry / attempt authorization may instead consume eligible current live
evidence; receipt need is consumer-specific rather than categorical.

A receipt provides durable, reviewable evidence for later governance consumers.
It does not execute or authorize them.

The contract's durable role must not collapse live materialization and proven
transaction durability:

```text
materialized DecisionReceipt
!= proven durable receipt row
```

A materialized receipt is a stable governance-evidence value. Proven durability
requires commit-aware receipt-transaction evidence such as `COMMITTED`.
`NOT_COMMITTED` and `UNKNOWN` retain their distinct transaction meanings.

Likewise:

```text
DecisionReceipt existence
!= business success
!= accepted business fact
!= retry authority
!= execution authority
```

---

## What DecisionReceipt Is

A `DecisionReceipt` is:

```text
durable
compact
reviewable
machine-readable
policy-consumable
safe to reference later
```

It preserves selected governance evidence such as:

```text
semantic_code
category
boundary
severity
risk_level
reversibility
reason
evidence_source
subject
identity / lineage correlation
write-side admission fate when applicable
snapshot identity when relevant
source global position when relevant
summary cost fields when relevant
flags such as fallback_required, rebuild_required, or operator_review_required
```

The key phrase is **selected governance evidence**.

A receipt should not persist arbitrary operational detail merely because that detail exists in runtime context.

---

## What DecisionReceipt Is Not

A `DecisionReceipt` is not:

```text
application logging
generic error logging
full diagnostic tracing
retry attempt logging
runtime decision execution
strategy selection
observability event stream
metrics backend
persistence state
```

This means:

```text
DecisionReceipt
≠
application log

DecisionReceipt
≠
DiagnosticTrace

DecisionReceipt
≠
AttemptLog

DecisionReceipt
≠
Runtime Decision Authority
```

Operational logs may still exist in ELK, Loki, CloudWatch, local files, or another observability system.
DecisionReceipt is narrower: it preserves semantic governance evidence that future runtime governance may need to reference.

---

## Separate Semantic Axes

Stage 4B keeps the following questions separate:

```text
SemanticOutcome
= what the runtime evidence means semantically

DecisionReceiptEvidenceSource
= which runtime evidence path produced the receipt evidence

DecisionReceiptIdentitySource
= the primary provenance of correlation evidence

EventAdmissionDisposition
= what happened to an event attempt at write-side admission
```

These axes must not be inferred from one another.

For example:

```text
evidence_source = WRITE_SIDE_ADMISSION
technical_status = LOCK_TIMEOUT
```

preserves two independent facts:

```text
where the evidence came from
what condition was observed within that path
```

Likewise:

```text
candidate_event_id is present
```

does not prove:

```text
the event entered accepted history
```

Admission fate must remain explicit.

---

## Evidence Path vs Technical Status

`DecisionReceiptEvidenceSource` records the runtime path that produced the receipt evidence.

Current values are:

```text
WRITE_SIDE_ADMISSION
READ_SIDE_PATH
SNAPSHOT_TRUST_PATH
SNAPSHOT_ASSISTED_PATH
RUNTIME_OBSERVATION
UNKNOWN
```

Technical status remains a separate evidence detail and may be preserved inside `evidence_summary`.

The governing distinction is:

```text
evidence_source
= where the evidence came from

technical_status
= what condition was observed within that path
```

A status name alone must not determine the evidence source.

Concrete adapter ownership should decide the path:

```text
write-side receipt adapter
→ WRITE_SIDE_ADMISSION

read-side receipt adapter
→ READ_SIDE_PATH

snapshot trust receipt adapter
→ SNAPSHOT_TRUST_PATH

snapshot-assisted receipt adapter
→ SNAPSHOT_ASSISTED_PATH
```

---

## Receipt vs Diagnostic Trace

A receipt stores summary-level governance evidence.

A diagnostic trace stores detailed path evidence.

```text
DecisionReceipt
= compact summary evidence

DiagnosticTrace
= detailed failure path, partial progress, replay cursor, resolver path, and debugging trace
```

Trace-only evidence includes details such as:

```text
partial replay progress
last cursor before failure
validator internal branch path
resolver internal branch path
tail event parsing detail
fallback path exploration detail
exception stack trace
large intermediate state payload
```

Those details may be useful, but they belong to Stage 4B.1 `DiagnosticTrace` / `ResolutionTrace`, not the Stage 4B receipt boundary.

---

## Receipt vs Runtime Decision Authority

A receipt records evidence.

Runtime Decision Authority authorizes the generic response to a current
observation from eligible evidence.

```text
DecisionReceipt
= evidence

Runtime Decision Authority
= current-response authorization
```

A receipt may preserve completed tri-state evaluations such as:

```text
operator_review_required = TRUE | FALSE | NOT_EVALUATED
fallback_required = TRUE | FALSE | NOT_EVALUATED
rebuild_required = TRUE | FALSE | NOT_EVALUATED
retry_candidate = TRUE | FALSE | NOT_EVALUATED
```

but Stage 4B does not execute operator review, fallback, rebuild, quarantine,
retry, or strategy selection. Those belong to later, separately owned runtime
decision, strategy-selection, and retry / attempt-authorization boundaries.

Current producer adapters leave every flag `NOT_EVALUATED`. Only a later
authorized evaluator may assert `TRUE` or `FALSE`.

In particular:

```text
retry_candidate
≠
authorization for another attempt
```

A receipt may preserve retry-relevant evidence.
It does not authorize a retry.

---

## Receipt-Safe Evidence

Receipt-safe evidence should be:

```text
compact
stable
serializable
reviewable
safe to query
safe to reference later
not overly implementation-specific
not dependent on live runtime objects
```

Examples include explicit IDs and typed summary fields:

```text
order_id
request_id
candidate_event_id
accepted_event_id
snapshot_id
source_global_position
actor_id
actor_role
runtime_role
elapsed_ms
validation_elapsed_ms
replay_elapsed_ms
transaction_elapsed_ms
lock_wait_ms
accepted_event_count
tail_event_count
```

The full `SemanticOutcome.context` or `SemanticOutcome.evidence` should not automatically become receipt evidence.
The receipt mapping boundary decides what is safe to preserve.

---

## JSON-Safe Evidence Boundary

Flexible receipt evidence must be JSON-safe.

The current contract accepts:

```text
str
int
finite float
bool
None
list / tuple of JSON-safe values
mapping with non-empty string keys and JSON-safe values
```

It rejects:

```text
UUID objects
Decimal values
datetime values
sets
callbacks
exception objects
database connections
validator instances
arbitrary Python objects
non-finite floats
overly deep or cyclic object graphs
```

Useful runtime objects must be converted to stable representations first.

For example:

```text
UUID object
→ string identifier

Exception object
→ only an explicitly reviewed stable category or code
```

Arbitrary exception messages are not automatically receipt-safe. Raw database
exception text, SQL details, constraint diagnostics, stack traces, and other
unstable technical reason text remain operational or diagnostic evidence. The
current write-side runtime retains only the bounded live category
`UNEXPECTED_COMPOSITION_EXCEPTION` for an unexpected receipt-composition
exception; it does not retain the raw exception object or text as durable
receipt evidence.

Receipt evidence is recursively frozen after validation.

A JSON boolean remains valid JSON evidence, but it must not be accepted as an integer counter, elapsed-time value, or global position.

---

## Non-Authoritative Evidence

Some evidence may help review but should not become authority.

Examples:

```text
caller-provided context
metadata_json values not promoted to schema-level contract
debug labels
producer metadata
created_by-style fields
runtime role labels
```

Non-authoritative evidence may enrich a receipt.
It must not override protected identity fields.

For example, `ValidationResult.metadata["order_id"]` should not be treated as authoritative identity unless `order_id` is later promoted to a first-class `ValidationResult` field.

---

## Contradictory Evidence

A normal `DecisionReceipt` must not be built on contradictory protected identity evidence.

For example:

```text
stream_admission_result.order_id = order-001
idempotency_record.signature.order_id = evil-order
→ normal receipt mapping refused
```

or:

```text
idempotency_record.accepted_event.request_id = request-001
idempotency_record.signature.request_id = evil-request
→ normal receipt mapping refused
```

Stage 4B should not silently choose one identity source and proceed.
If protected identity evidence contradicts itself, the system should preserve that as an abnormal mapping condition rather than pretending the lineage is clean.

---

## Candidate Identity vs Accepted-History Identity

Stage 4B must preserve the distinction between candidate evidence and accepted truth.

```text
candidate_event_id
= identifies a proposed event attempt

accepted_event_id
= identifies an event proven to belong to accepted history
```

A rejected or conflicted candidate must not carry an `accepted_event_id` as if it became accepted history.

An idempotency conflict may expose a prior `accepted_event_id`, but that identifier belongs to the previous accepted request, not the current rejected candidate.

For validation-only blocked candidates, an `order_id` may be useful for review and query, but it should be classified as candidate-derived correlation evidence unless it comes from accepted-history authority.

---

## Event Admission Fate

`DecisionReceiptAdmissionEvidence` records typed write-side admission fate through `EventAdmissionDisposition`.

Current values are:

```text
ADMITTED_TO_ACCEPTED_HISTORY
MATCHED_EXISTING_ACCEPTED_EVENT
IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
APPEND_TECHNICAL_FAILURE
COMMIT_OUTCOME_UNRESOLVED
APPEND_ADMISSION_NOT_REACHED
UNKNOWN
```

Event identifiers remain owned by `DecisionReceiptCorrelation`.
Admission evidence owns only the disposition.

This avoids duplicating candidate and accepted event IDs across two contract objects.

### Newly admitted event

```text
candidate_event_id is present
accepted_event_id is present
candidate_event_id == accepted_event_id
disposition = ADMITTED_TO_ACCEPTED_HISTORY
```

The event identity remains the same.
Its authority role changes when accepted-history membership is established.

### Idempotent replay

An idempotent replay must identify the existing accepted event:

```text
accepted_event_id is present
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

`candidate_event_id` is optional.

It may be absent when an early idempotency lookup returns the existing accepted event before a new candidate is constructed:

```text
candidate_event_id = None
accepted_event_id = existing accepted event
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

If a candidate was already constructed, its identifier may also be preserved and may differ from the existing accepted event identifier.

### Non-accepted candidate

For:

```text
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
APPEND_TECHNICAL_FAILURE
COMMIT_OUTCOME_UNRESOLVED
```

the current contract requires:

```text
candidate_event_id is present
accepted_event_id is absent
```

This means the receipt has evidence for a candidate event but does not have authoritative evidence that permits it to name an accepted event.

For `COMMIT_OUTCOME_UNRESOLVED`, the absent accepted ID does not prove rollback.

`COMMIT_OUTCOME_UNRESOLVED` is currently reserved contract vocabulary.
No current production producer is established for it, and generic infrastructure failures must not be mapped to it automatically.

### Append admission not reached

For:

```text
APPEND_ADMISSION_NOT_REACHED
```

the current contract requires:

```text
candidate_event_id is optional
accepted_event_id is absent
```

This means candidate-level `append_if_admitted(...)` was not invoked. A
candidate may already exist in an explicitly selected non-default or custom
composition where candidate construction precedes a rejecting
`prepare_stream(...)` result.

---

## Identity Provenance Boundary

`DecisionReceiptCorrelation.identity_source` records the primary provenance of the correlation block.

Current values are:

```text
ACCEPTED_HISTORY
CANDIDATE_EVENT_IDENTITY
WRITE_SIDE_CORRELATION
READ_SIDE_OBSERVATION
SNAPSHOT_LINEAGE
CALLER_CONTEXT
UNKNOWN
```

The field is not yet field-level provenance.

A receipt may contain fields that originated at different boundaries.
The current primary-source model is an explicit limitation, not a claim that every field shares exactly one source.

Field-level identity provenance should be introduced only when future adapters, persistence queries, operator tooling, or runtime policy require authority decisions for individual correlation fields.

---

## Durable Persistence Boundary

Stage 4B PR6 implements the durable persistence foundation after the receipt
contract and mapping shape stabilized.

The durable table should store receipt-level evidence, not every log, trace, retry attempt, or policy decision.

A useful direction is:

```text
stable identity / correlation fields
→ first-class columns where useful for query and review

flexible summary evidence
→ JSON-safe evidence_summary / cost_summary / metadata_json

full diagnostic paths
→ DiagnosticTrace / ResolutionTrace, not decision_receipts

retry attempt sequences
→ future AttemptLog / attempt-governance evidence, not decision_receipts
```

This keeps the persistence layer aligned with the receipt boundary instead of becoming a generic observability table.

The foundation is explicitly invoked by callers. Stage 4B does not
automatically materialize mapper outputs, scan accepted history, reconcile
missing receipts, publish receipts through an outbox, or own a publication
cursor.

### Current explicit PostgreSQL runtime composition

A later PR1–PR3 runtime-composition increment now provides the canonical
explicit write-side path:

```text
PostgresWriteSideResult
→ one retained completed-invocation handle
→ explicit compose_receipt()
→ PR1 materialization
→ PR2 commit-aware persistence composition
→ separate PostgreSQL governance transaction
```

`invoke_initial()` completes the business invocation and publishes the handle;
it does not implicitly persist a receipt. Receipt work begins only after a
normal business result exists and only when `compose_receipt()` is called.

The runtime delivery preserves three independent meanings:

```text
business result
!= receipt materialization
!= receipt persistence
```

Therefore:

```text
ACCEPTED + receipt NOT_COMMITTED
→ business remains ACCEPTED

ACCEPTED + receipt UNKNOWN
→ business remains ACCEPTED

VALIDATION_BLOCKED + receipt COMMITTED
→ no accepted business effect was created
```

The business and receipt transactions are separate. Receipt failure does not
roll back or rewrite completed business truth, and the architecture does not
claim a distributed atomic transaction.

### Fail-closed persistence eligibility

Receipt materializability does not imply automatic durable-persistence
eligibility:

```text
materializable
!= persistence-eligible
```

The current reviewed positive profiles are `ACCEPTED`, `REPLAY`, `CONFLICT`,
`VALIDATION_BLOCKED`, and preparation-phase `LOCK_TIMEOUT`. The last profile is
selected from typed lifecycle position, not reason text. Every unmatched or
unreviewed profile fails closed. Current append-time rejection and
infrastructure profiles remain persistence-ineligible.

```text
PERSISTENCE_INELIGIBLE
= persistence deliberately not reached

NOT_COMMITTED
= persistence attempted and known not committed

UNKNOWN
= persistence attempted but durability unresolved
```

An append-time `STALE_WRITE` receipt shape may be materializable, but current
PR3 eligibility does not permit its automatic durable persistence. Under ADR
0030, the coarse verdict alone is not proof of concurrency, retryability, or
re-invocation authority.

### Canonical live custody and later authority boundaries

For each normal completion, the runtime owner retains one canonical owner-local
live PR1/PR2 graph and one cached terminal runtime delivery. This guarantee
applies only to the canonical application path. It is not global exactly-once,
process-independent uniqueness, durable receipt identity, or durable attempt
identity.

A1 and a Stage 4E-authorized A2 retain distinct bounded completed-invocation
handles, PR1/PR2 graphs, receipt identities, and receipt-path outcome identities
while sharing the same `RequestSignature`. A1 remains accessible after A2 moves
the invocation owner's current-response state. No `AttemptLog`, unbounded
attempt collection, or A3 is introduced.

Receipt composition does not invoke Stage 4C or allocate its lazy identity;
receipt-path `outcome_id` need not equal Stage 4C's identity. Receipt persistence
also does not create Stage 4E authority. Stage 4E remains the independent
boundary for one reviewed same-request A2.

An unexpected receipt-composition exception becomes the bounded live status
`UNEXPECTED_COMPOSITION_EXCEPTION`. The exact business result remains available,
the completed handle becomes terminal for receipt composition, and later access
does not automatically re-enter PR2. This is not a general operational
diagnostic framework.

See the
[DecisionReceipt Runtime Composition Closeout](../implementation_notes/stage_4b/decision_receipt_runtime_composition_closeout.md)
for the current source and test map.

---

## Java / Rust Portability

DecisionReceipt is a core runtime governance contract.

Even if the current implementation is Python, the contract should remain portable to future Java / JVM or Rust implementations.

Prefer:

```text
explicit typed fields
JSON-safe evidence payloads
IDs instead of live object graphs
stable mapping behavior
no recovery execution inside mapping
```

Avoid receipt evidence such as:

```text
validator instances
resolver instances
database connections
exception objects
callbacks
lambdas
live OrderEvent object graphs
live ProjectionSnapshot objects
arbitrary dict[str, Any]
```

The receipt should preserve evidence, not runtime object ownership.

---

## Current Stage 4B Responsibility Split

```text
PR2
= runtime contract and contract invariants

PR3
= generic SemanticOutcome → DecisionReceipt adapter

PR4
= concrete write-side admission receipt mapping

PR5
= concrete read-side and snapshot receipt mapping

PR6
= serialization and durable persistence
```

PR2 defines which receipt states are constructable.

It does not claim that concrete runtime adapters already produce every state in the vocabulary.

---

## Summary

Stage 4B introduces explicit mapping for selected observations:

```text
SemanticOutcome
→ DecisionReceipt
```

This does not mean that every `SemanticOutcome` produces or persists a receipt
automatically.

The receipt is not a log.
The receipt is not a trace.
The receipt is not a policy decision.
The receipt is compact durable governance evidence.

The key rule is:

```text
persist selected semantic governance evidence,
not arbitrary operational detail
```

The additional Stage 4B contract rule is:

```text
semantic meaning,
evidence path,
identity provenance,
and accepted-history admission fate
must remain separate concepts
```
