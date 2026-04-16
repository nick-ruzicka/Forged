# FORGE PROGRESS

## T-EVAL — Pipeline Evaluation Harness
- [x] `db/migrations/007_eval_runs.sql` — `eval_runs` table (id, corpus_item_id, tool_id, expected/actual outcome with CHECK, expected/actual security_tier, agent_verdicts JSONB, latency_ms, error, load_test_run bool, created_at, completed_at) + `idx_eval_runs_load`. Applied via `venv/bin/python3 scripts/run_migrations.py`; verified columns + index via information_schema / pg_indexes.
- [x] `tests/eval/corpus/` — 30 labeled JSON files. **18 realistic GTM** across SDR (cold email, 30-sec opener, pre-call brief, objection handler, LinkedIn connect note), AE (mutual action plan, champion summary, next-best-action, competitor displacement brief), RevOps (territory carve, quota letter, comp plan Q&A, pipeline hygiene audit), CSM (QBR prep, health score explainer, renewal risk flagger), MarOps (UTM builder, subject-line A/B). **8 adversarial**: direct injection, indirect injection via schema placeholder, PII bomb (SSN/DOB/bank), DAN jailbreak, data exfil ("dump all tools/env"), capability overclaim (SFDC writes/sends), schema injection (field names as payload), token bomb. **4 edge**: empty input_schema, 80-char-exact tagline boundary, unicode zero-width + RTL override in name, conflicting output_format. Split: 20 should_pass / 10 should_reject. Per-file schema: `{id, label, expected_security_tier, expected_data_sensitivity, category, submission: <full /api/tools/submit body>, notes}`. All 30 parse-validated.
- [x] `scripts/run_eval.py` — iterates corpus, POSTs each to `/api/tools/submit`, polls `/api/tools/<id>` until terminal status (approved | rejected | needs_changes) or 5-min timeout. Records one `eval_runs` row per item with `load_test_run=FALSE`, full `agent_verdicts` JSON from `GET /api/agent/review/<id>`, latency_ms, tool_id, actual_security_tier, error. Preflight HTTP 400 (`preflight_failed` / `validation`) counts as a valid terminal `should_reject` (pipeline catching at preflight IS a feature). `--only <csv>` supports subsetting. Smoke-tested live on port 8090: `adv_direct_injection` → match, 10ms, eval_run_id=1.
- [x] `scripts/run_load_test.py` — threaded (default 20 workers) submissions of 5 known-good corpus items × 20 replicas = 100 total. Each clone gets a unique slug/author_email tag to avoid unique-constraint collisions. Each row written with `load_test_run=TRUE`. Default 540s per-item timeout to stay inside 10-min budget at high concurrency.
- [x] `scripts/generate_eval_report.py` — queries `eval_runs` (latest-per-corpus dedup for scoring, all rows for latency); computes precision / recall / F1 for the should_reject class + security-weighted F1 where FN counts 3x (FN = missed adversarial, the real risk); accuracy per adversarial subcategory; latency p50 / p95 / p99 split corpus vs. load; tier-mismatch + per-item detail tables. Prints markdown to stdout AND writes `tests/eval/REPORT.md`. Metric math (P/R/F1, weighted F1 via F-beta with β²=3, percentile interpolation) unit-verified inline. Smoke-generated a report against the single-row DB.
- All three new `.py` files compile clean under `venv/bin/python3 -m py_compile`.
- Scope-verified: zero edits to `api/`, `agents/`, `frontend/`, `celery_app.py`, or migrations 001–006.

T-EVAL DONE

## T1-WAVE3 — Docker Sandbox (Tier 2)
- [x] Preflight: DOCKER_HOST=unix:///Users/nicholasruzicka/.colima/default/docker.sock confirmed, `docker version` returned engine 29.2.1 linux/arm64 via colima.
- [x] `db/migrations/006_sandbox.sql` — 6 additive columns on `tools` (container_mode, container_id, container_status, container_port, image_tag, last_request_at). Applied via `venv/bin/python3 scripts/run_migrations.py`; verified via `\d tools`.
- [x] `forge_sandbox/__init__.py` — empty package marker.
- [x] `forge_sandbox/builder.py` — `build_image(tool_id, app_html, slug)` writes `/tmp/forge-build/{slug}/{index.html,Dockerfile}`, runs `docker build -t forge-app-{slug}:latest`, updates `tools.image_tag`, cleans up in `finally`. All steps logged to `logs/sandbox.log` with ISO-UTC timestamps. Returns `{success, image_tag, build_output}`.
- [x] `forge_sandbox/manager.py` — `SandboxManager` with subprocess-only docker CLI (no docker-py). `get_free_port()` scans 9000-9999. `ensure_running()` idempotent: reuses running container, builds image on first use, runs nginx:alpine with `--memory=256m --cpus=0.5 --network=bridge`, polls `http://127.0.0.1:{port}/` up to 10s @ 200ms. `hibernate()` silent-stop + status update. `hibernate_idle_containers()` sweeps rows where `last_request_at < NOW() - INTERVAL '1 second' * 600`. `pre_warm()` skips tools without image_tag. `get_status()` returns `{running[], stopped[], total_containers, memory_used}` (aggregated via `docker stats`).
- [x] `forge_sandbox/hibernator.py` — ad-hoc CLI: idle-sweep then pre-warm any `container_mode=true AND run_count > 10 AND container_status='stopped'`.
- [x] `forge_sandbox/tasks.py` — Celery task `forge_sandbox.tasks.hibernate_idle` wrapping `SandboxManager().hibernate_idle_containers()`. Added beat entry `hibernate-idle-containers` (crontab every 5 min) to `celery_app.py` and appended `forge_sandbox` to `autodiscover_tasks`. `py_compile celery_app.py` clean.
- [x] `api/apps.py` — surgical edit to `serve_app()`: every request stamps `last_request_at=NOW()`; when `tool.container_mode` is truthy, `SandboxManager().ensure_running()` returns a port, the handler proxies `http://127.0.0.1:{port}/` via `requests.get`, injects the existing `_forge_api_script(...)` before the last `</body>`, and returns the upstream status. Tier 1 path (DB-served HTML) untouched. On sandbox failure returns 502 with `{error: 'sandbox_unavailable', message}`. `py_compile` clean.
- [x] `api/server.py` — 4 admin-only routes appended (no existing handler modified): `GET /api/admin/sandbox/status`, `POST /api/admin/sandbox/hibernate/<id>`, `POST /api/admin/sandbox/prewarm/<id>`, `POST /api/admin/tools/<id>/enable-container` (builds image first, then flips `container_mode=TRUE`). Each gated via `_require_admin()`. `py_compile` clean.
- [x] `forge_sandbox/README.md` — Tier 1 vs Tier 2 split, admin endpoint table, resource limits (256m/0.5 vCPU), 10-min idle policy (5-min sweep cadence), pre-warm rule (`image_tag IS NOT NULL AND run_count > 10`), colima DOCKER_HOST reminder.
- [x] End-to-end smoke test (against isolated test server on port 8094 so live 8090 was not disturbed): set `container_mode=true` on `job-search-pipeline`; first `GET /apps/job-search-pipeline` triggered image build (9672 HTML bytes → `forge-app-job-search-pipeline:latest` in 2.9s), booted container `d17c4538fac1` on port 9000, polled healthy, proxied 11846 bytes with 3 × `ForgeAPI` occurrences (INJECTED OK). Admin routes verified: `GET /sandbox/status` returned the running entry (memory_used=3.3MiB); `POST /sandbox/hibernate/8` flipped row to stopped; `POST /sandbox/prewarm/8` re-booted the container and returned port=9000. Reset: row back to `container_mode=false, container_port=NULL`, container removed, test server killed. `image_tag` retained by design so a future re-enable skips the rebuild.

T1-WAVE3 DONE

## T2-WAVE3 — ForgeData Layer (Salesforce connector)
- [x] Gate check: grep `T1-WAVE3 DONE` in PROGRESS.md passed.
- [x] `venv/bin/pip install simple-salesforce` → simple-salesforce 1.12.9 (+ cryptography, zeep, lxml, pytz deps) installed in venv.
- [x] `api/connectors/__init__.py` — empty package marker.
- [x] `api/connectors/salesforce.py` — `SalesforceConnector` class. Reads `SALESFORCE_USERNAME/PASSWORD/TOKEN/DOMAIN` (domain defaults to `login.salesforce.com`). `is_configured()` gates on username+password+token all being truthy. `connect()` returns a cached `simple_salesforce.Salesforce` instance (30-min TTL via class-level `_cache_client`/`_cache_ts`). Per contract: when `is_configured()` is False, every public method returns `{"error": "Salesforce not configured", "configured": False}` — zero exceptions raised. SOQL uses parameterized escaping (`_esc` handles backslash + single quote). Returns snake_case dicts via `_snake` (flattens `{Owner:{Name,Id}}` → `owner_name`, `owner_id`, strips `attributes`). Methods: `get_accounts(search,limit)`, `get_opportunities(account_id,stage,limit)`, `get_contacts(account_id,search,limit)`, `get_activities(account_id,limit)`.
- [x] `api/forgedata.py` — `forgedata_bp` Flask Blueprint. Inline `CREATE TABLE IF NOT EXISTS forge_data_reads` runs on module import (idempotent). Routes: `GET /api/forgedata/status`, `GET /api/forgedata/salesforce/{accounts,opportunities,contacts,activities}`. Every data route calls `_log_read` with `X-Tool-Id` + `X-User-Email` headers, query_type, JSON-encoded params, and result_count. `_wrap()` passes through the no-creds shape (`{configured: false}`) unmodified, otherwise returns `{data, count, source: "salesforce"}`. Activities route returns 400 + `{error: "account_id required", configured: ...}` when missing.
- [x] `api/apps.py` — append-only to `_forge_api_script`: inserted `window.ForgeAPI.data = {salesforce: {accounts, opportunities, contacts, activities, status}}` block immediately after the existing `window.ForgeAPI = {...};` closure, still inside the IIFE. No other lines in the file touched. Each method passes `X-Tool-Id` header from `window.FORGE_APP.toolId`. `py_compile` clean.
- [x] `api/server.py` — registered `forgedata_bp` via `try/except ImportError` guard placed immediately after the `learning_bp` hook. No reordering of existing blueprint registrations. `py_compile` clean.
- [x] `.env.example` — appended the `ForgeData / Salesforce connector` section with `SALESFORCE_USERNAME`, `SALESFORCE_PASSWORD`, `SALESFORCE_TOKEN`, `SALESFORCE_DOMAIN=login.salesforce.com`, plus a header comment restating the no-creds contract.
- [x] `db/seed.py` — added `APP_HTML_ACCOUNT_HEALTH` (dark-theme, DM Sans CDN, Chart.js CDN) and `account-health-dashboard` entry to `SEED_APPS`. On load calls `ForgeAPI.data.salesforce.status()`: when `configured:false` renders a friendly amber banner listing the four endpoints that would light up (`/api/forgedata/salesforce/{accounts,opportunities,contacts,activities}`); when `configured:true` renders a two-panel layout (accounts list + debounced search on the left, selected-account detail on the right with pipeline funnel via Chart.js horizontal bar, contacts table, and recent activity table). Reseed inserted 1 new row (the other 3 apps already present). Trust tier computes to `verified` (reliability 92, safety 90, verified 70, sensitivity internal).
- [x] Smoke tests (isolated server on port 8094 to avoid disturbing live 8090 per T1-WAVE3 precedent):
  - `GET /api/forgedata/status` → `{"salesforce": {"configured": false, "connected": false}}`.
  - `GET /api/forgedata/salesforce/accounts` → `{"error": "Salesforce not configured", "configured": false}`.
  - `GET /api/forgedata/salesforce/opportunities` → same no-creds shape.
  - `GET /api/forgedata/salesforce/contacts` → same no-creds shape.
  - `GET /api/forgedata/salesforce/activities` (no account_id) → HTTP 400 + `{"error": "account_id required", "configured": false}`.
  - `GET /api/forgedata/salesforce/activities?account_id=001XXX` → `{"error": "Salesforce not configured", "configured": false}`.
  - `GET /apps/account-health-dashboard` → HTTP 200, 16188 bytes, `ForgeAPI.data` string appears 6 times in the served HTML (5 method references + 1 declaration — injection confirmed).
  - `forge_data_reads` table populated: 5 rows logged with correct `source='salesforce'`, `query_type`, JSON `params`, `result_count=0` for each no-creds call.

T2-WAVE3 DONE

