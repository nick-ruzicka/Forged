# FORGE PROGRESS

> **2026-04-21** — Methodology shifted. Old multi-terminal coordinator pattern archived to `_archive/`. See `VISION.md` for current product direction.

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

## T-DASH — GTM Analytics Dashboard
- [x] `api/analytics.py` — Flask blueprint `/api/analytics` with `X-Admin-Key` auth (decorator pattern copied from `api/admin.py`). Five endpoints, each a single SQL query: `GET /funnel` (6-stage submission lifecycle via FILTER + LATERAL join to agent_reviews for `reviewed`), `GET /builders` (author leaderboard grouped by author_email, LIMIT 20, returns submissions/approval_rate/avg_reliability/total_runs), `GET /quality` (confusion matrix + precision/recall from eval_runs; catches `UndefinedTable` and returns `{empty:true}` when the table or data is absent), `GET /latency` (width_bucket histogram over eval_runs.latency_ms WHERE load_test_run=TRUE; same empty-guard), `GET /cost-breakdown` (runs.cost_usd × week × tool category over last 90d, with a `categories` list so the frontend can stack consistently). `py_compile` clean. Does NOT duplicate any metric from `/api/admin/analytics` (T4, admin.py:467-563) — this blueprint complements it.
- [x] `frontend/analytics.html` — Dedicated page using existing Forge design tokens (dark default, DM Sans/Mono, #0066FF accent) from `css/styles.css`. 5-card KPI strip (total_tools, runs_month, avg_rating, agent_pass_rate, pending_count) feeding off the admin endpoint. 3×3 card grid: Adoption (runs/day line), Cost (stacked weekly bars), Lifecycle funnel (stage bars), Pipeline quality (confusion matrix + precision/recall), Latency distribution (histogram), Risk (trust tier doughnut + PII-masked inline counter), Top tools (horizontal bar), Builder leaderboard (spans 2 cols). Scoped `<style>` for dashboard-only widgets avoids touching global CSS. Responsive breakpoints at 1100/700px.
- [x] `frontend/js/analytics.js` — Parallelized `Promise.all` fetch of `/api/admin/analytics` + all five new endpoints; Chart.js 4.4.1 via jsDelivr CDN. Admin key: read from `localStorage.forge_admin_key`, prompts once if missing, cleared on 401 so reload re-prompts. Every card has a `.loading-note` overlay that flips to an `.empty-note` hint (`Run scripts/run_eval.py to populate`) when the server returns `{empty:true}` — layout is stable with no JS exceptions even if every endpoint 401s or 5xxs. Trust-tier doughnut uses the same color tokens as the rest of Forge.
- [x] `api/server.py` — Added analytics blueprint hook as the last entry alongside the existing try/except-guarded registrations (admin, creator, workflow, apps, learning, forgedata). `grep -n 'analytics' api/server.py` before: 0 matches. After: 2 matches (import + register_blueprint) at lines 941-942. `py_compile` clean.
- [x] `frontend/index.html` — Added single `<a href="/analytics.html" class="muted">Analytics</a>` entry into the existing top-right platform-links nav alongside Apps and Chain Tools.
- [x] Verification: `python3 -m py_compile api/analytics.py api/server.py` OK. `node --check frontend/js/analytics.js` OK. `html.parser` parse of `analytics.html` OK. Served `frontend/` statically on :8766 — `analytics.html`, `/js/analytics.js`, `/css/styles.css` all returned 200. Confirmed JS sets loading/empty notes on fetch failure so the 3×3 grid renders regardless of backend availability. `tasks/T_DASH.md` created with full task checklist.

T-DASH DONE

