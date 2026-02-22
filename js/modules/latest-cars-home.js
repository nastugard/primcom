function qs(sel, root = document) {
  return root.querySelector(sel);
}

function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

function clearEl(el) {
  if (!el) return;
  while (el.firstChild) el.removeChild(el.firstChild);
}

function formatDateTimeRu(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (!Number.isFinite(d.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function formatInt(value) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.trunc(n));
}

function formatMeta(item, currencySign = "¥") {
  const parts = [];
  if (typeof item?.year === "number") parts.push(String(item.year));
  const mileage = formatInt(item?.mileage_km);
  if (mileage) parts.push(`${mileage} км`);
  const price = formatInt(item?.price_cny);
  if (price) parts.push(`${currencySign} ${price}`);
  return parts.join(" • ");
}

const SECTION_PRESETS = {
  "latest-japan-home": {
    apiPath: "/api/auto-iz-yaponii",
    pageUrl: "./pages/auto-iz-yaponii.html",
    marketLabel: "японии",
    currency: "rub",
    source: "japan_manual",
    expectedSource: "japan_manual",
  },
  "latest-china-home": {
    apiPath: "/api/auto-iz-kitaya",
    pageUrl: "./pages/auto-iz-kitaya.html",
    marketLabel: "китая",
    currency: "cny",
    source: "guazi",
    expectedSource: "guazi",
  },
  "latest-korea-home": {
    apiPath: "/api/auto-iz-korei",
    pageUrl: "./pages/auto-iz-korei.html",
    marketLabel: "кореи",
    currency: "rub",
    source: "korea_manual",
    expectedSource: "korea_manual",
  },
};

function getAttr(root, name, fallback = "") {
  if (!root || !name) return fallback;
  const raw = root.getAttribute(name);
  const value = raw === null ? "" : String(raw).trim();
  return value || fallback;
}

function resolveSectionConfig(root) {
  const preset = root ? SECTION_PRESETS[root.id] || null : null;
  const apiPath = getAttr(root, "data-api-path", preset?.apiPath || "");
  const pageUrl = getAttr(root, "data-page-url", preset?.pageUrl || "./pages/auto-iz-kitaya.html");
  const marketLabel = getAttr(root, "data-market-label", preset?.marketLabel || "китая");
  const source = getAttr(root, "data-source", preset?.source || "");
  const expectedSource = getAttr(root, "data-expected-source", preset?.expectedSource || source)
    .toLowerCase();
  const currencyCode = getAttr(root, "data-currency", preset?.currency || "cny").toLowerCase();
  const currencySign = currencyCode === "rub" ? "₽" : "¥";

  return {
    apiPath,
    pageUrl,
    marketLabel,
    source,
    expectedSource,
    currencySign,
  };
}

function getApiCandidates(apiPath) {
  const path = String(apiPath || "/api/auto-iz-kitaya").trim() || "/api/auto-iz-kitaya";
  if (window.location.protocol === "file:") {
    return [
      `http://127.0.0.1:8010${path}`,
      path,
      `https://api.primcom.ru${path}`,
    ];
  }
  const host = String(window.location.hostname || "");
  if (host === "localhost" || host === "127.0.0.1") {
    return [
      `http://127.0.0.1:8010${path}`,
      path,
      `https://api.primcom.ru${path}`,
    ];
  }
  return [path, `https://api.primcom.ru${path}`];
}

function toAbsoluteUrl(apiBase, maybePath) {
  if (!maybePath) return null;
  const s = String(maybePath);
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/")) return `${apiBase}${s}`;
  return s;
}

function createCard(item, apiBase, pageUrl, marketLabel, currencySign) {
  const card = document.createElement("article");
  card.className = "china-car-card";

  const media = document.createElement("a");
  media.className = "china-car-card__media";
  media.href = pageUrl;
  media.setAttribute("aria-label", `Открыть раздел авто из ${marketLabel}`);

  const imgUrl = toAbsoluteUrl(apiBase, item?.cover_image_url);
  if (imgUrl) {
    const img = document.createElement("img");
    img.className = "china-car-card__img";
    img.loading = "lazy";
    img.decoding = "async";
    img.src = imgUrl;
    img.alt = `${item?.brand || ""} ${item?.model || ""}`.trim() || "Автомобиль";
    img.addEventListener("error", () => {
      clearEl(media);
      const ph = document.createElement("div");
      ph.className = "china-car-card__placeholder";
      ph.textContent = "Фото";
      media.appendChild(ph);
    });
    media.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "china-car-card__placeholder";
    ph.textContent = "Фото";
    media.appendChild(ph);
  }

  const body = document.createElement("div");
  body.className = "china-car-card__body";

  const title = document.createElement("h3");
  title.className = "china-car-card__title";
  title.textContent = `${item?.brand || ""} ${item?.model || ""}`.trim() || "Автомобиль";

  const meta = document.createElement("p");
  meta.className = "china-car-card__meta";
  meta.textContent = formatMeta(item, currencySign);

  const actions = document.createElement("div");
  actions.className = "china-car-card__actions";

  const details = document.createElement("a");
  details.className = "btn btn--small china-car-card__btn-detail";
  details.href = pageUrl;
  details.textContent = "Подробнее";

  const srcLink = document.createElement("a");
  srcLink.className = "btn btn--small btn--ghost";
  srcLink.textContent = "Источник";
  srcLink.href = item?.original_url || "#";
  srcLink.target = "_blank";
  srcLink.rel = "noopener";

  actions.appendChild(details);
  actions.appendChild(srcLink);
  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(actions);

  card.appendChild(media);
  card.appendChild(body);
  return card;
}

async function fetchLatest({ apiPath, source }) {
  const candidates = getApiCandidates(apiPath);
  let lastErr = null;
  for (const base of candidates) {
    try {
      const u = new URL(base.replace(/\/+$/, ""), window.location.href);
      if (source) u.searchParams.set("source", source);
      u.searchParams.set("limit", "4");
      u.searchParams.set("offset", "0");
      const res = await fetch(u.toString(), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { data, apiBase: `${u.protocol}//${u.host}` };
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("api unavailable");
}

export function initLatestCarsHome() {
  const roots = qsa("[data-latest-home]");
  if (!roots.length) return;

  roots.forEach((root) => {
    const statusEl = qs("[data-latest-home-status]", root);
    const updatedEl = qs("[data-latest-home-updated]", root);
    const listEl = qs("[data-latest-home-list]", root);
    const { apiPath, pageUrl, marketLabel, source, expectedSource, currencySign } = resolveSectionConfig(root);

    if (!listEl) {
      if (statusEl) statusEl.textContent = "Секция недоступна (не найден контейнер карточек).";
      return;
    }

    if (!apiPath) {
      if (statusEl) statusEl.textContent = "Секция недоступна (не задан API путь).";
      return;
    }

    const render = async () => {
      try {
        const { data, apiBase } = await fetchLatest({ apiPath, source });
        clearEl(listEl);
        const rawItems = Array.isArray(data?.items) ? data.items : [];
        const items = expectedSource
          ? rawItems.filter(
              (item) => String(item?.source || "").trim().toLowerCase() === expectedSource
            )
          : rawItems;

        if (expectedSource && rawItems.length && items.length !== rawItems.length) {
          console.warn("[latest-home] source mismatch filtered", {
            sectionId: root.id || "",
            expectedSource,
            received: rawItems.length,
            kept: items.length,
          });
        }

        if (!items.length) {
          if (statusEl) {
            statusEl.textContent =
              expectedSource && rawItems.length
                ? "Нет подходящих объявлений для этой секции."
                : "Пока нет объявлений.";
          }
          if (updatedEl) updatedEl.textContent = formatDateTimeRu(data?.last_scraped_at) || "—";
          return;
        }
        items.forEach((item) =>
          listEl.appendChild(createCard(item, apiBase, pageUrl, marketLabel, currencySign))
        );
        if (statusEl) statusEl.textContent = "";
        if (updatedEl) updatedEl.textContent = formatDateTimeRu(data?.last_scraped_at) || "—";
      } catch (err) {
        if (statusEl) statusEl.textContent = "Не удалось загрузить свежую подборку.";
        console.error("[latest-home] load failed", { apiPath, err });
      }
    };

    render();
    window.setInterval(render, 90_000);
  });
}
