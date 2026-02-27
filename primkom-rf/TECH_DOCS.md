# TECH DOCS: primkom-rf

## Назначение

`primkom-rf` — отдельная фронтовая сборка для домена `примком.рф` (`xn--h1aefbjch.xn--p1ai`) в формате контентного спутника бренда.

## SEO-модель

- Основной домен: `https://primcom.ru/`.
- Копии страниц в `primkom-rf`:
  - `meta robots="noindex,follow"`
  - canonical на соответствующий URL `primcom.ru`.
- Уникальные страницы спутника:
  - `meta robots="index,follow"`
  - self-canonical на `xn--h1aefbjch.xn--p1ai`.
- В `sitemap.xml` публикуются только уникальные индексируемые страницы спутника.

## Публикация

- На домен `примком.рф` деплоится только содержимое папки `primkom-rf/`.
- Перед релизом проверять:
  - валидность canonical и robots;
  - ссылки на `primcom.ru`;
  - соответствие `sitemap.xml` фактическим index-страницам.

## Журнал обновлений

### 2026-02-27 — Этап A

- Создана отдельная папка `primkom-rf` с фронтовой копией.
- Для дублируемых страниц выставлены `noindex,follow` + canonical на `primcom.ru`.
- Добавлена уникальная страница `pages/o-kompanii-primkom.html` (indexable, self-canonical).
- Добавлены сквозные ссылки на `primcom.ru` в `header`, `footer`, главной.
- Настроены `robots.txt` и `sitemap.xml` для `xn--h1aefbjch.xn--p1ai`.

