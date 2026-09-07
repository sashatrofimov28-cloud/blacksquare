#!/bin/sh
set -eu

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
DATABASE_PATH="${DATABASE_PATH:-/app/data/blacksquare_stock_crm_v2.db}"
export TZ="${TZ:-Asia/Yekaterinburg}"
export APP_TZ="${APP_TZ:-Asia/Yekaterinburg}"

mkdir -p "$(dirname "$DATABASE_PATH")"
export DATABASE_PATH

# Не валим весь контейнер из-за S3, если локальная база уже есть
if ! python3 scripts/restore_db_from_s3.py; then
  if [ -s "$DATABASE_PATH" ]; then
    echo "S3 restore failed, continuing with existing database: $DATABASE_PATH" >&2
  else
    echo "S3 restore failed and database missing: $DATABASE_PATH" >&2
    exit 1
  fi
fi

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
