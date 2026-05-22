# Postmortem: From Local PostgreSQL Setup to Defense-in-Depth Boundaries

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-22

## Summary

This note records a shift in understanding during Stage 3.5B.

The original question looked like a local development concern:

> Why is it acceptable for `docker-compose.yml` to contain a default PostgreSQL username and password?

At first, this looked like a security risk.  
If a password appears in a repository, does that mean someone can use it to access the real database?

The deeper lesson is:

> Different mechanisms protect different boundaries.  
> A modern system should not rely on one mechanism to protect everything.

In Stage 3.5B, this matters because the project is moving from an in-memory semantic baseline toward PostgreSQL-backed durable write-side persistence.

That transition is not only about adding a database.  
It also requires clear separation between:

- local reproducibility
- runtime secrets
- database permissions
- schema contracts
- production infrastructure ownership

Together, these mechanisms form a defense-in-depth model.

---

## 1. Trigger Question

The trigger was a practical setup question:

> If `docker-compose.yml` contains a PostgreSQL username and password, is that dangerous?

This question appeared during the local PostgreSQL setup work for Stage 3.5B.

The project needed a reproducible local environment so that the durable write-side schema and migration skeleton could be tested consistently.

A typical local setup might include values such as:

```yaml
POSTGRES_USER: compass_dev
POSTGRES_PASSWORD: compass_dev_password
POSTGRES_DB: compass_dev
```

At first glance, putting a password in a repository can look wrong.

But the important distinction is:

> A local development password is not a production secret.

This distinction is the starting point of the postmortem.

---

## 2. Initial Confusion

The initial concern was reasonable:

- passwords should not be committed to source code
- production credentials must never be exposed
- public repositories are scanned by attackers and automated tools
- leaking a real cloud database password would be a serious incident

However, this concern mixes two different things:

1. a local sandbox credential
2. a real deployment secret

These two have different meanings.

A Docker Compose password used for local development only creates access to a database running inside the developer's own local environment.

It does not grant access to production infrastructure.

The mistake would be to treat every credential-looking value as the same kind of secret.

The corrected model is:

> The danger is not that a local Docker password exists.  
> The danger is confusing local test credentials with real production credentials.

---

## 3. Boundary Clarification

The key clarification is that local development, source code, runtime configuration, and production infrastructure are separate boundaries.

They do not automatically share state or authority.

A person who reads the repository and sees the local Docker password can only use that password against a compatible local environment that they create themselves.

They cannot use it to access a protected production database unless production has mistakenly reused the same credential and exposed the production endpoint.

That would be a deployment and secret-management failure, not a Docker Compose failure.

The corrected boundary model is:

```text
Repository
  contains local environment blueprint

Developer machine
  runs isolated local PostgreSQL container

Production environment
  owns real infrastructure and real secrets

Runtime application
  receives environment-specific credentials

Database
  enforces permissions and constraints
```

These boundaries must be intentionally connected.

They should not be accidentally collapsed into one global environment.

---

## 4. Layer 1: Docker Compose as Local Environment Reproduction

Docker Compose should be understood as a local environment reproduction mechanism.

It gives contributors and future maintainers a consistent way to start the project.

In this project, that means:

- start a local PostgreSQL instance
- create a predictable database name
- run the migration skeleton
- test the durable write-side schema
- avoid manual environment drift across machines

The purpose is not to secure production.

The purpose is to make local development reproducible.

For Stage 3.5B, this is important because the project must test the physical shape of durable write-side persistence before implementing the full PostgreSQL store layer.

The local Docker environment is a sandbox.

It is acceptable for that sandbox to have a simple default username and password, because the sandbox is isolated to the developer's machine.

### What Docker Compose protects

Docker Compose helps protect against:

- inconsistent local setup
- "works on my machine" drift
- manual database setup mistakes
- unclear onboarding steps

### What Docker Compose does not protect

