export function initAnimations() {
  if (!window.gsap) return;
  const { gsap } = window;

  const st = window.ScrollTrigger;
  const obs = window.Observer;

  if (st) gsap.registerPlugin(st);
  if (obs) gsap.registerPlugin(obs);

  const mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: reduce)", () => {
    return () => {};
  });

  mm.add("(prefers-reduced-motion: no-preference)", () => {
    const hero = document.querySelector(".hero");
    const heroBg = document.querySelector(".hero__bg");

    if (hero) {
      const heroTl = gsap.timeline({ defaults: { ease: "power2.out" } });
      heroTl
        .from(".hero__kicker", { autoAlpha: 0, y: 10, duration: 0.6 }, 0)
        .from(".hero__title", { autoAlpha: 0, y: 18, duration: 0.75 }, 0.05)
        .from(".hero__lead", { autoAlpha: 0, y: 14, duration: 0.65 }, 0.15)
        .from(".hero__actions", { autoAlpha: 0, y: 10, duration: 0.6 }, 0.25)
        .from(".hero-strip", { autoAlpha: 0, y: 10, duration: 0.7, clearProps: "transform" }, 0.35);
    }

    if (hero && heroBg && window.ScrollTrigger) {
      gsap.to(heroBg, {
        scale: 1.06,
        yPercent: 6,
        ease: "none",
        scrollTrigger: {
          trigger: hero,
          start: "top top",
          end: "bottom top",
          scrub: true,
        },
      });
    }

    const revealTargets = [
      ".section__title",
      ".section__lead",
      ".info-card",
      ".review-card",
      ".vk-video",
    ];

    if (window.ScrollTrigger) {
      gsap.utils.toArray(revealTargets.join(",")).forEach((el) => {
        gsap.from(el, {
          autoAlpha: 0,
          y: 16,
          duration: 0.7,
          ease: "power2.out",
          scrollTrigger: {
            trigger: el,
            start: "top 85%",
            toggleActions: "play none none none",
          },
        });
      });

      const steps = document.querySelector(".steps");
      if (steps) {
        const playSteps = () => {
          gsap.fromTo(
            ".steps .step",
            { autoAlpha: 0, y: 18 },
            {
              autoAlpha: 1,
              y: 0,
              duration: 0.6,
              stagger: 0.12,
              ease: "power2.out",
              overwrite: true,
            }
          );
        };

        const trig = window.ScrollTrigger.create({
          trigger: steps,
          start: "top 80%",
          onEnter: playSteps,
          onEnterBack: playSteps,
          once: true,
        });

        const r = steps.getBoundingClientRect();
        if (r.bottom > 0 && r.top < window.innerHeight * 0.9) {
          playSteps();
          trig.kill();
        }
      }
    }

    mm.add("(min-width: 861px)", () => {
      const buttons = gsap.utils.toArray(".btn");
      const handlers = [];
      buttons.forEach((btn) => {
        const xTo = gsap.quickTo(btn, "x", { duration: 0.35, ease: "power3.out" });
        const yTo = gsap.quickTo(btn, "y", { duration: 0.35, ease: "power3.out" });

        const onMove = (e) => {
          const r = btn.getBoundingClientRect();
          const rx = (e.clientX - (r.left + r.width / 2)) / r.width;
          const ry = (e.clientY - (r.top + r.height / 2)) / r.height;
          xTo(rx * 8);
          yTo(ry * 6);
        };

        const onLeave = () => {
          xTo(0);
          yTo(0);
        };

        btn.addEventListener("mousemove", onMove);
        btn.addEventListener("mouseleave", onLeave);

        handlers.push({ btn, onMove, onLeave, xTo, yTo });
      });

      return () => {
        handlers.forEach(({ btn, onMove, onLeave, xTo, yTo }) => {
          btn.removeEventListener("mousemove", onMove);
          btn.removeEventListener("mouseleave", onLeave);
          xTo(0);
          yTo(0);
        });
      };
    });

    return () => {
      // GSAP matchMedia сам корректно откатывает созданные в этом контексте анимации.
    };
  });
}
