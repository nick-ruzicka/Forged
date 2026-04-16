-- 004_apps.sql
-- Forge App Platform: extend tools with HTML-app fields + per-user app_data store.

ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_html TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_type TEXT DEFAULT 'prompt';
ALTER TABLE tools ADD COLUMN IF NOT EXISTS schedule_cron TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS schedule_channel TEXT;

CREATE TABLE IF NOT EXISTS app_data (
    id          SERIAL PRIMARY KEY,
    tool_id     INTEGER REFERENCES tools(id),
    user_key    TEXT NOT NULL,
    data        TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(tool_id, user_key)
);

CREATE INDEX IF NOT EXISTS idx_app_data_tool ON app_data(tool_id);
