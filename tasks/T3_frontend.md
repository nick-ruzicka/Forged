# T3 FRONTEND TASKS
## Rules
- Own ONLY: frontend/css/styles.css, frontend/js/api.js, frontend/js/utils.js, frontend/js/catalog.js, frontend/js/tool.js, frontend/js/submit.js, frontend/js/skills.js, frontend/js/my-tools.js, frontend/index.html, frontend/tool.html, frontend/submit.html, frontend/skills.html, frontend/my-tools.html
- Never touch admin files
- Vanilla JS, no framework, no build step
- Dark mode: --bg #0d0d0d, --accent #0066FF, DM Sans + DM Mono from Google Fonts CDN
- Mark [x] done, update PROGRESS.md

## Tasks

UNBLOCKED: All backend APIs (T1) and admin endpoints (T4) are live — no dependency blockers remain. Every endpoint you call exists:
  - GET /api/tools, /api/tools/:id, /api/tools/slug/:slug (T1 line 15-16)
  - POST /api/tools/submit, /api/tools/:id/run (T1 line 17, 19)
  - POST /api/runs/:id/rate, /api/runs/:id/flag (T1 line 21-22)
  - GET /api/skills, POST /api/skills, /upvote, /copy (T1 line 23-26)
  - GET /api/agent/status/:tool_id (T1 line 28) — for submit.js pipeline progress polling
Recommended start order (all are independent of backend state, pure contract consumers):
  1. styles.css (0 deps, pure CSS)
  2. utils.js (0 deps, no network)
  3. api.js (0 deps, thin fetch wrapper)
  4. index.html + catalog.js (consumes GET /api/tools — seeded with 5 tools in db/seed.py)
  5. Everything else in parallel
No blocker exists. Just start. Seed data is live; load frontend/index.html against running Flask app and tool cards render immediately.

[x] frontend/css/styles.css - CSS variables: --bg #0d0d0d, --surface #1a1a1a, --surface-hover #222, --border #2a2a2a, --text-primary #f0f0f0, --text-secondary #888, --accent #0066FF, --accent-hover #0052cc, --trusted #1a7f4b, --verified #1a4fa0, --caution-text #b8860b, --caution-bg #2a2000, --restricted #c45c00, --unverified #555. Google Fonts DM Sans 400/600/700 and DM Mono 400/500. Components: buttons (primary/secondary/ghost/danger), badges (trust tiers + categories + output types), cards with hover lift, form elements (input/textarea/select/toggle), modal (overlay + panel), toast (bottom-right, 4 types), spinner, skeleton animation, tabs, empty-state. Fixed 56px header. Responsive 768px and 1200px breakpoints.
[x] frontend/js/utils.js - formatDate(iso), formatRelative(iso) "2h ago", formatDuration(ms), formatCost(usd), debounce(fn, delay), copyToClipboard(text, msg), showToast(msg, type, duration=3000) DOM toast system, getUser()/setUser(name,email) localStorage, trustTierBadge(tier) HTML, outputTypeBadge(type) HTML, categoryBadge(cat) HTML, truncate(str, n). Keyboard shortcuts init(): Cmd+K=focus search, g+c=catalog, g+s=submit, g+m=my-tools, Escape=close modals.
[x] frontend/js/api.js - BASE_URL='/api'. apiFetch(path, options) base function. Named functions: getTools(filters), getTool(id), getToolBySlug(slug), submitTool(data), forkTool(id, data), runTool(id, inputs, user), getRuns(toolId), rateRun(id, rating, note), flagRun(id, reason), getSkills(filters), submitSkill(data), upvoteSkill(id), copySkill(id), resolveToken(token), getAgentStatus(toolId).
[x] frontend/index.html + frontend/js/catalog.js - Catalog page. First-visit hero (localStorage forge_visited). Search bar Cmd+K focus. Filter bar: category pills, trust tier checkboxes, sort select. Tool cards 3-col grid, infinite scroll via IntersectionObserver. Card: category badge, trust badge, name bold, tagline 2-line clamp, output type dot, author+runs+rating, Run button. Loading: 6 skeleton cards. Empty state with CTA.
[x] frontend/tool.html + frontend/js/tool.js - Two column 40/60. Left: name, tagline, badges, trust explanation card (color per tier), governance scores expandable (5 bars), description (marked.js CDN rendered), version history accordion, stats, fork+share buttons. Right: dynamic run form, user identity row (localStorage prefill), Run button, output area with trust banner, output formatted per type (text/email_draft/table/json), star rating, flag button, previous runs.
[x] Dynamic form generator in tool.js - generateForm(inputSchema) creates HTML per field type. getInputValues() returns object. validateForm() highlights empty required red. saveInputsToStorage/restoreFromStorage for localStorage persistence keyed by tool slug.
[x] frontend/submit.html + frontend/js/submit.js - 5-step form with step dots. All data saved to localStorage forge_submit_draft on change. Step 1: name (live slug preview), tagline, description, category, tags, author. Step 2: input field builder (add/remove/reorder fields, each has name/label/type/required/placeholder). Live preview right panel. Step 3: model select, max_tokens slider, temperature slider, prompt textarea with {{variable}} highlighting (green=defined, red=undefined), live preview, Test Run button. Step 4: output type cards (DETERMINISTIC/PROBABILISTIC/MIXED), safety radio, data sensitivity cards, reliability_note. Step 5: review summary with edit links, Submit button. Post-submit: agent pipeline progress tracker polling every 3s.
[x] frontend/skills.html + frontend/js/skills.js - Skills library. Search + category filter. Cards: title, use_case, category badge, upvote count+button, Copy Prompt button (shows Copied! 2s, increments count). Submit Skill slide-up modal (title, use_case, prompt_text, category, author).
[x] frontend/my-tools.html + frontend/js/my-tools.js - Identity prompt if no localStorage user. Status tabs: All/Draft/In Review/Approved/Needs Changes/Rejected/Archived. Tool rows with status badge, run count, date, View/Edit/Archive buttons. In-Review rows: live pipeline progress polling every 5s.
[x] Responsive and accessibility pass - mobile single column, tablet 2-col, desktop 3-col. Focus outlines. Modals trap focus. Labels associated with inputs. Min 44px touch targets.

