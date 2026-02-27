export function initTiltCards() {
  if (!window.gsap) return;

  const { gsap } = window;
  const mm = gsap.matchMedia();

  mm.add(
    "(pointer: fine) and (hover: hover) and (min-width: 861px) and (prefers-reduced-motion: no-preference)",
    () => {
      const cards = Array.from(
        document.querySelectorAll(".info-card, .review-card, .strip-card, .step")
      );

      const cleanups = [];

      cards.forEach((card) => {
        card.classList.add("tilt-card");

        card.style.setProperty("--mx", "50%");
        card.style.setProperty("--my", "50%");

        gsap.set(card, {
          transformPerspective: 900,
          transformStyle: "preserve-3d",
          transformOrigin: "50% 50%",
          force3D: true,
        });

        const rotXTo = gsap.quickTo(card, "rotateX", {
          duration: 0.35,
          ease: "power3.out",
          overwrite: "auto",
        });

        const rotYTo = gsap.quickTo(card, "rotateY", {
          duration: 0.35,
          ease: "power3.out",
          overwrite: "auto",
        });

        const onMove = (e) => {
          const r = card.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width;
          const py = (e.clientY - r.top) / r.height;

          const rx = (py - 0.5) * -8;
          const ry = (px - 0.5) * 10;

          rotXTo(rx);
          rotYTo(ry);

          card.style.setProperty("--mx", `${Math.round(px * 100)}%`);
          card.style.setProperty("--my", `${Math.round(py * 100)}%`);
        };

        const onEnter = () => {
          card.classList.add("is-tilting");
        };

        const onLeave = () => {
          card.classList.remove("is-tilting");
          rotXTo(0);
          rotYTo(0);
        };

        card.addEventListener("mousemove", onMove);
        card.addEventListener("mouseenter", onEnter);
        card.addEventListener("mouseleave", onLeave);

        cleanups.push(() => {
          card.removeEventListener("mousemove", onMove);
          card.removeEventListener("mouseenter", onEnter);
          card.removeEventListener("mouseleave", onLeave);
          card.classList.remove("tilt-card", "is-tilting");
          card.style.removeProperty("--mx");
          card.style.removeProperty("--my");
          gsap.set(card, { rotateX: 0, rotateY: 0 });
        });
      });

      return () => {
        cleanups.forEach((fn) => fn());
      };
    }
  );

  return () => {
    mm.kill();
  };
}
