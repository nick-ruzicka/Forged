-- 018_install_discovery.sql
-- Schema for agent-driven install discovery & reconciliation.
-- See docs/superpowers/specs/2026-04-19-agent-install-discovery-design.md

-- 1. Catalog: optional Mac bundle ID for matching scanned /Applications entries.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_bundle_id TEXT;
CREATE INDEX IF NOT EXISTS tools_bundle_id_idx
    ON tools(app_bundle_id)
    WHERE app_bundle_id IS NOT NULL;

-- 2. Shelf: distinguish manual adds from auto-detected, allow hiding,
--    and let unknown-app rows live without a catalog tool_id.
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS detected_bundle_id TEXT;
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS detected_name TEXT;

-- Allow unknown-app rows (tool_id NULL).
ALTER TABLE user_items ALTER COLUMN tool_id DROP NOT NULL;

-- One row per user per unknown app.
CREATE UNIQUE INDEX IF NOT EXISTS user_items_detected_unique
    ON user_items(user_id, detected_bundle_id)
    WHERE tool_id IS NULL AND detected_bundle_id IS NOT NULL;
