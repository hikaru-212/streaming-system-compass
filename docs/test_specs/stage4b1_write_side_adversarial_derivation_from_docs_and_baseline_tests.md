# Experimental provenance

**Recorded on:** 2026-08-08

Experiment:
Documentation + baseline-test adversarial derivation

Purpose:
Determine whether additional write-side concurrency tests are logically
derivable from historical architecture knowledge plus the first six
characterization scenarios.

Historical timing and evidence boundary:
This derivation experiment was run before the later four advanced Stage 4B.1
PR4 write-side characterization scenarios were supplied as admissible test
evidence for this exercise.

During the derivation run, the evidence set intentionally stopped at:

historical architecture documentation
+
the first six characterization scenarios

The later four advanced PR4 characterization test examples / implementations
were not inspected or admitted as derivation premises in this exercise.

Any later overlap between those executable characterization scenarios and the
candidate obligations derived below should therefore be treated as retrospective
corroboration of reconstructable derivability, not as proof of blind independent
discovery.

Context contamination:
The Codex conversation has previously seen later project material.

Therefore:

this experiment DOES NOT claim blind independent discovery.

It evaluates reconstructable derivability and reasoning quality only.

Allowed argumentative evidence:
historical architecture documentation
+
first six characterization scenarios

Later test implementations, including the later four advanced PR4
characterization scenarios:
not admissible as derivation evidence

Output:
non-authoritative test specification / documentation-quality research artifact

This artifact is generated research evidence. It is not accepted Stage 4B.1
design, executable-test authority, or proof that every scenario can be
implemented with the repository's current test seams.

# Stage 4B.1 write-side adversarial derivation

## 1. Question and method

The question is not whether the six baseline scenarios are locally correct.
They are admitted here as executable facts. The question is whether local
correctness establishes correctness when transactions and admission strategies
compose.

Each proposed scenario must complete this chain:

```text
historical documented invariant
+ baseline execution fact
+ previously unexecuted composition
→ exact uncertainty window
→ falsifiable durable-state oracle
```

The analysis uses no production-source claim and no later test implementation
as a premise. Where PostgreSQL behavior, a synchronization seam, or a result
classification is not established by the admissible evidence, the limitation
is stated rather than silently filled from implementation knowledge.

## 2. Admissible historical documents actually used

All documents below existed at historical HEAD `b70bd09` and were read from
that Git object boundary.

- `docs/adr/0003_concurrency_idempotency_and_retry_safety.md`
  - concurrency control prevents stale observations from becoming successful
    stale writes;
  - request identity prevents one external intent from producing duplicate
    effects;
  - a successful server commit with a missing client response is ambiguous and
    must not authorize blind repetition.
- `docs/adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md`
  - candidate identity is not acceptance;
  - event-log membership grants accepted-history status.
- `docs/adr/0010_transaction_atomicity_vs_concurrency_admission.md`
  - append and idempotency persistence commit or roll back together;
  - transaction atomicity does not select the winning stream writer.
- `docs/adr/0011_validation_mode_vs_validation_placement.md`
  - the preferred material-validation compositions are
    `PRE_TRANSACTION + OPTIMISTIC` and
    `IN_TRANSACTION + PESSIMISTIC`;
  - PRE accepts a stale-observation window and relies on append-time version
    checking;
  - IN pessimistic protects read, validation, and append under a stream lock;
  - both compositions retain append-time continuity checking.
- `docs/adr/0012_two_phase_concurrency_admission.md`
  - pessimistic preparation occurs before protected history loading;
  - the transaction-scoped lock spans validation, append, idempotency
    persistence, and commit or rollback;
  - append-time continuity remains a final guard even after lock acquisition.
- `docs/architecture/transactional_core.md`
  - accepted history is authoritative and replayable;
  - validation and admission answer different questions;
  - duplicate requests must not produce duplicate semantic effects.
- `docs/architecture/write_side_schema_baseline.md`
  - `(order_id, sequence)` is unique in accepted history;
  - `request_id` is the durable idempotency key;
  - an accepted event without its idempotency record, or the reverse, is an
    invalid durability split.
- `docs/boundary_notes/idempotency_module.md`
  - replay requires the same request identity and semantic payload;
  - request idempotency does not replace event-stream continuity.
- `docs/boundary_notes/postgres_concurrency_admission_boundary.md`
  - optimistic admission detects stale writers at append;
  - pessimistic admission serializes the protected section;
  - physical sequence conflicts must become stable admission meaning.
- `docs/boundary_notes/validation_placement_strategy_boundary.md`
  - PRE validation is unsafe without append-time admission;
  - validation placement must not bypass idempotency or change domain legality.
- `docs/implementation_notes/stage_3_5b/pr_breakdown.md`
  - supplies the historical PR4/PR5/PR6 responsibility and ordering record;
  - treats PostgreSQL integration tests as executable architecture claims.
- `docs/postmortems/from_durable_persistence_to_semantic_gate_preservation.md`
  - durable physical success is insufficient if the semantic gate is skipped;
  - post-append idempotency failure is the canonical atomicity boundary.
