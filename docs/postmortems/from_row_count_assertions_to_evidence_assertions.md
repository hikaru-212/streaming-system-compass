# Postmortem: From Row-Count Assertions to Evidence Assertions

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-07-04

## Summary

This note records a near-miss testing lesson from Stage 3.5E PR4.

While adding permission-boundary tests for `projection_snapshots`, the test suite originally compared returned snapshot identifiers as strings.

PostgreSQL stores `projection_snapshots.snapshot_id` as a `UUID`, and `psycopg` returns that field as a Python `uuid.UUID` object.

The exact assertion:

```python
assert rows == [(snapshot_id,)]
```

exposed the mismatch immediately:

```text
UUID("...") != "..."
```

If the test had only asserted:

```python
assert len(rows) == 1
```

then the test would have passed while hiding the type mismatch.

No production incident occurred. The issue was caught during integration testing before merge.

The reusable lesson is:

```text
Row-count assertions prove that something came back.
Evidence assertions prove what came back.
```

---

## 1. Context

Stage 3.5E hardens database runtime permissions.

PR4 focuses on derived-state mutation permission boundaries for:

```text
projection_states
projection_checkpoints
projection_snapshots
```

The purpose of the tests is not to validate business logic or replay correctness.

The purpose is to prove the PostgreSQL privilege matrix:

```text
which runtime role can SELECT / INSERT / UPDATE / DELETE which derived-state table
```

Allowed permission probes use SQL statements with `RETURNING` or `SELECT` evidence so the test can verify not only that the statement succeeded, but also that the expected row was touched.

---

## 2. What Happened

The `projection_snapshots` permission tests used generated `snapshot_id` values.

The test helper originally created `snapshot_id` as a string:

```python
snapshot_id = str(uuid4())
```

The SQL statement inserted the value into a PostgreSQL `UUID` column:

```sql
snapshot_id UUID PRIMARY KEY
```

When the test selected or returned `snapshot_id`, `psycopg` returned a Python `uuid.UUID` object, not a string.

The assertion failed:

```text
[(UUID('973e9eef-2d30-40c8-b1ff-b6f5c4ba3cd0'),)]
!=
[('973e9eef-2d30-40c8-b1ff-b6f5c4ba3cd0',)]
```

The database row was correct.

The privilege boundary was correct.

The mismatch was between the test expectation and the database driver's physical return type.

---

## 3. Why It Was Confusing

The values looked identical when read visually:

```text
973e9eef-2d30-40c8-b1ff-b6f5c4ba3cd0
```

But Python equality is type-aware:

```python
UUID("973e9eef-2d30-40c8-b1ff-b6f5c4ba3cd0")
!=
"973e9eef-2d30-40c8-b1ff-b6f5c4ba3cd0"
```

This is not a precision problem.

It is a boundary-adapter problem:

```text
PostgreSQL UUID
→ psycopg adapter
→ Python uuid.UUID
```

The application must decide where that typed value is preserved and where it is serialized into a string.

---

## 4. What Would Have Been Missed

A weaker assertion such as:

```python
assert len(rows) == 1
```

would have passed.

It would have proved only:

```text
one row was returned
```

It would not have proved:

```text
the returned row carried the expected identifier
the row shape was exactly one column
the returned value matched the generated test evidence
the database driver's return type matched the test expectation
```

That would create false confidence.

The test would be green, but the storage boundary contract would remain partially unexamined.

---

## 5. Root Cause

The root cause was not PostgreSQL and not `psycopg`.

The root cause was an assertion-fidelity gap.

The test originally treated successful execution as the main proof target.

But for permission probes with `RETURNING` or `SELECT`, the stronger proof target should be:

```text
the statement succeeded and returned the exact evidence expected
```

The test needed to align Python expected values with PostgreSQL physical return types.

---

## 6. Resolution

The test helper was corrected to keep `snapshot_id` and `source_event_id` as Python `UUID` objects:

```python
from uuid import UUID, uuid4

snapshot_id = uuid4()
source_event_id = uuid4()
```

The helper return type was updated accordingly:

```python
def _insert_projection_snapshot_as_test_owner(...) -> UUID:
    ...
```

and:

```python
def _valid_projection_snapshot_insert_statement() -> tuple[
    str,
    tuple[object, ...],
    UUID,
]:
    ...
```

The exact evidence assertions remained unchanged:

```python
assert rows == [(snapshot_id,)]
```

This keeps the test aligned with the database schema:

```text
PostgreSQL UUID
→ Python UUID inside storage / test boundary
```

---

## 7. Corrected Testing Rule

For permission tests:

```text
If a SQL statement uses RETURNING or SELECT as evidence,
assert the exact returned evidence.
```

Prefer:

```python
assert rows == [(expected_value,)]
```

over:

```python
assert len(rows) == 1
```

when the returned value is part of the proof.

A row-count assertion is acceptable only when the content is irrelevant to the test's claim.

---

## 8. Corrected Type Boundary Rule

Database-native identity types should remain typed inside storage and domain boundaries.

For example:

```text
PostgreSQL UUID
→ Python UUID internally
→ explicit str(...) at JSON / API / receipt boundary
```

Do not silently collapse database identity values into strings too early.

Also do not let Python `UUID` objects escape into JSON-like external boundaries without an explicit serialization decision.

The conversion boundary should be deliberate.

---

## 9. Future Prevention

Future code should use several layers of defense.

### 9.1 Exact evidence assertions

Permission probes with `RETURNING` should compare returned rows directly.

This catches row-shape, value, and type mismatch issues early.

### 9.2 Store-boundary mapping

Raw database rows should be mapped into typed domain objects at the storage boundary.

For snapshots, this means preserving types such as:

```text
snapshot_id: UUID
source_event_id: UUID
total_amount: Decimal
paid_amount: Decimal
source_global_position: int
```

### 9.3 Serialization-boundary tests

Future receipt / API / JSON-producing code should explicitly test conversion from typed internal values into serialized external values.

For example:

```text
internal snapshot_id: UUID
external receipt snapshot_id: string
```

### 9.4 Static type checking

Static checking with tools such as `mypy` or `pyright` can help prevent accidental UUID / string drift once storage and domain models become more typed.

This should be introduced only when the project is ready to maintain that strictness consistently.

---

## 10. Non-Goals

This postmortem does not require PR4 permission tests to become broad serialization tests.

It does not require `projection_snapshots` permission tests to create accepted-history lineage records.

It does not introduce chaos testing, concurrent worker testing, production connection-pool testing, or API receipt testing.

Those belong to later runtime-governance and production-hardening stages.

The PR4 scope remains:

```text
PostgreSQL runtime role privilege matrix correctness
```

---

## 11. Relationship to Future Chaos / Production-Hardening Tests

This near miss is separate from chaos testing, but it points in the same direction:

```text
single-case success is not the same as production survivability
```

Stage 3.5E proves baseline permission boundaries.

Later stages should test behavior under:

```text
independent runtime connections
role-specific login identities
connection-pool reuse
rollback failure
concurrent snapshot writes
checkpoint races
worker crash windows
derived-state corruption and rebuild
permission bypass attempts during active workflows
```

Those tests should come after the runtime governance model is mature enough to classify, decide, retry, refuse, or recover from the observed failures.

---

## 12. Final Lesson

The key lesson is:

```text
A test should not only prove that an operation happened.
It should prove the evidence that makes the operation meaningful.
```

In this case:

```text
len(rows) == 1
```

was too weak.

The stronger pattern:

```text
assert rows == [(expected_value,)]
```

turned a hidden driver-type mismatch into an immediate, useful failure.

That is the value of evidence assertions.
