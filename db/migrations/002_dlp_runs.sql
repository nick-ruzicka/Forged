-- Forge Platform — Runtime DLP masking
-- T3_NEW: track how much PII the DLP engine masked per run.

ALTER TABLE runs
    ADD COLUMN IF NOT EXISTS dlp_tokens_found INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_runs_dlp_tokens_found
    ON runs (dlp_tokens_found)
    WHERE dlp_tokens_found > 0;
