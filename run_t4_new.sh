#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T4_NEW $(date) ===" | tee -a logs/t4_new.log
  claude --dangerously-skip-permissions -p "You are Terminal T4_NEW adding Tool Composability v1 (chained workflows) to Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T4_new.md. Own ONLY: api/workflow.py, frontend/workflow.html, frontend/js/workflow.js, tests/test_workflow.py, a new migration file db/migrations/003_workflow_steps.sql, plus targeted modifications to api/server.py (blueprint registration only) and frontend/index.html (one 'Chain Tools' link only). Do NOT edit other files. Use venv/bin/python3. Mark tasks [x] in tasks/T4_new.md as done. Update PROGRESS.md after each file. Run venv/bin/python3 -m py_compile api/workflow.py after edits and venv/bin/python3 -m pytest tests/test_workflow.py -v after writing tests. Never stop. When all tasks done write T4_NEW DONE to PROGRESS.md."
  grep -q "T4_NEW DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
