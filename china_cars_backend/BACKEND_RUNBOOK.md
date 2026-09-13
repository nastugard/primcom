# Primcom Backend Runbook

Дата актуализации: 2026-06-07

Этот документ является основным источником знаний по бэкенду `china_cars_backend`.
Перед любыми правками кода нужно читать этот runbook и релевантные секции.
После любых правок runbook должен быть обновлен в той части, которую затронули изменения.
Историю изменений смотреть в `BACKEND_CHANGELOG.md`.
Клиентскую версию возможностей backend смотреть в `BACKEND_CLIENT_OVERVIEW.md`.

## 1. Назначение проекта

Бэкенд обслуживает каталог авто на сайте Primcom:

- API каталога и деталей карточек.
- Скрейпинг объявлений из внешних источников.
- Загрузка и хранение изображений.
- Нормализация данных и перевод китайских названий.
- Ручное добавление карточек (China/Korea/Japan) через manager endpoint.
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

Отдельные связанные сервисы вне каталога `china_cars_backend`:

- `manager-listings-bot` - менеджерский Telegram-бот для ручных карточек Китая/Японии/Кореи;
- `primcom-monitor-bot` - отдельный Telegram-бот мониторинга состояния `primcom_bot` и `primcom-lead-api`.

Важно:

- `cv6067041.novalocal` в логах systemd - это hostname машины, а не отдельный сервис.
- Отсутствие `primcom-api-v2.service` и `primcom-scraper-v2.service` в `systemctl` означает, что v2 контур не активирован.

### 2.1 Актуальная схема серверов

- production backend: `ssh root@168.222.194.128`, рабочая папка `/opt/primcom/china_cars_backend`;
- production backend остаётся на сервере `168.222.194.128`;
- **статический сайт `primcom.ru` лежит НЕ здесь, а на reg.ru, `31.31.197.47`** (проверено DNS 2026-09-13).
  Прежняя формулировка «каталог сайта остаётся на `168.222.194.128`» была неверной и привела к плану выката,
  который нельзя выполнить. Следствие: публикатор пишет в локальную ФС, поэтому автопубликация SEO
  между двумя машинами не работает и `SEO_PUBLISH_COMMAND` остаётся пустым. Подробности и варианты
  решения — в `../DEPLOY_REGRU.md`;
- сайт читает карточки по-прежнему из production backend, поэтому VPN пользователю для просмотра не нужен;
- заявки сайта можно принимать на production backend, но пересылать в зарубежный `primcom-lead-api` через `LEAD_RELAY_URL`, чтобы российский backend не зависел от доступа к Telegram API.

Сервисы на сервере Telegram-ботов `ssh root@213.232.204.127`:

| Контур | Что делает | Как запущен | Где смотреть |
| --- | --- | --- | --- |
| `manager-listings-bot` | Ручное добавление/редактирование/удаление карточек Китая/Японии/Кореи | `primcom-manager-listings-bot.service` | `/opt/primcom/manager-listings-bot` |
| `primcom-bot` | Основной Telegram-бот/информационный бот, связанный с заявками | Docker-контейнер `primcom-bot` | проект `telegram-bot_clean_2026-01-23`, production-контур обычно в `/root/telegram-bot` |
| `primcom-lead-api` | HTTP API приема заявок сайта `POST /api/lead` и отправка уведомлений в Telegram | Docker-контейнер `primcom-lead-api` | проект `telegram-bot_clean_2026-01-23`, production-контур обычно в `/root/telegram-bot` |
| `primcom-monitor-bot` | Проверяет живы ли `primcom-bot` и `primcom-lead-api`, присылает alert | `primcom-monitor-bot.service` или ручной python-процесс | `/opt/primcom/primcom-monitor-bot` |

Важно по процессам на `213.232.204.127`:

- один `python main.py` может относиться к Docker-контейнеру `primcom-bot`, а не к `manager-listings-bot`;
- перед остановкой любого процесса нужно проверить `docker top primcom-bot`, `docker top primcom-lead-api`, `readlink -f /proc/<PID>/cwd` и `tr '\0' ' ' < /proc/<PID>/cmdline`;
- `manager-listings-bot` отправляет ручные карточки в production backend по `API_BASE_URL=https://api.primcom.ru`;
- `primcom-monitor-bot` надежнее держать на отдельном сервере от `primcom-bot`, иначе он не увидит полное падение хоста.

## 3. Быстрая карта кода

Основные entrypoints:

- API приложение: `app/main.py`
- API роуты: `app/api/routes.py`
- DB engine/session: `app/db.py`
- Конфиг: `app/core/settings.py` и реэкспорт `app/settings.py`
- Инициализация БД: `app/scripts/init_db.py`

Скрейпинг:

- Legacy runner (используется `primcom-scraper.service`): `app/scripts/scrape_che168.py`
- Daily external market runner: `app/scripts/scrape_external_market_daily.py`
- Multi-source runner (используется только в v2 контуре): `app/jobs/run_ingest.py`
- Сервис ingestion для v2 runner: `app/services/ingest.py`
- Скрейперы источников:
  - `app/scrapers/che168.py`
  - `app/scrapers/dongchedi.py`
  - `app/scrapers/guazi.py`
  - `app/scrapers/external_market.py`

Работа с БД:

- Репозиторий листингов/изображений: `app/storage/repository.py`
- Репозиторий telemetry/translation cache: `app/repositories/catalog.py`
- Канонический слой марки/модели: `app/services/canonical.py`
- Калькулятор ввоза авто: `app/services/import_calculator/*`

Утилиты:

- Скачивание и перекодирование картинок: `app/utils/media.py`
- Словари перевода брендов/моделей: `app/utils/name_translation.py`

Связанные внешние проекты в workspace:

- `/Volumes/SID/Колян АВТО/CSS&HTML Site/manager-listings-bot`
- `/Volumes/SID/Колян АВТО/CSS&HTML Site/primcom-monitor-bot`

## 4. Как запускается API

1. systemd запускает `primcom-api.service`:
   - `deploy/hostvds/primcom-api.service`
2. Процесс:
   - `uvicorn app.main:app --host 127.0.0.1 --port 8010`
3. `app/main.py`:
   - поднимает FastAPI;
   - монтирует `/media` из `settings.media_dir`;
   - подключает роутер из `app/api/routes.py`.

### 4.1 Import calculator API

- Endpoint: `POST /api/import-calculator/calculate`
- Назначение:
  - backend-authoritative расчёт обязательных платежей по ввозу авто в РФ;
  - единый контур для сайта и будущих B2B/API-интеграций.
- Внутренняя структура:
  - `app/services/import_calculator/config.py` - versioned rules (`2025`, `2026`);
  - `app/services/import_calculator/adapters.py` - exchange rate provider/fallback;
  - `app/services/import_calculator/core.py` - pure расчётные функции;
  - `app/services/import_calculator/service.py` - orchestration layer.
- Важно:
  - ставки и коэффициенты не хардкодятся в роуте;
  - при проблеме с rate provider расчёт падает не должен: используется fallback на config;
  - если для `fuel_type` нет явного правила в выбранной версии, API возвращает controlled validation error;
  - structured logs по расчётам пишутся в `app/api/routes.py`.

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

### 7.1 Нейтральный daily-импорт external market

Файлы:

- `app/scrapers/external_market.py`
- `app/scripts/scrape_external_market_daily.py`
- `deploy/hostvds/run_external_market_scrape.sh`
- `deploy/hostvds/primcom-external-market-scraper.service`
- `deploy/hostvds/primcom-external-market-scraper.timer`

Назначение:

- пополняет раздел Китая и раздел Кореи из внешнего каталога, URL которого хранится только в `.env`;
- по умолчанию добавляет до 3 карточек Китая и до 3 карточек Кореи за запуск;
- выбирает случайные страницы в пределах `EXTERNAL_MARKET_MAX_PAGES`;
- не обходит антибот-защиту: если источник возвращает verification/captcha/KillBot-экран, запуск завершается ошибкой `external_market_blocked`.

Параметры `.env`:

- `EXTERNAL_MARKET_BASE_URL` - базовый URL внешнего каталога, не коммитить в git;
- `EXTERNAL_MARKET_CHINA_PATH` (default `/catalog`);
- `EXTERNAL_MARKET_KOREA_PATH` (default `/korea`);
- `EXTERNAL_MARKET_CHINA_DAILY_LIMIT` (default `3`);
- `EXTERNAL_MARKET_KOREA_DAILY_LIMIT` (default `3`);
- `EXTERNAL_MARKET_MAX_PAGES` (default `20`);
- `EXTERNAL_MARKET_MAX_IMAGES` (default `10`);
- `EXTERNAL_MARKET_THROTTLE_MS` (default `1000`).

Сохранение:

- карточки Китая пишутся в источник `guazi`, чтобы существующий frontend-раздел Китая продолжал работать без изменений;
- карточки Кореи пишутся в `korea_manual`, потому что `/api/auto-iz-korei` читает этот источник;
- `source_listing_id` имеет формат `external_china_<id>` или `external_korea_<id>`;
- реальный URL хранится только во внутреннем `raw_data.private_source_url` и не отдается публичным API.

Ручная проверка:

```bash
python -m app.scripts.scrape_external_market_daily --dry-run
python -m app.scripts.scrape_external_market_daily --china-limit 3 --korea-limit 3 --max-pages 20 --max-images 10
```

