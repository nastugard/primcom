export function initScrollSmoother() {
  const root = document.documentElement;

  const wrapper = document.getElementById("smooth-wrapper");
  const content = document.getElementById("smooth-content");
  if (!wrapper || !content) {
    root.classList.remove("has-smoother");
    return null;
  }

  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (reduceMotion) {
    root.classList.remove("has-smoother");
    return null;
  }

  const coarsePointer = !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
  if (coarsePointer) {
    root.classList.remove("has-smoother");
    return null;
  }

  if (!window.gsap || !window.ScrollTrigger || !window.ScrollSmoother) {
    root.classList.remove("has-smoother");
    return null;
  }

  const { gsap } = window;
  gsap.registerPlugin(window.ScrollTrigger, window.ScrollSmoother);

  root.classList.add("has-smoother");

  window.ScrollTrigger.config({ ignoreMobileResize: true });

  const smoother = window.ScrollSmoother.create({
    smooth: 1,
    effects: true,
    smoothTouch: 0,
    ignoreMobileResize: true,
  });

  window.__smoother = smoother;

  return smoother;
}
