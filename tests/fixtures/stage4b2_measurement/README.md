# Frozen Stage 4B.2 Measurement Experiment Reference

`postgres_write_side_pr3_baseline.py.source` is an intentionally frozen,
non-importable, byte-for-byte source snapshot for a future PR6 observer-effect
experiment.

The snapshot was frozen from the committed Stage 4B.2 PR3 parent
`fd3733d57ff82beeaf9d54446924f8830c49db76` immediately before PR4
instrumentation.

It is experiment reference material only. It is **not** production code, a
fallback or compatibility implementation, a correctness specification, or an
alternate write path. Production modules must never import or execute it. The
snapshot is intentionally frozen: it must never track later production changes
or receive bug fixes.

`provenance.json` records the committed source identity and content hashes.
Future PR6 work may use this artifact only as the historical pre-PR4
observer-effect baseline, never as an oracle for current business correctness.
