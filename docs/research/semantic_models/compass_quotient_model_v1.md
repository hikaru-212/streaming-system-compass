# Compass Quotient Model v1

## 1. Purpose, authority, and status

> [!IMPORTANT]
> This is a public, non-authoritative research and cognitive-compression model. It is not a protocol specification, a proof of minimality, a conformance standard, or a replacement for production source or accepted architecture. If any conflict exists, current merged source, tests, accepted ADRs, accepted boundary notes, and accepted closeouts override this model.

This document is a candidate semantic compression intended to preserve the Compass-level distinctions currently established after the completed Stage 4 integration. Its adequacy has not been proved.

The principal current authority references are [ADR 0029](../../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md), the [Stage 4E closeout](../../implementation_notes/stage_4e/stage_4e_closeout.md), and the [PostgresWriteSideInvocationOwner boundary note](../../boundary_notes/postgres_write_side_invocation_owner_boundary.md). Accepted [ADR 0030](../../adr/0030_preserve_legacy_stale_write_carrier_and_normalize_at_the_semantic_abstraction_boundary.md) records the decision to keep the historical `STALE_WRITE` implementation carrier while normalizing its meaning at the semantic abstraction boundary. That accepted implementation-boundary decision does not make this research model authoritative.

It is also not a generic retry design, a universal AI-governance runtime, or a claim that the current implementation is already language- or storage-independent.

Current maturity:

```text
Stage 4C
= COMPLETE / CLOSED

Stage 4C.5
= COMPLETE
= bounded compatibility / documentation closeout
= no new runtime policy

Stage 4D
= responsibility retained
= implementation deferred

Stage 4E
= COMPLETE / CLOSED

ADR 0029
= ACCEPTED
```

ADR 0029 preserves:

```text
evidence
!=
proposal
!=
authority
!=
execution
```

Future planner / proposal / executor machinery is therefore not modeled as already implemented.

---

## 2. Why this is v1

Let \(v_0\) denote the internal Stage 4E working model developed before the PR5 authority expansion. It was never a published compatibility baseline.

The progression was:

1. PR3-era behavior supplied the reviewed preparation `LOCK_TIMEOUT` positive profile; append-time `STALE_WRITE` remained non-authorizing.
2. PR4 added typed append version-mismatch evidence. This made the refined observation representable but did not grant re-invocation authority.
3. PR5 changed `AssessReinvocation`: one narrow append version-advance profile became authorizing.
4. PR6 froze responsibility and closed Stage 4E.

PR4 was an evidence and semantic-universe refinement. PR5 was a consequence-bearing operation change, because it changed the behavior of:

\[
\operatorname{AssessReinvocation}_v
\]

for one previously non-authorizing observation class. That change justifies:

```text
v0
→
v1
```

v0 was an internal historical working model and is not a published compatibility baseline.

The `STALE_WRITE` carrier clarification added before publication does **not** create a new semantic version. It corrects how the reference implementation is projected into the candidate abstraction; it does not change the merged Stage 4 operation family \(F_{v_1}\). A future \(v_2\) remains reserved for a new consequence-bearing operation, context, sort, or other semantic change that makes \(v_1\) inadequate.

Let \(F_v\) denote the current family of consequence-bearing semantic operations, evaluators, and transition relations whose observable behavior contributes to \(\operatorname{Context}_v\), \(\operatorname{Beh}_v\), and the open counterparts defined below. No additional algebraic structure on \(F_v\) is assumed.

All principal objects remain version-indexed:

\[
X_v,\quad \operatorname{Context}_v,\quad \operatorname{Beh}_v,\quad
\sim_v,\quad Q_v,\quad \pi_v,\quad \sigma_v,\quad F_v.
\]

---

## 3. Semantic sorts

The model remains many-sorted:

\[
S_{v_1}
=
\{
\mathrm{effect},
\mathrm{observation},
\mathrm{authority},
\mathrm{owner}
\}.
\]

- **effect**: candidate, admission, accepted-effect, replay, and authoritative-world boundary states;
- **observation**: completed producer results and evidence-bearing configurations;
- **authority**: immutable consequence-indexed decision, refusal, and source-associated authorization content;
- **owner**: live request/composition custody, current-result custody, current-response lifecycle, re-invocation assessment cache, authority availability / consumption, and invocation-entry lifecycle.

Future `proposal` or `executor` concepts are not \(v_1\) semantic sorts. ADR 0029 recognizes them as distinct responsibilities, but current runtime evidence does not justify promoting them into the executable quotient.

---

## 4. Concrete semantic universe

The concrete semantic universe is:

\[
X_v
=
\bigsqcup_{s\in S_v}X_{v,s}.
\]

It contains reachable Compass-level semantic boundary states, not every Python object or instruction-level state.

### Effect sort

Includes:

- complete requests;
- candidate effects;
- validation and admission;
- accepted-effect membership;
- replay selection.

### Observation sort

Includes completed producer observations together with evidence required by current evaluators, including where applicable:

- terminal technical disposition;
- accepted-effect presence / absence;
- authoritative idempotency evidence;
- validation evidence;
- append-admission evidence;
- typed append version-mismatch evidence.

### Authority sort

Contains immutable consequence-boundary content such as current-response decisions and refusals, no-authority results, and issued re-invocation authorization associated with a complete request and a source observation. Availability and consumption are not immutable fields of an authorization artifact.

### Owner sort

