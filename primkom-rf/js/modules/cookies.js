const STORAGE_KEY = "cookieAccepted";

export function initCookieNotice() {
  const banner = document.querySelector("[data-cookie]");
  const acceptBtn = document.querySelector("[data-cookie-accept]");

  if (!banner || !acceptBtn) return;

  const accepted = localStorage.getItem(STORAGE_KEY) === "1";
  if (!accepted) banner.hidden = false;

  acceptBtn.addEventListener("click", () => {
    localStorage.setItem(STORAGE_KEY, "1");
    banner.hidden = true;

    // Событие для запуска аналитики.
    window.dispatchEvent(new CustomEvent("cookie:accepted"));
  });
}

export function isCookieAccepted() {
  return localStorage.getItem(STORAGE_KEY) === "1";
}
