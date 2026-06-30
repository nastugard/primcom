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
  - GSAP и плагины больше не подключаются статически в HTML: они догружаются runtime-модулем `js/modules/performance-mode.js` только там, где реально нужны.
- Общие компоненты шапки/футера подгружаются динамически через fetch:
  - `components/header.html`
  - `components/footer.html`

## 3. Инициализация приложения

Точка входа: `js/app.js`.

Порядок запуска на `DOMContentLoaded`:

1. `initPerformanceMode()`
2. `loadSharedComponents()`
3. `loadEnhancementRuntime()`
4. `initPageBg()`
5. `initHeader()`
6. `initCookieNotice()`
7. `initLeadModal()`
8. `initAutoIzKitaya()`
9. `initManualMarketCars()`
10. `initLatestCarsHome()`
11. `initImportCalculator()` (лениво, только если есть `[data-import-calculator]`)
12. `initScrollSmoother()` (только вне lite mode)
13. `initAnimations()` (только вне lite mode)
14. `initHeroStrip()` (только вне lite mode)
15. `initTiltCards()` (только вне lite mode)
16. `initScrollProgress()` (только вне lite mode)
17. `initAnalytics()`

Вызов каждого модуля обёрнут в `safeInit`, чтобы ошибка одного блока не останавливала весь фронт.
Модуль калькулятора не импортируется на верхнем уровне общего `app.js`: он догружается динамически только на странице с `[data-import-calculator]`, чтобы проблема с файлом калькулятора не могла остановить модалку заявки и остальные общие блоки сайта.

### 3.1 Performance mode

- Новый модуль: `js/modules/performance-mode.js`.
- Режимы:
  - `full` — обычное поведение сайта;
  - `lite` — облегчённый режим для слабых/бережных устройств.
- Автоматические сигналы для `lite`:
  - `prefers-reduced-motion: reduce`;
  - `matchMedia("(update: slow)")`;
  - `navigator.connection.saveData`;
  - `navigator.hardwareConcurrency <= 4`;
  - `navigator.deviceMemory <= 4`.
- Ручной override через query-string:
  - `?performance=lite`
  - `?performance=full`
  - `?performance=auto` (сброс override)
- Выбранный режим сохраняется в `localStorage` под ключом `primcom-performance-mode`.
- В `lite` режиме:
  - не запускаются `ScrollSmoother`, reveal-анимации, карусель отзывов, hero strip, tilt и scroll progress;
  - отключается интерактивный фон;
  - на карточках главной выключается hover-галерея фото;
  - CSS убирает тяжёлые blur/backdrop-filter/фоновые анимации.
- В `full` режиме runtime догружает только реально нужные библиотеки:
  - `gsap.min.js`
  - `ScrollTrigger.min.js`
  - `ScrollSmoother.min.js` только если на странице есть `#smooth-wrapper` и `#smooth-content`
  - `Observer.min.js` только если есть `.hero-strip`
- `Flip` больше не грузится глобально: модалки и остальные блоки должны корректно работать без него.

## 4. Карта файлов

### 4.1 Ключевые frontend директории

- `index.html` — главная.
- `pages/*.html` — внутренние страницы.
- `404.html` — страница 404.
- `components/header.html` — общая шапка.
- `components/footer.html` — общий футер.
- `css/main.css` — весь UI и адаптив.
- `data/2gis-reviews.json` — локальный источник отзывов 2ГИС для главной.
- `js/app.js` — orchestrator инициализации.
- `js/modules/*.js` — функциональные модули.
- `js/modules/performance-mode.js` — выбор режима производительности и ленивое подключение GSAP runtime.
- `scripts/sync-2gis-reviews.mjs` — синхронизация отзывов 2ГИС в локальный JSON и HTML главной.

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
  - после успешного ответа API отправляет JavaScript-цель Яндекс.Метрики `lead_submit_success`;
  - HTML-формы заявки помечены `ym-disable-submit`, чтобы автоцель Метрики "Отправка формы" не считала попытки без успешного API-ответа;
  - anti-spam (honeypot).
