FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/data/blacksquare_stock_crm_v2.db

WORKDIR /app

RUN echo "TIMEWEB BUILD MARKER: BlackSquare Dockerfile a78+ is being used"

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data && \
    python -m py_compile app.py server.py && \
    echo "TIMEWEB BUILD MARKER: app.py and server.py compiled successfully"

EXPOSE 8000
VOLUME ["/data"]

CMD ["python", "server.py"]
