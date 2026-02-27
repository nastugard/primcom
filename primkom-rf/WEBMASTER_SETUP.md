# WEBMASTER SETUP: примком.рф

Дата обновления: 2026-02-27.

## Свойство

- Основное для кабинетов: `https://xn--h1aefbjch.xn--p1ai/` (punycode)

## 1) Яндекс Вебмастер

1. Добавить сайт `https://xn--h1aefbjch.xn--p1ai/`.
2. Пройти верификацию (meta-тег или HTML-файл).
3. Отправить sitemap:
   - `https://xn--h1aefbjch.xn--p1ai/sitemap.xml`
4. Проверить индекс:
   - `https://xn--h1aefbjch.xn--p1ai/`
   - `https://xn--h1aefbjch.xn--p1ai/pages/kontakty.html`

## 2) Google Search Console

1. Добавить URL-prefix property `https://xn--h1aefbjch.xn--p1ai/`.
2. Пройти верификацию.
3. Отправить sitemap:
   - `https://xn--h1aefbjch.xn--p1ai/sitemap.xml`
4. Запросить индексацию двух страниц через URL Inspection.

## 3) Контроль после релиза

- Проверять, что индексируются только 2 страницы.
- Проверять, что удаленные legacy URL не остаются в индексе (после 301).
- Мониторить переходы на `https://primcom.ru/`.

## 4) Технический чек перед отправкой sitemap

- Доступен `robots.txt`: `https://xn--h1aefbjch.xn--p1ai/robots.txt`
- Доступен `sitemap.xml`: `https://xn--h1aefbjch.xn--p1ai/sitemap.xml`
- Работают 301-редиректы со старых `/pages/*.html` на `/`

