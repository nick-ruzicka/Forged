-- 012_local_backend.sql
-- Backend-aware app support. Frontend in Forge iframe; backend runs locally.
-- Health-check overlay injected on serve if backend not reachable.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS has_local_backend BOOLEAN DEFAULT FALSE;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS backend_port INTEGER;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS backend_docker_image TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS backend_start_script TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS backend_health_path TEXT DEFAULT '/health';
