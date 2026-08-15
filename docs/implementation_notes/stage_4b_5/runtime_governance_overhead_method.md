# Stage 4B.5 Runtime Governance Overhead Characterization Method

[← Back to Stage 4B.5](README.md)

## Status

```text
source-grounded design
= COMPLETE

benchmark harness, evidence schema, and safety checks
= IMPLEMENTED / AWAITING REVIEW

canonical recorded benchmark
= NOT RUN
```

No result is claimed by this method note. The canonical fixed runs require a
separate human decision after review of the harness, tests, evidence schema,
and test-database safety boundary.

---

## Question

The characterization asks:

```text
How much incremental runtime cost does the machine-readable Stage 4B.5
governance path introduce, and is that cost material relative to normal
PostgreSQL write-side execution?
```

The answer must distinguish:

- semantic-path micro latency;
- external PostgreSQL end-to-end latency;
- raw absolute latency and block/permutation batch comparisons;
- absolute and relative batch-level estimates against A;
- directly timed same-invocation C composition latency;
- measurement noise and block variation;
- environment differences and historical-comparability limits.

The objective is not to prove that governance has zero cost.

---

## A-Control Isolation Decision

### Compared options

| Concern | Historical worktree / subprocess | Verified Git-blob bundle / subprocess |
| --- | --- | --- |
| Historical/current import contamination | Low if the entire worktree and process are isolated | Low for the protected modules; fresh A process rejects prior protected imports |
| Benchmark harness duplication | Requires a compatible runner entry point in, or copied into, the historical checkout | One current orchestrator and worker protocol; only historical production modules are reconstructed |
| Same Python interpreter | Possible, but the worktree must deliberately invoke the current repository interpreter | Required and verified for A/B/C workers |
| Same PostgreSQL instance | Possible through the same guarded environment | Required and verified by PostgreSQL database OID and runtime facts |
| Workload parity | Requires cross-checkout serialization and duplicated setup code | One command/scenario protocol drives all three surfaces |
| Maintenance complexity | Higher: worktree lifecycle, path routing, cleanup, and cross-version runner compatibility | Lower: one manifest, three blobs, one loader, one worker protocol |
| Provenance clarity | Commit identity is direct, but runner provenance spans two checkouts | Commit, path, Git blob, and SHA-256 are explicit per protected module |
| Historical production semantics | Preserved if no historical source is changed | Preserved: exact historical bytes execute under canonical module names |

### Chosen design

The A control uses the narrower verified Git-blob bundle in a dedicated
subprocess.

It is a source-bundle form of Option 2, with one additional narrowing: the
historical bytes are not copied into mutable `.source` files. The A worker reads
the pinned blobs from the local Git object database and verifies:

```text
source commit
+ commit:path Git blob identity
+ SHA-256 of exact blob bytes
```

before compiling them under these canonical module names:

```text
src.compass.transition.validators
src.compass.transition.runtime
src.pipeline.transactional.postgres_write_side
```

The source identity is recorded in
`tests/fixtures/stage4b5_runtime_governance_overhead/provenance.json`.

The historical commit is:

```text
0bd2f515bcc49e8e1f0e9d2f9dba4a294adadd0d
```

The source-diff audit found that the protected A execution closure changed only
in those three modules. The separately changed Stage 4B.2 measurement module is
not imported by the normal unmeasured APIs used by this experiment. Shared
domain, admission, storage, type, configuration, trace-instrumentation, and
idempotency dependencies in the active execution closure were unchanged across
the audited source interval.

The process refuses A construction if any protected current module was already
imported. It first imports all required parent packages, then rechecks both
`sys.modules` and parent-package child attributes before installing any
historical child. It repeats that check between each dependency-ordered module
installation. A parent import that introduces a current protected child
therefore fails closed. B and C run in their own processes. This removes current
validator/runtime/write-side contamination without creating a Git worktree,
changing Git metadata, or maintaining a second benchmark implementation.

This design does not alter historical production semantics. Its deliberate
limitation is that audited-unchanged transitive dependencies load from the
current checkout. Their source parity is therefore an evidence prerequisite,
not an assumption that may silently drift.

