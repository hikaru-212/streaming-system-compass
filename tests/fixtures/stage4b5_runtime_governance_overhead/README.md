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

The manifest also freezes the complete set of `src/` paths allowed to differ
between the historical commit and the current B/C source. Canonical preflight
fails if another production path changes, forcing a new transitive-import audit
before A can be treated as credible again.
