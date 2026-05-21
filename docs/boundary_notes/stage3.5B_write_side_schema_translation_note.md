# Stage 3.5B Write-Side Schema Translation Note

[← Back to Boundary Notes Index](README.md)

## Purpose

This note translates the current Python-side write-side guarantees into database-side design requirements for **Stage 3.5B**.

It exists as the practical companion to the earlier postmortem:

- **From Git Local–Remote Drift to Database Immutability Boundaries**

That postmortem established the architectural lesson:

> Python-side guarantees do not automatically survive after data crosses into PostgreSQL.

This note continues from that realization and asks the next concrete question:

> If the current write-side semantics are already correct in Python, what must the database do so that durable persistence does not weaken them?

---

## 1. Current Python-Side Guarantees

Before persistence-backed write-side implementation, the current system already enforces several important guarantees in the Python layer.

### 1.1 Event immutability

Accepted event objects are treated as immutable facts.

In practice, this comes from:

- frozen dataclass semantics
- event creation through controlled domain paths
- no in-place mutation of accepted events

### 1.2 Append-only accepted history

The write-side currently behaves as an append-only accepted event log:

- candidate events are generated
- candidate events are validated
- admitted events are appended to history
- replay reconstructs state from accepted history
- old accepted events are not rewritten in place

### 1.3 Candidate / accepted identity boundary

The current design pre-allocates `OrderEvent.event_id` when an event-shaped candidate is created.

After ADR 0008, the interpretation is:

- before append, the value should be treated as `candidate_event_id`
- after successful append into accepted history, the same value may be referenced as `accepted_event_id`
- `event_id` alone does not imply accepted history
- event-log membership grants accepted-event status

This boundary must carry into the database schema.

For Stage 3.5B, the database representation should make this explicit:

- `order_events.accepted_event_id` uses PostgreSQL `UUID`
- `idempotency_records.accepted_event_id` references accepted history
- rejected candidates do not enter either accepted history or successful idempotency result records

The application remains responsible for event identity generation before append.

UUIDv7-compatible generation is the preferred future policy, but PR 1 only establishes the database UUID contract.

### 1.4 Idempotency distinction

The current system distinguishes:

- exact replay / same semantic request
- conflict / same request identifier but different semantic meaning

This means idempotency is not “duplicate request text.”

It is semantic identity.

### 1.5 Admission ordering and version consistency

The write-side already requires:

- expected version agreement
- stale-write rejection
- admitted history consistency
- replay-safe sequencing

### 1.6 Exact money semantics

Stage 3.5A completed migration from `float` to `Decimal`.

This means future persistence must preserve:

- exact money representation
- stable replay of money values
- stable idempotency / fingerprint basis
- no float-based ambiguity

---

## 2. The Stage 3.5B Problem

Stage 3.5B is not just:

- “add PostgreSQL”
- “save rows into a database”
- “replace in-memory stores with SQL tables”

The real problem is:

> how to preserve existing write-side semantic guarantees after crossing from Python memory into a durable storage process

That means database design must not merely store data.

It must help preserve:

- append-only event truth
- no rewrite of accepted history
- exact money storage
- stable stream identity
- candidate / accepted event identity distinction
- event format evolution
- separation between payload, proof, and runtime metadata
- transactional coupling between event append and idempotency record write

---

## 3. Translation Principle

For each Python-side guarantee, Stage 3.5B must ask:

1. what is the current guarantee?
2. where is it enforced today?
3. what database-side mechanism can restate it physically?
4. what remains application responsibility even after database constraints exist?

This note uses that translation method.

---

## 4. Python-to-Database Translation Table

| Python-side semantic guarantee | Database-side translation goal |
|---|---|
| `frozen=True` accepted event object | accepted event row should not be updated after insertion |
| append-only accepted event history | event table should allow insert growth, not in-place rewrite of old accepted rows |
| candidate vs accepted event identity | persisted event table should use accepted-history naming such as `accepted_event_id` |
| UUID-compatible event identity | `accepted_event_id` should use PostgreSQL `UUID`, while generation remains application-owned |
| event format evolution | `event_schema_version` should identify durable event format version |
| domain payload vs proof vs metadata separation | use `payload_json`, `proof_json`, and `metadata_json` separately |
| domain occurrence time vs DB append time | use `occurred_at_ms` and `appended_at` separately |
| stream identity by order + sequence | durable identity such as `(order_id, sequence)` must be protected |
| replay from accepted history | ordered reads must reconstruct history deterministically |
| Decimal money semantics | exact durable numeric representation must be used |
| idempotency replay vs conflict distinction | idempotency table must preserve enough semantic identity to detect conflict |
| version-consistent admission | append must happen under explicit transactional and concurrency conditions |

