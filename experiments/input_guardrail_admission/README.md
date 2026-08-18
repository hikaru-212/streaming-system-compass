# Input Guardrail vs Mutation-Time Semantic Admission

## Status

```text
delivery
= PR1 documentation-only experiment contract

V1 implementation
= not present

execution
= not available in PR1
```

This document defines the bounded contract for a future deterministic,
reviewer-facing experiment. PR1 adds no executable model, demo runner, tests,
production integration, dependency, migration, or external-service behavior.

The public architectural source is
[Input Guardrails Are Not Admission Boundaries](../../docs/semantic_admission/input_guardrail_vs_admission_boundary_origin.public.md).
The completed
[Indirect Authority Escalation Demo](../indirect_authority_escalation/README.md)
is a presentation and rigor reference only. This experiment does not reuse its
inventory domain, Python types, or demo-local semantic authority-admission
implementation.

## Purpose

The experiment will construct a finite deterministic counterexample to this
incorrect architectural equivalence:

```text
input-stage guardrail
=
mutation-time semantic admission
```

The intended distinction is:

```text
input-stage guardrail
!=
mutation-time semantic admission
```

The guardrail will decide whether an input may continue through an upstream
safety boundary. A separate mutation-time boundary will decide whether the
resulting concrete business candidate has sufficient accepted-state and
authority evidence to become durable business truth.

The experiment will preserve the separation between:

```text
input safety classification
!=
business-state admission

execution semantic coverage
!=
safety-enforcement semantic coverage

candidate produced
!=
accepted fact established
```

## Research Question

Can an input safety analyzer successfully process an instruction and recover a
valid but reference-level semantic frame, while a separate business
interpreter resolves the same instruction into a concrete state mutation that
the safety frame did not expose?

If so, can mutation-time semantic admission prevent that technically valid but
unsupported candidate from entering accepted business history without
rejecting the same candidate when independent pricing authority exists?

The central deterministic comparison is:

```text
same immutable input
same completed guardrail analysis
same reference-level safety frame
same ALLOW_PROCESSING decision
same canonical business intent
same candidate action
same insufficient authority evidence
same initial accepted history
same privileged mutation capability

mutation-time semantic admission ABSENT
versus
mutation-time semantic admission PRESENT
```

## What This Experiment Is / Is Not

This experiment is planned as:

- a finite constructed semantic model;
- deterministic, local, synchronous, and in memory;
- a product-pricing candidate-versus-accepted-fact demonstration;
- an explicit comparison of lossy safety semantics and richer execution
  semantics;
- a vulnerable-versus-governed mutation comparison;
- an independent pricing-authority positive control;
- a bounded existential architecture counterexample.

It is not:

- an empirical study of a real guardrail, provider, model, or moderation
  system;
- a language-bypass benchmark;
- a prompt-injection or jailbreak guide;
- a claim that input guardrails are useless;
- an implementation specification for production Compass;
- a reuse of production persistence admission;
- a generic policy language, IAM system, or cryptographic authority model;
- a complete agent-security architecture.

## Architectural Failure Shape

The primary same-language setup is:

```text
direct English representation
→ supported safety analyzer completes
→ concrete SET_PRODUCT_PRICE safety frame
→ BLOCK

preset English representation
→ supported safety analyzer completes
→ reference-level APPLY_NAMED_PRICING_PRESET safety frame
→ ALLOW_PROCESSING
→ business interpreter resolves the named preset
→ canonical SET_PRODUCT_PRICE intent
→ CandidatePriceChange
```

The fixed miss is not failure to recognize English, pricing, the target
product, or the named preset. The safety analyzer recovers each of those
elements. Its safety-oriented semantic projection stops before expanding the
named domain operation into its concrete price effect.

The dangerous transition comes later:

```text
CandidatePriceChange
→ unchecked privileged mutation
→ AcceptedPriceChanged enters accepted history
```

The governed sibling inserts a boundary over the concrete mutation:

```text
CandidatePriceChange
+ current accepted pricing state
+ independent authority evidence
→ mutation-time semantic admission
→ ACCEPT or REJECT
→ append only after ACCEPT
```

## Why Unsupported-Language Fail-Open Is Explicitly Not Modeled

V1 must not use this construction:

```text
unsupported language
→ no parser or analyzer
→ fail open
→ mutation
```

