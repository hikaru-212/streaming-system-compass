# Postmortem: When Individually Valid Fields Admit Invalid Semantic Objects

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-08-13

---

## 1. Purpose

This note records a representation-level correction discovered during Stage 4B.5 while defining the Order Correctness Contract.

The issue was not that the generated code was syntactically invalid.

It was not that the contract lacked types, immutability, tests, or structural validation.

The issue was subtler:

```text
Each field in CorrectnessRule could be individually valid,
while the composed CorrectnessRule object could still be semantically invalid.
```

The original representation allowed callers to independently provide:

```text
rule_id
semantic_proposition
category
subject
```

Each field was typed and locally valid, but the type system did not express the dependency:

```text
rule_id
→ {semantic_proposition, category, subject}
```

This meant the implementation admitted a much larger representable state space than the intended semantic model.

For example, a CREATE command legality rule could theoretically be paired with a transition-truth category or a predecessor-claim subject even though those combinations had no valid domain meaning.

The corrected direction is:

```text
stable rule identity
→ one authoritative semantic definition
```

rather than:

```text
independently supplied typed fields
→ canonical tests later confirm that selected tuples happen to be valid
```

This distinction matters in AI-assisted engineering because generated code can be locally well-formed, strongly typed, immutable, and well-tested while still exposing a representation that permits semantically nonsensical objects.

The reusable lesson is:

```text
Type-safe fields do not imply a semantically valid product space.
```

Or, in the language of this project:

```text
A field may be individually admissible,
while the composed object is not.
```

---

## 2. Context

Stage 4B.5 introduces a machine-readable Order Correctness Contract.

Its purpose is not to execute business logic.

Its purpose is to give stable identity to correctness boundaries so that a later runtime or agent-facing consumer can answer:

```text
Which correctness rule was violated?
```

without inferring semantics from:

```text
free-text reasons
coarse validation outcomes
technical statuses
implementation-specific branch names
```

The Stage 4B.5 V0 contract therefore defines:

```text
stable rule identities
correctness categories
rule subjects
allowed transition topology
amount constraints
shared declarative parameters
```

The contract remains:

```text
declarative specification
!= runtime evaluator
```

The initial PR2 representation used immutable typed records and canonical tests to freeze the approved V0 surface.

At first glance, this was strong enough.

The contract had:

```text
frozen dataclasses
typed enums
explicit rule IDs
typed categories
typed subjects
non-empty semantic propositions
immutable collections
duplicate protection
reference coherence
canonical exactness tests
```

The approved V0 also had a source-grounded set of 18 stable rules.

The problem only became visible after asking a different question:

```text
What objects does this representation allow us to construct?
```

---

## 3. Original Representation

The original `CorrectnessRule` concept had four independent fields:

```python
@dataclass(frozen=True)
class CorrectnessRule:
    rule_id: OrderCorrectnessRuleId
    semantic_proposition: str
    category: CorrectnessCategory
    subject: RuleSubject
```

Conceptually, a caller could provide:

```text
RuleId
×
Semantic Proposition
×
Correctness Category
×
Rule Subject
```

The constructor validated each component locally.

For example:

```text
rule_id
must be an OrderCorrectnessRuleId

category
must be a CorrectnessCategory

subject
must be a RuleSubject

semantic_proposition
must be a valid non-empty string
```

This made every field individually constrained.

However, there was no construction-time invariant saying:

```text
this specific rule_id
must use this specific category
and this specific subject
and this specific proposition
```

The canonical V0 instance and its tests selected the intended tuples correctly.

But the general `CorrectnessRule` representation still admitted invalid combinations.

---

## 4. Why the Original Design Looked Correct

The original design was not careless.

It was attractive for several legitimate reasons.

### 4.1 Strong local typing

The design prevented obvious mistakes such as:

```text
category = "random string"
subject = 123
rule_id = arbitrary text
```

### 4.2 Immutability

