# SemanticOutcome to DecisionReceipt Adapter

[← Back to Stage 4B](README.md)

## Purpose

This note defines the Stage 4B PR3 implementation contract for:

```text
SemanticOutcome
→ DecisionReceipt
```

Stage 4A already converts bounded technical runtime evidence into
`SemanticOutcome`.

Stage 4B PR2 already defines the typed `DecisionReceipt` runtime contract.

PR3 fills the generic construction boundary between them.

The core question is:

```text
How can a SemanticOutcome become a DecisionReceipt without reinterpreting
semantic meaning, inventing authority, or copying arbitrary runtime payloads?
```

The answer is:

```text
Preserve the typed semantic tuple exactly.
Require receipt identity and evidence path explicitly.
Accept only explicitly selected supporting receipt evidence.
Do not inspect or copy open-ended SemanticOutcome mappings.
```

---

## Core Relationship

```text
technical runtime evidence
→ Stage 4A producer adapter
→ SemanticOutcome
→ PR3 generic receipt adapter
→ DecisionReceipt
```

PR3 is a thin constructor adapter.

It is not a producer-specific evidence mapper.

```text
PR3
= generic receipt construction

PR4
= write-side admission receipt mapping

PR5
= read-side / snapshot receipt mapping

PR6
= serialization and durable persistence
```

---

## Required Semantic Preservation

The adapter must copy the complete semantic tuple exactly:

```text
SemanticOutcome.outcome_id
→ DecisionReceipt.outcome_id

SemanticOutcome.ok
→ DecisionReceipt.ok

SemanticOutcome.boundary
→ DecisionReceipt.boundary

SemanticOutcome.category
→ DecisionReceipt.category

SemanticOutcome.semantic_code
→ DecisionReceipt.semantic_code

SemanticOutcome.severity
→ DecisionReceipt.severity

SemanticOutcome.risk_level
→ DecisionReceipt.risk_level

SemanticOutcome.reversibility
→ DecisionReceipt.reversibility

SemanticOutcome.reason
→ DecisionReceipt.reason
```

The adapter must not perform a second semantic interpretation.

For example, it must not change:

```text
CONCURRENCY_UNCERTAIN
→ ESCALATION_REQUIRED
```

or:

```text
FAST_PATH_UNAVAILABLE
→ DRIFT_DETECTED
```

The rule is:

```text
SemanticOutcome → DecisionReceipt
= preservation

SemanticOutcome → DecisionReceipt
≠ remapping
```

---

## Recommended Minimal API

```python
def map_semantic_outcome_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome: SemanticOutcome,
    evidence_source: DecisionReceiptEvidenceSource,
    subject: DecisionReceiptSubject | None = None,
    correlation: DecisionReceiptCorrelation | None = None,
    actor: DecisionReceiptActor | None = None,
    cost_summary: DecisionReceiptCostSummary | None = None,
    flags: DecisionReceiptFlags | None = None,
    admission_evidence: DecisionReceiptAdmissionEvidence | None = None,
    evidence_summary: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> DecisionReceipt:
    ...
```

No selector class, allowlist object, callback extractor, or generic
context/evidence conversion abstraction is required for PR3.

There is no current producer, consumer, or test need for those abstractions.

---

## Receipt Identity Ownership

`receipt_id` must be supplied explicitly.

PR3 must not call:

```python
uuid4()
```

inside the mapper.

Receipt identity creation belongs to caller / orchestration.

This preserves:

```text
explicit identity ownership
deterministic tests
future replay compatibility
future persistence compatibility
absence of hidden mapper side effects
```

PR6 may later enforce durable uniqueness, but persistence must not retroactively
own semantic receipt construction.

---

## Evidence Source Ownership

`DecisionReceiptEvidenceSource` must be supplied explicitly.

PR3 must not infer evidence source from:

```text
technical_status
SemanticOutcome.boundary
SemanticOutcome.category
SemanticOutcome.semantic_code
SemanticOutcome.ok
```

The same technical or semantic status may be observed through different runtime
paths.

Concrete producer ownership belongs to later adapters:

```text
ReplayValidationResult
→ READ_SIDE_PATH

ProjectionSnapshotReplayValidationResult
→ SNAPSHOT_TRUST_PATH

ProjectionSnapshotAssistedResolutionResult
→ SNAPSHOT_ASSISTED_PATH

PostgresWriteSideResult
→ WRITE_SIDE_ADMISSION
```

PR3 accepts the selected evidence source.

PR4 and PR5 decide it.

---

## Supporting Contracts

PR3 may accept explicit typed supporting contracts:

```text
DecisionReceiptSubject
DecisionReceiptCorrelation
DecisionReceiptActor
DecisionReceiptCostSummary
DecisionReceiptFlags
DecisionReceiptAdmissionEvidence
```

When omitted, the adapter should preserve the existing `DecisionReceipt`
defaults.

This allows the generic mapper to construct an honest receipt even when a
producer-specific subject or correlation has not yet been selected.

The adapter must not infer supporting contracts from `SemanticOutcome.context`
or `SemanticOutcome.evidence`.

---

## Context and Evidence Boundary

