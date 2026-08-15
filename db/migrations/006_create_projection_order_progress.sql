-- Stage 3.5C committed-visibility repair / Stage 3.5E permission extension
--
-- projection_order_progress is derived processing evidence, not accepted-history
-- authority. It records the exact order-local sequence applied by one immutable
-- projection definition and epoch.
--
-- Epoch 1 is the initial repaired epoch. It is intentionally not bootstrapped
-- from pre-repair GLOBAL_POSITION checkpoints because those checkpoints prove
-- only the largest processed visible allocation position.
--
-- The current production worker supports only order_state_projection epoch 1.
-- The epoch is retained in progress identity to prevent evidence
-- reinterpretation, not to provide concurrent epochs over projection_states,
-- which remains keyed only by order_id.
--
-- This migration performs no cutover reset. Human-controlled rebuild may
-- clear derived evidence, but must preserve order_events as accepted authority.

CREATE UNIQUE INDEX IF NOT EXISTS uq_order_events_projection_progress_lineage
    ON order_events (
        accepted_event_id,
        order_id,
        sequence,
        global_position
    );

CREATE TABLE IF NOT EXISTS projection_order_progress (
    projection_name TEXT NOT NULL,
    projection_epoch INTEGER NOT NULL,
    order_id TEXT NOT NULL,

    last_sequence INTEGER NOT NULL,
    last_event_id UUID NOT NULL,
    last_global_position BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_projection_order_progress
        PRIMARY KEY (projection_name, projection_epoch, order_id),

    CONSTRAINT ck_projection_order_progress_name_not_empty
        CHECK (length(trim(projection_name)) > 0),

    CONSTRAINT ck_projection_order_progress_epoch_positive
        CHECK (projection_epoch > 0),

    CONSTRAINT ck_projection_order_progress_order_id_not_empty
        CHECK (length(trim(order_id)) > 0),

    CONSTRAINT ck_projection_order_progress_sequence_positive
        CHECK (last_sequence > 0),

    CONSTRAINT ck_projection_order_progress_global_position_positive
        CHECK (last_global_position > 0),

    CONSTRAINT fk_projection_order_progress_event_lineage
        FOREIGN KEY (
            last_event_id,
            order_id,
            last_sequence,
            last_global_position
        )
        REFERENCES order_events (
            accepted_event_id,
            order_id,
            sequence,
            global_position
        )
);

CREATE OR REPLACE FUNCTION enforce_projection_order_progress_exact_next()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.last_sequence <> 1 THEN
        RAISE EXCEPTION
            'new projection progress must start at order-local sequence 1'
            USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.projection_name <> OLD.projection_name
           OR NEW.projection_epoch <> OLD.projection_epoch
           OR NEW.order_id <> OLD.order_id THEN
            RAISE EXCEPTION
                'projection progress identity is immutable'
                USING ERRCODE = '23514';
        END IF;

        IF NEW.last_sequence <> OLD.last_sequence + 1 THEN
            RAISE EXCEPTION
                'projection progress must advance by exactly one order-local sequence'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_projection_order_progress_exact_next
BEFORE INSERT OR UPDATE ON projection_order_progress
FOR EACH ROW
EXECUTE FUNCTION enforce_projection_order_progress_exact_next();

REVOKE ALL ON FUNCTION enforce_projection_order_progress_exact_next() FROM PUBLIC;

REVOKE ALL ON TABLE projection_order_progress FROM
    compass_app_writer,
    compass_projection_worker,
    compass_snapshot_worker,
    compass_readonly;

GRANT SELECT, INSERT, UPDATE ON TABLE projection_order_progress
    TO compass_projection_worker;

GRANT SELECT ON TABLE projection_order_progress
    TO compass_snapshot_worker,
       compass_readonly;
