# ADR 0017: Separate Evidence Path, Identity Provenance, and Event Admission Fate in DecisionReceipt

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Implemented at the Stage 4B runtime-contract baseline.

The current `DecisionReceipt` contract now includes:

- evidence-path vocabulary through `DecisionReceiptEvidenceSource`
- subject and correlation separation
- primary identity provenance through `DecisionReceiptIdentitySource`
- typed write-side admission fate through `EventAdmissionDisposition`
- `DecisionReceiptAdmissionEvidence`
- cross-field validation between admission disposition and candidate / accepted event identities
- early idempotent replay support when no new candidate event exists

Field-level identity provenance is intentionally deferred. The current
`identity_source` field represents the primary source for the correlation block.

---

## Context

ADR 0016 established that `DecisionReceipt` is durable semantic governance
evidence rather than application logging, a generic error record, a diagnostic
trace, or a retry-attempt log.

Once the initial receipt contract was drafted, three different semantic axes
were still at risk of being collapsed:

```text
1. where the receipt evidence came from
2. where the receipt identity / lineage evidence came from
3. what ultimately happened to a candidate event at the write-side admission boundary
```

These questions are related, but they are not interchangeable.

A technical status such as:

```text
LOCK_TIMEOUT
```

does not identify an evidence path. A lock timeout may occur inside
write-side admission, snapshot-assisted resolution, or a generic runtime
observation.

Likewise, the presence of:

```text
candidate_event_id
accepted_event_id
```

does not by itself explain the authority or relationship of those identities.

A candidate may:

```text
be admitted as the same event identity
match an existing accepted event as an idempotent replay
be semantically rejected
encounter an append concurrency conflict
reach an unresolved commit outcome
never reach event admission
```

Without a typed admission-fate contract, readers and future governance layers
would need to infer these meanings from nullable identifiers, free-form reason
strings, or JSON evidence.

That would leave room for governance interpretation errors even if the
authoritative domain aggregate, Compass Layer 1, transaction boundary, and
accepted event history remained correct.

---

## Problem

The initial `DecisionReceipt` vocabulary mixed concepts that belonged to
different semantic dimensions.

### Evidence source ambiguity

The initial evidence-source vocabulary included names such as:

```text
RUNTIME_TECHNICAL_STATUS
READ_SIDE_REPLAY
SNAPSHOT_REPLAY
SNAPSHOT_ASSISTED_RESOLUTION
WRITE_SIDE_ADMISSION
```

These names mixed:

```text
runtime path
technical status category
specific operation
successful result wording
```

For example:

```text
LOCK_TIMEOUT
```

should remain a technical status inside receipt evidence. If it occurred during
write-side admission, the evidence path should remain:

```text
WRITE_SIDE_ADMISSION
```

The technical condition must not replace the path that produced it.

### Identity-source ambiguity

The initial identity-source vocabulary included:

```text
PRE_ADMISSION_CANDIDATE
WRITE_SIDE_ORCHESTRATION
```

`PRE_ADMISSION_CANDIDATE` could be read as:

```text
before Compass validation
before OCC
before append
before transaction commit
```

However, a candidate may already have passed semantic validation and still fail
during append or commit.

`WRITE_SIDE_ORCHESTRATION` was also broader than the actual purpose of the
field, which is to record write-side correlation provenance rather than the
entire orchestration process.

### Candidate / accepted-event ambiguity

The initial receipt correlation could contain:

```text
candidate_event_id
accepted_event_id
```

but did not formally represent their relationship.

The following state was ambiguous:

```text
candidate_event_id = candidate-A
accepted_event_id = None
```

It could mean:

```text
rejected before append
append conflict
commit outcome unresolved
admission not reached
missing mapping evidence
```

Likewise:

```text
candidate_event_id = candidate-B
accepted_event_id = accepted-A
```

could mean:

```text
newly accepted event
idempotent replay matched to an existing event
unexplained or contradictory identity evidence
```

