# Discovery — Plan 2 of 3: API + Frontend Surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Plan 1 data into a working user-facing `/discover` page. Ships as: user can open Forge, click Discover in the sidebar, see hero + lanes + Hidden Gems, click a repo, read the drawer, save/unsave, search. No admin tooling yet (Plan 3).

**Architecture:** Python Flask Blueprint under `api/discovery/routes.py`, registered in `server.py`. Next.js App Router page under `web/app/discover/`. SWR hooks for data fetching. Reuses existing shadcn primitives (`Sheet`, `Button`, `Input`, `Skeleton`).

**Tech Stack:** Flask Blueprints, psycopg2 RealDictCursor, Next.js 15, SWR, Tailwind, shadcn/ui, `lucide-react`, `recharts` (already in deps) for the sparkline.

**Depends on:** Plan 1 (`2026-04-20-discovery-01-backend-pipeline.md`) — requires tables populated with at least a few seeded rows for manual smoke-testing.

---

## File structure

**New backend files:**
- `api/discovery/routes.py` — Flask Blueprint `discovery_bp` mounted at `/api/discover`
- `tests/discovery/test_routes.py`

**New frontend files:**
- `web/app/discover/page.tsx`
- `web/app/discover/r/[slug]/page.tsx`
- `web/app/discover/saved/page.tsx`
- `web/components/repo-card.tsx`
- `web/components/discover-lane.tsx`
- `web/components/discover-hero.tsx`
- `web/components/hidden-gems-lane.tsx`
- `web/components/discover-search.tsx`
- `web/components/repo-detail-view.tsx`
- `web/components/repo-detail-drawer.tsx`
- `web/components/stars-sparkline.tsx`

**Modified backend files:**
- `api/server.py` — register the blueprint

**Modified frontend files:**
- `web/lib/types.ts` — add `DiscoveryRepo`, `DiscoveryLane`, `DiscoveryLanesResponse`, `DiscoveryRepoDetail`
- `web/lib/api.ts` — add `getDiscoveryLanes`, `getDiscoveryRepo`, `searchDiscovery`, `listDiscoverySaves`, `saveDiscoveryRepo`, `unsaveDiscoveryRepo`
- `web/lib/hooks.ts` — add `useDiscoveryLanes`, `useDiscoveryRepo`, `useDiscoverySearch`, `useDiscoverySaves`
- `web/components/sidebar.tsx` — add "Discover" nav item
- `web/app/my-forge/page.tsx` — add "Saved from Discover" section (path verified at implementation time if different)

---

## Task 1: API route — `GET /api/discover/lanes`

**Files:**
- Create: `api/discovery/routes.py`
- Create: `tests/discovery/test_routes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/discovery/test_routes.py
import json


class TestLanesEndpoint:
    def test_returns_hero_and_lanes_grouped(self, client, db):
        from api import db as dbmod
        import json as _j
        # Seed: 2 repos, 1 hero lane, 1 theme lane, 1 hidden_gems lane
        with dbmod.get_db() as cur:
            cur.execute(
                """INSERT INTO discovery_repos (owner, name, full_name, stars, classification,
                   topics, exa_explainer) VALUES
                   ('a','r1','a/r1',100,'app',%s,'E1'),
                   ('b','r2','b/r2',50,'hybrid',%s,'E2')
                   RETURNING id""",
                (_j.dumps(["agents"]), _j.dumps(["rag"])),
            )
            ids = [r["id"] for r in cur.fetchall()]
            cur.execute(
                "INSERT INTO discovery_lanes (slug,title,blurb,kind,repo_ids,position) "
                "VALUES ('hero','Editor''s pick','Hero blurb','hero',%s,0),"
                "       ('agent-stack','Agents','A blurb','theme',%s,1),"
                "       ('hidden-gems','Hidden gems','Gem blurb','hidden_gems',%s,999)",
                ([ids[0]], ids, [ids[1]]),
            )

        resp = client.get("/api/discover/lanes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hero"]["slug"] == "hero"
        assert len(data["hero"]["repos"]) == 1
        assert data["hero"]["repos"][0]["full_name"] == "a/r1"

        lane_slugs = [l["slug"] for l in data["lanes"]]
        assert "agent-stack" in lane_slugs
        assert "hidden-gems" in lane_slugs  # always last
        assert lane_slugs[-1] == "hidden-gems"

    def test_empty_when_no_lanes(self, client, db):
        resp = client.get("/api/discover/lanes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hero"] is None
        assert data["lanes"] == []
```

- [ ] **Step 2: Run — expect failure (404 or ImportError)**

Run: `pytest tests/discovery/test_routes.py::TestLanesEndpoint -v`
Expected: fails (blueprint not registered).

- [ ] **Step 3: Create `routes.py` with lanes endpoint**

```python
# api/discovery/routes.py
"""Flask blueprint for the Discover page API.

Register in api/server.py with:
    from api.discovery.routes import discovery_bp
    app.register_blueprint(discovery_bp)
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from api import db as dbmod

log = logging.getLogger("forge.discovery.routes")

discovery_bp = Blueprint("discovery", __name__, url_prefix="/api/discover")


def _repo_row_to_dict(row: dict) -> dict:
    """Normalize a discovery_repos row for JSON output."""
    return {
        "id": row["id"],
        "owner": row["owner"],
        "name": row["name"],
        "full_name": row["full_name"],
        "stars": row["stars"],
        "language": row.get("language"),
        "license": row.get("license"),
        "description": row.get("description"),
        "exa_explainer": row.get("exa_explainer"),
        "classification": row.get("classification"),
        "topics": row.get("topics") or [],
        "install_hint": row.get("install_hint"),
    }


def _get_user_id() -> str | None:
    return request.headers.get("X-Forge-User-Id") or request.args.get("user_id")


@discovery_bp.route("/lanes", methods=["GET"])
def get_lanes():
    """Return hero + theme lanes + hidden_gems (in that display order), with embedded repo data."""
    with dbmod.get_db() as cur:
        cur.execute(
            """SELECT id, slug, title, blurb, kind, repo_ids, position, generated_at
               FROM discovery_lanes
               ORDER BY
                 CASE kind WHEN 'hero' THEN 0 WHEN 'theme' THEN 1 WHEN 'hidden_gems' THEN 2 END,
                 position ASC"""
        )
        lane_rows = cur.fetchall()

        all_ids = set()
        for lr in lane_rows:
            all_ids.update(lr["repo_ids"] or [])
        if not all_ids:
            repos_by_id: dict[int, dict] = {}
        else:
            cur.execute(
                "SELECT * FROM discovery_repos WHERE id = ANY(%s) AND archived_at IS NULL",
                (list(all_ids),),
            )
            repos_by_id = {r["id"]: _repo_row_to_dict(r) for r in cur.fetchall()}

    hero = None
    lanes = []
    for lr in lane_rows:
        repos = [repos_by_id[rid] for rid in (lr["repo_ids"] or []) if rid in repos_by_id]
        payload = {
            "slug": lr["slug"],
            "title": lr["title"],
            "blurb": lr["blurb"],
            "kind": lr["kind"],
            "repos": repos,
            "generated_at": lr["generated_at"].isoformat() if lr["generated_at"] else None,
        }
        if lr["kind"] == "hero":
            hero = payload
        else:
            lanes.append(payload)

    return jsonify({"hero": hero, "lanes": lanes})
```

