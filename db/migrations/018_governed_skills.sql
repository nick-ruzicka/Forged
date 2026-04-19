-- 018_governed_skills.sql
-- Governed skills: review state, test cases, admin audit log.
-- Rollback: see DOWN section at bottom.

-- ============================================================
-- UP
-- ============================================================

-- 1. Extend skills with review state
ALTER TABLE skills
  ADD COLUMN IF NOT EXISTS review_status     TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS review_id         INTEGER,
  ADD COLUMN IF NOT EXISTS version           INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS parent_skill_id   INTEGER REFERENCES skills(id),
  ADD COLUMN IF NOT EXISTS data_sensitivity  TEXT,
  ADD COLUMN IF NOT EXISTS submitted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS approved_at       TIMESTAMP,
  ADD COLUMN IF NOT EXISTS blocked_reason    TEXT,
  ADD COLUMN IF NOT EXISTS blocked_at        TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_skills_review_status ON skills(review_status);

-- 3. Skill test cases (author-supplied positive/negative examples)
CREATE TABLE IF NOT EXISTS skill_test_cases (
    id          SERIAL PRIMARY KEY,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('positive', 'negative')),
    prompt      TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_test_cases_skill_id ON skill_test_cases(skill_id);

-- 4. Admin audit log for overrides and retroactive actions
CREATE TABLE IF NOT EXISTS skill_admin_actions (
    id              SERIAL PRIMARY KEY,
    skill_id        INTEGER NOT NULL REFERENCES skills(id),
    action          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    reviewer        TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_admin_actions_skill_id ON skill_admin_actions(skill_id);

-- 5. Backfill existing skills to 'approved' so they remain visible in catalog.
-- These were submitted before governance existed — they should not disappear.
UPDATE skills SET review_status = 'approved' WHERE review_status = 'pending';

-- ============================================================
-- DOWN (manual rollback — run these in reverse if needed)
-- ============================================================
-- DROP INDEX IF EXISTS idx_skill_admin_actions_skill_id;
-- DROP TABLE IF EXISTS skill_admin_actions;
-- DROP INDEX IF EXISTS idx_skill_test_cases_skill_id;
-- DROP TABLE IF EXISTS skill_test_cases;
-- DROP INDEX IF EXISTS idx_agent_reviews_skill_id;
-- ALTER TABLE agent_reviews DROP CONSTRAINT IF EXISTS agent_reviews_target_check;
-- ALTER TABLE agent_reviews DROP COLUMN IF EXISTS skill_id;
-- ALTER TABLE agent_reviews ALTER COLUMN tool_id SET NOT NULL;
-- DROP INDEX IF EXISTS idx_skills_review_status;
-- ALTER TABLE skills
--   DROP COLUMN IF EXISTS blocked_at,
--   DROP COLUMN IF EXISTS blocked_reason,
--   DROP COLUMN IF EXISTS approved_at,
--   DROP COLUMN IF EXISTS submitted_at,
--   DROP COLUMN IF EXISTS data_sensitivity,
--   DROP COLUMN IF EXISTS parent_skill_id,
--   DROP COLUMN IF EXISTS version,
--   DROP COLUMN IF EXISTS review_id,
--   DROP COLUMN IF EXISTS review_status;
