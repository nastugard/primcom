export function initHeader() {
  const header = document.querySelector("[data-header]");
  if (!header) return;

  const root = document.documentElement;
  let lastY = window.scrollY;
  let ticking = false;
  let hidden = false;

  const setHeaderOffset = () => {
    const h = header.getBoundingClientRect().height;
    root.style.setProperty("--header-offset", `${Math.ceil(h + 12)}px`);
  };

  const applyScrollState = () => {
    const currentY = window.scrollY;
    const delta = currentY - lastY;

    header.classList.toggle("is-detached", currentY > 10);

    if (currentY <= 16) {
      hidden = false;
    } else if (delta > 6) {
      hidden = true;
    } else if (delta < -6) {
      hidden = false;
    }

    header.classList.toggle("is-hidden", hidden);
    lastY = currentY;
    setHeaderOffset();
    ticking = false;
  };

  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(applyScrollState);
  };

  setHeaderOffset();
  applyScrollState();

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", setHeaderOffset, { passive: true });
  window.addEventListener("orientationchange", setHeaderOffset, { passive: true });

  header.addEventListener("focusin", () => {
    hidden = false;
    header.classList.remove("is-hidden");
  });
}