- `js/modules/latest-cars-home.js`
  - карточки на главной (`data-latest-home`), автообновление;
  - локальный snapshot самих списков подборок на главной и фоновая `meta_only` проверка обновлений;
  - hover-галерея фото в карточках (desktop/fine pointer, отключается в lite mode);
  - свайп фото в карточках на мобильном viewport/coarse pointer: горизонтальный жест лениво загружает detail-галерею и переключает фото, вертикальная прокрутка страницы сохраняется;
  - модалка подробностей с доп. фото и описанием по кнопке `Подробнее`.
  - для ручных карточек Китая (`source_listing_id` с префиксом `mgr-china-`) цена отображается в рублях, даже если секция Китая по умолчанию настроена на юани.
- `js/modules/performance-mode.js`
  - определяет `full/lite` режим;
  - сохраняет override в `localStorage`;
  - выставляет `window.__primcomPerformance`;
  - догружает GSAP/плагины только при необходимости.
- `js/modules/auto-iz-kitaya.js`
  - каталог Китая;
  - фильтры, пагинация, карточки, detail modal, lightbox;
  - локальный snapshot списка в `localStorage` и фоновая `meta_only` проверка обновлений;
  - если обложка из сохраненного snapshot больше не открывается, карточка подтягивает detail и подставляет первое актуальное фото.
  - ручные карточки Китая из manager bot (`mgr-china-*`) показывают цену с символом рубля; остальные карточки Китая сохраняют символ юаня.
- `js/modules/auto-manual-market.js`
  - каталоги Японии/Кореи;
  - фильтры, пагинация, detail modal, lightbox.
  - в detail-модалке выводит `auction_grade` (оценка аукциона) при наличии.
  - локальный snapshot списка в `localStorage` и фоновая `meta_only` проверка обновлений.
- `js/modules/animations.js`
  - reveal/hero анимации (GSAP + ScrollTrigger).
- `js/modules/hero-strip.js`
  - горизонтальный strip с drag/wheel/snap.
- `js/modules/tilt-cards.js`
  - tilt эффект карточек на desktop.
- `js/modules/scroll-smoother.js`
  - GSAP ScrollSmoother (десктоп, без reduce motion/coarse pointer, отключается в lite mode).
- `js/modules/scroll-progress.js`
  - верхний прогресс скролла.
- `js/modules/page-bg.js`
  - интерактивный фон, отключается в lite mode.
- `js/modules/analytics.js`
  - единая точка подключения Яндекс.Метрики;
  - счетчик `109674829` запускается после cookie consent;
  - экспортирует `trackYandexGoal(goalName, params)` для отправки JavaScript-целей;
  - подгружает `https://mc.yandex.ru/metrika/tag.js?id=109674829`, включает webvisor, clickmap, ecommerce через `dataLayer`, accurateTrackBounce и trackLinks.

## 5. Карта страниц и привязка к модулям

- `index.html`
  - hero, блок фактов `.hero__facts`, секции latest (`data-latest-home`), отзывы 2ГИС (`section--reviews-2gis`, горизонтальная лента в одну строку), VK Клипы (прямые iframe VK Видео), этапы;
  - модалка карточки latest: `data-latest-card-modal` (подробности, фото, характеристики);
  - VK Клипы на главной поддерживаются как ручной хронологический ряд: самые новые ролики должны стоять первыми слева, старые — дальше вправо;
  - текущий ряд VK Клипов начинается с `456239048`, `456239047`, далее идут сохранённые старые ролики `456239044`, `456239042`, `456239039`, `456239027`, `456239026`, `456239024`, `456239020`;
  - работает `latest-cars-home`, `animations`, `modal-lead`, `cookies`, `header`.
- `pages/auto-iz-kitaya.html`
  - root `data-china-cars`;
  - модалки `data-china-car-modal` и `data-china-lightbox`;
  - модуль `auto-iz-kitaya.js`;
  - форма фильтров помечена `ym-disable-submit`, а кнопка `Показать` имеет `type="button"` и `data-china-cars-apply`, чтобы Метрика не считала фильтрацию отправкой заявки;
  - при повторном открытии может мгновенно показать сохранённый локальный снимок каталога до завершения фоновой проверки API.
- `pages/auto-iz-yaponii.html` и `pages/auto-iz-korei.html`
  - root `data-manual-cars`;
  - модалки `data-manual-car-modal` и `data-manual-lightbox`;
  - модуль `auto-manual-market.js`;
  - форма фильтров помечена `ym-disable-submit`, а кнопка `Показать` имеет `type="button"` и `data-manual-cars-apply`, чтобы Метрика не считала фильтрацию отправкой заявки;
  - при повторном открытии может мгновенно показать сохранённый локальный снимок каталога до завершения фоновой проверки API.
