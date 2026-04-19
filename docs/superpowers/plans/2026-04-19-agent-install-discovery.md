# Agent Install Discovery & Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The local `forge_agent` discovers apps installed on the user's machine (`/Applications/*.app` + `brew list`) and the backend reconciles them against the catalog, marking matched tools as installed and surfacing unknown apps as personal "detected" tiles on **My Forge**.

**Architecture:** Agent stays dumb — it scans and POSTs a raw payload (`{apps, brew, brew_casks}`) to a new `POST /api/agent/scan` Flask endpoint. The backend owns all matching, three passes (bundle ID, brew formula, brew cask), upserts into `user_items` with a `source='detected'` marker, never overwriting `source='manual'` rows, and unmarks rows that fall out of the scan. Triggers: agent startup, post-install hook, on-demand "Refresh installed apps" button. No periodic polling. Unknown apps live as `user_items` rows with `tool_id=NULL` keyed by `detected_bundle_id`.

**Tech Stack:**
- Backend: Python 3, Flask, psycopg2, PostgreSQL
- Agent: Python 3 stdlib (`http.server`, `plistlib`, `subprocess`)
- Web: Next.js 16 + TypeScript + Tailwind + shadcn (under `web/`). **NOT vanilla JS — `frontend/` is being retired and is out of scope for this plan.**
- Tests: pytest (`tests/`), Postgres test DB via `tests/conftest.py`

**Spec:** `docs/superpowers/specs/2026-04-19-agent-install-discovery-design.md`

**Important repo notes:**
- `web/AGENTS.md` warns "This is NOT the Next.js you know" — read `web/node_modules/next/dist/docs/` before reaching for any Next.js API beyond standard client components, SWR, and shadcn primitives. This plan only uses those, so consult docs only if you deviate.
- Migration files run alphabetically via `tests/conftest.py:99` `glob.glob(... migrations_dir, "*.sql")`. Current head is `017_shelf_user_id_unique.sql`. Use `018_install_discovery.sql`.
- Identity comes from `_get_identity()` (`api/server.py:265`) — `X-Forge-User-Id` header (anonymous UUID) and optional `X-Forge-User-Email`.
- Backend DB pattern: `with db.get_db() as cur:` (see `api/server.py:894`).
- Agent token: `~/.forge/agent-token`, sent as `X-Forge-Token` header (see existing proxy at `api/server.py:722`).

---

## File Structure

**Create:**
- `db/migrations/018_install_discovery.sql` — schema changes (new columns + index)
- `db/migrations/data/bundle_ids.yaml` — hand-maintained slug → bundle ID mapping
- `db/seed_bundle_ids.py` — idempotent backfill script
- `forge_agent/scanner.py` — `/Applications` + `brew list` scanner (isolated module)
- `tests/agents/test_scanner.py` — unit tests for the scanner
- `tests/test_reconcile.py` — unit tests for the reconciliation helpers
- `tests/test_agent_scan_endpoint.py` — integration test for `POST /api/agent/scan`
- `web/components/detected-tile.tsx` — UI tile for unknown apps

**Modify:**
- `forge_agent/agent.py` — add `_handle_scan` handler, route `GET /scan`, startup hook, post-install hook
- `api/server.py` — add `_reconcile_matches`, `_reconcile_unknowns`, `_reconcile_uninstalls`, `POST /api/agent/scan`, `POST /api/me/items/<id>/hide`, extend `GET /api/me/items`, add proxy `GET /api/forge-agent/scan`
- `web/lib/types.ts` — extend `UserItem`
- `web/lib/api.ts` — add `scanInstalled()` and `hideItem()`
- `web/lib/hooks.ts` — invalidate `/me/items` after scan
- `web/app/my-forge/page.tsx` — Refresh button, Detected badge, Hide menu, render `DetectedTile`

---

## Pre-Reqs

Confirm before starting:

- Postgres running locally and `forge_test` database exists (`tests/conftest.py:28`).
- `forge_agent` can run locally (`forge_agent/install.sh`).
- `web/` dev server boots: `cd web && npm install && npm run dev`.

---

### Task 1: Migration 018 — Schema Changes

**Files:**
- Create: `db/migrations/018_install_discovery.sql`
- Test: `tests/test_migration_018.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_018.py`:

```python
"""Verify migration 018 installs the install-discovery schema correctly."""
import pytest


def test_tools_has_app_bundle_id_column(db):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'tools' AND column_name = 'app_bundle_id'
            """
        )
        row = cur.fetchone()
    assert row is not None, "tools.app_bundle_id missing"
    # tuple or dict cursor — handle both
    nullable = row[1] if isinstance(row, tuple) else row["is_nullable"]
    assert nullable == "YES"


def test_tools_has_partial_index_on_bundle_id(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'tools' AND indexname = 'tools_bundle_id_idx'"
        )
        assert cur.fetchone() is not None


@pytest.mark.parametrize("col,default", [
    ("source", "manual"),
    ("hidden", "false"),
    ("detected_bundle_id", None),
    ("detected_name", None),
])
def test_user_items_has_new_columns(db, col, default):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_name = 'user_items' AND column_name = %s
            """,
            (col,),
        )
        row = cur.fetchone()
    assert row is not None, f"user_items.{col} missing"


def test_user_items_tool_id_is_nullable(db):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'user_items' AND column_name = 'tool_id'
            """
        )
        row = cur.fetchone()
    nullable = row[0] if isinstance(row, tuple) else row["is_nullable"]
    assert nullable == "YES", "tool_id should be NULL-able for unknown-app rows"


def test_user_items_detected_unique_index_exists(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'user_items' AND indexname = 'user_items_detected_unique'"
        )
        assert cur.fetchone() is not None


def test_can_insert_unknown_app_row(db):
    """Sanity-check: a row with tool_id=NULL + detected_bundle_id should insert and be unique per user."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name, source, installed_locally)
            VALUES ('user-A', NULL, 'com.test.app', 'TestApp', 'detected', TRUE)
            """
        )
        # Second insert with the same (user_id, detected_bundle_id) must violate the partial unique index
        with pytest.raises(Exception):
            cur.execute(
                """
                INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name, source, installed_locally)
                VALUES ('user-A', NULL, 'com.test.app', 'TestApp Again', 'detected', TRUE)
                """
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_018.py -v`
Expected: FAIL — column / index does not exist.

- [ ] **Step 3: Write the migration**

Create `db/migrations/018_install_discovery.sql`:

```sql
-- 018_install_discovery.sql
-- Schema for agent-driven install discovery & reconciliation.
-- See docs/superpowers/specs/2026-04-19-agent-install-discovery-design.md

-- 1. Catalog: optional Mac bundle ID for matching scanned /Applications entries.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS app_bundle_id TEXT;
CREATE INDEX IF NOT EXISTS tools_bundle_id_idx
    ON tools(app_bundle_id)
    WHERE app_bundle_id IS NOT NULL;

-- 2. Shelf: distinguish manual adds from auto-detected, allow hiding,
--    and let unknown-app rows live without a catalog tool_id.
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS detected_bundle_id TEXT;
ALTER TABLE user_items ADD COLUMN IF NOT EXISTS detected_name TEXT;

-- Allow unknown-app rows (tool_id NULL).
ALTER TABLE user_items ALTER COLUMN tool_id DROP NOT NULL;

-- One row per user per unknown app.
CREATE UNIQUE INDEX IF NOT EXISTS user_items_detected_unique
    ON user_items(user_id, detected_bundle_id)
    WHERE tool_id IS NULL AND detected_bundle_id IS NOT NULL;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_018.py -v`
Expected: PASS — all six tests green.

- [ ] **Step 5: Commit**

```bash
git add db/migrations/018_install_discovery.sql tests/test_migration_018.py
git commit -m "feat(db): migration 018 — install discovery schema"
```

---

### Task 2: Scanner — `_scan_applications`

**Files:**
- Create: `forge_agent/scanner.py`
- Test: `tests/agents/test_scanner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agents/test_scanner.py`:

