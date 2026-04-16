# T4 ADMIN TASKS
## Rules
- Own ONLY: api/admin.py, frontend/admin.html, frontend/js/admin.js
- Admin auth: X-Admin-Key header vs ADMIN_KEY env var
- Mark [x] done, update PROGRESS.md

## Tasks
[x] api/admin.py - Flask Blueprint "admin" prefix="/api/admin". check_admin_key decorator returns 401 if wrong. All routes use decorator. Add comment: register with app.register_blueprint(admin_bp) in server.py.
[x] GET /api/admin/queue - all pending_review tools joined with agent_reviews. Return {tools, count}.
[x] GET /api/admin/queue/count - {count: N}.
[x] POST /api/admin/tools/:id/approve - status=approved, store reviewer data, apply score_overrides, compute trust_tier, launch deploy_tool background thread, insert tool_version. Return {success, trust_tier, endpoint_url}.
[x] POST /api/admin/tools/:id/reject - status=rejected, store feedback.
[x] POST /api/admin/tools/:id/needs-changes - status=needs_changes, store feedback.
[x] POST /api/admin/tools/:id/override-scores - update governance scores, recompute trust_tier.
[x] GET /api/admin/runs - paginated with filters tool_id/user_email/flagged/dates. Include full input/output. Join tool name.
[x] POST /api/admin/runs/:id/flag - flag run, increment tool flag_count.
[x] GET /api/admin/analytics - {total_tools, total_runs_month, avg_rating, pending_count, tools_by_trust_tier, runs_per_day last 30 days, top_tools top 10, category_distribution, agent_pass_rate}.
[x] POST /api/admin/tools/:id/archive - status=archived.
[x] POST /api/agent/rerun/:tool_id - clear agent_reviews, set agent_reviewing, relaunch pipeline.
[x] frontend/admin.html - Admin page. Check localStorage forge_admin_key on load, show key entry form if missing. Header with queue badge. Tab bar: Queue/Live Tools/Run Monitor/Analytics/Settings. Chart.js CDN. admin.js included.
[x] frontend/js/admin.js - Tab switching. Admin key management. On load: fetch queue count, load Queue tab. Functions: loadQueue(), loadLiveTools(), loadRunMonitor(), loadAnalytics(), loadSettings().
[x] Admin Queue tab in admin.js - renderQueue(tools). Each row: name, author, time, recommendation badge, expand button. Expanded panel: tool info, agent recommendation card, tabs (Classifier/Security/Red Team/Prompt Diff/QA), governance score editor (5 editable inputs + trust tier select + override reason), inline test runner (form + run button), decision section (approve/reject/needs-changes radio + notes + submit). On approve: API call, remove row, success toast.
[x] Prompt diff viewer in admin.js - renderPromptDiff(original, hardened, changes). Two columns side by side. Changed sections highlighted yellow in right column. Change count badge. Hover tooltip per change showing reason.
[x] Run monitor tab in admin.js - Table: time, tool name, user, duration badge (green<2s yellow<5s red>5s), cost, stars, flag button. Auto-refresh 30s. Row click: modal with full inputs/output. Flag button calls API.
[x] Analytics tab in admin.js - 4 metric cards. Chart.js: runs-per-day line, top tools bar, trust tier donut, category donut.
[x] Settings tab in admin.js - Slack webhook input + Test button, default model select, admin key display + Rotate button, maintenance mode toggle.

## Cycle 2 Tasks (self-healer UI + admin UX)

UNBLOCKED: FIVE of 10 Cycle 2 tasks below are zero-dependency — no blocker for starting right now: (a) GET /admin/audit (line 29, reads only existing agent_reviews + tools columns), (b) POST /admin/tools/bulk-approve (line 31, wraps existing approve logic in a transaction), (c) GET /admin/self-healer/activity (line 32, reads tool_versions; treat missing status column as 'pending' until T1 migration 002 lands), (d) admin keyboard shortcuts (line 37, pure JS), (e) Analytics CSV export (line 38, pure JS). Suggested pick order: audit endpoint FIRST (safest read-only) → bulk-approve (high user value) → self-healer activity GET → keyboard shortcuts → CSV export. The three self-healer write endpoints (lines 30, 33, 34) + self-healer UI tab (lines 35-36) need tool_versions.status column from T1 migration 002 — parked until that lands. Unarchive endpoint (line 30) can be implemented today if you treat the restore target as 'approved' without preserving previous status (SPEC allows this simplification).

[ ] api/admin.py - GET /api/admin/audit endpoint: return last 100 admin actions joined from agent_reviews.human_decision/human_reviewer/human_notes and tools.approved_by/approved_at; ordered by timestamp DESC.
[ ] api/admin.py - POST /api/admin/tools/:id/unarchive endpoint: set status back to previous status stored in a new column OR default 'approved'; clear archived_at; return {success, new_status}.
[ ] api/admin.py - POST /api/admin/tools/bulk-approve endpoint: body {ids:[int]}. Inside one DB transaction: approve each, launch deploy thread per id. Return {approved:[ids], failed:[{id, error}]}.
[ ] api/admin.py - GET /api/admin/self-healer/activity endpoint: SELECT from tool_versions WHERE created_by='self-healer' JOIN tools; return [{version_id, tool_id, tool_name, change_summary, created_at, status}]; status='pending' unless promoted.
[ ] api/admin.py - POST /api/admin/self-healer/:version_id/accept endpoint: copy hardened_prompt from tool_versions row into tools.hardened_prompt, increment tools.version, mark version accepted.
[ ] api/admin.py - POST /api/admin/self-healer/:version_id/reject endpoint: mark tool_versions row as rejected (add status column if needed); do not modify parent tool.
[ ] frontend/admin.html - add "Self-Healer" tab to the tab bar between Analytics and Settings; wire data-tab="self-healer" with empty div#self-healer-panel target.
[ ] frontend/js/admin.js - loadSelfHealerActivity(): fetch /admin/self-healer/activity, render each row with tool name, change_summary, side-by-side prompt diff (reuse renderPromptDiff), [Accept][Reject] buttons calling respective endpoints then refreshing.
[ ] frontend/js/admin.js - admin keyboard shortcuts (bound only on /admin page): j/k = next/prev queue row (scroll + highlight), a = approve focused tool, r = open reject modal, Enter = expand review panel, Escape = collapse.
[ ] frontend/js/admin.js - Analytics CSV export: add "Export CSV" button next to analytics header; serialize runs_per_day + top_tools + category_distribution into CSV string; trigger download via Blob + URL.createObjectURL with filename forge-analytics-YYYY-MM-DD.csv.
