# Reasoning Note: Conversation-Local History Retrieval and Progress Boundaries

[← Back to Reasoning Notes](README.md)

**Recorded on:** 2026-08-15

*Using a conversation-history observation to reason about partition-local retrieval, cursor semantics, progress evidence, and request amplification.*

**Status:** Architectural reasoning note / hypothesis
**Scope:** General history-oriented systems; not a claim about any vendor's internal implementation.

---

## Purpose

This note began from an observation about long conversation histories:

```text
open one conversation
→ recent content appears quickly
→ older content is loaded incrementally
```

and a separate failure pattern:

```text
scroll toward older history
→ requested region fails to appear
→ repeated activity appears to continue
→ terminal request-frequency error
```

The purpose is **not** to infer the actual storage, cache, frontend, or database architecture of any specific product.

The useful question is more general:

> How can a system expose a very large retained history without treating all history as one global traversal problem?

The central hypothesis is:

```text
global ownership
≠
global retrieval progress
```

A scalable history system can instead use:

```text
tenant / account
→ independently addressable local history
→ bounded incremental retrieval
```

---

## 1. Ownership Scope Is Not Traversal Scope

Consider an account containing many independent histories:

```text
Account
│
├── Conversation A
│   ├── Record A1
│   ├── Record A2
│   └── ...
│
├── Conversation B
│   ├── Record B1
│   └── ...
│
└── Conversation C
    └── ...
```

The account may define:

```text
ownership
authorization
billing
retention
tenant isolation
```

without also defining the unit of history traversal.

A more useful distinction is:

```text
account_id
= ownership namespace

conversation_id
= local history identity

message_id
= record identity

ordering coordinate
= local traversal order

cursor
= bounded retrieval progress
```

Opening Conversation A should not require reconstructing every record belonging to the account.

The important design rule is:

> **Partition retrieval by the natural owner of local history.**

---

## 2. Structural Analogy to Aggregate-Local Progress

Streaming System + Compass uses aggregate-local progress for a different semantic problem.

A simplified accepted-history model is:

```text
Accepted History
│
├── order_id = A
│   ├── sequence 1
│   ├── sequence 2
│   └── ...
│
├── order_id = B
│   ├── sequence 1
│   └── ...
│
└── ...
```

For an order-local projection, useful progress can be represented approximately as:

```text
projection identity
+
order_id
+
last processed local sequence
```

A conversation-history system may use a structurally similar decomposition:

```text
account
+
conversation_id
+
local traversal cursor
```

The analogy is intentionally limited.

```text
structural analogy
≠
semantic equivalence

order-local event sequence
≠
conversation message ordering
```

Compass accepted-event continuity may carry correctness meaning.

Conversation history may allow:

```text
deletion
branching
hidden records
moderation
retention gaps
```

without implying corruption.

The reusable idea is therefore not:

```text
chat history = event sourcing
```

It is:

> **Partition-local work should normally use partition-local progress.**

---

## 3. Ordering Does Not Automatically Mean Continuity

An ordering coordinate can establish:

```text
A before B
```

without proving:

```text
every coordinate between A and B must exist
```

This distinction matters when interpreting gaps.

For a strict domain event stream:

```text
sequence 10
sequence 12
```

may be correctness evidence if the contract requires exact-next progression.

For a user-facing history:

```text
message 10
message 12
```

may be completely legitimate if message 11 was deleted, hidden, or excluded.

Therefore:

```text
ordering
≠
continuity
```

and:

> **A gap is only an error when the domain contract says the gap is illegal.**

---

## 4. Cursor Is Not a Completeness Proof

A retrieval cursor can mean:

```text
continue reading before this record
```

or:

```text
continue reading after this record
```

That is a traversal contract.

It does not necessarily mean:

```text
everything before this point has been completely observed
```

The distinction is:

```text
cursor
= traversal position

completeness frontier
= proof about what has been fully processed
```

Those are different semantic strengths.

A history UI often needs only the first.

A projection or processing system may require the second.

Using one coordinate for both meanings without an explicit contract can create false completeness assumptions.

---

## 5. Progress Needs an Observable Witness

Incremental systems often operate through a repeated eligibility condition:

```text
more history requested?
→ fetch next page
```

After one attempt, something must establish whether progress occurred.

Possible progress witnesses include:

```text
cursor changed
loaded range expanded
requested page became materialized
terminal end-of-history marker appeared
explicit failure state was recorded
```

The dangerous state is:

```text
request still eligible
+
no observable progress
```

If the system automatically retries from that state, one logical user action can produce many physical requests.

A useful rule is:

> **After an automatic attempt, ask what changed.**

If nothing changed, repeated eligibility must be bounded.

---

## 6. Visible User Action Is Not Request Topology

A user may perform one visible action:

```text
scroll upward
```

while the system generates:

```text
pagination request
→ retry
→ cache miss recovery
→ artifact hydration
→ rerender-triggered request
→ another retry
```

Therefore:

```text
one visible action
≠
one network request
```

This matters when interpreting errors such as:

```text
too many requests
```

The terminal error does not prove that the user manually generated excessive requests.

It may instead reflect request amplification inside a feedback loop.

---

## 7. Candidate Request-Amplification Topology

One plausible generic failure shape is:

```text
viewport reaches pagination boundary
        ↓
request older local page
        ↓
fetch / parse / render fails to establish progress
        ↓
pagination condition remains eligible
        ↓
same or adjacent request is issued again
        ↓
retry amplification
        ↓
rate-limit or protection boundary
        ↓
terminal visible error
```

The first failure could occur at many places:

```text
backend latency
backend error
invalid cursor
client cache state
artifact hydration
render failure
observer loop
session throttling
```

The model therefore supports only:

```text
candidate causal topology
```

not:

```text
confirmed vendor root cause
```

---

## 8. Local Correctness Is Not Enough in a Feedback Loop

Each component may appear individually reasonable:

```text
viewport:
"more data is needed"

pagination:
"request the previous page"

retry:
"the request failed, try again"

renderer:
"data is still missing"
```

But their composition can create:

```text
missing state
→ request
→ failure
→ no progress
→ still missing
→ request again
```

Every local decision can look valid while the combined system amplifies work.

Therefore:

> **Local correctness is not enough when components form a feedback loop.**

Review must include:

```text
termination
progress
retry budget
deduplication
backoff
failure ownership
```

---

## 9. Cache Is Not Authority

History-oriented systems may contain several representations:

```text
durable history
        ↓
retrieval service
        ↓
server / edge cache
        ↓
client query state
        ↓
rendered viewport
```

These should not be collapsed into one semantic layer.

For example:

```text
viewport is blank
```

does not imply:

```text
durable history is missing
```

Likewise:

```text
cache contains record X
```

does not necessarily establish:

```text
record X is authoritative durable state
```

The reusable distinction is:

```text
durable history
≠
cache
≠
client materialization
≠
rendered presentation
```

---

## 10. Terminal Status Is Not Diagnosis

A terminal status such as:

```text
429
500
timeout
blank UI
```

describes an observable boundary.

It does not by itself identify the first failure.

For example:

```text
terminal outcome:
REQUEST_RATE_LIMITED
```

could coexist with:

```text
candidate diagnosis:
PAGINATION_PROGRESS_NOT_ADVANCING

candidate contributing evidence:
SAME_CURSOR_REQUESTED_REPEATEDLY
```

The exact vocabulary is system-specific.

The important rule is:

```text
surface outcome
≠
execution evidence
≠
diagnosis
```

This is the same reasoning discipline used elsewhere in Compass when separating technical status, semantic interpretation, evidence, and later governance.

---

## 11. Relationship to Compass

The connection to Compass is methodological rather than implementation-specific.

Both problems require asking:

```text
What owns local identity?

What does the ordering coordinate actually prove?

What counts as progress?

Are gaps legal?

Which representation is authoritative?

What evidence supports the final diagnosis?
```

The analogy stops where the semantic contracts diverge.

In Compass:

```text
accepted history
= authoritative business facts

aggregate-local sequence
= may carry strict correctness semantics

projection progress
= bounded processing evidence
```

In a conversation-history system:

```text
durable conversation history
= retained content source

message ordering
= traversal / presentation relation

cursor
= bounded retrieval progress
```

A conversation cursor should not inherit the semantic meaning of an accepted-event sequence merely because both are locally ordered coordinates.

---

## 12. Reusable Design Rules

### Rule 1 — Partition by the natural local history owner

If work is naturally conversation-local, include the conversation identity in the retrieval boundary.

### Rule 2 — Do not overload ordering coordinates

```text
ordering coordinate
≠
completeness proof
```

unless continuity is explicitly part of the contract.

### Rule 3 — Gaps require domain semantics

A missing coordinate is only an error if the domain says it must exist.

### Rule 4 — Progress requires evidence

After an automatic attempt:

```text
what changed?
```

must have a meaningful answer.

### Rule 5 — Bound duplicate work

One logical need should not create unlimited repeated work.

Possible mechanisms include:

```text
in-flight deduplication
bounded retry
backoff
terminal error state
explicit user retry
```

### Rule 6 — Cache is not authority

Keep durable history, cache, materialized client state, and rendered state conceptually separate.

### Rule 7 — Terminal symptoms are not root causes

Connect visible outcomes to execution evidence before assigning diagnosis.

### Rule 8 — Review feedback loops as systems

A set of locally reasonable components can still produce globally unsafe retry or request amplification.

---

## 13. General Architecture Pattern

The reusable model extends beyond chat:

```text
tenant
→ local history partition
→ bounded incremental read
→ observable progress
→ materialized client state
```

Possible examples include:

```text
support-ticket threads
email threads
workflow histories
audit timelines
agent-run histories
job logs
document revisions
order histories
activity feeds
```

For each system, ask:

```text
What is the local history identity?

What is the ordering relation?

What does the cursor mean?

Are gaps legal?

What proves progress?

How are duplicate requests suppressed?

What is durable?

What is cached?

What is merely rendered?
```

---

## Final Summary

The motivating observation leads to a broader architecture model:

```text
Account / Tenant
= ownership namespace

Local History
= independently addressable traversal boundary

Record
= item inside that history

Cursor
= bounded traversal progress

Cache
= optimization

Durable History
= retained source
```

The deeper reusable distinctions are:

```text
global storage
≠
global progress

ordering
≠
continuity

cursor
≠
completeness proof

visible action
≠
request topology

local correctness
≠
safe feedback-loop composition

terminal status
≠
diagnosis
```

The motivating conversation interface is only one example.

The reasoning applies more broadly to systems built around partitioned histories, incremental materialization, pagination, retries, and feedback-driven loading.
