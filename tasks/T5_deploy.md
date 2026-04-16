# T5 DEPLOY TASKS
## Rules
- Own ONLY: api/deploy.py, scripts/generate_instructions.py, scripts/generate_pdf.py, scripts/slack_notify.py, scripts/run_migrations.py, scripts/health_check.sh, deploy/nginx.conf, deploy/forge.service, deploy/setup.sh, deploy/deploy.sh, Dockerfile, docker-compose.yml, README.md
- Wrap WeasyPrint in try/except, skip PDF if not installed
- Skip Slack if no webhook configured
- Mark [x] done, update PROGRESS.md

## Tasks
[x] api/deploy.py - deploy_tool(tool_id): generate UUID access_token, build endpoint_url=FORGE_HOST+/tools/+slug, build shareable_url=FORGE_HOST+/t/+access_token, call generate_instructions_content(tool) save to static/instructions/{id}.md, try generate_pdf skip if fails, update tool record deployed=true/deployed_at/endpoint_url/access_token/instructions_url, try send_slack_announcement skip if fails. Return {success, endpoint_url, access_token, shareable_url, instructions_url}.
[x] scripts/generate_instructions.py - generate_instructions_content(tool_dict) calls Claude to write Markdown usage guide: title, what it does, access URL, field-by-field instructions, output explanation with trust tier, when to use, limitations, contact. Returns Markdown string. CLI: python3 scripts/generate_instructions.py --tool-id 123.
[x] scripts/generate_pdf.py - generate_pdf(tool_id, markdown_content). try import weasyprint except ImportError log warning return None. Convert to HTML with Forge header/footer. WeasyPrint to PDF. Save to static/instructions/{id}.pdf. Return path.
[x] scripts/slack_notify.py - send_slack_announcement(tool_dict). If no SLACK_WEBHOOK_URL return False. POST blocks: header with tool name, tagline, trust tier + category + author fields, Run and Instructions action buttons. Return True if 200.
[x] deploy/nginx.conf - listen 80. location / serves frontend/ with SPA try_files. location /api/ proxies localhost:8090. location /static/ serves static/ files. location /t/ proxies localhost:8090.
[x] deploy/forge.service - systemd unit. ExecStart=python3 api/server.py. WorkingDirectory=/root/forge. EnvironmentFile=/root/forge/.env. Restart=always. Logs to logs/.
[x] deploy/setup.sh - apt install python3 pip nginx git redis postgresql. pip3 install -r requirements.txt --break-system-packages. PostgreSQL create user+db forge. Clone repo. Copy .env.example. Run migrations. Copy nginx and service configs. Enable services. Print URL.
[x] deploy/deploy.sh - git pull, pip3 install, run_migrations.py, systemctl restart forge, echo deployed.
[x] scripts/run_migrations.py - forge_migrations table tracks run files. Read db/migrations/*.sql alphabetically. Skip already run. Run new in transactions. Print which ran.
[x] scripts/health_check.sh - curl localhost:8090/api/health, pg_isready, redis-cli ping. Write to logs/health.log. Exit 0 if healthy.
[x] Dockerfile - python:3.11-slim, WORKDIR /app, COPY+install requirements, COPY ., mkdir logs data static/instructions, EXPOSE 8090, CMD python3 api/server.py.
[x] docker-compose.yml - services: forge-app (build, 8090:8090, env_file, volumes logs+static, depends_on postgres+redis), postgres (postgres:15, POSTGRES_USER/PASSWORD/DB=forge, volume), redis (redis:7-alpine). volumes: postgres_data.
[x] scripts/generate_access_tokens.py - idempotent: for approved deployed tools with null access_token generate UUID and update.
[x] README.md - Prerequisites, Local Dev (docker-compose up), VPS Deploy, Environment Variables table, Submit First Tool walkthrough, Admin Access, Architecture Overview.

## Cycle 2 Tasks (production readiness)

CYCLE 11 HUMAN-RESCUE REQUIRED (2026-04-16): .env.example append is now **4 cycles overdue** (C8, C9, C10, C11 all passed with no pickup). Per Cycle 10 "any reviewer may append" authorization, Cycle 11 escalates to human operator. Paste these 4 lines at the end of `.env.example` (file currently ends after `FORGE_WEBHOOK_PORT=8093`):

```
# --- Slack bot (forge_bot/slack_bot.py) ---
SLACK_BOT_TOKEN=xoxb-
SLACK_APP_TOKEN=xapp-
# --- Slack announcements (scripts/slack_notify.py, outbound #forge-releases) ---
SLACK_WEBHOOK_URL=
# --- Flask ---
FLASK_ENV=production
```

~30-second edit. Unblocks every Slack integration test path and closes T5_slack_bot line-33 SKIPPED note. After append, mark task 34 below [x] and delete this CYCLE 11 header.

UNBLOCKED: SEVEN of 10 tasks below are zero-dependency — start immediately without waiting on any other terminal: .env.example (line 31), scripts/backup_db.sh (27), scripts/restore_db.sh (28), deploy/logrotate.conf (29), scripts/rollback.sh (30), deploy/setup-https.sh (32), README.md ops section (34). Suggested pick order: .env.example FIRST (unblocks every setup flow) → backup/restore → logrotate → rollback → setup-https → docker-compose.prod.yml → README. The two celery service units (lines 25-26) depend on T2 exposing a celery-compatible entrypoint — currently T2 pipeline is thread-based. Write the service units anyway using `celery -A agents.pipeline` as the ExecStart; T2 will wrap run_pipeline() as a @celery.task decorator in a follow-up. No blocker for drafting the unit files today.

[ ] deploy/celery-worker.service - systemd unit. ExecStart=/usr/bin/celery -A agents.pipeline worker --loglevel=info --concurrency=2. WorkingDirectory=/root/forge. EnvironmentFile=/root/forge/.env. After=redis.service postgresql.service. Restart=always. Logs to logs/celery-worker.log.
[ ] deploy/celery-beat.service - systemd unit. ExecStart=/usr/bin/celery -A agents.pipeline beat --loglevel=info. Schedules self-healer every 6h per SPEC line 603-610. WorkingDirectory=/root/forge. EnvironmentFile. Restart=always. Logs to logs/celery-beat.log.
[ ] scripts/backup_db.sh - pg_dump -U forge forge > backups/forge-$(date +%Y%m%d-%H%M%S).sql. ls -t backups/forge-*.sql | tail -n +8 | xargs rm -f (keep 7). Log to logs/backup.log. Designed for nightly cron.
[ ] scripts/restore_db.sh - arg=$1 backup file. Prompt "Restoring will OVERWRITE forge db, type YES to confirm". dropdb + createdb + psql < $1. Log to logs/restore.log.
[ ] deploy/logrotate.conf - /root/forge/logs/*.log { daily; rotate 14; compress; delaycompress; missingok; notifempty; copytruncate; }. Covers forge.log, agents.log, dlp.log, self_healer.log, celery-*.log.
[ ] scripts/rollback.sh - arg=$1 target SHA. git fetch && git reset --hard $1. pip3 install -r requirements.txt. systemctl restart forge forge-worker forge-beat. echo rollback complete. Log to logs/rollback.log.
[ ] .env.example - committed template: DATABASE_URL=postgresql://forge:forge@localhost/forge, REDIS_URL=redis://localhost:6379/0, ANTHROPIC_API_KEY=sk-ant-..., ADMIN_KEY=change-me, FORGE_HOST=http://localhost:8090, SLACK_WEBHOOK_URL=, FLASK_ENV=production. Include comments describing each.
[ ] deploy/setup-https.sh - apt install certbot python3-certbot-nginx. certbot --nginx -d $FORGE_DOMAIN --non-interactive --agree-tos -m $ADMIN_EMAIL. Add systemctl enable certbot.timer for auto-renewal. Verify nginx reload.
[ ] docker-compose.prod.yml - production override (extends base): forge-app uses gunicorn -w 4 (not python3 direct), restart: always, healthcheck on /api/health, no code volume mount, DATABASE_URL points to external managed PG via env. Add forge-worker + forge-beat services.
[ ] README.md - append Operations section: backup/restore procedures, log file locations and rotation, self-healer monitoring (logs/self_healer.log + admin panel), incident runbook (rollback, DB restore, redis flush), env var rotation steps.
