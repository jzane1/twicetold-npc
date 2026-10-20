-- A receipt commits with its observation; same-agent retries replay this result.
-- No backfill: previously accepted event IDs were not stored.
-- Purge removes receipts (including result metadata) through the memory FK.
CREATE TABLE observation_receipts (
    agent_id uuid NOT NULL REFERENCES agents (agent_id),
    event_id text NOT NULL CHECK (length(event_id) BETWEEN 1 AND 200),
    request_hash text NOT NULL,
    memory_id uuid NOT NULL REFERENCES memories (memory_id) ON DELETE CASCADE,
    response jsonb NOT NULL,
    PRIMARY KEY (agent_id, event_id)
);
CREATE INDEX observation_receipts_memory_idx ON observation_receipts (memory_id);
