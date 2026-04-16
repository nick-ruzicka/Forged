#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T2-APP $(date) ===" | tee -a logs/t2_app.log
  claude --dangerously-skip-permissions -p "You are Terminal T2-APP building the App Frontend for Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T2_app_frontend.md in that order. Own: frontend/index.html (additions only), frontend/js/catalog.js, frontend/submit.html, frontend/js/submit.js, frontend/tool.html, frontend/css/styles.css. Do NOT touch backend or any other terminal's files. CRITICAL security requirement: every iframe loading /apps/<slug> MUST have attribute sandbox='allow-scripts allow-forms allow-modals' (NO allow-same-origin). This applies to the app modal iframe, submit.html live preview iframe, and tool.html app-detail iframe. Use venv/bin/python3 for any Python commands. Mark tasks [x] in tasks/T2_app_frontend.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T2-APP DONE to PROGRESS.md."
  grep -q "T2-APP DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
