-- 022_synthesizer_structured_fields.sql
-- Persist the structured synthesizer output that the prompt already asks
-- Claude to produce. Previously only agent_recommendation, agent_confidence,
-- and review_summary were saved; issues, advisory_warnings, and
-- data_class_mismatch were dropped on the floor.

-- ============================================================
-- UP
-- ============================================================

ALTER TABLE agent_reviews
  ADD COLUMN IF NOT EXISTS issues              JSONB,
  ADD COLUMN IF NOT EXISTS advisory_warnings   JSONB,
  ADD COLUMN IF NOT EXISTS data_class_mismatch BOOLEAN DEFAULT FALSE;

-- ============================================================
-- DOWN (manual rollback)
-- ============================================================
-- ALTER TABLE agent_reviews
--   DROP COLUMN IF EXISTS data_class_mismatch,
--   DROP COLUMN IF EXISTS advisory_warnings,
--   DROP COLUMN IF EXISTS issues;
