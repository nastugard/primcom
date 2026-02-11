# Primcom China Cars — Backend (MVP)

Минимальный backend для агрегатора китайских авто:

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 (async)
- Playwright (будет использоваться на следующем этапе)
- Перевод через OpenAI (строго модель `gpt-5-nano` будет подключена на следующем этапе)

## 1) Запуск PostgreSQL

1. Скопируйте `.env.example` в `.env` и при необходимости измените параметры.
2. Запустите БД:

```bash
docker compose --env-file .env up -d
```

## 2) Установка зависимостей

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## 3) Инициализация схемы БД

```bash
python3 -m app.scripts.init_db
```

## 4) Запуск API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Проверка:

- `GET http://127.0.0.1:8010/health`

## 5) Структура данных

Полная DDL-схема: `schema.sql`.

Таблицы:

- `listing_sources`
- `listings`
- `listing_images`
- `listing_price_history`
- `listing_translations`

## 6) Скрейпинг источников

Скрипт импорта:

```bash
python3 -m app.scripts.scrape_che168 --source che168 --limit 30
```

Поддерживаемые источники в `--source`:

- `che168`
- `dongchedi`
- `guazi`

Проверка парсинга без сохранения в БД:

```bash
python3 -m app.scripts.scrape_che168 --source dongchedi --limit 10 --dry-run
python3 -m app.scripts.scrape_che168 --source guazi --limit 10 --dry-run
```
