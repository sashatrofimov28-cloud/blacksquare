# BlackSquare CRM

Проект из архива для домена `blacksquare72.ru`. Это не статический сайт, а Flask-приложение на Python с шаблонами, авторизацией и SQLite-базой.

GitHub Pages не запускает Python/Flask, поэтому этот проект нужно размещать на Timeweb-хостинге с поддержкой Python, Timeweb Cloud/VDS или другом Python-хостинге.

## Что внутри

- `app.py` — основное Flask-приложение.
- `server.py` — production-запуск Flask через Waitress для Docker/Timeweb Cloud.
- `templates/` — HTML-шаблоны.
- `static/style.css` — стили.
- `requirements.txt` — зависимости Python.
- `Dockerfile` и `.dockerignore` — запуск в Timeweb Cloud через Docker.
- `.cursor/mcp.json` — подключение Timeweb MCP для деплоя через Cursor/AI-агента.
- `.htaccess` и `index.wsgi` — файлы запуска для Python-хостинга Timeweb через WSGI.
- `CNAME` — домен `blacksquare72.ru` как справочный файл для проекта.
- `release/blacksquare-site.zip` — архив проекта для загрузки на хостинг.

## Логины из исходного архива

Пользователи:

- `director`
- `admin`
- `katya`
- `stas`

Пароль по умолчанию:

```text
blacksquare
```

После публикации обязательно смените пароль/секретный ключ, потому что сайт будет доступен в интернете.

## Локальный запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

После запуска откройте:

```text
http://127.0.0.1:5000
```

## Запуск через Docker

```bash
docker build -t blacksquare-crm .
docker run --rm -p 8000:8000 \
  -e FLASK_SECRET_KEY=change-me \
  -v blacksquare-data:/data \
  blacksquare-crm
```

После запуска откройте:

```text
http://127.0.0.1:8000
```

База SQLite хранится по пути `/data/blacksquare_stock_crm_v2.db`. Для продакшена обязательно подключите постоянный диск/volume к `/data`, иначе данные могут потеряться при пересоздании контейнера.

## Настройка в Timeweb Cloud через Dockerfile

1. В Timeweb Cloud создайте приложение/сервис из GitHub-репозитория.
2. В качестве способа сборки выберите `Dockerfile`.
3. Укажите ветку с Dockerfile. Сейчас Dockerfile находится в ветке:

   ```text
   cursor/static-site-zip-89e3
   ```

   Если выбираете ветку `main`, сначала нужно влить изменения из этой ветки в `main`.
4. Порт приложения: `8000`.
5. Для деплоя через **Dockerfile** отдельного поля «Команда запуска» обычно нет — Timeweb читает `ENTRYPOINT` и `CMD` из Dockerfile.
6. Путь проверки состояния: `/healthz`.
   Откройте **Настройки** → **Настройки деплоя** → **Редактировать** → укажите `/healthz`.
   Если путь пустой или стоит `/`, деплой может падать с ошибкой.
7. Добавьте переменные окружения:

   ```text
   FLASK_SECRET_KEY=случайная_длинная_строка
   DATABASE_PATH=/data/blacksquare_stock_crm_v2.db
   ```

   Переменную `PORT` можно не задавать: Docker-контейнер уже задает `PORT=8000` и `HOST=0.0.0.0`.

8. Подключите постоянный диск/volume к пути:

   ```text
   /app/data
   ```

   Если Timeweb предлагает путь `/data`, тогда задайте переменную `DATABASE_PATH=/data/blacksquare_stock_crm_v2.db`.

9. В настройках домена Timeweb Cloud привяжите `blacksquare72.ru` к этому приложению.
10. Если Timeweb Cloud выдаст CNAME или A-запись, добавьте ее в DNS-зону домена.

## Timeweb MCP в Cursor

В репозитории есть проектная конфигурация `.cursor/mcp.json` для официального MCP-сервера Timeweb Cloud. Токен в репозиторий не добавляется: Cursor передает его из переменной окружения `TIMEWEB_TOKEN`.

1. Создайте API-токен в панели Timeweb Cloud.
2. Добавьте переменную окружения `TIMEWEB_TOKEN` в окружение Cursor/Cloud Agent или локальной оболочки.
3. Перезапустите Cursor или MCP-серверы, чтобы конфигурация перечиталась.
4. Для деплоя можно попросить агента:

   ```text
   Запусти это Flask-приложение в Timeweb Cloud через Dockerfile.
   Репозиторий: sashatrofimov28-cloud/blacksquare
   Ветка: main
   Порт: 8000
   Health check: /healthz
   Переменные: FLASK_SECRET_KEY, DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db
   ```

## Настройка на Timeweb

1. В панели Timeweb убедитесь, что выбран тариф/раздел с поддержкой Python/Flask.
2. Загрузите файлы проекта в папку сайта, обычно `public_html`.
3. Создайте виртуальное окружение `venv` в этой же папке.
4. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

5. Убедитесь, что рядом с `app.py` лежат `.htaccess` и `index.wsgi`.
6. Для `index.wsgi` выставьте права на исполнение:

   ```bash
   chmod 755 index.wsgi
   ```

7. В переменных окружения Timeweb желательно указать:

   ```text
   FLASK_SECRET_KEY=случайная_длинная_строка
   ```

8. Откройте `https://blacksquare72.ru`.

## DNS для домена blacksquare72.ru

Если сайт будет размещен прямо на Timeweb, домен обычно нужно привязать к сайту в панели Timeweb. DNS-записи должны указывать на сервер Timeweb, который выдал хостинг.

Если Timeweb показывает конкретные A/CNAME-записи для вашего хостинга, используйте именно их.

## Как пересобрать ZIP-архив

```bash
zip -r release/blacksquare-site.zip \
  app.py server.py requirements.txt Dockerfile .dockerignore start.bat templates static .htaccess index.wsgi CNAME README.md \
  -x "*.DS_Store" "__pycache__/*" "*.db" "venv/*" ".venv/*"
```
