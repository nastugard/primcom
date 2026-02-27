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

function formatPrice(value, currencySign = "¥") {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "";
  return `${currencySign} ${new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
  }).format(Math.round(n))}`;
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function getTitle(item) {
  const parts = [];
  if (item?.brand) parts.push(String(item.brand));
  if (item?.model) parts.push(String(item.model));
  const t = parts.join(" ").trim();
  return t || "Автомобиль";
}

function uniqUrls(list) {
  const out = [];
  const seen = new Set();
  (Array.isArray(list) ? list : []).forEach((raw) => {
    const u = String(raw || "").trim();
    if (!u || seen.has(u)) return;
    seen.add(u);
    out.push(u);
  });
  return out;
}

function pickFirstText(...values) {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const text = String(value).replace(/\s+/g, " ").trim();
    if (text) return text;
  }
  return "";
}

function buildFallbackDescription(item) {
  const title = getTitle(item);
  const parts = [];
  if (item?.year) parts.push(`${item.year} г.`);
  const mileage = formatInt(item?.mileage_km);
  if (mileage) parts.push(`пробег ${mileage} км`);
  if (item?.engine_type) parts.push(`двигатель: ${item.engine_type}`);
  if (item?.drive_type) parts.push(`привод: ${item.drive_type}`);
  if (item?.transmission) parts.push(`КПП: ${item.transmission}`);
  if (item?.body_type) parts.push(`кузов: ${item.body_type}`);
  if (item?.trim) parts.push(`комплектация: ${item.trim}`);
  if (!parts.length) return `${title}. Подробности доступны в разделе.`;
  return `${title}: ${parts.join(", ")}.`;
}

function resolveDescription(primary, fallback = null) {
  const fromApi = pickFirstText(
    primary?.description,
    primary?.description_original,
    primary?.seller_comments_original,
    primary?.comment,
    primary?.comments,
    primary?.note,
    primary?.notes,
    primary?.equipment_original
  );
  return fromApi || buildFallbackDescription(primary || fallback || {});
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

function buildUrl(base, suffix = "", params = null) {
  const baseClean = String(base || "").replace(/\/+$/, "");
  const suffixClean = suffix ? `/${String(suffix).replace(/^\/+/, "")}` : "";
  const u = new URL(baseClean + suffixClean, window.location.href);
  if (params && typeof params === "object") {
    Object.entries(params).forEach(([k, v]) => {
      if (v === null || v === undefined || v === "") return;
      u.searchParams.set(k, String(v));
    });
  }
  return u;
}

function toAbsoluteUrl(apiBase, maybePath) {
  if (!maybePath) return null;
  const s = String(maybePath);
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/")) return `${apiBase}${s}`;
  return s;
}

function normalizeImageUrl(apiBase, imageItem) {
  if (!imageItem) return null;
  if (typeof imageItem === "string") {
    return toAbsoluteUrl(apiBase, imageItem);
  }
  if (typeof imageItem === "object") {
    return toAbsoluteUrl(
      apiBase,
      imageItem.url || imageItem.local_path || imageItem.src || imageItem.path || null
    );
  }
  return null;
}

function getDetailApiCandidates(apiPath = "") {
  const paths = [
    String(apiPath || "").trim(),
    "/api/auto-iz-kitaya",
    "/api/auto-iz-yaponii",
    "/api/auto-iz-korei",
  ].filter(Boolean);

  const seen = new Set();
  const out = [];
  paths.forEach((path) => {
    getApiCandidates(path).forEach((candidate) => {
      const clean = String(candidate || "").replace(/\/+$/, "");
      if (!clean || seen.has(clean)) return;
      seen.add(clean);
      out.push(clean);
    });
  });
  return out;
}

async function fetchJsonWithTimeout(url, timeoutMs = 12_000) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = window.setTimeout(() => controller && controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: controller ? controller.signal : undefined,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    window.clearTimeout(timer);
  }
}

const DETAIL_STORAGE_KEY = "latest-home-detail-cache:v1";
const DETAIL_STORAGE_TTL_MS = 12 * 60 * 60 * 1000;
const DETAIL_STORAGE_MAX_ITEMS = 120;
const detailCache = new Map();

function getDetailCacheKey(item) {
  const source = String(item?.source || "unknown").trim().toLowerCase();
  const id = String(item?.id || "").trim();
  return `${source}:${id}`;
}

