#!/usr/bin/env bash
# Forge health check — verifies Flask API, PostgreSQL, and Redis.
# Exits 0 if all healthy, 1 otherwise. Appends a line to logs/health.log.

set -u

FORGE_DIR="${FORGE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$FORGE_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/health.log"

API_URL="${FORGE_HEALTH_URL:-http://127.0.0.1:8090/api/health}"
PG_HOST="${PGHOST:-localhost}"
PG_PORT="${PGPORT:-5432}"
PG_USER="${PGUSER:-forge}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

api_status="unknown"
if code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$API_URL"); then
    if [ "$code" = "200" ]; then
        api_status="ok"
    else
        api_status="http_$code"
    fi
else
    api_status="unreachable"
fi

pg_status="unknown"
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" >/dev/null 2>&1; then
        pg_status="ok"
    else
        pg_status="down"
    fi
else
    pg_status="pg_isready_missing"
fi

redis_status="unknown"
if command -v redis-cli >/dev/null 2>&1; then
    if [ "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null)" = "PONG" ]; then
        redis_status="ok"
    else
        redis_status="down"
    fi
else
    redis_status="redis_cli_missing"
fi

line="$(now) api=$api_status postgres=$pg_status redis=$redis_status"
echo "$line" >> "$LOG_FILE"
echo "$line"

if [ "$api_status" = "ok" ] && [ "$pg_status" = "ok" ] && [ "$redis_status" = "ok" ]; then
    exit 0
fi
exit 1
