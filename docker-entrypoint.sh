#!/bin/sh
set -eu

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
DATABASE_PATH="${DATABASE_PATH:-/app/data/blacksquare_stock_crm_v2.db}"
export TZ="${TZ:-Europe/Moscow}"
export APP_TZ="${APP_TZ:-Europe/Moscow}"

mkdir -p "$(dirname "$DATABASE_PATH")"
export DATABASE_PATH

python3 scripts/restore_db_from_s3.py || exit 1

echo "LAUNCH BlackSquare CRM host=${HOST} port=${PORT} database=${DATABASE_PATH} tz=${TZ}" >&2

python -c "from app import app, today, now; print('IMPORT OK BlackSquare CRM', 'today='+today(), 'now='+now(), flush=True)" >&2

exec python -m gunicorn \
  --bind "${HOST}:${PORT}" \
  --workers 1 \
  --threads 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  app:app
