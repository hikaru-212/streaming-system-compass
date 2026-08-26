# ADR 0030 — Preserve the Legacy `STALE_WRITE` Carrier and Normalize at the Semantic Abstraction Boundary

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Accepted as a preservation and semantic-abstraction-boundary decision.
No production implementation change is required.

The decision is implemented by preserving the current reference implementation
and constraining stronger semantic projections to evidence that can support
them. This does not claim that the existing vocabulary is semantically perfect,
and it does not permanently prohibit a consequence-driven future refactor.

---

## Context

The completed Stage 4 reference implementation contains a historical technical verdict:

```text
AdmissionVerdict.STALE_WRITE
```

A source-first audit found that this verdict is not one coherent physical or semantic phenomenon.

Current concrete paths mapped into the carrier include, among others:

```text
append version inequality
candidate-sequence incompatibility after version equality
recognized PostgreSQL stream-position occupation
compatibility / synthetic append-conflict paths
```

The strongest counterexample is the append candidate-sequence check:

```text
current_version_in_store == expected_current_version

but

candidate.sequence != expected_current_version + 1
```

That condition does not establish that authoritative state advanced. It may reflect candidate mutation, old-candidate reuse, custom construction, or deterministic construction error.

Therefore:

```text
STALE_WRITE
!=
a single physical stale phenomenon
```

The same audit also found that some downstream current implementation vocabulary is more specific than the source evidence justifies:

```text
STALE_WRITE
→ CONCURRENT_STATE_STALENESS
```

and in durable receipt mapping:

```text
STALE_WRITE
→ APPEND_CONCURRENCY_CONFLICT
```

However, no current unsafe consequence has been established from this coarseness.

Stage 4C does not directly grant authority from `STALE_WRITE`.

Stage 4E does not implement:

```text
STALE_WRITE
→ ReinvocationAuthorization
```

Its append-positive profile remains narrowly source-grounded:

```text
completed rejected invocation
+ no accepted A1 effect
+ authoritative idempotency MISS
+ stream preparation ADMITTED
+ validation ALLOW
+ append conflict carrier
+ typed AppendVersionMismatchEvidence
+ observed_current_version > expected_current_version
+ candidate identity coherence
→ ReinvocationAuthorization
```

Thus:

```text
coarse technical carrier
!=
re-invocation authority
```

Known semantic and evidence debt therefore exists, but no unsafe authority path
has been demonstrated solely from the coarse carrier.

A source audit found that full normalization would cross production mappings,
durable `DecisionReceipt` compatibility, measurement artifacts, tests, and
current-facing documentation, with a blast radius on the order of dozens of
files. A prior audit estimate was roughly fifty files, but this decision does
not depend on that exact count.

The architectural reason not to refactor now is that current stronger
consequences already require source-specific typed evidence and reviewed
coherence, conservative abstraction can represent missing precision honestly,
and the migration cost is large relative to the demonstrated current
correctness benefit.

---

## Decision

### 1. Do not globally refactor the current reference implementation for this issue

The existing implementation retains:

```text
AdmissionVerdict.STALE_WRITE
```

and its historical downstream vocabulary.

This decision is not a claim that the name is semantically precise.

It is a deliberate decision not to reopen the completed Stage 4 implementation chain solely to normalize a historical technical carrier whose current consequential authority paths already fail closed.

The reference implementation remains authoritative for what it actually executes.

It is not required to use the same vocabulary as a future semantic model or protocol candidate.

---

### 2. Treat `STALE_WRITE` as a heterogeneous carrier of a non-injective technical classification

More precisely, let

\[
D_{\mathrm{append}} \subseteq X_{v,\mathrm{observation}}
\]

denote the reference-implementation append-admission observation/configuration
states represented in the current semantic universe, and let

\[
\kappa_{\mathrm{append}}:
D_{\mathrm{append}}\to L_{\mathrm{admission}}
\]

be the implementation's append-admission technical-classification map. The
fiber of the historical label may contain distinct states:

\[
\kappa_{\mathrm{append}}(x)
=
\kappa_{\mathrm{append}}(y)
=
\mathrm{STALE\_WRITE}
\]

while \(x\not\sim_{v,\mathrm{observation}} y\) under consequence-bearing
semantic contexts. The non-injectivity belongs to the classification map, not
to a bare enum value in isolation. `STALE_WRITE` is therefore an implementation
label shared by multiple concrete observation/configuration states, not the
name of one quotient class.

The project must not infer:

