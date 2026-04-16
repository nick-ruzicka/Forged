#!/bin/bash
set -u
cd "$(dirname "$0")/../.."

mkdir -p tests/reports tests/reports/screenshots

echo "Starting Forge continuous testing suite..."

venv/bin/python3 tests/agents/api_tester.py >> tests/reports/api_tester.log 2>&1 &
echo "API tester PID: $!"

venv/bin/python3 tests/agents/ui_tester.py >> tests/reports/ui_tester.log 2>&1 &
echo "UI tester PID: $!"

venv/bin/python3 tests/agents/code_auditor.py >> tests/reports/auditor.log 2>&1 &
echo "Code auditor PID: $!"

echo "All testers running. Monitor with: tail -f tests/reports/*.log"
echo "View reports: cat tests/reports/api_report.json"
