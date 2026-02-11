function qs(sel, root = document) {
  return root.querySelector(sel);
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

function formatMeta(item) {
  const parts = [];
  if (typeof item?.year === "number") parts.push(String(item.year));
  const mileage = formatInt(item?.mileage_km);
  if (mileage) parts.push(`${mileage} км`);
  const price = formatInt(item?.price_cny);
  if (price) parts.push(`¥ ${price}`);
  return parts.join(" • ");
}

function getApiCandidates() {
  if (window.location.protocol === "file:") {
    return [
      "http://127.0.0.1:8010/api/auto-iz-kitaya",
      "/api/auto-iz-kitaya",
      "https://api.primcom.ru/api/auto-iz-kitaya",
    ];
  }
  const host = String(window.location.hostname || "");
  if (host === "localhost" || host === "127.0.0.1") {
    return [
      "http://127.0.0.1:8010/api/auto-iz-kitaya",
      "/api/auto-iz-kitaya",
      "https://api.primcom.ru/api/auto-iz-kitaya",
    ];
  }
  return ["/api/auto-iz-kitaya", "https://api.primcom.ru/api/auto-iz-kitaya"];
}

function toAbsoluteUrl(apiBase, maybePath) {
  if (!maybePath) return null;
  const s = String(maybePath);
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/")) return `${apiBase}${s}`;
  return s;
}

function createCard(item, apiBase) {
  const card = document.createElement("article");
  card.className = "china-car-card";

  const media = document.createElement("a");
  media.className = "china-car-card__media";
  media.href = "./pages/auto-iz-kitaya.html";
  media.setAttribute("aria-label", "Открыть раздел авто из китая");

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
  meta.textContent = formatMeta(item);

  const actions = document.createElement("div");
  actions.className = "china-car-card__actions";

  const details = document.createElement("a");
  details.className = "btn btn--small china-car-card__btn-detail";
  details.href = "./pages/auto-iz-kitaya.html";
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

async function fetchLatest() {
  const candidates = getApiCandidates();
  let lastErr = null;
  for (const base of candidates) {
    try {
      const u = new URL(base.replace(/\/+$/, ""), window.location.href);
      u.searchParams.set("source", "guazi");
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
  const root = qs("[data-latest-home]");
  if (!root) return;

  const statusEl = qs("[data-latest-home-status]", root);
  const updatedEl = qs("[data-latest-home-updated]", root);
  const listEl = qs("[data-latest-home-list]", root);

  const render = async () => {
    try {
      const { data, apiBase } = await fetchLatest();
      clearEl(listEl);
      const items = Array.isArray(data?.items) ? data.items : [];
      if (!items.length) {
        if (statusEl) statusEl.textContent = "Пока нет объявлений.";
        if (updatedEl) updatedEl.textContent = "—";
        return;
      }
      items.forEach((item) => listEl.appendChild(createCard(item, apiBase)));
      if (statusEl) statusEl.textContent = "";
      if (updatedEl) updatedEl.textContent = formatDateTimeRu(data?.last_scraped_at) || "—";
    } catch (err) {
      if (statusEl) statusEl.textContent = "Не удалось загрузить свежую подборку.";
      console.error("[latest-home] load failed", err);
    }
  };

  render();
  window.setInterval(render, 90_000);
}
