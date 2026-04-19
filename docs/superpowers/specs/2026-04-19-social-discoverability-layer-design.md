# Social/Discoverability Layer — Design Spec

**Date:** 2026-04-19
**Vision alignment:** VISION.md principle #4 — "Social signals drive discovery, not taxonomies"
**Scope:** Phase 1 (co-installs + trending + external app control panel). Phase 2 (activity feed) and Phase 3 (fork lineage + publisher profiles) are deferred.

## Problem

The catalog is alphabetical with install counts as the only social signal. Discovery depends on scrolling. VISION.md says the primary organizing principle should be "what your team uses" — role-aware recommendations, install counts, co-install patterns.

## Phase 1 Deliverables

### 2a. Co-install patterns

**What:** "People who use X also use..." section in the catalog right pane, showing the top 3 tools most frequently co-installed by users who installed the selected tool.

**Backend — new endpoint:**

`GET /api/tools/<int:tool_id>/coinstalls`

Response:
```json
{
  "tool_id": 32,
  "coinstalls": [
    {"id": 5, "slug": "meeting-prep", "name": "Meeting Prep", "icon": "📋", "overlap": 4},
    {"id": 12, "slug": "hebbia", "name": "Hebbia Signal Engine", "icon": "🔍", "overlap": 3},
    {"id": 8, "slug": "kanban", "name": "Kanban Board", "icon": "📌", "overlap": 2}
  ]
}
```

SQL (computed on-demand, no materialized view):
```sql
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
```

Personalization rule: if the requesting user has installed fewer than 5 tools, use all users' co-install data (the subquery above). After 5 installs, restrict the subquery to users who share at least 2 tools with the requesting user (stronger signal):

```sql
-- Personalized variant: only consider users with >= 2 shared installs
WHERE ui2.user_id IN (
    SELECT ui3.user_id FROM user_items ui3
    WHERE ui3.tool_id IN (
        SELECT tool_id FROM user_items WHERE user_id = %(requesting_user_id)s
    )
    GROUP BY ui3.user_id
    HAVING COUNT(*) >= 2
)
```

Implementation: check requesting user's install count first, choose the appropriate subquery.

**Frontend — catalog.js right pane:**

Add a "People who use {name} also use..." section below the app description in `renderExternalCombined()` (and in the embedded app detail view). Contains 3 small cards:
- Each card: icon (24px) + name + overlap count ("used by 4 others")
- 80% opacity, hover to full opacity
- Click loads that app in the right pane via `selectApp()`
- If no co-install data (new app, no installs): hide section entirely

Location in right pane: after the install/installed CTA, before the interactive preview (if any).

### 2c. Role-aware trending

**What:** Replace the single "Recommended for you" chip strip with two labeled sections showing team-relevant signals.

**Backend — new endpoint:**

`GET /api/team/trending`

Headers: `X-Forge-User-Id` (standard auth)

Response:
```json
{
  "role_trending": [
    {"id": 5, "slug": "meeting-prep", "name": "Meeting Prep", "icon": "📋",
     "installs_this_week": 4, "reason": "4 AEs installed this week"}
  ],
  "team_popular": [
    {"id": 32, "slug": "pluely", "name": "Pluely", "icon": "🎙",
     "team_installs": 6, "reason": "popular on your team"}
  ],
  "role": "AE",
  "team": "ramp.com"
}
```

SQL for role_trending (top 3 tools installed this week by users with same role):
```sql
SELECT t.id, t.slug, t.name, t.icon,
       COUNT(*) as installs_this_week
FROM user_items ui
JOIN users u ON u.user_id = ui.user_id
JOIN tools t ON t.id = ui.tool_id
WHERE u.role = %(role)s
  AND ui.added_at >= NOW() - INTERVAL '7 days'
  AND t.status = 'approved'
  AND ui.tool_id NOT IN (
      SELECT tool_id FROM user_items WHERE user_id = %(user_id)s
  )
GROUP BY t.id, t.slug, t.name, t.icon
ORDER BY installs_this_week DESC
LIMIT 3
```

SQL for team_popular (top 3 most-installed tools on same team, excluding already installed):
```sql
SELECT t.id, t.slug, t.name, t.icon,
       COUNT(*) as team_installs
FROM user_items ui
JOIN users u ON u.user_id = ui.user_id
JOIN tools t ON t.id = ui.tool_id
WHERE u.team = %(team)s
  AND t.status = 'approved'
  AND ui.tool_id NOT IN (
      SELECT tool_id FROM user_items WHERE user_id = %(user_id)s
  )
GROUP BY t.id, t.slug, t.name, t.icon
ORDER BY team_installs DESC
LIMIT 3
```

Edge cases:
- No role set: skip `role_trending`, return empty array
- No team set: skip `team_popular`, return empty array
- No results for either: return empty arrays (frontend hides empty sections)

**Frontend — catalog.js recommendation strip:**

Replace the current single `#recs` section (which calls `/api/me/recommended`) with two labeled rows:

```
TRENDING WITH YOUR ROLE THIS WEEK          (if role_trending has items)
  [chip] [chip] [chip]

POPULAR ON YOUR TEAM                       (if team_popular has items)
  [chip] [chip] [chip]
```

Each chip reuses the existing `.rec-chip` styling with:
- Icon (`.rec-icon`)
- Name (`.rec-name`)
- Subtitle: "3 AEs installed this week" or "popular on your team" (`.rec-why`)
- Click → `selectApp()` to load in right pane

If both sections are empty (solo user, no role/team), show:
"Set your role and team to see personalized recommendations" with a link to profile settings, OR fall back to the existing `/api/me/recommended` response.

