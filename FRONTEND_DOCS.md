# Frontend Documentation

Актуально для проекта `CSS&HTML Site`.

## 1. Обязательный регламент работы

Этот регламент обязателен для всех следующих фронтенд-правок.

1. Перед любыми изменениями во фронтенде сначала читать:
   - `FRONTEND_DOCS.md`
   - `FRONTEND_CHANGELOG.md`
2. После изменений обязательно обновлять оба файла:
   - какие файлы изменены;
   - что именно изменено;
   - какие модули/секции могли быть затронуты косвенно.
3. Если правка затрагивает поведение, связанное с `data-*` атрибутами, обновлять разделы "Карта страниц" и "Связи разметки и JS".
4. Если добавлен новый модуль JS или новая крупная секция CSS, добавлять его в раздел "Карта файлов".
5. Если правка ломает прежние предположения из документа, сначала исправить документ, потом продолжать следующую задачу.

## 1.1 Связанный журнал

- Подробный лог задач и правок: `FRONTEND_CHANGELOG.md`.
- Этот журнал используется как обязательная часть документации.
- Клиентское описание фронта (для заказчика): `CLIENT_OVERVIEW.md`.
- SEO-практики и план продвижения: `SEO_GUIDE.md`.

## 2. Технологический профиль

- Архитектура: multi-page статический сайт без сборщика.
- Frontend stack:
  - HTML страницы (`index.html`, `pages/*.html`, `404.html`);
  - единый CSS: `css/main.css`;
  - нативные ES-модули: `js/app.js` + `js/modules/*.js`;
  - GSAP и плагины загружаются через CDN в каждой странице.
- Общие компоненты шапки/футера подгружаются динамически через fetch:
  - `components/header.html`
  - `components/footer.html`

## 3. Инициализация приложения

Точка входа: `js/app.js`.

Порядок запуска на `DOMContentLoaded`:

1. `loadSharedComponents()`
2. `initPageBg()`
3. `initScrollSmoother()`
4. `initHeader()`
5. `initCookieNotice()`
6. `initLeadModal()`
7. `initAutoIzKitaya()`
8. `initManualMarketCars()`
9. `initLatestCarsHome()`
10. `initAnimations()`
11. `initReviewsCarousel()`
12. `initHeroStrip()`
13. `initTiltCards()`
14. `initScrollProgress()`
15. `initAnalytics()`

Вызов каждого модуля обёрнут в `safeInit`, чтобы ошибка одного блока не останавливала весь фронт.

## 4. Карта файлов

### 4.1 Ключевые frontend директории

- `index.html` — главная.
- `pages/*.html` — внутренние страницы.
- `404.html` — страница 404.
- `components/header.html` — общая шапка.
- `components/footer.html` — общий футер.
- `css/main.css` — весь UI и адаптив.
- `js/app.js` — orchestrator инициализации.
- `js/modules/*.js` — функциональные модули.

### 4.2 JS-модули и ответственность

- `js/modules/components.js`
  - инжект header/footer;
  - проставляет логотип (`[data-logo]`);
  - нормализует ссылки с `./` по `data-root`.
- `js/modules/header.js`
  - sticky header;
  - класс `is-detached` на скролле;
  - dropdown меню (`details.nav-dd`);
  - active-link логика и hash-scroll;
  - пересчёт `--header-offset`.
- `js/modules/cookies.js`
  - cookie banner (`localStorage: cookieAccepted`).
- `js/modules/modal-lead.js`
  - модалка заявки;
  - auto-open логика;
  - отправка заявки в API (`/api/lead` и fallback);
  - anti-spam (honeypot).
- `js/modules/latest-cars-home.js`
  - карточки на главной (`data-latest-home`), автообновление;
  - hover-галерея фото в карточках (desktop/fine pointer);
  - модалка подробностей с доп. фото и описанием по кнопке `Подробнее`.
- `js/modules/auto-iz-kitaya.js`
  - каталог Китая;
  - фильтры, пагинация, карточки, detail modal, lightbox.
- `js/modules/auto-manual-market.js`
  - каталоги Японии/Кореи;
  - фильтры, пагинация, detail modal, lightbox.
  - в detail-модалке выводит `auction_grade` (оценка аукциона) при наличии.
- `js/modules/animations.js`
  - reveal/hero анимации (GSAP + ScrollTrigger).
- `js/modules/reviews-carousel.js`
  - бесконечная карусель отзывов.
- `js/modules/hero-strip.js`
  - горизонтальный strip с drag/wheel/snap.
- `js/modules/tilt-cards.js`
  - tilt эффект карточек на desktop.
- `js/modules/scroll-smoother.js`
  - GSAP ScrollSmoother (десктоп, без reduce motion/coarse pointer).
