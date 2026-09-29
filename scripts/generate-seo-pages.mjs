import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT_ROOT = path.resolve(process.env.SEO_OUTPUT_ROOT || ROOT);
const REGISTRY_PATH = path.resolve(process.env.SEO_REGISTRY_PATH || path.join(ROOT, "seo/content-registry.json"));
const registry = JSON.parse(await fs.readFile(REGISTRY_PATH, "utf8"));
const SITE = "https://primcom.ru";
// «Сегодня» — по Владивостоку: сервер живёт по UTC, и после 07:00 утра по Владивостоку
// дата отстала бы на сутки.
const today = new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Vladivostok", year:"numeric", month:"2-digit", day:"2-digit"}).format(new Date());
// lastmod каждого адреса хранится отдельно и меняется, только когда изменилась сама страница.
// Раньше всем адресам ставилась дата запуска, и sitemap каждый день говорил, что всё обновилось.
const STATE_PATH = path.resolve(process.env.SEO_LASTMOD_STATE || path.join(ROOT, "seo/lastmod-state.json"));
let previousPages = {};
try { previousPages = JSON.parse(await fs.readFile(STATE_PATH, "utf8")).pages || {}; } catch { /* первый запуск */ }
const pageState = {};
function recordPage(url, content) {
  const hash = crypto.createHash("sha1").update(content).digest("hex");
  const previous = previousPages[url];
  pageState[url] = {hash, date:previous && previous.hash === hash ? previous.date : today};
}
// Версия ресурсов берётся из index.html сайта, а не зашита в скрипт: иначе после каждого
// фронтенд-релиза страницы каталога, собранные на сервере, ссылались бы на старый CSS.
// Число в запасном значении используется, только если index.html рядом не нашёлся.
const SITE_ROOT = path.resolve(process.env.SEO_SITE_ROOT || ROOT);
let VERSION = "20260920-cls-fix-2";
try {
  const indexHtml = await fs.readFile(path.join(SITE_ROOT, "index.html"), "utf8");
  const found = indexHtml.match(/css\/main\.css\?v=([0-9A-Za-z._-]+)/);
  if (found) VERSION = found[1];
} catch { /* index.html рядом нет — остаётся запасное значение */ }

for (const generatedDir of ["cars", "guides", "cases"]) {
  await fs.rm(path.join(OUTPUT_ROOT, generatedDir), {recursive:true, force:true});
}

const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const money = (value) => new Intl.NumberFormat("ru-RU").format(value) + " ₽";
const dateRu = (value) => new Intl.DateTimeFormat("ru-RU", {day:"numeric", month:"long", year:"numeric"}).format(new Date(`${value}T00:00:00+10:00`));
const unique = (items) => [...new Set(items)];
const shortDate = (value) => new Intl.DateTimeFormat("ru-RU", {day:"2-digit", month:"2-digit", year:"numeric"}).format(new Date(`${value}T00:00:00+10:00`));
const plural = (count, one, few, many) => count % 10 === 1 && count % 100 !== 11 ? one : [2,3,4].includes(count % 10) && ![12,13,14].includes(count % 100) ? few : many;
const countryLabel = {japan:"Япония", china:"Китай", korea:"Корея"};
const countryCatalog = {japan:"/pages/auto-iz-yaponii.html", china:"/pages/auto-iz-kitaya.html", korea:"/pages/auto-iz-korei.html"};
const activeModels = registry.models.filter((model) => model.status !== "inactive");

