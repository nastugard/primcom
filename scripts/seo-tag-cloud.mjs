// Облако тегов «Полезно знать»: 10 коротких тем, под каждой — ответ на поисковый вопрос.
// Ответы — обычный HTML в коде страницы (видны роботам без JS), браузер сворачивает их
// встроенным скриптом сразу после разметки. Те же вопросы уходят в FAQPage JSON-LD.
// Используется генератором каталога и скриптом build-tag-clouds.mjs для статичных страниц.

const esc = (value = "") => String(value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const num = (value) => new Intl.NumberFormat("ru-RU").format(Math.round(value));
const money = (value) => `${num(value)} ₽`;
const plural = (n, one, few, many) => n % 10 === 1 && n % 100 !== 11 ? one : [2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100) ? few : many;
const unique = (items) => [...new Set(items)];
const listJoin = (items) => items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} и ${items.at(-1)}`;
const MONTHS = ["январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"];
const MONTHS_IN = ["январе","феврале","марте","апреле","мае","июне","июле","августе","сентябре","октябре","ноябре","декабре"];
const MONTHS_GEN = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
const COUNTRY_NAME = {japan:"Японии", korea:"Кореи", china:"Китая"};
const COUNTRY_PAGE = {japan:"/pages/auto-iz-yaponii.html", korea:"/pages/auto-iz-korei.html", china:"/pages/auto-iz-kitaya.html"};

/* ---------- разметка ---------- */

const SCRIPT = `<script>(function(){var r=document.currentScript&&document.currentScript.closest("[data-seo-tags]");if(!r)return;var t=[].slice.call(r.querySelectorAll(".seo-tags__tag")),p=[].slice.call(r.querySelectorAll(".seo-tags__panel"));function s(i){t.forEach(function(b,k){var o=k===i&&b.getAttribute("aria-expanded")!=="true";b.setAttribute("aria-expanded",o?"true":"false");p[k].hidden=!o;});}p.forEach(function(x){x.hidden=true;});t.forEach(function(b,i){b.addEventListener("click",function(){s(i);});});r.classList.add("is-ready");})();</script>`;

export function renderTagCloud(tags, {id = "seo-tags", title = "Полезно знать", lead = "Короткие ответы на частые вопросы. Нажмите на тему, чтобы прочитать ответ."} = {}) {
  if (!tags?.length) return "";
  const buttons = tags.map((tag, i) => `<button class="seo-tags__tag" type="button" id="${id}-tag-${i}" aria-expanded="false" aria-controls="${id}-panel-${i}">${esc(tag.label)}</button>`).join("");
  const panels = tags.map((tag, i) => {
    const text = (tag.text || []).map((p) => `<p>${esc(p)}</p>`).join("");
    const list = tag.list?.length ? `<ul>${tag.list.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>` : "";
    const after = (tag.after || []).map((p) => `<p>${esc(p)}</p>`).join("");
    const link = tag.link ? `<a class="seo-tags__link" href="${esc(tag.link.href)}">${esc(tag.link.label)} →</a>` : "";
    return `<article class="seo-tags__panel" id="${id}-panel-${i}" role="region" aria-labelledby="${id}-q-${i}"><h3 id="${id}-q-${i}">${esc(tag.question)}</h3>${text}${list}${after}${link}</article>`;
  }).join("");
  return `<section class="seo-tags" id="${id}" aria-labelledby="${id}-title" data-seo-tags><div class="seo-tags__head"><h2 class="seo-tags__title" id="${id}-title">${esc(title)}</h2><p class="seo-tags__lead">${esc(lead)}</p></div><div class="seo-tags__cloud">${buttons}</div><div class="seo-tags__panels">${panels}</div>${SCRIPT}</section>`;
}

export function faqEntities(tags) {
  return (tags || []).map((tag) => ({
    "@type": "Question",
    "name": tag.question,
    "acceptedAnswer": {"@type": "Answer", "text": [...(tag.text || []), ...(tag.list || []), ...(tag.after || [])].join(" ")},
  }));
}

/* ---------- расчёты для каталога ---------- */

// Ориентир даты ввоза: через два месяца после сборки страницы.
export function importDate(now = new Date()) {
  const d = new Date(now.getFullYear(), now.getMonth() + 2, 1);
  return {year: d.getFullYear(), month: d.getMonth() + 1, label: `${MONTHS[d.getMonth()]} ${d.getFullYear()}`, labelIn: `${MONTHS_IN[d.getMonth()]} ${d.getFullYear()}`};
}

function ageNote(year, imp) {
  const {year: I, month: M} = imp;
  const before = MONTHS_GEN[M - 1];
  if (year < I - 5) return `${year} год — старше 5 лет, пошлина по повышенной ставке`;
  if (year === I - 5) return M === 1 ? `${year} год — от 3 до 5 лет, проходной` : `${year} год — выпущенные до ${before} уже старше 5 лет, с ${before} — ещё проходные`;
  if (year < I - 3) return `${year} год — от 3 до 5 лет, проходной`;
  if (year === I - 3) return M === 1 ? `${year} год — до 3 лет, пошлина от стоимости` : `${year} год — выпущенные до ${before} проходные, с ${before} — ещё до 3 лет`;
  return `${year} год — до 3 лет, пошлина считается от стоимости`;
}

const RATE_35 = [[1000,1.5],[1500,1.7],[1800,2.5],[2300,2.7],[3000,3.0],[Infinity,3.6]];
const RATE_5 = [[1000,3.0],[1500,3.2],[1800,3.5],[2300,4.8],[3000,5.0],[Infinity,5.7]];
const rateFor = (table, cc) => table.find(([max]) => cc <= max)[1];
const volText = (l) => `${String(l).replace(".", ",")} л`;
const normBody = (b = "") => ({"хетчбэк":"хэтчбек","хэтчбэк":"хэтчбек","хэтчбек":"хэтчбек"})[b.toLowerCase()] || b.toLowerCase();
const gradeNum = (g) => g ? String(g).replace(/[^\d.,]/g, "").replace(",", ".") : "";

function cheapest(listings) { return [...listings].sort((a, b) => a.price - b.price)[0]; }
function priceRange(prices) {
  const min = Math.min(...prices), max = Math.max(...prices);
  return min === max ? money(min) : `от ${money(min)} до ${money(max)}`;
}
function dateRu(value) {
  const d = new Date(`${value}T00:00:00+10:00`);
  return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()}`;
}

