# Backend Change Log

Дата начала журнала: 2026-02-22

Этот файл обязателен к использованию как эксплуатационная документация изменений по бэкенду.

Правила ведения:

1. Перед началом новых правок прочитать последние записи этого файла.
2. После любых правок добавить новую запись.
3. В записи обязательно указать:
   - что изменено;
   - зачем изменено;
   - какие файлы затронуты;
   - как проверено;
   - что нужно сделать на сервере (если нужно).
4. Записи не переписывать и не удалять задним числом.

Формат записи:

## YYYY-MM-DD HH:MM (TZ)

### Изменение

Краткое название изменения.

### Причина

Зачем внесено.

### Затронутые файлы

- `path/to/file1`
- `path/to/file2`

### Проверка

- Что было проверено локально/на сервере.

### Действия на сервере

- Что нужно выполнить после выката.

---

## 2026-09-13 (+10)

### Изменение

Только документация. В `BACKEND_RUNBOOK.md` зафиксировано, что SEO-публикация на production не включена: `SEO_PUBLISH_COMMAND` и `PRIMCOM_SITE_ROOT` не заданы. Код backend не менялся.

### Причина

Релиз `primcom-seo-20260814` готов и проверен локально, но на сервер не загружен: SSH-ключ отклонён, фактический document root nginx не подтверждён. Без явной отметки в runbook поведение «карточка сохранена, SEO-страница не собрана» читается как дефект, хотя это штатная реакция на незаданную переменную.

### Затронутые файлы

- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- Поведение подтверждено по коду: при пустой `SEO_PUBLISH_COMMAND` возвращается `SeoPublishResult(False, "Автопубликация SEO не настроена на сервере.")`, `app/services/seo_publish.py:98`.
- Карточка при этом сохраняется, ошибка SEO-сборки её не откатывает.

### Дальше

- Подтвердить document root командой из `../deploy/primcom-seo-20260814/DEPLOY.md`.
- Добавить четыре SEO-переменные в `.env`, перезапустить `primcom-api.service` и `primcom-manager-listings-bot.service`.
- Сводный статус релиза: `../SEO_GUIDE.md`, раздел `0.4`.

## 2026-08-24 (+10)

### Изменение

В SEO-публикатор, запускаемый бэкендом через `SEO_PUBLISH_COMMAND`, добавлена защита от массовой деиндексации.

### Причина

Синхронизация доверяла любому успешному ответу каталога API. Ответ `200` с пустым `items` формально валиден, но переводил все модели страны в `inactive`, то есть в `noindex,follow` и вне sitemap. Публикация запускается автоматически после каждой ручной карточки, поэтому временный сбой каталога или скрейпера мог одномоментно снять с индексации 130 URL. Существующий порог QA (`не менее 20 сгенерированных URL`) этот случай не ловит: снятые с публикации страницы всё равно генерируются.

### Затронутые файлы

- `../scripts/sync-seo-catalog.mjs`
- `../scripts/test-seo-publisher.mjs`
- `../deploy/primcom-seo-20260814/seo-publisher/scripts/sync-seo-catalog.mjs`
- `../deploy/primcom-seo-20260814/DEPLOY.md`
- `BACKEND_RUNBOOK.md`
- frontend/SEO документация

### Проверка

- Пустой каталог по всем странам: сборка падает с `catalog shrink guard`, реестр не перезаписан.
- Пустая только Япония при живых Китае и Корее: падение по проверке страны.
- Обычное сокращение на 2 модели: проходит, `activeModels:88, inactiveModels:2`.
- `node scripts/test-seo-publisher.mjs` и `node scripts/check-seo-pages.mjs` — успешно.

### Действия на сервере

- Обновить `/opt/primcom/seo-publisher/scripts/sync-seo-catalog.mjs` вместе с остальным пакетом `seo-publisher`.
- Изменения бэкенда и БД не требуются, перезапуск `primcom-api.service` для этой правки не нужен.
- При появлении в журнале `catalog shrink guard` проверять каталог API и скрейперы, а не публикатор.

## 2026-08-14 18:42 (+10)

### Изменение

Добавлена автоматическая SEO-публикация после создания, изменения и удаления ручных карточек.

Реализовано:

- проверка обязательных полей: рынок, марка, модель, год, цена и фото;
- стабильный модельный URL и статусы `published`, `updated`, `catalog_only` в manager API;
- безопасный запуск внешнего атомарного публикатора с таймаутом и журналированием;
- сохранение карточки при ошибке SEO-сборки;
- сообщение результата публикации в manager-listings-bot.