- `docs/postmortems/pre_transaction_read_cleanup_boundary.md`
  - PRE's preliminary database read must be physically closed before CPU-side
    validation;
  - logical placement labels must agree with connection transaction state.
- `docs/reasoning_notes/autocommit_boundary_and_partial_write_risk.md`
  - statement return is not transaction commit;
  - commit makes the accepted fact durable and rollback removes uncommitted
    partial writes;
  - a transaction-scoped lock is meaningful only while its owning transaction
    covers the protected work.
- `docs/postmortems/from_architectural_warning_to_executable_invariant.md`
  - a concurrency warning is not enforcement until an exact transaction
    schedule and authority oracle make it falsifiable.

## 3. Admitted baseline facts

The six baseline characterizations establish local topology:

1. PRE validation block terminates before business UOW and admission.
2. PRE authoritative replay occurs after preliminary miss, history,
   validation, and business-UOW entry, then rolls back.
3. PRE OCC loss after successful validation returns `STALE_WRITE`, rolls back,
   and performs no automatic reload or retry.
4. IN concrete pessimistic acceptance protects history and validation, then
   appends, persists idempotency, and commits cleanly.
5. IN pessimistic lock non-acquisition terminates before protected history,
   validation, and append.
6. IN pessimistic validation block rolls back before append.

Those facts prove where one invocation stops. They do not by themselves prove:

- compatibility between the two preferred compositions;
- behavior while a competing next-position row exists but is uncommitted;
- the opposite outcomes when that row's owner commits versus rolls back;
- transaction-scoped lock release after a semantically blocked owner;
- recovery when the server's commit decision and the caller's knowledge diverge.

## 4. Ranked scenario summary

| Scenario | Tier | Derivation | Core missing proof |
|---|---|---|---|
| DER-A01 | TIER 1 | DIRECT | Post-append failure cannot leave half of the business UOW durable. |
| DER-A02 | TIER 1 | COMPOSITIONAL | PRE OCC remains safe when the winning writer uses IN pessimistic admission. |
| DER-A03 | TIER 1 | COMPOSITIONAL | A competing PRE append cannot pass while an IN append is uncommitted and later commits. |
| DER-A04 | TIER 1 | COMPOSITIONAL | A rolled-back uncommitted append does not poison the slot for the eventual PRE winner. |
| DER-A05 | TIER 2 | COMPOSITIONAL | Pessimistic protection lasts through validation and is released by rollback. |
| DER-A06 | TIER 3 | SPECULATIVE | Idempotency recovers an accepted result after commit acknowledgement is lost. |

## 5. Additional scenario specifications

### DER-A01 — Post-append idempotency failure removes the candidate from durable history

**Tier:** TIER 1 — must-have correctness characterization

**Invariant under attack**

An append operation returning normally does not make an event durable accepted
history. Event append and idempotency-result persistence are one business UOW
and must commit or roll back together.

#### Premise A — documented architecture fact

- `docs/adr/0010_transaction_atomicity_vs_concurrency_admission.md`,
  **Decision**, assigns coordinated append/idempotency commit and rollback to
  transaction atomicity.
- `docs/reasoning_notes/autocommit_boundary_and_partial_write_risk.md`,
  **Rule 1** and **Updated Mental Model**, state that successful `INSERT`
  execution is not commit, commit makes the fact durable, and rollback removes
  partial uncommitted writes.
- `docs/postmortems/from_durable_persistence_to_semantic_gate_preservation.md`,
  **Physical transaction atomicity**, identifies failure of idempotency
  persistence after append as the concrete atomicity test.

#### Premise B — baseline-test fact

Baseline scenario 4 establishes the normal accepted order:

```text
append returns
→ idempotency persistence returns
→ clean commit
```

No baseline scenario fails between the first two boundaries.

#### Missing composition

The normal IN accepted topology has not been composed with a failure at the
next durable operation after append.

#### Race / uncertainty window

Immediately after append admission returns normally, while the accepted-event
row is still transaction-local, but before idempotency persistence returns.

#### Candidate invariant

There must never be a durable `order_events` row without the corresponding
successful `idempotency_records` row for this business execution.

#### Required adversarial test

Run an otherwise accepting write and deterministically fail idempotency-record
persistence after the real PostgreSQL append has returned. Allow the exception
to leave the UOW. Observe the database from an independent connection after
rollback completes.

#### Expected durable truth

Neither the candidate event nor its request-to-result mapping exists. Existing
history is unchanged and remains replayable.

**Documentation premises:** the three documents above, plus
`docs/architecture/write_side_schema_baseline.md`, **Transaction Grouping
Requirement**.

**First-six-test premises:** baseline 4 proves the normal boundary order;
baselines 5 and 6 prove only earlier rollback terminals.

**Required initial durable state:** an order state from which one command is
individually legal, with no idempotency record for the new request.

**Actor A composition:** `IN_TRANSACTION + concrete pessimistic admission`,
allowing validation and append.

**Actor B composition:** a deterministic test-controlled persistence
collaborator that raises at idempotency-record persistence. Actor B is a fault
injector, not another business command.