function dutyLines(volumes) {
  return unique(volumes.filter((v) => v > 0)).sort((a, b) => a - b).map((v) => {
    const cc = Math.round(v * 1000);
    const r35 = rateFor(RATE_35, cc), r5 = rateFor(RATE_5, cc);
    return `${volText(v)}: от 3 до 5 лет — ${String(r35).replace(".", ",")} € за см³, около ${num(r35 * cc)} €; старше 5 лет — ${String(r5).replace(".", ",")} € за см³, около ${num(r5 * cc)} €`;
  });
}

/* ---------- теги страницы модели ---------- */

export function modelTags(m, {models = [], imp = importDate(), overrides = {}, modelUrl = () => ""} = {}) {
  const name = `${m.make} ${m.model}`;
  const from = COUNTRY_NAME[m.country];
  const L = m.listings || [];
  if (!L.length) return [];
  const catalog = `${COUNTRY_PAGE[m.country]}?brand=${encodeURIComponent(m.make)}&model=${encodeURIComponent(m.model)}`;
  const years = unique(L.map((l) => l.year)).sort((a, b) => a - b);
  const vols = unique(L.map((l) => l.engineVolumeL).filter((v) => v > 0)).sort((a, b) => a - b);
  const powers = unique(L.map((l) => l.powerHp).filter(Boolean)).sort((a, b) => a - b);
  const low = cheapest(L);
  const dates = L.map((l) => l.listedAt).sort();
  const tags = [];

  tags.push({id: "price", label: `Цена ${m.model}`, question: `Сколько стоит ${name} из ${from} под ключ`, text: [
    `В каталоге Примкома ${L.length} ${plural(L.length, "предложение", "предложения", "предложений")} ${name}: ${priceRange(L.map((l) => l.price))} под ключ. Цены указаны на дату объявления — ${dates[0] === dates.at(-1) ? dateRu(dates[0]) : `с ${dateRu(dates[0])} по ${dateRu(dates.at(-1))}`}.`,
    `Самый доступный вариант — ${low.year} год${low.mileageKm ? `, пробег ${num(low.mileageKm)} км` : ""}, ${money(low.price)}. Доставка в другой город считается отдельно.`,
  ], link: {href: catalog, label: `Все ${name} в каталоге`}});

  tags.push({id: "age", label: `${m.model}: проходной?`, question: `Проходной ли ${name} из ${from} ${years.length > 1 ? `${years[0]}–${years.at(-1)}` : years[0]} года`, text: [
    `Проходным считается автомобиль от 3 до 5 лет на дату ввоза: пошлина для него считается по объёму двигателя и обычно самая низкая. Если ввозить ${name} в ${imp.labelIn}:`,
  ], list: years.map((y) => ageNote(y, imp)), after: ["Возраст считают от месяца выпуска, поэтому точную категорию проверяем по документам машины."], link: {href: "/pages/rastamozhka-i-poshliny.html", label: "Ставки пошлин по возрасту"}});

  tags.push({id: "duty", label: `Пошлина на ${m.model}`, question: `Какая пошлина на ${name}${vols.length === 1 ? ` ${volText(vols[0])}` : ""} из ${from}`, text: vols.length
    ? [`Для физлица пошлина на ${name} старше 3 лет зависит от объёма двигателя. Ориентир в евро:`]
    : [`Объём двигателя в объявлениях ${name} не указан, поэтому пошлину считаем по документам конкретной машины.`],
    list: dutyLines(vols), after: [`Для машин до 3 лет действует другой расчёт: 48–54% от стоимости, но не меньше минимальной ставки за см³. В рублях сумма считается по курсу евро ЦБ на день оформления; объём в см³ берётся из документов.`], link: {href: "/pages/kalkulyator-stoimosti.html", label: "Посчитать в калькуляторе"}});

  const util = powers.length
    ? powers.every((p) => p <= 160)
      ? `Мощность ${name} в каталоге — ${listJoin(powers.map((p) => `${p} л.с.`))}, это не больше 160 л.с. При ввозе для себя сбор льготный: 5 200 ₽ для машины старше 3 лет и 3 400 ₽ для более новой.`
      : `Мощность ${name} в каталоге — ${listJoin(powers.map((p) => `${p} л.с.`))}. Версии мощнее 160 л.с. не попадают под льготу: сбор считается по повышенной шкале и зависит от мощности, объёма и возраста, поэтому сумму показываем в расчёте.`
    : `В объявлениях ${name} мощность не указана, проверим её по документам. Если у версии не больше 160 л.с. и объём до 3 л, при ввозе для себя сбор льготный: 5 200 ₽ для машины старше 3 лет и 3 400 ₽ для более новой. Мощнее 160 л.с. — сбор по повышенной шкале.`;
  tags.push({id: "util", label: `Утильсбор ${m.model}`, question: `Какой утильсбор на ${name} из ${from}`, text: [util, "Гибриды и электромобили считаются по своим правилам, их проверяем отдельно."], link: {href: "/pages/rastamozhka-i-poshliny.html", label: "Как считается утильсбор"}});

  const withKm = L.filter((l) => l.mileageKm);
  tags.push({id: "mileage", label: `Пробег ${m.model}`, question: `С каким пробегом продаются ${name} из ${from}`, text: withKm.length
    ? [`Пробег ${name} в каталоге — ${withKm.length > 1 ? `от ${num(Math.min(...withKm.map((l) => l.mileageKm)))} до ${num(Math.max(...withKm.map((l) => l.mileageKm)))} км` : `${num(withKm[0].mileageKm)} км`}. По каждому предложению:`]
    : [`Пробег в объявлениях ${name} не указан — запросим его вместе с документами.`],
    list: withKm.map((l) => `${l.year} год, ${num(l.mileageKm)} км${l.grade ? `, оценка ${gradeNum(l.grade)}` : ""} — ${money(l.price)}`),
    after: [m.country === "japan" ? "Для Японии пробег сверяем с аукционным листом: в карточке он округлён." : "Пробег сверяем с документами и историей обслуживания до покупки."]});

  if (m.country === "japan") {
    const big = vols.filter((v) => v > 1.9);
    tags.push({id: "export", label: "Запрет 1,9 л", question: `Можно ли привезти ${name} из Японии при запрете на машины больше 1,9 л`, text: [
      "С 9 августа 2023 года Япония не выпускает в Россию автомобили с двигателем больше 1 900 см³, а также гибриды и электромобили.",
      big.length
        ? `В каталоге есть ${name} ${listJoin(big.map(volText))} — на них запрет распространяется. Как поставляется конкретная машина, менеджер расскажет до договора.${vols.some((v) => v <= 1.9) ? ` Версии ${listJoin(vols.filter((v) => v <= 1.9).map(volText))} под запрет не попадают.` : ""}`
        : `У ${name} в каталоге объём ${listJoin(vols.map(volText))} — это меньше 1,9 л, поэтому бензиновые и дизельные версии под запрет не попадают. Гибридную версию из Японии напрямую вывезти нельзя.`,
    ], link: {href: COUNTRY_PAGE.japan, label: "Авто из Японии"}});
  } else if (m.country === "korea") {
    const big = vols.filter((v) => v > 2);
    tags.push({id: "export", label: "Ограничение 2 л", question: `Можно ли привезти ${name} из Кореи с двигателем больше 2 л`, text: [
      "С начала 2024 года Южная Корея выпускает в Россию автомобили с двигателем больше 2 литров только по специальному разрешению правительства, и таможня Кореи усиливает контроль.",
      big.length
        ? `В каталоге есть ${name} ${listJoin(big.map(volText))}. Способ поставки такой машины менеджер объяснит до договора.`
        : `У ${name} в каталоге объём ${listJoin(vols.map(volText))}, ограничение по объёму её не касается.`,
    ], link: {href: COUNTRY_PAGE.korea, label: "Авто из Кореи"}});
  } else {
    tags.push({id: "export", label: "Китайская версия", question: `Что проверить у ${name} для китайского рынка`, text: [
      `${name} из Китая сделан для внутреннего рынка. До покупки проверяем язык мультимедиа и приложений, комплектацию и наличие сервисной поддержки в России.`,
      "При оформлении СБКТС на машину ставят систему ЭРА-ГЛОНАСС, без неё ЭПТС не выдадут. Это входит в расчёт под ключ.",
    ], link: {href: COUNTRY_PAGE.china, label: "Авто из Китая"}});
  }

  const graded = L.filter((l) => l.grade);
  if (m.country === "japan" && graded.length) {
    tags.push({id: "grade", label: "Аукционная оценка", question: `Какие аукционные оценки у ${name} в каталоге`, text: [
      `У ${name} в каталоге ${graded.length === 1 ? "оценка" : "оценки"} ${listJoin(unique(graded.map((l) => gradeNum(l.grade))).sort())}. Оценка 4 и выше — хорошее состояние с небольшими следами эксплуатации, 3,5 — заметные дефекты, которые смотрим на схеме кузова.`,
    ], list: graded.map((l) => `${l.year} год${l.trim ? `, ${l.trim}` : ""}: оценка ${gradeNum(l.grade)}${l.mileageKm ? `, ${num(l.mileageKm)} км` : ""}`), link: {href: "/guides/kak-chitat-aukcionnyy-list/", label: "Как читать аукционный лист"}});
  } else {
    const drives = unique(L.map((l) => (l.drive || "").toLowerCase()).filter(Boolean));
    const bodies = unique(L.map((l) => normBody(l.body)).filter(Boolean));
    tags.push({id: "body", label: "Кузов и привод", question: `Какой кузов и привод у ${name} из ${from}`, text: [
      `${name} в каталоге — ${listJoin(bodies)}, привод ${listJoin(drives)}. ${drives.includes("полный") ? "Полноприводные версии обычно дороже и встречаются реже." : "Если нужен полный привод, менеджер проверит, есть ли такая версия на рынке."}`,
    ], link: {href: catalog, label: `Смотреть ${name}`}});
  }

  const trims = unique(L.map((l) => l.trim).filter(Boolean));
  tags.push({id: "versions", label: `Версии ${m.model}`, question: `Какие версии ${name} из ${from} есть в каталоге`, text: [
    `${trims.length ? `Комплектации: ${listJoin(trims)}. ` : ""}${vols.length ? `Двигатели: ${listJoin(vols.map(volText))}${powers.length ? `, ${listJoin(powers.map((p) => `${p} л.с.`))}` : ""}.` : ""} Годы выпуска: ${listJoin(years.map(String))}.`,
    "Если нужна другая версия, оставьте заявку: подберём её на аукционах и площадках.",
  ], link: {href: catalog, label: "Сравнить версии"}});

  const rel = models.find((x) => x !== m && x.country === m.country && x.makeSlug === m.makeSlug && x.status !== "inactive")
    || models.find((x) => x !== m && x.country === m.country && x.status !== "inactive" && normBody(x.listings?.[0]?.body) === normBody(L[0].body))
    || models.find((x) => x !== m && x.country === m.country && x.status !== "inactive" && x.listings?.length);
  if (rel) {
    const rName = `${rel.make} ${rel.model}`;
    const rYears = unique(rel.listings.map((l) => l.year)).sort((a, b) => a - b);
    tags.push({id: "compare", label: `${m.model} или ${rel.model}`, question: `${name} или ${rName}: что выбрать из ${from}`, text: [
      `По каталогу Примкома: ${name} — ${priceRange(L.map((l) => l.price))}, ${years.length > 1 ? `${years[0]}–${years.at(-1)}` : years[0]} годы; ${rName} — ${priceRange(rel.listings.map((l) => l.price))}, ${rYears.length > 1 ? `${rYears[0]}–${rYears.at(-1)}` : rYears[0]} годы.`,
      "Сравнивайте не только цену, но и возраст на дату ввоза, объём двигателя и состояние: от них зависят пошлина и будущие расходы.",
    ], link: {href: modelUrl(rel), label: `Смотреть ${rName}`}});
  }

  const route = {
    japan: "Из Японии машину везут морем во Владивосток: после выкупа на аукционе её доставляют в порт отправки и грузят на судно.",
    korea: "Из Кореи машину везут морем из Пусана во Владивосток.",
    china: "Из Китая машину везут во Владивосток морем или по суше через погранпереходы.",
  }[m.country];
  tags.push({id: "delivery", label: `Доставка ${m.model}`, question: `Как привезти ${name} из ${from} в свой город`, text: [
    `${route} Во Владивостоке ${name} проходит склад временного хранения и таможню, получает СБКТС и ЭПТС.`,
    "Дальше машину отправляют в ваш город автовозом или в контейнере по железной дороге — эта часть считается отдельно.",
  ], link: {href: "/pages/dostavka.html", label: "Доставка по России"}});

  // Ручные теги для популярных моделей заменяют расчётные с тем же id или добавляются в конец.
  for (const extra of overrides[`${m.country}/${m.makeSlug}/${m.slug}`] || []) {
    const at = tags.findIndex((t) => t.id === extra.replaces);
    if (at >= 0) tags[at] = extra; else tags.push(extra);
  }
  return tags.slice(0, 10);
}