function loadPersistedDetails() {
  if (typeof localStorage === "undefined") return {};
  try {
    const raw = localStorage.getItem(DETAIL_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_) {
    return {};
  }
}

function savePersistedDetails(items) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(DETAIL_STORAGE_KEY, JSON.stringify(items || {}));
  } catch (_) {
    // ignore storage quota/privacy errors
  }
}

function normalizeCachedPayload(payload) {
  if (!payload || typeof payload !== "object") return null;
  const detail = payload.detail;
  const apiBase = String(payload.apiBase || "").trim();
  if (!detail || typeof detail !== "object") return null;
  if (!apiBase) return null;
  return { detail, apiBase };
}

function getPersistedDetail(cacheKey) {
  const now = Date.now();
  const cache = loadPersistedDetails();
  let changed = false;

  Object.entries(cache).forEach(([key, entry]) => {
    const cachedAt = Number(entry?.cachedAt || 0);
    if (!cachedAt || now - cachedAt > DETAIL_STORAGE_TTL_MS) {
      delete cache[key];
      changed = true;
    }
  });

  const entry = cache[cacheKey];
  const payload = normalizeCachedPayload(entry?.payload);
  if (!payload && entry) {
    delete cache[cacheKey];
    changed = true;
  }

  if (changed) savePersistedDetails(cache);
  return payload;
}

function setPersistedDetail(cacheKey, payload) {
  const normalized = normalizeCachedPayload(payload);
  if (!normalized) return;

  const now = Date.now();
  const cache = loadPersistedDetails();
  cache[cacheKey] = { cachedAt: now, payload: normalized };

  const freshEntries = Object.entries(cache)
    .filter(([, entry]) => {
      const cachedAt = Number(entry?.cachedAt || 0);
      if (!cachedAt || now - cachedAt > DETAIL_STORAGE_TTL_MS) return false;
      return !!normalizeCachedPayload(entry?.payload);
    })
    .sort((a, b) => Number(b[1]?.cachedAt || 0) - Number(a[1]?.cachedAt || 0))
    .slice(0, DETAIL_STORAGE_MAX_ITEMS);

  const next = {};
  freshEntries.forEach(([key, entry]) => {
    next[key] = entry;
  });
  savePersistedDetails(next);
}

