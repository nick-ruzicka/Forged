#!/bin/bash
# T2-WAVE3 — ForgeData layer. Gated on T1-WAVE3 DONE.
mkdir -p logs
while true; do
  echo "=== T2-WAVE3 $(date) ===" | tee -a logs/t2_wave3.log
  claude --dangerously-skip-permissions -p "You are Terminal T2-WAVE3 building the Forge ForgeData layer (Salesforce connector + /api/forgedata blueprint + seeded dashboard app). First: grep 'T1-WAVE3 DONE' PROGRESS.md — if absent, exit 0 immediately (the loop will retry in 5s). Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T2_forgedata.md. Own ONLY: api/forgedata.py, api/connectors/ (new dir), append-only modification to ForgeAPI injection in api/apps.py (do NOT rewrite existing code — locate the line immediately after the existing 'window.ForgeAPI = {...};' and append the new 'window.ForgeAPI.data = {...}' block), forgedata_bp registration in api/server.py (after learning_bp), new account-health-dashboard seed in db/seed.py, .env.example additions. First task: venv/bin/pip install simple-salesforce. No-creds behavior is NON-NEGOTIABLE: every route must return {error: 'Salesforce not configured', configured: false} when env vars are missing — NOT empty arrays, NOT exceptions. Use venv/bin/python3 for all Python. Run venv/bin/python3 -m py_compile on Python files. Mark tasks [x] in tasks/T2_forgedata.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T2-WAVE3 DONE to PROGRESS.md."
  grep -q "T2-WAVE3 DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
