// Вставляет облако тегов «Полезно знать» в статичные страницы (главная и pages/*.html).
// Данные — seo/tag-cloud.json, раздел "pages" с ключами-URL. Блок стоит между метками
// SEO_TAGS перед </main>, FAQPage — между метками SEO_TAGS_SCHEMA в <head>; на странице,
// где FAQPage уже есть (faq.html), вопросы добавляются в неё с @id "#seo-tag-N".
//
//   node scripts/build-tag-clouds.mjs          — обновить страницы
//   node scripts/build-tag-clouds.mjs --check  — только проверить, что страницы актуальны
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderTagCloud, faqEntities } from "./seo-tag-cloud.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHECK = process.argv.includes("--check");
const data = JSON.parse(await fs.readFile(path.join(ROOT, "seo/tag-cloud.json"), "utf8"));

const BLOCK = /\n[ \t]*<!-- SEO_TAGS:START -->[\s\S]*?<!-- SEO_TAGS:END -->/;
const SCHEMA = /\n?\s*<!-- SEO_TAGS_SCHEMA:START -->[\s\S]*?<!-- SEO_TAGS_SCHEMA:END -->/;
const LD = /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g;

function withFaq(html, tags) {
  const entities = faqEntities(tags).map((q, i) => ({"@id": `#seo-tag-${i + 1}`, ...q}));
  let merged = false;
  html = html.replace(LD, (whole, json) => {
    let doc;
    try { doc = JSON.parse(json); } catch { return whole; }
    const nodes = Array.isArray(doc) ? doc : doc["@graph"] || [doc];
    const faq = nodes.find((n) => n["@type"] === "FAQPage");
    if (!faq) return whole;
    faq.mainEntity = [...(faq.mainEntity || []).filter((q) => !String(q["@id"] || "").startsWith("#seo-tag-")), ...entities];
    merged = true;
    return `<script type="application/ld+json">\n${JSON.stringify(doc, null, 2)}\n  </script>`;
  });
  if (merged) return html;
  const script = `\n  <!-- SEO_TAGS_SCHEMA:START -->\n  <script type="application/ld+json">${JSON.stringify({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqEntities(tags)})}</script>\n  <!-- SEO_TAGS_SCHEMA:END -->`;
  return html.replace(/\n?<\/head>/, `${script}\n</head>`);
}

const stale = [];
for (const [url, tags] of Object.entries(data.pages || {})) {
  if (url !== "/" && !url.startsWith("/pages/")) continue; // остальные страницы строит генератор каталога
  const file = path.join(ROOT, url === "/" ? "index.html" : url.slice(1));
  const before = await fs.readFile(file, "utf8");
  let html = before.replace(BLOCK, "").replace(SCHEMA, "");
  const block = `<!-- SEO_TAGS:START -->\n    <section class="section section--seo-tags" aria-label="Полезно знать">\n      <div class="container">${renderTagCloud(tags, {id: "seo-tags"})}</div>\n    </section>\n    <!-- SEO_TAGS:END -->`;
  html = html.replace(/\n([ \t]*)<\/main>/, (m, indent) => `\n    ${block}\n${indent}</main>`);
  html = withFaq(html, tags);
  if (html === before) continue;
  if (CHECK) stale.push(url);
  else { await fs.writeFile(file, html); console.log(`updated ${path.relative(ROOT, file)} (${tags.length} tags)`); }
}
if (CHECK && stale.length) { console.error(`Облако тегов устарело: ${stale.join(", ")}. Запустите node scripts/build-tag-clouds.mjs`); process.exit(1); }
if (CHECK) console.log("Tag clouds up to date.");
