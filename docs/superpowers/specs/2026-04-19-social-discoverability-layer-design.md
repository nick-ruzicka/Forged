# Social/Discoverability Layer — Design Spec

**Date:** 2026-04-19
**Vision alignment:** VISION.md principle #4 — "Social signals drive discovery, not taxonomies"
**Scope:** Phase 1 only (co-installs + trending). Phase 2 (activity feed) and Phase 3 (fork lineage + publisher profiles) are deferred.

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

## Files to modify

### Backend (api/server.py)
- Add `GET /api/tools/<int:tool_id>/coinstalls` handler (~30 lines)
- Add `GET /api/team/trending` handler (~50 lines)

### Frontend (frontend/js/catalog.js)
- Modify recommendation loading: replace `/api/me/recommended` call with `/api/team/trending`
- Modify `renderRecs()` (or equivalent): render two labeled sections instead of one
- Modify `renderExternalCombined()`: add co-install cards section after install CTA
- Add `renderCoinstalls(toolId, container)` helper: fetches + renders 3 clickable cards
- Also add co-install section to the embedded app detail view (same `selectApp` code path)

### No migrations needed
All required columns exist: `user_items.added_at`, `users.role`, `users.team`, `tools.role_tags`.

## What is NOT in scope (Phase 1)

- Activity feed (Phase 2 — needs event logging table)
- Fork lineage badges (Phase 3 — data model exists, UI doesn't)
- Publisher profiles (Phase 3 — new page)
- External app control panel in right pane (separate spec)
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
