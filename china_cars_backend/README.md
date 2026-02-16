# Primcom China Cars — Backend v2

Backend v2 для агрегатора китайских авто:

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 (async)
- Playwright (che168/dongchedi/guazi)
- Перевод через OpenAI (`gpt-5-nano`) с DB-кэшем `translation_cache`
- Run telemetry в `scrape_runs`

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

DDL-схемы:
- `schema.sql` (legacy core)
- `schema_v2.sql` (run telemetry, translation cache, canonical layer)

Таблицы:

- `listing_sources`
- `listings`
- `listing_images`
- `listing_price_history`
- `listing_translations`

## 6) Скрейпинг источников

Скрипт импорта v2:

```bash
python3 -m app.jobs.run_ingest --sources che168,dongchedi,guazi --limit 30 --skip-existing --throttle-ms 700
```

Поддерживаемые источники:

- `che168`
- `dongchedi`
- `guazi`

Проверка парсинга без сохранения в БД:

```bash
python3 -m app.scripts.scrape_che168 --source dongchedi --limit 10 --dry-run
python3 -m app.scripts.scrape_che168 --source guazi --limit 10 --dry-run
```
