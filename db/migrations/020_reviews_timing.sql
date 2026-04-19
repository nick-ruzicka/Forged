-- 020_reviews_timing.sql
-- Per-agent timing log for the review pipeline.

CREATE TABLE IF NOT EXISTS reviews_timing (
    id              SERIAL PRIMARY KEY,
    review_id       INTEGER NOT NULL REFERENCES agent_reviews(id),
    skill_id        INTEGER NOT NULL REFERENCES skills(id),
    agent_name      TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    ended_at        TIMESTAMP,
    duration_ms     INTEGER,
    outcome         TEXT NOT NULL,
    error_detail    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reviews_timing_review_id ON reviews_timing(review_id);
CREATE INDEX IF NOT EXISTS idx_reviews_timing_agent_name ON reviews_timing(agent_name);
