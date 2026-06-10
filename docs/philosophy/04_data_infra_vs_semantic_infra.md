# Future Architecture Philosophy: Separating Data Infrastructure from Semantic Infrastructure

[← Back to Philosophy Index](README.md)

## 1. Why This Note Exists

This project started from a practical engineering question:

```text
How can a system preserve correctness under failure?
```

At first, the answer seemed to be about durable persistence, transaction boundaries, idempotency, concurrency admission, projection replay, and checkpoint progress.

These are important.

However, as the project evolved, a deeper architectural pattern became visible:

```text
physical correctness
does not automatically imply
semantic correctness
```

A database can commit a transaction successfully.

A checkpoint can advance.

A projection worker can run.

A message can be delivered.

But none of these facts alone prove that the resulting system state still preserves the intended business meaning.

This note records a future architecture direction:

```text
Data Infrastructure
should be separated from
Semantic Infrastructure
```

This separation is not fully implemented yet.

It is a guiding philosophy for how Compass should evolve after the durable write-side, durable read-side, replay-efficiency, and runtime semantic validation baselines become stable.

This separation also matched an architectural intuition that kept returning during the project: the system seemed to require two different layers.

One layer preserves physical facts.

Another layer evaluates semantic meaning.

The later terms Data Infrastructure and Semantic Infrastructure simply gave that intuition a more precise name.

---

## 2. Origin: From Context-Dependent Labeling to Governance

Before this project started using terms such as Data Infrastructure or Semantic Infrastructure, the original question was much smaller.

It began with a simple labeling problem:

```text
Can the same tool carry different semantic roles in different contexts?
```

For example, Airflow may be only an enabler in a small local pipeline.

But in an enterprise data platform, Airflow may become part of the core operating system.

The tool did not change.

The context changed.

The role changed.

The governance requirement changed.

At first, this looked like a documentation or classification problem.

But it revealed a deeper architectural question:

```text
If meaning depends on context,
who decides the meaning,
how is that meaning represented,
and how does the runtime enforce it?
```

A semantic label is harmless if it only appears in a README.

But once the label changes runtime behavior, it becomes governance.

For example:

```text
If a component is labeled as Core,
the system may require stricter validation, stronger audit, and safer failure behavior.

If a component is labeled as Enabler,
the system may allow fallback, replacement, or degraded execution.
```

This is the semantic shift:

```text
context-dependent labeling
→ semantic representation
→ semantic validation
→ runtime policy
→ enforcement
```

This was the early seed of Compass.

Compass did not begin as an AI governance framework.

It began from the observation that tools do not have fixed meaning by themselves.

Their meaning depends on system context, business intent, and runtime responsibility.

Later, this same idea reappeared in more concrete engineering forms:

* whether validation belongs inside or outside a transaction
* whether a retry preserves the same intent
* whether a snapshot is trustworthy enough for the fast path
* whether a projection state still reflects accepted history
* whether an action is safe to execute

In that sense, the original Core / Enabler labeling question evolved into a broader philosophy:

```text
systems need a way to represent and govern context-dependent meaning
```

This note uses the terms Data Infrastructure and Semantic Infrastructure to describe that future direction.

Data Infrastructure preserves physical facts.

Semantic Infrastructure evaluates whether those facts still preserve the intended meaning.

---

## 3. Data Infrastructure

Data Infrastructure is responsible for physical system facts.

It answers questions such as:

```text
Was the event persisted?
Was the transaction committed?
Was the message delivered?
Was the checkpoint advanced?
Was the sequence continuous?
Was the row written atomically?
```

Examples of Data Infrastructure concerns include:

* PostgreSQL persistence
* transaction atomicity
* event-store append behavior
* idempotency result memory
* concurrency admission
* checkpoint storage
* projection-state persistence
* global sequence or stream position
* local development database setup
* schema constraints
* migration execution

These mechanisms are essential.

Without them, the system cannot reliably preserve facts.

However, Data Infrastructure mainly protects the physical shape and durability of data.

