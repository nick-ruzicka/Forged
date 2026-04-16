# T1 APP PLATFORM BACKEND

## Rules
- Own ONLY: `db/migrations/004_apps.sql`, `api/apps.py`, `db/seed.py`, plus one targeted edit to `api/server.py` (blueprint registration only)
- Do NOT modify any other terminal's files
- Use `venv/bin/python3` and `venv/bin/pip` for all commands
- Mark tasks `[x]` in this file when done, update PROGRESS.md after each file
- Run `venv/bin/python3 -m py_compile` on every edited Python file
- Never stop. When all tasks done write `T1-APP DONE` to PROGRESS.md

## Tasks

[x] `db/migrations/004_apps.sql` — Add to tools table: `ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_html TEXT; ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_type TEXT DEFAULT 'prompt'; ALTER TABLE tools ADD COLUMN IF NOT EXISTS schedule_cron TEXT; ALTER TABLE tools ADD COLUMN IF NOT EXISTS schedule_channel TEXT; CREATE TABLE IF NOT EXISTS app_data (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id), user_key TEXT NOT NULL, data TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW(), UNIQUE(tool_id, user_key));` Run migration immediately: `venv/bin/python3 scripts/run_migrations.py`

[x] `api/apps.py` — Flask Blueprint (name `apps_bp`). Routes:
  - `GET /apps/<slug>` — serve full app HTML page. Inject `<script>` at top of `<body>` with `window.FORGE_APP = {toolId, slug, userName, apiBase: '/api'}` and `window.ForgeAPI = {getData, setData, deleteData, runTool, listTools}`. Each ForgeAPI function calls the corresponding `/api/apps/` endpoint. Return complete HTML document.
  - `GET /api/apps/<id>/data/<key>` — return `{value, found: bool}` from app_data table
  - `POST /api/apps/<id>/data/<key>` — body `{value: any}`, upsert app_data. Return `{success}`
  - `DELETE /api/apps/<id>/data/<key>` — delete key. Return `{success}`
  - `GET /api/apps/<id>/data` — return all keys for this app as `{keys: [{key, updated_at}]}`
  - `POST /api/apps/analyze` — body `{html: string}`. Use Claude (Sonnet) to return `{suggested_name, suggested_tagline, suggested_category, detected_inputs: [], uses_forge_api: bool, safety_notes: []}`. Powers auto-fill in submit form.

[x] Register `apps_bp` in `api/server.py` — add `from api.apps import apps_bp; app.register_blueprint(apps_bp)` after existing blueprint registrations. ONLY this change to server.py.

