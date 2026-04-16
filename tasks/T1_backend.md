# T1 BACKEND TASKS
## Rules
- Own ONLY: api/server.py, api/db.py, api/models.py, api/executor.py, db/migrations/, db/seed.py
- PostgreSQL only, raw psycopg2, no ORM
- Mark [x] when done, update PROGRESS.md after each file
- Run python3 -m py_compile on every Python file
- Never stop

## Tasks
[x] db/migrations/001_initial_schema.sql - CREATE TABLE tools (id SERIAL PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, tagline TEXT NOT NULL, description TEXT, category TEXT, tags TEXT, reliability_score INTEGER DEFAULT 0, safety_score INTEGER DEFAULT 0, data_sensitivity TEXT DEFAULT 'internal', complexity_score INTEGER DEFAULT 0, verified_score INTEGER DEFAULT 0, trust_tier TEXT DEFAULT 'unverified', output_type TEXT, output_format TEXT DEFAULT 'text', security_tier INTEGER DEFAULT 1, requires_review BOOLEAN DEFAULT FALSE, tool_type TEXT DEFAULT 'prompt', system_prompt TEXT, hardened_prompt TEXT, prompt_diff TEXT, input_schema TEXT NOT NULL DEFAULT '[]', model TEXT DEFAULT 'claude-haiku-4-5-20251001', max_tokens INTEGER DEFAULT 1000, temperature REAL DEFAULT 0.3, status TEXT DEFAULT 'draft', version INTEGER DEFAULT 1, author_name TEXT, author_email TEXT, fork_of INTEGER REFERENCES tools(id), deployed BOOLEAN DEFAULT FALSE, deployed_at TIMESTAMP, endpoint_url TEXT, access_token TEXT, instructions_url TEXT, run_count INTEGER DEFAULT 0, unique_users INTEGER DEFAULT 0, avg_rating REAL DEFAULT 0, flag_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW(), submitted_at TIMESTAMP, approved_at TIMESTAMP, approved_by TEXT, last_run_at TIMESTAMP); CREATE TABLE tool_versions (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id), version INTEGER, system_prompt TEXT, hardened_prompt TEXT, input_schema TEXT, change_summary TEXT, created_by TEXT, created_at TIMESTAMP DEFAULT NOW()); CREATE TABLE runs (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id), tool_version INTEGER DEFAULT 1, input_data TEXT, rendered_prompt TEXT, output_data TEXT, output_parsed TEXT, output_flagged BOOLEAN DEFAULT FALSE, flag_reason TEXT, run_duration_ms INTEGER, model_used TEXT, tokens_used INTEGER, cost_usd REAL, user_name TEXT, user_email TEXT, source TEXT DEFAULT 'web', rating INTEGER, rating_note TEXT, created_at TIMESTAMP DEFAULT NOW()); CREATE TABLE agent_reviews (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id), classifier_output TEXT, detected_output_type TEXT, detected_category TEXT, classification_confidence REAL, security_scan_output TEXT, security_flags TEXT, security_score INTEGER, pii_risk BOOLEAN DEFAULT FALSE, injection_risk BOOLEAN DEFAULT FALSE, red_team_output TEXT, red_team_attacks_succeeded INTEGER DEFAULT 0, hardener_output TEXT, hardened_prompt TEXT, changes_made TEXT, qa_output TEXT, qa_pass_rate REAL, qa_issues TEXT, agent_recommendation TEXT, agent_confidence REAL, review_summary TEXT, review_duration_ms INTEGER, human_decision TEXT, human_reviewer TEXT, human_notes TEXT, created_at TIMESTAMP DEFAULT NOW(), completed_at TIMESTAMP); CREATE TABLE skills (id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT, prompt_text TEXT NOT NULL, category TEXT, use_case TEXT, author_name TEXT, upvotes INTEGER DEFAULT 0, copy_count INTEGER DEFAULT 0, featured BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW());
[x] api/db.py - psycopg2 connection pool via DATABASE_URL env var. get_db() context manager yields cursor, commits on exit, rolls back on exception. init_db() runs all SQL files in db/migrations/ in order. Retry logic 3 attempts 1s sleep.
[x] api/models.py - dataclasses Tool, Run, AgentReview, Skill. Each has from_row(row, cursor) classmethod using cursor.description. Each has to_dict() with datetime ISO serialization.
[x] api/executor.py - sanitize_inputs(inputs, schema): validate required, strip HTML, scan PII patterns (email, phone, SSN), log to logs/dlp.log. interpolate_prompt(template, inputs): replace {{var}}, raise ValueError if missing. call_claude(system_prompt, user_msg, model, max_tokens, temp): call Anthropic API return {text, input_tokens, output_tokens, cost_usd}. run_tool(tool_id, inputs, user_name, user_email, source): full orchestration, log to runs table, return {run_id, output, duration_ms, cost_usd}.
[x] api/server.py - Flask app, CORS, dotenv, error handlers (404/500/400). Serve frontend/ as static files. GET /api/health returns {status, version, timestamp}. Try import api/admin.py Blueprint gracefully.
[x] GET /api/tools - filters: category, output_type, trust_tier, search, sort (popular/newest/rating), page, limit=12. Paginated. Approved only.
[x] GET /api/tools/:id and GET /api/tools/slug/:slug - full tool detail, input_schema as parsed JSON.
[x] POST /api/tools/submit - validate, generate unique slug, insert status=pending_review, launch agents/pipeline.py in background thread. Return {id, slug, status}.
[x] POST /api/tools/:id/fork - copy with fork_of set, status=draft. Return {id, slug}.
[x] POST /api/tools/:id/run - validate, call executor.run_tool(), return result.
[x] GET /api/tools/:id/runs - last 20 runs, public stats only no content.
[x] POST /api/runs/:id/rate - update rating, recompute tool avg_rating.
[x] POST /api/runs/:id/flag - flag run, increment flag_count, set needs_review if >=3.
[x] GET /api/skills - filter category and search.
[x] POST /api/skills - create skill.
[x] POST /api/skills/:id/upvote - increment upvotes.
[x] POST /api/skills/:id/copy - increment copy_count.
[x] GET /api/t/:access_token - resolve token to tool slug.
[x] GET /api/agent/status/:tool_id - return agent pipeline progress from agent_reviews table.
[x] Rate limiting - 30 runs/hour per IP in-memory, 429 with retry_after.
[x] db/seed.py - 5 approved seed tools: Account Research Brief, Prospect Email Draft, ICP Qualification Check, Call Prep Summary, Churn Risk Check. All status=approved deployed=true with governance scores set.

