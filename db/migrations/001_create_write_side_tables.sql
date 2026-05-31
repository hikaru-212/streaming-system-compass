-- Stage 3.5B Write-Side Durable Schema Baseline
--
-- This migration creates the first durable write-side tables:
-- - order_events
-- - idempotency_records
--
-- Design principles:
-- - order_events stores accepted history only.
-- - idempotency_records stores successful request-to-accepted-event mappings.
-- - accepted_event_id is stored as PostgreSQL UUID.
-- - event identity is application-generated before append.
-- - order_id + sequence defines aggregate-local replay order.
-- - money values use NUMERIC, not FLOAT.
-- - idempotency records reference accepted events, not rejected candidates.
-- - metadata_json is reserved for non-domain runtime metadata, including
--   future validation timing, registry-stage timing, trace/debug metadata,
--   validator identity, and validation mode.
-- - event append and idempotency record write should later be coordinated
--   by the transactional write-side boundary.

CREATE TABLE IF NOT EXISTS order_events (
    accepted_event_id UUID PRIMARY KEY,
    event_schema_version INTEGER NOT NULL DEFAULT 1,

    order_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    request_id TEXT NOT NULL,

    amount NUMERIC(18, 2) NOT NULL,
    occurred_at_ms BIGINT NOT NULL,

    proof_prev_event_id UUID NULL,
    proof_prev_version INTEGER NOT NULL,
    proof_prev_status TEXT NOT NULL,

    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    proof_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,

    appended_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_order_events_order_sequence
        UNIQUE (order_id, sequence),

    CONSTRAINT ck_order_events_schema_version_positive
        CHECK (event_schema_version > 0),

    CONSTRAINT ck_order_events_sequence_positive
        CHECK (sequence > 0),

    CONSTRAINT ck_order_events_event_type
        CHECK (event_type IN ('created', 'paid')),

    CONSTRAINT ck_order_events_amount_non_negative
        CHECK (amount >= 0),

    CONSTRAINT ck_order_events_payload_json_object
        CHECK (jsonb_typeof(payload_json) = 'object'),

    CONSTRAINT ck_order_events_proof_json_object
        CHECK (jsonb_typeof(proof_json) = 'object'),

    CONSTRAINT ck_order_events_metadata_json_object
        CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    request_id TEXT PRIMARY KEY,

    order_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,

    fingerprint_version INTEGER NOT NULL DEFAULT 1,
    semantic_fingerprint TEXT NOT NULL,

    accepted_event_id UUID NOT NULL,
    result_sequence INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'SUCCEEDED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_idempotency_accepted_event
        FOREIGN KEY (accepted_event_id)
        REFERENCES order_events (accepted_event_id),

    CONSTRAINT ck_idempotency_fingerprint_version_positive
        CHECK (fingerprint_version > 0),

    CONSTRAINT ck_idempotency_semantic_fingerprint_not_empty
        CHECK (length(trim(semantic_fingerprint)) > 0),

    CONSTRAINT ck_idempotency_result_sequence_positive
        CHECK (result_sequence > 0),

    CONSTRAINT ck_idempotency_status
        CHECK (status IN ('SUCCEEDED')),

    CONSTRAINT ck_idempotency_command_type
        CHECK (command_type IN ('create', 'pay')),

    CONSTRAINT ck_idempotency_amount_non_negative
        CHECK (amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_order_id
    ON idempotency_records (order_id);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_accepted_event_id
    ON idempotency_records (accepted_event_id);