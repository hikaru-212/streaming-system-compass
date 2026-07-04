# ADR 0015: Permission Probing with SET ROLE Instead of Production Login Identity Simulation

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted as a testing-scope decision for Stage 3.5E.

Stage 3.5E verifies PostgreSQL runtime-role permission boundaries through a test-owner database connection and `SET ROLE` probes.

No separate production login users, role-specific database URLs, role-specific connection pools, CI secrets, or deployment identity topology are introduced in the current baseline.

The current implementation continues to model runtime database roles as responsibility roles:

```text
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

The tests activate those responsibility roles through `SET ROLE` to verify their effective PostgreSQL privileges.

This decision is implemented through the Stage 3.5E permission-test helper layer and security integration tests.

Related implementation notes that preserve this boundary:

- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Layered Testing Strategy for Permission and Governance](../boundary_notes/layered_testing_strategy_for_permission_and_governance.md)

Future work may revisit this decision only if the project needs production-like database identity isolation, role-specific connection pools, deployment credential hardening, or end-to-end service identity tests.

---

## Context

Stage 3.5E introduces database role and privilege hardening around durable accepted history, write-side receipts, projection state, checkpoints, and snapshots.

The goal is to verify that each runtime responsibility role has the intended effective privileges:

```text
compass_app_writer
→ can append accepted-history records and idempotency receipts
→ cannot mutate read-side derived state

compass_projection_worker
→ can consume accepted history
→ can maintain projection state and checkpoint progress
→ cannot mutate accepted history or idempotency receipts

compass_snapshot_worker
→ can read required derived state and write snapshot evidence
→ cannot mutate projection state or checkpoint progress
→ cannot rewrite or delete snapshot evidence by default

compass_readonly
→ can observe allowed durable state
→ cannot mutate durable state
```

A production deployment could represent these roles with separate login identities and role-specific connection pools:

```text
app-writer service
→ app-writer database login / connection pool

projection worker
→ projection-worker database login / connection pool

snapshot worker
→ snapshot-worker database login / connection pool

readonly API / reporting path
→ readonly database login / connection pool
```

That deployment model is valuable, but it answers a different question.

The current Stage 3.5E question is:

```text
If this PostgreSQL role is active, does it have the correct effective privileges?
```

It is not yet:

```text
Are production services wired to separate database credentials and connection pools?
```

Introducing production login identities at this stage would add infrastructure complexity before it improves the current proof target.

---

## Decision

Use `SET ROLE` from a test-owner connection to probe runtime responsibility roles in Stage 3.5E.

Do not introduce separate production-style login users or role-specific database URLs in the current baseline.

Current test model:

```text
test-owner connection
→ SET ROLE compass_app_writer
→ probe effective privileges

test-owner connection
→ SET ROLE compass_projection_worker
→ probe effective privileges

test-owner connection
→ SET ROLE compass_snapshot_worker
→ probe effective privileges

test-owner connection
→ SET ROLE compass_readonly
→ probe effective privileges
```

The purpose is to validate the PostgreSQL privilege matrix directly.

This decision does not claim that `SET ROLE` is the preferred production runtime identity model.

If production identity hardening is introduced later, it should be modeled separately as deployment / connection-topology hardening, not as a replacement for the Stage 3.5E privilege-matrix tests.

---

## Rationale

Stage 3.5E needs to prove the database privilege matrix, not production deployment topology.

Using `SET ROLE` keeps the test surface focused:

```text
role grants
role revokes
table privileges
sequence privileges
effective PostgreSQL permission checks
```

It avoids introducing unrelated failure causes:

```text
missing database user
wrong password
wrong connection string
CI secret misconfiguration
connection-pool setup error
Docker initialization ordering
role membership setup drift
```

Those are real production concerns, but they are not the core Stage 3.5E concern.

The current tests should fail because a privilege boundary is wrong, not because a production-like login topology was misconfigured.

This also keeps PR3 and PR4 focused:

```text
PR3
= accepted-history and write-side receipt mutation hardening

