# Retire Vanilla Frontend — Parity Checklist

**Status:** In progress. Verification baseline passed: Next.js catalog renders 12 cards on :3002 with no console errors (2026-04-19).

**Plan:** Close every parity gap below (or explicitly accept it), then retire `frontend/` by removing the Flask static-serve routes and deleting the directory.

---

## Legend
- ✅ Next.js has it (verified)
- 🟡 Next.js has a partial/different version — decide accept vs. close
- ❌ Missing in Next.js — must build or explicitly drop
- 🚫 Intentionally dropped (document the reason)

---

## Catalog (`frontend/index.html` → `web/app/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Search (debounced) | ✅ | 300ms debounce, same as vanilla |
| Category pills | ✅ | Extracted from apps |
| Role-aware sort | ✅ | Matches role_tags to top |
| Star / unstar | ✅ | On card via `StarButton` |
| Install / Open / Launch buttons | ✅ | Via `InstallButton` |
| Role picker onboarding (first visit) | ✅ | `RolePicker` modal |
| Skeleton loading state | ✅ | 6-card skeleton grid |
| Empty state with CTA | ✅ | Links to /publish |
| **Split-view with live preview pane** | 🚫 | Replaced by `/apps/[slug]` route — deliberate UX change |
| **7-day usage chart for external apps** | ❌ | Needs `useAgentUsage` hook + chart component on catalog |
| **Co-installs ("people also use…")** | ❌ | Needs `GET /tools/{id}/coinstalls` wiring + section component |
| **Trending recommendations** | ❌ | Needs `GET /team/trending` wiring + section |
| **External app control panel** (status dot, uptime, privacy) | ❌ | Critical for external delivery UX |
| **Update check** for external apps | ❌ | `GET /forge-agent/updates` not wired |
| **Inspection badges on catalog cards** | 🟡 | Shown on detail only — decide if catalog needs them |
| **Keyboard nav on cards (↑↓/Enter/I)** | 🟡 | `/` opens command menu, but no arrow-key card nav |
| Peer install stats on card | 🟡 | `install_count` shown; peer/team split not shown |
| "Sample data" banner for uninstalled embedded apps | ✅ | On `/apps/[slug]` Open App tab |

## App Detail (`selectApp()` in catalog.js → `web/app/apps/[slug]/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Back link to catalog | ✅ | |
| App metadata header | ✅ | Name, tagline, author, category, install count |
| Install / uninstall button | ✅ | `InstallButton` |
| Star button | ✅ | |
| Source URL external link | ✅ | |
| Overview tab (description, install progress) | ✅ | |
| Review list | ✅ | `ReviewCard` |
| Review form (1-5 stars + text) | ✅ | `ReviewForm` |
| Open App tab (iframe embed) | ✅ | `AppEmbed` |
| Install progress for external apps | ✅ | `InstallProgress` + agent status poll |
| **Privacy disclosure modal** | ❌ | Needed for external apps |
| **"Show in Finder" button** | ❌ | |

## My Forge (`frontend/my-tools.html` → `web/app/my-forge/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Tabs: Installed / Saved / Skills with counts | ✅ | |
| Identity bar (email / name / sign out) | ✅ | |
| Tile grid | ✅ | |
| Open embedded app in modal pane | ✅ | |
| Launch external app via agent | ✅ | |
| Remove / unsave actions | ✅ | |
| Empty states per tab with CTAs | ✅ | |
| **Uptime badge format ("Just started" → "Xm" → "Xh Ym")** | 🟡 | Verify formatter parity |
| **External app auto-discovery from forge-agent** | ❌ | Merges running apps into shelf — needs `GET /forge-agent/running` poll |
| **15s running-status polling** | ❌ | |
| **External app install modal** (copyable command + GitHub link) | 🟡 | Verify — InstallProgress may cover this |
| Tile launch-count increments | ✅ | `POST /me/items/{id}/launch` wired |

