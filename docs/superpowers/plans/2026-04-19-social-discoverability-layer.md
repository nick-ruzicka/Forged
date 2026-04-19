# Social/Discoverability Layer + External App Control Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the catalog's static right pane for external apps with a live control panel, add co-install patterns and role-aware trending to the catalog discovery surface.

**Architecture:** Three new backend endpoints (co-installs, trending, usage) + one agent endpoint (usage aggregation) + rewritten right pane renderer for external apps in catalog.js. No DB migrations needed.

**Tech Stack:** Python/Flask backend, vanilla JS frontend, inline SVG for charts, PostgreSQL queries for social data, forge-agent HTTP for usage/status.

---

### Task 1: Add `/usage` endpoint to forge-agent

**Files:**
- Modify: `forge_agent/agent.py:292-326` (do_GET routing) and add handler

- [ ] **Step 1: Add route in do_GET**

In `forge_agent/agent.py`, add the usage route after the `/privacy` check (line 318):

```python
        if parsed.path == "/usage":
            qs = parse_qs(parsed.query)
            slug = (qs.get("slug") or [""])[0]
            self._handle_usage(slug)
            return
```

- [ ] **Step 2: Add _handle_usage method**

Add this method after `_handle_privacy` (after line 696):

```python
    def _handle_usage(self, slug):
        """Return usage stats for a slug from usage.jsonl, aggregated over 7 days."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        day_buckets = {}
        for i in range(7):
            d = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
            day_buckets[d] = {"date": d, "duration_sec": 0, "count": 0}

        last_opened = None
        try:
            with open(USAGE_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if slug and entry.get("slug") != slug:
                        continue
                    started = entry.get("started_at", "")
                    try:
                        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    if dt >= cutoff:
                        day_key = dt.strftime("%Y-%m-%d")
                        if day_key in day_buckets:
                            day_buckets[day_key]["duration_sec"] += entry.get("duration_sec", 0)
                            day_buckets[day_key]["count"] += 1
                    if last_opened is None or started > last_opened:
                        last_opened = started
        except FileNotFoundError:
            pass

        sessions_7d = list(day_buckets.values())
        total_sec = sum(d["duration_sec"] for d in sessions_7d)
        session_count = sum(d["count"] for d in sessions_7d)
        self._json({
            "slug": slug,
            "sessions_7d": sessions_7d,
            "total_sec_7d": total_sec,
            "session_count_7d": session_count,
            "last_opened": last_opened,
        })
```

- [ ] **Step 3: Test manually**

```bash
curl -s "http://localhost:4242/usage?slug=pluely" | python3 -m json.tool
```

Expected: JSON with `sessions_7d` array (7 entries), `total_sec_7d`, `session_count_7d`, `last_opened`.

- [ ] **Step 4: Commit**

```bash
git add forge_agent/agent.py
git commit -m "feat: add /usage endpoint to forge-agent for 7-day usage aggregation"
```

---

### Task 2: Add "reveal" action to forge-agent `/launch`

**Files:**
- Modify: `forge_agent/agent.py:583-607` (_handle_launch)

- [ ] **Step 1: Add action parameter handling**

Replace the `_handle_launch` method body to support `action: "reveal"`:

```python
    def _handle_launch(self, body):
        """Launch or reveal a locally installed app (macOS)."""
        app_slug = body.get("app_slug", "")
        app_name = body.get("app_name", "")
        action = body.get("action", "launch")  # "launch" or "reveal"
        if not app_name and not app_slug:
            self._json({"error": "app_name or app_slug required"}, 400)
            return
        # For reveal, look up install_path from installed.json
        if action == "reveal":
            installed = _load_installed()
            app_entry = next((a for a in installed if a.get("slug") == app_slug), None)
            install_path = app_entry.get("install_path", "") if app_entry else ""
            if not install_path:
                install_path = f"/Applications/{app_name}.app"
            try:
                r = subprocess.run(["open", "-R", install_path],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    self._json({"success": True, "message": f"Revealed {install_path}"})
                else:
                    self._json({"success": False, "message": r.stderr.strip()[:200]}, 400)
            except subprocess.TimeoutExpired:
                self._json({"success": False, "message": "Reveal timed out"}, 500)
            return
        # Original launch logic
        if not app_name:
            self._json({"error": "app_name required"}, 400)
            return
        if not re.match(r"^[a-zA-Z0-9 .\-]+$", app_name):
            self._json({"error": "Invalid app name"}, 400)
            return
        audit.info("LAUNCH %s (%s)", app_name, app_slug)
        if app_slug:
            _pending_launches[app_slug] = time.time() + 45
        try:
            r = subprocess.run(["open", "-a", app_name],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                self._json({"success": True, "message": f"Launched {app_name}"})
            else:
                self._json({"success": False,
                            "message": r.stderr.strip()[:200] or f"Could not launch {app_name}"}, 400)
        except subprocess.TimeoutExpired:
            self._json({"success": False, "message": "Launch timed out"}, 500)
```

- [ ] **Step 2: Test manually**