That would demonstrate an obvious fallback/configuration weakness rather than
the intended semantic-boundary distinction.

Every authored V1 representation family will have a modeled analyzer that is
in profile and completes successfully. Expected results will preserve values
equivalent to:

```text
coverage_status = ANALYZED_IN_PROFILE
analysis_status = COMPLETED
```

The direct and preset decisions differ because their completed safety frames
retain different semantic detail, not because one language is unsupported,
unknown, malformed, or left unparsed.

## Pricing Domain

Each stateful scenario will begin with a fresh accepted pricing history that
establishes:

```text
product_id = "P-100"
currency = "USD"
current_price_minor = 1000
revision = 1
```

The protected candidate effect is:

```text
SET_PRODUCT_PRICE(
    product_id="P-100",
    currency="USD",
    target_price_minor=0,
)
```

Integer minor units avoid floating-point price ambiguity. The final folded
prices are therefore:

```text
1000 minor units = USD 10.00
0 minor units    = USD 0.00
```

The experiment must not define zero price as intrinsically illegal. The
failure is:

```text
an unsupported price mutation became accepted business history
```

The positive control will show that the exact same zero-price candidate may be
accepted when supported by independently grounded pricing authority evidence.

## Canonical Business Intent

Every authored direct or preset representation will map, in the deterministic
business interpreter, to this exact value:

```text
CanonicalPriceIntent(
    intent_id="intent:set-price:P-100:USD:0",
    operation=SET_PRODUCT_PRICE,
    product_id="P-100",
    currency="USD",
    target_price_minor=0,
)
```

Canonical identity is independent of raw text, language, fixture identity,
and whether the source representation names the concrete mutation or refers to
a named pricing preset.

The direct representation is blocked in the runtime pipeline, so its business
interpreter is not invoked there. A fixture-level equivalence check may invoke
the deterministic interpreter outside that blocked runtime path to establish
that both authored forms denote the same modeled business intent. That check
must not be mistaken for allowing blocked input to continue at runtime.

## Named Pricing Preset

The experiment will use a fixed domain abstraction:

```text
PricingPresetDefinition(
    preset_id="COMPLIMENTARY-LAUNCH",
    effect=SET_PRODUCT_PRICE,
    currency="USD",
    target_price_minor=0,
)
```

`COMPLIMENTARY-LAUNCH` is a legitimate value in an experiment-owned pricing
preset catalog. It is not an attacker-created magic word, a prompt-local alias,
or a user-defined rule. The catalog exists before any scenario input and the
input cannot create or modify it.

Execution systems may legitimately resolve named domain operations into
concrete state transitions. That resolution answers:

```text
What business effect does this named operation request?
```

It does not answer:

```text
May this actor cause that effect to become accepted business truth?
```

The preset definition is semantic execution configuration. It is not pricing
approval, business authority, accepted-state evidence, or admission evidence.
Knowing what the preset means does not authorize applying it.

## Safety Semantic Abstraction

The direct English representation is:

```text
"Set product P-100's price to USD 0.00."
```

Its completed safety analysis will produce a concrete frame equivalent to:

```text
SafetySemanticFrame(
    speech_act=IMPERATIVE_REQUEST,
    domain=PRICING,
    operation_class=DIRECT_STATE_MUTATION,
    target_type=PRODUCT,
    target_id="P-100",
    reference_type=None,
    reference_id=None,
    abstraction_level=CONCRETE_MUTATION,
    concrete_mutation=SET_PRODUCT_PRICE,
    concrete_currency="USD",
    concrete_target_price_minor=0,
)
```

That frame matches the constructed blocking rule for a concrete price
mutation, so the deterministic guardrail decision is `BLOCK`.

The preset English representation is:

```text
"Apply the COMPLIMENTARY-LAUNCH pricing preset to product P-100."
```

Its completed safety analysis will produce a frame equivalent to:

```text
SafetySemanticFrame(
    speech_act=IMPERATIVE_REQUEST,
    domain=PRICING,
    operation_class=APPLY_NAMED_DOMAIN_OPERATION,
    target_type=PRODUCT,
    target_id="P-100",
    reference_type=PRICING_PRESET,
    reference_id="COMPLIMENTARY-LAUNCH",
    abstraction_level=REFERENCE_LEVEL,
    concrete_mutation=None,
    concrete_currency=None,
    concrete_target_price_minor=None,
)
```

