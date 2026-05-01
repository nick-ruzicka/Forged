-- 025_agent_reviews_projects.sql
-- Extend agent_reviews to support Claude Code project submissions.
--
-- Adds:
--   - project_id column (FK to claude_code_projects)
--   - governance_output JSONB for the pre-pipeline validator's output
--
-- Relaxes the XOR constraint from 2-way (tool_id XOR skill_id) to 3-way
-- (exactly one of tool_id, skill_id, project_id is NOT NULL).

-- ============================================================
-- UP
-- ============================================================

ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS project_id INTEGER;
ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS governance_output JSONB;

-- Drop the 2-way XOR added by 021
ALTER TABLE agent_reviews DROP CONSTRAINT IF EXISTS agent_reviews_target_check;

-- Add 3-way XOR: exactly one of (tool_id, skill_id, project_id) is NOT NULL
ALTER TABLE agent_reviews ADD CONSTRAINT agent_reviews_target_check
  CHECK (
    ((tool_id IS NOT NULL)::int +
     (skill_id IS NOT NULL)::int +
     (project_id IS NOT NULL)::int) = 1
  );

-- FK to claude_code_projects (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agent_reviews_project_id_fkey'
  ) THEN
    ALTER TABLE agent_reviews
      ADD CONSTRAINT agent_reviews_project_id_fkey
        FOREIGN KEY (project_id) REFERENCES claude_code_projects(id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_agent_reviews_project_id ON agent_reviews(project_id);

-- ============================================================
-- DOWN (manual rollback)
-- ============================================================
-- ALTER TABLE agent_reviews DROP CONSTRAINT IF EXISTS agent_reviews_target_check;
-- ALTER TABLE agent_reviews DROP CONSTRAINT IF EXISTS agent_reviews_project_id_fkey;
-- DROP INDEX IF EXISTS idx_agent_reviews_project_id;
-- ALTER TABLE agent_reviews DROP COLUMN IF EXISTS governance_output;
-- ALTER TABLE agent_reviews DROP COLUMN IF EXISTS project_id;
-- ALTER TABLE agent_reviews ADD CONSTRAINT agent_reviews_target_check
--   CHECK ((tool_id IS NULL) <> (skill_id IS NULL));