Contains retained request/composition custody, current-result custody, current-response evaluation state, cached re-invocation assessment, authority availability, authority consumption, and A1/A2 entry state.

At first use in this model:

- **A1** is the original public-writer invocation owned by the current live invocation owner.
- **A2** is the single additional fresh public-writer invocation that may enter after one positive Stage 4E authority is consumed.

A2 does not resume A1 and does not reuse A1's candidate, validation, or append work.

Excluded:

```text
unreachable combinations
raw DB connection identity
raw lock objects
production A3
generic retry budgets / backoff
durable AttemptLog semantics
future Stage 5 action semantics
future planner / proposal / executor runtime state
```

---

## 5. Nominal domains and alpha-equivalence

The declared nominal domains are:

\[
N_{v_1}
=
\{
\mathrm{RequestId},
\mathrm{OrderId},
\mathrm{EventId},
\mathrm{OutcomeId},
\mathrm{AcceptedEffectRef}
\}.
\]

An alpha-renaming is a family of domain-preserving bijections:

\[
\rho=(\rho_D)_{D\in N_v},\qquad \rho_D:D\to D.
\]

For observable structures \(b,b'\):

\[
b\equiv_{\alpha,v}b'
\quad\Longleftrightarrow\quad
\exists\rho.\;\rho\cdot b=b'.
\]

Renaming must preserve equality, inequality, freshness, source binding, complete-request identity, candidate/accepted membership, and accepted-effect reference relationships.

Alpha-renaming never changes semantic fields such as:

```text
amount
command_type
semantic category
validation verdict
admission verdict
RuntimeDecision response
authority availability
current-response lifecycle
expected_current_version
observed_current_version
```

Thus opaque IDs may be renamed consistently, but `amount=100` cannot become `amount=500`.

Alpha-equivalence is not the Compass semantic equivalence relation. When applied to a candidate signature, \(\equiv_{\alpha,v}\) means componentwise alpha-equivalence on nominal coordinates while every non-nominal semantic field remains fixed.

---

## 6. Contextual semantic equivalence

For each sort \(s\), let:

\[
\operatorname{Context}_v(s)
\]

be the set of current, well-typed, consequence-bearing state-level contexts applicable to that sort.

For a pure state-level context and \(x\in X_{v,s}\), \(\operatorname{Beh}_v(C,x)\) is its returned value, observable typed failure, outcome set, or trace tree. Open behavior over execution configurations is defined separately in Section 9.

The quotient construction below relies on mathematical assumptions that remain proof obligations:

- alpha-equivalence is well-defined over every observable behavior shape, including returned values, typed failures, outcome sets, trace trees, source references, and accepted-effect references;
- the relevant contexts are nominally parametric, or equivariant, so consistent renaming cannot be detected by literal identifier spelling;
- alpha-equivalence is reflexive, symmetric, and transitive; and
- the action of renaming is coherent with the equality, freshness, membership, and source relationships observed by those contexts.

Under these assumptions, the induced contextual relation is reflexive, symmetric, and transitive, and therefore is an equivalence relation. This has not been mechanically proved.

Define:

\[
x\sim_{v,s}y
\quad\Longleftrightarrow\quad
\forall C\in\operatorname{Context}_v(s),\;
\operatorname{Beh}_v(C,x)\equiv_{\alpha,v}\operatorname{Beh}_v(C,y).
\]

Literal UUID spelling cannot distinguish states. Equality structure, source relationships, complete-request identity, typed version relationships, authority availability, and consequence-bearing lifecycle state may.

---

## 7. Quotient and projection

For each sort:

\[
Q_{v,s}=X_{v,s}/\sim_{v,s}.
\]

Let \(\sim_v\) be the sort-preserving disjoint union. Then:

\[
Q_v=X_v/\sim_v
\cong
\bigsqcup_{s\in S_v}Q_{v,s}.
\]

The canonical projection is:

\[
\pi_{v,s}:X_{v,s}\to Q_{v,s},
\qquad
\pi_{v,s}(x)=[x]_{v,s}.
\]

Projection classifies a concrete semantic state. It is not effect admission, semantic interpretation, Stage 4C evaluation, Stage 4E assessment, authority consumption, execution, or accepted-history mutation.

```text
classification
!=
authorization
!=
execution
```

---

## 8. Candidate finite-arity semantic summary

A currently useful candidate finite-arity semantic summary is a function:

\[
\sigma_v:X_v\to\Sigma_v,
\qquad
\sigma_v(x)
=
(
\operatorname{sort}(x),
\widehat O,
\widehat S,
\widehat C,
\widehat R,
\widehat L
).
\]

Here \(\Sigma_v\) denotes the corresponding product of typed coordinate carriers.

where:

- \(\widehat O\): observation / producer evidence;
- \(\widehat S\): semantic interpretation;
- \(\widehat C\): current-response state;
- \(\widehat R\): immutable source-associated re-invocation authority or refusal content;
- \(\widehat L\): owner-local invocation and authority-availability lifecycle.

Typed bottom values represent non-applicable coordinates.

This summary has a finite number of coordinates, but coordinates such as evidence or retained state may contain unbounded structure. It is not claimed to be the smallest summary.

No theorem currently proves that \(\sigma_v\) is a complete invariant for \(\sim_v\):

\[
\sigma_v(x)\equiv_{\alpha,v}\sigma_v(y)
\quad\Longleftrightarrow\quad
x\sim_v y.
\]

Nor has an induced bijection between quotient classes and signature classes been proved. Adequacy, irredundancy, and mathematical minimality remain open proof obligations.

---

## 9. Local evaluation versus open execution

A local Stage 4E evaluator input state contains at least:

\[
x_{\mathrm{local}}
=
(
\mathrm{RequestSignature},
\mathrm{CompletedProducerObservation}
).
\]

This is sufficient for pure authority assessment but not for predicting the result of the next invocation.

Let \(\mathcal W_v\) be a candidate authoritative-environment space. The current Stage 4E candidate abstraction uses:

\[
W=(H,I,B),
\]

where:

- \(H\): relevant accepted history;
- \(I\): authoritative idempotency relation;
- \(B\): abstract contention / resolution state.

This is a current Stage 4E open-world candidate, not a proved complete or mathematically smallest environment model. In particular, \(B\) abstracts the contention and resolution distinctions currently relevant to the modeled behavior; it does not silently claim to represent every infrastructure failure. \(W\) excludes database connection identity, threads, and raw lock mechanics.

Define a separate carrier for open execution:

\[
\Gamma_v
=
\{\gamma=(x\parallel W)\mid x\in X_v,\;W\in\mathcal W_v,\;\gamma\text{ is well-typed}\}.
\]

Let \(\operatorname{OpenContext}_v\) be the candidate family of well-typed contexts over \(\Gamma_v\). For \(C\in\operatorname{OpenContext}_v\) and \(\gamma\in\Gamma_v\), \(\operatorname{OpenBeh}_v(C,\gamma)\) is the observable outcome set or trace tree induced by admissible authoritative-environment evolutions. It is not the state-level \(\operatorname{Beh}_v(C,x)\).

Fresh invocation can gain information because \(W\) may change between A1 and A2.

---

## 10. Current-response submodel

The following five labels are candidate semantic projections of current implementation state:

\[
\begin{aligned}
&\mathrm{CURRENT\_ABSENT}\\
&\mathrm{CURRENT\_UNEVALUATED}(result)\\
&\mathrm{CURRENT\_IDENTIFIED}(result,\nu)\\
&\mathrm{CURRENT\_DECIDED}(result,\nu,decision,selection)\\
&\mathrm{CURRENT\_REFUSED}(result,\nu,refusal).
\end{aligned}
\]

They are not exported production enums, a durable state machine, or proved irreducible quotient classes.

Normal result publication creates `CURRENT_UNEVALUATED` and does not allocate \(\nu\).

First evaluation allocates and retains \(\nu\). Structural mapping or evaluation failure leaves `CURRENT_IDENTIFIED`; later evaluation reuses the same \(\nu\). Successful evaluation produces `CURRENT_DECIDED` or `CURRENT_REFUSED`.

At A2 entry the owner clears A1's current-response state. Normal A2 completion publishes a fresh `CURRENT_UNEVALUATED(A2)` result. If A2 raises before normal publication, no current normal result remains. A2 receives a new identity only if its current response is evaluated.

Under the model's nominal-freshness assumption, if A1 already had \(\nu_{A1}\), then:

\[
\nu_{A2}\ne\nu_{A1}.
\]

The current Python implementation realizes this assumption by allocating a fresh `uuid4()` when A2's current response is first identified. It does not maintain an explicit global collision-proof identity allocator, so this is not a formal uniqueness theorem.

Preserve:

```text
current-response state
!=
invocation history
```

The owner retains only the current-response state; it has no current-response history collection.

---

## 11. Re-invocation submodel

Before quotienting, `source` denotes a concrete completed observation. The authority sort contains immutable content:

\[
\begin{aligned}
&\mathrm{NO\_REINVOCATION\_AUTHORITY}(r)\\
&\mathrm{ISSUED\_REINVOCATION\_AUTHORITY}(r).
\end{aligned}
\]

Here \(r\) is the complete `RequestSignature`. The exact source is related separately through `SourceOf`, not carried as a field of this authority content.

The owner sort separately contains assessment and consumption lifecycle:

\[
\begin{aligned}
&\mathrm{REINVOCATION\_UNASSESSED}(r,source)\\
&\mathrm{REINVOCATION\_ASSESSED\_WITHOUT\_AUTHORITY}(r,source)\\
&\mathrm{REINVOCATION\_AVAILABLE}(authority)\\
&\mathrm{REINVOCATION\_SPENT}(authority).
\end{aligned}
\]

These names describe the candidate model rather than exported production enums. After projection, `source` is represented by an observation class, subject to the source-relation proof obligation in Section 13.

`NO_REINVOCATION_AUTHORITY` means no authority was issued from this source under \(v_1\); it is not permanent denial under every future semantic version. Issued authority is not the same as currently available authority, and the immutable authorization artifact is not the owner lifecycle.

Owner-local `AVAILABLE -> SPENT` occurs before A2 writer entry and is irreversible. One positive authority permits at most one production A2. It does not create automatic A3, and authorization remains distinct from execution.

### Positive profile A — preparation timeout

Conceptually:

```text
complete RequestSignature
+ completed ADMISSION_REJECTED result
+ accepted effect absent
+ authoritative idempotency MISS / no record
+ stream preparation LOCK_TIMEOUT
+ matching subject identity
+ validation not reached
+ append not reached
→ ReinvocationAuthorization
```

### Positive profile B — append version advance

The consequence-bearing production predicate is:

```text
complete RequestSignature
+ result.outcome = ADMISSION_REJECTED
+ result.accepted_event = None
+ authoritative idempotency verdict = MISS
+ authoritative idempotency record = None
+ stream preparation result exists
+ stream preparation verdict = ADMITTED
+ stream preparation order_id = RequestSignature.order_id
+ validation result exists
+ validation decision exists
+ validation decision action = ALLOW
+ append result exists
+ append verdict = STALE_WRITE
+ append accepted_event_id = None
+ typed AppendVersionMismatchEvidence exists
+ observed_current_version > expected_current_version
+ append candidate_event_id = validation result candidate_event_id
→ ReinvocationAuthorization
```

The predicate does not require a particular `validation_result.verdict`; `validation_decision_evidence` may be absent; reason text is not authority evidence; and no additional `RequestSignature` comparisons are imposed. Fuller request/result association is supplied by trusted live owner-local custody. The exact production predicate remains owned by merged source and tests.

Still invalid:

```text
generic STALE_WRITE
→ ReinvocationAuthorization
```

and:

```text
technical failure
!=
re-invocation authority

semantic failure
!=
re-invocation authority
```

---

## 12. Three append version-mismatch evidence layers

Stage 4E v1 includes:

```text
AppendVersionMismatchEvidence(
    expected_current_version,
    observed_current_version,
)
```

### Layer 1 — `AppendVersionMismatchEvidence` type

Both coordinates must be exact integers; `bool` is excluded. They must be nonnegative and unequal. Either mismatch direction is valid at this type layer.

### Layer 2 — `AdmissionResult` embedding coherence

Typed mismatch evidence is coherent in an append-admission result only under the current source constraints: the append verdict is `STALE_WRITE`, `accepted_event_id` is absent, and `candidate_event_id` is present. These embedding constraints are distinct from the evidence type's own validity.

### Layer 3 — Stage 4E authority predicate

Only the reviewed Stage 4E authority predicate adds `observed_current_version > expected_current_version`, together with the completed-result coherence listed in positive profile B.

Therefore:

```text
typed evidence validity
!=
AdmissionResult coherence

AdmissionResult coherence
!=
re-invocation authority

observed version advance
!=
authority by itself

generic STALE_WRITE
!=
authority
```

This is important to the quotient: two observations with the same terminal technical status may remain semantically distinguishable when typed physical evidence changes the result of an authority-bearing context.

### Legacy `STALE_WRITE` carrier interpretation

Let

\[
D_{\mathrm{append}} \subseteq X_{v,\mathrm{observation}}
\]

denote the reference-implementation append-admission observation/configuration
states represented in the current semantic universe, and let:

\[
\kappa_{\mathrm{append}}:
D_{\mathrm{append}}\to L_{\mathrm{admission}}
\]

be the reference implementation's append-admission technical-classification
map. A source-first audit showed that the fiber
\(\kappa_{\mathrm{append}}^{-1}(\mathrm{STALE\_WRITE})\) contains several
different physical situations, including:

- append version inequality;
- candidate-sequence incompatibility after version equality;
- recognized stream-position occupation;
- compatibility or synthetic conflict paths for which no single physical cause is established.

Thus `STALE_WRITE` is a **heterogeneous implementation carrier**. More
precisely, for \(x,y\in D_{\mathrm{append}}\), it may be true that:

\[
\kappa_{\mathrm{append}}(x)
=
\kappa_{\mathrm{append}}(y)
=
\mathrm{STALE\_WRITE}
\quad\text{while}\quad
x\not\sim_{v,\mathrm{observation}} y.
\]

Accordingly, \(\kappa_{\mathrm{append}}\) is an implementation technical
classifier, not the semantic quotient projection
\(\pi_{v,\mathrm{observation}}\).

Therefore:

```text
same implementation label
!=
same physical phenomenon
!=
same semantic equivalence class
```

The model does **not** define a quotient class named `[STALE_WRITE]`.

The implementation label may be part of the concrete evidence used by a projection, but abstract classification must depend on the consequential source evidence and relationships that are actually available. A candidate normalized projection may therefore distinguish:

```text
STALE_WRITE
+ typed forward append-version evidence
+ reviewed coherence
→ [AUTHORITATIVE_PREMISE_SUPERSEDED]

STALE_WRITE
+ version equality
+ candidate-sequence incompatibility
→ [CANDIDATE_SEQUENCE_INCOMPATIBLE]

STALE_WRITE
+ recognized stream-position occupation
→ [STREAM_POSITION_OCCUPIED]

STALE_WRITE
+ insufficient trustworthy source evidence
→ [UNCLASSIFIED_APPEND_ADMISSION_CONFLICT]
```

These bracketed names are **candidate abstraction vocabulary**, not current production enums, accepted protocol states, or proof that the listed classes are irreducible.

The first three precise projections are available only when trustworthy,
source-specific evidence is actually present in the concrete projection domain.
Current completed `AdmissionResult` and `DecisionReceipt` artifacts do not
always retain typed candidate-sequence or stream-position discriminators. A
projection must not parse diagnostic reason text to manufacture a formal source
fact.

The conservative rule is:

> The projection must not infer semantic certainty that the concrete evidence does not contain.

Therefore:

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
interpretation, and future protocol classification. An unclassified concrete
conflict remains unclassified rather than being promoted because the historical
enum happens to contain the word `STALE`.

The same limitation applies to durable evidence. `DecisionReceipt` is the
current durable semantic-governance evidence contract: when explicitly
constructed and materialized, it can preserve bounded semantic and governance
evidence about accepted or non-accepted supported execution outcomes. Its
existence does not imply success or an accepted business effect.

A current `DecisionReceipt` may preserve only the coarse
`APPEND_CONCURRENCY_CONFLICT` disposition. It is governance evidence, not a
fully normalized future protocol artifact; without a retained trustworthy
source discriminator, a precise normalized conflict class cannot be recovered.

---

## 13. Source-binding relation

The concrete model records exact source association through the relation:

\[
\operatorname{SourceOf}_v
\subseteq
X_{v,\mathrm{authority}}
\times
X_{v,\mathrm{observation}}.
\]

The live implementation establishes this relation through trusted live owner-local causal custody:

```text
producer observation
→ evaluator
→ authority / refusal evaluation
→ source association retained by invocation-owner custody
```

`ReinvocationAuthorization` contains the complete `RequestSignature`; it does not contain a source result, source ID, availability flag, or spent state. The owner retains the exact A1 result and its cached Stage 4E evaluation.

The model introduces no authority ID, attempt ID, durable authority-provenance record, cryptographic source proof, or persistent attempt lineage. Current source binding is trusted live causal custody, not durable independently verifiable provenance.

Keep quotient-level source binding relational. Define the candidate relation:

\[
\operatorname{SourceClassOf}_v([a],[o])
\quad\Longleftrightarrow\quad
\exists a'\in[a],\;\exists o'\in[o].\;
\operatorname{SourceOf}_v(a',o').
\]

Representative independence requires `SourceOf` to be saturated with respect to \(\sim_{v,\mathrm{authority}}\) and \(\sim_{v,\mathrm{observation}}\). That condition, and therefore quotient-level well-definedness, remains a proof obligation.

---

## 14. Pure evaluators and open transition relation

The family \(F_v\) includes local evaluators represented as typed deterministic functions or partial functions:

\[
\operatorname{Interpret}_v(o),
\qquad
\operatorname{CurrentResponse}_v(o,\nu),
\qquad
\operatorname{AssessReinvocation}_v(r,o).
\]

They return semantic values, decisions, authorization content associated with its source through owner custody, typed refusal, or observable failure.

They do not themselves mutate accepted history, consume re-invocation authority, enter A2, or execute external consequences.

It also includes stateful/open transition relations over \(\Gamma_v\):

\[
\gamma
\xrightarrow{\ell,\omega}_v
\gamma',
\qquad
\gamma=(x\parallel W),
\quad
\gamma'=(x'\parallel W').
\]

Possible semantic labels include:

```text
ADMIT
COMMIT
IDENTIFY_CURRENT
CACHE_CURRENT
ASSESS_REINVOCATION
ISSUE_REINVOCATION
CONSUME_REINVOCATION
ENTER_A2
PUBLISH_RESULT
REPLAY_RESOLVE
```

\(\omega\) abstracts admissible environment evolution or interleaving, not PostgreSQL mechanics.

Authorization enables an execution transition; it is not that transition.

No claim is made that this open transition relation descends to \(Q_v\). Such a claim would require a congruence proof.

---

## 15. Core Stage 4 invariants

Current production / accepted invariants:

- Stage 4C current-response authority and Stage 4E another-invocation authority are parallel consequence families.
- Stage 4C refusal does not preclude a valid Stage 4E authorization.
- Stage 4E assessment uses the complete `RequestSignature`.
- The live owner binds Stage 4E assessment and authority to the exact completed observation that justified it through trusted causal custody.
- Owner-local `AVAILABLE -> SPENT` occurs before A2 entry and never reverses.
- At most one production A2 may enter through one issued positive authority.
- A2 entry clears the prior current-response state.
- Normal A2 publication creates `CURRENT_UNEVALUATED(A2)`.
- A2 failure before normal publication leaves no current normal result.
- Production does not reassess A2 into automatic A3.
- Stage 4C decisions do not themselves alter accepted history.
- Stage 4E authorizations do not themselves alter accepted history.
- Fresh A2 re-observes authoritative state rather than reusing A1 candidate, validation, or append work.
- Typed version-mismatch evidence is not itself authority.
- Generic `STALE_WRITE` is not self-authorizing.

Preserve:

```text
current response
!=
another invocation

authorization
!=
execution

fresh invocation
!=
resume stale work
```

---

## 16. Experimental witnesses and promotion

Executable experiments may reveal a meaningful distinction before it becomes production semantics.

```text
experimental distinction
!=
production semantics
```

Current witnesses:

| Witness | Distinction demonstrated | Current status |
| --- | --- | --- |
| Successive re-invocation resolution | The same preparation-timeout class can lead to different later results after authoritative resolution; elapsed time alone is not the semantic distinction. | Executable experiment only |
| Authority laundering | Local edge permission does not imply path-effect authority. | Executable experiment and adjacent public research |
| Append version-mismatch stale witness | Fresh full invocation after a concrete version mismatch can observe information unavailable to stale A1. | Experimentally discovered distinction later partially promoted into production evidence and authority |

Promotion path:

```text
Experiment
→ establish information value

PR4
→ preserve typed source distinction

PR5
→ consume one narrow version-advance profile as production authority

PR6
→ freeze responsibility and close Stage 4E
```

This demonstrates:

> A distinction may be discovered experimentally without being production semantics, then later become production-relevant only after its evidence contract and consequence authority are separately reviewed.

Generic `STALE_WRITE` remains non-authorizing.

---

## 17. Semantic-version evolution

Three changes remain distinct.

### Evidence maturity change

If evidence becomes more mature without changing consequence-bearing operations, \(v\) need not change.

### Context addition

On a common semantic-state carrier, if operations keep their meanings and the new context family contains the old one:

\[
\operatorname{Context}_v(s)
\subseteq
\operatorname{Context}_{v'}(s)
\quad\Longrightarrow\quad
\sim_{v',s}
\subseteq
\sim_{v,s}.
\]

The quotient may then become a refinement. Without a common carrier or an explicit embedding between carriers, this relation is not asserted.

### Operation change

If the current consequence-bearing family changes:

\[
F_v\ne F_{v'}.
\]

Then the semantic version changes.

The transition:

```text
v0
→
v1
```

is such a change because \(\operatorname{AssessReinvocation}_{v_0}\) and \(\operatorname{AssessReinvocation}_{v_1}\) differ for the promoted typed append-version-advance profile. Thus \(F_{v_0}\ne F_{v_1}\).

### Future autonomous-governance work

A future flow may introduce:

```text
RecoveryPlanner
→ RecoveryProposal
→ consequence authority
→ ControlledExecutor
```

Whether this requires \(v_2\) depends on semantics, not implementation size.

If the new machinery is expressible through existing distinctions, that machinery alone may not require \(v_2\).

If it creates a new consequence-bearing distinction that \(v_1\) cannot represent, quotient refinement and a new semantic version may be justified.

---

## 18. ADR 0029 and the automation boundary

[ADR 0029](../../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md) establishes:

```text
Stage 4B and earlier
≈ evidence / understanding

Stage 4C+
≈ explicit machine consequence-authority boundary
```

The quotient model does not turn this into a mandatory runtime sequence.

Preserve:

```text
evidence
!=
proposal
!=
authority
!=
execution

SemanticOutcome
!=
RuntimeDecision

RuntimeDecision
!=
execution

ReinvocationAuthorization
!=
invocation execution
```

Stage 4C and Stage 4E are two current examples of consequence-specific authority.

Stage 4D owns dynamic `HOW` selection only when an already-authorized operation has multiple eligible strategies. No production dynamic Stage 4D selector exists, and adding one would not currently change observable behavior:

```text
Stage 4D responsibility
= accepted

Stage 4D implementation
= deferred
```

Do not encode:

```text
Stage 4C
→ Stage 4D
→ Stage 4E
→ execution
```

as a mandatory pipeline.

---

## 19. Relationship to agent-era research

Current public research, including [Probabilistic Agency Inside Deterministic Business Workflows](../ai_governance/probabilistic_agency_inside_deterministic_business_workflows.md), distinguishes:

```text
Delegation
→ Should AI decide this?

Influence
→ What may AI affect?

Semantic Admission
→ May the candidate become trusted?
```

These concepts are relevant to Compass but are not additional \(v_1\) runtime sorts merely because they are public.

Likewise:

```text
direct mutation authority
!=
reachable business influence
```

is an important cross-cutting research claim, not a new current production quotient state.

A later agent workflow that makes proposal or influence states consequence-bearing may justify new contexts, new signature coordinates, or new sorts.

---

## 20. Candidate implementation-independent meanings

The current model identifies candidate meanings that a future conformance definition may require:

### Request

- complete request identity;
- request equality stronger than `request_id` equality alone.

### Effect

- candidate effect versus accepted membership;
- accepted-history effect;
- replay selection.

### Observation

- completed producer evidence;
- semantic interpretation;
- typed refusal;
- typed append version-mismatch source distinction.

### Authority

- current-response authority;
- another-invocation authority;
- no-authority result;
- source association.

### Owner

- current-result custody;
- request/composition custody;
- current-response lifecycle;
- authority availability and irreversible consumption;
- one-shot A2 entry.

Future implementations may represent storage transactions, locks, caches, object graphs, and opaque identities differently. Agreement of Compass-level contextual behavior modulo declared nominal renaming is a candidate future conformance target, not a present requirement or a demonstrated language- or storage-independent protocol.

The current reference implementation's `STALE_WRITE` carrier is intentionally **not** a future conformance requirement. Under a future conformance definition, an implementation could use a different conflict vocabulary or no corresponding enum at all, provided its concrete states could be projected into the definition's reviewed abstract distinctions without inventing evidence.

---

## 21. Current implementation leaks and portability question

Current implementation evidence still exposes:

```text
Python types
in-process owner state
UUID allocation
PostgreSQL transactions
PostgreSQL contention profiles
preparation LOCK_TIMEOUT
version-oriented append mismatch evidence
```

One especially important open portability question is:

> Which part of `AppendVersionMismatchEvidence` belongs to a defensible implementation-independent semantic abstraction, and which part is only one PostgreSQL representation?

The concrete evidence says:

```text
expected_current_version = n
observed_current_version = m
m > n
```

One candidate abstract semantic relation may instead be closer to:

```text
the authoritative world advanced
beyond the premise against which A1 attempted admission
```

or:

```text
A1's append premise was superseded
by accepted authoritative progress
```

Both formulations are open portability hypotheses. Neither is frozen as accepted architecture or a protocol requirement in \(v_1\).

A future Rust + Redis or other implementation may expose different physical evidence. Whether it preserves the same Compass-level consequence is a future conformance question, not a present achievement.

---

## 22. Open proof obligations

Current obligations include:

- discharge the assumptions that make \(\sim_{v,s}\) an equivalence relation;
- prove adequacy and irredundancy of \(\sigma_v\);
- prove or refute an induced bijection between quotient classes and signature classes;
- prove congruence for proposed quotient-level operations;
- prove representative independence / saturation for `SourceClassOf`;
- determine whether \(W=(H,I,B)\) is sufficient for current open behavior;
- define portable accepted-effect reference semantics;
- decide whether any current-response lifecycle states can collapse;
- characterize preparation-timeout semantics without storage-specific lock vocabulary;
- characterize the smallest portable meaning of `AppendVersionMismatchEvidence`;
- determine whether `observed_current_version > expected_current_version` is part of the implementation-independent model or only a concrete witness for a more abstract world-advance relation;
- prove that the two positive Stage 4E evidence families remain distinct exactly where consequence-bearing contexts can distinguish them;
- characterize which concrete physical producers currently hidden behind the heterogeneous `STALE_WRITE` carrier are distinguishable under the current context set, rather than treating the untyped remainder as one residual semantic class;
- determine whether future `RecoveryProposal` / `ControlledExecutor` semantics require a new sort or only new contexts;
- eventually test conformance against a second implementation stack.

No full reachable-state congruence theorem, candidate-summary representation theorem, conformance theorem, or mathematical-minimality theorem is claimed.

---

## 23. Compact implementation projection

| Concrete artifact or state | Candidate semantic projection |
| --- | --- |
| Complete `RequestSignature` | Complete request component; nominal IDs may be renamed, semantic fields remain fixed. |
| Candidate `OrderEvent` | Candidate effect, not accepted membership. |
| Accepted event/history | Membership in \(H\) plus accepted-effect relationships. |
| Completed write-side result | Observation class determined by consequential evidence, not terminal enum alone. |
| Legacy `STALE_WRITE` carrier | Heterogeneous implementation label only; projection must inspect source evidence and may conservatively map to an unclassified append-admission conflict. |
| `DecisionReceipt` with coarse `APPEND_CONCURRENCY_CONFLICT` only | Durable governance evidence, not a normalized protocol artifact; without retained source-specific evidence, precise conflict classification remains unavailable. |
| `SemanticOutcome` | Semantic interpretation \(\widehat S\), separate from authority. |
| `RuntimeDecision` | Current-response authority content. |
| Stage 4C refusal | `CURRENT_REFUSED`. |
| `ReinvocationAuthorization` | Immutable issued-authority content containing the complete `RequestSignature`; source association is maintained by live owner custody. |
| `NoReinvocationAuthority` | Immutable no-authority result associated with the assessed source through live owner custody. |
| `AppendVersionMismatchEvidence` | Concrete typed append-version-inequality evidence. It is not a generic `STALE_WRITE` semantic class; forward supersession requires additional reviewed coherence, and the portability abstraction remains open. |
| Owner before / after consumption | Owner-local `REINVOCATION_AVAILABLE` / `REINVOCATION_SPENT`; not fields of the authorization artifact. |
| A2 in flight without normal result | `CURRENT_ABSENT` with A2 lifecycle active. |
| Normal A2 publication | `CURRENT_UNEVALUATED(A2)`. |
| Replay with selected prior result | Replay consequence preserving accepted-effect selection. |
| Future `RecoveryProposal` | Not yet a \(v_1\) production quotient state. |
| Future `ControlledExecutor` | Not yet a \(v_1\) production quotient state. |

This table is a candidate projection guide, not a completeness proof.

---

## 24. Canonical mental model

Compass separates:

```text
authoritative world
candidate effect
completed observation
semantic interpretation
consequence-specific authority / refusal
owner-local authority availability / consumption
execution
authoritative effect
```

Completed observations feed local evaluators.

Stage 4C current-response authority and Stage 4E another-invocation authority remain parallel rather than one mandatory pipeline.

Stage 4E evaluation is associated with its source through trusted live owner custody, and owner-local consumption is one-shot.

A positive authority profile means only:

```text
one additional fresh invocation may enter
```

It does not mean:

```text
reuse old candidate
reuse old validation
reuse old append
guaranteed success
automatic A3
retry until success
```

Fresh A2 re-observes the authoritative world.

Compact model:

```text
S_v1 = {effect, observation, authority, owner}

X_v = ⨆_{s ∈ S_v} X_{v,s}

x ~_{v,s} y
⇔
∀C ∈ Context_v(s),
Beh_v(C,x) ≡_{α,v} Beh_v(C,y)

Q_{v,s} = X_{v,s} / ~_{v,s}

Q_v = X_v / ~_v
≅
⨆_{s ∈ S_v} Q_{v,s}

π_{v,s}(x) = [x]_{v,s}

σ_v(x)
=
(sort, O_hat, S_hat, C_hat, R_hat, L_hat)

σ_v is a candidate finite-arity summary;
no complete-invariant or quotient-representation theorem is proved

W ∈ 𝒲_v
W = (H, I, B) as the current Stage 4E candidate abstraction

Γ_v = {γ = (x || W) | x ∈ X_v, W ∈ 𝒲_v, γ well-typed}

γ = (x || W)
--{ℓ,ω}_v-->
γ' = (x' || W')

SourceClassOf_v([a],[o])
⇔
∃a' ∈ [a], ∃o' ∈ [o]. SourceOf_v(a',o')
subject to representative-independence proof

CURRENT_ABSENT
CURRENT_UNEVALUATED(result)
CURRENT_IDENTIFIED(result, ν)
CURRENT_DECIDED(result, ν, decision, selection)
CURRENT_REFUSED(result, ν, refusal)

REINVOCATION_UNASSESSED(r, source)
NO_REINVOCATION_AUTHORITY(r)
ISSUED_REINVOCATION_AUTHORITY(r)
REINVOCATION_AVAILABLE(authority)  # owner state
REINVOCATION_SPENT(authority)      # owner state
```

A reference-implementation label is not itself a quotient class:

```text
same technical carrier
!=
semantic equivalence
```

The \(v_1\) production-positive Stage 4E families are:

```text
Preparation-timeout profile
→ authority

Typed append version-advance profile
→ authority
```

while:

```text
generic STALE_WRITE
!=
authority
```

---

## 25. Current boundary after Stage 4

```text
Stage 4A
→ SemanticOutcome
→ COMPLETE / CLOSED

Stage 4B
→ DecisionReceipt
→ COMPLETE / CLOSED

Stage 4B.1
→ completed bounded producer-specific DiagnosticTrace / ResolutionTrace stage
→ COMPLETE / CLOSED

Stage 4B.2
→ Measurement Evidence
→ COMPLETE / CLOSED

Stage 4B.3
→ Projection Trust Continuation investigation
→ CLOSED AS NOT CURRENTLY JUSTIFIED

Stage 4B.5
→ Order Correctness Contract v0
→ COMPLETE / CLOSED

Stage 4C
→ current-response Runtime Decision Authority
→ COMPLETE / CLOSED

Stage 4C.5
→ bounded compatibility / documentation closeout
→ COMPLETE
→ no new runtime policy

Stage 4D
→ dynamic HOW-selection responsibility retained
→ implementation deferred

Stage 4E
→ bounded same-request re-invocation authority
→ COMPLETE / CLOSED

ADR 0029
→ Stage 4C+ exists at the automation boundary
→ ACCEPTED
```

Stage 4B.1 was a bounded producer-specific trace stage; this inventory does not imply that one generic cross-producer `DiagnosticTrace` abstraction exists.

Known reference-implementation debt retained intentionally:

```text
AdmissionVerdict.STALE_WRITE
= heterogeneous coarse technical carrier

STALE_WRITE alone
!= proof of concurrency
!= proof of authoritative-world advance
!= retryability
!= re-invocation authority
```

The reference implementation remains authoritative for what it actually executes, while this model normalizes only at the abstraction boundary.

Still not implemented:

```text
generic retry framework
dynamic strategy selector
automatic A3
retry budgets / backoff
durable AttemptLog
restart-recovery authority
RecoveryPlanner runtime
RecoveryProposal runtime
ControlledExecutor runtime
universal agent protocol
Stage 5 action-safety runtime
```

This candidate quotient model describes the distinctions it proposes for current Compass behavior, not what the next experiment may add.

---

## 26. Next semantic checkpoint

A future protocol-oriented model may use normalized vocabulary such as `APPEND_ADMISSION_CONFLICT`, `AUTHORITATIVE_PREMISE_SUPERSEDED`, `CANDIDATE_SEQUENCE_INCOMPATIBLE`, `STREAM_POSITION_OCCUPIED`, and `UNCLASSIFIED_APPEND_ADMISSION_CONFLICT` even if the historical Python implementation continues to expose `STALE_WRITE`. Those names would be protocol-candidate vocabulary only after separate review; the current reference implementation need not be globally renamed to match them.

The next major quotient checkpoint should occur after a bounded autonomous-governance experiment introduces a concrete flow such as:

```text
producer / Stage 4B evidence
        ↓
deterministic RecoveryPlanner
        ↓
RecoveryProposal
        ↓
Stage 4C / Stage 4E authority
        ↓
ControlledExecutor
        ↓
fresh observation
        ↓
governance again
```

with:

```text
planner proposal
!=
execution authority
```

Then ask:

> Does this composition create a genuinely new Compass-level semantic distinction?

If no:

```text
implementation expands
without that distinction alone requiring v2
```

If yes:

```text
Context_v1 or F_v1 is insufficient
→ quotient refinement
→ possible v2
```

---

## 27. Final principle

The quotient model should erase only distinctions that do not change any consequence Compass currently cares about.

Formally:

\[
x\sim_v y
\]

only when every current consequence-bearing context observes equivalent behavior modulo permitted nominal renaming.

The practical compression is:

```text
large concrete implementation state space
        ↓
preserve consequence-bearing distinctions
        ↓
candidate compressed semantic model
```

The architecture can then evolve by asking:

> Did this implementation change merely add another representation of an existing semantic distinction, or did it create a new distinction that current Compass contexts can observe?

`v1` records the completed Stage 4 boundary:

```text
candidate
!=
accepted fact

evidence
!=
semantic meaning

semantic meaning
!=
authority

authority
!=
execution

current-response authority
!=
another-invocation authority

typed source evidence
!=
heterogeneous technical carrier

same implementation label
!=
semantic equivalence

fresh re-invocation
!=
reuse of stale work
```

Future autonomous proposal / execution semantics remain evidence-driven candidates for the next quotient revision.
