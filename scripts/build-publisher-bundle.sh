#!/usr/bin/env bash
# Собирает папку для сервера, где будет работать автопубликация SEO-страниц.
#
#   bash scripts/build-publisher-bundle.sh [папка]
#
# Внутри: скрипты публикатора, реестр, пример настроек и site-staging — полная копия сайта.
# Копия нужна проверке качества: она убеждается, что каждая ссылка и каждый файл
# (CSS, шрифты, баннер, страницы, которые ведут друг на друга) на месте. Поэтому в неё
# входят и cars/, guides/, sitemap.xml — главная ссылается на них, и без них самая первая
# сборка отклонила бы сама себя.
#
# Каждый релиз фронтенда (CSS, JS, страницы) — обновить site-staging. Это правило одно:
# версия ресурсов в собираемых страницах берётся из site-staging/index.html.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/deploy/seo-publisher-$(date +%Y%m%d)}"

rm -rf "$OUT"
mkdir -p "$OUT/scripts" "$OUT/seo" "$OUT/site-staging"

for name in generate-seo-pages check-seo-pages sync-seo-catalog publish-seo-catalog sync-to-host publish-and-sync; do
  cp "$ROOT/scripts/$name.mjs" "$OUT/scripts/"
done
cp "$ROOT/seo/content-registry.json" "$OUT/seo/"
[ -f "$ROOT/seo/lastmod-state.json" ] && cp "$ROOT/seo/lastmod-state.json" "$OUT/seo/"
cp "$ROOT/sync.env.example" "$OUT/"

cd "$ROOT"
for f in index.html 404.html robots.txt sitemap.xml site.webmanifest; do cp "$f" "$OUT/site-staging/"; done
for d in assets banner components css fonts js pages cars guides; do
  rsync -a --exclude='.DS_Store' --exclude='.keep' "$d" "$OUT/site-staging/"
done
mkdir -p "$OUT/site-staging/logo"
cp "logo/logo 3 dark.png" "$OUT/site-staging/logo/"

find "$OUT" -name '.DS_Store' -delete
echo "Готово: $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') файлов, $(du -sh "$OUT" | cut -f1))"