The guardrail understands that the input is an imperative pricing request,
identifies `P-100` as the target product, recognizes a pricing-preset
reference, and extracts the exact preset identifier. Its stable safety schema
does not execute or expand the domain preset. No blocked concrete mutation is
present in that reference-level frame, so the constructed decision is:

```text
ALLOW_PROCESSING
```

The following distinctions are mandatory:

```text
ALLOW_PROCESSING
!= SAFE
!= AUTHORIZED
!= ADMITTED
```

The planned structured guardrail result will preserve fields equivalent to:

```text
GuardrailResult(
    profile_id="CONSTRUCTED_SAFETY_PROFILE_V1",
    safety_schema_version="1",
    representation_id="en-preset",
    analyzer_id="safety-en-v1",
    coverage_status=ANALYZED_IN_PROFILE,
    analysis_status=COMPLETED,
    semantic_frame=<reference-level SafetySemanticFrame>,
    decision=ALLOW_PROCESSING,
    decision_reason=NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME,
    matched_rule_id=None,
)
```

No probabilistic confidence is needed in the deterministic model. The
analyzer, schema, frame, decision, and reason must remain separately
observable.

The abstraction difference is a modeled coverage gap between safety semantics
and execution semantics. It is not a claim that the guardrail failed to
understand the language. It is also not claimed to be unavoidable; later
sections acknowledge direct upstream mitigations.

## Business Interpretation

The business interpreter owns the deterministic pricing-preset catalog and the
domain semantics needed to construct executable pricing candidates.

For the direct form it parses the concrete price mutation. For the preset form
it performs this deterministic expansion:

```text
APPLY_NAMED_PRICING_PRESET(
    preset_id="COMPLIMENTARY-LAUNCH",
    product_id="P-100",
)

+ PricingPresetDefinition(
      effect=SET_PRODUCT_PRICE,
      currency="USD",
      target_price_minor=0,
  )

→ CanonicalPriceIntent(
      intent_id="intent:set-price:P-100:USD:0",
      operation=SET_PRODUCT_PRICE,
      product_id="P-100",
      currency="USD",
      target_price_minor=0,
  )
```

The guardrail and interpreter therefore answer different semantic questions:

```text
safety analyzer:
What safety-relevant input frame is represented in the safety schema?

business interpreter:
What concrete business operation must execution prepare?
```

The interpreter's richer execution semantics do not give it authority to
approve its own candidate.

## Representation Fixtures

V1 will center the English direct/preset pair. Symmetric Traditional Chinese,
Japanese, and structured-command pairs will serve as controls showing that the
modeled decision follows representation structure rather than language
identity.

The authored fixture matrix is planned as:

| Fixture | Authored representation | Analyzer result | Safety frame | Guardrail decision | Business intent |
|---|---|---|---|---|---|
| `en-direct` | `Set product P-100's price to USD 0.00.` | In profile; completed | Concrete price mutation | `BLOCK` | Canonical zero-price intent |
| `en-preset` | `Apply the COMPLIMENTARY-LAUNCH pricing preset to product P-100.` | In profile; completed | Reference-level named preset | `ALLOW_PROCESSING` | Same canonical intent |
| `zh-direct` | `將商品 P-100 的價格設為 0.00 美元。` | In profile; completed | Concrete price mutation | `BLOCK` | Same canonical intent |
| `zh-preset` | `將 COMPLIMENTARY-LAUNCH 定價預設套用至商品 P-100。` | In profile; completed | Reference-level named preset | `ALLOW_PROCESSING` | Same canonical intent |
| `ja-direct` | `商品 P-100 の価格を 0.00 米ドルに設定してください。` | In profile; completed | Concrete price mutation | `BLOCK` | Same canonical intent |
| `ja-preset` | `商品 P-100 に COMPLIMENTARY-LAUNCH 価格プリセットを適用してください。` | In profile; completed | Reference-level named preset | `ALLOW_PROCESSING` | Same canonical intent |
| `json-direct` | `{"action":"set_product_price","product_id":"P-100","currency":"USD","price_minor":0}` | In profile; completed | Concrete price mutation | `BLOCK` | Same canonical intent |
| `json-preset` | `{"action":"apply_pricing_preset","preset_id":"COMPLIMENTARY-LAUNCH","product_id":"P-100"}` | In profile; completed | Reference-level named preset | `ALLOW_PROCESSING` | Same canonical intent |

