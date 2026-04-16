#!/bin/bash
# T1-WAVE3 — Docker sandbox. Runs the agent in a self-restarting loop until T1-WAVE3 DONE.
# Colima socket override: Docker SDK / docker CLI default to /var/run/docker.sock,
# but colima on macOS puts the socket at ~/.colima/default/docker.sock.
# Exporting DOCKER_HOST here so every subprocess inherits it without sudo symlinks.
export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"

mkdir -p logs
while true; do
  echo "=== T1-WAVE3 $(date) ===" | tee -a logs/t1_wave3.log
  claude --dangerously-skip-permissions -p "You are Terminal T1-WAVE3 building the Forge Docker sandbox. DOCKER_HOST is already exported ($DOCKER_HOST) — colima provides the daemon. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T1_docker_sandbox.md in that order. Preflight: run 'docker version' — if the daemon is not reachable, append 'T1-WAVE3 BLOCKED: docker daemon unreachable' to PROGRESS.md and exit. Own ONLY: forge_sandbox/ (new dir), db/migrations/006_sandbox.sql, surgical additions to api/apps.py (container proxy branch only), new sandbox admin routes in api/server.py, additive entry in celery_app.py beat_schedule, scripts/run_migrations.py invocation. Use venv/bin/python3 and venv/bin/pip. Run venv/bin/python3 -m py_compile on every Python file. Mark tasks [x] in tasks/T1_docker_sandbox.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T1-WAVE3 DONE to PROGRESS.md."
  grep -q "T1-WAVE3 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
