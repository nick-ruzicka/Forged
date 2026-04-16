#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T2 $(date) ===" | tee -a logs/t2.log
  claude --dangerously-skip-permissions -p "You are Terminal 2 building the Forge agent pipeline. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T2_agents.md. Own ONLY: agents/ scripts/run_pipeline.py scripts/run_self_healer.py. If api/db.py missing stub it. Mark tasks [x] in tasks/T2_agents.md. Update PROGRESS.md after each file. Run python3 -m py_compile on each Python file. Never stop. When all tasks done write T2 DONE to PROGRESS.md."
  grep -q "T2 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
