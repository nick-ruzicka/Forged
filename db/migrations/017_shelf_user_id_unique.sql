-- 017_shelf_user_id_unique.sql
-- Add unique constraint on (user_id, tool_id) for user_items so anonymous
-- users (no email) get proper upsert behavior on shelf add.

-- Drop duplicates first (keep earliest)
DELETE FROM user_items a USING user_items b
WHERE a.id > b.id AND a.user_id IS NOT NULL
  AND a.user_id = b.user_id AND a.tool_id = b.tool_id;

CREATE UNIQUE INDEX IF NOT EXISTS user_items_user_id_tool_id_uniq
  ON user_items (user_id, tool_id) WHERE user_id IS NOT NULL;