Nullable identifiers alone were not a safe governance contract.

---

## Decision

`DecisionReceipt` will represent the following concepts separately:

```text
SemanticOutcome
= what the runtime evidence means semantically

DecisionReceiptEvidenceSource
= which runtime evidence path produced the receipt

DecisionReceiptIdentitySource
= the primary provenance of the receipt correlation block

DecisionReceiptAdmissionEvidence
= the typed write-side admission fate of an event attempt

DecisionReceiptCorrelation
= the queryable event, request, order, snapshot, and lineage identifiers
```

The current evidence-path vocabulary is:

```text
WRITE_SIDE_ADMISSION
READ_SIDE_PATH
SNAPSHOT_TRUST_PATH
SNAPSHOT_ASSISTED_PATH
RUNTIME_OBSERVATION
UNKNOWN
```

The current identity-provenance vocabulary is:

```text
ACCEPTED_HISTORY
CANDIDATE_EVENT_IDENTITY
WRITE_SIDE_CORRELATION
READ_SIDE_OBSERVATION
SNAPSHOT_LINEAGE
CALLER_CONTEXT
UNKNOWN
```

The current event-admission vocabulary is:

```text
ADMITTED_TO_ACCEPTED_HISTORY
MATCHED_EXISTING_ACCEPTED_EVENT
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
COMMIT_OUTCOME_UNRESOLVED
ADMISSION_NOT_REACHED
UNKNOWN
```

Event identifiers remain owned by `DecisionReceiptCorrelation`.

`DecisionReceiptAdmissionEvidence` stores only admission fate and must not
duplicate candidate or accepted event identifiers.

The receipt runtime contract must validate the admission disposition against the
correlation identities.

---

## Rationale

### Evidence path must not be replaced by technical status

The receipt must be able to represent:

```text
evidence_source = WRITE_SIDE_ADMISSION
technical_status = LOCK_TIMEOUT
```

This preserves two independent facts:

```text
where the evidence came from
what condition occurred within that path
```

Renaming `RUNTIME_TECHNICAL_STATUS` to `RUNTIME_OBSERVATION` prevents the
misleading implication that all technical conditions belong to that evidence
source.

### Read-side and snapshot names must describe boundaries, not implementations

`READ_SIDE_PATH` is broader and more stable than `READ_SIDE_REPLAY`.

Read-side evidence may come from:

```text
projection validation
derived-state comparison
checkpoint inspection
replay
read-side observation
```

`SNAPSHOT_TRUST_PATH` is more accurate than `SNAPSHOT_REPLAY` because the
boundary evaluates whether snapshot-derived evidence is trustworthy, not merely
whether replay occurred.

`SNAPSHOT_ASSISTED_PATH` is more accurate than
`SNAPSHOT_ASSISTED_RESOLUTION` because the path can succeed, fail, be
unavailable, detect drift, or require fallback.

### Candidate identity must not imply a particular validation phase

`CANDIDATE_EVENT_IDENTITY` states only that the identity came from a candidate
event.

It does not claim that the candidate is:

```text
before semantic validation
before OCC
before append
before commit
```

This is important because semantic validity and accepted-history admission are
different facts.

### Write-side correlation must be named by its actual responsibility

`WRITE_SIDE_CORRELATION` describes identifiers generated or managed by the
write-side processing path, such as:

```text
request correlation
attempt correlation
idempotency correlation
command-handling correlation
```

It does not describe the candidate event itself and does not claim accepted-
history authority.

### Admission fate must be typed

A candidate can be semantically valid without entering accepted history.

For example:

```text
semantic validation passed
+
append conflict
```

This cannot safely be represented by a generic success flag or by
`accepted_event_id is None`.

A typed disposition allows the receipt to distinguish:

```text
known semantic rejection
known append concurrency conflict
unknown commit result
admission not reached
idempotent match
successful append
```

This makes the receipt safe for human review and future policy consumption.

---

## Event Identity Model

### Newly admitted event