**Exact deterministic interleaving point:** the append call has returned an
admitted result; the UOW has not attempted commit; idempotency persistence is
about to execute.

**Competing action:** fail the idempotency persistence operation before it can
return normally.

**Expected winner semantics:** there is no accepted business winner. The
database rollback is the correctness-preserving outcome.

**Expected loser semantics:** Actor A propagates the existing persistence
failure rather than returning an accepted primary result.

**Expected committed database state:** zero new event rows and zero new
idempotency rows for Actor A; all prior accepted rows remain unchanged.

**Guard expected to preserve correctness:** UOW rollback and append/idempotency
transaction grouping.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED**. A fake can show
method ordering, but only a real transaction proves that an already executed
insert disappears on rollback.

**Deterministic synchronization requirement:** a narrow failure injection at
the idempotency persistence boundary after the real append returns. No sleep is
needed.

**Why none of the six baseline tests proves this:** all six terminate before
append or exercise either append rejection or the complete accepted path. None
crosses append successfully and then fails before commit.

**Derivation confidence:** **DIRECT**.

**Derivability result:** **YES — DIRECTLY**. The documentation names this exact
atomicity obligation; the first-six topology supplies its precise injection
boundary.

**Why absence is material:** without this test, the claim that event history
and idempotency memory form one durable write-side result is asserted but not
falsified at its only dangerous intermediate boundary.

---

### DER-A02 — A pessimistic winner invalidates a prevalidated optimistic candidate

**Tier:** TIER 1 — must-have correctness characterization

**Invariant under attack**

The two preferred execution compositions must preserve one accepted-history
continuity rule when they operate concurrently on the same stream. A PRE
candidate validated against version N must not become accepted after an IN
pessimistic writer commits version N+1.

#### Premise A — documented architecture fact

- `docs/adr/0011_validation_mode_vs_validation_placement.md`, **Supported
  Strategy Combinations**, makes PRE optimistic rely on late expected-version
  arbitration and IN pessimistic protect history and validation under a lock.
- The same ADR states that append-time continuity remains required in both
  compositions.
- `docs/boundary_notes/postgres_concurrency_admission_boundary.md`,
  **Optimistic Admission**, requires stale writers to be rejected at append.

#### Premise B — baseline-test fact

Baseline 3 proves that a PRE candidate can lose with `STALE_WRITE` after
validation. Baseline 4 proves that an IN pessimistic execution can accept and
commit. Neither fact identifies their concurrent composition as proven.

#### Missing composition

A PRE candidate's stale window has not been filled specifically by the other
preferred composition while both target the same order.

#### Race / uncertainty window

Actor A has observed version N and returned from PRE validation with `ALLOW`,
but has not entered its business UOW. Actor B can still lock the stream, read
version N, append N+1, persist idempotency, and commit.

#### Candidate invariant

Admission strategy choice must not partition accepted-history authority. Only
one event may occupy N+1, and the stale PRE candidate must not enter history.

#### Required adversarial test

Pause Actor A immediately after PRE validation returns. Execute Actor B through
the concrete IN pessimistic accepted path to clean commit. Resume Actor A and
allow its authoritative idempotency check and optimistic append to run.

#### Expected durable truth

Only Actor B's accepted event occupies N+1 and only Actor B's idempotency result
is new. Actor A leaves no accepted event and no idempotency record.

**Documentation premises:** ADRs 0010, 0011, and 0012; the validation-placement
and concurrency-admission boundary notes; the `(order_id, sequence)` uniqueness
rule in `docs/architecture/write_side_schema_baseline.md`.

**First-six-test premises:** baseline 3 supplies PRE's stale-loss semantics;
baseline 4 supplies IN pessimistic's complete accepted topology.

**Required initial durable state:** one accepted order at stream version N for
which both separately identified requests propose a command legal at N.

**Actor A composition:** `PRE_TRANSACTION + OCC`, with request A and validation
`ALLOW` against version N.

**Actor B composition:** `IN_TRANSACTION + concrete pessimistic admission`,
with different request B against the same order.

**Exact deterministic interleaving point:** after Actor A's validation call
returns and before Actor A enters its business UOW.

**Competing action:** Actor B completes the entire guarded write and clean
commit, advancing accepted history to N+1.

**Expected winner semantics:** Actor B returns the normal accepted result for
its N+1 event.

**Expected loser semantics:** Actor A reaches append-time admission and returns
the current admission-rejected result with `STALE_WRITE`; it does not reload,
retry, or reinterpret Actor B's request as its own success.

**Expected committed database state:** continuous history through N+1 with one
new accepted event, one matching request-B idempotency row, and no request-A
row.

**Guard expected to preserve correctness:** Actor A's append-time OCC/version
continuity check, backed by the unique stream-position boundary.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED**. The claim is
about independent transaction visibility and durable stream arbitration.

**Deterministic synchronization requirement:** a callback/barrier after PRE
validation returns and before business-UOW entry. Actor B's commit completion
releases Actor A.

**Why none of the six baseline tests proves this:** baseline 3 proves a PRE
loser and baseline 4 proves an IN winner in isolation. Individual correctness
does not prove that two admission strategies share the same final authority.

