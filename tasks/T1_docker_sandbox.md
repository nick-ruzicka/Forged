# T1 DOCKER SANDBOX (Wave 3)

## Architecture
- **Tier 1 (existing):** HTML in DB served directly from Flask. Keep working for all apps with `container_mode=false`.
- **Tier 2 (new):** `nginx:alpine` container per app. Hibernate/wake pattern. Agent runs OUTSIDE the container. All state via PostgreSQL ForgeAPI.

## Environment notes (important — read before writing code)

- Docker runtime on this Mac is **colima**, NOT Docker Desktop.
- Default Docker SDK expects `/var/run/docker.sock`, but colima puts the socket at `~/.colima/default/docker.sock`.
- **Runner script already exports `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`** — any subprocess or `docker-py` / `docker.from_env()` usage inherits it.
- Do not `sudo ln -s` the socket; just rely on the env var.
- First task item below double-checks the env var is active in this shell.

## Rules
- Own ONLY: `forge_sandbox/` (entire new dir), `db/migrations/006_sandbox.sql`, **surgical** additions to `api/apps.py` (container proxy branch only), new sandbox routes in `api/server.py`
- Next migration number is **006** (005 already exists)
- Run `venv/bin/python3 -m py_compile` on each Python file
- Mark tasks `[x]` as done, update PROGRESS.md after each file
- Never stop. When all tasks done write `T1-WAVE3 DONE` to PROGRESS.md

## Tasks

UNBLOCKED (Cycle 12 coordinator note, 2026-04-16): Two tasks done (preflight verified colima socket; migration 006_sandbox.sql applied — confirmed on disk). The remaining 10 tasks are all within T1_docker_sandbox ownership (forge_sandbox/ + targeted apps.py and server.py edits). Zero cross-terminal blocker — colima is live, migration columns are in place, Celery is already running per T1_NEW Cycle 1 smoke test. T2_forgedata is **explicitly blocked on this track's T1-WAVE3 DONE marker** — every task you ship moves T2_forgedata's seed app closer to launch. Suggested pick order: (1) `forge_sandbox/__init__.py` (5 sec, empty file). (2) `forge_sandbox/builder.py` — pure subprocess wrapping `docker build` (zero Python deps; no docker-py needed). (3) `forge_sandbox/manager.py` — SandboxManager class with port-scan + `docker run`/`docker stop` via subprocess. (4) `forge_sandbox/hibernator.py` CLI (one-pager). (5) `forge_sandbox/tasks.py` Celery wrapper + beat_schedule append. (6) Surgical `api/apps.py` proxy branch — preserve existing Tier 1 path. (7) Admin sandbox routes in `api/server.py`. (8) `forge_sandbox/README.md`. (9) End-to-end smoke test on `job-search-pipeline`. (10) Append T1-WAVE3 DONE → unblocks T2_forgedata immediately. Reminder: every subprocess call inherits `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` from the runner script; do NOT hardcode the socket path in Python or fall back to `/var/run/docker.sock`. Resource limits (256m / 0.5 cpu) are per SPEC's "small VPS" intent — do not raise without explicit ask.

[x] Preflight: `echo "$DOCKER_HOST"` should print `unix://$HOME/.colima/default/docker.sock`. Then `docker version` — daemon must respond. If not, print `DOCKER DAEMON NOT RUNNING — run: colima start` and exit 1. Do not try to auto-install/start — the user owns that.

[x] `db/migrations/006_sandbox.sql` — schema extension. Apply via `venv/bin/python3 scripts/run_migrations.py` immediately after writing.
```sql
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_mode BOOLEAN DEFAULT FALSE;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_id TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_status TEXT DEFAULT 'stopped';
ALTER TABLE tools ADD COLUMN IF NOT EXISTS container_port INTEGER;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS image_tag TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS last_request_at TIMESTAMP;
```

[x] `forge_sandbox/__init__.py` — empty package marker.

[x] `forge_sandbox/builder.py` — `build_image(tool_id, app_html, slug)`:
  - Temp dir `/tmp/forge-build/{slug}/`. Write `app_html` as `index.html`. Write `Dockerfile`:
    ```
    FROM nginx:alpine
    COPY index.html /usr/share/nginx/html/
    EXPOSE 80
    ```
  - Run `docker build -t forge-app-{slug}:latest /tmp/forge-build/{slug}/` via `subprocess.run`, capture stdout/stderr
  - Update tool row: `image_tag = 'forge-app-{slug}:latest'`
  - Clean up temp dir (even on failure)
  - Return `{success: bool, image_tag: str | None, build_output: str}`
  - Log every step to `logs/sandbox.log` with ISO timestamps

