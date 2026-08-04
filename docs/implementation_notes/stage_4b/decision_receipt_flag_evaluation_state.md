# DecisionReceipt Flag Evaluation State

[← Back to Stage 4B](README.md)

## Purpose

This Interlude defines the evaluation-state vocabulary for:

```text
DecisionReceiptFlags
```

It is a documentation-first refinement of the existing `DecisionReceipt`
governance-evidence contract.

The shared runtime contract and tests now implement this refinement.

---

## Problem

Before this Interlude, the shared contract stored four booleans:

```text
fallback_required: bool = False
rebuild_required: bool = False
operator_review_required: bool = False
retry_candidate: bool = False
```

That representation collapsed:

```text
evaluated and explicitly false
not evaluated
not provided
evaluation not completed
```

into the same durable value:

```text
False
```

The collapse was unsafe for governance evidence. A future consumer could not
tell whether a producer explicitly negated a condition or never completed an
evaluation for it.

The intended default must no longer be an implicit negative assertion.

---

## Chosen State Vocabulary

The shared contract uses one explicit portable enum:

```python
class DecisionReceiptFlagState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    NOT_EVALUATED = "NOT_EVALUATED"
```

Each field in `DecisionReceiptFlags` uses
`DecisionReceiptFlagState`.

The default for every field is:

```text
NOT_EVALUATED
```

The chosen vocabulary is:

```text
TRUE
FALSE
NOT_EVALUATED
```

`NOT_APPLICABLE` is not part of the current contract.

---

## Exact Durable Meaning

The states apply independently to the proposition named by each flag field.

### `TRUE`

```text
Evidence from the evaluation owner explicitly affirms the condition.
```

`TRUE` requires a completed evaluation supported by evidence that the producer
is authorized to interpret for that field.

It is not inferred from the absence of contrary evidence.

### `FALSE`

```text
The evaluation owner completed evaluation of the condition, and its evidence
explicitly negates the condition.
```

`FALSE` is an evidence assertion.

It must not mean:

```text
the field was omitted
the producer did not evaluate the condition
the producer lacked enough evidence
the generic mapper supplied a default
```

### `NOT_EVALUATED`

```text
The receipt contains no completed evaluation for the condition.
```

This state covers:

```text
the condition was not evaluated
no evaluation state was supplied
evaluation was not started
evaluation was incomplete
available evidence was insufficient to complete the evaluation
```

It does not assert that the condition is false.

The contract does not distinguish why evaluation was not completed. If a
future producer or consumer needs that explanation, it requires separately
defined evidence rather than another interpretation of `NOT_EVALUATED`.

---

## Meaning of the Flag Fields

The state vocabulary does not change the proposition represented by each
field:

```text
fallback_required
= whether the producer-supported evaluation affirms that fallback is required

rebuild_required
= whether the producer-supported evaluation affirms that rebuild is required

operator_review_required
= whether the producer-supported evaluation affirms that operator review is
   required

retry_candidate
= whether the producer-supported evaluation identifies the receipt as a
   candidate for later retry classification
```

For every field:

```text
TRUE
= explicit affirmation

FALSE
= completed explicit negation

NOT_EVALUATED
= no completed evaluation in this receipt
```

The field states remain evidence.

They do not execute fallback, rebuild, operator review, or retry.

In particular:

```text
rebuild_required = TRUE
≠ rebuild execution

retry_candidate = TRUE
≠ retry classification
≠ retry safety
≠ retry authorization
≠ retry execution
```

---

## Why `NOT_APPLICABLE` Is Not Justified

`NOT_APPLICABLE` would require a stable rule proving that a condition is outside
the scope of a particular receipt or producer.

No current `DecisionReceiptFlags` producer, consumer, invariant, or test makes
that distinction.

Current production code contains:

```text
the public DecisionReceiptFlagState enum and runtime-package export
the shared flag dataclass and strict enum validation
the PR3 pass-through/default boundary
no boolean convenience properties that collapse FALSE and NOT_EVALUATED
```

There are no producer-specific receipt flag adapters yet.

The repository does use `NOT_APPLICABLE` in a separate future retry
classification vocabulary for `intent_consistency`. That contract has a
specific meaning: some cases are not request or idempotency replay questions.
It does not establish an applicability rule for any `DecisionReceiptFlags`
field.

