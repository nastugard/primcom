import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT_ROOT = path.resolve(process.env.SEO_OUTPUT_ROOT || ROOT);
const SITE_ROOT = path.resolve(process.env.SEO_SITE_ROOT || OUTPUT_ROOT);
const REGISTRY_PATH = path.resolve(process.env.SEO_REGISTRY_PATH || path.join(ROOT, "seo/content-registry.json"));
const registry = JSON.parse(await fs.readFile(REGISTRY_PATH, "utf8"));
const errors = [];
const seenTitles = new Map();
const seenDescriptions = new Map();
const generatedFiles = [];

async function walk(dir) {
  for (const entry of await fs.readdir(dir, {withFileTypes:true})) {
    const target = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(target);
    else if (entry.name === "index.html") generatedFiles.push(target);
  }
}
for (const dir of ["cars", "guides", "cases"]) {
  try { await walk(path.join(OUTPUT_ROOT, dir)); } catch {}
}

function one(html, regex) { return html.match(regex)?.[1]?.trim() || ""; }
function duplicate(map, value, file, label) {
  if (!value) return;
  if (map.has(value)) errors.push(`${label} duplicate: ${file} and ${map.get(value)}`);
  else map.set(value, file);
}

for (const file of generatedFiles) {
  const html = await fs.readFile(file, "utf8");
  const rel = path.relative(OUTPUT_ROOT, file);
  const title = one(html, /<title>([\s\S]*?)<\/title>/i);
  const description = one(html, /<meta name="description" content="([^"]*)"/i);
  const robots = one(html, /<meta name="robots" content="([^"]*)"/i);
  const canonical = one(html, /<link rel="canonical" href="([^"]*)"/i);
  const h1Count = (html.match(/<h1\b/gi) || []).length;
  if (!title || !description || !canonical || !robots) errors.push(`${rel}: missing required SEO metadata`);
  if (h1Count !== 1) errors.push(`${rel}: expected one H1, found ${h1Count}`);
  if (!canonical.startsWith("https://primcom.ru/")) errors.push(`${rel}: invalid canonical ${canonical}`);
  for (const match of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/gi)) {
    try { JSON.parse(match[1]); } catch (error) { errors.push(`${rel}: invalid JSON-LD (${error.message})`); }
  }
  if (robots === "index,follow") {
    duplicate(seenTitles, title, rel, "title");
    duplicate(seenDescriptions, description, rel, "description");
    const forbiddenPublicPhrases = ["снимок каталога", "предложений в снимке", "модели пилота", "черновик", "ожидает проверки", "production"];
    for (const phrase of forbiddenPublicPhrases) {
      if (html.toLowerCase().includes(phrase)) errors.push(`${rel}: internal wording leaked into public page: ${phrase}`);
    }
  }
}

const sitemap = await fs.readFile(path.join(OUTPUT_ROOT, "sitemap.xml"), "utf8");
const sitemapUrls = new Set([...sitemap.matchAll(/<loc>https:\/\/primcom\.ru([^<]*)<\/loc>/g)].map((m) => m[1]));
for (const file of generatedFiles) {
  const html = await fs.readFile(file, "utf8");
  const url = one(html, /<link rel="canonical" href="https:\/\/primcom\.ru([^"]*)"/i);
  const robots = one(html, /<meta name="robots" content="([^"]*)"/i);
  if (robots === "index,follow" && !sitemapUrls.has(url)) errors.push(`${url}: indexable but absent from sitemap`);
  if (robots.startsWith("noindex") && sitemapUrls.has(url)) errors.push(`${url}: noindex URL is present in sitemap`);
}

if (generatedFiles.length < 20) errors.push(`expected at least 20 generated URLs, found ${generatedFiles.length}`);

const htmlFiles = [path.join(SITE_ROOT, "index.html"), ...generatedFiles];
for (const name of await fs.readdir(path.join(SITE_ROOT, "pages"))) {
  if (name.endsWith(".html")) htmlFiles.push(path.join(SITE_ROOT, "pages", name));
}
for (const file of htmlFiles) {
  const html = await fs.readFile(file, "utf8");
  for (const block of html.matchAll(/<details class="seo-topics">([\s\S]*?)<\/details>/g)) {
    const links = [...block[1].matchAll(/<a href="([^"]+)">([^<]+)<\/a>/g)];
    if (links.length < 4 || links.length > 12) {
      errors.push(`${path.relative(SITE_ROOT,file)}: SEO topics must contain 4-12 useful links, found ${links.length}`);
    }
    const hrefs = links.map((match) => match[1]);
    const labels = links.map((match) => match[2].replace(/\s+/g, " ").trim().toLowerCase());
    if (new Set(hrefs).size !== hrefs.length) errors.push(`${path.relative(SITE_ROOT,file)}: duplicate href in SEO topics`);
    if (new Set(labels).size !== labels.length) errors.push(`${path.relative(SITE_ROOT,file)}: duplicate label in SEO topics`);
    if (hrefs.some((href) => href.includes("?"))) errors.push(`${path.relative(SITE_ROOT,file)}: filter/query URL in SEO topics`);
  }
  for (const match of html.matchAll(/href="([^"]+)"/g)) {
    const raw = match[1];
    if (/^(?:https?:|mailto:|tel:|#)/.test(raw)) continue;
    const clean = raw.split(/[?#]/)[0];
    if (!clean) continue;
    const generatedTarget = clean.startsWith("/") ? path.join(OUTPUT_ROOT, clean) : path.resolve(path.dirname(file), clean);
    const staticTarget = clean.startsWith("/") ? path.join(SITE_ROOT, clean) : generatedTarget;
    let target = generatedTarget;
    let stat = null;
    try {
      stat = await fs.stat(generatedTarget);
      if (stat.isDirectory()) await fs.access(path.join(generatedTarget, "index.html"));
    } catch {
      target = staticTarget;
      stat = null;
      try {
        stat = await fs.stat(staticTarget);
        if (stat.isDirectory()) await fs.access(path.join(staticTarget, "index.html"));
      } catch { stat = null; }
    }
    if (stat?.isDirectory()) {
      try { await fs.access(path.join(target, "index.html")); } catch { errors.push(`${path.relative(SITE_ROOT,file)}: broken directory link ${raw}`); }
    } else if (!stat?.isFile()) {
      errors.push(`${path.relative(SITE_ROOT,file)}: broken link ${raw}`);
    }
  }
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log(`SEO QA passed: ${generatedFiles.length} generated URLs, ${sitemapUrls.size} total sitemap URLs.`);