**Derivation confidence:** **COMPOSITIONAL**.

**Derivability result:** **YES — THROUGH COMPOSITIONAL REASONING**.

**Why absence is material:** without it, the architecture has two preferred
correctness-preserving strategies but no executable evidence that their
guarantees compose on one stream.

---

### DER-A03 — An uncommitted pessimistic append that later commits defeats a concurrent PRE append

**Tier:** TIER 1 — must-have correctness characterization

**Invariant under attack**

Append statement return must not be confused with commit, and an optimistic
contender must not occupy the same next stream position while another
transaction's already-inserted row is uncommitted and later becomes durable.

#### Premise A — documented architecture fact

- `docs/reasoning_notes/autocommit_boundary_and_partial_write_risk.md` states
  that successful insert execution is not commit and that commit makes the
  accepted fact durable.
- ADR 0012 says the pessimistic lock and transaction span append,
  idempotency persistence, and commit or rollback.
- ADR 0011 says optimistic admission does not lock early and uses append-time
  continuity as its primary arbitration mechanism.

#### Premise B — baseline-test fact

Baseline 4 separates append, idempotency persistence, and clean commit into
ordered boundaries. Baseline 3 proves stale classification only after a
competing accepted write; it does not establish behavior when the competitor
is not yet committed when the losing append begins.

#### Missing composition

No baseline executes a PRE append while an IN transaction owns an uncommitted
row for the same next stream position.

#### Race / uncertainty window

Actor A's pessimistic append has returned `ADMITTED`, but its idempotency write
and commit have not completed. Actor B has observed only the previously
committed history and begins optimistic append for the same N+1 position.

#### Candidate invariant

Transaction visibility gaps must not allow two accepted events to occupy N+1.
After Actor A commits, Actor B must resolve to stable stale-writer meaning and
must not persist idempotency.

#### Required adversarial test

Pause Actor A after its real append returns and before idempotency persistence.
Run Actor B through PRE validation and into its real append call. Confirm Actor
B's backend has reached the database wait/conflict boundary. Then allow Actor A
to persist idempotency and commit.

#### Expected durable truth

Only Actor A's event and idempotency record are durable. Actor B contributes no
row to either table.

**Documentation premises:** ADRs 0010–0012; the autocommit reasoning note; the
schema's unique `(order_id, sequence)` and transaction-grouping rules.

**First-six-test premises:** baseline 4 proves the owner can be between append
return and commit; baseline 3 supplies the PRE append-loss classification.

**Required initial durable state:** one accepted order at version N; two
different new request IDs whose commands are independently legal at N.

**Actor A composition:** `IN_TRANSACTION + concrete pessimistic admission`,
paused after append admission returns but before idempotency persistence.

**Actor B composition:** `PRE_TRANSACTION + OCC`, which observes committed
version N, validates, and attempts N+1 while Actor A remains uncommitted.

**Exact deterministic interleaving point:** Actor A's append statement has
returned; Actor A has neither persisted idempotency nor committed. Actor B has
entered the PostgreSQL append/uniqueness arbitration for N+1.

**Competing action:** Actor A completes idempotency persistence and commits
while Actor B's append is pending against the uncommitted conflicting row.

**Expected winner semantics:** Actor A returns accepted after clean commit.

**Expected loser semantics:** after Actor A commits, Actor B's append returns
stable `STALE_WRITE`; its write-side result is admission rejected, with no
automatic reload or retry.

**Expected committed database state:** exactly one N+1 event, belonging to
Actor A; one matching Actor-A idempotency row; no Actor-B durable rows.

**Guard expected to preserve correctness:** PostgreSQL stream-position
uniqueness plus append-time OCC conflict translation. Actor A's advisory lock
does not by itself authorize a claim about an optimistic actor that does not
acquire it.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED**. MVCC visibility,
unique-index arbitration against an uncommitted row, and post-commit conflict
translation cannot be established by a fake.

**Deterministic synchronization requirement:** two independent connections;
an after-append/before-idempotency barrier for Actor A; and database-visible
confirmation that Actor B is waiting at the conflicting append boundary before
Actor A is released. A PostgreSQL wait-state or lock observation is preferable
to timing assumptions.

**Why none of the six baseline tests proves this:** none starts the losing
append before the winning transaction commits. The distinction between
statement completion and transaction finality is therefore untested by those
six facts.

**Derivation confidence:** **COMPOSITIONAL**.

**Derivability result:** **YES — THROUGH COMPOSITIONAL REASONING**. The schedule
is reconstructable, although the exact PostgreSQL wait-state probe is a harness
detail not supplied by the documents.

**Why absence is material:** ordinary serial competition can pass even if the
implementation mishandles an uncommitted conflicting row. This is the commit
branch of the architecture's explicit statement-versus-finality distinction.

---

### DER-A04 — Rollback of an uncommitted pessimistic append releases the stream position to the PRE contender

**Tier:** TIER 1 — must-have correctness characterization

**Invariant under attack**