Docker Compose does not protect against:

- production secret leakage
- overly broad database roles
- unsafe application permissions
- missing database constraints
- bad deployment configuration

Docker Compose is a reproducibility tool, not the entire security model.

---

## 5. Layer 2: `.env` as Runtime Secret Injection

The `.env` boundary solves a different problem.

It separates source code from environment-specific configuration.

The source code should know names such as:

```text
DATABASE_URL
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

But the source code should not contain the real production values.

The production values should be injected by the deployment environment.

This keeps the repository reusable without giving away real credentials.

The correct mental model is:

> Source code defines what configuration is needed.  
> The environment provides the actual values.

In local development, the values may come from Docker Compose or a local `.env` file.

In production, the values should come from a real secret-management path, such as a cloud secret manager, CI/CD secret store, Kubernetes secret, or other organization-approved mechanism.

### What `.env` protects

`.env` and environment-specific configuration help protect against:

- hardcoded production credentials
- accidentally committing real secrets
- coupling source code to one deployment environment
- leaking cloud database access through Git

### What `.env` does not protect

`.env` does not protect against:

- an application using too much database privilege
- a developer manually running destructive SQL
- a bug that updates or deletes rows if the database role allows it
- missing append-only constraints

`.env` is a secret separation boundary.

It is not a permission model.

---

## 6. Layer 3: Least Privilege as Blast Radius Control

Least privilege solves another different problem.

Even if the application has valid credentials, those credentials should not give it unrestricted power.

For the durable write-side runtime, the application should not casually operate as a database superuser.

If the runtime only needs to insert accepted events and read history, its role should be shaped around those needs.

For example, an application role may need:

- `SELECT` on event history
- `INSERT` on accepted event tables
- `SELECT` / `INSERT` on idempotency records

But it should not automatically need:

- unrestricted `UPDATE`
- unrestricted `DELETE`
- schema ownership
- superuser access

This is especially important for an event-sourced system.

Accepted event history is supposed to be extended, not rewritten.

So database permissions should support the same semantic intent.

### Why this matters

Imagine an application bug accidentally runs a destructive statement:

```sql
UPDATE order_events SET amount = 0;
```

If the application role has broad update permission, the accepted event history can be corrupted.

If the application role does not have update permission, PostgreSQL rejects the operation.

This is blast radius control.

The point is not that permissions replace application correctness.

The point is that permissions reduce damage when application correctness fails.

### What least privilege protects

Least privilege helps protect against:

- application bugs
- accidental destructive queries
- compromised runtime code
- overly powerful automation
- careless internal operations

### What least privilege does not protect

Least privilege does not replace:

- application validation
- Compass Layer 1 validation
- schema constraints
- transaction design
- idempotency logic
- durable replay semantics

Least privilege is one defensive layer.

It is not the whole architecture.

---

## 7. Layer 4: SQL Migration as Durable Schema Contract

SQL migration files solve yet another problem.

They define the durable physical shape of the database.

For Stage 3.5B, migration files are not merely setup scripts.

They are the database-side expression of the persistence contract.

The migration defines tables such as:

- `order_events`
- `idempotency_records`

It also defines durable rules such as:

- accepted event identity
- stream sequence uniqueness
- exact numeric storage
- JSON object boundaries
- event schema versioning
- idempotency record references

This is where in-memory semantic assumptions begin to become physical database constraints.

A migration should therefore be treated as a durable contract, not as a temporary setup helper.

### Schema-as-contract

A useful mental model is:

> The SQL migration is the database contract for what durable truth is allowed to look like.

This does not mean SQL migration is the entirety of Infrastructure as Code.

More precisely:

> SQL migrations are an infrastructure-as-code style practice for database schema evolution.  
> They define database structure as versioned code, but they do not replace full infrastructure provisioning tools such as Terraform, Pulumi, or CloudFormation.

This distinction matters.

A SQL migration defines the database schema.

A provisioning tool may define the database instance, network, IAM, storage, backups, and deployment infrastructure.

Both can be code.

They operate at different layers.

---

## 8. Defense in Depth

The deeper engineering lesson is defense in depth.

No single mechanism should be expected to solve every problem.

Each layer protects a different boundary:

| Mechanism | Boundary | Main Purpose |
|---|---|---|
| Docker Compose | local environment boundary | reproduce a local sandbox |
| `.env` / environment variables | secret boundary | keep real secrets out of source code |
| least privilege | permission boundary | reduce runtime blast radius |
| SQL migrations | schema boundary | define durable database shape |
| Compass validation | semantic boundary | prevent invalid events from becoming accepted history |
| transactions | consistency boundary | commit related durable writes together |

The mistake is asking one layer to do another layer's job.

For example:

- Docker Compose does not protect production secrets.
- `.env` does not enforce database immutability.
- least privilege does not define event schema evolution.
- SQL constraints do not replace semantic validation.
- Compass validation does not replace transaction atomicity.

The system becomes safer when each layer does its own job clearly.

---

## 9. Relation to the Existing Database Immutability Postmortem

This postmortem is closely related to the earlier lesson:

> Boundaries do not preserve semantics automatically.  
> They require explicit alignment.

The previous postmortem focused on the transition from Python memory semantics to PostgreSQL durable semantics.

For example:

- `frozen=True` protects Python objects in memory
- PostgreSQL rows are mutable by default
- append-only intent must be re-declared through database permissions, constraints, and write-path discipline

This postmortem extends that same idea into environment and security boundaries.

The shared rule is:

> A guarantee must be declared in the layer where it is expected to hold.

Examples:

| Desired Guarantee | Where It Must Be Declared |
|---|---|
| local setup is reproducible | Docker Compose |
| production secrets are not leaked | environment-specific secret injection |
| runtime cannot rewrite history | database permissions / policy |
| stream sequence is unique | database constraints |
| money remains exact | database numeric type and Python Decimal handling |
| invalid transition cannot enter history | Compass Layer 1 |
| event append and idempotency record succeed together | transaction boundary |

This is the same architectural pattern repeated at different levels.

---

## 10. Relation to Stage 3.5B

Stage 3.5B is the durable write-side baseline.

It should not be treated as a simple database integration task.

It includes several boundary translations:

```text
in-memory event history
  → durable accepted event table

