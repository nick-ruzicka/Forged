#!/bin/bash
# Start the Forge Slack deployment bot in socket mode.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
LOG_DIR="$HERE/logs"
mkdir -p "$LOG_DIR"

cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

exec "$REPO_ROOT/venv/bin/python3" "$HERE/slack_bot.py" >> "$LOG_DIR/slack.log" 2>&1