For a normal event that is appended to accepted history, the current model
preserves one event identity across lifecycle roles:

```text
candidate_event_id = event-A
accepted_event_id = event-A
disposition = ADMITTED_TO_ACCEPTED_HISTORY
```

The identity does not change. Its authority role changes when accepted-history
membership is established.

### Idempotent replay

An early idempotent replay may be resolved before a new candidate is created:

```text
candidate_event_id = None
accepted_event_id = event-A
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

If a candidate was already created before the existing accepted event was
identified, the receipt may preserve both identities:

```text
candidate_event_id = event-B
accepted_event_id = event-A
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

The current candidate is not appended as a new accepted event. It is associated
with an existing accepted-history event.

### Rejected, conflicted, or unresolved candidate

For:

```text
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
COMMIT_OUTCOME_UNRESOLVED
```

the receipt requires:

```text
candidate_event_id != None
accepted_event_id = None
```

In the unresolved-commit case, `accepted_event_id = None` does not prove that
the transaction rolled back. It means the receipt lacks authoritative evidence
that permits it to name an accepted event.

### Admission not reached

For:

```text
ADMISSION_NOT_REACHED
```

the receipt requires:

```text
candidate_event_id = None
accepted_event_id = None
```

This prevents request-level or infrastructure failure from being misrepresented
as candidate-level admission evidence.

---

## Cross-Field Invariants

The runtime contract enforces the following invariants.

### `ADMITTED_TO_ACCEPTED_HISTORY`

Requires:

```text
candidate_event_id is present
accepted_event_id is present
candidate_event_id == accepted_event_id
```

### `MATCHED_EXISTING_ACCEPTED_EVENT`

Requires:

```text
accepted_event_id is present
candidate_event_id may be present or absent
```

If the candidate identifier is present, the identifiers may differ.

### `SEMANTIC_ADMISSION_REJECTED`

Requires:

```text
candidate_event_id is present
accepted_event_id is absent
```

### `APPEND_CONCURRENCY_CONFLICT`

Requires:

```text
candidate_event_id is present
accepted_event_id is absent
```

### `COMMIT_OUTCOME_UNRESOLVED`

Requires:

```text
candidate_event_id is present
accepted_event_id is absent
```

The absence of an accepted ID means there is no authoritative accepted-history
evidence available to the receipt.

No current production producer is established for this disposition. Generic
infrastructure failures must not be mapped to it automatically.

### `ADMISSION_NOT_REACHED`

Requires:

```text
candidate_event_id is absent
accepted_event_id is absent
```

These rules make contradictory receipt states unconstructable at the runtime
contract boundary.

---

## Identity Provenance Boundary

`DecisionReceiptCorrelation.identity_source` currently represents the primary
source of the correlation block.

It is not field-level provenance.

A receipt may contain:

```text
request_id from WRITE_SIDE_CORRELATION
candidate_event_id from CANDIDATE_EVENT_IDENTITY
accepted_event_id from ACCEPTED_HISTORY
snapshot_id from SNAPSHOT_LINEAGE
```

The current contract intentionally selects one primary source rather than
introducing a field-level provenance map prematurely.

This is an explicit limitation, not an implicit claim that all correlation
fields share one source.

Field-level identity provenance should be introduced only when future adapters,
persistence queries, audit workflows, or runtime policies must make automated
authority decisions about individual correlation fields.

---

## Why Admission Evidence Does Not Own Event IDs

An alternative design would place:

```text
candidate_event_id
accepted_event_id
disposition
```

inside `DecisionReceiptAdmissionEvidence`.

This was rejected because the same identifiers already exist in
`DecisionReceiptCorrelation`.

Duplicating them would permit contradictory objects such as:

```text
correlation.candidate_event_id = event-A
admission_evidence.candidate_event_id = event-B
```

The selected ownership rule is:

```text
DecisionReceiptCorrelation
= identity ownership

DecisionReceiptAdmissionEvidence
= admission-fate ownership
```

