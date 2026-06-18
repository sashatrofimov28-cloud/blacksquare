#!/bin/sh
set -eu

exec gunicorn \
  --bind 0.0.0.0:8000 \
  --workers "${WEB_CONCURRENCY:-1}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  app:app
