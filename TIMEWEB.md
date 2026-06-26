# Деплой на Timeweb Cloud

## Если старый деплой постоянно падает

Удалять GitHub-репозиторий **не нужно**. Проще создать **новое** приложение в Timeweb:

1. Timeweb Cloud → **App Platform** → **Создать приложение**
2. Тип: **Dockerfile**
3. Репозиторий: `sashatrofimov28-cloud/blacksquare`
4. Ветка: `main`
5. Порт: `8000`
6. Путь проверки состояния: можно оставить пустым или указать `/healthz`
7. Поле «Путь к директории проекта» — **пустое**
8. Запустить деплой

Старое приложение **Wild Lacerta** можно удалить после успешного запуска нового.

## Настройки

| Параметр | Значение |
|----------|----------|
| Ветка | `main` |
| Порт | `8000` |
| Автодеплой | выключен в панели — после push в `main` нужен ручной деплой (см. ниже) |

## Если изменения не появились на сайте

На Timeweb **App Platform** → приложение **BlackSquare CRM Mobile** → вкладка **Деплой** → **Запустить деплой** (ветка `main`, последний коммит).

Либо попросите агента запустить деплой через API.
| Путь проверки | пусто или `/healthz` |
| Команда запуска | не нужна (берётся из Dockerfile) |

## Timeweb MCP

В проект добавлен `.cursor/mcp.json` для официального MCP-сервера Timeweb Cloud:

```json
{
  "mcpServers": {
    "timeweb": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "timeweb-mcp-server"],
      "env": {
        "TIMEWEB_TOKEN": "${env:TIMEWEB_TOKEN}"
      }
    }
  }
}
```

Перед использованием добавьте токен Timeweb Cloud в переменную окружения `TIMEWEB_TOKEN` в Cursor/Cloud Agent или локальной оболочке. Сам токен нельзя коммитить в репозиторий.

Подходящий запрос агенту:

```text
Запусти это Flask-приложение в Timeweb Cloud через Dockerfile.
Репозиторий: sashatrofimov28-cloud/blacksquare
Ветка: main
Порт: 8000
Health check: /healthz
Переменные: FLASK_SECRET_KEY, DATABASE_PATH=/app/data/blacksquare_stock_crm_v2.db
```

## После успешного деплоя

- Сайт: `https://blacksquare72.ru`
- Логин: `director`
- Пароль: `blacksquare`

## Локальная проверка

```bash
pip install -r requirements.txt
python app.py
```

Откройте `http://127.0.0.1:8000`.
