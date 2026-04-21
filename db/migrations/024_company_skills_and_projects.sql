-- 024_company_skills_and_projects.sql
-- Company skills library + Claude Code project scaffolding tables.

-- 1. Company skills — governance rules and domain knowledge as reusable markdown
CREATE TABLE IF NOT EXISTS company_skills (
    id              SERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT,
    content         TEXT NOT NULL,           -- the markdown that gets injected into CLAUDE.md
    required_sections TEXT,                  -- JSON array of section headers that must be preserved
    behavior_tests  TEXT,                    -- JSON array of adversarial test specs
    category        TEXT DEFAULT 'governance',
    is_default      BOOLEAN DEFAULT FALSE,   -- auto-applied to all new projects
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_skills_slug ON company_skills(slug);
CREATE INDEX IF NOT EXISTS idx_company_skills_category ON company_skills(category);

-- 2. Claude Code projects — tracks scaffolded projects
CREATE TABLE IF NOT EXISTS claude_code_projects (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT,
    user_email      TEXT,
    slug            TEXT NOT NULL,
    description     TEXT,
    skills_applied  TEXT,                    -- JSON array of company_skill slugs
    local_path      TEXT,                    -- ~/forge-projects/{slug}
    governance_checksum TEXT,                -- checksum of required sections at scaffold time
    status          TEXT DEFAULT 'active',   -- active, submitted, approved, rejected
    submission_id   INTEGER,                 -- FK to agent_reviews if submitted
    created_at      TIMESTAMP DEFAULT NOW(),
    last_submitted_at TIMESTAMP,
    UNIQUE (user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_ccp_user_id ON claude_code_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_ccp_status ON claude_code_projects(status);
