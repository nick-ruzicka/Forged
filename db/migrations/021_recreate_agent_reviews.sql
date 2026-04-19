-- 021_recreate_agent_reviews.sql
-- Re-create agent_reviews after it was dropped by 008_drop_prompt_stack.sql.
-- This table stores the output of the 6-agent governance pipeline.

CREATE TABLE IF NOT EXISTS agent_reviews (
    id                        SERIAL PRIMARY KEY,
    tool_id                   INTEGER REFERENCES tools(id),
    skill_id                  INTEGER,
    classifier_output         TEXT,
    detected_output_type      TEXT,
    detected_category         TEXT,
    security_output           TEXT,
    security_risk_level       TEXT,
    red_team_output           TEXT,
    red_team_risk_level       TEXT,
    qa_output                 TEXT,
    qa_pass                   BOOLEAN,
    synthesizer_output        TEXT,
    overall_verdict           TEXT,
    overall_risk              TEXT,
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_reviews_tool_id ON agent_reviews(tool_id);
CREATE INDEX IF NOT EXISTS idx_agent_reviews_skill_id ON agent_reviews(skill_id);