[x] `forge_sandbox/manager.py` — `SandboxManager` class:
  - `get_free_port()` — scans 9000-9999 with `socket.socket(AF_INET, SOCK_STREAM)` → `bind` → close. Returns first free.
  - `ensure_running(tool_id) -> int`:
    - Load tool. If `container_status=='running'` and `container_id`: `docker inspect` — if actually running return `container_port`.
    - If `image_tag is None`: call `builder.build_image(...)` first.
    - `docker run -d --name forge-{slug} -p {port}:80 --memory=256m --cpus=0.5 --network=bridge forge-app-{slug}:latest`
    - Poll `GET http://localhost:{port}/` up to 10s, 200ms between attempts. Fail if never 200.
    - Update tool: `container_id`, `container_status='running'`, `container_port=port`, `last_request_at=NOW()`.
    - Return port.
  - `hibernate(tool_id)` — if `container_id`: `docker stop forge-{slug}` (silent on error). Set `container_status='stopped'`. Log.
  - `hibernate_idle_containers()` — `SELECT id FROM tools WHERE container_status='running' AND last_request_at < NOW() - INTERVAL '10 minutes'`. Call `hibernate(id)` for each. Return count.
  - `pre_warm(tool_id)` — if `image_tag` and `container_status='stopped'`, call `ensure_running(tool_id)`. Log `pre-warmed {slug}`.
  - `get_status() -> dict` — query all `container_mode=true` tools, return `{running: [{slug, port, last_request_at}], stopped: [{slug}], total_containers, memory_used}` (memory: `docker stats --no-stream --format {{.MemUsage}}` aggregate).

[x] `forge_sandbox/hibernator.py` — CLI entry (for ad-hoc runs):
```python
from forge_sandbox.manager import SandboxManager
if __name__ == "__main__":
    mgr = SandboxManager()
    count = mgr.hibernate_idle_containers()
    print(f"Hibernated {count} idle containers")
    # Pre-warm anything with run_count > 10
    with db.get_db() as cur:
        cur.execute("SELECT id FROM tools WHERE container_mode=true AND run_count>10 AND container_status='stopped'")
        for row in cur.fetchall():
            mgr.pre_warm(row["id"])
```