A created rule could not be casually mutated later.

This prevented a different class of corruption:

```text
valid rule
→ mutate category
→ silently change meaning
```

### 4.3 Canonical exactness tests

The V0 tests froze:

```text
exact rule count
exact rule IDs
exact category associations
exact subject associations
exact allowed graph
exact amount constraints
```

The selected canonical contract therefore had strong executable evidence.

### 4.4 Generic contract evolution remained possible

The generic `OrderCorrectnessContract` type was not hard-coded to one exact V0 instance.

A future contract edition could select a different subset or introduce new known identities without redefining the entire structural container.

All of these were useful properties.

The flaw was not local implementation quality.

The flaw was the representable semantic state space.

---

## 5. The Question That Exposed the Problem

The issue became visible while reviewing `CorrectnessRule` as a mathematical object rather than only as a Python dataclass.

The key question was:

```text
If this class has four independently supplied fields,
what prevents arbitrary combinations of those fields?
```

The original answer was:

```text
canonical V0 tests prevent the approved 18 rules from being misconfigured
```

That answer was useful but incomplete.

It protected:

```text
the selected V0 tuples
```

It did not protect:

```text
the general construction space
```

A more precise question was then asked:

```text
If rule_id is CREATE-related,
can a caller still pair it with a completely unrelated subject or category?
```

Under the original representation, the answer was:

```text
Yes, as long as every field is individually type-valid.
```

That was the hidden mismatch.

---

## 6. Hidden Cartesian Product

The original representation can be viewed mathematically as a product space.

Let:

```text
I = set of rule IDs
P = set of admissible semantic proposition strings
C = set of correctness categories
S = set of rule subjects
```

Then the structural type roughly admits values from:

```text
I × P × C × S
```

The intended semantic model does not.

The intended model contains only a very small relation:

```text
R ⊂ I × P × C × S
```

For the canonical V0:

```text
|R| = 18
```

The important observation is:

```text
The contract does not mean that every valid RuleId
may be freely paired with every valid Category,
every valid Subject,
and every valid Proposition.
```

The intended dependency is:

```text
rule_id
→ {semantic_proposition, category, subject}
```

That is a functional dependency.

Once the stable rule identity is known, the rest of the semantic metadata is not independent input.

It is part of that identity's meaning.

---

## 7. Example of a Type-Safe but Semantically Invalid Rule

Consider a hypothetical object:

```python
CorrectnessRule(
    rule_id=OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT,
    semantic_proposition="A candidate predecessor claim must match accepted history.",
    category=CorrectnessCategory.TRANSITION_TRUTH,
    subject=RuleSubject.PREDECESSOR_CLAIM,
)
```

Every field is locally valid:

```text
CREATE_ALLOWED_FROM_INIT
is a valid RuleId

the proposition
is a valid string

TRANSITION_TRUTH
is a valid category

PREDECESSOR_CLAIM
is a valid subject
```

But the combination is semantically incoherent.

The rule identity says:

```text
CREATE command legality
```

while the dependent metadata says:

```text
accepted-history transition truth
about a predecessor claim
```

This is not merely a bad label.

It is an invalid semantic object.

The important failure mode is:

```text
all fields pass local validation
while the composed meaning is garbage
```

---

## 8. Why Canonical Tests Were Not Enough

The existing tests were strong at proving:

```text
the canonical V0 contains exactly the reviewed 18 rules

each reviewed rule currently has the expected category

each reviewed rule currently has the expected subject

the allowed graph is exact

the amount constraints are exact

references resolve coherently
```

Those tests were valuable.

They proved:

```text
the selected V0 instances are correct
```

But they did not prove:

```text
invalid semantic instances are unrepresentable
```

This distinction is important.

A test can confirm:

```text
we constructed the right objects
```

without confirming:

```text
the representation prevents us from constructing the wrong objects
```

The reusable lesson is:

```text
Tests can prove that chosen instances are correct
without proving that the model excludes invalid instances.
```

The deeper question is:

```text
Does the representation expose degrees of freedom
that the domain model says should not exist?
```

---

## 9. Corrected Invariant

The corrected invariant is:

```text
Stable rule identity determines stable semantic meaning.
```

Formally:

```text
rule_id
→ {semantic_proposition, category, subject}
```

The design therefore changes from:

```text
caller independently supplies four typed fields
```

to:

```text
caller selects one stable rule identity
→ authoritative definition supplies the dependent metadata
```

This makes the model closer to a function:

```text
f(rule_id)
=
(semantic_proposition, category, subject)
```

rather than an unconstrained Cartesian product.

The semantic state space is reduced intentionally.

---

## 10. Corrected Representation

The corrected direction introduces one authoritative rule-definition registry.

Conceptually:

```text
OrderCorrectnessRuleId
        ↓
authoritative rule-definition registry
        ↓
semantic_proposition
category
subject
```

A rule definition may be represented by a private immutable record such as:

```python
@dataclass(frozen=True)
class _RuleDefinition:
    semantic_proposition: str
    category: CorrectnessCategory
    subject: RuleSubject
```

The registry then defines exactly one semantic meaning for each known stable rule identity:

```python
_RULE_DEFINITIONS = {
    OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT: _RuleDefinition(
        semantic_proposition="...",
        category=CorrectnessCategory.COMMAND_LEGALITY,
        subject=RuleSubject.AGGREGATE_COMMAND,
    ),
    ...
}
```

The public construction path becomes rule-ID driven:

```python
CorrectnessRule.from_rule_id(
    OrderCorrectnessRuleId.CREATE_ALLOWED_FROM_INIT
)
```

The caller no longer independently chooses:

```text
semantic_proposition
category
subject
```

Those values are derived from the authoritative rule definition.

---

## 11. Single Authority Requirement

The registry must not create a second copy of the same semantic metadata.

The wrong shape would be:

```text
RULE_DEFINITIONS
contains the metadata once

and

ORDER_CORRECTNESS_CONTRACT_V0
manually repeats the same metadata again
```

That would create dual authority.

The corrected hierarchy is:

```text
OrderCorrectnessRuleId
        ↓
authoritative definitions
        ↓
V0 selects rule IDs
        ↓
CorrectnessRule values are materialized
```

The responsibilities are therefore separated:

```text
Rule ID
= stable identity

Rule definition registry
= stable meaning of that identity

V0 rule selection
= which identities belong to contract version 0

OrderCorrectnessContract
= immutable materialized edition
```

---

## 12. Versioning Boundary

The stronger invariant does not mean every future rule must retroactively belong to V0.

These are separate sets:

```text
known stable rule identities
!=
rules selected by contract version 0
```

A future rule may be introduced as:

```text
OrderCorrectnessRuleId.NEW_RULE
```

with one corresponding authoritative definition.

A later V1 contract may select it.

V0 does not automatically change.

The intended model remains:

```text
registry
= meaning of known identities

edition
= selected identities for that version
```

This preserves contract-version evolution without reopening arbitrary metadata composition.

---

## 13. Why This Matters in AI-Assisted Engineering

This issue is especially relevant when code is produced with AI assistance.

AI systems are often strong at generating code that is:

```text
plausible
typed
immutable
well-factored
locally defensive
well-tested
```

That can make a representation look finished.

However, a locally strong implementation can still encode too much semantic freedom.

The hidden review question is not:

```text
Does this code run?
```

It is not even:

```text
Are the current tests green?
```

It is:

```text
What invalid meanings can this representation still express?
```

This matters because AI-generated systems can propagate locally valid but globally nonsensical structures very efficiently.

A downstream component may receive an object whose fields are individually well-typed and then be forced to reason about whether the combination makes sense.

That creates unnecessary cognitive and governance load.

Instead of allowing:

```text
producer creates ambiguous semantic tuple
→ consumer re-checks coherence
→ later consumer re-checks again
```

the preferred model is:

```text
construction boundary enforces semantic dependency
→ downstream consumers receive a narrower trusted representation
```

The principle is:

```text
Do not make every downstream reader rediscover
which combinations were supposed to be legal.
```

---

## 14. Cognitive Load as a Correctness Concern

This correction was not motivated only by mathematical elegance.

It was also motivated by reviewability.

If the representation admits nonsense such as:

```text
CREATE rule
+
TRANSITION_TRUTH
+
PREDECESSOR_CLAIM
```

then every reader must mentally ask:

```text
Is this tuple actually meaningful?
```

That question should not be repeatedly delegated downstream.

A good contract should reduce the number of interpretations a reader must consider.

The design goal therefore becomes:

```text
reduce representable semantic ambiguity
```

not merely:

```text
reject syntactically invalid values
```

In this sense, unnecessary representable states are themselves a form of cognitive debt.

This is particularly important in an AI-assisted codebase where future agents may consume the same types mechanically.

A machine should not be asked to infer a dependency that the schema already knows.

---

## 15. Why This Is Not Simply an AI Failure

The correct conclusion is not:

```text
AI generated bad code.
```

The original code was useful.

It established:

```text
stable rule IDs
typed categories
typed subjects
immutability
canonical exactness
structural coherence
```

The failure mode was narrower:

```text
the implementation modeled every field independently
even though the domain semantics made some fields functionally dependent
```

This issue could also occur in human-written code.

The AI-assisted aspect matters because plausible code can be generated faster than semantic assumptions are challenged.

The human review therefore still needs to ask questions such as:

```text
Which fields are actually independent?

Which fields are derived?

Which combinations are meaningful?

Which combinations should be impossible?

What is the smallest valid representable state space?
```

The lesson is not:

```text
do not use AI
```

The lesson is:

```text
AI-generated representations need semantic state-space review.
```

---

## 16. Prompting Lesson

This discovery also highlights a limit of trying to specify every invariant in the initial AI prompt.

It would be possible to ask:

```text
Ensure that rule_id functionally determines category,
subject, and semantic proposition,
and do not expose an API that permits arbitrary cross-product composition.
```

But that instruction requires the reviewer to already know that this is the relevant failure mode.

In this case, the invariant became visible only after reviewing the generated representation.

The practical workflow is therefore iterative:

```text
AI proposes a representation
        ↓
implementation review
        ↓
semantic state-space review
        ↓
human challenges hidden degrees of freedom
        ↓
representation is tightened
        ↓
tests freeze the corrected invariant
```

The objective is not to produce a perfect first prompt.

The objective is to maintain a strong semantic admission boundary before a representation is frozen.

---

## 17. Reusable Review Heuristic

When reviewing an AI-assisted dataclass, DTO, contract, enum bundle, or schema, ask:

```text
1. Which fields are genuinely independent?

2. Which fields are functionally determined by another field?

3. If every field is individually valid, can their combination still be nonsense?

4. Does the constructor expose more degrees of freedom than the domain model actually has?

5. Is an identity field being treated as only a label even though it should determine meaning?

6. Are canonical tests merely proving that current examples are correct?

7. Can a caller still construct an invalid semantic object outside those examples?

8. Can the invalid state be removed from the normal construction API?

9. Is there one authoritative source of semantic mapping?

10. Would downstream consumers otherwise need to repeatedly re-check the same relationship?
```

If the answer to several of these questions is unclear, the model may expose an unnecessarily large semantic state space.

---

## 18. Design Principle: Make Invalid Semantic States Unrepresentable

The correction follows a familiar design principle:

```text
Make illegal states unrepresentable.
```

In Python, absolute impossibility is not always enforceable in the same way as in a more restrictive type system.

However, the normal supported API can still be designed so that:

```text
semantically invalid combinations
cannot be constructed through ordinary use
```

This is stronger than:

```text
invalid combinations are possible,
but tests remind maintainers not to create them
```

The distinction is especially important for long-lived contract types.

---

## 19. Relation to Compass

This issue mirrors a broader Compass theme.

Compass repeatedly separates:

```text
structured input
from
admitted semantic truth
```

The same distinction applies inside the correctness contract.

A `CorrectnessRule` can be:

```text
typed
immutable
structurally valid
```

and still not be semantically admissible if its fields describe incompatible meanings.

The contract itself therefore needs an admission boundary.

The corrected representation says:

```text
stable rule identity
is not merely one field among several

it is the authority for the rule's semantic definition
```

This is a smaller instance of the same principle used elsewhere in the project:

```text
shared structure
does not imply shared authority

typed values
do not imply valid composition

available combinations
do not imply admissible meanings
```

---

## 20. Testing Direction After the Correction

After the representation change, tests should protect the stronger invariant.

The important tests are no longer only:

```text
V0 has exactly 18 rules

the 18 current category associations are correct

the 18 current subject associations are correct
```

They should also prove:

```text
every known RuleId has exactly one authoritative definition

the registry and RuleId vocabulary are exactly aligned

public CorrectnessRule construction is rule-ID driven

dependent metadata cannot be independently supplied through the normal API

V0 selects identities rather than manually repeating their metadata

V0 materialized rules match the authoritative definitions

generic contracts may select valid subsets

future known identities do not automatically enter V0
```

The difference is:

```text
before:
tests protected selected instances

after:
representation + tests protect the dependency itself
```

---

## 21. Non-Goals

This correction does not introduce a rule engine.

It does not make the declarative contract executable.

It does not change:

```text
OrderAggregate command behavior
Money normalization behavior
candidate construction behavior
trusted event application
FullProofValidator semantics
admission
idempotency
SemanticOutcome
DecisionReceipt
retry policy
recovery strategy
projection behavior
database persistence
```

The authoritative registry defines:

```text
what a stable rule identity means
```

It does not define:

```text
how runtime code evaluates that rule
```

Executable-authority parity remains a separate concern.

---

## 22. Before / After

### Before

```text
CorrectnessRule(
    rule_id,
    semantic_proposition,
    category,
    subject,
)

caller controls all four fields
```

Protection:

```text
field-level typing
+
canonical V0 tests
```

Failure mode:

```text
type-safe but semantically nonsensical tuples remain representable
```

### After

```text
CorrectnessRule.from_rule_id(rule_id)
```

with:

```text
rule_id
→ authoritative definition
→ proposition/category/subject
```

Protection:

```text
controlled construction
+
single semantic authority
+
registry completeness tests
+
canonical edition tests
```

Result:

```text
the normal construction path no longer exposes
semantic degrees of freedom that the domain does not have
```

---

## 23. Final Decision

Stage 4B.5 PR2 should use an authoritative rule-definition registry.

The stable dependency is:

```text
rule_id
→ {semantic_proposition, category, subject}
```

The registry defines the unique semantic meaning of each known rule identity.

A contract edition selects rule IDs.

The corresponding `CorrectnessRule` objects are materialized from that registry.

The normal public construction path must not invite independent composition of:

```text
rule_id
semantic_proposition
category
subject
```

The existing V0 rule count remains:

```text
18
```

The approved rule meanings remain unchanged.

The change is representational:

```text
from
correct examples inside a permissive model

to
a model whose normal construction path expresses the intended dependency
```

The final lesson is:

```text
A typed object can still expose an invalid semantic state space.
```

A stronger version is:

```text
Do not only validate the values inside a model.

Validate whether the model should permit those combinations at all.
```

And, for AI-assisted engineering:

```text
Generated code may be correct enough to compile,
typed enough to look safe,
and tested enough to look finished,

while still allowing meanings that should never have been representable.
```
