import { isCookieAccepted } from "./cookies.js";

// Архитектурная заготовка под аналитику (Яндекс Метрика / Google Analytics).
// Подключаем скрипты только после согласия на cookies.
export function initAnalytics() {
  const start = () => {
    // TODO (этап 4): добавить реальную интеграцию.
    // Пример:
    // - create <script> for Yandex Metrika
    // - create <script> for Google Analytics
  };

  if (isCookieAccepted()) {
    start();
    return;
  }

  window.addEventListener("cookie:accepted", () => start(), { once: true });
}
