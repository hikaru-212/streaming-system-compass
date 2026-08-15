# Why Stage 4B.5 Exists

[← Back to Stage 4B.5](README.md)

## Status

Stage 4B.5 is complete.

This note records why the stage was necessary, what semantic gap it closes, and
what it deliberately leaves for later governance layers.

It is a stage-level rationale.

It is not a replacement for the Order correctness contract, runtime evidence
contracts, implementation notes, or future Retry Governance policy.

---

## The Problem Before Stage 4B.5

Before Stage 4B.5, the runtime could already answer broad questions such as:

```text
Did validation pass?

Did validation block the candidate?

What broad semantic outcome describes the completed write-side result?

What durable governance evidence should be retained?
```

Those boundaries were necessary.

They were not sufficient for a machine consumer that must react to the reason
a candidate was rejected.

Consider:

```text
ValidationResult = FAILED

ValidationDecision = BLOCK

SemanticOutcome =
    category: BLOCK_REQUIRED
    semantic_code: SEMANTIC_CONFLICT_DETECTED
```

This correctly says that the candidate must not proceed.

It does not answer:

```text
Which correctness proposition failed?
```

A human can often read a reason string and infer what happened.

A machine should not need to.

---

## FAILED Is a Result Class, Not a Semantic Identity

A `FAILED` validation result may represent many different correctness failures.

For example:

```text
candidate sequence is not the next accepted version

candidate prev_event_id does not match accepted history

candidate prev_version does not match accepted history

candidate prev_status does not match accepted history

candidate event type is unsupported

candidate event type is illegal from the accepted status
```

All six failures may correctly produce:

```text
FAILED
→ BLOCK
```

but they do not mean the same thing.

The distinction matters when a later system needs to decide whether another
candidate should even be considered.

Without stable rule identity, downstream code would have to infer semantics
from a coarse status or from free text.

Stage 4B.5 exists to remove that inference requirement.

---

## Free Text Is Evidence for Humans, Not Authority for Machines

A reason such as:

```text
candidate previous version does not match accepted history
```

is useful diagnostic information.

It should not become a machine authority boundary.

Text can change because of:

```text
wording
punctuation
localization
logging changes
diagnostic detail
refactoring
```

A machine consumer should not depend on:

```text
if "previous version" in reason:
    ...
```

That would convert presentation text into protocol.

Stage 4B.5 therefore introduces stable correctness-rule identities such as:

```text
order.transition.sequence-matches-accepted-next-version

order.transition.proof-prev-event-id-matches-accepted

order.transition.proof-prev-version-matches-accepted

order.transition.proof-prev-status-matches-accepted

order.transition.candidate-event-type-supported

order.transition.event-type-legal-from-accepted-status
```

The runtime emits the identity at the exact executable predicate branch.

It does not reconstruct the identity afterward from text.

---

## The Correctness Contract Comes Before Runtime Evidence

Stage 4B.5 first defines the Order correctness vocabulary independently of
runtime production.

The canonical contract contains eighteen stable rules across four categories:

```text
COMMAND_LEGALITY

CANDIDATE_CONSTRUCTION

TRUSTED_APPLICATION

TRANSITION_TRUTH
```

The contract is identity-driven.

Conceptually:

```text
rule_id
→ semantic proposition
→ category
→ subject
```

Specialized relationships are also identity-driven:

```text
transition_rule_id
→ command
→ predecessor status
→ candidate event type
→ resulting status
```

and:

```text
amount_rule_id
→ command
→ amount constraint
```

The purpose is not merely to enumerate valid examples.

The purpose is to prevent arbitrary combinations of independently valid fields
from becoming supported semantic objects.

The authoritative definition determines the dependent metadata.

---

## Contract Coverage Is Not Runtime Producer Coverage

The canonical Order correctness contract contains eighteen rules.

Stage 4B.5 does not claim that all eighteen currently have typed runtime
producers.

The concrete runtime producer added in this stage is the existing
`FullProofValidator`.

Its current executable authority covers six `TRANSITION_TRUTH` rules.

Therefore:

```text
canonical contract vocabulary
= 18 rules

current FullProof typed producer coverage
= 6 transition-truth rules
```

This distinction is intentional.

A stable semantic vocabulary may exist before every proposition has a concrete
runtime producer.

Stage 4B.5 must not fabricate evidence for rules that were not actually
observed by an executable authority.

---

## Same Invocation Matters

The central runtime evidence is not merely:

```text
validation failed
+
some rule object
```

The rule observation belongs to the same validation invocation that produced
the `ValidationDecision`.

Conceptually:

```text
candidate
+
ValidationContext
        ↓
FullProofValidator
        ↓
ValidationResult
+
optional exact OrderRuleViolationEvidence
        ↓
ValidationPolicy
        ↓
ValidationDecision
```

The runtime carrier preserves:

```text
the exact ValidationDecision object

the exact observed violation object
```

No second validation pass occurs.

No fallback re-validation occurs.

No reason parsing occurs.

No evidence is fabricated when validation never happened.

This prevents a later layer from accidentally combining a decision from one
invocation with evidence from another.

---

## Write-Side Propagation Preserves Observation, Not Policy

Once validation has occurred, the write side may later terminate for another
reason.

For example:

```text
validation succeeds
→ authoritative idempotency re-check
→ replay/conflict

validation succeeds
→ append admission
→ stale write
```

Stage 4B.5 preserves the runtime observation through the write-side result when
that observation actually happened.

But preservation does not make that evidence the terminal explanation for
every later outcome.

This distinction becomes important in the terminal semantic composition layer.

---

## SemanticOutcome Is Deliberately Not Expanded Per Rule

One possible design would have introduced new Stage 4A semantic codes such as:

```text
SEQUENCE_RULE_VIOLATED

PREVIOUS_EVENT_RULE_VIOLATED

PREVIOUS_VERSION_RULE_VIOLATED

PREVIOUS_STATUS_RULE_VIOLATED
...
```

Stage 4B.5 rejects that direction.

`SemanticOutcome` remains the coarse shared semantic interpretation boundary.

Exact correctness-rule identity is a refinement layered beside it.

Conceptually:

```text
PostgresWriteSideResult
        ↓
Stage 4A mapping
        ↓
SemanticOutcome

PostgresWriteSideResult
        ↓
terminal rule refinement
        ↓
OrderRuleViolationEvidence | None
```

The combined feedback therefore means:

```text
broad semantic conclusion
+
exact domain-specific refinement when applicable
```

rather than:

```text
one global semantic enum containing every possible business rule
```

This keeps the shared semantic vocabulary stable while allowing business
domains to retain their own precise correctness language.

---

## Terminal Refinement Is Source-Controlled

The terminal write-side composition applies exact rule refinement only when the
terminal result is:

```text
VALIDATION_BLOCKED
```

For that terminal outcome, typed Order rule evidence is required.

If the refined mapper receives:

```text
VALIDATION_BLOCKED
+
no OrderRuleViolationEvidence
```

it fails closed.

Other terminal outcomes expose:

```text
rule_refinement = None
```

even if a prior validation observation was preserved internally.

That prevents a previous validation observation from being misrepresented as
the terminal cause of:

```text
REPLAY

CONFLICT

ADMISSION_REJECTED

ACCEPTED
```

The Stage 4A mapping remains independently compatible with legacy coarse
results.

The stricter requirement belongs specifically to the Stage 4B.5 refined
feedback boundary.

---

## Why This Matters for Future Retry Governance

Stage 4B.5 does not decide retry.

That separation is one of its primary reasons for existing.

Without exact evidence, a future retry layer would see something like:

```text
FAILED
→ BLOCK
```

and would have to guess how another candidate should differ.

With Stage 4B.5:

```text
Candidate A
        ↓
SemanticOutcome
+
exact correctness-rule violation
        ↓
future Retry Governance
```

A later policy can reason about:

```text
Was another attempt authorized?

Why was it authorized or denied?

Which candidate dimensions may change?

Which dimensions must remain fixed?

Would another candidate merely reproduce the same invalid state?
```

