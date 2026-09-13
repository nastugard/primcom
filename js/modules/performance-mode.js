const MODE_STORAGE_KEY = "primcom-performance-mode";
const GSAP_BASE_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.1/dist";

function storageGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // localStorage может быть недоступен в sandbox/private mode.
  }
}

function storageRemove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Игнорируем недоступное хранилище.
  }
}

function readOverrideMode() {
  const params = new URLSearchParams(window.location.search);
  const queryMode = params.get("performance");

  if (queryMode === "lite" || queryMode === "full") {
    storageSet(MODE_STORAGE_KEY, queryMode);
    return queryMode;
  }

  if (queryMode === "auto") {
    storageRemove(MODE_STORAGE_KEY);
    return null;
  }

  const stored = storageGet(MODE_STORAGE_KEY);
  return stored === "lite" || stored === "full" ? stored : null;
}

function getSignals() {
  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const slowUpdate = !!(window.matchMedia && window.matchMedia("(update: slow)").matches);
  const saveData = !!(navigator.connection && navigator.connection.saveData);
  const cpuCores = Number(navigator.hardwareConcurrency || 0);
  const deviceMemory = Number(navigator.deviceMemory || 0);

  return {
    reduceMotion,
    slowUpdate,
    saveData,
    cpuCores,
    deviceMemory,
    lowCpu: cpuCores > 0 && cpuCores <= 4,
    lowMemory: deviceMemory > 0 && deviceMemory <= 4,
  };
}

function getAutoLiteMode(signals) {
  return !!(
    signals.reduceMotion ||
    signals.slowUpdate ||
    signals.saveData ||
    signals.lowCpu ||
    signals.lowMemory
  );
}

function applyMode(mode, signals, override) {
  const root = document.documentElement;
  const isLite = mode === "lite";

  root.classList.toggle("performance-lite", isLite);
  root.classList.toggle("performance-full", !isLite);
  root.dataset.performanceMode = mode;

  const profile = {
    mode,
    isLite,
    override,
    signals,
  };

  window.__primcomPerformance = profile;
  return profile;
}

function getScriptNeeds() {
  const hasHeroStrip = !!document.querySelector(".hero-strip");

  return {
    core: true,
    scrollTrigger: true,
    scrollSmoother: false,
    observer: hasHeroStrip,
  };
}

function loadScriptOnce(src) {
  const existing = document.querySelector(`script[data-runtime-src="${src}"]`);
  if (existing) {
    if (existing.dataset.loaded === "1") return Promise.resolve();
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    script.defer = false;
    script.dataset.runtimeSrc = src;
    script.crossOrigin = "anonymous";
    script.addEventListener("load", () => {
      script.dataset.loaded = "1";
      resolve();
    }, { once: true });
    script.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
    document.head.appendChild(script);
  });
}

export function initPerformanceMode() {
  const override = readOverrideMode();
  const signals = getSignals();
  const autoLite = getAutoLiteMode(signals);
  const mode = override || (autoLite ? "lite" : "full");

  return applyMode(mode, signals, override);
}

export async function loadEnhancementRuntime(profile) {
  if (profile && profile.isLite) {
    return { loaded: false, mode: "lite", needs: null };
  }

  const needs = getScriptNeeds();
  const urls = [];

  if (needs.core) {
    urls.push(`${GSAP_BASE_URL}/gsap.min.js`);
  }
  if (needs.scrollTrigger) {
    urls.push(`${GSAP_BASE_URL}/ScrollTrigger.min.js`);
  }
  if (needs.scrollSmoother) {
    urls.push(`${GSAP_BASE_URL}/ScrollSmoother.min.js`);
  }
  if (needs.observer) {
    urls.push(`${GSAP_BASE_URL}/Observer.min.js`);
  }

  for (const url of urls) {
    await loadScriptOnce(url);
  }

  return { loaded: urls.length > 0, mode: "full", needs };
}
