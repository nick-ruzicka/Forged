-- 021_recreate_agent_reviews.sql
-- Ensure agent_reviews exists with the full governed-skills schema.
--
-- Handles three cases:
-- 1. Table doesn't exist (dropped by 008) → CREATE
-- 2. Table exists from 001 but missing skill_id → ALTER to add columns
-- 3. Table already has full schema → no-ops via IF NOT EXISTS / IF EXISTS

-- Create the table if it was dropped by 008
CREATE TABLE IF NOT EXISTS agent_reviews (
    id                        SERIAL PRIMARY KEY,
    tool_id                   INTEGER REFERENCES tools(id),
    skill_id                  INTEGER,
    classifier_output         TEXT,
    detected_output_type      TEXT,
    detected_category         TEXT,
    classification_confidence REAL,
    security_scan_output      TEXT,
    security_flags            TEXT,
    security_score            INTEGER,
    pii_risk                  BOOLEAN DEFAULT FALSE,
    injection_risk            BOOLEAN DEFAULT FALSE,
    data_exfil_risk           BOOLEAN DEFAULT FALSE,
    red_team_output           TEXT,
    red_team_attacks_succeeded INTEGER DEFAULT 0,
    attacks_attempted         INTEGER DEFAULT 0,
    attacks_succeeded         INTEGER DEFAULT 0,
    vulnerabilities           TEXT,
    hardening_suggestions     TEXT,
    hardener_output           TEXT,
    original_prompt           TEXT,
    hardened_prompt           TEXT,
    changes_made              TEXT,
    hardening_summary         TEXT,
    qa_output                 TEXT,
    test_cases                TEXT,
    qa_pass_rate              REAL,
    qa_issues                 TEXT,
    agent_recommendation      TEXT,
    agent_confidence          REAL,
    review_summary            TEXT,
    review_duration_ms        INTEGER,
    human_decision            TEXT,
    human_reviewer            TEXT,
    human_notes               TEXT,
    human_overrides           TEXT,
    created_at                TIMESTAMP DEFAULT NOW(),
    completed_at              TIMESTAMP
);

-- If the table existed from 001 but is missing skill_id, add it
ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS skill_id INTEGER;

-- Make tool_id nullable (it was NOT NULL in 001)
ALTER TABLE agent_reviews ALTER COLUMN tool_id DROP NOT NULL;

-- Add XOR constraint if not present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agent_reviews_target_check'
  ) THEN
    ALTER TABLE agent_reviews
      ADD CONSTRAINT agent_reviews_target_check
        CHECK ((tool_id IS NULL) <> (skill_id IS NULL));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_agent_reviews_tool_id ON agent_reviews(tool_id);
CREATE INDEX IF NOT EXISTS idx_agent_reviews_skill_id ON agent_reviews(skill_id);
