# T4 GITHUB APP / AUTO-DEPLOY

## Rules
- Own: `forge_bot/` directory (everything inside it except files T5 owns), plus one targeted edit to `api/server.py` (new endpoint `POST /api/admin/tools/<id>/update-html` only)
- T5 owns `forge_bot/slack_bot.py`, `forge_bot/start_slack.sh`, `forge_bot/slack_README.md` — do NOT touch those
- Use `venv/bin/python3` and `venv/bin/pip` for all commands
- Mark tasks `[x]` when done, update PROGRESS.md after each file
- Run `venv/bin/python3 -m py_compile` on every edited Python file
- Never stop. When all tasks done write `T4-APP DONE` to PROGRESS.md

## Tasks

UNBLOCKED: THREE of your tasks are zero-dep and can ship today without waiting on T3_forge_cli: (a) forge_bot/webhook.py signature validation + push-event handler skeleton (pure Flask on port 8093, HMAC comparison via stdlib hmac.compare_digest), (b) forge_bot/forge.yaml.example (10-line YAML template), (c) POST /api/admin/tools/<id>/update-html endpoint (admin-auth decorator already exists in api/admin.py — reuse check_admin_key). The deployer.py call to /api/submit/app needs T3_forge_cli to finish that endpoint first — write deployer.py today with a TODO comment at the POST line noting it will succeed once T3 lands. Suggested pick order: (1) forge.yaml.example (5 min, pure YAML). (2) webhook.py with HMAC validation (pure stdlib, independent of other tracks). (3) /api/admin/tools/<id>/update-html endpoint (10 min, reuses existing admin decorator). (4) deployer.py skeleton with TODO for POST. (5) Complete deployer.py AFTER T3_forge_cli ships /api/submit/app. (6) setup.sh + README.md. Port reminder: webhook runs on 8093 (NOT 8091 — that's reserved for test dashboard). GitHub token env var should be `GITHUB_TOKEN` (standard GitHub convention) and documented in .env.example.

[x] `venv/bin/pip install pyyaml` — required for forge.yaml parsing

[x] `forge_bot/__init__.py` (empty) and `mkdir -p forge_bot/logs`

[x] `forge_bot/webhook.py` — Flask app on port **8093** (NOT 8091 — that port is taken by the test dashboard). Listens for GitHub webhook events. `POST /webhook`:
  - Validate `X-Hub-Signature-256` header using `GITHUB_WEBHOOK_SECRET` env var — use `hmac.compare_digest()` for timing-safe comparison
  - On push event to `main`/`master`: read `repository.clone_url`, head commit SHA; call `handle_push(repo_url, repo_name, commit_sha)` in a background thread
  - Return 200 quickly (under 10s) so GitHub doesn't retry

[x] `forge_bot/deployer.py` — `handle_push(repo_url, repo_name, commit_sha)`:
  1. `git clone --depth=1 {repo_url} /tmp/forge-deploy/{repo_name}-{commit_sha}`
  2. Look for `forge.yaml` in repo root. If missing and `index.html` exists, auto-generate a forge.yaml with name from repo name.
  3. Parse forge.yaml: `{name, tagline, description, category, entry (default: index.html), type (default: app), schedule (optional cron), slack_channel (optional)}`
  4. Read entry file as `app_html`
  5. POST to Forge `/api/submit/app` with html + metadata. Uses `FORGE_API_URL` and `FORGE_API_KEY` env vars.
  6. If slug collision (tool already exists): POST to `/api/admin/tools/{id}/update-html` to update in place (endpoint defined below).
  7. Call GitHub API to post commit status: `POST /repos/{owner}/{repo}/statuses/{sha}` with `{state:'success', target_url: forge_app_url, description:'Deployed to Forge', context:'forge/deploy'}`. Requires a GitHub token env var — document which one in README.
  8. Cleanup: `shutil.rmtree` the temp directory
  9. Log all steps to `forge_bot/logs/deploy.log`

[x] `forge_bot/forge.yaml.example`:
  ```
  name: My App
  tagline: What my app does in one sentence
  category: other
  entry: index.html
  type: app
  # Optional
  # schedule: "0 8 * * 1-5"
  # slack_channel: "#sales-team"
  ```

[x] `forge_bot/setup.sh` — installs git (if missing), writes a systemd unit (or launchd plist) for the webhook service, prints GitHub App + webhook URL setup instructions. Include ngrok tip for local dev.

[x] Add `POST /api/admin/tools/<id>/update-html` endpoint to `api/server.py` (ONLY this endpoint):
  - Admin-only (`X-Admin-Key` header)
  - Body: `{html: string}`
  - Updates `app_html` on existing approved app tool
  - Returns `{success, url}`
  - No re-review required — this path is for trusted auto-redeploy from GitHub.

[x] Append to `.env.example`: `GITHUB_WEBHOOK_SECRET=`, `FORGE_API_URL=http://localhost:8090`, `FORGE_API_KEY=`, and `GITHUB_TOKEN=` (for posting commit statuses).

[x] `forge_bot/README.md` — setup: 1) Create GitHub App at github.com/settings/apps. 2) Set webhook URL to `https://your-forge-host:8093/webhook` (or ngrok for local dev). 3) Set env vars. 4) Add `forge.yaml` to any repo. 5) Push to main — app auto-deploys. Include troubleshooting section.