- [ ] **Step 4: Register blueprint**

Open `api/server.py`, find the Blueprint registration block (near line 2245). Add:

```python
try:
    from api.discovery.routes import discovery_bp  # type: ignore
    app.register_blueprint(discovery_bp)
except Exception as e:
    print(f"[server] discovery blueprint failed: {e}")
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/discovery/test_routes.py::TestLanesEndpoint -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add api/discovery/routes.py api/server.py tests/discovery/test_routes.py
git commit -m "feat(discovery): GET /api/discover/lanes endpoint"
```

---

## Task 2: API route — `GET /api/discover/repo/<path:full_name>`

**Files:**
- Modify: `api/discovery/routes.py` (append)
- Modify: `tests/discovery/test_routes.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestRepoDetailEndpoint:
    def test_returns_repo_with_stars_series_and_saved_flag(self, client, db):
        from api import db as dbmod
        from datetime import date, timedelta
        import json as _j

        with dbmod.get_db() as cur:
            cur.execute(
                """INSERT INTO discovery_repos (owner,name,full_name,stars,classification,
                   topics,exa_explainer,description) VALUES
                   ('x','y','x/y',250,'app',%s,'Explainer','desc') RETURNING id""",
                (_j.dumps(["agents", "rag"]),),
            )
            rid = cur.fetchone()["id"]
            # 3 days of star history
            for i, d in enumerate([date.today() - timedelta(days=2),
                                    date.today() - timedelta(days=1),
                                    date.today()]):
                cur.execute("INSERT INTO discovery_repo_stars (repo_id,date,stars) VALUES (%s,%s,%s)",
                            (rid, d, 200 + i * 25))
            cur.execute("INSERT INTO user_discovery_saves (user_id, repo_id) VALUES (%s, %s)",
                        ("user-123", rid))

        # As the saving user
        resp = client.get("/api/discover/repo/x/y", headers={"X-Forge-User-Id": "user-123"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["repo"]["full_name"] == "x/y"
        assert data["repo"]["topics"] == ["agents", "rag"]
        assert len(data["stars_series"]) == 3
        assert data["saved"] is True

        # As a different user
        resp2 = client.get("/api/discover/repo/x/y", headers={"X-Forge-User-Id": "other"})
        assert resp2.get_json()["saved"] is False

    def test_returns_404_for_unknown_repo(self, client, db):
        resp = client.get("/api/discover/repo/does/not-exist")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_routes.py::TestRepoDetailEndpoint -v`
Expected: 404 on both tests (route missing).

- [ ] **Step 3: Append endpoint**

Append to `api/discovery/routes.py`:

```python
@discovery_bp.route("/repo/<path:full_name>", methods=["GET"])
def get_repo_detail(full_name: str):
    """Return single repo detail + 90-day stars series + saved-by-me flag."""
    uid = _get_user_id()
    with dbmod.get_db() as cur:
        cur.execute("SELECT * FROM discovery_repos WHERE full_name = %s AND archived_at IS NULL",
                    (full_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not_found"}), 404

        cur.execute(
            """SELECT date, stars FROM discovery_repo_stars
               WHERE repo_id = %s ORDER BY date ASC""",
            (row["id"],),
        )
        stars_rows = cur.fetchall()

        saved = False
        if uid:
            cur.execute(
                "SELECT 1 FROM user_discovery_saves WHERE user_id = %s AND repo_id = %s",
                (uid, row["id"]),
            )
            saved = cur.fetchone() is not None

    return jsonify({
        "repo": _repo_row_to_dict(row),
        "stars_series": [
            {"date": s["date"].isoformat(), "stars": s["stars"]} for s in stars_rows
        ],
        "saved": saved,
    })
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/discovery/test_routes.py::TestRepoDetailEndpoint -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/routes.py tests/discovery/test_routes.py
git commit -m "feat(discovery): GET /api/discover/repo/<full_name> endpoint"
```

---

## Task 3: API route — `GET /api/discover/search?q=`

**Files:**
- Modify: `api/discovery/routes.py` (append)
- Modify: `tests/discovery/test_routes.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestSearchEndpoint:
    def test_returns_results_matching_query(self, client, db, monkeypatch):
        from api import db as dbmod
        import json as _j
        with dbmod.get_db() as cur:
            cur.execute(
                """INSERT INTO discovery_repos (owner,name,full_name,stars,classification,topics,exa_explainer)
                   VALUES ('o','hit','o/hit',100,'app',%s,'match'),
                          ('o','miss','o/miss',100,'app',%s,'no') RETURNING id""",
                (_j.dumps(["agents"]), _j.dumps(["agents"])),
            )

        # EXA returns the "hit" full_name
        def fake_search(q, num_results=20):
            return [{"full_name": "o/hit", "owner": "o", "name": "hit", "stars": 0,
                     "language": None, "license": None, "default_branch": None, "description": ""}]
        monkeypatch.setattr("api.discovery.routes._search_impl", fake_search)

        resp = client.get("/api/discover/search?q=agent+framework")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["results"]) == 1
        assert data["results"][0]["full_name"] == "o/hit"

    def test_empty_query_returns_empty(self, client, db):
        resp = client.get("/api/discover/search?q=")
        assert resp.status_code == 200
        assert resp.get_json()["results"] == []
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_routes.py::TestSearchEndpoint -v`
Expected: fail.

- [ ] **Step 3: Append endpoint**

