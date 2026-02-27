import { loadSharedComponents } from "./modules/components.js";
import { initHeader } from "./modules/header.js";
import { initPageBg } from "./modules/page-bg.js";

function safeInit(name, fn) {
  try {
    fn();
  } catch (err) {
    console.error(`[app] ${name} failed`, err);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    await loadSharedComponents();
  } catch (err) {
    console.error("[app] loadSharedComponents failed", err);
  }

  safeInit("initPageBg", initPageBg);
  safeInit("initHeader", initHeader);
});
