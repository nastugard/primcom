# Выкат на production: пошаговый гайд

Обновлено: 2026-09-13. Актуальная версия ресурсов: `20260913-oswald-1`.

---

## 0. Схема: три разные машины

| Что | Адрес | Доступ | Рабочая папка |
|---|---|---|---|
| Сайт `primcom.ru` | `31.31.197.47` | reg.ru, SFTP/FTP | document root хостинга |
| Backend `api.primcom.ru` | `168.222.194.128` | `ssh root@168.222.194.128` | `/opt/primcom/china_cars_backend` |
| Telegram-боты | `213.232.204.127` | `ssh root@213.232.204.127` | `/opt/primcom/manager-listings-bot` |

Сайт и backend — **разные машины**. Это определяет всё остальное:
публикатор SEO-страниц пишет в локальную файловую систему и не может обновить
сайт на другом хосте, поэтому `SEO_PUBLISH_COMMAND` остаётся пустым (раздел 7).

---

## 1. Два предупреждения, которые важнее всего

### 1.1 Не выкладывайте из папки `deploy/`

Пакет `deploy/primcom-seo-20260814/` собран 14 августа и **устарел**:
в нём версия ресурсов `20260814-seo-topics-1`, а в рабочем дереве `20260913-oswald-1`.
Он не содержит ни заполненных ОГРНИП и ИНН, ни таблиц ставок, ни WebP-баннера,
ни исправления LCP.

**Источник для выката — рабочее дерево репозитория**, а не папка `deploy/`.

### 1.2 Никогда не выкладывайте эти папки

Заливка «всего репозитория целиком» опубликует секреты и исходники.
В document root **не должно попасть**:

| Папка | Почему |
|---|---|
| `telegram-bot_clean_2026-01-23/` | содержит `.env` с **живым токеном Telegram-бота** |
| `china_cars_backend/` | исходники backend, `.env.example`, тесты |
| `manager-listings-bot/`, `primcom-monitor-bot/` | код ботов |
| `scripts/`, `seo/` | публикатор и реестр — должны лежать вне document root |
| `deploy/`, `.git/`, `seo-audit-*/`, `geo-audit-*/` | пакеты, история, отчёты |
| `*.md` в корне | внутренняя документация |
| `primkom-rf/`, `review/`, `nginx/` | старые копии и конфиги |

Отдельно: **токен бота всё ещё читается из истории git**. Отозвать его через
@BotFather нужно независимо от выката — см. коммит `f8f082a`.

---

## 2. Что именно заливать

**Готовый пакет: `deploy/primcom-20260913/site/` — 177 файлов, 2.9 МБ.**
В нём уже нет ничего лишнего, список — в `deploy/primcom-20260913/FILES.txt`.

Собрать заново или проверить состав:

```bash
cd "/Volumes/SID/Колян АВТО/CSS&HTML Site"
{ ls index.html 404.html robots.txt sitemap.xml site.webmanifest; \
  find assets banner components css fonts js logo pages cars guides -type f; } \
  | grep -v '\.DS_Store' | sort
```

Состав:

| Путь | Файлов | Что это |
|---|---|---|
| корень | 5 | `index.html`, `404.html`, `robots.txt`, `sitemap.xml`, `site.webmanifest` |
| `pages/` | 12 | страницы направлений, FAQ, доставка, растаможка, калькулятор, контакты, правовые |
| `cars/` | 125 | 90 моделей + 34 марки + индекс |
| `guides/` | 5 | 4 руководства + индекс |
| `js/` | 20 | `app.js` и модули |
| `css/` | 1 | `main.css` |
| `fonts/` | 4 | три `oswald-*.woff2` и `OFL.txt` |
| `components/` | 2 | шапка и подвал |
| `banner/` | 2 | `banner_main.png` и **новый** `banner_main.webp` |
| `logo/`, `assets/` | 2 | логотип и favicon |

`data/2gis-reviews.json` на сервере уже есть, сайтом не читается — не трогайте.


### 2.1 Удалить с сервера лишние шрифты

На production сейчас лежат и публично скачиваются пять шрифтов, которые сайтом не используются.
Они удалены из репозитория, но заливка «без удаления» их не уберёт — **удалить вручную по SFTP**:

```
fonts/galderglynn-titling.light.otf
fonts/galderglynn-titling.thin.otf
fonts/Racama.otf
fonts/Vladivostok regular.ttf
fonts/galderglynntitlingbk_regular.ttf
fonts/galderglynntitlingbl_regular.ttf
fonts/galderglynntitlingrg_bold.ttf
logo/logo 3 dark.svg
logo/logo 3 light.svg
logo/logo 3 dark — копия.jpg
```

