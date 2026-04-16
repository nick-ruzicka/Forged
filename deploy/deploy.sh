#!/usr/bin/env bash
# Forge deploy — run on every update to pull + migrate + restart.

set -euo pipefail

FORGE_DIR="${FORGE_DIR:-/root/forge}"
cd "$FORGE_DIR"

log() { printf '[deploy] %s\n' "$*"; }

log "Pulling latest..."
git pull --ff-only

log "Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages

log "Running migrations..."
python3 scripts/run_migrations.py

log "Restarting forge..."
systemctl restart forge

log "Deploy complete at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