```python
"""Unit tests for forge_agent.scanner — pure-function scanner for installed apps."""
import plistlib
from pathlib import Path

import pytest

from forge_agent import scanner


def _make_app(root: Path, name: str, bundle_id: str | None, bundle_name: str | None = None) -> Path:
    """Create a fake .app bundle. Pass bundle_id=None to skip CFBundleIdentifier."""
    app_dir = root / f"{name}.app" / "Contents"
    app_dir.mkdir(parents=True)
    plist = {}
    if bundle_id is not None:
        plist["CFBundleIdentifier"] = bundle_id
    if bundle_name is not None:
        plist["CFBundleName"] = bundle_name
    (app_dir / "Info.plist").write_bytes(plistlib.dumps(plist))
    return app_dir.parent


def test_scan_returns_normal_app(tmp_path):
    _make_app(tmp_path, "Pluely", "com.pluely.Pluely", "Pluely")
    result = scanner._scan_applications(root=str(tmp_path))
    assert {"bundle_id": "com.pluely.Pluely",
            "name": "Pluely",
            "path": str(tmp_path / "Pluely.app")} in result


def test_scan_uses_filename_when_bundle_name_missing(tmp_path):
    _make_app(tmp_path, "Raycast", "com.raycast.macos", bundle_name=None)
    result = scanner._scan_applications(root=str(tmp_path))
    names = [r["name"] for r in result]
    assert "Raycast" in names


def test_scan_skips_app_without_bundle_id(tmp_path):
    _make_app(tmp_path, "Broken", bundle_id=None, bundle_name="Broken")
    result = scanner._scan_applications(root=str(tmp_path))
    assert result == []


def test_scan_skips_app_with_no_info_plist(tmp_path):
    (tmp_path / "Empty.app" / "Contents").mkdir(parents=True)
    result = scanner._scan_applications(root=str(tmp_path))
    assert result == []


def test_scan_includes_nested_apps_at_depth_two(tmp_path):
    """Suite bundles like Xcode contain helper .app at Contents/Applications/*.app."""
    inner = tmp_path / "Xcode.app" / "Contents" / "Applications"
    inner.mkdir(parents=True)
    _make_app(inner, "Instruments", "com.apple.Instruments", "Instruments")
    # Also add the outer app
    _make_app(tmp_path, "Xcode", "com.apple.Xcode", "Xcode")
    result = scanner._scan_applications(root=str(tmp_path))
    bundle_ids = {r["bundle_id"] for r in result}
    assert "com.apple.Xcode" in bundle_ids
    assert "com.apple.Instruments" in bundle_ids


def test_scan_returns_empty_when_root_missing(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert scanner._scan_applications(root=str(missing)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Ensure the test directory exists, then run:

```bash
mkdir -p tests/agents
touch tests/agents/__init__.py
pytest tests/agents/test_scanner.py -v
```

Expected: FAIL — `ModuleNotFoundError: forge_agent.scanner`.

- [ ] **Step 3: Write minimal implementation**

Create `forge_agent/scanner.py`:

```python
"""Local scanner for installed Mac apps and Homebrew packages.

Pure functions — no HTTP, no global state. Called from forge_agent/agent.py.
"""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

DEFAULT_APPLICATIONS_ROOT = "/Applications"
_APPLICATIONS_GLOB_DEPTH = 2  # /Applications/*.app and /Applications/*/Contents/Applications/*.app


def scan() -> dict:
    """Return the full scan payload for POSTing to the backend."""
    return {
        "apps": _scan_applications(),
        "brew": _brew_list(cask=False),
        "brew_casks": _brew_list(cask=True),
    }


def _scan_applications(root: str = DEFAULT_APPLICATIONS_ROOT) -> list[dict]:
    """Find every *.app under root (depth 2), return [{bundle_id, name, path}].

    Skips bundles without Info.plist or without CFBundleIdentifier.
    Returns [] if root doesn't exist or is unreadable.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    results: list[dict] = []
    seen_paths: set[str] = set()
    try:
        # Depth 1: /Applications/*.app
        # Depth 2: /Applications/*/Contents/Applications/*.app (suite helpers like Xcode)
        candidates = list(root_path.glob("*.app")) + list(root_path.glob("*/Contents/Applications/*.app"))
    except OSError:
        return []

    for app in candidates:
        path_str = str(app)
        if path_str in seen_paths:
            continue
        seen_paths.add(path_str)
        info = app / "Contents" / "Info.plist"
        if not info.is_file():
            continue
        try:
            with info.open("rb") as fh:
                plist = plistlib.load(fh)
        except Exception:
            continue
        bundle_id = plist.get("CFBundleIdentifier")
        if not bundle_id:
            continue
        name = plist.get("CFBundleName") or app.stem
        results.append({"bundle_id": bundle_id, "name": name, "path": path_str})
    return results


def _brew_list(cask: bool) -> list[str]:
    """Return brew formulas (or casks). Empty list on failure or missing brew."""
    cmd = ["brew", "list"] + (["--cask"] if cask else ["--formula"])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_scanner.py -v`
Expected: PASS — all six application-scanning tests.

- [ ] **Step 5: Commit**

```bash
git add forge_agent/scanner.py tests/agents/test_scanner.py tests/agents/__init__.py
git commit -m "feat(agent): add /Applications scanner with bundle-id extraction"
```

---

### Task 3: Scanner — `_brew_list` and `scan()` Composition

**Files:**
- Modify: `tests/agents/test_scanner.py` (add brew tests)
- Verify: `forge_agent/scanner.py` (already implements `_brew_list` + `scan()` from Task 2)

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/test_scanner.py`:

```python
def test_brew_list_returns_lines(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "node\nraycast\n\nyarn\n"
    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    assert scanner._brew_list(cask=False) == ["node", "raycast", "yarn"]


def test_brew_list_returns_empty_when_brew_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("brew not in PATH")
    monkeypatch.setattr(scanner.subprocess, "run", boom)
    assert scanner._brew_list(cask=False) == []


def test_brew_list_returns_empty_on_nonzero_exit(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    assert scanner._brew_list(cask=True) == []


def test_brew_list_casks_uses_cask_flag(monkeypatch):
    seen_cmds: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stdout = "raycast\n"

    def fake_run(cmd, **k):
        seen_cmds.append(cmd)
        return FakeProc()

    monkeypatch.setattr(scanner.subprocess, "run", fake_run)
    scanner._brew_list(cask=True)
    assert seen_cmds[-1] == ["brew", "list", "--cask"]


def test_scan_composes_apps_and_brew(monkeypatch, tmp_path):
    _make_app(tmp_path, "Pluely", "com.pluely.Pluely", "Pluely")

    class FakeProc:
        returncode = 0
        stdout = "node\n"

    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.setattr(scanner, "DEFAULT_APPLICATIONS_ROOT", str(tmp_path))

    payload = scanner.scan()
    assert any(a["bundle_id"] == "com.pluely.Pluely" for a in payload["apps"])
    assert payload["brew"] == ["node"]
    assert payload["brew_casks"] == ["node"]  # same fake; just proves both calls
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/agents/test_scanner.py -v`
Expected: PASS already (`scanner._brew_list` and `scan()` were implemented in Task 2).

If any test fails, the implementation is wrong — fix `forge_agent/scanner.py` until tests pass before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/agents/test_scanner.py
git commit -m "test(agent): cover scanner brew_list edge cases and scan() composition"
```

---

### Task 4: Agent — `GET /scan` Endpoint with 30s Cache

**Files:**
- Modify: `forge_agent/agent.py` (add `_handle_scan`, register route, add caching)

- [ ] **Step 1: Read the existing agent route table**

Run: `grep -n "self.path ==" forge_agent/agent.py | head -20`

Expected: a `do_GET` / `do_POST` dispatch where each route is a string compare (e.g., `if self.path == "/running": ...`). This is `http.server` style — no Flask. Add `/scan` to the same dispatch.

- [ ] **Step 2: Add the cache and handler**

In `forge_agent/agent.py`, find the section near other module-level caches like `_running_cache` (search for `_running_cache = `). Add right below it:

```python
# 30-second cache for /scan results — second call within 30s of last
# successful scan returns the cached payload without re-scanning.
_scan_cache: dict = {"ts": 0.0, "result": None}
SCAN_CACHE_TTL_SEC = 30
```

Then, near other `_handle_*` methods (e.g., next to `_handle_running`), add:

```python
def _handle_scan(self):
    """Run a local scan, POST results to backend, return aggregated counts.

    Cached for 30s — repeat calls within the window return the prior result
    without rescanning or re-POSTing.
    """
    import urllib.request as ur
    from forge_agent import scanner

    now = time.time()
    if (now - _scan_cache["ts"] < SCAN_CACHE_TTL_SEC) and _scan_cache["result"] is not None:
        self._json(_scan_cache["result"])
        return

    payload = scanner.scan()

    # Forward identity headers so the backend can attribute the scan to a user.
    user_id = self.headers.get("X-Forge-User-Id", "")
    user_email = self.headers.get("X-Forge-User-Email", "")
    if not user_id:
        self._json({"error": "user_id_required"}, 400)
        return

    try:
        req = ur.Request(
            f"{ALLOWED_ORIGIN.rstrip('/')}/api/agent/scan",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Forge-User-Id": user_id,
                "X-Forge-User-Email": user_email,
            },
            method="POST",
        )
        with ur.urlopen(req, timeout=15) as r:
            backend_resp = json.loads(r.read())
    except Exception as exc:
        audit.info("SCAN failed: %s", str(exc)[:200])
        self._json({"error": str(exc)[:200]}, 502)
        return

    _scan_cache["ts"] = now
    _scan_cache["result"] = backend_resp
    audit.info("SCAN matched=%s detected=%s unmarked=%s",
               backend_resp.get("matched"), backend_resp.get("detected"), backend_resp.get("unmarked"))
    self._json(backend_resp)
```

Then in the GET dispatch (search for `def do_GET` and look for the `if self.path == "/running":` branch), add a sibling branch:

```python
        if self.path == "/scan":
            self._handle_scan()
            return
```

- [ ] **Step 3: Add a smoke test**

Create `tests/agents/test_agent_scan_handler.py`:

```python
"""Smoke test: agent's /scan handler caches results and POSTs to backend."""
from unittest.mock import MagicMock, patch