[x] When all tasks complete, append `T4-APP DONE` line to PROGRESS.md.

## Cycle 7 Tasks (PR previews + safety rails + installations)

UNBLOCKED: All 10 tasks stay inside T4_github_app ownership (forge_bot/webhook.py, deployer.py, README.md, forge_bot/tests/). Backend POST /api/submit/app + POST /api/admin/tools/<id>/update-html already live from Cycle 1. PR-preview path (task 1) requires no new Forge backend work — reuse update-html with a derived slug. Secrets scanning (task 9) reuses api/dlp.py regex patterns but only import the module, no cross-terminal edit. Suggested pick order: schema validator (2) FIRST (fast, improves error messages) → allowlist (3) → secrets scan (9) → commit-message tokens (6) → deploy history (5) → automated rollback (4) → PR previews (1) → installation flow (7) → README badge (8) → test suite last.

[ ] forge_bot/deployer.py - forge.yaml schema validator: require name, tagline, entry; enum-validate category (account_research|email_generation|contact_scoring|data_lookup|reporting|onboarding|forecasting|other) and type ('app'|'prompt'); validate schedule string via croniter; on failure POST commit status='failure' with message and abort.
[ ] forge_bot/webhook.py + forge_bot/deployer.py - repo allowlist via FORGE_REPO_ALLOWLIST env var (comma-separated owner/repo); if set, reject push events from non-listed repos with commit status='error' description="Repo not on Forge allowlist"; no-op when env unset.
[ ] forge_bot/deployer.py - secrets pre-scan: `from api.dlp import DLPEngine`; run DLPEngine(level='strict').detect_category(app_html); if any of {aws_key, github_token, openai_key, jwt, ssn, credit_card} detected, abort deploy with commit status='failure' listing detected types (NEVER the actual values).
[ ] forge_bot/deployer.py - commit-message tokens: read commit message from GitHub API at deploy time; `{{forge-skip}}` aborts deploy cleanly with status='success' desc='Skipped via commit message'; `{{forge-deploy:<slug>}}` overrides destination slug; log every parsed token to deploy.log.
[ ] forge_bot/webhook.py - per-commit deploy history: each handled push appends a JSON line to forge_bot/logs/deploys.jsonl with {repo, sha, tool_id, tool_slug, status, duration_ms, ts}; reuse existing RotatingFileHandler pattern (daily rotation, keep 14).
[ ] forge_bot/deployer.py - automated rollback: on /api/submit/app returning 5xx/4xx, retry 2× with 5s/15s backoff; if still failing AND forge_bot/snapshots/<slug>.html exists, POST that snapshot to /api/admin/tools/<id>/update-html to restore last-known-good; log decision path.
[ ] forge_bot/webhook.py - pull_request events (opened|synchronize): deploy to preview slug `<slug>-pr<number>`; post sticky PR comment with preview URL via GitHub API; on closed event, POST /api/admin/tools/<id>/archive to hide the preview tool (skipped if update-html based).
[ ] forge_bot/webhook.py - GitHub App installation webhook: persist installation_id + account login to forge_bot/installations.json on `installation` event (action='created' or 'deleted'); deployer uses this to exchange JWT for installation access token when posting commit statuses.
[ ] forge_bot/README.md - add Forge status badge snippet: `![Forge](<FORGE_HOST>/api/tools/<id>/badge.svg)` + note that T1 badge endpoint is a follow-up (fall back to a stub SVG until live).
[ ] forge_bot/tests/test_webhook.py - pytest covering: HMAC valid/invalid/empty-secret/missing-header, push-to-main dispatch (mock handle_push), push-to-feature-branch ignored, ping returns pong, PR opened triggers preview deploy (mock deployer), installation event persists JSON.
