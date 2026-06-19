FROM python:3.12

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data

ENV DATABASE_PATH=/data/blacksquare_stock_crm_v2.db \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - app:app"]
