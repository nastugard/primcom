# Frontend Change Log

Цель файла: фиксировать все изменения фронтенда с объяснением "что", "зачем", "где" и "какой эффект".

## Обязательный порядок ведения

1. Перед любыми правками фронтенда читать:
   - `FRONTEND_DOCS.md`
   - `FRONTEND_CHANGELOG.md`
2. После каждой фронтенд-правки добавлять новую запись в этот файл.
3. Запись добавляется даже для небольших правок (1-2 строки CSS/HTML/JS).
4. Если изменение откатили, это тоже фиксируется отдельной записью.

## Формат записи

- Дата: `YYYY-MM-DD`
- Задача: коротко
- Зачем: причина изменения
- Изменённые файлы: список путей
- Что сделано: конкретные изменения
- Проверка: как проверили (визуально/логически/командами)
- Риски/заметки: что учитывать в следующих задачах

---

## Записи

### 2026-02-28

Задача: Доработать типографику страницы контактов: зафиксировать display-шрифт для `Связь/Офис` и увеличить lead-фразу под заголовком.

Зачем: Визуально казалось, что `Связь`/`Офис` рендерятся не тем же шрифтом; также нужно было растянуть и усилить фразу `Владивосток. Можно написать, позвонить или приехать в офис компании Примком.`.

Изменённые файлы:
- `css/main.css`
- `pages/kontakty.html`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `pages/kontakty.html`:
  - lead-фразе добавлен класс `.section__lead--contacts`;
  - заголовкам `Связь` и `Офис` добавлен класс `.contacts-section__title`.
- В `css/main.css`:
  - `.section__lead--contacts`: снят лимит `max-inline-size`, растянуто на ширину контейнера, увеличен шрифт (`clamp`) и межстрочка;
  - `.contacts-section__title`: явно задано семейство `GalderGlynnTitlingLight`, uppercase и та же размерная шкала, что у контентных `h2`.
- Обновлён cache-bust общего CSS на всех страницах:
  - `?v=20260228-fonts-global-11`.

Проверка:
- `rg -n "section__lead--contacts|contacts-section__title" pages/kontakty.html css/main.css`
- `rg -n "main\\.css\\?v=20260228-fonts-global-11" index.html 404.html pages/*.html | wc -l` -> `14`.

Риски/заметки:
- Lead-фраза на контактах стала заметно крупнее; на узких экранах размер контролируется `clamp`, чтобы сохранить читаемость без переломов.

### 2026-02-28

Задача: Исправить «съезд» пунктов навигации в шапке при переходе в `is-detached` на desktop.

Зачем: При скролле и сжатии glass-шапки ссылки `Авто под заказ`, `Полезное`, `Контакты` переносились/ломали строку.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Для nav в шапке зафиксирован однострочный режим:
  - `.site-nav__list` -> `flex-wrap: nowrap`;
  - `.site-nav__item` -> `flex: 0 0 auto`;
  - `.site-nav__link` и `.nav-dd__summary` -> `white-space: nowrap`.
- На desktop применен адаптивный размер nav-ссылок через `clamp()`.
- Для detached-состояния добавлено дополнительное уплотнение:
  - меньше gap в `.site-header.is-detached .site-nav__list`;
  - чуть меньше размер шрифта в `.site-header.is-detached .site-nav__link`;
  - уменьшен gap в `.site-header.is-detached .site-actions`.
- Ширина detached-контейнера увеличена до `min(var(--container), calc(100% - 32px))`, чтобы убрать переломы строки в nav при скролле.
- Обновлён cache-bust общего CSS на всех страницах:
  - `?v=20260228-fonts-global-10`.

Проверка:
- `rg -n "site-nav__list|site-nav__item|site-nav__link|nav-dd__summary|site-header\\.is-detached" css/main.css`
- `rg -n "main\\.css\\?v=20260228-fonts-global-10" index.html 404.html pages/*.html | wc -l` -> `14`.

Риски/заметки:
- На узких ноутбуках при включённом zoom браузера >100% nav всё равно может стать плотным; базовый перенос строк в меню отключен намеренно по задаче.

### 2026-02-28

Задача: Удержать пункты меню шапки в 1 строку на мобильных за счёт адаптивного уменьшения шрифта.

Зачем: На мобильных экранах пункты `Авто под заказ`, `Полезное`, `Контакты` переносились на вторую строку; требование — всегда одна строка без переносов.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В мобильных правилах шапки (`@media (max-width: 860px)`) изменены параметры навигации:
  - `.site-nav` растянут на ширину ряда (`inline-size: 100%`);
  - `.site-nav__list` -> `flex-wrap: nowrap`, адаптивный `gap: clamp(...)`;
  - `.site-nav__link` -> `font-size: clamp(...)`, `white-space: nowrap`, уменьшен `letter-spacing`;
  - `.nav-dd__summary` и `.nav-dd__caret` получили адаптивные зазоры/размеры для экономии ширины.