### Причина

Ручные карточки должны автоматически обновлять индексируемые страницы моделей, но ошибка генерации не должна повреждать сайт или блокировать каталог.

### Затронутые файлы

- `app/api/routes.py`
- `app/core/settings.py`
- `app/services/seo_publish.py`
- `tests/test_seo_publish.py`
- `.env.example`
- `deploy/hostvds/.env.prod.example`
- `../manager-listings-bot/main.py`
- `../manager-listings-bot/tests/test_listing_import.py`
- эксплуатационная документация

### Проверка

- Python syntax check.
- Backend: 22 теста успешно, 7 API-тестов калькулятора пропущены из-за отсутствующего локального `python-multipart`.
- Manager-bot: 7 тестов успешно на Python 3.13 / aiogram 3.22.0.
- Изолированный Node integration test активной и снятой модели.

### Действия на сервере

- Сначала подтвердить фактический document root сайта.
- Установить `seo-publisher` вне document root, задать `PRIMCOM_SITE_ROOT`, `SEO_PUBLISH_COMMAND`, `SEO_PUBLISH_WORKDIR` и timeout.
- Обновить backend и перезапустить только `primcom-api.service` текущего `hostvds`-контура.
- Обновить `manager-listings-bot/main.py` на сервере ботов и перезапустить только `primcom-manager-listings-bot.service`.
- Создать тестовую полную карточку и убедиться, что бот возвращает URL опубликованной модельной страницы.

---

## 2026-06-22 20:27 (+10)

### Изменение

В `manager-listings-bot` добавлен импорт готовых Telegram-публикаций с автомобилями.

Реализовано:

- сбор пересланного Telegram-альбома по `media_group_id`;
- извлечение из подписи рынка, марки, модели, года, пробега, двигателя, привода, кузова, мощности, комплектации, аукционной оценки и цены;
- сохранение фотографий альбома в исходном порядке;
- отправка только распознанных данных без запроса отсутствующих характеристик;
- стандартное подтверждение перед отправкой в существующий `POST /api/manager/manual-listing`;
- отдельная кнопка меню с инструкцией по импорту;
- unit-тесты парсера на формате реальной карточки и альтернативной записи полей.

### Причина

Менеджер уже публикует готовые карточки в Telegram-канале. Повторный полный ввод тех же данных в manager-bot занимал время и создавал риск расхождений между каналом и сайтом.

### Затронутые файлы

