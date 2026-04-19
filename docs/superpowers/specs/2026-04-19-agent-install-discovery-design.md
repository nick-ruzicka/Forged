# Agent-Driven Install Discovery & Reconciliation

**Date:** 2026-04-19
**Status:** Design — pending implementation plan

## Problem

Forge tracks "installed" state only for apps the user installs *through* Forge. Apps already on the machine (e.g., Pluely.app installed manually, `raycast` installed via `brew` before Forge existed) are invisible to Forge. The user's expectation — "forge should know this" — is that the local agent discovers what's on the machine and reconciles it against the catalog, both for tools Forge knows about and for tools it doesn't.

## Goals

1. When a tool in Forge's catalog is already installed on the user's machine, the user's shelf reflects `installed_locally = TRUE` without any manual "Mark Installed" click.
2. When an app is installed on the machine but absent from the catalog, it still surfaces on the user's **My Tools** as a "detected" tile, so the user can see Forge recognizing it.
3. When the user uninstalls an app, Forge notices and updates state (matched tools un-mark; unknown tiles disappear).
4. No unreviewed machine contents leak into the public catalog or cross-user signals.

## Non-Goals (v1)

- Detecting `pip`, `pipx`, `npm -g`, `$PATH` binaries, or anything outside `/Applications` and Homebrew. Revisit if real catalog tools demand it.
- Polished icons for unknown apps. Use a generic icon. Icon extraction deferred.
- "Submit to public catalog" flow for unknown apps. A personal tile is all v1 offers.
- `fswatch` / filesystem-event-driven scanning. Explicit triggers only.
- Automation of the separate one-off of adding `Pluely` to the catalog — that's trivial data entry, tracked outside this spec.

## Architecture

The agent is *dumb*; the backend is *smart*.

```
[forge_agent]  --POST /api/agent/scan-->  [Flask API]  -->  [Postgres]
     |                                         |
     | scans:                                  | matches against:
     |   /Applications/*.app (plistlib)        |   tools.app_bundle_id
     |   `brew list` + `brew list --cask`      |   tools.install_meta.formula
     |                                         |   tools.install_meta.cask
     | triggers:                               | reconciles user_items for the
     |   - agent startup                       | authenticated user:
     |   - post-install hook                   |   - matched tools → installed
     |   - on-demand GET /scan                 |   - unknown apps → detected rows
     |                                         |   - missing apps → unmarked
```

**Why the split:** the catalog lives in Postgres, and matching rules will evolve as the catalog grows. Shipping a new agent version on every catalog change would be painful. The agent ships a raw scan payload; the backend owns all matching logic.

## Schema Changes

### `tools` table (catalog)

```sql
ALTER TABLE tools ADD COLUMN app_bundle_id TEXT;
CREATE INDEX tools_bundle_id_idx
    ON tools(app_bundle_id)
    WHERE app_bundle_id IS NOT NULL;
```

One nullable column. Most catalog entries leave it null (CLI tools with no `.app`). Populated via a hand-maintained seed file (`db/migrations/data/bundle_ids.yaml` or similar) mapping catalog slug → bundle ID for the subset of catalog tools that ship as Mac `.app`s. The migration inserts these; future catalog additions include `app_bundle_id` inline. No dynamic introspection of a reference machine.

### `user_items` table (shelf)

```sql
ALTER TABLE user_items ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
    -- 'manual'   — user added via UI or install flow
    -- 'detected' — scanner found it
ALTER TABLE user_items ADD COLUMN hidden BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user_items ADD COLUMN detected_bundle_id TEXT;
ALTER TABLE user_items ADD COLUMN detected_name TEXT;

-- Relax existing NOT NULL on tool_id to allow unknown-app rows
ALTER TABLE user_items ALTER COLUMN tool_id DROP NOT NULL;

-- Ensure one row per user per unknown app
CREATE UNIQUE INDEX user_items_detected_unique
    ON user_items(user_id, detected_bundle_id)
    WHERE tool_id IS NULL AND detected_bundle_id IS NOT NULL;
```

Unknown apps share the `user_items` table (rather than a separate `personal_tools` table) so shelf-loading code stays uniform. An unknown row has `tool_id = NULL` and is identified by `(user_id, detected_bundle_id)`.

## Agent Changes

### New module: `forge_agent/scanner.py`

Isolated from the HTTP layer so it can be unit-tested without standing up the agent.