PR4
= derived-state, checkpoint, and snapshot permission boundaries
```

Neither PR needs to prove that production service credentials have already been separated.

---

## Role Boundary Being Tested

The Stage 3.5E tests verify effective privileges after role activation.

They answer:

```text
Can compass_app_writer SELECT order_events?
Can compass_app_writer UPDATE order_events?
Can compass_projection_worker UPDATE projection_states?
Can compass_snapshot_worker DELETE projection_snapshots?
Can compass_readonly INSERT projection_checkpoints?
Can non-app-writer roles consume order_events_global_position_seq?
```

They do not answer:

```text
Which production service owns which database URL?
Which connection pool is used by each runtime component?
How are credentials rotated?
How are secrets stored?
Can a deployed worker accidentally receive the wrong DSN?
Can a pooled connection leak an elevated role across borrowers?
```

Those questions belong to a future runtime deployment hardening layer.

---

## Source of Truth Boundary

This ADR does not change the accepted-history authority model.

The authority boundary remains:

```text
order_events / accepted history
= source of truth
```

The permission-testing boundary is separate:

```text
runtime responsibility roles
= database privilege boundaries

SET ROLE probes
= test-time mechanism for activating those boundaries

production login identities
= future deployment hardening concern
```

A successful `SET ROLE` permission test proves that the role's effective privileges are correct once active.

It does not prove that production runtime identity isolation has been implemented.

---

## Alternatives Considered

### Alternative 1: Create Production-Style Login Users Now

The project could create login users such as:

```text
compass_app_writer_login
compass_projection_worker_login
compass_snapshot_worker_login
compass_readonly_login
```

Each integration test could connect with a role-specific database URL.

This would make the tests more production-like, but it would add infrastructure cost:

```text
more database initialization logic
more environment variables
more CI configuration
more connection setup paths
more secret-management assumptions
more failure modes unrelated to privilege grants
```

This option is deferred.

It may become appropriate when the project begins testing deployment identity isolation or connection-pool hardening.

### Alternative 2: Use Only the Test Owner Without SET ROLE

The project could run all permission tests as the high-privilege test owner.

This would be simpler, but it would not verify runtime role boundaries.

It would only verify schema constraints or owner-level behavior.

This option is rejected because Stage 3.5E exists specifically to verify role-specific permission boundaries.

### Alternative 3: Use SET ROLE for Permission Probes

The project uses a test-owner connection and temporarily activates runtime responsibility roles with `SET ROLE`.

This keeps the test focused on effective PostgreSQL privileges while avoiding production login topology.

This option is accepted for Stage 3.5E.

---

## Consequences

### Positive Consequences

The tests directly verify the PostgreSQL privilege matrix.

The current baseline avoids unnecessary deployment complexity.

The failure surface remains small and interpretable.

Security tests can be written as permission probes:

```text
role + statement → allowed / rejected
```

The project can harden database privileges before designing production identity isolation.

### Negative Consequences

The current tests do not prove production services use separate database credentials.

They do not prove role-specific connection pools exist.

They do not prove connection-pool borrowers cannot inherit the wrong session role.

They do not prove deployment secrets are separated, rotated, or scoped.

They do not catch mistakes where a production service is wired to the wrong database URL.

These remain future deployment-hardening concerns.

---

## Future Trigger Conditions

Revisit this decision when one or more of the following become true:

```text
1. The project introduces production-like service processes.
2. App writer, projection worker, snapshot worker, and readonly paths run as separate deployable components.
3. CI needs to verify role-specific database URLs.
4. Connection-pool isolation becomes a correctness or security concern.
5. Credentials and secrets become part of the tested deployment boundary.
6. Runtime services must prove they cannot accidentally receive elevated privileges.
7. SET ROLE leakage across pooled sessions becomes a realistic risk.
8. Stage 4 / Stage 5 introduces governance tests that require production identity evidence.
9. The project moves from local integration tests toward deployment-hardening tests.
```

At that point, introduce production identity tests as a deployment hardening layer, not as a replacement for privilege-matrix tests.

---

## Relationship to Compass

In Compass terms:

```text
accepted history
= Core authority

runtime database roles
= operational permission boundary

SET ROLE permission probes
= test-time evidence for effective privilege correctness

production login identities / connection pools
= future deployment hardening substrate
```

This ADR preserves the distinction between:

```text
what the database role is allowed to do
```

and:

```text
how production services obtain database identity
```

The first is a Stage 3.5E database-permission concern.

The second is a future deployment / operations concern.

---

## Current Decision Summary

Do not introduce production-style login identities in Stage 3.5E.

Current model:

```text
test-owner connection = test harness authority
SET ROLE = test-time role activation
runtime role = responsibility-level privilege boundary
```

Future model, if needed:

```text
service-specific login identity = deployment identity boundary
role-specific connection pool = runtime isolation mechanism
privilege matrix = still enforced by PostgreSQL roles
```

The decision can be revisited when production identity isolation becomes real enough to justify additional infrastructure.