async function fetchCardDetail(item, apiPath = "") {
  const id = String(item?.id || "").trim();
  const cacheKey = getDetailCacheKey(item);
  if (!id) throw new Error("missing listing id");
  if (detailCache.has(cacheKey)) return detailCache.get(cacheKey);

  const persisted = getPersistedDetail(cacheKey);
  if (persisted) {
    const fromStorage = Promise.resolve(persisted);
    detailCache.set(cacheKey, fromStorage);
    return fromStorage;
  }

  const promise = (async () => {
    const candidates = getDetailApiCandidates(apiPath);
    let lastErr = null;
    for (const base of candidates) {
      try {
        const u = buildUrl(base, id);
        const detail = await fetchJsonWithTimeout(u.toString(), 12_000);
        const payload = {
          detail,
          apiBase: `${u.protocol}//${u.host}`,
        };
        setPersistedDetail(cacheKey, payload);
        return payload;
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr || new Error("detail api unavailable");
  })();

  detailCache.set(cacheKey, promise);
  try {
    return await promise;
  } catch (err) {
    detailCache.delete(cacheKey);
    throw err;
  }
}

function getDetailImages(detail, apiBase, coverUrl = "") {
  const rawImages = Array.isArray(detail?.images) ? detail.images : [];
  const normalized = rawImages
    .map((img) => normalizeImageUrl(apiBase, img))
    .filter(Boolean);
  if (coverUrl) normalized.unshift(coverUrl);
  return uniqUrls(normalized);
}

function renderSpecRows(specsEl, item, currencySign) {
  if (!specsEl) return;
  clearEl(specsEl);
  const rows = [
    ["Марка", item?.brand],
    ["Модель", item?.model],
    ["Год", item?.year],
    ["Пробег", item?.mileage_km ? `${formatInt(item.mileage_km)} км` : ""],
    ["Цена", formatPrice(item?.price_cny, currencySign)],
    ["Привод", item?.drive_type],
    ["Топливо", item?.engine_type],
    ["Объем", item?.engine_volume_l ? `${item.engine_volume_l} л` : ""],
    ["Мощность", item?.power_hp ? `${item.power_hp} л.с.` : ""],
    ["Кузов", item?.body_type],
    ["Комплектация", item?.trim],
    ["Коробка", item?.transmission],
    ["Оценка аукциона", item?.auction_grade],
  ];

  rows.forEach(([label, value]) => {
    const text = value === null || value === undefined ? "" : String(value).trim();
    if (!text) return;
    const row = document.createElement("div");
    row.className = "manual-car__spec-row";

    const key = document.createElement("span");
    key.className = "manual-car__spec-key";
    key.textContent = String(label);

    const val = document.createElement("span");
    val.className = "manual-car__spec-val";
    val.textContent = text;

    row.appendChild(key);
    row.appendChild(val);
    specsEl.appendChild(row);
  });
}

function makePhotoDots(total) {
  const n = Math.max(1, Math.min(8, Number(total || 1)));
  const dots = [];
  for (let i = 0; i < n; i += 1) {
    const dot = document.createElement("span");
    dot.className = "latest-home-card__photo-dot";
    dots.push(dot);
  }
  return dots;
}

function createLatestModalController() {
  const modal = qs("[data-latest-card-modal]");
  if (!modal) {
    return {
      open: async () => {},
    };
  }

  const closers = qsa("[data-latest-card-close]", modal);
  const titleEl = qs("[data-latest-card-title]", modal);
  const metaEl = qs("[data-latest-card-meta]", modal);
  const updatedEl = qs("[data-latest-card-updated]", modal);
  const specsEl = qs("[data-latest-card-specs]", modal);
  const descriptionEl = qs("[data-latest-card-description]", modal);
  const statusEl = qs("[data-latest-card-status]", modal);
  const mainImgEl = qs("[data-latest-card-main-img]", modal);
  const thumbsEl = qs("[data-latest-card-thumbs]", modal);
  const sectionLinkEl = qs("[data-latest-card-section-link]", modal);

  let images = [];
  let imageIndex = 0;
  let openToken = 0;

  const anyOpenModals = () => qsa(".modal:not([hidden])").length > 0;

  const show = () => {
    if (!modal.hidden) return;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  };

  const hide = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (!anyOpenModals()) {
      document.body.style.overflow = "";
    }
  };

  const setStatus = (text) => {
    if (!statusEl) return;
    statusEl.textContent = text || "";
  };

  const setDescription = (text) => {
    if (!descriptionEl) return;
    const value = String(text || "").trim();
    descriptionEl.textContent = value;
    descriptionEl.hidden = !value;
  };

  const setMainImage = (src, alt) => {
    if (!mainImgEl) return;
    if (!src) {
      mainImgEl.hidden = true;
      mainImgEl.removeAttribute("src");
      mainImgEl.alt = "";
      return;
    }
    mainImgEl.hidden = false;
    mainImgEl.src = src;
    mainImgEl.alt = alt || "Фото автомобиля";
  };

  const setActiveThumb = () => {
    const thumbs = qsa("[data-latest-card-thumb]", thumbsEl || modal);
    thumbs.forEach((thumb, idx) => {
      thumb.classList.toggle("is-active", idx === imageIndex);
    });
  };

  const renderThumbs = (title) => {
    if (!thumbsEl) return;
    clearEl(thumbsEl);
    if (images.length <= 1) {
      thumbsEl.hidden = true;
      return;
    }
    thumbsEl.hidden = false;
    images.forEach((src, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "manual-car__thumb";
      btn.setAttribute("data-latest-card-thumb", String(idx));
      if (idx === imageIndex) btn.classList.add("is-active");

      const img = document.createElement("img");
      img.loading = "lazy";
      img.decoding = "async";
      img.src = src;
      img.alt = title || "Фото автомобиля";

      btn.appendChild(img);
      btn.addEventListener("click", () => {
        imageIndex = idx;
        setMainImage(images[imageIndex], title);
        setActiveThumb();
      });
      thumbsEl.appendChild(btn);
    });
  };

  closers.forEach((el) => el.addEventListener("click", hide));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.hidden) hide();
  });

  const open = async ({ item, pageUrl, currencySign, coverUrl, apiPath }) => {
    const token = ++openToken;
    const baseTitle = getTitle(item);
    if (titleEl) titleEl.textContent = baseTitle;
    if (metaEl) metaEl.textContent = formatMeta(item, currencySign);
    if (updatedEl) updatedEl.textContent = formatDateTimeRu(item?.scraped_at) || "—";
    if (sectionLinkEl) sectionLinkEl.href = pageUrl;
    setDescription(resolveDescription(item, item));
    renderSpecRows(specsEl, item, currencySign);

    images = coverUrl ? [coverUrl] : [];
    imageIndex = 0;
    setMainImage(images[0] || "", baseTitle);
    renderThumbs(baseTitle);
    setStatus("Загружаем описание и фото...");

    show();

    try {
      const payload = await fetchCardDetail(item, apiPath);
      if (modal.hidden || token !== openToken) return;

      const detail = payload?.detail || null;
      const detailApiBase = payload?.apiBase || window.location.origin;
      const detailTitle = getTitle(detail || item);

      if (titleEl) titleEl.textContent = detailTitle;
      if (metaEl) metaEl.textContent = formatMeta(detail || item, currencySign);
      if (updatedEl) updatedEl.textContent = formatDateTimeRu((detail || item)?.scraped_at) || "—";
      setDescription(resolveDescription(detail || item, item));
      renderSpecRows(specsEl, detail || item, currencySign);

      const nextImages = getDetailImages(detail, detailApiBase, coverUrl);
      images = nextImages;
      imageIndex = 0;
      setMainImage(images[0] || "", detailTitle);
      renderThumbs(detailTitle);

      if (!nextImages.length) {
        setStatus("Дополнительные фото не найдены.");
      } else {
        setStatus("");
      }
    } catch (err) {
      if (modal.hidden || token !== openToken) return;
      setStatus("Не удалось загрузить карточку автомобиля.");
      console.error("[latest-home] detail load failed", err);
    }
  };

  return { open };
}