- `pages/kalkulyator-stoimosti.html`
  - root `data-import-calculator`;
  - модуль `import-calculator.js`;
  - страница работает как thin client к backend endpoint `/api/import-calculator/calculate`;
  - при ручном submit формы отправляет JavaScript-цель Яндекс.Метрики `calculator_calculate_click`;
  - форма калькулятора помечена `ym-disable-submit`, чтобы автоцель Метрики "Отправка формы" не смешивалась с целью расчёта;
  - поле цены авто использует `step="any"`, чтобы Safari и другие браузеры не блокировали произвольную сумму;
  - кнопка `Рассчитать` имеет `type="button"`; модуль калькулятора обрабатывает и click кнопки, и submit формы по Enter, чтобы при сбое JS форма не отправлялась GET-запросом в URL;
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
  - успешная отправка заявки трекается только через JavaScript-цель `lead_submit_success` после ответа API; автоцель Метрики "Отправка формы" для оптимизации рекламы не использовать.
  - формы заявки должны сохранять класс `ym-disable-submit`.
- Cookie:
  - `[data-cookie]`, `[data-cookie-accept]`.
- Latest home:
  - `[data-latest-home]`, `[data-latest-home-list]`, `[data-latest-home-status]`, `[data-latest-home-updated]`.
  - фото карточки создаётся как `.latest-home-card__media`; на мобильном устройстве модуль добавляет `.latest-home-card__media--swipe` и обрабатывает `touchstart/touchmove/touchend`;
  - modal selectors:
    - `[data-latest-card-modal]`, `[data-latest-card-close]`
    - `[data-latest-card-title]`, `[data-latest-card-meta]`, `[data-latest-card-updated]`
    - `[data-latest-card-description]`, `[data-latest-card-main-img]`, `[data-latest-card-thumbs]`, `[data-latest-card-specs]`
    - `[data-latest-card-status]`, `[data-latest-card-section-link]`
- China catalog:
  - `[data-china-cars]` и дочерние `data-china-*`;
  - кнопка применения фильтров: `[data-china-cars-apply]`.
- Manual market catalog:
  - `[data-manual-cars]` и дочерние `data-manual-*`;
  - кнопка применения фильтров: `[data-manual-cars-apply]`.
- Import calculator:
  - `[data-import-calculator]`, `[data-calc-form]`, `[data-calc-submit]`, `[data-calc-status]`
  - output selectors:
    - `[data-out-car-price]`, `[data-out-duty]`, `[data-out-excise]`, `[data-out-util]`, `[data-out-vat]`, `[data-out-total]`
    - `[data-out-rule-version]`, `[data-out-exchange-rate]`, `[data-out-util-mode]`
    - `[data-calc-debug]`, `[data-calc-debug-pre]`
  - форма калькулятора должна сохранять класс `ym-disable-submit`; расчет трекается через JavaScript-цель `calculator_calculate_click`.
- Reviews 2ГИС:
  - секция `#reviews.section--reviews-2gis`;
  - HTML между комментариями `<!-- 2GIS_REVIEWS:START -->` и `<!-- 2GIS_REVIEWS:END -->` считается генерируемым и обновляется только скриптом `scripts/sync-2gis-reviews.mjs`.
  - раскладка карточек задаётся CSS-классом `.reviews-2gis__list`: это горизонтальная flex-лента с `overflow-x`, `scroll-snap` и скрытым scrollbar, поэтому sync-скрипт не должен менять HTML-обёртку для прокрутки.

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

## 8. Отзывы 2ГИС

- Источник отзывов: публичная страница 2ГИС и публичный review API 2ГИС для branch `70000001110927328`.
- Локальное хранилище: `data/2gis-reviews.json`.
- Скрипт `scripts/sync-2gis-reviews.mjs`:
  - запрашивает summary со страницы `https://2gis.ru/vladivostok/firm/70000001110927328/tab/reviews`;
  - получает последние отзывы с `public-api.reviews.2gis.com`;
  - нормализует данные;
  - обновляет `data/2gis-reviews.json`;
  - перерисовывает HTML секции отзывов в `index.html`.