The existing `/api/me/recommended` endpoint stays alive (used elsewhere) but the catalog index page stops calling it and calls `/api/team/trending` instead.

### 2e. External app control panel (right pane)

**What:** For external apps (delivery=external), the catalog right pane becomes a live control panel instead of a static info sheet.

**Layout — top to bottom:**

**Header row:**
- App icon (48px) + name + tagline + install type pill (brew/dmg/external)
- Live status: green dot "Running · 23 min" or gray dot "Not running"
- Primary button: "Focus" (running) / "Launch" (installed) / "Install" (not installed)
- Status polls `/api/forge-agent/running` every 15s while pane is visible; polling stops on navigate-away

**Card 1 — "Your usage":**
- 7-day bar chart (inline SVG, 7 bars, sparkline-style, no chart library)
- Summary: "3h 15m this week · 8 sessions · last opened 42m ago"
- Data from new endpoint `GET /api/forge-agent/usage?slug={slug}`
- Empty state: "Not used yet — click Launch above"

New endpoint on forge-agent — `GET /usage?slug=X`:
```json
{
  "slug": "pluely",
  "sessions_7d": [
    {"date": "2026-04-13", "duration_sec": 3600, "count": 2},
    {"date": "2026-04-14", "duration_sec": 0, "count": 0},
    ...
  ],
  "total_sec_7d": 11700,
  "session_count_7d": 8,
  "last_opened": "2026-04-19T08:18:00Z"
}
```
Implementation: read `~/.forge/usage.jsonl`, filter by slug, aggregate last 7 days.

Proxy through Flask: `GET /api/forge-agent/usage?slug=X` → `http://localhost:4242/usage?slug=X`

**Card 2 — "Team":**
- Install count: "4 teammates installed this"
- Role concentration (only if one role >60% of installs): "Popular with AEs — 3 of 4 installs from AEs"
- Recent activity: "2 new installs this week" (from `user_items.added_at` timestamps)
- Empty state: "Be the first on your team to use this"
- Future: add heartbeat system for live presence. See VISION.md social features roadmap.

Data from existing `GET /api/tools/{id}/social` endpoint, extended with:
- `role_concentration`: `{role: "AE", count: 3, total: 4}` if dominant role >60%
- `installs_this_week`: count of `user_items.added_at >= NOW() - INTERVAL '7 days'`

**"Available update" section (conditional):**
- Only rendered if `/api/forge-agent/updates` reports an update for this app
- Shows: current version, new version, "Update" button
- Gold/amber left border
- Proxy: `GET /api/forge-agent/updates?slug=X`

**"Quick actions" row:**
- Show in Finder → POST `/api/forge-agent/launch` with `{app_slug, action: "reveal"}` (new action) → `open -R /Applications/{App}.app`
- View source → `window.open(tool.source_url)` (already in data)
- Uninstall → confirmation modal → POST `/api/forge-agent/uninstall`

**"About" section (collapsed by default):**
- Full description from tool metadata
- Install date, install location (from `~/.forge/installed.json`)

**Privacy footer:**
- 11px, 40% opacity: "Forge monitors: process name only · Not tracked: window titles, URLs, keystrokes"
- Click → modal showing `/api/forge-agent/privacy` response

## Files to modify

### Backend — api/server.py
- Add `GET /api/tools/<int:tool_id>/coinstalls` handler
- Add `GET /api/team/trending` handler
- Extend `GET /api/tools/<int:tool_id>/social` with `role_concentration` and `installs_this_week`
- Add `GET /api/forge-agent/usage` proxy to forge-agent

### Backend — forge_agent/agent.py
- Add `GET /usage?slug=X` handler: reads usage.jsonl, aggregates last 7 days per slug
- Add "reveal" action to `/launch` endpoint: `open -R` instead of `open -a`

### Frontend — frontend/js/catalog.js
- Replace `renderExternalCombined()` with new control panel renderer
- Replace recommendation strip: two labeled sections from `/api/team/trending`
- Add co-install cards section to right pane (both external and embedded views)
- Add usage chart rendering (inline SVG, 7 bars)
- Add privacy modal
- Add polling lifecycle: start on external app select, stop on navigate-away

### No migrations needed
All required columns exist: `user_items.added_at`, `users.role`, `users.team`, `tools.role_tags`.

## What is NOT in scope (Phase 1)

- Activity feed (Phase 2 — needs event logging table)
- Fork lineage badges (Phase 3 — data model exists, UI doesn't)
- Publisher profiles (Phase 3 — new page)
- Live presence / "active now" (requires heartbeat infrastructure — see VISION.md roadmap)
- Co-install cache/materialization (premature at current scale)

## Verification

1. Open catalog as a user with role=AE and team set
2. "Trending with your role this week" shows tools installed by other AEs in the last 7 days
3. "Popular on your team" shows tools with high team-wide install rates
4. Click an app in the catalog, scroll right pane, see "People who use X also use..." with 3 clickable cards
5. Click a co-install card — right pane swaps to that app
6. Co-install cards show real overlap counts, not hardcoded
7. Trending chips show real install counts from the DB
8. If no team/role data: sections gracefully hide, no errors

### Control panel verification

9. Click Pluely in catalog. Right pane shows header with live status dot, usage card with 7-day bar chart, team card, quick actions, privacy footer
10. Launch Pluely from the Focus/Launch button. Status flips green within 15s (next poll)
11. Usage card shows session data from usage.jsonl (real data, not hardcoded)
12. Team card shows install count and role concentration from DB
13. Click "Show in Finder" → Finder opens to /Applications with Pluely highlighted
14. Click "View source" → opens Pluely's GitHub in new tab
15. Click privacy link → modal shows full scope from /privacy endpoint
16. Quit Pluely → status flips gray on next poll
