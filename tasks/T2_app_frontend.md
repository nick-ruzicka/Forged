# T2 APP FRONTEND

## Rules
- Own: `frontend/index.html` (additions only — don't remove existing content), `frontend/js/catalog.js`, `frontend/submit.html`, `frontend/js/submit.js`, `frontend/tool.html`, `frontend/css/styles.css`
- Do NOT touch backend or any other terminal's files
- Use `venv/bin/python3` and `venv/bin/pip` for any Python commands
- Mark tasks `[x]` in this file when done, update PROGRESS.md after each file
- Never stop. When all tasks done write `T2-APP DONE` to PROGRESS.md

## Tasks

UNBLOCKED: T1_app_platform already shipped migration 004_apps.sql (tools.app_html/app_type/schedule_cron/schedule_channel + app_data table) AND api/apps.py blueprint (GET /apps/<slug> injects window.FORGE_APP + window.ForgeAPI; POST /api/apps/analyze Claude Sonnet analyzer live). Every backend dependency you need is already registered in api/server.py. Suggested pick order: (1) frontend/css/styles.css FIRST — add .badge-app/.btn-open-app/.app-modal rules (5 min, zero-dep, pure CSS). (2) frontend/index.html Apps nav + filter pill (10 min, HTML only). (3) frontend/js/catalog.js renderToolCard branch + openAppModal + query-param filter (consumes existing GET /api/tools). (4) frontend/submit.html + submit.js app-type selector using CodeMirror CDN (skip if clipboard API unavailable — fall back to textarea paste). (5) frontend/tool.html iframe swap for app_type=='app'. Sandbox reminder: iframe MUST use sandbox="allow-scripts allow-forms allow-modals" — NEVER include allow-same-origin (security-critical, non-negotiable). Seed data for 3 real apps is still pending in T1_app_platform so cards may show empty app list during dev; test openAppModal against a manually inserted app row via psql.

[x] Update `frontend/index.html` — add "Apps" filter pill to category filter bar. Add "Apps" link to nav (supports `?type=app` query param).

[x] Update `frontend/css/styles.css` — add:
  - `.badge-app { background:#0066FF; color:white; font-size:9px; font-weight:700; padding:2px 8px; border-radius:3px; text-transform:uppercase; }`
  - `.btn-open-app { background:#1a7f4b; color:white; }` (visually distinct from Run Tool, use grid icon ⊞ not arrow)
  - `.app-modal`, `.app-modal-header`, `.app-modal-iframe`, `.app-modal-close`

[x] Update `frontend/js/catalog.js` — modify `renderToolCard(tool)` to branch on `tool.app_type === 'app'`. App cards: show "APP" badge in top-left instead of category badge, button text "Open App" (green, grid icon), click handler calls `openAppModal(tool)` instead of navigating.

[x] Add `openAppModal(tool)` to `catalog.js` — full-screen modal (position:fixed, inset:0, z-index:1000, background rgba(0,0,0,0.95)). Header: tool name + trust badge + close button (X and Escape key). Large iframe to `/apps/${tool.slug}?user=${currentUser}`.
  **IMPORTANT security requirement:** iframe MUST have attribute `sandbox="allow-scripts allow-forms allow-modals"` (NO `allow-same-origin` — this is mandatory to prevent untrusted apps from accessing parent origin storage/cookies). No border, fills modal space minus header. Spinner while loading. Closing modal removes iframe from DOM.

[x] Catalog query param support — if URL has `?type=app`, filter cards to `app_type==='app'` only. Reflect active state in the Apps nav link.

[x] Update `frontend/submit.html` + `frontend/js/submit.js` — add app type selector BEFORE step 1 with two large clickable cards: "Prompt Tool" (existing 5-step flow) and "Full App" (new flow). Store choice in `localStorage.forge_submit_type`.

[x] If "Full App" selected — skip steps 2–4, replace with single-step App Builder. App Builder contains:
  - Large HTML editor textarea using CodeMirror from CDN `https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js` + htmlmixed mode + same CDN's `.css`
  - "Analyze with AI" button → POSTs to `/api/apps/analyze`, auto-fills name/tagline/category
  - Live preview iframe below editor (debounced 1s) — ALSO must use `sandbox="allow-scripts allow-forms allow-modals"` (no allow-same-origin)
  - "Paste from clipboard" button reads clipboard and fills editor
  - Step 1 Basics and Governance steps remain visible
  - Submit creates tool with `app_type='app'` and `app_html` set

[x] Update `frontend/tool.html` — if `tool.app_type === 'app'`, replace right-side run form panel with: large iframe to `/apps/${slug}` (again `sandbox="allow-scripts allow-forms allow-modals"`), "Open in full screen" link (new tab), "Copy shareable link" button.

[x] When all tasks complete, append `T2-APP DONE` line to PROGRESS.md.

## Cycle 7 Tasks (app UX polish + templates + history)

UNBLOCKED: All 10 tasks stay inside T2_app_frontend ownership (frontend/index.html, catalog.js, submit.html, submit.js, tool.html, tool.js, styles.css, my-tools.html/js). Backend: T1_app_platform Cycle 1 endpoints already live (GET /apps/<slug>, POST /api/apps/analyze, data/get/set/delete). Cycle 7 items that rely on T1_app_platform Cycle 7 (GET /apps/<id>/runs, /export, app version history) should ship with graceful 404 fallbacks so frontend lands independently. Sandbox reminder still stands on any new iframe: `sandbox="allow-scripts allow-forms allow-modals"`, never `allow-same-origin`. Suggested pick order: Apps tab in my-tools (1) → CodeMirror hints (2) → copy HTML source (6) → full-screen mode (5) → resize handle (4) → template gallery (7) → version panel (10) → onboarding tour (9) → grid/list toggle (3) → admin analytics block (8).

[ ] frontend/my-tools.html + frontend/js/my-tools.js - Apps tab that filters getUser().email-owned tools where app_type=='app'; each row: Open App (launches openAppModal), Edit HTML (links /submit.html?edit=<id>&type=app), View runs (modal listing last 20 app_runs; 404 fallback "No runs recorded yet").
[ ] frontend/js/submit.js - CodeMirror integration upgrades: enable htmlmixed mode, autoCloseTags, matchTags, lint addon from cdnjs; Cmd/Ctrl+S binds to existing "Analyze with AI" action; add visible "Lines: N | Bytes: B" indicator below editor.
[ ] frontend/js/catalog.js - Grid/List view toggle in catalog toolbar (localStorage forge_catalog_view='grid'|'list'); list mode renders a dense row per tool with thumbnail captured via html2canvas from a throwaway iframe to /apps/<slug>; thumbnails cached in localStorage 24h, keyed by slug+mtime.
[ ] frontend/tool.html + frontend/js/tool.js - app iframe resize handle bottom-right (CSS resize:both + a custom <div class="resize-handle">); min 400x300, max window.innerHeight-120; persist {w,h} in localStorage keyed by tool.slug.
[ ] frontend/css/styles.css + frontend/js/tool.js - .app-full-screen class (position:fixed; inset:0; z:999) + .escape-hint; bind F key and a corner ⤢ button on the app iframe to toggle full-screen; Escape exits and restores previous size.
[ ] frontend/js/tool.js - "Copy HTML source" button below the app iframe, visible only when getUser().email === tool.author_email. Uses navigator.clipboard.writeText(tool.app_html); showToast("Copied HTML").
[ ] frontend/submit.html + frontend/js/submit.js - App template gallery sidebar (6 starter templates: blank, kanban, dashboard, form, timer, checklist); each template loads inline HTML string into the CodeMirror editor when clicked; preserved in localStorage as forge_submit_last_template.
[ ] frontend/js/admin.js - Apps analytics block in the Analytics tab: aggregate client-side from GET /api/tools?app_type=app + individual run_count fields; render a top-5 horizontal bar chart via Chart.js (reuse existing Chart instance array).
[ ] frontend/index.html + frontend/js/catalog.js - first-visit app-catalog onboarding tour: 3 steps pointing at "Apps" filter pill, an app card, and "Open App" button; use minimal stepper (no external library) storing dismissed state in localStorage.forge_apps_tour_done.
[ ] frontend/css/styles.css + frontend/js/tool.js - app version history accordion below the left panel per SPEC lines 905-908: fetches GET /api/tools/:id/versions (already live via T1 Cycle 1); shows version+summary+date+author; "View this version" button swaps iframe src to /apps/<slug>?version=N (frontend-only param, backend falls through for now).
