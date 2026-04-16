# Forge Sandbox (Tier 2)

Per-app Docker containers for Forge apps that outgrow the Tier 1 "HTML in DB"
path. Containers are hibernated after 10 minutes of idle and pre-warmed for
hot tools. The platform agent always runs **outside** the container; all
state flows through the existing PostgreSQL-backed ForgeAPI.

---

## Two serving tiers

| Tier | `container_mode` | What happens on `GET /apps/<slug>` |
| ---- | ---------------- | ---------------------------------- |
| Tier 1 (default) | `FALSE` | Flask reads `tools.app_html` from Postgres and injects ForgeAPI inline. |
| Tier 2 (new)     | `TRUE`  | `SandboxManager().ensure_running(tool_id)` builds/starts an `nginx:alpine` container on a free port in `9000-9999`, Flask proxies the upstream HTML, and injects ForgeAPI before `</body>`. |

The Tier 1 code path is untouched. Flipping `container_mode` back to `FALSE`
returns that app to the DB-served path with no other changes required.

---

## Enable container mode for a tool

Admin-only. The endpoint builds the image before flipping the flag so the
first user request doesn't pay the build cost.

```bash
curl -X POST http://localhost:8090/api/admin/tools/<TOOL_ID>/enable-container \
  -H "X-Admin-Key: $ADMIN_KEY"
# → {"success": true, "tool_id": N, "image_tag": "forge-app-<slug>:latest"}
```

Admin operations:

| Endpoint | Purpose |
| -------- | ------- |
| `GET  /api/admin/sandbox/status` | List running/stopped containers, aggregated memory. |
| `POST /api/admin/sandbox/hibernate/<tool_id>` | Stop a running container. |
| `POST /api/admin/sandbox/prewarm/<tool_id>` | Boot a stopped container whose `image_tag` is already built. |
| `POST /api/admin/tools/<tool_id>/enable-container` | Build image + set `container_mode=TRUE`. |

All four require `X-Admin-Key`.

---

## Resource limits

Every container is run with:

- `--memory=256m`
- `--cpus=0.5`
- `--network=bridge`

These match the "small VPS" intent in SPEC.md; raise only with explicit
approval.

---

## Hibernate policy

- **Idle threshold:** 10 minutes without a `GET /apps/<slug>` hit. The
  Flask handler stamps `last_request_at = NOW()` on every request.
- **Sweep cadence:** `forge_sandbox.tasks.hibernate_idle` runs every 5
  minutes via Celery Beat (see `celery_app.py`).
- **Ad-hoc sweep:** `venv/bin/python3 -m forge_sandbox.hibernator` runs the
  same idle sweep synchronously and then pre-warms any stopped container
  whose parent tool has `run_count > 10`.

A hibernated container is restarted on the next `/apps/<slug>` hit.

---

## Pre-warm rule

`pre_warm(tool_id)` starts a container only when:

1. `image_tag IS NOT NULL` (image was previously built), AND
2. `container_status = 'stopped'`.

The `hibernator` CLI pre-warms every `container_mode=TRUE AND run_count > 10
AND container_status='stopped'` row after the idle sweep.

---

## Environment

Docker runtime is **colima**. Every subprocess call inherits
`DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` from the runner
script. Do **not** hardcode the socket path in Python or fall back to
`/var/run/docker.sock`.

---

## Logs

All build/lifecycle events are appended to `logs/sandbox.log` with ISO-UTC
timestamps. Grep by `tool_id=` or `slug=` to trace a single app.