- Текущий локальный снимок после синхронизации 2026-06-30: рейтинг 5.0, 7 оценок, 5 отзывов; новые карточки выводятся первыми слева/сверху.
- На сайте отзывы не тянутся напрямую из 2ГИС браузером пользователя: главная использует уже локально обновлённый HTML.
- В карточках отзывов допускаются:
  - аватар автора из `user.photo_preview_urls`, если 2ГИС реально отдаёт непустой URL;
  - fallback на инициалы автора, если avatar URL пустой;
  - мини-галерея фото отзыва из `photos[].preview_urls`.
- Для автоматизации безопаснее запускать только этот sync-скрипт по расписанию, а не менять отзывы вручную в `index.html`.

## 9. Кэш каталогов

- Каталоги `Китай`, `Япония`, `Корея` сохраняют последний успешно загруженный список в `localStorage`.
- Ключ кэша включает текущие фильтры, лимит и offset, поэтому кэш раздельный для каждой комбинации выдачи.
- При загрузке страницы модуль сначала пытается отрисовать локальный snapshot, затем запрашивает у API только метаданные через `meta_only=1`.
- Если `last_scraped_at` и `total` совпадают, повторный полный запрос списка не выполняется.
- Если каталог обновился, модуль делает обычный полный запрос, перерисовывает список и обновляет локальный snapshot.
- Для каталога Китая есть точечный fallback на случай сервисной очистки изображений: если сохраненный `cover_image_url` из snapshot больше не грузится, карточка запрашивает detail конкретного объявления и показывает первое доступное актуальное фото.
- Начальный запрос списка больше не ждёт окончания `facets`: filters и list стартуют параллельно.

## 10. Кэш подборок на главной

- Блоки свежих подборок на главной (`Япония`, `Китай`, `Корея`) тоже сохраняют последний успешно загруженный список в `localStorage`.
- Кэш разделён по секциям главной, API path и источнику данных.
- При повторном заходе на главную подборки сначала показываются из локального snapshot, затем в фоне проверяются метаданные `last_scraped_at` и `total`.
- Если изменений нет, полный список заново не запрашивается.
- Полная загрузка с сервера выполняется только если подборка реально обновилась или локального snapshot ещё нет.

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
- На мобильных (`max-width: 860px`) навигация шапки держится в 1 строку:
  - у `.site-nav__list` отключен перенос (`flex-wrap: nowrap`);
  - у `.site-nav__link` включены `white-space: nowrap` и адаптивный размер через `clamp()`;
  - зазоры между пунктами и размер caret также адаптивные (`clamp()`), чтобы пункты `Авто под заказ`, `Полезное`, `Контакты` не переносились.
- В `is-detached` на desktop у шапки также отключены переносы в nav и включено более компактное адаптивное меню:
  - `.site-nav__link` имеет desktop `clamp()`-размер;
  - `.site-header.is-detached .site-nav__link` и `.site-header.is-detached .site-nav__list` дополнительно уплотняются;
  - ширина glass-контейнера detached синхронизирована с `--container`, чтобы пункты меню не съезжали и не переносились при скролле.

Hero readability:

- Для лучшей читаемости на баннере у `.hero__kicker`, `.hero__title`, `.hero__lead` используется многослойный `text-shadow`.
- Тени сделаны в холодной темной гамме и не меняют layout блока, только контраст текста.
- В нижней зоне hero добавлен блок фактов `.hero__facts` (4 ключевых метрики компании) с glass-подложкой и таймлайн-разметкой:
  - на desktop: 4 колонки с верхней разделительной линией (без точек-маркеров над колонками);
  - на mobile: карточки перестраиваются в сетку 2x2 без горизонтального скролла.
  - текущее выравнивание: верхние значения и подписи центрируются внутри колонок;
  - текущая типографика: верхняя строка сделана компактнее, а нижняя строка чуть крупнее для лучшей читаемости.
  - текущий акцент: мягкая волна свечения текста идет последовательно слева направо (1 -> 4 колонка) через `--facts-wave-delay` и `heroFactsSoftWave`.
