#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T4 $(date) ===" | tee -a logs/t4.log
  claude --dangerously-skip-permissions -p "You are Terminal 4 building the Forge admin interface. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T4_admin.md. Own ONLY: api/admin.py frontend/admin.html frontend/js/admin.js. Admin auth via X-Admin-Key header vs ADMIN_KEY env. Use Chart.js CDN. Run python3 -m py_compile api/admin.py. Mark tasks [x] in tasks/T4_admin.md. Update PROGRESS.md. Never stop. When done write T4 DONE to PROGRESS.md."
  grep -q "T4 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
