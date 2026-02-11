export function initScrollProgress() {
  if (!window.gsap || !window.ScrollTrigger) return;

  const { gsap } = window;
  gsap.registerPlugin(window.ScrollTrigger);

  let el = document.querySelector("[data-scroll-progress]");

  if (!el) {
    el = document.createElement("div");
    el.className = "scroll-progress";
    el.setAttribute("data-scroll-progress", "");
    document.body.appendChild(el);
  }

  gsap.set(el, { scaleX: 0, transformOrigin: "0% 50%" });

  const tween = gsap.to(el, {
    scaleX: 1,
    ease: "none",
    scrollTrigger: {
      trigger: document.documentElement,
      start: "top top",
      end: "bottom bottom",
      scrub: 0.2,
    },
  });

  return () => {
    tween.scrollTrigger && tween.scrollTrigger.kill();
    tween.kill();
  };
}
