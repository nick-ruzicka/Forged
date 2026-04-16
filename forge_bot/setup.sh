#!/usr/bin/env bash
# forge_bot/setup.sh
#
# Install dependencies, register the webhook as a long-running service, and
# print GitHub App configuration instructions. Safe to re-run.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
PY="${ROOT}/venv/bin/python3"
PIP="${ROOT}/venv/bin/pip"
WEBHOOK_PORT="${FORGE_WEBHOOK_PORT:-8093}"
SERVICE_NAME="forge-webhook"

log() { echo "[forge_bot/setup] $*"; }

# --- git (required to clone repos on push) ---------------------------------
if ! command -v git >/dev/null 2>&1; then
  log "git not found — attempting to install"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y git
  elif command -v brew >/dev/null 2>&1; then
    brew install git
  else
    log "please install git manually and re-run"
    exit 1
  fi
fi

# --- Python deps -----------------------------------------------------------
if [ -x "${PIP}" ]; then
  log "installing Python deps into venv"
  "${PIP}" install --quiet flask python-dotenv pyyaml
else
  log "warning: ${PIP} not found — skipping pip install"
fi

mkdir -p "${HERE}/logs"

# --- service registration --------------------------------------------------
UNAME_S="$(uname -s 2>/dev/null || echo unknown)"

register_systemd() {
  local unit="/etc/systemd/system/${SERVICE_NAME}.service"
  log "writing systemd unit: ${unit}"
  sudo tee "${unit}" >/dev/null <<EOF
[Unit]
Description=Forge GitHub Webhook Receiver
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
EnvironmentFile=${ROOT}/.env
ExecStart=${PY} -m forge_bot.webhook
Restart=always
RestartSec=5
StandardOutput=append:${HERE}/logs/webhook.stdout.log
StandardError=append:${HERE}/logs/webhook.stderr.log

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now "${SERVICE_NAME}"
  log "systemd service '${SERVICE_NAME}' enabled and started"
}

register_launchd() {
  local plist="${HOME}/Library/LaunchAgents/com.forge.webhook.plist"
  log "writing launchd plist: ${plist}"
  mkdir -p "${HOME}/Library/LaunchAgents"
  cat > "${plist}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.forge.webhook</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PY}</string>
        <string>-m</string>
        <string>forge_bot.webhook</string>
    </array>
    <key>WorkingDirectory</key><string>${ROOT}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>${HERE}/logs/webhook.stdout.log</string>
    <key>StandardErrorPath</key><string>${HERE}/logs/webhook.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FORGE_WEBHOOK_PORT</key><string>${WEBHOOK_PORT}</string>
    </dict>
</dict>
</plist>
EOF
  launchctl unload "${plist}" 2>/dev/null || true
  launchctl load "${plist}"
  log "launchd agent loaded"
}

case "${UNAME_S}" in
  Linux*)  register_systemd ;;
  Darwin*) register_launchd ;;
  *)       log "unknown OS (${UNAME_S}) — skipping service registration" ;;
esac

# --- instructions ----------------------------------------------------------
cat <<EOF

===========================================================================
 Forge GitHub auto-deploy webhook is ready.
===========================================================================

 1. Create a GitHub App:
      https://github.com/settings/apps/new

    - Homepage URL:  https://your-forge-host/
    - Webhook URL:   https://your-forge-host:${WEBHOOK_PORT}/webhook
    - Webhook secret: (paste value of GITHUB_WEBHOOK_SECRET from .env)
    - Permissions:
        * Repository -> Contents: Read-only
        * Repository -> Commit statuses: Read & write
        * Repository -> Metadata: Read-only
    - Subscribe to events: "Push"

 2. Install the app on the repos you want auto-deployed.

 3. Local dev tip — expose port ${WEBHOOK_PORT} with ngrok:
      ngrok http ${WEBHOOK_PORT}
    then use the https://*.ngrok.io URL as the webhook URL.

 4. Add forge.yaml to any repo (see forge_bot/forge.yaml.example).

 5. Push to main — the app deploys automatically and a commit status
    'forge/deploy' appears on the commit with a link to the live tool.

 Logs:
    ${HERE}/logs/webhook.log
    ${HERE}/logs/deploy.log
EOF