```text
same implementation label
→ same physical phenomenon
```

or:

```text
same implementation label
→ same semantic equivalence class
```

In particular:

```text
STALE_WRITE alone
!= proof of concurrency
!= proof that authoritative state advanced
!= proof that a stale premise was superseded
!= retryability
!= re-invocation authority
```

New consequence-bearing logic must not derive authority solely from the coarse verdict.

Stronger semantic claims require:

```text
source-specific typed evidence
+ trusted source coherence
+ reviewed consequence rule
```

Current Stage 4E already follows this pattern.

---

### 3. Normalize at the semantic abstraction boundary

The Compass Quotient Model and any future protocol-oriented semantic model may use normalized abstract distinctions that do not exist as one-to-one production enums.

For example, candidate abstract vocabulary may distinguish:

```text
APPEND_ADMISSION_CONFLICT
├── AUTHORITATIVE_PREMISE_SUPERSEDED
├── CANDIDATE_SEQUENCE_INCOMPATIBLE
├── STREAM_POSITION_OCCUPIED
└── UNCLASSIFIED_APPEND_ADMISSION_CONFLICT
```

These names are not retroactive claims about current production types.

They are candidate semantic abstractions.

The abstraction/projection relation may therefore map different concrete states that share the same historical `STALE_WRITE` label into different abstract classes.

Conceptually:

```text
STALE_WRITE
+ typed forward append-version evidence
+ reviewed coherence
→ [AUTHORITATIVE_PREMISE_SUPERSEDED]
```

while:

```text
STALE_WRITE
+ version equality
+ candidate-sequence incompatibility
→ [CANDIDATE_SEQUENCE_INCOMPATIBLE]
```

and, when a trustworthy source discriminator is retained:

```text
STALE_WRITE
+ recognized stream-position occupation
→ [STREAM_POSITION_OCCUPIED]
```

and:

```text
STALE_WRITE
+ insufficient trustworthy source evidence
→ [UNCLASSIFIED_APPEND_ADMISSION_CONFLICT]
```

These precise projections are available only when trustworthy,
source-specific evidence is actually present in the concrete projection
domain. Current completed `AdmissionResult` and `DecisionReceipt` artifacts do
not always retain typed candidate-sequence or stream-position discriminators.
The historical label or diagnostic reason text cannot reconstruct that lost
information.

---

### 4. Projection must never invent missing semantic certainty

If a concrete implementation state does not retain enough source evidence to support a precise abstract classification, the projection must remain conservative.

Therefore:

```text
insufficient evidence
→ explicit unclassified / unresolved abstraction
```

rather than:

```text
insufficient evidence
→ infer staleness from the enum name
```

In particular:

```text
STALE_WRITE
+ no retained trustworthy source discriminator
→ [UNCLASSIFIED_APPEND_ADMISSION_CONFLICT]

reason text
!= authority evidence

lost information
cannot be reconstructed by abstraction
```

This rule applies to authoritative-premise supersession,
candidate-sequence incompatibility, stream-position occupation, concurrency
interpretation, and any future protocol classification.

---

### 5. Current Stage 4E authority remains unchanged

This ADR does not broaden or narrow current Stage 4E production authority.

The two current reviewed positive families remain:

```text
preparation LOCK_TIMEOUT profile
→ one same-request re-invocation authority
```

and:

```text
fully coherent typed forward append-version profile
→ one same-request re-invocation authority
```

Unsupported conflict shapes remain non-authorizing.

Preserve:

```text
technical conflict
!=
re-invocation authority
```

and:

```text
authorization
!=
execution
```

The owner lifecycle also remains unchanged:

```text
AVAILABLE → SPENT before A2 entry

no automatic A3

fresh A2
!= resume A1
!= reuse A1 candidate
!= reuse A1 validation
!= reuse A1 append
```

---

### 6. Current Stage 4C authority remains unchanged

This ADR does not create new Stage 4C positive policy.

More precise future semantic classification may explain a refusal differently, but no current unsupported conflict gains current-response authority merely because its physical source becomes better understood.

---

### 7. `DecisionReceipt` remains the current durable semantic-governance evidence contract

This ADR does not redesign or migrate `DecisionReceipt`.

`DecisionReceipt` remains the current durable semantic-governance evidence
contract. When explicitly constructed and materialized, it preserves bounded
semantic and governance evidence about a supported execution outcome, whether
that outcome became an accepted business fact or remained non-accepted.

Therefore:

```text
DecisionReceipt existence
!= proof of success
!= proof of an accepted business effect
```

Some vocabulary carried by existing receipts is historical and coarse, but the
`DecisionReceipt` contract itself is current. Existing durable dispositions,
serializer/deserializer behavior, schema constraints, and historical rows
remain unchanged.

Future consumers must not treat a coarse durable disposition such as:

```text
APPEND_CONCURRENCY_CONFLICT
```

as independently sufficient proof of:

```text
authoritative premise supersession
retryability
re-invocation authority
```

If future durable recovery or planner behavior requires source-specific classification, that requirement must be justified as a separate evidence-contract evolution.

Some historical receipts preserve only the coarse
`APPEND_CONCURRENCY_CONFLICT` disposition. Where no trustworthy source-specific
discriminator was retained, a precise normalized conflict class cannot be
reconstructed and the conservative projection remains unclassified.

---

### 8. Frozen measurement artifacts remain historical evidence

Existing Stage 4B.2 experiment artifacts are not rewritten to normalize vocabulary.

Historical cohort names remain historical evidence of what the implementation produced at that time.

A future normalized experiment may use different vocabulary, but must not silently pool legacy and normalized cohorts as semantically identical without a reviewed mapping.

---

### 9. Keep one public Quotient Model v1 for the current stage

The unpublished Quotient Model v1 is corrected before publication.

A second Quotient Model version is not created solely for this clarification.

Reason:

```text
reference implementation behavior
= unchanged

Stage 4 consequence-bearing operation family
= unchanged
```

The correction changes the abstraction of a known heterogeneous implementation carrier; it does not introduce a new production semantic operation.

A future `v2` should be reserved for a genuine semantic change, such as:

- a new consequence-bearing context;
- a new semantic sort;
- changed authority behavior;
- changed abstract operation family;
- evidence from autonomous-governance composition showing that v1 is inadequate.

---

### 10. Future protocol vocabulary is not constrained by historical implementation names

A future protocol/specification candidate may require normalized distinctions even if the original Python/PostgreSQL implementation never adopts those exact names.

Under a future conformance definition, an implementation would be judged by
preserved abstract behavior, not by whether its enums match the reference
implementation.

Conceptually, for implementation \(I\):

\[
\pi_I : X_I \rightarrow Q
\]

may inspect concrete evidence, source relationships, authoritative effects, and lifecycle state.

It need not be a direct mapping from one implementation enum to one protocol state.

The long-term target is:

```text
Implementation A ──π_A──┐
                         ├── shared abstract semantics Q
Implementation B ──π_B──┘
```

rather than:

```text
all implementations
must reproduce Python enum names
```

---

## Why not perform the full refactor now?

### Correctness benefit is limited under current authority behavior

The source audit found real semantic imprecision, but not a current unsafe authority path caused solely by the coarse carrier.

For example, a candidate-sequence mismatch may currently be described too broadly as concurrency staleness, but both the current and normalized designs remain fail-closed for current Stage 4C / Stage 4E positive authority.

The principal immediate benefits of a full refactor would therefore be:

```text
diagnostic precision
semantic cleanliness
better durable source evidence
future maintainability
```

rather than correction of a demonstrated unauthorized accepted effect.

### Migration cost is disproportionately high

The current Stage 4 contracts deliberately amplify semantic changes so that new or changed governance vocabulary cannot silently pass through serialization, persistence, tests, and evidence machinery.

That is a useful property.

For this particular debt, however, paying that amplification cost would require reopening a large, already-characterized chain primarily to normalize vocabulary.

### Non-normative research context

Preserving the reference implementation leaves room for later
cross-implementation or protocol research. This context does not require a
particular framework, backend, second implementation, conformance project, or
publication plan.

---

## Consequences

### Positive

- Completed Stage 4 behavior and test evidence remain untouched.
- No broad multi-layer semantic migration is required now.
- Existing durable receipts and frozen measurement artifacts remain historically valid.
- The Quotient Model becomes clearer about the difference between implementation labels and semantic classes.
- The `STALE_WRITE` case becomes a concrete example motivating consequence-based abstraction.
- Future protocol vocabulary remains free from historical Python/PostgreSQL naming debt.
- Later research may evaluate the abstraction across different implementations.

### Negative

- The reference implementation retains a misleading historical name.
- Stage 4A and some durable receipt vocabulary remain more concurrency-oriented than some underlying physical producers justify.
- Future maintainers must understand that `STALE_WRITE` is not self-interpreting semantic evidence.
- Some legacy conflict states cannot be precisely projected because current source-specific typed evidence was not preserved.
- Any future planner or durable recovery consumer must avoid depending on coarse labels alone.