- Текущий премиальный шрифтовой профиль на главной:
  - display-family разделен на:
    - `GalderGlynnTitlingLight` (основные заголовки/навигация),
    - `GalderGlynnTitlingThin` (мелкие капсы/лейблы).
  - `.hero__title`, `.section__title`, `.hero__facts-value` используют light-family.
  - `.hero__kicker` и `.hero__facts-kicker` используют thin-family и `letter-spacing: 0.22em`.
  - в header light-family применен к `.site-nav__link`, `.nav-dd__item`, `.header-phone__text`, `.site-header .btn--small`.
  - в footer thin-family используется для `.footer-title`, light-family для `.footer-text` и `.footer-copy`.
  - правила регистра текста:
    - заголовки (`.hero__title`, `.section__title`) и заголовки карточек (`.china-car-card__title`, `.strip-card__title`, `.review-card__title`, `.info-card__title`, `.step__title`, `.modal__title`, `.calc-result__title`) фиксируются в `UPPERCASE` через CSS (`text-transform: uppercase`);
    - значения в блоке достижений `.hero__facts-value` также фиксируются в `UPPERCASE`.
  - подзаголовки используют то же начертание, что и заголовки (light-family), но меньший размер:
    - `.hero__lead`, `.section__lead`, `.china-car__meta`, `.manual-car__meta`.
    - на контентных страницах внутри `.legal` подзаголовки `h2/h3` также используют display-family и `UPPERCASE` с меньшей иерархией размеров.
  - на странице контактов добавлен явный класс `.contacts-section__title` для заголовков `Связь/Офис`, чтобы гарантировать display-family без зависимости от каскада.
  - lead-строка страницы контактов (`.section__lead--contacts`) растягивается на всю ширину контейнера и имеет увеличенный адаптивный размер шрифта.
  - для контактов добавлены секционные модификаторы:
    - `.section--contacts-intro` (меньший нижний отступ);
    - `.section--contacts-content` (меньший верхний отступ),
    чтобы сократить вертикальный разрыв между lead-строкой и блоком `Связь/Офис`.
  - для light/thin в `@font-face` используется `font-display: block`, чтобы убрать заметный переход «толстый -> тонкий» после первого рендера.
  - preload `galderglynn-titling.thin.otf` и `galderglynn-titling.light.otf` расположен перед подключением `main.css` на всех страницах.
  - в hero-блоке кнопка `Оставить заявку` использует display-family (`.hero__cta`), чтобы визуально совпадать с остальными display-элементами.
  - в `hero__actions` оставлена одна CTA-кнопка (`Оставить заявку`); ссылка `Этапы работы` из hero удалена.

## 8. API и fallback-логика фронта

- Lead form:
  - основной endpoint: `https://api.primcom.ru/api/lead`;
  - fallback: относительный `/api/lead`;
  - возможен токен через `window.PRIMCOM_LEAD_TOKEN`.
- China catalog:
  - endpoint кандидаты формируются в `auto-iz-kitaya.js`.
  - цена ручных карточек Китая (`mgr-china-*`) отображается как финальная цена во Владивостоке в рублях; парсерные карточки Китая продолжают использовать валюту секции.
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
  - валюту можно задать секционно через `data-currency`, но ручные карточки Китая (`mgr-china-*`) имеют item-level override на рубли.
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
5. Если меняется общий `css/main.css` или `js/app.js`, вручную поднимать query-параметр версии на всех HTML-страницах: виртуальный хостинг держит долгий cache-control для статики.
6. Для мобильных правок проверять минимум брейкпоинты:
   - `max-width: 860px`
   - `max-width: 520px`
   - `max-width: 700px` (catalog/lightbox)
7. Для секций каталога и "Свежих подборок" всегда проводить мобильную проверку:
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

### 2026-04-15

- Мобильное модальное окно характеристик авто использует компактный двухколоночный layout:
  - слева ключ (`.manual-car__spec-key`);
  - справа значение (`.manual-car__spec-val`).
- Layout общий для главной и страниц Японии/Кореи/Китая, потому что все они используют одни и те же классы `manual-car__spec-*`.

### 2026-04-15

- Мобильные модалки с классами `.modal__dialog` и `.modal__dialog--wide` раскрываются на всю ширину/высоту экрана от `700px` и ниже.
- Кнопка `.modal__close` в мобильной версии намеренно сделана более контрастной, потому что лежит поверх фото и тёмного контента.
- У wide-модалок карточек авто (`.modal__dialog--wide`) mobile override должен идти позже базового desktop-правила, иначе ширина снова схлопывается и справа становится видна страница под модалкой.
