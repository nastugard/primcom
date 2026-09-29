import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const API_BASE = String(process.env.PRIMCOM_CATALOG_API || "https://api.primcom.ru").replace(/\/+$/, "");
const REGISTRY_PATH = path.resolve(process.env.SEO_REGISTRY_PATH || path.join(ROOT, "seo/content-registry.json"));
const OUTPUT_PATH = path.resolve(process.env.SEO_REGISTRY_OUTPUT || REGISTRY_PATH);
const FIXTURE_PATH = process.env.SEO_CATALOG_FIXTURE ? path.resolve(process.env.SEO_CATALOG_FIXTURE) : "";
const PAGE_SIZE = 100;
const ALLOW_CATALOG_SHRINK = /^(1|true|yes)$/i.test(String(process.env.SEO_ALLOW_CATALOG_SHRINK || ""));
const MIN_ACTIVE_RATIO = (() => {
  const parsed = Number(process.env.SEO_MIN_ACTIVE_RATIO);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1 ? parsed : 0.5;
})();

const countryName = {japan:"Японии", china:"Китая", korea:"Кореи"};
const endpoints = {
  japan:"/api/auto-iz-yaponii",
  china:"/api/auto-iz-kitaya?source=guazi",
  korea:"/api/auto-iz-korei",
};

const transliteration = {
  а:"a",б:"b",в:"v",г:"g",д:"d",е:"e",ё:"e",ж:"zh",з:"z",и:"i",й:"y",к:"k",л:"l",м:"m",
  н:"n",о:"o",п:"p",р:"r",с:"s",т:"t",у:"u",ф:"f",х:"h",ц:"ts",ч:"ch",ш:"sh",щ:"sch",
  ъ:"",ы:"y",ь:"",э:"e",ю:"yu",я:"ya",
};

