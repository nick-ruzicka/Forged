# T1_NEW — Celery Async Pipeline

## Rules
- Own ONLY: celery_app.py, agents/tasks.py, scripts/start_worker.sh, scripts/start_beat.sh, modifications to api/server.py (submit endpoint only) and docker-compose.yml (add services only)
- Do NOT touch code outside those files
- Mark tasks [x] when done, update PROGRESS.md after each change
- Run `venv/bin/python3 -m py_compile` on every Python file edited
- When all tasks done write `T1_NEW DONE` to PROGRESS.md

## Tasks
[x] Install celery redis: `venv/bin/pip install celery[redis] redis`
[x] Create `celery_app.py` in root — Celery app instance using REDIS_URL env var, auto-discover tasks from `agents/`
[x] Create `agents/tasks.py` — Celery task: `run_pipeline_task(tool_id)` that calls `agents/pipeline.run_pipeline(tool_id)`. Decorator: `@celery_app.task(bind=True, max_retries=3)`
[x] Modify `api/server.py` POST `/api/tools/submit` — replace background thread with `celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id])`
[x] Create `scripts/start_worker.sh` — starts Celery worker: `venv/bin/celery -A celery_app worker --loglevel=info --concurrency=4 -l logs/celery.log`
[x] Create `scripts/start_beat.sh` — starts Celery Beat scheduler: `venv/bin/celery -A celery_app beat --loglevel=info`
[x] Add periodic task to `celery_app.py` — run `agents.tasks.self_heal` every 6 hours using celery `beat_schedule`
[x] Create `agents/tasks.py` `self_heal` task — calls `agents/self_healer.SelfHealerAgent().heal_underperforming_tools()`
[x] Test: submit a tool via API, verify it appears as `pending_review`, verify Celery worker log shows pipeline running
[x] Update `docker-compose.yml` — add `celery-worker` and `celery-beat` services

## Smoke Test Evidence (2026-04-16)
- Redis 8.6.2 started locally on :6379
- `bash scripts/start_worker.sh` → worker boots with `[tasks] agents.tasks.run_pipeline_task, agents.tasks.self_heal`
- `POST /api/tools/submit` → `{"id":7,"slug":"celery-smoke-1776312033","status":"pending_review"}`
- `logs/celery.log` shows `Task agents.tasks.run_pipeline_task[...] received` followed by classifier → security_scanner → red_team executing against the Anthropic API (real Claude calls succeeded).
- Tool row transitioned `pending_review` → `agent_reviewing` while the worker was running, confirming the Celery path replaces the in-process thread.

## Cycle 5 Tasks (Celery hardening — v2)

UNBLOCKED: All 10 tasks stay inside T1_NEW ownership (celery_app.py, agents/tasks.py, scripts/start_*.sh, docker-compose.yml additions only). Zero cross-terminal dependency — Redis + Celery worker already live per Cycle 1 smoke test. SPEC references: line 55-60 (Celery never runs in Flask), line 380 (pipeline ALWAYS dispatched to Celery), line 603-610 (Celery Beat every 6h). Suggested pick order: result backend FIRST (unblocks task-status polling) → retry policy → progress signals → priority queues → timeout enforcement → DLQ → autoscale → caching → flower → health endpoint.

[ ] T1_new - celery_app.py - set `result_backend = REDIS_URL + '/1'` (separate DB from broker); configure `result_expires=3600` so polling endpoints can read agent_reviews progress + task state; set `task_track_started=True`.
[ ] T1_new - agents/tasks.py - wrap run_pipeline_task in `autoretry_for=(anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.InternalServerError)` with `retry_backoff=2, retry_backoff_max=60, retry_jitter=True, max_retries=3`; log each retry attempt to logs/celery.log.
[ ] T1_new - agents/tasks.py - emit Celery signal on each pipeline stage completion via `self.update_state(state='PROGRESS', meta={'stage': name, 'progress_pct': pct})` so /api/agent/status/:tool_id can surface live state without DB round-trip.
[ ] T1_new - celery_app.py - define 3 task queues: `high_priority` (security_tier=3 tools), `normal` (tier=2 default), `low` (tier=1 batch/self-heal); `task_routes` map by task name; scripts/start_worker.sh accepts `--queues` arg for per-worker queue subscription.
[ ] T1_new - celery_app.py - per-agent-stage soft/hard timeouts: `task_soft_time_limit=90, task_time_limit=120` as defaults, plus `SOFT_TIMEOUT_PER_STAGE={'classifier':30,'security_scanner':30,'red_team':90,'hardener':60,'qa':90,'synth':45}` read inside agents/tasks.py.
[ ] T1_new - agents/tasks.py - dead-letter queue: on final retry failure, `celery_app.send_task('agents.tasks.handle_dlq', args=[tool_id, error])`; handle_dlq writes agent_reviews row with `status='review_failed', stage_failed=<stage>` and posts to admin alerts log.
[ ] T1_new - agents/tasks.py - idempotency cache: before running pipeline, check Redis key `pipeline:{tool_id}:{prompt_hash}`; if present and <24h old, skip and return cached agent_reviews id; on success SETEX the key. Prevents duplicate dispatch during rapid resubmits.
[ ] T1_new - docker-compose.yml - add `celery-flower` service (mher/flower image, port 5555, BROKER_URL=REDIS_URL, basic-auth via FLOWER_BASIC_AUTH env); mount read-only. For admin-only task monitoring during demo.
[ ] T1_new - scripts/start_worker.sh - add `--autoscale=8,2` (max 8 min 2), `--max-tasks-per-child=100` (prevents memory leaks from long-lived Python processes calling Anthropic SDK), `-Ofair` flag for long-task fairness.
[ ] T1_new - celery_app.py - add custom `celery_app.task` named `healthcheck` that returns `{broker_ok: True, workers: ping_count, beat_last_tick: iso}`; expose via /api/health enhancement (coordinate with T1 backend to call celery.control.ping() with 1s timeout, fall back to broker-only check).
