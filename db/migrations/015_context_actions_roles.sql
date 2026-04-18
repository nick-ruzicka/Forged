-- User context: role, recent activity, preferences
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT;
  -- AE, SDR, RevOps, CS, Product, Eng, Recruiter, Other
ALTER TABLE users ADD COLUMN IF NOT EXISTS context_data TEXT;
  -- JSON: cached context object (calendar, deals, recent activity)
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded BOOLEAN DEFAULT FALSE;

-- Action log: every action an app takes on behalf of a user
CREATE TABLE IF NOT EXISTS action_log (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  tool_id INTEGER REFERENCES tools(id),
  action_type TEXT NOT NULL,  -- 'slack_post', 'email_draft', 'crm_update', etc.
  action_data TEXT,           -- JSON payload
  status TEXT DEFAULT 'completed', -- 'completed', 'failed', 'pending_approval'
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS action_log_user_idx ON action_log (user_id);
CREATE INDEX IF NOT EXISTS action_log_tool_idx ON action_log (tool_id);

-- Role tags on tools for role-aware filtering
ALTER TABLE tools ADD COLUMN IF NOT EXISTS role_tags TEXT;
  -- JSON array: ["AE", "SDR", "RevOps"]
