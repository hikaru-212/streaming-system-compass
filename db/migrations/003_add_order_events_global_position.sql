-- Stage 3.5C PR4 Global-Position Projection Worker Baseline
--
-- Adds a durable global event-log position to accepted history.
--
-- order_events.sequence remains aggregate-local:
--   (order_id, sequence)
--
-- order_events.global_position is a globally unique allocation / storage
-- coordinate. It provides accepted-event lineage and may be used as a
-- deterministic scheduling tie-breaker among currently eligible work.
--
-- PostgreSQL sequence allocation order is not transaction commit order.
-- global_position is therefore not a commit-safe completeness cursor and does
-- not prove that all lower positions are committed or visible. This migration
-- intentionally keeps it outside domain meaning and cross-order causality.

ALTER TABLE order_events
ADD COLUMN IF NOT EXISTS global_position BIGINT;

CREATE SEQUENCE IF NOT EXISTS order_events_global_position_seq AS BIGINT;

ALTER SEQUENCE order_events_global_position_seq
OWNED BY order_events.global_position;

WITH ordered_events AS (
    SELECT
        accepted_event_id,
        ROW_NUMBER() OVER (
            ORDER BY appended_at ASC, order_id ASC, sequence ASC, accepted_event_id ASC
        ) AS row_number
    FROM order_events
    WHERE global_position IS NULL
),
existing_global_position AS (
    SELECT COALESCE(MAX(global_position), 0) AS max_global_position
    FROM order_events
    WHERE global_position IS NOT NULL
)
UPDATE order_events AS event
SET global_position =
    existing_global_position.max_global_position + ordered_events.row_number
FROM ordered_events, existing_global_position
WHERE event.accepted_event_id = ordered_events.accepted_event_id;

SELECT setval(
    'order_events_global_position_seq',
    COALESCE((SELECT MAX(global_position) FROM order_events), 0) + 1,
    false
);

ALTER TABLE order_events
ALTER COLUMN global_position
SET DEFAULT nextval('order_events_global_position_seq'::regclass);

ALTER TABLE order_events
ALTER COLUMN global_position
SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_order_events_global_position
ON order_events (global_position);