Cross-field validation connects the two contracts.

---

## Examples

### Newly accepted candidate

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = ACCEPTED_EVENT
identity_source = ACCEPTED_HISTORY
candidate_event_id = event-A
accepted_event_id = event-A
disposition = ADMITTED_TO_ACCEPTED_HISTORY
```

### Early idempotent replay

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = ACCEPTED_EVENT
identity_source = ACCEPTED_HISTORY
candidate_event_id = None
accepted_event_id = event-A
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

### Idempotent replay after candidate construction

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = ACCEPTED_EVENT
identity_source = ACCEPTED_HISTORY
candidate_event_id = event-B
accepted_event_id = event-A
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

### Compass-blocked candidate

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = CANDIDATE_EVENT
identity_source = CANDIDATE_EVENT_IDENTITY
candidate_event_id = event-C
accepted_event_id = None
disposition = SEMANTIC_ADMISSION_REJECTED
```

### OCC append conflict after semantic validation

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = CANDIDATE_EVENT
identity_source = CANDIDATE_EVENT_IDENTITY
candidate_event_id = event-D
accepted_event_id = None
disposition = APPEND_CONCURRENCY_CONFLICT
```

This explicitly preserves:

```text
semantic validation may have passed
accepted-history admission did not succeed
```

### Commit outcome unresolved

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = CANDIDATE_EVENT
identity_source = CANDIDATE_EVENT_IDENTITY
candidate_event_id = event-E
accepted_event_id = None
disposition = COMMIT_OUTCOME_UNRESOLVED
```

This does not claim either commit success or rollback.

### Failure before candidate creation

```text
evidence_source = WRITE_SIDE_ADMISSION
subject = REQUEST
identity_source = WRITE_SIDE_CORRELATION
candidate_event_id = None
accepted_event_id = None
disposition = ADMISSION_NOT_REACHED
```

---

## Alternatives Considered

### Alternative 1: Keep the original enum names

Rejected.

The original names mixed evidence paths, technical status categories, replay
operations, and successful-result language.

This would preserve ambiguity in adapter mappings and future review.

### Alternative 2: Put admission fate in `evidence_summary`

Rejected as the durable contract.

Free-form JSON is appropriate for diagnostic and adapter-specific detail, but
authority-bearing relationships must be typed if later governance layers may
consume them.

Strings such as:

```text
"candidate_to_accepted_relation": "ADMITTED_AS"
```

would not prevent missing IDs, contradictory IDs, spelling drift, or incomplete
mappings.

### Alternative 3: Infer disposition from nullable IDs

Rejected.

`accepted_event_id = None` cannot distinguish rejection, append conflict,
unresolved commit, admission not reached, or incomplete mapping.

### Alternative 4: Treat semantic validity as proof of accepted-history admission

Rejected.

A candidate can pass domain and Compass validation and still fail during OCC,
append, or commit.

The architecture must preserve:

```text
semantic validity
≠
accepted-history admission
```

### Alternative 5: Add field-level identity provenance immediately

Deferred.

It would improve precision, but current adapters do not yet require automated
authority decisions for every correlation field.

The primary-source model is sufficient for the present contract as long as its
limitation is explicit.

### Alternative 6: Require a candidate ID for every idempotent replay

Rejected.

The write-side path may identify an existing accepted event before constructing
a new candidate. Requiring a candidate ID would force the adapter to invent an
identity or refuse a truthful receipt.

### Alternative 7: Duplicate event IDs inside admission evidence

Rejected.

This would create multiple owners for the same identity and allow contradictory
receipt state.

---

## Consequences

### Positive Consequences

- Evidence source now consistently describes a path or observation source.
- Technical status remains independent from evidence path.
- Candidate identity no longer implies a particular pre-validation phase.
- Write-side correlation is separated from candidate identity.
- Candidate fate is explicit and machine-readable.
- Idempotent replay is distinct from newly admitted events.
- Rejection, append conflict, unresolved commit, and admission-not-reached are
  distinct states.