`SemanticOutcome` stores:

```text
context: Mapping[str, Any]
evidence: Mapping[str, Any]
```

These mappings are frozen, but they are not guaranteed to be JSON-safe,
receipt-safe, authority-safe, or stable across producers.

`DecisionReceipt` stores:

```text
evidence_summary: JSON-safe mapping
metadata: JSON-safe mapping
```

Therefore PR3 must not:

```text
copy outcome.context into metadata
copy outcome.evidence into evidence_summary
flatten both mappings into one object
namespace and preserve both mappings
select values through a generic allowlist
automatically convert rich values
```

The mapper should not read either open-ended mapping.

Only explicitly supplied, preselected:

```text
evidence_summary
metadata
```

may enter the receipt.

---

## Why Explicit Preselection Is Required

Current producer mappings may contain:

```text
canonical identity / lineage context
adapter summary evidence
caller-provided enrichment
implementation-oriented labels
rich in-memory values
```

Even when a value is structurally JSON-safe, it may not be semantically safe to
preserve as governance evidence.

For example:

```text
technical_status
```

may be useful as explicit receipt summary evidence.

But:

```text
result_type
```

is currently a Python implementation type name and should not automatically
become authority-bearing receipt evidence.

Likewise, canonical identities belong in typed `subject` and `correlation`
fields rather than being duplicated in flexible JSON.

Explicit preselection is therefore both:

```text
a JSON-safety boundary
and
a semantic-admission boundary
```

---

## Evidence Shape

PR3 uses one explicit flat:

```text
evidence_summary
```

and one explicit:

```text
metadata
```

It does not automatically preserve namespaced copies such as:

```json
{
  "context": {...},
  "evidence": {...}
}
```

Namespacing arbitrary input would preserve implementation structure rather than
define a stable receipt vocabulary.

Flattening is also unsafe because current producer mappings can contain the same
key in both containers, such as:

```text
write_side_outcome
```

PR4 and PR5 should construct producer-specific evidence summaries deliberately.

---

## JSON-Safe Validation

PR3 does not add another JSON conversion layer.

It passes explicitly supplied `evidence_summary` and `metadata` into the
existing `DecisionReceipt` contract.

The existing receipt boundary is responsible for accepting:

```text
str
int
finite float
bool
None
list / tuple of JSON-safe values
string-keyed mappings of JSON-safe values
```

and rejecting values such as:

```text
UUID in flexible evidence
Decimal
datetime
set
domain state object
aggregate object
event object
exception object
database connection
arbitrary Python object
non-finite float
invalid mapping key
overly deep or circular structure
```

Typed UUID identity belongs in typed receipt fields.

Decimal values, if ever required later, must be deliberately represented by a
stable decimal string rather than an implicit binary float conversion.

---

## Flags Boundary

PR3 accepts explicit `DecisionReceiptFlags`.

It must not derive flags from:

```text
ok
category
semantic_code
severity
risk_level
reversibility
boundary
technical_status
```

No complete authoritative mapping currently exists from `SemanticOutcome` to:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

Partial intuitive mappings are not sufficient to establish a generic contract.

When flags are omitted, PR3 preserves:

```python
DecisionReceiptFlags()
```

This all-false value means:

```text
no flag evidence was supplied through this generic adapter
```

It must not be interpreted by future consumers as proof that fallback, rebuild,
operator review, or retry relevance was evaluated and ruled out.

Concrete PR4 and PR5 adapters may later introduce narrowly tested flag mappings.

Retry authorization remains outside Stage 4B and belongs to later retry
governance.

---

## Admission Evidence Boundary

PR3 may pass through an explicitly supplied:

```text
DecisionReceiptAdmissionEvidence
```

It must not infer admission disposition from:

```text
SemanticOutcome boundary
SemanticOutcome category
SemanticOutcome code
technical_status
candidate_event_id presence
accepted_event_id presence
```

Concrete write-side lifecycle mapping belongs to PR4.

PR3 relies on the existing `DecisionReceipt` contract for current admission
identity invariants.

It does not introduce a second producer-specific compatibility matrix.

---

## Ownership Matrix

| Concern | Owner |
|---|---|
| Exact semantic tuple preservation | PR3 generic adapter |
| Receipt construction | PR3 generic adapter |
| `receipt_id` creation | Caller / orchestration |
| Evidence-source selection | Caller at PR3 boundary; PR4 / PR5 for concrete paths |
| Subject selection | PR4 / PR5 or caller / orchestration |
| Correlation and identity provenance | PR4 / PR5 |
| Actor evidence | Caller / orchestration |
| Cost measurement and summary | Caller / orchestration; later measurement stage |
| Flags | Explicit pass-through in PR3; concrete mapping deferred |
| Admission disposition | PR4 |
| Receipt-safe evidence selection | PR4 / PR5 or caller / orchestration |
| Metadata selection | Caller / orchestration |
| Serialization and persistence | PR6 |
| Policy interpretation | Stage 4C |
| Strategy selection | Stage 4D |
| Retry safety and authorization | Stage 4E |

---

## Expected Production Files

PR3 is expected to add:

