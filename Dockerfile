FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/blacksquare_stock_crm_v2.db

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
VOLUME ["/data"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