An insert that returned inside a transaction that later rolls back must not
remain accepted truth or permanently poison its stream position. A concurrent
valid contender must be able to become the eventual winner after rollback.

#### Premise A — documented architecture fact

- The autocommit reasoning note states that rollback removes uncommitted
  partial writes.
- ADR 0010 and the schema baseline require event/idempotency atomicity.
- ADR 0012 makes the pessimistic lock transaction-scoped through rollback and
  retains append-time continuity as the final stream guard.

#### Premise B — baseline-test fact

Baseline 4 exposes the append-returned-before-commit boundary. Baselines 5 and
6 prove rollback before append. No baseline rolls back after append has
returned, and none lets another composition contend during that interval.

#### Missing composition

The uncommitted-row schedule from DER-A03 needs its opposite owner finality:
rollback instead of commit.

#### Race / uncertainty window

Actor A has inserted N+1 transaction-locally and holds the pessimistic
transaction. Actor B begins optimistic append for N+1. Actor A then fails at
idempotency persistence and rolls back.

#### Candidate invariant

After rollback, Actor A must have no accepted identity, event row, idempotency
row, or surviving lock claim. Actor B may then be admitted against still-current
durable version N.

#### Required adversarial test

Pause Actor A after append returns. Start Actor B and establish that its append
has reached the database conflict/wait boundary. Inject Actor A's idempotency
persistence failure, allow UOW rollback, then let Actor B finish normally.

#### Expected durable truth

Exactly Actor B's N+1 event and idempotency mapping are durable. Nothing from
Actor A remains.

**Documentation premises:** ADRs 0010–0012;
`docs/reasoning_notes/autocommit_boundary_and_partial_write_risk.md`;
`docs/architecture/write_side_schema_baseline.md`.

**First-six-test premises:** baseline 4 supplies the intermediate append-return
boundary; baseline 3 supplies PRE append behavior; none supplies post-append
rollback.

**Required initial durable state:** one accepted order at version N; different
new request IDs for two commands legal at N.

**Actor A composition:** `IN_TRANSACTION + concrete pessimistic admission`,
with append allowed and a deterministic idempotency-persistence failure.

**Actor B composition:** `PRE_TRANSACTION + OCC`, validated against committed
version N and attempting N+1 while Actor A remains uncommitted.

**Exact deterministic interleaving point:** Actor A's append has returned but
idempotency and commit have not; Actor B has entered append-time database
arbitration for the same N+1 slot.

**Competing action:** fail Actor A's idempotency persistence, causing rollback
of its event and release of transaction-scoped resources.

**Expected winner semantics:** Actor B's append is admitted after Actor A's
rollback and Actor B returns accepted after its own clean commit.

**Expected loser semantics:** Actor A propagates the persistence failure and
does not produce a normal accepted result.

**Expected committed database state:** continuous history with one N+1 event
from Actor B; one Actor-B idempotency row; no Actor-A event or idempotency row.

**Guard expected to preserve correctness:** Actor A's UOW rollback, PostgreSQL
transactional uniqueness arbitration, and Actor B's append-time continuity
check.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED**. The essential
claim is that a competing insert can proceed correctly after the conflicting
uncommitted row rolls back.

**Deterministic synchronization requirement:** the same two-connection
append/wait barrier as DER-A03, plus a deterministic failure at Actor A's
idempotency boundary. Do not infer blocking from elapsed time.

**Why none of the six baseline tests proves this:** the six show rollback only
before append and clean commit only after full persistence. They do not prove
that a returned append is removed or that a waiting cross-strategy actor can
become the winner after rollback.

**Derivation confidence:** **COMPOSITIONAL**.

**Derivability result:** **YES — THROUGH COMPOSITIONAL REASONING**.

**Why absence is material:** this is the rollback half of the same
transaction-finality state tested by DER-A03. Testing only the commit half
would not prove that an aborted owner cannot leave a false accepted-history
obstacle.

---

### DER-A05 — Pessimistic lock spans semantic validation and is released after validation rollback

**Tier:** TIER 2 — strong adversarial hardening

**Invariant under attack**

The transaction-scoped pessimistic lock must protect the entire claimed
critical section, including validation, but lock ownership must not turn a
semantically blocked candidate into accepted history. Rollback must release the
lock cleanly.

#### Premise A — documented architecture fact

- ADR 0012 says preparation precedes history and the lock is held across
  history, validation, append, idempotency persistence, and commit or rollback.
- ADR 0011 says IN pessimistic protects validation but append-time continuity
  remains required.
- The autocommit reasoning note says the lock's physical lifetime must match
  the protected transaction scope.

#### Premise B — baseline-test fact

Baseline 5 proves non-acquisition stops a contender early. Baseline 6 proves an
owner can acquire protection and then block in validation. Neither composes the
two executions or proves lock release after the owner's rollback.

#### Missing composition

One execution owns the lock but is destined to be semantically blocked while a
second IN pessimistic execution attempts the same stream.

#### Race / uncertainty window

Actor A has acquired the stream lock and loaded protected history, then pauses
inside deterministic validation before returning `BLOCK`. Actor B attempts
pessimistic preparation during that pause.

