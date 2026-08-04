-- Stage 4B PR6 — DecisionReceipt Durable Persistence Foundation
--
-- decision_receipts stores the versioned semantic DecisionReceipt payload plus
-- a separate persistence envelope. It does not grant accepted-history
-- authority, materialize receipts at runtime, or perform reconciliation.
--
-- Migration 005 establishes the runtime roles used by the explicit grants at
-- the end of this migration. Normal runtime roles receive no UPDATE or DELETE
-- privilege on durable receipt evidence.

CREATE TABLE IF NOT EXISTS decision_receipts (
    receipt_id UUID PRIMARY KEY,
    receipt_serialization_version INTEGER NOT NULL,

    outcome_id UUID NOT NULL,
    ok BOOLEAN NOT NULL,
    boundary TEXT NOT NULL,
    category TEXT NOT NULL,
    semantic_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    reversibility TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_source TEXT NOT NULL,

    subject_type TEXT NOT NULL,
    subject_id TEXT NULL,

    order_id TEXT NULL,
    request_id TEXT NULL,
    candidate_event_id UUID NULL,
    accepted_event_id UUID NULL,
    snapshot_id UUID NULL,
    source_global_position BIGINT NULL,
    identity_source TEXT NOT NULL,

    actor_id TEXT NULL,
    actor_role TEXT NULL,
    runtime_role TEXT NULL,

    elapsed_ms BIGINT NULL,
    validation_elapsed_ms BIGINT NULL,
    replay_elapsed_ms BIGINT NULL,
    transaction_elapsed_ms BIGINT NULL,
    lock_wait_ms BIGINT NULL,

    fallback_required TEXT NOT NULL,
    rebuild_required TEXT NOT NULL,
    operator_review_required TEXT NOT NULL,
    retry_candidate TEXT NOT NULL,
    admission_disposition TEXT NULL,

    evidence_summary JSONB NOT NULL,
    metadata JSONB NOT NULL,

    materialization_provenance TEXT NOT NULL,
    materialized_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_decision_receipts_serialization_version_v1
        CHECK (receipt_serialization_version = 1),

    CONSTRAINT ck_decision_receipts_boundary
        CHECK (boundary IN (
            'LAYER_1_WRITE_SIDE',
            'LAYER_2_READ_SIDE',
            'SNAPSHOT_TRUST',
            'IDEMPOTENCY',
            'CONCURRENCY_ADMISSION',
            'RUNTIME_GOVERNANCE'
        )),

    CONSTRAINT ck_decision_receipts_category
        CHECK (category IN (
            'VALID',
            'UNRESOLVED',
            'UNTRUSTED',
            'DRIFT',
            'FALLBACK_REQUIRED',
            'REBUILD_REQUIRED',
            'BLOCK_REQUIRED',
            'ESCALATION_REQUIRED',
            'CONCURRENCY_UNCERTAIN',
            'RETRY_CLASSIFIED',
            'INTENT_INCONSISTENT'
        )),

    CONSTRAINT ck_decision_receipts_semantic_code
        CHECK (semantic_code IN (
            'SEMANTICALLY_VALID',
            'RUNTIME_UNRESOLVED',
            'DERIVED_STATE_UNTRUSTED',
            'DRIFT_DETECTED',
            'FAST_PATH_UNAVAILABLE',
            'REQUIRES_AUTHORITY_FALLBACK',
            'REQUIRES_REBUILD',
            'REQUIRES_OPERATOR_REVIEW',
            'REJECT_DOWNSTREAM_USAGE',
            'CONCURRENCY_UNCERTAIN',
            'IDEMPOTENT_REPLAY_ALLOWED',
            'SEMANTIC_CONFLICT_DETECTED',
            'INTENT_DRIFT_DETECTED'
        )),

    CONSTRAINT ck_decision_receipts_severity
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),

    CONSTRAINT ck_decision_receipts_risk_level
        CHECK (risk_level IN (
            'LOW',
            'MEDIUM',
            'HIGH',
            'CRITICAL',
            'UNKNOWN'
        )),

    CONSTRAINT ck_decision_receipts_reversibility
        CHECK (reversibility IN (
            'REVERSIBLE',
            'REBUILDABLE',
            'COMPENSABLE',
            'IRREVERSIBLE',
            'UNKNOWN'
        )),

    CONSTRAINT ck_decision_receipts_evidence_source
        CHECK (evidence_source IN (
            'WRITE_SIDE_ADMISSION',
            'READ_SIDE_PATH',
            'SNAPSHOT_TRUST_PATH',
            'SNAPSHOT_ASSISTED_PATH',
            'RUNTIME_OBSERVATION',
            'UNKNOWN'
        )),

    CONSTRAINT ck_decision_receipts_subject_type
        CHECK (subject_type IN (
            'ORDER',
            'REQUEST',
            'CANDIDATE_EVENT',
            'ACCEPTED_EVENT',
            'SNAPSHOT',
            'PROJECTION',
            'RUNTIME',
            'UNKNOWN'
        )),

    CONSTRAINT ck_decision_receipts_identity_source
        CHECK (identity_source IN (
            'ACCEPTED_HISTORY',
            'CANDIDATE_EVENT_IDENTITY',
            'WRITE_SIDE_CORRELATION',
            'READ_SIDE_OBSERVATION',
            'SNAPSHOT_LINEAGE',
            'CALLER_CONTEXT',
            'UNKNOWN'
        )),

    CONSTRAINT ck_decision_receipts_fallback_required
        CHECK (fallback_required IN ('TRUE', 'FALSE', 'NOT_EVALUATED')),

    CONSTRAINT ck_decision_receipts_rebuild_required
        CHECK (rebuild_required IN ('TRUE', 'FALSE', 'NOT_EVALUATED')),

    CONSTRAINT ck_decision_receipts_operator_review_required
        CHECK (operator_review_required IN (
            'TRUE',
            'FALSE',
            'NOT_EVALUATED'
        )),

    CONSTRAINT ck_decision_receipts_retry_candidate
        CHECK (retry_candidate IN ('TRUE', 'FALSE', 'NOT_EVALUATED')),

    CONSTRAINT ck_decision_receipts_admission_disposition
        CHECK (
            admission_disposition IS NULL
            OR admission_disposition IN (
                'ADMITTED_TO_ACCEPTED_HISTORY',
                'MATCHED_EXISTING_ACCEPTED_EVENT',
                'IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY',
                'SEMANTIC_ADMISSION_REJECTED',
                'APPEND_CONCURRENCY_CONFLICT',
                'APPEND_TECHNICAL_FAILURE',
                'COMMIT_OUTCOME_UNRESOLVED',
                'APPEND_ADMISSION_NOT_REACHED',
                'UNKNOWN'
            )
        ),

    CONSTRAINT ck_decision_receipts_materialization_provenance
        CHECK (materialization_provenance IN (
            'LIVE_RESULT',
            'ACCEPTED_HISTORY_RECONCILIATION'
        )),

    CONSTRAINT ck_decision_receipts_reason_not_empty
        CHECK (length(trim(reason)) > 0),

    CONSTRAINT ck_decision_receipts_subject_id_not_empty
        CHECK (subject_id IS NULL OR length(trim(subject_id)) > 0),

    CONSTRAINT ck_decision_receipts_order_id_not_empty
        CHECK (order_id IS NULL OR length(trim(order_id)) > 0),

    CONSTRAINT ck_decision_receipts_request_id_not_empty
        CHECK (request_id IS NULL OR length(trim(request_id)) > 0),

    CONSTRAINT ck_decision_receipts_actor_id_not_empty
        CHECK (actor_id IS NULL OR length(trim(actor_id)) > 0),

    CONSTRAINT ck_decision_receipts_actor_role_not_empty
        CHECK (actor_role IS NULL OR length(trim(actor_role)) > 0),

    CONSTRAINT ck_decision_receipts_runtime_role_not_empty
        CHECK (runtime_role IS NULL OR length(trim(runtime_role)) > 0),

    CONSTRAINT ck_decision_receipts_source_position_non_negative
        CHECK (
            source_global_position IS NULL
            OR source_global_position >= 0
        ),

    CONSTRAINT ck_decision_receipts_elapsed_ms_non_negative
        CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),

    CONSTRAINT ck_decision_receipts_validation_elapsed_ms_non_negative
        CHECK (
            validation_elapsed_ms IS NULL
            OR validation_elapsed_ms >= 0
        ),

    CONSTRAINT ck_decision_receipts_replay_elapsed_ms_non_negative
        CHECK (replay_elapsed_ms IS NULL OR replay_elapsed_ms >= 0),

    CONSTRAINT ck_decision_receipts_transaction_elapsed_ms_non_negative
        CHECK (
            transaction_elapsed_ms IS NULL
            OR transaction_elapsed_ms >= 0
        ),

    CONSTRAINT ck_decision_receipts_lock_wait_ms_non_negative
        CHECK (lock_wait_ms IS NULL OR lock_wait_ms >= 0),

    CONSTRAINT ck_decision_receipts_evidence_summary_object
        CHECK (jsonb_typeof(evidence_summary) = 'object'),

    CONSTRAINT ck_decision_receipts_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object'),

    CONSTRAINT ck_decision_receipts_admission_identity_alignment
        CHECK (
            admission_disposition IS NULL
            OR admission_disposition = 'UNKNOWN'
            OR (
                admission_disposition = 'ADMITTED_TO_ACCEPTED_HISTORY'
                AND candidate_event_id IS NOT NULL
                AND accepted_event_id IS NOT NULL
                AND candidate_event_id = accepted_event_id
            )
            OR (
                admission_disposition IN (
                    'MATCHED_EXISTING_ACCEPTED_EVENT',
                    'IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY'
                )
                AND accepted_event_id IS NOT NULL
            )
            OR (
                admission_disposition IN (
                    'SEMANTIC_ADMISSION_REJECTED',
                    'APPEND_CONCURRENCY_CONFLICT',
                    'APPEND_TECHNICAL_FAILURE',
                    'COMMIT_OUTCOME_UNRESOLVED'
                )
                AND candidate_event_id IS NOT NULL
                AND accepted_event_id IS NULL
            )
            OR (
                admission_disposition = 'APPEND_ADMISSION_NOT_REACHED'
                AND accepted_event_id IS NULL
            )
        ),

    CONSTRAINT fk_decision_receipts_accepted_event
        FOREIGN KEY (accepted_event_id)
        REFERENCES order_events (accepted_event_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_receipts_admitted_write_side_event
    ON decision_receipts (accepted_event_id)
    WHERE evidence_source = 'WRITE_SIDE_ADMISSION'
      AND admission_disposition = 'ADMITTED_TO_ACCEPTED_HISTORY';

REVOKE ALL ON TABLE decision_receipts FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT ON TABLE decision_receipts TO compass_app_writer;
GRANT SELECT ON TABLE decision_receipts TO compass_readonly;