import pytest


def test_scan_endpoint_caches_within_ttl(monkeypatch):
    from forge_agent import agent as agent_mod

    # Reset cache
    agent_mod._scan_cache["ts"] = 0.0
    agent_mod._scan_cache["result"] = None

    fake_scan = {"apps": [], "brew": [], "brew_casks": []}
    monkeypatch.setattr(agent_mod, "scanner",
                        type("S", (), {"scan": staticmethod(lambda: fake_scan)}))

    backend_calls = []

    def fake_urlopen(req, timeout=15):
        backend_calls.append(req)
        class R:
            def read(self): return b'{"matched": 0, "detected": 0, "unmarked": 0}'
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return R()

    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", fake_urlopen)

    handler = MagicMock()
    handler.headers = {"X-Forge-User-Id": "user-A"}
    handler._json_args = []
    handler._json = lambda body, status=200: handler._json_args.append((body, status)) or None

    # AgentHandler is at forge_agent/agent.py:286.
    bound = agent_mod.AgentHandler._handle_scan

    bound(handler)
    assert len(backend_calls) == 1
    bound(handler)  # within TTL
    assert len(backend_calls) == 1, "Second call within TTL should hit cache"
    assert handler._json_args[-1][0]["matched"] == 0
```

> **Note for implementer:** If the handler class name in `agent.py` is not `AgentHandler`, update the import. Run `grep -n "class .*Handler" forge_agent/agent.py` to find it.

- [ ] **Step 4: Run the test and adjust**

Run: `pytest tests/agents/test_agent_scan_handler.py -v`

If it fails because of class-name mismatch, fix the import and rerun. Expected end state: PASS.

- [ ] **Step 5: Commit**

```bash
git add forge_agent/agent.py tests/agents/test_agent_scan_handler.py
git commit -m "feat(agent): GET /scan endpoint with 30s cache"
```

---

### Task 5: Agent — Startup + Post-Install Triggers

**Files:**
- Modify: `forge_agent/agent.py`

- [ ] **Step 1: Add the post-install trigger**

In `forge_agent/agent.py`, find `_stream_process` (currently around line 588). After the `_register_app(registry_entry)` call on success, fire a scan via in-process call. Locate the success branch:

```python
            if proc.returncode == 0:
                if registry_entry:
                    _register_app(registry_entry)
                self._sse_event("installed", {"success": True, "message": f"{name} installed successfully"})
```

Modify to:

```python
            if proc.returncode == 0:
                if registry_entry:
                    _register_app(registry_entry)
                # Trigger a scan so the backend reconciles any sidecar installs
                # (e.g., `brew install node` pulls in npm). Fire-and-forget; never
                # block the install response on this.
                _trigger_background_scan(self.headers.get("X-Forge-User-Id", ""),
                                         self.headers.get("X-Forge-User-Email", ""))
                self._sse_event("installed", {"success": True, "message": f"{name} installed successfully"})
```

- [ ] **Step 2: Add the helper near the other module-level helpers**

Place this near `_scan_cache` (added in Task 4):

```python
def _trigger_background_scan(user_id: str, user_email: str = "") -> None:
    """Fire scan asynchronously; swallow all errors. Used for startup + post-install."""
    import threading
    import urllib.request as ur
    from forge_agent import scanner

    if not user_id:
        return  # No identity yet — caller will retry on next event.

    def _worker():
        try:
            payload = scanner.scan()
            req = ur.Request(
                f"{ALLOWED_ORIGIN.rstrip('/')}/api/agent/scan",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Forge-User-Id": user_id,
                    "X-Forge-User-Email": user_email,
                },
                method="POST",
            )
            with ur.urlopen(req, timeout=15) as r:
                _scan_cache["ts"] = time.time()
                _scan_cache["result"] = json.loads(r.read())
                audit.info("BG-SCAN ok")
        except Exception as exc:
            logging.warning("background scan failed: %s", str(exc)[:200])

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
```

- [ ] **Step 3: Add startup trigger**

Find the `if __name__ == "__main__":` block at the bottom of `forge_agent/agent.py` (or wherever the server is started — search for `HTTPServer(`). Just before the `serve_forever()` call, add a deferred scan that reads the last-known user from `~/.forge/last-user.json` (the agent doesn't have a user identity until the first request, so we cache it).

First, modify the `/install` and `/scan` handlers to write user identity on each request. Add this helper near `_register_app`:

```python
LAST_USER_FILE = FORGE_DIR / "last-user.json"


def _remember_user(user_id: str, user_email: str = "") -> None:
    """Cache the most recent user identity so startup can trigger a scan."""
    if not user_id:
        return
    try:
        LAST_USER_FILE.write_text(json.dumps({"user_id": user_id, "email": user_email}))
    except OSError:
        pass


def _last_user() -> tuple[str, str]:
    if not LAST_USER_FILE.exists():
        return "", ""
    try:
        d = json.loads(LAST_USER_FILE.read_text())
        return d.get("user_id", ""), d.get("email", "")
    except Exception:
        return "", ""
```

In `_handle_scan` and `_handle_install`, after extracting `user_id`, add:

```python
_remember_user(user_id, user_email)
```

(For `_handle_install`, capture both header values into local variables first if not already done.)

Then in the startup section of `agent.py` (before `serve_forever`):

```python
# Fire a startup scan against the last-known user so /api/me/items
# is current the moment the user opens My Forge after a reboot.
_uid, _email = _last_user()
if _uid:
    _trigger_background_scan(_uid, _email)
```

- [ ] **Step 4: Manual verification**

Restart the agent (`launchctl unload ~/Library/LaunchAgents/com.forge.agent.plist && launchctl load ~/Library/LaunchAgents/com.forge.agent.plist`) and tail `~/.forge/agent.log`. Within a few seconds you should see either `BG-SCAN ok` or a `background scan failed` warning. The "failed" path is fine if the backend isn't running yet — that's expected and gracefully recovered.

- [ ] **Step 5: Commit**

```bash
git add forge_agent/agent.py
git commit -m "feat(agent): scan on startup + after every successful install"
```

---

### Task 6: Backend — `_reconcile_matches` Helper

**Files:**
- Modify: `api/server.py` (new helper)
- Test: `tests/test_reconcile.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_reconcile.py`:

```python
"""Unit tests for backend reconciliation helpers."""
import json
import uuid

import pytest


@pytest.fixture
def seeded_user(db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    return uid


@pytest.fixture
def insert_tool(db):
    def _insert(slug, **kw):
        cols = {
            "slug": slug,
            "name": kw.pop("name", slug),
            "tagline": "test",
            "description": "test",
            "category": "other",
            "output_type": "probabilistic",
            "system_prompt": "x",
            "hardened_prompt": "x",
            "input_schema": json.dumps([]),
            "status": "approved",
            "delivery": kw.pop("delivery", "external"),
            "app_bundle_id": kw.pop("app_bundle_id", None),
            "install_meta": kw.pop("install_meta", None),
        }
        cols.update(kw)
        with db.cursor() as cur:
            keys = ", ".join(cols.keys())
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO tools ({keys}) VALUES ({placeholders}) RETURNING id",
                list(cols.values()),
            )
            return cur.fetchone()[0]
    return _insert


def test_reconcile_matches_by_bundle_id(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    payload = {
        "apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/Applications/Pluely.app"}],
        "brew": [],
        "brew_casks": [],
    }

    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched

    with db.cursor() as cur:
        cur.execute(
            "SELECT installed_locally, source FROM user_items WHERE user_id = %s AND tool_id = %s",
            (seeded_user, tool_id),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] is True or row[0] == True  # installed_locally
    assert row[1] == "detected"  # source


