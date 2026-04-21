#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T4-APP $(date) ===" | tee -a logs/t4_github.log
  claude --dangerously-skip-permissions -p "You are Terminal T4-APP building the GitHub App / Auto-Deploy integration for Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T4_github_app.md in that order. Own: forge_bot/ directory EXCEPT forge_bot/slack_bot.py, forge_bot/start_slack.sh, forge_bot/slack_README.md (those are T5's). Also one targeted edit to api/server.py adding POST /api/admin/tools/<id>/update-html endpoint. Do NOT touch any other file. CRITICAL: the webhook Flask app MUST listen on port 8093 (NOT 8091 — that port is taken by the test dashboard). FIRST task: venv/bin/pip install pyyaml (required for forge.yaml parsing). Use hmac.compare_digest for timing-safe webhook signature verification. Use venv/bin/python3 for all commands. Run venv/bin/python3 -m py_compile on every Python file. Mark tasks [x] in tasks/T4_github_app.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T4-APP DONE to PROGRESS.md."
  grep -q "T4-APP DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