#### Candidate invariant

Actor B cannot enter protected history while Actor A owns the lock. Actor A's
validation block creates no durable rows. Once Actor A rolls back, the lock is
not orphaned and a fresh transaction can acquire it.

#### Required adversarial test

Pause Actor A in its validation callback after protected history was loaded.
Run Actor B against the same stream and require preparation non-acquisition.
Release Actor A to return `BLOCK` and roll back. Finally, use a fresh
transactional lock probe on the same stream to prove the lock is available;
the probe is verification, not automatic retry.

#### Expected durable truth

After Actor A and Actor B terminate, neither has added an event or idempotency
record. The pre-existing order history is unchanged.

**Documentation premises:** ADRs 0011 and 0012; PostgreSQL concurrency-admission
boundary; autocommit/transaction-boundary reasoning note.

**First-six-test premises:** baselines 5 and 6 establish the two local terminal
paths.

**Required initial durable state:** an order for which Actor A can construct a
candidate, plus distinct unprocessed request identities for A and B.

**Actor A composition:** `IN_TRANSACTION + concrete pessimistic admission`,
with validation configured to return `BLOCK` after the test barrier releases.

**Actor B composition:** another `IN_TRANSACTION + concrete pessimistic`
execution targeting the same order while A is paused.

**Exact deterministic interleaving point:** after Actor A's pessimistic
preparation and protected history observation, while its validation call has
not returned.

**Competing action:** Actor B attempts stream preparation on an independent
connection.

**Expected winner semantics:** Actor A is the critical-section owner, not a
business winner; it returns validation blocked and rolls back.

**Expected loser semantics:** Actor B returns admission rejected with
preparation-level non-acquisition and never loads history, validates, or
appends.

**Expected committed database state:** no new event or idempotency rows. A
post-settlement transaction can acquire the stream lock, proving rollback
released it.

**Guard expected to preserve correctness:** transaction-scoped pessimistic
admission during overlap; validation block and rollback for Actor A; rollback
lock release at settlement.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED**. A fake lock does
not prove transaction-scoped ownership or release across connections.

**Deterministic synchronization requirement:** a validation callback/barrier
inside Actor A, independent connections, and a post-rollback lock probe. No
sleep-based assumption is needed.

**Why none of the six baseline tests proves this:** baseline 5 need not have a
write-side owner paused inside validation, while baseline 6 need not expose a
real contender. Their composition is the lock-lifetime claim.

**Derivation confidence:** **COMPOSITIONAL**.

**Derivability result:** **YES — THROUGH COMPOSITIONAL REASONING**.

---

### DER-A06 — Lost commit acknowledgement is recovered by durable idempotency truth

**Tier:** TIER 3 — useful but speculative

**Invariant under attack**

A caller's failure to receive commit acknowledgement must not authorize the
same external request to create a duplicate semantic effect. Durable event and
idempotency truth, not the first caller's local uncertainty, governs recovery.

#### Premise A — documented architecture fact

- `docs/adr/0003_concurrency_idempotency_and_retry_safety.md`, **Ambiguous
  Commit Handling**, explicitly describes a commit that may succeed while the
  worker misses the response and requires request identity to recover.
- The schema baseline links the successful idempotency record to accepted
  history in the same durability group.

#### Premise B — baseline-test fact

Baseline 4 proves normal acceptance only through clean commit return. Baseline
2 proves authoritative replay after a prior result is visible. None places a
transport failure between the database commit decision and client
acknowledgement.

#### Missing composition

The accepted transaction and authoritative replay paths have not been composed
across a lost commit acknowledgement.

#### Race / uncertainty window

After PostgreSQL has received the owner's `COMMIT`, but before the caller has a
reliable response identifying whether commit became durable.

#### Candidate invariant

Once quiescent, the same request and payload produce exactly one accepted event
and one idempotency record regardless of the first caller's uncertainty.

#### Required adversarial test

Use deterministic infrastructure capable of separating the backend commit
decision from delivery of the client acknowledgement. Then issue the same
request and payload from Actor B.

Two controlled subcases are required:

1. backend commit is confirmed durable, acknowledgement is lost;
2. backend transaction is confirmed not committed.

#### Expected durable truth

In both subcases there is exactly one semantic effect after recovery. If Actor
A committed, Actor B replays the prior accepted result. If Actor A did not
commit, Actor B may execute and commit the operation once.

**Documentation premises:** ADR 0003; idempotency boundary note; schema
transaction-grouping requirement.

**First-six-test premises:** baseline 4 provides the commit boundary; baseline
2 provides authoritative replay after durable visibility.

**Required initial durable state:** an order on which the request is legal and
no prior idempotency record for that request.

**Actor A composition:** either preferred accepted write composition, with a
fault at commit acknowledgement delivery.

**Actor B composition:** a later execution of the same request identity and
semantically identical payload.

**Exact deterministic interleaving point:** after the server has received the
commit decision but before the application receives a trustworthy response.

**Competing action:** suppress or sever the commit acknowledgement, establish
the intended backend outcome using independent authority, then submit Actor B.