function createCard({
  item,
  apiBase,
  apiPath,
  pageUrl,
  marketLabel,
  currencySign,
  onOpenDetail,
}) {
  const card = document.createElement("article");
  card.className = "china-car-card latest-home-card";

  const media = document.createElement("button");
  media.type = "button";
  media.className = "china-car-card__media latest-home-card__media";
  media.setAttribute("aria-label", `Открыть карточку авто из ${marketLabel}`);

  const coverUrl = toAbsoluteUrl(apiBase, item?.cover_image_url);
  let imageEl = null;
  let placeholderEl = null;
  let images = coverUrl ? [coverUrl] : [];
  let activeImageIndex = 0;
  const hasFinePointer = !!(window.matchMedia && window.matchMedia("(pointer: fine)").matches);
  const expectedImageCount = Math.max(1, Number(item?.images_count || 0));
  const canUseHoverGallery = hasFinePointer && expectedImageCount > 1;
  let galleryLoaded = false;
  let galleryLoading = false;

  const ensureImageEl = (src) => {
    if (imageEl) {
      imageEl.src = src;
      return;
    }
    if (placeholderEl) {
      placeholderEl.remove();
      placeholderEl = null;
    }
    const img = document.createElement("img");
    img.className = "china-car-card__img";
    img.loading = "lazy";
    img.decoding = "async";
    img.src = src;
    img.alt = getTitle(item);
    img.addEventListener("error", () => {
      if (images.length > 1) return;
      if (imageEl) {
        imageEl.remove();
        imageEl = null;
      }
      const ph = document.createElement("div");
      ph.className = "china-car-card__placeholder";
      ph.textContent = "Фото";
      media.appendChild(ph);
      placeholderEl = ph;
    });
    media.appendChild(img);
    imageEl = img;
  };

  if (coverUrl) {
    ensureImageEl(coverUrl);
  } else {
    const ph = document.createElement("div");
    ph.className = "china-car-card__placeholder";
    ph.textContent = "Фото";
    media.appendChild(ph);
    placeholderEl = ph;
  }

  const countBadge = document.createElement("span");
  countBadge.className = "latest-home-card__photo-count";

  const dotsWrap = document.createElement("div");
  dotsWrap.className = "latest-home-card__photo-dots";

  const loadingHint = document.createElement("span");
  loadingHint.className = "latest-home-card__loading";
  loadingHint.textContent = "Фото загружаются";
  loadingHint.setAttribute("aria-hidden", "true");

  const dots = [];
  const refreshCount = () => {
    const fallbackCount = Number(item?.images_count || 0);
    const total = Math.max(1, fallbackCount, images.length);
    countBadge.textContent = `${total} фото`;

    const nextDots = makePhotoDots(total);
    clearEl(dotsWrap);
    dots.length = 0;
    nextDots.forEach((dot) => {
      dots.push(dot);
      dotsWrap.appendChild(dot);
    });
  };

  const refreshActiveDot = () => {
    const total = Math.max(1, images.length);
    const maxDotIndex = Math.max(0, dots.length - 1);
    const dotIndex = maxDotIndex
      ? Math.round((clamp(activeImageIndex, 0, total - 1) / Math.max(1, total - 1)) * maxDotIndex)
      : 0;
    dots.forEach((dot, idx) => {
      dot.classList.toggle("is-active", idx === dotIndex);
    });
  };

  const setImageByIndex = (idx) => {
    if (!images.length) return;
    activeImageIndex = clamp(idx, 0, images.length - 1);
    ensureImageEl(images[activeImageIndex]);
    refreshActiveDot();
  };

  const syncGalleryHint = () => {
    const ready = images.length > 1;
    loadingHint.hidden = !canUseHoverGallery || ready;
    loadingHint.classList.toggle("is-loading", !!galleryLoading);
  };

  const ensureGalleryLoaded = async () => {
    if (!media.isConnected) return;
    const fallbackCount = Number(item?.images_count || 0);
    if (galleryLoaded || galleryLoading || fallbackCount <= 1) return;
    galleryLoading = true;
    syncGalleryHint();
    try {
      const payload = await fetchCardDetail(item, apiPath);
      const detail = payload?.detail || null;
      const detailApiBase = payload?.apiBase || apiBase;
      const nextImages = getDetailImages(detail, detailApiBase, coverUrl);
      if (nextImages.length) {
        images = nextImages;
        activeImageIndex = clamp(activeImageIndex, 0, images.length - 1);
        refreshCount();
        setImageByIndex(activeImageIndex);
      }
      galleryLoaded = true;
    } catch (err) {
      console.warn("[latest-home] gallery preload failed", err);
    } finally {
      galleryLoading = false;
      syncGalleryHint();
    }
  };

  refreshCount();
  refreshActiveDot();
  media.appendChild(countBadge);
  media.appendChild(dotsWrap);
  media.appendChild(loadingHint);
  syncGalleryHint();

  if (canUseHoverGallery) {
    media.addEventListener("pointerenter", () => {
      ensureGalleryLoaded();
    });

    media.addEventListener("mousemove", (e) => {
      if (images.length <= 1) {
        ensureGalleryLoaded();
        return;
      }
      const rect = media.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = rect.width > 0 ? clamp(x / rect.width, 0, 1) : 0;
      const index = clamp(Math.floor(ratio * images.length), 0, images.length - 1);
      if (index !== activeImageIndex) {
        setImageByIndex(index);
      }
    });

    media.addEventListener("mouseleave", () => {
      setImageByIndex(0);
    });

    const preloadDelayMs = 220 + Math.floor(Math.random() * 460);
    window.setTimeout(() => {
      if (!media.isConnected) return;
      ensureGalleryLoaded();
    }, preloadDelayMs);
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

  const details = document.createElement("button");
  details.type = "button";
  details.className = "btn btn--small china-car-card__btn-detail";
  details.textContent = "Подробнее";
  details.addEventListener("click", () => {
    onOpenDetail({
      item,
      apiPath,
      pageUrl,
      currencySign,
      coverUrl,
    });
  });

  media.addEventListener("click", () => {
    onOpenDetail({
      item,
      apiPath,
      pageUrl,
      currencySign,
      coverUrl,
    });
  });

  actions.appendChild(details);
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
  const modalController = createLatestModalController();

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
        items.forEach((item) => {
          const card = createCard({
            item,
            apiBase,
            apiPath,
            pageUrl,
            marketLabel,
            currencySign,
            onOpenDetail: (payload) => modalController.open(payload),
          });
          listEl.appendChild(card);
        });
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