[x] Update `db/seed.py` — add 3 real app seeds with `app_type='app'`, `status='approved'`, `deployed=True`. All three must match Forge dark theme exactly (bg #0d0d0d, surface #1a1a1a, accent #0066FF, DM Sans from Google Fonts CDN) and look genuinely professional.

  **App 1 — "Job Search Pipeline"** slug=`job-search-pipeline` category=`other` trust_tier=`verified`. Single-file kanban app: columns (Applied / Phone Screen / Interview / Final Round / Offer / Rejected), add company form (company, role, date, notes, salary, url), drag cards between columns, count per column, click card to expand/edit, uses `window.ForgeAPI.getData('board')` / `setData('board')` for persistence, color-coded columns, keyboard shortcut `N` adds a card.

  **App 2 — "Meeting Prep Generator"** slug=`meeting-prep` category=`account_research` trust_tier=`verified`. Inputs: company name + contact name + meeting purpose. Generate button calls `window.ForgeAPI.runTool('account-research-brief', {company_name})` to get research, formats result as structured pre-call brief (background / pain points / questions / objections), saves to history via `ForgeAPI.setData`, shows last 5 preps in sidebar, print button for physical copy. Demonstrates apps calling prompt tools internally.

  **App 3 — "Pipeline Velocity Dashboard"** slug=`pipeline-velocity` category=`reporting` trust_tier=`verified`. Manual deal entry (company, stage, days_in_stage, value, close_date). Calculates pipeline velocity metrics (avg days per stage, conversion estimates, at-risk deals flagged). Chart.js from CDN. Export-to-CSV button. Persists via `ForgeAPI.setData('deals')`.

[x] Run `venv/bin/python3 db/seed.py` to reseed and verify the 3 apps land in DB with `app_type='app'`.

[x] Verify all 3 apps load end-to-end: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/apps/job-search-pipeline` returns 200, same for `meeting-prep` and `pipeline-velocity`. Also hit `/api/apps/<id>/data/testkey` POST then GET and verify the roundtrip works.

[x] When all tasks complete, append `T1-APP DONE` line to PROGRESS.md.

## Cycle 7 Tasks (scheduler + MCP layer + app runs)

UNBLOCKED: All 10 tasks stay inside T1_app_platform ownership (api/apps.py, db/seed.py, new db/migrations/006–008, plus one targeted `api/server.py` blueprint-only touch). Zero cross-terminal dependency — migration 004 + apps_bp already live. SPEC drivers: line 83 (tools.schedule_cron/schedule_channel already provisioned), lines 1497-1504 (MCP Integration Layer), lines 603-610 (Celery Beat pattern). Suggested pick order: migration 006 FIRST (unblocks app_runs writes) → GET /apps/<id>/runs → /data/batch → migration 007 indexes → POST /schedule → scheduled-run Celery task → /export → /import → /mcp endpoint → migration 008.

[ ] db/migrations/006_app_runs.sql - CREATE TABLE app_runs (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE, trigger TEXT CHECK (trigger IN ('manual','scheduled','webhook')), user_email TEXT, duration_ms INTEGER, outcome TEXT, error TEXT, created_at TIMESTAMP DEFAULT NOW()); CREATE INDEX idx_app_runs_tool_id_created ON app_runs(tool_id, created_at DESC).
[ ] api/apps.py - GET /api/apps/<id>/runs endpoint: SELECT last 50 app_runs rows joined with user_email; return [{id, trigger, user_email, duration_ms, outcome, created_at}]. Admin or matching-author access only (compare tools.author_email to X-User-Email header).
[ ] api/apps.py - POST /api/apps/<id>/data/batch endpoint: body `{keys: {k1: v1, ...}}` upserts all keys inside one transaction; reject with 400 if >50 keys; return {upserted: N, skipped: []}.
[ ] db/migrations/007_app_data_indexes.sql - CREATE INDEX IF NOT EXISTS idx_app_data_tool_key ON app_data(tool_id, user_key); CREATE OR REPLACE FUNCTION set_updated_at() ... ; CREATE TRIGGER trg_app_data_updated BEFORE UPDATE ON app_data FOR EACH ROW EXECUTE FUNCTION set_updated_at(); keeps updated_at fresh on every write.
[ ] api/apps.py - POST /api/apps/<id>/schedule endpoint: body {cron, channel}; validate cron (croniter), write tools.schedule_cron + tools.schedule_channel; publish {tool_id, cron} onto Redis key `forge:schedules` so Celery Beat can pick it up on next reload. Return {next_run_iso}.
[ ] agents/tasks.py - new `run_scheduled_app(tool_id)` Celery task: reads tool row, records an app_runs row with trigger='scheduled', posts one-line digest to tools.schedule_channel via scripts/slack_notify.send_channel(channel, text) if channel is set; auto-skips if schedule_cron is NULL.
[ ] api/apps.py - GET /api/apps/<id>/export endpoint: stream a zip (stdlib zipfile) containing index.html (from tools.app_html), forge.yaml (generated from tool fields), README.md describing the app. Content-Disposition: attachment with slug-based filename.
[ ] api/apps.py - POST /api/apps/<id>/import endpoint: multipart zip upload; extract index.html and replace tools.app_html atomically inside a transaction; bump tools.version and insert a tool_versions row with change_summary='app html imported'. Admin-only via check_admin_key.
[ ] api/apps.py - GET /api/apps/<id>/mcp endpoint returning tools.mcp_connectors parsed as list (empty [] if NULL); POST /api/apps/<id>/mcp body {connectors:[str]} validates each is in the allowed connector enum (salesforce, hubspot) and writes back. Logs every enable/disable to mcp_audits.
[ ] db/migrations/008_app_mcp.sql - ALTER TABLE tools ADD COLUMN IF NOT EXISTS mcp_connectors TEXT; CREATE TABLE mcp_audits (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE, connector TEXT NOT NULL, operation TEXT NOT NULL, run_id INTEGER REFERENCES runs(id), created_at TIMESTAMP DEFAULT NOW()); CREATE INDEX idx_mcp_audits_tool ON mcp_audits(tool_id, created_at DESC).