```bash
TOKEN=$(cat ~/.forge/agent-token)
curl -s -X POST http://localhost:4242/launch \
  -H "X-Forge-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"app_slug":"pluely","app_name":"pluely","action":"reveal"}'
```

Expected: Finder opens to /Applications with Pluely.app highlighted.

- [ ] **Step 3: Commit**

```bash
git add forge_agent/agent.py
git commit -m "feat: add reveal action to /launch for Show in Finder"
```

---

### Task 3: Add Flask proxy for `/api/forge-agent/usage`

**Files:**
- Modify: `api/server.py` (after the existing proxy endpoints ~line 715)

- [ ] **Step 1: Add proxy endpoint**

Add after the `proxy_running` function:

```python
@app.route("/api/forge-agent/usage", methods=["GET"])
def proxy_usage():
    """Proxy usage stats request to forge-agent."""
    slug = request.args.get("slug", "")
    try:
        import urllib.request as ur
        req = ur.Request(f"http://localhost:4242/usage?slug={slug}")
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception:
        return jsonify({"slug": slug, "sessions_7d": [], "total_sec_7d": 0,
                        "session_count_7d": 0, "last_opened": None}), 200
```

- [ ] **Step 2: Test**

```bash
curl -s "http://localhost:8090/api/forge-agent/usage?slug=pluely" | python3 -m json.tool
```

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat: add /api/forge-agent/usage proxy endpoint"
```

---

### Task 4: Add `/api/tools/<id>/coinstalls` endpoint

**Files:**
- Modify: `api/server.py` (after social_stats, ~line 1175)

- [ ] **Step 1: Add endpoint**

```python
@app.route("/api/tools/<int:tool_id>/coinstalls", methods=["GET"])
def tool_coinstalls(tool_id: int):
    """Top 3 tools most frequently co-installed with this tool."""
    uid, _ = _get_identity()
    with db.get_db() as cur:
        # Check requesting user's install count for personalization
        user_count = 0
        if uid:
            cur.execute("SELECT COUNT(*) AS n FROM user_items WHERE user_id = %s", (uid,))
            user_count = cur.fetchone()["n"]

        if user_count >= 5 and uid:
            # Personalized: only users who share >= 2 installs with requesting user
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon, COUNT(*) as overlap
                FROM user_items ui2
                JOIN tools t ON t.id = ui2.tool_id
                WHERE ui2.user_id IN (
                    SELECT ui3.user_id FROM user_items ui3
                    WHERE ui3.tool_id IN (
                        SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                    )
                    AND ui3.user_id != %(uid)s
                    GROUP BY ui3.user_id
                    HAVING COUNT(*) >= 2
                )
                AND ui2.tool_id != %(tool_id)s
                AND t.status = 'approved'
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY overlap DESC
                LIMIT 3
            """, {"uid": uid, "tool_id": tool_id})
        else:
            # Global: all users who installed this tool
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon, COUNT(*) as overlap
                FROM user_items ui2
                JOIN tools t ON t.id = ui2.tool_id
                WHERE ui2.user_id IN (
                    SELECT user_id FROM user_items WHERE tool_id = %(tool_id)s
                )
                AND ui2.tool_id != %(tool_id)s
                AND t.status = 'approved'
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY overlap DESC
                LIMIT 3
            """, {"tool_id": tool_id})

        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"tool_id": tool_id, "coinstalls": rows})
```

- [ ] **Step 2: Test**

```bash
curl -s "http://localhost:8090/api/tools/32/coinstalls" -H "X-Forge-User-Id: test" | python3 -m json.tool
```

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat: add /api/tools/<id>/coinstalls endpoint for co-install patterns"
```

---

### Task 5: Add `/api/team/trending` endpoint

**Files:**
- Modify: `api/server.py` (after coinstalls endpoint)

- [ ] **Step 1: Add endpoint**

```python
@app.route("/api/team/trending", methods=["GET"])
def team_trending():
    """Role-aware trending + team popular tools for the catalog discovery strip."""
    uid, email = _get_identity()
    if not uid:
        return jsonify({"role_trending": [], "team_popular": [], "role": None, "team": None})

    user_role = None
    user_team = None
    with db.get_db() as cur:
        cur.execute("SELECT role, team FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        if row:
            user_role = row.get("role")
            user_team = row.get("team")

    role_trending = []
    team_popular = []

    with db.get_db() as cur:
        if user_role:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon,
                       COUNT(*) as installs_this_week
                FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                JOIN tools t ON t.id = ui.tool_id
                WHERE u.role = %(role)s
                  AND ui.added_at >= NOW() - INTERVAL '7 days'
                  AND t.status = 'approved'
                  AND ui.tool_id NOT IN (
                      SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                  )
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY installs_this_week DESC
                LIMIT 3
            """, {"role": user_role, "uid": uid})
            role_trending = [
                {**dict(r), "reason": f"{r['installs_this_week']} {user_role}s installed this week"}
                for r in cur.fetchall()
            ]

        if user_team:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon,
                       COUNT(*) as team_installs
                FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                JOIN tools t ON t.id = ui.tool_id
                WHERE u.team = %(team)s
                  AND t.status = 'approved'
                  AND ui.tool_id NOT IN (
                      SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                  )
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY team_installs DESC
                LIMIT 3
            """, {"team": user_team, "uid": uid})
            team_popular = [
                {**dict(r), "reason": "popular on your team"}
                for r in cur.fetchall()
            ]

    return jsonify({
        "role_trending": role_trending,
        "team_popular": team_popular,
        "role": user_role,
        "team": user_team,
    })
```