### Accepted trade-off

The project accepts this implementation debt because:

```text
reference implementation cleanliness
<
semantic abstraction correctness
+
conservative projection
+
cross-implementation research leverage
```

for the current project objective.

---

## Re-entry conditions

Reconsider a production normalization only if at least one concrete condition appears:

1. a current or planned consequence-bearing consumer begins making decisions from `STALE_WRITE` alone;
2. coarse Stage 4A / DecisionReceipt classification causes an actual incorrect authority or execution consequence;
3. durable restart/recovery semantics require a physical distinction that cannot be recovered from current stored evidence;
4. a future protocol or conformance implementation requires stronger concrete evidence than the current contract retains;
5. a required abstract distinction cannot be projected soundly from current evidence;
6. a concrete consumer justifies migration cost that exceeds the cost of continued compatibility;
7. a second implementation exposes a distinction that requires revisiting the reference implementation.

Absent one of these conditions, no production refactor is required by this ADR.

---

## Non-goals

This ADR does not:

- claim `STALE_WRITE` is a good semantic name;
- claim every `STALE_WRITE` is concurrency;
- claim every append conflict is stale;
- rename the production enum;
- migrate historical receipts;
- rewrite Stage 4B.2 evidence artifacts;
- rewrite accepted ADRs or closeouts;
- add new Stage 4C authority;
- add new Stage 4E authority;
- introduce automatic retry;
- introduce a generic conflict framework;
- define the final protocol;
- claim that the current reference implementation is fully conformant to a future normalized protocol model.

---

## Research interpretation

This decision preserves an important distinction:

```text
implementation taxonomy
!=
semantic taxonomy
```

Using the append-admission classification domain defined above, the current
reference implementation supplies a concrete witness shape:

```text
κ_append(x)
=
κ_append(y)
=
STALE_WRITE
```

for \(x,y\in D_{\mathrm{append}}\), while source evidence and downstream
consequence contexts may still establish:

\[
x \not\sim_{v,\mathrm{observation}} y.
\]

This is not treated as proof that the current Quotient Model is complete.

It is evidence that protocol-level semantic classes must be derived from consequence-bearing distinctions rather than inherited directly from implementation labels.

---

## Relationship to Quotient Model v1

Quotient Model v1 should explicitly record:

```text
STALE_WRITE
= heterogeneous non-injective implementation carrier
= not one quotient class
```

and preserve the rule:

```text
same implementation label
!=
semantic equivalence
```

A precise projection may use typed evidence where available.

An imprecise concrete state must remain conservatively unclassified.

No v2 is created for this documentation correction alone.

---

## Relationship to future protocol work

A future protocol candidate may normalize the write-admission conflict family independently of the historical implementation.

Possible candidate vocabulary may include:

```text
APPEND_ADMISSION_CONFLICT
AUTHORITATIVE_PREMISE_SUPERSEDED
CANDIDATE_SEQUENCE_INCOMPATIBLE
STREAM_POSITION_OCCUPIED
UNCLASSIFIED_APPEND_ADMISSION_CONFLICT
```

These names remain provisional until the protocol-oriented model is separately reviewed.

A future second implementation may use different concrete mechanisms and test
whether both implementations can project into shared candidate semantics. This
is a research direction, not a requirement or a current conformance claim.

---

## Final decision rule

Preserve the historical reference implementation unless its coarse carrier begins to control a consequence that requires a distinction it cannot truthfully support.

Normalize semantic meaning at the abstraction boundary.

Do not derive authority from a coarse implementation label.

Do not fabricate evidence to make the abstraction look cleaner.

Re-enter production normalization only when a concrete consequence or evidence
requirement justifies it.

---

## References

- [ADR 0029 — Stage 4C+ Exists at the Automation Boundary](0029_stage_4c_plus_exists_at_the_automation_boundary.md)
- [Stage 4E Closeout](../implementation_notes/stage_4e/stage_4e_closeout.md)
- [PostgreSQL Concurrency Admission Boundary](../boundary_notes/postgres_concurrency_admission_boundary.md)
- [PostgresWriteSideInvocationOwner Boundary](../boundary_notes/postgres_write_side_invocation_owner_boundary.md)
- [DecisionReceipt Boundary](../boundary_notes/decision_receipt_boundary.md)
