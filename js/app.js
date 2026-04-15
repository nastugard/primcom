import { loadSharedComponents } from "./modules/components.js";
import { initHeader } from "./modules/header.js";
import { initCookieNotice } from "./modules/cookies.js";
import { initLeadModal } from "./modules/modal-lead.js";
import { initAnalytics } from "./modules/analytics.js";
import { initAnimations } from "./modules/animations.js";
import { initHeroStrip } from "./modules/hero-strip.js";
import { initTiltCards } from "./modules/tilt-cards.js";
import { initScrollProgress } from "./modules/scroll-progress.js";
import { initScrollSmoother } from "./modules/scroll-smoother.js";
import { initPageBg } from "./modules/page-bg.js";
import { initAutoIzKitaya } from "./modules/auto-iz-kitaya.js?v=20260411-catalog-cache-1";
import { initLatestCarsHome } from "./modules/latest-cars-home.js?v=20260412-home-list-cache-1";
import { initManualMarketCars } from "./modules/auto-manual-market.js?v=20260411-catalog-cache-1";
import { initVkClipsCarousel } from "./modules/vk-clips-carousel.js";
import { initPerformanceMode, loadEnhancementRuntime } from "./modules/performance-mode.js";
import { initImportCalculator } from "./modules/import-calculator.js?v=20260415-import-calculator-1";

function safeInit(name, fn) {
  try {
    fn();
  } catch (err) {
    console.error(`[app] ${name} failed`, err);
  }
}

// Единая точка входа.
// GSAP и плагины догружаются только там, где они реально нужны.
document.addEventListener("DOMContentLoaded", async () => {
  const performanceProfile = initPerformanceMode();

  try {
    await loadSharedComponents();
  } catch (err) {
    console.error("[app] loadSharedComponents failed", err);
  }

  try {
    await loadEnhancementRuntime(performanceProfile);
  } catch (err) {
    console.error("[app] loadEnhancementRuntime failed", err);
  }

  safeInit("initPageBg", initPageBg);
  safeInit("initHeader", initHeader);
  safeInit("initCookieNotice", initCookieNotice);
  safeInit("initLeadModal", initLeadModal);
  safeInit("initAutoIzKitaya", initAutoIzKitaya);
  safeInit("initManualMarketCars", initManualMarketCars);
  safeInit("initLatestCarsHome", initLatestCarsHome);
  safeInit("initVkClipsCarousel", initVkClipsCarousel);
  safeInit("initImportCalculator", initImportCalculator);

  if (!performanceProfile.isLite) {
    safeInit("initScrollSmoother", initScrollSmoother);
    safeInit("initAnimations", initAnimations);
    safeInit("initHeroStrip", initHeroStrip);
    safeInit("initTiltCards", initTiltCards);
    safeInit("initScrollProgress", initScrollProgress);
  }

  // Аналитика включается после согласия на cookies (логика в modules/analytics.js).
  safeInit("initAnalytics", initAnalytics);
});
