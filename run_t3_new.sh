#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T3_NEW $(date) ===" | tee -a logs/t3_new.log
  claude --dangerously-skip-permissions -p "You are Terminal T3_NEW adding Runtime DLP Masking to Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T3_new.md. Own ONLY: api/dlp.py, tests/test_dlp.py, a new migration file db/migrations/002_dlp_runs.sql, plus targeted modifications to api/executor.py (DLP integration only), api/admin.py (analytics stat only), and frontend/js/admin.js (DLP badge only). Do NOT edit other files. Use venv/bin/python3. Mark tasks [x] in tasks/T3_new.md as done. Update PROGRESS.md after each file. Run venv/bin/python3 -m py_compile on every edited Python file and venv/bin/python3 -m pytest tests/test_dlp.py -v after writing tests. Never stop. When all tasks done write T3_NEW DONE to PROGRESS.md."
  grep -q "T3_NEW DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