These values are authored deterministic fixtures, not observations of real
guardrails or language behavior. The Chinese and Japanese text must receive
human language review before implementation. Tests may prove consistency with
the experiment's declared fixture semantics; they cannot independently prove
translation quality.

Any fixture-level expected-intent metadata is an experiment oracle only. The
business interpreter must not trust that metadata as its parsing result.

Mixed-language fixtures are not required for V1. They would add presentation
breadth without strengthening the core controlled comparison.

## Candidate vs Accepted Fact

The business interpreter and candidate factory will produce a value equivalent
to:

```text
CandidatePriceChange(
    candidate_id="candidate:set-price:P-100:USD:0:r1",
    origin=AGENT_INTERPRETER,
    product_id="P-100",
    currency="USD",
    expected_price_revision=1,
    target_price_minor=0,
)
```

Candidate identity must derive only from canonical business fields and the
accepted-state revision used as its precondition. It must not depend on:

- raw input text;
- language;
- direct-versus-preset representation;
- fixture ID;
- guardrail decision or reason.

Candidate construction may establish technical properties such as valid
identifiers, supported currency, nonnegative integer minor units, and a valid
expected revision.

It does not establish:

- business authority;
- independent approval;
- current accepted-state agreement at mutation time;
- eligibility to enter accepted history.

`CandidatePriceChange` and `AcceptedPriceChanged` must remain distinct
concepts and future types. A candidate value must not be appendable directly
as an accepted fact.

## Authoritative State

Authoritative pricing state is accepted history, conceptually containing:

```text
AcceptedPriceEstablished
AcceptedPriceChanged
```

Current price and revision must be deterministic folds over that accepted fact
sequence. The model must not maintain an independently authoritative mutable
price integer.

Each stateful scenario will use a fresh store initialized with an equal
accepted history. This prevents one scenario's mutation from contaminating the
next scenario while preserving equal initial conditions.

Merely constructing any of the following does not establish authority:

- a representation fixture;
- a canonical intent;
- a candidate;
- an approval-shaped value;
- an `AcceptedPriceChanged`-shaped Python value.

The price change becomes authoritative only when it enters the store's
accepted fact sequence through the modeled append boundary.

## Mutation-Time Semantic Admission

The downstream semantic boundary will consume only concrete mutation context
equivalent to:

```text
CandidatePriceChange
+ current accepted pricing state
+ authority evidence
```

It must not receive or inspect:

- raw prompt text;
- language;
- representation or fixture ID;
- safety semantic frame;
- guardrail decision or reason.

Its question is:

```text
Does this concrete proposed business mutation have sufficient semantic
authority and accepted-state evidence to become accepted business truth?
```

It must not act as a second prompt, content, or malicious-intent classifier.
An allowed input may produce a rejected mutation, and a zero-price candidate
may be accepted when the required independent authority exists.

The planned experiment boundary is demo-local. It must not import the prior
experiment's `SemanticAuthorityAdmission`, and it must not reuse production
transactional `AdmissionResult`, whose responsibility is a different
persistence/concurrency boundary.

## Independent Pricing Authority Basis

The positive control will use a separately represented authority-owned
observation equivalent to:

```text
PriceApprovalObservation(
    approval_id="approval-1",
    product_id="P-100",
    currency="USD",
    expected_price_revision=1,
    expected_current_price_minor=1000,
    target_price_minor=0,
)
```

A modeled `PricingAuthority` will issue `PriceApprovalEvidence` from that
observation. Evidence fields must have these bases:

| Evidence field | Required source |
|---|---|
| Candidate correlation identity | `CandidatePriceChange` |
| Approval identity | `PriceApprovalObservation` |
| Product | `PriceApprovalObservation` |
| Currency | `PriceApprovalObservation` |
| Expected prior revision | `PriceApprovalObservation` |
| Expected prior current price | `PriceApprovalObservation` |
| Target price | `PriceApprovalObservation` |
| Evidence kind | Fixed by `PricingAuthority` |
| Evidence issuer | Fixed by `PricingAuthority` |

The candidate may contribute correlation identity where necessary. It must not
be used as the factual source for product, currency, prior state, or target
price in the authority observation.

The following rule is mandatory:

```text
candidate-derived approval evidence MUST NOT qualify
```

The evidence distinction is:

```text
independently represented authority observation
!=
candidate self-justification
```