That future layer may produce a separate contract such as:

```text
RetryDecisionEvidence
```

The separation is deliberate:

```text
RuleViolationEvidence
= what correctness proposition was violated?

RetryDecisionEvidence
= why is another attempt allowed or denied?
```

One does not imply the other.

In particular:

```text
failure observed
≠ retry permitted

retry permitted
≠ retry now

retry permitted
≠ retry forever
```

---

## YAML Is a Projection, Not a Second Authority

Stage 4B.5 also provides a deterministic YAML projection of the canonical Order
correctness contract.

Its purpose is readability and reviewability.

The authority direction remains:

```text
canonical Python contract
        ↓
deterministic projection
        ↓
YAML
```

not:

```text
YAML
→ production runtime semantics
```

Production code does not parse the YAML to determine correctness.

The committed projection exists so humans and external tooling can inspect the
contract without turning a second representation into a competing source of
truth.

---

## Runtime Cost Was Characterized Separately

Semantic correctness and runtime cost are different questions.

After the semantic path was complete, Stage 4B.5 characterized the incremental
cost using historical A, current B, and composed C surfaces.

The bounded findings are:

```text
micro evidence-aware B-A propagation
≈ 1–2 µs

micro semantic composition
≈ 13 µs

micro complete governance path
≈ 14–15 µs
```

In the recorded PostgreSQL workload:

```text
A baseline median
≈ 1–3 ms

same-invocation semantic composition
≈ 47–70 µs

complete C-A median estimate
≈ 50–100 µs
```

The PostgreSQL result corresponds to roughly low- to mid-single-digit median
overhead in the measured cells.

These measurements characterize one fixed workload and environment.

They do not establish universal production performance or permission to weaken
governance.

---

## A Closeout Lesson: Evidence Requirement Is Not Environment Accident

The Stage 4B.5 characterization also exposed an important implementation lesson.

Historical A-source verification genuinely requires access to the pinned Git
objects.

The first CI execution used a shallow repository checkout.

The local repository had the required historical commit; the CI checkout did
not.

The resulting failure was legitimate:

```text
required provenance object unavailable
→ provenance cannot be verified
→ fail closed
```

The CI checkout was therefore changed to provide the history required by the
experiment.

A different check exposed the opposite problem.

The benchmark initially required execution from a Python virtual environment.

That requirement was not semantic evidence.

A GitHub-hosted Python toolchain and the local shared project virtual
environment can both provide a valid interpreter, provided the characterization
records and compares:

```text
Python executable

Python version

Python implementation
```

across the orchestrator and A/B/C workers.

The virtual-environment requirement was therefore removed.

The distinction is:

```text
historical source availability
= real provenance dependency

virtual-environment presence
= accidental execution-environment coupling
```

The lesson is broader than CI:

```text
An evidence contract should require the facts needed to establish trust.

It should not require incidental properties of one developer environment.
```

---

## What Stage 4B.5 Establishes

Stage 4B.5 establishes the following chain:

```text
business correctness vocabulary
        ↓
stable rule identity
        ↓
executable predicate
        ↓
same-invocation typed violation evidence
        ↓
runtime decision carrier
        ↓
write-side propagation
        ↓
terminal SemanticOutcome + rule refinement
        ↓
future policy-consumable evidence
```

It does not establish:

```text
automatic retry

retry authorization

candidate regeneration

generic business-rule inference

all-rule runtime coverage

a universal business correctness protocol
```

The domain still owns its correctness propositions.

Compass provides the structure through which those propositions can become
machine-readable runtime evidence.

---

## Final Boundary

The reason Stage 4B.5 exists can be summarized as:

```text
A system should not require a machine consumer
to reverse-engineer business correctness
from FAILED, BLOCK, or free text.
```

Instead:

```text
the business domain defines stable correctness identities

the executable authority reports which identity failed

the runtime preserves that evidence without reinterpretation

shared semantic interpretation remains coarse

domain-specific refinement remains precise

later governance decides what action, if any, is authorized
```

That is the boundary Stage 4B.5 closes.
