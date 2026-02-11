import { loadSharedComponents } from "./modules/components.js";
import { initHeader } from "./modules/header.js";
import { initCookieNotice } from "./modules/cookies.js";
import { initLeadModal } from "./modules/modal-lead.js";
import { initAnalytics } from "./modules/analytics.js";
import { initAnimations } from "./modules/animations.js";
import { initReviewsCarousel } from "./modules/reviews-carousel.js";
import { initHeroStrip } from "./modules/hero-strip.js";
import { initTiltCards } from "./modules/tilt-cards.js";
import { initScrollProgress } from "./modules/scroll-progress.js";
import { initScrollSmoother } from "./modules/scroll-smoother.js";
import { initPageBg } from "./modules/page-bg.js";
import { initAutoIzKitaya } from "./modules/auto-iz-kitaya.js";
import { initLatestCarsHome } from "./modules/latest-cars-home.js";

function safeInit(name, fn) {
  try {
    fn();
  } catch (err) {
    console.error(`[app] ${name} failed`, err);
  }
}

// Единая точка входа.
// Важно: GSAP подключается через CDN в HTML и доступен глобально (window.gsap).
document.addEventListener("DOMContentLoaded", async () => {
  try {
    await loadSharedComponents();
  } catch (err) {
    console.error("[app] loadSharedComponents failed", err);
  }

  safeInit("initPageBg", initPageBg);
  safeInit("initScrollSmoother", initScrollSmoother);
  safeInit("initHeader", initHeader);
  safeInit("initCookieNotice", initCookieNotice);
  safeInit("initLeadModal", initLeadModal);
  safeInit("initAutoIzKitaya", initAutoIzKitaya);
  safeInit("initLatestCarsHome", initLatestCarsHome);
  safeInit("initAnimations", initAnimations);
  safeInit("initReviewsCarousel", initReviewsCarousel);
  safeInit("initHeroStrip", initHeroStrip);
  safeInit("initTiltCards", initTiltCards);
  safeInit("initScrollProgress", initScrollProgress);

  // Аналитика включается после согласия на cookies (логика в modules/analytics.js).
  safeInit("initAnalytics", initAnalytics);
});
