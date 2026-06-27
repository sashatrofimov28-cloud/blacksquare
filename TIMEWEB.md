# Деплой BlackSquare CRM на Timeweb Cloud

## Продакшен (текущий)

| Параметр | Значение |
|----------|----------|
| Приложение | **BlackSquare CRM Prod** (ID `215409`) |
| Регион | Москва (`msk-1`) |
| Домен | **https://blacksquare72.ru** |
| IP | `85.239.37.243` |
| Ветка | `main` |
| Порт | `8000` |
| Health check | `/healthz` |
| **Run command** | `./docker-entrypoint.sh` |

### Важно

Timeweb для Flask по умолчанию подставляет `gunicorn main:app` — **так нельзя**: контейнер падает, сайт отдаёт пустую страницу.

В настройках приложения → **Команда запуска** должно быть:

```bash
./docker-entrypoint.sh
```

Файл `main.py` в репозитории добавлен как запасной вариант (`gunicorn main:app`), но S3-восстановление БД работает только через `docker-entrypoint.sh`.

### Переменные окружения

- `PUBLIC_BASE_URL=https://blacksquare72.ru`
- `DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db`
- `FLASK_SECRET_KEY`, `PORT=8000`
- S3: `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `S3_DB_KEY`
- Telegram, OpenAI, VAPID — как в панели

### DNS (Timeweb → Домены → blacksquare72.ru)

- **A** `@` → IP приложения, **привязать к сервису** BlackSquare CRM Prod
- **A** `www` → тот же IP (редирект на основной домен в приложении)

### После push в `main`

App Platform → BlackSquare CRM Prod → **Деплой** → запустить с последним коммитом `main`.

## Локальная проверка

```bash
pip install -r requirements.txt
export DATABASE_PATH=./data/blacksquare_stock_crm_v2.db
./docker-entrypoint.sh
```

Откройте http://127.0.0.1:8000 — логин `director` / `blacksquare`.

## Ссылки

- Сотрудники: https://blacksquare72.ru/login
- Онлайн-запись: https://blacksquare72.ru/booking