Therefore the present contract cannot durably distinguish:

```text
not applicable
```

from:

```text
no completed evaluation
```

without inventing producer-specific applicability semantics before PR4 and PR5
perform their audits.

For the current contract:

```text
no completed applicability-aware evaluation
→ NOT_EVALUATED
```

`NOT_APPLICABLE` may be reconsidered only when a concrete producer, consumer,
invariant, or test requires a distinct applicability assertion and defines who
owns it.

---

## Default and Omission

The default `DecisionReceiptFlags()` means:

```text
fallback_required = NOT_EVALUATED
rebuild_required = NOT_EVALUATED
operator_review_required = NOT_EVALUATED
retry_candidate = NOT_EVALUATED
```

At the construction boundary:

```text
omitted flags object
→ all fields NOT_EVALUATED

omitted individual flag state
→ that field NOT_EVALUATED
```

Omission must never become `FALSE`.

For a future durable representation, omission may be accepted as an input
default only when the contract version unambiguously defines it as
`NOT_EVALUATED`. Durable output should emit every flag field explicitly so
reviewers and non-Python consumers do not have to infer default behavior.

---

## Producer Ownership

Only the component that owns a completed, evidence-supported evaluation may
assert `TRUE` or `FALSE`.

For the planned Stage 4B adapters:

```text
PR4 write-side adapter
→ may construct states supported by write-side producer evidence

PR5 read-side / snapshot adapter
→ may construct states supported by read-side or snapshot producer evidence
```

A direct caller may supply `TRUE` or `FALSE` only when it is itself the
evaluation owner and can support that assertion with the receipt's selected
evidence.

An adapter must use `NOT_EVALUATED` when:

```text
it does not own the evaluation
its evidence does not complete the evaluation
its mapping table does not define the condition
```

PR4 and PR5 must define and test their concrete producer mappings separately.
This Interlude does not define those mapping tables.

---

## PR3 Generic Mapper Behavior

The PR3 generic mapper remains:

```text
pass-through only
```

It may:

```text
preserve an explicitly supplied DecisionReceiptFlags object
use the shared DecisionReceiptFlags default when flags are omitted
```

It must not derive any flag state from:

```text
ok
category
semantic_code
severity
risk_level
reversibility
boundary
technical_status
SemanticOutcome.context
SemanticOutcome.evidence
```

Under the refined shared contract:

```text
flags omitted at PR3 boundary
→ DecisionReceiptFlags()
→ all fields NOT_EVALUATED
```

PR3 does not assert `FALSE` by applying the default.

---

## Consumer Interpretation

Consumers must inspect the enum state explicitly.

They must not:

```text
coerce the state to bool
treat any non-TRUE state as FALSE
treat NOT_EVALUATED as proof that the condition is absent
derive authorization or execution directly from a flag
```

The required interpretation is:

```text
TRUE
→ explicit positive evidence is present

FALSE
→ explicit negative evidence is present

NOT_EVALUATED
→ no completed evaluation is present; the consumer must preserve uncertainty
```

Stage 4C and later policy layers may consume this evidence to choose policy.
Those layers must define their own safe behavior for `NOT_EVALUATED`; the
receipt contract does not supply a policy default.

The former boolean convenience properties:

```text
requires_operator_review
requires_rebuild
requires_fallback
```

were removed because they made `FALSE` and `NOT_EVALUATED` indistinguishable.
Callers inspect the enum state directly.

---

## Retry Boundary

`retry_candidate` remains preliminary governance evidence.

PR4 or PR5 may evaluate retry candidacy only when their producer evidence
supports that narrow assertion.

They do not own:

```text
retry class
intent consistency
retry safety
retry authorization
attempt policy
retry execution
```

Stage 4E alone owns retry classification and authorization.

Therefore:

```text
retry_candidate = TRUE
```

means only:

```text
this producer-supported evaluation identifies the receipt for later Stage 4E
retry consideration
```

It never means:

```text
retry_allowed = true
```

---

## JSON Representation

The durable JSON representation should use the exact enum strings:

```json
{
  "flags": {
    "fallback_required": "NOT_EVALUATED",
    "rebuild_required": "TRUE",
    "operator_review_required": "FALSE",
    "retry_candidate": "NOT_EVALUATED"
  }
}
```

JSON booleans and `null` must not represent flag evaluation state.

