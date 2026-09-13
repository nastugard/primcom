import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const temp = await fs.mkdtemp(path.join(os.tmpdir(), "primcom-seo-test-"));
const registry = path.join(temp, "registry.json");
const fixture = path.join(temp, "fixture.json");
const output = path.join(temp, "site");

function run(script, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(ROOT, "scripts", script)], {
      cwd:ROOT,
      env:{...process.env, ...env},
      stdio:"pipe",
    });
    let stderr = "";
    child.stderr.on("data", (chunk) => { stderr += String(chunk); });
    child.on("error", reject);
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${script}: ${stderr}`)));
  });
}

try {
  await fs.copyFile(path.join(ROOT, "seo", "content-registry.json"), registry);
  const item = {
    id:"fixture-note",
    source:"japan_manual",
    source_listing_id:"mgr-japan-20260814000000-fixture",
    brand:"Nissan",
    model:"Note",
    year:2022,
    price_cny:1250000,
    images_count:3,
    cover_image_url:"/media/japan_manual/fixture/000.webp",
    scraped_at:"2026-08-14T00:00:00Z",
  };
  await fs.writeFile(fixture, JSON.stringify({japan:[item], china:[], korea:[]}));
  await run("sync-seo-catalog.mjs", {SEO_REGISTRY_PATH:registry, SEO_REGISTRY_OUTPUT:registry, SEO_CATALOG_FIXTURE:fixture, SEO_ALLOW_CATALOG_SHRINK:"1"});
  await run("generate-seo-pages.mjs", {SEO_REGISTRY_PATH:registry, SEO_OUTPUT_ROOT:output});
  await run("check-seo-pages.mjs", {SEO_REGISTRY_PATH:registry, SEO_OUTPUT_ROOT:output, SEO_SITE_ROOT:ROOT});

  const activeHtml = await fs.readFile(path.join(output, "cars", "japan", "nissan", "note", "index.html"), "utf8");
  assert.match(activeHtml, /<meta name="robots" content="index,follow"/);
  assert.match(activeHtml, /<details class="seo-topics">/);
  assert.match(activeHtml, /Рассчитать стоимость Nissan Note/);
  const inactiveHtml = await fs.readFile(path.join(output, "cars", "japan", "toyota", "raize", "index.html"), "utf8");
  assert.match(inactiveHtml, /<meta name="robots" content="noindex,follow"/);
  const sitemap = await fs.readFile(path.join(output, "sitemap.xml"), "utf8");
  assert.match(sitemap, /\/cars\/japan\/nissan\/note\//);
  assert.doesNotMatch(sitemap, /\/cars\/japan\/toyota\/raize\//);
  console.log("SEO publisher integration test passed.");
} finally {
  await fs.rm(temp, {recursive:true, force:true});
}
