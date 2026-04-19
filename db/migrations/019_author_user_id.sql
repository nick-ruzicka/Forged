-- 019_author_user_id.sql
-- Add author identity to skills for review endpoint gating.

ALTER TABLE skills
  ADD COLUMN IF NOT EXISTS author_user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_skills_author_user_id ON skills(author_user_id);
