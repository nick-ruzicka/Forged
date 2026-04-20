# Discovery — Plan 3 of 3: Admin + Ops

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add operational surface for keeping discovery healthy in production — admin dashboard, re-cluster/re-enrich buttons, cron wiring, backfill runbook. Closes out §11 and §13 of the spec.

**Architecture:** Admin-gated endpoints appended to `discovery_bp`. New Next.js admin page at `/admin/discovery`. Cron runs via existing infra (crontab on the box or Celery beat — choose what matches current Forge practice at implementation time).

**Depends on:** Plans 1 + 2.

---

## File structure

**New files:**
- `web/app/admin/discovery/page.tsx`
- `docs/runbooks/discovery-operations.md`

**Modified files:**
- `api/discovery/routes.py` — admin endpoints
- `tests/discovery/test_routes.py` — admin endpoint tests
- `web/lib/api.ts` — admin fetchers
- `web/lib/hooks.ts` — admin hooks
- `scripts/start_beat.sh` OR crontab entry (whichever is Forge's convention) — wire the daily job
- `README.md` (root) — add "Discovery Page" section with env-var + cron setup

---

## Task 1: Admin API — status endpoint

**Files:**
- Modify: `api/discovery/routes.py` (append)
- Modify: `tests/discovery/test_routes.py` (append)

- [ ] **Step 1: Append test**

```python
class TestAdminStatusEndpoint:
    def test_requires_admin_key(self, client, db):
        resp = client.get("/api/discover/admin/status")
        assert resp.status_code == 401

    def test_returns_summary_when_authorized(self, client, db, admin_headers):
        from api import db as dbmod
        import json as _j
        with dbmod.get_db() as cur:
            cur.execute(
                "INSERT INTO discovery_repos (owner,name,full_name,stars,classification,topics,exa_explainer) "
                "VALUES ('a','b','a/b',10,'app',%s,'x')",
                (_j.dumps(["agents"]),),
            )
            cur.execute(
                "INSERT INTO discovery_lanes (slug,title,blurb,kind,repo_ids,position) "
                "VALUES ('hero','H','b','hero',ARRAY[1]::int[],0),"
                "       ('t1','T','b','theme',ARRAY[1]::int[],1)"
            )
        resp = client.get("/api/discover/admin/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["repos_total"] >= 1
        assert data["repos_enriched"] >= 1
        assert "lanes" in data
        assert any(l["kind"] == "hero" for l in data["lanes"])
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_routes.py::TestAdminStatusEndpoint -v`
Expected: 404 (route missing).

- [ ] **Step 3: Append admin-gate helper + status endpoint**

In `api/discovery/routes.py`:

```python
import os
from functools import wraps


def _require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("ADMIN_KEY", "")
        provided = request.headers.get("X-Admin-Key", "")
        if not expected or provided != expected:
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


@discovery_bp.route("/admin/status", methods=["GET"])
@_require_admin
def admin_status():
    with dbmod.get_db() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repos WHERE archived_at IS NULL")
        total = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repos WHERE classification IS NOT NULL")
        enriched = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repos WHERE last_seen_at > NOW() - INTERVAL '48 hours'")
        seen_recent = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repos WHERE last_enriched_at > NOW() - INTERVAL '24 hours'")
        enriched_recent = cur.fetchone()["n"]

        cur.execute(
            """SELECT slug, title, blurb, kind, position, generated_at,
                      array_length(repo_ids, 1) AS repo_count
               FROM discovery_lanes ORDER BY position ASC"""
        )
        lanes = [{
            "slug": r["slug"],
            "title": r["title"],
            "blurb": r["blurb"],
            "kind": r["kind"],
            "position": r["position"],
            "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
            "repo_count": r["repo_count"] or 0,
        } for r in cur.fetchall()]

    return jsonify({
        "repos_total": total,
        "repos_enriched": enriched,
        "repos_seen_48h": seen_recent,
        "repos_enriched_24h": enriched_recent,
        "lanes": lanes,
    })
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/discovery/test_routes.py::TestAdminStatusEndpoint -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/routes.py tests/discovery/test_routes.py
git commit -m "feat(discovery): admin status endpoint"
```

---

## Task 2: Admin API — re-cluster now + re-enrich repo

**Files:**
- Modify: `api/discovery/routes.py` (append)
- Modify: `tests/discovery/test_routes.py` (append)

- [ ] **Step 1: Append tests**

```python
class TestAdminActions:
    def test_recluster_triggers_pipeline(self, client, db, admin_headers, monkeypatch):
        from api.discovery import pipeline
        called = {}
        def fake_recluster(min_new_repos=30, max_age_days=5, max_input_repos=100):
            called["ran"] = True
            return {"ran": True, "lanes": 4}
        monkeypatch.setattr(pipeline, "stage5_recluster_lanes", fake_recluster)

        resp = client.post("/api/discover/admin/recluster", headers=admin_headers)
        assert resp.status_code == 200
        assert called.get("ran") is True

    def test_reenrich_repo_triggers_enrichment(self, client, db, admin_headers, monkeypatch):
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute(
                "INSERT INTO discovery_repos (owner,name,full_name,stars) VALUES ('r','e','r/e',5) RETURNING id"
            )
            rid = cur.fetchone()["id"]

        called = {}
        def fake_stage3(repos, gh):
            called["count"] = len(repos)
            return {"enriched": len(repos), "skipped_etag": 0, "failed": 0}
        monkeypatch.setattr("api.discovery.pipeline.stage3_enrich_new", fake_stage3)
        monkeypatch.setattr("api.discovery.pipeline._gh_client", lambda: object())

        resp = client.post(
            "/api/discover/admin/reenrich",
            json={"full_name": "r/e"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert called["count"] == 1
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_routes.py::TestAdminActions -v`
Expected: fail.

- [ ] **Step 3: Append endpoints**

```python
@discovery_bp.route("/admin/recluster", methods=["POST"])
@_require_admin
def admin_recluster():
    from api.discovery import pipeline
    result = pipeline.stage5_recluster_lanes(min_new_repos=0, max_age_days=0)
    pipeline.rebuild_hidden_gems_lane()
    return jsonify(result)


@discovery_bp.route("/admin/reenrich", methods=["POST"])
@_require_admin
def admin_reenrich():
    from api.discovery import pipeline
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"error": "full_name_required"}), 400

    with dbmod.get_db() as cur:
        cur.execute(
            "SELECT id, owner, name, full_name, description, readme_etag "
            "FROM discovery_repos WHERE full_name = %s",
            (full_name,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "not_found"}), 404
        # Force re-enrich by wiping the etag
        cur.execute("UPDATE discovery_repos SET readme_etag = NULL WHERE id = %s", (row["id"],))

    result = pipeline.stage3_enrich_new([{
        "id": row["id"], "owner": row["owner"], "name": row["name"],
        "full_name": row["full_name"], "description": row["description"],
        "readme_etag": None,
    }], pipeline._gh_client())
    return jsonify(result)
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/discovery/test_routes.py::TestAdminActions -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/routes.py tests/discovery/test_routes.py
git commit -m "feat(discovery): admin recluster + reenrich endpoints"
```

---

## Task 3: Frontend — admin page

**Files:**
- Modify: `web/lib/api.ts` (append)
- Modify: `web/lib/hooks.ts` (append)
- Create: `web/app/admin/discovery/page.tsx`

- [ ] **Step 1: API helpers**

Append to `web/lib/api.ts`:

```typescript
// Discovery admin
export function getDiscoveryAdminStatus(adminKey: string) {
  return api<{
    repos_total: number;
    repos_enriched: number;
    repos_seen_48h: number;
    repos_enriched_24h: number;
    lanes: Array<{
      slug: string; title: string; blurb: string | null;
      kind: string; position: number;
      generated_at: string | null; repo_count: number;
    }>;
  }>("/discover/admin/status", {
    headers: { "X-Admin-Key": adminKey },
  });
}

export function reclusterDiscovery(adminKey: string) {
  return api<{ ran: boolean }>("/discover/admin/recluster", {
    method: "POST",
    headers: { "X-Admin-Key": adminKey },
  });
}

export function reenrichDiscoveryRepo(adminKey: string, fullName: string) {
  return api<{ enriched: number }>("/discover/admin/reenrich", {
    method: "POST",
    headers: { "X-Admin-Key": adminKey, "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName }),
  });
}
```

- [ ] **Step 2: Hook**

Append to `web/lib/hooks.ts`:

```typescript
import { getDiscoveryAdminStatus } from "./api";

export function useDiscoveryAdminStatus(adminKey: string | null) {
  return useSWR(
    adminKey ? ["/discover/admin/status", adminKey] : null,
    () => getDiscoveryAdminStatus(adminKey!),
    { refreshInterval: 30_000 },
  );
}
```

- [ ] **Step 3: Admin page**

```tsx
// web/app/admin/discovery/page.tsx
"use client";

import { useState } from "react";
import { mutate } from "swr";
import { AdminGate } from "@/components/admin-gate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDiscoveryAdminStatus } from "@/lib/hooks";
import { reclusterDiscovery, reenrichDiscoveryRepo } from "@/lib/api";
import { useUser } from "@/lib/user-context";

function AdminDiscoveryInner() {
  const { adminKey } = useUser();
  const { data } = useDiscoveryAdminStatus(adminKey);
  const [reenrichTarget, setReenrichTarget] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function handleRecluster() {
    if (!adminKey) return;
    setBusy("recluster");
    try {
      await reclusterDiscovery(adminKey);
      mutate(["/discover/admin/status", adminKey]);
      mutate("/discover/lanes");
    } finally {
      setBusy(null);
    }
  }

  async function handleReenrich() {
    if (!adminKey || !reenrichTarget.trim()) return;
    setBusy("reenrich");
    try {
      await reenrichDiscoveryRepo(adminKey, reenrichTarget.trim());
      setReenrichTarget("");
      mutate(["/discover/admin/status", adminKey]);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <h1 className="text-[22px] font-bold tracking-[-0.02em] text-white/95">Discovery — admin</h1>

      {!data ? (
        <p className="text-sm text-white/50">Loading…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Repos total" value={data.repos_total} />
            <Stat label="Enriched" value={data.repos_enriched} />
            <Stat label="Seen last 48h" value={data.repos_seen_48h} />
            <Stat label="Enriched last 24h" value={data.repos_enriched_24h} />
          </div>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-white/85">Lanes</h2>
            <div className="rounded-xl border border-border overflow-hidden">
              <table className="w-full text-[12px]">
                <thead className="bg-white/[0.02] text-left text-[10px] uppercase tracking-[0.1em] text-white/40">
                  <tr>
                    <th className="px-3 py-2">Kind</th>
                    <th className="px-3 py-2">Slug</th>
                    <th className="px-3 py-2">Title</th>
                    <th className="px-3 py-2 text-right">Repos</th>
                    <th className="px-3 py-2 text-right">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lanes.map((l) => (
                    <tr key={l.slug} className="border-t border-border">
                      <td className="px-3 py-2 text-white/60">{l.kind}</td>
                      <td className="px-3 py-2 text-white/85">{l.slug}</td>
                      <td className="px-3 py-2 text-white/75">{l.title}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-white/60">{l.repo_count}</td>
                      <td className="px-3 py-2 text-right text-[11px] text-white/45">
                        {l.generated_at?.slice(0, 16) ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-white/85">Actions</h2>
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleRecluster} disabled={busy !== null}>
                {busy === "recluster" ? "Re-clustering…" : "Re-cluster lanes now"}
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Input
                placeholder="owner/name"
                value={reenrichTarget}
                onChange={(e) => setReenrichTarget(e.target.value)}
                className="max-w-xs"
              />
              <Button onClick={handleReenrich} disabled={busy !== null || !reenrichTarget.trim()}>
                {busy === "reenrich" ? "Re-enriching…" : "Re-enrich repo"}
              </Button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-[10px] uppercase tracking-[0.1em] text-white/40">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-white/95">{value.toLocaleString()}</div>
    </div>
  );
}

export default function AdminDiscoveryPage() {
  return (
    <AdminGate>
      <AdminDiscoveryInner />
    </AdminGate>
  );
}
```

- [ ] **Step 4: Typecheck + smoke**

Run: `cd web && npx tsc --noEmit`
Navigate to `/admin/discovery` with an admin key set — verify stats display, table renders, re-cluster + re-enrich buttons work.

- [ ] **Step 5: Commit**

```bash
git add web/lib/api.ts web/lib/hooks.ts web/app/admin/discovery
git commit -m "feat(discovery): admin dashboard"
```

---

## Task 4: Cron wiring

**Files:**
- Modify: whichever cron/beat file Forge uses (check `scripts/start_beat.sh` first; if Forge uses system cron, provide a crontab snippet in the runbook instead)

- [ ] **Step 1: Inspect existing cron/beat setup**

Run: `cat scripts/start_beat.sh 2>/dev/null; cat scripts/start_worker.sh 2>/dev/null`

If Celery beat exists with a schedule file, open it and follow the pattern below.

If there's no beat (system cron only), skip to Step 3.

- [ ] **Step 2 (Celery path): Add a beat entry**

If a Celery app with a beat schedule exists, register:

```python
# In wherever the beat schedule lives:
from celery.schedules import crontab

beat_schedule = {
    # ... existing entries ...
    "discovery-ingest-daily": {
        "task": "discovery.ingest",
        "schedule": crontab(minute=0, hour=3),  # 03:00 UTC daily
    },
}
```

And wrap `pipeline.run()` in a Celery task in a new `api/discovery/tasks.py`:

```python
# api/discovery/tasks.py
from celery import shared_task
from api.discovery import pipeline

@shared_task(name="discovery.ingest")
def ingest_task():
    return pipeline.run()
```

- [ ] **Step 3 (System cron path): Document crontab entry**

If no beat scheduler exists, the runbook (next task) will provide this crontab entry:

```cron
# Forge Discovery — daily ingestion
0 3 * * * cd /path/to/forge && /usr/bin/env -i HOME=$HOME PATH=/usr/bin:/bin DATABASE_URL=... GITHUB_DISCOVERY_TOKEN=... EXA_API_KEY=... ANTHROPIC_API_KEY=... python scripts/discovery_ingest.py >> /var/log/forge/discovery.log 2>&1
```

- [ ] **Step 4: Commit**

```bash
git add -p   # stage only the files you changed
git commit -m "feat(discovery): cron wiring for daily ingestion"
```

---

## Task 5: Runbook + README updates

**Files:**
- Create: `docs/runbooks/discovery-operations.md`
- Modify: `README.md` (root)

- [ ] **Step 1: Write the runbook**

```markdown
# Discovery Page — Operations Runbook

## Environment variables

Set these in the Forge environment (systemd unit / `.env` / infra manager):

- `GITHUB_DISCOVERY_TOKEN` — classic PAT with `public_repo` scope. [Generate](https://github.com/settings/tokens).
- `EXA_API_KEY` — from [dashboard.exa.ai](https://dashboard.exa.ai).
- `ANTHROPIC_API_KEY` — already required for other Forge features.
- `DATABASE_URL` — standard Forge DB URL.

Optional:
- `DISCOVERY_ENRICH_MODEL` — override Haiku model ID (default: `claude-haiku-4-5-20251001`).
- `DISCOVERY_CLUSTER_MODEL` — override Sonnet model ID (default: `claude-sonnet-4-6`).

## First-time backfill

After migration 024 is applied, run a one-time backfill before exposing the
`/discover` route to users:

```bash
python scripts/discovery_ingest.py --backfill --verbose
```

Expected: runs 10–20 min. Populates ~200–500 repos. Watch the log for enrichment failures — any repo that fails enrichment will retry on the next daily run.

Then force the initial clustering (otherwise lanes won't appear until 30 repos enrich):

```bash
python scripts/discovery_ingest.py --force-cluster --verbose
```

Confirm lanes populated via `/admin/discovery` or:

```sql
SELECT slug, kind, array_length(repo_ids, 1) AS n FROM discovery_lanes ORDER BY position;
```

## Daily cron

Pick ONE scheduling method below based on what Forge already uses.

### Celery beat (preferred if Forge already runs Celery)

See `api/discovery/tasks.py` and the beat schedule entry `discovery-ingest-daily`.

### System cron (if no Celery)

Edit the Forge service user's crontab:

```bash
crontab -e
```

Add:

```cron
# Forge Discovery — daily ingestion at 03:00 UTC
0 3 * * * cd /opt/forge && /opt/forge/venv/bin/python scripts/discovery_ingest.py >> /var/log/forge/discovery.log 2>&1
```

Ensure env vars are available — either set them in the cron environment or source them from a shared file:

```cron
0 3 * * * cd /opt/forge && . /opt/forge/.env.discovery && /opt/forge/venv/bin/python scripts/discovery_ingest.py >> /var/log/forge/discovery.log 2>&1
```

## Monitoring

- `/admin/discovery` shows repos seen in the last 48h and enriched in the last 24h. If either drops to zero, the cron is broken.
- Check `/var/log/forge/discovery.log` for recent runs.
- Query the DB directly:
  ```sql
  SELECT MAX(last_seen_at) AS last_fetch, MAX(last_enriched_at) AS last_enrich FROM discovery_repos;
  SELECT MAX(generated_at) AS last_cluster FROM discovery_lanes WHERE kind = 'theme';
  ```

## Common issues

**Issue:** "All lanes are old / nothing new in days"
**Check:** `MAX(last_seen_at)` — if older than 48h, the cron isn't running. Check scheduler logs.

**Issue:** "Hidden gems lane is empty"
**Check:** `SELECT COUNT(*) FROM discovery_repos WHERE stars < 1000 AND classification IN ('app','hybrid')` — if low, the EXA hidden-gems query isn't returning app-classified repos. Re-run `--force-cluster` and inspect the latest ingestion log for EXA errors.

**Issue:** "Classification looks wrong on a specific repo"
**Action:** Use `/admin/discovery` → "Re-enrich repo" with the `owner/name`. Forces a fresh Haiku call.

**Issue:** "GitHub rate-limited"
**Check:** Pipeline log for 403/429. Backoff is automatic. If persistent, verify `GITHUB_DISCOVERY_TOKEN` is set and valid. Unauthenticated requests cap at 60/hour and will fail fast.

**Issue:** "EXA is down"
**Impact:** Hidden gems lane falls back to a SQL heuristic; theme lanes continue using GitHub-sourced repos. No user-visible outage.
```

- [ ] **Step 2: Update root README**

Append a "Discovery page" section to the root `README.md`:

```markdown
## Discovery page

Forge includes a curated external-repo discovery page powered by EXA + GitHub. It surfaces trending AI repos and under-the-radar "hidden gems," classified and explained by an LLM.

Set these env vars to enable it:

- `GITHUB_DISCOVERY_TOKEN` — GitHub PAT (public_repo scope)
- `EXA_API_KEY` — exa.ai API key
- `ANTHROPIC_API_KEY` — already required elsewhere

Then run the first-time backfill:

```bash
python scripts/discovery_ingest.py --backfill --force-cluster --verbose
```

Wire the daily cron — see `docs/runbooks/discovery-operations.md`.

Access the page at `/discover`. Admin dashboard at `/admin/discovery`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/discovery-operations.md README.md
git commit -m "docs(discovery): operations runbook + README updates"
```

---

## Task 6: Final smoke + close-out

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/discovery/ -v`
Expected: all tests pass.

Run: `cd web && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 2: Manual admin smoke**

- [ ] `/admin/discovery` loads for admin-key holder; returns 401 for non-admin.
- [ ] Re-cluster button regenerates lanes (verify `generated_at` timestamps refresh).
- [ ] Re-enrich a real repo — `exa_explainer` updates.
- [ ] Backfill command completes without crash (`--dry-run` if env vars unset, or run with real creds against a staging DB).

- [ ] **Step 3: Tag release**

Optional — not a code commit, just note the shippable state.

```bash
git log --oneline -30  # confirm full span of discovery commits
```

---

## Self-review — what Plan 3 delivers

- `/admin/discovery` gives full operational visibility.
- Re-cluster + re-enrich actions exposed without SSH.
- Cron wiring documented, with both Celery beat and system-cron paths.
- Backfill runbook with explicit commands and error-mode troubleshooting.
- README updated so new operators know discovery exists and how to turn it on.

**Spec coverage delta (vs Plans 1+2):**
- §11 Admin surface → Tasks 1-3 ✓
- §13 Rollout → Tasks 4-5 ✓ (migration, env vars, backfill, cron all documented)

**Discovery is feature-complete for v1 after Plan 3.** v2 follow-ups (enabling "Add as external app", team intel, role-aware sorting) are covered in §9 of the spec and left for separate specs.