def test_reconcile_matches_by_brew_formula(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("nodejs",
                          install_meta=json.dumps({"type": "brew", "formula": "node"}))
    payload = {"apps": [], "brew": ["node"], "brew_casks": []}
    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched


def test_reconcile_matches_by_brew_cask(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("raycast",
                          install_meta=json.dumps({"type": "brew", "cask": "raycast"}))
    payload = {"apps": [], "brew": [], "brew_casks": ["raycast"]}
    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched


def test_reconcile_matches_does_not_overwrite_manual(db, seeded_user, insert_tool):
    """Manual-source rows that are already installed_locally=TRUE keep source='manual'."""
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
            VALUES (%s, %s, TRUE, NOW(), 'manual')
            """,
            (seeded_user, tool_id),
        )
    payload = {"apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/x"}],
               "brew": [], "brew_casks": []}
    server._reconcile_matches(seeded_user, payload, db.cursor())
    with db.cursor() as cur:
        cur.execute("SELECT source FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (seeded_user, tool_id))
        assert cur.fetchone()[0] == "manual"


def test_reconcile_matches_upgrades_manual_uninstalled_to_installed(db, seeded_user, insert_tool):
    """A manual row with installed_locally=FALSE flips to TRUE on detection but source stays manual."""
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, source)
            VALUES (%s, %s, FALSE, 'manual')
            """,
            (seeded_user, tool_id),
        )
    payload = {"apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/x"}],
               "brew": [], "brew_casks": []}
    server._reconcile_matches(seeded_user, payload, db.cursor())
    with db.cursor() as cur:
        cur.execute("SELECT installed_locally, source FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (seeded_user, tool_id))
        row = cur.fetchone()
        assert row[0] is True
        assert row[1] == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reconcile.py -v -k matches`
Expected: FAIL — `AttributeError: module 'api.server' has no attribute '_reconcile_matches'`.

- [ ] **Step 3: Add the helper to `api/server.py`**

Insert this near other shelf code (e.g., right after `shelf_mark_installed`, around line 1046):

```python
# -------------------- Install discovery (agent scan) --------------------

def _reconcile_matches(user_id: str, payload: dict, cur) -> set[int]:
    """Three-pass match: bundle ID, brew formula, brew cask.

    Upserts user_items rows with source='detected'. Manual-source rows that
    are already installed_locally=TRUE keep source='manual'. Manual rows with
    installed_locally=FALSE are upgraded to TRUE on detection (source stays
    'manual'). Returns the set of matched tool ids for the caller's bookkeeping.
    """
    bundle_ids = [a["bundle_id"] for a in payload.get("apps", []) if a.get("bundle_id")]
    formulas = list(payload.get("brew", []))
    casks = list(payload.get("brew_casks", []))

    matched: set[int] = set()

    if bundle_ids:
        cur.execute(
            "SELECT id FROM tools WHERE app_bundle_id = ANY(%s) AND status = 'approved'",
            (bundle_ids,),
        )
        matched.update(r[0] for r in cur.fetchall())

    if formulas:
        cur.execute(
            """
            SELECT id FROM tools
            WHERE status = 'approved'
              AND install_meta IS NOT NULL
              AND (install_meta::jsonb)->>'type' = 'brew'
              AND (install_meta::jsonb)->>'formula' = ANY(%s)
            """,
            (formulas,),
        )
        matched.update(r[0] for r in cur.fetchall())

    if casks:
        cur.execute(
            """
            SELECT id FROM tools
            WHERE status = 'approved'
              AND install_meta IS NOT NULL
              AND (install_meta::jsonb)->>'type' = 'brew'
              AND (install_meta::jsonb)->>'cask' = ANY(%s)
            """,
            (casks,),
        )
        matched.update(r[0] for r in cur.fetchall())

    for tool_id in matched:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
            VALUES (%s, %s, TRUE, NOW(), 'detected')
            ON CONFLICT (user_id, tool_id) WHERE user_id IS NOT NULL DO UPDATE
              SET installed_locally = TRUE,
                  installed_at = COALESCE(user_items.installed_at, NOW()),
                  -- preserve manual provenance; only upgrade source when row was detected before
                  source = CASE WHEN user_items.source = 'manual'
                                THEN 'manual' ELSE 'detected' END
            """,
            (user_id, tool_id),
        )

    return matched
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reconcile.py -v -k matches`
Expected: PASS — all five `matches` tests.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_reconcile.py
git commit -m "feat(api): _reconcile_matches — three-pass scan-to-shelf reconciler"
```

---

### Task 7: Backend — `_reconcile_unknowns` Helper

**Files:**
- Modify: `api/server.py`
- Test: `tests/test_reconcile.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_reconcile.py`:

```python
def test_reconcile_unknowns_creates_row_for_unmatched_app(db, seeded_user, insert_tool):
    from api import server

    payload = {
        "apps": [
            {"bundle_id": "com.unknown.foo", "name": "Foo", "path": "/Applications/Foo.app"},
        ],
        "brew": [], "brew_casks": [],
    }
    server._reconcile_unknowns(seeded_user, payload["apps"], matched_tool_ids=set(), cur=db.cursor())

    with db.cursor() as cur:
        cur.execute(
            """SELECT detected_name, source, installed_locally, hidden
               FROM user_items
               WHERE user_id = %s AND tool_id IS NULL AND detected_bundle_id = %s""",
            (seeded_user, "com.unknown.foo"),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "Foo"
    assert row[1] == "detected"
    assert row[2] is True
    assert row[3] is False


def test_reconcile_unknowns_skips_apps_that_matched(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    payload = {
        "apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/x"}],
        "brew": [], "brew_casks": [],
    }
    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    server._reconcile_unknowns(seeded_user, payload["apps"], matched, db.cursor())

    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM user_items WHERE user_id=%s AND tool_id IS NULL",
            (seeded_user,),
        )
        assert cur.fetchone()[0] == 0  # No unknown row created — it matched a tool.


def test_reconcile_unknowns_preserves_hidden_flag(db, seeded_user):
    from api import server

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                    source, installed_locally, hidden)
            VALUES (%s, NULL, 'com.unknown.foo', 'Foo', 'detected', TRUE, TRUE)
            """,
            (seeded_user,),
        )
    payload = {"apps": [{"bundle_id": "com.unknown.foo", "name": "Foo Updated", "path": "/x"}],
               "brew": [], "brew_casks": []}
    server._reconcile_unknowns(seeded_user, payload["apps"], set(), db.cursor())

    with db.cursor() as cur:
        cur.execute(
            "SELECT hidden, detected_name FROM user_items WHERE user_id=%s AND detected_bundle_id=%s",
            (seeded_user, "com.unknown.foo"),
        )
        row = cur.fetchone()
    assert row[0] is True, "hidden flag must not be cleared by a re-detection"
    assert row[1] == "Foo Updated", "name should still refresh so un-hide shows current data"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_reconcile.py -v -k unknowns`
Expected: FAIL — `_reconcile_unknowns` not defined.

- [ ] **Step 3: Add the helper**

Append to `api/server.py` immediately after `_reconcile_matches`:

```python
def _reconcile_unknowns(user_id: str, apps: list, matched_tool_ids: set, cur) -> int:
    """Upsert user_items rows for apps that didn't match any catalog tool.

    Identifies unknowns by bundle_id; preserves hidden=TRUE when re-detecting.
    Returns the count of unknown rows touched.
    """
    # Build the set of bundle_ids that matched a catalog tool — those don't become unknowns.
    if matched_tool_ids:
        cur.execute(
            "SELECT app_bundle_id FROM tools WHERE id = ANY(%s) AND app_bundle_id IS NOT NULL",
            (list(matched_tool_ids),),
        )
        matched_bundle_ids = {r[0] for r in cur.fetchall()}
    else:
        matched_bundle_ids = set()

    touched = 0
    for app in apps:
        bundle_id = app.get("bundle_id")
        if not bundle_id or bundle_id in matched_bundle_ids:
            continue
        name = app.get("name") or bundle_id
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                    source, installed_locally, installed_at, hidden)
            VALUES (%s, NULL, %s, %s, 'detected', TRUE, NOW(), FALSE)
            ON CONFLICT (user_id, detected_bundle_id) WHERE tool_id IS NULL AND detected_bundle_id IS NOT NULL
            DO UPDATE SET
                detected_name     = EXCLUDED.detected_name,
                installed_locally = TRUE,
                installed_at      = COALESCE(user_items.installed_at, NOW())
                -- hidden is intentionally NOT touched here
            """,
            (user_id, bundle_id, name),
        )
        touched += 1
    return touched
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_reconcile.py -v -k unknowns`
Expected: PASS — all three unknown tests.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_reconcile.py
git commit -m "feat(api): _reconcile_unknowns — surface uncatalogued apps as detected rows"
```

---

### Task 8: Backend — `_reconcile_uninstalls` Helper

**Files:**
- Modify: `api/server.py`
- Test: `tests/test_reconcile.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_reconcile.py`:

```python
def test_reconcile_uninstalls_unmarks_matched_tool_no_longer_present(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    # Detected previously
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
               VALUES (%s, %s, TRUE, NOW(), 'detected')""",
            (seeded_user, tool_id),
        )
    # Now scan no longer contains it
    payload = {"apps": [], "brew": [], "brew_casks": []}
    unmarked = server._reconcile_uninstalls(seeded_user, payload, set(), db.cursor())
    assert unmarked >= 1

    with db.cursor() as cur:
        cur.execute(
            "SELECT installed_locally, installed_at FROM user_items WHERE user_id=%s AND tool_id=%s",
            (seeded_user, tool_id),
        )
        row = cur.fetchone()
    assert row[0] is False
    assert row[1] is None