This table defines the schema thinking for Stage 3.5B.

---

## 5. Event Table: What It Must Preserve

The durable event table is the most important write-side table.

It should preserve the same meaning currently carried by the in-memory accepted-history log.

### 5.1 Minimum role

The event table must be the durable representation of:

- admitted events only
- append-only accepted history
- replayable event stream for one order

### 5.2 Minimum required properties

The event table must support:

- one row per accepted event
- stable event ordering per order
- deterministic replay by sequence
- durable storage of exact event facts
- durable storage of proof / metadata needed by the chosen write-side model
- durable distinction between accepted history and rejected candidate events
- durable event format evolution through `event_schema_version`

### 5.3 Important non-goal

The event table should not become:

- a mutable current-state table
- a place where accepted history is edited retroactively
- a hidden compensation mechanism through row mutation
- an audit table for rejected candidates

If past accepted history must change, that should happen through new events or controlled migration strategy, not casual row rewrite.

---

## 6. Durable Analogue of `frozen=True`

In Python, `frozen=True` protects event objects from in-place mutation.

In PostgreSQL, no direct equivalent exists automatically.

So Stage 3.5B must approximate the same meaning through physical controls.

### 6.1 Primary expectation

For accepted event rows, the runtime write-side application path should normally behave as if it only has:

- `SELECT`
- `INSERT`

and should normally not rely on:

- `UPDATE`
- `DELETE`

### 6.2 Why permissions matter

If runtime code can freely update accepted event rows, then the event log stops being append-only history and becomes a mutable table of convenience.

That would violate the write-side model.

### 6.3 Why permissions should not be first

Permission restriction is not the whole story.

The first Stage 3.5B baseline should prioritize:

- schema shape
- repository API
- transaction semantics
- tests

A concrete runtime DB role / privilege model can be implemented as a later hardening step after the minimal durable loop works.

This avoids making early database setup harder before the basic persistence semantics are proven.

### 6.4 Combined durable analogue

The durable analogue of `frozen=True` is not one feature.

It is a combination of:

- append-only application discipline
- durable stream identity constraints
- exact storage representation
- transaction boundary
- tests
- later permission hardening
- optional trigger-based immutability hardening

---

## 7. Append-Only Event History in Database Terms

Append-only should be defined more strictly than “I usually only insert.”

For this project, append-only means:

- new admitted events are inserted as new rows
- previously accepted event rows are not updated
- previously accepted event rows are not deleted by runtime paths
- sequence identity cannot be overwritten
- history is replayed by ordered read, not by mutable current-state replacement

### 7.1 Practical implication

The write-side schema should make it awkward or impossible for ordinary runtime code to treat accepted history as mutable business state.

That is the database continuation of the earlier in-memory design.

---

## 8. Stream Identity and Sequence Protection

The in-memory model already assumes:

- one stream per order
- one sequence number per event within that stream
- deterministic replay in sequence order

Stage 3.5B must make that physically true.

### 8.1 Durable identity

At minimum, the schema should enforce a durable uniqueness boundary such as:

- `(order_id, sequence)`

This prevents two different accepted rows from occupying the same logical event slot.

### 8.2 Why this matters

Without durable stream identity:

- replay becomes ambiguous
- append-only shape becomes unstable
- duplicate or overwritten sequence slots could corrupt accepted history

### 8.3 Relation to event identity

A globally unique `accepted_event_id` is still useful.

For Stage 3.5B, it should use PostgreSQL `UUID`.

But `accepted_event_id` alone is not enough to preserve stream ordering semantics.

The write-side model cares not only that an event exists, but also that it occupies the correct place in one stream.

---

## 9. Money Storage Requirements

Stage 3.5A already established exact money semantics in Python.

Stage 3.5B must preserve that work durably.

### 9.1 Durable goal

The database must store money-like values in exact form.

