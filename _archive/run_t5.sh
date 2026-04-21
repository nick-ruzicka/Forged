#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T5 $(date) ===" | tee -a logs/t5.log
  claude --dangerously-skip-permissions -p "You are Terminal 5 building the Forge deployment system. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T5_deploy.md. Own ONLY: api/deploy.py scripts/generate_instructions.py scripts/generate_pdf.py scripts/slack_notify.py scripts/run_migrations.py scripts/health_check.sh deploy/nginx.conf deploy/forge.service deploy/setup.sh deploy/deploy.sh Dockerfile docker-compose.yml README.md. Wrap WeasyPrint in try/except. Skip Slack if no webhook. Run python3 -m py_compile on Python files. Mark tasks [x] in tasks/T5_deploy.md. Update PROGRESS.md. Never stop. When done write T5 DONE to PROGRESS.md."
  grep -q "T5 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
