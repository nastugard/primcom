// Модальное окно заявки.
// На следующем этапе добавим GSAP Flip-анимацию и реальную отправку в Telegram.

const OPEN_DELAY_MS = 30_000;
const OPEN_SCROLL_RATIO = 0.98;

const LS_KEY_AUTOSHOW_VISITED = "primcom_lead_autoshow_visited_v1";
const LS_KEY_AUTOSHOW_DISMISSED = "primcom_lead_autoshow_dismissed_v1";

const DEFAULT_LEAD_ENDPOINT = "https://api.primcom.ru/api/lead";
const TARGET_GROUP_ID = -1003540261166;

function qs(sel) {
  return document.querySelector(sel);
}

function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function storageGet(key) {
  try {
    return window.localStorage ? window.localStorage.getItem(key) : null;
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    if (!window.localStorage) return;
    window.localStorage.setItem(key, String(value));
  } catch {
    // ignore
  }
}

function getScrollRatio() {
  const doc = document.documentElement;
  const max = doc.scrollHeight - doc.clientHeight;
  if (max <= 0) return 0;
  return doc.scrollTop / max;
}

function prefersReducedMotion() {
  return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
}

function applyRect(el, rect) {
  if (!el || !rect || !window.gsap) return;
  window.gsap.set(el, {
    position: "fixed",
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    margin: 0,
  });
}

function show(modal) {
  if (!modal.hidden) return;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function hide(modal) {
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.style.overflow = "";
}

function setStatus(text, type) {
  const el = qs("[data-form-status]");
  if (!el) return;

  el.textContent = text;
  el.dataset.type = type || "";
}

function validateForm(form) {
  const name = form.elements.namedItem("name");
  const phone = form.elements.namedItem("phone");
  const consent = form.elements.namedItem("consent");

  if (!name || !phone || !consent) return false;

  if (!String(name.value || "").trim()) return false;
  if (!String(phone.value || "").trim()) return false;
  if (!consent.checked) return false;

  return true;
}

function getLeadEndpoint() {
  const value = window.PRIMCOM_LEAD_ENDPOINT;
  if (typeof value !== "string") return DEFAULT_LEAD_ENDPOINT;
  const trimmed = value.trim();
  if (!trimmed) return DEFAULT_LEAD_ENDPOINT;
  return trimmed;
}

async function postJson(url, payload, timeoutMs) {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = window.setTimeout(() => controller && controller.abort(), timeoutMs);

  try {
    const headers = { "Content-Type": "application/json" };
    const token = window.PRIMCOM_LEAD_TOKEN;
    if (typeof token === "string" && token.trim()) {
      headers["X-Primcom-Token"] = token.trim();
    }

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller ? controller.signal : undefined,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `HTTP ${res.status}`);
    }

    return res;
  } finally {
    window.clearTimeout(timer);
  }
}