- Для узких экранов (`@media (max-width: 520px)`) добавлено дополнительное уменьшение:
  - меньший `gap` между пунктами;
  - меньший адаптивный размер `.site-nav__link`.
- Обновлён cache-bust общего CSS на всех страницах:
  - `?v=20260228-fonts-global-9`.
- Документация (`FRONTEND_DOCS.md`) дополнена правилом «мобильное меню шапки в 1 строку».

Проверка:
- `rg -n "max-width: 860px|max-width: 520px|site-nav__list|site-nav__link|white-space: nowrap|clamp\\(" css/main.css`
- `rg -n "main\\.css\\?v=20260228-fonts-global-9" index.html 404.html pages/*.html | wc -l` -> `14`.

Риски/заметки:
- На очень узких экранах (~320px) текст в nav уменьшен сильнее обычного ради сохранения 1 строки.

### 2026-02-28

Задача: Скорректировать hero-кнопки на главной: единый шрифт для `Оставить заявку` и убрать `Этапы работы`.

Зачем: По задаче нужно оставить в баннере только одну CTA и привести её типографику к общему display-стилю сайта.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `index.html` в блоке `.hero__actions` удалена кнопка-ссылка `Этапы работы`.
- Кнопке `Оставить заявку` добавлен класс `.hero__cta`.
- В `css/main.css` для `.hero__cta` задан display-шрифт:
  - `font-family: var(--font-display)`;
  - `font-weight: 400`;
  - `letter-spacing: 0.01em`.
- Обновлён cache-bust общего CSS на всех страницах:
  - `?v=20260228-fonts-global-8`.
- В `FRONTEND_DOCS.md` добавлено правило по hero CTA и составу `.hero__actions`.

Проверка:
- `rg -n "hero__actions|hero__cta|Оставить заявку|Этапы работы" index.html css/main.css`
- `rg -n "main\\.css\\?v=20260228-fonts-global-8" index.html 404.html pages/*.html | wc -l` -> `14`.

Риски/заметки:
- При кэше старого HTML/CSS нужно сделать hard reload, чтобы убрать старую вторую кнопку из hero.

### 2026-02-28

Задача: Вернуть капс в заголовках/карточках на внутренних страницах и привести подзаголовки к тому же шрифтовому начертанию, что и заголовки.

Зачем: На части страниц заголовки и карточки визуально ушли из `UPPERCASE`, а подзаголовки (`h2/h3` в контентных блоках) оставались в другом стиле.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `css/main.css` добавлены правила для контентных подзаголовков:
  - `.legal h2`, `.legal h3` переведены на display-family (`var(--font-display)`), с уменьшенной иерархией размеров и `text-transform: uppercase`.
- Проверена/сохранена типографическая политика капса для:
  - `.section__title`, `.china-car-card__title` и других title-классов карточек/модалок.
- Для немедленного применения правок обновлён cache-bust `main.css` на всех страницах:
  - `?v=20260228-fonts-global-7`.
- В `FRONTEND_DOCS.md` зафиксировано правило для `.legal h2/h3` (подзаголовки в том же display-начертании, что и заголовки).

Проверка:
- `rg -n "\\.legal h2|\\.legal h3|\\.section__title|\\.china-car-card__title|text-transform: uppercase;" css/main.css`
- `rg -n "main\\.css\\?v=20260228-fonts-global-7" index.html 404.html pages/*.html | wc -l` -> `14`.
- Ручная проверка, что все страницы с общим `main.css` получили новую версию query-параметра.

Риски/заметки:
- После обновления query-параметра кэш CSS сбрасывается; если где-то виден старый стиль, нужно сделать hard reload страницы.

### 2026-02-28

Задача: Синхронизировать шрифты баннера/достижений и дополнительно скорректировать header/footer в том же профиле.

