FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/blacksquare_stock_crm_v2.db

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data

EXPOSE 80 8000
VOLUME ["/data"]

CMD ["sh", "-c", "if [ -n \"$PORT\" ] && [ \"$PORT\" != \"80\" ] && [ \"$PORT\" != \"8000\" ]; then EXTRA_BIND=\"--bind 0.0.0.0:$PORT\"; fi; exec gunicorn --bind 0.0.0.0:80 --bind 0.0.0.0:8000 ${EXTRA_BIND:-} --workers ${WEB_CONCURRENCY:-2} --timeout ${GUNICORN_TIMEOUT:-120} app:app"]