// Таблица конкретных автомобилей модели. Колонка появляется, только если значение есть
// хотя бы у одного автомобиля; всё берётся из каталога, ничего не домысливается.
function listingsTable(m) {
  const list = Array.isArray(m.listings) ? m.listings : [];
  if (!list.length) return "";
  const nf = new Intl.NumberFormat("ru-RU");
  const cols = [
    {key:"year", head:"Год", cell:(x) => x.year},
    {key:"trim", head:"Комплектация", cell:(x) => escapeHtml(x.trim)},
    {key:"body", head:"Кузов", cell:(x) => escapeHtml(x.body)},
    {key:"engineVolumeL", head:"Объём", cell:(x) => `${String(x.engineVolumeL).replace(".", ",")} л`},
    {key:"powerHp", head:"Мощность", cell:(x) => `${x.powerHp} л.с.`},
    {key:"drive", head:"Привод", cell:(x) => escapeHtml(x.drive)},
    {key:"transmission", head:"КПП", cell:(x) => escapeHtml(x.transmission)},
    {key:"mileageKm", head:"Пробег", cell:(x) => `${nf.format(x.mileageKm)} км`},
    {key:"grade", head:"Оценка", cell:(x) => escapeHtml(x.grade)},
    {key:"price", head:"Цена под ключ", cell:(x) => money(x.price)},
    {key:"listedAt", head:"Актуально на", cell:(x) => shortDate(x.listedAt)},
  ].filter((c) => list.some((x) => x[c.key] !== undefined));
  if (cols.length < 3) return "";
  const head = cols.map((c) => `<th scope="col">${c.head}</th>`).join("");
  const rows = list.map((x) => `<tr>${cols.map((c) => `<td>${x[c.key] === undefined ? "—" : c.cell(x)}</td>`).join("")}</tr>`).join("");
  return `<section class="seo-section"><h2>Автомобили ${escapeHtml(m.make)} ${escapeHtml(m.model)} в каталоге</h2><p>Параметры и цены взяты из карточек каталога. Цена указана под ключ на дату из колонки «Актуально на»; наличие и актуальную цену подтверждает менеджер перед покупкой.</p><div class="rate-table__scroll"><table class="rate-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function topicLinks(links) {
  const seenHrefs = new Set();
  const seenLabels = new Set();
  const cleanLinks = links.filter(({href, label}) => {
    const cleanHref = String(href || "").trim();
    const cleanLabel = String(label || "").replace(/\s+/g, " ").trim();
    if (!cleanHref || !cleanLabel || seenHrefs.has(cleanHref) || seenLabels.has(cleanLabel.toLowerCase())) return false;
    seenHrefs.add(cleanHref);
    seenLabels.add(cleanLabel.toLowerCase());
    return true;
  }).slice(0, 12);
  return `<details class="seo-topics"><summary><span>Популярные направления и полезные ссылки</span><span class="seo-topics__hint" aria-hidden="true">Открыть</span></summary><nav class="seo-topics__links" aria-label="Популярные направления и полезные ссылки">${cleanLinks.map(({href, label}) => `<a href="${href}">${escapeHtml(label)}</a>`).join("")}</nav></details>`;
}

function breadcrumbs(items) {
  return `<nav class="seo-breadcrumbs" aria-label="Хлебные крошки"><ol>${items.map((item, index) => `<li>${index === items.length - 1 ? `<span aria-current="page">${escapeHtml(item.name)}</span>` : `<a href="${item.url}">${escapeHtml(item.name)}</a>`}</li>`).join("")}</ol></nav>`;
}

function layout({title, description, canonical, h1, body, crumbs, robots = "index,follow", schemaType = "WebPage"}) {
  const schema = {
    "@context":"https://schema.org",
    "@graph":[
      {"@type":schemaType,"name":h1,"description":description,"url":SITE + canonical,"isPartOf":{"@type":"WebSite","name":"Примком","url":SITE + "/"}},
      {"@type":"BreadcrumbList","itemListElement":crumbs.map((item, index) => ({"@type":"ListItem","position":index + 1,"name":item.name,"item":SITE + item.url}))}
    ]
  };
  return `<!doctype html>
<html lang="ru" data-root="/">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="format-detection" content="telephone=no" />
  <meta name="theme-color" content="#101325" />
  <meta name="color-scheme" content="dark" />
  <meta name="robots" content="${robots}" />
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(description)}" />
  <link rel="canonical" href="${SITE}${canonical}" />
  <meta property="og:type" content="website" />
  <meta property="og:locale" content="ru_RU" />
  <meta property="og:site_name" content="Примком" />
  <meta property="og:title" content="${escapeHtml(h1)}" />
  <meta property="og:description" content="${escapeHtml(description)}" />
  <meta property="og:url" content="${SITE}${canonical}" />
  <meta property="og:image" content="${SITE}/banner/banner_main.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${escapeHtml(h1)}" />
  <meta name="twitter:description" content="${escapeHtml(description)}" />
  <meta name="twitter:image" content="${SITE}/banner/banner_main.png" />
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />
  <link rel="manifest" href="/site.webmanifest" />
  <link rel="stylesheet" href="/css/main.css?v=${VERSION}" />
  <script type="application/ld+json">${JSON.stringify(schema)}</script>
