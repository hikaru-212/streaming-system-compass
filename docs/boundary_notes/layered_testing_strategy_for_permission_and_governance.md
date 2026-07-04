# Layered Testing Strategy for Permission Boundaries and Runtime Governance

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the testing boundary between:

```text
ordinary storage / mechanism integration tests
permission-boundary integration tests
future Stage 4 governance-flow integration tests
```

It exists to prevent a future misunderstanding:

```text
adding runtime database roles
does not mean all existing integration tests must stop using the test-owner connection
```

Stage 3.5E introduces database roles and table-level privilege boundaries, but those roles should not be allowed to distort the meaning of existing tests.

The project should preserve a clear distinction between:

```text
mechanism correctness
permission boundary correctness
runtime governance correctness
```

Each test layer should use the connection authority that matches the boundary under test.

---

## Core Principle

The project should not collapse all integration tests into one role model.

Instead, tests should be layered:

```text
compass_user / test owner
= setup, cleanup, migration, fixture authority, ordinary mechanism tests

compass_* runtime roles
= permission-boundary verification

multiple runtime roles together
= future Stage 4 governance-flow verification
```

The goal is not to make every test use low-privilege runtime roles.

The goal is to use the correct role for the boundary being tested.

---

## Layer 1 — Ordinary Storage / Mechanism Integration Tests

These tests verify that the system mechanisms work correctly.

They may continue to use:

```text
compass_user
```

or another high-privilege test / migration owner connection.

This is acceptable because these tests are not trying to prove permission boundaries.

They are trying to prove behavior such as:

```text
PostgresEventStore append / load works
PostgresIdempotencyStore replay / conflict behavior works
PostgresProjectionStore save / load / clear works
PostgresCheckpointStore persists worker progress
PostgresProjectionSnapshotStore saves and loads snapshots
Projection worker applies reducer output correctly
Replay validator compares derived state against accepted history
Snapshot-assisted resolver resolves through snapshot + tail replay
```

These tests often need setup and cleanup authority:

```text
truncate tables
insert fixtures
clear derived state
simulate invalid rows
prepare edge cases
rollback failed writes
reset database state
```

Forcing all of these tests to use low-privilege runtime roles would mix two concerns:

```text
Does the mechanism work?
Does this role have the correct permission?
```

Those should remain separate unless the test is explicitly about runtime-role behavior.

---

## Store Capability Is Not Runtime Role Authority

A store method may expose cleanup or reset helpers for tests, local maintenance, rebuild flows, or future controlled repair paths.

That does not mean every normal runtime role should be able to execute every store method through database privileges.

For example:

```text
PostgresProjectionSnapshotStore.clear_snapshots(order_id)
```

is a storage-level cleanup capability.

It may be valid under:

```text
test-owner authority
migration / maintenance authority
controlled rebuild authority
future governance-controlled repair authority
```

But it does not imply that the normal snapshot production role should receive runtime `DELETE` authority on `projection_snapshots`.

The intended distinction is:

```text
snapshot_worker
= produces snapshot artifacts
= SELECT / INSERT projection_snapshots

snapshot cleanup / reset / quarantine / retention
= separate maintenance or governance-controlled authority
= not normal snapshot production
```

This prevents a common mistake:

```text
storage capability exists
therefore runtime role should have permission to use it
```

That inference is not valid in this project.

The permission boundary must preserve responsibility, not merely make every method callable by the nearest runtime component.

---

## Layer 2 — Permission-Boundary Integration Tests

These tests verify that Stage 3.5E database roles express the intended durable mutation boundary.

They should use the runtime roles introduced by the permission baseline, such as:

```text
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

A typical structure is:

```text
setup data with compass_user / test owner
SET ROLE to the runtime role being tested
attempt an allowed or forbidden operation
assert success or permission rejection
RESET ROLE and rollback to restore the test connection
cleanup with compass_user / test owner
```

These tests are not full business-flow tests.

They are durable mutation-boundary tests.

Expected examples:

```text
compass_app_writer can SELECT / INSERT order_events
compass_app_writer cannot UPDATE / DELETE order_events
compass_app_writer can SELECT / INSERT idempotency_records
compass_app_writer cannot UPDATE / DELETE idempotency_records
compass_app_writer cannot access projection_states by default
compass_app_writer can use order_events_global_position_seq

compass_projection_worker can SELECT order_events
compass_projection_worker cannot INSERT / UPDATE / DELETE order_events
compass_projection_worker can INSERT / UPDATE / DELETE projection_states
compass_projection_worker can INSERT / UPDATE / DELETE projection_checkpoints
compass_projection_worker cannot mutate idempotency_records
compass_projection_worker cannot consume order_events_global_position_seq

