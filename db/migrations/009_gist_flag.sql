-- 009_gist_flag.sql — separate gist from component evidence
-- (ruled 2026-09-27, docs\decisions.md "Gist over-selection -> minimal gist,
-- folded into the write call"). Before this, memory_gist_spans (migration 001)
-- served double duty: the reconstruction gist constraint AND the sole
-- component-evidence ledger (matched_component_id, read by the trim path and by
-- coref). The write call now selects a MINIMAL factual gist, while the NLP pass
-- keeps emitting the full entity/category/coref spans as evidence. This column
-- splits the two roles: is_gist = true rows are the frozen facts reconstruction
-- reads; is_gist = false rows are component evidence only (trim, coref).
--
-- New column, DEFAULT true so any pre-009 row keeps reconstructing (it predates
-- the split); every new insert sets is_gist explicitly. IF NOT EXISTS as
-- defense-in-depth; the ledger remains the primary idempotency mechanism.

ALTER TABLE memory_gist_spans
    ADD COLUMN IF NOT EXISTS is_gist boolean NOT NULL DEFAULT true;

-- Reconstruction and the reconstruction-metrics read only is_gist = true; the
-- partial index keeps that hot path off the (typically more numerous) evidence
-- rows.
CREATE INDEX IF NOT EXISTS memory_gist_spans_gist_idx
    ON memory_gist_spans (memory_id) WHERE is_gist;