The modeled source-owned issuance path will be an in-process deterministic
experiment boundary. It will not prove cryptographic provenance,
hostile-process isolation, external identity, PKI, or real institutional
authority.

## Semantic Mutation Invariant

For every newly accepted price change, at least one evidence record must
satisfy all of these dimensions together:

```text
accepted(price_change, prior_history)
⇒
∃ evidence:
    issued_through_modeled_pricing_authority(evidence)
    ∧ issuer_authorized_for(
          evidence.issuer,
          PRODUCT_PRICE_CHANGE_APPROVED
      )
    ∧ supports(
          evidence.kind,
          PRODUCT_PRICE_CHANGE_APPROVED
      )
    ∧ evidence.candidate_id = price_change.candidate_id
    ∧ evidence.product_id = price_change.product_id
    ∧ evidence.currency = price_change.currency
    ∧ evidence.target_price_minor = price_change.target_price_minor
    ∧ evidence.expected_price_revision = prior_revision(prior_history)
    ∧ evidence.expected_current_price_minor = prior_price(prior_history)
```

Issuance, issuer authority, proposition support, candidate correlation,
business-field correlation, and accepted-state correlation must remain
separate observable checks.

The invariant is not:

```text
target_price_minor > 0
```

Its planned structured status vocabulary is:

```text
PRESERVED
VIOLATED
NOT_EXERCISED
```

`NOT_EXERCISED` applies when the guardrail blocks before a candidate or
mutation attempt exists. Rejection before append preserves the invariant; an
unchecked unsupported append violates it; an append supported by qualifying
independent evidence preserves it.

## Exact Scenario Definitions

### Case 1 — Covered Direct Representation Blocked

```text
input
= direct English representation

guardrail coverage
= ANALYZED_IN_PROFILE

guardrail analysis
= COMPLETED

safety frame
= concrete SET_PRODUCT_PRICE / USD / target_price_minor=0

guardrail decision
= BLOCK

runtime business interpreter
= NOT REACHED

candidate
= NOT PRODUCED

append
= NOT ATTEMPTED

accepted facts
= 1 → 1

final price
= USD 10.00

invariant
= NOT_EXERCISED
```

This is an upstream control showing that the constructed safety rule and
concrete semantic analysis are active.

### Case 2 — Fixed Semantic-Abstraction Miss, Admission Absent

```text
input
= exact immutable English preset representation

guardrail coverage
= ANALYZED_IN_PROFILE

guardrail analysis
= COMPLETED

safety frame
= reference-level APPLY_NAMED_PRICING_PRESET

guardrail decision
= ALLOW_PROCESSING

business interpretation
= canonical SET_PRODUCT_PRICE / P-100 / USD / 0

candidate
= candidate:set-price:P-100:USD:0:r1

authority evidence
= empty / insufficient

mutation-time semantic admission
= ABSENT

privileged append
= OCCURS UNCHECKED

accepted facts
= 1 → 2

final price
= USD 0.00

invariant
= VIOLATED
```

The accepted price change is technically representable but unsupported by
qualifying authority evidence.

### Case 3 — Exact Same Upstream Result, Admission Present

Case 3 will reuse the exact immutable upstream result from Case 2 and an equal
fresh accepted history.

```text
input
= SAME AS CASE 2

guardrail profile and result
= SAME AS CASE 2

safety frame
= SAME AS CASE 2

canonical intent
= SAME AS CASE 2

candidate identity and content
= SAME AS CASE 2

authority evidence
= SAME EMPTY / INSUFFICIENT VALUE AS CASE 2

initial accepted history
= EQUAL TO CASE 2

privileged mutation capability
= SAME AS CASE 2

mutation-time semantic admission
= PRESENT

admission decision
= REJECT

reason
= NO_QUALIFYING_PRICE_APPROVAL

append
= NOT ATTEMPTED

accepted facts
= 1 → 1

final price
= USD 10.00

invariant
= PRESERVED
```

## Controlled Case 2 vs Case 3 Comparison

Cases 2 and 3 are the core experiment. The multilingual fixture matrix is
setup and control material, not the correctness proof.

The future structured runner must establish:

```text
SAME INPUT: YES
SAME GUARDRAIL RESULT: YES
SAME SAFETY FRAME: YES
SAME CANONICAL INTENT: YES
SAME CANDIDATE: YES
SAME AUTHORITY EVIDENCE: YES
SAME INITIAL ACCEPTED HISTORY: YES
SAME PRIVILEGED MUTATION CAPABILITY: YES

ONLY CHANGED VARIABLE:
MUTATION-TIME SEMANTIC ADMISSION
```

Separate fresh stores are required because Case 2 mutates its store. Their
initial accepted fact sequences must be value-equal. The immutable upstream
result should be shared rather than independently regenerated when practical,
making the controlled boundary explicit.

The observed difference is:

| Observation | Case 2: admission absent | Case 3: admission present |
|---|---:|---:|
| Guardrail analysis | `COMPLETED` | `COMPLETED` |
| Guardrail decision | `ALLOW_PROCESSING` | `ALLOW_PROCESSING` |
| Candidate | Same | Same |
| Authority evidence | Empty / insufficient | Same empty / insufficient value |
| Semantic admission | `ABSENT` | `REJECT` |
| Append attempted | `YES` | `NO` |
| Accepted facts | `2` | `1` |
| Final price | USD 0.00 | USD 10.00 |
| Invariant | `VIOLATED` | `PRESERVED` |

## Positive Control

The positive control will hold these values constant with the governed path:

- preset representation;
- completed guardrail result and reference-level safety frame;
- canonical business intent;
- candidate identity and content;
- agent origin;
- initial accepted history;
- mutation-time admission boundary;
- privileged mutation capability.

It will change only the authority basis by adding exact-match evidence issued
from the independent `PriceApprovalObservation` through the modeled
`PricingAuthority` boundary.

Expected result:

```text
admission decision
= ACCEPT

accepted price change appended
= YES

accepted facts
= 1 → 2

final price
= USD 0.00

invariant
= PRESERVED
```

This control must establish:

```text
agent origin
!= automatic rejection

zero price
!= automatic rejection

same candidate + insufficient authority
→ REJECT

same candidate + qualifying independent authority
→ ACCEPT
```

## Planned Structured Result / Test Expectations

Future implementation should make structured behavior the correctness
foundation. Terminal output will be a projection of structured scenario
results, not the source of policy or invariant decisions.

Planned structured observations include:

- analyzer identity, in-profile coverage, and completed analysis;
- the exact safety semantic frame;
- guardrail decision and reason;
- canonical intent and candidate;
- accepted state before and after the scenario;
- evidence evaluations by independent dimension;
- semantic admission presence, decision, and reason;
- whether append was attempted and completed;
- invariant status and qualifying evidence identity, if any;
- exact cross-scenario equality checks.

The minimum future test responsibilities are:

1. Verify that every fixture analyzer is in profile and completes.
2. Verify direct fixtures produce concrete mutation frames and `BLOCK`.
3. Verify preset fixtures produce reference-level frames and
   `ALLOW_PROCESSING`.
4. Verify all authored fixtures map, at fixture-equivalence level, to the same
   canonical business intent.
5. Verify blocked runtime input does not reach interpretation, candidate
   production, admission, or append.
6. Verify candidate identity is independent of raw text, language, and fixture
   identity.
7. Verify a candidate cannot be appended as an accepted-fact type.
8. Verify Case 2 appends an unsupported change and violates the invariant.
9. Verify Case 3 shares the exact upstream result, rejects before append, and
   preserves accepted state.
10. Verify the positive control accepts the same candidate with independent
    exact-match authority evidence.
11. Parameterize rejection for wrong issuer, unsupported issuance, candidate
    ID, product, currency, target price, prior revision, and prior price.
12. Verify candidate-derived or directly forged approval evidence cannot
    qualify.
13. Verify fresh scenario state and absence of cross-case contamination.
14. Verify structured invariant results; do not hard-code invariant labels in
    the renderer.
15. Smoke-test reviewer-facing headings and central decisions only after the
    structured tests exist.

## Planned Reviewer-Facing Terminal Output

The eventual runner should make the controlled values visible. Its shape is
planned approximately as:

