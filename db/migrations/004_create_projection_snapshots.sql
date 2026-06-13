CREATE TABLE IF NOT EXISTS projection_snapshots (
    snapshot_id UUID PRIMARY KEY,
    order_id TEXT NOT NULL,

    source_event_id UUID NOT NULL,
    source_event_sequence INTEGER NOT NULL,
    source_global_position BIGINT NOT NULL,

    state_status TEXT NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL,
    paid_amount NUMERIC(18, 2) NOT NULL,
    state_version INTEGER NOT NULL,

    snapshot_schema_version INTEGER NOT NULL DEFAULT 1,
    reducer_version TEXT NOT NULL,
    payload_hash TEXT NOT NULL,

    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL DEFAULT 'system',

    CONSTRAINT ck_projection_snapshots_order_id_not_empty
        CHECK (length(trim(order_id)) > 0),

    CONSTRAINT ck_projection_snapshots_source_event_sequence_positive
        CHECK (source_event_sequence > 0),

    CONSTRAINT ck_projection_snapshots_source_global_position_positive
        CHECK (source_global_position > 0),

    CONSTRAINT ck_projection_snapshots_state_status_valid
        CHECK (state_status IN ('CREATED', 'PAID')),

    CONSTRAINT ck_projection_snapshots_total_amount_non_negative
        CHECK (total_amount >= 0),

    CONSTRAINT ck_projection_snapshots_paid_amount_non_negative
        CHECK (paid_amount >= 0),

    CONSTRAINT ck_projection_snapshots_paid_amount_not_greater_than_total
        CHECK (paid_amount <= total_amount),

    CONSTRAINT ck_projection_snapshots_state_version_non_negative
        CHECK (state_version >= 0),

    CONSTRAINT ck_projection_snapshots_state_version_not_ahead_of_source_seq
        CHECK (state_version <= source_event_sequence),

    CONSTRAINT ck_projection_snapshots_schema_version_positive
        CHECK (snapshot_schema_version > 0),

    CONSTRAINT ck_projection_snapshots_reducer_version_not_empty
        CHECK (length(trim(reducer_version)) > 0),

    CONSTRAINT ck_projection_snapshots_payload_hash_not_empty
        CHECK (length(trim(payload_hash)) > 0),

    CONSTRAINT ck_projection_snapshots_created_by_not_empty
        CHECK (length(trim(created_by)) > 0),

    CONSTRAINT ck_projection_snapshots_metadata_is_object
        CHECK (jsonb_typeof(metadata_json) = 'object'),

    CONSTRAINT uq_projection_snapshots_order_id_source_event_sequence
        UNIQUE (order_id, source_event_sequence),

    CONSTRAINT uq_projection_snapshots_order_id_source_global_position
        UNIQUE (order_id, source_global_position)
);

CREATE INDEX IF NOT EXISTS idx_projection_snapshots_order_id_source_global_position_desc
    ON projection_snapshots (order_id, source_global_position DESC);

CREATE INDEX IF NOT EXISTS idx_projection_snapshots_order_id_created_at_desc
    ON projection_snapshots (order_id, created_at DESC);