def test_reconcile_uninstalls_unmarks_unknown_app_no_longer_present(db, seeded_user):
    from api import server

    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                       source, installed_locally, installed_at)
               VALUES (%s, NULL, 'com.gone.app', 'Gone', 'detected', TRUE, NOW())""",
            (seeded_user,),
        )
    payload = {"apps": [], "brew": [], "brew_casks": []}
    unmarked = server._reconcile_uninstalls(seeded_user, payload, set(), db.cursor())
    assert unmarked >= 1

    with db.cursor() as cur:
        cur.execute(
            "SELECT installed_locally FROM user_items WHERE user_id=%s AND detected_bundle_id=%s",
            (seeded_user, "com.gone.app"),
        )
        assert cur.fetchone()[0] is False


def test_reconcile_uninstalls_does_not_touch_manual_rows(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
               VALUES (%s, %s, TRUE, NOW(), 'manual')""",
            (seeded_user, tool_id),
        )
    payload = {"apps": [], "brew": [], "brew_casks": []}
    server._reconcile_uninstalls(seeded_user, payload, set(), db.cursor())

    with db.cursor() as cur:
        cur.execute(
            "SELECT installed_locally FROM user_items WHERE user_id=%s AND tool_id=%s",
            (seeded_user, tool_id),
        )
        assert cur.fetchone()[0] is True, "manual rows must never be auto-unmarked"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_reconcile.py -v -k uninstalls`
Expected: FAIL — `_reconcile_uninstalls` undefined.

- [ ] **Step 3: Add the helper**

Append to `api/server.py` immediately after `_reconcile_unknowns`:

```python
def _reconcile_uninstalls(user_id: str, payload: dict, matched_tool_ids: set, cur) -> int:
    """Set installed_locally=FALSE for source='detected' rows missing from this scan.

    - Matched rows (tool_id NOT NULL): keyed by app_bundle_id / install_meta lookup.
    - Unknown rows (tool_id NULL): keyed by detected_bundle_id.
    Manual-source rows are never touched.
    """
    seen_bundle_ids = {a["bundle_id"] for a in payload.get("apps", []) if a.get("bundle_id")}
    seen_formulas = set(payload.get("brew", []))
    seen_casks = set(payload.get("brew_casks", []))

    # Pre-load currently-detected, currently-installed shelf rows for this user.
    cur.execute(
        """
        SELECT ui.id, ui.tool_id, ui.detected_bundle_id,
               t.app_bundle_id,
               (t.install_meta::jsonb)->>'formula' AS formula,
               (t.install_meta::jsonb)->>'cask' AS cask
        FROM user_items ui
        LEFT JOIN tools t ON t.id = ui.tool_id
        WHERE ui.user_id = %s
          AND ui.source = 'detected'
          AND ui.installed_locally = TRUE
        """,
        (user_id,),
    )
    candidates = cur.fetchall()

    to_unmark: list[int] = []
    for row in candidates:
        ui_id, tool_id, det_bundle_id, app_bundle_id, formula, cask = row
        if tool_id is None:
            # Unknown row — key on detected_bundle_id.
            if det_bundle_id and det_bundle_id not in seen_bundle_ids:
                to_unmark.append(ui_id)
        else:
            # Matched row — present in scan if any of its match keys match.
            present = (
                (app_bundle_id and app_bundle_id in seen_bundle_ids)
                or (formula and formula in seen_formulas)
                or (cask and cask in seen_casks)
            )
            if not present:
                to_unmark.append(ui_id)

    if to_unmark:
        cur.execute(
            "UPDATE user_items SET installed_locally = FALSE, installed_at = NULL WHERE id = ANY(%s)",
            (to_unmark,),
        )
    return len(to_unmark)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_reconcile.py -v -k uninstalls`
Expected: PASS — all three uninstall tests.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_reconcile.py
git commit -m "feat(api): _reconcile_uninstalls — flip installed_locally=FALSE when scan misses a detected row"
```

---

### Task 9: Backend — `POST /api/agent/scan` Endpoint

**Files:**
- Modify: `api/server.py`
- Test: `tests/test_agent_scan_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_scan_endpoint.py`:

```python
"""Integration test for POST /api/agent/scan."""
import json
import uuid


def test_scan_endpoint_requires_user_id(client):
    r = client.post("/api/agent/scan", json={"apps": [], "brew": [], "brew_casks": []})
    assert r.status_code == 400
    assert "user_id" in r.get_json().get("error", "").lower()


def test_scan_endpoint_returns_counts(client, db, sample_tool):
    # Seed the catalog tool with a bundle id we can match against.
    with db.cursor() as cur:
        cur.execute(
            "UPDATE tools SET app_bundle_id = %s WHERE id = %s",
            ("com.test.bundle", sample_tool["id"]),
        )
    uid = f"user-{uuid.uuid4().hex[:8]}"
    payload = {
        "apps": [
            {"bundle_id": "com.test.bundle", "name": "Test", "path": "/x"},
            {"bundle_id": "com.unknown.zzz", "name": "Zzz", "path": "/y"},
        ],
        "brew": [],
        "brew_casks": [],
    }
    r = client.post("/api/agent/scan", json=payload, headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["matched"] == 1
    assert body["detected"] == 1


def test_scan_endpoint_round_trip_then_uninstall(client, db, sample_tool):
    """Two scans: first installs, second drops the app — row goes installed=False."""
    with db.cursor() as cur:
        cur.execute("UPDATE tools SET app_bundle_id = %s WHERE id = %s",
                    ("com.test.bundle", sample_tool["id"]))
    uid = f"user-{uuid.uuid4().hex[:8]}"

    p1 = {"apps": [{"bundle_id": "com.test.bundle", "name": "Test", "path": "/x"}],
          "brew": [], "brew_casks": []}
    r1 = client.post("/api/agent/scan", json=p1, headers={"X-Forge-User-Id": uid})
    assert r1.status_code == 200

    p2 = {"apps": [], "brew": [], "brew_casks": []}
    r2 = client.post("/api/agent/scan", json=p2, headers={"X-Forge-User-Id": uid})
    assert r2.status_code == 200
    assert r2.get_json()["unmarked"] >= 1

    with db.cursor() as cur:
        cur.execute("SELECT installed_locally FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (uid, sample_tool["id"]))
        assert cur.fetchone()[0] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_agent_scan_endpoint.py -v`
Expected: FAIL — endpoint returns 404.

- [ ] **Step 3: Add the endpoint**

Append to `api/server.py` after `_reconcile_uninstalls`:

```python
@app.route("/api/agent/scan", methods=["POST"])
def agent_scan():
    """Receive a scan payload from forge_agent and reconcile against this user's shelf.

    Body shape:
        {"apps": [{"bundle_id": str, "name": str, "path": str}, ...],
         "brew": [str, ...],
         "brew_casks": [str, ...]}
    """
    uid, _email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("apps"), list):
        return jsonify({"error": "apps_must_be_list"}), 400

    with db.get_db() as cur:
        matched = _reconcile_matches(uid, payload, cur)
        _reconcile_unknowns(uid, payload["apps"], matched, cur)
        unmarked = _reconcile_uninstalls(uid, payload, matched, cur)

        cur.execute(
            """SELECT COUNT(*) FROM user_items
               WHERE user_id = %s AND tool_id IS NULL
                 AND installed_locally = TRUE AND hidden = FALSE""",
            (uid,),
        )
        detected_count = cur.fetchone()[0]

    return jsonify({
        "matched":  len(matched),
        "detected": detected_count,
        "unmarked": unmarked,
    })
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_agent_scan_endpoint.py -v`
Expected: PASS — all three endpoint tests.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_agent_scan_endpoint.py
git commit -m "feat(api): POST /api/agent/scan composes reconciliation passes"
```

---

### Task 10: Backend — `POST /api/me/items/<id>/hide`

**Files:**
- Modify: `api/server.py`
- Test: `tests/test_agent_scan_endpoint.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_scan_endpoint.py`:

```python
def test_hide_endpoint_marks_row_hidden(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source)
               VALUES (%s, %s, TRUE, 'detected') RETURNING id""",
            (uid, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["hidden"] is True

    with db.cursor() as cur:
        cur.execute("SELECT hidden FROM user_items WHERE id = %s", (ui_id,))
        assert cur.fetchone()[0] is True


def test_hide_endpoint_is_idempotent(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source, hidden)
               VALUES (%s, %s, TRUE, 'detected', TRUE) RETURNING id""",
            (uid, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["hidden"] is True


def test_hide_endpoint_rejects_other_users(client, db, sample_tool):
    owner = f"user-{uuid.uuid4().hex[:8]}"
    intruder = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source)
               VALUES (%s, %s, TRUE, 'detected') RETURNING id""",
            (owner, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": intruder})
    assert r.status_code == 404, "Other users must not be able to hide rows on someone else's shelf"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_agent_scan_endpoint.py::test_hide_endpoint_marks_row_hidden -v`
Expected: FAIL — 404 (no such endpoint).

> **Path collision warning:** the existing `shelf_mark_installed` is registered at `/api/me/items/<int:tool_id>/install` keyed on `tool_id`. The new hide endpoint is keyed on `user_items.id`, not `tool_id`. Use `<int:item_id>` and look up by `id`.

- [ ] **Step 3: Add the endpoint**

Insert in `api/server.py` near `shelf_mark_installed`:

```python
@app.route("/api/me/items/<int:item_id>/hide", methods=["POST"])
def shelf_hide_item(item_id: int):
    """Hide a shelf row from My Forge. Idempotent. Scoped to the calling user."""
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            UPDATE user_items
            SET hidden = TRUE
            WHERE id = %s
              AND (user_id = %s OR (%s IS NOT NULL AND user_email = %s))
            RETURNING id
            """,
            (item_id, uid, email, email),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"hidden": True, "item_id": item_id})
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_agent_scan_endpoint.py -v -k hide`
Expected: PASS — all three hide tests.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_agent_scan_endpoint.py
git commit -m "feat(api): POST /api/me/items/<id>/hide for dismissing shelf tiles"
```

---

### Task 11: Backend — Extend `GET /api/me/items` to Surface Detected + Unknown

**Files:**
- Modify: `api/server.py` (`shelf_list` at line ~885)
- Test: `tests/test_agent_scan_endpoint.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_scan_endpoint.py`:

```python
def test_shelf_list_returns_detected_unknowns(client, db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                       source, installed_locally)
               VALUES (%s, NULL, 'com.unknown.app', 'UnknownApp', 'detected', TRUE)""",
            (uid,),
        )
    r = client.get(f"/api/me/items?user_id={uid}")
    assert r.status_code == 200
    items = r.get_json()["items"]
    unknown = [i for i in items if i.get("detected_bundle_id") == "com.unknown.app"]
    assert len(unknown) == 1
    assert unknown[0]["name"] == "UnknownApp"
    assert unknown[0]["source"] == "detected"
    assert unknown[0]["tool_id"] is None
    assert unknown[0]["installed_locally"] is True


def test_shelf_list_excludes_hidden(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source, hidden)
               VALUES (%s, %s, TRUE, 'detected', TRUE)""",
            (uid, sample_tool["id"]),
        )
    r = client.get(f"/api/me/items?user_id={uid}")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert all(i.get("tool_id") != sample_tool["id"] for i in items), \
        "Hidden rows must not appear on the shelf"


def test_shelf_list_excludes_uninstalled_unknowns(client, db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                       source, installed_locally)
               VALUES (%s, NULL, 'com.gone.app', 'Gone', 'detected', FALSE)""",
            (uid,),
        )
    r = client.get(f"/api/me/items?user_id={uid}")
    items = r.get_json()["items"]
    assert all(i.get("detected_bundle_id") != "com.gone.app" for i in items), \
        "Unknown rows with installed_locally=FALSE should not render"


def test_shelf_list_includes_source_field_for_matched(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source)
               VALUES (%s, %s, TRUE, 'detected')""",
            (uid, sample_tool["id"]),
        )
    r = client.get(f"/api/me/items?user_id={uid}")
    items = r.get_json()["items"]
    matched = [i for i in items if i.get("tool_id") == sample_tool["id"]]
    assert len(matched) == 1
    assert matched[0]["source"] == "detected"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_agent_scan_endpoint.py -v -k shelf_list`
Expected: FAIL — `source` and `detected_bundle_id` not exposed.

- [ ] **Step 3: Modify `shelf_list`**

> **Semantic change:** the existing response shape returns `id` as the **catalog tool id** (`t.id`). The new shape returns `id` as the **shelf row id** (`user_items.id`) and exposes `tool_id` separately. The only consumers of `item.id` in `web/app/my-forge/page.tsx` are the `key={item.id}` prop and the fallback `item.tool_id ?? item.id` (which only runs the fallback when `tool_id` is null — i.e., unknown rows, which never trigger Launch/Remove). The new hide endpoint requires the shelf id, which is what we want. **No other consumers exist** (verified via grep across `web/`).

Replace the body of `shelf_list` (currently `api/server.py:885-918`) with:

```python
@app.route("/api/me/items", methods=["GET"])
def shelf_list():
    """Return everything on a user's shelf. Includes detected unknown apps.

    Excludes rows where:
      - hidden = TRUE
      - tool_id IS NULL AND installed_locally = FALSE  (uninstalled unknowns)
    """
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT ui.id AS shelf_id, ui.tool_id, ui.added_at, ui.installed_locally,
                   ui.installed_at, ui.installed_version, ui.last_opened_at, ui.open_count,
                   ui.source, ui.hidden, ui.detected_bundle_id, ui.detected_name,
                   t.*
            FROM user_items ui
            LEFT JOIN tools t ON t.id = ui.tool_id
            WHERE (ui.user_id = %s OR (%s IS NOT NULL AND ui.user_email = %s))
              AND ui.hidden = FALSE
              AND (
                t.id IS NOT NULL AND t.status = 'approved'
                OR (ui.tool_id IS NULL AND ui.installed_locally = TRUE)
              )
            ORDER BY ui.last_opened_at DESC NULLS LAST, ui.added_at DESC
            """,
            (uid, email, email),
        )
        rows = [dict(r) for r in cur.fetchall()]

    items = []
    for r in rows:
        if r.get("tool_id") is None:
            # Unknown app row.
            items.append({
                "id": r["shelf_id"],
                "tool_id": None,
                "slug": None,
                "name": r.get("detected_name"),
                "icon": None,
                "delivery": "external",
                "detected_bundle_id": r.get("detected_bundle_id"),
                "source": r.get("source") or "detected",
                "installed_locally": True,
                "installed_at": r.get("installed_at").isoformat() if r.get("installed_at") else None,
                "added_at": r.get("added_at").isoformat() if r.get("added_at") else None,
                "open_count": r.get("open_count") or 0,
            })
            continue
        # Catalog-matched row — preserve previous behaviour and add new fields.
        d = _jsonify_tool(r)
        d["id"] = r["shelf_id"]
        d["tool_id"] = r["tool_id"]
        d["added_at"] = r.get("added_at").isoformat() if r.get("added_at") else None
        d["installed_locally"] = r.get("installed_locally") or False
        d["installed_at"] = r.get("installed_at").isoformat() if r.get("installed_at") else None
        d["installed_version"] = r.get("installed_version")
        d["last_opened_at"] = r.get("last_opened_at").isoformat() if r.get("last_opened_at") else None
        d["open_count"] = r.get("open_count") or 0
        d["source"] = r.get("source") or "manual"
        d["detected_bundle_id"] = None
        items.append(d)
    return jsonify({"items": items, "count": len(items)})
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_agent_scan_endpoint.py -v -k shelf_list`
Expected: PASS — all four new tests.