compass_snapshot_worker can SELECT order_events
compass_snapshot_worker can SELECT projection_states
compass_snapshot_worker can SELECT projection_checkpoints
compass_snapshot_worker can SELECT / INSERT projection_snapshots
compass_snapshot_worker cannot mutate accepted history
compass_snapshot_worker cannot mutate projection state or checkpoints
compass_snapshot_worker cannot DELETE projection_snapshots by default
compass_snapshot_worker cannot consume order_events_global_position_seq

compass_readonly can SELECT durable tables
compass_readonly cannot INSERT / UPDATE / DELETE / TRUNCATE
compass_readonly cannot consume order_events_global_position_seq
```

These tests prove:

```text
accepted history is harder to mutate than derived runtime state
```

They also preserve the distinction:

```text
database permission boundary
≠
Compass semantic admission
```

A role may be allowed to use an append path, while Compass may still reject a candidate event.

A semantically valid candidate should still not be written through an unauthorized durable mutation path.

---

## Layer 3 — Future Stage 4 Governance-Flow Integration Tests

Stage 4 may begin to connect multiple runtime roles into realistic governance flows.

These tests should verify not only storage behavior and permission behavior, but also:

```text
runtime decision ownership
semantic outcome production
decision receipt evidence
policy-guided retry / fallback behavior
snapshot trust selection
runtime-state resolution under governance
```

Unlike Layer 1 tests, these may intentionally use multiple runtime roles in one scenario.

A future Stage 4 test may look like:

```text
1. setup uses compass_user / test owner
   - reset database
   - prepare fixtures
   - apply migrations

2. compass_app_writer performs write-side command path
   - checks idempotency
   - rehydrates aggregate from accepted history
   - runs Compass Layer 1
   - inserts order_events
   - inserts successful idempotency_records

3. compass_projection_worker processes accepted history
   - reads order_events
   - updates projection_states
   - updates projection_checkpoints

4. compass_snapshot_worker produces snapshot evidence
   - reads accepted history / projection state / checkpoint progress
   - inserts projection_snapshots

5. future runtime governance role evaluates state
   - reads accepted history, projection state, snapshot, receipts, or policy inputs
   - writes DecisionReceipt / SemanticOutcome / validation evidence

6. compass_readonly observes results
   - can read accepted state, derived state, and evidence
   - cannot mutate durable state
```

This layer should answer questions such as:

```text
Can the system execute the intended runtime flow using responsibility-specific roles?

Can semantic decision evidence be written only by the intended runtime component?

Can snapshot fast paths require qualified trust evidence?

Can rejected candidates produce structured evidence without entering accepted history?

Can readonly observers inspect evidence without gaining mutation authority?
```

---

## What `compass_user` Means in Tests

`compass_user` should not be treated as obsolete after runtime roles are added.

In tests, it may continue to represent:

```text
test harness authority
migration/setup authority
fixture authority
cleanup authority
ordinary integration-test owner
```

This is different from runtime responsibility.

The mistake to avoid is not:

```text
using compass_user in tests
```

The mistake to avoid is:

```text
using compass_user for every test
and then claiming runtime role boundaries have been verified
```

Therefore:

```text
compass_user tests
= prove mechanisms work

compass_* role tests
= prove responsibility boundaries hold

multi-role governance tests
= prove Stage 4 runtime semantics work under the intended authority model
```

---

## Stage 3.5E Position

Stage 3.5E should not force all existing tests to use runtime roles.

PR2 establishes the database role / privilege baseline.

The expected PR2 behavior is:

```text
create runtime roles
grant intended table privileges
do not disturb existing integration tests
do not revoke compass_user
do not force all test connections to become low-privilege roles
```

PR3 and PR4 may then add permission-boundary tests.

Those tests should intentionally use runtime roles.

But existing storage, reducer, replay, snapshot, and worker tests may continue to use the test owner connection.

---

## Stage 4 Position

Stage 4 may introduce tests that are closer to real runtime role orchestration.

Those tests should not replace all earlier tests.

They should add a new layer that verifies:

```text
semantic governance
decision evidence
runtime policy
snapshot trust
retry classification
state resolution
under responsibility-specific database roles
```

This preserves the layered test model:

```text
Layer 1:
mechanism correctness

Layer 2:
permission boundary correctness

Layer 3:
runtime governance correctness
```

---

## Final Rule

Use the role that matches the boundary under test.

```text
If the test is about storage behavior:
use the test owner connection.

If the test is about permission enforcement:
use the runtime role being tested.

If the test is about Stage 4 runtime governance:
use the participating runtime roles together.
```

This keeps tests expressive without turning every integration test into a permission test.