[x] `forge_sandbox/tasks.py` — Celery wrapper (folded in from T4, zero coordination seam):
```python
from celery_app import celery_app

@celery_app.task(name="forge_sandbox.tasks.hibernate_idle")
def hibernate_idle():
    try:
        from forge_sandbox.manager import SandboxManager
        return {"hibernated": SandboxManager().hibernate_idle_containers()}
    except Exception as e:
        return {"error": str(e)}
```
Then register the schedule in `celery_app.py` `beat_schedule` (add entry, don't rewrite the dict):
```python
"hibernate-idle-containers": {
    "task": "forge_sandbox.tasks.hibernate_idle",
    "schedule": crontab(minute="*/5"),
},
```

[x] `api/apps.py` — **surgical** update to `GET /apps/<slug>` ONLY:
  - At the top of the handler: load tool, update `last_request_at = NOW()`.
  - `if tool.container_mode:` call `SandboxManager().ensure_running(tool_id) -> port`; proxy via `requests.get(f"http://localhost:{port}/")`; take `resp.text`, inject ForgeAPI script before `</body>` via string replace; return response.
  - `else:` existing behavior (serve `app_html` from DB with existing ForgeAPI injection) — do NOT modify this branch.

[x] `api/server.py` — add routes **only** (do not modify existing):
  - `GET /api/admin/sandbox/status` — admin only, returns `SandboxManager().get_status()`
  - `POST /api/admin/sandbox/hibernate/<int:tool_id>` — admin only
  - `POST /api/admin/sandbox/prewarm/<int:tool_id>` — admin only
  - `POST /api/admin/tools/<int:tool_id>/enable-container` — admin only; sets `container_mode=true`, calls `builder.build_image(...)`, returns `{success, image_tag}`

[x] `forge_sandbox/README.md` — Tier 1 vs Tier 2, how to enable container mode, resource limits (256 MB / 0.5 vCPU), hibernate policy (10 min idle), pre-warm rule (run_count > 10).

[x] End-to-end smoke test:
```bash
psql -U forge -d forge -c "UPDATE tools SET container_mode=true WHERE slug='job-search-pipeline';"
# Trigger build + run
curl -s -o /tmp/sandbox.html http://localhost:8090/apps/job-search-pipeline
grep -q "ForgeAPI" /tmp/sandbox.html && echo "INJECTED OK" || echo "MISSING INJECTION"
# Reset
psql -U forge -d forge -c "UPDATE tools SET container_mode=false WHERE slug='job-search-pipeline';"
```

[x] Append `T1-WAVE3 DONE` to PROGRESS.md when all above are complete.

## Cycle 12 Tasks (sandbox hardening — v2)

UNBLOCKED (Cycle 12 coordinator note, 2026-04-16): Wave 3 v1 shipped end-to-end — image build, hibernate/wake, admin routes, smoke test all green per top-of-PROGRESS notes. Wave 3 v2 is pure hardening: nothing in this block changes the Tier 1 path or breaks the existing container_mode contract. All 10 tasks stay inside T1_docker_sandbox ownership (forge_sandbox/* + db/migrations/00X_sandbox_*.sql + tests/test_sandbox.py + targeted server.py admin routes). SPEC drivers: lines 1208-1320 (deployment ops + nginx), lines 626-652 (Runtime DLP Layer reuse for app_html secrets scan at build time), lines 1497-1504 (MCP connector secret injection into containers — adjacent to T2_forgedata's Salesforce slice), lines 603-610 (Celery Beat cadence pattern). Suggested pick order: migration 007_sandbox_builds FIRST (unblocks build-history writes) → builder.py records build outcome → tests/test_sandbox.py (proves contract before adding features) → image GC sweep → pre-warm Celery beat → per-tool resource override → container env injection → /api/admin/sandbox/builds endpoint + admin UI hook → sandbox.log rotation → image rebuild on app_html change.

[ ] T1_docker_sandbox - db/migrations/007_sandbox_builds.sql - CREATE TABLE sandbox_builds (id SERIAL PRIMARY KEY, tool_id INTEGER REFERENCES tools(id) ON DELETE CASCADE, image_tag TEXT NOT NULL, success BOOLEAN NOT NULL, duration_ms INTEGER, build_output TEXT, app_html_hash TEXT, created_at TIMESTAMP DEFAULT NOW()); CREATE INDEX idx_sandbox_builds_tool ON sandbox_builds(tool_id, created_at DESC); CREATE INDEX idx_sandbox_builds_hash ON sandbox_builds(app_html_hash) — supports cache-skip lookup on rebuild.
[ ] T1_docker_sandbox - forge_sandbox/builder.py - record every build into sandbox_builds: insert one row with success/duration/build_output/SHA-256(app_html); on success update tools.image_tag; on failure leave image_tag unchanged so Tier 2 keeps serving last-known-good image. Hash logic enables next task's cache-skip.
[ ] T1_docker_sandbox - forge_sandbox/builder.py - rebuild detection: before docker build, SELECT app_html_hash FROM sandbox_builds WHERE tool_id=X ORDER BY id DESC LIMIT 1; if matches current SHA-256(app_html), short-circuit return {success:true, image_tag, build_output:'cache hit', cached:true}; otherwise proceed with full build. Removes spurious rebuilds when /api/admin/tools/<id>/update-html is called with identical HTML.
[ ] T1_docker_sandbox - forge_sandbox/manager.py - image GC sweep `gc_orphan_images()`: list `docker images forge-app-* --format {{.Repository}}` then SELECT slug FROM tools WHERE container_mode=true; remove any image whose forge-app-{slug} no longer maps to a container_mode=true tool. Logs each removal with reclaimed bytes (`docker image rm --force`). Returns {removed_count, reclaimed_mb}.
[ ] T1_docker_sandbox - forge_sandbox/tasks.py + celery_app.py - new Celery beat entry `gc-orphan-images` running daily at 03:00 UTC; wraps gc_orphan_images() in a try/except that logs to sandbox.log; never raises (so failed sweeps don't poison the beat schedule). Append the entry, do not rewrite the dict.
[ ] T1_docker_sandbox - forge_sandbox/tasks.py + celery_app.py - new Celery beat entry `prewarm-popular-apps` running every 10 min: `SELECT id FROM tools WHERE container_mode=true AND container_status='stopped' AND run_count>10`; call `pre_warm(id)` for each. Caps at 10 prewarms per tick to avoid stampedes. Per SPEC line 603-610 cadence pattern.
[ ] T1_docker_sandbox - forge_sandbox/manager.py - per-tool resource override: read tools.sandbox_memory_mb (NULL → 256) and tools.sandbox_cpu (NULL → 0.5) from a new column added in this migration. Pass to docker run as `--memory={mb}m --cpus={cpu}`. Hard-cap at 1024m / 2.0 vCPU server-side; reject larger values. Add ALTER TABLE columns to migration 007.
[ ] T1_docker_sandbox - forge_sandbox/manager.py - container env injection for MCP connector tokens (SPEC line 1497-1504 alignment with T2_forgedata): if tools.mcp_connectors JSON includes 'salesforce', read `SALESFORCE_*` env vars and pass `-e SALESFORCE_USERNAME=... -e SALESFORCE_TOKEN=...` to docker run. NEVER log secret values. Skip cleanly if mcp_connectors NULL or env vars absent.
[ ] T1_docker_sandbox - api/server.py - new admin route `GET /api/admin/sandbox/builds?tool_id=X&limit=20`: return last N rows from sandbox_builds joined with tool name; admin-only via _require_admin(). Powers a future admin UI panel for build history; surface success rate + median duration in response payload as aggregates.
[ ] T1_docker_sandbox - tests/test_sandbox.py - pytest covering: builder.build_image with mocked subprocess returns success/failure paths and writes correct sandbox_builds rows; cache-skip path (same hash → no docker build call); manager.ensure_running idempotency (running container short-circuits); hibernate_idle_containers respects 10-min interval; gc_orphan_images skips active containers; pre_warm bails when image_tag is NULL. Mock subprocess.run + db cursor; no real docker calls.
