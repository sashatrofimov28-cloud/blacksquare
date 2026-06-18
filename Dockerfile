FROM python:3.12-slim

COPY . /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data

ENTRYPOINT ["python"]
CMD ["app.py"]

EXPOSE 8000
