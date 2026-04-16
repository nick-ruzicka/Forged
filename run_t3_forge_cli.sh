#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T3-APP $(date) ===" | tee -a logs/t3_forge_cli.log
  claude --dangerously-skip-permissions -p "You are Terminal T3-APP building the Forge CLI. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T3_forge_cli.md in that order. Own: forge_cli/ directory (all files), plus one targeted edit to api/server.py adding POST /api/submit/app endpoint. Do NOT touch any other file. CRITICAL: the /api/submit/app endpoint MUST dispatch the agent pipeline via Celery using celery_app.send_task('agents.tasks.run_pipeline_task', args=[tool_id]) — NOT a raw background thread. This matches /api/tools/submit. CLI must be stdlib-only (argparse + urllib + webbrowser, no external deps). Use venv/bin/python3 and venv/bin/pip. Run venv/bin/python3 -m py_compile on every Python file. Install with venv/bin/pip install -e forge_cli/ and verify venv/bin/forge --version prints 0.1.0. Mark tasks [x] in tasks/T3_forge_cli.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T3-APP DONE to PROGRESS.md."
  grep -q "T3-APP DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
