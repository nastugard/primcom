import { isCookieAccepted } from "./cookies.js";

const YANDEX_METRIKA_ID = 109674829;
const YANDEX_METRIKA_SRC = `https://mc.yandex.ru/metrika/tag.js?id=${YANDEX_METRIKA_ID}`;

let isStarted = false;

function startYandexMetrika() {
  if (isStarted) return;
  isStarted = true;

  window.dataLayer = window.dataLayer || [];

  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () {
      (m[i].a = m[i].a || []).push(arguments);
    };
    m[i].l = 1 * new Date();
    for (let j = 0; j < document.scripts.length; j += 1) {
      if (document.scripts[j].src === r) return;
    }
    k = e.createElement(t);
    a = e.getElementsByTagName(t)[0];
    k.async = 1;
    k.src = r;
    a.parentNode.insertBefore(k, a);
  })(window, document, "script", YANDEX_METRIKA_SRC, "ym");

  window.ym(YANDEX_METRIKA_ID, "init", {
    ssr: true,
    webvisor: true,
    clickmap: true,
    ecommerce: "dataLayer",
    referrer: document.referrer,
    url: location.href,
    accurateTrackBounce: true,
    trackLinks: true,
  });
}

export function trackYandexGoal(goalName, params) {
  if (typeof window.ym !== "function") return;

  window.ym(YANDEX_METRIKA_ID, "reachGoal", goalName, params);
}

// Единая точка подключения аналитики (Яндекс Метрика).
// Подключаем скрипты только после согласия на cookies.
export function initAnalytics() {
  if (isCookieAccepted()) {
    startYandexMetrika();
    return;
  }

  window.addEventListener("cookie:accepted", () => startYandexMetrika(), { once: true });
}