## Cycle 4 Tasks (SPEC output-format + share/fork polish)

UNBLOCKED: All 10 tasks below are within T3 file ownership. Backend endpoints (T1 Cycle 1 /run, /fork, /agent/status, GET /api/health) are all live. For task 4 the /instructions endpoint is a T1 Cycle 2 item — if it returns 404 just show "Instructions not yet generated" placeholder so the button can ship independently. For task 5 the progress_pct column is pending T1 migration 002 — fall back to existing stages[] array when field is absent (SPEC line 915-952 drives these items).

[ ] frontend/js/tool.js - renderEmailDraft(output) block for output_format=='email_draft': fake email card with To/Subject/Body rows (monospace body) and "Copy as email" button that copies formatted text per SPEC line 951.
[ ] frontend/js/tool.js - renderTable(output) for output_format=='table': HTML <table> with click-to-sort headers (asc/desc toggle, stable per-column), striped rows, responsive overflow-x per SPEC line 952.
[ ] frontend/js/tool.js - "Copy Shareable Link" button visible on deployed tools: build `${location.origin}/t/${access_token}` and navigator.clipboard.writeText; showToast("Link copied") per SPEC line 916.
[ ] frontend/js/tool.js - "View Usage Instructions" button: fetch /api/tools/:id/instructions, render markdown in modal (reuse marked.js), include "Download PDF" link pointing to /api/tools/:id/instructions.pdf; show placeholder text if 404 per SPEC line 915.
[ ] frontend/js/submit.js - pipeline progress bar reading agent_reviews.progress_pct (0-100) from /api/agent/status/:tool_id: render <div class="progress-bar"><div style="width:N%"> with current stage label; fall back to stages[] array when progress_pct absent.
[ ] frontend/css/styles.css + frontend/js/tool.js - trust-tier output banners per SPEC lines 355-375: .banner-verified (blue info), .banner-caution (yellow warning), .banner-restricted (orange gated), .banner-unverified (gray experimental), TRUSTED = no banner; inject above output area based on tool.trust_tier.
[ ] frontend/js/utils.js - renderMarkdown(text) helper: marked.parse + DOMPurify.sanitize (add DOMPurify CDN script in tool.html and skills.html head); replace raw marked() calls in tool.js description render and skills.js prompt preview.
[ ] frontend/js/my-tools.js - archive action on draft/needs_changes rows: PUT /api/tools/:id body {status:'archived', author_email: getUser().email}; hide button for approved status; on 200 remove row + showToast; on 403 show "Only the author can archive".
[ ] frontend/index.html + frontend/tool.html + frontend/submit.html + frontend/skills.html + frontend/my-tools.html - global footer partial (injected by utils.js initFooter()): version badge from GET /api/health, #forge-help Slack link, status page link per SPEC line 820.
[ ] frontend/js/tool.js - Fork flow: "Fork this tool" button prompts for new name, POST /api/tools/:id/fork with {author_name, author_email} from getUser(), on 201 redirect to /submit.html?forked_from=<newId> preloading the draft via localStorage forge_submit_draft.
