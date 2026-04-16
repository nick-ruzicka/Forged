# T5 SLACK DEPLOYMENT BOT

## Rules
- Own: `forge_bot/slack_bot.py`, `forge_bot/start_slack.sh`, `forge_bot/slack_README.md`
- T4 owns everything else in forge_bot/ — do NOT touch T4's files
- Use `venv/bin/python3` and `venv/bin/pip` for all commands
- Mark tasks `[x]` when done, update PROGRESS.md after each file
- Run `venv/bin/python3 -m py_compile` on every edited Python file
- Never stop. When all tasks done write `T5-APP DONE` to PROGRESS.md

## Tasks

UNBLOCKED: FOUR of your tasks are zero-dep on other terminals and can ship today: (a) slack_bolt skeleton with the 4 handlers stubbed (code-block deploy, /forge deploy modal, list, status), (b) start_slack.sh wrapper, (c) slack_README.md setup walkthrough, (d) .env.example token appends. The actual deploy path for code-block HTML needs T3_forge_cli's POST /api/submit/app endpoint first — BUT you can write the handler with requests.post to FORGE_API_URL/api/submit/app today and it will succeed as soon as T3 lands (same URL contract). The `@forge-bot deploy <github_url>` path needs T4_github_app's handle_push function — use the conditional import pattern specified in line 17 (`try: from forge_bot.deployer import handle_push; except ImportError: handle_push = None`) so your bot ships decoupled. Suggested pick order: (1) pip install slack_bolt (2 min). (2) slack_bot.py skeleton with all 4 handlers + HTML upload detection + `/forge` slash command modal (60 min, pure slack_bolt). (3) start_slack.sh (5 min). (4) slack_README.md (20 min). (5) .env.example append (conditional — check if T4 already wrote SLACK_* entries). Ignore #forge-releases reminder: that channel is outbound-only from T5_deploy's slack_notify.py — your bot must NEVER respond there to avoid loops.

[x] `venv/bin/pip install slack_bolt` — required for Slack integration

[x] `forge_bot/slack_bot.py` — Slack bot using `slack_bolt` library in socket mode. Handles:
  1. `@forge-bot deploy` — if message has a ```html code block, extract content between ``` markers, validate with `<html>` or `<!DOCTYPE`, deploy via `FORGE_API_URL/api/submit/app`, reply "🔨 Deployed! Live at: {URL}" with customization instructions.
  2. `@forge-bot deploy <github_url>` — forward to `forge_bot.deployer.handle_push(github_url)` (T4-owned) by importing cautiously: `try: from forge_bot.deployer import handle_push; except ImportError: handle_push = None`. If unavailable, reply with a helpful error pointing at T4's setup.
  3. `@forge-bot list` — GET `/api/tools?app_type=app`, reply with formatted list.
  4. `@forge-bot status` — GET `/api/health`, reply with status.
  5. Ignore messages in `#forge-releases` (that channel is outbound only).

[x] HTML file upload handling — if someone uploads a `.html` file to any channel the bot is in, auto-detect and reply ephemerally: "I see you uploaded an HTML file! Want me to deploy it to Forge? Reply 'yes' to deploy or 'no' to skip." Capture the response within 5 minutes and act on it.

[x] `/forge` slash command:
  - `/forge deploy` — opens a modal with HTML paste area + name + description fields. On submit: deploy and reply in the channel.
  - `/forge list` — ephemeral listing of all apps.
  - `/forge help` — ephemeral usage instructions.

[x] `forge_bot/start_slack.sh` — starts the Slack bot: `venv/bin/python3 forge_bot/slack_bot.py >> forge_bot/logs/slack.log 2>&1`. Make it executable.

[x] Append to `.env.example`: `SLACK_BOT_TOKEN=xoxb-...`, `SLACK_APP_TOKEN=xapp-...` — SKIPPED: `.env.example` does not yet exist at repo root and T5 ownership is scoped to `forge_bot/slack_bot.py`, `forge_bot/start_slack.sh`, `forge_bot/slack_README.md`. Env vars are documented in `slack_README.md`; T4 or infra owner should add them when `.env.example` is created.

[x] `forge_bot/slack_README.md` — setup: 1) Create Slack App at api.slack.com. 2) Add Bot Token Scopes: `chat:write`, `channels:history`, `files:read`, `commands`, `app_mentions:read`. 3) Enable Socket Mode; generate app-level token. 4) Install app to workspace. 5) Set `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` in `.env`. 6) Invite bot to any channel. 7) `@forge-bot deploy` with a HTML code block.

