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
  return s ? `${s} км` : "";
}

function formatPriceRub(value) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) return "";
  return `₽ ${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(n))}`;
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

const LIST_CACHE_PREFIX = "primcom-auto-manual-list-cache:v1";

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
    return toAbsoluteUrl(apiOrigin, imageItem.url || imageItem.local_path || imageItem.src || imageItem.path || null);
  }
  return null;
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

function buildUrl(base, suffix, params) {
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

function getTitle(item) {
  const parts = [];
  if (item?.brand) parts.push(String(item.brand));
  if (item?.model) parts.push(String(item.model));
  const t = parts.join(" ").trim();
  return t || "Автомобиль";
}

function getMeta(item) {
  const parts = [];
  if (typeof item?.year === "number") parts.push(String(item.year));
  const mileage = formatMileageKm(item?.mileage_km);
  if (mileage) parts.push(mileage);
  const price = formatPriceRub(item?.price_cny);
  if (price) parts.push(price);
  return parts.join(" • ");
}

function createCard(item, apiOrigin, onOpen) {
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
    img.addEventListener("error", () => {
      clearEl(mediaBtn);
      const ph = document.createElement("div");
      ph.className = "china-car-card__placeholder";
      ph.textContent = "Фото";
      mediaBtn.appendChild(ph);
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

function getEndpointCandidates(market, customListApi) {
  if (customListApi && customListApi.trim()) {
    return [customListApi.trim().replace(/\/+$/, "")];
  }

  const map = {
    korea: {
      local: "http://127.0.0.1:8010/api/auto-iz-korei",
      prod: "https://api.primcom.ru/api/auto-iz-korei",
      rel: "/api/auto-iz-korei",
    },
    japan: {
      local: "http://127.0.0.1:8010/api/auto-iz-yaponii",
      prod: "https://api.primcom.ru/api/auto-iz-yaponii",
      rel: "/api/auto-iz-yaponii",
    },
  };

  const e = map[market] || map.korea;
  const isFile = window.location.protocol === "file:";
  const host = String(window.location.hostname || "");
  const isLocal = isFile || host === "localhost" || host === "127.0.0.1" || host === "::1";

  if (isLocal) {
    return [e.local, e.rel, e.prod];
  }
  return [e.rel, e.prod];
}

export function initManualMarketCars() {
  const root = qs("[data-manual-cars]");
  if (!root) return;

  const market = String(root.getAttribute("data-market") || "").trim().toLowerCase();
  if (!(market === "korea" || market === "japan")) return;

  const customListApi = root.getAttribute("data-list-api") || "";
  const customDetailApi = root.getAttribute("data-detail-api") || "";

  const form = qs("[data-manual-cars-form]", root);
  const listEl = qs("[data-manual-cars-list]", root);
  const statusEl = qs("[data-manual-cars-status]", root);
  const lastUpdateEl = qs("[data-manual-cars-last-update]", root);
  const prevBtn = qs("[data-manual-cars-prev]", root);
  const nextBtn = qs("[data-manual-cars-next]", root);
  const pageEl = qs("[data-manual-cars-page]", root);
  const applyBtn = qs("[data-manual-cars-apply]", root);
  const resetBtn = qs("[data-manual-cars-reset]", root);
  const initialUrlFilters = new URLSearchParams(window.location.search);

  const modal = qs("[data-manual-car-modal]");
  const modalTitle = qs("[data-manual-car-title]", modal || document);
  const modalMeta = qs("[data-manual-car-meta]", modal || document);
  const modalCalcAt = qs("[data-manual-car-calc-at]", modal || document);
  const modalSpecs = qs("[data-manual-car-specs]", modal || document);
  const modalMainBtn = qs("[data-manual-main-button]", modal || document);
  const modalMainImg = qs("[data-manual-main-image]", modal || document);
  const modalThumbs = qs("[data-manual-thumbs]", modal || document);
  const modalPrev = qs("[data-manual-prev]", modal || document);
  const modalNext = qs("[data-manual-next]", modal || document);
  const modalClosers = qsa("[data-manual-car-close]", modal || document);

  const lightbox = qs("[data-manual-lightbox]");
  const lightboxImg = qs("[data-manual-lightbox-img]", lightbox || document);
  const lightboxCounter = qs("[data-manual-lightbox-counter]", lightbox || document);
  const lightboxStage = qs("[data-manual-lightbox-stage]", lightbox || document);
  const lightboxPrev = qs("[data-manual-lightbox-prev]", lightbox || document);
  const lightboxNext = qs("[data-manual-lightbox-next]", lightbox || document);
  const lightboxClosers = qsa("[data-manual-lightbox-close]", lightbox || document);

  const state = {
    limit: 12,
    offset: 0,
    listApiBase: null,
    listApiBasePromise: null,
    detailApiBase: null,
    apiOrigin: window.location.origin,
    facets: null,
    lastLoadId: 0,
    modalImages: [],
    modalImageIndex: 0,
    lightboxImages: [],
    lightboxIndex: 0,
    touchStartX: 0,
    touchStartY: 0,
    touchActive: false,
  };

  const setStatus = (text) => {
    if (statusEl) statusEl.textContent = text || "";
  };

  const setPager = (total) => {
    const t = Number(total || 0);
    const pages = Math.max(1, Math.ceil(t / state.limit));
    const page = Math.floor(state.offset / state.limit) + 1;
    if (pageEl) pageEl.textContent = `${page} / ${pages}`;
    if (prevBtn) prevBtn.disabled = state.offset <= 0;
    if (nextBtn) nextBtn.disabled = state.offset + state.limit >= t;
  };

  const getFilters = () => {
    const fd = form ? new FormData(form) : null;
    const v = (name) => (fd ? String(fd.get(name) || "").trim() : "");
    return {
      brand: v("brand"),
      model: v("model"),
      year_from: v("year_from"),
      year_to: v("year_to"),
      mileage_from: v("mileage_from"),
      mileage_to: v("mileage_to"),
      limit: String(state.limit),
      offset: String(state.offset),
    };
  };

  const renderListPayload = (data, apiOriginOverride = state.apiOrigin) => {
    if (lastUpdateEl) {
      lastUpdateEl.textContent = formatDateTimeRu(data?.last_scraped_at) || "—";
    }

    clearEl(listEl);
    const items = Array.isArray(data?.items) ? data.items : [];
    items.forEach((item) => {
      const card = createCard(item, apiOriginOverride, openDetail);
      listEl && listEl.appendChild(card);
    });

    setPager(data?.total || 0);
    setStatus(items.length ? "" : "Ничего не найдено.");
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

  const ensureListApiBase = async () => {
    if (state.listApiBase) return state.listApiBase;
    if (state.listApiBasePromise) return state.listApiBasePromise;

    state.listApiBasePromise = (async () => {
      const candidates = getEndpointCandidates(market, customListApi);
      let lastErr = null;

      for (const base of candidates) {
        try {
          const probe = buildUrl(base, "", { limit: "1", offset: "0" });
          await fetchJsonWithTimeout(probe.toString(), 10_000);
          state.listApiBase = base;
          state.apiOrigin = new URL(base, window.location.href).origin;
          return base;
        } catch (e) {
          lastErr = e;
        }
      }

      throw lastErr || new Error("API is unavailable");
    })();

    try {
      return await state.listApiBasePromise;
    } catch (err) {
      state.listApiBasePromise = null;
      throw err;
    }
  };

  const ensureDetailApiBase = async () => {
    if (state.detailApiBase) return state.detailApiBase;

    if (customDetailApi && customDetailApi.trim()) {
      state.detailApiBase = customDetailApi.trim().replace(/\/+$/, "");
      return state.detailApiBase;
    }

    const listBase = await ensureListApiBase();
    const parsed = new URL(listBase, window.location.href);
    state.detailApiBase = `${parsed.protocol}//${parsed.host}/api/auto-iz-kitaya`;
    return state.detailApiBase;
  };

  const loadFacets = async () => {
    if (!form) return;
    const listBase = await ensureListApiBase();
    const u = buildUrl(listBase, "facets", null);
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

    ["brand", "model", "year_from", "year_to", "mileage_from", "mileage_to"].forEach((name) => {
      const value = String(initialUrlFilters.get(name) || "").trim();
      const control = form.elements.namedItem(name);
      if (value && control && Array.from(control.options || []).some((option) => option.value === value)) {
        control.value = value;
      }
    });
  };

  const renderLightbox = () => {
    if (!lightboxImg || !lightboxCounter) return;
    const n = state.lightboxImages.length;
    if (!n) return;
    state.lightboxIndex = clamp(state.lightboxIndex, 0, n - 1);
    lightboxImg.src = state.lightboxImages[state.lightboxIndex] || "";
    lightboxCounter.textContent = `${state.lightboxIndex + 1} / ${n}`;
  };

  const openLightbox = (images, index = 0) => {
    if (!lightbox) return;
    const arr = (Array.isArray(images) ? images : []).filter(Boolean);
    if (!arr.length) return;
    state.lightboxImages = arr;
    state.lightboxIndex = clamp(index, 0, arr.length - 1);
    renderLightbox();
    showModal(lightbox);
  };

  const closeLightbox = () => {
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

  const setModalImage = (index) => {
    const n = state.modalImages.length;
    if (!n || !modalMainImg) return;
    state.modalImageIndex = clamp(index, 0, n - 1);
    const nextSrc = state.modalImages[state.modalImageIndex];
    if (!nextSrc) return;

    modalMainImg.classList.add("manual-car__img--fading");
    window.setTimeout(() => {
      modalMainImg.src = nextSrc;
      modalMainImg.classList.remove("manual-car__img--fading");
    }, 120);

    const thumbs = qsa("[data-manual-thumb-index]", modalThumbs || document);
    thumbs.forEach((el) => {
      const idx = Number(el.getAttribute("data-manual-thumb-index") || "0");
      el.classList.toggle("is-active", idx === state.modalImageIndex);
    });
  };

  const renderSpecRows = (item) => {
    clearEl(modalSpecs);
    if (!modalSpecs) return;

    const priceRowLabel = market === "japan" ? "Цена" : "Цена во Владивостоке под ключ";

    const rows = [
      ["Марка", item?.brand],
      ["Модель", item?.model],
      ["Год", item?.year],
      ["Пробег", formatMileageKm(item?.mileage_km)],
      [priceRowLabel, formatPriceRub(item?.price_cny)],
      ["Привод", item?.drive_type],
      ["Топливо", item?.engine_type],
      ["Объем", item?.engine_volume_l ? `${item.engine_volume_l} л` : ""],
      ["Мощность", item?.power_hp ? `${item.power_hp} л.с.` : ""],
      ["Кузов", item?.body_type],
      ["Оценка аукциона", item?.auction_grade],
      ["Комплектация", item?.trim],
      ["Коробка", item?.transmission],
    ];

    rows.forEach(([label, value]) => {
      const val = value === null || value === undefined ? "" : String(value).trim();
      if (!val) return;
      const isPriceRow = String(label) === priceRowLabel;
      const row = document.createElement("div");
      row.className = isPriceRow ? "manual-car__spec-row manual-car__spec-row--price" : "manual-car__spec-row";

      const k = document.createElement("span");
      k.className = isPriceRow ? "manual-car__spec-key manual-car__spec-key--nowrap" : "manual-car__spec-key";
      k.textContent = String(label);

      const v = document.createElement("span");
      v.className = isPriceRow ? "manual-car__spec-val manual-car__spec-val--price" : "manual-car__spec-val";
      v.textContent = val;

      row.appendChild(k);
      row.appendChild(v);
      modalSpecs.appendChild(row);
    });
  };

  const openDetail = async (item) => {
    if (!modal) return;
    const leadButton = modal.querySelector('[data-open-lead-modal]');
    if (leadButton) {
      leadButton.dataset.leadModel = [item.brand,item.model].filter(Boolean).join(' ');
      leadButton.dataset.leadLabel = `${item.year || ''} · ${item.trim || ''}`;
    }

    if (modalTitle) modalTitle.textContent = getTitle(item);
    if (modalMeta) modalMeta.textContent = getMeta(item);
    if (modalCalcAt) modalCalcAt.textContent = formatDateTimeRu(item?.scraped_at) || "—";
    renderSpecRows(item);

    clearEl(modalThumbs);
    if (modalMainImg) modalMainImg.src = "";
    state.modalImages = [];
    state.modalImageIndex = 0;

    showModal(modal);

    try {
      const detailBase = await ensureDetailApiBase();
      const u = buildUrl(detailBase, String(item?.id || ""), null);
      const detail = await fetchJsonWithTimeout(u.toString(), 12_000);

      if (modalTitle) modalTitle.textContent = getTitle(detail);
      if (modalMeta) modalMeta.textContent = getMeta(detail);
      if (modalCalcAt) modalCalcAt.textContent = formatDateTimeRu(detail?.scraped_at) || "—";
      renderSpecRows(detail);

      const images = (Array.isArray(detail?.images) ? detail.images : [])
        .map((x) => normalizeImageUrl(state.apiOrigin, x))
        .filter(Boolean);

      if (!images.length) {
        const empty = document.createElement("p");
        empty.className = "china-car__empty";
        empty.textContent = "Фото не найдены.";
        modalThumbs && modalThumbs.appendChild(empty);
        return;
      }

      state.modalImages = images;
      state.modalImageIndex = 0;
      if (modalMainImg) {
        modalMainImg.src = images[0];
        modalMainImg.alt = getTitle(detail);
      }

      images.forEach((img, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "manual-car__thumb";
        btn.setAttribute("data-manual-thumb-index", String(idx));
        if (idx === 0) btn.classList.add("is-active");

        const el = document.createElement("img");
        el.loading = "lazy";
        el.decoding = "async";
        el.alt = getTitle(detail);
        el.src = img;
        btn.appendChild(el);

        btn.addEventListener("click", () => setModalImage(idx));
        modalThumbs && modalThumbs.appendChild(btn);
      });
    } catch (err) {
      console.error("[manual-market] detail load failed", err);
      const empty = document.createElement("p");
      empty.className = "china-car__empty";
      empty.textContent = "Не удалось загрузить фото и детали.";
      clearEl(modalThumbs);
      modalThumbs && modalThumbs.appendChild(empty);
    }
  };

  const closeDetail = () => hideModal(modal);

  const loadList = async () => {
    const loadId = ++state.lastLoadId;
    const params = getFilters();
    const cacheKey = buildListCacheKey(`${LIST_CACHE_PREFIX}:${market}`, params);
    const cached = readListCache(cacheKey);

    if (cached?.data) {
      renderListPayload(cached.data, cached.apiOrigin || state.apiOrigin);
      setStatus("Проверяем обновления...");
    } else {
      setStatus("Загрузка...");
    }

    try {
      const listBase = await ensureListApiBase();
      const apiOrigin = new URL(listBase, window.location.href).origin;

      if (cached?.data) {
        try {
          const meta = await fetchJsonWithTimeout(
            buildUrl(listBase, "", { ...params, meta_only: "1" }).toString(),
            8_000
          );
          if (loadId !== state.lastLoadId) return;
          if (getListSignature(meta) === getListSignature(cached.data)) {
            renderListPayload(cached.data, cached.apiOrigin || apiOrigin);
            return;
          }
        } catch {
          // Если meta-проверка не удалась, просто делаем полный запрос.
        }
      }

      const data = await fetchJsonWithTimeout(buildUrl(listBase, "", params).toString(), 12_000);
      if (loadId !== state.lastLoadId) return;
      renderListPayload(data, apiOrigin);
      writeListCache(cacheKey, { apiOrigin, data });
    } catch (err) {
      if (loadId !== state.lastLoadId) return;
      if (cached?.data) {
        renderListPayload(cached.data, cached.apiOrigin || state.apiOrigin);
        setStatus("Показаны сохраненные объявления. Обновление временно недоступно.");
        return;
      }
      console.error("[manual-market] list load failed", err);
      clearEl(listEl);
      setPager(0);
      const msg = err && typeof err === "object" && "message" in err ? String(err.message || "") : "";
      setStatus(`Не удалось загрузить каталог. ${msg || ""}`.trim());
    }
  };

  const applyFilters = () => {
    state.offset = 0;
    loadList();
  };

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      applyFilters();
    });

    const inputs = qsa("input, select", form);
    let timer = 0;
    const onChange = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        state.offset = 0;
        loadList();
      }, 300);
    };

    inputs.forEach((el) => {
      el.addEventListener("input", onChange);
      el.addEventListener("change", onChange);
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", applyFilters);
  }

  if (resetBtn && form) {
    resetBtn.addEventListener("click", () => {
      form.reset();
      state.offset = 0;
      loadFacets().catch(() => {}).finally(() => loadList());
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      state.offset = Math.max(0, state.offset - state.limit);
      loadList();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      state.offset += state.limit;
      loadList();
    });
  }

  if (modal && modalClosers.length) {
    modalClosers.forEach((el) => el.addEventListener("click", closeDetail));
  }

  if (modalMainBtn) {
    modalMainBtn.addEventListener("click", () => {
      if (state.modalImages.length) {
        openLightbox(state.modalImages, state.modalImageIndex);
      }
    });

    modalMainBtn.addEventListener("mousemove", (e) => {
      if (!state.modalImages.length) return;
      const rect = modalMainBtn.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = rect.width > 0 ? x / rect.width : 0;
      const idx = clamp(Math.floor(ratio * state.modalImages.length), 0, state.modalImages.length - 1);
      if (idx !== state.modalImageIndex) {
        setModalImage(idx);
      }
    });
  }

  if (modalPrev) {
    modalPrev.addEventListener("click", () => {
      if (!state.modalImages.length) return;
      const idx = (state.modalImageIndex - 1 + state.modalImages.length) % state.modalImages.length;
      setModalImage(idx);
    });
  }

  if (modalNext) {
    modalNext.addEventListener("click", () => {
      if (!state.modalImages.length) return;
      const idx = (state.modalImageIndex + 1) % state.modalImages.length;
      setModalImage(idx);
    });
  }

  if (lightbox) {
    lightboxClosers.forEach((el) => el.addEventListener("click", closeLightbox));
    if (lightboxPrev) lightboxPrev.addEventListener("click", () => stepLightbox(-1));
    if (lightboxNext) lightboxNext.addEventListener("click", () => stepLightbox(1));
  }

  document.addEventListener("keydown", (e) => {
    if (e.defaultPrevented) return;
    if (e.key === "Escape") {
      if (lightbox && !lightbox.hidden) closeLightbox();
      else closeDetail();
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

  loadFacets()
    .catch(() => {})
    .finally(() => loadList());
}
