FROM python:3.12

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data

ENV DATABASE_PATH=/data/blacksquare_stock_crm_v2.db \
    PORT=8000 \
    TZ=Europe/Moscow \
    APP_TZ=Europe/Moscow

EXPOSE 8000

RUN chmod +x docker-entrypoint.sh scripts/restore_db_from_s3.py

ENTRYPOINT ["./docker-entrypoint.sh"]