Зачем: В блоке «Примком в цифрах» значения выглядели тяжелее заголовка баннера; в шапке/футере был разнобой по гарнитуре; на страницах был заметен переход веса при догрузке.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `404.html`
- `pages/auto-iz-kitaya.html`
- `pages/auto-iz-korei.html`
- `pages/auto-iz-yaponii.html`
- `pages/consent.html`
- `pages/dogovor-i-garantii.html`
- `pages/dostavka.html`
- `pages/faq.html`
- `pages/kalkulyator-stoimosti.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/process-podbora.html`
- `pages/rastamozhka-i-poshliny.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `css/main.css` шрифты разделены на отдельные семейства:
  - `GalderGlynnTitlingLight` (light),
  - `GalderGlynnTitlingThin` (thin),
  - оба с `font-display: block`.
- Блок достижений синхронизирован с баннером:
  - `.hero__facts-value` использует light-family (как `hero__title`).
- В header переведены на light-family:
  - `.site-nav__link`, `.nav-dd__item`, `.header-phone__text`, `.site-header .btn--small`.
- В footer переведены на профиль:
  - `.footer-title` -> thin-family;
  - `.footer-text`, `.footer-copy` -> light-family.
- На всех страницах preload шрифтов `thin/light` расположен перед `main.css`.
- На всех страницах обновлён cache-bust CSS:
  - `main.css?v=20260228-fonts-global-5`.

Проверка:
- `rg -n "GalderGlynnTitlingLight|GalderGlynnTitlingThin|site-nav__link|footer-title|hero__facts-value|font-display" css/main.css`
- `rg -n "css/main.css\\?v=20260228-fonts-global-5" index.html 404.html pages/*.html | wc -l` -> `14`.
- Проверка порядка тегов в `head`:
  - `preload` (`thin/light`) расположен выше `rel=\"stylesheet\"` во всех страницах.

Риски/заметки:
- `font-display: block` убирает «перещелкивание» веса, но при очень медленном соединении текст display-элементов может кратко появляться с задержкой.

### 2026-02-28

Задача: Перевести заголовки и kicker на новые thin/light веса GalderGlynnTitling для более премиальной типографики.

Зачем: По задаче нужно смягчить подачу заголовков (light) и сделать мелкие капсы более изящными (thin + увеличенный трекинг).

Изменённые файлы:
- `css/main.css`
- `index.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `css/main.css` подключены новые `@font-face`:
  - `galderglynn-titling.thin.otf` как `font-weight: 200`;
  - `galderglynn-titling.light.otf` как `font-weight: 300`.
- На главной изменена типографика:
  - `.hero__title` -> `font-weight: 300`;
  - `.section__title` -> `font-weight: 300`;
  - `.hero__kicker` и `.hero__facts-kicker` -> `font-family: var(--font-display)`, `font-weight: 200`, `letter-spacing: 0.22em`.
- В `index.html` обновлён query-параметр CSS для сброса кэша:
  - `./css/main.css?v=20260228-premium-fonts-1`.

Проверка:
- `rg -n "@font-face|galderglynn-titling\\.thin|galderglynn-titling\\.light|hero__title|section__title|hero__kicker|hero__facts-kicker" css/main.css`
- `rg -n "css/main.css\\?v=20260228-premium-fonts-1" index.html`
- Ручная проверка diff по блокам typography.

Риски/заметки:
- Новые `otf` подключены для основного сайта из корневой папки `fonts`; в `primkom-rf` эти веса пока не применялись.

### 2026-02-27

Задача: Убрать маркеры-точки в блоке «Примком в цифрах» и добавить мягкую волну перелива текста слева направо по колонкам.

Зачем: По задаче нужно отказаться от круглых маркеров над цифрами и сделать спокойный последовательный световой акцент от первой колонки к последней.

Изменённые файлы:
- `css/main.css`
- `index.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `css/main.css` для desktop отключены верхние маркеры в карточках фактов:
  - `.hero__facts-item::before { content: none; }`.
- Добавлена последовательная волна по тексту колонок:
  - у `.hero__facts-item` введён `--facts-wave-delay`;
  - задержка по колонкам через `:nth-child(2..4)`, чтобы эффект шёл слева направо;
  - для `.hero__facts-value` и `.hero__facts-text` добавлена анимация `heroFactsSoftWave` с мягким усилением цвета/свечения без резкой яркости.
- Добавлен fallback для accessibility:
  - при `prefers-reduced-motion: reduce` анимация отключается.
- На главной в `index.html` обновлена ссылка на стили:
  - `./css/main.css?v=20260228-hero-facts-wave` для сброса кэша браузера.

Проверка:
- `rg -n "hero__facts-item::before|heroFactsSoftWave|facts-wave-delay|prefers-reduced-motion" css/main.css`
- `rg -n "css/main.css\\?v=20260228-hero-facts-wave" index.html`
- Ручная проверка диффа по блоку `.hero__facts*`.

Риски/заметки:
- Если сервер отдает старый `index.html` или CDN кэширует HTML, ссылка с новым query-параметром может примениться с задержкой до обновления HTML-кэша.

### 2026-02-27

Задача: Скорректировать типографику блока «Примком в цифрах» на первом экране.

Зачем: Верхние значения выглядели слишком крупно и визуально перетягивали внимание; подписи второй строки читались слишком мелко.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `.hero__facts-item` включено центрирование контента:
  - добавлены `display: flex`, `flex-direction: column`, `align-items: center`, `text-align: center`.
- Маркер таймлайна в `.hero__facts-item::before` перемещён в центр колонки (`left: 50%` + `transform`).
- Верхняя строка (`.hero__facts-value`) уменьшена:
  - desktop: `clamp(24px, 2.5vw, 34px)` -> `clamp(20px, 2.1vw, 28px)`;
  - mobile: `clamp(20px, 6vw, 30px)` -> `clamp(18px, 5vw, 24px)`.
- Нижняя строка (`.hero__facts-text`) увеличена:
  - desktop: `13px` -> `14px`;
  - mobile: `12px` -> `13px`.

Проверка:
- Ручная проверка diff в `css/main.css`.
- Поиск измененных селекторов: `rg -n "hero__facts-item|hero__facts-value|hero__facts-text" css/main.css`.

Риски/заметки:
- При последующих правках блока важно сохранять баланс между высотой hero и размерами текста, особенно на ноутбуках с высотой viewport ~800px.

### 2026-02-27

Задача: Закрыть критичные технические SEO-замечания по основному сайту после аудита.

Зачем: На главной был невалидный JSON-LD, в `robots.txt` блокировались общие HTML-компоненты, на страницах Японии/Кореи отсутствовала часть social metadata.

Изменённые файлы:
- `index.html`
- `robots.txt`
- `pages/auto-iz-yaponii.html`
- `pages/auto-iz-korei.html`
- `SEO_GUIDE.md`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `index.html` исправлен синтаксис JSON-LD в блоке `AutoDealer/LocalBusiness`:
  - массив `sameAs` корректно закрывается `]`, из-за чего structured data снова валидна.
- В `robots.txt` удалён `Disallow: /components/`:
  - поисковые роботы теперь могут загружать `components/header.html` и `components/footer.html`, которые критичны для полной перелинковки при JS-рендеринге.
- В `pages/auto-iz-yaponii.html` и `pages/auto-iz-korei.html` добавлены недостающие social-теги:
  - `og:image:alt`, `og:image:width`, `og:image:height`;
  - `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`, `twitter:image:alt`.
- Обновлён `SEO_GUIDE.md`:
  - дата актуализации и отдельная фиксация внесённых технических SEO-исправлений.

Проверка:
- `python3`-проверка валидности всех JSON-LD блоков (`ALL_JSONLD_VALID`).
- `python3`-проверка обязательных `og/twitter` мета-тегов для страниц Японии/Кореи (`OK`).
- `rg -n '^Disallow: /components/' robots.txt` (подтверждено отсутствие блокировки).

Риски/заметки:
- В рабочем дереве есть несвязанные изменения в ряде файлов; в этой задаче затронуты только перечисленные выше SEO-файлы и документация.

### 2026-02-27

Задача: Добавить на главный экран визуальный блок с ключевыми фактами компании и упростить подпись цены в модалке Японии.

Зачем: На первом экране не хватало отдельного акцентного блока с доверием/цифрами, а длинная подпись цены в модалке выглядела перегруженно.

Изменённые файлы:
- `index.html`
- `css/main.css`
- `js/modules/animations.js`
- `js/modules/auto-manual-market.js`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`
- `CLIENT_OVERVIEW.md`

Что сделано:
- На главной (`index.html`) добавлен новый блок `.hero__facts` в нижней части hero:
  - 4 факта: `5 лет`, `400+`, `Все виды`, `3 страны`;
  - блок расположен между hero-контентом и следующей секцией.
- В `css/main.css` добавлены стили блока:
  - glass-панель, таймлайн-линия и маркеры на desktop;
  - адаптивная версия 2x2 на mobile без горизонтального сдвига.
- В `js/modules/animations.js` добавлена плавная анимация появления панели фактов и отдельных пунктов.
- В `js/modules/auto-manual-market.js` подпись строки цены в detail-модалке изменена на `Цена`.

Проверка:
- `node --check js/modules/auto-manual-market.js`
- `node --check js/modules/animations.js`
- `rg -n "hero__facts|Примком в цифрах|market === \"japan\" \\? \"Цена\"|Цена во Владивостоке под ключ" index.html css/main.css js/modules/auto-manual-market.js js/modules/animations.js`
- Ручная проверка diff по зонам hero и modal specs.

Риски/заметки:
- Новый факт-блок влияет на высоту первого экрана; при следующих правках hero важно проверять отступы на viewport ~800-950px.
- Подпись `Цена` применена только для рынка Японии (`data-market="japan"`); для Кореи оставлена прежняя формулировка.

### 2026-02-24

Задача: Усилить техническое SEO сайта и подготовить практическую инструкцию по продвижению в Google и Яндексе.

Зачем: Сайт слабо находится по брендовому запросу; нужна системная работа по индексации и продвижению, плюс понятный рабочий регламент.

Изменённые файлы:
- `index.html`
- `pages/kontakty.html`
- `pages/privacy.html`
- `pages/consent.html`
- `robots.txt`
- `sitemap.xml`
- `SEO_GUIDE.md`
- `CLIENT_OVERVIEW.md`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Усилены structured data на главной:
  - добавлены `Organization`, `WebSite`, `AutoDealer/LocalBusiness` с `@id`-связями.
- Усилен structured data на странице контактов:
  - `AutoDealer/LocalBusiness`, `hasMap`, `areaServed`, `sameAs`.
- Юридические страницы (`privacy`, `consent`) переведены в `noindex,follow`.
- Из `sitemap.xml` удалены `privacy/consent`, добавлены `lastmod` по индексируемым URL.
- В `robots.txt` добавлен `Host: primcom.ru` (для Яндекс-сценариев).
- Создан `SEO_GUIDE.md` с пошаговым планом:
  - индексация (Search Console / Яндекс Вебмастер),
  - чек-листы,
  - KPI,
  - план продвижения на 1-2 месяца.
- `CLIENT_OVERVIEW.md` дополнен фронтовой SEO-частью в формате для заказчика.

Проверка:
- Проверка валидности `sitemap.xml`.
- Проверка наличия новых meta robots и structured data в измененных страницах.
- Ручная проверка структуры `SEO_GUIDE.md`.

Риски/заметки:
- Брендовая выдача не появляется мгновенно даже после технических правок; обычно нужен цикл переобхода + внешние бренд-сигналы (карты/справочники/упоминания).

### 2026-02-24

Задача: Скорректировать клиентский файл под фронт-рамки: убрать backend-составляющую и вести его только по фронту.

Зачем: Заказчику нужен отдельный понятный документ именно про сайт и его интерфейсные улучшения, без технических деталей backend/парсера/ботов.

Изменённые файлы:
- `CLIENT_OVERVIEW.md`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- `CLIENT_OVERVIEW.md` переработан в чисто фронтовой формат:
  - удалены backend/API/парсер/бот-блоки;
  - оставлены только описание сайта, UX, карточек и бизнес-эффект фронтовых улучшений.
- Изменено правило ведения файла:
  - пополняется только по ключевым фронтовым изменениям.
- В `FRONTEND_DOCS.md` обновлена формулировка назначения `CLIENT_OVERVIEW.md`:
  - теперь это клиентское описание фронта.

Проверка:
- Ручная проверка содержимого `CLIENT_OVERVIEW.md` на отсутствие backend-секций.
- Проверка согласованности правил в `FRONTEND_DOCS.md`.

Риски/заметки:
- При будущих правках важно не смешивать в `CLIENT_OVERVIEW.md` frontend и backend изменения; backend остается в своих документах.

### 2026-02-24

Задача: Подготовить единое описание проекта для заказчика (frontend + API + парсер + боты) в лаконичном деловом формате.

Зачем: Нужен понятный файл, который можно быстро показать заказчику без технической перегрузки и использовать как живой документ по ключевым улучшениям.

Изменённые файлы:
- `CLIENT_OVERVIEW.md`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Создан новый файл `CLIENT_OVERVIEW.md` в корне проекта.
- В файле описаны:
  - текущие возможности сайта;
  - backend API;
  - парсер и обновление каталога;
  - менеджер-бот и контур заявок;
  - последние ключевые улучшения и их бизнес-эффект.
- Добавлено правило: после ключевых изменений дополнять этот файл в том же стиле.
- В `FRONTEND_DOCS.md` добавлена ссылка на `CLIENT_OVERVIEW.md` как связанный документ.

Проверка:
- Ручная проверка структуры и читаемости текста.
- Проверка наличия файла и ссылки на него в `FRONTEND_DOCS.md`.

Риски/заметки:
- Файл может устаревать при активных изменениях; актуальность поддерживается через обязательное пополнение после каждого ключевого релиза/правки.

### 2026-02-23

Задача: Добавить persistent-кэш карточек главной, чтобы повторно не ждать загрузку фото-карусели.

Зачем: После переходов между страницами сайта и возврата на главную галереи карточек заново догружались; нужен быстрый повторный доступ к уже просмотренным карточкам.

Изменённые файлы:
- `js/modules/latest-cars-home.js`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Для detail-данных карточек latest-home добавлен 2-уровневый кэш:
  - runtime `Map` (в пределах открытой страницы);
  - persistent `localStorage` (`latest-home-detail-cache:v1`) для повторных заходов.
- Добавлен TTL для persistent-кэша (~12 часов) и лимит записей (LRU-подобная очистка по времени).
- При наличии валидной записи detail-данные и фото-карусель берутся из localStorage без повторного ожидания API.

Проверка:
- `node --check js/modules/latest-cars-home.js`
- Ручная проверка diff.

Риски/заметки:
- Кэш на клиенте может кратковременно показывать чуть устаревшие detail-данные в пределах TTL; срок ограничен 12 часами для баланса скорости и актуальности.

### 2026-02-23

Задача: Показать в карточках главной статус загрузки фото до готовности hover-карусели.

Зачем: При первом открытии страницы дополнительные фото в карточках не всегда доступны сразу; нужен явный визуальный статус, что галерея еще загружается.

Изменённые файлы:
- `js/modules/latest-cars-home.js`
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В карточку latest-home добавлен overlay-статус `Фото загружаются`.
- Статус показывается только для desktop/fine pointer карточек, где ожидается больше одного фото.
- Добавлен фоновый preload галереи после рендера карточки (краткая задержка), чтобы быстрее открыть hover-прокрутку.
- Статус автоматически скрывается, когда в карточке доступны дополнительные фото для прокрутки.
- Добавлены стили overlay и легкая pulse-анимация.

Проверка:
- `node --check js/modules/latest-cars-home.js`
- Ручная проверка diff.

Риски/заметки:
- Добавлен дополнительный preload detail-запросов на главной для карточек с несколькими фото (компромисс между скоростью UX и сетевой нагрузкой).

### 2026-02-23

Задача: Обновить карточки на главной (Япония/Китай/Корея): интерактив фото, модалка по `Подробнее`, убрать `Источник`.

Зачем: На главной нужен быстрый просмотр карточки без перехода на отдельную страницу и более понятная работа с фотографиями.

Изменённые файлы:
- `js/modules/latest-cars-home.js`
- `index.html`
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Карточки главной:
  - добавлена hover-навигация по фото влево/вправо (desktop/fine pointer);
  - добавлены индикаторы количества фото и текущей позиции;
  - удалена кнопка `Источник`.
- Кнопка `Подробнее` и клик по фото теперь открывают модалку карточки на главной:
  - показываются описание, характеристики, дата обновления, доп. фото;
  - добавлена кнопка `Перейти в раздел` как единственный переход на страницу рынка из карточки.
- В `index.html` добавлена модалка latest-card с `data-*` селекторами для JS.
- В `css/main.css` добавлены стили индикаторов фото и элементов модалки latest-card.

Проверка:
- `node --check js/modules/latest-cars-home.js`
- `rg -n "Источник|srcLink" js/modules/latest-cars-home.js`
- `rg -n "data-latest-card-" index.html`

Риски/заметки:
- Детальная карточка для главной использует detail endpoint по ID; при временной недоступности API модалка открывается с базовыми данными карточки и сообщением об ошибке загрузки доп. данных.

### 2026-02-23

Задача: Показать в карточках Японии оценку аукционного листа, которую теперь сохраняет менеджер-бот.

Зачем: Для японского рынка это ключевой параметр при выборе авто; он должен быть виден в модалке карточки.

Изменённые файлы:
- `js/modules/auto-manual-market.js`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `renderSpecRows` добавлена строка спецификации:
  - `Оценка аукциона` <- `item.auction_grade`.
- Строка показывается только при наличии значения (существующая логика пропуска пустых полей сохранена).
- Документация обновлена: зафиксировано, что модуль Японии/Кореи читает `auction_grade`.

Проверка:
- `node --check js/modules/auto-manual-market.js`
- Ручная проверка diff.

Риски/заметки:
- Если backend не передает `auction_grade`, строка не отрисуется (ожидаемое поведение).

### 2026-02-22

Задача: Добавить плавную анимацию перехода шапки между статичным состоянием и состоянием при прокрутке.

Зачем: Переход `static <-> is-detached` выглядел слишком резким.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Для `.site-header__inner` добавлен `transition` на ключевые свойства перехода:
  - `inline-size`, `padding`, `border-color`, `border-radius`, `background-color`, `backdrop-filter`, `box-shadow`.
- Для `.brand__logo` добавлен `transition` по `inline-size`.
- JS-логика скролла не менялась; анимация полностью CSS.

Проверка:
- Ручная проверка diff.
- Логическая проверка: изменения ограничены header-стилями, без правок модулей JS.

Риски/заметки:
- На очень слабых устройствах анимация blur может быть тяжелее; при необходимости уменьшается длительность/набор анимируемых свойств.

### 2026-02-22

Задача: Сделать подложку шапки при прокрутке менее прозрачной.

Зачем: В состоянии `is-detached` логотип и элементы шапки недостаточно отделялись от фона контента.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В `is-detached` изменен фон панели шапки:
  - `.site-header.is-detached .site-header__inner`
  - `background: var(--glass-bg)` -> `background: rgba(9, 18, 46, 0.74)`
- Геометрия, скролл-логика и анимации шапки не менялись.

Проверка:
- Ручная проверка diff.
- Логическая проверка области действия: изменение только в селекторе `is-detached`.

Риски/заметки:
- Если подложка покажется слишком плотной на отдельных дисплеях, корректируется только alpha у этого `rgba`.

### 2026-02-22

Задача: Добавить тени на текст hero-баннера для повышения читаемости.

Зачем: На светлых участках фонового баннера буквы заголовка и описания местами терялись.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Добавлены многослойные `text-shadow` для:
  - `.hero__kicker`
  - `.hero__title`
  - `.hero__lead`
- Тени сделаны в темной холодной гамме, чтобы подчеркнуть контраст без утяжеления блока.

Проверка:
- Ручная проверка diff.
- Логическая проверка: изменения затрагивают только визуал текста hero, без влияния на скролл/сетки/адаптив.

Риски/заметки:
- На отдельных мониторах с очень высокой контрастностью тени могут казаться чуть плотными; при необходимости корректируется только alpha в `text-shadow`.

### 2026-02-22

Задача: Добавить полупрозрачную подложку под статичную шапку в границах высоты header, не трогая скролл-состояние.

Зачем: Логотип и пункты меню на баннере местами сливались с фоном; нужна более читаемая шапка в начальном состоянии.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Добавлен псевдо-элемент подложки у шапки:
  - `.site-header::before` с фоном `rgba(9, 18, 46, 0.66)`, `backdrop-filter: blur(10px) saturate(135%)`, и нижней границей `1px`.
- Подложка включена только для статичного состояния:
  - `.site-header:not(.is-detached)::before { opacity: 1; }`
- Для корректного слоя контента шапки добавлено:
  - `.site-header > * { position: relative; z-index: 1; }`
- Стиль `is-detached` не изменялся.

Проверка:
- Ручная проверка diff.
- Логическая проверка селекторов: подложка завязана на `:not(.is-detached)`, поэтому скролл-состояние не затронуто.

Риски/заметки:
- На слабых мобильных устройствах `backdrop-filter` может быть тяжелее, но подложка ограничена областью шапки и не должна заметно ухудшить производительность.

### 2026-02-22

Задача: Добавить override размера логотипа для шапки в состоянии скролла (`is-detached`).

Зачем: Изменение размера логотипа в статичной шапке автоматически применялось и при скролле, нужно было разнести значения.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Базовый размер логотипа оставлен для mobile/tablet:
  - `.brand__logo { inline-size: 70px; }`
- Для desktop оставлен увеличенный static размер логотипа:
  - `.brand__logo { inline-size: 100px; }`
- Добавлен отдельный override для detached-состояния:
  - `.site-header.is-detached .brand__logo { inline-size: 82px; }`
- JS-логика скролла не менялась; управление полностью через CSS.

Проверка:
- Ручная проверка diff.
- Логическая проверка приоритетов CSS в desktop media query.

Риски/заметки:
- Любые будущие правки `.brand__logo` нужно сверять сразу с `.site-header.is-detached .brand__logo`, чтобы не терять раздельное поведение.

### 2026-02-22

Задача: Дополнительно увеличить логотип в шапке в статичной desktop-версии без изменения поведения на скролле.

Зачем: Требовалось сделать логотип заметнее в обычном состоянии шапки на десктопе.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- В desktop media query (`@media (min-width: 861px)`) увеличен размер логотипа:
  - `.brand__logo`: `82px` -> `90px`.
- Логика состояния `is-detached` не изменялась, размер логотипа при скролле остается тем же.

Проверка:
- Ручная проверка diff.
- Логическая проверка области действия: изменение ограничено desktop media query.

Риски/заметки:
- При дальнейших изменениях шапки проверять баланс между размером логотипа и доступным местом для навигации на ширине ~900-1100px.

### 2026-02-22

Задача: Увеличить логотип в шапке только на desktop и убрать горизонтальный сдвиг страницы на мобильных.

Зачем: На desktop логотип выглядел слишком маленьким; на мобильных при вертикальном свайпе страница "уезжала" влево/вправо, что ухудшало UX.

Изменённые файлы:
- `css/main.css`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Увеличен логотип шапки только для desktop (`@media (min-width: 861px)`):
  - `.brand__logo` увеличен до `82px`.
- Размер логотипа при скролле не изменяется (поведение `is-detached` по логотипу не трогалось).
- Добавлен root overflow guard от горизонтального скролла:
  - `html { overflow-x: hidden; }`
  - через `@supports (overflow: clip)` включено `overflow-x: clip` для `html, body`.

Проверка:
- Ручная проверка diff.
- Логическая проверка, что изменение размера логотипа ограничено desktop media query.
- Логическая проверка, что mobile/tablet размеры логотипа и скролл-хедер по размеру логотипа не изменены.

Риски/заметки:
- Если на странице есть намеренные горизонтальные элементы, root-ограничение не должно их ломать, но требует визуальной проверки на iOS Safari.
- Для шапки сохраняется правило: любые дополнительные изменения проверять на desktop и mobile отдельно.

### 2026-02-22

Задача: Разобраться, почему в мобильной версии карточки Китая могли попадать в блок Японии, и защитить фронт от смешивания рынков.

Зачем: На мобильных устройствах пользователь увидел несоответствие карточек разделу. Требуется жёсткая защита от таких состояний.

Изменённые файлы:
- `js/modules/latest-cars-home.js`
- `index.html`
- `FRONTEND_DOCS.md`
- `FRONTEND_CHANGELOG.md`

Что сделано:
- Выполнена проверка связки `index.html` + `latest-cars-home.js` + API.
- Выявлена уязвимость: при отсутствующих `data-*` атрибутах секции модуль использовал silent fallback на `/api/auto-iz-kitaya`, что могло приводить к "китайским" карточкам в чужой секции.
- В `latest-cars-home.js` добавлены:
  - presets по `id` секций (`latest-japan-home`, `latest-china-home`, `latest-korea-home`);
  - отказ от silent fallback на Китай при пустом `data-api-path` (с явным статусом ошибки);
  - фильтрация карточек по `item.source` через `data-expected-source` для изоляции рынков.
- В `index.html` для всех трех секций главной добавлены явные `data-source` и `data-expected-source`.
- Документация обновлена: мобильная проверка секций с карточками сделана обязательной.

Проверка:
- Логическая проверка и чтение diff.
- Синтаксическая проверка: `node --check js/modules/latest-cars-home.js`.
- Проверка прод-данных в мобильном headless viewport (Playwright): API Японии/Китая/Кореи отдают разные наборы карточек; секции в DOM разделены корректно.

Риски/заметки:
- Если backend вернет карточки с некорректным `item.source`, такие карточки будут отфильтрованы и секция покажет статус "Нет подходящих объявлений...".
- Мобильная проверка главной и market-страниц теперь обязательна для каждой правки, связанной с карточками и секциями.

### 2026-02-22

Задача: Создана базовая frontend-документация.

Зачем: Нужна единая точка входа по архитектуре фронта перед быстрыми правками.

Изменённые файлы:
- `FRONTEND_DOCS.md`

Что сделано:
- Описана структура фронтенда (страницы, компоненты, CSS, JS-модули).
- Зафиксированы связи `data-*` атрибутов и модулей.
- Добавлены правила безопасных правок и обязательный процесс актуализации документации.

Проверка:
- Ручная проверка содержимого файла.

Риски/заметки:
- При любой правке шапки проверять связку: `components/header.html`, `css/main.css`, `js/modules/header.js`.

### 2026-02-22

Задача: Ретроспективно зафиксированы изменения по шапке/логотипу на главной.

Зачем: В течение сессии было много итераций; важно сохранить контекст "что пробовали и зачем".

Изменённые файлы:
- `css/main.css`
- `index.html`

Что сделано:
- Проводились итерации по поведению логотипа и шапки:
  - увеличение/уменьшение логотипа;
  - добавление/скрытие подложки;
  - поведение в статике и при скролле;
  - попытка вынести логотип отдельным слоем в статике;
  - коррекция сетки шапки после смещений.

Проверка:
- Визуальная проверка по скриншотам и ручная проверка CSS-правил.

Риски/заметки:
- Шапка чувствительна к изменениям потока/grid при `position: fixed` у логотипа.
- Любые изменения логотипа могут сдвигать навигацию и блок действий.

### 2026-02-22

Задача: Создан frontend-журнал изменений и включён в обязательный процесс.

Зачем: Нужен отдельный лог всех фронтенд-правок с причинами и эффектом.

Изменённые файлы:
- `FRONTEND_CHANGELOG.md`
- `FRONTEND_DOCS.md`

Что сделано:
- Создан этот файл.
- В `FRONTEND_DOCS.md` добавлены требования читать и обновлять оба документа.

Проверка:
- Ручная проверка структуры и содержимого.

Риски/заметки:
- Если после правки нет записи в этом файле, процесс считается нарушенным.
