# T-DASH — GTM Analytics Dashboard

Scope: GTM analytics dashboard that CONSUMES the existing `/api/admin/analytics`
endpoint (owned by T4, api/admin.py lines 467-563) and extends it with five new
analytics endpoints + a dedicated frontend page.

Owns exclusively:
- api/analytics.py
- frontend/analytics.html
- frontend/js/analytics.js

Touches (one-line edits only):
- api/server.py (blueprint registration)
- frontend/index.html (nav link)

## Tasks

- [x] api/analytics.py — Flask blueprint at `/api/analytics`, X-Admin-Key auth
      (decorator copied from api/admin.py). Five endpoints, one SQL each:
  - [x] GET /funnel          (submitted/reviewed/approved/run_once/run_10x/active_30d)
  - [x] GET /builders        (author leaderboard, LIMIT 20)
  - [x] GET /quality         (eval_runs precision/recall, empty=true if missing/empty)
  - [x] GET /latency         (eval_runs load-test latency histogram, empty=true if none)
  - [x] GET /cost-breakdown  (runs.cost_usd grouped by tool category × week, 90d)
- [x] frontend/analytics.html — 3×3 card grid + header KPI strip, Forge design
      language (DM Sans, dark, #0066FF accent).
- [x] frontend/js/analytics.js — parallel fetch of `/api/admin/analytics` + 5
      new endpoints, Chart.js via CDN, localStorage admin key prompt, inline
      empty-state hints referencing `scripts/run_eval.py`.
- [x] api/server.py — registered `analytics_bp` alongside existing blueprint hooks.
- [x] frontend/index.html — added `<a href="/analytics.html">Analytics</a>` nav link.

## Verification

- `python3 -m py_compile api/analytics.py api/server.py` → OK
- `node --check frontend/js/analytics.js` → OK
- Static serve from `frontend/` returns 200 for analytics.html + js/css.
- `grep -n 'analytics' api/server.py` confirms single blueprint hook (2 lines:
  import + register).
- All 6 cards render loading/empty state text when endpoints are unreachable —
  no JS exceptions, layout stable.

## Cycle 13 Tasks (T-DASH v2 — depth + automation)

UNBLOCKED (Cycle 13 coordinator note, 2026-04-16): v1 dashboard shipped end-to-end last cycle (5 endpoints + 3×3 card grid). v2 extends depth without breaking existing payloads. All 10 tasks stay inside T-DASH ownership (api/analytics.py, frontend/analytics.html, frontend/js/analytics.js, tests/test_analytics.py). New data sources come online this cycle that v2 should consume: dlp_audits (T3_NEW Cycle 4 migration 004), sandbox_builds (T1_docker_sandbox Cycle 12 migration 007), forge_data_reads/writes (T2_forgedata Cycle 13 migration 008), app_runs (T1_app_platform Cycle 7 migration 006). If a source table is not yet live, return `{empty: true, reason: "<table> not yet populated"}` following the v1 eval_runs pattern (api/analytics.py:/quality handler) so the card renders gracefully. SPEC drivers: lines 1183-1198 (Analytics tab charts + key metrics strip). Suggested pick order: /rating-trend FIRST (pure runs.rating rollup, zero-dep) → /dlp-rollup → /sandbox-builds-rollup → /forgedata-rollup → /cohort-retention → /builders-deep → filter dropdowns → CSV export → digest email → tests last. Every endpoint reuses the X-Admin-Key decorator from api/admin.py (already copied into analytics.py in v1).

[ ] T-DASH - api/analytics.py - GET /api/analytics/rating-trend: SELECT week_bucket, AVG(rating), COUNT(*) FROM runs WHERE rating IS NOT NULL AND created_at > NOW() - INTERVAL '90 days' GROUP BY date_trunc('week', created_at) ORDER BY week_bucket; returns [{week_iso, avg_rating, run_count}]. Powers SPEC line 1189 "Average rating over time" line chart as a dedicated endpoint (currently inlined in /api/admin/analytics).
[ ] T-DASH - api/analytics.py - GET /api/analytics/dlp-rollup: SELECT pii_type, COUNT(*) FROM dlp_audits WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY pii_type ORDER BY count DESC; graceful empty={empty:true, reason:"dlp_audits table not yet live"} when T3_NEW Cycle 4 migration 004 absent. Returns [{pii_type, count, percent}] with percent computed client-side-friendly.
[ ] T-DASH - api/analytics.py - GET /api/analytics/sandbox-builds-rollup: SELECT COUNT(*) FILTER (WHERE success) AS successful, COUNT(*) FILTER (WHERE NOT success) AS failed, AVG(duration_ms) AS avg_ms, percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms FROM sandbox_builds WHERE created_at > NOW() - INTERVAL '14 days'; empty flag when T1_docker_sandbox Cycle 12 migration 007 not yet live. Surfaces build reliability.
[ ] T-DASH - api/analytics.py - GET /api/analytics/forgedata-rollup: SELECT source, COUNT(*) AS reads, COUNT(DISTINCT tool_id) AS tools_using, AVG(latency_ms) AS avg_ms FROM forge_data_reads WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY source; empty flag when forge_data_reads table absent. Exposes ForgeData adoption per connector.
[ ] T-DASH - api/analytics.py - GET /api/analytics/cohort-retention: runs aggregated by user_email first-seen week vs activity week; returns 2D matrix [{cohort_week, week_offset, active_users, retention_pct}]; limit to 12 weeks. SPEC-aligned retention signal absent from v1. Exclude admin email (FORGE_ADMIN_EMAILS env) from calculation.
[ ] T-DASH - api/analytics.py - GET /api/analytics/builders-deep: extends v1 /builders — add tool_count, total_runs_by_their_tools, avg_trust_tier_numeric (TRUSTED=4..UNVERIFIED=0), weeks_active, last_active_iso per author. Still LIMIT 20. Drives a richer leaderboard card with a sparkline of weekly submissions.
[ ] T-DASH - frontend/analytics.html + frontend/js/analytics.js - filter toolbar at the top: date range picker (7d/30d/90d/custom), category multi-select, trust tier multi-select. Filters applied via query string params passed to every analytics endpoint. Persist last selection in localStorage.forge_dash_filters so reload restores state.
[ ] T-DASH - frontend/js/analytics.js - per-card "Export CSV" button (reuse pattern from T4_admin Cycle 2 line 41 if available): serialize card's data array to CSV string; trigger download via Blob + URL.createObjectURL with filename `forge-<card-slug>-YYYY-MM-DD.csv`. Skip cards with empty=true.
[ ] T-DASH - api/analytics.py - POST /api/analytics/digest/send: admin-only; payload `{to_email, range_days=7}`; composes a plain-text digest (total runs, top 5 tools, trust tier distribution, pending reviews) and POSTs to SLACK_WEBHOOK_URL if configured OR returns the payload in response for manual send. Never raises on missing webhook — returns `{skipped: "no webhook configured"}`.
[ ] T-DASH - tests/test_analytics.py - pytest covering: (a) all 5 v1 endpoints return expected shape on seeded data; (b) each v2 endpoint empty={true, reason} when its source table absent (use SAVEPOINT/ROLLBACK to simulate); (c) filters propagate to SQL WHERE clauses (mock db.get_db and assert on executed SQL); (d) /digest/send with no SLACK_WEBHOOK_URL returns skipped; (e) non-admin X-Admin-Key header → 401 on every endpoint. Mock anthropic and slack_sdk; no real external calls.
