#!/bin/sh
set -eu

echo "LAUNCH BlackSquare CRM via python server.py on port ${PORT:-8000}" 1>&2
exec python /app/server.py