Using explicit strings preserves the distinction between:

```text
FALSE
NOT_EVALUATED
```

and avoids assigning an unstable meaning to `null`.

This defines the portable value shape only. Serialization implementation,
schema versioning, persistence, and migration SQL remain deferred.

---

## Java / Rust Portability

The string-backed enum maps directly to closed enum types in future runtimes.

Conceptually:

```text
Python
DecisionReceiptFlagState.TRUE

Java
DecisionReceiptFlagState.TRUE

Rust
DecisionReceiptFlagState::TRUE

JSON
"TRUE"
```

The exact uppercase tokens are language-neutral and do not depend on Python
truthiness or nullable-value behavior.

`bool | None` is not selected because `None` does not durably identify whether
the producer omitted the field, did not evaluate it, could not complete the
evaluation, or used a transport-level null. An explicit enum gives the shared
meaning a stable name across Python, Java, Rust, and JSON.

---

## Migration Impact on Existing Code and Tests

The shared runtime-contract migration is complete.

The implementation updated:

```text
DecisionReceiptFlags field types and defaults
flag-state runtime validation
runtime package export for DecisionReceiptFlagState
removal of boolean convenience properties
```

DecisionReceipt tests replaced:

```text
boolean construction and validation
all-false default expectations
boolean convenience-property expectations
```

with coverage for:

```text
the exact three-member enum
NOT_EVALUATED defaults for every field
explicit TRUE preservation
explicit FALSE preservation
rejection of bool, raw string, None, integer, and unsupported enum values
no bool coercion or state collapse
flags remain evidence rather than runtime actions
```

PR3 mapper tests prove:

```text
omitted flags become all NOT_EVALUATED
explicit mixed states pass through unchanged
semantic categories and codes still derive no flag state
```

No current producer-specific receipt tests require migration because PR4 and
PR5 have not started.

---

## Implementation Status

Complete.

`DecisionReceiptFlagState` is implemented and publicly exported.
`DecisionReceiptFlags` uses it for all four fields, defaults every field to
`NOT_EVALUATED`, and rejects legacy booleans, raw strings, `None`, integers,
and unrelated enum values.

`NOT_APPLICABLE` was not added.

The old boolean convenience properties were removed. PR3 remains unchanged and
pass-through-only.

Focused DecisionReceipt tests and the runtime unit suite passed:

```text
test_decision_receipt.py
→ 150 passed

test_decision_receipt_mapping.py
→ 21 passed

tests/unit/compass/runtime
→ 276 passed
```

The full repository suite was attempted:

```text
511 passed
84 skipped
197 PostgreSQL integration setup errors
```

The PostgreSQL integration tests could not start because `TEST_DATABASE_URL`
was unavailable.

---

## ADR Decision

A new ADR is not required.

ADR 0016 already establishes:

```text
DecisionReceipt
= durable governance evidence
≠ runtime decision or action
```

ADR 0017 reinforces that receipt evidence axes must remain explicit rather than
be inferred from overloaded values.

The three-state vocabulary is a narrow correction to the existing
`DecisionReceiptFlags` evidence representation. It does not change the
architectural ownership of evidence, policy, strategy, retry, or accepted
history.

---

## Explicit Non-goals

This Interlude does not design or implement:

```text
PR4 write-side mapping
PR5 read-side / snapshot mapping
flag derivation tables for concrete producers
runtime policy
retry classification or authorization
fallback execution
rebuild execution
operator-review execution
serialization code
database persistence
migration SQL
field-level identity provenance
schema versioning
```

It also does not add `NOT_APPLICABLE` or a separate classification-completeness
contract for theoretical completeness.

---

## Decision Summary

The shared contract is:

```text
DecisionReceiptFlagState
= TRUE | FALSE | NOT_EVALUATED

DecisionReceiptFlags default
= NOT_EVALUATED for every field

TRUE / FALSE
= completed producer-owned evaluation

NOT_EVALUATED
= no completed evaluation in the receipt

PR3
= explicit pass-through only

PR4 / PR5
= future producer-supported evaluation

Stage 4C+
= future policy consumption

Stage 4E
= retry classification and authorization
```

The Interlude is complete.

The next work is separate PR4 / PR5 read-only audits. Producer-specific flag
mapping tables remain deferred to those later scopes.