- `js/modules/scroll-progress.js`
  - верхний прогресс скролла.
- `js/modules/page-bg.js`
  - интерактивный фон.
- `js/modules/analytics.js`
  - заготовка под аналитику, запуск после cookie consent.

## 5. Карта страниц и привязка к модулям

- `index.html`
  - hero, блок фактов `.hero__facts`, секции latest (`data-latest-home`), отзывы (`data-carousel="reviews"`), этапы;
  - модалка карточки latest: `data-latest-card-modal` (подробности, фото, характеристики);
  - работает `latest-cars-home`, `reviews-carousel`, `animations`, `modal-lead`, `cookies`, `header`.
- `pages/auto-iz-kitaya.html`
  - root `data-china-cars`;
  - модалки `data-china-car-modal` и `data-china-lightbox`;
  - модуль `auto-iz-kitaya.js`.
- `pages/auto-iz-yaponii.html` и `pages/auto-iz-korei.html`
  - root `data-manual-cars`;
  - модалки `data-manual-car-modal` и `data-manual-lightbox`;
  - модуль `auto-manual-market.js`.
- `pages/kalkulyator-stoimosti.html`
  - калькулятор реализован inline-скриптом в странице;
  - общие модули (header, modal, cookies, animations) также подключены.
- Контентные страницы (`faq`, `dostavka`, `process-podbora`, `dogovor-i-garantii`, `kontakty`, `rastamozhka-i-poshliny`, `privacy`, `consent`, `404`)
  - используют общую шапку/футер;
  - где есть форма заявки: `data-lead-modal`.

## 6. Связи разметки и JS (критично)

Нельзя менять эти `data-*` атрибуты без синхронной правки соответствующего модуля:

- Header:
  - `[data-header]`, `[data-nav]`, `[data-logo]`.
- Lead modal:
  - `[data-lead-modal]`, `[data-open-lead-modal]`, `[data-modal-close]`, `[data-lead-form]`.
- Cookie:
  - `[data-cookie]`, `[data-cookie-accept]`.
- Latest home:
  - `[data-latest-home]`, `[data-latest-home-list]`, `[data-latest-home-status]`, `[data-latest-home-updated]`.
  - modal selectors:
    - `[data-latest-card-modal]`, `[data-latest-card-close]`
    - `[data-latest-card-title]`, `[data-latest-card-meta]`, `[data-latest-card-updated]`
    - `[data-latest-card-description]`, `[data-latest-card-main-img]`, `[data-latest-card-thumbs]`, `[data-latest-card-specs]`
    - `[data-latest-card-status]`, `[data-latest-card-section-link]`
- China catalog:
  - `[data-china-cars]` и дочерние `data-china-*`.
- Manual market catalog:
  - `[data-manual-cars]` и дочерние `data-manual-*`.
- Reviews:
  - `[data-carousel="reviews"]`, `[data-carousel-track]`.

## 7. CSS-структура (основные зоны)

Файл: `css/main.css`.

Крупные блоки:

1. Variables / Base / Page background
2. Layout (`container`, `site-main`, button system)
3. Header (`.site-header`, `.site-nav`, `.brand`, `.site-actions`, `is-detached`)
4. Hero и strip
5. Sections/cards/reviews/steps
6. Footer
7. Cookie
8. Modal + form controls
9. Catalog blocks (`china-cars*`, `china-car*`, `manual-car*`, lightbox)
10. Media queries

Примечание: по проекту используется один общий CSS для всех страниц. Любая правка в хедере/кнопках/модалках почти всегда глобальная.

Дополнительно по шапке и мобильному скроллу:

- Размер логотипа (`.brand__logo`) задается через CSS:
  - базовый размер для mobile/tablet: `70px` (и `62px` на `max-width: 520px`);
  - отдельное увеличение только на desktop в `@media (min-width: 861px)`.
  - текущее desktop-значение (static): `inline-size: 100px`.
  - текущее desktop-значение (detached): `inline-size: 82px` через `.site-header.is-detached .brand__logo`.
- При скролле изменение размера логотипа задается только явным override в CSS, без JS-логики.
- Подложка статичной шапки задается через `.site-header:not(.is-detached)::before`:
  - полупрозрачный фон + blur для читаемости логотипа и меню на баннере;
  - при `is-detached` эта подложка отключается (opacity 0), чтобы не вмешиваться в скролл-стиль.
- Фон шапки в `is-detached` сделан менее прозрачным для читаемости:
  - `.site-header.is-detached .site-header__inner { background: rgba(9, 18, 46, 0.74); }`
- Переход между static и `is-detached` делается плавно через `transition`:
  - у `.site-header__inner` (ширина, padding, фон, границы, blur);
  - у `.brand__logo` (размер).
