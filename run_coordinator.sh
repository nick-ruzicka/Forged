#!/bin/bash
mkdir -p logs
while true; do
  echo "=== COORDINATOR $(date) ===" | tee -a logs/coordinator.log
  claude --dangerously-skip-permissions -p "You are the Forge build coordinator. Do NOT write code. Read PROGRESS.md and all tasks/T*.md files. Then: 1) If any task file has fewer than 3 incomplete tasks add 10 new specific tasks based on SPEC.md. 2) If any terminal appears stuck write UNBLOCKED: solution above that task. 3) Write status summary to PROGRESS.md under COORDINATOR STATUS. Task format: [ ] filename - description"
  sleep 600
done