Первые семь — платные шрифты, заменённые на Oswald. Последние три не используются,
причём `— копия.jpg` на деле SVG с чужим расширением и браузером не отрисовывается.

Причина не только в 400 КБ. Это платные шрифты сторонних авторов, и метаданные
`Vladivostok regular.ttf` прямо запрещают их передачу: «This font may not be given away».
Сейчас любой может скачать их с сайта. Подробности — в `FONTS_LICENSE_CHECK.md`.

После удаления проверить, что оставшиеся два отдаются:

```bash
curl -I https://primcom.ru/fonts/oswald-cyrillic.woff2            # 200
curl -I https://primcom.ru/fonts/galderglynn-titling.light.otf    # ожидается 404
```


## 2.2 Файл `.htaccess`

В пакете лежит `.htaccess` для корня сайта. Он **скрытый**: во многих FTP-клиентах
нужно включить показ скрытых файлов, иначе вы его не увидите.

Закрывает четыре подтверждённые проблемы: заглушку reg.ru вместо своей страницы 404,
отсутствие редиректа с www, полное отсутствие заголовков безопасности
и отсутствие `Cache-Control` у шрифтов и WebP-баннера.

Важно про схему: nginx на reg.ru отдаёт `css`, `js`, `png`, `jpg` сам, а `woff2`,
`webp` и HTML пробрасывает на Apache — видно по разному формату ETag.
Значит правила применятся к тому, что идёт через Apache; заголовки безопасности
на css и js могут не появиться, и для них нужна настройка nginx через поддержку.

**Если после заливки сайт отдаёт 500** — хостинг не принял какую-то директиву.
Переименуйте файл в `.htaccess.off`, сайт поднимется сразу.

HSTS выставлен на неделю, а не на год: браузер запоминает запрет на http,
и быстро откатить это невозможно. Через неделю нормальной работы срок можно поднять.

---

## 3. Перед заливкой

### 3.1 Узнать document root

В панели reg.ru: «Сайты» → `primcom.ru` → «Корневая директория».
Типичный вид: `/var/www/uXXXXXXX/data/www/primcom.ru`.

Если есть SSH-доступ, проверить можно так:

```bash
ls -la /var/www/*/data/www/primcom.ru/index.html
```

### 3.2 Сделать резервную копию

Скачать текущий document root целиком по SFTP в локальную папку с датой.
**Без рабочего бэкапа дальше не идти** — это единственный путь отката.

### 3.3 Проверить локальную сборку

```bash
cd "/Volumes/SID/Колян АВТО/CSS&HTML Site"
node scripts/check-seo-pages.mjs          # ожидается: 130 generated, 141 sitemap
python3 scripts/build-customs-tables.py --check   # ожидается: совпадают с config.py
```

Обе команды должны пройти. Если вторая падает — сначала выполнить
`python3 scripts/build-customs-tables.py`, иначе сайт покажет ставки,
отличные от расчёта калькулятора.

---

## 4. Заливка

Заливать **с перезаписью, без удаления** серверных файлов.

Порядок важен в одном месте: `sitemap.xml` — **последним**. Иначе робот может
прийти по новому URL раньше, чем появится страница.

1. `banner/` — включая новый `banner_main.webp`
2. `css/`, `js/`, `fonts/`, `components/`, `logo/`, `assets/`
3. `pages/`
4. `cars/`, `guides/`
5. `index.html`, `404.html`, `robots.txt`, `site.webmanifest`
6. **`sitemap.xml`**

Если на хостинге есть SSH и rsync:

```bash
SITE_ROOT=/var/www/uXXXXXXX/data/www/primcom.ru
rsync -av --exclude='.DS_Store' \
  index.html 404.html robots.txt site.webmanifest \
  assets banner components css fonts js logo pages cars guides \
  user@primcom.ru:"$SITE_ROOT/"
rsync -av sitemap.xml user@primcom.ru:"$SITE_ROOT/"
```

Обратите внимание: `sitemap.xml` намеренно вынесен во вторую команду.

---

## 5. Проверка после заливки

### 5.1 Доступность

```bash
curl -I https://primcom.ru/
curl -I https://primcom.ru/cars/
curl -I https://primcom.ru/cars/japan/toyota/
curl -I https://primcom.ru/guides/
curl -I https://primcom.ru/banner/banner_main.webp
curl -s https://primcom.ru/sitemap.xml | grep -c '<loc>'
```

Ожидается: пять раз `200`, затем `141`.

### 5.2 Что новая версия действительно доехала

