# Forge

Internal AI tool marketplace for the Navan RevOps team. Builders submit
tools they've prototyped in Claude; a multi-agent pipeline reviews,
hardens, and scores them; approved tools auto-deploy to a live URL with
a generated usage guide and Slack announcement.

Tagline: **Build once. Run everywhere. Trust everything.**

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- An Anthropic API key (set as `ANTHROPIC_API_KEY`)
- Optional: a Slack incoming webhook URL for `#forge-releases`

## Local Development (Docker)

The fastest way to run the full stack locally.

```bash
cp .env.example .env              # then fill in ANTHROPIC_API_KEY
docker-compose up --build
# Forge API:         http://localhost:8090
# Static assets:     http://localhost:8090/static/
# Postgres:          localhost:5432  (forge / forge)
# Redis:             localhost:6379
```

Run migrations against the running stack:

```bash
docker-compose exec forge-app python3 scripts/run_migrations.py
```

## Local Development (bare metal)

```bash
pip install -r requirements.txt
createdb forge
python3 scripts/run_migrations.py
python3 api/server.py            # serves on :8090
```

## VPS Deployment (Hetzner / Ubuntu)

Fresh server, run once as root:

```bash
curl -fsSL https://raw.githubusercontent.com/nick-ruzicka/forge-platform/main/deploy/setup.sh | bash
```

or clone manually and run the bundled script:

```bash
git clone https://github.com/nick-ruzicka/forge-platform.git /root/forge
cd /root/forge
bash deploy/setup.sh
```

Every subsequent update:

```bash
bash /root/forge/deploy/deploy.sh
```

Check health:

```bash
bash /root/forge/scripts/health_check.sh
```

## Environment Variables

| Variable               | Required | Default                                          | Description                                    |
| ---------------------- | -------- | ------------------------------------------------ | ---------------------------------------------- |
| `DATABASE_URL`         | yes      | `postgresql://forge:forge@localhost:5432/forge`  | Postgres connection string                     |
| `REDIS_URL`            | yes      | `redis://localhost:6379/0`                       | Celery broker and rate-limit store             |
| `ANTHROPIC_API_KEY`    | yes      | —                                                | Claude API key for agents and tool execution   |
| `FORGE_HOST`           | yes      | `http://localhost:8090`                          | Public base URL (used for shareable links)    |
| `ADMIN_KEY`            | yes      | `change-me`                                      | Shared secret for `X-Admin-Key` header         |
| `SLACK_WEBHOOK_URL`    | no       | —                                                | Announce approved tools to `#forge-releases`   |
| `FORGE_DOC_MODEL`      | no       | `claude-haiku-4-5-20251001`                      | Model used to write usage guides               |
| `FORGE_HEALTH_URL`     | no       | `http://127.0.0.1:8090/api/health`               | Health-check target                            |

## Submit Your First Tool

1. Open Forge in your browser → click **Submit a Tool**.
2. **Step 1 (Basics):** name, tagline, description, category.
3. **Step 2 (Inputs):** add the fields your tool needs (`text`, `select`, etc.).
4. **Step 3 (Prompt):** write the Claude prompt — reference inputs as `{{field_name}}`.
5. **Step 4 (Governance):** self-classify output type, safety, data sensitivity.
6. **Step 5:** review and submit.

The review pipeline (classifier → security → red team → hardener → QA →
synthesizer) runs async via Celery. You'll be notified when it
completes. On approval, the tool auto-deploys and appears in the catalog.

## Admin Access

Admin UI lives at `/admin`. Authenticate by setting your admin key:

```js
localStorage.setItem('forge_admin_key', '<ADMIN_KEY from .env>')
```

From there you can:

- review the pending queue (agent progress, full review panel)
- approve / reject / request changes
- override governance scores
- monitor live runs
- view analytics

## Architecture Overview

```
  ┌─────────────┐      ┌────────────────┐      ┌──────────────────┐
  │  Frontend   │ ───▶ │  Flask API     │ ───▶ │  PostgreSQL      │
  │  (vanilla)  │      │  :8090 /api/   │      │  tools, runs,    │
  └─────────────┘      │                │      │  agent_reviews   │
                       └──────┬─────────┘      └──────────────────┘
                              │
                              ▼
                       ┌────────────────┐      ┌──────────────────┐
                       │  Celery worker │ ───▶ │  Redis (broker + │
                       │  agent pipeline│      │   rate limit)    │
                       └────────────────┘      └──────────────────┘
                              │
                              ▼
                       ┌────────────────┐
                       │  Claude API    │
                       └────────────────┘
```

Approval pipeline:

```
submit → pre-flight → classifier → security → red team
                       ↓
                     hardener → QA tester → synthesizer → admin review
                                                             ↓
                                               approve → deploy_tool()
                                                             ↓
                                          instructions (MD + PDF)
                                                             ↓
                                               Slack announcement
```

Deployment (`api/deploy.py`) is the last step: it mints an access
token, writes the Markdown usage guide to
`static/instructions/{tool_id}.md`, attempts to render a PDF via
WeasyPrint (skipped if unavailable), persists deployment metadata, and
posts to Slack if `SLACK_WEBHOOK_URL` is configured.

## Operations

- Logs: `logs/forge.log`, `logs/forge.error.log`, `logs/dlp.log`, `logs/health.log`
- Services: `systemctl status forge`
- Nginx: `/etc/nginx/sites-available/forge`
- Static instructions: `static/instructions/{tool_id}.md|.pdf`
- Backfill missing access tokens: `python3 scripts/generate_access_tokens.py`
