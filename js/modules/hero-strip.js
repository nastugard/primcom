function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function closest(points, value) {
  if (!points.length) return value;
  let best = points[0];
  let bestD = Math.abs(best - value);
  for (let i = 1; i < points.length; i += 1) {
    const d = Math.abs(points[i] - value);
    if (d < bestD) {
      best = points[i];
      bestD = d;
    }
  }
  return best;
}

export function initHeroStrip() {
  const el = document.querySelector("[data-strip]");
  if (!el) return;

  const progress = document.querySelector("[data-strip-progress]");
  const progressBar = progress ? progress.querySelector("[data-strip-progress-bar]") : null;

  if (!window.gsap) return;
  const { gsap } = window;

  const mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: no-preference)", () => {
    const items = Array.from(el.children);
    let max = 0;
    let snapPoints = [];

    let raf = 0;
    const updateProgress = () => {
      raf = 0;
      if (!progressBar) return;
      const p = max <= 0 ? 0 : el.scrollLeft / max;
      progressBar.style.transform = `scaleX(${Math.max(0, Math.min(1, p))})`;
    };

    const scheduleProgress = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(updateProgress);
    };

    const compute = () => {
      max = Math.max(0, el.scrollWidth - el.clientWidth);
      el.scrollLeft = clamp(el.scrollLeft, 0, max);
      snapPoints = items
        .map((node) => clamp(node.offsetLeft, 0, max))
        .filter((v, idx, arr) => arr.indexOf(v) === idx);

      scheduleProgress();
    };

    const snapToClosest = (velocityX) => {
      if (!snapPoints.length) return;
      const projected = clamp(el.scrollLeft - velocityX * 280, 0, max);
      const target = closest(snapPoints, projected);
      gsap.to(el, { scrollLeft: target, duration: 0.85, ease: "power3.out", onUpdate: updateProgress });
    };

    compute();
    window.addEventListener("resize", compute, { passive: true });

    const onWheel = (e) => {
      const absX = Math.abs(e.deltaX);
      const absY = Math.abs(e.deltaY);
      const raw = e.shiftKey && absX < absY ? e.deltaY : absX > absY ? e.deltaX : 0;
      if (raw === 0) return;

      const next = el.scrollLeft + raw;
      const willClamp = next < 0 || next > max;
      if (willClamp) return;

      e.preventDefault();
      gsap.killTweensOf(el);

      el.scrollLeft = clamp(next, 0, max);

      window.clearTimeout(onWheel._t);
      onWheel._t = window.setTimeout(() => {
        snapToClosest(0);
      }, 140);
    };

    const finePointer = window.matchMedia && window.matchMedia("(pointer: fine) and (hover: hover)").matches;
    const desktopLayout = window.matchMedia && window.matchMedia("(min-width: 861px)").matches;
    const allowFineEnhancements = finePointer && desktopLayout;

    if (allowFineEnhancements) {
      el.addEventListener("wheel", onWheel, { passive: false });
    }

    el.addEventListener("scroll", scheduleProgress, { passive: true });

    const allowDrag = allowFineEnhancements && max > 0 && !!window.Observer;

    let obs = null;
    if (allowDrag) {
      gsap.registerPlugin(window.Observer);
      obs = window.Observer.create({
        target: el,
        type: "pointer",
        lockAxis: true,
        preventDefault: true,
        onPress: () => {
          gsap.killTweensOf(el);
        },
        onChangeX: (self) => {
          el.scrollLeft = clamp(el.scrollLeft + self.deltaX, 0, max);
          scheduleProgress();
        },
        onRelease: (self) => {
          snapToClosest(self.velocityX);
        },
      });
    }

    return () => {
      if (obs) obs.kill();
      if (allowFineEnhancements) el.removeEventListener("wheel", onWheel);
      el.removeEventListener("scroll", scheduleProgress);
      window.removeEventListener("resize", compute);
      if (raf) window.cancelAnimationFrame(raf);
    };
  });
}