---

## Compared Surfaces

```text
A
= historical Stage 4B.2 source behavior reconstructed from canonical Git blobs
= ValidationRuntime.decide(...)
= historical PostgresWriteSideResult terminal boundary

B
= current Stage 4B.5 evidence-aware behavior
= FullProof rule evidence
+ ValidationRuntime carrier
+ PostgreSQL write-side propagation
= current PostgresWriteSideResult terminal boundary

C
= B
+ map_postgres_write_side_result_to_semantic_rule_feedback(...)
```

The comparison interpretations are:

```text
B - A
= difference of matched block/permutation batch medians
= evidence-aware validation/runtime/write-side propagation estimate

C - B
= primary: directly timed same-invocation C composition lap
= Stage 4A mapping plus PR7 terminal semantic-refinement composition estimate

C - B full-path subtraction
= secondary, noise-sensitive descriptive batch comparison only

C - A
= difference of matched block/permutation batch medians
= total Stage 4B.5 machine-readable semantic-governance estimate
```

`B - A` is not described as only `OrderRuleViolationEvidence` construction.
It includes the complete evidence-aware validation, carrier, result, and
write-side propagation difference inside the selected boundary.

---

## Fixed Scenario Matrix

### Semantic-path micro layer

The four cells are not pooled:

1. `CREATE_ACCEPTED`
2. `CREATE_VALIDATION_BLOCKED`
3. `PAY_ACCEPTED`
4. `PAY_VALIDATION_BLOCKED`

The micro boundary excludes candidate construction. It includes validation,
policy, and construction of the surface-specific `PostgresWriteSideResult`.
C additionally includes the PR7 mapper. This layer isolates the semantic and
result-composition path from PostgreSQL.

### PostgreSQL end-to-end layer

The eight cells are not pooled:

| Command | Placement | Terminal |
| --- | --- | --- |
| CREATE | PRE_TRANSACTION | ACCEPTED |
| CREATE | PRE_TRANSACTION | VALIDATION_BLOCKED |
| CREATE | IN_TRANSACTION | ACCEPTED |
| CREATE | IN_TRANSACTION | VALIDATION_BLOCKED |
| PAY | PRE_TRANSACTION | ACCEPTED |
| PAY | PRE_TRANSACTION | VALIDATION_BLOCKED |
| PAY | IN_TRANSACTION | ACCEPTED |
| PAY | IN_TRANSACTION | VALIDATION_BLOCKED |

`PRE_TRANSACTION` uses the normal current PostgreSQL optimistic/OCC admission
composition. `IN_TRANSACTION` uses the normal concrete PostgreSQL pessimistic
admission composition.

PAY setup creates its required accepted `CREATED` history outside the timed
region. Every invocation uses a unique request and order identity.

### Deterministic blocked workload

The same benchmark-owned perturbation drives A, B, and C:

```text
accepted-history-derived ValidationContext.actual_prev_version + 1
```

The candidate sequence therefore fails the first FullProof sequence-continuity
branch. The benchmark subclass changes only context construction for the
blocked workload; production source is not modified.

For A, verification requires ordinary historical `VALIDATION_BLOCKED` behavior
and explicitly forbids a claim of Stage 4B.5 typed evidence.

For B and C, verification requires the exact typed identity:

```text
order.transition.sequence-matches-accepted-next-version
```

For accepted B/C paths, exact evidence propagation is present but observed
violation is `None`. For C, `rule_refinement` must be the identical violation
object on validation block and must be `None` on accepted outcomes.

---

## Timing Boundaries

All timing uses `time.perf_counter_ns()`.

### Micro

```text
A start
→ historical ValidationRuntime.decide(...)
→ historical PostgresWriteSideResult constructed
→ stop

B start
→ current ValidationRuntime.decide_with_rule_evidence(...)
→ current evidence-aware PostgresWriteSideResult constructed
→ stop

C start
→ B path
→ producer_return
→ map_postgres_write_side_result_to_semantic_rule_feedback(...)
→ stop
```

Every C observation records three exact fields:

```text
producer_elapsed_ns
= producer_return - start

composition_elapsed_ns
= stop - producer_return

total_elapsed_ns
= stop - start
= producer_elapsed_ns + composition_elapsed_ns
```

Candidate and validation-context construction, UUID construction, and
post-return verification remain outside the timer.

### PostgreSQL end to end

```text
A start
→ normal historical create_order(...) or pay_order(...)
→ historical PostgresWriteSideResult
→ stop

B start
→ normal current create_order(...) or pay_order(...)
→ current PostgresWriteSideResult
→ stop

C start
→ normal current create_order(...) or pay_order(...)
→ current PostgresWriteSideResult
→ producer_return
→ map_postgres_write_side_result_to_semantic_rule_feedback(...)
→ stop
```

The `producer_return` timestamp is benchmark-owned and lies immediately after
the normal producer returns. The composition lap changes no production source
or behavior. It directly measures the PR7 call in the same C invocation, so
PostgreSQL write noise is not subtracted to estimate the primary C-B semantic
composition cost.

The primary timer does not use
`create_order_with_measurement(...)`, `pay_order_with_measurement(...)`, traced
delivery, or any active Stage 4B.2 detailed measurement wrapper. This avoids
their observer effect and prevents an incomplete C boundary.

Database reset, PAY seeding, identity setup, durable-history verification, and
connection-state verification are outside timing.

YAML parsing and YAML projection never enter any process timing boundary. There
is no production YAML parsing.

---

## Fixed Schedule

All six permutations of A/B/C are executed in a fixed seeded order.

### Micro

```text
5 complete untimed warmup blocks
30 recorded blocks
6 A/B/C permutations in every block
100 repetitions per permutation
fixed seed 4500617
no adaptive extension
```

The fixed recorded population is `216,000` samples:

```text
4 scenarios × 30 blocks × 6 permutations × 3 surfaces × 100 repetitions
```

Each exact scenario/surface cell contains `18,000` samples.

### PostgreSQL

```text
5 untimed warmup cycles
30 recorded blocks
6 A/B/C permutations in every recorded block
10 repetitions per permutation
reset/setup/verification outside timing
fixed seed 4500617
no adaptive extension
```

Each warmup cycle exercises all eight cells and all three surfaces once. The
fixed recorded population is `43,200` samples:

```text
8 scenarios × 30 blocks × 6 permutations × 3 surfaces × 10 repetitions
```

Each exact scenario/surface cell contains `1,800` samples.

---

## Statistics

Raw absolute distributions and block/permutation comparison distributions are
reported separately for every unpooled cell.

The surface runner executes batches, not paired invocations:

```text
A repetitions
→ B repetitions
→ C repetitions
```

Equal repetition indexes across those batches are schedule coordinates only.
They are not statistical pairs. The experimental comparison unit is one
`scenario + recorded block + surface permutation` batch. Each surface's
repetitions are first reduced to an empirical nearest-rank batch median.

Each scenario therefore has:

```text
30 recorded blocks × 6 permutations
= 180 comparison units
```

The harness uses empirical nearest-rank percentiles:

- raw absolute p50 and p95 for both layers;
- raw absolute and raw C composition-lap p99 for the micro layer;
- batch-comparison p50 and p95;
- batch-comparison p99 withheld because 180 units provide only two
  observations at the one-percent tail;
- PostgreSQL p99 withheld because the predeclared fixed per-cell population is
  below the `10,000`-observation credibility threshold;
- IQR and MAD;
- every recorded block median and a distribution of block medians;
- fixed-seed, 2,000-repetition recorded-block cluster-bootstrap confidence
  interval for each reported distribution median.

For each bootstrap repetition, the harness samples recorded blocks with
replacement, retains every comparison or invocation unit in each selected
block, concatenates that complete resampled population, and calculates its
empirical nearest-rank median. It does not first reduce blocks to medians and
does not independently resample permutation or invocation units. The bootstrap
therefore targets the same pooled-unit median as the reported p50 while using
the recorded block as the dependence-preserving resampling cluster.

The comparison construction is mandatory:

```text
group repetitions by scenario + block + permutation + surface
→ calculate one surface batch median
→ match A/B/C batch medians by scenario + block + permutation
→ calculate B-A and C-A batch estimates
→ use C composition batch median as primary C-B estimate
→ retain independent C-B full total difference as secondary only
→ percentile the resulting 180-unit comparison distributions
```

The harness never reports `p95(B) - p95(A)` as p95 overhead.

Every relative estimate uses the matched A batch median as its reference. This
includes the primary same-invocation C composition lap and the secondary
full-path C-B comparison, so reported relative overhead remains directly
comparable to the accepted A baseline. Negative batch differences remain
visible and are not clamped to zero.

---

## Safety and Evidence Validity

Canonical execution requires:

- execution inside a Python virtual environment; the environment may live
  outside this worktree;
- the exact `sys.executable`, Python version, and Python implementation recorded;
- a clean working tree so B/C have an unambiguous source identity;
- an explicit canonical-run confirmation string;
- an unused run identity;
- exact A commit/blob/SHA-256 verification;
- the identical `sys.executable`, Python version, and implementation for A/B/C
  workers;
- complete fixed sample populations;
- exact equality with the configured scenario/block/permutation/repetition/
  surface coordinate universe;
- no missing, duplicate, additional, or out-of-range coordinate;
- complete A/B/C batch units for every block/permutation comparison;
- exact outcome and typed-evidence verification;
- positive integer timer values;
- no adaptive retries, replacements, or extensions.

PostgreSQL execution additionally requires:

- `TEST_DATABASE_URL` to exist without being written to output;
- `current_database()` to end exactly in `_test` before reset;
- required tables through migration `007`;
- autocommit disabled;
- the same database OID, PostgreSQL version, psycopg version, isolation, and
  schema level across A/B/C;
- an `IDLE` connection immediately before and after timed invocation;
- durable accepted/blocked history verification outside timing.

The runner does not read `.env` files, emit a connection string, record the
environment variable value, run migrations, change PostgreSQL configuration,
or invoke retry governance.

Evidence publication uses a repository-local publication lock, stages complete
files, atomically renames the validated directory, refuses an existing final
directory, and scans every document for connection-secret markers. A validated
run writes:

```text
manifest.json
samples.jsonl
batch_summaries.jsonl
batch_comparisons.jsonl
aggregates.json
```

under one immutable run namespace.

---

## Recorded Environment Evidence

The manifest records at minimum:

- run and evidence-schema identity;
- exact A commit/module/path/blob/SHA-256 provenance;
- B/C commit, branch, and clean-tree state;
- worker source-module identities;
- Python version, implementation, and executable;
- psycopg version;
- PostgreSQL server version and guarded database OID;
- OS, release, architecture, processor string, and logical CPU count when
  available;
- timer identity, implementation, monotonicity, adjustability, and resolution;
- garbage-collection enabled state for the orchestrator and workers;
- migration level;
- transaction isolation and autocommit;
- exact scenario definitions;
- timing boundaries and excluded setup;
- warmup, recorded-block, repetition, permutation, seed, and bootstrap counts;
- raw invocation laps, batch summaries, batch comparisons, aggregate
  distributions, and limitations.

Hostnames, usernames, credentials, connection strings, and
`TEST_DATABASE_URL` are not evidence fields.

---

## Human Canonical Execution

Do not run these commands until the harness and tests have been reviewed, the
chosen interpreter is running inside an existing virtual environment, and the
reviewed source is committed with a clean working tree. The virtual environment
does not need to live in this worktree.

The repository `.gitignore` does not ignore
`experiments/stage4b5/evidence/`. A successful run therefore makes the tree
dirty by design. Preserve the cleanliness guarantee with this explicit
two-run workflow:

```text
review harness
→ commit harness
→ verify clean tree
→ canonical micro run
→ review and commit immutable micro evidence
→ verify clean tree
→ canonical PostgreSQL run
→ review and commit immutable PostgreSQL evidence
```

Committing micro evidence changes the repository commit identity but must not
change the recorded production `src` tree or harness blobs. The manifest records
the overall commit, production `src` tree identity, and both harness blob
identities so the two runs can demonstrate that boundary explicitly.