```python
def _search_impl(query: str, num_results: int = 20) -> list[dict]:
    """Extracted for easy mocking in tests. Uses ExaClient against the discovery corpus."""
    from api.discovery.clients import ExaClient
    exa = ExaClient()
    return exa.semantic_search(query, num_results=num_results)


@discovery_bp.route("/search", methods=["GET"])
def search():
    """EXA semantic search that returns only repos also present in discovery_repos."""
    query = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 20)
    limit = max(1, min(50, limit))
    if not query:
        return jsonify({"results": []})

    try:
        exa_hits = _search_impl(query, num_results=limit)
    except Exception as e:
        log.warning("search failed: %s", e)
        return jsonify({"results": [], "error": "search_unavailable"}), 200

    full_names = [h["full_name"] for h in exa_hits if h.get("full_name")]
    if not full_names:
        return jsonify({"results": []})

    with dbmod.get_db() as cur:
        cur.execute(
            "SELECT * FROM discovery_repos WHERE full_name = ANY(%s) AND archived_at IS NULL",
            (full_names,),
        )
        by_name = {r["full_name"]: _repo_row_to_dict(r) for r in cur.fetchall()}

    ordered = [by_name[fn] for fn in full_names if fn in by_name]
    return jsonify({"results": ordered})
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/discovery/test_routes.py::TestSearchEndpoint -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/routes.py tests/discovery/test_routes.py
git commit -m "feat(discovery): GET /api/discover/search endpoint"
```

---

## Task 4: API routes — saves (GET/POST/DELETE)

**Files:**
- Modify: `api/discovery/routes.py` (append)
- Modify: `tests/discovery/test_routes.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestSavesEndpoints:
    def test_post_creates_save(self, client, db):
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute("INSERT INTO discovery_repos (owner,name,full_name,stars) "
                        "VALUES ('s','r','s/r',1) RETURNING id")
            rid = cur.fetchone()["id"]
        resp = client.post(
            "/api/discover/saves",
            json={"full_name": "s/r"},
            headers={"X-Forge-User-Id": "u1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["saved"] is True

        with dbmod.get_db() as cur:
            cur.execute("SELECT 1 FROM user_discovery_saves WHERE user_id='u1' AND repo_id=%s", (rid,))
            assert cur.fetchone()

    def test_post_is_idempotent(self, client, db):
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute("INSERT INTO discovery_repos (owner,name,full_name,stars) "
                        "VALUES ('s','r','s/r',1)")
        client.post("/api/discover/saves", json={"full_name": "s/r"}, headers={"X-Forge-User-Id": "u1"})
        resp = client.post("/api/discover/saves", json={"full_name": "s/r"}, headers={"X-Forge-User-Id": "u1"})
        assert resp.status_code == 200

    def test_delete_removes_save(self, client, db):
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute("INSERT INTO discovery_repos (owner,name,full_name,stars) "
                        "VALUES ('s','r','s/r',1) RETURNING id")
            rid = cur.fetchone()["id"]
            cur.execute("INSERT INTO user_discovery_saves (user_id, repo_id) VALUES ('u1', %s)", (rid,))
        resp = client.delete(
            "/api/discover/saves",
            json={"full_name": "s/r"},
            headers={"X-Forge-User-Id": "u1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["saved"] is False

    def test_get_lists_user_saves_newest_first(self, client, db):
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute("INSERT INTO discovery_repos (owner,name,full_name,stars) "
                        "VALUES ('a','1','a/1',1),('b','2','b/2',1) RETURNING id")
            rows = cur.fetchall()
            cur.execute("INSERT INTO user_discovery_saves (user_id,repo_id,saved_at) "
                        "VALUES ('u1', %s, NOW() - INTERVAL '1 hour'),"
                        "       ('u1', %s, NOW())",
                        (rows[0]["id"], rows[1]["id"]))
        resp = client.get("/api/discover/saves", headers={"X-Forge-User-Id": "u1"})
        data = resp.get_json()
        assert len(data["repos"]) == 2
        assert data["repos"][0]["full_name"] == "b/2"  # newest first

    def test_requires_user_id(self, client, db):
        resp = client.post("/api/discover/saves", json={"full_name": "x/y"})
        assert resp.status_code == 400
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_routes.py::TestSavesEndpoints -v`
Expected: fail.

- [ ] **Step 3: Append endpoints**

```python
@discovery_bp.route("/saves", methods=["POST"])
def save_repo():
    uid = _get_user_id()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"error": "full_name_required"}), 400

    with dbmod.get_db() as cur:
        cur.execute("SELECT id FROM discovery_repos WHERE full_name = %s AND archived_at IS NULL",
                    (full_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "repo_not_found"}), 404
        cur.execute(
            "INSERT INTO user_discovery_saves (user_id, repo_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (uid, row["id"]),
        )
    return jsonify({"saved": True, "full_name": full_name})


@discovery_bp.route("/saves", methods=["DELETE"])
def unsave_repo():
    uid = _get_user_id()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"error": "full_name_required"}), 400
    with dbmod.get_db() as cur:
        cur.execute(
            "DELETE FROM user_discovery_saves USING discovery_repos "
            "WHERE user_discovery_saves.repo_id = discovery_repos.id "
            "  AND discovery_repos.full_name = %s AND user_discovery_saves.user_id = %s",
            (full_name, uid),
        )
    return jsonify({"saved": False, "full_name": full_name})


@discovery_bp.route("/saves", methods=["GET"])
def list_saves():
    uid = _get_user_id()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with dbmod.get_db() as cur:
        cur.execute(
            """SELECT dr.*, uds.saved_at
               FROM user_discovery_saves uds
               JOIN discovery_repos dr ON dr.id = uds.repo_id
               WHERE uds.user_id = %s AND dr.archived_at IS NULL
               ORDER BY uds.saved_at DESC""",
            (uid,),
        )
        rows = cur.fetchall()
    return jsonify({
        "repos": [{**_repo_row_to_dict(r), "saved_at": r["saved_at"].isoformat()} for r in rows]
    })
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/discovery/test_routes.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/routes.py tests/discovery/test_routes.py
git commit -m "feat(discovery): saves endpoints (GET/POST/DELETE)"
```

---

## Task 5: Frontend types + api client

**Files:**
- Modify: `web/lib/types.ts` (append)
- Modify: `web/lib/api.ts` (append)

- [ ] **Step 1: Append types**