```python
def scan() -> dict:
    return {
        "apps":       _scan_applications(),   # [{bundle_id, name, path}]
        "brew":       _brew_list(cask=False), # [str]
        "brew_casks": _brew_list(cask=True),
    }

def _scan_applications() -> list[dict]:
    # Glob /Applications for *.app up to depth 2 (covers suite bundles like
    # /Applications/Xcode.app/Contents/Applications/*).
    # Read Contents/Info.plist via plistlib.
    # Skip entries without CFBundleIdentifier.
    # Return [{"bundle_id": CFBundleIdentifier,
    #          "name": CFBundleName or basename sans .app,
    #          "path": str(path)}]

def _brew_list(cask: bool) -> list[str]:
    # subprocess.run(["brew", "list"] + (["--cask"] if cask else []),
    #                timeout=10, capture_output=True, text=True)
    # Return [] on non-zero exit or FileNotFoundError (brew not installed).
```

### New endpoint: `GET /scan` on the agent

- Runs `scanner.scan()`.
- POSTs the payload to the Flask backend's `/api/agent/scan`, passing through the user token.
- Returns the backend's response `{matched, detected, unmarked}` to the caller for UI display.
- Cached for 30 seconds: a second `/scan` call within 30s of the last successful scan returns the cached result without rescanning or re-POSTing. No other rate limiting.

### Triggers

1. **Startup.** After `forge_agent` boots and obtains its user token, fire one scan asynchronously. Failures (backend down, no brew, etc.) log and return — never crash the agent.
2. **Post-install.** At the end of the `_handle_install` success path (currently `agent.py` line ~602, just after `_register_app`), trigger a scan. Catches sidecar installs like `brew install node` pulling in `npm`.
3. **On-demand.** A "Refresh installed apps" button in the web UI hits the Flask proxy → agent `/scan`.

No periodic polling. Users who install apps entirely outside Forge and outside the post-install path can refresh manually.

## Backend Changes

### New endpoint: `POST /api/agent/scan`

```python
@app.post("/api/agent/scan")
def agent_scan():
    payload = request.get_json()
    # payload shape:
    # {apps: [{bundle_id, name, path}], brew: [str], brew_casks: [str]}
    user_id = current_user_id()

    matched_tool_ids = _reconcile_matches(user_id, payload)
    _reconcile_unknowns(user_id, payload["apps"], matched_tool_ids)
    unmarked = _reconcile_uninstalls(user_id, payload, matched_tool_ids)

    return {"matched":  len(matched_tool_ids),
            "detected": _count_active_unknowns(user_id),
            "unmarked": unmarked}
```

Auth uses the same user-token scheme as other `/api/me/*` endpoints.

### `_reconcile_matches` — three passes

Performed inside one transaction per user:

1. **Bundle ID match:**
   `SELECT id FROM tools WHERE app_bundle_id = ANY(:bundle_ids)`
2. **Brew formula match:**
   `WHERE install_meta->>'type' = 'brew' AND install_meta->>'formula' = ANY(:formulas)`
3. **Brew cask match:**
   `WHERE install_meta->>'type' = 'brew' AND install_meta->>'cask' = ANY(:casks)`

For each matched tool:

- Upsert `user_items` with `user_id, tool_id`, `installed_locally=TRUE`, `installed_at=NOW()`, `source='detected'`.
- **Never overwrite `source='manual'`** when it already has `installed_locally=TRUE`. Manual intent wins. The scan can upgrade a manual `installed_locally=FALSE` row to `TRUE`, but `source` stays `manual`.

### `_reconcile_unknowns`

Apps with a `bundle_id` that matched no catalog row:

- Upsert on `(user_id, detected_bundle_id)` where `tool_id IS NULL`.
- Set `installed_locally=TRUE`, `installed_at=NOW()`, `source='detected'`, `detected_name`.
- If `hidden=TRUE` on an existing row: leave `hidden=TRUE` alone (don't resurrect dismissed), but refresh `installed_locally` and `detected_name` so the record stays accurate if the user un-hides later.

### `_reconcile_uninstalls`

For all rows on this user's shelf with `source='detected'` and `installed_locally=TRUE`, check whether the scan still contains them:

- **Matched rows** (`tool_id IS NOT NULL`): key on `tools.app_bundle_id` or `install_meta.formula`/`install_meta.cask` — whichever matched on the way in. If absent from the current scan payload, set `installed_locally=FALSE`, `installed_at=NULL`. The shelf row persists so the user sees "you had this; click to reinstall".
- **Unknown rows** (`tool_id IS NULL`): key on `detected_bundle_id`. If absent from `payload["apps"]`, set `installed_locally=FALSE`. The frontend filters unknown tiles where `installed_locally=FALSE` so they disappear from view, matching user intuition ("I deleted it, it's gone from Forge").

`source='manual'` rows are **never** auto-unmarked. A user who manually clicked "Mark Installed" stays marked until they explicitly change it.

Return the count of rows transitioned to `installed_locally=FALSE`.

### New endpoint: `POST /api/me/items/{id}/hide`

Sets `hidden=TRUE`. Idempotent. Covers both matched and unknown rows. A user can un-hide via a "Show hidden" toggle (out of scope for v1 — hidden rows just don't render).

## Frontend Changes

Build in `web/` (Next.js) only. `frontend/` is being retired per the 2026-04-19 plan.

**My Tools page:**

- Render tiles for every `user_items` row where `hidden = FALSE`, *and* (for unknown rows) where `installed_locally = TRUE`.
- Matched tile: existing catalog rendering plus a subtle `Detected` badge when `source='detected'`.
- Unknown tile: generic icon, `detected_name`, "Detected on your machine" subtitle. No **Open** button (no launch_url). Overflow menu offers **Hide** (POST `/api/me/items/{id}/hide`).
- **Refresh installed apps** button at the top. Calls the Flask → agent proxy for `/scan`. Shows a spinner + toast with the `{matched, detected, unmarked}` counts on completion.

No changes to the public catalog view. `/api/tools` never returns unknown rows.

## Error Handling

- `brew` missing on the user's machine: scanner returns empty `brew` and `brew_casks` lists. Backend treats this as "no brew matches" and moves on. No user-visible error.
- `/Applications` unreadable (unusual): scanner logs, returns empty `apps`. Same graceful fallthrough.
- Backend unreachable from agent: agent logs and retries on next trigger. No backoff needed given triggers are sparse.
- Malformed payload at backend: reject with 400; agent logs and drops. Payload has no side effects across users, so no cleanup needed.
- Race between two scans (startup + post-install arriving near-simultaneously): per-user transaction serializes them. Idempotent upserts make order irrelevant.

## Testing

**Unit — scanner** (`tests/agents/test_scanner.py`):

- `_scan_applications` with a fake `/Applications` tree containing: a normal `.app`, a nested `.app` (depth 2), an `.app` missing `Info.plist`, and an `.app` with no `CFBundleIdentifier`. Assert only valid ones are emitted.
- `_brew_list` with `brew` missing (FileNotFoundError), non-zero exit, and normal output.

**Unit — reconciler** (`tests/test_reconcile.py`):

- Bundle-ID match sets `installed_locally=TRUE`.
- Brew formula match sets `installed_locally=TRUE`.
- Brew cask match sets `installed_locally=TRUE`.
- Unknown app creates a `tool_id=NULL` row with correct `detected_bundle_id` / `detected_name`.
- Uninstall of a matched tool flips `installed_locally=FALSE` but preserves the row.
- Uninstall of an unknown app flips `installed_locally=FALSE` (and the frontend will hide it — covered by the frontend test).
- Manual-source row with `installed_locally=TRUE` is **not** unmarked when the scan is missing that tool.
- Manual-source row with `installed_locally=FALSE` **is** upgraded to `TRUE` when the scan finds it (source stays 'manual').
- `hidden=TRUE` unknown row doesn't resurface; its `installed_locally` still tracks reality.

**End-to-end** (extend existing functional audit or add `tests/agents/test_install_discovery.py`):

- Stand up agent + API against a test DB with a seeded catalog.
- POST a synthetic scan payload; assert shelf reflects expected state.
- POST a second scan with one app removed; assert matched tool goes `installed_locally=FALSE` and unknown tile disappears from My Tools endpoint.

## Rollout

1. Migration 018: schema changes (next available — current head is 017).
2. Backfill script populates `app_bundle_id` for a starter set of catalog tools with Mac apps.
3. Ship backend endpoint with a feature flag defaulting off. Agent scanner code lands disabled.
4. Flip the flag for the author's user; manual QA on own machine (Pluely should appear as an unknown tile after a fresh scan).
5. Flip globally.

## Open Questions

None at spec time. Call out during implementation if new ambiguities surface.