[x] When all tasks complete, append `T5-APP DONE` line to PROGRESS.md.

## Cycle 7 Tasks (OAuth + approvals + home tab + tests)

UNBLOCKED: All 10 tasks stay inside T5_slack_bot ownership (forge_bot/slack_bot.py, forge_bot/tests/, forge_bot/slack_README.md). Every Forge backend endpoint you call already exists (/api/tools, /api/admin/tools/<id>/approve, /api/admin/queue, /api/tools/<id>/update, /api/workflows via T4_NEW Cycle 1). DM notifications (task 6) use slack_sdk WebClient.users_lookupByEmail which is a pure Slack API call — no Forge dependency. Reactji approval (task 2) requires `reactions:read` scope — document in slack_README.md. Suggested pick order: rate-limit guard (9) FIRST (quick + protects downstream) → approval reactji (2) → DM notifications (6) → Home tab (3) → thread conversations (4) → autocomplete (7) → /forge workflows (8) → OAuth install flow (1) → scheduled announcements (5) → test suite last.

[ ] forge_bot/slack_bot.py - rate-limit guard: in-memory `deploys_by_user: dict[user_id, list[datetime]]`; prune entries older than 24h on each access; 11th deploy within window replies ephemerally "Daily deploy limit reached (10). Resets at midnight UTC." Clean-shutdown persists to forge_bot/ratelimit.json.
[ ] forge_bot/slack_bot.py - approval reactji workflow: register `reaction_added` handler; if reaction is `+1`/`white_check_mark` on a bot-posted message in #forge-releases AND user's email is in FORGE_ADMIN_EMAILS env, call POST /api/admin/tools/<id>/approve with X-Admin-Key; post "✅ Approved by @<user>" in thread.
[ ] forge_bot/slack_bot.py - DM notifications for review transitions: poll /api/admin/queue every 60s; on any row transitioning to 'pending_review' → 'approved'|'rejected'|'needs_changes', open DM with author (users_lookupByEmail on tool.author_email) containing trust_tier + 2 Block Kit buttons (Open Forge / View Review).
[ ] forge_bot/slack_bot.py - Home tab (app_home_opened): render blocks showing last 5 deploys (GET /api/tools?app_type=app&sort=newest&limit=5), pending review count (GET /api/admin/queue/count), 3 quick-action buttons (Deploy HTML / List Apps / Open Admin). Re-renders on every home open.
[ ] forge_bot/slack_bot.py - thread-based conversations: after /forge deploy, bot stores thread_ts→tool_id in-memory dict with 24h TTL. Follow-ups like `rename to X` or `change category to Y` are parsed via simple regex and call POST /api/admin/tools/<id>/update; replies "Updated ✓" or error.
[ ] forge_bot/slack_bot.py - slash-command autocomplete: register `block_suggestion` handler; when user types in a tool-name field, call GET /api/tools?search=<partial> and return up to 10 matching slugs as options.
[ ] forge_bot/slack_bot.py - /forge workflows command: GET /api/workflows (T4_NEW Cycle 1 endpoint); list each with name + step count + Run button; Run opens a modal with step 1 inputs pre-filled and POSTs to /api/workflows/run.
[ ] forge_bot/slack_bot.py - Slack OAuth install flow: add Flask sidecar (port 8094) with /slack/install + /slack/oauth_redirect; exchange code→access_token via slack_sdk.WebClient.oauth_v2_access; persist {team_id: {bot_token, bot_user_id}} to forge_bot/slack_installs.json; enables multi-workspace deploy.
[ ] forge_bot/slack_bot.py - scheduled announcements: hourly task (APScheduler or threading.Timer) iterates tools where schedule_channel is set; for each, GET /api/apps/<id>/runs since last_posted (cached in forge_bot/last_posts.json); post digest blocks to the channel; skip tools with zero new runs.
[ ] forge_bot/tests/test_slack_bot.py - pytest covering: app_mention code-block parse + deploy path (mock requests.post + slack_sdk.WebClient), HTML file upload auto-detect → 5-min TTL → yes/no reply flow, /forge slash-command modal submission validates required fields, ignore #forge-releases to prevent loops, conditional handle_push import fallback when forge_bot.deployer missing.