Open `web/lib/types.ts` and append:

```typescript
// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export interface DiscoveryRepo {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  stars: number;
  language: string | null;
  license: string | null;
  description: string | null;
  exa_explainer: string | null;
  classification: "app" | "library" | "hybrid" | null;
  topics: string[];
  install_hint: string | null;
  saved_at?: string;  // present on GET /saves
}

export interface DiscoveryLane {
  slug: string;
  title: string;
  blurb: string | null;
  kind: "hero" | "theme" | "hidden_gems";
  repos: DiscoveryRepo[];
  generated_at: string | null;
}

export interface DiscoveryLanesResponse {
  hero: DiscoveryLane | null;
  lanes: DiscoveryLane[];
}

export interface StarPoint {
  date: string;
  stars: number;
}

export interface DiscoveryRepoDetail {
  repo: DiscoveryRepo;
  stars_series: StarPoint[];
  saved: boolean;
}

export interface DiscoverySearchResponse {
  results: DiscoveryRepo[];
  error?: string;
}
```

- [ ] **Step 2: Append api client functions**

Open `web/lib/api.ts` and append:

```typescript
// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------
import type {
  DiscoveryLanesResponse,
  DiscoveryRepoDetail,
  DiscoverySearchResponse,
  DiscoveryRepo,
} from "./types";

export function getDiscoveryLanes() {
  return api<DiscoveryLanesResponse>("/discover/lanes");
}

export function getDiscoveryRepo(fullName: string) {
  return api<DiscoveryRepoDetail>(`/discover/repo/${fullName}`);
}

export function searchDiscovery(q: string, limit = 20) {
  return api<DiscoverySearchResponse>("/discover/search", {
    params: { q, limit: String(limit) },
  });
}

export function listDiscoverySaves() {
  return api<{ repos: DiscoveryRepo[] }>("/discover/saves");
}

export function saveDiscoveryRepo(fullName: string) {
  return api<{ saved: boolean; full_name: string }>("/discover/saves", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName }),
  });
}

export function unsaveDiscoveryRepo(fullName: string) {
  return api<{ saved: boolean; full_name: string }>("/discover/saves", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName }),
  });
}
```

Adjust the existing `import type {...}` block at the top of `api.ts` to include the new types if imports are consolidated; otherwise the local import above works.

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no new type errors.

- [ ] **Step 4: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat(discovery): frontend types + api client"
```

---

## Task 6: Frontend hooks

**Files:**
- Modify: `web/lib/hooks.ts` (append)

- [ ] **Step 1: Append hooks**

Open `web/lib/hooks.ts` and append at the bottom:

```typescript
// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------
import {
  getDiscoveryLanes,
  getDiscoveryRepo,
  searchDiscovery,
  listDiscoverySaves,
} from "./api";
import type {
  DiscoveryLanesResponse,
  DiscoveryRepoDetail,
  DiscoverySearchResponse,
  DiscoveryRepo,
} from "./types";

export function useDiscoveryLanes() {
  return useSWR<DiscoveryLanesResponse>("/discover/lanes", getDiscoveryLanes);
}

export function useDiscoveryRepo(fullName: string | undefined) {
  return useSWR<DiscoveryRepoDetail>(
    fullName ? ["/discover/repo", fullName] : null,
    () => getDiscoveryRepo(fullName!),
  );
}

export function useDiscoverySearch(query: string) {
  const trimmed = query.trim();
  return useSWR<DiscoverySearchResponse>(
    trimmed ? ["/discover/search", trimmed] : null,
    () => searchDiscovery(trimmed),
  );
}