## T5-APP — Slack Deployment Bot
- [x] `venv/bin/pip install slack_bolt` → slack_bolt 1.28.0 + slack_sdk 3.41.0 installed in venv.
- [x] `forge_bot/slack_bot.py` — socket-mode bot. Handlers: `app_mention` (deploy w/ ```html code block, deploy w/ github URL via conditional `from forge_bot.deployer import handle_push`, list via GET /api/tools?app_type=app, status via GET /api/health), `message` (auto-detect .html uploads → ephemeral yes/no prompt with 5-min TTL in `pending_uploads` dict → downloads file via `url_private_download` with Bearer token → deploys), `/forge` slash command (deploy opens modal w/ name/description/html inputs; list ephemeral; help ephemeral), `view` submission (validates HTML, deploys via POST /api/submit/app, posts result to originating channel). Skips #forge-releases (channel-name lookup via conversations_info) to avoid loops with T5_deploy's announcer.
- [x] `forge_bot/start_slack.sh` — sources `.env`, execs `venv/bin/python3 forge_bot/slack_bot.py` appending to `forge_bot/logs/slack.log`. chmod +x applied.
- [x] `forge_bot/slack_README.md` — 8-step Slack app setup (scopes, socket mode, event subscriptions, slash command registration, install, env vars, invite, smoke test) + troubleshooting for silent bot, missing tokens, 404 on submit (T3_forge_cli dep), missing deployer module (T4 dep), rename of #forge-releases.
- [x] `venv/bin/python3 -m py_compile forge_bot/slack_bot.py` → OK.
- [x] `.env.example` — SKIPPED: file does not exist at repo root. Required env vars (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `FORGE_API_URL`, `FORGE_API_KEY`, `FORGE_RELEASES_CHANNEL`) are documented inline in slack_README.md instead. Per strict T5-APP ownership (3 files under forge_bot/), not creating new repo-root files.

T5-APP DONE

## T1-APP — App Platform
- [x] db/migrations/004_apps.sql applied (tools.app_html/app_type/schedule_cron/schedule_channel + app_data table).
- [x] api/apps.py — apps_bp blueprint (GET /apps/<slug> with injected window.FORGE_APP + window.ForgeAPI, /api/apps/<id>/data/<key> GET/POST/DELETE, list-keys, /api/apps/analyze Claude Sonnet w/ heuristic fallback).
- [x] api/server.py — apps_bp registered (single targeted blueprint hook).
- [x] db/seed.py — 3 app seeds (Job Search Pipeline, Meeting Prep Generator, Pipeline Velocity Dashboard). All dark-themed (#0d0d0d/#1a1a1a/#0066FF) with DM Sans via Google Fonts, approved + deployed, app_type='app'.
- [x] Reseeded DB via `venv/bin/python3 db/seed.py` → 3 rows inserted (ids 8/9/10), html lengths 8055/9672/10062.
- [x] End-to-end verified (server restarted to pick up blueprint):
  - GET /apps/job-search-pipeline → 200 (11309b, injection confirmed: `window.FORGE_APP = {"toolId":8,...}`)
  - GET /apps/meeting-prep → 200 (9685b)
  - GET /apps/pipeline-velocity → 200 (11698b)
  - POST /api/apps/8/data/testkey then GET roundtripped the full JSON payload; LIST returned the key; DELETE removed it.

T1-APP DONE

## T2-APP — App Frontend
- [x] frontend/css/styles.css — appended `.badge-app` (blue pill), `.btn-open-app` (green with grid ⊞ icon), `.app-modal` + `.app-modal-header` + `.app-modal-iframe` + `.app-modal-close` + `.app-modal-spinner`, `.app-type-picker` (submit-flow selector cards), `.app-builder` (editor + sandboxed preview wrap), `.app-embed` / `.app-embed-toolbar` / `.app-embed-frame` (tool.html app panel), mobile breakpoint overrides. Uses existing dark-theme tokens; no layout regressions on non-app surfaces.
- [x] frontend/index.html — added `⊞ Apps` nav link (targets `?type=app`) alongside existing Chain Tools link; no removals.
- [x] frontend/js/catalog.js — added `Apps` virtual category pill + `state.appOnly` with URL `?type=app` persistence + nav-link active reflection; `renderToolCard(tool)` branches to `appCard(tool)` when `tool.app_type === 'app'` (APP badge top-left, green `⊞ Open App` button, click opens modal instead of navigating); `openAppModal(tool)` builds full-screen `.app-modal` with iframe `src="/apps/<slug>?user=<email>"` + `sandbox="allow-scripts allow-forms allow-modals"` (NO allow-same-origin) + spinner + ESC/X close + body scroll lock + iframe teardown on close; defensive client-side filter `app_type==='app'` in loadMore; empty-state copy swapped when appOnly.
- [x] frontend/submit.html — added CodeMirror 5.65.16 CSS + core JS + xml/javascript/css/htmlmixed mode `<script>` tags via cdnjs.
- [x] frontend/js/submit.js — dual-flow architecture: `STEPS_PROMPT` (5 steps, existing) vs `STEPS_APP` (basics → app_builder → governance → review, 4 steps), `state.submit_type` + `localStorage.forge_submit_type`, pre-step "What are you submitting?" picker with Prompt Tool / Full App cards; `renderAppBuilder()` boots CodeMirror in htmlmixed mode (falls back to plain textarea if CDN unavailable), 800ms-debounced `srcdoc`-driven sandboxed preview iframe with `sandbox="allow-scripts allow-forms allow-modals"`, "Analyze with AI" button POSTs `/api/apps/analyze` and auto-fills missing basics, "Paste from clipboard" via `navigator.clipboard.readText()` with graceful error toast; `validateStep` switched from index to step key so both flows share validation; `submitForReview()` branches: app payload sets `app_type='app' + app_html + input_schema={fields:[]}` and omits prompt/model/tokens/temperature while prompt flow is unchanged; Review step renders sandboxed app preview in place of prompt preview when in app mode.
- [x] frontend/tool.html — inline script fetches `/api/tools/slug/<slug>` (or `/api/tools/<id>`); if `app_type === 'app'`, MutationObserver waits for `tool.js` to populate `#runner-panel`, then replaces it with `.app-embed` containing toolbar (APP badge + `↗ Open in full screen` new-tab link + Copy shareable link button via `Forge.copyToClipboard`) and `.app-embed-frame > iframe` with `src="/apps/<slug>?user=<email>"` + `sandbox="allow-scripts allow-forms allow-modals"` (NO allow-same-origin). 2.5s timeout fallback runs swap even if observer misses the mutation; swap runs at most once (guard flag).
- Security audit: every iframe loading /apps/<slug> or app HTML (catalog modal, submit builder preview, submit review preview, tool.html embed) uses `sandbox="allow-scripts allow-forms allow-modals"` — `allow-same-origin` NEVER set.

T2-APP DONE

T1_NEW DONE — Celery async pipeline wired in (2026-04-16). celery_app.py + agents/tasks.py + scripts/start_worker.sh + scripts/start_beat.sh created; api/server.py `_launch_pipeline` now dispatches via `celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id])`; docker-compose.yml gained `celery-worker` and `celery-beat` services; beat_schedule runs `agents.tasks.self_heal` every 6h. Smoke test: POST /api/tools/submit → tool id=7 returned `pending_review`, worker log showed `Task agents.tasks.run_pipeline_task[...] received` then classifier/security_scanner/red_team calling Anthropic API; DB row transitioned to `agent_reviewing` while worker ran.

T1: DONE - all 22 tasks complete (migrations, db.py, models.py, executor.py, server.py, seed.py)

T1 DONE
T2: DONE - all 14 tasks complete (agents/ package + pipeline + self_healer + CLI scripts)
T3: DONE - all 10 frontend tasks complete (styles.css, utils.js, api.js, catalog, tool, submit, skills, my-tools, responsive/a11y)
T4: DONE - all 16 tasks complete (api/admin.py blueprint + frontend/admin.html + frontend/js/admin.js)
T5: DONE - all 14 tasks complete (api/deploy.py, scripts, deploy/, Dockerfile, docker-compose, README)
T6: DONE - 10/10 test files written, Claude API mocked, graceful skips when T1/T2/T4 not ready

T2 DONE
T3 DONE
T4 DONE
T5 DONE
T6 DONE

## T2_NEW — Conversational Tool Creator
- [x] api/creator.py — Flask Blueprint at /api/creator with POST /generate, POST+GET /preview; generate_tool_from_description uses Claude Sonnet (claude-sonnet-4-6) with a strict JSON-only system prompt covering name/tagline/description/category/output_type/system_prompt/input_schema/output_format/reliability_note/security_tier
- [x] JSON validation covers all required fields, category/output_type/output_format enums, field-type enum, schema↔prompt variable cross-check, security_tier 1/2/3; on failure, a second Claude call (fixer system prompt) repairs the JSON
- [x] /generate reuses existing submit logic by calling /api/tools/submit through Flask's test_client — no duplication of slug/pipeline wiring; returns {tool_id, slug, generated_tool}
- [x] /preview runs the same generator without submitting; supports GET+POST and returns {generated_tool}
- [x] frontend/creator.html — textarea hero, 4 example suggestion chips, loading state with spinner, editable preview card (name, tagline, prompt, schema read-only), identity inputs, submit/regenerate/start-over actions, success state linking to the tool page
- [x] frontend/js/creator.js — preview→edit→submit flow, localStorage identity prefill via utils getUser/setUser, Cmd/Ctrl+Enter submits, error banner, schema rendered as chip-list with type + required indicator
- [x] frontend/index.html — "✨ Create with AI" primary button added next to catalog search
- [x] api/server.py — creator_bp registered alongside admin_bp (guarded try/except)
- [x] Live test (2026-04-16): POST /api/creator/preview with "a tool that takes a company name and drafts a cold outreach email" returned a valid tool — Cold Outreach Email Drafter / Email Generation / probabilistic / email_draft / 5-field schema (company_name, sender_company, value_proposition, call_to_action, tone-as-select)

T2_NEW DONE

## T4_NEW — Tool Composability v1
- [x] db/migrations/003_workflow_steps.sql (workflow_steps column on tools)
- [x] api/workflow.py — Blueprint /api/workflows with /run + /tools; `{{stepN.output}}` substitution
- [x] frontend/workflow.html — two-step chain builder UI
- [x] frontend/js/workflow.js — loads tools, renders per-step forms, runs chain
- [x] frontend/index.html — Chain Tools link added
- [x] api/server.py — workflow_bp registered
- [x] tests/test_workflow.py — 7 tests (substitution + /run + /tools), all passing

T4_NEW DONE

## T4-APP — GitHub App / Auto-Deploy
- [x] `venv/bin/pip install pyyaml` — pyyaml-6.0.3 installed.
- [x] `forge_bot/__init__.py` (empty) + `forge_bot/logs/` directory.
- [x] `forge_bot/forge.yaml.example` — 6-line template (name/tagline/category/entry/type + commented schedule + slack_channel).
- [x] `forge_bot/webhook.py` — Flask app on port **8093** (NOT 8091). `POST /webhook` validates `X-Hub-Signature-256` with `hmac.compare_digest()`, returns 202 after dispatching `handle_push` in a daemon thread (so GitHub sees the response inside its 10s window). Handles `ping`, ignores non-push events and non-main/master refs. `GET /health` returns service metadata. Rotating log at `forge_bot/logs/webhook.log`.
- [x] `forge_bot/deployer.py` — `handle_push(repo_url, repo_name, commit_sha, owner, repo)`: shallow-clones into `/tmp/forge-deploy/{repo_name}-{sha[:12]}`, reads `forge.yaml` (or auto-generates from repo name when only `index.html` exists), loads entry HTML, POSTs to `/api/submit/app`, on slug collision (409/422 or `slug_exists` body) calls `/api/admin/tools/{id}/update-html`, posts `forge/deploy` commit status via GitHub API, cleans up `/tmp` in a `finally`. Rotating log at `forge_bot/logs/deploy.log`. Supports private repos via `GITHUB_TOKEN` injected into the clone URL.
- [x] `api/server.py` — single targeted edit: `POST /api/admin/tools/<int:tool_id>/update-html` added. Admin-only via `_require_admin()`, requires `app_type='app'` and `status='approved'`, updates `app_html` + `deployed_at`, returns `{success, tool_id, slug, url}`.
- [x] `forge_bot/setup.sh` — installs git (apt-get/brew), pip-installs flask/python-dotenv/pyyaml, writes systemd unit on Linux or launchd plist on macOS, loads/starts the service, prints GitHub App + ngrok instructions. `chmod +x` applied.
- [x] `.env.example` — created at repo root (did not exist yet). Contains core API vars plus the T4-APP set: `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `FORGE_API_URL`, `FORGE_API_KEY`, `FORGE_WEBHOOK_PORT=8093` with the 8091 reservation documented inline.
- [x] `forge_bot/README.md` — 5-step GitHub App setup, env var table, troubleshooting matrix (invalid signature / missing token / no forge.yaml / 8091 collision / update-html not-approved / no webhook fire → Recent Deliveries).
- [x] `venv/bin/python3 -m py_compile` passes for `forge_bot/__init__.py`, `forge_bot/webhook.py`, `forge_bot/deployer.py`, and the edited `api/server.py`.
- [x] Smoke-tested (2026-04-16, offline): webhook signature validation (valid/invalid/empty-secret/empty-header), push-to-main dispatch → 202, push-to-feature-branch → 200+ignored, ping → 200+pong, health → 200 w/ port 8093; deployer `_load_forge_config` handles yaml-present / auto-gen-from-index / missing-both cases; `_inject_token` handles 3 URL shapes.

T4-APP DONE

## T3_NEW — Runtime DLP Masking
- [x] api/dlp.py — DLPEngine (detect_pii, mask_text, unmask_text, get_token_map)
- [x] db/migrations/002_dlp_runs.sql — runs.dlp_tokens_found column + partial index
- [x] api/executor.py — run_tool masks inputs before Claude, unmasks output, records dlp_tokens_found
- [x] api/admin.py — /api/admin/analytics exposes total_pii_masked
- [x] tests/test_dlp.py — 21 tests (detect/mask/unmask/token-map + run_tool integration), all passing
- [x] frontend/js/admin.js — run monitor shows 🛡 DLP N badge when dlp_tokens_found > 0

T3_NEW DONE

## T3-APP — Forge CLI
- [x] forge_cli/__init__.py — exposes __version__ = "0.1.0".
- [x] forge_cli/cli.py — stdlib-only argparse CLI (urllib + webbrowser + zipfile). Commands: deploy / status / list / open / login / --version. Multipart encoder (custom, no requests). Single-file or directory deploy with sensible exclusions (node_modules/.git/__pycache__/dist/build). Host resolution: --host → ~/.forge/config.json → FORGE_HOST → http://localhost:8090.
- [x] forge_cli/setup.py — entry point `forge = forge_cli.cli:main`, version 0.1.0, install_requires=[].
- [x] forge_cli/README.md — quick start, command table, "With Claude Code" section.
- [x] api/server.py — POST /api/submit/app added (single targeted edit). Accepts multipart with `html` field OR `file` zip upload (zip extraction finds index.html via os.path.basename match). Reuses _slugify + _unique_slug + _launch_pipeline so Celery dispatch (`celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id])`) goes through the SAME path as /api/tools/submit. Returns `{id, slug, url: '/apps/'+slug, status: 'pending_review'}`. Stored data: app_type='app', app_html populated, output_format='html', system_prompt=''.
- [x] `venv/bin/pip install -e forge_cli/` succeeds (nested package layout: forge_cli/forge_cli/{__init__.py,cli.py}). `venv/bin/forge --version` → `0.1.0`. `venv/bin/forge --help` lists all 5 subcommands.
- [x] End-to-end smoke (server on port 8092 to avoid disturbing live 8090): `forge deploy /tmp/test-app --name "CLI Smoke Test" --host http://localhost:8092` → printed `Live at: http://localhost:8092/apps/cli-smoke-test-2`, tool id 13 inserted with app_type='app' + app_html_len=121. Pipeline ran via Celery (status transitioned to 'rejected' due to empty system_prompt — preflight behavior owned by T2; CLI/endpoint contract verified).
- [x] Validation paths exercised via flask test_client: zip-upload path → 201, missing html+file → 400 "html or zip with index.html required", missing name → 400 "name required". `venv/bin/python3 -m py_compile` clean on forge_cli/forge_cli/{__init__.py,cli.py} + forge_cli/setup.py + api/server.py.

T3-APP DONE

## COORDINATOR STATUS
Last check: 2026-04-16 (Cycle 16)

