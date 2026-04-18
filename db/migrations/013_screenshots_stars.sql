ALTER TABLE tools ADD COLUMN IF NOT EXISTS screenshots TEXT; -- JSON array of image URLs
CREATE TABLE IF NOT EXISTS starred_items (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  tool_id INTEGER NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  starred_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (user_id, tool_id)
);
CREATE INDEX IF NOT EXISTS starred_items_user_idx ON starred_items (user_id);