```text
src/compass/runtime/decision_receipt_mapping.py
tests/unit/compass/runtime/test_decision_receipt_mapping.py
```

and update:

```text
src/compass/runtime/__init__.py
```

The production module should add only:

```text
map_semantic_outcome_to_decision_receipt
```

No selector class, producer registry, path-specific helper, serializer, store, or
policy object should be introduced.

---

## Unit-Test Contract

PR3 tests should prove:

```text
exact semantic tuple preservation
explicit receipt_id preservation
explicit evidence_source preservation
default supporting contracts
explicit supporting contracts
receipt-safe evidence acceptance
non-JSON-safe evidence rejection
no wholesale context copying
no wholesale evidence copying
no write-side admission inference
no read-side / snapshot path inference
no automatic flag derivation
no runtime policy or retry authorization
no persistence behavior
```

A useful non-copying test should place both JSON-safe and rich values into the
source outcome mappings, omit explicit receipt evidence, and confirm:

```text
receipt.evidence_summary == {}
receipt.metadata == {}
```

The mapper should succeed because it never reads the open-ended outcome
mappings.

---

## Explicit Non-goals

PR3 does not implement:

```text
write-side evidence-source selection
write-side subject or correlation mapping
write-side event-ID conversion
write-side admission disposition mapping
idempotent replay receipt mapping
read-side evidence-source selection
snapshot evidence-source selection
snapshot subject or lineage mapping
producer-specific evidence-summary selection
automatic flag derivation
serialization
schema versioning
SQL migrations
PostgresDecisionReceiptStore
receipt queries
DiagnosticTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
automatic retry
automatic fallback
automatic rebuild
operator-review execution
```

---

## Known Limitations and Deferred Decisions

### Default flags are not three-state evidence

The current flag contract uses booleans.

Therefore omitted flags become `False`, not `Unknown`.

Future consumers must not treat a default false value as proof that the
corresponding concern was evaluated.

### Field-level identity provenance remains deferred

The current `identity_source` describes the primary correlation source.

PR4 / PR5 must choose it carefully when a receipt contains mixed identity
sources.

### Write-side event ID conversion belongs to PR4

Current write-side outcome context uses event-ID strings.

`DecisionReceiptCorrelation` uses native UUID fields.

PR3 must not parse those strings.

### String-backed Enum handling remains unchanged

The current JSON validator may accept `str`-backed Enum values through Python
subclass behavior.

Current fixed producers already normalize enum summaries to plain strings.

PR3 does not reopen this primitive boundary.

---

## Implementation Status

Complete.

Stage 4B PR3 implements the generic:

```text
SemanticOutcome
→ DecisionReceipt
```

construction boundary.

The production adapter:

- preserves the complete typed `SemanticOutcome` semantic tuple;
- requires caller-supplied `receipt_id` and `evidence_source`;
- accepts explicit optional receipt supporting contracts;
- accepts only caller-preselected `evidence_summary` and `metadata`;
- delegates supporting-contract, admission-invariant, and JSON-safety checks to
  the existing `DecisionReceipt` contract;
- never inspects or copies `SemanticOutcome.context` or
  `SemanticOutcome.evidence`;
- does not infer subject, correlation, identity provenance, admission fate,
  governance flags, runtime policy, strategy, retry authorization, or
  persistence behavior.

Schema-level ownership tests explicitly classify every current
`SemanticOutcome` and `DecisionReceipt` field so future contract evolution
cannot silently bypass the generic mapper boundary.

---

## PR3 Closeout Decision

PR3 is complete and should merge before producer-specific receipt mapping
begins.

The next work is not PR4 or PR5.

The next required step is:

```text
Interlude — DecisionReceipt Flag Evaluation State
```

The Interlude must review the shared `DecisionReceiptFlags` contract before
PR4 and PR5 begin producing durable flag evidence.

The current boolean defaults cannot distinguish:

```text
explicit true
explicit false after evaluation
not evaluated
not supplied
not applicable
incomplete flag evidence
```

PR3 correctly preserves the existing shared contract and does not create a
mapper-specific flag interpretation.

The shared flag contract must therefore be reviewed separately rather than
modified only inside the PR3 adapter.

---

## Next Work: Flag Evaluation State Interlude

The Interlude should determine:

```text
whether TRUE / FALSE / NOT_EVALUATED is sufficient
whether NOT_APPLICABLE is required
whether FALSE always means evaluated and explicitly denied
whether NOT_EVALUATED covers both not supplied and not executed
whether classification completeness must be represented
how future policy consumers interpret each state
the stable JSON representation
Java / Rust portability
whether the decision requires a new ADR
```

The Interlude must complete before PR4 and PR5 implementation because those
specialized adapters will be the first production producers of
producer-specific flag evidence.

It must also complete before PR6 persistence so durable storage does not
collapse unknown or absent evaluation into `False`.

After the shared flag contract stabilizes, PR4 and PR5 should first perform
separate read-only audits. If implemented in parallel, they must use separate
Git worktrees.

PR4 and PR5 must stop and report if they discover another shared
`DecisionReceipt` contract blocker. They must not independently modify shared
contracts from producer-specific branches.
