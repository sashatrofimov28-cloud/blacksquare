FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/data/blacksquare_stock_crm_v2.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py server.py templates static ./

RUN mkdir -p /data templates static

EXPOSE 8000

CMD ["python", "server.py"]
