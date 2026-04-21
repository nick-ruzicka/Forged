#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T1 $(date) ===" | tee -a logs/t1.log
  claude --dangerously-skip-permissions -p "You are Terminal 1 building the Forge backend. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T1_backend.md in that order. Own ONLY: api/server.py api/db.py api/models.py api/executor.py db/migrations/ db/seed.py. Mark tasks [x] in tasks/T1_backend.md as done. Update PROGRESS.md after each file. Run python3 -m py_compile on each Python file. Never stop. When all tasks done write T1 DONE to PROGRESS.md."
  grep -q "T1 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
