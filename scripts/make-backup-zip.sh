#!/bin/bash
# Собрать полный ZIP-бэкап проекта (код + последняя копия БД)
set -e
cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d)
OUTDIR="release/blacksquare-crm-${STAMP}"
ZIP="release/blacksquare-crm-backup-${STAMP}.zip"
rm -rf "$OUTDIR"
mkdir -p "$OUTDIR/data"
cp app.py server.py requirements.txt Dockerfile docker-entrypoint.sh .dockerignore \
   .htaccess index.wsgi start.sh start.bat CNAME TIMEWEB.md README.md RESTORE.md "$OUTDIR/"
cp -r templates static dns "$OUTDIR/"
LATEST_DB=$(ls -t backups/blacksquare_*.db 2>/dev/null | head -1)
if [ -n "$LATEST_DB" ]; then
  cp "$LATEST_DB" "$OUTDIR/data/blacksquare_stock_crm_v2.db"
fi
rm -f "$ZIP"
(cd release && zip -r "$(basename "$ZIP")" "$(basename "$OUTDIR")")
rm -rf "$OUTDIR"
echo "Готово: $ZIP ($(du -h "$ZIP" | cut -f1))"
