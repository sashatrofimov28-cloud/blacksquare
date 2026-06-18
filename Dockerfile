FROM python:3.12

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /app/data

ENV DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db

ENTRYPOINT ["python"]
CMD ["app.py"]

EXPOSE 8000
