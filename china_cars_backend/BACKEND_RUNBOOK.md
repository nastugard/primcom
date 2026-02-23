# Primcom Backend Runbook

Дата актуализации: 2026-02-23

Этот документ является основным источником знаний по бэкенду `china_cars_backend`.
Перед любыми правками кода нужно читать этот runbook и релевантные секции.
После любых правок runbook должен быть обновлен в той части, которую затронули изменения.
Историю изменений смотреть в `BACKEND_CHANGELOG.md`.

## 1. Назначение проекта

Бэкенд обслуживает каталог авто на сайте Primcom:

- API каталога и деталей карточек.
- Скрейпинг объявлений из внешних источников.
- Загрузка и хранение изображений.
- Нормализация данных и перевод китайских названий.
- Ручное добавление карточек (Korea/Japan) через manager endpoint.
- Логирование запусков скрейпера (`scrape_runs`) и raw-данных (`raw_listings`).

## 2. Текущий рабочий контур

В проекте есть два набора deploy-файлов:

- `deploy/hostvds/*` - текущий основной (legacy) контур.
- `deploy/hostvds-v2/*` - альтернативный контур миграции.

На сервере, где установлены только:

- `primcom-api.service`
- `primcom-scraper.service`
- `primcom-scraper.timer`

используется именно `deploy/hostvds/*`.

Важно:

- `cv6067041.novalocal` в логах systemd - это hostname машины, а не отдельный сервис.
- Отсутствие `primcom-api-v2.service` и `primcom-scraper-v2.service` в `systemctl` означает, что v2 контур не активирован.

## 3. Быстрая карта кода

Основные entrypoints:

- API приложение: `app/main.py`
- API роуты: `app/api/routes.py`
- DB engine/session: `app/db.py`
- Конфиг: `app/core/settings.py` и реэкспорт `app/settings.py`
- Инициализация БД: `app/scripts/init_db.py`

Скрейпинг:

- Legacy runner (используется `primcom-scraper.service`): `app/scripts/scrape_che168.py`
- Multi-source runner (используется только в v2 контуре): `app/jobs/run_ingest.py`
- Сервис ingestion для v2 runner: `app/services/ingest.py`
- Скрейперы источников:
  - `app/scrapers/che168.py`
  - `app/scrapers/dongchedi.py`
  - `app/scrapers/guazi.py`

Работа с БД:

- Репозиторий листингов/изображений: `app/storage/repository.py`
- Репозиторий telemetry/translation cache: `app/repositories/catalog.py`
- Канонический слой марки/модели: `app/services/canonical.py`

Утилиты:

- Скачивание и перекодирование картинок: `app/utils/media.py`
- Словари перевода брендов/моделей: `app/utils/name_translation.py`

## 4. Как запускается API

1. systemd запускает `primcom-api.service`:
   - `deploy/hostvds/primcom-api.service`
2. Процесс:
   - `uvicorn app.main:app --host 127.0.0.1 --port 8010`
3. `app/main.py`:
   - поднимает FastAPI;
   - монтирует `/media` из `settings.media_dir`;
   - подключает роутер из `app/api/routes.py`.

Проверка:

```bash
curl -s http://127.0.0.1:8010/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## 5. Как запускается скрейпер (текущий production-путь)

Цепочка запуска:

1. `primcom-scraper.timer` по расписанию (`05:00`) дергает
2. `primcom-scraper.service`, который выполняет
3. `deploy/hostvds/run_scrape.sh`, который запускает
4. `python -m app.scripts.scrape_che168 ...`

Файлы:

- `deploy/hostvds/primcom-scraper.timer`
- `deploy/hostvds/primcom-scraper.service`
- `deploy/hostvds/run_scrape.sh`
- `app/scripts/scrape_che168.py`

Почему `primcom-scraper.service` может быть `static`:

- В unit нет `[Install]`, т.к. сервис oneshot и запускается таймером.
- Это нормальная конфигурация.

## 6. Режимы ingestion: legacy vs v2

### 6.1 Legacy (основной на текущем сервере)

Запускает `app/scripts/scrape_che168.py`.

Характеристики:

- Один источник за запуск (`--source`, обычно `guazi`).
- Расширенная логика переводов и LLM-нормализации внутри скрипта.
- Опциональная очистка старых карточек через `--delete-old`.
- Работа с изображениями и медиа-папкой внутри самого скрипта.

### 6.2 v2 (альтернативный контур)

Запускает `app/jobs/run_ingest.py` -> `app/services/ingest.py`.

Характеристики:

- Мульти-источник за запуск (`--sources che168,dongchedi,guazi`).
- run telemetry (`scrape_runs`) и `raw_listings`.
- Слой canonical mapping (`listing_vehicle_map` и related tables).

Важно:

- v2 сервисы не должны использоваться, если они не установлены в systemd.

## 7. Поведение текущего run_scrape.sh

Файл: `deploy/hostvds/run_scrape.sh`

Параметры из `.env`:

- `SCRAPER_SOURCE` (default `guazi`)
- `DAILY_NEW_LIMIT`
- `DAILY_DELETE_LIMIT`
- `SCRAPER_ENABLE_DELETE_OLD` (новый флаг безопасности)
- `CHE168_MAX_IMAGES`
- `SCRAPER_THROTTLE_MS`
- `SCRAPER_SKIP_EXISTING`
- `SCRAPER_ALLOW_NON_ENGLISH`
- `SCRAPER_TRANSLATE_CHINESE`

Ключевой момент:

- `--delete-old` передается только если:
  - `SCRAPER_ENABLE_DELETE_OLD=1`
  - и `DAILY_DELETE_LIMIT != 0`

Это сделано для отключения случайного автоудаления карточек по умолчанию.

## 8. Модель данных (БД)

DDL:

- `schema.sql` - core таблицы каталога.
- `schema_v2.sql` - telemetry, translation_cache, canonical layer.

Ключевые таблицы:

- `listing_sources` - источники.
- `listings` - карточки.
- `listing_images` - изображения карточек (с `ON DELETE CASCADE` по listing).
- `listing_price_history` - история цены.
- `listing_translations` - legacy-переводы на уровне листинга.
- `scrape_runs` - журналы запусков.
- `raw_listings` - сырой payload из источников.
- `translation_cache` - кэш переводов.
- `listing_vehicle_map` + `vehicle_*` - канонический слой.

## 9. Медиа и изображения

Скачивание:

- `app/utils/media.py::download_image`
- Сначала скачивание по URL с `Referer` по домену источника.
- Затем конвертация в `.webp` (или сохранение webp как есть).

Путь хранения:

- `<MEDIA_DIR>/<source_code>/<source_listing_id>/<pos>.webp`
- Пример:
  - `/opt/primcom/china_cars_backend/data/media/guazi/163006478120062/000.webp`

### 9.1 Защита от пустых карточек

Пустой карточкой считаем карточку без валидного `local_path` изображения.

В API список каталога фильтруется условием:

- есть хотя бы одна запись в `listing_images` с непустым `local_path` и расширением `webp/jpg/jpeg/png`.

Файл:

- `app/api/routes.py` (`list_china_cars`)

### 9.2 Скрипт очистки пустых карточек

Файл:

- `app/scripts/cleanup_empty_image_listings.py`

Назначение:

- Находит и удаляет карточки выбранного источника без валидных изображений.

Команды:

```bash
python -m app.scripts.cleanup_empty_image_listings --source guazi --dry-run --preview-limit 100
python -m app.scripts.cleanup_empty_image_listings --source guazi --preview-limit 100
```

## 10. Источники и особенности

### 10.1 guazi

Файл:

- `app/scrapers/guazi.py`

Особенности:

- Детальный парсинг DOM + JSON responses.
- Placeholder-защита (`_is_placeholder_listing`).
- Жесткий фильтр изображений (`_filter_and_limit_guazi_image_urls`):
  - блок QR/mini/wechat/icon/logo/sprite и т.п.
  - ранжирование URL, похожих на реальные фото авто.
- Лимит изображений `_GZ_MAX_IMAGES=10`.

### 10.2 che168

Файл:

- `app/scrapers/che168.py`

Особенности:

- mobile-entrypoint;
- фильтрация image URL с приоритетом `autoimg`;
- fallback на DOM изображений при отсутствии в raw JSON.

### 10.3 dongchedi

Файл:

- `app/scrapers/dongchedi.py`

Особенности:

- детект captcha/verification экранов;
- extraction ссылок через URL pattern `/usedcar/<id>`;
- fallback по JSON id extraction.

## 11. API endpoints (основные)

Meta:

- `GET /`
- `GET /health`

Каталог:

- `GET /api/auto-iz-kitaya`
- `GET /api/china-cars` (alias)
- `GET /api/auto-iz-kitaya/{listing_id}`
- `GET /api/auto-iz-kitaya/facets`

Ручной ввод (менеджер):

- `POST /api/manager/manual-listing`
- Требует `X-Manager-Api-Key`.
- Режимы:
  - создание карточки;
  - редактирование существующей карточки через `listing_id` и `replace_photos`.
- Дополнительно:
  - `GET /api/manager/manual-listings` — список ручных карточек (для поиска/редактирования в боте);
  - `GET /api/manager/manual-listing/{listing_id}` — детали карточки;
  - `DELETE /api/manager/manual-listing/{listing_id}` — мягкое удаление карточки (`status='deleted'`).
- Для рынка Японии поддерживается поле `auction_grade` (оценка по аукционному листу), хранится в `raw_data`.

Лиды:

- `POST /api/lead`
- Rate limit по IP + отправка в Telegram.

Ops:

- `GET /api/scrape-runs`

## 12. Переменные окружения

Базовые (обязательные):

- `DATABASE_URL`
- `MEDIA_DIR`

API:

- `API_HOST`, `API_PORT`, `CORS_ORIGINS`

Скрапер:

- `SCRAPER_SOURCE`
- `DAILY_NEW_LIMIT`
- `DAILY_DELETE_LIMIT`
- `SCRAPER_ENABLE_DELETE_OLD` (`0` по умолчанию)
- `CHE168_MAX_IMAGES`
- `SCRAPER_THROTTLE_MS`
- `SCRAPER_SKIP_EXISTING`
- `SCRAPER_ALLOW_NON_ENGLISH`
- `SCRAPER_TRANSLATE_CHINESE`

Перевод:

- `OPENAI_API_KEY`
- `OPENAI_TRANSLATION_MODEL`
- `OPENAI_NORMALIZE_MODEL`
- `TRANSLATION_PROXY_URL`
- `TRANSLATION_PROXY_TOKEN`
- `TRANSLATION_PROXY_TIMEOUT_MS`

Безопасность/интеграции:

- `MANAGER_API_KEY`
- `LEAD_API_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_GROUP_ID`
- `LEAD_RATE_LIMIT_PER_MINUTE`

## 13. Операционные команды

Проверка сервисов:

```bash
systemctl list-unit-files | grep primcom
systemctl status primcom-api.service --no-pager
systemctl status primcom-scraper.timer --no-pager
```

Ручной запуск скрейпера:

```bash
systemctl start primcom-scraper.service
journalctl -u primcom-scraper.service -n 200 --no-pager
```

Проверка API:

```bash
curl -s http://127.0.0.1:8010/health
curl -s "http://127.0.0.1:8010/api/auto-iz-kitaya?source=guazi&limit=5&offset=0"
```

## 14. Диагностика типовых проблем

### 14.1 В логах только `skip_existing`

Причина:

- `SCRAPER_SKIP_EXISTING=1`, а парсер получает карточки, которые уже есть в БД.

Что делать:

- временно запускать с `--no-skip-existing` вручную;
- или увеличить разнообразие выборки/источник;
- или очистить проблемные карточки и дать набрать новые.

### 14.2 На фронте пустые карточки с надписью "Фото"

Причины:

- нет валидного `local_path` в `listing_images`;
- путь в БД неразрешим в URL;
- изображение не скачалось.

Действия:

1. Проверить API выборку (уже фильтрует валидные изображения).
2. Запустить:
   - `cleanup_empty_image_listings --dry-run`
   - затем реальный delete.
3. Перезапустить скрейпер.

### 14.3 В карточку попали не те изображения (QR/иконки)

Причина:

- слишком широкий сбор URL изображений на стороне источника.

Текущее решение:

- усиленная фильтрация и ранжирование URL в `guazi.py`.

### 14.4 Таймауты перевода при массовом парсинге

Симптом:

- в логах `batch translation failed`/`ReadTimeout`;
- при большом `--limit` часть значений не переводится.

Текущее поведение:

- batch-перевод через proxy выполняется чанками;
- есть ретраи с увеличением timeout;
- при сбое batch делается fallback на одиночный перевод;
- при частичном результате логируется `batch translation incomplete`.

Файл:

- `app/scripts/scrape_che168.py`

### 14.5 Таймауты скачивания изображений

Симптом:

- в логах `download_image_failed` с `ReadTimeout`.

Текущее поведение:

- повторные попытки скачивания;
- timeout увеличивается от попытки к попытке;
- логируется частичное сохранение изображений (`download_images_partial`).

Файл:

- `app/utils/media.py`

## 15. Политика изменений (обязательная)

Перед изменениями:

1. Прочитать этот runbook полностью.
2. Прочитать `BACKEND_CHANGELOG.md` (последние записи).
3. Прочитать релевантные файлы модуля, который меняется.
4. Зафиксировать, какой deploy-контур используется на сервере (`hostvds` или `hostvds-v2`).

После изменений:

1. Обновить этот runbook:
   - секции "Как работает" и "Диагностика", если поведение изменилось;
   - секцию "Журнал изменений".
2. Добавить запись в `BACKEND_CHANGELOG.md`:
   - что изменено;
   - зачем;
   - какие файлы затронуты;
   - как проверено;
   - что нужно сделать на сервере.
3. Обновить шаблоны `.env`/deploy-файлы, если добавлены новые env-переменные.
4. Проверить синтаксис измененных файлов (`python -m py_compile`, `bash -n` для shell).

## 16. Журнал изменений runbook

### 2026-02-22

- Добавлен полный runbook по архитектуре и эксплуатации.
- Зафиксировано, что текущий production-контур использует `deploy/hostvds/*`.
- Документирован флаг `SCRAPER_ENABLE_DELETE_OLD`.
- Документированы правила поддержки актуальности документации.
- Добавлена ссылка на обязательный журнал изменений `BACKEND_CHANGELOG.md`.
- Добавлены секции по диагностике таймаутов перевода и скачивания изображений.
