function qs(sel, root = document) {
  return root.querySelector(sel);
}

function getApiCandidates(apiPath) {
  const path = String(apiPath || "/api/import-calculator/calculate").trim()
    || "/api/import-calculator/calculate";
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

function formatMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(Math.round(n));
}

function formatRate(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function parseApiError(text, status) {
  try {
    const parsed = JSON.parse(text || "{}");
    const detail = parsed?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      if (typeof first?.msg === "string" && first.msg.trim()) {
        return first.msg.trim();
      }
    }
  } catch {
    // ignore
  }

  if (status >= 500) return "Сервис расчёта временно недоступен.";
  return "Не удалось выполнить расчёт. Проверьте параметры формы.";
}

function humanizeUtilMode(value) {
  return value === "privileged" ? "льготный" : "коммерческий";
}

function setStatus(statusEl, text, type = "") {
  if (!statusEl) return;
  statusEl.textContent = text || "";
  if (type) {
    statusEl.dataset.type = type;
  } else {
    delete statusEl.dataset.type;
  }
}

async function postJson(url, payload, timeoutMs = 10_000) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = window.setTimeout(() => controller && controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller ? controller.signal : undefined,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(parseApiError(text, res.status));
    }
    return await res.json();
  } finally {
    window.clearTimeout(timer);
  }
}

async function postWithFallback(apiCandidates, payload) {
  let lastErr = null;
  for (const url of apiCandidates) {
    try {
      return await postJson(url, payload);
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error("Calculator endpoint unavailable");
}

function buildPayload(form) {
  return {
    car_price_foreign: Number(form.elements.carPriceForeign?.value || 0),
    currency: String(form.elements.currency?.value || "USD").toUpperCase(),
    engine_volume: Number(form.elements.engineVolume?.value || 0),
    engine_power_hp: Number(form.elements.enginePowerHp?.value || 0),
    vehicle_age: String(form.elements.vehicleAge?.value || "used"),
    fuel_type: String(form.elements.fuelType?.value || "petrol"),
    is_personal_use: !!form.elements.isPersonalUse?.checked,
    debug: !!form.elements.debug?.checked,
  };
}

function renderResult(root, payload, data) {
  const breakdown = data?.breakdown || {};
  const meta = data?.meta || {};

  const outCarPrice = qs("[data-out-car-price]", root);
  const outDuty = qs("[data-out-duty]", root);
  const outExcise = qs("[data-out-excise]", root);
  const outUtil = qs("[data-out-util]", root);
  const outVat = qs("[data-out-vat]", root);
  const outTotal = qs("[data-out-total]", root);
  const outRuleVersion = qs("[data-out-rule-version]", root);
  const outExchangeRate = qs("[data-out-exchange-rate]", root);
  const outUtilMode = qs("[data-out-util-mode]", root);
  const debugBox = qs("[data-calc-debug]", root);
  const debugPre = qs("[data-calc-debug-pre]", root);

  if (outCarPrice) outCarPrice.textContent = formatMoney(breakdown.car_price_rub);
  if (outDuty) outDuty.textContent = formatMoney(breakdown.duty);
  if (outExcise) outExcise.textContent = formatMoney(breakdown.excise);
  if (outUtil) outUtil.textContent = formatMoney(breakdown.util);
  if (outVat) outVat.textContent = formatMoney(breakdown.vat);
  if (outTotal) outTotal.textContent = formatMoney(data.total_cost);
  if (outRuleVersion) outRuleVersion.textContent = String(meta.rule_version || "—");
  if (outExchangeRate) {
    const rate = formatRate(meta.exchange_rate);
    const source = String(meta.exchange_rate_source || "").trim();
    outExchangeRate.textContent = `${payload.currency}/RUB: ${rate}${source ? ` (${source})` : ""}`;
  }
  if (outUtilMode) outUtilMode.textContent = humanizeUtilMode(meta.util_mode);

  if (debugBox && debugPre) {
    if (payload.debug && data.debug_trace) {
      debugBox.hidden = false;
      debugPre.textContent = JSON.stringify(data.debug_trace, null, 2);
    } else {
      debugBox.hidden = true;
      debugPre.textContent = "";
    }
  }
}

export function initImportCalculator() {
  const root = qs("[data-import-calculator]");
  if (!root) return;

  const form = qs("[data-calc-form]", root);
  if (!form) return;

  const submitBtn = qs("[data-calc-submit]", root);
  const statusEl = qs("[data-calc-status]", root);
  const apiPath = root.getAttribute("data-api-path") || "/api/import-calculator/calculate";
  const apiCandidates = getApiCandidates(apiPath);

  const setBusy = (busy) => {
    form.setAttribute("aria-busy", busy ? "true" : "false");
    if (submitBtn) submitBtn.disabled = busy;
  };

  const calculate = async () => {
    const payload = buildPayload(form);
    setBusy(true);
    setStatus(statusEl, "Считаем платежи...", "loading");
    try {
      const data = await postWithFallback(apiCandidates, payload);
      renderResult(root, payload, data);
      setStatus(
        statusEl,
        "Расчёт выполнен. Точный коммерческий расчёт с логистикой и сопровождением уточняется отдельно.",
        "success"
      );
    } catch (err) {
      const msg = String(err?.message || "Сервис расчёта временно недоступен.");
      setStatus(statusEl, msg, "error");
    } finally {
      setBusy(false);
    }
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    void calculate();
  });

  form.addEventListener("input", () => {
    if (String(statusEl?.dataset.type || "") === "error") {
      setStatus(statusEl, "Параметры обновлены. Нажмите «Рассчитать» для нового запроса.");
    }
  });

  void calculate();
}
