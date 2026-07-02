-- Stage 3.5E PR2 — Durable State Permission Role Baseline
--
-- Purpose:
-- Establish the first PostgreSQL role / privilege boundary for durable state.
--
-- Core rule:
-- accepted history should be harder to mutate than derived runtime state.
--
-- This migration intentionally defines a minimal role / grant baseline.
-- It does not implement full RBAC, login/session auth, JWT, user accounts,
-- multi-tenant authorization, production IAM, Compass Layer 2, or Stage 4
-- runtime governance.
--
-- Role model:
--
-- compass_migration_owner
--   Declared migration / setup authority boundary.
--   Not a normal runtime role.
--   This migration does not transfer table ownership to this role.
--
-- compass_app_writer
--   Write-side runtime role.
--   May append accepted events and insert successful idempotency receipts.
--   Does not read or mutate projection tables by default.
--
-- compass_projection_worker
--   Read-side projection runtime role.
--   May read accepted history and maintain derived projection state/checkpoints.
--
-- compass_snapshot_worker
--   Snapshot artifact production role.
--   May read accepted history / derived state and insert projection snapshots.
--
-- compass_readonly
--   Read-only observer role.
--
-- Important:
-- These roles are runtime responsibility boundaries.
-- They are not product users and not a full RBAC system.
--
-- Existing tests and migrations may continue to use the high-privilege
-- compass_user / test owner connection. Runtime-role permission behavior is
-- verified separately in later Stage 3.5E permission tests.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_migration_owner') THEN
        CREATE ROLE compass_migration_owner;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_app_writer') THEN
        CREATE ROLE compass_app_writer;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_projection_worker') THEN
        CREATE ROLE compass_projection_worker;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_snapshot_worker') THEN
        CREATE ROLE compass_snapshot_worker;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_readonly') THEN
        CREATE ROLE compass_readonly;
    END IF;
END
$$;

-- Runtime roles need schema usage before table privileges are useful.
GRANT USAGE ON SCHEMA public TO
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

-- ---------------------------------------------------------------------------
-- order_events
-- ---------------------------------------------------------------------------
-- order_events is accepted history / authority.
--
-- app_writer may append accepted events through the intended write-side path.
-- No normal runtime role should UPDATE or DELETE accepted history.

REVOKE ALL ON TABLE order_events FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT ON TABLE order_events TO compass_app_writer;
GRANT SELECT ON TABLE order_events TO compass_projection_worker;
GRANT SELECT ON TABLE order_events TO compass_snapshot_worker;
GRANT SELECT ON TABLE order_events TO compass_readonly;

-- ---------------------------------------------------------------------------
-- idempotency_records
-- ---------------------------------------------------------------------------
-- idempotency_records is successful request-effect receipt memory.
--
-- Current schema records only successful request-to-accepted-event mappings:
-- request_id -> accepted_event_id.
--
-- It is not a retry lifecycle table, pending request table, failed-attempt log,
-- or conflict-history table.
--
-- Therefore app_writer may SELECT / INSERT successful receipts, but should not
-- receive normal UPDATE / DELETE privileges under the current design.

REVOKE ALL ON TABLE idempotency_records FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT ON TABLE idempotency_records TO compass_app_writer;
GRANT SELECT ON TABLE idempotency_records TO compass_readonly;

-- ---------------------------------------------------------------------------
-- projection_states
-- ---------------------------------------------------------------------------
-- projection_states is derived read-side state.
--
-- It is not authority.
-- It must remain controlled mutable so projection workers can update current
-- read models and clear/rebuild derived state when needed.
--
-- app_writer intentionally receives no projection_states access by default.
-- Write-side command admission rehydrates from accepted history, not from
-- derived read models.

REVOKE ALL ON TABLE projection_states FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE projection_states
    TO compass_projection_worker;

GRANT SELECT ON TABLE projection_states TO compass_snapshot_worker;
GRANT SELECT ON TABLE projection_states TO compass_readonly;

-- ---------------------------------------------------------------------------
-- projection_checkpoints
-- ---------------------------------------------------------------------------
-- projection_checkpoints is operational progress metadata.
--
-- It is not business truth.
-- It must remain controlled mutable by projection workers.
--
-- app_writer intentionally receives no checkpoint access by default.

REVOKE ALL ON TABLE projection_checkpoints FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE projection_checkpoints
    TO compass_projection_worker;

GRANT SELECT ON TABLE projection_checkpoints TO compass_snapshot_worker;
GRANT SELECT ON TABLE projection_checkpoints TO compass_readonly;

-- ---------------------------------------------------------------------------
-- projection_snapshots
-- ---------------------------------------------------------------------------
-- projection_snapshots is derived state compression / evidence.
--
-- A snapshot is not authority.
-- Snapshot existence does not imply trust.
--
-- snapshot_worker may insert snapshot artifacts, but normal runtime roles should
-- not UPDATE or DELETE snapshots by default.

REVOKE ALL ON TABLE projection_snapshots FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT ON TABLE projection_snapshots TO compass_projection_worker;
GRANT SELECT, INSERT ON TABLE projection_snapshots TO compass_snapshot_worker;
GRANT SELECT ON TABLE projection_snapshots TO compass_readonly;

-- ---------------------------------------------------------------------------
-- Sequences
-- ---------------------------------------------------------------------------
-- order_events.global_position uses a sequence-backed default.
--
-- Only compass_app_writer receives sequence usage because it is the only runtime
-- role in this baseline allowed to INSERT into order_events.
--
-- Projection and snapshot workers may read accepted history, but they should not
-- be able to consume accepted-history cursor values by calling nextval(...).

REVOKE ALL ON SEQUENCE order_events_global_position_seq FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT USAGE, SELECT ON SEQUENCE order_events_global_position_seq
    TO compass_app_writer;

GRANT SELECT ON SEQUENCE order_events_global_position_seq
    TO compass_readonly;

-- ---------------------------------------------------------------------------
-- Default privileges
-- ---------------------------------------------------------------------------
-- No broad default table privileges are granted here.
--
-- Future migrations should explicitly grant table-specific privileges according
-- to each table's semantic authority level.
