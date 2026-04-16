# T3 FORGE CLI

## Rules
- Own: `forge_cli/` directory and everything inside it, plus one targeted edit to `api/server.py` (new endpoint `POST /api/submit/app` only)
- Do NOT modify any other terminal's files
- Use `venv/bin/python3` and `venv/bin/pip` for all commands
- Mark tasks `[x]` in this file when done, update PROGRESS.md after each file
- Run `venv/bin/python3 -m py_compile` on every edited Python file
- Never stop. When all tasks done write `T3-APP DONE` to PROGRESS.md

## Tasks

UNBLOCKED: All CLI scaffolding is zero-dep stdlib work (argparse + urllib + webbrowser — NO external deps). The POST /api/submit/app endpoint you need to add is also zero-dep on other terminals: tools table already has app_html/app_type columns from T1_app_platform migration 004, and celery_app.send_task('agents.tasks.run_pipeline_task') is already live from T1_NEW. Suggested pick order: (1) forge_cli/__init__.py + cli.py skeleton with argparse commands FIRST (30 min, pure Python). (2) forge_cli/setup.py entry_point (5 min). (3) forge_cli/README.md (10 min). (4) POST /api/submit/app in api/server.py — reuse existing slug generation + celery dispatch from /api/tools/submit. Use werkzeug's FileStorage for zip uploads; zipfile.ZipFile stdlib to extract. (5) pip install -e forge_cli/ + smoke test. All 7 implementation tasks can be done serially in ~90 minutes of focused work; zero cross-terminal coordination required. NOTE: T4_github_app's deployer.py will POST to this endpoint and T5_slack_bot will also use it — ship this first to unblock both.

[x] Create `forge_cli/__init__.py` (empty) and `forge_cli/cli.py`.

[x] `forge_cli/cli.py` — Python CLI using `argparse` (stdlib only; OK to use `urllib` for HTTP). Commands:
  - `forge deploy [path] [--name NAME] [--description DESC] [--category CAT] [--host HOST]`
    - `path` defaults to current dir
    - If single `index.html` found → read it, POST to `HOST/api/submit/app` with html + metadata as multipart/form-data
    - If directory → zip it (exclude `node_modules`, `.git`, `__pycache__`), POST zip as multipart/form-data
    - If `--name` missing → derive from directory name converted to Title Case
    - Prints `Deploying [name] to Forge...` then `Live at: [url]` on success
  - `forge status` — GET `HOST/api/health`, print status
  - `forge list` — GET `HOST/api/tools?app_type=app`, print table of live apps
  - `forge open [slug]` — open `HOST/apps/SLUG` using `webbrowser` module
  - `forge login [host]` — save host URL to `~/.forge/config.json`
  - `forge --version` — print version

[x] `forge_cli/setup.py` — package setup so `pip install -e forge_cli/` works. Entry point: `forge = forge_cli.cli:main`. Version `0.1.0`. Zero external dependencies.

[x] `forge_cli/README.md` — quick start. First line: "Deploy any HTML app to Forge in one command." Installation (`pip install -e /path/to/forge_cli`). Examples for each command. Section "With Claude Code" — you can tell Claude to run `forge deploy` to publish the current project.

[x] Add `POST /api/submit/app` to `api/server.py` (ONLY this endpoint; do not modify anything else in server.py):
  - Accepts multipart/form-data with fields: `html` (string) OR `file` (zip upload); plus `name`, `description`, `category`, `author_name`, `author_email`
  - If zip: extract, find `index.html`, read as `app_html`
  - Create tool row with `app_type='app'`, `status='pending_review'`, slug derived from name
  - **Pipeline dispatch MUST use Celery** (same as `/api/tools/submit`):
    `celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id])`
    DO NOT use a raw background thread.
  - Return `{id, slug, url: '/apps/' + slug, status}`

[x] Install forge_cli: `venv/bin/pip install -e forge_cli/`. Verify `venv/bin/forge --version` prints `0.1.0`.