This means avoiding float / approximate numeric representations.

### 9.2 Practical schema implication

The storage strategy should use an exact representation such as:

- SQL `NUMERIC(...)`
- exact canonical decimal strings when constructing semantic fingerprints
- exact string representation when embedded in structured JSON payloads

### 9.3 Why this matters

If persistence reintroduces float approximation, then Stage 3.5A’s Decimal migration would be partially undone at the storage boundary.

That would damage:

- replay stability
- idempotency comparison
- fingerprint reproducibility
- eventual read-side correctness

---

## 10. Event Payload vs Hard Columns

A key Stage 3.5B schema question is:

> Which event facts should be hard columns, and which should remain in payload?

This note clarifies the decision principle.

### 10.1 Hard columns are justified when

A field is needed for:

- stream identity
- replay ordering
- filtering / debugging / operational visibility
- stable write-side safety queries
- stable future durability semantics
- foreign-key or uniqueness constraints

### 10.2 Payload is justified when

A field is:

- auxiliary event detail
- not part of stream identity
- not needed for durable write-side safety queries
- mainly part of the event fact body rather than enforcement boundary

### 10.3 Likely hard-column candidates

For the event table, likely hard columns include:

- `accepted_event_id`
- `event_schema_version`
- `order_id`
- `sequence`
- `event_type`
- `request_id`
- `amount`
- `occurred_at_ms`
- proof predecessor fields needed for traceability
- `appended_at`

This should be finalized in the schema draft.

---

## 11. Payload, Proof, and Metadata Separation

Stage 3.5B should preserve three different JSON extension surfaces:

| Column | Meaning |
|---|---|
| `payload_json` | Domain event payload details |
| `proof_json` | Compass proof / validation provenance details |
| `metadata_json` | Runtime metadata such as source, actor, trace id, correlation id, or writer component |

This separation prevents general runtime metadata from being mixed into domain payload or validation proof.

`metadata_json` is also the future container for write-side observability metadata.

Future uses may include:

- Compass validation timing
- registry-stage timing
- validator identity
- validation mode
- runtime trace/debug metadata

These fields are not part of domain truth or proof truth.

They support debugging, audit, and future performance analysis.

---

## 12. Idempotency Table: Why It Must Be Written Together

The write-side does not only persist accepted events.

It also persists idempotency decisions.

This creates one of the most important Stage 3.5B requirements:

> accepted event append and idempotency record write must be transactionally coordinated

### 12.1 Why

If an event row is written but the idempotency record is not, then the system may later mis-handle a retry.

If an idempotency record is written but the event row is not, then the system may later incorrectly believe that an admitted event already exists.

So these two writes must not drift apart.

### 12.2 Meaning of “same transaction”

For this stage, “same transaction” means:

- both durable writes succeed together
- or both fail together
- the database does not commit one without the other

This is one of the central semantics of Stage 3.5B.

---

## 13. Concurrency Boundary Still Exists

Introducing a database does not remove the need for explicit concurrency thinking.

The current write-side already distinguishes:

- semantic validation
- idempotency logic
- version consistency / stale-write rejection

Stage 3.5B should preserve that conceptual separation.

### 13.1 What the database can help with

The database can help with:

- durable uniqueness boundaries
- transaction atomicity
- conditional insert logic
- row-level persistence semantics
- foreign-key integrity

### 13.2 What still remains an application concern

The application still owns:

- candidate-event creation
- semantic validation
- proof evaluation
- admission orchestration
- meaning of stale write vs semantic conflict
- idempotency replay / conflict classification
- event identity generation

The database strengthens the physical boundary.

It does not replace domain meaning.

---

## 14. Minimum Stage 3.5B Schema Questions To Answer

Before implementation, the following questions should be answered explicitly.

### Event history table

- what is the durable primary identity?
- what ordering key defines replay truth?
- which columns are hard columns vs payload?
- how is exact money stored?
- what columns are required for debugging / operational visibility?
- what does the table name communicate about domain scope?
- how should event format evolution be represented?
- how should domain payload, proof, and runtime metadata remain separate?

### Idempotency table

- what uniquely identifies a request at the durable boundary?
- what semantic identity must be stored so replay vs conflict can still be distinguished?
- what result metadata must be durably recoverable?
- should conflicts be persisted now or only detected?

