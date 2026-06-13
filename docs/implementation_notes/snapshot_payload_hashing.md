# Snapshot Payload Hashing

[← Back to Implementation Notes](README.md)

## Purpose

This note defines deterministic canonical payload hashing for Stage 3.5D snapshots.

Snapshot trust checks depend on `payload_hash`.

If hash generation is not deterministic, valid snapshots may be incorrectly rejected, or corrupted snapshots may be inconsistently detected.

The goal is:

```text
same logical snapshot payload
→ same canonical representation
→ same payload_hash
```

---

## Core Rule

`payload_hash` must be computed over a canonical snapshot payload, not over arbitrary Python object serialization.

A snapshot hash must not depend on:

- Python dictionary insertion order
- JSON whitespace
- object memory identity
- non-deterministic serialization
- locale-specific formatting
- incidental datetime formatting differences

---

## Canonical JSON Encoding

The recommended JSON encoding is:

```python
json.dumps(
    canonical_payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

Then:

```python
hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

---

## Canonical Primitive Conversion

Before JSON encoding, all values should be converted into canonical primitives.

Suggested conversions:

```text
Decimal("100.00") → "100.00"
UUID("...") → lowercase canonical UUID string
Enum.VALUE → stable enum value string
datetime → UTC ISO-8601 string with explicit timezone
dict → recursively canonicalized mapping
list / tuple → recursively canonicalized sequence
```

Do not rely on default `str()` for objects unless the object has an explicitly stable representation.

---

## Decimal Rule

Money-like values should preserve scale when scale is semantically meaningful.

For the current order domain:

```text
Decimal("100.00") → "100.00"
Decimal("0.00") → "0.00"
```

Avoid converting Decimal to float.

Avoid representations that can produce:

```text
100.0
100
1E+2
```

unless the project explicitly defines those as canonical.

---

## Suggested Helper Shape

```python
def canonicalize_snapshot_payload(value: Any) -> Any:
    ...

def encode_canonical_snapshot_payload(payload: Mapping[str, Any]) -> str:
    canonical_payload = canonicalize_snapshot_payload(payload)
    return json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

def compute_snapshot_payload_hash(payload: Mapping[str, Any]) -> str:
    canonical_json = encode_canonical_snapshot_payload(payload)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

---

## Payload Scope

The hash should cover the snapshot state payload and any fields required to prove state integrity.

It should not include fields that are expected to differ across equivalent writes, such as:

```text
snapshot_id
created_at
created_by
metadata_json.trace_id
```

unless the project intentionally defines those fields as part of the integrity boundary.

A common pattern is:

```text
hash covers canonical state payload + source boundary + schema version + logic version
hash excludes database record identity and operational metadata
```

For projection snapshots, the source boundary should include:

```text
source_event_id
source_event_sequence
source_global_position
```

The exact scope should be consistent for both builder and validator.

---

## Projection Snapshot Payload Example

A projection snapshot canonical payload may include:

```json
{
  "kind": "PROJECTION",
  "order_id": "order-001",
  "source_event_id": "00000000-0000-0000-0000-000000000001",
  "source_event_sequence": 2,
  "source_global_position": 10,
  "state": {
    "status": "PAID",
    "total_amount": "100.00",
    "paid_amount": "100.00",
    "version": 2
  },
  "snapshot_schema_version": 1,
  "reducer_version": "order_projection_reducer:v1"
}
```

---

## Aggregate Snapshot Payload Example

An aggregate snapshot canonical payload may include:

```json
{
  "kind": "AGGREGATE",
  "order_id": "order-001",
  "source_event_id": "00000000-0000-0000-0000-000000000001",
  "source_event_sequence": 2,
  "source_global_position": 10,
  "state": {
    "status": "PAID",
    "total_amount": "100.00",
    "paid_amount": "100.00",
    "version": 2
  },
  "snapshot_schema_version": 1,
  "aggregate_logic_version": "order_aggregate_rehydration:v1"
}
```

---

## Tests

Hashing tests should verify:

- same logical payload with different dict key order produces same hash
- Decimal values do not become floats
- UUID values are stable
- Enum values are stable
- nested dictionaries are sorted recursively
- metadata excluded from hash does not change hash
- relevant state payload changes do change hash

---

## Non-goals

This note does not define:

- cryptographic signing
- HMAC
- sealed milestone snapshots
- production key management
- tamper-proof storage

Those are later governance or security hardening concerns.
