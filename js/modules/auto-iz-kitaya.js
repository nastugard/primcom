function qs(sel, root = document) {
  return root.querySelector(sel);
}

function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function formatInt(value) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.trunc(n));
}

function formatMileageKm(value) {
  const s = formatInt(value);
  if (!s) return "";
  return `${s} км`;
}

function isManualChinaItem(item) {
  return String(item?.source_listing_id || "").startsWith("mgr-china-");
}

function getCurrencySign(item) {
  return isManualChinaItem(item) ? "₽" : "¥";
}

function formatPrice(value, currencySign = "¥") {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) return "";
  return `${currencySign} ${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(n))}`;
}

function formatRegDate(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (!Number.isFinite(d.getTime())) return "";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${d.getFullYear()}-${mm}`;
}

function sleep(ms) {
  return new Promise((r) => window.setTimeout(r, ms));
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

const LIST_CACHE_PREFIX = "primcom-auto-iz-kitaya-list-cache:v1";

function getLocalStorageSafe() {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

function buildListCacheKey(prefix, params) {
  const sp = new URLSearchParams();
  Object.entries(params || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") return;
      sp.set(key, String(value));
    });
  return `${prefix}:${sp.toString()}`;
}

function readListCache(key) {
  const storage = getLocalStorageSafe();
  if (!storage) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !parsed.data) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeListCache(key, payload) {
  const storage = getLocalStorageSafe();
  if (!storage) return;
  try {
    storage.setItem(
      key,
      JSON.stringify({
        savedAt: Date.now(),
        apiOrigin: payload?.apiOrigin || "",
        data: payload?.data || null,
      })
    );
  } catch {
    // localStorage может быть недоступен в private mode.
  }
}

function getListSignature(data) {
  const total = Number(data?.total || 0);
  const last = data?.last_scraped_at ? String(data.last_scraped_at) : "";
  return `${last}::${total}`;
}

async function fetchJsonWithTimeout(url, timeoutMs = 12_000) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = window.setTimeout(() => controller && controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: controller ? controller.signal : undefined,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `HTTP ${res.status}`);
    }
    return await res.json();
  } finally {
    window.clearTimeout(timer);
  }
}

function getApiCandidates() {
  const custom = window.PRIMCOM_AUTO_IZ_KITAYA_API;
  if (typeof custom === "string" && custom.trim()) {
    return [custom.trim().replace(/\/+$/, "")];
  }

  const isFile = window.location && window.location.protocol === "file:";
  if (isFile) {
    return [
      "http://127.0.0.1:8010/api/auto-iz-kitaya",
      "/api/auto-iz-kitaya",
      "https://api.primcom.ru/api/auto-iz-kitaya",
    ];
  }

  const host = window.location && window.location.hostname ? String(window.location.hostname) : "";
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "::1";
  if (isLocal) {
    return [
      "http://127.0.0.1:8010/api/auto-iz-kitaya",
      "/api/auto-iz-kitaya",
      "https://api.primcom.ru/api/auto-iz-kitaya",
    ];
  }

  return ["/api/auto-iz-kitaya", "https://api.primcom.ru/api/auto-iz-kitaya"];
}

function buildUrl(base, pathSuffix, params) {
  const normalizedBase = String(base || "").replace(/\/+$/, "");
  const url = new URL(normalizedBase + (pathSuffix ? `/${String(pathSuffix).replace(/^\/+/, "")}` : ""), window.location.href);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v === null || v === undefined || v === "") return;
      url.searchParams.set(k, String(v));
    });
  }
  return url;
}

function setHidden(el, hidden) {
  if (!el) return;
  el.hidden = !!hidden;
}

function showModal(modal) {
  if (!modal || !modal.hidden) return;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function hideModal(modal) {
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.style.overflow = "";
}

function clearEl(el) {
  if (!el) return;
  while (el.firstChild) el.removeChild(el.firstChild);
}

function toAbsoluteUrl(apiOrigin, maybePath) {
  if (!maybePath) return null;
  const s = String(maybePath);
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/")) return `${apiOrigin}${s}`;
  return s;
}

function normalizeImageUrl(apiOrigin, imageItem) {
  if (!imageItem) return null;
  if (typeof imageItem === "string") {
    return toAbsoluteUrl(apiOrigin, imageItem);
  }
  if (typeof imageItem === "object") {
    return toAbsoluteUrl(
      apiOrigin,
      imageItem.url || imageItem.local_path || imageItem.src || imageItem.path || null
    );
  }
  return null;
}

function getTitle(item) {
  const parts = [];
  if (item?.brand) parts.push(String(item.brand));
  if (item?.model) parts.push(String(item.model));
  const title = parts.join(" ").trim();
  return title || "Автомобиль";
}

function getMeta(item) {
  const meta = [];
  if (typeof item?.year === "number") {
    meta.push(String(item.year));
  } else {
    const reg = formatRegDate(item?.first_registration_date);
    if (reg) meta.push(reg);
  }
  const m = formatMileageKm(item?.mileage_km);
  if (m) meta.push(m);
  const p = formatPrice(item?.price_cny, getCurrencySign(item));
  if (p) meta.push(p);
  return meta.join(" • ");
}

function getSpecs(item) {
  const specs = [];
  if (item?.engine_type) specs.push(`Топливо: ${item.engine_type}`);
  if (item?.drive_type) specs.push(`Привод: ${item.drive_type}`);
  if (item?.engine_volume_l) specs.push(`Объём: ${String(item.engine_volume_l)} л`);
  return specs.join(" • ");
}

function createCard(item, apiOrigin, onOpen, resolveCoverImage) {
  const card = document.createElement("article");
  card.className = "china-car-card";

  const mediaBtn = document.createElement("button");
  mediaBtn.type = "button";
  mediaBtn.className = "china-car-card__media";
  mediaBtn.addEventListener("click", () => onOpen(item));

  const imgUrl = toAbsoluteUrl(apiOrigin, item?.cover_image_url);
  if (imgUrl) {
    const img = document.createElement("img");
    img.className = "china-car-card__img";
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = getTitle(item);
    img.src = imgUrl;
    let triedFallbackCover = false;
    img.addEventListener("error", async () => {
      if (!triedFallbackCover && typeof resolveCoverImage === "function") {
        triedFallbackCover = true;
        const fallbackUrl = await resolveCoverImage(item);
        if (fallbackUrl && fallbackUrl !== img.src) {
          img.src = fallbackUrl;
          return;
        }
      }

      try {
        clearEl(mediaBtn);
        const ph = document.createElement("div");
        ph.className = "china-car-card__placeholder";
        ph.textContent = "Фото";
        mediaBtn.appendChild(ph);
      } catch {
        // noop
      }
    });
    mediaBtn.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "china-car-card__placeholder";
    ph.textContent = "Фото";
    mediaBtn.appendChild(ph);
  }

  const body = document.createElement("div");
  body.className = "china-car-card__body";

  const title = document.createElement("h3");
  title.className = "china-car-card__title";
  title.textContent = getTitle(item);

  const meta = document.createElement("p");
  meta.className = "china-car-card__meta";
  meta.textContent = getMeta(item);

  const actions = document.createElement("div");
  actions.className = "china-car-card__actions";

  const openBtn = document.createElement("button");
  openBtn.type = "button";
  openBtn.className = "btn btn--small china-car-card__btn-detail";
  openBtn.textContent = "Подробнее";
  openBtn.addEventListener("click", () => onOpen(item));

  const srcLink = document.createElement("a");
  srcLink.className = "btn btn--small btn--ghost";
  srcLink.textContent = "Источник";
  srcLink.href = item?.original_url || "#";
  srcLink.target = "_blank";
  srcLink.rel = "noopener";

  actions.appendChild(openBtn);
  actions.appendChild(srcLink);

  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(actions);

  card.appendChild(mediaBtn);
  card.appendChild(body);

  return card;
}

export function initAutoIzKitaya() {
  const root = qs("[data-china-cars]");
  if (!root) return;

  const form = qs("[data-china-cars-form]", root);
  const listEl = qs("[data-china-cars-list]", root);
  const statusEl = qs("[data-china-cars-status]", root);
  const lastUpdateEl = qs("[data-china-cars-last-update]", root);
  const prevBtn = qs("[data-china-cars-prev]", root);
  const nextBtn = qs("[data-china-cars-next]", root);
  const pageEl = qs("[data-china-cars-page]", root);
  const applyBtn = qs("[data-china-cars-apply]", root);
  const resetBtn = qs("[data-china-cars-reset]", root);
  const initialUrlFilters = new URLSearchParams(window.location.search);

  const modal = qs("[data-china-car-modal]");
  const modalTitle = qs("[data-china-car-title]", modal || document);
  const modalMeta = qs("[data-china-car-meta]", modal || document);
  const modalSpecs = qs("[data-china-car-specs]", modal || document);
  const modalGallery = qs("[data-china-car-gallery]", modal || document);
  const modalClosers = qsa("[data-china-car-close]", modal || document);
  const lightbox = qs("[data-china-lightbox]");
  const lightboxImg = qs("[data-china-lightbox-img]", lightbox || document);
  const lightboxCounter = qs("[data-china-lightbox-counter]", lightbox || document);
  const lightboxStage = qs("[data-china-lightbox-stage]", lightbox || document);
  const lightboxPrev = qs("[data-china-lightbox-prev]", lightbox || document);
  const lightboxNext = qs("[data-china-lightbox-next]", lightbox || document);
  const lightboxClosers = qsa("[data-china-lightbox-close]", lightbox || document);

  const state = {
    limit: 12,
    offset: 0,
    apiBase: null,
    apiBasePromise: null,
    apiOrigin: window.location.origin,
    lastLoadId: 0,
    lightboxImages: [],
    lightboxIndex: 0,
    touchStartX: 0,
    touchStartY: 0,
    touchActive: false,
    facets: null,
  };

  const renderLightbox = () => {
    if (!lightboxImg || !lightboxCounter) return;
    const n = state.lightboxImages.length;
    if (!n) return;
    const i = clamp(state.lightboxIndex, 0, n - 1);
    state.lightboxIndex = i;
    lightboxImg.src = state.lightboxImages[i] || "";
    lightboxCounter.textContent = `${i + 1} / ${n}`;
  };

  const openLightbox = (images, index = 0) => {
    if (!lightbox) return;
    const arr = Array.isArray(images) ? images.filter(Boolean) : [];
    if (!arr.length) return;
    state.lightboxImages = arr;
    state.lightboxIndex = clamp(index, 0, arr.length - 1);
    renderLightbox();
    showModal(lightbox);
  };

  const closeLightbox = () => {
    if (!lightbox) return;
    hideModal(lightbox);
    if (modal && !modal.hidden) {
      document.body.style.overflow = "hidden";
    }
  };

  const stepLightbox = (dir) => {
    const n = state.lightboxImages.length;
    if (!n) return;
    state.lightboxIndex = (state.lightboxIndex + dir + n) % n;
    renderLightbox();
  };

  const setStatus = (text) => {
    if (!statusEl) return;
    statusEl.textContent = text || "";
  };

  const populateSelect = (sel, values, emptyLabel) => {
    if (!sel) return;
    const prev = String(sel.value || "");
    clearEl(sel);
    const emptyOpt = document.createElement("option");
    emptyOpt.value = "";
    emptyOpt.textContent = emptyLabel;
    sel.appendChild(emptyOpt);
    (Array.isArray(values) ? values : []).forEach((v) => {
      const s = String(v);
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
    if (prev && Array.from(sel.options).some((o) => o.value === prev)) {
      sel.value = prev;
    }
  };

  const populateModelsForBrand = () => {
    const brandSel = form ? form.elements.namedItem("brand") : null;
    const modelSel = form ? form.elements.namedItem("model") : null;
    if (!brandSel || !modelSel || !state.facets) return;
    const b = String(brandSel.value || "");
    const byBrand = state.facets.models_by_brand || {};
    const values = b ? byBrand[b] || [] : state.facets.models || [];
    populateSelect(modelSel, values, "Все модели");
  };

  const applyRangeConstraints = () => {
    if (!form) return;
    const yearFromSel = form.elements.namedItem("year_from");
    const yearToSel = form.elements.namedItem("year_to");
    const mileageFromSel = form.elements.namedItem("mileage_from");
    const mileageToSel = form.elements.namedItem("mileage_to");

    const limitLowerBound = (fromSel, toSel) => {
      if (!fromSel || !toSel) return;
      const fromVal = fromSel.value ? Number(fromSel.value) : null;
      let toHadValue = false;
      const toVal = toSel.value ? Number(toSel.value) : null;
      if (toVal !== null) toHadValue = true;

      Array.from(toSel.options).forEach((opt) => {
        if (!opt.value) {
          opt.hidden = false;
          opt.disabled = false;
          return;
        }
        const n = Number(opt.value);
        const hide = fromVal !== null && Number.isFinite(n) && n < fromVal;
        opt.hidden = hide;
        opt.disabled = hide;
      });

      if (toHadValue && toVal !== null && fromVal !== null && toVal < fromVal) {
        toSel.value = "";
      }
    };

    const limitUpperBound = (fromSel, toSel) => {
      if (!fromSel || !toSel) return;
      const toVal = toSel.value ? Number(toSel.value) : null;
      let fromHadValue = false;
      const fromVal = fromSel.value ? Number(fromSel.value) : null;
      if (fromVal !== null) fromHadValue = true;

      Array.from(fromSel.options).forEach((opt) => {
        if (!opt.value) {
          opt.hidden = false;
          opt.disabled = false;
          return;
        }
        const n = Number(opt.value);
        const hide = toVal !== null && Number.isFinite(n) && n > toVal;
        opt.hidden = hide;
        opt.disabled = hide;
      });

      if (fromHadValue && fromVal !== null && toVal !== null && fromVal > toVal) {
        fromSel.value = "";
      }
    };

    limitLowerBound(yearFromSel, yearToSel);
    limitUpperBound(yearFromSel, yearToSel);
    limitLowerBound(mileageFromSel, mileageToSel);
    limitUpperBound(mileageFromSel, mileageToSel);
  };

  const loadFacets = async () => {
    if (!form) return;
    const sourceSel = form.elements.namedItem("source");
    const source = sourceSel ? String(sourceSel.value || "guazi") : "guazi";
    const base = await ensureApiBase();
    const u = buildUrl(base, "facets", { source });
    const facets = await fetchJsonWithTimeout(u.toString(), 12_000);
    state.facets = facets || null;

    const brandSel = form.elements.namedItem("brand");
    const modelSel = form.elements.namedItem("model");
    const yearFromSel = form.elements.namedItem("year_from");
    const yearToSel = form.elements.namedItem("year_to");
    const mileageFromSel = form.elements.namedItem("mileage_from");
    const mileageToSel = form.elements.namedItem("mileage_to");

    populateSelect(brandSel, facets?.brands || [], "Все марки");
    populateSelect(modelSel, facets?.models || [], "Все модели");
    populateSelect(yearFromSel, facets?.years || [], "Любой");
    populateSelect(yearToSel, facets?.years || [], "Любой");
    populateSelect(mileageFromSel, facets?.mileages || [], "Любой");
    populateSelect(mileageToSel, facets?.mileages || [], "Любой");
    populateModelsForBrand();
    ["source", "brand", "model", "year_from", "year_to", "mileage_from", "mileage_to"].forEach((name) => {
      const value = String(initialUrlFilters.get(name) || "").trim();
      const control = form.elements.namedItem(name);
      if (value && control && Array.from(control.options || []).some((option) => option.value === value)) {
        control.value = value;
        if (name === "brand") populateModelsForBrand();
      }
    });
    applyRangeConstraints();
  };

  const setPager = (total) => {
    const t = Number(total || 0);
    const lim = state.limit;
    const off = state.offset;
    const pages = lim > 0 ? Math.max(1, Math.ceil(t / lim)) : 1;
    const page = lim > 0 ? Math.floor(off / lim) + 1 : 1;

    if (pageEl) pageEl.textContent = `${page} / ${pages}`;

    if (prevBtn) prevBtn.disabled = off <= 0;
    if (nextBtn) nextBtn.disabled = off + lim >= t;
  };

  const renderListPayload = (data, apiOriginOverride = state.apiOrigin) => {
    if (lastUpdateEl) {
      const t = formatDateTimeRu(data?.last_scraped_at);
      lastUpdateEl.textContent = t || "—";
    }

    clearEl(listEl);

    const items = Array.isArray(data?.items) ? data.items : [];
    items.forEach((item) => {
      const el = createCard(item, apiOriginOverride, openDetail, resolveCoverImage);
      listEl && listEl.appendChild(el);
    });

    setPager(data?.total || 0);
    setStatus(items.length ? "" : "Ничего не найдено.");
  };

  const getFilters = () => {
    const fd = form ? new FormData(form) : null;
    const v = (name) => (fd ? String(fd.get(name) || "").trim() : "");
    const source = v("source") || "guazi";

    const brand = v("brand");
    const model = v("model");

    const yearFrom = v("year_from");
    const yearTo = v("year_to");

    const mileageFrom = v("mileage_from");
    const mileageTo = v("mileage_to");

    return {
      source,
      brand,
      model,
      year_from: yearFrom,
      year_to: yearTo,
      mileage_from: mileageFrom,
      mileage_to: mileageTo,
      limit: String(state.limit),
      offset: String(state.offset),
    };
  };

  const ensureApiBase = async () => {
    if (state.apiBase) return state.apiBase;
    if (state.apiBasePromise) return state.apiBasePromise;

    state.apiBasePromise = (async () => {
      const candidates = getApiCandidates();
      let lastErr = null;

      for (const base of candidates) {
        try {
          const u = buildUrl(base, "", { limit: "1", offset: "0", source: "guazi" });
          await fetchJsonWithTimeout(u.toString(), 10_000);
          state.apiBase = base;
          state.apiOrigin = new URL(base, window.location.href).origin;
          return state.apiBase;
        } catch (err) {
          lastErr = err;
          await sleep(80);
        }
      }

      throw lastErr || new Error("API недоступен");
    })();

    try {
      return await state.apiBasePromise;
    } catch (err) {
      state.apiBasePromise = null;
      throw err;
    }
  };

  const resolveCoverImage = async (item) => {
    const id = item?.id ? String(item.id) : "";
    if (!id) return null;

    try {
      const base = await ensureApiBase();
      const apiOrigin = new URL(base, window.location.href).origin;
      const data = await fetchJsonWithTimeout(buildUrl(base, id, null).toString(), 12_000);
      const rawImages = Array.isArray(data?.images) ? data.images : [];
      for (const image of rawImages) {
        const abs = normalizeImageUrl(apiOrigin, image);
        if (abs) return abs;
      }
    } catch (err) {
      console.warn("[auto-iz-kitaya] cover fallback failed", err);
    }

    return null;
  };

  const loadList = async () => {
    const myLoadId = ++state.lastLoadId;
    const params = getFilters();
    const cacheKey = buildListCacheKey(LIST_CACHE_PREFIX, params);
    const cached = readListCache(cacheKey);

    if (cached?.data) {
      renderListPayload(cached.data, cached.apiOrigin || state.apiOrigin);
      setStatus("Проверяем обновления...");
    } else {
      setStatus("Загрузка…");
      if (prevBtn) prevBtn.disabled = true;
      if (nextBtn) nextBtn.disabled = true;
    }

    try {
      const base = await ensureApiBase();
      const apiOrigin = new URL(base, window.location.href).origin;

      if (cached?.data) {
        try {
          const meta = await fetchJsonWithTimeout(
            buildUrl(base, "", { ...params, meta_only: "1" }).toString(),
            8_000
          );
          if (myLoadId !== state.lastLoadId) return;
          if (getListSignature(meta) === getListSignature(cached.data)) {
            renderListPayload(cached.data, cached.apiOrigin || apiOrigin);
            return;
          }
        } catch {
          // Если лёгкая проверка не удалась, просто переходим к обычной загрузке.
        }
      }

      const u = buildUrl(base, "", params);
      const data = await fetchJsonWithTimeout(u.toString(), 12_000);
      if (myLoadId !== state.lastLoadId) return;
      renderListPayload(data, apiOrigin);
      writeListCache(cacheKey, { apiOrigin, data });
    } catch (err) {
      if (myLoadId !== state.lastLoadId) return;
      if (cached?.data) {
        renderListPayload(cached.data, cached.apiOrigin || state.apiOrigin);
        setStatus("Показаны сохраненные объявления. Обновление временно недоступно.");
        return;
      }
      const msg = err && typeof err === "object" && "message" in err ? String(err.message || "") : "";
      console.error("[auto-iz-kitaya] loadList failed", err);
      setStatus(`Не удалось загрузить каталог. ${msg || ""}`.trim());
      clearEl(listEl);
      setPager(0);
    }
  };

  const openDetail = async (item) => {
    if (!modal) return;

    const titleText = getTitle(item);
    if (modalTitle) modalTitle.textContent = titleText;

    if (modalMeta) {
      const m = getMeta(item);
      modalMeta.textContent = m || "";
    }
    if (modalSpecs) {
      modalSpecs.textContent = getSpecs(item) || "";
    }

    clearEl(modalGallery);
    showModal(modal);

    try {
      const base = await ensureApiBase();
      const u = buildUrl(base, String(item?.id || ""), null);
      const data = await fetchJsonWithTimeout(u.toString(), 12_000);
      const detail = { ...item, ...(data || {}) };
      const detailTitle = getTitle(detail) || titleText;

      if (modalTitle) modalTitle.textContent = detailTitle;
      if (modalMeta) modalMeta.textContent = getMeta(detail);
      if (modalSpecs) modalSpecs.textContent = getSpecs(detail);
      const rawImages = Array.isArray(data?.images) ? data.images : [];
      const lightboxImages = rawImages
        .map((img) => normalizeImageUrl(state.apiOrigin, img))
        .filter(Boolean);

      lightboxImages.forEach((abs, idx) => {
        const a = document.createElement("button");
        a.type = "button";
        a.className = "china-car__img";

        const el = document.createElement("img");
        el.loading = "lazy";
        el.decoding = "async";
        el.alt = detailTitle;
        if (abs) el.src = abs;
        a.addEventListener("click", () => {
          openLightbox(lightboxImages, idx);
        });

        a.appendChild(el);
        modalGallery && modalGallery.appendChild(a);
      });

      if (!lightboxImages.length) {
        const p = document.createElement("p");
        p.className = "china-car__empty";
        p.textContent = "Фото не найдено.";
        modalGallery && modalGallery.appendChild(p);
      }
    } catch {
      clearEl(modalGallery);
      const p = document.createElement("p");
      p.className = "china-car__empty";
      p.textContent = "Не удалось загрузить детали. Попробуйте позже.";
      modalGallery && modalGallery.appendChild(p);
    }
  };

  const closeModal = () => hideModal(modal);

  if (modal && modalClosers.length) {
    modalClosers.forEach((btn) => btn.addEventListener("click", closeModal));
  }
  if (lightbox) {
    lightboxClosers.forEach((btn) => btn.addEventListener("click", closeLightbox));
    if (lightboxPrev) lightboxPrev.addEventListener("click", () => stepLightbox(-1));
    if (lightboxNext) lightboxNext.addEventListener("click", () => stepLightbox(1));
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (lightbox && !lightbox.hidden) closeLightbox();
      else closeModal();
      return;
    }
    if (lightbox && !lightbox.hidden && e.key === "ArrowLeft") {
      stepLightbox(-1);
    } else if (lightbox && !lightbox.hidden && e.key === "ArrowRight") {
      stepLightbox(1);
    }
  });
  if (lightboxStage) {
    lightboxStage.addEventListener(
      "touchstart",
      (e) => {
        const t = e.changedTouches && e.changedTouches[0];
        if (!t) return;
        state.touchActive = true;
        state.touchStartX = t.clientX;
        state.touchStartY = t.clientY;
      },
      { passive: true }
    );
    lightboxStage.addEventListener(
      "touchend",
      (e) => {
        if (!state.touchActive) return;
        state.touchActive = false;
        const t = e.changedTouches && e.changedTouches[0];
        if (!t) return;
        const dx = t.clientX - state.touchStartX;
        const dy = t.clientY - state.touchStartY;
        const adx = Math.abs(dx);
        const ady = Math.abs(dy);
        if (adx > 40 && adx > ady) {
          stepLightbox(dx < 0 ? 1 : -1);
          return;
        }
        if (dy > 90 && ady > adx) {
          closeLightbox();
        }
      },
      { passive: true }
    );
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      state.offset = Math.max(0, state.offset - state.limit);
      loadList();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      state.offset = state.offset + state.limit;
      loadList();
    });
  }

  if (form) {
    const applyFilters = () => {
      state.offset = 0;
      loadList();
    };

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      applyFilters();
    });

    if (applyBtn) {
      applyBtn.addEventListener("click", applyFilters);
    }

    const inputs = qsa("input, select", form);
    let t = 0;
    const onFilterChange = (inp) => {
        if (inp.name === "source") {
          state.offset = 0;
          loadFacets()
            .catch(() => {})
            .finally(() => loadList());
          return;
        }
        if (inp.name === "brand") {
          populateModelsForBrand();
        }
        if (
          inp.name === "year_from" ||
          inp.name === "year_to" ||
          inp.name === "mileage_from" ||
          inp.name === "mileage_to"
        ) {
          applyRangeConstraints();
        }
        window.clearTimeout(t);
        t = window.setTimeout(() => {
          state.offset = 0;
          loadList();
        }, 350);
    };
    inputs.forEach((inp) => {
      inp.addEventListener("input", () => onFilterChange(inp));
      inp.addEventListener("change", () => onFilterChange(inp));
    });
  }

  if (resetBtn && form) {
    resetBtn.addEventListener("click", () => {
      form.reset();
      state.offset = 0;
      loadFacets()
        .catch(() => {})
        .finally(() => loadList());
    });
  }

  loadFacets()
    .catch(() => {})
    .finally(() => loadList());
}
