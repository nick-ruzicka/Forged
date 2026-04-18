-- 010_identity_social_versions.sql
-- Production-ready additions for the shelf experience:
--   - user_id (anonymous UUID) on user_items, in addition to user_email
--   - skill_subscriptions (per-user skill follows, drives `forge sync`)
--   - tool_versions_v2 (separate from the dropped legacy table) for app versioning
--   - tool_reviews (1-5 stars + optional note)
--   - tool_inspections (auto-derived "behind the scenes" trust badges)
--   - users (lightweight identity record — UUID-keyed, optional email/name)

-- 1. Lightweight users table. user_id is a UUID generated client-side on first visit.
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  email TEXT,
  name TEXT,
  team TEXT,                              -- derived from email domain or self-set
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS users_email_idx ON users (email);

-- 2. Add user_id to user_items. Backfill from email where possible.
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS user_items_user_id_idx ON user_items (user_id);
-- Allow user_email to be NULL for anonymous users.
ALTER TABLE user_items ALTER COLUMN user_email DROP NOT NULL;

-- 3. Skill subscriptions — for `forge sync`.
CREATE TABLE IF NOT EXISTS skill_subscriptions (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  subscribed_at TIMESTAMP DEFAULT NOW(),
  last_synced_at TIMESTAMP,
  installed_version TEXT,
  UNIQUE (user_id, skill_id)
);
CREATE INDEX IF NOT EXISTS skill_subs_user_idx ON skill_subscriptions (user_id);

-- 4. App versions (clean slate, the legacy tool_versions table was dropped in 008).
CREATE TABLE IF NOT EXISTS app_versions (
  id SERIAL PRIMARY KEY,
  tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  app_html TEXT,
  install_command TEXT,
  changelog TEXT,                         -- author-written "what's new"
  is_user_facing BOOLEAN DEFAULT TRUE,    -- false = silent bug fix, no banner
  is_security BOOLEAN DEFAULT FALSE,      -- true = red "Recommended now" chip
  created_by TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (tool_id, version_number)
);
CREATE INDEX IF NOT EXISTS app_versions_tool_idx ON app_versions (tool_id);

-- 5. Reviews (1-5 stars + optional text).
CREATE TABLE IF NOT EXISTS tool_reviews (
  id SERIAL PRIMARY KEY,
  tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  note TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (tool_id, user_id)
);
CREATE INDEX IF NOT EXISTS tool_reviews_tool_idx ON tool_reviews (tool_id);

-- 6. Inspection results — auto-derived "behind the scenes" badges.
CREATE TABLE IF NOT EXISTS tool_inspections (
  id SERIAL PRIMARY KEY,
  tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  uses_ai BOOLEAN DEFAULT FALSE,
  ai_calls TEXT,                          -- JSON array of {fn, snippet}
  reads_data TEXT,                        -- JSON array of source names
  writes_data BOOLEAN DEFAULT FALSE,
  external_hosts TEXT,                    -- JSON array of hostnames
  uses_storage BOOLEAN DEFAULT FALSE,
  uses_eval BOOLEAN DEFAULT FALSE,        -- security flag
  inspected_at TIMESTAMP DEFAULT NOW(),
  inspector_version TEXT DEFAULT 'v1',
  UNIQUE (tool_id)
);

-- 7. Add a few catalog convenience columns to tools.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS install_count INTEGER DEFAULT 0;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS setup_complexity TEXT DEFAULT 'one-click';
  -- 'one-click' | 'manual-setup' | 'multi-step' — drives honest labels on cards