- Для защиты от бокового сдвига страницы на мобильных в корне включено ограничение горизонтального overflow (`html/body`).

Hero readability:

- Для лучшей читаемости на баннере у `.hero__kicker`, `.hero__title`, `.hero__lead` используется многослойный `text-shadow`.
- Тени сделаны в холодной темной гамме и не меняют layout блока, только контраст текста.
- В нижней зоне hero добавлен блок фактов `.hero__facts` (4 ключевых метрики компании) с glass-подложкой и таймлайн-разметкой:
  - на desktop: 4 колонки с верхней разделительной линией (без точек-маркеров над колонками);
  - на mobile: карточки перестраиваются в сетку 2x2 без горизонтального скролла.
  - текущее выравнивание: верхние значения и подписи центрируются внутри колонок;
  - текущая типографика: верхняя строка сделана компактнее, а нижняя строка чуть крупнее для лучшей читаемости.
  - текущий акцент: мягкая волна свечения текста идет последовательно слева направо (1 -> 4 колонка) через `--facts-wave-delay` и `heroFactsSoftWave`.

## 8. API и fallback-логика фронта

- Lead form:
  - основной endpoint: `https://api.primcom.ru/api/lead`;
  - fallback: относительный `/api/lead`;
  - возможен токен через `window.PRIMCOM_LEAD_TOKEN`.
- China catalog:
  - endpoint кандидаты формируются в `auto-iz-kitaya.js`.
- Japan/Korea:
  - list и detail endpoint в `auto-manual-market.js`;
  - поддерживаются `data-list-api`, `data-detail-api` на странице.
  - в detail-модалке на странице Японии строка цены отображается как `Цена` (без длинной подписи).
- Главная подборка:
  - читает `data-api-path`, `data-source`, `data-expected-source` из секций.
  - `js/modules/latest-cars-home.js` использует жёсткие presets по `id` секций:
    - `latest-japan-home`
    - `latest-china-home`
    - `latest-korea-home`
  - если у секции отсутствует `data-api-path`, модуль НЕ уходит в fallback на Китай, а показывает статус ошибки секции.
  - карточки дополнительно фильтруются по `item.source` через `data-expected-source`, чтобы исключить смешивание рынков при кэше/некорректном ответе API.
  - detail-данные карточек кэшируются на клиенте:
    - in-memory map на время текущей страницы;
    - `localStorage` (`latest-home-detail-cache:v1`) с TTL ~12 часов и лимитом записей, чтобы при повторном заходе не ждать загрузку уже известных карточек.
  - на карточках главной:
    - hover по фото (desktop/fine pointer) переключает фото внутри карточки;
    - есть индикаторы количества/позиции фото;
    - пока галерея карточки догружается, поверх фото показывается статус `Фото загружаются`;
    - статус скрывается, когда в карточке доступны дополнительные фото для прокрутки;
    - `Подробнее` и клик по фото открывают модалку карточки (без перехода на страницу);
    - в модалке есть описание, характеристики и доп. фото;
    - кнопка `Источник` в карточке отсутствует;
    - переход в market-страницу остается только через `Перейти в раздел` (в шапке секции и внутри модалки).

## 9. Правила безопасных правок

1. Для правок шапки всегда проверять:
   - `components/header.html`
   - `css/main.css`
   - `js/modules/header.js`
2. Для правок ссылок и путей учитывать `data-root`:
   - главная: `data-root="./"`
   - вложенные страницы: `data-root="../"`
3. Для новых блоков с JS обязательно:
   - добавить стабильный `data-*` селектор в HTML;
   - описать его здесь (раздел 6).
4. Для любых правок анимаций учитывать fallback без GSAP (в проекте предусмотрен graceful degradation).
5. Для мобильных правок проверять минимум брейкпоинты:
   - `max-width: 860px`
   - `max-width: 520px`
   - `max-width: 700px` (catalog/lightbox)
6. Для секций каталога и "Свежих подборок" всегда проводить мобильную проверку:
   - главная (`/`) на viewport около `390x844`;
   - страницы маркетов (`/pages/auto-iz-yaponii.html`, `/pages/auto-iz-kitaya.html`, `/pages/auto-iz-korei.html`);
   - контроль, что карточки каждой секции соответствуют ее рынку.

## 10. Обязательный процесс обновления документации после правок

После каждой фронтенд-правки обновлять:

1. `FRONTEND_DOCS.md`:
   - какие секции затронуты;
   - если появились новые правила/селекторы/модули.
2. `FRONTEND_CHANGELOG.md`:
   - дата;
   - задача;
   - изменённые файлы;
   - эффект и риски.
3. `SEO_GUIDE.md`:
   - если правка связана с SEO (meta, robots, sitemap, structured data, индексация, продвижение), фиксировать изменение и ожидаемый эффект.

