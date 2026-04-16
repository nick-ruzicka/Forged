# T2 FORGEDATA LAYER (Wave 3)

## What it is
Governed read-only data layer that exposes real business data through `window.ForgeAPI.data.*`. Every read logged. No writes in v1.

## Dependency
Must check `PROGRESS.md` for `T1-WAVE3 DONE` on startup. If absent → exit immediately (the runner loop retries in 5s).

## No-creds behavior (pinned)
When Salesforce env vars are missing, every route returns:
```json
{"error": "Salesforce not configured", "configured": false}
```
**Explicit signal, not empty success.** Downstream pipeline agents (red_team, qa_tester) must branch on `configured === false` when evaluating tools that consume ForgeData.

## Rules
- Own ONLY: `api/forgedata.py`, `api/connectors/` (new dir), append-only to ForgeAPI injection in `api/apps.py`, blueprint registration in `api/server.py`, new seed in `db/seed.py`
- Run `venv/bin/pip install simple-salesforce` first
- Run `venv/bin/python3 -m py_compile` on all Python files
- Mark tasks `[x]` as done, update PROGRESS.md after each file
- Never stop. When done write `T2-WAVE3 DONE` to PROGRESS.md

## Tasks

UNBLOCKED (Cycle 12 coordinator note, 2026-04-16): This track is **gated on T1-WAVE3 DONE marker** which has not yet appeared in PROGRESS.md. T1_docker_sandbox is currently 2/12 complete (preflight + migration 006 shipped per its task file); the remaining 10 implementation tasks block this track from starting. Per the dependency contract on line 7-8, the exit-0-and-retry behavior is correct — do NOT skip the gate to start work early, since the seed app on line 99-103 directly consumes the container-mode pathway. Suggested coordinator action while waiting: nothing required from this terminal yet. When T1-WAVE3 DONE lands, suggested pick order: (1) salesforce.py connector with is_configured() short-circuit FIRST (zero-dep, defines the no-creds contract everything else inherits), (2) forgedata_bp blueprint + routes, (3) ForgeAPI append in apps.py, (4) blueprint registration in server.py, (5) .env.example append (will collide with T5_deploy's still-pending append — coordinate or just append), (6) seed app, (7) smoke tests. SPEC drivers: lines 1497-1504 (MCP Integration Layer) — this is the Salesforce slice of that vision. Do NOT raise exceptions on missing creds; return the explicit `{configured: false}` shape per line 14-15 so red_team and qa_tester agents can branch correctly downstream.

[x] Check `PROGRESS.md` for `T1-WAVE3 DONE`. If absent, exit 0 immediately (retry loop handles re-entry).

[x] `venv/bin/pip install simple-salesforce`

[x] `api/connectors/__init__.py` — empty

[x] `api/connectors/salesforce.py` — `SalesforceConnector` class.
  - Reads `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, `SALESFORCE_TOKEN`, `SALESFORCE_DOMAIN` (default `login.salesforce.com`) from env
  - `is_configured()` returns bool based on required vars being set
  - `connect()` — returns cached `simple_salesforce.Salesforce` instance (30 min cache)
  - If `is_configured()` returns False: every method below returns `{"error": "Salesforce not configured", "configured": False}` — NO exceptions raised
  - `get_accounts(search=None, limit=20)` — SOQL: `SELECT Id,Name,Type,Industry,AnnualRevenue,NumberOfEmployees,OwnerId,Owner.Name,LastActivityDate,CreatedDate FROM Account WHERE IsDeleted=false [AND Name LIKE '%{search}%'] LIMIT {limit}`. Return list of snake_case dicts.
  - `get_opportunities(account_id=None, stage=None, limit=20)` — similar shape
  - `get_contacts(account_id=None, search=None, limit=20)` — similar shape
  - `get_activities(account_id, limit=10)` — `SELECT Id,Subject,ActivityDate,Status,OwnerId,Owner.Name,WhatId,What.Name FROM Task WHERE WhatId='{account_id}' ORDER BY ActivityDate DESC LIMIT {limit}`

[x] `api/forgedata.py` — Flask Blueprint `forgedata_bp` at `/api/forgedata`.
  - Inline table creation on blueprint import (idempotent):
    ```sql
    CREATE TABLE IF NOT EXISTS forge_data_reads (
      id SERIAL PRIMARY KEY,
      tool_id INTEGER,
      user_email TEXT,
      source TEXT,
      query_type TEXT,
      params TEXT,
      result_count INTEGER,
      created_at TIMESTAMP DEFAULT NOW()
    )
    ```
  - Routes (each logs a `forge_data_reads` row with `X-Tool-Id` and `X-User-Email` headers):
    - `GET /api/forgedata/salesforce/accounts` → `?search=&limit=20`
    - `GET /api/forgedata/salesforce/opportunities` → `?account_id=&stage=&limit=20`
    - `GET /api/forgedata/salesforce/contacts` → `?account_id=&search=&limit=20`
    - `GET /api/forgedata/salesforce/activities` → `?account_id=&limit=10`
    - `GET /api/forgedata/status` → `{salesforce: {configured: bool, connected: bool}}`
  - Every data route returns `{data: [...], count: N, source: "salesforce"}` on success, or the no-creds shape above.

[x] `api/apps.py` — **append-only** to the injected ForgeAPI script (do NOT rewrite existing injection code):
  ```javascript
  window.ForgeAPI.data = {
    salesforce: {
      accounts: async(params={}) => fetch('/api/forgedata/salesforce/accounts?' + new URLSearchParams(params),
        {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(r=>r.json()),
      opportunities: async(params={}) => fetch('/api/forgedata/salesforce/opportunities?' + new URLSearchParams(params),
        {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(r=>r.json()),
      contacts: async(params={}) => fetch('/api/forgedata/salesforce/contacts?' + new URLSearchParams(params),
        {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(r=>r.json()),
      activities: async(account_id) => fetch('/api/forgedata/salesforce/activities?account_id=' + encodeURIComponent(account_id),
        {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(r=>r.json()),
      status: async() => fetch('/api/forgedata/status').then(r=>r.json())
    }
  };
  ```
  Find the line immediately after the existing `window.ForgeAPI = {...};` declaration and append this block as a separate assignment. Do not modify anything else in the file.

[x] `api/server.py` — register blueprint:
  ```python
  try:
      from api.forgedata import forgedata_bp
      app.register_blueprint(forgedata_bp)
  except ImportError:
      pass
  ```
  Place immediately after the learning_bp registration. Do not reorder existing hooks.

[x] Append to `.env.example`:
  ```
  SALESFORCE_USERNAME=
  SALESFORCE_PASSWORD=
  SALESFORCE_TOKEN=
  SALESFORCE_DOMAIN=login.salesforce.com
  ```

[x] `db/seed.py` — add a new approved seed app:
  - `slug=account-health-dashboard`, name "Account Health Dashboard", tagline "Live account data from Salesforce in one view", category `account_research`, `app_type='app'`, `status='approved'`, `trust_tier='verified'`
  - `app_html`: full dark-theme dashboard, DM Sans CDN. On load calls `ForgeAPI.data.salesforce.status()`:
    - If `configured: false` → friendly banner "Salesforce not connected yet — contact your admin" + shows which endpoints would light up (`/api/forgedata/salesforce/*`).
    - If `configured: true` → accounts list with search, click account to show opportunities / contacts / recent activities. Chart.js (CDN) mini pipeline funnel per account.

[x] Smoke tests:
```bash
# No creds → graceful degradation
curl -s http://localhost:8090/api/forgedata/status | python3 -m json.tool
# Expect: {"salesforce": {"configured": false, "connected": false}}

curl -s http://localhost:8090/api/forgedata/salesforce/accounts | python3 -m json.tool
# Expect: {"error": "Salesforce not configured", "configured": false}

# Seed smoke
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/apps/account-health-dashboard
# Expect: 200
```

[x] Append `T2-WAVE3 DONE` to PROGRESS.md when complete.

## Cycle 13 Tasks (ForgeData v2 — HubSpot + writes + governance)

UNBLOCKED (Cycle 13 coordinator note, 2026-04-16): Wave 3 v1 shipped end-to-end last cycle (Salesforce read layer, 8 endpoints, seed app, no-creds contract, audit log). v2 is pure expansion: adds HubSpot (SPEC line 1500), write-back (SPEC line 1499), per-tool connector permission model (SPEC line 1502), and governance tooling. All 10 tasks stay inside T2_forgedata ownership (api/forgedata.py, api/connectors/*, append-only to ForgeAPI injection in api/apps.py, blueprint in api/server.py, db/migrations/008_forge_data_governance.sql, tests/test_forgedata.py). Zero cross-terminal blocker — Salesforce connector's is_configured() short-circuit pattern is now the reference contract all new connectors inherit. SPEC drivers: lines 1497-1504 (MCP Integration Layer full vision). `venv/bin/pip install hubspot-api-client` first. Suggested pick order: migration 008 FIRST (unblocks connector permission + cache persistence) → hubspot.py connector mirroring salesforce.py contract → /api/forgedata/hubspot/* routes → Salesforce write-back methods (log_activity, create_note) → per-tool permission model → Redis-backed cache → admin /reads audit endpoint → ForgeAPI.data.hubspot append → credential rotation → tests last. No-creds contract (explicit `{configured: false}`) inherits to every new connector — NEVER raise exceptions on missing env vars. Write-back paths require admin approval flag on tool row before executing.

[ ] T2_forgedata - db/migrations/008_forge_data_governance.sql - ALTER TABLE forge_data_reads ADD COLUMN IF NOT EXISTS latency_ms INTEGER; CREATE INDEX IF NOT EXISTS idx_forge_data_reads_tool_created ON forge_data_reads(tool_id, created_at DESC); CREATE TABLE forge_data_writes (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id), run_id INTEGER REFERENCES runs(id), user_email TEXT, source TEXT, operation TEXT, payload_hash TEXT, result TEXT, created_at TIMESTAMP DEFAULT NOW()); CREATE TABLE forge_data_permissions (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE, connector TEXT NOT NULL CHECK (connector IN ('salesforce','hubspot')), scopes TEXT NOT NULL, approved_by TEXT, approved_at TIMESTAMP DEFAULT NOW(), UNIQUE(tool_id, connector)); CREATE INDEX idx_forge_data_permissions_tool ON forge_data_permissions(tool_id).
[ ] T2_forgedata - `venv/bin/pip install hubspot-api-client` + api/connectors/hubspot.py - HubSpotConnector mirroring SalesforceConnector contract exactly: reads HUBSPOT_ACCESS_TOKEN env var (private app token); is_configured() returns bool; no-creds branches return `{error: "HubSpot not configured", configured: false}`. Methods: get_contacts(search, limit), get_companies(search, limit), get_deals(company_id, stage, limit), get_engagements(company_id, limit). SOQL-equivalent field filters via hubspot-api-client's search API; snake_case dict output matching salesforce.py.
[ ] T2_forgedata - api/forgedata.py - 5 new HubSpot routes mirroring salesforce routes: GET /api/forgedata/hubspot/{contacts,companies,deals,engagements}; GET /api/forgedata/status payload extends to {salesforce:{...}, hubspot:{configured, connected}}. Every call writes forge_data_reads row with source='hubspot' and latency_ms captured via time.perf_counter(). No-creds passthrough unchanged.
[ ] T2_forgedata - api/connectors/salesforce.py - write-back methods (SPEC line 1499): log_activity(account_id, subject, body, owner_email) creates Task row via simple_salesforce; create_note(parent_id, title, body) creates ContentNote + ContentDocumentLink. Both methods check tool permission before executing (tool_id passed in); reject with `{error: "Tool not permitted for salesforce.write", configured: true}` when missing forge_data_permissions row with 'write' in scopes. Writes logged to forge_data_writes with payload SHA-256 (NEVER raw values).
[ ] T2_forgedata - api/forgedata.py - POST /api/forgedata/salesforce/{activities,notes} routes calling new write methods; require X-Tool-Id + X-User-Email headers; reject with 403 if forge_data_permissions row missing or scope lacks 'write'. Payload limits: activity body ≤2000 chars, note body ≤10000; return 400 on overflow. Dry-run flag `?dry_run=1` returns the would-be payload without hitting Salesforce.
[ ] T2_forgedata - api/forgedata.py - per-tool permission management: POST /api/forgedata/permissions body `{tool_id, connector, scopes: ["read"]|["read","write"]}` admin-only via _require_admin(); GET /api/forgedata/permissions?tool_id=X returns active permissions. Every read route short-circuits with `{error: "Tool not permitted for <connector>", configured: true}` when no permission row exists (default deny). SPEC line 1502 alignment: each connector requires admin approval per tool.
[ ] T2_forgedata - api/forgedata.py - Redis cache layer: cache key `forgedata:{source}:{endpoint}:{hash(params)}`, TTL 60s for read endpoints only (writes never cached); on cache hit append `{cached: true}` to response and DO NOT write forge_data_reads row (only log cache misses to keep audit trail accurate). Fallback: if REDIS_URL unset, skip caching transparently. Invalidation: successful write-back invalidates all cache keys starting with `forgedata:<source>:*` for the affected account_id via Redis SCAN.
[ ] T2_forgedata - api/forgedata.py - admin audit endpoints: GET /api/forgedata/reads?tool_id=X&limit=100 returns last N forge_data_reads rows joined with tool name; GET /api/forgedata/writes?tool_id=X returns forge_data_writes with payload_hash (never raw). Both admin-only. Powers future admin UI panel and satisfies SPEC-implied governance need. Include p50/p95 latency aggregate in /reads response.
[ ] T2_forgedata - api/apps.py - append-only extension to `window.ForgeAPI.data` injection: adds `hubspot: {contacts, companies, deals, engagements, status}` methods + `salesforce.log_activity(account_id, subject, body)` and `salesforce.create_note(parent_id, title, body)` async methods. Every call passes X-Tool-Id header from window.FORGE_APP.toolId. Do NOT rewrite existing injection block — append a new `window.ForgeAPI.data.hubspot = {...}` and `Object.assign(window.ForgeAPI.data.salesforce, {...})` after the existing declaration, still inside the IIFE.
[ ] T2_forgedata - tests/test_forgedata.py - pytest coverage: (a) SalesforceConnector.is_configured() false path returns no-creds shape without touching simple_salesforce; (b) HubSpotConnector mirror contract parity; (c) permission model default-deny (no row → 403); (d) cache hit short-circuits DB insert; (e) write-back without 'write' scope → 403; (f) dry_run returns payload without calling external API; (g) /api/forgedata/reads returns latency aggregates; (h) concurrent read does not duplicate forge_data_reads rows when cache hits. Mock simple_salesforce.Salesforce + hubspot.Client; mock Redis via fakeredis; no real API calls.