Also re-run the whole test_agent_scan_endpoint suite to make sure nothing regressed: `pytest tests/test_agent_scan_endpoint.py -v`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_agent_scan_endpoint.py
git commit -m "feat(api): /me/items returns detected unknowns + source/hidden filters"
```

---

### Task 12: Backend — Flask Proxy `GET /api/forge-agent/scan`

**Files:**
- Modify: `api/server.py`
- Test: not strictly required (proxy is a thin pass-through and existing proxies have no unit tests); manual smoke step instead.

- [ ] **Step 1: Add the proxy endpoint**

Insert in `api/server.py` right after `proxy_running` (around line 765):

```python
@app.route("/api/forge-agent/scan", methods=["GET"])
def proxy_scan():
    """Proxy a scan trigger to the local forge-agent.

    Forwards X-Forge-User-Id / X-Forge-User-Email so the agent can attribute
    the resulting POST /api/agent/scan to the correct user.
    """
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        req = ur.Request(
            "http://localhost:4242/scan",
            headers={
                "X-Forge-Token": token,
                "X-Forge-User-Id": request.headers.get("X-Forge-User-Id", ""),
                "X-Forge-User-Email": request.headers.get("X-Forge-User-Email", ""),
            },
        )
        with ur.urlopen(req, timeout=20) as r:
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e), "matched": 0, "detected": 0, "unmarked": 0}), 502
```

- [ ] **Step 2: Smoke test manually**

With agent + Flask running:

```bash
curl -s -H "X-Forge-User-Id: $(cat ~/.forge/last-user.json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin).get("user_id",""))' 2>/dev/null || echo dev-user)" \
     http://localhost:8090/api/forge-agent/scan
```

Expected: JSON like `{"matched": N, "detected": M, "unmarked": K}`. If the agent is down, expect a 502 with an error string — that's the documented degraded behaviour.

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat(api): proxy GET /api/forge-agent/scan to local agent"
```

---

### Task 13: Bundle ID Seed File + Backfill Script

**Files:**
- Create: `db/migrations/data/bundle_ids.yaml`
- Create: `db/seed_bundle_ids.py`

- [ ] **Step 1: Create the seed file**

Create `db/migrations/data/bundle_ids.yaml`:

```yaml
# Slug → CFBundleIdentifier for catalog tools that ship as Mac .app bundles.
# Add new entries inline as new external apps are added to the catalog.
# Slugs must already exist in the `tools` table; the seed script is idempotent.
#
# To find a bundle ID for an installed app:
#   plutil -p /Applications/<Name>.app/Contents/Info.plist | grep CFBundleIdentifier
# or:
#   mdls -name kMDItemCFBundleIdentifier "/Applications/<Name>.app"

# Currently in the catalog (verified before merge):
meetily: net.zackz.meetily
# Add more here as the catalog grows. Pluely will be added in a separate one-off
# (it's not yet a catalog tool — see spec rationale).
```

> **Implementer:** verify the `meetily` slug exists in the seeded catalog and that the bundle ID is correct before merging. Run:
> `grep -r "meetily" db/seed*.py` to confirm the slug. Update or remove the entry if it's wrong.

- [ ] **Step 2: Create the script**

Create `db/seed_bundle_ids.py`:

```python
"""Idempotent backfill: read bundle_ids.yaml and UPDATE tools.app_bundle_id.

Usage:
    python -m db.seed_bundle_ids
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from api import db


def main() -> int:
    seed_path = Path(__file__).parent / "migrations" / "data" / "bundle_ids.yaml"
    if not seed_path.is_file():
        print(f"missing seed file: {seed_path}", file=sys.stderr)
        return 1
    mapping: dict[str, str] = yaml.safe_load(seed_path.read_text()) or {}

    updated = 0
    skipped = 0
    with db.get_db() as cur:
        for slug, bundle_id in mapping.items():
            cur.execute(
                "UPDATE tools SET app_bundle_id = %s WHERE slug = %s RETURNING id",
                (bundle_id, slug),
            )
            row = cur.fetchone()
            if row:
                updated += 1
            else:
                skipped += 1
                print(f"  warn: slug {slug!r} not found in tools — skipped")

    print(f"updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Add `pyyaml` to requirements if absent**

Check `requirements.txt` for `pyyaml`. If missing:

```bash
echo "pyyaml" >> requirements.txt
```

- [ ] **Step 4: Smoke test**

```bash
python -m db.seed_bundle_ids
```

Expected: prints `updated=N skipped=M` with no traceback. Re-run — same result, no errors (idempotent).

- [ ] **Step 5: Commit**

```bash
git add db/migrations/data/bundle_ids.yaml db/seed_bundle_ids.py requirements.txt
git commit -m "feat(db): bundle_ids seed file + idempotent backfill script"
```

---

### Task 14: Web — Types, API Client, Hook

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/lib/hooks.ts`

- [ ] **Step 1: Extend `UserItem` in `web/lib/types.ts`**

Locate the `UserItem` interface (line ~42) and replace with:

```typescript
export interface UserItem {
  id: number;                 // user_items.id (shelf row id)
  tool_id: number | null;     // null for unknown/detected apps
  slug?: string | null;
  name?: string;
  tagline?: string;
  icon?: string;
  delivery?: string;
  source_url?: string;
  install_command?: string;
  open_count?: number;
  added_at?: string;
  last_opened_at?: string;
  installed_locally?: boolean;
  installed_at?: string | null;
  installed_version?: string | null;
  // New for install discovery:
  source?: "manual" | "detected";
  detected_bundle_id?: string | null;
}
```

- [ ] **Step 2: Add API client functions in `web/lib/api.ts`**

Locate the existing `installItem` (line ~163) and add right after it:

```typescript
export interface ScanResult {
  matched: number;
  detected: number;
  unmarked: number;
  error?: string;
}

// Trigger a local scan via the forge-agent. Backend reconciles + returns counts.
export function scanInstalled(): Promise<ScanResult> {
  return api<ScanResult>("/forge-agent/scan");
}

// Hide a shelf row (matched or unknown). Idempotent.
export function hideItem(itemId: number): Promise<{ hidden: boolean }> {
  return api<{ hidden: boolean }>(`/me/items/${itemId}/hide`, { method: "POST" });
}
```

- [ ] **Step 3: Add `useScanInstalled` invalidation helper in `web/lib/hooks.ts`**

Locate the section using `globalMutate("/me/items")` (around line 213) and append:

```typescript
import { scanInstalled } from "@/lib/api";

// Trigger a scan; on success, invalidate /me/items so the shelf re-renders.
export async function refreshInstalled(): Promise<{ matched: number; detected: number; unmarked: number }> {
  const result = await scanInstalled();
  await globalMutate("/me/items");
  return result;
}
```

> If `scanInstalled` is already imported elsewhere in `hooks.ts`, drop the import line above to avoid duplicate-import lint errors.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: clean compile (no errors related to the new fields). Existing components that consumed `UserItem.tool_id` as `number` may now produce `null` warnings — those are caller bugs, but resolve them in Task 15.

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts web/lib/hooks.ts
git commit -m "feat(web): UserItem types + scanInstalled/hideItem API client + refresh hook"
```

---

### Task 15: Web — My Forge Page UI Updates

**Files:**
- Create: `web/components/detected-tile.tsx`
- Modify: `web/app/my-forge/page.tsx`

- [ ] **Step 1: Create the unknown-app tile**

Create `web/components/detected-tile.tsx`:

```typescript
"use client";

import { EyeOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { UserItem } from "@/lib/types";

export function DetectedTile({
  item,
  onHide,
}: {
  item: UserItem;
  onHide: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 rounded-xl border border-dashed border-border bg-card p-3 transition-colors hover:border-border-strong">
      <span className="text-2xl">📦</span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">
          {item.name || item.detected_bundle_id || "Unknown app"}
        </span>
        <span className="truncate text-xs text-text-secondary">
          Detected on your machine
        </span>
        <Badge variant="outline" className="mt-1 w-fit text-[10px]">
          Detected
        </Badge>
      </div>
      <Button
        variant="ghost"
        size="icon-xs"
        className="opacity-0 group-hover:opacity-100 hover:text-destructive"
        onClick={onHide}
        aria-label="Hide"
      >
        <EyeOff />
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Wire DetectedTile + Refresh button into `web/app/my-forge/page.tsx`**

At the top of the file, augment the existing imports:

```typescript
import { useState, useCallback, useMemo } from "react";  // (useState may already be imported)
import { RefreshCw } from "lucide-react";
import { useMyItems, useMyStars, useMySkills, useAgentAvailable, useRunningApps, uninstallApp, refreshInstalled } from "@/lib/hooks";
import { launchItem, removeStar, launchApp, hideItem } from "@/lib/api";
import { DetectedTile } from "@/components/detected-tile";
```

Inside the component, near the other `useCallback`s, add:

```typescript
const [scanning, setScanning] = useState(false);

const handleRefresh = useCallback(async () => {
  setScanning(true);
  try {
    const r = await refreshInstalled();
    toast(`Scanned: ${r.matched} matched, ${r.detected} detected, ${r.unmarked} removed`);
  } catch {
    toast.error("Scan failed — is the agent running?");
  } finally {
    setScanning(false);
  }
}, []);

const handleHide = useCallback(async (shelfId: number) => {
  try {
    await hideItem(shelfId);
    toast("Hidden");
    mutateItems();
  } catch {
    toast.error("Failed to hide");
  }
}, [mutateItems]);
```

In the **Installed tab** content (currently the `<TabsContent value="installed">` block), add the Refresh button just above the grid, and split the items render to use `DetectedTile` for unknown rows. Replace the grid block with:

```typescript
{(!items || items.length === 0) ? (
  <EmptyState
    icon={<span className="text-3xl">📦</span>}
    title="No apps installed"
    message="Browse the catalog and install your first app, or click Refresh to scan."
    actionLabel="Browse Apps"
    actionHref="/"
  />
) : (
  <>
    <div className="mb-3 flex justify-end">
      <Button variant="outline" size="sm" onClick={handleRefresh} disabled={scanning}>
        <RefreshCw data-icon="inline-start" className={scanning ? "animate-spin" : undefined} />
        {scanning ? "Scanning…" : "Refresh installed apps"}
      </Button>
    </div>
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
      {items.map((item) =>
        item.tool_id == null ? (
          <DetectedTile
            key={`detected-${item.id}`}
            item={item}
            onHide={() => handleHide(item.id)}
          />
        ) : (
          <InstalledTile
            key={item.id}
            item={item}
            isRunning={item.delivery === "external" && !!runningData?.apps.find(a => a.slug === item.slug && a.running)}
            onOpen={() => {
              if (item.delivery === "external" && item.slug) {
                handleLaunch(item.tool_id ?? item.id, item.slug, item.name || item.slug);
              } else if (item.slug) {
                openPane(item.slug, item.name || item.slug);
              }
            }}
            onRemove={() => handleRemoveItem(item.tool_id ?? item.id)}
          />
        )
      )}
    </div>
  </>
)}
```

In the existing `InstalledTile` sub-component (around line 228), add a "Detected" badge when `item.source === "detected"`. Inside the badges row (around line 259-266), add:

```typescript
{item.source === "detected" && (
  <Badge variant="outline" className="text-[10px]">
    Detected
  </Badge>
)}
```

Add a **Hide** menu entry. The simplest path: add an extra small ghost button next to the Trash that calls `handleHide(item.id)`. Inside the button row (around lines 268-292), insert before the Trash button:

```typescript
<Button
  variant="ghost"
  size="icon-xs"
  className="opacity-0 group-hover:opacity-100"
  onClick={() => handleHide(item.id)}
  aria-label="Hide"
>
  <EyeOff />
</Button>
```

And add the icon import at the top:

```typescript
import { ExternalLink, LogOut, Trash2, X, EyeOff, RefreshCw } from "lucide-react";
```

Pass `handleHide` into `InstalledTile`. Update the call site:

```typescript
<InstalledTile
  key={item.id}
  item={item}
  isRunning={...}
  onOpen={...}
  onRemove={() => handleRemoveItem(item.tool_id ?? item.id)}
  onHide={() => handleHide(item.id)}
/>
```

And the `InstalledTile` signature:

```typescript
function InstalledTile({
  item,
  isRunning,
  onOpen,
  onRemove,
  onHide,
}: {
  item: UserItem;
  isRunning?: boolean;
  onOpen: () => void;
  onRemove: () => void;
  onHide: () => void;
}) { ... }
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit
```

Expected: clean. Tracking down `tool_id: number | null` callers is the most common breakage — the existing `handleLaunch(item.tool_id ?? item.id, ...)` already uses `??`, so it's safe.

- [ ] **Step 4: Manual UI smoke**

Start agent + Flask + Next:

```bash
cd web && npm run dev   # in one shell
# in another: ensure forge_agent is running and api/server.py is on :8090
```

Open http://localhost:3000/my-forge. Click **Refresh installed apps**. Expected:

- A toast like `Scanned: N matched, M detected, K removed`.
- Pluely (or whichever apps are on the user's machine that aren't in the catalog) appears as a dashed-border tile labeled "Detected on your machine".
- Hover any tile and click the eye-off icon — the tile disappears, toast shows "Hidden".

- [ ] **Step 5: Commit**

```bash
git add web/components/detected-tile.tsx web/app/my-forge/page.tsx
git commit -m "feat(web): Refresh installed apps + Detected tiles + Hide on My Forge"
```

---

### Task 16: End-to-End Integration Test

**Files:**
- Create: `tests/agents/test_install_discovery_e2e.py`

- [ ] **Step 1: Write the test**

Create `tests/agents/test_install_discovery_e2e.py`:

```python
"""End-to-end: synthetic scan payloads round-trip through reconciler and shelf list."""
import json
import uuid


def test_full_round_trip(client, db, sample_tool):
    """A scan that includes our catalog tool by bundle id + an unknown app:
       - Both appear on /me/items
       - A second scan that drops both unmarks them; they vanish from /me/items
    """
    with db.cursor() as cur:
        cur.execute("UPDATE tools SET app_bundle_id = %s WHERE id = %s",
                    ("com.test.bundle", sample_tool["id"]))
    uid = f"user-{uuid.uuid4().hex[:8]}"

    # Scan 1: both present
    p1 = {
        "apps": [
            {"bundle_id": "com.test.bundle", "name": "Test", "path": "/Applications/Test.app"},
            {"bundle_id": "com.unknown.foo", "name": "Foo", "path": "/Applications/Foo.app"},
        ],
        "brew": [], "brew_casks": [],
    }
    r = client.post("/api/agent/scan", json=p1, headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["matched"] == 1
    assert body["detected"] == 1
    assert body["unmarked"] == 0

    shelf = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    matched = [i for i in shelf if i.get("tool_id") == sample_tool["id"]]
    unknown = [i for i in shelf if i.get("detected_bundle_id") == "com.unknown.foo"]
    assert len(matched) == 1 and matched[0]["installed_locally"] is True
    assert len(unknown) == 1 and unknown[0]["name"] == "Foo"

    # Scan 2: both removed
    p2 = {"apps": [], "brew": [], "brew_casks": []}
    r2 = client.post("/api/agent/scan", json=p2, headers={"X-Forge-User-Id": uid})
    body2 = r2.get_json()
    assert body2["unmarked"] >= 2

    shelf2 = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    # Matched tool persists (still on shelf, but installed_locally=False)
    assert any(i.get("tool_id") == sample_tool["id"] and i["installed_locally"] is False for i in shelf2)
    # Unknown app: rendered tiles filter installed_locally=False, so it disappears
    assert all(i.get("detected_bundle_id") != "com.unknown.foo" for i in shelf2)


def test_hide_then_rescan_unknown_does_not_reappear(client, db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    p = {"apps": [{"bundle_id": "com.x.y", "name": "X", "path": "/x"}],
         "brew": [], "brew_casks": []}
    client.post("/api/agent/scan", json=p, headers={"X-Forge-User-Id": uid})

    shelf = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    target = next(i for i in shelf if i.get("detected_bundle_id") == "com.x.y")

    client.post(f"/api/me/items/{target['id']}/hide", headers={"X-Forge-User-Id": uid})

    # Re-scan: hidden flag must persist
    client.post("/api/agent/scan", json=p, headers={"X-Forge-User-Id": uid})
    shelf2 = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    assert all(i.get("detected_bundle_id") != "com.x.y" for i in shelf2)
```

- [ ] **Step 2: Run all relevant tests as a regression sweep**

```bash
pytest tests/test_migration_018.py tests/test_reconcile.py tests/test_agent_scan_endpoint.py tests/agents/test_install_discovery_e2e.py tests/agents/test_scanner.py -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add tests/agents/test_install_discovery_e2e.py
git commit -m "test: e2e round trip for install discovery + hide-stickiness"
```

---

## Done Criteria

- All 16 tasks committed.
- `pytest -q` passes the new test files plus the prior suites that touched `user_items` (`tests/test_*tools*.py` if any).
- Manual QA: with the agent running, opening **My Forge** in the Next.js app and clicking **Refresh installed apps** produces a toast, surfaces unknown apps as "Detected" tiles (Pluely should appear), and hides any apps that have been deleted from `/Applications` since the last scan.
- `frontend/` (vanilla) **was not modified** — Next.js `web/` is the only frontend touched, per the retirement plan.

---

## Notes for the Implementer

- **Don't edit `frontend/`.** It is being retired (see `docs/superpowers/plans/2026-04-19-retire-vanilla-frontend.md`). Any My Tools changes must land only in `web/`.
- **Read `web/AGENTS.md` if you reach for any Next.js API beyond client components, SWR, and shadcn primitives.** This plan's UI changes don't trigger that, but the warning matters.
- **Prefer small commits.** Each task ends with a commit. Don't squash across tasks.
- **If a manual smoke step fails because the agent isn't running**, that's an environment issue — not a code defect. The test suites cover correctness without needing the agent process.
- **The `_scan_cache` is module-level on `agent.py`.** This is intentional — the agent is single-process. If it ever multi-thread workers per request, revisit.