export function useDiscoverySaves() {
  return useSWR<{ repos: DiscoveryRepo[] }>("/discover/saves", listDiscoverySaves);
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add web/lib/hooks.ts
git commit -m "feat(discovery): SWR hooks for lanes/repo/search/saves"
```

---

## Task 7: `RepoCard` component

**Files:**
- Create: `web/components/repo-card.tsx`

- [ ] **Step 1: Write the component**

```tsx
// web/components/repo-card.tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import { Heart, ExternalLink } from "lucide-react";
import { mutate } from "swr";
import { cn } from "@/lib/utils";
import { saveDiscoveryRepo, unsaveDiscoveryRepo } from "@/lib/api";
import type { DiscoveryRepo } from "@/lib/types";

interface RepoCardProps {
  repo: DiscoveryRepo;
  saved?: boolean;
  compact?: boolean;
}

export function RepoCard({ repo, saved = false, compact = false }: RepoCardProps) {
  const [localSaved, setLocalSaved] = useState(saved);
  const [pending, setPending] = useState(false);

  const classDot = {
    app: "bg-[#5B9FFF]",
    library: "bg-white/30",
    hybrid: "bg-gradient-to-br from-[#5B9FFF] to-white/30",
  }[repo.classification ?? "library"];

  async function toggleSave(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (pending) return;
    setPending(true);
    const next = !localSaved;
    setLocalSaved(next);  // optimistic
    try {
      if (next) await saveDiscoveryRepo(repo.full_name);
      else await unsaveDiscoveryRepo(repo.full_name);
      mutate("/discover/saves");
    } catch {
      setLocalSaved(!next);  // rollback
    } finally {
      setPending(false);
    }
  }

  const href = `/discover/r/${encodeURIComponent(repo.full_name)}`;

  return (
    <Link
      href={href}
      className={cn(
        "group relative flex flex-col gap-1.5 rounded-xl border border-border bg-card p-4 transition-colors duration-150 hover:border-border-strong hover:bg-white/[0.02]",
        compact ? "min-w-[260px] max-w-[320px]" : "",
      )}
    >
      {/* Header: owner/name + save */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className={cn("size-1.5 shrink-0 rounded-full", classDot)}
                  title={repo.classification ?? "unknown"} />
            <span className="truncate text-[13px] font-semibold text-white/90">
              {repo.full_name}
            </span>
          </div>
        </div>
        <button
          onClick={toggleSave}
          aria-label={localSaved ? "Unsave" : "Save"}
          className={cn(
            "shrink-0 rounded p-1 transition-colors",
            localSaved ? "text-[#ff6b9d]" : "text-white/40 hover:text-white/70",
          )}
        >
          <Heart className="size-3.5" fill={localSaved ? "currentColor" : "none"} />
        </button>
      </div>

      {/* Description */}
      {repo.description && (
        <p className="line-clamp-2 text-[11px] leading-snug text-white/55">
          {repo.description}
        </p>
      )}

      {/* Footer: stars + language + license */}
      <div className="mt-auto flex items-center gap-2 pt-1 text-[10px] text-white/40">
        <span className="tabular-nums">{formatStars(repo.stars)}★</span>
        {repo.language && <span>· {repo.language}</span>}
        {repo.license && <span>· {repo.license}</span>}
      </div>
    </Link>
  );
}

function formatStars(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/components/repo-card.tsx
git commit -m "feat(discovery): RepoCard component"
```

---

## Task 8: Lane components — `DiscoverLane`, `DiscoverHero`, `HiddenGemsLane`

**Files:**
- Create: `web/components/discover-lane.tsx`
- Create: `web/components/discover-hero.tsx`
- Create: `web/components/hidden-gems-lane.tsx`

- [ ] **Step 1: `DiscoverLane`**

```tsx
// web/components/discover-lane.tsx
"use client";

import { RepoCard } from "@/components/repo-card";
import type { DiscoveryLane as Lane, DiscoveryRepo } from "@/lib/types";

interface Props {
  lane: Lane;
  savedIds?: Set<number>;
}

export function DiscoverLane({ lane, savedIds }: Props) {
  if (!lane.repos.length) return null;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/40">
          {lane.title}
        </span>
        {lane.blurb && (
          <p className="text-[12px] text-white/50">{lane.blurb}</p>
        )}
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x snap-mandatory">
        {lane.repos.map((r) => (
          <div key={r.id} className="snap-start">
            <RepoCard repo={r} saved={savedIds?.has(r.id) ?? false} compact />
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: `DiscoverHero`**

```tsx
// web/components/discover-hero.tsx
"use client";

import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import type { DiscoveryLane } from "@/lib/types";

interface Props {
  hero: DiscoveryLane | null;
}

export function DiscoverHero({ hero }: Props) {
  if (!hero || hero.repos.length === 0) return null;
  const repo = hero.repos[0];
  const href = `/discover/r/${encodeURIComponent(repo.full_name)}`;
  return (
    <Link
      href={href}
      className="group relative block overflow-hidden rounded-2xl border border-[rgba(91,159,255,0.15)] p-7"
      style={{ background: "linear-gradient(135deg, rgba(91,159,255,0.06), transparent 60%)" }}
    >
      <div className="flex items-start gap-5">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-[rgba(91,159,255,0.15)] text-[#5B9FFF]">
          <Sparkles className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#5B9FFF]/80">
            Editor&rsquo;s pick
          </div>
          <h2 className="mt-1 font-serif text-2xl font-normal tracking-tight text-white/95">
            {repo.full_name}
          </h2>
          {hero.blurb && (
            <p className="mt-2 text-sm leading-relaxed text-white/65">{hero.blurb}</p>
          )}
          <div className="mt-3 flex items-center gap-3 text-[11px] text-white/45">
            <span className="tabular-nums">{repo.stars.toLocaleString()}★</span>
            {repo.language && <span>· {repo.language}</span>}
          </div>
        </div>
        <ArrowRight className="mt-2 size-4 shrink-0 text-white/30 transition-transform group-hover:translate-x-1" />
      </div>
    </Link>
  );
}
```

- [ ] **Step 3: `HiddenGemsLane`**

```tsx
// web/components/hidden-gems-lane.tsx
"use client";

import { Gem } from "lucide-react";
import { DiscoverLane } from "@/components/discover-lane";
import type { DiscoveryLane as Lane } from "@/lib/types";

interface Props {
  lane: Lane | undefined;
  savedIds?: Set<number>;
}

export function HiddenGemsLane({ lane, savedIds }: Props) {
  if (!lane || lane.repos.length === 0) return null;
  return (
    <section className="rounded-2xl border border-white/[0.04] bg-gradient-to-b from-[#1a1626]/60 to-transparent p-5">
      <div className="mb-4 flex items-center gap-2">
        <Gem className="size-3.5 text-[#b988ff]" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#b988ff]/80">
          Hidden gems
        </span>
      </div>
      <DiscoverLane lane={{ ...lane, title: lane.blurb ?? "", blurb: null }} savedIds={savedIds} />
    </section>
  );
}
```

- [ ] **Step 4: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/components/discover-lane.tsx web/components/discover-hero.tsx web/components/hidden-gems-lane.tsx
git commit -m "feat(discovery): lane + hero + hidden-gems components"
```

---

## Task 9: `DiscoverSearch`

**Files:**
- Create: `web/components/discover-search.tsx`

- [ ] **Step 1: Write component**

```tsx
// web/components/discover-search.tsx
"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { useDiscoverySearch } from "@/lib/hooks";

interface Props {
  onQueryChange?: (q: string) => void;
}

export function DiscoverSearch({ onQueryChange }: Props) {
  const [raw, setRaw] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(raw), 300);
    return () => clearTimeout(t);
  }, [raw]);

  useEffect(() => {
    onQueryChange?.(debounced);
  }, [debounced, onQueryChange]);

  return (
    <div className="relative max-w-xl">
      <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-white/35" />
      <input
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder="Search repos (semantic)…"
        className="h-8 w-full rounded-lg border border-white/[0.06] bg-white/[0.03] pl-8 pr-8 text-[12px] text-white/85 placeholder:text-white/35 outline-none focus:border-[rgba(91,159,255,0.25)] focus:bg-white/[0.04]"
      />
      {raw && (
        <button
          onClick={() => setRaw("")}
          aria-label="Clear"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-white/35 hover:text-white/70"
        >
          <X className="size-3" />
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/components/discover-search.tsx
git commit -m "feat(discovery): DiscoverSearch input"
```

---

## Task 10: `StarsSparkline` + `RepoDetailView`

**Files:**
- Create: `web/components/stars-sparkline.tsx`
- Create: `web/components/repo-detail-view.tsx`

- [ ] **Step 1: `StarsSparkline`**

```tsx
// web/components/stars-sparkline.tsx
"use client";

import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import type { StarPoint } from "@/lib/types";

interface Props {
  series: StarPoint[];
  height?: number;
}

export function StarsSparkline({ series, height = 60 }: Props) {
  if (!series || series.length < 2) return null;
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <LineChart data={series}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="stars"
            stroke="#5B9FFF"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: `RepoDetailView`**

```tsx
// web/components/repo-detail-view.tsx
"use client";

import { useState } from "react";
import { Heart, ExternalLink, Lock } from "lucide-react";
import { mutate } from "swr";
import { Button } from "@/components/ui/button";
import { StarsSparkline } from "@/components/stars-sparkline";
import { saveDiscoveryRepo, unsaveDiscoveryRepo } from "@/lib/api";
import { useDiscoveryRepo } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface Props {
  fullName: string;
  onClose?: () => void;
}

export function RepoDetailView({ fullName }: Props) {
  const { data, isLoading, error } = useDiscoveryRepo(fullName);
  const [savedLocal, setSavedLocal] = useState<boolean | null>(null);

  if (isLoading) {
    return <div className="p-6 text-sm text-white/50">Loading…</div>;
  }
  if (error || !data) {
    return <div className="p-6 text-sm text-white/50">Not found.</div>;
  }

  const { repo, stars_series, saved } = data;
  const isSaved = savedLocal ?? saved;

  async function toggleSave() {
    const next = !isSaved;
    setSavedLocal(next);
    try {
      if (next) await saveDiscoveryRepo(fullName);
      else await unsaveDiscoveryRepo(fullName);
      mutate(["/discover/repo", fullName]);
      mutate("/discover/saves");
    } catch {
      setSavedLocal(!next);
    }
  }

  const installAvailable = repo.classification === "app" || repo.classification === "hybrid";

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-xl font-bold tracking-tight text-white/95">
            {repo.full_name}
          </h2>
          <div className="mt-1 flex items-center gap-2 text-[11px] text-white/50">
            <span className="tabular-nums">{repo.stars.toLocaleString()}★</span>
            {repo.language && <span>· {repo.language}</span>}
            {repo.license && <span>· {repo.license}</span>}
            {repo.classification && (
              <span className="rounded bg-white/[0.05] px-1.5 py-0.5 uppercase">{repo.classification}</span>
            )}
          </div>
        </div>
      </div>

      {/* Explainer */}
      {repo.exa_explainer && (
        <p className="text-[13px] leading-relaxed text-white/70 italic">
          {repo.exa_explainer}
        </p>
      )}

      {/* Sparkline */}
      {stars_series.length >= 2 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-[0.12em] text-white/35">
            Stars — last {stars_series.length} days
          </div>
          <StarsSparkline series={stars_series} />
        </div>
      )}

      {/* Topics */}
      {repo.topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {repo.topics.map((t) => (
            <span key={t} className="rounded bg-white/[0.04] px-2 py-0.5 text-[10px] text-white/55">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Description (from GitHub, separate from explainer) */}
      {repo.description && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-[0.12em] text-white/35">
            GitHub description
          </div>
          <p className="text-[12px] text-white/60">{repo.description}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-4">
        <Button
          onClick={toggleSave}
          variant={isSaved ? "default" : "outline"}
          size="sm"
          className={cn(isSaved && "bg-[#ff6b9d]/20 text-[#ff6b9d] hover:bg-[#ff6b9d]/30")}
        >
          <Heart className="mr-1.5 size-3.5" fill={isSaved ? "currentColor" : "none"} />
          {isSaved ? "Saved" : "Save"}
        </Button>
        <a
          href={`https://github.com/${repo.full_name}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] px-3 py-1.5 text-[12px] text-white/70 hover:bg-white/[0.03]"
        >
          <ExternalLink className="size-3.5" />
          Open on GitHub
        </a>
        <div
          title="Coming in v2 — publish this repo as an external app in your Forge."
          className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-md border border-dashed border-white/[0.08] px-3 py-1.5 text-[12px] text-white/40"
        >
          <Lock className="size-3.5" />
          Add as external app (v2)
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/components/stars-sparkline.tsx web/components/repo-detail-view.tsx
git commit -m "feat(discovery): stars sparkline + repo detail view"
```

---

## Task 11: `/discover` page + sidebar nav

**Files:**
- Create: `web/app/discover/page.tsx`
- Modify: `web/components/sidebar.tsx`

- [ ] **Step 1: Write the page**

```tsx
// web/app/discover/page.tsx
"use client";

import { useState, useMemo } from "react";
import { Compass } from "lucide-react";
import { DiscoverHero } from "@/components/discover-hero";
import { DiscoverLane } from "@/components/discover-lane";
import { HiddenGemsLane } from "@/components/hidden-gems-lane";
import { DiscoverSearch } from "@/components/discover-search";
import { RepoCard } from "@/components/repo-card";
import { useDiscoveryLanes, useDiscoverySearch, useDiscoverySaves } from "@/lib/hooks";
import { Skeleton } from "@/components/ui/skeleton";

export default function DiscoverPage() {
  const { data, isLoading } = useDiscoveryLanes();
  const { data: savesData } = useDiscoverySaves();
  const [query, setQuery] = useState("");
  const { data: searchData, isLoading: searchLoading } = useDiscoverySearch(query);

  const savedIds = useMemo(
    () => new Set((savesData?.repos ?? []).map((r) => r.id)),
    [savesData],
  );

  const inSearchMode = query.trim().length > 0;
  const themeLanes = (data?.lanes ?? []).filter((l) => l.kind === "theme");
  const gemsLane = (data?.lanes ?? []).find((l) => l.kind === "hidden_gems");

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Compass className="size-5 text-[#5B9FFF]" />
          <h1 className="text-[28px] font-bold tracking-[-0.03em] text-white/98">Discover</h1>
        </div>
        <p className="text-sm text-white/55 leading-relaxed">
          What&rsquo;s shipping in open-source AI. Curated daily.
        </p>
      </div>

      <DiscoverSearch onQueryChange={setQuery} />

      {/* Search mode */}
      {inSearchMode && (
        <section className="flex flex-col gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/40">
            Search results{searchLoading ? " — searching…" : ""}
          </span>
          {(searchData?.results ?? []).length === 0 && !searchLoading && (
            <p className="text-[12px] text-white/50">No matches.</p>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {(searchData?.results ?? []).map((r) => (
              <RepoCard key={r.id} repo={r} saved={savedIds.has(r.id)} />
            ))}
          </div>
        </section>
      )}

      {/* Curated mode */}
      {!inSearchMode && (
        <>
          {isLoading && (
            <div className="flex flex-col gap-6">
              <Skeleton className="h-36 rounded-2xl" />
              <Skeleton className="h-28 rounded-2xl" />
              <Skeleton className="h-28 rounded-2xl" />
            </div>
          )}
          {!isLoading && data && (
            <>
              <DiscoverHero hero={data.hero} />
              {themeLanes.map((lane) => (
                <DiscoverLane key={lane.slug} lane={lane} savedIds={savedIds} />
              ))}
              <HiddenGemsLane lane={gemsLane} savedIds={savedIds} />
              {!data.hero && themeLanes.length === 0 && !gemsLane && (
                <p className="text-sm text-white/50">
                  First scan runs tonight. Check back tomorrow.
                </p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Modify sidebar nav**

In `web/components/sidebar.tsx`, locate the `NAV_ITEMS` array (around line 35) and update:

```typescript
const NAV_ITEMS = [
  { label: "Apps", href: "/", icon: LayoutGrid },
  { label: "Discover", href: "/discover", icon: Compass },
  { label: "Skills", href: "/skills", icon: Sparkles },
  { label: "My Forge", href: "/my-forge", icon: Box },
  { label: "Publish", href: "/publish", icon: Upload },
] as const;
```

And update the import at the top of the file to include `Compass`:

```typescript
import {
  LayoutGrid,
  Sparkles,
  Box,
  Upload,
  Shield,
  Search,
  Compass,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";
```

- [ ] **Step 3: Boot dev server and smoke-test**

Run: `cd web && npm run dev`
Navigate to `http://localhost:3000/discover`.
Expected:
- Sidebar shows new "Discover" item.
- Page renders. If lanes DB is empty, shows "First scan runs tonight".
- Typing in search bar triggers search-mode (may show "search_unavailable" if EXA not configured — that's fine; UI still renders empty results).

- [ ] **Step 4: Commit**

```bash
git add web/app/discover/page.tsx web/components/sidebar.tsx
git commit -m "feat(discovery): /discover page + sidebar nav item"
```

---

## Task 12: `/discover/r/[slug]` standalone + drawer

**Files:**
- Create: `web/app/discover/r/[slug]/page.tsx`
- Create: `web/components/repo-detail-drawer.tsx`

**Note:** Next 15 App Router supports parallel/intercepting routes for drawer-over-page pattern. This plan uses a simpler approach: the `/discover` page embeds `RepoDetailDrawer` controlled by a `?r=<full_name>` query param. The `/discover/r/[slug]` route is the same component in full-page mode for direct links.

- [ ] **Step 1: `RepoDetailDrawer`**

```tsx
// web/components/repo-detail-drawer.tsx
"use client";

import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { RepoDetailView } from "@/components/repo-detail-view";

interface Props {
  fullName: string | null;
  onClose: () => void;
}

export function RepoDetailDrawer({ fullName, onClose }: Props) {
  return (
    <Sheet open={!!fullName} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full max-w-[560px] overflow-y-auto p-0">
        <SheetTitle className="sr-only">{fullName ?? "Repo detail"}</SheetTitle>
        {fullName && <RepoDetailView fullName={fullName} onClose={onClose} />}
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 2: Full-page `/discover/r/[slug]`**

Slug format is URL-encoded `owner/name`. The App Router param will be the encoded string.

```tsx
// web/app/discover/r/[slug]/page.tsx
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { RepoDetailView } from "@/components/repo-detail-view";

export default async function RepoDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const fullName = decodeURIComponent(slug);
  return (
    <div className="max-w-2xl mx-auto p-6 md:p-8">
      <Link
        href="/discover"
        className="mb-4 inline-flex items-center gap-1 text-[12px] text-white/55 hover:text-white/85"
      >
        <ChevronLeft className="size-3.5" />
        Back to Discover
      </Link>
      <RepoDetailView fullName={fullName} />
    </div>
  );
}
```

- [ ] **Step 3: Wire drawer into `/discover` page via URL state**

Modify `web/app/discover/page.tsx`. Adjust `RepoCard` linking behavior: instead of linking to `/discover/r/<slug>`, it pushes a `?r=<slug>` query on the same route — the drawer watches that param. Direct links to `/discover/r/<slug>` still work for sharing.

Update `web/components/repo-card.tsx` to accept an `onOpen` callback that is called instead of navigating, if provided:

```tsx
// web/components/repo-card.tsx (modify existing)
interface RepoCardProps {
  repo: DiscoveryRepo;
  saved?: boolean;
  compact?: boolean;
  onOpen?: (fullName: string) => void;  // optional drawer opener
}

// In RepoCard body, replace `<Link href={...}>` with:
const Wrapper = onOpen
  ? ({ children, className }: { children: React.ReactNode; className: string }) => (
      <button onClick={() => onOpen(repo.full_name)} className={className + " text-left w-full"}>
        {children}
      </button>
    )
  : ({ children, className }: { children: React.ReactNode; className: string }) => (
      <Link href={href} className={className}>{children}</Link>
    );

// Then wrap the existing markup in <Wrapper className="...">...</Wrapper>
```

Update `web/app/discover/page.tsx` to manage drawer state:

```tsx
// At the top of DiscoverPage:
import { useRouter, useSearchParams } from "next/navigation";
import { RepoDetailDrawer } from "@/components/repo-detail-drawer";

export default function DiscoverPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const openRepo = searchParams.get("r");

  function openDrawer(fullName: string) {
    const sp = new URLSearchParams(searchParams.toString());
    sp.set("r", fullName);
    router.push(`/discover?${sp.toString()}`, { scroll: false });
  }
  function closeDrawer() {
    const sp = new URLSearchParams(searchParams.toString());
    sp.delete("r");
    router.push(`/discover${sp.toString() ? `?${sp}` : ""}`, { scroll: false });
  }

  // ... existing code unchanged ...

  // Pass openDrawer to every RepoCard: `onOpen={openDrawer}`
  // At the very end of the returned JSX, render:
  // <RepoDetailDrawer fullName={openRepo} onClose={closeDrawer} />
}
```

Pass `onOpen={openDrawer}` to every `<RepoCard>` in DiscoverPage, DiscoverLane, HiddenGemsLane, and DiscoverHero (plumb through props).

- [ ] **Step 4: Typecheck + smoke test**

Run: `cd web && npx tsc --noEmit && npm run dev`
Open `/discover`, click a card — drawer should slide in from the right. Close with Esc/backdrop. Open `/discover/r/<owner>--<name>` directly → full-page view.

- [ ] **Step 5: Commit**

```bash
git add web/app/discover/r web/components/repo-detail-drawer.tsx web/app/discover/page.tsx web/components/repo-card.tsx web/components/discover-lane.tsx web/components/discover-hero.tsx web/components/hidden-gems-lane.tsx
git commit -m "feat(discovery): detail drawer + standalone detail page"
```

---

## Task 13: `/discover/saved` + My Forge integration

**Files:**
- Create: `web/app/discover/saved/page.tsx`
- Modify: `web/app/my-forge/page.tsx` (add saved-from-discover section)

- [ ] **Step 1: `/discover/saved`**

```tsx
// web/app/discover/saved/page.tsx
"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { RepoCard } from "@/components/repo-card";
import { useDiscoverySaves } from "@/lib/hooks";

export default function DiscoverSavedPage() {
  const { data, isLoading } = useDiscoverySaves();
  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <Link href="/discover" className="inline-flex items-center gap-1 text-[12px] text-white/55 hover:text-white/85">
        <ChevronLeft className="size-3.5" /> Back to Discover
      </Link>
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-white/95">Saved from Discover</h1>
      {isLoading && <p className="text-sm text-white/50">Loading…</p>}
      {!isLoading && (data?.repos?.length ?? 0) === 0 && (
        <p className="text-sm text-white/50">
          Nothing saved yet. Click the heart on any repo to save it.
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {(data?.repos ?? []).map((r) => (
          <RepoCard key={r.id} repo={r} saved />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: My Forge section**

Open `web/app/my-forge/page.tsx`. Find the layout of existing sections (installed apps, skills, etc.) and add a new section. Exact placement depends on the file — insert it after the primary content block:

```tsx
// Add these imports at the top:
import { useDiscoverySaves } from "@/lib/hooks";
import { RepoCard } from "@/components/repo-card";
import Link from "next/link";

// Somewhere in the main render, add:
function SavedFromDiscoverSection() {
  const { data } = useDiscoverySaves();
  const saves = data?.repos ?? [];
  if (saves.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-white/85">Saved from Discover</h2>
        <Link href="/discover/saved" className="text-[11px] text-white/50 hover:text-white/80">
          See all →
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {saves.slice(0, 6).map((r) => (
          <RepoCard key={r.id} repo={r} saved />
        ))}
      </div>
    </section>
  );
}
```

Then call `<SavedFromDiscoverSection />` in the page body. If the file structure differs significantly, adapt the placement to match existing patterns — keep this section below user-owned apps and above skills.

- [ ] **Step 3: Typecheck + smoke test**

Run: `cd web && npx tsc --noEmit && npm run dev`
Save a repo on `/discover`. Visit `/discover/saved` → see it. Visit `/my-forge` → see a preview of saved repos.

- [ ] **Step 4: Commit**

```bash
git add web/app/discover/saved web/app/my-forge/page.tsx
git commit -m "feat(discovery): saved view + My Forge integration"
```

---

## Task 14: End-to-end manual smoke checklist

**Files:** None created. Execution-time validation.

- [ ] **Step 1: Seed some test data (if Plan 1 hasn't produced real data yet)**

```sql
-- via psql
INSERT INTO discovery_repos (owner,name,full_name,stars,classification,topics,exa_explainer,description)
VALUES ('demo','a','demo/a',500,'app','["agents"]','Demo explainer A.','Demo desc A'),
       ('demo','b','demo/b',100,'hybrid','["rag"]','Demo explainer B.','Demo desc B'),
       ('demo','c','demo/c',50,'app','["voice"]','Demo explainer C.','Demo desc C');

INSERT INTO discovery_lanes (slug,title,blurb,kind,repo_ids,position) VALUES
  ('hero','Editor''s pick','What we''re obsessed with this week.','hero',
   (SELECT ARRAY[id] FROM discovery_repos WHERE full_name='demo/a'),0),
  ('agent-stack','Agent frameworks','Tools for building agents.','theme',
   (SELECT ARRAY_AGG(id) FROM discovery_repos WHERE full_name IN ('demo/a','demo/b','demo/c')),1),
  ('hidden-gems','Hidden gems','Small AI apps you probably missed.','hidden_gems',
   (SELECT ARRAY_AGG(id) FROM discovery_repos WHERE classification='app' AND stars < 1000),999);
```

- [ ] **Step 2: Run Flask + Next dev servers together**

Terminal 1: `python api/server.py` (or however Forge normally runs)
Terminal 2: `cd web && npm run dev`

- [ ] **Step 3: Walk through the checklist**

Open http://localhost:3000/discover. Verify:
- [ ] Sidebar shows Discover between Apps and Skills.
- [ ] Hero card renders with editor's pick repo.
- [ ] At least one theme lane renders.
- [ ] Hidden gems lane appears last with purple accent.
- [ ] Click a repo card → drawer slides in from the right.
- [ ] Drawer shows explainer, sparkline (if ≥2 days of stars), topics, description.
- [ ] Save button on drawer and card work; heart turns pink.
- [ ] Close drawer with Esc, backdrop click, and URL back button.
- [ ] Direct-link `/discover/r/demo%2Fa` renders full-page detail with back link.
- [ ] `/discover/saved` lists saved repos.
- [ ] `/my-forge` has "Saved from Discover" section (if you've saved anything).
- [ ] Typing in search bar replaces lanes with "Search results". If EXA is unconfigured, shows empty gracefully.

- [ ] **Step 4: No code commit — just confirm the checklist passed**

If any item fails, file a follow-up; do not claim the plan complete until all items pass.

---

## Self-review — what Plan 2 delivers

- `/api/discover/lanes`, `/api/discover/repo/<full_name>`, `/api/discover/search`, `/api/discover/saves` all functional and tested.
- Blueprint registered in server.py.
- Discover page visible in the sidebar, working end-to-end against Plan 1's data.
- Drawer + standalone routes both render the same component.
- Saved view + My Forge integration.
- All backend routes have tests; frontend validated by manual smoke check.

**Spec coverage delta (vs Plan 1):**
- §3 IA → Task 11 (sidebar), Tasks 12, 13 (routes) ✓
- §7 API surface → Tasks 1-4 ✓
- §8 Frontend → Tasks 5-13 ✓
- §10 Testing (API) → Tasks 1-4 ✓
- §11 Admin → deferred to Plan 3

**Next:** Plan 3 (admin dashboard + cron wiring + backfill runbook).
