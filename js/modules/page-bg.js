const clamp01 = (v) => Math.max(0, Math.min(1, v));

export function initPageBg() {
  const bg = document.querySelector(".page-bg");
  if (!bg) return;

  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (reduceMotion) return;

  const finePointer = !!(window.matchMedia && window.matchMedia("(pointer: fine)").matches);

  let raf = 0;
  let tx = 0.5;
  let ty = 0.22;

  const apply = () => {
    raf = 0;

    const x = (tx * 100).toFixed(2) + "%";
    const y = (ty * 100).toFixed(2) + "%";

    const sx = (tx * 100).toFixed(2) + "%";
    const sy = (Math.min(0.72, ty + 0.10) * 100).toFixed(2) + "%";

    bg.style.setProperty("--bg-x", x);
    bg.style.setProperty("--bg-y", y);
    bg.style.setProperty("--bg-sx", sx);
    bg.style.setProperty("--bg-sy", sy);
  };

  const schedule = () => {
    if (raf) return;
    raf = window.requestAnimationFrame(apply);
  };

  const setFromMouse = (e) => {
    const nx = clamp01(e.clientX / Math.max(1, window.innerWidth));
    const ny = clamp01(e.clientY / Math.max(1, window.innerHeight));

    tx = 0.5 + (nx - 0.5) * 0.18;
    ty = 0.20 + (ny - 0.5) * 0.16;
    schedule();
  };

  const setFromScroll = () => {
    const smoother = window.__smoother;

    const scrollY = smoother && typeof smoother.scrollTop === "function" ? smoother.scrollTop() : window.scrollY;
    const contentEl = smoother && typeof smoother.content === "function" ? smoother.content() : null;

    const doc = document.documentElement;
    const scrollH = contentEl ? contentEl.scrollHeight : doc.scrollHeight;
    const max = Math.max(1, scrollH - window.innerHeight);

    const p = clamp01(scrollY / max);

    tx = 0.52 + Math.sin(p * Math.PI * 2) * 0.06;
    ty = 0.18 + p * 0.44;
    schedule();
  };

  apply();

  if (finePointer) {
    window.addEventListener("mousemove", setFromMouse, { passive: true });
  } else {
    window.addEventListener("scroll", setFromScroll, { passive: true });
    window.addEventListener("resize", setFromScroll, { passive: true });
    setFromScroll();
  }

  return () => {
    if (finePointer) {
      window.removeEventListener("mousemove", setFromMouse);
    } else {
      window.removeEventListener("scroll", setFromScroll);
      window.removeEventListener("resize", setFromScroll);
    }
    if (raf) window.cancelAnimationFrame(raf);
  };
}
