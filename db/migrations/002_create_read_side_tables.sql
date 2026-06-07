-- Stage 3.5C PR1 Durable Read-Side Schema Baseline

CREATE TABLE IF NOT EXISTS projection_states (
    order_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    paid_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    version INTEGER NOT NULL,
    last_sequence INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_projection_states_order_id_not_empty
        CHECK (length(trim(order_id)) > 0),

    CONSTRAINT ck_projection_states_status
        CHECK (status IN ('INIT', 'CREATED', 'PAID')),

    CONSTRAINT ck_projection_states_total_amount_non_negative
        CHECK (total_amount >= 0),

    CONSTRAINT ck_projection_states_paid_amount_non_negative
        CHECK (paid_amount >= 0),

    CONSTRAINT ck_projection_states_paid_amount_not_exceed_total_amount
        CHECK (paid_amount <= total_amount),

    CONSTRAINT ck_projection_states_version_non_negative
        CHECK (version >= 0),

    CONSTRAINT ck_projection_states_last_sequence_non_negative
        CHECK (last_sequence >= 0)
);

CREATE TABLE IF NOT EXISTS projection_checkpoints (
    worker_name TEXT PRIMARY KEY,
    cursor_kind TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    cursor_value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_projection_checkpoints_worker_name_not_empty
        CHECK (length(trim(worker_name)) > 0),

    CONSTRAINT ck_projection_checkpoints_cursor_kind
        CHECK (cursor_kind IN (
            'UNSPECIFIED',
            'APPENDED_AT',
            'EVENT_ID',
            'GLOBAL_POSITION'
        )),

    CONSTRAINT ck_projection_checkpoints_value_alignment
        CHECK (
            (cursor_kind = 'UNSPECIFIED' AND cursor_value = '') OR
            (cursor_kind = 'GLOBAL_POSITION' AND cursor_value ~ '^[0-9]+$') OR
            (
                cursor_kind = 'EVENT_ID'
                AND trim(cursor_value) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) OR
            (cursor_kind = 'APPENDED_AT' AND length(trim(cursor_value)) > 0)
        )
);