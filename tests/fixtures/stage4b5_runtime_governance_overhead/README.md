# Stage 4B.5 Runtime-Governance A Control

This fixture records the immutable source identity used to reconstruct the A
control. The benchmark does not copy these sources into the current import
graph. Its A worker reads the named blobs from the local Git object database,
verifies each blob's Git identity and SHA-256 digest, and executes the modules
under their canonical names in a fresh subprocess.

The pinned source commit is the canonical combined PR5+PR6 predecessor selected
by the source audit:

```text
0bd2f515bcc49e8e1f0e9d2f9dba4a294adadd0d
```

This design intentionally preserves the historical `ValidationRuntime.decide`
and PostgreSQL write-side behavior. It does not load current validator, runtime,
or write-side modules into the A process, create a Git worktree, parse YAML, or
change historical production semantics.

`provenance.json` also retains the complete audit-time set of `src/` paths that
differed between historical A and the B/C source used by the original review.
Its `allowed_current_source_differences` field is immutable historical metadata,
not an ongoing allowlist for later production evolution.

`replay_review.json` is a separate current-replay review artifact. It binds one
reviewed replay status to exact SHA-256 identities for every protected current
transitive dependency. The current status is `REFUSED`: Stage 4E PR4 changed
that protected surface and no performance-equivalence review has been
performed. Matching those exact identities makes the refusal expected; any
later committed or working-tree protected byte change fails closed until a new
explicit review. Historical provenance and recorded evidence remain unchanged.
