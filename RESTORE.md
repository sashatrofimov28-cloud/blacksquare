# BlackSquare CRM — восстановление из архива

Архив содержит полный код сайта на момент сборки и копию базы данных (если есть в папке `data/`).

## Быстрый запуск локально

```bash
unzip blacksquare-crm-backup-*.zip
cd blacksquare-crm
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_PATH=./data/blacksquare_stock_crm_v2.db
mkdir -p data
# если в архиве есть data/blacksquare_stock_crm_v2.db — база уже на месте
python app.py
```

Откройте http://127.0.0.1:8000  
Логин: `director` / пароль: `blacksquare` (если не меняли на проде).

## Timeweb Cloud (Flask / Docker)

1. Загрузите репозиторий или распакуйте архив в GitHub.
2. App Platform → Flask (или Docker) → репозиторий `blacksquare`, ветка `main`.
3. Порт: `8000`, health: `/healthz`.
4. **Run command (обязательно):** `./docker-entrypoint.sh` — не используйте голый `gunicorn`, иначе контейнер падает и сайт отдаёт пустую страницу.
5. Переменные окружения (из старого приложения):
   - `DATABASE_PATH=/data/blacksquare_stock_crm_v2.db`
   - `FLASK_SECRET_KEY=...`
   - `PUBLIC_BASE_URL=https://blacksquare72.ru`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED=1`
   - `OPENAI_API_KEY` (для голосовых)
   - S3: `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `S3_DB_KEY`
   - Push: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`

База на проде хранится в `/data` и в S3 — при новом сервере восстановите из S3 или из `data/` в этом архиве.

## Восстановить базу вручную

Скопируйте `data/blacksquare_stock_crm_v2.db` в `/data/` на сервере или укажите `DATABASE_PATH` на локальный путь.

## Домен

`blacksquare72.ru`, `www.blacksquare72.ru` — см. `dns/` и `CNAME`.

Сборка архива: автоматически из репозитория BlackSquare CRM.