export function initLeadModal() {
  const modal = qs("[data-lead-modal]");
  if (!modal) return;

  const openers = qsa("[data-open-lead-modal]");
  const closers = qsa("[data-modal-close]");
  const form = qs("[data-lead-form]");

  const dialog = modal.querySelector(".modal__dialog");
  const backdrop = modal.querySelector(".modal__backdrop");

  let openedOnce = false;
  let lastOpener = openers[0] || null;
  let formOpenedAt = Date.now();

  const dismissed = storageGet(LS_KEY_AUTOSHOW_DISMISSED) === "1";
  const firstVisit = storageGet(LS_KEY_AUTOSHOW_VISITED) !== "1";
  if (firstVisit) storageSet(LS_KEY_AUTOSHOW_VISITED, "1");

  const canFlip = !!(window.gsap && window.Flip && dialog && !prefersReducedMotion());
  if (canFlip) {
    window.gsap.registerPlugin(window.Flip);
  }

  const closeWithFlip = false;

  let autoTimer = 0;
  let autoScrollHandler = null;

  const disableAutoOpen = () => {
    if (autoTimer) {
      window.clearTimeout(autoTimer);
      autoTimer = 0;
    }
    if (autoScrollHandler) {
      window.removeEventListener("scroll", autoScrollHandler);
      autoScrollHandler = null;
    }
  };

  const open = (fromEl) => {
    if (!modal.hidden) return;

    modal.classList.remove("is-closing");

    show(modal);
    openedOnce = true;
    formOpenedAt = Date.now();
    disableAutoOpen();

    if (!canFlip) return;

    const { gsap } = window;
    const from = fromEl || lastOpener;
    const rect = from ? from.getBoundingClientRect() : null;

    gsap.killTweensOf([dialog, backdrop]);

    gsap.set(dialog, { opacity: 1, y: 0, scale: 1 });

    if (backdrop) gsap.set(backdrop, { opacity: 0 });

    if (rect) {
      applyRect(dialog, rect);
      const state = window.Flip.getState(dialog);
      gsap.set(dialog, { clearProps: "position,left,top,width,height,margin" });

      window.Flip.from(state, {
        duration: 0.75,
        ease: "power3.out",
        absolute: true,
        scale: true,
      });
    } else {
      gsap.fromTo(
        dialog,
        { y: 18, scale: 0.98, opacity: 0 },
        { y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "power3.out" }
      );
    }

    if (backdrop) gsap.to(backdrop, { opacity: 1, duration: 0.25, ease: "power2.out" });
  };

  const close = () => {
    if (modal.hidden) return;

    storageSet(LS_KEY_AUTOSHOW_DISMISSED, "1");
    disableAutoOpen();

    modal.classList.add("is-closing");

    if (!canFlip || !closeWithFlip) {
      const { gsap } = window;
      gsap && gsap.killTweensOf([dialog, backdrop]);

      if (backdrop && gsap) gsap.to(backdrop, { opacity: 0, duration: 0.2, ease: "power2.out" });
      if (dialog && gsap) {
        gsap.to(dialog, {
          y: 10,
          scale: 0.98,
          opacity: 0,
          duration: 0.22,
          ease: "power2.in",
          onComplete: () => {
            modal.classList.remove("is-closing");
            hide(modal);
          },
        });
        return;
      }

      modal.classList.remove("is-closing");
      hide(modal);
      return;
    }

    const { gsap } = window;
    const to = lastOpener;
    const rect = to ? to.getBoundingClientRect() : null;

    gsap.killTweensOf([dialog, backdrop]);

    if (!rect) {
      if (backdrop) gsap.to(backdrop, { opacity: 0, duration: 0.2, ease: "power2.out" });
      gsap.to(dialog, {
        y: 10,
        scale: 0.98,
        opacity: 0,
        duration: 0.25,
        ease: "power2.in",
        onComplete: () => {
          modal.classList.remove("is-closing");
          hide(modal);
        },
      });
      return;
    }

    const state = window.Flip.getState(dialog);
    applyRect(dialog, rect);

    window.Flip.from(state, {
      duration: 0.6,
      ease: "power3.inOut",
      absolute: true,
      scale: true,
      onComplete: () => {
        gsap.set(dialog, { clearProps: "position,left,top,width,height,margin" });
        modal.classList.remove("is-closing");
        hide(modal);
      },
    });

    if (backdrop) gsap.to(backdrop, { opacity: 0, duration: 0.25, ease: "power2.out" });
  };

  openers.forEach((btn) =>
    btn.addEventListener("click", () => {
      lastOpener = btn;
      open(btn);
    })
  );
  closers.forEach((btn) => btn.addEventListener("click", close));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  const canAutoOpen = firstVisit && !dismissed;
  if (canAutoOpen) {
    autoTimer = window.setTimeout(() => {
      if (!openedOnce) open(lastOpener);
    }, OPEN_DELAY_MS);

    autoScrollHandler = () => {
      if (openedOnce) return;
      if (getScrollRatio() >= OPEN_SCROLL_RATIO) open(lastOpener);
    };
    window.addEventListener("scroll", autoScrollHandler, { passive: true });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      setStatus("", "");

      const hp = form.elements.namedItem("company");
      if (hp && String(hp.value || "").trim()) {
        setStatus("Ошибка отправки.", "error");
        return;
      }

      if (Date.now() - formOpenedAt < 1200) {
        setStatus("Пожалуйста, попробуйте ещё раз.", "error");
        return;
      }

      if (!validateForm(form)) {
        setStatus("Проверьте поля и подтвердите согласие.", "error");
        return;
      }

      try {
        setStatus("Отправляем…", "pending");

        const name = String(form.elements.namedItem("name")?.value || "").trim();
        const phone = String(form.elements.namedItem("phone")?.value || "").trim();
        const comment = String(form.elements.namedItem("comment")?.value || "").trim();

        const payload = {
          name,
          phone,
          comment,
          chat_id: TARGET_GROUP_ID,
          source: "site_modal",
          page_url: window.location.href,
          user_agent: navigator.userAgent,
        };

        await postJson(getLeadEndpoint(), payload, 12_000);

        setStatus("Заявка отправлена. Мы свяжемся с вами.", "success");
        form.reset();

        window.setTimeout(() => close(), 900);
      } catch (err) {
        setStatus("Не удалось отправить. Попробуйте позже.", "error");
      }
    });
  }
}
