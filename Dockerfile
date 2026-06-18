FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py server.py start.sh templates static ./

RUN chmod +x /app/start.sh && mkdir -p /app/data

EXPOSE 8000

ENTRYPOINT ["python"]
CMD ["server.py"]