## Cycle 2 Tasks (SPEC endpoints not yet built)

CYCLE 11 HUMAN-RESCUE REQUIRED (2026-04-16): migration 002 is now **11 CYCLES STALE**. Cycle 10 authorized any reviewer to write it; still no pickup. Per Cycle 10 action-item contract, this is the cycle where a human operator (not an agent terminal) picks up the file. The SQL is ready to paste — no design work, no cross-terminal coordination, no discovery required. Copy this block into `db/migrations/002_phase2_fields.sql` and run `venv/bin/python3 scripts/run_migrations.py`:

```sql
ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS progress_pct INTEGER DEFAULT 0;
ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS review_tokens_used INTEGER DEFAULT 0;
ALTER TABLE agent_reviews ADD COLUMN IF NOT EXISTS stage_failed TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS pii_detected BOOLEAN DEFAULT FALSE;
ALTER TABLE tool_versions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
```

Filename-slot note: T3_NEW already shipped `002_dlp_runs.sql`; keep this filename `002_phase2_fields.sql` — `scripts/run_migrations.py` sorts alphabetically so both apply. Unblocks 4 downstream terminals (T2_agents progress_pct/token accounting/stage_failed, T4_admin self-healer tool_versions.status, T3_frontend Cycle 4 task 5 progress bar, T6_testing test_rate_limit + test_versions_api).

UNBLOCKED: Start HERE with migration 002 first — it unblocks three other terminals. Extend the Cycle 2 migration 002 task below to also add: progress_pct INTEGER DEFAULT 0 on agent_reviews (T2 needs it for progress polling), review_tokens_used INTEGER DEFAULT 0 on agent_reviews (T2 base.py token accounting), stage_failed TEXT on agent_reviews (T2 pipeline timeout tracking), status TEXT DEFAULT 'pending' on tool_versions (T4 self-healer accept/reject). After migration 002 lands, all endpoint tasks below are pure Flask handler work with no cross-terminal blockers. Suggested pick order: migration 002 → forge_migrations tracking table → GET /versions → GET /instructions → PUT /:id → GET /agent/review/:tool_id → GET /categories → GET /runs/:id → redis rate limiter.

[ ] api/server.py - GET /api/tools/:id/versions endpoint: read tool_versions table filtered by tool_id, ordered by version DESC, return [{version, change_summary, created_by, created_at}].
[ ] api/server.py - GET /api/tools/:id/instructions endpoint: read static/instructions/{id}.md from disk, return text/markdown content-type, 404 if tool not deployed or file missing.
[ ] api/server.py - GET /api/tools/:id/instructions.pdf endpoint: stream static/instructions/{id}.pdf with application/pdf content-type, 404 if missing.
[ ] api/server.py - PUT /api/tools/:id endpoint: update draft-status tool (reject if status != 'draft' OR author_email != body.author_email), whitelist fields name/tagline/description/system_prompt/input_schema/model/max_tokens/temperature/tags.
[ ] api/server.py - GET /api/runs/:id endpoint: return full run detail including input_data, rendered_prompt, output_data; require matching user_email query param or X-Admin-Key header, else 403.
[ ] api/server.py - GET /api/agent/review/:tool_id endpoint: return agent_reviews row with all *_output fields parsed from JSON strings into objects; 404 if no review exists.
[ ] api/server.py - GET /api/tools/categories endpoint: SELECT category, COUNT(*) FROM tools WHERE status='approved' GROUP BY category; return [{category, count}] for filter UI dropdowns.
[ ] api/db.py - add forge_migrations tracking table (id SERIAL, filename TEXT UNIQUE, applied_at TIMESTAMP DEFAULT NOW()); init_db() inserts row after each file runs, SKIPS files already present.
[ ] api/executor.py - add Redis-backed rate limiter replacing in-memory dict: key=rate:{ip}:{hour}, INCR with EXPIRE 3600 on first hit, 429 when count>30; fallback to existing in-memory dict if REDIS_URL unset or connection fails.
[ ] db/migrations/002_phase2_fields.sql - ALTER tools ADD COLUMN archived_at TIMESTAMP; ALTER runs ADD COLUMN pii_detected BOOLEAN DEFAULT FALSE; CREATE INDEX idx_runs_created_at ON runs(created_at DESC); CREATE INDEX idx_tools_status ON tools(status).