```bash
# версия ресурсов должна быть customs-rates-1
curl -s https://primcom.ru/ | grep -o 'v=20260913-oswald-1' | head -1

# реквизиты заполнены, прочерков быть не должно
curl -s https://primcom.ru/pages/privacy.html | grep -o 'ОГРНИП: [0-9]*'

# таблицы ставок на месте
curl -s https://primcom.ru/pages/rastamozhka-i-poshliny.html | grep -c '<table'
```

Ожидается: строка с версией, `ОГРНИП: 322253600067330`, и `6`.

### 5.3 Калькулятор не пострадал

Открыть `https://primcom.ru/pages/kalkulyator-stoimosti.html`, заполнить форму,
нажать расчёт. Должны заполниться пошлина, акциз, утильсбор, НДС и итог.
Калькулятор ходит в `api.primcom.ru` — если он молчит, проблема на backend, а не в заливке.

### 5.4 Служебные файлы не отдаются

```bash
curl -I https://primcom.ru/.primcom-seo-publish.lock
```

Ожидается `403` или `404`. Если файл отдаётся — попросить reg.ru закрыть dot-файлы.

### 5.5 Сообщить поисковым системам

- Яндекс.Вебмастер → «Индексирование» → «Файлы Sitemap» → `https://primcom.ru/sitemap.xml`
- Google Search Console → «Файлы Sitemap» → тот же адрес

Ни Вебмастер, ни GSC сейчас не подключены. Это стоит сделать в тот же день:
без них измерить результат выката нечем.

---

## 6. Откат

Залить обратно резервную копию из п. 3.2 с перезаписью.
База данных на выкате не затрагивается, откат безопасен и полный.

Частичный откат одной страницы: залить её версию из бэкапа и поднять
версию ресурсов, иначе у части посетителей останется кэш.

---

## 7. Этап 2: backend и бот

**Нужен, только если включается автопубликация.** Сайт от этого этапа не зависит.

Текущее состояние: `SEO_PUBLISH_COMMAND` пуст, потому что публикатор пишет
в локальную ФС, а сайт на другой машине. Три пути описаны ниже; пока не выбран
ни один — этап 2 можно не делать вообще.

Если всё же выкатывать (файлы берутся из рабочего дерева, не из `deploy/`):

```bash
# backend, 168.222.194.128
systemctl list-units --type=service --state=running | grep -E 'primcom-api(-v2)?\.service'
# скопировать app/api/routes.py, app/core/settings.py, app/services/seo_publish.py
systemctl restart primcom-api.service
journalctl -u primcom-api.service -n 100 --no-pager
```

```bash
# боты, 213.232.204.127
# скопировать manager-listings-bot/main.py
systemctl restart primcom-manager-listings-bot.service
journalctl -u primcom-manager-listings-bot.service -n 100 --no-pager
```

Если работает `primcom-api-v2.service`, перезапускать именно его.
Миграция базы и перезапуск скрейперов не нужны.

Сообщение «Автопубликация SEO не настроена на сервере» менеджеру больше не показывается
(коммит `69b0011`): это состояние сервера, а не результат его действия.
Реальные сбои сборки по-прежнему сообщаются.

---

## 8. Как включить автопубликацию

Подробная пошаговая инструкция — `seo/AUTOPUBLISH.md`. Всё необходимое написано и проверено:
`scripts/publish-and-sync.mjs` собирает страницы и отправляет на хостинг только изменившиеся файлы.
Папка для сервера собирается командой `bash scripts/build-publisher-bundle.sh`.

Выбор зависит от одного факта о хостинге:

- **Есть SSH и Node.js на reg.ru** (проверка: `ssh` в аккаунт и `node -v`) — публикатор
  ставится на хостинг и запускается по cron. Проще всего.
- **Есть только FTP или SFTP** — сборка идёт на сервере с backend, файлы уходят на хостинг
  по FTP. Работает сразу после карточки, бот показывает результат.
- **Перенос сайта на `168.222.194.128`** — тоже вариант, но требует смены хостинга и здесь не нужен.

## 9. Что сделать после выката

1. Подключить Яндекс.Вебмастер и Яндекс.Метрику, затем Google Search Console.
2. Отозвать токен Telegram-бота через @BotFather.
3. Повторить SEO и GEO аудиты через 3–4 недели — на новой версии, с установленным
   Playwright и `PAGESPEED_API_KEY`.
4. Заняться оставшимися пунктами планов: сроки доставки в днях, размер комиссии,
   `Car`/`Offer` в генераторе, индивидуальные `lastmod`, хабы `/cars/japan/`.