function slugify(value) {
  const transliterated = [...String(value || "").trim().toLowerCase()]
    .map((char) => transliteration[char] ?? char)
    .join("");
  return transliterated
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function key(country, make, model) {
  return [country, make, model].map((value) => String(value || "").trim().toLocaleLowerCase("ru")).join("::");
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

// Параметры конкретного автомобиля для таблицы на странице модели.
// Берём только то, что реально есть в карточке каталога; пустые поля не выдумываем.
function listingFacts(item) {
  const num = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? undefined : Number(v));
  const txt = (v) => { const t = cleanText(v); return t || undefined; };
  const facts = {
    year:num(item.year),
    trim:txt(item.trim),
    body:txt(item.body_type),
    engineVolumeL:num(item.engine_volume_l),
    powerHp:num(item.power_hp),
    drive:txt(item.drive_type),
    transmission:txt(item.transmission),
    mileageKm:num(item.mileage_km),
    grade:txt(item.auction_grade),
    price:num(item.price_cny) === undefined ? undefined : Math.round(Number(item.price_cny)),
  };
  return Object.fromEntries(Object.entries(facts).filter(([, v]) => v !== undefined));
}

function isEligible(country, item) {
  const expectedPrefix = `mgr-${country}-`;
  return String(item?.source_listing_id || "").startsWith(expectedPrefix)
    && cleanText(item?.brand)
    && cleanText(item?.model)
    && Number.isInteger(Number(item?.year))
    && Number(item?.year) >= 1980
    && Number(item?.price_cny) > 0
    && Number(item?.images_count) > 0
    && cleanText(item?.cover_image_url);
}

async function fetchPage(country, offset) {
  const endpoint = endpoints[country];
  const separator = endpoint.includes("?") ? "&" : "?";
  const url = `${API_BASE}${endpoint}${separator}limit=${PAGE_SIZE}&offset=${offset}`;
  const response = await fetch(url, {headers:{accept:"application/json"}});
  if (!response.ok) throw new Error(`${country}: catalog API returned HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || !Array.isArray(payload.items)) throw new Error(`${country}: invalid catalog payload`);
  return payload;
}

async function fetchCountry(country) {
  if (FIXTURE_PATH) {
    const fixture = JSON.parse(await fs.readFile(FIXTURE_PATH, "utf8"));
    return (Array.isArray(fixture[country]) ? fixture[country] : []).filter((item) => isEligible(country, item));
  }
  const items = [];
  let offset = 0;
  while (true) {
    const payload = await fetchPage(country, offset);
    items.push(...payload.items);
    offset += payload.items.length;
    if (!payload.items.length || offset >= Number(payload.total || 0)) break;
  }
  return items.filter((item) => isEligible(country, item));
}

function uniqueSlug(base, used, fallback) {
  const safeBase = base || fallback;
  let candidate = safeBase;
  let suffix = 2;
  while (used.has(candidate)) candidate = `${safeBase}-${suffix++}`;
  used.add(candidate);
  return candidate;
}

const previous = JSON.parse(await fs.readFile(REGISTRY_PATH, "utf8"));
const previousByKey = new Map((previous.models || []).map((model) => [key(model.country, model.make, model.model), model]));
const grouped = new Map();

for (const country of Object.keys(endpoints)) {
  const items = await fetchCountry(country);
  for (const item of items) {
    const make = cleanText(item.brand);
    const model = cleanText(item.model);
    const groupKey = key(country, make, model);
    if (!grouped.has(groupKey)) grouped.set(groupKey, {country, make, model, items:[]});
    grouped.get(groupKey).items.push(item);
  }
}

const usedMakeSlugs = new Map();
const resolvedMakeSlugs = new Map();
const usedModelSlugs = new Map();
const activeModels = [];

for (const group of [...grouped.values()].sort((a, b) => key(a.country, a.make, a.model).localeCompare(key(b.country, b.make, b.model), "ru"))) {
  const old = previousByKey.get(key(group.country, group.make, group.model));
  const makeScope = group.country;
  if (!usedMakeSlugs.has(makeScope)) usedMakeSlugs.set(makeScope, new Set());
  const makeKey = key(group.country, group.make, "");
  const existingMakeSlug = resolvedMakeSlugs.get(makeKey)
    || old?.makeSlug
    || (previous.brandHubs || []).find((hub) => key(hub.country, hub.make, "") === makeKey)?.makeSlug;
  const makeSlug = existingMakeSlug || uniqueSlug(slugify(group.make), usedMakeSlugs.get(makeScope), "make");
  resolvedMakeSlugs.set(makeKey, makeSlug);
  usedMakeSlugs.get(makeScope).add(makeSlug);

  const modelScope = `${group.country}::${makeSlug}`;
  if (!usedModelSlugs.has(modelScope)) usedModelSlugs.set(modelScope, new Set());
  const modelSlug = old?.slug || uniqueSlug(slugify(group.model), usedModelSlugs.get(modelScope), "model");
  usedModelSlugs.get(modelScope).add(modelSlug);

  const years = [...new Set(group.items.map((item) => Number(item.year)))].sort((a, b) => a - b);
  const prices = [...new Set(group.items.map((item) => Math.round(Number(item.price_cny))))].sort((a, b) => a - b);
  const newest = [...group.items].sort((a, b) => String(b.scraped_at || "").localeCompare(String(a.scraped_at || "")))[0];
  const yearText = years.length === 1 ? `${years[0]} года` : `${years[0]}–${years.at(-1)} годов`;

  activeModels.push({
    country:group.country,
    countryName:countryName[group.country],
    make:group.make,
    makeSlug,
    model:group.model,
    slug:modelSlug,
    years,
    prices,
    listingCount:group.items.length,
    listings:group.items.map(listingFacts).sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity)),
    image:newest.cover_image_url,
    summary:old?.summary || `${group.make} ${group.model} ${yearText} представлена в актуальном каталоге компании Примком с фотографиями и ценами автомобилей.`,
    status:"approved",
  });
}

const activeKeys = new Set(activeModels.map((model) => key(model.country, model.make, model.model)));
const inactiveModels = (previous.models || [])
  .filter((model) => !activeKeys.has(key(model.country, model.make, model.model)))
  .map((model) => ({...model, status:"inactive", inactiveSince:model.inactiveSince || new Date().toISOString().slice(0, 10)}));

const previousActiveModels = (previous.models || []).filter((model) => model.status !== "inactive");
if (!ALLOW_CATALOG_SHRINK && previousActiveModels.length) {
  const problems = [];
  for (const country of Object.keys(endpoints)) {
    const before = previousActiveModels.filter((model) => model.country === country).length;
    const after = activeModels.filter((model) => model.country === country).length;
    if (before > 0 && after === 0) problems.push(`${country}: было ${before} активных моделей, стало 0`);
  }
  const minimumActive = Math.ceil(previousActiveModels.length * MIN_ACTIVE_RATIO);
  if (activeModels.length < minimumActive) {
    problems.push(`всего: было ${previousActiveModels.length}, стало ${activeModels.length}, минимум ${minimumActive}`);
  }
  if (problems.length) {
    throw new Error(
      `catalog shrink guard: ${problems.join("; ")}. `
      + "Каталог API вернул подозрительно мало карточек; работающие SEO-страницы не тронуты. "
      + "Для намеренного сокращения запустить с SEO_ALLOW_CATALOG_SHRINK=1."
    );
  }
}

const allModels = [...activeModels, ...inactiveModels];
const hubs = new Map();
for (const model of activeModels) {
  const hubKey = key(model.country, model.make, "");
  if (!hubs.has(hubKey)) {
    hubs.set(hubKey, {
      country:model.country,
      countryName:model.countryName,
      make:model.make,
      makeSlug:model.makeSlug,
      models:[],
      status:"approved",
    });
  }
  hubs.get(hubKey).models.push(model.slug);
}

for (const oldHub of previous.brandHubs || []) {
  const hubKey = key(oldHub.country, oldHub.make, "");
  if (!hubs.has(hubKey)) hubs.set(hubKey, {...oldHub, status:"inactive"});
}

const today = new Date().toISOString().slice(0, 10);
const next = {
  ...previous,
  generatedAt:today,
  catalogSnapshotAt:today,
  source:API_BASE,
  brandHubs:[...hubs.values()].sort((a, b) => key(a.country, a.make, "").localeCompare(key(b.country, b.make, ""), "ru")),
  models:allModels,
};

await fs.mkdir(path.dirname(OUTPUT_PATH), {recursive:true});
await fs.writeFile(OUTPUT_PATH, `${JSON.stringify(next, null, 2)}\n`);
console.log(JSON.stringify({activeModels:activeModels.length, inactiveModels:inactiveModels.length, output:OUTPUT_PATH}));