- `../manager-listings-bot/main.py`
- `../manager-listings-bot/tests/test_listing_import.py`
- `../manager-listings-bot/tests/test_import_flow.py`
- `../manager-listings-bot/requirements.txt`
- `../manager-listings-bot/README.md`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CLIENT_OVERVIEW.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `PYTHONPATH=/tmp/manager-listings-bot-deps:. python3 -m unittest discover -s tests -v` — 5 тестов, включая сбор альбома и прямой FSM-переход к подтверждению без дозапроса отсутствующей мощности.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile listing_import.py main.py tests/test_listing_import.py tests/test_import_flow.py`
- загрузка `main.py` и регистрация 33 handlers на `aiogram 3.29.0`.
- загрузка `main.py`, регистрация 33 handlers и 5 тестов на минимальной поддерживаемой версии `aiogram 3.7.0` + `aiohttp 3.9.5`.
- чистая установка зависимостей из `requirements.txt` и импорт `main.py`.
- `git diff --check`

### Действия на сервере

- выкатить каталог `manager-listings-bot` на сервер бота `213.232.204.127`;
- перезапустить только `primcom-manager-listings-bot.service`;
- переслать боту публикацию с альбомом и проверить, что он собрал все фото, не запросил отсутствующую мощность и сразу показал подтверждение;
- backend `primcom-api.service` перезапускать не требуется.

---

## 2026-06-22 21:35 (+10)

### Изменение

Зафиксирован результат production-проверки импорта Telegram-карточек.

Подтверждено:

- `manager-listings-bot` работает с версией `2026-06-22.telegram-import-v3`;
- systemd запускает правильный файл из `/opt/primcom/manager-listings-bot`;
- токены manager-бота и Docker-бота разные, конфликта polling нет;
- импорт пересланной публикации работает;
- высокий `restart_count` на экране monitor-bot относится к накопленной истории другого контура — Docker-контейнера `primcom-bot`.

### Причина

После выката запуск polling занял несколько минут, из-за чего исправный сервис был принят за неработающий. Требовалось документально разделить manager-service и Docker-контуры.

### Затронутые файлы

- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- В journal подтверждены строки `manager-listings-bot started version=2026-06-22.telegram-import-v3`, `Start polling` и `Run polling`.
- Проверены PID, рабочая директория и командная строка systemd-процесса.
- Функциональность подтверждена пользователем.

### Действия на сервере

- Не требуются.

---

## 2026-06-22 21:20 (+10)

### Изменение

Добавлена production-диагностика импорта Telegram-альбомов в manager-bot:

- явная версия приложения в стартовом логе;
- логи получения сообщения, сборки альбома и готовности карточки;
- перехват и полный traceback ошибок фоновой обработки альбома;
- пользовательское сообщение при внутренней ошибке импорта.

### Причина

Manager-service успешно запускается, но без диагностических событий невозможно отличить старую версию файла, пересылку не в тот бот, отсутствие срабатывания handler и исключение фоновой задачи.

### Затронутые файлы

- `../manager-listings-bot/main.py`
- `../manager-listings-bot/tests/test_import_flow.py`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- 5 тестов успешно на `aiogram 3.7.0`.
- `python -m py_compile` успешно.
- импорт сообщает версию `2026-06-22.telegram-import-v3` и 33 handlers.

### Действия на сервере

- выкатить новый `main.py`;
- проверить SHA-256 и версию;
- перезапустить только `primcom-manager-listings-bot.service`;
- открыть journal в follow-режиме и переслать тестовый альбом.

---

## 2026-06-22 20:57 (+10)

### Изменение

Исправлена надежность выката импорта Telegram-карточек:

- парсер перенесен внутрь `manager-listings-bot/main.py`, поэтому сервис больше не падает при отсутствии отдельного `listing_import.py`;
- устранен конфликт зависимостей: нижняя граница `aiohttp` изменена с `3.10.0` на `3.9.0`, совместимую с минимальной заявленной версией `aiogram 3.7.0`;
- повторно проверены импорт приложения, регистрация handlers и тесты на старой и актуальной версиях aiogram.

### Причина

Первоначальный выкат мог не стартовать, если на сервер был доставлен только `main.py`, без нового модуля `listing_import.py`. Кроме того, `requirements.txt` содержал несовместимые требования для чистой установки `aiogram 3.7.0`.

### Затронутые файлы

- `../manager-listings-bot/main.py`
- `../manager-listings-bot/requirements.txt`
- `../manager-listings-bot/tests/test_listing_import.py`
- `../manager-listings-bot/README.md`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- 5 тестов успешно на `aiogram 3.7.0` + `aiohttp 3.9.5`.
- 5 тестов успешно на `aiogram 3.29.0` + `aiohttp 3.14.1`.
- чистая установка `requirements.txt` и успешный импорт `main.py` с 33 handlers.
- systemd-подобный запуск дошел до обращения к Telegram API; с тестовым токеном ожидаемо завершился `TelegramUnauthorizedError`, то есть загрузка приложения и конфигурации прошла.

### Действия на сервере

- выкатить только обновленный `manager-listings-bot/main.py`;
- проверить импорт через `.venv/bin/python -c "import main; print(len(main.router.observers['message'].handlers))"`;
- перезапустить `primcom-manager-listings-bot.service`;
- если сервис не стартует, снять полный traceback через `journalctl -u primcom-manager-listings-bot.service -n 100 --no-pager -l`.

---

## 2026-06-07 21:15 (+10)

### Изменение

Уточнена эксплуатационная документация по Telegram-ботам на сервере `213.232.204.127`.

Зафиксировано:

- `manager-listings-bot` работает отдельно через `primcom-manager-listings-bot.service`;
- основной бот заявок/информационный бот работает в Docker-контейнере `primcom-bot`;
- API заявок сайта работает в Docker-контейнере `primcom-lead-api`;
- monitor-bot проверяет `primcom-bot` и `primcom-lead-api`;
- `python main.py` на сервере ботов нельзя останавливать без проверки `docker top` и `/proc/<PID>/cwd`, потому что это может быть не manager-bot.

### Причина

На сервере ботов одновременно работают несколько разных Telegram-контуров. При диагностике загрузки фото в manager-bot появился риск принять процесс другого бота за дубль manager-bot и случайно остановить уведомления с сайта.

### Затронутые файлы

- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- Прочитаны `primcom-monitor-bot/README.md` и `telegram-bot_clean_2026-01-23/deployment_manual.md`.

### Действия на сервере

- Не требуются. Это документационная правка.

---

## 2026-06-07 20:35 (+10)

### Изменение

Manager-bot начал принимать изображения, отправленные как файлы-документы (`JPG`, `PNG`, `WEBP`), а не только обычные Telegram `photo`.

Реализовано:

- добавлен handler `ListingFlow.photos + F.document`;
- документ принимается, если `mime_type` начинается с `image/` или имя файла заканчивается на `.jpg/.jpeg/.png/.webp`;
- общий helper добавляет file_id в состояние и выводит счетчик `Фото добавлено: N шт.`;
- при отправке в backend filename/content-type теперь определяются по Telegram `file_path`, поэтому `.webp` уходит как `image/webp`;
- backend менять не пришлось: он уже читает байты `UploadFile` и перекодирует все изображения в `.webp`;
- runbook дополнен актуальными IP серверов backend/bot и поддержкой WEBP в manager-bot.

### Причина

При загрузке `.webp` Telegram отправлял файл как `document`, а бот слушал только `message.photo`. Из-за этого на шаге загрузки фото бот отвечал "Пришлите фото", хотя изображение было отправлено.

### Затронутые файлы

- `../manager-listings-bot/main.py`
- `../manager-listings-bot/README.md`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile main.py` в `manager-listings-bot`
- `git diff --check -- manager-listings-bot/main.py manager-listings-bot/README.md`