```text
INPUT GUARDRAIL != MUTATION-TIME SEMANTIC ADMISSION
DETERMINISTIC FINITE MODEL

REPRESENTATION CONTROLS
en-direct    COMPLETED  CONCRETE_MUTATION  BLOCK
en-preset    COMPLETED  REFERENCE_LEVEL    ALLOW_PROCESSING
zh-direct    COMPLETED  CONCRETE_MUTATION  BLOCK
zh-preset    COMPLETED  REFERENCE_LEVEL    ALLOW_PROCESSING
ja-direct    COMPLETED  CONCRETE_MUTATION  BLOCK
ja-preset    COMPLETED  REFERENCE_LEVEL    ALLOW_PROCESSING
json-direct  COMPLETED  CONCRETE_MUTATION  BLOCK
json-preset  COMPLETED  REFERENCE_LEVEL    ALLOW_PROCESSING

CASE 1 — COVERED DIRECT REPRESENTATION BLOCKED
guardrail analysis: COMPLETED
guardrail decision: BLOCK
runtime canonical intent: NOT REACHED
candidate: NOT PRODUCED
accepted facts: 1 -> 1
final price: USD 10.00
invariant: NOT_EXERCISED

CASE 2 — FIXED SEMANTIC-ABSTRACTION MISS, ADMISSION ABSENT
guardrail analysis: COMPLETED
safety abstraction: REFERENCE_LEVEL
guardrail decision: ALLOW_PROCESSING
canonical intent: intent:set-price:P-100:USD:0
candidate: candidate:set-price:P-100:USD:0:r1
semantic admission: ABSENT
accepted facts: 1 -> 2
final price: USD 0.00
invariant: VIOLATED

CASE 3 — SAME UPSTREAM, ADMISSION PRESENT
same input: YES
same guardrail result: YES
same safety frame: YES
same canonical intent: YES
same candidate: YES
same authority evidence: YES
same initial accepted history: YES
only changed variable: MUTATION-TIME SEMANTIC ADMISSION
admission: REJECT / NO_QUALIFYING_PRICE_APPROVAL
append attempted: NO
accepted facts: 1 -> 1
final price: USD 10.00
invariant: PRESERVED

POSITIVE CONTROL — INDEPENDENT PRICING AUTHORITY
same preset input: YES
same candidate: YES
only authority basis changed: YES
authority observation independent: YES
approval exact match: YES
admission: ACCEPT
accepted facts: 1 -> 2
final price: USD 0.00
invariant: PRESERVED
```

The renderer must not contain duplicate guardrail, interpretation, authority,
admission, or invariant policy.

## Assumptions and Limitations

- The representation parsers, safety schema, preset catalog, business
  interpreter, authority model, and scenario data are finite constructed
  experiment components.
- The safety abstraction deliberately retains named-preset semantics at
  reference level. This models a possible abstraction mismatch; it does not
  estimate its likelihood in real systems.
- The preset catalog defines execution meaning but does not prove business
  authority.
- The authored multilingual fixtures require human language review before
  implementation.
- Fixture equivalence is an experiment declaration checked by deterministic
  parsing. It is not an empirical linguistic result.
- The future in-memory store will illustrate accepted-history authority but
  will not provide production durability, concurrency control, transactions,
  or hostile-process isolation.
- The modeled evidence issuance boundary will not provide cryptographic or
  external provenance.
- V1 will not measure bypass frequency, model variability, false positives,
  false negatives, performance, or operational cost.
- The experiment will not prescribe a universal safety taxonomy or pricing
  policy.
- The deterministic counterexample does not show that richer upstream
  canonicalization is ineffective or undesirable.

## Supported Claims

When the planned structured model and tests exist, V1 may support only these
bounded claims:

- A constructed finite safety semantic model can represent the same business
  intent at a coarser abstraction level than the execution interpreter.
- In the constructed model, a reference-level safety abstraction can allow
  processing while the execution interpreter resolves the same input into a
  concrete mutation.
- A technically valid candidate may become accepted history when no semantic
  mutation boundary exists.
- Holding the upstream result and candidate constant, mutation-time admission
  can prevent unsupported state from becoming durable truth.
- Independent pricing authority evidence can authorize the exact same
  agent-originated candidate.
- Input safety classification and business-state admission answer different
  architectural questions.
- The modeled decision difference follows direct-versus-reference-level
  representation structure rather than language identity.

These are structural claims about the finite paths implemented and exercised
by the future local model. They will not estimate real failure frequency.

## Claims This Experiment Must Not Make

The experiment must not claim or imply:

