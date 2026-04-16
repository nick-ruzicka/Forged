#!/usr/bin/env bash
# Start the Forge Celery worker.
# Reads REDIS_URL from .env (via celery_app.py's dotenv loader).
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p logs

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

exec venv/bin/celery -A celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    -n forge-worker@%h \
    --logfile=logs/celery.log
