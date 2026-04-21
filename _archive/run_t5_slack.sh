#!/bin/bash
mkdir -p logs
while true; do
  echo "=== T5-APP $(date) ===" | tee -a logs/t5_slack.log
  claude --dangerously-skip-permissions -p "You are Terminal T5-APP building the Slack Deployment Bot for Forge. Read SPEC.md, CONTRACTS.md, PROGRESS.md, tasks/T5_slack_bot.md in that order. Own ONLY: forge_bot/slack_bot.py, forge_bot/start_slack.sh, forge_bot/slack_README.md. T4 owns everything else in forge_bot/ — do NOT touch T4's files (webhook.py, deployer.py, forge.yaml.example, setup.sh, README.md). FIRST task: venv/bin/pip install slack_bolt. Use socket mode for the Slack bot. Use venv/bin/python3 for all commands. Run venv/bin/python3 -m py_compile forge_bot/slack_bot.py. Mark tasks [x] in tasks/T5_slack_bot.md. Update PROGRESS.md after each file. Never stop. When all tasks done append T5-APP DONE to PROGRESS.md."
  grep -q "T5-APP DONE" PROGRESS.md 2>/dev/null && break
  sleep 5
done