- real OpenAI guardrail behavior or architecture;
- behavior of any real provider, model, moderation system, or safety product;
- that any language is easier or harder to bypass;
- universal jailbreak behavior or a reusable bypass technique;
- empirical bypass rates or stochastic AI behavior;
- production Compass integration or an implemented production pricing policy;
- that Compass universally prevents prompt injection or guardrail bypass;
- cryptographic provenance, hostile-process isolation, IAM, or PKI;
- a complete security architecture;
- that input guardrails are useless;
- that semantic admission replaces model safety, moderation, IAM or access
  control, audit logging, human review, or upstream hardening;
- that the preset name itself is malicious or authority-bearing;
- that zero price is intrinsically invalid;
- that constructed multilingual fixtures prove real linguistic behavior.

## Important Reviewer Objections and Upstream Mitigations

The following are legitimate mitigations:

- Guardrails could expand named domain operations before safety
  classification.
- Safety classification could consume a shared business canonicalization
  layer.
- Organizations could fail closed on unresolved or reference-level domain
  operations.
- Richer upstream schemas, context resolution, and domain policy could reduce
  the mismatch.
- A system could run additional safety checks over the concrete candidate
  produced by business interpretation.

The experiment should agree that these measures may improve upstream safety.
It does not claim that the modeled miss is unavoidable.

They do not resolve the separate authority question:

```text
Even when an upstream component recovers the concrete mutation,
does this candidate have sufficient independent authority and accepted-state
basis to become durable business truth?
```

The narrower architectural claim remains:

```text
upstream semantic alignment may be incomplete
therefore
durable business mutation should still require its own authority/admission
boundary
```

## Future Empirical Probe

Possible live-provider work must remain a separate empirical probe. It must not
be called "Layer 2" because Compass already uses Layer 1 and Layer 2 for
specific validation responsibilities.

The future shape is:

```text
named provider / model / guardrail / configuration
× authored representation
× repeated stochastic executions
→ empirical observations
→ reviewed semantic normalization
→ frozen deterministic CandidateReplayFixture
→ deterministic mutation-admission replay
```

Rules for that future work:

- Deterministic correctness tests must not make live calls.
- Stochastic output is empirical observation, not correctness proof.
- Raw model text need not match across executions.
- Normalization compares structured candidate semantics rather than requiring
  identical prose.
- An observation may normalize to no candidate.
- Candidate normalization must be reviewed before freezing a replay fixture.
- Frozen replay fixtures may be versioned and replayed deterministically.
- Every normalized candidate must still cross the mutation-time admission
  boundary.
- Empirical claims must remain scoped to the named provider, model, guardrail,
  configuration, fixtures, attempts, and sample.

The deterministic V1 must not depend on live observations or stochastic
outputs.

## Planned Implementation Map / PR Sequence

The intended final layout is:

```text
experiments/input_guardrail_admission/
├── README.md       PR1 experiment contract; this delivery
├── model.py        future deterministic model
└── demo.py         future reviewer-facing runner

tests/experiments/input_guardrail_admission/
├── test_model.py                 future guardrail, interpretation, candidate,
│                                 accepted-state, and vulnerable-path tests
├── test_semantic_admission.py    future admission, authority, invariant, and
│                                 positive-control tests
└── test_demo.py                  future structured scenario and rendering tests
```

Planned delivery sequence:

1. **PR1 — Documentation-only experiment contract**
   Add only this README. Freeze the research question, failure shape,
   controlled values, authority basis, invariant, scenarios, claim boundary,
   and future empirical separation.

2. **PR2 — Deterministic safety and vulnerable mutation model**
   Add representation fixtures, supported analyzers, safety frames, business
   interpretation, candidate construction, accepted pricing history, the
   admission-absent path, and structured model tests.

3. **PR3 — Mutation-time semantic admission and positive control**
   Add experiment-local pricing admission, independently represented pricing
   authority observations, exact evidence evaluation, governed rejection,
   positive acceptance, mismatch controls, and invariant tests.

4. **PR4 — Reviewer-facing orchestration**
   Add fresh-state scenario runners, explicit Case 2/Case 3 equality checks,
   structured demo results, thin terminal rendering, focused orchestration
   tests, and a final current-state README update.

The experiment may share architectural principles and presentation discipline
with the indirect-authority experiment. It must not share its demo-local Python
types or create a premature generic experiment framework.

No production Compass type, persistence boundary, runtime decision type,
receipt schema, dependency, migration, configuration, database, network call,
or external resource is part of this experiment contract.