[x] End-to-end test: create `/tmp/test-app/index.html` with a minimal `<!DOCTYPE html>` document, run `venv/bin/forge deploy /tmp/test-app --name "CLI Smoke Test" --host http://localhost:8090`, verify the tool appears at `/api/tools?search=CLI%20Smoke`.

[x] When all tasks complete, append `T3-APP DONE` line to PROGRESS.md.

## Cycle 7 Tasks (CLI polish + dev UX + tests)

UNBLOCKED: All 10 tasks stay inside T3_forge_cli ownership (forge_cli/cli.py, forge_cli/tests/, forge_cli/README.md). Zero cross-terminal blockers — everything builds on /api/tools, /api/tools/<id>/versions, /api/tools/<id>/runs, /api/submit/app (all live). `forge rollback` + `forge tail` reference T1_app_platform Cycle 7 endpoints (/runs and a possible /rollback) — implement against the expected URL with graceful fallback so CLI ships independently. Suggested pick order: forge init FIRST (zero-dep scaffolding) → forge dev (stdlib http.server) → forge diff (difflib) → forge logs → forge test → forge status upgrade → forge login wave 2 → forge tail (SSE) → forge rollback → test suite last.

[ ] forge_cli/cli.py - `forge init [template]` command: scaffolds new project with index.html + forge.yaml stubs; templates 'blank'|'kanban'|'dashboard' fetched from HOST/api/tools/slug/<template-slug> (graceful fallback to bundled strings if HOST unreachable). Skips overwriting existing files, --force overrides.
[ ] forge_cli/cli.py - `forge dev` command: starts stdlib http.server on :8094 rooted at current dir; opens webbrowser.open('http://localhost:8094'); polls index.html mtime every 500ms and injects a tiny <script> that reloads on change (appended at runtime, not written to disk).
[ ] forge_cli/cli.py - `forge diff [tool_id]` command: GET HOST/api/tools/<id>, read local index.html, print difflib.unified_diff(local, remote.app_html); exit 0 on match, 1 on diff (useful in CI gates).
[ ] forge_cli/cli.py - `forge logs [--tool ID] [--follow]` command: GET HOST/api/apps/<id>/runs (depends on T1 Cycle 7 endpoint) and print JSON lines; --follow long-polls every 3s for new rows. On 404 prints "Runs endpoint not yet live" and exits 0.
[ ] forge_cli/cli.py - `forge test` command: reads local forge.yaml test_cases section ([{inputs, expected_contains}]); POST each to HOST/api/tools/<tool_id>/run; assert output contains expected_contains. Exit 0 on all-pass, 1 on any-fail. Prints colored per-case verdict (OK/FAIL).
[ ] forge_cli/cli.py - `forge status --tool <id>` upgrade: GET HOST/api/agent/status/<tool_id>, render pipeline progress with text bars for each stage (Classifier/Security/RedTeam/Hardener/QA/Synth); exit 0 when status=approved, 1 on rejected, 2 still running.
[ ] forge_cli/cli.py - `forge login` wave 2: if FORGE_API_KEY env not set, getpass.getpass("API key:") prompt; persist to ~/.forge/config.json with os.chmod(path, 0o600); subsequent commands add X-API-Key header from this file.
[ ] forge_cli/cli.py - `forge tail <tool_id>` command: opens urllib SSE stream from HOST/api/apps/<id>/runs/stream; prints each event as JSON line; Ctrl+C exits cleanly. 404 fallback: prints "Streaming endpoint unavailable — use `forge logs --follow` instead".
[ ] forge_cli/cli.py - `forge rollback <tool_id>` command: GET HOST/api/tools/<id>/versions (already live); interactive prompt picks a version; POST HOST/api/admin/tools/<id>/rollback (T1_app_platform Cycle 7 item) with {version} body + X-Admin-Key header; prints new endpoint_url on 200, falls back to `forge deploy --update` hint on 404.
[ ] forge_cli/tests/test_cli.py - pytest covering: deploy (monkeypatch urllib.request.urlopen), status, list, open (monkeypatch webbrowser.open), init template scaffolding + --force behavior, login key persistence with mode-check, diff exit codes (0 match / 1 diff). Use pytest --tb=short; mark network paths with responses fixture.