### Действия на сервере

- выкатить `manager-listings-bot/main.py` и `manager-listings-bot/README.md` на сервер бота `213.232.204.127`;
- перезапустить `primcom-manager-listings-bot.service`;
- проверить в Telegram: на шаге загрузки фото отправить `.webp` как файл и убедиться, что бот отвечает `Фото добавлено: 1 шт.`.

---

## 2026-06-07 17:10 (+10)

### Изменение

Расширен ручной manager-контур карточек: добавлен рынок `china` в backend manager API и Telegram manager-bot.

Реализовано:

- `POST /api/manager/manual-listing` принимает `market=china`;
- ручные карточки Китая сохраняются в source `guazi`, чтобы текущая страница Китая и блок главной продолжили работать без frontend-миграции;
- операции просмотра/редактирования/удаления через manager API для `guazi` ограничены только карточками с `raw_data.manual=true`;
- manager-bot получил кнопку `Китай`, поддержку `/recent china`, создание и редактирование китайских карточек;
- оценка по аукционному листу по-прежнему спрашивается только для Японии.

### Причина

Автоматические парсеры начали упираться в anti-bot/verification, поэтому пополнение Китая нужно перевести в уже рабочий ручной контур, аналогичный Японии и Корее.

### Затронутые файлы

- `app/api/routes.py`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CLIENT_OVERVIEW.md`
- `BACKEND_CHANGELOG.md`
- `../manager-listings-bot/main.py`
- `../manager-listings-bot/README.md`

### Проверка

- `.venv/bin/python -m py_compile app/api/routes.py`
- `python3 -m py_compile main.py` в `manager-listings-bot`

### Действия на сервере

- выкатить `app/api/routes.py` на backend-сервер и перезапустить `primcom-api.service`;
- выкатить `manager-listings-bot/main.py` на сервер бота и перезапустить `primcom-manager-listings-bot.service`;
- в боте проверить создание карточки с площадкой `Китай` и появление карточки на странице авто из Китая.

---

## 2026-06-07 16:30 (+10)

### Изменение

Добавлен нейтральный daily-импорт `external_market` для пополнения карточек Китая и Кореи из внешнего каталога без хранения реального домена в коде.

Реализовано:

- новый scraper `app/scrapers/external_market.py`;
- новый runner `app/scripts/scrape_external_market_daily.py`;
- отдельные deploy-файлы systemd для ежедневного запуска со случайной задержкой;
- настройки `EXTERNAL_MARKET_*` в `app/core/settings.py`;
- принудительное перекодирование изображений в `.webp` для нового импорта;
- публичный API не отдает `original_url` для карточек с `source_listing_id` формата `external_*`;
- при detection verification/captcha/KillBot запуск завершается ошибкой, без обхода защиты.

### Причина

Текущий автоматический источник Китая начал отдавать anti-bot verification вместо списка объявлений, из-за чего каталог перестал пополняться. Нужен отдельный безопасный контур пополнения карточек Китая и Кореи без изменения frontend-кэша и без публикации внешнего URL в API.

### Затронутые файлы

- `app/core/settings.py`
- `app/utils/media.py`
- `app/api/routes.py`
- `app/scrapers/external_market.py`
- `app/scripts/scrape_external_market_daily.py`
- `deploy/hostvds/run_external_market_scrape.sh`
- `deploy/hostvds/primcom-external-market-scraper.service`
- `deploy/hostvds/primcom-external-market-scraper.timer`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CLIENT_OVERVIEW.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `python3 -m py_compile app/scrapers/external_market.py app/scripts/scrape_external_market_daily.py app/api/routes.py app/core/settings.py app/utils/media.py`
- проверено, что в tracked-файлах нет буквального названия или домена реального внешнего источника.
- `git diff --check`

### Действия на сервере

- выкатить новые и измененные файлы;
- в `/opt/primcom/china_cars_backend/.env` добавить `EXTERNAL_MARKET_BASE_URL`, `EXTERNAL_MARKET_CHINA_PATH`, `EXTERNAL_MARKET_KOREA_PATH`, лимиты и throttle;
- выполнить dry-run:
  - `python -m app.scripts.scrape_external_market_daily --dry-run`
- выполнить ручной запуск и проверить API Китая/Кореи;
- установить и включить `primcom-external-market-scraper.timer`.

---

## 2026-04-26 17:30 (+10)

### Изменение

Добавлена content-проверка изображений `guazi` и скрипт очистки уже сохраненных служебных Guazi-картинок.

Скрипт очистки дополнительно:

- разрешает относительные пути через текущую папку проекта и `MEDIA_DIR`;
- выводит диагностические счетчики `db_rows`, `scanned_files`, `missing_files`, `unreadable_files`.
- выводит `top_green_preview` с метриками самых похожих на Guazi-бренд-арт изображений.
- добавлено отдельное правило для реального проблемного файла: низкий широкий Guazi-баннер около `293x56`, который сохранялся как `000.webp` и становился обложкой карточки.

### Причина

В карточки снова попадал зеленый бренд-арт Guazi: источник отдавал его как обычный CDN `.jpg/.webp`, без явных URL-маркеров `logo`, `qr`, `icon`. Старый фильтр проверял в основном адрес картинки и поэтому не мог надежно отличить такую служебную графику от фото автомобиля.

### Затронутые файлы

- `app/utils/media.py`
- `app/scripts/cleanup_guazi_brand_images.py`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CLIENT_OVERVIEW.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `python -m py_compile app/utils/media.py app/scripts/cleanup_guazi_brand_images.py`
- smoke-проверка `is_guazi_brand_art_image` на скриншоте с зеленым Guazi-артом.
- проверка на реальных файлах `https://api.primcom.ru/media/guazi/<source_listing_id>/000.webp`: проблемный `293x56` баннер определяется как служебный, нормальное фото `001.webp` не отбрасывается.