**Expected winner semantics:** if Actor A committed, its accepted event is the
single winner and Actor B returns replay. If Actor A did not commit, Actor B is
the single accepted execution.

**Expected loser semantics:** no second accepted effect exists. Actor A may
have no normal application result because its transport outcome is ambiguous.

**Expected committed database state:** exactly one accepted event and exactly
one matching idempotency record for the request, with no split durability.

**Guard expected to preserve correctness:** atomic event/idempotency commit and
authoritative idempotency lookup on the recovery execution.

**Required infrastructure level:** **REAL_POSTGRES_REQUIRED** plus a
deterministic network or protocol fault harness. Ordinary monkeypatching before
or after `commit()` does not prove the ambiguous interval.

**Deterministic synchronization requirement:** a proxy, driver fault seam, or
server-coordinated harness that can prove the backend commit outcome while
withholding the response. The historical documentation does not choose such a
harness.

**Why none of the six baseline tests proves this:** clean commit return and
ordinary replay exclude the epistemic gap where the database and caller may
know different things.

**Derivation confidence:** **SPECULATIVE** with respect to executable harness
support, although the invariant itself is directly documented.

**Derivability result:** **PARTIALLY**. The scenario and durable oracle are
directly derivable; deterministic implementation requires infrastructure
knowledge outside the admitted evidence.

## 6. Why these tiers

### TIER 1

- **DER-A01:** without a post-append failure, transaction atomicity is never
  challenged after one half of the durability group has physically executed.
- **DER-A02:** without a mixed-strategy winner/loser schedule, the two preferred
  compositions are only individually correct; shared authority is unproven.
- **DER-A03:** without the commit branch of the uncommitted-row schedule,
  statement return may be mistaken for either absence or durable truth by a
  contender.
- **DER-A04:** without the rollback branch, a transaction-local insert could
  leave a false obstacle or prevent the legitimate eventual writer even though
  the owner never committed.

### TIER 2

DER-A05 strongly verifies the physical lifetime claimed for pessimistic
protection. The six baseline cases already establish its two local terminals,
so the missing evidence is compositional hardening rather than an entirely
unproven durability group.

### TIER 3

DER-A06 is architecturally important, but the admitted material does not define
a deterministic commit-acknowledgement fault harness or a business commit
ambiguity result contract. It should remain a specification until those
questions receive an explicit owner.

## 7. Categories investigated but not promoted to separate scenarios

### Same-strategy PRE versus PRE

The PRE stale-candidate schedule is already a baseline fact, and the historical
OCC documents explicitly describe same-version competitors. Merely replacing
the competitor in baseline 3 with another PRE invocation would be a shallow
variant unless it introduced an uncommitted-row or idempotency race. DER-A03
and DER-A04 exercise the stronger missing state.

### Same-request concurrent MISS on both executions

The documents require duplicate-effect prevention and the baseline proves
replay after a prior commit is visible. They do not determine the exact public
loser classification when two transactions both observe `MISS` before either
idempotency record is committed and stream-position and request-key constraints
race with each other. The durable oracle—one effect—is clear, but whether the
loser should be replay, admission rejected, idempotency conflict, or a later
reclassification is not derivable without a more explicit contract. This is a
documented gap, not a promoted test with an invented verdict.

### Conflicting payload under the same request identity

The idempotency boundary directly requires conflict rather than replay, but the
six baseline extension question adds no new concurrency composition unless the
two request payloads overlap before either commits. That simultaneous case has
the same under-specified loser-classification problem described above.

### PRE preliminary-read cleanup failure

The cleanup postmortem supplies a strong connection-state invariant. It also
explicitly defers cleanup-failure classification and pooled-connection policy.
An additional production-grade failure test cannot be specified without
inventing those owners. Ordinary cleanup ordering is important but is not one
of the highest-value compositional scenarios selected here.

### Competing different legal transitions

The historical architecture discusses generic competing legal operations, but
the admitted baseline describes only the current create/pay write topology and
does not establish another simultaneously legal transition for the same order.
No cancellation/refund scenario is invented.

## Documentation Operability Assessment

### Which documents supplied useful semantic invariants?

The most productive semantic documents were:

- ADR 0003 for the separation of idempotency and concurrency and for ambiguous
  commit recovery;
- ADR 0008 for the distinction between candidate identity and accepted truth;
- ADR 0010 for atomicity versus admission;
- the write-side schema baseline for the durable stream-position and
  request-identity constraints;
- the semantic-gate preservation postmortem for the rule that physical success
  alone does not authorize accepted history.

These documents produce durable-state oracles rather than merely naming
components.

### Which documents supplied execution-order knowledge?

ADR 0011, ADR 0012, the validation-placement boundary, and the Stage 3.5B PR
breakdown supplied the critical orderings:

```text
PRE:
observe / validate
→ later append-time OCC

IN pessimistic:
transaction / idempotency
→ lock
→ protected history / validation
→ append
→ idempotency persistence
→ commit or rollback
```

The autocommit reasoning note added the physical distinction among statement
execution, transaction commit, and rollback.

### Which facts came only from the first six tests?