It does not, by itself, answer whether the data still means the right thing.

---

## 4. Semantic Infrastructure

Semantic Infrastructure is responsible for meaning.

It answers questions such as:

```text
Is this candidate event truthful relative to accepted history?
Does this derived state still match the event log?
Is this retry preserving the same intent?
Is this snapshot trustworthy enough for the fast path?
Is this action safe to execute?
Is this failure reversible, rebuildable, or dangerous?
```

In this project, Compass is evolving toward this role.

Today, Compass already has a Layer 1 baseline:

```text
candidate event
→ transition-truth validation
→ accepted history admission
```

In later stages, Compass should evolve toward:

```text
accepted history
→ derived state validation
→ structured semantic outcome
→ runtime decision
→ action safety
→ governance-oriented control
```

This future direction is what I call Semantic Infrastructure.

Semantic Infrastructure does not replace Data Infrastructure.

It sits above it and asks a different question:

```text
The system physically persisted something.
But is that thing semantically valid?
```

---

## 5. Why Physical Success Is Not Enough

A system can be physically successful while semantically wrong.

For example:

```text
A transaction commits,
but the event should not have been accepted.
```

```text
A projection checkpoint advances,
but the projection state no longer matches accepted history.
```

```text
A retry arrives,
but it no longer represents the same intent.
```

```text
A snapshot loads quickly,
but it was produced by an outdated reducer or corrupted after creation.
```

These are not ordinary infrastructure failures.

They are semantic failures.

If the system only checks whether data was persisted, delivered, or checkpointed, these failures may remain invisible until much later.

This is why Compass should not be treated as just another validation helper.

Compass is intended to become the semantic control layer that explains whether physical system progress is still meaningful.

---

## 6. Validation Placement as a Boundary

One important sign of this separation is validation placement.

Validation placement asks:

```text
Where should semantic validation happen relative to physical transaction boundaries?
```

For example:

```text
IN_TRANSACTION
```

means semantic validation occurs inside the physical transaction path.

```text
PRE_TRANSACTION
```

means semantic validation may occur before entering the physical transaction, while append-time admission still protects accepted-history mutation.

This distinction matters because semantic validation and physical persistence are related but not identical.

A database transaction can protect atomicity.

It cannot decide business meaning.

Compass validation can decide meaning.

It should not accidentally replace concurrency admission or transaction atomicity.

Therefore:

```text
validation placement
is a boundary between
semantic evaluation
and
physical persistence
```

This is one reason the project separates:

```text
ValidationMode
```

from:

```text
ValidationPlacement
```

`ValidationMode` describes the strength or behavior of validation.

`ValidationPlacement` describes where validation is executed relative to the physical persistence boundary.

They should not be collapsed.

---

## 7. Validation Strength Should Be Orchestrated, Not Hardcoded

A future Semantic Infrastructure layer should not hardcode every validation behavior into the core execution path.

Instead, the system should move toward protocol-based validation boundaries.

The core runtime should depend on an abstract validation contract, not on one concrete validator.

Conceptually:

```python
class SemanticValidator:
    def validate(self, candidate, context):
        ...
```

The runtime should be able to receive different validator implementations:

```text
StrictValidator
LaxValidator
AuditValidator
Layer1Validator
Layer2Validator
```

The important design idea is:

```text
the processor depends on the protocol,
not on the concrete validator
```

This is dependency inversion applied to semantic validation.

It allows the system to change validation strength or validation strategy without rewriting the physical execution path.

In future stages, this becomes important because different environments may need different validation behavior:

```text
local tests
→ strict validation

benchmarking
→ validation-off or measurement mode

production safety
→ strict or risk-aware validation

audit mode
→ physical path proceeds, semantic layer records evidence asynchronously
```

This does not mean all modes are equally safe.

It means validation strength becomes an explicit runtime / composition-level choice rather than hidden branching logic scattered across the codebase.

---

## 8. Snapshot Trust as a Semantic Infrastructure Problem

Snapshot work also points toward the same separation.