### Действия на сервере

- выкатить обновленные файлы;
- выполнить dry-run очистки:
  - `python -m app.scripts.cleanup_guazi_brand_images --source guazi --dry-run --preview-limit 50`
- если список корректный, удалить плохие фото:
  - `python -m app.scripts.cleanup_guazi_brand_images --source guazi --preview-limit 50 --delete-files`
- следующий запуск `primcom-scraper.service` будет сохранять новые фото уже с content-защитой.

---

## 2026-04-26 17:20 (+10)

### Изменение

Добавлен relay-режим для заявок сайта:

- `POST /api/lead` сохраняет текущую валидацию, rate limit и API-контракт;
- если задан `LEAD_RELAY_URL`, заявка пересылается в внешний lead relay вместо прямой отправки в Telegram;
- добавлены `LEAD_RELAY_TOKEN` и `LEAD_RELAY_TIMEOUT_MS`;
- прямой Telegram-режим остаётся fallback-поведением, если relay не настроен.

### Причина

Production backend находится на российском сервере, где доступ к Telegram API может быть заблокирован. Старый рабочий подход проекта уже выносил Telegram-сервисы на зарубежный сервер; теперь сайт может принимать заявки на российском backend и пересылать их в зарубежный `primcom-lead-api`.

### Затронутые файлы