## 11. Журнал изменений документации

### 2026-02-27

- Для блока `.hero__facts` уточнены актуальные параметры:
  - центрирование верхней и нижней строк;
  - уменьшение верхних значений (`5 лет`, `400+`, `Все виды`, `3 страны`);
  - небольшое увеличение нижних подписей.

### 2026-02-27

- На главной в hero задокументирован новый блок `.hero__facts`:
  - состав контента (5 лет, 400+, все виды транспорта/техники, 3 страны);
  - поведение desktop/mobile и стилизация как таймлайн-факты.
- Для `auto-manual-market.js` зафиксировано обновление label строки цены в модалке:
  - `Цена` вместо длинной формулировки.

### 2026-02-22

- Создана базовая документация фронтенда.
- Добавлены:
  - архитектура запуска;
  - карта файлов и модулей;
  - карта страниц;
  - связи разметки и JS через `data-*`;
  - правила безопасных правок;
  - обязательный регламент поддержки документации в актуальном состоянии.

### 2026-02-22

- Добавлен обязательный linked-файл журнала правок:
  - `FRONTEND_CHANGELOG.md`.
- Обновлён регламент:
  - перед правками читать оба файла;
  - после правок обновлять оба файла.

### 2026-02-22

- Уточнена логика главной секции подборок:
  - закреплены обязательные `data-source`/`data-expected-source`;
  - зафиксирована изоляция рынков по `item.source` в `latest-cars-home.js`;
  - убран риск silent fallback на Китай при неполных атрибутах секции.
- В правила добавлен обязательный mobile QA для разделов с карточками.

### 2026-02-22

- Обновлены правила для шапки:
  - логотип на desktop увеличивается только через media query;
  - в состоянии `is-detached` размер логотипа остается неизменным.
- Добавлена фиксация от горизонтального "уезда" страницы на мобильных через root overflow guard.

### 2026-02-22

- Логотип шапки в статичном desktop-состоянии увеличен до `90px`.
- Подтверждено правило: при скролле (`is-detached`) размер логотипа не изменяется.

### 2026-02-22

- Добавлен CSS override для `is-detached`, чтобы разделить размеры логотипа:
  - static desktop: `100px`;
  - detached desktop: `82px`.

### 2026-02-22

- Добавлена полупрозрачная подложка под статичную шапку:
  - реализована через псевдо-элемент `.site-header::before`;
  - активна только в `:not(.is-detached)`.

### 2026-02-22

- Усилена читаемость текста в hero-блоке:
  - добавлены тени для `.hero__kicker`, `.hero__title`, `.hero__lead`.

### 2026-02-22

- Подложка шапки в состоянии прокрутки (`is-detached`) сделана менее прозрачной:
  - фон `.site-header__inner` повышен до `rgba(9, 18, 46, 0.74)`.

### 2026-02-22

- Добавлена плавная анимация перехода шапки между static и `is-detached`:
  - анимируются параметры контейнера `.site-header__inner`;
  - анимируется размер логотипа `.brand__logo`.

### 2026-02-23

- Главная подборка авто обновлена по UX карточек:
  - добавлена hover-смена фото в карточках (desktop);
  - добавлены индикаторы количества/позиции фото на карточке;
  - `Подробнее` открывает модалку с описанием, характеристиками и доп. фото;
  - убрана кнопка `Источник` только с карточек на главной.

### 2026-02-23

- Для карточек главной добавлен статус загрузки галереи:
  - текст `Фото загружаются` поверх карточки до готовности доп. фото;
  - статус автоматически скрывается, когда прокрутка фото в карточке становится доступна.

### 2026-02-23

- Для latest-карточек добавлен persistent client cache detail-данных:
  - хранение в `localStorage` с TTL/лимитом записей;
  - ускорен повторный просмотр карточек после переходов между страницами в пределах сайта.

### 2026-02-24

- Добавлен отдельный файл `CLIENT_OVERVIEW.md`:
  - единое описание фронта для заказчика простым деловым языком;
  - правило обязательного пополнения файла только после ключевых фронтовых изменений.

### 2026-02-24

- Добавлен файл `SEO_GUIDE.md`:
  - единый практический план SEO-работ для Google и Яндекса;
  - пошаговый чек-лист индексации и продвижения;
  - правило поддержки файла после SEO-правок.

### 2026-02-27

- Закрыты критичные SEO-моменты:
  - исправлена синтаксическая ошибка JSON-LD в `index.html` (валидная structured data на главной);
  - из `robots.txt` убрана блокировка `/components/`, чтобы header/footer оставались доступными роботам;
  - в `pages/auto-iz-yaponii.html` и `pages/auto-iz-korei.html` добавлен полный набор `og/twitter` мета-тегов для корректных social-превью.
