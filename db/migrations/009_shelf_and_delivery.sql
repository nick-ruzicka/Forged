-- 009_shelf_and_delivery.sql
-- Adds the minimum schema to support the shelf experience:
--   - delivery: how an item reaches the user (embedded in iframe vs external install)
--   - user_items: each user's "shelf" — items they've Added
--
-- Deliberately minimal. Stars/likes/reviews/installation_state/etc. layer on later.

-- The delivery column is for the renderer to branch on. Never user-facing copy.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS delivery TEXT DEFAULT 'embedded';
ALTER TABLE tools ADD COLUMN IF NOT EXISTS install_command TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS launch_url TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS icon TEXT;

-- Each user's shelf. user_email is the identifier (Forge has no real auth yet).
CREATE TABLE IF NOT EXISTS user_items (
  id SERIAL PRIMARY KEY,
  user_email TEXT NOT NULL,
  tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  added_at TIMESTAMP DEFAULT NOW(),
  installed_locally BOOLEAN DEFAULT FALSE,
  installed_at TIMESTAMP,
  installed_version TEXT,
  last_opened_at TIMESTAMP,
  open_count INTEGER DEFAULT 0,
  UNIQUE (user_email, tool_id)
);

CREATE INDEX IF NOT EXISTS user_items_user_email_idx ON user_items (user_email);
CREATE INDEX IF NOT EXISTS user_items_tool_id_idx ON user_items (tool_id);