Python object identity
  → PostgreSQL UUID identity

Decimal money semantics
  → exact NUMERIC persistence

in-memory idempotency memory
  → durable idempotency records

single-process write path
  → transactional database write boundary

developer machine setup
  → reproducible local PostgreSQL environment

runtime credentials
  → environment-specific secret injection

application authority
  → least-privilege database roles
```

The immediate implementation order remains:

1. local schema and migration setup
2. `PostgresEventStore`
3. `PostgresIdempotencyStore`
4. transactional write-side boundary

But this postmortem clarifies the security and environment model behind that work.

---

## 11. Why Local Credentials Are Not the Same as Production Secrets

A local Docker credential is acceptable when it has only local meaning.

It becomes dangerous when any of the following mistakes happen:

- the same password is reused in production
- the production database is exposed to the public internet
- production accepts the local development credential
- the application code hardcodes production credentials
- secrets are committed into version control
- deployment relies on repository defaults instead of environment-specific secrets

Therefore, the rule is not:

> Never show any password-looking value anywhere.

The rule is:

> Never commit real environment secrets.  
> Never reuse local sandbox credentials as production credentials.  
> Never let source-code defaults become production authority.

This is a more precise rule.

It allows local reproducibility without weakening production security.

---

## 12. Why Least Privilege Still Matters Even With `.env`

Even if production secrets are stored correctly, the application can still be too powerful.

A properly injected password can still belong to an overly privileged database role.

That means secret management alone does not solve permission design.

The application's runtime identity should be limited according to what the application actually needs to do.

For an event-sourced write-side runtime, this is especially important because historical events are not ordinary mutable records.

They represent accepted history.

A runtime path that appends accepted events should not casually have the power to rewrite prior accepted events.

This is why `.env` and least privilege are separate concerns:

```text
.env answers:
Where does the credential come from?