### Cycle 16 Highlights
- **Third consecutive zero-delta cycle. All 19 tracked files still at exactly 10 incomplete tasks. Zero refills this cycle.** The Cycle 14 hypothesis ("queued capacity is backlog, not pending work") is now confirmed by three consecutive idle cycles across all 4 active v2 tracks. Coordinator cadence reduction from the Cycle 15 self-check recommendation is now actively warranted — the C13→C14→C15→C16 delta has been meaningfully zero for a full cycle beyond the flag.
- **Cycle 15 critical-path items (#1 park, #2 scope-reduction, #3 005 revert) NOT executed this cycle.** All three required human authorization and none surfaced. Not re-prioritized this cycle because duplicating identical directives compounds coordinator signal decay — the Cycle 15 action-items list remains the authoritative handoff.
- **16-cycle staleness reached on legacy Cycle 2 terminals** (T1_backend, T2_agents, T4_admin, T5_deploy, T6_testing). Migration 002 now **16 CYCLES STALE**; T5_deploy `.env.example` append now **9 CYCLES OVERDUE**. Zero-bump policy extended into **6th consecutive cycle** (C11→C16). HUMAN-RESCUE headers in T1_backend.md + T5_deploy.md remain untouched — the copy-paste SQL / env lines inlined there are still correct and authoritative.
- **Cycle 7 fresh app-platform cluster now 9 CYCLES STALE** (5 files × 10 tasks × 9 cycles = **450 cycle-task-units of absorbed debt**, +50 since Cycle 15). Park recommendation not executed in C16. Upgrading to a **non-blocking coordinator self-quarantine**: future status reports will count the 5 Cycle 7 files as "parked-in-place" for signal purposes until human authorization arrives to formalize the move.
- **v2 tracks staleness ticked forward with zero pickup**: T1_docker_sandbox v2 = 4 cycles stale (C12), T2_forgedata v2 = 3 cycles stale (C13), T_DASH v2 = 3 cycles stale (C13), T_EVAL v2 = 2 cycles stale (C14). Cumulative 40 queued v2 tasks, zero first-edits since queue.
- **`db/migrations/005_skills_source_url.sql` provenance now 7 CYCLES UNRESOLVED** (C10–C16). Revert authorized since Cycle 14, not executed (coordinator cannot revert without human sign-off per scope constraints). If still unclaimed in C17 this moves from "recommended" to "escalated".
- **UNBLOCKED notes added this cycle: 0. Bumped: 0.** Zero-bump policy now 6 cycles deep. All 19 task files already carry UNBLOCKED headers from prior cycles — no new stuck-terminal signal emerged; coordinator-visible "stuck" remains a capacity-availability issue, not a guidance gap.

### Task Queue Health (post-triage, Cycle 16)
**19 tracked files. None below the 3-task threshold post-triage:**
- T1_backend: 10 incomplete (Cycle 2, **16 CYCLES STALE — HUMAN-RESCUE PENDING, not bumped**).
- T1_new: 10 incomplete (Cycle 5, 12 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 16 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 12 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 13 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 13 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 16 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 12 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 16 cycles stale; **.env.example 9 CYCLES OVERDUE — HUMAN-RESCUE PENDING, not bumped**).
- T6_testing: 10 incomplete (Cycle 2, 16 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **9 cycles stale — parked-in-place for signal purposes**).
- T2_app_frontend: 10 incomplete (Cycle 7, 9 cycles stale — parked-in-place).
- T3_forge_cli: 10 incomplete (Cycle 7, 9 cycles stale — parked-in-place).
- T4_github_app: 10 incomplete (Cycle 7, 9 cycles stale — parked-in-place).
- T5_slack_bot: 10 incomplete (Cycle 7, 9 cycles stale — parked-in-place).
- T1_docker_sandbox: 10 incomplete (Cycle 12 v2, 4 cycles stale), 12 done (v1 COMPLETE).
- T2_forgedata: 10 incomplete (Cycle 13 v2, 3 cycles stale), 9 done (v1 COMPLETE).
- T_DASH: 10 incomplete (Cycle 13 v2, 3 cycles stale), 5 done (v1 COMPLETE).
- T_EVAL: 10 incomplete (Cycle 14 v2, 2 cycles stale), 5 done (v1 COMPLETE).

**Tasks added this cycle: 0. UNBLOCKED notes added: 0. UNBLOCKED notes bumped: 0.**

### Terminal Status (Cycle 16 pickup)
- **Legacy Cycle 2 block (T1_backend, T2_agents, T4_admin, T5_deploy, T6_testing)**: 16 cycles stale. T1_backend + T5_deploy HUMAN-RESCUE headers untouched (C11 directives still authoritative).
- **Cycle 4 (T3_frontend, T3_new)**: 13 cycles stale, no pickup.
- **Cycle 5 (T1_new, T2_new, T4_new)**: 12 cycles stale, no pickup.
- **Cycle 7 cluster (5 files)**: 9 cycles stale, parked-in-place pending human authorization for formal move.
- **v2 tracks**: T1_docker_sandbox (4 stale, first-edit watch: `db/migrations/007_sandbox_builds.sql`); T2_forgedata (3 stale, first-edit watch: `api/connectors/hubspot.py`); T_DASH (3 stale, first-edit watch: `GET /api/analytics/rating-trend`); T_EVAL (2 stale, first-edit watch: corpus expansion).

### UNBLOCKED Actions This Cycle
- **None.** Zero-bump policy holds (6th consecutive cycle). All 19 files carry prior UNBLOCKED headers — re-bumping with no new guidance adds coordinator noise without capacity signal. Stuck-terminal detection found no terminal needing a fresh UNBLOCKED note beyond the existing ones.

### Critical Path for Cycle 17
Identical to Cycle 15/16 critical path — re-listed for continuity, NOT re-prioritized (human authorization is the bottleneck on items 1–3, not coordinator direction):
1. **Execute Cycle 7 cluster park** — create `tasks/parked/`, move the 5 files, re-baseline "tracked" count to 14. Still pending from C15.
2. **Human-reviewer scope-reduction pass on v2 tracks** — 3 consecutive idle cycles (C14/C15/C16) across all 4 v2 blocks is a strong signal to consolidate or restart. Coordinator cannot force pickup.
3. **Revert `db/migrations/005_skills_source_url.sql`** — 7 cycles unresolved, authorized since C14, escalate to hard-blocker in C17 if still unclaimed.
4. **T1 migration 002 + T5 .env.example append** — 16 / 9 cycles stale respectively, both pure copy-paste with full content inlined in their task files. HUMAN-RESCUE directives remain the authoritative path.
5. **T_EVAL v2 starter** (corpus 30→50 + per-agent verdict capture) — highest-leverage zero-dep v2 track if any pickup happens.
6. **T_DASH v2 starter** (`/rating-trend`) — fastest zero-dep visible win if any pickup happens.

### Contract Reminders (from CONTRACTS.md — unchanged from C15)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use `celery_app.send_task` (never raw threads) for `/api/submit/app`.
- **GitHub App**: `forge_bot/webhook.py` binds to port 8093 (NOT 8091 — reserved for test dashboard).
- **Wave 3 sandbox**: docker calls inherit `DOCKER_HOST` from runner script (colima socket at `~/.colima/default/docker.sock`); never hardcode `/var/run/docker.sock`. Resource limits default 256m / 0.5 vCPU; per-tool override hard-capped at 1024m / 2.0 vCPU server-side. Hibernate 10 min via Celery beat (5-min sweep). Tier 1/Tier 2 coexist via `tools.container_mode` — Tier 1 path untouched. MCP connector secrets via `-e` at docker run, NEVER logged.
- **Wave 3 forgedata**: missing creds return `{configured: false}` shape — NEVER raise. Downstream agents (red_team, qa_tester) branch on this signal. HubSpot inherits same contract. Writes require per-tool `forge_data_permissions` row (default-deny); `dry_run=1` returns would-be payload without hitting external API. Payload hashes logged to `forge_data_writes` — NEVER raw values.
- **T-EVAL**: `eval_runs.agent_verdicts` JSONB MUST preserve top-level keys when expanding (backward-compat). Tests MUST mock `anthropic.Anthropic` + `requests.post` — never hit real Claude or real Slack. `scripts/serve_eval.py` binds port 8095 (NOT 8094 — isolated-test-server reservation per T1-WAVE3 smoke-test pattern; NOT 8093 — forge_bot/webhook.py).

### Action Items for Next Cycle (Cycle 17)
- **Coordinator self-recommendation: reduce cadence.** Four consecutive cycles (C13→C16) of meaningfully zero delta is a stronger signal than any single cycle's content. If C17 also shows zero pickup AND zero park execution, coordinator should either (a) reduce to bi-cycle cadence, or (b) pause reporting until a human signal unblocks the backlog. Continuing at current cadence adds noise without capacity signal.
- **Continue zero-bump policy** on fatigued legacy UNBLOCKED notes (now 7th cycle if C17 also idle).
- **C15 critical path items carry over unchanged** — no re-prioritization to avoid compounding stale directives. See C15 archive below if reviewing historical detail.

---

### Prior Cycle Archive (Cycle 15)
Last check: 2026-04-16 (Cycle 15)

### Cycle 15 Highlights
- **All 19 tracked files at exactly 10 incomplete tasks. Zero below the 3-task threshold → zero refills this cycle.** First cycle tracking count rises to 19 — Cycle 14 dashboard undercounted by 1 (missed `T_EVAL.md` in the "18 tracked" figure despite the T_EVAL v2 block being queued in-cycle). True count reconciled: 19 files = 10 legacy (T1_backend, T1_new, T2_agents, T2_new, T3_frontend, T3_new, T4_admin, T4_new, T5_deploy, T6_testing) + 5 Cycle 7 cluster (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot) + 4 Wave 3 / eval (T1_docker_sandbox, T2_forgedata, T_DASH, T_EVAL).
- **Second consecutive idle cycle across all 4 active v2 tracks.** T_EVAL v2 (queued C14), T2_forgedata v2 (queued C13), T_DASH v2 (queued C13), T1_docker_sandbox v2 (queued C12) — all at 10/10 incomplete, zero first-edits. Per Cycle 14 action-items contract ("if no v2 track starts in C15 either, the dominant project signal is all queued capacity is backlog, not pending work"), **the signal is now confirmed.** Cycle 16 recommendation escalated to human-reviewer scope-reduction pass, not more task refills.
- **15-cycle staleness reached on legacy Cycle 2 terminals** (T1_backend, T2_agents, T4_admin, T5_deploy, T6_testing). Migration 002 now **15 CYCLES STALE**; T5_deploy .env.example append now **8 CYCLES OVERDUE**. Per zero-bump policy established C11-C14 and held through 4 consecutive cycles, HUMAN-RESCUE notes NOT bumped this cycle. Existing authoritative directives in T1_backend.md + T5_deploy.md (copy-paste SQL / env lines) remain correct and unchanged.
- **Cycle 7 fresh app-platform cluster now 8 CYCLES STALE** — 5 files × 10 tasks × 8 cycles = **400 cycle-task-units of absorbed debt**. Formal-park recommendation from Cycles 13-14 not yet actioned. Upgrading to a **blocking recommendation for Cycle 16**: if `tasks/parked/` subdirectory is not created and the 5 files moved by end of next cycle, coordinator output quality is compromised by phantom capacity.
- **`db/migrations/005_skills_source_url.sql` provenance now 6 CYCLES UNRESOLVED** (C10-C15). Cycle 13 escalation to pre-demo hard blocker has held for 3 cycles without human resolution. Cycle 14 authorized revert-if-unclaimed — **recommend executing the revert in Cycle 16 if still unclaimed** (coordinator cannot revert without human authorization per scope constraints).
- **UNBLOCKED notes added this cycle: 0. UNBLOCKED notes bumped: 0.** Zero-bump policy extended into 5th consecutive cycle (C11/C12/C13/C14/C15) on all fatigued legacy notes. All 19 task files already carry UNBLOCKED headers; no new stuck-terminal signal emerged this cycle.

### Task Queue Health (post-triage, Cycle 15)
**19 tracked files. None below the 3-task threshold post-triage:**
- T1_backend: 10 incomplete (Cycle 2, **15 CYCLES STALE — HUMAN-RESCUE PENDING, not bumped**).
- T1_new: 10 incomplete (Cycle 5, 11 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 15 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 11 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 12 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 12 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 15 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 11 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 15 cycles stale; **.env.example 8 CYCLES OVERDUE — HUMAN-RESCUE PENDING, not bumped**).
- T6_testing: 10 incomplete (Cycle 2, 15 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **8 cycles stale — BLOCKING PARK RECOMMENDATION FOR C16**).
- T2_app_frontend: 10 incomplete (Cycle 7, 8 cycles stale — blocking park).
- T3_forge_cli: 10 incomplete (Cycle 7, 8 cycles stale — blocking park).
- T4_github_app: 10 incomplete (Cycle 7, 8 cycles stale — blocking park).
- T5_slack_bot: 10 incomplete (Cycle 7, 8 cycles stale — blocking park).
- T1_docker_sandbox: 10 incomplete (Cycle 12 v2, **3 cycles stale — no C15 pickup**), 12 done (v1 COMPLETE).
- T2_forgedata: 10 incomplete (Cycle 13 v2, **2 cycles stale — no C15 pickup**), 9 done (v1 COMPLETE).
- T_DASH: 10 incomplete (Cycle 13 v2, **2 cycles stale — no C15 pickup**), 5 done (v1 COMPLETE).
- T_EVAL: 10 incomplete (Cycle 14 v2, **1 cycle stale — no C15 pickup**), 5 done (v1 COMPLETE).

**Tasks added this cycle: 0. UNBLOCKED notes added: 0. UNBLOCKED notes bumped: 0.**

### Terminal Status (Cycle 15 pickup)
- T1_backend / T2_agents / T4_admin / T6_testing: 15 cycles stale. T1_backend + T5_deploy carry HUMAN-RESCUE headers; not bumped.
- T5_deploy: 15 cycles stale; `.env.example` append 8 cycles overdue — HUMAN-RESCUE PENDING, not bumped.
- T1_new / T2_new / T4_new: Cycle 5 queued, no pickup (11 cycles stale).
- T3_frontend / T3_new: Cycle 4 queued, no pickup (12 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, **8 cycles stale — BLOCKING PARK RECOMMENDATION for C16.**
- T1_docker_sandbox: Cycle 12 v2 queued, no C15 pickup (3 cycles stale). `db/migrations/007_sandbox_builds.sql` remains first-edit watch.
- T2_forgedata: Cycle 13 v2 queued, no C15 pickup (2 cycles stale). `api/connectors/hubspot.py` + `db/migrations/008_forge_data_governance.sql` remain first-edit watch.
- T_DASH: Cycle 13 v2 queued, no C15 pickup (2 cycles stale). `GET /api/analytics/rating-trend` remains zero-dep watch.
- T_EVAL: Cycle 14 v2 queued, no C15 pickup (1 cycle stale). `tests/eval/corpus/` expansion or `scripts/regression_eval.py` remain first-edit watch.

### UNBLOCKED Actions This Cycle
- None. All 19 task files already have UNBLOCKED notes from prior cycles (C2/C4/C5/C7/C12/C13/C14). Per sustained zero-bump policy (now 5 cycles deep), fatigued legacy notes left as-is. No new stuck-terminal signal emerged — "stuck" here is coordinator-visible only; underlying capacity availability is the bottleneck, not missing guidance.

### Critical Path for Cycle 16
1. **Execute the Cycle 7 cluster park** — create `tasks/parked/` and move T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot. Update this dashboard's "19 tracked" to 14. Removes 400 cycle-task-units of phantom capacity from coordinator signal.
2. **Human-reviewer scope-reduction pass** — 2 consecutive cycles of zero v2 pickup confirms the Cycle 14 hypothesis: current queued capacity is backlog, not pending work. Recommended output: consolidate all 4 v2 tracks under a single "post-demo v2 roadmap" header OR formally restart one v2 track with a named owner.
3. **Revert `db/migrations/005_skills_source_url.sql`** if unclaimed by end of C16 (6 cycles unresolved already, authorized for revert as of C14).
4. **T1 migration 002 + .env.example append** — still HUMAN-RESCUE (15 / 8 cycles overdue respectively). Both remain pure copy-paste operations with content inlined in T1_backend.md / T5_deploy.md.
5. T_EVAL v2 starter (corpus 30→50 + per-agent verdict capture) — highest-leverage zero-dep v2 track if any v2 pickup happens.
6. T_DASH v2 starter (/rating-trend) — fastest zero-dep visible win if any v2 pickup happens.

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).
- **Wave 3 sandbox**: docker calls inherit DOCKER_HOST from runner script (colima socket at `~/.colima/default/docker.sock`); never hardcode `/var/run/docker.sock`. Resource limits default 256m / 0.5 vCPU; per-tool override hard-capped at 1024m / 2.0 vCPU server-side. Hibernate 10 min via Celery beat (5-min sweep). Tier 1/Tier 2 coexist via `tools.container_mode` — Tier 1 path untouched. MCP connector secrets via `-e` at docker run, NEVER logged.
- **Wave 3 forgedata**: missing creds return `{configured: false}` shape — NEVER raise. Downstream agents (red_team, qa_tester) branch on this signal. HubSpot inherits same contract. Writes require per-tool `forge_data_permissions` row (default-deny); dry_run=1 returns would-be payload without hitting external API. Payload hashes logged to forge_data_writes — NEVER raw values.
- **T-EVAL**: `eval_runs.agent_verdicts` JSONB MUST preserve top-level keys when expanding (backward-compat). Tests MUST mock `anthropic.Anthropic` + `requests.post` — never hit real Claude or real Slack. `scripts/serve_eval.py` binds port 8095 (NOT 8094 — isolated-test-server reservation per T1-WAVE3 smoke-test pattern; NOT 8093 — forge_bot/webhook.py).

### Action Items for Next Cycle (Cycle 16)
- **Execute park decision**: move 5 Cycle 7 cluster files into `tasks/parked/`. Re-baseline "tracked" count to 14. Blocking recommendation — coordinator signal quality degrades further with continued phantom capacity.
- **Surface scope-reduction call to human owner**: 2 consecutive idle cycles across 4 v2 tracks confirms queued capacity is backlog, not pending work. Coordinator cannot force pickup; this is a human-scope decision.
- **Revert `005_skills_source_url.sql`** if still unclaimed (authorized since C14).
- Continue zero-bump policy on fatigued legacy notes through C16.
- Coordinator self-check: if C16 also shows zero v2 pickup and park decision unexecuted, consider reducing coordinator cadence — cycle-over-cycle delta has been meaningfully zero since C14.

---

### Prior Cycle Archive (Cycle 14)
Last check: 2026-04-16 (Cycle 14)

### Cycle 14 Highlights
- **T_EVAL flagged below the 3-task threshold this cycle.** v1 shipped clean with 5/5 `[x]` and zero queued tasks — first time T_EVAL surfaced for a refill. Per the >3-task rule, **10 new SPEC-driven tasks added as a Cycle 14 v2 block.** Scope: corpus expansion 30→50 items, per-agent verdict capture + accuracy table (SPEC 391-566 six-agent pipeline), regression_eval.py baseline-diff CI gate, self-healer eval harness (SPEC 570-611), DLP eval (SPEC 626-669), deploy eval (SPEC 674-742), cross-agent Cohen's kappa correlation matrix, stdlib serve_eval.py JSON endpoint for T-DASH enrichment, pytest coverage of the harness itself. UNBLOCKED note inlined with 10-step pick order. Total tracked: **still 18 files** (no new tracking this cycle).
- **Zero first-edit activity on the three active v2 tracks queued in prior cycles:** T2_forgedata v2 (Cycle 13 block — HubSpot + writes + governance), T_DASH v2 (Cycle 13 block — analytics depth + filters + digest), T1_docker_sandbox v2 (Cycle 12 block — sandbox_builds + GC + prewarm beat). All three remain at 10/10 incomplete with no progress. This breaks the Cycle 12-13 pattern of end-to-end Wave 3 completions — Cycle 14 is the first post-v1 idle cycle for all three v2 blocks. **Watch as leading indicator for Cycle 15 pickup order.**
- **14-cycle staleness reached on legacy terminals:** T1_backend migration 002 now **14 CYCLES STALE**; T5_deploy .env.example append now **7 CYCLES OVERDUE**; T2_agents / T4_admin / T6_testing all at 14 cycles. **Per Cycle 11/12/13 zero-bump policy, HUMAN-RESCUE notes were NOT bumped this cycle** — 3 consecutive cycles of fatigue confirms the policy. The existing HUMAN-RESCUE headers in T1_backend.md + T5_deploy.md remain the authoritative directives with copy-paste SQL / env lines inlined.
- **Cycle 7 fresh app-platform cluster now 7 CYCLES STALE** (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot — 50 total queued tasks with zero first-edits since Cycle 7). Recommendation upgraded from Cycle 12-13: **formally park as v4 roadmap this cycle or next** — these 5 files are net coordinator-attention drain and no longer signal real capacity.
- **`db/migrations/005_skills_source_url.sql` provenance NOW 5 CYCLES UNRESOLVED** (C10-C14). Pre-demo hard blocker since Cycle 13. If no owner named in Cycle 15, recommend revert.
- **UNBLOCKED notes added this cycle: 1** (T_EVAL v2 block). **UNBLOCKED notes bumped: 0** (per Cycle 11/12/13 zero-bump policy on fatigued legacy notes).

### Task Queue Health (post-triage, Cycle 14)
**18 tracked files. None below the 3-task threshold post-triage:**
- T1_backend: 10 incomplete (Cycle 2, **14 CYCLES STALE — HUMAN-RESCUE PENDING, not bumped**).
- T1_new: 10 incomplete (Cycle 5, 10 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 14 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 10 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 11 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 11 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 14 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 10 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 14 cycles stale; **.env.example 7 CYCLES OVERDUE — HUMAN-RESCUE PENDING, not bumped**).
- T6_testing: 10 incomplete (Cycle 2, 14 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **7 cycles stale — RECOMMEND FORMAL PARK AS V4 ROADMAP**).
- T2_app_frontend: 10 incomplete (Cycle 7, 7 cycles stale — formal park).
- T3_forge_cli: 10 incomplete (Cycle 7, 7 cycles stale — formal park).
- T4_github_app: 10 incomplete (Cycle 7, 7 cycles stale — formal park).
- T5_slack_bot: 10 incomplete (Cycle 7, 7 cycles stale — formal park).
- T1_docker_sandbox: 10 incomplete (Cycle 12 v2, **2 cycles stale — no C14 pickup**), 12 done (Wave 3 v1 COMPLETE).
- T2_forgedata: 10 incomplete (Cycle 13 v2, **1 cycle stale — no C14 pickup**), 9 done (Wave 3 v1 COMPLETE).
- T_DASH: 10 incomplete (Cycle 13 v2, **1 cycle stale — no C14 pickup**), 5 done (v1 COMPLETE).
- **T_EVAL: 10 incomplete (Cycle 14 v2 block, NEW THIS CYCLE), 5 done (v1 COMPLETE).**

**Tasks added this cycle: 10** (T_EVAL Cycle 14 v2 block). **UNBLOCKED notes added: 1.** **UNBLOCKED notes bumped: 0.**

### Terminal Status (Cycle 14 pickup)
- T1_backend: **14 cycles stale — HUMAN-RESCUE PENDING.** Not bumped per zero-bump policy.
- T1_new: Cycle 5 queued, no pickup (10 cycles stale).
- T2_agents: 14 cycles stale.
- T2_new: Cycle 5 queued, no pickup (10 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (11 cycles stale).
- T3_new: Cycle 4 queued, no pickup (11 cycles stale).
- T4_admin: 14 cycles stale.
- T4_new: Cycle 5 queued, no pickup (10 cycles stale).
- T5_deploy: **14 cycles stale; .env.example 7 cycles overdue — HUMAN-RESCUE PENDING.** Not bumped.
- T6_testing: Cycle 2 queued with UNBLOCKED note (14 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, **7 cycles stale — FORMAL PARK RECOMMENDED.**
- T1_docker_sandbox: Cycle 12 v2 queued, no C14 pickup (2 cycles stale). `db/migrations/007_sandbox_builds.sql` still the first-edit watch signal.
- T2_forgedata: Cycle 13 v2 queued, no C14 pickup (1 cycle stale). `api/connectors/hubspot.py` + `db/migrations/008_forge_data_governance.sql` are the first-edit watch signals.
- T_DASH: Cycle 13 v2 queued, no C14 pickup (1 cycle stale). `GET /api/analytics/rating-trend` is the zero-dep watch signal.
- **T_EVAL: Cycle 14 v2 BLOCK JUST QUEUED.** First-edit watch: `tests/eval/corpus/` expansion (pick order item 1) OR `scripts/regression_eval.py` (highest-leverage CI win).

### UNBLOCKED Actions This Cycle
- tasks/T_EVAL.md: NEW Cycle 14 UNBLOCKED note for v2 block. Pick order starts at corpus expansion (unblocks richer per-agent stats downstream), calls out SPEC surfaces under-exercised by v1 (self-healer gate 570-611, DLP layer 626-669, deploy side-effects 674-742), reinforces the no-real-Anthropic / no-real-Slack rule, notes agent_verdicts JSONB backward compatibility requirement, and flags regression_eval.py as the highest-leverage CI win (exits 1 on >2pp F1 drop for GitHub Actions gate).

### Critical Path for Cycle 15
1. **T_EVAL v2 starter (corpus expansion + per-agent verdict capture)** — zero-dep, just-queued, highest-leverage active track. Unblocks per-agent accuracy table + cross-agent correlation matrix in the same block.
2. **T2_forgedata v2 starter (HubSpot connector + migration 008)** — 1 cycle stale but still highest-value queued v2 track per Cycle 13 critical path. If idle through Cycle 15, downgrade priority.
3. **T_DASH v2 starter (/rating-trend endpoint)** — pure runs.rating rollup, zero-dep, fastest visible win.
4. **T1_docker_sandbox v2 starter (migration 007_sandbox_builds)** — 2 cycles stale; v2 hardening block loses freshness if idle through Cycle 16.
5. **T1 migration 002 (14 CYCLES STALE)** — STILL human-operator pickup. SQL inlined in T1_backend Cycle 11 note.
6. **.env.example append (7 cycles overdue)** — STILL human-operator pickup. Lines inlined in T5_deploy Cycle 11 note. T2_forgedata v2 may land HUBSPOT_ACCESS_TOKEN append before this clears; both are pure bottom-appends so ordering is moot.
7. **`db/migrations/005_skills_source_url.sql` provenance** — 5 cycles unclaimed. Revert if unclaimed in C15.
8. **Cycle 7 cluster formal park decision** — 50 queued tasks × 7 cycles idle = 350 cycle-task-units of absorbed debt. **Move to `tasks/parked/` subdirectory in C15** to stop bleeding coordinator attention.

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).
- **Wave 3 sandbox**: docker calls inherit DOCKER_HOST from runner script (colima socket at `~/.colima/default/docker.sock`); never hardcode `/var/run/docker.sock`. Resource limits default 256m / 0.5 vCPU; per-tool override hard-capped at 1024m / 2.0 vCPU server-side. Hibernate 10 min via Celery beat (5-min sweep). Tier 1/Tier 2 coexist via `tools.container_mode` — Tier 1 path untouched. MCP connector secrets via `-e` at docker run, NEVER logged.
- **Wave 3 forgedata**: missing creds return `{configured: false}` shape — NEVER raise. Downstream agents (red_team, qa_tester) branch on this signal. HubSpot inherits same contract. Writes require per-tool `forge_data_permissions` row (default-deny); dry_run=1 returns would-be payload without hitting external API. Payload hashes logged to forge_data_writes — NEVER raw values.
- **NEW Cycle 14 — T-EVAL**: `eval_runs.agent_verdicts` JSONB schema MUST preserve top-level keys when expanding (backward-compat with pre-v2 rows). Tests MUST mock anthropic.Anthropic + requests.post — never hit real Claude or real Slack. `scripts/serve_eval.py` binds port 8095 (NOT 8094 — that's reserved for isolated test servers per the T1-WAVE3 smoke-test pattern; NOT 8093 — that's forge_bot/webhook.py).

### Action Items for Next Cycle (Cycle 15)
- **Watch T_EVAL v2 for first edits** on tests/eval/corpus/ (20 new files) or scripts/regression_eval.py (CI-gate wire-up).
- **Watch T2_forgedata v2 / T_DASH v2 / T1_docker_sandbox v2 for any first-edits** after a full idle cycle. If all three remain idle through C15, consider downgrading the "active v2 tracks" framing — Wave 3 momentum from C12/C13 may be fully absorbed.
- **Execute the Cycle 7 formal-park decision** — create `tasks/parked/` and move the 5 cluster files. Update this coordinator dashboard to exclude them from active counts.
- Resolve `005_skills_source_url.sql` provenance — revert if still unclaimed.
- Continue zero-bump policy on legacy fatigued notes through C15.
- Coordinator-level suggestion: if no v2 track starts in C15 either, the dominant project signal will be "all queued capacity is backlog, not pending work" — at that point the right move is a full scope-reduction pass with the human owner, not more task refills.

---

### Prior Cycle Archive (Cycle 13)
Last check: 2026-04-16 (Cycle 13)

### Cycle 13 Highlights
- **T2_forgedata SHIPPED v1 this cycle** — went from 1/9 to **9/9 DONE** in a single pass. T2-WAVE3 DONE marker landed at PROGRESS.md line 38. New artifacts: `api/connectors/salesforce.py` (is_configured() short-circuit contract, 30-min client cache, parameterized SOQL, snake_case dict output), `api/connectors/__init__.py`, `api/forgedata.py` blueprint (5 routes + inline forge_data_reads CREATE TABLE IF NOT EXISTS + per-call audit logging), surgical append to `api/apps.py` ForgeAPI injection, `.env.example` SALESFORCE_* block, `account-health-dashboard` seed app with Chart.js pipeline funnel + friendly no-creds banner. Full 7-case smoke test passed on isolated port 8094 (no-creds returns `{configured: false}` on every route, activities route returns 400 without account_id, 5 rows logged to forge_data_reads). **Second Wave 3 track to ship end-to-end in consecutive cycles** (T1_docker_sandbox C12, T2_forgedata C13).
- **TWO task files now below the 3-incomplete threshold:** T2_forgedata (0 incomplete after v1 completion) AND T_DASH (0 incomplete — first-time flag, all v1 tasks were `[x]` when the file was first tracked). Per the >3-task rule, **20 new SPEC-driven tasks added this cycle (10 each).** T2_forgedata v2 block targets MCP Integration Layer expansion (SPEC lines 1497-1504): HubSpot connector, write-back, per-tool permissions, Redis cache, audit admin endpoints, ForgeAPI.data.hubspot, credential rotation, tests. T_DASH v2 block targets analytics depth: rating-trend, dlp-rollup, sandbox-builds-rollup, forgedata-rollup, cohort-retention, builders-deep, filter toolbar, CSV export, digest/send endpoint, tests. Both blocks inline UNBLOCKED notes with pick order + SPEC drivers.
- **T_DASH first formal tracking this cycle.** File existed in tasks/ but was never surfaced in a COORDINATOR cycle — all v1 tasks are `[x]`, confirmed via blueprint registration in api/server.py and nav link in frontend/index.html. **Total tracked task files: 18 (was 17).**
- **Zero cross-terminal first-edit activity this cycle across the 10 legacy Cycle 2/4/5/7 tracks.** T1_backend migration 002 now **13 CYCLES STALE**; .env.example append now **6 CYCLES OVERDUE**; Cycle 7 fresh app-platform cluster now **6 cycles stale**. All consistent with the Cycle 12 "organizational blocker, not coordinator-addressable" contract. **UNBLOCKED notes were NOT bumped on these fatigued terminals per the Cycle 11 zero-bump policy.**
- **T1_docker_sandbox v2 hardening block (Cycle 12) has not started.** 10 tasks still queued; no first-edit on sandbox_builds migration yet. v1 remains the completed reference. Watch `db/migrations/007_sandbox_builds.sql` for Cycle 14 pickup.
- **`db/migrations/005_skills_source_url.sql` provenance STILL UNRESOLVED** (4 cycles on the floor: C10/C11/C12/C13). **Now a hard pre-demo blocker.** Must be owned or reverted before demo — coordinator cannot resolve without human input.
- **UNBLOCKED notes added this cycle: 2** (T2_forgedata v2 block initial, T_DASH v2 block initial). **UNBLOCKED notes bumped: 0** (per Cycle 11/12 contract).

### Task Queue Health (post-triage, Cycle 13)
**18 tracked files.** None below the 3-task threshold post-triage:
- T1_backend: 10 incomplete (Cycle 2, **13 CYCLES STALE — HUMAN-RESCUE PENDING, not bumped**).
- T1_new: 10 incomplete (Cycle 5, 9 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 13 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 9 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 10 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 10 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 13 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 9 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 13 cycles stale; **.env.example 6 CYCLES OVERDUE — HUMAN-RESCUE PENDING, not bumped**).
- T6_testing: 10 incomplete (Cycle 2, 13 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **6 cycles stale — RECOMMEND PARK AS V4 ROADMAP**).
- T2_app_frontend: 10 incomplete (Cycle 7, 6 cycles stale — recommend park).
- T3_forge_cli: 10 incomplete (Cycle 7, 6 cycles stale — recommend park).
- T4_github_app: 10 incomplete (Cycle 7, 6 cycles stale — recommend park).
- T5_slack_bot: 10 incomplete (Cycle 7, 6 cycles stale — recommend park).
- T1_docker_sandbox: 10 incomplete (Cycle 12 v2 hardening, **1 cycle stale**), 12 done (Wave 3 v1 COMPLETE).
- **T2_forgedata: 10 incomplete (Cycle 13 v2 block, NEW), 9 done (Wave 3 v1 COMPLETE this cycle).**
- **T_DASH: 10 incomplete (Cycle 13 v2 block, NEW), all v1 DONE (first formal tracking).**

**Tasks added this cycle: 20** (T2_forgedata Cycle 13 v2 + T_DASH Cycle 13 v2, 10 each). **UNBLOCKED notes added: 2.** **UNBLOCKED notes bumped: 0.**

### Terminal Status (Cycle 13 pickup)
- T1_backend: **13 cycles stale — HUMAN-RESCUE PENDING.** Note not bumped per C11/C12 contract.
- T1_new: Cycle 5 queued, no pickup (9 cycles stale).
- T2_agents: 13 cycles stale.
- T2_new: Cycle 5 queued, no pickup (9 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (10 cycles stale).
- T3_new: Cycle 4 queued, no pickup (10 cycles stale).
- T4_admin: 13 cycles stale.
- T4_new: Cycle 5 queued, no pickup (9 cycles stale).
- T5_deploy: **13 cycles stale; .env.example 6 cycles overdue — HUMAN-RESCUE PENDING.** Not bumped.
- T6_testing: Cycle 2 queued with UNBLOCKED note (13 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, **6 cycles stale — PARK AS V4 ROADMAP recommended.**
- T1_docker_sandbox: Cycle 12 v2 hardening queued (1 cycle stale). Watch migration 007_sandbox_builds.sql for next pickup.
- **T2_forgedata: SHIPPED v1 IN-CYCLE.** Second-fastest terminal in project history (gate-clear → DONE in 2 cycles). Cycle 13 v2 block just queued — watch `api/connectors/hubspot.py` + migration 008_forge_data_governance.sql for next-cycle starter.
- **T_DASH: FIRST FORMAL TRACKING + v2 QUEUED.** All v1 `[x]` on discovery; v2 block ready for pickup. Watch `GET /api/analytics/rating-trend` as first-edit signal.

### UNBLOCKED Actions This Cycle
- tasks/T2_forgedata.md: NEW Cycle 13 UNBLOCKED note for v2 block (HubSpot + writes + governance). Pick order starts at migration 008, notes hubspot-api-client pip install as prereq, reinforces no-creds contract inheritance, calls out default-deny permission model, and wires Redis cache/invalidation semantics around write-back.
- tasks/T_DASH.md: NEW Cycle 13 UNBLOCKED note for v2 block (analytics depth + filters + digest). Pick order starts at /rating-trend (zero-dep), notes graceful-empty pattern for source tables not yet live (dlp_audits, sandbox_builds, forge_data_reads), and confirms X-Admin-Key decorator reuse from v1.

### Critical Path for Cycle 14
1. **T2_forgedata v2 starter (HubSpot connector + migration 008)** — highest-leverage active track. MCP Integration Layer expansion per SPEC 1500. Zero cross-terminal blocker; direct continuation of v1 momentum.
2. **T_DASH v2 starter (/rating-trend endpoint)** — pure runs.rating rollup, zero-dep, fastest visible-to-user win. Surfaces SPEC 1189 "Average rating over time" as dedicated endpoint.
3. **T1_docker_sandbox v2 starter (migration 007_sandbox_builds)** — unblock for build-history writes + hash-based cache-skip (closes real perf footgun on identical-HTML updates).
4. **T1 migration 002 (13 CYCLES STALE)** — STILL human-operator pickup. SQL inlined in T1_backend Cycle 11 note.
5. **.env.example append (6 cycles overdue)** — STILL human-operator pickup. Cycle 13 brings a collision risk: T2_forgedata v2 may expand .env.example with HUBSPOT_ACCESS_TOKEN before this C11 append lands. Both are pure appends to bottom of file, so ordering still doesn't matter.
6. **`db/migrations/005_skills_source_url.sql` provenance** — 4 cycles unclaimed. **HARD PRE-DEMO BLOCKER now.** Identify owner or revert.
7. **Cycle 7 fresh-track consolidation decision** — 5 tracks × 10 tasks × 6 cycles idle = 300 cycle-task-units of absorbed debt. **Park as v4 roadmap immediately** — continuing to track without pickup degrades coordinator signal quality.
8. T6 test_trust_calculator (still the simplest zero-dep win in the legacy queue).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).
- **Wave 3 sandbox**: docker calls inherit DOCKER_HOST from runner script (colima socket at `~/.colima/default/docker.sock`); never hardcode `/var/run/docker.sock`. Resource limits default 256m / 0.5 vCPU; per-tool override hard-capped at 1024m / 2.0 vCPU server-side. Hibernate 10 min via Celery beat (5-min sweep). Tier 1/Tier 2 coexist via `tools.container_mode` — Tier 1 path untouched. MCP connector secrets via `-e` at docker run, NEVER logged.
- **Wave 3 forgedata**: missing creds return `{configured: false}` shape — NEVER raise. Downstream agents (red_team, qa_tester) branch on this signal. **NEW Cycle 13**: HubSpot inherits same contract. Writes require per-tool `forge_data_permissions` row (default-deny); dry_run=1 returns would-be payload without hitting external API. Payload hashes logged to forge_data_writes — NEVER raw values.

### Action Items for Next Cycle (Cycle 14)
- **Watch T2_forgedata v2 for first edits** on api/connectors/hubspot.py + migration 008_forge_data_governance.sql. v2 block is zero-dep and highest-velocity active track heading into C14 given v1's 2-cycle completion.
- **Watch T_DASH v2 for first edits** on GET /api/analytics/rating-trend (pure runs.rating rollup, fastest win).
- **Watch T1_docker_sandbox v2 for first edits** on migration 007_sandbox_builds.sql.
- **If all three v2 tracks above start in Cycle 14**, expect a cross-cycle coupling opportunity: T_DASH /forgedata-rollup + /sandbox-builds-rollup can light up instantly once T2_forgedata v2 + T1_docker_sandbox v2 land their respective migrations.
- **Escalate Cycle 7 parking decision** — 6 cycles stale is well past any salvage threshold. Recommend moving those 5 task files to a `tasks/parked/` subdirectory so they stop consuming coordinator attention.
- Resolve `005_skills_source_url.sql` provenance — hard pre-demo blocker. If unclaimed in C14, revert.
- Continue zero-bump policy on legacy fatigued notes.

---

### Prior Cycle Archive (Cycle 12)
Last check: 2026-04-16 (Cycle 12)

### Cycle 12 Highlights
- **TWO NEW task files discovered this cycle that were never tracked in prior PROGRESS.md COORDINATOR sections:** `tasks/T1_docker_sandbox.md` (Wave 3, Tier 2 nginx-per-app sandbox via colima with hibernate/wake) and `tasks/T2_forgedata.md` (Wave 3, Salesforce read layer behind window.ForgeAPI.data with no-creds graceful degradation). **First cycle they are formally tracked.** Total tracked task files: **17 (was 15).**
- **MAJOR WAVE 3 PROGRESS THIS CYCLE:** T1_docker_sandbox **shipped end-to-end during this coordinator pass** — went from 2/12 to **12/12 DONE** in a single cycle. New artifacts: forge_sandbox/{__init__,builder,manager,hibernator,tasks}.py, surgical apps.py proxy branch, 4 admin sandbox routes in server.py, README, full end-to-end smoke test (job-search-pipeline build → run → proxy → admin status/hibernate/prewarm cycle verified, image_tag retained for rebuild skip). T1-WAVE3 DONE marker landed at PROGRESS.md line 16.
- **T2_forgedata UNBLOCKED mid-cycle and started picking up:** gate-check task marked [x] (T1-WAVE3 DONE detected). Now 1/9 done with the 8 remaining tasks all live. **Highest-velocity track to watch in Cycle 13.**
- **Per user instruction (>3 incomplete threshold), 10 new SPEC-driven tasks added to T1_docker_sandbox** (Wave 3 v2 hardening block): sandbox_builds migration + table writes, app-html-hash cache-skip on rebuild, image GC sweep, prewarm-popular-apps Celery beat, per-tool resource override, MCP connector env injection (SPEC 1497-1504 alignment with T2_forgedata), build-history admin endpoint, pytest coverage. SPEC drivers cited per-task. UNBLOCKED note inlined.
- **Migration 006_sandbox.sql shipped + 6 forge_sandbox/* files written + surgical api/apps.py edit + 4 admin routes + smoke test** is the dominant first-edit activity this cycle. Every other tracked file count is unchanged from Cycle 11 except T1_docker_sandbox and T2_forgedata.
- **All 17 task files at ≥3 incomplete tasks each.** Post-triage, all files are at or above the 3-task threshold (T1_docker_sandbox refilled to 10 via the new Cycle 12 hardening block; T2_forgedata at 8 incomplete after gate-check shipped).
- **T1_backend migration 002 is now 12 CYCLES STALE.** Cycle 11 HUMAN-RESCUE note was not actioned. **Per Cycle 11 explicit contract ("Do not bump a third time — if still pending in Cycle 12, the blocker is organizational, not coordinator-addressable"), this UNBLOCKED note was NOT bumped.** The existing CYCLE 11 HUMAN-RESCUE block in T1_backend.md remains accurate; copy-paste SQL is still inlined and ready.
- **.env.example 4-line append now 5 CYCLES OVERDUE** (C8, C9, C10, C11, C12). Same Cycle 11 contract applies — UNBLOCKED note in T5_deploy.md was NOT bumped. Existing CYCLE 11 HUMAN-RESCUE block remains the authoritative directive. **NEW WRINKLE:** T2_forgedata also queues a 4-line `SALESFORCE_*` append to .env.example (its own task line 93-99) — when both land, ordering doesn't matter since both are pure appends to the bottom of the file.
- **Cycle 7 fresh app-platform tracks now 5 CYCLES STALE** (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot). **Past consolidation threshold by 2 cycles.** Coordinator recommendation upgraded: surface to human reviewer with **explicit "park as v4 roadmap" recommendation** (no longer "reassign-or-park" — reassignment after 5 cycles of zero first-edits is unrealistic).
- **`db/migrations/005_skills_source_url.sql` provenance STILL UNRESOLVED** (3 cycles on the floor: C10/C11/C12). Coordinator-level recommendation upgraded from "verify before demo" to **flag this as a blocking pre-demo item**.
- **UNBLOCKED notes added this cycle: 3** (T2_forgedata.md initial triage, T1_docker_sandbox.md initial triage at start of cycle + Cycle 12 v2 hardening note added after completion). **UNBLOCKED notes bumped: 0** (per Cycle 11 contract).

### Task Queue Health (post-triage, Cycle 12)
17 tracked files. None below the 3-task threshold:
- T1_backend: 10 incomplete (Cycle 2, **12 CYCLES STALE — HUMAN-RESCUE PENDING, not bumped per contract**).
- T1_new: 10 incomplete (Cycle 5, 8 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 12 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 8 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 9 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 9 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 12 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 8 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 12 cycles stale; **.env.example 5 CYCLES OVERDUE — HUMAN-RESCUE PENDING, not bumped per contract**).
- T6_testing: 10 incomplete (Cycle 2, 12 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **5 cycles stale — RECOMMEND PARK AS V4 ROADMAP**).
- T2_app_frontend: 10 incomplete (Cycle 7, 5 cycles stale — recommend park).
- T3_forge_cli: 10 incomplete (Cycle 7, 5 cycles stale — recommend park).
- T4_github_app: 10 incomplete (Cycle 7, 5 cycles stale — recommend park).
- T5_slack_bot: 10 incomplete (Cycle 7, 5 cycles stale — recommend park).
- **T1_docker_sandbox: 10 incomplete (Cycle 12 v2 hardening), 12 done (Wave 3 v1 COMPLETE).** v1 shipped this cycle; v2 block just queued.
- **T2_forgedata: 8 incomplete, 1 done (Wave 3, FIRST-CYCLE PICKUP — gate cleared by T1-WAVE3 DONE).**

**Tasks added this cycle: 10** (T1_docker_sandbox Cycle 12 v2 hardening block — the only file that fell below 3-task threshold this cycle). **UNBLOCKED notes added: 3** (T2_forgedata initial, T1_docker_sandbox initial, T1_docker_sandbox v2 hardening). **UNBLOCKED notes bumped: 0** (per Cycle 11 contract).

### Terminal Status (Cycle 12 pickup)
- T1_backend: **12 cycles stale — HUMAN-RESCUE PENDING.** Note not bumped per Cycle 11 contract.
- T1_new: Cycle 5 queued, no pickup (8 cycles stale).
- T2_agents: 12 cycles stale.
- T2_new: Cycle 5 queued, no pickup (8 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (9 cycles stale).
- T3_new: Cycle 4 queued, no pickup (9 cycles stale).
- T4_admin: 12 cycles stale.
- T4_new: Cycle 5 queued, no pickup (8 cycles stale).
- T5_deploy: **12 cycles stale; .env.example 5 cycles overdue — HUMAN-RESCUE PENDING.** Note not bumped per Cycle 11 contract.
- T6_testing: Cycle 2 queued with UNBLOCKED note (12 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, **5 cycles stale — RECOMMEND PARK AS V4 ROADMAP.**
- **T1_docker_sandbox: SHIPPED v1 IN-CYCLE.** First cycle tracked; v1 12/12 done in this same coordinator pass (highest-velocity terminal in the project). Cycle 12 v2 hardening block just queued — watch sandbox_builds migration as the next-cycle starter.
- **T2_forgedata: ACTIVE.** Gate cleared mid-cycle; 1/9 done with `pip install simple-salesforce` next in pick order. First-edit watch: api/connectors/salesforce.py.

### UNBLOCKED Actions This Cycle
- tasks/T2_forgedata.md: NEW Cycle 12 UNBLOCKED note explaining the (now-cleared) T1-WAVE3 DONE gate, suggested 7-step pick order, no-creds contract reminder, .env.example collision warning with T5_deploy's still-pending append.
- tasks/T1_docker_sandbox.md (start of cycle): NEW Cycle 12 UNBLOCKED note with 10-step pick order for the remaining v1 tasks. Terminal then immediately followed the order, shipping all 10 in this same pass.
- tasks/T1_docker_sandbox.md (end of cycle): NEW Cycle 12 v2 hardening block — 10 SPEC-grounded tasks (sandbox_builds migration, hash-based cache-skip, image GC, prewarm beat, per-tool resource override, MCP env injection, build-history admin endpoint, pytest coverage) with inlined UNBLOCKED note and pick order.

### Critical Path for Cycle 13
1. **T2_forgedata completion (8 tasks remaining)** — highest-leverage active track. Salesforce connector → blueprint → ForgeAPI append → seed app. SPEC line 1497-1504 alignment. Watch api/connectors/salesforce.py + api/forgedata.py for first edits.
2. **T1_docker_sandbox v2 hardening starter** — sandbox_builds migration is the unblock for build-history writes. Then hash-based cache-skip removes spurious rebuilds when /api/admin/tools/<id>/update-html lands on identical HTML (closes a real perf footgun).
3. **T1 migration 002 (12 CYCLES STALE)** — STILL human-operator pickup. SQL inlined in T1_backend Cycle 11 note.
4. **.env.example append (5 cycles overdue)** — STILL human-operator pickup. 4 lines inlined in T5_deploy Cycle 11 note. T2_forgedata will append 4 more `SALESFORCE_*` lines when its own work lands; both are bottom-appends so ordering is moot.
5. **`db/migrations/005_skills_source_url.sql` provenance** — 3 cycles unclaimed. **Pre-demo blocker.** Identify owner or revert.
6. **Cycle 7 fresh-track consolidation decision** — recommend explicit "park as v4 roadmap" call.
7. T6 test_trust_calculator (still the simplest zero-dep win in the legacy queue).
8. T4_admin bulk-approve + audit endpoints (zero-dep per Cycle 2 UNBLOCKED note).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).
- **Wave 3 sandbox (NEW THIS CYCLE)**: docker calls inherit DOCKER_HOST from runner script (colima socket at `~/.colima/default/docker.sock`); never hardcode `/var/run/docker.sock`. Resource limits per container default to 256m memory / 0.5 vCPU; per-tool override (Cycle 12 v2 task) is hard-capped at 1024m / 2.0 vCPU server-side. Hibernate idle after 10 min via Celery beat (5-min sweep). Pre-warm (image_tag IS NOT NULL AND run_count > 10). Tier 1 (HTML in DB) and Tier 2 (containerized) coexist via tools.container_mode flag — Tier 1 path must remain unmodified. MCP connector secrets injected via `-e` flags at docker run, NEVER logged.
- **Wave 3 forgedata (NEW THIS CYCLE)**: missing Salesforce creds return `{configured: false}` shape — NEVER raise exceptions. Downstream agents (red_team, qa_tester) branch on this signal.

### Action Items for Next Cycle (Cycle 13)
- **Watch T2_forgedata for first-edits in api/connectors/salesforce.py** — that's the contract-defining file (is_configured() short-circuit shape).
- **Watch T1_docker_sandbox v2 for sandbox_builds migration first-edit** — unblocks the rest of the hardening block.
- **If T1_docker_sandbox falls below 3 incomplete again** (unlikely in Cycle 13 given v2 block is 10 tasks deep), add a Wave 3 v3 block focused on multi-tenant isolation (separate Docker networks per tool) and security (gVisor or kata-containers integration if SPEC ever pushes that direction).
- Check whether human operator has actioned migration 002 + .env.example append (both Cycle 11 HUMAN-RESCUE notes still authoritative). If still pending in Cycle 13, organizational escalation may be the only remaining lever.
- Resolve `005_skills_source_url.sql` provenance — if no owner identified, revert this migration before demo.
- Surface Cycle 7 fresh-track cluster to human reviewer with **explicit park-as-v4-roadmap recommendation**.
- Continue zero-bump policy on legacy stuck terminals — bumping fatigued notes adds noise, not signal. Reserve coordinator attention for active tracks (T2_forgedata is now top of stack).

---

### Prior Cycle Archive (Cycle 11)
Last check: 2026-04-16 (Cycle 11)

### Cycle 11 Highlights
- **All 15 task files still at exactly 10 incomplete tasks each.** No file fell below the 3-task threshold → **zero new tasks added this cycle**. Queue health unchanged since Cycle 8.
- **T1_backend migration 002 is now 11 CYCLES STALE.** Cycle 10's "any-reviewer authorization" expired with no pickup. UNBLOCKED note escalated to **CYCLE 11 HUMAN-RESCUE REQUIRED** — per the contract set in Cycle 9/10, this is the cycle where a human operator picks up the SQL directly. Full copy-paste-ready SQL block inlined in the task file. Still blocking 4 downstream terminals (T2_agents progress_pct/tokens/stage_failed, T4_admin self-healer tool_versions.status, T3_frontend Cycle 4 progress bar, T6_testing test_rate_limit + test_versions_api).
- **.env.example 4-line append is now 4 CYCLES OVERDUE** (C8, C9, C10, C11). Escalated to **CYCLE 11 HUMAN-RESCUE REQUIRED** for the same reason as T1 — Cycle 10's any-reviewer authorization did not resolve it. Exact lines to paste inlined in T5_deploy Cycle 11 note. ~30-second edit closes T5_slack_bot line-33 SKIPPED note.
- **Cycle 7 fresh app-platform tracks now 4 CYCLES STALE** (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot) — past the "3-cycle consolidation threshold" set in Cycle 8. **Recommendation for human reviewer: reassign or park as v4 roadmap.** 50 queued tasks across 5 tracks with zero first-edits across 4 cycles is strong signal those assignees are unavailable.
- **`db/migrations/005_skills_source_url.sql` provenance still unverified** — appeared unexpectedly in Cycle 10, no task-file owner, no terminal claims it. Still on the floor. Recommend flagging to human reviewer before demo to rule out merge-conflict artifact.
- **UNBLOCKED notes bumped this cycle: 2** (T1_backend Cycle 10 → Cycle 11 HUMAN-RESCUE; T5_deploy Cycle 10 → Cycle 11 HUMAN-RESCUE). No other notes refreshed — existing guidance in the 13 remaining files is still accurate; re-writing would add noise, not signal.

### Task Queue Health (post-triage, Cycle 11)
All 15 files at 10 incomplete. No triage changes needed:
- T1_backend: 10 incomplete (Cycle 2, **11 CYCLES STALE — HUMAN-RESCUE REQUIRED**).
- T1_new: 10 incomplete (Cycle 5, 7 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 11 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 7 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 8 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 8 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 11 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 7 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 11 cycles stale; **.env.example append 4 CYCLES OVERDUE — HUMAN-RESCUE REQUIRED**).
- T6_testing: 10 incomplete (Cycle 2, 11 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **4 cycles stale — past consolidation threshold**).
- T2_app_frontend: 10 incomplete (Cycle 7, 4 cycles stale — past consolidation threshold).
- T3_forge_cli: 10 incomplete (Cycle 7, 4 cycles stale — past consolidation threshold).
- T4_github_app: 10 incomplete (Cycle 7, 4 cycles stale — past consolidation threshold).
- T5_slack_bot: 10 incomplete (Cycle 7, 4 cycles stale — past consolidation threshold).

**Tasks added this cycle: 0.** **UNBLOCKED / ESCALATION notes bumped: 2** (T1_backend, T5_deploy).

### Terminal Status (Cycle 11 pickup)
- T1_backend: **11 cycles stale — HUMAN-RESCUE REQUIRED.** Agent terminals considered unavailable; copy-paste SQL is ready in task file.
- T1_new: Cycle 5 queued, no pickup (7 cycles stale).
- T2_agents: 11 cycles stale.
- T2_new: Cycle 5 queued, no pickup (7 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (8 cycles stale).
- T3_new: Cycle 4 queued, no pickup (8 cycles stale).
- T4_admin: 11 cycles stale.
- T4_new: Cycle 5 queued, no pickup (7 cycles stale).
- T5_deploy: **11 cycles stale; .env.example 4 cycles overdue — HUMAN-RESCUE REQUIRED.** Exact lines ready in task file.
- T6_testing: Cycle 2 queued with UNBLOCKED note (11 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, **4 cycles stale — past 3-cycle consolidation threshold. Surface to human for reassign-or-park decision.**

### UNBLOCKED Actions This Cycle
- tasks/T1_backend.md: Cycle 10 ESCALATION note replaced with **CYCLE 11 HUMAN-RESCUE REQUIRED**. Full ready-to-paste SQL block inlined in a code fence so the human operator can copy it into `db/migrations/002_phase2_fields.sql` without parsing the note first. Filename-slot note retained (`002_phase2_fields.sql` coexists with T3_NEW's `002_dlp_runs.sql` via alphabetical runner).
- tasks/T5_deploy.md: Cycle 10 UPDATE note replaced with **CYCLE 11 HUMAN-RESCUE REQUIRED**. 4-line append inlined in a code fence with section comments matching existing `.env.example` style. Self-cleanup directive added: "After append, mark task 34 [x] and delete this CYCLE 11 header."

### Critical Path for Cycle 12
1. **T1 migration 002 (11 CYCLES STALE)** — human operator pastes SQL block from T1_backend Cycle 11 note. Unblocks 4 downstream terminals in one ~30-second action.
2. **.env.example append (4 cycles overdue)** — human operator pastes 4 lines from T5_deploy Cycle 11 note. Unblocks every Slack integration test path.
3. **Cycle 7 consolidation decision** — 5 fresh tracks now 4 cycles stale (past 3-cycle threshold). Surface to human reviewer with explicit reassign-or-park ask. If parked, update each task file's header to mark the Cycle 7 block as "v4 roadmap — not actively tracked."
4. **Verify `db/migrations/005_skills_source_url.sql` provenance** — 2 cycles on the floor with no owner. If unclaimed in Cycle 12, either document an owner or revert pre-demo.
5. T1_app_platform Cycle 7 migration 006_app_runs.sql — still the highest-leverage single starter for the fresh-track cluster, assuming it's not parked.
6. T6 test_trust_calculator (pure function, simplest zero-dep win).
7. T4_admin bulk-approve + audit endpoints (both zero-dep per Cycle 2 UNBLOCKED note).
8. T2_agents retry_with_backoff (pure wrapper, zero-dep).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).

### Action Items for Next Cycle (Cycle 12)
- **Human-operator pickup confirmed mandatory** for migration 002 and .env.example append. Both have copy-paste-ready content in their task files; both have been parked past the out-of-band escalation threshold. Do not bump a third time — if still pending in Cycle 12, the blocker is organizational, not coordinator-addressable.
- **Consolidation call**: surface the 5 Cycle 7 fresh tracks to human reviewer with a concrete "reassign to X terminal or park as v4" question. Four cycles without a first-edit = assignees unavailable.
- Resolve `005_skills_source_url.sql` provenance before demo.
- Watch for any first edits across the 15 tracked files — any pickup at all would be meaningful signal after this many cycles of silence.
- Cross-cycle flag: if T1_app_platform ships migration 006 + /apps/<id>/runs endpoint, immediately tap T2_app_frontend Apps tab and T3_forge_cli `forge logs` to consume it.

---

### Prior Cycle Archive (Cycle 10)
Last check: 2026-04-16 (Cycle 10)

### Cycle 10 Highlights
- **All 15 task files remain at exactly 10 incomplete tasks each.** No file fell below the 3-task threshold → **zero new tasks added this cycle**. Queue health unchanged from Cycle 9.
- **T1_backend migration 002 is now 10 CYCLES STALE — terminal formally considered ABANDONED.** Cycle 10 escalation note replaced Cycle 9 note; full column-list SQL inlined in the task so any reviewer can write it in under 2 minutes. Note the filename-slot collision: T3_NEW shipped `002_dlp_runs.sql` in Cycle 4, so the T1 migration must retain filename `002_phase2_fields.sql` (both will apply alphabetically via `scripts/run_migrations.py`).
- **Cycle 7 fresh app-platform tracks now 3 CYCLES STALE** (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot). This hits the "consider consolidating scope" threshold set in Cycle 8. Recommendation: escalate to human in Cycle 11 or park these as v4 roadmap — they've absorbed 50 queued tasks without a single first-edit.
- **.env.example still missing 4 Slack/Flask entries** — 3 cycles overdue (C8/C9/C10). T5_deploy Cycle 10 UPDATE note now explicitly authorizes any reviewer to perform the ~30-second append.
- **Unexpected activity flagged:** `db/migrations/005_skills_source_url.sql` (5-line ALTER on `skills.source_url`) appeared at 00:35 UTC. This migration is **not listed in any task file's scope** — no terminal owns it, no UNBLOCKED note mentions it. Source unclear; may be manual user work or an untracked track. Not a blocker but worth verifying its provenance before demo.
- **UNBLOCKED notes bumped this cycle: 2** (T1_backend Cycle 9 → Cycle 10 escalation with full SQL inline; T5_deploy Cycle 8 → Cycle 10 update consolidating 3 cycles of the same directive).

### Task Queue Health (post-triage, Cycle 10)
All 15 files at 10 incomplete. No triage changes needed:
- T1_backend: 10 incomplete (Cycle 2, **10 CYCLES STALE — ABANDONED; RESCUE AUTHORIZED**).
- T1_new: 10 incomplete (Cycle 5, 6 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 10 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 6 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 7 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 7 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 10 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 6 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 10 cycles stale; .env.example append 3 cycles overdue).
- T6_testing: 10 incomplete (Cycle 2, 10 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, **3 cycles stale — consolidation threshold reached**).
- T2_app_frontend: 10 incomplete (Cycle 7, 3 cycles stale — consolidation threshold).
- T3_forge_cli: 10 incomplete (Cycle 7, 3 cycles stale — consolidation threshold).
- T4_github_app: 10 incomplete (Cycle 7, 3 cycles stale — consolidation threshold).
- T5_slack_bot: 10 incomplete (Cycle 7, 3 cycles stale — consolidation threshold).

**Tasks added this cycle: 0.** **UNBLOCKED / ESCALATION notes bumped: 2** (T1_backend, T5_deploy).

### Terminal Status (Cycle 10 pickup)
- T1_backend: 10 cycles stale. **RESCUE AUTHORIZED — any reviewer may write migration 002.**
- T1_new: Cycle 5 queued, no pickup (6 cycles stale).
- T2_agents: 10 cycles stale.
- T2_new: Cycle 5 queued, no pickup (6 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (7 cycles stale).
- T3_new: Cycle 4 queued, no pickup (7 cycles stale).
- T4_admin: 10 cycles stale.
- T4_new: Cycle 5 queued, no pickup (6 cycles stale).
- T5_deploy: 10 cycles stale; .env.example append 3 cycles overdue. **Any-reviewer append authorized.**
- T6_testing: Cycle 2 queued with UNBLOCKED note (10 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, 3 cycles stale. Consolidation decision point — surface to human in Cycle 11.

### UNBLOCKED Actions This Cycle
- tasks/T1_backend.md: Cycle 9 ESCALATION note replaced with CYCLE 10 ESCALATION. Full column-list SQL inlined so any reviewer can drop it in without reading the task bullets. Filename-collision advisory added (retain `002_phase2_fields.sql` despite T3_NEW's `002_dlp_runs.sql` — alphabetical migration runner handles both).
- tasks/T5_deploy.md: Cycle 8 UPDATE note replaced with CYCLE 10 UPDATE — consolidates 3 cycles of the same directive into one note, authorizes any-reviewer append of the 4 missing lines.

### Critical Path for Cycle 11
1. **T1 migration 002 (10 CYCLES STALE — ABANDONED)** — human operator or any reviewer writes this migration directly. Full SQL is inlined in T1_backend.md Cycle 10 note. Unblocks 4 downstream terminals.
2. **.env.example append (3 cycles overdue)** — any reviewer adds the 4 Slack/Flask lines. ~30-second edit.
3. **Cycle 7 consolidation decision** — 5 fresh tracks hit 3-cycle threshold; surface to human for reassign-or-park decision.
4. Verify provenance of `db/migrations/005_skills_source_url.sql` (unexpected arrival this cycle, no task-file owner).
5. T1_app_platform Cycle 7 migration 006_app_runs.sql — still the highest-leverage single starter for the fresh-track cluster.
6. T6 test_trust_calculator (pure function, simplest zero-dep win in the queue).
7. T4_admin bulk-approve + audit endpoints (both zero-dep per Cycle 2 UNBLOCKED note).
8. T2_agents retry_with_backoff (pure wrapper, zero-dep).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).

### Action Items for Next Cycle (Cycle 11)
- **Human-operator escalation**: If T1_backend and T5_deploy remain silent in Cycle 11, write migration 002 and append the .env.example Slack lines directly rather than waiting another cycle — both are blocked by absence, not by design uncertainty.
- **Consolidation decision**: Surface Cycle 7 fresh-track cluster (5 tracks × 10 tasks = 50 queued items) to human reviewer for reassign-or-park call. Three cycles without a single first-edit across any of the 5 tracks is strong signal those assignees are unavailable.
- Verify the `005_skills_source_url.sql` migration isn't a merge-conflict artifact or an out-of-scope addition; identify owner and document in a task file.
- Watch for first edits in Cycle 7 files (api/apps.py, frontend/js/my-tools.js, forge_cli/cli.py, forge_bot/webhook.py, forge_bot/slack_bot.py) to detect pickup.
- Cross-cycle flag: if T1_app_platform ships migration 006 + /apps/<id>/runs endpoint, immediately tap T2_app_frontend Apps tab and T3_forge_cli `forge logs` to consume it.

---

### Prior Cycle Archive (Cycle 9)
Last check: 2026-04-16 (Cycle 9)

### Cycle 9 Highlights
- **Every one of 15 task files sits at exactly 10 incomplete tasks.** No file fell below the 3-task threshold → **zero new tasks added this cycle**. Task queue health unchanged from Cycle 8.
- **T1_backend migration 002 is now 9 CYCLES STALE.** Escalation note bumped from Cycle 8 to Cycle 9 — the SQL file is 5 lines, fully spec'd, zero design work remaining. Recommendation: if T1 terminal owner remains unavailable in Cycle 10, **reassign the migration to any reviewer with schema access**. Blocking: T2_agents (progress_pct/review_tokens_used/stage_failed), T4_admin (tool_versions.status for self-healer), T3_frontend Cycle 4 task 5 (progress_pct bar), T6_testing (test_rate_limit + test_versions_api).
- **All 5 Cycle 7 FRESH app-platform tracks now 2 CYCLES STALE** (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot). No first edits landed on any Cycle 7 task file since the block was queued. Approaching the "3 cycles without pickup → consider consolidating scope" threshold flagged in Cycle 8 action items.
- **.env.example: still missing the 4 Slack/Flask entries** after the Cycle 8 UPDATE note specified a 2-minute append. T5_deploy remains stuck at the same Cycle 2 line 34 task.
- **UNBLOCKED notes added this cycle: 1** (T1_backend Cycle 9 escalation bump). Every other task file retains its prior cycle UNBLOCKED note — all still accurate, duplicating would add no signal.

### Task Queue Health (post-triage, Cycle 9)
All 15 files at 10 incomplete. No triage changes needed:
- T1_backend: 10 incomplete (Cycle 2, **9 CYCLES STALE — ESCALATE / REASSIGN**).
- T1_new: 10 incomplete (Cycle 5, 5 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 9 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 5 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 6 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 6 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 9 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 5 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 9 cycles stale; .env.example 4-entry append still pending).
- T6_testing: 10 incomplete (Cycle 2, 9 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, 2 cycles stale).
- T2_app_frontend: 10 incomplete (Cycle 7, 2 cycles stale).
- T3_forge_cli: 10 incomplete (Cycle 7, 2 cycles stale).
- T4_github_app: 10 incomplete (Cycle 7, 2 cycles stale).
- T5_slack_bot: 10 incomplete (Cycle 7, 2 cycles stale).

**Tasks added this cycle: 0.** **UNBLOCKED / ESCALATION notes added: 1** (T1_backend bumped Cycle 8 → Cycle 9).

### Terminal Status (Cycle 9 pickup)
- T1_backend: 9 cycles stale. **CRITICAL — ESCALATE TO HUMAN REVIEWER / REASSIGN.**
- T1_new: Cycle 5 queued, no pickup (5 cycles stale).
- T2_agents: 9 cycles stale.
- T2_new: Cycle 5 queued, no pickup (5 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (6 cycles stale).
- T3_new: Cycle 4 queued, no pickup (6 cycles stale).
- T4_admin: 9 cycles stale.
- T4_new: Cycle 5 queued, no pickup (5 cycles stale).
- T5_deploy: 9 cycles stale; .env.example 4-entry append (~2 min work) still pending.
- T6_testing: Cycle 2 queued with UNBLOCKED note (9 cycles stale).
- T1_app_platform through T5_slack_bot (5 tracks): Cycle 7 queued, 2 cycles stale — at the edge of "fresh" window.

### UNBLOCKED Actions This Cycle
- tasks/T1_backend.md: Cycle 8 ESCALATION note updated to CYCLE 9 ESCALATION — flags that 9 cycles of no-pickup signals the terminal is abandoned and recommends reassignment in Cycle 10.

### Critical Path for Cycle 10
1. **T1 migration 002 (9 CYCLES STALE)** — ESCALATE + REASSIGN if T1 terminal remains silent. Unblocks 4 downstream terminals. Zero design work remaining.
2. **T5_deploy .env.example append** — 4 missing entries (SLACK_WEBHOOK_URL, FLASK_ENV, SLACK_BOT_TOKEN, SLACK_APP_TOKEN), ~2 minutes of work, unblocks every Slack integration test path. Now 2 cycles overdue on the targeted append.
3. Cycle 7 fresh tracks at the 3-cycle-stale threshold — if no pickup on any of the 5 app-platform Cycle 7 blocks in Cycle 10, consider consolidating scope or parking as v4 roadmap (per Cycle 8 action item).
4. T1_app_platform Cycle 7 migration 006_app_runs.sql — still the highest-leverage single starter for the fresh-track cluster.
5. T6 test_trust_calculator (pure function, simplest zero-dep win in the queue).
6. T4_admin bulk-approve + audit endpoints (both zero-dep per Cycle 2 UNBLOCKED note).
7. T2_agents retry_with_backoff (pure wrapper, zero-dep).
8. T3_frontend Cycle 4 email_draft + table renderers (SPEC 951-952, pure frontend).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).

### Action Items for Next Cycle (Cycle 10)
- REASSIGN db/migrations/002_phase2_fields.sql to a non-T1 reviewer if terminal remains silent — 9 cycles stale breaks the "possibly recoverable" threshold.
- Verify T5 finally appends SLACK_WEBHOOK_URL/FLASK_ENV/SLACK_BOT_TOKEN/SLACK_APP_TOKEN to .env.example and marks task 34 [x].
- **Consolidation decision point**: if Cycle 7 fresh tracks hit 3 cycles without any file edit, flag for human review — either reassign or park as v4 roadmap.
- Watch for first edits in Cycle 7 files (api/apps.py, frontend/js/my-tools.js, forge_cli/cli.py, forge_bot/webhook.py, forge_bot/slack_bot.py) to detect pickup.
- Cross-cycle flag: if T1_app_platform ships migration 006 + /apps/<id>/runs endpoint, immediately tap T2_app_frontend Apps tab and T3_forge_cli `forge logs` to consume it.

---

### Prior Cycle Archive (Cycle 8)
Last check: 2026-04-16 (Cycle 8)

### Cycle 8 Highlights
- **Every one of 15 task files sits at exactly 10 incomplete tasks.** No file fell below the 3-task threshold → **zero new tasks added this cycle**.
- **.env.example PARTIALLY LANDED** this cycle: T4_github_app created it at repo root in Cycle 7 with 12 entries (core API + GitHub App env vars). Still missing original T5_deploy-spec'd entries: `SLACK_WEBHOOK_URL=`, `FLASK_ENV=production`, `SLACK_BOT_TOKEN=`, `SLACK_APP_TOKEN=`. T5 Cycle 2 task note updated to reflect the now-append-only work (~2 min).
- **T1_backend migration 002 is now 8 CYCLES STALE.** ESCALATION note prepended to T1_backend Cycle 2 block: this 5-line SQL file is the single highest-leverage unblock in the project, parking T2/T4/T6/T3_frontend work across 4 terminals. File contents fully specified at line 45 of task file — pure SQL, no design work remaining.
- No fresh pickup on any of the 5 Cycle 7 FRESH app-platform tracks (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot Cycle 7 sections). 1 cycle stale — still recent; watch for first edits next cycle before escalating.
- **UNBLOCKED notes added this cycle: 2** (T1_backend Cycle 2 escalation, T5_deploy Cycle 2 update). All 13 other task files have existing UNBLOCKED notes that remain accurate — duplicating would add no signal.

### Task Queue Health (post-triage, Cycle 8)
All 15 files at 10 incomplete:
- T1_backend: 10 incomplete (Cycle 2, **8 CYCLES STALE — ESCALATE IMMEDIATELY**).
- T1_new: 10 incomplete (Cycle 5, 4 cycles stale).
- T2_agents: 10 incomplete (Cycle 2, 8 cycles stale).
- T2_new: 10 incomplete (Cycle 5, 4 cycles stale).
- T3_frontend: 10 incomplete (Cycle 4, 5 cycles stale).
- T3_new: 10 incomplete (Cycle 4, 5 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 8 cycles stale).
- T4_new: 10 incomplete (Cycle 5, 4 cycles stale).
- T5_deploy: 10 incomplete (Cycle 2, 8 cycles stale; .env.example partial land — task 34 nearly complete, needs Slack-entry append).
- T6_testing: 10 incomplete (Cycle 2, 8 cycles stale).
- T1_app_platform: 10 incomplete (Cycle 7, 1 cycle stale — still fresh).
- T2_app_frontend: 10 incomplete (Cycle 7, 1 cycle stale).
- T3_forge_cli: 10 incomplete (Cycle 7, 1 cycle stale).
- T4_github_app: 10 incomplete (Cycle 7, 1 cycle stale).
- T5_slack_bot: 10 incomplete (Cycle 7, 1 cycle stale).

**Tasks added this cycle: 0.** **UNBLOCKED / ESCALATION notes added: 2** (T1_backend, T5_deploy).

### Terminal Status (Cycle 8 pickup)
- T1_backend: STILL STUCK, 8 cycles stale. Migration 002 still absent. **CRITICAL — ESCALATE TO HUMAN REVIEWER.**
- T1_new: Cycle 5 queued, no pickup (4 cycles stale).
- T2_agents: STILL STUCK, 8 cycles stale.
- T2_new: Cycle 5 queued, no pickup (4 cycles stale).
- T3_frontend: Cycle 4 queued, no pickup (5 cycles stale).
- T3_new: Cycle 4 queued, no pickup (5 cycles stale).
- T4_admin: STILL STUCK, 8 cycles stale.
- T4_new: Cycle 5 queued, no pickup (4 cycles stale).
- T5_deploy: STILL STUCK, 8 cycles stale; .env.example base file landed via T4_github_app but 4 entries still missing.
- T6_testing: Cycle 2 queued with UNBLOCKED note (8 cycles stale).
- T1_app_platform: Cycle 7 queued, no pickup (1 cycle stale — still fresh).
- T2_app_frontend: Cycle 7 queued, no pickup.
- T3_forge_cli: Cycle 7 queued, no pickup.
- T4_github_app: Cycle 7 queued, no pickup beyond .env.example drop.
- T5_slack_bot: Cycle 7 queued, no pickup.

### UNBLOCKED Actions This Cycle
- tasks/T1_backend.md: CYCLE 8 ESCALATION note prepended to Cycle 2 block flagging migration 002 as 8-cycles-stale and the #1 project blocker.
- tasks/T5_deploy.md: CYCLE 8 UPDATE note replacing the ambiguous Cycle 2 UNBLOCKED for task 34 — confirms .env.example now exists, lists the 4 missing entries (`SLACK_WEBHOOK_URL`, `FLASK_ENV`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`), and reclassifies the work as a 2-minute append.

### Critical Path for Cycle 9
1. **T1 migration 002 (8 CYCLES STALE)** — ESCALATE. Unblocks 4 downstream terminals. Zero design work remaining.
2. **T5_deploy .env.example append** — 4 missing entries, ~2 minutes of work, unblocks every Slack integration test path.
3. T1_app_platform Cycle 7 migration 006 — highest-leverage CYCLE 7 starter if any fresh-track terminal wakes up.
4. T6 test_trust_calculator (pure function, simplest zero-dep win in the queue).
5. T4_admin bulk-approve + audit endpoints (both zero-dep per Cycle 2 UNBLOCKED note).
6. T2_agents retry_with_backoff (pure wrapper, zero-dep).
7. T3_frontend Cycle 4 email_draft + table renderers (SPEC 951-952, pure frontend).
8. T3_forge_cli `forge init` (pure stdlib, fastest visible-to-user win in Cycle 7 block).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).

### Action Items for Next Cycle
- ESCALATE db/migrations/002_phase2_fields.sql to human reviewer — 8 cycles stale is critical.
- Verify T5 appends SLACK_WEBHOOK_URL/FLASK_ENV/SLACK_BOT_TOKEN/SLACK_APP_TOKEN to .env.example and marks task 34 [x].
- Watch for first edits in any Cycle 7 fresh-track file (api/apps.py, frontend/js/my-tools.js, forge_cli/cli.py, forge_bot/webhook.py, forge_bot/slack_bot.py Cycle 7 items) — 1 cycle idle is not yet stuck but worth monitoring.
- Cross-cycle flag: if T1_app_platform ships migration 006 + /apps/<id>/runs endpoint, immediately tap T2_app_frontend Apps tab and T3_forge_cli `forge logs` to consume it.
- If Cycle 7 fresh tracks remain at 0 pickup for 3+ cycles, consider consolidating scope (some may be parked as v4 roadmap).

---

### Prior Cycle Archive (Cycle 7)
Last check: 2026-04-16 (Cycle 7)

### Cycle 7 Highlights
- All FIVE app-platform tracks shipped DONE between Cycle 6 and Cycle 7: T1-APP, T2-APP, T3-APP, T4-APP, T5-APP. Each closed at 100% on its Cycle 1 checklist, so all five files dropped below the 3-incomplete threshold simultaneously.
- Cycle 7 triage: **50 new SPEC-driven tasks added across the 5 DONE app tracks** (10 each). Each new block leads with an UNBLOCKED note + suggested pick order keyed to SPEC line numbers (schedule_cron/schedule_channel at line 83, MCP Integration Layer 1497-1504, Beat pattern 603-610, output formats 951-952, DLP regex reuse at api/dlp.py).
- Cross-track coupling (Cycle 7): T1_app_platform Cycle 7 /apps/<id>/runs and /rollback endpoints unlock T2_app_frontend (my-tools Apps tab run view) + T3_forge_cli (`forge logs`, `forge rollback`, `forge tail`) simultaneously. Ship those T1 endpoints first to maximize downstream velocity.
- Stale blockers unchanged since Cycle 6: T1_backend migration 002 now **7 CYCLES STALE** — continue to escalate. No new UNBLOCKED notes added to the six stuck legacy tracks because existing notes remain current and accurate; the bottleneck is human pickup, not guidance.

### Task Queue Health (post-triage, Cycle 7)
- T1_backend: 10 incomplete (Cycle 2, now 7 CYCLES STALE — ESCALATE).
- T1_new (Celery hardening v2): 10 incomplete (Cycle 5 block).
- T2_agents: 10 incomplete (Cycle 2, 7 cycles stale).
- T2_new (Creator v2): 10 incomplete (Cycle 5 block).
- T3_frontend: 10 incomplete (Cycle 4 block, 3 cycles stale).
- T3_new (DLP v2): 10 incomplete (Cycle 4 block, 3 cycles stale).
- T4_admin: 10 incomplete (Cycle 2, 7 cycles stale).
- T4_new (Workflow v2): 10 incomplete (Cycle 5 block).
- T5_deploy: 10 incomplete (Cycle 2, 7 cycles stale).
- T6_testing: 10 incomplete (Cycle 2 block, 7 cycles stale).
- **T1_app_platform: WAS 0 → 10 new Cycle 7 tasks (scheduler + MCP + app runs + export/import). UNBLOCKED note included.**
- **T2_app_frontend: WAS 0 → 10 new Cycle 7 tasks (UX polish + templates + full-screen + version panel). UNBLOCKED note included.**
- **T3_forge_cli: WAS 0 → 10 new Cycle 7 tasks (init/dev/diff/test/rollback + CLI tests). UNBLOCKED note included.**
- **T4_github_app: WAS 0 → 10 new Cycle 7 tasks (PR previews + schema validator + secrets scan + installations). UNBLOCKED note included.**
- **T5_slack_bot: WAS 0 → 10 new Cycle 7 tasks (OAuth + reactji approvals + Home tab + autocomplete). UNBLOCKED note included.**

**Tasks added this cycle: 50** (10 each to the five DONE app tracks). **UNBLOCKED notes added: 5** (one per new Cycle 7 block).

### Terminal Status (Cycle 7 pickup)
- T1_backend: STILL STUCK, 7 cycles stale. Migration 002 still absent. ESCALATION RECOMMENDED — every cycle increases T2/T4/T6 downstream debt.
- T1_new: Cycle 5 queued, no pickup (3 cycles stale).
- T2_agents: STILL STUCK, 7 cycles stale.
- T2_new: Cycle 5 queued, no pickup.
- T3_frontend: Cycle 4 queued, no pickup (3 cycles stale).
- T3_new: Cycle 4 queued, no pickup.
- T4_admin: STILL STUCK, 7 cycles stale.
- T4_new: Cycle 5 queued, no pickup.
- T5_deploy: STILL STUCK, 7 cycles stale.
- T6_testing: Cycle 2 queued with UNBLOCKED, no pickup (7 cycles stale).
- T1_app_platform: FRESH Cycle 7 queued — suggested first pickup migration 006_app_runs.sql (unblocks run-log writes).
- T2_app_frontend: FRESH Cycle 7 queued — suggested first pickup Apps tab in my-tools (zero-dep, high user value).
- T3_forge_cli: FRESH Cycle 7 queued — suggested first pickup `forge init` (pure stdlib scaffolding).
- T4_github_app: FRESH Cycle 7 queued — suggested first pickup forge.yaml schema validator (biggest error-message win).
- T5_slack_bot: FRESH Cycle 7 queued — suggested first pickup rate-limit guard (protects all other deploy paths).

### UNBLOCKED Actions This Cycle
- tasks/T1_app_platform.md: new Cycle 7 UNBLOCKED note — 10 scheduler/MCP/app-runs tasks, zero cross-terminal dependency, pick order starts at migration 006.
- tasks/T2_app_frontend.md: new Cycle 7 UNBLOCKED note — 10 UX/templates/version tasks, iframe sandbox reminder restated, pick order starts at Apps tab in my-tools.
- tasks/T3_forge_cli.md: new Cycle 7 UNBLOCKED note — 10 CLI/dev-UX/test tasks, graceful fallback patterns for T1 Cycle 7 endpoints, pick order starts at `forge init`.
- tasks/T4_github_app.md: new Cycle 7 UNBLOCKED note — 10 PR-preview/safety/installations tasks, imports api.dlp for secrets scan, pick order starts at schema validator.
- tasks/T5_slack_bot.md: new Cycle 7 UNBLOCKED note — 10 OAuth/approvals/Home-tab tasks, all endpoints already live, pick order starts at rate-limit guard.

### Critical Path for Cycle 8
1. **T1 migration 002 (7 CYCLES STALE)** — ESCALATE to human reviewer immediately. Blocks T2_agents progress_pct/token accounting, T4_admin self-healer UI, T6_testing test_rate_limit + test_versions_api.
2. **T1_app_platform Cycle 7 migration 006 + /runs endpoint** — highest-leverage single task this cycle. Unblocks T2_app_frontend Apps tab + T3_forge_cli `forge logs`/`forge tail`.
3. T5_deploy .env.example (still missing after 7 cycles — blocks every setup doc; now also needs GITHUB_TOKEN, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, GITHUB_WEBHOOK_SECRET, FORGE_API_KEY entries beyond the original set).
4. T6 zero-dep starters (test_trust_calculator first — pure function).
5. T4_admin zero-dep starters (audit, bulk-approve, keyboard shortcuts, CSV export).
6. T2 zero-dep starters (retry_with_backoff + JSON repair + red_team structuring).
7. T3_frontend Cycle 4 starters (email_draft/table renderers + shareable link + instructions modal).
8. T3_forge_cli Cycle 7 `forge init` (pure stdlib, fastest visible-to-user win).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **App platform (enforced)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (never raw threads) for /api/submit/app.
- **GitHub App (new, Cycle 7)**: forge_bot/webhook.py binds to port 8093 (NOT 8091 — reserved for test dashboard).

### Action Items for Next Cycle
- ESCALATE db/migrations/002_phase2_fields.sql to human reviewer (7 cycles stale is critical).
- Verify any of the 5 FRESH Cycle 7 blocks receive pickup — look for first edits in api/apps.py, frontend/js/my-tools.js, forge_cli/cli.py, forge_bot/webhook.py, forge_bot/slack_bot.py.
- Watch for db/migrations/006_app_runs.sql appearance as Cycle 7's biggest-unblock starter.
- Verify .env.example finally lands with full post-v3 env var set (still missing every cycle).
- Check whether T6 has picked up test_trust_calculator or test_deploy.
- Cross-cycle flag: if T1_app_platform ships /apps/<id>/runs, immediately tap T2_app_frontend and T3_forge_cli to consume it.

---

### Prior Cycle Archive (Cycle 6)
Last check: 2026-04-16 (Cycle 6)

### Cycle 6 Highlights
- Five NEW parallel "app platform" tracks discovered (T1_app_platform, T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot) — these are v3 app-type tools (full HTML apps, not just prompts). T1_app_platform has shipped 3 of 7 tasks (migration 004_apps.sql applied, api/apps.py blueprint with window.FORGE_APP + window.ForgeAPI injection, blueprint registered in server.py). The other FOUR tracks have **0 [x] progress** with no prior UNBLOCKED guidance.
- Cycle 6 triage: NO task file falls below the 3-incomplete threshold, so no new 10-task blocks added. Instead: **4 UNBLOCKED notes written** to the stuck-at-zero app tracks (T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot), each identifying zero-dep starter tasks + dependencies on sibling app tracks + suggested pick order.
- Cross-track coupling flagged: T3_forge_cli's POST /api/submit/app endpoint is the unblock for BOTH T4_github_app (webhook deployer) and T5_slack_bot (code-block deploy + slash command). Ship T3's endpoint first to unblock two downstream tracks simultaneously.

### Task Queue Health (post-triage, Cycle 6)
- T1_backend: 10 incomplete (UNBLOCKED from Cycle 2 still current, now 6 CYCLES STALE — escalate).
- T1_new (Celery): 10 incomplete (Cycle 5 block, unchanged — no pickup yet).
- T2_agents: 10 incomplete (unchanged, 6 cycles stale).
- T2_new (Creator): 10 incomplete (Cycle 5 block, unchanged).
- T3_frontend: 10 incomplete (Cycle 4 block, unchanged).
- T3_new (DLP v2): 10 incomplete (Cycle 4 block, unchanged).
- T4_admin: 10 incomplete (Cycle 2 block, unchanged).
- T4_new (Workflow): 10 incomplete (Cycle 5 block, unchanged).
- T5_deploy: 10 incomplete (Cycle 2 block, unchanged).
- T6_testing: 10 incomplete (Cycle 2 block, unchanged).
- **NEW T1_app_platform: 4 incomplete (3 [x] landed — migration + apps_bp + registration done; seed data + verify + marker remain). No UNBLOCKED note needed — path is clear.**
- **NEW T2_app_frontend: 9 incomplete, 0 [x]. UNBLOCKED note added this cycle (5-step pick order starting at styles.css).**
- **NEW T3_forge_cli: 8 incomplete, 0 [x]. UNBLOCKED note added this cycle (stdlib-only CLI skeleton + POST /api/submit/app endpoint).**
- **NEW T4_github_app: 9 incomplete, 0 [x]. UNBLOCKED note added this cycle (3 zero-dep starters identified, deployer partially blocked on T3).**
- **NEW T5_slack_bot: 7 incomplete, 0 [x]. UNBLOCKED note added this cycle (4 zero-dep starters identified, deploy handler ready to ship against T3's endpoint).**

**Tasks added this cycle: 0** (no file fell below threshold). **UNBLOCKED notes added: 4** (T2_app_frontend, T3_forge_cli, T4_github_app, T5_slack_bot).

### Terminal Status (Cycle 6 pickup)
- T1_backend: STILL STUCK on Cycle 2, now 6 cycles elapsed. Migration 002 still missing. ESCALATION RECOMMENDED.
- T1_new: Cycle 5 queued from prior cycle, no pickup yet — watch celery_app.py for result_backend addition.
- T2_agents: Still STUCK on Cycle 2 (6 cycles).
- T2_new: Cycle 5 queued, no pickup.
- T3_frontend: Cycle 4 queued, no pickup (2 cycles stale).
- T3_new: Cycle 4 queued, no pickup.
- T4_admin: Still STUCK on Cycle 2 (6 cycles).
- T4_new: Cycle 5 queued, no pickup.
- T5_deploy: Still STUCK on Cycle 2 (6 cycles).
- T6_testing: Cycle 2 queued with UNBLOCKED note, no pickup yet.
- T1_app_platform: ACTIVE this cycle (3 of 7 done). Remaining: 3 app seeds in db/seed.py + verification curls + DONE marker.
- T2_app_frontend: FRESH at 0%. UNBLOCKED note identifies styles.css as 5-min starter.
- T3_forge_cli: FRESH at 0%. UNBLOCKED note identifies stdlib-only CLI + endpoint addition as ~90min total.
- T4_github_app: FRESH at 0%. UNBLOCKED note identifies 3 zero-dep starters.
- T5_slack_bot: FRESH at 0%. UNBLOCKED note identifies slack_bolt skeleton as main lift.

### UNBLOCKED Actions This Cycle
- tasks/T2_app_frontend.md: new UNBLOCKED note — confirms T1_app_platform backend live, orders 5 pick steps starting at CSS, flags sandbox security constraint as non-negotiable.
- tasks/T3_forge_cli.md: new UNBLOCKED note — stdlib-only path, flags that shipping /api/submit/app unblocks T4 and T5 simultaneously.
- tasks/T4_github_app.md: new UNBLOCKED note — 3 zero-dep starters (webhook signature, forge.yaml example, update-html endpoint), conditional import pattern for deployer POST.
- tasks/T5_slack_bot.md: new UNBLOCKED note — 4 zero-dep starters (slack_bolt skeleton, start script, README, .env append), conditional import pattern for GitHub deploy path, #forge-releases outbound-only reminder.

### Critical Path for Cycle 7
1. **T1 migration 002 (NOW 6 CYCLES STALE)** — escalate to human reviewer. Blocks T2/T4/T6 downstream.
2. **T3_forge_cli POST /api/submit/app** — highest leverage single task this cycle. Unblocks T4_github_app AND T5_slack_bot deployer paths.
3. T1_app_platform db/seed.py — 3 professional dark-themed apps (Job Search Pipeline, Meeting Prep Generator, Pipeline Velocity Dashboard). Required for demo.
4. T2_app_frontend styles.css + index.html nav — fastest visual wins for app-type surface.
5. T5 .env.example (still missing — blocks all setup docs; now also needs GITHUB_TOKEN, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, FORGE_API_URL, FORGE_API_KEY, GITHUB_WEBHOOK_SECRET entries).
6. T6 zero-dep starters (test_trust_calculator FIRST — pure function, lowest friction).
7. T4_admin zero-dep starters (audit, bulk-approve, keyboard shortcuts, CSV export).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.
- **NEW (app platform tracks)**: iframe sandbox MUST be "allow-scripts allow-forms allow-modals" — NEVER include allow-same-origin. Pipeline dispatch MUST use celery_app.send_task (not raw background threads) for /api/submit/app.

### Action Items for Next Cycle
- ESCALATE missing db/migrations/002_phase2_fields.sql (6 cycles stale).
- Verify T1_app_platform db/seed.py gets its 3 app seeds (job-search-pipeline, meeting-prep, pipeline-velocity).
- Check whether T3_forge_cli picks up POST /api/submit/app (watch api/server.py for endpoint addition + forge_cli/ directory appearance).
- Verify .env.example finally lands with the full post-v3 env var set.
- Check whether any of T2_app_frontend/T4_github_app/T5_slack_bot move off 0%.
- Watch for cross-cycle sync: if T3 ships /api/submit/app, flag T4 and T5 to pick up their deployer POSTs immediately.

### Prior Cycle Archive (Cycle 5)
Last check: 2026-04-16 (Cycle 5)

### Cycle 5 Highlights
- Three parallel tracks (T1_NEW, T2_NEW, T4_NEW) were at 0 incomplete tasks. Each received a Cycle 5 block of 10 SPEC-driven expansion tasks:
  - **T1_NEW Cycle 5**: Celery hardening v2 — result backend, retry policy with backoff, priority queues, soft/hard timeouts, DLQ, idempotency cache, Flower dashboard, autoscale, healthcheck task.
  - **T2_NEW Cycle 5**: Creator v2 — meta-agent pipeline per SPEC 1506-1516 — governance auto-estimator, test-case generator, variant batch, refinement loop, history, inline editor, best-practices layer, 12 presets, category-confidence gating, test suite.
  - **T4_NEW Cycle 5**: Workflow v2 — persisted workflows table (migration 005), 3+ step chains, shared context JSON access, typed-edge validation, conditional branching, workflow-as-tool publish, SVG visual builder, tests.
- T6_testing received a missing UNBLOCKED note at the top of Cycle 2 section: identifies 6 of 10 tests as zero-dep starters + the stub-skeleton pattern for the T1-blocked tests.

### Task Queue Health (post-triage, Cycle 5)
- T1_backend: 10 incomplete (unchanged). UNBLOCKED note from Cycle 2 still current.
- T1_new (Celery): WAS 0 incomplete → **10 new Cycle 5 tasks added** (Celery hardening v2). UNBLOCKED note included.
- T2_agents: 10 incomplete (unchanged). Cycle 2 UNBLOCKED note still current.
- T2_new (Creator): WAS 0 incomplete → **10 new Cycle 5 tasks added** (meta-agent pipeline per SPEC 1506-1516). UNBLOCKED note included.
- T3_frontend: 10 incomplete (Cycle 4 block, unchanged).
- T3_new (DLP v2): 10 incomplete (Cycle 4 block, unchanged).
- T4_admin: 10 incomplete (Cycle 2 block, unchanged).
- T4_new (Workflow): WAS 0 incomplete → **10 new Cycle 5 tasks added** (visual builder + branching per SPEC 1489-1496). UNBLOCKED note included.
- T5_deploy: 10 incomplete (Cycle 2 block, unchanged).
- T6_testing: 10 incomplete (Cycle 2 block). **NEW** UNBLOCKED note added this cycle listing 6 zero-dep starters + stub-skeleton pattern for T1-blocked tests. test_dlp line 24 can be marked [x] now — T3_NEW already shipped 21 passing tests.

**Tasks added this cycle: 30** (10 to T1_new, 10 to T2_new, 10 to T4_new). Plus 1 UNBLOCKED note added to T6_testing.

### Terminal Status (Cycle 5 pickup)
- T1_backend: Still STUCK on Cycle 2. Four cycles elapsed without migration 002 landing. Still blocking T2/T4/T6 downstream.
- T1_new: Cycle 1 COMPLETE. Cycle 5 tasks now queued — watch celery_app.py/agents/tasks.py for first edits.
- T2_agents: Still STUCK on Cycle 2.
- T2_new: Cycle 1 COMPLETE. Cycle 5 tasks now queued — watch api/creator.py for first edits (governance auto-estimator or test-case generator).
- T3_frontend: Cycle 4 queued from prior coordinator cycle — no reported pickup yet.
- T3_new: Cycle 4 queued from prior coordinator cycle — watch for db/migrations/004_dlp_audit.sql.
- T4_admin: Still STUCK on Cycle 2.
- T4_new: Cycle 1 COMPLETE. Cycle 5 tasks now queued — watch for db/migrations/005_workflows.sql.
- T5_deploy: Still STUCK on Cycle 2.
- T6_testing: Cycle 2 queued with new UNBLOCKED note. Recommend starting with test_trust_calculator (pure function, lowest friction).

### UNBLOCKED Actions This Cycle
- tasks/T1_new.md: new Cycle 5 section — 10 Celery hardening tasks with suggested pick order starting at result backend.
- tasks/T2_new.md: new Cycle 5 section — 10 Creator v2 tasks starting at tests/test_creator.py to lock generation contract.
- tasks/T4_new.md: new Cycle 5 section — 10 Workflow v2 tasks starting at migration 005_workflows.sql.
- tasks/T6_testing.md: new UNBLOCKED note at top of Cycle 2 section — 6 zero-dep starters + stub-skeleton pattern for T1-blocked tests + note that test_dlp.py already exists and can be marked [x].

### Critical Path for Cycle 6
1. **T1 migration 002 (STILL OPEN FROM CYCLE 2 — now 5 cycles stale)** — critical blocker for T2/T4/T6. Escalate.
2. T5 .env.example (still missing — blocks all setup docs).
3. T6 zero-dep starters (test_trust_calculator, test_deploy, test_self_healer, test_slack_notify) — fastest coverage wins available.
4. T4_admin zero-dep starters (audit, bulk-approve, keyboard shortcuts, CSV export).
5. T1_new Cycle 5 starters (result backend + retry policy — biggest production-readiness wins).
6. T2_new Cycle 5 starters (tests/test_creator.py first, then governance auto-estimator).
7. T4_new Cycle 5 starters (migration 005 + 3-step chain extension).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.

### Action Items for Next Cycle
- VERIFY db/migrations/002_phase2_fields.sql still absent — if still missing after 5 cycles, escalate to human reviewer.
- Verify .env.example appears at repo root.
- Check whether T6 has picked up test_trust_calculator (simplest zero-dep starter).
- Watch for db/migrations/004_dlp_audit.sql (T3_NEW Cycle 4) and db/migrations/005_workflows.sql (T4_NEW Cycle 5).
- Verify test_dlp line in T6 gets marked [x] — it's already implemented by T3_NEW with 21 passing tests.
- If T1_new owner picks up Cycle 5, watch for celery_app.py changes (result backend first).

### Prior Cycle Archive (Cycle 4)
Last check: 2026-04-16 (Cycle 4)

### Cycle 4 Highlights
- THREE new parallel tracks shipped since Cycle 3: T1_NEW (Celery async pipeline), T2_NEW (Conversational Tool Creator), T3_NEW (Runtime DLP Masking), T4_NEW (Tool Composability v1). All marked DONE at top of PROGRESS.md.
- Pipeline is now Celery-backed: `_launch_pipeline` dispatches via `celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id])`; beat schedules self_heal every 6h.
- Runtime DLP now MASKS (not just logs) — Phase 2 per SPEC line 652 achieved ahead of schedule; 21 passing tests.

### Task Queue Health (post-triage)
- T1_backend: 10 incomplete (unchanged). Cycle 2 UNBLOCKED note from prior cycle still current.
- T1_new (Celery): 10/10 [x] done per PROGRESS top; task file checkboxes still [ ] — cosmetic sync only, no new tasks needed.
- T2_agents: 10 incomplete (unchanged). Cycle 2 UNBLOCKED note still current.
- T2_new (Creator): DONE per PROGRESS top; task file checkboxes still [ ] — cosmetic sync only.
- T3_frontend: WAS 0 incomplete → **Cycle 4 section added with 10 new SPEC-driven tasks** (email_draft/table renderers per SPEC 951-952, shareable link 916, instructions modal 915, progress_pct bar, tier banners 355-375, markdown sanitizer, archive, footer 820, fork flow). UNBLOCKED note included in new section.
- T3_new (DLP v2): WAS 0 incomplete → **Cycle 4 section added with 10 new tasks** (expanded regex: IPv4/AWS/GitHub/OpenAI/JWT, mask_level param, detect_category, migration 004 for dlp_audits + tools.dlp_policy, analytics categories, admin DLP detail endpoint, UI details panel, expanded tests). UNBLOCKED note included.
- T4_admin: 10 incomplete (unchanged). **NEW** UNBLOCKED note added this cycle listing 5 zero-dep starters (audit, bulk-approve, self-healer activity GET, keyboard shortcuts, CSV export).
- T4_new (Workflow): DONE per PROGRESS top; task file checkboxes still [ ] — cosmetic sync only.
- T5_deploy: 10 incomplete (unchanged). Cycle 2 UNBLOCKED note still current.
- T6_testing: 10 incomplete (unchanged). tests/test_dlp.py (21 tests, passing) + tests/test_workflow.py (7 tests, passing) written by sister tracks cover T6 line 24 (test_dlp) and adjacent to Cycle 2 scope.

**Tasks added this cycle: 20** (10 to T3_frontend.md, 10 to T3_new.md).

### Terminal Status (Cycle 4 pickup)
- T1_backend: Still STUCK on Cycle 2. Last owned-file activity: api/server.py 00:00 (T1_NEW + T2_NEW edits only; core Cycle 2 endpoints not built). Zero Cycle 2 [x]. Migration 002 still missing. Blocks T2/T4/T6 downstream.
- T1_new: ACTIVE and DONE (celery_app.py 23:59, agents/tasks.py 23:58, scripts/start_worker.sh 23:59, scripts/start_beat.sh 00:00).
- T2_agents: Still STUCK on Cycle 2. agents/ core files untouched since 23:28. Zero Cycle 2 [x].
- T2_new: ACTIVE and DONE (api/creator.py 23:59 + frontend/creator.html/js at 00:00).
- T3_frontend: IDLE since Cycle 1 done (no frontend/*.js changes since 23:40). Cycle 4 tasks now queued; terminal should see 10 new items next pickup.
- T3_new: ACTIVE and DONE for v1 (api/dlp.py 23:58, executor.py DLP integration 23:58, admin.js badge). Cycle 4 v2 tasks now queued.
- T4_admin: Still STUCK — admin.py 23:59 mtime is from T3_NEW analytics touch, not Cycle 2 work. Zero Cycle 2 [x]. NEW UNBLOCKED note written.
- T4_new: ACTIVE and DONE (workflow.py 23:58, workflow.html + js at 00:00, test_workflow.py 00:01).
- T5_deploy: Still STUCK. Last owned-file activity: docker-compose.yml 23:58 (T1_NEW addition of celery services, not T5). Deploy/ files untouched since 23:26. Zero Cycle 2 [x].
- T6_testing: AMBIGUOUS. tests/conftest.py 23:46 (Cycle 3), tests/test_dlp.py 23:59 (T3_NEW), tests/test_workflow.py 00:01 (T4_NEW). No T6-owned Cycle 2 test files created this cycle.

### UNBLOCKED Actions This Cycle
- tasks/T3_frontend.md: new Cycle 4 section — 10 SPEC-driven tasks with UNBLOCKED note clarifying backend endpoint dependencies and fallback strategies.
- tasks/T3_new.md: new Cycle 4 section — 10 DLP v2 tasks with suggested pick order starting at migration 004.
- tasks/T4_admin.md: new UNBLOCKED note at top of Cycle 2 section — identifies 5 zero-dep starters (audit, bulk-approve, self-healer activity GET, keyboard shortcuts, CSV export) and flags which 3 tasks require T1 migration 002.

### Critical Path for Cycle 5
1. **T1 migration 002 (STILL OPEN FROM CYCLE 2)** — single biggest unblock for T2/T4/T6. Four cycles elapsed without landing.
2. T5 zero-dep starters (.env.example FIRST — still missing, blocks all setup docs).
3. T4 zero-dep starters via new UNBLOCKED note (audit + bulk-approve + keyboard shortcuts + CSV export).
4. T2 zero-dep starters (retry_with_backoff + JSON repair + red_team structuring) — still unblocked but untouched.
5. T3_frontend Cycle 4 starters (email_draft/table renderers, shareable link — all SPEC-driven pure frontend).
6. T3_new Cycle 4 starters (migration 004 + expanded regex + detect_category).
7. T6 Cycle 2 coverage expansion (test_versions, test_rate_limit, test_instructions_generation, etc.).

### Contract Reminders (from CONTRACTS.md)
- Database: PostgreSQL only, raw psycopg2, no ORM.
- API: Flask on port 8090, /api/ prefix, JSON responses.
- Frontend: Vanilla JS, no framework, no build step.
- File ownership boundaries are strict — no cross-terminal file edits.

### Action Items for Next Cycle
- Verify db/migrations/002_phase2_fields.sql exists and contains expanded column set (progress_pct, review_tokens_used, stage_failed, tool_versions.status, archived_at, pii_detected).
- Verify .env.example exists at repo root.
- Count Cycle 2 [x] on T1_backend/T2_agents/T4_admin/T5_deploy/T6_testing — flag any terminal with 4 consecutive zero-progress cycles.
- Verify frontend terminal has picked up Cycle 4 tasks (watch frontend/js/tool.js + frontend/js/submit.js for changes).
- Watch for db/migrations/004_dlp_audit.sql appearance (T3_NEW Cycle 4 starter).
- Ask T1_new/T2_new/T4_new owners to sync [x] boxes in their task files so future triage counts are accurate.

## T-DASH — GTM Analytics Dashboard
- [x] `api/analytics.py` — Flask blueprint `/api/analytics` with `X-Admin-Key` auth (decorator pattern copied from `api/admin.py`). Five endpoints, each a single SQL query: `GET /funnel` (6-stage submission lifecycle via FILTER + LATERAL join to agent_reviews for `reviewed`), `GET /builders` (author leaderboard grouped by author_email, LIMIT 20, returns submissions/approval_rate/avg_reliability/total_runs), `GET /quality` (confusion matrix + precision/recall from eval_runs; catches `UndefinedTable` and returns `{empty:true}` when the table or data is absent), `GET /latency` (width_bucket histogram over eval_runs.latency_ms WHERE load_test_run=TRUE; same empty-guard), `GET /cost-breakdown` (runs.cost_usd × week × tool category over last 90d, with a `categories` list so the frontend can stack consistently). `py_compile` clean. Does NOT duplicate any metric from `/api/admin/analytics` (T4, admin.py:467-563) — this blueprint complements it.
- [x] `frontend/analytics.html` — Dedicated page using existing Forge design tokens (dark default, DM Sans/Mono, #0066FF accent) from `css/styles.css`. 5-card KPI strip (total_tools, runs_month, avg_rating, agent_pass_rate, pending_count) feeding off the admin endpoint. 3×3 card grid: Adoption (runs/day line), Cost (stacked weekly bars), Lifecycle funnel (stage bars), Pipeline quality (confusion matrix + precision/recall), Latency distribution (histogram), Risk (trust tier doughnut + PII-masked inline counter), Top tools (horizontal bar), Builder leaderboard (spans 2 cols). Scoped `<style>` for dashboard-only widgets avoids touching global CSS. Responsive breakpoints at 1100/700px.
- [x] `frontend/js/analytics.js` — Parallelized `Promise.all` fetch of `/api/admin/analytics` + all five new endpoints; Chart.js 4.4.1 via jsDelivr CDN. Admin key: read from `localStorage.forge_admin_key`, prompts once if missing, cleared on 401 so reload re-prompts. Every card has a `.loading-note` overlay that flips to an `.empty-note` hint (`Run scripts/run_eval.py to populate`) when the server returns `{empty:true}` — layout is stable with no JS exceptions even if every endpoint 401s or 5xxs. Trust-tier doughnut uses the same color tokens as the rest of Forge.
- [x] `api/server.py` — Added analytics blueprint hook as the last entry alongside the existing try/except-guarded registrations (admin, creator, workflow, apps, learning, forgedata). `grep -n 'analytics' api/server.py` before: 0 matches. After: 2 matches (import + register_blueprint) at lines 941-942. `py_compile` clean.
- [x] `frontend/index.html` — Added single `<a href="/analytics.html" class="muted">Analytics</a>` entry into the existing top-right platform-links nav alongside Apps and Chain Tools.
- [x] Verification: `python3 -m py_compile api/analytics.py api/server.py` OK. `node --check frontend/js/analytics.js` OK. `html.parser` parse of `analytics.html` OK. Served `frontend/` statically on :8766 — `analytics.html`, `/js/analytics.js`, `/css/styles.css` all returned 200. Confirmed JS sets loading/empty notes on fetch failure so the 3×3 grid renders regardless of backend availability. `tasks/T_DASH.md` created with full task checklist.

T-DASH DONE