- [ ] **Step 2: Test**

```bash
curl -s "http://localhost:8090/api/team/trending" -H "X-Forge-User-Id: test" | python3 -m json.tool
```

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat: add /api/team/trending endpoint for role + team discovery"
```

---

### Task 6: Extend `/api/tools/<id>/social` with role concentration + weekly installs

**Files:**
- Modify: `api/server.py:1135-1175` (social_stats function)

- [ ] **Step 1: Add role_concentration and installs_this_week queries**

Replace the `social_stats` function:

```python
@app.route("/api/tools/<int:tool_id>/social", methods=["GET"])
def social_stats(tool_id: int):
    """Per-tool social aggregates: installs, team installs, role concentration, weekly."""
    uid, _ = _get_identity()
    user_team = None
    if uid:
        with db.get_db() as cur:
            cur.execute("SELECT team FROM users WHERE user_id = %s", (uid,))
            row = cur.fetchone()
            if row:
                user_team = row.get("team")
    with db.get_db() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM user_items WHERE tool_id = %s",
            (tool_id,),
        )
        total = cur.fetchone()["n"]
        team_n = 0
        role_concentration = None
        installs_this_week = 0
        if user_team:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                WHERE ui.tool_id = %s AND u.team = %s
                """,
                (tool_id, user_team),
            )
            team_n = cur.fetchone()["n"]
            # Role concentration: which role dominates installs for this tool on this team?
            if team_n >= 2:
                cur.execute(
                    """
                    SELECT u.role, COUNT(*) AS n FROM user_items ui
                    JOIN users u ON u.user_id = ui.user_id
                    WHERE ui.tool_id = %s AND u.team = %s AND u.role IS NOT NULL
                    GROUP BY u.role ORDER BY n DESC LIMIT 1
                    """,
                    (tool_id, user_team),
                )
                top_role = cur.fetchone()
                if top_role and top_role["n"] / team_n > 0.6:
                    role_concentration = {
                        "role": top_role["role"],
                        "count": top_role["n"],
                        "total": team_n,
                    }
            # Installs this week on team
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                WHERE ui.tool_id = %s AND u.team = %s
                  AND ui.added_at >= NOW() - INTERVAL '7 days'
                """,
                (tool_id, user_team),
            )
            installs_this_week = cur.fetchone()["n"]
        cur.execute(
            "SELECT AVG(rating)::float AS avg, COUNT(*) AS n FROM tool_reviews WHERE tool_id = %s",
            (tool_id,),
        )
        ratings = dict(cur.fetchone())
    return jsonify({
        "tool_id": tool_id,
        "install_count": total,
        "team_install_count": team_n,
        "team": user_team,
        "avg_rating": ratings.get("avg"),
        "review_count": ratings.get("n") or 0,
        "role_concentration": role_concentration,
        "installs_this_week": installs_this_week,
    })
```

- [ ] **Step 2: Test**

```bash
curl -s "http://localhost:8090/api/tools/32/social" -H "X-Forge-User-Id: test" | python3 -m json.tool
```

Expected: response now includes `role_concentration` and `installs_this_week`.

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat: extend /social with role_concentration and installs_this_week"
```

---

### Task 7: Replace recommendation strip in catalog.js

**Files:**
- Modify: `frontend/js/catalog.js:787-819` (loadRecommendations + renderRecs)

- [ ] **Step 1: Replace loadRecommendations with loadTrending**

Replace lines 787-819:

```javascript
  // ---- Trending / Discovery ----

  let trendingData = { role_trending: [], team_popular: [] };

  async function loadTrending() {
    try {
      const r = await fetch('/api/team/trending', { headers: authHeaders() });
      trendingData = await r.json();
    } catch (e) {
      trendingData = { role_trending: [], team_popular: [] };
    }
  }

  function renderRecs() {
    const wrap = document.getElementById('recs');
    const list = document.getElementById('recs-list');
    if (!wrap || !list) return;

    const hasRole = trendingData.role_trending.length > 0;
    const hasTeam = trendingData.team_popular.length > 0;

    if (!hasRole && !hasTeam) {
      wrap.style.display = 'none';
      return;
    }
    wrap.style.display = '';

    let html = '';
    if (hasRole) {
      html += `<div style="grid-column:1/-1;font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:1.2px;font-weight:500;">Trending with ${esc(trendingData.role || 'your role')}s this week</div>`;
      html += trendingData.role_trending.map(r => `
        <div class="rec-chip" data-slug="${esc(r.slug)}">
          <span class="rec-icon">${esc(r.icon || '⊞')}</span>
          <span class="rec-name">${esc(r.name)}</span>
          <span class="rec-why">${esc(r.reason || '')}</span>
        </div>
      `).join('');
    }
    if (hasTeam) {
      html += `<div style="grid-column:1/-1;font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:1.2px;font-weight:500;${hasRole ? 'margin-top:8px;' : ''}">Popular on your team</div>`;
      html += trendingData.team_popular.map(r => `
        <div class="rec-chip" data-slug="${esc(r.slug)}">
          <span class="rec-icon">${esc(r.icon || '⊞')}</span>
          <span class="rec-name">${esc(r.name)}</span>
          <span class="rec-why">${esc(r.reason || '')}</span>
        </div>
      `).join('');
    }

    list.innerHTML = html;
    list.querySelectorAll('.rec-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const slug = chip.dataset.slug;
        const tool = state.items.find(t => t.slug === slug);
        if (tool) selectApp(tool);
      });
    });
  }
```

- [ ] **Step 2: Update init() to call loadTrending instead of loadRecommendations**

In the `init()` function (line 896), change:

```javascript
    await Promise.all([loadItems(), loadUserState(), loadTrending()]);
```

- [ ] **Step 3: Update recs label**

In `index.html`, change the recs label (line 218):

```html
    <div id="recs" style="display:none;padding:10px 16px;border-bottom:1px solid #1a1a1a;">
      <div id="recs-list" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;"></div>
    </div>
```

Remove the hardcoded "Recommended for you" label div since the label is now dynamic per section.

- [ ] **Step 4: Test in browser**

Hard refresh the catalog. If user has role/team set, trending sections appear. If not, section is hidden.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/catalog.js frontend/index.html
git commit -m "feat: replace recommendation strip with role-aware trending + team popular"
```

---

### Task 8: Rewrite external app right pane as control panel

**Files:**
- Modify: `frontend/js/catalog.js:342-530` (renderExternalCombined)

This is the largest task. The `renderExternalCombined` function is replaced with a control panel renderer.

- [ ] **Step 1: Add running status polling infrastructure**

Add at the top of the IIFE (after `state` declaration, ~line 34):

```javascript
  let _runningPollTimer = null;
  let _runningApps = {}; // slug -> {running, pid, uptime_sec}

  function startRunningPoll(slug) {
    stopRunningPoll();
    pollRunning(slug); // immediate first poll
    _runningPollTimer = setInterval(() => pollRunning(slug), 15000);
  }

  function stopRunningPoll() {
    if (_runningPollTimer) { clearInterval(_runningPollTimer); _runningPollTimer = null; }
  }

  async function pollRunning(slug) {
    try {
      const r = await fetch('/api/forge-agent/running', { signal: AbortSignal.timeout(8000) });
      if (r.ok) {
        const data = await r.json();
        _runningApps = {};
        (data.apps || []).forEach(a => { _runningApps[a.slug] = a; });
        updateControlPanelStatus(slug);
      }
    } catch (e) {}
  }

  function updateControlPanelStatus(slug) {
    const dot = document.getElementById('cp-status-dot');
    const label = document.getElementById('cp-status-label');
    const btn = document.getElementById('cp-primary-btn');
    if (!dot || !label) return;
    const rs = _runningApps[slug];
    const running = rs && rs.running;
    dot.className = 'cp-dot ' + (running ? 'running' : 'stopped');
    if (running) {
      const uptime = rs.uptime_sec ? formatUptime(rs.uptime_sec) : '';
      label.innerHTML = `<span style="color:#22c55e;">Running${uptime ? ' · ' + uptime : ''}</span>`;
      if (btn) { btn.textContent = 'Focus'; btn.dataset.action = 'focus'; }
    } else {
      label.innerHTML = '<span style="color:#555;">Not running</span>';
      if (btn) { btn.textContent = 'Launch'; btn.dataset.action = 'launch'; }
    }
  }

  function formatUptime(sec) {
    if (!sec || sec < 60) return 'just now';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return h + 'h ' + m + 'm';
  }
```

- [ ] **Step 2: Add usage chart SVG renderer**

Add after the polling infrastructure:

```javascript
  function renderUsageChart(sessions7d) {
    if (!sessions7d || !sessions7d.length) return '';
    const maxSec = Math.max(...sessions7d.map(d => d.duration_sec), 1);
    const barW = 24, gap = 4, h = 48;
    const totalW = sessions7d.length * (barW + gap) - gap;
    const bars = sessions7d.map((d, i) => {
      const barH = Math.max((d.duration_sec / maxSec) * h, d.duration_sec > 0 ? 3 : 0);
      const x = i * (barW + gap);
      const y = h - barH;
      const fill = d.duration_sec > 0 ? '#0066FF' : '#1a1a1a';
      const dayLabel = d.date.slice(5); // MM-DD
      return `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="3" fill="${fill}" opacity="0.8"/>
              <text x="${x + barW / 2}" y="${h + 14}" text-anchor="middle" fill="#555" font-size="9">${dayLabel}</text>`;
    }).join('');
    return `<svg width="${totalW}" height="${h + 18}" viewBox="0 0 ${totalW} ${h + 18}">${bars}</svg>`;
  }

  function formatDuration(sec) {
    if (!sec || sec < 60) return '0m';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return h + 'h ' + (m ? m + 'm' : '');
  }

  function timeAgo(isoStr) {
    if (!isoStr) return '';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }
```

- [ ] **Step 3: Replace renderExternalCombined with control panel**

Replace the entire `renderExternalCombined` function (lines 342-530):

```javascript
  function renderExternalCombined(tool) {
    const isInstalled = state.installedSet.has(tool.id);
    const slug = tool.slug || '';

    // Stop any previous polling
    stopRunningPoll();

    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;inset:0;overflow-y:auto;padding:24px;';

    // Parse install type from install_meta
    let installType = 'external';
    try {
      const meta = typeof tool.install_meta === 'string' ? JSON.parse(tool.install_meta) : tool.install_meta;
      if (meta && meta.type) installType = meta.type; // brew, dmg, etc.
    } catch (e) {}

    // ── Header ──
    wrap.innerHTML = `
      <div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:20px;">
        <div style="font-size:28px;width:48px;height:48px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:12px;flex-shrink:0;">${esc(tool.icon || '⊞')}</div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <h2 style="margin:0;font-size:18px;font-weight:700;">${esc(tool.name)}</h2>
            <span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(255,255,255,0.06);color:#888;text-transform:uppercase;letter-spacing:0.5px;">${esc(installType)}</span>
          </div>
          <p style="margin:3px 0 0;color:rgba(255,255,255,0.5);font-size:13px;">${esc(tool.tagline || '')}</p>
        </div>
        <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span id="cp-status-dot" class="cp-dot stopped"></span>
            <span id="cp-status-label" style="font-size:12px;"><span style="color:#555;">Checking...</span></span>
          </div>
          <button id="cp-primary-btn" data-action="${isInstalled ? 'launch' : 'install'}"
            style="background:#0066FF;color:white;border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">
            ${isInstalled ? 'Launch' : 'Install'}
          </button>
        </div>
      </div>

      <!-- Cards row -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
        <div id="cp-usage-card" style="background:#141414;border:1px solid #2a2a2a;border-radius:10px;padding:16px;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;">Your usage</div>
          <div id="cp-usage-content" style="color:#555;font-size:12px;">Loading...</div>
        </div>
        <div id="cp-team-card" style="background:#141414;border:1px solid #2a2a2a;border-radius:10px;padding:16px;">
          <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;">Team</div>
          <div id="cp-team-content" style="color:#555;font-size:12px;">Loading...</div>
          <!-- Future: add heartbeat system for live presence. See VISION.md social features roadmap. -->
        </div>
      </div>

      <!-- Updates placeholder -->
      <div id="cp-update-section"></div>

      <!-- Co-installs -->
      <div id="cp-coinstalls" style="margin-bottom:16px;"></div>

      <!-- Quick actions -->
      <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;">
        <button id="cp-reveal" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;">Show in Finder</button>
        ${tool.source_url ? `<a href="${esc(tool.source_url)}" target="_blank" rel="noopener" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;text-decoration:none;">View source</a>` : ''}
        <button id="cp-uninstall" style="background:#1a1a1a;border:1px solid #2a2a2a;color:#888;padding:7px 14px;border-radius:6px;font-size:11px;cursor:pointer;">Uninstall</button>
      </div>

      <!-- About (collapsed) -->
      <details style="margin-bottom:20px;">
        <summary style="font-size:11px;color:#888;cursor:pointer;text-transform:uppercase;letter-spacing:0.5px;">About</summary>
        <div style="margin-top:10px;font-size:13px;color:rgba(255,255,255,0.6);line-height:1.6;white-space:pre-wrap;">${esc(tool.description || 'No description available.')}</div>
        <div style="margin-top:8px;font-size:11px;color:#555;">by ${esc(tool.author_name || 'Unknown')}</div>
      </details>

      <!-- Privacy footer -->
      <div style="font-size:11px;color:rgba(255,255,255,0.4);border-top:1px solid #1a1a1a;padding-top:12px;">
        Forge monitors: process name only · Not tracked: window titles, URLs, keystrokes
        <a href="#" id="cp-privacy-link" style="color:rgba(255,255,255,0.3);margin-left:6px;">Privacy details</a>
      </div>
    `;

    // ── Inject CSS for status dot ──
    if (!document.getElementById('cp-dot-style')) {
      const style = document.createElement('style');
      style.id = 'cp-dot-style';
      style.textContent = `
        .cp-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
        .cp-dot.running { background:#22c55e; box-shadow:0 0 4px #22c55e; animation:cp-pulse 2s ease-in-out infinite; }
        .cp-dot.stopped { background:#444; }
        @keyframes cp-pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
      `;
      document.head.appendChild(style);
    }

    appPane.appendChild(wrap);

    // ── Wire primary button ──
    wrap.querySelector('#cp-primary-btn').addEventListener('click', async (e) => {
      const btn = e.target;
      const action = btn.dataset.action;
      if (action === 'install') {
        selectApp(tool); // fall through to install flow
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Opening…';
      try {
        await fetch('/api/forge-agent/launch', {
          method: 'POST',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ app_slug: slug, app_name: tool.name }),
          signal: AbortSignal.timeout(5000),
        });
        btn.textContent = '● Focus';
        btn.style.background = 'rgba(34,197,94,0.15)';
        btn.style.color = '#22c55e';
        btn.style.border = '1px solid rgba(34,197,94,0.3)';
      } catch (err) {
        btn.textContent = 'Launch';
      }
      btn.disabled = false;
    });

    // ── Wire Show in Finder ──
    const revealBtn = wrap.querySelector('#cp-reveal');
    if (revealBtn) {
      revealBtn.addEventListener('click', async () => {
        try {
          const tokenR = await fetch('/api/agent/token');
          const tokenD = await tokenR.json();
          await fetch('http://localhost:4242/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Forge-Token': tokenD.token },
            body: JSON.stringify({ app_slug: slug, app_name: tool.name, action: 'reveal' }),
            signal: AbortSignal.timeout(5000),
          });
        } catch (e) {}
      });
    }

    // ── Wire Uninstall ──
    const uninstallBtn = wrap.querySelector('#cp-uninstall');
    if (uninstallBtn) {
      uninstallBtn.addEventListener('click', async () => {
        if (!confirm(`Uninstall ${tool.name}?`)) return;
        uninstallBtn.disabled = true;
        uninstallBtn.textContent = 'Removing…';
        try {
          await fetch('/api/forge-agent/uninstall', {
            method: 'POST',
            headers: { ...authHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ slug }),
            signal: AbortSignal.timeout(10000),
          });
          await fetch(`/api/me/items/${tool.id}`, { method: 'DELETE', headers: authHeaders() });
          state.installedSet.delete(tool.id);
          renderList();
          uninstallBtn.textContent = 'Uninstalled';
        } catch (e) {
          uninstallBtn.textContent = 'Uninstall';
          uninstallBtn.disabled = false;
        }
      });
    }

    // ── Wire Privacy link ──
    wrap.querySelector('#cp-privacy-link').addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const r = await fetch('/api/forge-agent/privacy');
        const data = await r.json();
        const modal = document.createElement('div');
        modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:200;display:flex;align-items:center;justify-content:center;padding:24px;';
        modal.innerHTML = `<div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;max-width:500px;width:100%;padding:24px;max-height:80vh;overflow:auto;">
          <h3 style="margin:0 0 12px;font-size:16px;">Privacy Details</h3>
          <div style="font-size:12px;color:#ccc;line-height:1.6;">
            <p><strong>Scope:</strong> ${esc(data.scope || '')}</p>
            <p><strong>Method:</strong> ${esc(data.method || '')}</p>
            <p><strong>Data collected:</strong></p>
            <ul style="color:#888;margin:4px 0 12px;">${(data.data_collected || []).map(d => '<li>' + esc(d) + '</li>').join('')}</ul>
            <p><strong>Data NOT collected:</strong></p>
            <ul style="color:#888;margin:4px 0 12px;">${(data.data_not_collected || []).map(d => '<li>' + esc(d) + '</li>').join('')}</ul>
            <p style="color:#555;">Storage: ${esc(data.storage || '')}</p>
          </div>
          <button onclick="this.closest('div[style*=fixed]').remove()" style="margin-top:12px;background:#1a1a1a;border:1px solid #2a2a2a;color:#ccc;padding:7px 16px;border-radius:6px;font-size:12px;cursor:pointer;">Close</button>
        </div>`;
        modal.addEventListener('click', (ev) => { if (ev.target === modal) modal.remove(); });
        document.body.appendChild(modal);
      } catch (err) {}
    });

    // ── Async: Load usage data ──
    fetch(`/api/forge-agent/usage?slug=${encodeURIComponent(slug)}`).then(r => r.json()).then(usage => {
      const el = wrap.querySelector('#cp-usage-content');
      if (!el) return;
      if (!usage.session_count_7d) {
        el.innerHTML = '<span style="color:#555;">Not used yet — click Launch above</span>';
        return;
      }
      const chart = renderUsageChart(usage.sessions_7d);
      const lastOpened = usage.last_opened ? timeAgo(usage.last_opened) : 'unknown';
      el.innerHTML = `
        ${chart}
        <div style="margin-top:10px;font-size:12px;color:#aaa;">
          ${formatDuration(usage.total_sec_7d)} this week · ${usage.session_count_7d} sessions · last opened ${lastOpened}
        </div>`;
    }).catch(() => {
      const el = wrap.querySelector('#cp-usage-content');
      if (el) el.innerHTML = '<span style="color:#555;">Usage data unavailable</span>';
    });

    // ── Async: Load team/social data ──
    fetch(`/api/tools/${tool.id}/social`, { headers: authHeaders() }).then(r => r.json()).then(social => {
      const el = wrap.querySelector('#cp-team-content');
      if (!el) return;
      if (!social.team_install_count) {
        el.innerHTML = '<span style="color:#555;">Be the first on your team to use this</span>';
        return;
      }
      let html = `<div style="font-size:14px;color:#e0e0e0;font-weight:500;margin-bottom:6px;">${social.team_install_count} teammate${social.team_install_count > 1 ? 's' : ''} installed this</div>`;
      if (social.role_concentration) {
        const rc = social.role_concentration;
        html += `<div style="font-size:12px;color:#888;margin-bottom:4px;">Popular with ${esc(rc.role)}s — ${rc.count} of ${rc.total} installs from ${esc(rc.role)}s</div>`;
      }
      if (social.installs_this_week > 0) {
        html += `<div style="font-size:12px;color:#888;">${social.installs_this_week} new install${social.installs_this_week > 1 ? 's' : ''} this week</div>`;
      }
      el.innerHTML = html;
    }).catch(() => {
      const el = wrap.querySelector('#cp-team-content');
      if (el) el.innerHTML = '<span style="color:#555;">Team data unavailable</span>';
    });

    // ── Async: Load co-installs ──
    fetch(`/api/tools/${tool.id}/coinstalls`, { headers: authHeaders() }).then(r => r.json()).then(data => {
      const el = wrap.querySelector('#cp-coinstalls');
      if (!el || !data.coinstalls || !data.coinstalls.length) return;
      el.innerHTML = `
        <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;">People who use ${esc(tool.name)} also use</div>
        <div style="display:flex;gap:10px;">
          ${data.coinstalls.map(ci => `
            <div class="ci-card" data-slug="${esc(ci.slug)}" style="flex:1;background:#141414;border:1px solid #2a2a2a;border-radius:8px;padding:12px;cursor:pointer;opacity:0.8;transition:opacity 0.15s,border-color 0.15s;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="font-size:16px;">${esc(ci.icon || '⊞')}</span>
                <span style="font-size:13px;font-weight:600;color:#f0f0f0;">${esc(ci.name)}</span>
              </div>
              <div style="font-size:10px;color:#555;">used by ${ci.overlap} others</div>
            </div>
          `).join('')}
        </div>`;
      el.querySelectorAll('.ci-card').forEach(card => {
        card.addEventListener('mouseenter', () => { card.style.opacity = '1'; card.style.borderColor = '#0066FF'; });
        card.addEventListener('mouseleave', () => { card.style.opacity = '0.8'; card.style.borderColor = '#2a2a2a'; });
        card.addEventListener('click', () => {
          const ciSlug = card.dataset.slug;
          const ciTool = state.items.find(t => t.slug === ciSlug);
          if (ciTool) selectApp(ciTool);
        });
      });
    }).catch(() => {});

    // ── Async: Check for updates ──
    fetch('/api/forge-agent/running', { signal: AbortSignal.timeout(3000) }).then(r => r.json()).then(() => {
      // Updates check — only show if forge-agent reports an update
      fetch(`/api/forge-agent/updates?slug=${encodeURIComponent(slug)}`, { signal: AbortSignal.timeout(5000) })
        .then(r => r.ok ? r.json() : null)
        .then(upd => {
          if (!upd || !upd.updates || !upd.updates.length) return;
          const update = upd.updates[0];
          const section = wrap.querySelector('#cp-update-section');
          if (!section) return;
          section.innerHTML = `
            <div style="background:#141414;border:1px solid #2a2a2a;border-left:3px solid #d97706;border-radius:10px;padding:16px;margin-bottom:16px;">
              <div style="font-size:10px;color:#d97706;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">Available update</div>
              <div style="font-size:13px;color:#e0e0e0;">${esc(update.detail || 'A newer version is available')}</div>
            </div>`;
        }).catch(() => {});
    }).catch(() => {});

    // ── Start polling running status ──
    if (isInstalled) startRunningPoll(slug);
  }
```

- [ ] **Step 4: Add proxy for /api/forge-agent/privacy and /api/forge-agent/updates**

In `api/server.py`, add after the usage proxy:

```python
@app.route("/api/forge-agent/privacy", methods=["GET"])
def proxy_privacy():
    """Proxy privacy request to forge-agent."""
    try:
        import urllib.request as ur
        req = ur.Request("http://localhost:4242/privacy")
        with ur.urlopen(req, timeout=5) as r:
            return jsonify(json.loads(r.read()))
    except Exception:
        return jsonify({"error": "forge-agent unavailable"}), 200


@app.route("/api/forge-agent/updates", methods=["GET"])
def proxy_updates():
    """Proxy updates request to forge-agent."""
    try:
        import urllib.request as ur
        slug = request.args.get("slug", "")
        req = ur.Request(f"http://localhost:4242/updates")
        with ur.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            if slug:
                data["updates"] = [u for u in data.get("updates", []) if u.get("slug") == slug]
            return jsonify(data)
    except Exception:
        return jsonify({"updates": []}), 200
```

- [ ] **Step 5: Stop polling on navigate-away**

In `selectApp()`, add at the beginning (line 234):

```javascript
    stopRunningPoll(); // Clean up previous external app polling
```

- [ ] **Step 6: Test in browser**

1. Hard refresh catalog
2. Click Pluely — right pane shows control panel with header, status dot, usage card, team card, quick actions, privacy footer
3. Click "Show in Finder" — Finder opens
4. Click "View source" — GitHub opens in new tab
5. Click privacy link — modal opens with full scope
6. Usage chart renders with data from usage.jsonl

- [ ] **Step 7: Commit**

```bash
git add frontend/js/catalog.js api/server.py
git commit -m "feat: external app control panel with usage, team signals, co-installs"
```

---

### Task 9: Add co-install cards to embedded app view

**Files:**
- Modify: `frontend/js/catalog.js:314-338` (inside selectApp, embedded branch)

- [ ] **Step 1: Add co-installs section to embedded app social bar**

After the social info bar (line 324), before the iframe, add:

```javascript
      // Co-installs section
      const coinstallWrap = document.createElement('div');
      coinstallWrap.style.cssText = 'padding:0 16px 8px;';
      fetch(`/api/tools/${tool.id}/coinstalls`, { headers: authHeaders() }).then(r => r.json()).then(data => {
        if (!data.coinstalls || !data.coinstalls.length) return;
        coinstallWrap.innerHTML = `
          <div style="font-size:10px;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;">Also used by people who use ${esc(tool.name)}</div>
          <div style="display:flex;gap:8px;margin-bottom:4px;">
            ${data.coinstalls.map(ci => `
              <div class="ci-card" data-slug="${esc(ci.slug)}" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:6px 10px;cursor:pointer;opacity:0.8;transition:opacity 0.15s;display:flex;align-items:center;gap:6px;">
                <span style="font-size:14px;">${esc(ci.icon || '⊞')}</span>
                <span style="font-size:11px;color:#ccc;">${esc(ci.name)}</span>
              </div>
            `).join('')}
          </div>`;
        coinstallWrap.querySelectorAll('.ci-card').forEach(card => {
          card.addEventListener('mouseenter', () => { card.style.opacity = '1'; });
          card.addEventListener('mouseleave', () => { card.style.opacity = '0.8'; });
          card.addEventListener('click', () => {
            const ciSlug = card.dataset.slug;
            const ciTool = state.items.find(t => t.slug === ciSlug);
            if (ciTool) selectApp(ciTool);
          });
        });
      }).catch(() => {});
      wrap.appendChild(coinstallWrap);
```

Insert this before `wrap.appendChild(iframe)` (currently at line 337).

- [ ] **Step 2: Test**

Click an embedded app (e.g., Hebbia Signal Engine). Below the social bar, co-install cards should appear if any users share installations.

- [ ] **Step 3: Commit**

```bash
git add frontend/js/catalog.js
git commit -m "feat: add co-install cards to embedded app view"
```

---

### Task 10: Restart servers and end-to-end verification

- [ ] **Step 1: Restart forge-agent**

```bash
kill $(lsof -t -i :4242) 2>/dev/null; sleep 1; python3 forge_agent/agent.py &
```

- [ ] **Step 2: Restart Flask server**

```bash
kill $(lsof -t -i :8090) 2>/dev/null; sleep 1; PYTHONPATH=. python3 api/server.py &
```

- [ ] **Step 3: Verify backend endpoints**

```bash
# Co-installs
curl -s "http://localhost:8090/api/tools/32/coinstalls" -H "X-Forge-User-Id: test" | python3 -m json.tool

# Trending
curl -s "http://localhost:8090/api/team/trending" -H "X-Forge-User-Id: test" | python3 -m json.tool

# Usage
curl -s "http://localhost:8090/api/forge-agent/usage?slug=pluely" | python3 -m json.tool

# Social (extended)
curl -s "http://localhost:8090/api/tools/32/social" -H "X-Forge-User-Id: test" | python3 -m json.tool

# Privacy proxy
curl -s "http://localhost:8090/api/forge-agent/privacy" | python3 -m json.tool
```

- [ ] **Step 4: Browser verification**

1. Open catalog. Trending sections show tools (if user has role/team set)
2. Click Pluely. Right pane = control panel with status dot, usage chart, team card, quick actions
3. Usage chart renders real data from usage.jsonl
4. Co-install cards are clickable and swap the right pane
5. Status dot shows green if Pluely is running, gray if not
6. Click "Show in Finder" → Finder opens
7. Click "View source" → GitHub in new tab
8. Click privacy link → modal with full scope
9. Click an embedded app → co-install cards appear below social bar

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: social/discoverability layer phase 1 — co-installs, trending, control panel"
```
