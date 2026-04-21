#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T2_NEW $(date) ===" | tee -a logs/t2_new.log
  claude --dangerously-skip-permissions -p "You are Terminal T2_NEW building the Conversational Tool Creator for Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T2_new.md. Own ONLY: api/creator.py, frontend/creator.html, frontend/js/creator.js, plus targeted modifications to api/server.py (blueprint registration only) and frontend/index.html (one 'Create with AI' button only). Do NOT edit other files. Use Claude Sonnet via the anthropic SDK for generation. Use venv/bin/python3. Mark tasks [x] in tasks/T2_new.md as done. Update PROGRESS.md after each file. Run venv/bin/python3 -m py_compile api/creator.py after edits. Never stop. When all tasks done write T2_NEW DONE to PROGRESS.md."
  grep -q "T2_NEW DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