A snapshot may be stored physically in a database.

But that does not make it semantically trustworthy.

A snapshot is derived state.

It may help the system avoid full replay on every normal path, but it also creates a trust boundary.

The future Snapshot Trust Contract should answer:

```text
Where did this snapshot come from?
Which event prefix does it represent?
Which reducer version produced it?
Is the tail replay continuous?
Was the payload changed after creation?
Can this snapshot be ignored and rebuilt?
```

This means snapshot trust is not only a storage optimization.

It is a Semantic Infrastructure concern.

The physical database stores the snapshot.

The semantic layer decides whether the snapshot is qualified for the fast path.

The event log remains the authority path.

---

## 9. Retry Classification as a Semantic Infrastructure Problem

Retry is another example.

From a physical infrastructure point of view, a retry may simply look like another request.

But semantically, retry-like situations are not the same.

Examples:

```text
same request_id + same fingerprint
→ safe idempotent replay
```

```text
same request_id + different fingerprint
→ same identity carrying different meaning
```

```text
different request_id + stale expected_version
→ concurrency retry
```

```text
same future intent_id + different intent_fingerprint
→ possible agent intent drift
```

If all of these are collapsed into one generic `retry`, the runtime loses the ability to govern correctly.

This is why retry reason classification belongs to future `SemanticOutcome` / request-attempt evidence design.

It should not be forced into `idempotency_records`.

`idempotency_records` should remain successful request-result memory.

Retry reason, retry safety, and intent consistency belong to the future Semantic Infrastructure layer.

---

## 10. Projection Drift as a Semantic Infrastructure Problem

Projection state is also derived state.

A projection worker may successfully persist state and advance a checkpoint.

But the question remains:

```text
Does the persisted projection state still match accepted history?
```

This is the future role of Compass Layer 2.

Layer 2 should compare:

```text
accepted event history replay
```

against:

```text
persisted projection state
```

and produce a structured result when they diverge.

This turns projection drift from an invisible data inconsistency into a governable semantic outcome.

The database stores projection state.

Compass decides whether that derived state is semantically faithful.

---

## 11. Future Direction: Toward a Semantic Infra Layer

The long-term direction of this project is not merely:

```text
add more tests
add more database tables
add more validators
```

The direction is:

```text
separate physical infrastructure from semantic governance
```

A future architecture may look like this:

```text
Data Infrastructure
- stores accepted events
- persists idempotency records
- stores projection state
- stores checkpoints
- provides transaction boundaries
- enforces physical constraints

Semantic Infrastructure
- validates candidate event truth
- validates derived state truth
- classifies semantic failures
- distinguishes retry causes
- evaluates snapshot trust
- maps outcomes to runtime decisions
- guards high-risk actions
```

In this model, Compass becomes the bridge between physical data movement and semantic action safety.

It does not own all persistence.

It does not replace the database.

It gives the runtime a way to ask:

```text
Given what was physically persisted,
is the system still semantically safe?
```

---

## 12. Current Stage Boundary

This note describes a future architecture direction.

It does not mean the project already implements the full Semantic Infrastructure layer.

Current and near-term stages remain narrower:

```text
Stage 3.5C
→ durable read-side baseline

Stage 3.5D
→ snapshot trust / replay efficiency

Stage 3.5E
→ durable history and permission hardening

Stage 4
→ Layer 2 validation, SemanticOutcome, RuntimeDecisionPolicy

Stage 5
→ semantic correctness × operational freshness → action safety

Stage 5+
→ possible isolated derived-state runtime / agent-facing governance hardening
```

The purpose of this note is to preserve the design philosophy so that later implementation work does not collapse semantic concerns back into physical persistence concerns.

---

## 13. Design Principle

The guiding principle is:

```text
Data Infrastructure preserves physical facts.
Semantic Infrastructure evaluates whether those facts still preserve meaning.
```

Or more directly:

```text
A system is not correct just because data moved successfully.
A system is correct only when physical progress still preserves semantic truth.
```

This is the direction Compass should evolve toward.