- `app/api/routes.py`
- `app/core/settings.py`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `python -m py_compile app/api/routes.py app/core/settings.py`
- `git diff --check`

### Действия на сервере

- выкатить `app/api/routes.py` и `app/core/settings.py` на production backend;
- в `/opt/primcom/china_cars_backend/.env` задать `LEAD_RELAY_URL` на зарубежный relay endpoint;
- если relay защищён токеном, задать `LEAD_RELAY_TOKEN`;
- перезапустить `primcom-api.service`;
- проверить `POST /api/lead`.

---

## 2026-04-16 00:18 (+10)

### Изменение

Доработан существующий import calculator без смены архитектуры:

- `vehicle_age` переведён с 2 состояний на 3 диапазона: `new`, `3-5`, `5+`;
- duty config перестроен по возрастным таблицам, включая отдельные ставки для `3-5` и `5+`;
- НДС теперь начисляется только для `is_legal_entity=true`;
- логика акциза и утильсбора сохранена, но привязана к новым age enum без изменения формул.

### Причина

Нужно было адаптировать текущий калькулятор под новые правила расчёта пошлины и НДС, не переписывая сервис заново и не ломая уже существующий API/UI-контур.

### Затронутые файлы

- `app/api/routes.py`
- `app/services/import_calculator/config.py`
- `app/services/import_calculator/core.py`
- `app/services/import_calculator/service.py`
- `app/services/import_calculator/types.py`
- `tests/test_import_calculator.py`
- `BACKEND_CHANGELOG.md`

### Проверка

- `python3 -m py_compile china_cars_backend/app/api/routes.py china_cars_backend/app/services/import_calculator/*.py china_cars_backend/tests/test_import_calculator.py`
- `cd china_cars_backend && .venv/bin/python -m unittest tests.test_import_calculator.ImportCalculatorCoreTests tests.test_import_calculator.ImportCalculatorExchangeTests -v`
- `git diff --check`

### Действия на сервере

- выкатить обновлённые файлы `app/api/routes.py` и `app/services/import_calculator/*`;
- перезапустить `primcom-api.service`;
- проверить `POST /api/import-calculator/calculate` с `vehicle_age=3-5` и двумя вариантами `is_legal_entity` (`true` и `false`).

## 2026-04-15 12:06 (+10)

### Изменение

Добавлен production-ready контур калькулятора ввоза авто:

- новый пакет `app/services/import_calculator/` с versioned config, core-формулами и exchange adapter;
- новый endpoint `POST /api/import-calculator/calculate`;
- controlled validation errors для неподдержанных `rule_version`/`fuel_type`;
- structured logging по каждому расчёту.

### Причина

Нужно было вынести расчёт пошлины, акциза, НДС и утильсбора из фронтовой страницы в backend-authoritative сервис, пригодный для сайта и B2B/API-интеграций.

### Затронутые файлы

