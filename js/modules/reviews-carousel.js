function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

export function initReviewsCarousel() {
  const root = document.querySelector('[data-carousel="reviews"]');
  if (!root) return;

  const track = root.querySelector("[data-carousel-track]");
  if (!track) return;

  const items = Array.from(track.children);
  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  if (!window.gsap) return;
  const { gsap } = window;

  let max = 0;
  const baseSpeed = 34;
  const speedState = { v: reduceMotion ? 0 : baseSpeed };
  let speedTween = null;
  let tickerOn = false;
  let lastT = 0;
  let isHovering = false;
  let hoveredCard = null;
  let wheelResumeTimer = 0;
  let scrollRaf = 0;

  const setSpeed = (v, duration) => {
    if (speedTween) speedTween.kill();
    speedTween = gsap.to(speedState, {
      v,
      duration,
      ease: "power2.out",
      overwrite: true,
    });
  };

  const stepForFirst = () => {
    const first = track.firstElementChild;
    const second = first ? first.nextElementSibling : null;
    if (!first) return 0;
    if (second) {
      const a = first.getBoundingClientRect();
      const b = second.getBoundingClientRect();
      return Math.max(0, b.left - a.left);
    }
    return Math.max(0, first.getBoundingClientRect().width);
  };

  const stepForLast = () => {
    const last = track.lastElementChild;
    const prev = last ? last.previousElementSibling : null;
    if (!last) return 0;
    if (prev) {
      const a = prev.getBoundingClientRect();
      const b = last.getBoundingClientRect();
      return Math.max(0, b.left - a.left);
    }
    return Math.max(0, last.getBoundingClientRect().width);
  };

  const shiftFirstToEnd = () => {
    const first = track.firstElementChild;
    if (!first) return;
    const step = stepForFirst();
    if (step <= 0) return;
    track.appendChild(first);
    root.scrollLeft = clamp(root.scrollLeft - step, 0, max);
  };

  const shiftLastToStart = () => {
    const last = track.lastElementChild;
    const first = track.firstElementChild;
    if (!last || !first) return;
    const step = stepForLast();
    if (step <= 0) return;
    track.insertBefore(last, first);
    root.scrollLeft = clamp(root.scrollLeft + step, 0, max);
  };

  const normalize = () => {
    if (max <= 0) return;

    let guard = 0;
    while (guard < 200) {
      const step = stepForFirst();
      if (step > 0 && root.scrollLeft >= step) {
        shiftFirstToEnd();
        guard += 1;
        continue;
      }
      break;
    }
  };

  const applyDelta = (delta) => {
    if (!delta) return;
    if (max <= 0) return;

    let guard = 0;
    while (delta < 0 && root.scrollLeft <= 1 && guard < 10) {
      shiftLastToStart();
      guard += 1;
    }

    root.scrollLeft = clamp(root.scrollLeft + delta, 0, max);
    normalize();
  };

  const onTick = () => {
    if (reduceMotion) return;
    if (max <= 0) return;

    const t = gsap.ticker.time;
    const dt = t - lastT;
    lastT = t;
    if (!Number.isFinite(dt) || dt <= 0) return;
    if (speedState.v === 0) return;

    applyDelta(speedState.v * dt);
  };

  const startAuto = () => {
    if (reduceMotion) return;
    if (tickerOn) return;
    tickerOn = true;
    lastT = gsap.ticker.time;
    gsap.ticker.add(onTick);
    setSpeed(baseSpeed, 0.0);
  };

  const stopAuto = () => {
    if (speedTween) speedTween.kill();
    speedTween = null;
    speedState.v = 0;
    if (tickerOn) {
      gsap.ticker.remove(onTick);
      tickerOn = false;
    }
  };

  const pauseAuto = () => {
    if (reduceMotion) return;
    setSpeed(0, 0.20);
  };

  const resumeAuto = () => {
    if (reduceMotion) return;
    if (isHovering) return;
    setSpeed(baseSpeed, 0.75);
  };

  const compute = () => {
    max = Math.max(0, root.scrollWidth - root.clientWidth);
    root.classList.toggle("is-locked", max <= 0);
    root.classList.toggle("is-infinite", max > 0);

    if (max > 0) {
      startAuto();
      normalize();
    } else {
      stopAuto();
    }
  };

  compute();
  window.addEventListener("resize", compute, { passive: true });

  const onWheel = (e) => {
    if (max <= 0) return;

    const absX = Math.abs(e.deltaX);
    const absY = Math.abs(e.deltaY);
    const raw = e.shiftKey && absX < absY ? e.deltaY : absX > absY ? e.deltaX : 0;
    if (raw === 0) return;

    e.preventDefault();

    pauseAuto();
    window.clearTimeout(wheelResumeTimer);
    wheelResumeTimer = window.setTimeout(() => resumeAuto(), 550);

    applyDelta(raw);
  };

  root.addEventListener("wheel", onWheel, { passive: false });

  const finePointer = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  let isDown = false;
  let downX = 0;
  let downScroll = 0;

  const onPointerDown = (e) => {
    if (!finePointer) return;
    if (e.button !== 0) return;
    isDown = true;
    downX = e.clientX;
    downScroll = root.scrollLeft;
    pauseAuto();
    root.setPointerCapture && root.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e) => {
    if (!isDown) return;
    const dx = e.clientX - downX;
    root.scrollLeft = clamp(downScroll - dx, 0, max);
    normalize();
    if (Math.abs(dx) > 2) e.preventDefault();
  };

  const onPointerUp = (e) => {
    if (!isDown) return;
    isDown = false;
    root.releasePointerCapture && root.releasePointerCapture(e.pointerId);
    window.clearTimeout(wheelResumeTimer);
    wheelResumeTimer = window.setTimeout(() => resumeAuto(), 550);
  };

  const allCards = Array.from(track.querySelectorAll(".review-card"));
  const onEnterCard = (card) => {
    if (!card) return;
    isHovering = true;
    hoveredCard = card;
    pauseAuto();
    gsap.killTweensOf(card);
    gsap.to(card, { scale: 1.035, duration: 0.22, ease: "power2.out" });
  };

  const onLeaveCard = (card) => {
    if (!card) return;
    gsap.killTweensOf(card);
    gsap.to(card, { scale: 1, duration: 0.22, ease: "power2.out" });
    if (hoveredCard === card) hoveredCard = null;
    isHovering = false;
    resumeAuto();
  };

  const fineHover = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  if (fineHover) {
    const handleEnter = (e) => onEnterCard(e.currentTarget);
    const handleLeave = (e) => onLeaveCard(e.currentTarget);

    allCards.forEach((card) => {
      card.addEventListener("mouseenter", handleEnter);
      card.addEventListener("mouseleave", handleLeave);
    });

    root.__reviewsHoverHandlers = { handleEnter, handleLeave };
  }

  root.addEventListener("pointerdown", onPointerDown, { passive: true });
  root.addEventListener("pointermove", onPointerMove, { passive: false });
  root.addEventListener("pointerup", onPointerUp, { passive: true });
  root.addEventListener("pointercancel", onPointerUp, { passive: true });

  const onScroll = () => {
    if (scrollRaf) return;
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = 0;
      normalize();
    });
  };

  root.addEventListener("scroll", onScroll, { passive: true });

  return () => {
    root.removeEventListener("wheel", onWheel);
    root.removeEventListener("pointerdown", onPointerDown);
    root.removeEventListener("pointermove", onPointerMove);
    root.removeEventListener("pointerup", onPointerUp);
    root.removeEventListener("pointercancel", onPointerUp);
    root.removeEventListener("scroll", onScroll);
    window.clearTimeout(wheelResumeTimer);
    if (scrollRaf) window.cancelAnimationFrame(scrollRaf);
    if (speedTween) speedTween.kill();
    if (tickerOn) {
      gsap.ticker.remove(onTick);
      tickerOn = false;
    }
    if (fineHover) {
      const handlers = root.__reviewsHoverHandlers;
      allCards.forEach((card) => {
        if (handlers) {
          card.removeEventListener("mouseenter", handlers.handleEnter);
          card.removeEventListener("mouseleave", handlers.handleLeave);
        }
      });
      delete root.__reviewsHoverHandlers;
    }
    window.removeEventListener("resize", compute);
  };
}
