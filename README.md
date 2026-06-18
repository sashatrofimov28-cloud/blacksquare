# BlackSquare CRM

Проект из архива для домена `blacksquare72.ru`. Это не статический сайт, а Flask-приложение на Python с шаблонами, авторизацией и SQLite-базой.

GitHub Pages не запускает Python/Flask, поэтому этот проект нужно размещать на Timeweb-хостинге с поддержкой Python, Timeweb Cloud/VDS или другом Python-хостинге.

## Что внутри

- `app.py` — основное Flask-приложение.
- `templates/` — HTML-шаблоны.
- `static/style.css` — стили.
- `requirements.txt` — зависимости Python.
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
  app.py requirements.txt start.bat templates static .htaccess index.wsgi CNAME README.md \
  -x "*.DS_Store" "__pycache__/*" "*.db" "venv/*" ".venv/*"
```
