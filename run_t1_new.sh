#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T1_NEW $(date) ===" | tee -a logs/t1_new.log
  claude --dangerously-skip-permissions -p "You are Terminal T1_NEW adding Celery async pipeline to Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T1_new.md. Own ONLY: celery_app.py (root), agents/tasks.py, scripts/start_worker.sh, scripts/start_beat.sh, plus targeted modifications to api/server.py (submit endpoint only) and docker-compose.yml (add services only). Do NOT edit other files. Use venv/bin/python3 and venv/bin/pip. Mark tasks [x] in tasks/T1_new.md as done. Update PROGRESS.md after each file. Run venv/bin/python3 -m py_compile on every Python file. Never stop. When all tasks done write T1_NEW DONE to PROGRESS.md."
  grep -q "T1_NEW DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
