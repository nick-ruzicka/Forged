-- 006_sandbox.sql — Tier 2 Docker sandbox columns for per-app containers.
-- Added by T1-WAVE3. All additive; existing Tier 1 (app_html-from-DB) path untouched.

ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_mode BOOLEAN DEFAULT FALSE;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_id TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_status TEXT DEFAULT 'stopped';
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_port INTEGER;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS image_tag TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS last_request_at TIMESTAMP;
