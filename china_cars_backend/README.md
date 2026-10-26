# Primcom China Cars — Backend

## Обязательно

Перед изменениями и перед эксплуатационными действиями сначала открывайте:

- `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_RUNBOOK.md`
- `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_CHANGELOG.md`

Это основной комплект актуальной документации по архитектуре, сервисам, скрейперу, БД и истории изменений.

Связанные эксплуатационные проекты в этом workspace:

- `/Volumes/SID/Колян АВТО/CSS&HTML Site/manager-listings-bot`
- `/Volumes/SID/Колян АВТО/CSS&HTML Site/primcom-monitor-bot`

## Известные ошибки

- 26.10.2026: в `app/services/import_calculator/config.py` в шкале пошлин для машин до 3 лет нет ступени ЕТТ «свыше 42 300 до 84 500 € — 48%, не менее 7,5 €/см³». Сейчас весь диапазон до 169 000 € считается с минимумом 15 €/см³, поэтому калькулятор завышает пошлину новых машин этой стоимости. Таблица на сайте (`scripts/build-customs-tables.py`) строится из этого файла и повторяет ошибку. Не исправлено: нужны правка конфигурации, тесты калькулятора, перезапуск backend и пересборка таблицы.

## Что внутри проекта

- API: FastAPI + SQLAlchemy async + PostgreSQL
- Скрейперы: `che168`, `dongchedi`, `guazi` (Playwright)
- Изображения: скачивание и хранение в `MEDIA_DIR`
- Переводы: OpenAI и/или translation proxy
- Телеметрия запусков: `scrape_runs`, `raw_listings`
- Ручные карточки Korea/Japan через отдельный `manager-listings-bot`
- Отдельный `primcom-monitor-bot` для контроля `primcom_bot`/`primcom-lead-api`

## Быстрый локальный запуск

1. Скопировать `.env.example` в `.env`.
2. Поднять Postgres (локально через Docker) и установить зависимости.
3. Применить схемы:

```bash
python -m app.scripts.init_db
```

4. Запустить API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

5. Проверить:

```bash
curl -s http://127.0.0.1:8010/health
```

## Скрейпинг

Текущий legacy-раннер:

```bash
python -m app.scripts.scrape_che168 --source guazi --limit 10 --skip-existing --translate-chinese
```

Проверка без записи в БД:

```bash
python -m app.scripts.scrape_che168 --source guazi --limit 10 --dry-run
```

Multi-source runner (альтернативный контур):

```bash
python -m app.jobs.run_ingest --sources che168,dongchedi,guazi --limit 30 --skip-existing --throttle-ms 700
```