Таймер:

- `primcom-external-market-scraper.timer` запускается один раз в сутки со случайной задержкой до 23 часов (`RandomizedDelaySec=23h`);
- старые карточки этот импорт автоматически не удаляет.

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
- Для `guazi` после скачивания дополнительно проверяется содержимое файла:
  - служебные бренд-картинки Guazi с крупным зеленым логотипом/иероглифом на темном фоне отбрасываются до сохранения;
  - отдельное правило ловит низкий широкий Guazi-баннер примерно `293x56`, который источник иногда ставит первым кадром галереи;
  - это защищает от CDN-картинок, которые выглядят как обычный `.jpg/.webp`, но не являются фото автомобиля.
- Затем конвертация в `.webp` (или сохранение webp как есть).
- Для external market importer используется принудительное перекодирование в `.webp` даже если исходник уже WebP. Это убирает EXIF/metadata и дополнительно отбрасывает слишком маленькие изображения.

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

### 9.3 Скрипт очистки служебных Guazi-картинок

Файл:

- `app/scripts/cleanup_guazi_brand_images.py`

Назначение:

- Находит уже сохраненные служебные Guazi-картинки с зеленым бренд-артом.
- Удаляет только записи `listing_images`, не всю карточку.
- После удаления пересобирает позиции оставшихся фото.

Команды:

```bash
python -m app.scripts.cleanup_guazi_brand_images --source guazi --dry-run --preview-limit 50
python -m app.scripts.cleanup_guazi_brand_images --source guazi --preview-limit 50 --delete-files
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
- Дополнительная content-проверка в `app/utils/media.py` отбрасывает Guazi-бренд-арт, если он пришел с нейтрального CDN URL.
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

### 10.4 external_market

Файл:

- `app/scrapers/external_market.py`

Особенности:

- реальный домен не хранится в коде, только в `.env`;
- DOM/JSON parser извлекает ссылки деталей, характеристики и изображения по нейтральным правилам;
- публичные endpoint-ы не отдают внешний `original_url` для карточек `external_*`;
- если источник показывает anti-bot/verification/captcha-экран, запуск падает с диагностикой и не создает карточки.

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
- Поддерживаемые рынки:
  - `china` - сохраняется в source `guazi`, чтобы текущая страница Китая и блок главной продолжили читать карточки без frontend-миграции;
  - `korea` - сохраняется в `korea_manual`;
  - `japan` - сохраняется в `japan_manual`.
- Manager API для `guazi` работает только с карточками, у которых `raw_data.manual=true`; старые парсерные карточки Guazi через manager-bot не редактируются и не удаляются.
- Для рынка Японии поддерживается поле `auction_grade` (оценка по аукционному листу), хранится в `raw_data`.
- Фото от manager-bot backend принимает как multipart `photos` и сам перекодирует в `.webp` через `save_upload_image_bytes`.
- Manager-bot принимает обычные Telegram-фото и изображения, отправленные как файлы-документы (`JPG`, `PNG`, `WEBP`).
- Manager-bot умеет импортировать пересланную публикацию из Telegram-канала:
  - сообщения одного альбома объединяются по `media_group_id`;
  - из подписи извлекаются доступные поля карточки;
  - отсутствующие характеристики не запрашиваются и отправляются пустыми;
  - перед отправкой используется тот же экран подтверждения, что и при ручном вводе.
- Ставки калькулятора продублированы статическими таблицами на `pages/rastamozhka-i-poshliny.html`.
  При изменении `app/services/import_calculator/config.py` выполнить `python3 scripts/build-customs-tables.py`
  в корне фронтенда и выложить страницу, иначе сайт будет показывать ставки, отличные от расчёта API.
- Статус на 2026-09-13: SEO-публикация на production **не включена**. Код `app/services/seo_publish.py` готов и покрыт тестами,
  но `SEO_PUBLISH_COMMAND` и `PRIMCOM_SITE_ROOT` не заданы, потому что фактический document root nginx не подтверждён.
  Пока `SEO_PUBLISH_COMMAND` пуста, карточка сохраняется нормально, а `seo_reason` возвращает
  «Автопубликация SEO не настроена на сервере.» (`app/services/seo_publish.py:98`). Порядок включения — в
  `deploy/primcom-seo-20260814/DEPLOY.md`, сводный статус релиза — в `SEO_GUIDE.md`, раздел `0.4`.
- После commit ручной карточки backend проверяет SEO-полноту и запускает команду из `SEO_PUBLISH_COMMAND`.
- Обязательные поля SEO-публикации: market, brand, model, year, положительная price и хотя бы одно изображение.
- Публикатор должен находиться отдельно от document root, например `/opt/primcom/seo-publisher`; публичный корень передается через `PRIMCOM_SITE_ROOT`.
- Рекомендуемая команда: `/usr/bin/node /opt/primcom/seo-publisher/scripts/publish-seo-catalog.mjs`.
- Ответы create/delete содержат `seo_status`, `seo_url`, `seo_reason`; ошибка SEO-сборки не откатывает сохранённую карточку.
- После удаления последней карточки страница модели остаётся доступной с `noindex,follow` и исчезает из sitemap.
- Публикатор отказывается собирать каталог, если ответ каталога API внезапно опустел: страна с активными моделями обнулилась или общее число активных моделей упало ниже `SEO_MIN_ACTIVE_RATIO` (по умолчанию `0.5`). В журнале это видно как `seo_publish_failed` с текстом `catalog shrink guard`.
- Такая ошибка означает проблему каталога, а не публикатора: сначала проверять `GET /api/auto-iz-yaponii`, `/api/auto-iz-kitaya?source=guazi`, `/api/auto-iz-korei` и скрейперы. Работающие SEO-страницы при этом не изменены.
- Намеренное сокращение каталога публикуется только вручную: `SEO_ALLOW_CATALOG_SHRINK=1 /usr/bin/node /opt/primcom/seo-publisher/scripts/publish-seo-catalog.mjs`.
- Парсер подписи встроен в `../manager-listings-bot/main.py`, чтобы production-запуск не зависел от доставки дополнительного Python-модуля; backend endpoint и env-параметры для импорта не менялись.
- Диагностика production-импорта:
  - стартовая версия пишется как `manager-listings-bot started version=...`;
  - получение частей альбома пишется как `telegram_import_media`;
  - завершение сборки альбома — `telegram_import_album_ready`;
  - готовность карточки к подтверждению — `telegram_import_ready`;
  - исключения фоновой обработки — `telegram_import_album_failed` с traceback.
- Production-проверка 2026-06-22:
  - версия импорта `2026-06-22.telegram-import-v3` была успешно проверена; после SEO-релиза ожидаемая версия — `2026-08-14.seo-publish-v1`;
  - рабочий процесс: `/opt/primcom/manager-listings-bot/.venv/bin/python /opt/primcom/manager-listings-bot/main.py`;
  - manager-bot использует отдельный Telegram-токен, не совпадающий с токеном Docker-контейнера `primcom-bot`;
  - значение `restart_count=1416` в monitor-bot относится к накопленной истории контейнера `primcom-bot`; контейнер непрерывно работает с 2026-06-15, поэтому это не перезапуски manager-bot;
  - сообщения `Received SIGTERM` при ручном `systemctl restart` являются штатной остановкой polling.

Лиды:

- `POST /api/lead`
- Rate limit по IP + отправка в Telegram.
- Если задан `LEAD_RELAY_URL`, production backend не отправляет сообщение в Telegram напрямую, а пересылает JSON заявки в relay endpoint.
- Рекомендуемый relay - зарубежный `primcom-lead-api` на сервере с доступом к Telegram API. Каталог и медиа при этом остаются на production backend.

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
- `LEAD_RELAY_URL`
- `LEAD_RELAY_TOKEN`
- `LEAD_RELAY_TIMEOUT_MS`
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

Проверка связанных сервисов:

```bash
ssh root@213.232.204.127
systemctl status primcom-manager-listings-bot.service --no-pager
systemctl status primcom-monitor-bot.service --no-pager
journalctl -u primcom-manager-listings-bot.service -n 100 --no-pager
journalctl -u primcom-monitor-bot.service -n 100 --no-pager
```

Важно:

- `primcom-manager-listings-bot.service` и `primcom-monitor-bot.service` могут жить не на том же сервере, что и backend;
- для них нужно проверять именно тот хост, на который они были вынесены.

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

### 14.3 В карточку попали не те изображения (QR/иконки/зеленый бренд-арт Guazi)

Причина:

- слишком широкий сбор URL изображений на стороне источника.
- часть служебных картинок Guazi приходит как обычный CDN `.jpg/.webp` без слов `logo`, `qr`, `icon` в URL, поэтому URL-фильтр не всегда достаточен.
- частый общий признак проблемных файлов: позиция `000.webp`, размер около `293x56`, крупный зеленый текст/логотип Guazi на темном фоне.

Текущее решение:

- усиленная фильтрация и ранжирование URL в `guazi.py`.
- content-проверка скачанного изображения в `app/utils/media.py`.
- очистка уже сохраненных плохих фото:
  - `python -m app.scripts.cleanup_guazi_brand_images --source guazi --dry-run --preview-limit 50`
  - `python -m app.scripts.cleanup_guazi_brand_images --source guazi --preview-limit 50 --delete-files`

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