- Cross-field invariants reject contradictory receipt construction.
- Human reviewers do not need to infer admission fate from nullable IDs.
- Future policy, retry, audit, and operator tooling can consume stable typed
  evidence.
- Flexible JSON remains available for diagnostics without carrying the primary
  authority relation.

### Negative Consequences

- Adds another enum and supporting dataclass.
- Adds cross-field validation complexity.
- Adapter mappings must provide accurate disposition values.
- Incorrect mapping may now fail loudly instead of producing a partial receipt.
- Future persistence schemas must account for admission evidence.
- The primary identity-source model still cannot represent field-level
  provenance.

### Neutral but Important Consequences

`DecisionReceipt` remains evidence, not action.

The presence of:

```text
retry_candidate = true
fallback_required = true
operator_review_required = true
```

does not execute retry, fallback, or operator review.

The authoritative business result remains governed by:

```text
Domain Aggregate
Compass Layer 1
transaction / concurrency admission
accepted event history
```

This ADR improves governance evidence correctness. It does not replace those
authoritative runtime boundaries.

---

## Future Trigger Conditions

Revisit this ADR when one or more of the following become true:

```text
1. A receipt adapter must preserve multiple identity sources and future policy
   must reason about each field independently.
2. DecisionReceipt persistence requires field-level authority queries.
3. RetryGovernance determines retry safety from candidate and accepted-event
   provenance.
4. AttemptLog links multiple requests, attempts, candidates, and accepted events.
5. Operator review tooling must distinguish caller-provided, candidate-derived,
   write-side-generated, and accepted-history identities per field.
6. Snapshot-assisted receipts combine snapshot lineage with accepted-history
   tail-event identity and require field-level provenance.
7. A deployment needs formal audit evidence for individual correlation fields.
8. New admission dispositions are required for additional append or commit
   protocols.
```

The likely future extension is:

```text
primary identity_source
+
field-level identity provenance
```

The primary source should remain available for compact review, while field-level
provenance supplies exact authority for automated consumers.

---

## Relationship to Other ADRs

### ADR 0003

ADR 0003 defines concurrency, idempotency, and retry-safety boundaries.

This ADR supplies typed receipt evidence for outcomes such as:

```text
idempotent replay
append conflict
commit outcome unresolved
```

It does not itself decide retry safety.

### ADR 0008

ADR 0008 defines pre-allocated event identity and the candidate / accepted event
naming boundary.

This ADR applies that lifecycle rule to `DecisionReceipt` evidence:

```text
event identity may exist as a candidate
accepted-history membership grants accepted authority
```

### ADR 0012

ADR 0012 defines two-phase concurrency admission.

This ADR records the resulting admission fate without collapsing semantic
validation and append outcome.

### ADR 0013

ADR 0013 separates snapshot trust, runtime eligibility, and future validation
receipts.

This ADR applies the same boundary discipline by separating:

```text
SNAPSHOT_TRUST_PATH
SNAPSHOT_ASSISTED_PATH
```

### ADR 0016

ADR 0016 defines `DecisionReceipt` as semantic governance evidence rather than
application logging.

This ADR refines the internal semantic contract of that evidence by separating:

```text
evidence path
identity provenance
event admission fate
```

---

## Current Decision Summary

The current Stage 4B contract adopts the following model:

```text
SemanticOutcome
= semantic interpretation

DecisionReceiptEvidenceSource
= evidence path

DecisionReceiptCorrelation
= queryable identity and lineage fields

DecisionReceiptIdentitySource
= primary correlation provenance

DecisionReceiptAdmissionEvidence
= typed write-side admission fate

EventAdmissionDisposition
= machine-readable candidate-to-accepted-history outcome
```

The decisive rule is:

```text
semantic validity,
evidence path,
identity provenance,
and accepted-history admission fate
must remain separate concepts.
```

A receipt must not require a human or future policy layer to infer authoritative
admission meaning from nullable identifiers or free-form JSON.