### Proposed immutable derived-statistics correction artifact

An accepted canonical timing namespace is never edited or regenerated to
correct aggregation logic. The narrow correction namespace proposed for the
canonical micro run is:

```text
experiments/stage4b5/evidence/
  runtime-governance-overhead-micro-corrections/
    stage4b5-runtime-overhead-micro-20260815-e3193f3/
      bootstrap-estimand-v1/
        manifest.json
        bootstrap_ci_corrections.json
```

This proposal is not written automatically. `manifest.json` would bind the
correction to the original run identity and SHA-256 hashes of its five immutable
files, identify the correcting source commit and algorithm, and state that only
bootstrap confidence intervals are superseded. The corrections document would
contain the original and corrected interval for each aggregate key; it would
not duplicate or alter samples, batch summaries, batch comparisons, empirical
percentiles, or the original `aggregates.json`. Publication would use a new
exclusive-create immutable namespace after separate human review.

Run the semantic-path layer:

```bash
<existing-virtual-environment>/bin/python \
  experiments/stage4b5/runtime_governance_overhead_recorded_run.py \
  micro \
  --run-id <immutable-micro-run-id> \
  --confirm I_UNDERSTAND_THIS_IS_A_FIXED_RECORDED_RUN
```

After setting `TEST_DATABASE_URL` through the operator's normal secret-handling
mechanism, run the PostgreSQL layer:

```bash
<existing-virtual-environment>/bin/python \
  experiments/stage4b5/runtime_governance_overhead_recorded_run.py \
  postgres \
  --run-id <immutable-postgres-run-id> \
  --confirm I_UNDERSTAND_THIS_IS_A_FIXED_RECORDED_RUN
```

Expected evidence namespaces are:

```text
experiments/stage4b5/evidence/runtime-governance-overhead-micro/<run-id>/
experiments/stage4b5/evidence/runtime-governance-overhead-postgres/<run-id>/
```

The non-database smoke command verifies all 12 micro surface/cell combinations,
discards elapsed values, writes no evidence, and must not be described as a
benchmark result:

```bash
<existing-virtual-environment>/bin/python \
  experiments/stage4b5/runtime_governance_overhead_recorded_run.py \
  smoke-micro
```

---

## Historical Stage 4B.2 Context

The following historical materials remain context, not numerical controls:

- [Stage 4B.2 closeout](../stage_4b_2/stage_4b_2_closeout.md)
- [PostgreSQL strategy comparison method](../stage_4b_2/postgres_strategy_comparison_method.md)
- [PostgreSQL strategy comparison report](../stage_4b_2/postgres_strategy_comparison_report.md)
- `experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/`

Those records used a historical source, machine state, Python environment,
psycopg/PostgreSQL environment, workload, and measurement wrapper. Their
absolute values may be displayed beside new findings only with an explicit
environment-comparability warning.

No new estimate may directly subtract a historical Stage 4B.2 recorded value
from a new B or C value. All numerical `B-A`, `C-B`, and `C-A` results must come
from the new fixed schedule in one characterization environment.

---

## Remaining Comparability Limits

Even after a valid canonical run:

- A/B/C process scheduling and runtime jitter remain measurement noise;
- separate processes reduce import contamination but cannot make process state
  identical;
- garbage collection, CPU frequency, thermal state, background load, and
  PostgreSQL cache state may contribute to block variation;
- the A bundle depends on a repeated transitive-source parity audit if the
  current source changes;
- micro deltas describe the chosen semantic/result boundary, not object-level
  causal attribution;
- B-A and C-A are matched batch comparisons, not per-invocation pairs;
- independent full-path C-B subtraction remains secondary because PostgreSQL
  noise may dominate the small semantic composition duration;
- PostgreSQL deltas describe the guarded environment and fixed workload, not a
  universal deployment cost;
- accepted and validation-blocked paths, CREATE/PAY, and PRE/IN must remain
  separate;
- a statistically measurable micro delta may still be operationally immaterial
  relative to normal PostgreSQL latency.

The eventual report must retain those qualifications and must distinguish
absolute latency, relative delta, measurement noise, environment differences,
and historical-comparability limitations.
