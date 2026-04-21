#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T3 $(date) ===" | tee -a logs/t3.log
  claude --dangerously-skip-permissions -p "You are Terminal 3 building the Forge frontend. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T3_frontend.md. Own ONLY: frontend/css/styles.css frontend/js/api.js frontend/js/utils.js frontend/js/catalog.js frontend/js/tool.js frontend/js/submit.js frontend/js/skills.js frontend/js/my-tools.js frontend/index.html frontend/tool.html frontend/submit.html frontend/skills.html frontend/my-tools.html. Never touch admin files. Vanilla JS no framework. Dark theme accent #0066FF. API base /api. Mark tasks [x] in tasks/T3_frontend.md. Update PROGRESS.md. Never stop. When done write T3 DONE to PROGRESS.md."
  grep -q "T3 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