The six baselines contributed execution precision not fully guaranteed by the
older conceptual flows:

- PRE has both preliminary and authoritative idempotency boundaries;
- PRE validation block never reaches the business UOW;
- PRE OCC conflict has no automatic reload, retry, or second attempt;
- concrete pessimistic non-acquisition terminates before history and
  validation;
- append, idempotency persistence, and clean commit are distinct normal-return
  checkpoints;
- the current normal terminal meanings for replay, lock non-acquisition,
  validation block, stale append, and acceptance are typed.

### What became visible only after combining both sources?

Three important obligations emerged only compositionally:

1. the two preferred strategies must arbitrate one stream even though only one
   of them participates in the pessimistic advisory-lock protocol;
2. an optimistic contender can interact with a row that has been inserted but
   is not yet committed;
3. the correct eventual winner changes when that row's owner commits versus
   rolls back.

The architecture documents name all the boundaries, and the baseline topology
locates the pauses. Neither source alone gives the complete adversarial
schedule.

### Was cross-strategy concurrency derivable?

**Yes, through compositional reasoning.** ADR 0011 explicitly makes both
compositions preferred, assigns them different protection timing, and retains
one append-time continuity boundary. The six baselines establish executable
local paths. It is therefore reasonable—without knowing a later test
implementation—to require them to compete on the same stream.

### Was append-returned-before-commit behavior derivable?

**Yes.** The autocommit reasoning note directly says statement success is not
transaction success. Baseline 4 independently orders append return,
idempotency persistence, and clean commit. DER-A03 and DER-A04 follow by giving
another connection access to that intermediate state and exploring both owner
finalities.

### Which race windows required substantial inference?

The largest inference was PostgreSQL arbitration when a PRE optimistic append
targets a stream slot already inserted by an uncommitted IN transaction. The
documents require uniqueness and final stale-write meaning, but they do not
describe the exact wait event, constraint-check timing, or driver behavior.
The test oracle is strong; the synchronization implementation needs database
expertise.

### Which important questions remain impossible to answer from the admitted evidence?

- What exact result should a simultaneous same-request loser receive when both
  authoritative checks saw `MISS` before either transaction committed?
- Which test seam can pause after a real append statement returns but before
  idempotency persistence without changing production behavior?
- Which PostgreSQL wait-state observation is stable enough for deterministic
  synchronization across supported driver/database versions?
- What transaction isolation level is an explicit public contract rather than
  an incidental default?
- How should business commit ambiguity be represented, if at all, when the
  commit call raises or loses its response?
- How should a failed PRE cleanup rollback interact with future connection-pool
  invalidation?
- Does any future consumer require cross-attempt classification? That belongs
  outside this single-execution audit.

### Where did documentation describe responsibilities without enough ordering?

The idempotency documents are strong about durable replay/conflict semantics
but weak about two first-seen transactions overlapping before either record is
visible. ADR 0003 describes recovery after ambiguous commit but not a
deterministic fault mechanism. The schema defines uniqueness but not how
constraint waits should be observed by tests. These are the main places where
responsibility is clear and executable scheduling is not.

### What documentation would improve future adversarial synthesis?

1. A short transaction-visibility schedule for the authoritative business UOW:
   append returned / row uncommitted / other-connection observation / commit or
   rollback.
2. An explicit cross-strategy compatibility statement: pessimistic locks
   coordinate participating pessimistic writers, while append-time continuity
   remains the common arbitration boundary for all writers.
3. A contract for simultaneous same-request first execution, including loser
   classification after both initial idempotency checks return `MISS`.
4. A supported deterministic PostgreSQL synchronization toolbox: callbacks,
   backend identifiers, lock/wait-state probes, and forbidden sleep-based
   patterns.
5. A separate business-transaction commit-ambiguity boundary that does not
   borrow governance-receipt transaction-owner vocabulary.
6. A table connecting each architectural “must” to an executable schedule,
   durable oracle, or explicit deferred risk.

### Overall operability judgment

The documentation is operational enough to design high-value adversarial tests,
not merely to summarize architecture. It supplies stable semantic ownership,
preferred execution compositions, transaction grouping, lock lifetime, and
accepted-history authority. The first six baselines turn those general flows
into pauseable checkpoints.

The strongest new scenarios are therefore reconstructably derivable through
composition. The documentation is not sufficient to choose every harness seam
or every simultaneous-race result classification. Its quality is strongest at
the invariant/oracle level and weaker at the deterministic scheduling and
commit-ambiguity delivery levels.

## 8. Experimental result

Additional scenarios proposed: **6**.

Tier distribution:

- TIER 1: **4**
- TIER 2: **1**
- TIER 3: **1**

Derivation-confidence distribution:

- DIRECT: **1**
- COMPOSITIONAL: **4**
- SPECULATIVE: **1**

The core answer is:

```text
historical architecture documentation
+ first six execution characterizations
→ enough evidence for source-independent adversarial specifications
  at the invariant, interleaving, and durable-oracle levels

but

→ not enough evidence for every synchronization implementation,
  simultaneous-idempotency loser verdict, or commit-ambiguity delivery contract
```