/* ---------- теги страницы марки ---------- */

export function brandTags(hub, {models = [], hubs = [], imp = importDate(), modelUrl = () => "", makeUrl = () => ""} = {}) {
  const own = models.filter((m) => m.country === hub.country && m.makeSlug === hub.makeSlug && m.status !== "inactive" && m.listings?.length);
  if (!own.length) return [];
  const make = hub.make, from = COUNTRY_NAME[hub.country];
  const L = own.flatMap((m) => m.listings.map((l) => ({...l, m})));
  const low = cheapest(L);
  const years = unique(L.map((l) => l.year)).sort((a, b) => a - b);
  const vols = unique(L.map((l) => l.engineVolumeL).filter((v) => v > 0)).sort((a, b) => a - b);
  const powers = L.map((l) => l.powerHp).filter(Boolean);
  const bodies = unique(L.map((l) => normBody(l.body)).filter(Boolean));
  const awd = own.filter((m) => m.listings.some((l) => /полный/i.test(l.drive || "")));
  const catalog = `${COUNTRY_PAGE[hub.country]}?brand=${encodeURIComponent(make)}`;
  const tags = [];

  tags.push({label: `Модели ${make}`, question: `Какие модели ${make} можно привезти из ${from}`, text: [`Сейчас в каталоге Примкома ${own.length} ${plural(own.length, "модель", "модели", "моделей")} ${make} из ${from}:`],
    list: own.map((m) => `${m.make} ${m.model} — ${priceRange(m.listings.map((l) => l.price))}`), after: ["Других моделей нет в каталоге, но их можно заказать под ваш запрос."], link: {href: catalog, label: `Все ${make} в каталоге`}});
  tags.push({label: `Цены ${make}`, question: `Сколько стоит ${make} из ${from} под ключ`, text: [`${make} из ${from} в каталоге стоят ${priceRange(L.map((l) => l.price))} под ключ на дату объявления. Это ${L.length} ${plural(L.length, "автомобиль", "автомобиля", "автомобилей")} ${years[0]}–${years.at(-1)} годов.`, "Цена под ключ включает покупку, доставку во Владивосток, таможню, утильсбор и оформление документов."], link: {href: "/pages/kalkulyator-stoimosti.html", label: "Рассчитать стоимость"}});
  tags.push({label: `Недорогой ${make}`, question: `Какой ${make} из ${from} самый доступный в каталоге`, text: [`Самый доступный сейчас — ${low.m.make} ${low.m.model} ${low.year} года${low.mileageKm ? ` с пробегом ${num(low.mileageKm)} км` : ""} за ${money(low.price)} под ключ.`, "Перед заказом сравните возраст на дату ввоза и состояние: недорогая машина старше 5 лет может потерять выгоду на пошлине."], link: {href: modelUrl(low.m), label: `Смотреть ${low.m.make} ${low.m.model}`}});
  tags.push({label: "Годы выпуска", question: `${make} каких годов выгодно везти из ${from}`, text: [`В каталоге ${make} ${years.length > 1 ? `${years[0]}–${years.at(-1)}` : years[0]} годов. Для ввоза в ${imp.labelIn}:`], list: years.map((y) => ageNote(y, imp)), link: {href: "/pages/rastamozhka-i-poshliny.html", label: "Пошлины по возрасту"}});
  tags.push({label: `Пошлина ${make}`, question: `Какая пошлина на ${make} из ${from}`, text: vols.length ? [`Для машин старше 3 лет пошлина зависит от объёма. Ориентир для объёмов ${make} в каталоге:`] : ["Объём двигателя в объявлениях не указан, считаем по документам."], list: dutyLines(vols), after: ["Сумма в рублях — по курсу евро ЦБ на день оформления."], link: {href: "/pages/kalkulyator-stoimosti.html", label: "Калькулятор растаможки"}});
  tags.push({label: `Утильсбор ${make}`, question: `Будет ли льготный утильсбор на ${make} из ${from}`, text: [powers.length ? `Мощность указана у ${powers.length} из ${L.length} ${make}: ${powers.filter((p) => p <= 160).length} из них не больше 160 л.с. и подходят под льготу.` : `Мощность в объявлениях ${make} не указана, проверим по документам.`, "Льготный сбор для ввоза себе — 5 200 ₽ для машины старше 3 лет и 3 400 ₽ для более новой, если мощность до 160 л.с. и объём до 3 л. Мощнее — сбор по повышенной шкале."], link: {href: "/cars/podborki/do-160-ls/", label: "Подборка до 160 л.с."}});
  if (hub.country === "japan") {
    const big = vols.filter((v) => v > 1.9);
    tags.push({label: "Запрет 1,9 л", question: `Какие ${make} можно вывезти из Японии в Россию`, text: ["Япония с 9 августа 2023 года не выпускает в Россию машины с двигателем больше 1 900 см³, гибриды и электромобили.", big.length ? `В каталоге есть ${make} ${listJoin(big.map(volText))}; как поставляется такая машина, менеджер расскажет по конкретному автомобилю.` : `Все ${make} в каталоге — до 1,9 л, ограничение их не касается.`], link: {href: COUNTRY_PAGE.japan, label: "Авто из Японии"}});
  } else if (hub.country === "korea") {
    tags.push({label: "Ограничение 2 л", question: `Можно ли купить ${make} в Корее с мотором больше 2 л`, text: ["Корея с начала 2024 года выпускает в Россию машины с двигателем больше 2 литров только по специальному разрешению.", vols.some((v) => v > 2) ? `В каталоге есть такие ${make} (${listJoin(vols.filter((v) => v > 2).map(volText))}); способ поставки объясним до договора.` : `${make} в каталоге — не больше 2 л, ограничение их не касается.`], link: {href: COUNTRY_PAGE.korea, label: "Авто из Кореи"}});
  } else {
    tags.push({label: "Гарантия и сервис", question: `Как обслуживать ${make} из Китая в России`, text: [`${make} из Китая сделан для внутреннего рынка Китая. До покупки проверяем язык мультимедиа, комплектацию и доступность запчастей и сервиса в вашем городе.`, "Заводская гарантия Китая в России обычно не действует, поэтому состояние проверяем до выкупа."], link: {href: COUNTRY_PAGE.china, label: "Авто из Китая"}});
  }
  tags.push({label: `Кузова ${make}`, question: `Какие кузова ${make} из ${from} есть в каталоге`, text: [`${make} из ${from} в каталоге: ${listJoin(bodies)}. ${awd.length ? `Полный привод есть у ${listJoin(awd.map((m) => m.model))}.` : "Полноприводных версий сейчас нет, их можно заказать отдельно."}`], link: {href: catalog, label: "Фильтр по кузову"}});
  const other = hubs.find((h) => h.makeSlug === hub.makeSlug && h.country !== hub.country && h.status !== "inactive");
  const otherModels = other ? models.filter((m) => m.country === other.country && m.makeSlug === other.makeSlug && m.listings?.length) : [];
  if (otherModels.length) {
    const oL = otherModels.flatMap((m) => m.listings);
    tags.push({label: `${make}: ${hub.country === "japan" ? "Япония" : hub.country === "korea" ? "Корея" : "Китай"} или ${other.country === "japan" ? "Япония" : other.country === "korea" ? "Корея" : "Китай"}`, question: `Откуда выгоднее везти ${make}: из ${from} или из ${COUNTRY_NAME[other.country]}`, text: [`По каталогу Примкома ${make} из ${from} — ${priceRange(L.map((l) => l.price))}, из ${COUNTRY_NAME[other.country]} — ${priceRange(oL.map((l) => l.price))}.`, "Разница не только в цене: рынки отличаются комплектациями, возрастом машин и ограничениями на вывоз. Сравним варианты под ваш бюджет."], link: {href: makeUrl(other), label: `${make} из ${COUNTRY_NAME[other.country]}`}});
  } else {
    tags.push({label: `Доставка ${make}`, question: `Как доставить ${make} из ${from} в ваш город`, text: [`${make} сначала приходит во Владивосток: здесь склад временного хранения, таможня, СБКТС и ЭПТС.`, "Дальше машина едет автовозом или в контейнере по железной дороге — сумма зависит от города и считается отдельно."], link: {href: "/pages/dostavka.html", label: "Доставка по России"}});
  }
  tags.push({label: `Заказать ${make}`, question: `Как заказать ${make} из ${from}, которого нет в каталоге`, text: [`Напишите модель, год, бюджет и важные опции. Менеджер найдёт ${make} на ${hub.country === "japan" ? "японских аукционах" : "площадках и у дилеров"}, проверит историю и пришлёт расчёт под ключ до вашего города.`, "Договор заключается после согласования конкретной машины."], link: {href: COUNTRY_PAGE[hub.country], label: "Оставить заявку"}});
  return tags.slice(0, 10);
}