## Publish (`frontend/publish.html` → `web/app/publish/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Three modes: Paste / Upload / GitHub | ✅ | |
| Drag-drop HTML into textarea | ✅ | |
| Metadata form (name, tagline, category, icon, description, author) | ✅ | |
| Category dropdown | ✅ | |
| localStorage persistence for author | ✅ | |
| Success screen with CTAs | ✅ | |
| **Zip upload mode** | ❌ | Vanilla accepts `.zip`; verify Next.js `FileInput` accepts it and multipart POST works |
| Drag-drop file into drop zone | 🟡 | Verify drop zone accepts both `.html` and `.zip` |

## Skills (`frontend/skills.html` → `web/app/skills/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Search, category pills, sort dropdown | ✅ | |
| 3-col skill card grid | ✅ | |
| Submit skill dialog | ✅ | |
| Skeleton loaders | ✅ | |
| Subscribe button | ✅ | |
| **Install command (curl) with copy** | ❌ | `<details>` with curl install — needs component |
| **Upvote button + count** | ❌ | `POST /skills/{id}/upvote` not wired |
| **Download .md button** | ❌ | `GET /skills/{id}/download` not wired |

## Admin (`frontend/admin.html` → `web/app/admin/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Password gate | ✅ | `AdminGate` |
| Stats cards (live / pending / skills) | ✅ | |
| Review queue | ✅ | |
| Approve with confirmation | ✅ | |
| Reject with reason prompt | ✅ | |
| Preview button (new tab) | ✅ | |
| **Inspection badges lazy-loaded on each queue item** | 🟡 | Verify |

## Admin Runs (`frontend/admin-runs.html` → `web/app/admin/runs/page.tsx`)

| Feature | Status | Notes |
|---|---|---|
| Run list sidebar | ✅ | |
| Detail pane (prompt + output) | ✅ | |
| New prompt submit (Cmd+Enter) | ✅ | |
| Auto-polling (5s list / 3s running detail) | ✅ | |
| Status badges | ✅ | |

## Global

| Feature | Status | Notes |
|---|---|---|
| Sidebar nav | ✅ | Collapsible, persistent — better than vanilla |
| Installed apps shortcut in sidebar | ✅ | Top 8 most-recently-opened |
| Command menu (Cmd+K / `/`) | ✅ | Better than vanilla |
| Role picker | ✅ | |
| Toasts | ✅ | Sonner — better than vanilla |
| g-chord keyboard nav (g+c/s/m) | ✅ | Better than vanilla |
| localStorage user tracking | ✅ | |
| Mobile layout (hamburger + overlay) | ✅ | |

---

## Summary of gaps

**Must-close before retiring vanilla (external-app UX depends on them):**
1. External app control panel (status/uptime/privacy) on catalog
2. Update check for external apps
3. Privacy disclosure modal on detail
4. External app auto-discovery on My Forge (forge-agent poll + merge)
5. 15s running-status polling on My Forge
6. Skills: install command, upvote, download .md

**Should-close (feature completeness):**
7. 7-day usage chart for external apps
8. Co-installs section
9. Trending recommendations section
10. Zip upload mode on Publish

**Nice-to-have:**
11. Inspection badges on catalog cards
12. Arrow-key card navigation
13. "Show in Finder" button

**Explicitly dropped:**
- Split-view catalog with live preview pane → replaced by `/apps/[slug]` route

---

## Retirement steps (do these last)

1. Close all Must-close gaps above.
2. Run `tests/agents/functional_audit.py` against `:3002` (currently targets `:8090`) — expect 21/21 pass equivalent.
3. Remove Flask static-serve routes in `api/server.py` that `send_from_directory(FRONTEND_DIR, ...)`.
4. Delete `frontend/` and `frontend/js/`, `frontend/css/`.
5. Update `README.md` to point at `web/` as the only frontend.
6. Commit.
