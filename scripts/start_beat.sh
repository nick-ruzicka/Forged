#!/usr/bin/env bash
# Start the Forge Celery Beat scheduler (runs periodic tasks like self-healer).
# Reads REDIS_URL from .env (via celery_app.py's dotenv loader).
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p logs

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

exec venv/bin/celery -A celery_app beat \
    --loglevel=info \
    --schedule=logs/celerybeat-schedule \
    --pidfile=logs/celerybeat.pid \
    --logfile=logs/celerybeat.log
