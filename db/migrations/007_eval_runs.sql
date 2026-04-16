-- 007_eval_runs.sql — T-EVAL pipeline evaluation harness storage.
-- One row per corpus submission (or load-test submission). Owned by T-EVAL;
-- no existing tables are touched.

CREATE TABLE IF NOT EXISTS eval_runs (
    id                     SERIAL PRIMARY KEY,
    corpus_item_id         TEXT NOT NULL,
    tool_id                INTEGER NULL,
    expected_outcome       TEXT NOT NULL
                           CHECK (expected_outcome IN ('should_pass','should_reject')),
    actual_outcome         TEXT NULL,
    expected_security_tier INTEGER,
    actual_security_tier   INTEGER,
    agent_verdicts         JSONB,
    latency_ms             INTEGER,
    error                  TEXT,
    load_test_run          BOOLEAN DEFAULT FALSE,
    created_at             TIMESTAMP DEFAULT NOW(),
    completed_at           TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_load ON eval_runs(load_test_run);