</head>
<body>
  <a class="skip-link" href="#main">К основному содержимому</a>
  <div class="page-bg" aria-hidden="true"><div class="page-bg__base"></div><div class="page-bg__aurora"></div><div class="page-bg__grid"></div><div class="page-bg__grain"></div></div>
  <div id="site-header"></div>
  <main class="site-main" id="main"><div class="container seo-page">${breadcrumbs(crumbs)}<h1 class="section__title">${escapeHtml(h1)}</h1>${body}</div></main>
  <div id="site-footer"></div>
  <script type="module" src="/js/app.js?v=${VERSION}"></script>
</body>
</html>`;
}

async function writeUrl(url, html) {
  const dir = path.join(OUTPUT_ROOT, url.replace(/^\//, ""));
  await fs.mkdir(dir, {recursive:true});
  await fs.writeFile(path.join(dir, "index.html"), html);
}

const approvedUrls = [];
async function publish(url, data) {
  const html = layout({...data, canonical:url});
  await writeUrl(url, html);
  recordPage(url, html);
  if (data.robots !== "noindex,follow") approvedUrls.push(url);
}

const modelUrl = (m) => `/cars/${m.country}/${m.makeSlug}/${m.slug}/`;
const makeUrl = (h) => `/cars/${h.country}/${h.makeSlug}/`;
const modelCard = (m) => {
  const priceText = Math.min(...m.prices) === Math.max(...m.prices) ? money(m.prices[0]) : `${money(Math.min(...m.prices))} — ${money(Math.max(...m.prices))}`;
  const years = unique(m.years).sort((a,b) => a-b);
  const countWord = plural(m.listingCount, "предложение", "предложения", "предложений");
  return `<article class="seo-card seo-card--model"><a class="seo-card__image" href="${modelUrl(m)}"><img src="https://api.primcom.ru${m.image}" alt="${escapeHtml(`${m.make} ${m.model} из ${m.countryName}`)}" width="480" height="320" loading="lazy" /></a><div class="seo-card__body"><p class="seo-card__eyebrow">${countryLabel[m.country]}</p><h2><a href="${modelUrl(m)}">${m.make} ${m.model}</a></h2><p>${years.join(", ")} · ${m.listingCount} ${countWord}</p><p class="seo-card__meta">${priceText}</p><a class="btn btn--small" href="${modelUrl(m)}">Смотреть модель</a></div></article>`;
};

await publish("/cars/", {
  title:"Каталог моделей авто из Японии, Кореи и Китая | Примком",
  description:"Модели автомобилей из Японии, Кореи и Китая с актуальными предложениями каталога и переходом к расчету стоимости под ключ.",
  h1:"Автомобили из Японии, Кореи и Китая",
  crumbs:[{name:"Главная",url:"/"},{name:"Автомобили",url:"/cars/"}],
  body:`<p class="section__lead">Выберите страну, марку и модель автомобиля. В карточках указаны цены под ключ на дату публикации объявления.</p><div class="seo-card-grid">${registry.brandHubs.filter((hub) => hub.status !== "inactive").map((hub) => { const count = activeModels.filter((m) => m.country === hub.country && m.makeSlug === hub.makeSlug).length; return `<article class="seo-card"><p class="seo-card__eyebrow">${countryLabel[hub.country]}</p><h2>${hub.make}</h2><p>${count} ${count === 1 ? "модель" : count < 5 ? "модели" : "моделей"} ${hub.make} из ${hub.countryName}.</p><a class="btn btn--small" href="${makeUrl(hub)}">Смотреть ${hub.make}</a></article>`; }).join("")}</div><section class="seo-section"><h2>Модели в каталоге компании Примком</h2><p>Данные в карточках обновлены ${dateRu(registry.catalogSnapshotAt)}. Наличие автомобиля и актуальную цену подтверждает менеджер перед покупкой.</p><div class="seo-card-grid seo-card-grid--models">${activeModels.map(modelCard).join("")}</div></section>`
});

for (const hub of registry.brandHubs) {
  const isInactiveHub = hub.status === "inactive";
  const models = activeModels.filter((m) => m.country === hub.country && m.makeSlug === hub.makeSlug);
  const brandTopics = [
    ...models.map((model) => ({href:modelUrl(model), label:`${model.make} ${model.model} из ${model.countryName}`})),
    {href:countryCatalog[hub.country], label:`Автомобили из ${hub.countryName} под заказ`},
    {href:"/pages/kalkulyator-stoimosti.html", label:"Рассчитать стоимость ввоза"},
    {href:"/pages/dostavka.html", label:"Доставка автомобиля по России"},
    {href:"/pages/rastamozhka-i-poshliny.html", label:"Растаможка и пошлины"},
  ];
  await publish(makeUrl(hub), {
    title:`Автомобили ${hub.make} из ${hub.countryName} под заказ | Примком`,
    description:`Модели ${hub.make} из ${hub.countryName} под заказ: автомобили в каталоге, годы выпуска и цены под ключ.`,
    h1:`Автомобили ${hub.make} из ${hub.countryName}`,
    robots:isInactiveHub ? "noindex,follow" : "index,follow",
    crumbs:[{name:"Главная",url:"/"},{name:"Автомобили",url:"/cars/"},{name:countryLabel[hub.country],url:countryCatalog[hub.country]},{name:hub.make,url:makeUrl(hub)}],
    body:isInactiveHub
      ? `<p class="section__lead">Сейчас в каталоге нет актуальных предложений ${hub.make} из ${hub.countryName}. Посмотрите другие марки или оставьте заявку на индивидуальный подбор.</p>${topicLinks(brandTopics)}<section class="seo-section"><h2>Что можно сделать сейчас</h2><div class="seo-link-grid"><a href="${countryCatalog[hub.country]}">Открыть каталог</a><a href="/pages/process-podbora.html">Изучить процесс подбора</a><a href="/pages/kontakty.html">Связаться с компанией Примком</a></div></section>`
      : `<p class="section__lead">Выберите модель ${hub.make} из ${hub.countryName}, сравните доступные автомобили и уточните у менеджера наличие и актуальную цену. Цены в каталоге указаны под ключ на дату публикации объявления.</p><div class="seo-card-grid seo-card-grid--models">${models.map(modelCard).join("")}</div>${topicLinks(brandTopics)}<section class="seo-section"><h2>Как заказать ${hub.make}</h2><p>После выбора автомобиля компания Примком проверит данные предложения, подтвердит цену и зафиксирует условия в договоре. Затем компания организует выкуп, доставку и оформление.</p><div class="seo-link-grid"><a href="/pages/process-podbora.html">Процесс подбора</a><a href="/pages/kalkulyator-stoimosti.html">Калькулятор платежей</a><a href="/pages/dogovor-i-garantii.html">Договор и гарантии</a></div></section>`
  });
}

for (const m of registry.models) {
  const isInactive = m.status === "inactive";
  const brandRelated = activeModels.filter((x) => x.country === m.country && x.makeSlug === m.makeSlug && x.slug !== m.slug).slice(0, 4);
  const related = brandRelated.length
    ? brandRelated
    : activeModels.filter((x) => x.country === m.country && x.makeSlug !== m.makeSlug).slice(0, 4);
  const catalogQuery = `${countryCatalog[m.country]}?brand=${encodeURIComponent(m.make)}&model=${encodeURIComponent(m.model)}`;
  const years = unique(m.years).sort((a,b) => a-b);
  const priceText = Math.min(...m.prices) === Math.max(...m.prices) ? money(m.prices[0]) : `${money(Math.min(...m.prices))} — ${money(Math.max(...m.prices))}`;
  const priceDescription = Math.min(...m.prices) === Math.max(...m.prices) ? `цена под ключ ${priceText}` : `цены под ключ от ${money(Math.min(...m.prices))} до ${money(Math.max(...m.prices))}`;
  const yearText = years.length === 1 ? `${years[0]} года` : `${years[0]}–${years.at(-1)} годов`;
  const countText = `${m.listingCount} ${plural(m.listingCount, "автомобиль", "автомобиля", "автомобилей")}`;
  const approvedHub = registry.brandHubs.find((hub) => hub.country === m.country && hub.makeSlug === m.makeSlug);
  const modelCrumbs = [{name:"Главная",url:"/"},{name:"Автомобили",url:"/cars/"},{name:countryLabel[m.country],url:countryCatalog[m.country]}];
  if (approvedHub) modelCrumbs.push({name:m.make,url:makeUrl(approvedHub)});
  modelCrumbs.push({name:`${m.make} ${m.model}`,url:modelUrl(m)});
  const modelTopics = [
    ...(approvedHub ? [{href:makeUrl(approvedHub), label:`Все ${m.make} из ${m.countryName}`}] : []),
    {href:countryCatalog[m.country], label:`Автомобили из ${m.countryName} под заказ`},
    {href:"/pages/kalkulyator-stoimosti.html", label:`Рассчитать стоимость ${m.make} ${m.model}`},
    {href:"/pages/dostavka.html", label:"Доставка автомобиля по России"},
    {href:"/pages/rastamozhka-i-poshliny.html", label:"Растаможка автомобиля"},
    {href:"/pages/process-podbora.html", label:"Как проходит подбор автомобиля"},
    ...related.map((model) => ({href:modelUrl(model), label:`${model.make} ${model.model} из ${model.countryName}`})),
  ];
  await publish(modelUrl(m), {
    title:`${m.make} ${m.model} из ${m.countryName} под заказ — цены | Примком`,
    description:`${m.make} ${m.model} из ${m.countryName} под заказ: ${yearText}, ${priceDescription}. Доставка во Владивосток и по России.`,
    h1:`${m.make} ${m.model} из ${m.countryName} под заказ`,
    schemaType:"CollectionPage",
    robots:isInactive ? "noindex,follow" : "index,follow",
    crumbs:modelCrumbs,
    body:isInactive
      ? `<p class="section__lead">Сейчас в каталоге нет актуальных предложений ${m.make} ${m.model} из ${m.countryName}. Посмотрите другие модели или оставьте заявку на индивидуальный подбор.</p>${topicLinks(modelTopics)}<section class="seo-section"><h2>Что можно сделать сейчас</h2><div class="seo-link-grid"><a href="${countryCatalog[m.country]}">Открыть каталог</a><a href="/pages/process-podbora.html">Изучить процесс подбора</a><a href="/pages/kontakty.html">Связаться с компанией Примком</a></div></section>`
      : `<p class="section__lead">В каталоге компании Примком ${countText} ${m.make} ${m.model} ${yearText}. Перейдите к автомобилям, чтобы посмотреть фотографии и подробные параметры.</p><div class="seo-model-hero"><img src="https://api.primcom.ru${m.image}" alt="${escapeHtml(`${m.make} ${m.model} из ${m.countryName}`)}" width="720" height="480" loading="eager" /><div class="seo-facts"><h2>${m.make} ${m.model} в каталоге</h2><dl><div><dt>Автомобилей</dt><dd>${m.listingCount}</dd></div><div><dt>Годы выпуска</dt><dd>${years.join(", ")}</dd></div><div><dt>${m.prices.length > 1 ? "Диапазон цен под ключ" : "Цена под ключ"}</dt><dd>${priceText}</dd></div><div><dt>Данные обновлены</dt><dd>${dateRu(m.updatedAt || registry.catalogSnapshotAt)}</dd></div></dl><a class="btn btn--primary" href="${catalogQuery}">Посмотреть автомобили</a></div></div>${listingsTable(m)}${topicLinks(modelTopics)}<section class="seo-section"><h2>Что входит в подбор</h2><p>Компания Примком проверяет данные выбранного автомобиля, согласовывает бюджет и условия покупки, организует выкуп, доставку и оформление. Указанная цена — цена автомобиля под ключ на дату публикации объявления в каталоге; наличие и актуальную цену подтверждает менеджер перед покупкой.</p></section><section class="seo-section"><h2>Как получить расчёт стоимости</h2><ol class="seo-steps"><li>Откройте предложения ${m.make} ${m.model}.</li><li>Выберите автомобиль по году, фотографиям и параметрам.</li><li>Отправьте выбранный вариант менеджеру, чтобы подтвердить наличие, актуальную цену и условия.</li></ol><div class="seo-link-grid"><a href="/pages/kalkulyator-stoimosti.html">Калькулятор стоимости</a><a href="/pages/dostavka.html">Доставка</a><a href="/pages/rastamozhka-i-poshliny.html">Растаможка и пошлины</a><a href="/pages/dogovor-i-garantii.html">Договор и гарантии</a></div></section>${related.length ? `<section class="seo-section"><h2>${brandRelated.length ? `Другие модели ${m.make}` : `Другие модели из ${m.countryName}`}</h2><div class="seo-link-grid">${related.map((x) => `<a href="${modelUrl(x)}">${x.make} ${x.model}</a>`).join("")}</div></section>` : ""}`
  });
}

await publish("/guides/", {
  title:"Полезные материалы о покупке авто из Азии | Примком",
  description:"Практические руководства компании Примком по выбору, расчету и покупке автомобилей из Японии, Кореи и Китая.",
  h1:"Руководства по покупке авто из Азии",
  crumbs:[{name:"Главная",url:"/"},{name:"Руководства",url:"/guides/"}],
  body:`<p class="section__lead">Материалы помогают подготовиться к выбору автомобиля и разговору с менеджером. Точные цены, сроки и условия рассчитываются для конкретного предложения.</p><div class="seo-card-grid">${registry.guides.map((g) => `<article class="seo-card"><h2>${escapeHtml(g.title)}</h2><p>${escapeHtml(g.description)}</p><a class="btn btn--small" href="/guides/${g.slug}/">Читать</a></article>`).join("")}</div>`
});

for (const guide of registry.guides) {
  await publish(`/guides/${guide.slug}/`, {
    title:`${guide.title} | Примком`, description:guide.description, h1:guide.title, schemaType:"Article",
    crumbs:[{name:"Главная",url:"/"},{name:"Руководства",url:"/guides/"},{name:guide.title,url:`/guides/${guide.slug}/`}],
    body:`<p class="section__lead">${escapeHtml(guide.description)}</p>${guide.sections.map(([heading,text]) => `<section class="seo-section"><h2>${escapeHtml(heading)}</h2><p>${escapeHtml(text)}</p></section>`).join("")}<section class="seo-section"><h2>Следующий шаг</h2><div class="seo-link-grid"><a href="/cars/">Выбрать модель</a><a href="/pages/kalkulyator-stoimosti.html">Открыть калькулятор</a><a href="/pages/process-podbora.html">Изучить процесс подбора</a><a href="/pages/kontakty.html">Связаться с компанией Примком</a></div></section>`
  });
}


const existing = [
  ["/","weekly","1.0"],
  ["/pages/auto-iz-yaponii.html","weekly","0.9"], ["/pages/auto-iz-korei.html","weekly","0.9"], ["/pages/auto-iz-kitaya.html","weekly","0.9"],
  ["/pages/rastamozhka-i-poshliny.html","monthly","0.8"], ["/pages/dostavka.html","monthly","0.8"], ["/pages/process-podbora.html","monthly","0.8"],
  ["/pages/dogovor-i-garantii.html","monthly","0.8"], ["/pages/kalkulyator-stoimosti.html","weekly","0.9"], ["/pages/faq.html","monthly","0.8"], ["/pages/kontakty.html","monthly","0.9"]
];
for (const [url] of existing) {
  const file = url === "/" ? "index.html" : url.replace(/^\//, "");
  try { recordPage(url, await fs.readFile(path.join(SITE_ROOT, file), "utf8")); } catch { pageState[url] = {hash:"", date:today}; }
}
const sitemapRows = [...existing, ...approvedUrls.map((url) => [url,"weekly",url.split("/").filter(Boolean).length <= 1 ? "0.9" : "0.8"])];
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${sitemapRows.map(([url,freq,priority]) => `  <url>\n    <loc>${SITE}${url}</loc>\n    <lastmod>${(pageState[url] || {date:today}).date}</lastmod>\n    <changefreq>${freq}</changefreq>\n    <priority>${priority}</priority>\n  </url>`).join("\n")}\n</urlset>\n`;
await fs.mkdir(OUTPUT_ROOT, {recursive:true});
await fs.writeFile(path.join(OUTPUT_ROOT, "sitemap.xml"), sitemap);
await fs.writeFile(path.join(OUTPUT_ROOT, "lastmod-state.json"), JSON.stringify({pages:pageState}, null, 1));
console.log(`Generated ${approvedUrls.length} deploy-ready indexable URLs. Drafts remain registry-only.`);
