#!/usr/bin/env bash
# Forge VPS setup — run once on a fresh Hetzner/Ubuntu server as root.
#
# Provisions Python, PostgreSQL, Redis, nginx; installs dependencies;
# runs migrations; installs the forge systemd unit; reloads nginx.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/nick-ruzicka/forge-platform.git}"
FORGE_DIR="${FORGE_DIR:-/root/forge}"
PG_USER="${PG_USER:-forge}"
PG_PASS="${PG_PASS:-forge}"
PG_DB="${PG_DB:-forge}"

log() { printf '[setup] %s\n' "$*"; }

log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    python3 python3-pip python3-venv \
    nginx git curl \
    redis-server \
    postgresql postgresql-contrib \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    weasyprint

if [ ! -d "$FORGE_DIR/.git" ]; then
    log "Cloning repo to $FORGE_DIR..."
    git clone "$REPO_URL" "$FORGE_DIR"
fi

cd "$FORGE_DIR"
mkdir -p logs data static/instructions

log "Installing Python dependencies..."
pip3 install -r requirements.txt --break-system-packages

log "Configuring PostgreSQL..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$PG_USER'" \
    | grep -q 1 || sudo -u postgres createuser "$PG_USER"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" \
    | grep -q 1 || sudo -u postgres createdb "$PG_DB" -O "$PG_USER"
sudo -u postgres psql -c \
    "ALTER USER $PG_USER WITH PASSWORD '$PG_PASS';"

if [ ! -f "$FORGE_DIR/.env" ]; then
    log "Creating .env from template..."
    cat > "$FORGE_DIR/.env" <<ENV
DATABASE_URL=postgresql://$PG_USER:$PG_PASS@localhost:5432/$PG_DB
REDIS_URL=redis://localhost:6379/0
FORGE_HOST=http://localhost
ADMIN_KEY=change-me
ANTHROPIC_API_KEY=
SLACK_WEBHOOK_URL=
ENV
    log "Edit $FORGE_DIR/.env before restarting services."
fi

log "Running migrations..."
DATABASE_URL="postgresql://$PG_USER:$PG_PASS@localhost:5432/$PG_DB" \
    python3 scripts/run_migrations.py

log "Installing nginx config..."
cp "$FORGE_DIR/deploy/nginx.conf" /etc/nginx/sites-available/forge
ln -sf /etc/nginx/sites-available/forge /etc/nginx/sites-enabled/forge
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

log "Installing systemd unit..."
cp "$FORGE_DIR/deploy/forge.service" /etc/systemd/system/forge.service
systemctl daemon-reload
systemctl enable forge
systemctl restart forge

log "Setup complete."
log "Forge is live at: http://$(hostname -I | awk '{print $1}')"
