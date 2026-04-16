-- Forge Platform — Initial Schema
-- PostgreSQL

CREATE TABLE IF NOT EXISTS tools (
    id                    SERIAL PRIMARY KEY,
    slug                  TEXT UNIQUE NOT NULL,
    name                  TEXT NOT NULL,
    tagline               TEXT NOT NULL,
    description           TEXT,
    category              TEXT,
    tags                  TEXT,

    reliability_score     INTEGER DEFAULT 0,
    safety_score          INTEGER DEFAULT 0,
    data_sensitivity      TEXT DEFAULT 'internal',
    complexity_score      INTEGER DEFAULT 0,
    verified_score        INTEGER DEFAULT 0,
    trust_tier            TEXT DEFAULT 'unverified',

    output_type           TEXT,
    output_classification TEXT,
    output_format         TEXT DEFAULT 'text',

    security_tier         INTEGER DEFAULT 1,
    requires_review       BOOLEAN DEFAULT FALSE,

    tool_type             TEXT DEFAULT 'prompt',
    system_prompt         TEXT,
    hardened_prompt       TEXT,
    prompt_diff           TEXT,
    input_schema          TEXT NOT NULL DEFAULT '[]',
    model                 TEXT DEFAULT 'claude-haiku-4-5-20251001',
    max_tokens            INTEGER DEFAULT 1000,
    temperature           REAL DEFAULT 0.3,

    status                TEXT DEFAULT 'draft',
    version               INTEGER DEFAULT 1,

    author_name           TEXT,
    author_email          TEXT,
    fork_of               INTEGER REFERENCES tools(id),
    parent_version        INTEGER REFERENCES tools(id),

    deployed              BOOLEAN DEFAULT FALSE,
    deployed_at           TIMESTAMP,
    endpoint_url          TEXT,
    access_token          TEXT,
    instructions_url      TEXT,

    run_count             INTEGER DEFAULT 0,
    unique_users          INTEGER DEFAULT 0,
    avg_rating            REAL DEFAULT 0,
    flag_count            INTEGER DEFAULT 0,

    created_at            TIMESTAMP DEFAULT NOW(),
    submitted_at          TIMESTAMP,
    approved_at           TIMESTAMP,
    approved_by           TEXT,
    last_run_at           TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
CREATE INDEX IF NOT EXISTS idx_tools_trust_tier ON tools(trust_tier);
CREATE INDEX IF NOT EXISTS idx_tools_access_token ON tools(access_token);

CREATE TABLE IF NOT EXISTS tool_versions (
    id              SERIAL PRIMARY KEY,
    tool_id         INTEGER REFERENCES tools(id),
    version         INTEGER NOT NULL,
    system_prompt   TEXT,
    hardened_prompt TEXT,
    input_schema    TEXT,
    change_summary  TEXT,
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_versions_tool_id ON tool_versions(tool_id);

CREATE TABLE IF NOT EXISTS runs (
    id                SERIAL PRIMARY KEY,
    tool_id           INTEGER REFERENCES tools(id),
    tool_version      INTEGER DEFAULT 1,
    input_data        TEXT,
    rendered_prompt   TEXT,
    output_data       TEXT,
    output_parsed     TEXT,
    output_flagged    BOOLEAN DEFAULT FALSE,
    flag_reason       TEXT,
    run_duration_ms   INTEGER,
    model_used        TEXT,
    tokens_used       INTEGER,
    cost_usd          REAL,
    user_name         TEXT,
    user_email        TEXT,
    source            TEXT DEFAULT 'web',
    session_id        TEXT,
    rating            INTEGER,
    rating_note       TEXT,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_tool_id ON runs(tool_id);
CREATE INDEX IF NOT EXISTS idx_runs_user_email ON runs(user_email);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_flagged ON runs(output_flagged);

CREATE TABLE IF NOT EXISTS agent_reviews (
    id                        SERIAL PRIMARY KEY,
    tool_id                   INTEGER REFERENCES tools(id),

    classifier_output         TEXT,
    detected_output_type      TEXT,
    detected_category         TEXT,
    classification_confidence REAL,

    security_scan_output      TEXT,
    security_flags            TEXT,
    security_score            INTEGER,
    pii_risk                  BOOLEAN DEFAULT FALSE,
    injection_risk            BOOLEAN DEFAULT FALSE,
    data_exfil_risk           BOOLEAN DEFAULT FALSE,

    red_team_output           TEXT,
    red_team_attacks_succeeded INTEGER DEFAULT 0,
    attacks_attempted         INTEGER DEFAULT 0,
    attacks_succeeded         INTEGER DEFAULT 0,
    vulnerabilities           TEXT,
    hardening_suggestions     TEXT,

    hardener_output           TEXT,
    original_prompt           TEXT,
    hardened_prompt           TEXT,
    changes_made              TEXT,
    hardening_summary         TEXT,

    qa_output                 TEXT,
    test_cases                TEXT,
    qa_pass_rate              REAL,
    qa_issues                 TEXT,

    agent_recommendation      TEXT,
    agent_confidence          REAL,
    review_summary            TEXT,
    review_duration_ms        INTEGER,

    human_decision            TEXT,
    human_reviewer            TEXT,
    human_notes               TEXT,
    human_overrides           TEXT,

    created_at                TIMESTAMP DEFAULT NOW(),
    completed_at              TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_reviews_tool_id ON agent_reviews(tool_id);

CREATE TABLE IF NOT EXISTS skills (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    prompt_text     TEXT NOT NULL,
    category        TEXT,
    use_case        TEXT,
    author_name     TEXT,
    upvotes         INTEGER DEFAULT 0,
    copy_count      INTEGER DEFAULT 0,
    featured        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);

CREATE TABLE IF NOT EXISTS announcements (
    id          SERIAL PRIMARY KEY,
    tool_id     INTEGER REFERENCES tools(id),
    title       TEXT,
    body        TEXT,
    slack_sent  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
