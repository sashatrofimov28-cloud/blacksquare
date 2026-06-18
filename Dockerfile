FROM python:3.12-slim

COPY requirements.txt /app/
COPY app.py /app/
COPY templates/ /app/templates/
COPY static/ /app/static/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /app/data \
    && test -f /app/templates/login.html

ENTRYPOINT ["python"]
CMD ["app.py"]

EXPOSE 8000
