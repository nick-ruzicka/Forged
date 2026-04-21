#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T6 $(date) ===" | tee -a logs/t6.log
  claude --dangerously-skip-permissions -p "You are Terminal 6 writing tests for Forge. Read CONTRACTS.md, PROGRESS.md, tasks/T6_testing.md and all files in api/ and agents/. Own ONLY: tests/ directory. Mock all Claude API calls. If tested file missing write test anyway with comment. Mark tasks [x] in tasks/T6_testing.md. Update PROGRESS.md. Never stop. When done write T6 DONE to PROGRESS.md."
  grep -q "T6 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