least privilege answers:
What is that credential allowed to do?
```

Both are necessary.

They solve different problems.

---

## 13. Why SQL Migration Is More Than Setup

A migration file can look like a setup detail, but in a durable system it has deeper meaning.

It defines:

- what can be stored
- what identity means
- what uniqueness means
- which values must be exact
- which fields belong to payload, proof, or metadata
- how schema evolution is represented

For this project, migrations should help preserve the semantic meaning of accepted history.

Examples:

- `accepted_event_id` represents accepted history identity
- `(order_id, sequence)` protects stream position uniqueness
- `amount NUMERIC(18, 2)` preserves exact money semantics
- `event_schema_version` supports durable event evolution
- `metadata_json` separates runtime metadata from domain payload and proof

This means the migration is part of the correctness story.

It is not merely database plumbing.

---

## 14. Practical Rules Going Forward

This postmortem produces the following practical rules for future implementation.

### Rule 1: Local defaults are allowed only as local defaults

Repository defaults may support local development.

They must not be reused as production authority.

### Rule 2: Real secrets must be environment-specific

Production credentials should be injected outside source code.

The repository should define configuration names, not production values.

### Rule 3: Runtime roles should be narrow

Application database users should have only the permissions required by the runtime path.

For accepted event history, broad `UPDATE` and `DELETE` should be avoided.

### Rule 4: Schema migrations are durability contracts

Migrations should be reviewed as part of the semantic boundary, not as incidental setup scripts.

### Rule 5: Validation, permissions, constraints, and transactions are different layers

Do not expect one layer to replace the others.

Each layer has a different job.

### Rule 6: A guarantee must exist where the failure can happen

If the failure can happen inside PostgreSQL, PostgreSQL must participate in the protection.

If the failure can happen in runtime configuration, configuration boundaries must participate.

If the failure can happen before event admission, Compass validation must participate.

---

## 15. Updated Mental Model

The old mental model was too flat:

```text
Docker + password + database = security concern
```

The corrected model is layered:

```text
Docker Compose
  reproduces local infrastructure

.env / secret injection
  separates real credentials from source code

least privilege
  limits what runtime credentials can do

SQL migrations
  define the durable database contract

Compass validation
  protects semantic truth before history acceptance

transactions
  protect atomic durable writes
```

This model is more useful because it explains which mechanism is responsible for which boundary.

---

## 16. Final Lesson

The final lesson is:

> Modern software safety is not created by one perfect tool.  
> It is created by aligning multiple boundaries so that each one protects the layer it actually controls.

For this project, that means:

- Docker Compose should make local PostgreSQL reproducible.
- `.env` and deployment secrets should keep real credentials outside source code.
- database permissions should reduce runtime blast radius.
- SQL migrations should define durable schema truth.
- Compass validation should prevent invalid events from entering accepted history.
- transactions should keep event append and idempotency record writes consistent.

Stage 3.5B is therefore not just a storage upgrade.

It is the point where local reproducibility, durable schema design, runtime permissions, and semantic correctness begin to meet.

That is the main insight this postmortem preserves.

---

## Suggested Follow-Up

Use this postmortem as a Stage 3.5B companion note.

Possible follow-up work:

- add a concise reference from `docs/postmortems/README.md`
- later extract stable rules into `docs/boundary_notes/environment_isolation_and_defense_in_depth.md`
- document which database role is used for local development versus future production runtime
- keep production role hardening as a future non-goal until the durable baseline is complete
- avoid mixing local Docker credentials with real deployment secrets