- `app/api/routes.py`
- `app/core/settings.py`
- `app/services/import_calculator/__init__.py`
- `app/services/import_calculator/adapters.py`
- `app/services/import_calculator/config.py`
- `app/services/import_calculator/core.py`
- `app/services/import_calculator/exceptions.py`
- `app/services/import_calculator/service.py`
- `app/services/import_calculator/types.py`
- `tests/test_import_calculator.py`
- `BACKEND_RUNBOOK.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- `.venv/bin/python -m py_compile app/api/routes.py app/services/import_calculator/*.py tests/test_import_calculator.py`
- `.venv/bin/python -m unittest tests.test_import_calculator.ImportCalculatorCoreTests tests.test_import_calculator.ImportCalculatorExchangeTests -v`
- `.venv/bin/python -m unittest tests.test_import_calculator -v` -> API subset skipped locally из-за отсутствующего `python-multipart` в `.venv`

### Действия на сервере

- выкатить новый пакет `app/services/import_calculator/` и обновлённый `app/api/routes.py`;
- проверить, что в окружении установлен `python-multipart`, как и указано в `requirements.txt`;
- перезапустить API:
  - `systemctl restart primcom-api.service`;
- проверить endpoint:
  - `POST /api/import-calculator/calculate`.

## 2026-02-24 21:49 (+10)

### Изменение

Создан отдельный документ для заказчика с описанием backend-возможностей и ключевых изменений в простом деловом формате:

- текущее состояние backend (API, парсер, боты, данные, эксплуатация);
- понятные бизнес-эффекты по последним изменениям;
- правило регулярного пополнения раздела ключевых изменений.

### Причина

Нужен единый краткий документ, который можно показывать заказчику без технической перегрузки и использовать как живую историю ключевых улучшений.

### Затронутые файлы

- `BACKEND_CLIENT_OVERVIEW.md`
- `BACKEND_CHANGELOG.md`

### Проверка

- ручная проверка структуры и содержания клиентского документа;
- проверка наличия новых правил обновления в самом файле.

### Действия на сервере

- выкатить `BACKEND_CLIENT_OVERVIEW.md` вместе с остальными backend-документами (при следующем деплое).

---

## 2026-03-18 23:20 (VLAT)

### Изменение

Актуализирована документация по эксплуатационным ботам и добавлен новый monitor-контур:

- в `manager-listings-bot` зафиксирована рабочая production-схема с размещением бота на зарубежном сервере;
- создан отдельный проект `primcom-monitor-bot` с README, `.env.example`, `systemd` unit и реализацией Telegram monitor-бота;
- обновлены backend-документы, чтобы новая схема и мониторинг были отражены в общем комплекте документации.

### Причина

Нужно закрепить текущую рабочую схему после переноса manager-бота и подготовить прозрачный контур мониторинга `primcom_bot`/`primcom-lead-api`.

### Затронутые файлы

- `manager-listings-bot/README.md`
- `primcom-monitor-bot/main.py`
- `primcom-monitor-bot/README.md`
- `primcom-monitor-bot/.env.example`
- `primcom-monitor-bot/requirements.txt`
- `primcom-monitor-bot/deploy/primcom-monitor-bot.service`
- `china_cars_backend/README.md`
- `china_cars_backend/BACKEND_RUNBOOK.md`
- `china_cars_backend/BACKEND_CLIENT_OVERVIEW.md`
- `china_cars_backend/BACKEND_CHANGELOG.md`

### Проверка

- `python3 -m py_compile manager-listings-bot/main.py`
- `python3 -m py_compile primcom-monitor-bot/main.py`

### Действия на сервере

- выкатить `primcom-monitor-bot` на выделенный сервер;
- при необходимости обновить `manager-listings-bot/README.md` рядом с production-контуром;
- использовать обновленные runbook/README как основной источник истины по деплою и мониторингу.

---

## 2026-02-23 01:30 (MSK)

### Изменение

Расширен manager-контур для ручных карточек Японии/Кореи:

- в API добавлены операции просмотра, списка и удаления ручных карточек;
- `POST /api/manager/manual-listing` теперь поддерживает редактирование существующей карточки (`listing_id`) и режим сохранения/замены фото (`replace_photos`);
- добавлено поле `auction_grade` (оценка по аукционному листу) для японских карточек;
- `auction_grade` добавлен в list/detail выдачу каталога.

### Причина

Нужно дать менеджеру полноценное управление карточками (создать/изменить/удалить) и сохранить в карточке Японии оценку по аукционному листу.

### Затронутые файлы

- `app/api/routes.py`
- `BACKEND_RUNBOOK.md`

### Проверка

- `python -m py_compile app/api/routes.py`
- ручная проверка SQL/JSON-мэппинга:
  - list/detail каталога отдают `auction_grade`;
  - manager endpoint-ы покрывают create/edit/delete/list/get.

### Действия на сервере

- выкатить `app/api/routes.py`;
- перезапустить API:
  - `systemctl restart primcom-api.service`;
- проверить manager endpoint-ы:
  - `GET /api/manager/manual-listings` (с `X-Manager-Api-Key`);
  - `GET /api/manager/manual-listing/{id}`;
  - `DELETE /api/manager/manual-listing/{id}`.

---

## 2026-02-22 13:50 (MSK)

### Изменение

Создана постоянная документационная база по бэкенду:

- подробный runbook;
- локальные инструкции для процесса изменений;
- актуализация README и env-шаблонов.

### Причина

Нужно зафиксировать единый источник истины по архитектуре и эксплуатации бэка и убрать рассинхрон в командах/сервисах.

### Затронутые файлы

- `BACKEND_RUNBOOK.md`
- `AGENTS.md`
- `README.md`
- `.env.example`
- `deploy/hostvds/.env.prod.example`

### Проверка

- проверена доступность файлов и содержимое;
- проверено наличие новых env-параметров в шаблонах;
- проверен git diff только по документации/шаблонам.

### Действия на сервере

- не требуется, кроме обновления файлов при деплое.

---

## 2026-02-22 14:05 (MSK)

### Изменение

Усилена устойчивость массового парсинга к сетевым таймаутам:

- batch-перевод через proxy разбит на чанки;
- добавлены ретраи batch/single переводов с увеличением timeout;
- добавлен fallback на одиночный перевод для неразобранных значений;
- добавлена диагностика частичного перевода (`batch translation incomplete`);
- улучшена устойчивость скачивания изображений: timeout увеличивается от попытки к попытке.

### Причина

При запуске с большим `--limit` возникали `ReadTimeout` на batch-переводе и при скачивании отдельных изображений, из-за чего качество заполнения карточек снижалось.

### Затронутые файлы

- `app/scripts/scrape_che168.py`
- `app/utils/media.py`
- `BACKEND_RUNBOOK.md`

### Проверка

- `python -m py_compile app/scripts/scrape_che168.py app/utils/media.py`
- проверка наличия новых секций в `BACKEND_RUNBOOK.md`.

### Действия на сервере

- выкатить обновленные файлы;
- запустить повторно:
  - `python -m app.scripts.scrape_che168 --source guazi --limit 60 --max-images 10 --no-skip-existing --allow-non-english-brand --translate-chinese --throttle-ms 700`
- проверить логи: отсутствие критических `batch translation failed` и приемлемый процент `download_images_partial`.

---

## 2026-02-22 13:10 (MSK)

### Изменение

Усилен фильтр изображений `guazi` и ограничен сбор изображений в более релевантных DOM-зонах.

### Причина

В карточки попадали нерелевантные изображения (QR/иконки/служебная графика) при доборе фото.

### Затронутые файлы

- `app/scrapers/guazi.py`

### Проверка

- `python -m py_compile app/scrapers/guazi.py`
- smoke-проверка функции `_filter_and_limit_guazi_image_urls` с тестовыми URL:
  - QR/иконки отбрасываются;
  - URL, похожие на фото авто, остаются.

### Действия на сервере

- выкатить обновленный файл;
- запустить `primcom-scraper.service`.

---

## 2026-02-22 13:15 (MSK)

### Изменение

Исправлена обработка изображений в ingestion и API:

- в v2 ingestion сохраняются только реально скачанные изображения;
- список каталога фильтруется по карточкам с валидными изображениями;
- `images_count` и `cover_image_url` считаются только по валидным `local_path`.

### Причина

Часть карточек имела записи в `listing_images`, но фактического изображения для фронта не было.

### Затронутые файлы

- `app/services/ingest.py`
- `app/api/routes.py`

### Проверка

- `python -m py_compile app/services/ingest.py app/api/routes.py`

### Действия на сервере

- перезапустить `primcom-api.service`;
- при использовании v2 ingestion учесть обновленную логику сохранения изображений.

---

## 2026-02-22 13:20 (MSK)

### Изменение

Автоудаление карточек после парсинга отключено по умолчанию через дополнительный флаг.

### Причина

Нужно предотвратить случайное удаление карточек, пока идет стабилизация парсера.

### Затронутые файлы

- `deploy/hostvds/run_scrape.sh`
- `.env.example`
- `deploy/hostvds/.env.prod.example`

### Проверка

- `bash -n deploy/hostvds/run_scrape.sh`
- проверка наличия `SCRAPER_ENABLE_DELETE_OLD=0` в env-шаблонах.

### Действия на сервере

- в `.env` установить `SCRAPER_ENABLE_DELETE_OLD=0`;
- перезапустить/перезапустить вручную `primcom-scraper.service`.

---

## 2026-02-22 13:25 (MSK)

### Изменение

Добавлен утилитарный скрипт удаления карточек без валидных изображений.

### Причина

Нужно быстро чистить "пустые" карточки из каталога перед повторным набором данных скрейпером.

### Затронутые файлы

- `app/scripts/cleanup_empty_image_listings.py`

### Проверка

- `python -m py_compile app/scripts/cleanup_empty_image_listings.py`
- на сервере запуск:
  - `--dry-run` показал `count: 0`;
  - реальный запуск также `count: 0`.

### Действия на сервере

- по необходимости запускать:
  - `python -m app.scripts.cleanup_empty_image_listings --source guazi --dry-run`
  - `python -m app.scripts.cleanup_empty_image_listings --source guazi`
