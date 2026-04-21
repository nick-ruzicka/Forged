#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T1-APP $(date) ===" | tee -a logs/t1_app.log
  claude --dangerously-skip-permissions -p "You are Terminal T1-APP building the App Platform backend for Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T1_app_platform.md in that order. Own ONLY: db/migrations/004_apps.sql, api/apps.py, db/seed.py (add 3 app seeds), plus one targeted edit to api/server.py to register apps_bp. Do NOT touch any other file. CRITICAL: the migration filename must be 004_apps.sql (002 and 003 are taken). Use venv/bin/python3 and venv/bin/pip. Run venv/bin/python3 -m py_compile on every Python file. Mark tasks [x] in tasks/T1_app_platform.md. Update PROGRESS.md after each file. Verify end-to-end that /apps/job-search-pipeline, /apps/meeting-prep, /apps/pipeline-velocity all return 200. Never stop. When all tasks done append T1-APP DONE to PROGRESS.md."
  grep -q "T1-APP DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