### Permissions

- what runtime DB role should eventually be allowed to do?
- should runtime role be insert/select only for accepted history?
- who, if anyone, can update or delete historical rows?
- should permission hardening be implemented now or after the durable loop is proven?

### Transactions

- how are event append and idempotency write committed together?
- what happens under conflict or stale-write rejection?
- what happens if DB write partially fails?
- where does the transaction boundary live in Python?

---

## 15. Recommended Stage 3.5B Implementation Order

The implementation order should remain conservative.

### Step 1: Schema translation draft

Write down the event table and idempotency table shape before writing repository code.

### Step 2: Permission / append-only policy definition

Clarify what the runtime role can and cannot do.

At this stage, permission policy may be documented before it is fully enforced in PostgreSQL roles.

### Step 3: SQL migration draft

Create the first executable schema anchor for `order_events` and `idempotency_records`.

### Step 4: Transaction design

Define exactly how durable event append and idempotency write happen together.

### Step 5: Repository / store implementation

Only after the schema and transaction semantics are clear should code be written.

### Step 6: Replay verification

Confirm that persistence-backed history still replays correctly and deterministically.

This protects the project from drifting into “database code first, semantics later.”

---

## 16. Proposed Boundary Rule For Stage 3.5B

A useful working rule is:

> Python still owns meaning.  
> PostgreSQL must durably defend the shape of accepted truth.

This means:

### Python owns

- event meaning
- proof meaning
- semantic validation
- candidate-event construction
- admission orchestration
- idempotency classification
- event identity generation

### PostgreSQL must defend

- append-only accepted history shape
- no accidental rewrite of admitted facts
- exact money storage
- durable stream identity
- durable event identity type
- event schema version
- transaction coupling of event append + idempotency write
- foreign-key linkage between idempotency records and accepted events

This is the correct split of responsibility.

---

## 17. Durable Event Identity Policy

The database stores accepted event identity as PostgreSQL `UUID`.

The application remains responsible for generating event identity before append.

This matters because the system already has a candidate / accepted lifecycle:

```text
candidate_event_id before append
accepted_event_id after append
```

If the database generated event identity only after insertion, the candidate identity would be harder to trace before admission.

Preferred future policy:

```text
application-generated UUIDv7-compatible event IDs
```

Stage 3.5B PR 1 does not need to implement the Python UUID generator.

It only defines the durable database shape that later storage code must follow.

---

## 18. Future Production Hardening

The following concerns are intentionally deferred from the Stage 3.5B minimal baseline:

- append-only trigger to block `UPDATE` / `DELETE` on `order_events`
- production DB roles with stricter runtime privileges
- table partitioning
- `tx_id` / WAL investigation support
- idempotency conflict audit table
- distributed ordering / HLC research

These are valid production concerns.

They are not required for the first durable write-side loop.

Deferring them keeps Stage 3.5B focused on the minimal durable baseline.

---

## 19. Final Design Intuition

The database should not be treated as a passive bucket.

It is the first physical environment outside the Python process that must be taught the rules of:

- immutability
- append-only truth
- exact numeric storage
- UUID-compatible accepted event identity
- event format versioning
- replay-safe history
- coupled durability of event + idempotency result

If those are not restated explicitly, then the move to persistence weakens the system.

If they are restated correctly, Stage 3.5B becomes the natural continuation of the existing write-side semantics rather than a semantic regression.

---

## 20. Suggested Immediate Next Deliverables

The next concrete artifacts should likely be:

1. architecture note for `order_events` and `idempotency_records`
2. boundary note for Python-to-database semantic translation
3. SQL migration draft
4. transaction sequence note for append + idempotency write
5. runtime role / privilege policy draft

The first Stage 3.5B PR may include the first, second, and third items.

The transaction sequence and privilege enforcement can be refined in follow-up work.

---

## Closing Rule

The most important reminder for Stage 3.5B is:

> Do not assume the database already knows Python’s rules.

If the write-side currently depends on:

- frozen event facts
- append-only accepted history
- exact money values
- deterministic replayable streams
- request-level idempotency semantics
- candidate / accepted event identity

then those guarantees must now be translated into:

- database constraints
- database permissions
- transaction boundaries
- schema design

That is the real work of Stage 3.5B.
